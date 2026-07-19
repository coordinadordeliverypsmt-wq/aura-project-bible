"""Integracion: memoria de trabajo (contexto de conversacion dentro de la sesion)."""

import json

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _Captura:
    def __init__(self):
        self.name = "cap"
        self.prompts = []

    async def infer(self, prompt):
        self.prompts.append(prompt)
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "ok"})


async def _yes(a, args, t):
    return True


@pytest.mark.asyncio
async def test_contexto_de_conversacion_en_el_prompt():
    cap = _Captura()
    orch = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([cap], 1200),
        PermissionManager(_yes),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    await orch.handle_utterance("u", "Enciende la luz de la sala", "T1")
    await orch.wait("T1")
    await orch.handle_utterance("u", "Y ahora apagala", "T2")
    await orch.wait("T2")
    # el prompt del 2do turno debe incluir el contexto del 1ro (continuidad conversacional)
    assert "Enciende la luz de la sala" in cap.prompts[1]
    assert "conversacion reciente" in cap.prompts[1]
