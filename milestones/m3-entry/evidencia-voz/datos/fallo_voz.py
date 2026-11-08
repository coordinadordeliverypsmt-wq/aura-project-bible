"""Prueba de FALLO REAL de voz (MISION VOZ, §12): el turno sobrevive y lo dice.

No usa dobles: el adaptador real de Piper se apunta a una voz que no existe, que es exactamente lo que
ocurre si la USB se desmonta o el modelo se borra. Despues se restaura y se comprueba la recuperacion.

Uso:  python3 fallo_voz.py <salida.json>
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid

VOZ_REAL = "/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"
VOZ_ROTA = "/media/majo1230/AURORA_EXT/piper_voices/ESTA-VOZ-NO-EXISTE.onnx"
PREGUNTA = "¿qué sabes de mí?"  # ruta determinista del Core: aisla la voz del coste del modelo


async def _turno(orq, entrada: str, etiqueta: str, informe: dict) -> dict:
    tid = uuid.uuid4().hex[:12]
    t0 = time.time()
    await orq.handle_utterance("mauricio", entrada, tid)
    r = await orq.wait(tid, timeout=600)
    reg = {
        "etiqueta": etiqueta,
        "say": r["say"],
        "provider": r["provider"],
        "dominio": r["dominio"],
        "estatus": r["estatus"],
        "voz": r.get("voz", "(ausente)"),
        "total_s": round(time.time() - t0, 2),
    }
    informe["turnos"].append(reg)
    print(f"[{etiqueta}] {reg['total_s']}s voz={reg['voz']} provider={reg['provider']}")
    print(f"          say={reg['say'][:110]!r}")
    return reg


async def _main() -> None:
    salida = sys.argv[1]
    informe: dict = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "turnos": [], "boot": []}
    datos = tempfile.mkdtemp(prefix="aura-fallo-voz-")
    audio = tempfile.mkdtemp(prefix="aura-fallo-audio-")

    from aura_skeleton import observability as obs
    from aura_skeleton.composicion import Configuracion, componer

    real_log = obs.log

    def _espia(*a, **k):
        linea = " ".join(str(x) for x in a)
        if "voz:" in linea:
            informe["boot"].append(linea)
        return real_log(*a, **k)

    obs.log = _espia

    # ---- FASE 1: la voz esta ROTA (ruta inexistente, como si la USB se hubiera ido) ----
    os.environ["AURA_PIPER_VOICE"] = VOZ_ROTA
    s = componer(Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=True))
    s.orquestador.voice._out = audio
    roto = await _turno(s.orquestador, PREGUNTA, "voz-rota", informe)

    # ---- FASE 2: se restaura la voz. El MISMO sistema debe volver a hablar ----
    s.orquestador.voice._voice = VOZ_REAL
    sano = await _turno(s.orquestador, PREGUNTA, "voz-restaurada", informe)

    informe["audios"] = [
        {"fichero": f, "bytes": os.path.getsize(os.path.join(audio, f))} for f in sorted(os.listdir(audio))
    ]
    informe["veredicto"] = {
        "respuesta_conservada_con_voz_rota": bool(roto["say"].strip()),
        "fallo_observable": roto["voz"] == "no_disponible",
        "turno_completado": roto["provider"] == "core",
        "recuperacion": sano["voz"] == "ok",
        "mismo_texto_en_ambos": roto["say"] == sano["say"],
        "audio_solo_tras_restaurar": len(informe["audios"]) == 1,
    }
    print("\nVEREDICTO:", json.dumps(informe["veredicto"], ensure_ascii=False))

    with open(salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2, default=str)
    print(f"Informe -> {salida}")


if __name__ == "__main__":
    asyncio.run(_main())
