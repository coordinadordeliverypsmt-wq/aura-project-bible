#!/usr/bin/env python3
"""T2.a — Validacion del pipeline de voz por BUCLE CERRADO TTS -> STT.

Piper sintetiza una frase conocida a WAV; faster-whisper transcribe ESE WAV; se compara.

Por que este diseno (leccion de la auditoria T1): `stt()` devuelve el texto de entrada sin
transcribir cuando recibe texto plano. Una validacion que pasara texto pasaria sin ejecutar
Whisper jamas. Aqui la entrada es una RUTA A WAV, de modo que la rama de passthrough ni se toca:
la prueba solo puede pasar si el modelo transcribe de verdad.

Criterio: similitud por palabras, no igualdad literal. Todo STT comete errores menores de
puntuacion o acentuacion; exigir coincidencia exacta produciria una prueba fragil que fallaria
por la razon equivocada.
"""

import asyncio
import os
import sys
import time
import unicodedata

FRASE = "Hola, soy AURA, tu sistema operativo de inteligencia personal"
UMBRAL = 0.70


def _norm(t: str) -> list[str]:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [w for w in "".join(c if c.isalnum() or c.isspace() else " " for c in t).split() if w]


async def main() -> int:
    from aura_skeleton.adapters.voice_real import WhisperPiperVoice

    voz = WhisperPiperVoice(
        whisper_model=os.environ.get("AURA_WHISPER_MODEL", "base"),
        piper_voice=os.environ["AURA_PIPER_VOICE"],
        out_dir="/tmp/aura",
    )

    print(f"Frase original : {FRASE!r}")
    t0 = time.time()
    wav = await voz.tts(FRASE, "t2a")
    t_tts = (time.time() - t0) * 1000
    print(f"TTS            : {wav} ({os.path.getsize(wav)} bytes) en {t_tts:.0f} ms")

    t0 = time.time()
    texto = await voz.stt(wav, "t2a")
    t_stt = (time.time() - t0) * 1000
    print(f"STT transcribio: {texto!r} en {t_stt:.0f} ms")

    orig, trans = _norm(FRASE), _norm(texto)
    comunes = sum(1 for w in orig if w in trans)
    sim = comunes / len(orig) if orig else 0.0
    print(f"\nSimilitud      : {sim:.0%} ({comunes}/{len(orig)} palabras)  umbral={UMBRAL:.0%}")

    # Comprobacion anti-passthrough: la entrada fue una ruta .wav, no la frase.
    assert texto.strip() != wav, "STT devolvio la ruta: no hubo transcripcion (passthrough)"
    ok = sim >= UMBRAL
    print(f"RESULTADO      : {'PASS' if ok else 'FALLO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
