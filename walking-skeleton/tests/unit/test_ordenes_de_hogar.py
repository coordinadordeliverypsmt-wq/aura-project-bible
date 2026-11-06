"""Órdenes de hogar interpretadas por el CORE, con confirmación explícita (semana 2, 2026-09-27).

EL DEFECTO, MEDIDO `[EJEC]`: «enciende la tele» lo interpretaba el MODELO, que contestaba «encendí la
luz de la sala» y ejecutaba `encender_dispositivo` sobre un dispositivo que nadie había nombrado.
ADR-0014 §4: una garantía no puede depender de que un modelo se comporte; el modelo no decide qué se
ejecuta. El Core reconoce la orden, la PROPONE y solo la ejecuta con un «sí».

Pedir confirmación es MÁS estricto que la lista verde vigente (D4: encender/apagar se ejecutan sin
preguntar): esta superficie no amplía ninguna autoridad, la reduce.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core import hogar


@pytest.mark.parametrize(
    "frase,capacidad,dispositivo",
    [
        ("enciende la tele", "encender_dispositivo", "tele"),
        ("Apaga la TV", "apagar_dispositivo", "tv"),
        ("prende la luz del salón", "encender_dispositivo", "luz del salón"),
        ("Aurora, apaga el televisor", "apagar_dispositivo", "televisor"),
        ("apaga la tele por favor", "apagar_dispositivo", "tele"),
        ("¿puedes apagar la tele?", "apagar_dispositivo", "tele"),
    ],
)
def test_reconoce_la_orden_y_el_dispositivo(frase, capacidad, dispositivo):
    assert hogar.reconocer(frase) == (capacidad, dispositivo)


@pytest.mark.parametrize(
    "frase",
    [
        "no apagues la tele",  # negada
        "apaga la tele y borra el informe",  # compuesta: ante la duda, no (ADR-0003)
        "¿está encendida la tele?",  # pregunta de estado, no orden
        "la tele se apaga sola",  # descripción
        "apaga",  # sin dispositivo
        "enciende la tele, la luz y la radio",  # varias a la vez
        "me llamo Mauricio",
    ],
)
def test_no_reconoce_lo_que_no_es_una_orden_limpia_de_hogar(frase):
    assert hogar.reconocer(frase) is None


@pytest.mark.parametrize(
    "frase,esperado",
    [
        ("sí", True),
        ("si", True),
        ("Sí, hazlo", True),
        ("adelante", True),
        ("vale", True),
        ("no", False),
        ("No, déjalo", False),
        ("cancela", False),
        ("mejor no", False),
        ("¿qué hora es?", None),
        ("", None),
        ("sí pero antes dime la hora", None),
    ],
)
def test_interpreta_la_confirmacion(frase, esperado):
    assert hogar.confirmacion(frase) is esperado


def test_la_propuesta_nombra_la_accion_y_el_dispositivo():
    texto = hogar.proponer("apagar_dispositivo", "tele")
    assert "apagar" in texto and "tele" in texto and "?" in texto


def test_la_variante_de_transcripcion_OBSERVADA_enciente_es_encender():
    """Medido por el aire el 2026-10-04 [EJEC]: una persona dijo «enciende la televisión» y Whisper escribió
    «¿Enciente la televisión?» (no_habla 0,009, logprob -0,428). Es el MISMO verbo mal escrito, no una orden
    nueva: misma acción y mismo dispositivo, y sigue exigiendo activación + confirmación."""
    assert hogar.reconocer("¿Enciente la televisión?") == ("encender_dispositivo", "televisión")


def test_la_variante_no_abre_otros_verbos():
    """Control: solo la variante observada; una palabra parecida pero distinta no es una orden."""
    assert hogar.reconocer("encienta la televisión") is None
