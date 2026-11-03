"""Que AURA conteste cuando le hablan como se habla — y solo eso (M3, 2026-09-09).

**El defecto, medido a traves del producto real con `AURA_STACK_REAL=1`.** Tres turnos, tres veces la
misma frase: «No tengo ningun recuerdo registrado sobre eso.» — 38-53 ms, `provider=core`, **el modelo
no se llamo ni una vez**. Con la memoria vacia, `_es_consulta_de_memoria` es verdadera para CUALQUIER
interrogativa, de modo que la unica salida hacia la cognicion es `es_cognicion_general`, y esa puerta
tenia dos agujeros:

1. **«crees» estaba en la lista de ORDENES** (subjuntivo de *crear*), asi que «¿Por que crees que
   dormir poco afecta al animo?» se clasificaba `ORDEN` y no llegaba a ser `PREGUNTA`.
2. **Pedir consejo se confundia con interrogar un registro**: «¿Que me recomiendas para dormir mejor?»
   daba `HECHO_USUARIO` y moria en la guarda de memoria vacia.

**La asimetria que lo hace seguro, y es el motivo por el que se puede ensanchar:** las 24 consultas
protegidas piden todas un DATO concreto —un nombre, una hora, un numero, una combinacion, una fecha—.
Ninguna pide consejo ni opinion. La frontera nueva es una lista POSITIVA Y CERRADA de peticiones de
consejo: no se parece a ninguna de las 24, y el `24/24` se vuelve a medir aqui mismo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura_skeleton.core import intencion
from aura_skeleton.core.intencion import PREGUNTA, acto_de_habla, es_cognicion_general
from aura_skeleton.core.orchestrator import _es_consulta_de_memoria

# ------------------------------------------------------ 1 · UNA PREGUNTA NO ES UNA ORDEN --

INTERROGATIVAS_CON_CREES = [
    "¿Crees que es buena idea hacer ejercicio de noche?",
    "¿Por qué crees que dormir poco afecta al ánimo?",
    "¿Tú qué crees?",
]


@pytest.mark.parametrize("texto", INTERROGATIVAS_CON_CREES)
def test_una_interrogativa_con_crees_NO_es_una_orden(texto):
    """`crees` es subjuntivo de *crear* y presente de *creer*. La colision ya se pago una vez con
    `baja`, `marca` y `lista` (D-M-2): la forma que colisiona sale de la lista."""
    assert acto_de_habla(texto) == PREGUNTA, acto_de_habla(texto)


def test_crear_sigue_siendo_una_orden():
    """Caso de control. Quitar `crees` no puede desarmar el imperativo real."""
    from aura_skeleton.core.intencion import ORDEN
    assert acto_de_habla("crea una carpeta para el proyecto") == ORDEN


# --------------------------------------------------- 2 · PEDIR CONSEJO ES CONVERSACION --

PIDE_CONSEJO = [
    "¿Qué me recomiendas para dormir mejor?",
    "¿Qué me aconsejas?",
    "¿Cómo puedo organizarme mejor?",
    "¿Qué puedo hacer para concentrarme?",
    "¿Crees que es buena idea hacer ejercicio de noche?",
    "¿Por qué crees que dormir poco afecta al ánimo?",
    "¿Qué opinas de madrugar?",
]


@pytest.mark.parametrize("texto", PIDE_CONSEJO)
def test_pedir_consejo_llega_a_la_cognicion(texto):
    assert es_cognicion_general(texto), "se quedaria en «no tengo ningun recuerdo»"


@pytest.mark.parametrize("texto", PIDE_CONSEJO)
def test_pedir_consejo_no_se_guarda_como_hecho_del_usuario(texto):
    """Una peticion de consejo no AFIRMA nada: no puede entrar en la memoria como hecho."""
    assert not intencion.debe_almacenarse(texto)


# ------------------------------------------------ 3 · LO QUE NO PUEDE ABRIRSE: 24/24 --


def _las_24() -> list[str]:
    datos = json.loads((Path(__file__).parent.parent / "datos" / "bateria_memoria.json")
                       .read_text(encoding="utf-8"))
    textos = [c["texto"] for c in datos["consultas"] if c["esperado"] is None]
    assert len(textos) == 24, "la bateria cambio: vuelve a medir antes de decidir"
    return textos


def test_las_24_siguen_sin_ser_cognicion_general():
    """La garantia que NO se negocia. Si una sola de las 24 se volviera «cognicion general»,
    la memoria vacia dejaria de protegerla y el modelo podria fabricar el dato."""
    escapadas = [t for t in _las_24() if es_cognicion_general(t)]
    assert escapadas == [], f"{len(escapadas)} de 24 dejarian de estar protegidas: {escapadas}"


def test_las_24_siguen_entrando_por_la_puerta_de_memoria():
    assert sum(1 for t in _las_24() if _es_consulta_de_memoria(t)) == 24


EVOCACION_EXPLICITA = [
    "¿Qué me recomendaste ayer?",
    "¿Qué te conté sobre mi abuela?",
    "¿Qué me dijiste la semana pasada?",
]


@pytest.mark.parametrize("texto", EVOCACION_EXPLICITA)
def test_preguntar_por_lo_ya_dicho_NO_es_cognicion_general(texto):
    """El pasado del verbo es la diferencia: «¿que me recomiendas?» pide consejo, «¿que me
    recomendaste?» interroga el registro. Lo segundo es memoria y sigue siendo del Core."""
    assert not es_cognicion_general(texto)


DATOS_PERSONALES = [
    "¿Cuál es el nombre de mi abuela?",
    "¿Cuál es la combinación de mi caja fuerte?",
    "¿Cuánto gana mi jefa Marta?",
    "¿Cuál es mi número de la seguridad social?",
]


@pytest.mark.parametrize("texto", DATOS_PERSONALES)
def test_preguntar_por_un_dato_personal_NO_es_cognicion_general(texto):
    assert not es_cognicion_general(texto)


# ------------------------------------ 4 · LOS DOS FRENOS, CADA UNO CON SU PRUEBA --
#
# Ambas garantias las destapo la verificacion de mutacion: `CN-M2` y `CN-M5` sobrevivieron porque
# ninguna prueba declarada las cubria. Un mutante que sobrevive es una garantia sin red.

CONSEJO_SOBRE_ALGO_MIO = [
    "¿Crees que mi hermana vive en Madrid?",
    "¿Crees que mis gatos están bien?",
    "¿Qué me recomiendas para el regalo de mi madre?",
]


@pytest.mark.parametrize("texto", CONSEJO_SOBRE_ALGO_MIO)
def test_un_consejo_que_nombra_algo_MIO_vuelve_al_core(texto):
    """El freno del posesivo (mata `CN-M2`).

    «¿Crees que...?» con un posesivo propio deja de ser opinion y pasa a interrogar el mundo del
    usuario: exactamente la forma en que un modelo fabricaria un hecho personal con aire de cautela.
    """
    assert not es_cognicion_general(texto)


CONSEJO_SOBRE_LO_YA_DICHO = [
    "¿Qué puedo hacer con lo que te conté?",
    "¿Cómo puedo recordar lo que me dijiste?",
    "¿Qué me recomiendas sobre lo que hablamos de mi trabajo?",
]


@pytest.mark.parametrize("texto", CONSEJO_SOBRE_LO_YA_DICHO)
def test_un_consejo_sobre_lo_ya_dicho_vuelve_al_core(texto):
    """El freno de la evocacion (mata `CN-M5`). Pedir consejo NO es excusa para entrar al registro."""
    assert not es_cognicion_general(texto)


def test_los_marcadores_incluyen_a_AURA_como_sujeto():
    """Caso de control del punto ciego: faltaban las formas en que AURA es quien dijo algo."""
    assert "me dijiste" in intencion.MARCADORES_DE_EVOCACION
    assert "te conte" in intencion.MARCADORES_DE_EVOCACION
