"""Una FASE de la prueba de reinicio (MISION VOZ, §13). Proceso nuevo cada vez: sin estado heredado.

Uso:  python3 fase_reinicio.py <etiqueta> <salida.json> [ruta_wav]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid


async def _main() -> None:
    etiqueta, salida = sys.argv[1], sys.argv[2]
    wav = sys.argv[3] if len(sys.argv) > 3 else None
    datos = tempfile.mkdtemp(prefix="aura-reinicio-")
    audio = tempfile.mkdtemp(prefix="aura-reinicio-audio-")

    from aura_skeleton import observability as obs
    from aura_skeleton.composicion import Configuracion, componer

    boot: list[str] = []
    real_log = obs.log

    def _espia(*a, **k):
        linea = " ".join(str(x) for x in a)
        if "voz:" in linea:
            boot.append(linea)
        return real_log(*a, **k)

    obs.log = _espia

    informe: dict = {
        "etiqueta": etiqueta,
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "usb_montada": os.path.ismount("/media/majo1230/AURORA_EXT"),
        "voz_declarada": os.environ.get("AURA_PIPER_VOICE", "(sin declarar)"),
        "voz_existe": os.path.isfile(os.environ.get("AURA_PIPER_VOICE", "")),
        "hf_home": os.environ.get("HF_HOME", "(sin declarar)"),
        "pid": os.getpid(),
    }

    s = componer(Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=True))
    s.orquestador.voice._out = audio
    informe["boot_voz"] = boot

    async def turno(entrada: str, nombre: str) -> None:
        tid = uuid.uuid4().hex[:12]
        t0 = time.time()
        try:
            await s.orquestador.handle_utterance("mauricio", entrada, tid)
            r = await s.orquestador.wait(tid, timeout=600)
            informe[nombre] = {
                "say": r["say"], "provider": r["provider"], "dominio": r["dominio"],
                "estatus": r["estatus"], "voz": r.get("voz", "(ausente)"),
                "total_s": round(time.time() - t0, 2),
            }
        except Exception as e:  # noqa: BLE001 — se registra para el informe
            informe[nombre] = {"excepcion": f"{type(e).__name__}: {e}"}
        print(f"  [{nombre}] {json.dumps(informe[nombre], ensure_ascii=False)[:180]}")

    await turno("¿qué sabes de mí?", "turno_texto")
    if wav:
        await turno(wav, "turno_audio")

    informe["audios"] = sorted(os.listdir(audio))
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(_main())
