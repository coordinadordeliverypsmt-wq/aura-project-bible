"""Nombrar algo para olvidarlo o refutarlo nunca actúa sobre la entrada equivocada.

HALLAZGOS de la auditoría independiente del 2026-09-15, los dos PREEXISTENTES en `6dad6af` (reproducidos
sobre una copia exportada) y de la clase de `ALERTA-006` —actuar sobre el dato equivocado y confirmarlo—:

(a) **Ambigüedad resuelta por orden.** Dos entradas de atributos distintos contienen la misma palabra.
    «olvida lo de cartagena» borraba la primera que aparecía y respondía «Hecho», sin avisar de que había
    otra igual de válida.

(d) **Coincidencia por subcadena.** `_foco` comparaba con `w in t`. «valencia» —de «mi ciudad favorita es
    Valencia»— está dentro de «valenciana», así que «olvida lo de valenciana» borraba la CIUDAD y dejaba
    intacta la comida que el usuario había nombrado casi literalmente.

La regla que se aplica ya estaba escrita en la docstring de `_foco`: *«Devolver None NO es un fallo: es la
respuesta correcta a una petición ambigua»* («ante la duda, roja», ADR-0003). Se coincide por PALABRA
COMPLETA, gana la entrada con MÁS palabras coincidentes, y un empate se pregunta.

Cada caso lleva CONTROL: la variante inequívoca, que SÍ debe actuar. Sin él, estas pruebas pasarían
también con una implementación que se negara a olvidar nada.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"
_DESAMBIGUA = "¿A qué te refieres?"


@pytest.fixture
def sistema(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(config)


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


async def _contenidos(s) -> set[str]:
    return {e["contenido"] for e in await s.modelo_usuario.ver(UID) if e["tipo"] == "semantica"}


async def _declarar_ambas(s, a: str, b: str) -> None:
    await _turno(s.orquestador, a)
    await _turno(s.orquestador, b)
    assert await _contenidos(s) >= {a, b}, "precondicion: las dos entradas deben existir en memoria"


# ------------------------------------------------------------- (d) SUBCADENA --

_CIUDAD = "mi ciudad favorita es Valencia"
_COMIDA = "mi comida favorita es paella valenciana"


@pytest.mark.asyncio
async def test_una_palabra_que_solo_CONTIENE_otra_no_selecciona_esa_otra_entrada(sistema):
    await _declarar_ambas(sistema, _CIUDAD, _COMIDA)
    r = await _turno(sistema.orquestador, "olvida lo de valenciana")
    assert "Hecho" in r["say"], r["say"]
    quedan = await _contenidos(sistema)
    assert _CIUDAD in quedan, "se borro la ciudad por una coincidencia de subcadena"
    assert _COMIDA not in quedan, "debia olvidarse lo que el usuario nombro"


@pytest.mark.asyncio
async def test_CONTROL_la_palabra_exacta_si_selecciona_su_entrada(sistema):
    await _declarar_ambas(sistema, _CIUDAD, _COMIDA)
    r = await _turno(sistema.orquestador, "olvida lo de valencia")
    assert "Hecho" in r["say"], r["say"]
    quedan = await _contenidos(sistema)
    assert _CIUDAD not in quedan and _COMIDA in quedan, quedan


# ----------------------------------------------------------- (a) AMBIGUEDAD --

# Las dos con la forma «mi X es Y»: solo esa forma se captura como hecho declarado. Una primera version
# usaba «mi cumpleaños lo celebro en Cartagena», que NO se captura, y el caso de ambiguedad «pasaba»
# con una sola entrada en memoria. La precondicion de abajo existe para que eso no vuelva a colarse.
_CUMPLE = "mi fiesta favorita es la feria de Cartagena"
_NATAL = "mi ciudad natal es Cartagena"


@pytest.mark.asyncio
async def test_dos_entradas_igual_de_validas_para_lo_nombrado_se_pregunta_y_no_se_borra_nada(sistema):
    await _declarar_ambas(sistema, _CUMPLE, _NATAL)
    r = await _turno(sistema.orquestador, "olvida lo de cartagena")
    assert _DESAMBIGUA in r["say"], r["say"]
    assert await _contenidos(sistema) >= {_CUMPLE, _NATAL}, "ante la ambiguedad no se destruye nada"


@pytest.mark.asyncio
async def test_refutar_con_el_mismo_empate_tambien_pregunta(sistema):
    await _declarar_ambas(sistema, _CUMPLE, _NATAL)
    r = await _turno(sistema.orquestador, "lo de cartagena ya no es cierto")
    assert _DESAMBIGUA in r["say"], r["say"]
    assert all(not e["refutada"] for e in await sistema.modelo_usuario.ver(UID))


@pytest.mark.asyncio
async def test_CONTROL_si_una_entrada_coincide_en_MAS_palabras_esa_gana_sin_preguntar(sistema):
    """No se pregunta por cualquier palabra compartida: «ciudad natal» señala una sola entrada aunque
    «cartagena» esté en las dos. Preguntar aquí sería degradar la soberanía en nombre de la prudencia."""
    await _declarar_ambas(sistema, _CUMPLE, _NATAL)
    r = await _turno(sistema.orquestador, "olvida mi ciudad natal cartagena")
    assert "Hecho" in r["say"], r["say"]
    quedan = await _contenidos(sistema)
    assert _NATAL not in quedan and _CUMPLE in quedan, quedan
