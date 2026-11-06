"""Verificación funcional del chat — misión §12 (10 casos) + §13 (límites de la gramática).

Registra por turno: ruta, quién responde, llamadas al LLM, tiempo, estado, si hubo escritura en memoria
y quién tuvo la autoridad. El contador envuelve al proveedor real SIN tocar el código de AURA.

El caso 10 entra por AUDIO REAL (WAV sintetizado con Piper), no por texto.
El caso 11 es OBSERVACIÓN de una limitación conocida: no se cambia la gramática, solo se mira qué hace.

Uso:  python3 chat_10.py <salida.json>
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

VOZ = "/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"


class _Contador:
    def __init__(self, real) -> None:
        self._real = real
        self.name = real.name
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return await self._real.infer(prompt, modo)


async def _main() -> None:
    salida = sys.argv[1]
    datos = tempfile.mkdtemp(prefix="aura-chat10-")
    audio_dir = tempfile.mkdtemp(prefix="aura-chat10-audio-")

    from aura_skeleton.composicion import Configuracion, componer

    config = Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=True)
    sistema = componer(config)
    orq = sistema.orquestador
    orq.voice._out = audio_dir
    contador = _Contador(orq.router.providers[0])
    orq.router.providers = [contador]

    # Caso 10: audio REAL. Se sintetiza con el mismo Piper del producto: es el "microfono".
    wav = os.path.join(audio_dir, "pregunta.wav")
    subprocess.run(["piper", "--model", VOZ, "--output_file", wav], input="¿Cómo me llamo?".encode(),
                   check=True, timeout=300)

    casos = [
        ("01_saludo", "Hola", "texto"),
        ("02_declaracion_propia", "Me llamo Mauricio", "texto"),
        ("03_consulta_memoria", "¿Cómo me llamo?", "texto"),
        ("04_memoria_inexistente", "¿Cómo se llama mi hija?", "texto"),
        ("05_matematica_determinista", "si tengo 4 manzanas y me como una cuantas me quedan", "texto"),
        ("06_conocimiento_general", "el cielo de qué color es", "texto"),
        ("07_sensible_persona_real", "quién es Simón Bolívar", "texto"),
        ("08_requiere_llm", "por qué flotan los barcos", "texto"),
        ("09_hecho_propio_2", "mi color favorito es el verde", "texto"),
        ("10_voz_a_conversacion", wav, "audio"),
        ("11_limite_conocido_observacion", "tomo ibuprofeno", "texto"),
    ]

    informe: dict = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modelo": config.modelo,
        "voz": os.environ.get("AURA_PIPER_VOICE", "(sin declarar)"),
        "turnos": [],
    }

    for etiqueta, entrada, via in casos:
        antes_llm = contador.llamadas
        antes_mem = len(await sistema.modelo_usuario.ver("mauricio"))
        tid = uuid.uuid4().hex[:12]
        t0 = time.time()
        await orq.handle_utterance("mauricio", entrada, tid)
        r = await orq.wait(tid, timeout=1800)
        despues_mem = len(await sistema.modelo_usuario.ver("mauricio"))
        reg = {
            "caso": etiqueta,
            "via": via,
            "entrada": entrada if via == "texto" else os.path.basename(entrada),
            "ruta": r["dominio"] or ("llm" if r["provider"] != "core" else "core"),
            "quien_responde": "CORE" if r["provider"] == "core" else f"MODELO ({r['provider']})",
            "llamadas_llm": contador.llamadas - antes_llm,
            "tiempo_s": round(time.time() - t0, 2),
            "estatus": r["estatus"],
            "escritura_en_memoria": despues_mem - antes_mem,
            "autoridad": "CORE" if r["provider"] == "core" else "CORE (marca la respuesta como propuesta)",
            "voz": r.get("voz", "(ausente)"),
            "say": r["say"],
        }
        informe["turnos"].append(reg)
        print(f"[{etiqueta}] {reg['tiempo_s']}s {reg['quien_responde']} ruta={reg['ruta']} "
              f"llm={reg['llamadas_llm']} mem={reg['escritura_en_memoria']:+d} estatus={reg['estatus']}")
        print(f"      {reg['say'][:140]!r}")

    informe["memoria_final"] = await sistema.modelo_usuario.ver("mauricio")
    informe["llamadas_llm_totales"] = contador.llamadas
    informe["audios_generados"] = sorted(f for f in os.listdir(audio_dir) if f.startswith("resp_"))
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nLLM: {contador.llamadas} llamadas en {len(casos)} turnos")
    print(f"memoria final ({len(informe['memoria_final'])}): "
          f"{[h['contenido'] for h in informe['memoria_final']]}")
    print(f"Informe -> {salida}")


if __name__ == "__main__":
    asyncio.run(_main())
