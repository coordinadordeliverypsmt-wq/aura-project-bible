"""E2E stack real (D24). Se SALTAN si faster-whisper/piper/ollama/nats no estan disponibles.
En el hardware objetivo, validan la sustitucion de mocks por productos reales tras el mismo contrato."""

import importlib.util
import os
import socket

import pytest


def _has(mod):
    return importlib.util.find_spec(mod) is not None


def _port(host, p):
    try:
        s = socket.create_connection((host, p), timeout=0.5)
        s.close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not (_has("faster_whisper") and _port("127.0.0.1", 11434) and _port("127.0.0.1", 4222)),
    reason="stack real ausente (faster-whisper/Ollama:11434/NATS:4222) — se valida en hardware objetivo (D24)",
)


@pytest.mark.asyncio
async def test_ollama_provider_cumple_contrato():
    from aura_skeleton.contracts import ModelProvider
    from aura_skeleton.modules.providers_real import OllamaProvider

    assert isinstance(OllamaProvider("ollama", "qwen2.5:3b"), ModelProvider)


@pytest.mark.asyncio
async def test_voz_real_cumple_contrato():
    from aura_skeleton.adapters.voice_real import WhisperPiperVoice

    v = WhisperPiperVoice()
    assert hasattr(v, "stt") and hasattr(v, "tts")


@pytest.mark.skipif(
    not (_has("faster_whisper") and os.environ.get("AURA_TEST_VOZ_REAL") == "1"),
    reason="requiere faster-whisper + AURA_TEST_VOZ_REAL=1 (tarda ~60 s en CPU)",
)
@pytest.mark.asyncio
async def test_bucle_cerrado_tts_stt():
    """T2.a — Piper sintetiza una frase; Whisper transcribe ESE WAV; se comparan.

    La entrada de `stt()` es una RUTA A WAV, no texto: la rama de passthrough del adaptador
    ni se toca, de modo que la prueba solo puede pasar si el modelo transcribe realmente
    (leccion de la auditoria T1). Criterio: similitud por palabras, no igualdad literal —
    exigir coincidencia exacta haria fallar la prueba por errores de puntuacion, que es
    fallar por la razon equivocada.

    No se ejecuta en el Quality Gate por defecto: tarda ~60 s en esta CPU.
    """
    import unicodedata

    from aura_skeleton.adapters.voice_real import WhisperPiperVoice

    def _norm(t):
        t = unicodedata.normalize("NFD", t.lower())
        t = "".join(c for c in t if unicodedata.category(c) != "Mn")
        return [w for w in "".join(c if c.isalnum() or c.isspace() else " " for c in t).split() if w]

    frase = "Hola, soy AURA, tu sistema operativo de inteligencia personal"
    voz = WhisperPiperVoice(whisper_model="base", piper_voice=os.environ["AURA_PIPER_VOICE"], out_dir="/tmp/aura")

    wav = await voz.tts(frase, "t2a")
    assert os.path.exists(wav) and os.path.getsize(wav) > 1000, "Piper no genero audio"

    texto = await voz.stt(wav, "t2a")
    assert texto.strip() != wav, "STT devolvio la ruta: no hubo transcripcion (passthrough)"

    orig, trans = _norm(frase), _norm(texto)
    sim = sum(1 for w in orig if w in trans) / len(orig)
    assert sim >= 0.70, f"similitud {sim:.0%} < 70% — original={frase!r} transcrito={texto!r}"
