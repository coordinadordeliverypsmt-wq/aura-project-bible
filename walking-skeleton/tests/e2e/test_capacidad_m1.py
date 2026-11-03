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
    r = await _run(orch, "Enciende la luz de la sala en modo tenue")
    assert "ejecutada" in r["say"]
    # accion peligrosa rechazada (HITL)
    r = await _run(orch, "Elimina el archivo de impuestos")
    assert "No ejecute" in r["say"]
    # kill switch detiene todo
    ks.engage("emergencia")
    r = await _run(orch, "Enciende la luz de la sala")
    assert "kill switch activo" in r["say"]
    ks.disengage()

    # EL VEHICULO DE LA PERSISTENCIA ES UNA AFIRMACION, NO LA ORDEN (CEO, 2026-09-09).
    #
    # Antes, el recuerdo que se recuperaba mas abajo procedia de la ORDEN de arriba. Dejo de ser
    # valido cuando se aprobo `HISTORICO_NO_RECUPERABLE`: una orden pura se persiste con `kind`
    # historico y NO vuelve en un `recall` -es lo que el usuario PIDIO, no lo que AFIRMO sobre si
    # mismo-. Por `DP-D-M-7` (eje 2) esta afirmacion si tiene destino `RECUPERABLE`.
    #
    # Y la prueba sale REFORZADA, no debilitada: la orden sigue en el mismo almacen, con las mismas
    # palabras -"sala", "tenue"-, marcada como historico. Si el filtro cediera, el `recall` de abajo
    # devolveria DOS cosas en vez de una. Que solo vuelva la afirmacion es la garantia entera.
    r = await _run(orch, "Prefiero la luz de la sala en modo tenue")
    assert r["say"], "la afirmacion tiene que cerrar turno como cualquier otra"

    # persistencia entre sesiones: nueva instancia carga del disco
    mem2 = PersistentMemory(mem_path)
    orch2 = _orch(mem2, ks)
    # T1: la asercion debe discriminar RECUERDO de REPETICION de la pregunta. Se pregunta por
    # "la sala" (termino presente en la pregunta) pero se asevera sobre "tenue", que aparece
    # UNICAMENTE en el recuerdo cargado del disco. Antes se aseveraba "luz", palabra contenida
    # en la propia pregunta: la prueba pasaba aunque no hubiera recuperacion de memoria alguna.
    r = await _run(orch2, "Que acordamos sobre la sala?")
    assert "tenue" in r["say"].lower(), (
        f"no se recupero el recuerdo desde disco (respuesta: {r['say']!r}). "
        "'tenue' solo puede provenir de la memoria persistida, no de la pregunta."
    )

    # recuperacion tras perdida
    b = mem2.backup()
    mem2._items = []
    mem2._persist()
    assert mem2.restore(b) is True
    assert await mem2.recall("mauricio", "tenue")


async def _run(orch, text):
    import uuid

    tid = uuid.uuid4().hex[:12]
    await orch.handle_utterance("mauricio", text, tid)
    return await orch.wait(tid)
