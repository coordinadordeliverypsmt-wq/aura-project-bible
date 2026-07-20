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


def test_contrato_adapter_firma():
    """H1 (M2.0): la firma declarada en el Protocol debe coincidir con la de las implementaciones.

    `isinstance` con `runtime_checkable` solo comprueba que el metodo EXISTA. Por eso el contrato
    pudo declarar `execute(command, args)` mientras el orquestador llamaba con cuatro argumentos,
    sin que ninguna prueba fallara. Esta comprobacion cierra ese hueco.
    """
    import inspect

    from aura_skeleton.contracts import Adapter

    esperada = [p for p in inspect.signature(Adapter.execute).parameters if p != "self"]
    for impl in (HomeAssistantMock,):
        real = [p for p in inspect.signature(impl.execute).parameters if p != "self"]
        assert real == esperada, f"{impl.__name__}.execute{tuple(real)} != contrato{tuple(esperada)}"


def test_contrato_adapter_refleja_la_llamada_real_del_orquestador():
    """El contrato debe admitir exactamente como el orquestador invoca al adaptador."""
    import inspect

    from aura_skeleton.contracts import Adapter

    params = [p for p in inspect.signature(Adapter.execute).parameters if p != "self"]
    assert params == ["command", "args", "trace_id", "event_id"]
