"""E2E capacidad M1: flujo conversacional como producto (memoria persistente, HITL, kill switch)."""

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


async def _deny(action, args, tid):
    return False


def _orch(mem, ks):
    return Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([MockProvider("m", 3, healthy=True)], 1200),
        PermissionManager(_deny, kill_switch=ks),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )


@pytest.mark.asyncio
async def test_capacidad_conversacional_completa(tmp_path):
    mem_path = str(tmp_path / "mem.json")
    ks = KillSwitch(str(tmp_path / "KILL"))
    orch = _orch(PersistentMemory(mem_path), ks)

    # accion segura
    r = await _run(orch, "Enciende la luz de la sala")
    assert "ejecutada" in r["say"]
    # accion peligrosa rechazada (HITL)
    r = await _run(orch, "Elimina el archivo de impuestos")
    assert "No ejecute" in r["say"]
    # kill switch detiene todo
    ks.engage("emergencia")
    r = await _run(orch, "Enciende la luz de la sala")
    assert "kill switch activo" in r["say"]
    ks.disengage()

    # persistencia entre sesiones: nueva instancia carga del disco
    mem2 = PersistentMemory(mem_path)
    orch2 = _orch(mem2, ks)
    r = await _run(orch2, "Que acordamos sobre la luz de la sala?")
    assert "luz" in r["say"].lower()

    # recuperacion tras perdida
    b = mem2.backup()
    mem2._items = []
    mem2._persist()
    assert mem2.restore(b) is True
    assert await mem2.recall("mauricio", "luz")


async def _run(orch, text):
    import uuid

    tid = uuid.uuid4().hex[:12]
    await orch.handle_utterance("mauricio", text, tid)
    return await orch.wait(tid)
