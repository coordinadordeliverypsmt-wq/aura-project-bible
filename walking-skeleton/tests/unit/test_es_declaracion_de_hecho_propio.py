"""`es_declaracion_de_hecho_propio`: el criterio que el Core consulta es EL MISMO que usa la captura."""

from __future__ import annotations

import pytest

from aura_skeleton.conectores.conversacion import ConectorConversacion, es_declaracion_de_hecho_propio
from aura_skeleton.core.senales import ClaseSenal

PROPIOS = [
    "me llamo Mauricio",
    "Me llamo Mauricio",
    "mi cumpleaños es el 10 de mayo",
    "trabajo en logística",
    "mi color favorito es el azul",
]
AJENOS = [
    "mi abuela es enfermera",  # tercero
    "Hoy tuve un día difícil",  # estado, no hecho
    "¿cómo me llamo?",  # pregunta
    "me gusta el jazz",  # PREFERENCIA_DECLARADA, no HECHO_DECLARADO
    "",
]


@pytest.mark.parametrize("texto", PROPIOS)
def test_reconoce_hechos_propios(texto):
    assert es_declaracion_de_hecho_propio(texto) is True


@pytest.mark.parametrize("texto", AJENOS)
def test_no_reconoce_lo_que_no_es_hecho_propio(texto):
    assert es_declaracion_de_hecho_propio(texto) is False


@pytest.mark.parametrize("texto", PROPIOS + AJENOS)
async def test_una_sola_definicion_coincide_con_lo_que_la_captura_clasifica(texto):
    """Control: si la función tuviera su propia lista, divergiría de la captura en algún caso."""
    conector = ConectorConversacion()
    conector.observar(texto)
    senales = await conector.recoger("t")
    capturado = any(s.clase is ClaseSenal.HECHO_DECLARADO for s in senales)
    assert es_declaracion_de_hecho_propio(texto) is capturado


def test_es_pura_no_encola_nada_en_la_captura():
    conector = ConectorConversacion()
    es_declaracion_de_hecho_propio("me llamo Mauricio")
    assert conector._pendientes == []
