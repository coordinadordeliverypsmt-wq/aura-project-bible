"""Prueba REAL end-to-end de voz: audio -> STT -> Core -> say -> TTS (MISION VOZ, §11).

No usa mocks en ninguna etapa: Piper genera el audio de entrada, faster-whisper lo transcribe, el Core
decide, y Piper sintetiza la respuesta. Registra tiempos por etapa, memoria y rutas efectivas.

Uso:  python3 e2e_voz.py <salida.json> [--cognitivo]
"""

from __future__ import annotations

import asyncio
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
import uuid

VOZ = "/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"
FRASE_ENTRADA = "Hola AURA, me llamo Mauricio."
PREGUNTA_COGNITIVA = "¿Por qué el cielo es azul?"


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _memoria_libre_mb() -> int:
    with open("/proc/meminfo") as f:
        for linea in f:
            if linea.startswith("MemAvailable"):
                return int(linea.split()[1]) // 1024
    return -1


def _sintetizar_entrada(texto: str, destino: str) -> float:
    """Genera el WAV de ENTRADA con el mismo Piper que usa el producto. Es el 'microfono'."""
    t0 = time.time()
    subprocess.run(
        ["piper", "--model", VOZ, "--output_file", destino],
        input=texto.encode(), check=True, timeout=300,
    )
    return time.time() - t0


async def _main() -> None:
    salida_json = sys.argv[1]
    cognitivo = "--cognitivo" in sys.argv
    datos = tempfile.mkdtemp(prefix="aura-voz-e2e-")
    audio_dir = tempfile.mkdtemp(prefix="aura-voz-audio-")

    informe: dict = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rutas": {
            "piper_voice": VOZ,
            "hf_home": os.environ.get("HF_HOME", "(sin declarar)"),
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE", "0"),
            "modelo_llm": os.environ.get("AURA_LLM_MODEL", "(defecto)"),
            "datos": datos,
        },
        "memoria_libre_mb_inicio": _memoria_libre_mb(),
        "turnos": [],
    }

    wav_entrada = os.path.join(audio_dir, "entrada.wav")
    informe["tts_entrada_s"] = round(_sintetizar_entrada(FRASE_ENTRADA, wav_entrada), 2)
    informe["wav_entrada_bytes"] = os.path.getsize(wav_entrada)

    from aura_skeleton.composicion import Configuracion, componer

    t0 = time.time()
    sistema = componer(Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=True))
    informe["arranque_s"] = round(time.time() - t0, 2)
    orq = sistema.orquestador
    orq.voice._out = audio_dir  # el audio de salida va al temporal, no a /tmp/aura

    async def turno(entrada: str, etiqueta: str, timeout: float) -> dict:
        tid = uuid.uuid4().hex[:12]
        t_ini = time.time()
        await orq.handle_utterance("mauricio", entrada, tid)
        r = await orq.wait(tid, timeout=timeout)
        total = time.time() - t_ini
        marks = r.get("marks", {})
        registro = {
            "etiqueta": etiqueta,
            "entrada": entrada,
            "say": r["say"],
            "provider": r["provider"],
            "dominio": r["dominio"],
            "estatus": r["estatus"],
            "voz": r.get("voz", "(ausente)"),
            "total_s": round(total, 2),
            "marks_ms": {k: round(v, 1) for k, v in marks.items()},
            "latency_ms": round(r["latency_ms"], 1),
            "memoria_libre_mb": _memoria_libre_mb(),
        }
        informe["turnos"].append(registro)
        print(f"[{etiqueta}] {total:.1f}s  voz={registro['voz']}  provider={r['provider']}")
        print(f"          say={r['say'][:120]!r}")
        return registro

    # ---- TURNO 1: audio real -> STT real -> Core -> TTS real ------------------
    await turno(wav_entrada, "voz-completa-core", timeout=600)

    # ¿Sonó de verdad? El WAV de respuesta debe existir y pesar.
    audios = sorted(f for f in os.listdir(audio_dir) if f.startswith("resp_"))
    informe["audios_generados"] = [
        {"fichero": a, "bytes": os.path.getsize(os.path.join(audio_dir, a))} for a in audios
    ]

    # ---- TURNO 2: el Core recuerda lo que entró POR VOZ -----------------------
    await turno("¿cómo me llamo?", "memoria-tras-voz", timeout=600)

    # ---- TURNO 3 (opcional): ruta cognitiva con el modelo real ----------------
    if cognitivo:
        await turno(PREGUNTA_COGNITIVA, "cognitivo-real", timeout=1800)

    informe["memoria_libre_mb_fin"] = _memoria_libre_mb()
    informe["rss_max_mb"] = round(_rss_mb(), 1)
    informe["hechos_en_memoria"] = await sistema.modelo_usuario.ver("mauricio")

    with open(salida_json, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nInforme -> {salida_json}")


if __name__ == "__main__":
    asyncio.run(_main())
