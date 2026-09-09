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


# Texto de entrada que LLEGA al LLM. Antes se usaba "hola", pero Conversacion General v1 lo responde
# ahora en el nucleo: estas tres pruebas habrian dejado de ejercitar el parsing que dicen probar sin
# fallar por ello (`assert res["say"]` lo satisface cualquier respuesta). Cada una comprueba ademas
# `provider == "raw"`, para que la prueba se rompa -en vez de volverse decorativa- si una superficie
# determinista futura vuelve a reclamar el turno.
_ORDEN_QUE_LLEGA_AL_LLM = "enciende la luz de la sala"


@pytest.mark.asyncio
async def test_json_malformado_no_crashea():
    orch = _orch("esto no es json en absoluto")
    await orch.handle_utterance("u", _ORDEN_QUE_LLEGA_AL_LLM, "T")
    res = await orch.wait("T")  # no debe lanzar excepcion
    assert res["provider"] == "raw", "el turno no llego al LLM: la prueba no ejercita el parsing"
    assert "reformular" in res["say"].lower()


@pytest.mark.asyncio
async def test_json_con_texto_alrededor_se_extrae():
    salida = 'Claro: {"intent":"x","action":"consulta","args":{},"say":"Listo"} espero que sirva'
    orch = _orch(salida)
    await orch.handle_utterance("u", _ORDEN_QUE_LLEGA_AL_LLM, "T")
    res = await orch.wait("T")
    assert res["provider"] == "raw", "el turno no llego al LLM: la prueba no ejercita el parsing"
    assert res["say"] == "Listo"


@pytest.mark.asyncio
async def test_claves_faltantes_usan_valores_seguros():
    orch = _orch(json.dumps({"foo": "bar"}))  # sin action ni say
    await orch.handle_utterance("u", _ORDEN_QUE_LLEGA_AL_LLM, "T")
    res = await orch.wait("T")
    assert res["provider"] == "raw", "el turno no llego al LLM: la prueba no ejercita el parsing"
    # El valor seguro cambió por instrucción del CEO (2026-09-01, FASE 5): «Entendido.» AFIRMA que
    # se atendió algo, y ante un `say` ausente el usuario no puede distinguir esa confirmación de una
    # respuesta real. Lo que se prueba aquí sigue siendo lo mismo —que el defecto seguro se aplica—;
    # lo que cambia es cuál es.
    assert res["say"] == "No he sabido qué responder a eso.", "el valor seguro por defecto dejo de aplicarse"
    assert "entendido" not in res["say"].lower(), "una confirmación no es una respuesta"
