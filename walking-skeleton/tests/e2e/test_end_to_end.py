"""E2E: turno completo por el bus in-process (Bible 3.2 flujo extremo a extremo)."""

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


def _mk(confirm):
    bus = InProcessEventBus()
    orch = Orchestrator(
        bus,
        SimpleMemory(),
        ModelRouter([MockProvider("b", 5, healthy=True)], 1200),
        PermissionManager(confirm),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    return orch


@pytest.mark.asyncio
async def test_verde_ejecuta():
    async def yes(a, args, t):
        return True

    orch = _mk(yes)
    await orch.handle_utterance("u", "Enciende la luz de la sala", "T1")
    res = await orch.wait("T1")
    assert "ejecutada" in res["say"]


@pytest.mark.asyncio
async def test_roja_denegada_no_ejecuta():
    async def no(a, args, t):
        return False

    orch = _mk(no)
    await orch.handle_utterance("u", "Elimina el archivo de impuestos", "T2")
    res = await orch.wait("T2")
    assert "No ejecute" in res["say"]
