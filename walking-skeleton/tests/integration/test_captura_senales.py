"""Captura de senales por el camino real del usuario (M3.0).

Leccion de ALERTA-005 aplicada por adelantado: **una prueba que verifica una pieza no demuestra que
la pieza este conectada.** Estas pruebas conversan con AURA; no llaman al capturador directamente.
"""

import json

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import ConectorConversacion
from aura_skeleton.core.contexto import RegistroContexto
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import ClaseSenal
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import ModelRouter


class _Fijo:
    name = "fijo"

    def __init__(self, say="Entendido."):
        self._say = say

    async def infer(self, prompt):
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": self._say})


async def _si(a, args, t):
    return True


def _montar(tmp_path, con_captura=True):
    mem = PersistentMemory(str(tmp_path / "memoria.json"))
    conector = ConectorConversacion()
    registro = RegistroContexto([conector]) if con_captura else None
    orch = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([_Fijo()], 1200),
        PermissionManager(_si),
        VoiceAdapterMock(),
        HomeAssistantMock(),
        contexto=registro,
    )
    return orch, mem


@pytest.mark.asyncio
async def test_preferencia_declarada_se_persiste_como_semantica(tmp_path):
    """Una preferencia dicha en conversacion acaba en memoria semantica, con procedencia."""
    orch, mem = _montar(tmp_path)

    await orch.handle_utterance("mauricio", "Prefiero la luz de la sala tenue por la noche", "T1")
    await orch.wait("T1")

    semanticas = [i for i in mem._items if i["kind"] == "semantica"]
    assert semanticas, "la preferencia declarada no se capturo por el camino conversacional"
    assert "tenue" in semanticas[0]["content"]
    assert semanticas[0]["provenance"]["trace_id"] == "T1"
    assert semanticas[0]["provenance"]["clase"] == ClaseSenal.PREFERENCIA_DECLARADA.value
    assert semanticas[0]["provenance"]["origen"] == "declarada"


@pytest.mark.asyncio
async def test_frase_corriente_no_genera_senal(tmp_path):
    """CASO DE CONTROL. Sin el, un capturador que marcase todo como preferencia pasaria."""
    orch, mem = _montar(tmp_path)

    await orch.handle_utterance("mauricio", "Que hora es", "T2")
    await orch.wait("T2")

    assert [i for i in mem._items if i["kind"] == "semantica"] == []


@pytest.mark.asyncio
async def test_captura_no_altera_la_respuesta(tmp_path):
    """RESTRICCION 2: la instrumentacion es completamente pasiva.

    Misma peticion con y sin captura: la respuesta al usuario debe ser identica.
    """
    orch_con, _ = _montar(tmp_path / "con", con_captura=True)
    orch_sin, _ = _montar(tmp_path / "sin", con_captura=False)

    await orch_con.handle_utterance("u", "Prefiero el te al cafe", "A")
    r_con = await orch_con.wait("A")
    await orch_sin.handle_utterance("u", "Prefiero el te al cafe", "B")
    r_sin = await orch_sin.wait("B")

    assert r_con["say"] == r_sin["say"], "la captura altero la respuesta: no es pasiva"


@pytest.mark.asyncio
async def test_senal_sobre_tercero_no_se_persiste(tmp_path):
    """RESTRICCION 3 (4.4 §1, ALERTA-002): nada de perfiles de terceros.

    La frase esta elegida para que **si** se clasifique como senal —contiene "no me gusta que",
    marcador de feedback directo— y ademas mencione a un tercero. Una primera version de esta prueba
    usaba "A Ana le gusta el cafe": no la detectaba ninguna mutacion, porque el clasificador nunca
    llegaba a considerarla senal y la prueba pasaba por la razon equivocada. Falso PASS descubierto
    por prueba de mutacion.

    Nota de diseno: es una preferencia DEL usuario, pero persistirla dejaria rastro sobre otra
    persona. Ante la duda, no se captura.
    """
    orch, mem = _montar(tmp_path)

    await orch.handle_utterance("mauricio", "No me gusta que mi hermana use mi computador", "T3")
    await orch.wait("T3")

    persistido = " ".join(i["content"] for i in mem._items if i["kind"] in ("semantica", "procedimental"))
    assert "hermana" not in persistido, "se construyo rastro persistente sobre un tercero"


@pytest.mark.asyncio
async def test_sin_registro_de_contexto_el_sistema_funciona_igual(tmp_path):
    """La captura es opcional: su ausencia no puede romper un turno (compatibilidad M1/M2)."""
    orch, _ = _montar(tmp_path, con_captura=False)
    await orch.handle_utterance("u", "Hola", "T4")
    res = await orch.wait("T4")
    assert res["say"]
