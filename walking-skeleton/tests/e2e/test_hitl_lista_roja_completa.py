"""Regresion (bug detectado por evals_m1): TODA accion de lista roja pasa por HITL (ADR-0003/5.3),
no solo las 3 que el orquestador enrutaba antes. Tolerancia cero a falsos negativos (2.5 §5.4)."""

import json

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _Fixed:
    """Proveedor que devuelve una accion fija (aisla el enrutamiento por permisos)."""

    def __init__(self, action):
        self.name = "fx"
        self._a = action

    async def infer(self, prompt):
        return json.dumps({"intent": "x", "action": self._a, "args": {}, "say": "ok"})


async def _deny(a, args, t):
    return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action", ["transferencia", "abrir_cerradura", "pago", "mensaje_a_tercero", "accion_financiera"]
)
async def test_toda_accion_roja_se_detiene(action):
    orch = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([_Fixed(action)], 1200),
        PermissionManager(_deny),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    # FRONTERA COGNITIVA (mandato §20, 2026-09-13): un turno cognitivo nunca llega al motor. «x» no pide
    # ninguna accion; la garantia -una accion roja propuesta en la conversacion se detiene en HITL- se
    # ejercita con una frase que SI la pide.
    await orch.handle_utterance("u", "ejecuta la accion", "T")
    res = await orch.wait("T")
    assert "No ejecute" in res["say"], f"accion roja {action} NO fue detenida (falso negativo HITL)"
