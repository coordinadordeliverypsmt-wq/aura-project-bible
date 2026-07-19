"""Unit: resiliencia del orquestador ante salida imperfecta del LLM (real, format=json no garantizado)."""

import json

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _Raw:
    def __init__(self, salida):
        self.name = "raw"
        self._s = salida

    async def infer(self, prompt):
        return self._s


async def _yes(a, args, t):
    return True


def _orch(salida):
    return Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([_Raw(salida)], 1200),
        PermissionManager(_yes),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )


@pytest.mark.asyncio
async def test_json_malformado_no_crashea():
    orch = _orch("esto no es json en absoluto")
    await orch.handle_utterance("u", "hola", "T")
    res = await orch.wait("T")  # no debe lanzar excepcion
    assert "reformular" in res["say"].lower()


@pytest.mark.asyncio
async def test_json_con_texto_alrededor_se_extrae():
    salida = 'Claro: {"intent":"x","action":"consulta","args":{},"say":"Listo"} espero que sirva'
    orch = _orch(salida)
    await orch.handle_utterance("u", "hola", "T")
    res = await orch.wait("T")
    assert res["say"] == "Listo"


@pytest.mark.asyncio
async def test_claves_faltantes_usan_valores_seguros():
    orch = _orch(json.dumps({"foo": "bar"}))  # sin action ni say
    await orch.handle_utterance("u", "hola", "T")
    res = await orch.wait("T")
    assert res["say"]  # no vacio, no crash
