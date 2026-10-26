"""Evocación de hechos desde el Core — DR-1 = A (CEO, 2026-09-15).

DEFECTO MEDIDO. Tras declarar «me llamo Mauricio» y «mi color favorito es el verde», AURA listaba esos
hechos con «¿qué sabes de mí?» y un turno después respondía «No tengo ningún recuerdo registrado sobre
eso» a «¿te acuerdas de lo que te dije antes?». 5 de 7 evocaciones genéricas fallaban: la puerta de
ADR-0014 decide con la búsqueda LÉXICA, y esa frase no comparte términos con ningún recuerdo.

LO QUE LA DECISIÓN EXIGE: responder desde el Core, de forma determinista, respetando vigencia,
supersesión y refutación, sin inventar hechos y sin que el LLM decida si un recuerdo existe. La puerta
de ADR-0014 no se toca.

Todas las pruebas usan la COMPOSICIÓN REAL y un espía que cuenta las llamadas al modelo: la evocación
que responde el Core tiene que hacerlo con CERO llamadas.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estatus import Estatus
from aura_skeleton.core.identidad_memoria import atributo_evocado, es_evocacion_generica
from aura_skeleton.core.orchestrator import _normalizar
from aura_skeleton.core.senales import ClaseSenal

UID = "mauricio"
NOMBRE = "me llamo Mauricio"
COLOR = "mi color favorito es el verde"
_SIN_HECHOS = "No me consta que me hayas dicho nada que siga dando por cierto."
_AUSENCIA_ADR_0014 = "No tengo ningun recuerdo registrado sobre eso."


class _Espia:
    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "FABRICADO por el LLM"})


@pytest.fixture
def sistema(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    espia = _Espia()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


# ----------------------------------------------------------------- LA GRAMATICA --


@pytest.mark.parametrize(
    "texto",
    [
        "¿te acuerdas de lo que te dije antes?",
        "¿Te acuerdas de lo que te dije?",
        "¿recuerdas lo que te conté?",
        "¿qué te dije antes?",
        "¿sabes lo que te he dicho?",
    ],
)
def test_reconoce_la_evocacion_generica(texto):
    assert es_evocacion_generica(_normalizar(texto))


@pytest.mark.parametrize(
    "texto",
    [
        "¿de qué hablamos?",  # evocacion CONVERSACIONAL: la alternativa C, no aprobada
        "¿recuerdas que te dije que me llamaras?",  # pide otra cosa: no es la frase entera
        "olvida lo que te dije",  # es una orden de olvido
        "te dije que no",
    ],
)
def test_no_reconoce_lo_que_no_es_evocacion_de_hechos(texto):
    assert not es_evocacion_generica(_normalizar(texto))


def test_la_evocacion_de_un_atributo_se_reconoce_y_se_extrae():
    assert atributo_evocado(_normalizar("¿te acuerdas de mi color favorito?")) == "color favorito"
    assert atributo_evocado(_normalizar("¿recuerdas mi nombre?")) == "nombre"
    assert atributo_evocado(_normalizar("¿te acuerdas de mi color favorito y del tuyo?")) is None


# ----------------------------------------------------------- EVOCACION EXISTENTE --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pregunta",
    [
        "¿te acuerdas de lo que te dije antes?",
        "¿recuerdas lo que te conté?",
        "¿qué te dije antes?",
    ],
)
async def test_la_evocacion_generica_la_responde_el_Core_con_todos_los_hechos_declarados(sistema, pregunta):
    s, espia = sistema
    await _turno(s.orquestador, NOMBRE)
    await _turno(s.orquestador, COLOR)
    r = await _turno(s.orquestador, pregunta)
    assert r["provider"] == "core" and r["estatus"] == Estatus.HECHO.value, r
    assert NOMBRE in r["say"] and COLOR in r["say"], r["say"]
    assert espia.llamadas == 0, "la existencia de un recuerdo no la decide el LLM"


@pytest.mark.asyncio
async def test_la_evocacion_de_un_atributo_se_responde_como_la_consulta_de_ese_atributo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, NOMBRE)
    await _turno(s.orquestador, COLOR)
    nombre = await _turno(s.orquestador, "¿te acuerdas de mi nombre?")
    color = await _turno(s.orquestador, "¿te acuerdas de mi color favorito?")
    assert nombre["say"] == "Te llamas Mauricio.", nombre["say"]
    assert color["provider"] == "core" and "verde" in color["say"], color
    assert espia.llamadas == 0


# -------------------------------------------------------- EVOCACION INEXISTENTE --


@pytest.mark.asyncio
async def test_sin_hechos_declarados_la_evocacion_generica_lo_dice_sin_inventar(sistema):
    s, espia = sistema
    r = await _turno(s.orquestador, "¿te acuerdas de lo que te dije?")
    assert r["say"] == _SIN_HECHOS and r["estatus"] == Estatus.AUSENCIA.value, r
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_un_atributo_nunca_declarado_cae_a_la_puerta_de_ADR_0014_sin_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, NOMBRE)
    r = await _turno(s.orquestador, "¿te acuerdas de mi coche?")
    assert r["say"] == _AUSENCIA_ADR_0014, r["say"]
    assert espia.llamadas == 0


# ---------------------------------------------------- SUPERSEDED · REFUTADO · OBSERVADO --


@pytest.mark.asyncio
async def test_la_evocacion_no_presenta_una_version_superseded(sistema):
    s, _ = sistema
    await _turno(s.orquestador, "mi cumpleaños es el 10 de mayo")
    await _turno(s.orquestador, "mi cumpleaños es el 3 de junio")
    r = await _turno(s.orquestador, "¿te acuerdas de lo que te dije?")
    assert "3 de junio" in r["say"] and "10 de mayo" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_la_evocacion_no_presenta_un_hecho_refutado(sistema):
    s, espia = sistema
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    await _turno(s.orquestador, "eso ya no es cierto")
    r = await _turno(s.orquestador, "¿te acuerdas de lo que te dije?")
    assert r["say"] == _SIN_HECHOS, r["say"]
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_lo_OBSERVADO_no_se_presenta_como_algo_que_el_usuario_dijo(sistema):
    s, _ = sistema
    await _turno(s.orquestador, NOMBRE)
    await s.orquestador.memory.write(
        UID,
        "procedimental",
        "suele conectarse de noche",
        {
            "trace_id": "t-obs",
            "fuente": "computador",
            "clase": ClaseSenal.PATRON_DE_USO.value,
            "origen": "observada",
            "ts": 1.0,
        },
    )
    r = await _turno(s.orquestador, "¿te acuerdas de lo que te dije?")
    assert NOMBRE in r["say"], r["say"]
    assert "de noche" not in r["say"], "«lo que te dije» no incluye lo que AURA observo"


# ------------------------------------------------ «ESO» TRAS UNA EVOCACION MULTIPLE --


@pytest.mark.asyncio
async def test_tras_evocar_varios_hechos_olvida_eso_pregunta_en_vez_de_elegir(sistema):
    s, _ = sistema
    await _turno(s.orquestador, NOMBRE)
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, "¿te acuerdas de lo que te dije?")
    r = await _turno(s.orquestador, "olvida eso")
    assert "¿A qué te refieres?" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_CONTROL_tras_evocar_un_solo_hecho_olvida_eso_lo_olvida(sistema):
    s, _ = sistema
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, "¿te acuerdas de lo que te dije?")
    r = await _turno(s.orquestador, "olvida eso")
    assert "Hecho" in r["say"], r["say"]
    assert await s.modelo_usuario.ver(UID) == []


# ---------------------------------------------------------- LA PUERTA NO SE MUEVE --


@pytest.mark.asyncio
async def test_la_evocacion_CONVERSACIONAL_sigue_fuera_de_esta_superficie(sistema):
    """DR-1 aprobo la evocacion de HECHOS. «¿de que hablamos?» no la atiende esta superficie."""
    s, _ = sistema
    await _turno(s.orquestador, NOMBRE)
    r = await _turno(s.orquestador, "¿de qué hablamos?")
    assert r.get("dominio") != "modelo_usuario", r
