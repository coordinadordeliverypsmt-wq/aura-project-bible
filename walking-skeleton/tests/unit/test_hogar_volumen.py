"""Reconocimiento de las órdenes de volumen y silencio (acta `decisiones/2026-10-22-acta-ecosistema-domestico.md` §4).

Gramática CERRADA y aparte de la de encender/apagar: una orden negada, compuesta o que solo describe el volumen no se
reconoce y el turno sigue su camino de siempre (ADR-0003: ante la duda, no).
"""

from __future__ import annotations

import pytest

from aura_skeleton.core import hogar


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("sube el volumen de la tele", ("subir_volumen", "tele")),
        ("Súbele el volumen a la televisión, por favor", ("subir_volumen", "television")),
        ("sube el volumen de la tele de la sala", ("subir_volumen", "tele de la sala")),
        ("Aurora, baja el volumen de la tele", ("bajar_volumen", "tele")),
        ("bájale el volumen al televisor", ("bajar_volumen", "televisor")),
        ("silencia la tele", ("silenciar", "tele")),
        ("pon en silencio la tele de la sala", ("silenciar", "tele de la sala")),
        ("quita el silencio de la tele", ("quitar_silencio", "tele")),
        ("quítale el silencio a la tv", ("quitar_silencio", "tv")),
        ("sube el volumen", ("subir_volumen", "tele")),
        ("baja el volumen", ("bajar_volumen", "tele")),
    ],
)
def test_reconoce_las_ordenes_de_volumen_con_su_dispositivo(frase, esperado):
    assert hogar.reconocer(frase) == esperado


@pytest.mark.parametrize(
    "frase",
    [
        "no subas el volumen de la tele",
        "sube el volumen de la tele y apaga la luz",
        "el volumen de la tele está alto",
        "¿subiste el volumen de la tele?",
        "sube el volumen de la tele, luego bájalo",
        "subir",
    ],
)
def test_no_reconoce_frases_que_no_son_UNA_orden_limpia_de_volumen(frase):
    assert hogar.reconocer(frase) is None


def test_las_ordenes_de_encender_y_apagar_no_cambian():
    assert hogar.reconocer("apaga la tele") == ("apagar_dispositivo", "tele")
    assert hogar.reconocer("enciende la luz de la cocina") == ("encender_dispositivo", "luz de la cocina")


def test_la_voz_solo_admite_encender_y_apagar():
    """Opción C (DP-VOZ-ACCION §8) sigue vigente: el volumen por voz es una decisión aparte (acta 2026-10-22 §5)."""
    assert hogar.CAPACIDADES_DE_VOZ == frozenset({"encender_dispositivo", "apagar_dispositivo"})
    assert {"subir_volumen", "bajar_volumen", "silenciar", "quitar_silencio"} <= hogar.CAPACIDADES


def test_el_alias_por_nombre_humano_no_elige_si_casan_varias_o_ninguna():
    """Mutante M10 (volumen-tv): con dos entidades del MISMO nombre humano no se elige la primera; se devuelve None y la
    resolución de siempre pregunta cuál."""
    sala, otra = "media_player.tv_sala", "media_player.otra_tv_sala"
    assert hogar.entidad_por_nombre_humano("la tele de la sala", {sala: "la TV de la sala"}) == sala
    assert (
        hogar.entidad_por_nombre_humano("la tele de la sala", {sala: "la TV de la sala", otra: "la TV de la sala"})
        is None
    )
    assert hogar.entidad_por_nombre_humano("la tele del cuarto", {sala: "la TV de la sala"}) is None
    assert hogar.entidad_por_nombre_humano("la tele", {sala: "la TV de la sala"}) is None
