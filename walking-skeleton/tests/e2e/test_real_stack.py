"""E2E stack real (D24). Se SALTAN si faster-whisper/piper/ollama/nats no estan disponibles.
En el hardware objetivo, validan la sustitucion de mocks por productos reales tras el mismo contrato."""

import importlib.util
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
