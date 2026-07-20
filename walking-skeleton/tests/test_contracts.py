"""Verificacion de contratos (Bible 3.3/3.4): las implementaciones cumplen los Protocolos."""

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.contracts import Adapter, EventBus, MemoryStore, ModelProvider, VoiceAdapter
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import MockProvider


def test_bus_cumple_contrato():
    assert isinstance(InProcessEventBus(), EventBus)


def test_memoria_cumple_contrato():
    assert isinstance(SimpleMemory(), MemoryStore)


def test_proveedor_cumple_contrato():
    assert isinstance(MockProvider("x", 1), ModelProvider)


def test_adaptador_cumple_contrato():
    assert isinstance(HomeAssistantMock(), Adapter)


def test_voz_mock_cumple_contrato():
    """T2.b: el doble de voz cumple el contrato formal, no solo la convencion."""
    from aura_skeleton.adapters.voice import VoiceAdapterMock

    assert isinstance(VoiceAdapterMock(), VoiceAdapter)


def test_voz_real_cumple_contrato():
    """T2.b: la implementacion real (Whisper+Piper) cumple el MISMO contrato que el doble.

    Es la comprobacion que da valor al Protocol: garantiza que sustituir el mock por el
    stack real no cambia la interfaz que el orquestador consume.
    """
    from aura_skeleton.adapters.voice_real import WhisperPiperVoice

    assert isinstance(WhisperPiperVoice(), VoiceAdapter)
