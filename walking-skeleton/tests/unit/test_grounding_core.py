"""ADR-0014 — El Core es la unica fuente de verdad sobre los hechos del sistema.

Verifica que la ausencia de memoria la resuelve el NUCLEO de forma deterministica y que
en ese caso NO se consulta al LLM. Regresion de ALERTA-004: con mocks la garantia parecia
cumplirse porque el doble estaba escrito para cumplirla; aqui se comprueba el sistema.
"""

import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _ProveedorEspia:
    """Registra si el orquestador llego a consultar al modelo."""

    name = "espia"

    def __init__(self, salida='{"intent":"x","action":"consulta","args":{},"say":"Claro, lo acordamos ayer."}'):
        self.llamadas = 0
        self._salida = salida

    async def infer(self, prompt: str) -> str:
        self.llamadas += 1
        return self._salida


async def _si(action, args, tid):
    return True


def _orq(espia, memoria=None):
    return Orchestrator(
        InProcessEventBus(),
        memoria or SimpleMemory(),
        ModelRouter([espia], 1200),
        PermissionManager(_si),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )


async def _turno(orq, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return await orq.wait(tid)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pregunta",
    [
        "Que acordamos sobre el presupuesto del proximo trimestre?",
        "¿Qué habíamos hablado del viaje?",
        "Te acuerdas de mi preferencia de luz?",
        "Que dijimos sobre la reunion?",
    ],
)
async def test_memoria_vacia_responde_el_core_sin_consultar_al_llm(pregunta):
    """Con memoria vacia, el nucleo declara la ausencia y NO llama al proveedor."""
    espia = _ProveedorEspia()
    r = await _turno(_orq(espia), pregunta)

    assert espia.llamadas == 0, "el LLM no debe consultarse cuando no hay nada que recordar"
    assert r["provider"] == "core"
    say = r["say"].lower()
    assert "no" in say and "recuerd" in say, f"debe declarar la ausencia de registro: {r['say']!r}"


@pytest.mark.asyncio
async def test_no_bloquea_peticiones_que_no_son_consultas_de_memoria():
    """Una orden normal tiene 0 hits de memoria pero SI debe llegar al LLM (no romper lista verde)."""
    espia = _ProveedorEspia('{"intent":"domotica","action":"encender_dispositivo","args":{},"say":"Listo."}')
    r = await _turno(_orq(espia), "Enciende la luz de la sala")

    assert espia.llamadas == 1, "las ordenes normales deben seguir enrutandose al modelo"
    assert r["provider"] == "espia"


@pytest.mark.asyncio
async def test_con_recuerdos_si_consulta_al_llm():
    """Si existe registro, el turno sigue el camino normal: el Core no cortocircuita."""
    mem = SimpleMemory()
    await mem.write("mauricio", "episodica", "prefiere la luz tenue por la noche", {})
    espia = _ProveedorEspia()
    r = await _turno(_orq(espia, mem), "Que acordamos sobre la luz?")

    assert espia.llamadas == 1, "con recuerdos disponibles el modelo debe razonar sobre ellos"
    assert r["provider"] == "espia"
