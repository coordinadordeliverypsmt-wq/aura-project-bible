"""Verificacion de contratos (Bible 3.3/3.4): las implementaciones cumplen los Protocolos."""

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.contracts import Adapter, EventBus, MemoryStore, ModelProvider
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
