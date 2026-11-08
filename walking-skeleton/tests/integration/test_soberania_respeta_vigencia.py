"""Las superficies de soberanía no tratan como presente lo que ya es historial.

DEFECTO MEDIDO (2026-09-15, datos aislados, composición real). AMP-AURA etapas 1-2 cierra con
`valid_until` la versión anterior de un atributo cuando el usuario lo redeclara, y `_responder_hecho`
ya aplica la consecuencia: *«una entrada con `valid_until` fue superseded por una redeclaración y
pertenece al historial, no al presente»*. Pero tres superficies de soberanía no se adaptaron:

    tu> mi cumpleaños es el 10 de mayo
    tu> mi cumpleaños es el 3 de junio
    tu> olvida mi cumpleaños
    AURA> Hecho. Ya no lo consideraré parte de lo que sé de ti.
    tu> ¿cuál es mi cumpleaños?
    AURA> Tu cumpleaños es 3 de junio.

AURA confirmó el olvido y **borró la versión antigua**, que ya no estaba vigente. Es la clase de
defecto de `ALERTA-006` —actuar sobre el dato equivocado y confirmarlo— y rompe INV-9: narra un éxito
que no ocurrió. Y el mismo origen hace que «¿qué sabes de mí?» liste las dos fechas como conocimiento
actual, y que «eso ya no es cierto», justo después, refute la antigua.

LO QUE ESTAS PRUEBAS NO DECIDEN. Qué debe hacer «olvidar» con el HISTORIAL de un atributo —si arrastra
las versiones anteriores o las conserva— es `D-AMP-3`, pendiente de decisión del CEO. Aquí solo se exige
que el olvido y la refutación actúen sobre lo que AURA presenta como vigente. Por eso una prueba fija
explícitamente que la versión antigua SIGUE existiendo como historial tras el olvido: si alguien
decidiera D-AMP-3 en código sin acta, esta prueba lo diría.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"
V1 = "mi cumpleaños es el 10 de mayo"
V2 = "mi cumpleaños es el 3 de junio"


@pytest.fixture
def sistema(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(config)


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


async def _semantica(s, contenido: str) -> dict | None:
    for e in await s.modelo_usuario.ver(UID):
        if e["contenido"] == contenido:
            return e
    return None


async def _redeclarado(s) -> None:
    await _turno(s.orquestador, V1)
    await _turno(s.orquestador, V2)
    v1 = await _semantica(s, V1)
    assert v1 is not None and v1["valid_until"] is not None, "precondicion: V1 debe quedar superseded"


# --------------------------------------------------------- «¿qué sabes de mí?» --


@pytest.mark.asyncio
async def test_CONTROL_con_una_sola_version_el_listado_la_muestra(sistema):
    await _turno(sistema.orquestador, V1)
    r = await _turno(sistema.orquestador, "¿qué sabes de mí?")
    assert V1 in r["say"], r["say"]


@pytest.mark.asyncio
async def test_el_listado_no_presenta_la_version_superseded_como_conocimiento_actual(sistema):
    await _redeclarado(sistema)
    r = await _turno(sistema.orquestador, "¿qué sabes de mí?")
    assert V2 in r["say"], r["say"]
    assert V1 not in r["say"], r["say"]


# ------------------------------------------------------------------- OLVIDAR --


@pytest.mark.asyncio
async def test_olvidar_un_atributo_redeclarado_retira_la_version_VIGENTE(sistema):
    """El caso medido: antes se borraba la V1 (ya superseded) y AURA seguia afirmando la V2."""
    await _redeclarado(sistema)
    r = await _turno(sistema.orquestador, "olvida mi cumpleaños")
    assert "Hecho" in r["say"], r["say"]

    presente = await _turno(sistema.orquestador, "¿cuál es mi cumpleaños?")
    assert "3 de junio" not in presente["say"], f"AURA confirmo el olvido y sigue afirmandolo: {presente['say']!r}"
    assert await _semantica(sistema, V2) is None, "la version vigente debe ser la olvidada"


@pytest.mark.asyncio
async def test_olvidar_NO_decide_D_AMP_3_la_version_antigua_sigue_como_historial(sistema):
    """Guarda de alcance, no de comportamiento deseado: que el olvido arrastre o no el historial es
    `D-AMP-3`, sin decidir. Esta correccion no toca el historial, y esta prueba lo fija."""
    await _redeclarado(sistema)
    await _turno(sistema.orquestador, "olvida mi cumpleaños")
    v1 = await _semantica(sistema, V1)
    assert v1 is not None and v1["valid_until"] is not None, "el historial no debe desaparecer sin D-AMP-3"


# ------------------------------------------- «ESO» CADUCADO POR UNA REDECLARACION --
#
# Hallazgo de la auditoria independiente del 2026-09-15, preexistente en `6dad6af`. Listar fija el foco
# de «eso»; si ENTRE ese turno y el siguiente el usuario redeclara el atributo, la entrada enfocada pasa a
# superseded, pero el foco cacheado se validaba solo contra «¿sigue existiendo?». «olvida eso» borraba
# entonces la version que acababa de quedar antigua, respondia «Hecho», y AURA seguia afirmando el valor
# recien dicho. Ante un «eso» que ya no señala nada vigente, lo correcto es preguntar (ADR-0003).

_DESAMBIGUA = "¿A qué te refieres?"


async def _listado_y_redeclaracion(s) -> None:
    await _turno(s.orquestador, V1)
    await _turno(s.orquestador, V2)
    await _turno(s.orquestador, "¿qué sabes de mí?")  # el foco queda en V2
    await _turno(s.orquestador, "mi cumpleaños es el 7 de agosto")  # V2 pasa a superseded
    v2 = await _semantica(s, V2)
    assert v2 is not None and v2["valid_until"] is not None, "precondicion: V2 debe quedar superseded"


@pytest.mark.asyncio
async def test_olvida_eso_con_el_foco_caducado_pregunta_en_vez_de_borrar_la_version_antigua(sistema):
    await _listado_y_redeclaracion(sistema)
    r = await _turno(sistema.orquestador, "olvida eso")
    assert _DESAMBIGUA in r["say"], r["say"]
    assert await _semantica(sistema, V2) is not None, "no debia borrarse la version que el foco señalaba"
    assert await _semantica(sistema, "mi cumpleaños es el 7 de agosto") is not None


@pytest.mark.asyncio
async def test_refutar_eso_con_el_foco_caducado_pregunta_en_vez_de_refutar_la_version_antigua(sistema):
    await _listado_y_redeclaracion(sistema)
    r = await _turno(sistema.orquestador, "eso ya no es cierto")
    assert _DESAMBIGUA in r["say"], r["say"]
    v2 = await _semantica(sistema, V2)
    assert v2 is not None and not v2["refutada"], "no debia refutarse la version que el foco señalaba"


# ------------------------------------------ EL HISTORIAL SIGUE SIENDO TUYO: SE PUEDE BORRAR --
#
# Hallazgo de la auditoria independiente: la primera version de esta correccion buscaba la entrada
# nombrada SOLO entre las vigentes, y una version superseded quedaba sin ninguna frase que pudiera
# borrarla («olvida lo de Bangkok» pedia aclaracion). En `6dad6af` si se podia. Regresion de soberania
# (ADR-0017): lo vigente tiene preferencia al nombrar, pero el historial no puede quedar fuera de alcance.


@pytest.mark.asyncio
async def test_se_puede_olvidar_una_version_antigua_nombrandola_explicitamente(sistema):
    await _turno(sistema.orquestador, "mi destino favorito es Bangkok")
    await _turno(sistema.orquestador, "mi destino favorito es Barcelona")
    r = await _turno(sistema.orquestador, "olvida lo de Bangkok")
    assert "Hecho" in r["say"], r["say"]
    assert await _semantica(sistema, "mi destino favorito es Bangkok") is None
    vigente = await _semantica(sistema, "mi destino favorito es Barcelona")
    assert vigente is not None and vigente["valid_until"] is None, "la vigente no debia tocarse"


# ------------------------------------------------------------------ REFUTAR --


@pytest.mark.asyncio
async def test_refutar_eso_tras_el_listado_actua_sobre_la_version_VIGENTE(sistema):
    """El caso medido: tras listar, «eso ya no es cierto» refutaba la V1, que ni siquiera era vigente."""
    await _redeclarado(sistema)
    await _turno(sistema.orquestador, "¿qué sabes de mí?")
    r = await _turno(sistema.orquestador, "eso ya no es cierto")
    assert "corrijo" in r["say"], r["say"]

    v2 = await _semantica(sistema, V2)
    assert v2 is not None and v2["refutada"] is True, f"debia refutarse la vigente: {v2}"
    v1 = await _semantica(sistema, V1)
    assert v1 is not None and not v1["refutada"], "la version superseded no debia tocarse"
