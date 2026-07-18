"""Rendimiento: latencia estructural del turno y del bus (Bible 2.5 / 7.2).
NOTA: con proveedor MOCK; la latencia REAL (HC-1) se valida en hardware objetivo (D24)."""

import time

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.contracts import Event
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


@pytest.mark.asyncio
async def test_latencia_turno_estructural():
    async def yes(a, args, t):
        return True

    orch = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([MockProvider("b", 5, healthy=True)], 1200),
        PermissionManager(yes),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    await orch.handle_utterance("u", "Enciende la luz", "T")
    res = await orch.wait("T")
    # cota estructural amplia (mock): el overhead de orquestacion no debe explotar
    assert res["latency_ms"] < 500


@pytest.mark.asyncio
async def test_bus_overhead_bajo():
    bus = InProcessEventBus()

    async def h(ev):
        pass

    bus.subscribe("perception.turn_end", h)
    t0 = time.perf_counter()
    for _ in range(200):
        await bus.publish(Event("perception.turn_end", "T", "u", {}, event_id="e" + str(time.perf_counter())))
    dt = (time.perf_counter() - t0) * 1000 / 200
    assert dt < 5.0  # < 5ms por evento in-process
