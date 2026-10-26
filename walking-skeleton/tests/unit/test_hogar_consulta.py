"""Consultar el ESTADO de la TV sin el modelo (acta `decisiones/2026-10-22-acta-ecosistema-domestico.md` §4).

Gramática cerrada y redacción pura: lo que Home Assistant da se dice como observado, con su fuente y su hora; lo que
no da —o da como `None`— se declara desconocido. Nunca se infiere ni se recuerda un valor anterior.
"""

from __future__ import annotations

import time

import pytest

from aura_skeleton.core import hogar


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("¿está encendida la tele?", ("encendida", "tele")),
        ("¿Aurora, está prendida la tele de la sala?", ("encendida", "tele de la sala")),
        ("¿está apagada la televisión?", ("apagada", "television")),
        ("¿la tele está encendida?", ("encendida", "tele")),
        ("¿a qué volumen está la tele de la sala?", ("volumen", "tele de la sala")),
        ("¿qué volumen tiene la tele?", ("volumen", "tele")),
        ("¿qué está poniendo la tele?", ("contenido", "tele")),
        ("¿qué hay en la tele de la sala?", ("contenido", "tele de la sala")),
        ("¿qué se está viendo en la tele?", ("contenido", "tele")),
    ],
)
def test_reconoce_las_consultas_de_estado(frase, esperado):
    assert hogar.reconocer_consulta(frase) == esperado


@pytest.mark.parametrize(
    "frase",
    [
        "sube el volumen de la tele",
        "apaga la tele",
        "¿apagaste la tele?",
        "¿está encendida la tele y la luz?",
        "la tele está rara",
        "¿qué hay conectado?",
    ],
)
def test_no_confunde_ordenes_ni_otras_preguntas_con_una_consulta(frase):
    assert hogar.reconocer_consulta(frase) is None


_ON = {"state": "on", "last_changed": "2026-10-22T02:05:00+00:00"}


@pytest.fixture
def zona(monkeypatch):
    """La hora se dice en la zona LOCAL: la prueba la fija para no depender de la máquina (revisión ECC, MEDIO)."""

    def fijar(tz):
        monkeypatch.setenv("TZ", tz)
        time.tzset()

    yield fijar
    monkeypatch.undo()
    time.tzset()


def test_encendida_se_dice_con_fuente_y_hora_local(zona):
    zona("America/Bogota")
    r = hogar.describir_estado("encendida", "la TV de la sala", dict(_ON, attributes={}), por_voz=False)
    assert r.startswith("Sí: la TV de la sala está encendida") and "Home Assistant" in r and "21:05" in r, r


def test_apagada_dice_no_y_unavailable_dice_que_no_lo_sabe():
    apagada = {"state": "off", "attributes": {}, "last_changed": "2026-10-21T03:38:47+00:00"}
    assert hogar.describir_estado("encendida", "la TV", apagada, por_voz=False).startswith("No: la TV está apagada")
    caida = {"state": "unavailable", "attributes": {}}
    r = hogar.describir_estado("encendida", "la TV", caida, por_voz=False)
    assert r.startswith("No lo sé") and "unavailable" in r, r


def test_el_volumen_solo_se_dice_si_es_legible():
    con = dict(_ON, attributes={"volume_level": 0.21, "is_volume_muted": False})
    assert "21" in hogar.describir_estado("volumen", "la TV", con, por_voz=False)
    silenciada = dict(_ON, attributes={"volume_level": 0.21, "is_volume_muted": True})
    assert "silenciada" in hogar.describir_estado("volumen", "la TV", silenciada, por_voz=False)
    sin = dict(_ON, attributes={"volume_level": None})
    r = hogar.describir_estado("volumen", "la TV", sin, por_voz=False)
    assert "no lo sé" in r and "None" not in r, r
    apagada = {"state": "off", "attributes": {"volume_level": 0.5}}
    r = hogar.describir_estado("volumen", "la TV", apagada, por_voz=False)
    assert "apagada" in r and "50" not in r, "con la TV apagada no se da un volumen viejo como actual"


def test_el_contenido_dice_solo_lo_expuesto_y_el_titulo_nunca_por_voz():
    a = {"source": "HDMI 1", "app_name": "Netflix", "media_title": "Serie X"}
    texto = hogar.describir_estado("contenido", "la TV", dict(_ON, attributes=a), por_voz=False)
    assert "HDMI 1" in texto and "Netflix" in texto and "Serie X" in texto, texto
    voz = hogar.describir_estado("contenido", "la TV", dict(_ON, attributes=a), por_voz=True)
    assert "Serie X" not in voz and "Netflix" in voz and "por escrito" in voz, voz
    nada = hogar.describir_estado("contenido", "la TV", dict(_ON, attributes={}), por_voz=False)
    assert "no lo sé" in nada, nada
    apagada = hogar.describir_estado("contenido", "la TV", {"state": "off", "attributes": a}, por_voz=False)
    assert "apagada" in apagada and "Serie X" not in apagada, apagada


@pytest.mark.parametrize(
    "frase",
    ["¿qué hay en la nevera?", "¿está encendida la luz de la cocina?", "¿a qué volumen está la radio?"],
)
def test_una_consulta_sobre_algo_que_no_es_la_TV_no_se_reconoce(frase):
    """Mutante C7 (consulta-estado-tv): la gramática exige que el dispositivo NOMBRE la TV; si no, el turno sigue igual."""
    assert hogar.reconocer_consulta(frase) is None


def test_control_en_otra_zona_horaria_la_hora_cambia(zona):
    zona("UTC")
    r = hogar.describir_estado("encendida", "la TV", dict(_ON, attributes={}), por_voz=False)
    assert "02:05" in r and "21:05" not in r, r


@pytest.mark.parametrize(
    ("estado", "si_encendida", "si_apagada"),
    [
        ("on", "Sí", "No"),
        ("playing", "Sí", "No"),
        ("paused", "Sí", "No"),
        ("idle", "Sí", "No"),
        ("off", "No", "Sí"),
        ("standby", "No", "Sí"),
    ],
)
def test_la_respuesta_conserva_la_polaridad_de_la_pregunta_en_cada_estado(estado, si_encendida, si_apagada):
    """«¿está apagada?» con la TV apagada es «Sí» (revisión ECC, ALTO); los estados de reproducción cuentan como encendida."""
    e = {"state": estado, "attributes": {}}
    assert hogar.describir_estado("encendida", "la TV", e, por_voz=False).startswith(f"{si_encendida}:")
    assert hogar.describir_estado("apagada", "la TV", e, por_voz=False).startswith(f"{si_apagada}:")


def test_una_consulta_con_estado_asumido_lo_dice_sin_afirmar_que_lee_el_aparato():
    e = {"state": "on", "attributes": {"assumed_state": True}}
    t = hogar.describir_estado("encendida", "la TV", e, por_voz=False)
    assert "la da por encendida sin poder leerla" in t, t
    v = hogar.describir_estado(
        "volumen", "la TV", {**e, "attributes": {"assumed_state": True, "volume_level": 0.3}}, False
    )
    assert "asumido" in v, v


@pytest.mark.parametrize("attrs", [{}, {"assumed_state": False}])
def test_control_sin_estado_asumido_la_consulta_no_cambia(attrs):
    t = hogar.describir_estado("encendida", "la TV", {"state": "on", "attributes": attrs}, por_voz=False)
    assert "asumido" not in t and "sin poder leerla" not in t
