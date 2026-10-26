"""La ZONA de una cámara es metadato, nunca una denegación (acta `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`).

Antes: el docstring de la política decía «un canal privado (dormitorio) queda restringido» y la composición se inventaba
la zona «interior» para cualquier cámara de red; la cámara de red se llamaba siempre «camara». Ahora el propietario la
NOMBRA (`AURA_CAMARA_NOMBRE`) y declara su zona como etiqueta (`AURA_CAMARA_ZONA`); lo que da o quita permisos sigue
siendo SOLO `autorizado` y los permisos de cada modalidad (deny-by-default).
"""

from __future__ import annotations

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie

_ZONAS = ("habitacion", "dormitorio", "recamara", "sala", "garaje", "exterior", "privada", "desconocida", "")


def _sup(zona, autorizado=True, visual=True, audio=False):
    return Superficie(
        surface_id="c",
        device_id="d",
        channel_id=None,
        zona=zona,
        proposito="obs",
        autorizado=autorizado,
        visual_processing_allowed=visual,
        audio_processing_allowed=audio,
    )


def _permisos(sup):
    r = RegistroDeSuperficies([sup])
    return (
        r.puede_procesar_visual("c"),
        r.puede_procesar_audio("c"),
        r.puede_persistir("c"),
        r.puede_identificar("c"),
        r.puede_actuar("c"),
    )


@pytest.mark.parametrize("zona", _ZONAS)
def test_una_camara_autorizada_no_se_bloquea_por_su_zona(zona):
    assert _permisos(_sup(zona))[0] is True, f"la zona «{zona}» bloqueó una cámara autorizada"


def test_cambiar_la_zona_no_cambia_NINGUN_permiso():
    for autorizado in (True, False):
        for visual, audio in ((True, False), (False, True), (True, True)):
            vistos = {_permisos(_sup(z, autorizado, visual, audio)) for z in _ZONAS}
            assert len(vistos) == 1, f"la zona cambió permisos: {vistos}"


@pytest.mark.parametrize("zona", _ZONAS)
def test_sin_autorizacion_ninguna_zona_da_acceso_ni_identifica_ni_actua(zona):
    assert _permisos(_sup(zona, autorizado=False)) == (False, False, False, False, False)


# --------------------------------------------------------------------------- composición: nombre y zona --


def _superficies(monkeypatch, tmp_path, **entorno):
    for clave in ("AURA_CAMARA_RTSP", "AURA_CAMARA_AUDIO_RTSP", "AURA_CAMARA_NOMBRE", "AURA_CAMARA_ZONA"):
        monkeypatch.delenv(clave, raising=False)
    for clave, valor in entorno.items():
        monkeypatch.setenv(clave, valor)
    sis = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))
    pv = sis.orquestador.percepcion_visual
    return pv, pv._politica


def test_la_camara_de_red_se_llama_como_la_nombra_el_propietario_y_su_zona_es_la_declarada(monkeypatch, tmp_path):
    pv, politica = _superficies(
        monkeypatch,
        tmp_path,
        AURA_CAMARA_RTSP="rtsp://192.0.2.10:554/0/video0",
        AURA_CAMARA_NOMBRE="Habitación",
        AURA_CAMARA_ZONA="dormitorio",
    )
    assert "habitacion" in pv.superficies_autorizadas(), pv.superficies_autorizadas()
    sup = politica.superficie("habitacion")
    assert sup is not None and sup.zona == "dormitorio" and politica.puede_procesar_visual("habitacion")
    assert not politica.puede_identificar("habitacion") and not politica.puede_persistir("habitacion")


def test_sin_nombre_ni_zona_la_camara_de_red_conserva_su_nombre_y_su_zona_es_desconocida_no_inventada(
    monkeypatch, tmp_path
):
    pv, politica = _superficies(monkeypatch, tmp_path, AURA_CAMARA_RTSP="rtsp://192.0.2.10:554/0/video0")
    sup = politica.superficie("camara")
    assert sup is not None and sup.zona == "desconocida", sup
    assert politica.puede_procesar_visual("camara")


def test_un_nombre_que_no_es_una_palabra_limpia_no_se_usa_como_superficie(monkeypatch, tmp_path):
    pv, _ = _superficies(
        monkeypatch, tmp_path, AURA_CAMARA_RTSP="rtsp://192.0.2.10/x", AURA_CAMARA_NOMBRE="../local; rm"
    )
    assert pv.superficies_autorizadas() == ["camara", "local"], pv.superficies_autorizadas()


def test_un_nombre_que_coincide_con_la_camara_local_no_la_suplanta(monkeypatch, tmp_path):
    pv, politica = _superficies(
        monkeypatch, tmp_path, AURA_CAMARA_RTSP="rtsp://192.0.2.10/x", AURA_CAMARA_NOMBRE="local"
    )
    assert politica.superficie("local").device_id == "equipo_aura" and "camara" in pv.superficies_autorizadas()


def test_estar_en_la_red_no_da_acceso_sin_la_activacion_del_propietario(monkeypatch, tmp_path):
    pv, politica = _superficies(monkeypatch, tmp_path, AURA_CAMARA_NOMBRE="habitacion", AURA_CAMARA_ZONA="dormitorio")
    assert pv.superficies_autorizadas() == ["local"] and politica.superficie("habitacion") is None
