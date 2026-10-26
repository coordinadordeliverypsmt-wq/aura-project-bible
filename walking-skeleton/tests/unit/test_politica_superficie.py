"""Política por superficie de cámara (corrección CEO, 2026-09-28).

El error anterior fue un bloqueo GLOBAL: «existe una cámara de un menor → bloquear todo». Lo correcto es
por superficie/canal: un canal exterior se integra; un canal privado recibe una política restrictiva, sin
tumbar los demás. Y separa niveles: procesar imagen ≠ detectar evento ≠ identificar persona.

Deny-by-default: una superficie desconocida o no autorizada NO se procesa, y `PercepcionVisual` **ni
siquiera captura** de ella (la política se comprueba ANTES de tocar la cámara).
"""

from __future__ import annotations

from aura_skeleton.core.percepcion import Frame, PercepcionVisual
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie


class _FuenteContada:
    nombre = "rtsp"

    def __init__(self):
        self.capturas = 0
        self.liberada = False

    def capturar(self):
        self.capturas += 1
        return Frame(ancho=1280, alto=720, fuente=self.nombre)

    def liberar(self):
        self.liberada = True


def _exterior(sid="dvr80_ch1"):
    return Superficie(
        surface_id=sid,
        device_id="dvr_80",
        channel_id=1,
        zona="exterior",
        proposito="seguridad_exterior",
        autorizado=True,
        visual_processing_allowed=True,
        persistence_allowed=False,
        identity_processing_allowed=False,
        action_allowed=False,
        effect_verification_allowed=False,
    )


def _privada(sid="dvr80_ch6"):
    return Superficie(
        surface_id=sid,
        device_id="dvr_80",
        channel_id=6,
        zona="privada",
        proposito="privado",
        autorizado=False,
        visual_processing_allowed=False,
        persistence_allowed=False,
        identity_processing_allowed=False,
        action_allowed=False,
        effect_verification_allowed=False,
    )


def test_superficie_desconocida_se_deniega_por_defecto():
    reg = RegistroDeSuperficies()
    assert reg.puede_procesar_visual("no_registrada") is False


def test_una_superficie_exterior_autorizada_permite_procesamiento_visual():
    reg = RegistroDeSuperficies([_exterior()])
    assert reg.puede_procesar_visual("dvr80_ch1") is True


def test_una_superficie_privada_no_permite_procesamiento_visual():
    reg = RegistroDeSuperficies([_privada()])
    assert reg.puede_procesar_visual("dvr80_ch6") is False


def test_un_canal_privado_NO_bloquea_a_los_canales_exteriores_del_mismo_DVR():
    reg = RegistroDeSuperficies([_exterior("dvr80_ch1"), _privada("dvr80_ch6")])
    assert reg.puede_procesar_visual("dvr80_ch1") is True
    assert reg.puede_procesar_visual("dvr80_ch6") is False


def test_identidad_esta_denegada_aunque_el_procesamiento_visual_este_permitido():
    reg = RegistroDeSuperficies([_exterior()])
    assert reg.puede_procesar_visual("dvr80_ch1") is True
    assert reg.puede_identificar("dvr80_ch1") is False, "identidad es una frontera aparte, no se hereda"


def test_percepcion_NO_captura_de_una_superficie_no_autorizada():
    fuente = _FuenteContada()
    reg = RegistroDeSuperficies([_privada("s")])
    lectura = PercepcionVisual(fuente, superficie="s", politica=reg).percibir("T")
    assert lectura.frame_recibido is False
    assert fuente.capturas == 0, "no se debe capturar de una superficie denegada: ni se toca la cámara"


def test_percepcion_SI_captura_de_una_superficie_exterior_autorizada():
    fuente = _FuenteContada()
    reg = RegistroDeSuperficies([_exterior("s")])
    lectura = PercepcionVisual(fuente, superficie="s", politica=reg).percibir("T")
    assert lectura.frame_recibido is True and fuente.capturas == 1


def test_percepcion_con_superficie_no_registrada_deniega_sin_capturar():
    fuente = _FuenteContada()
    reg = RegistroDeSuperficies([_exterior("otra")])
    lectura = PercepcionVisual(fuente, superficie="s_desconocida", politica=reg).percibir("T")
    assert lectura.frame_recibido is False and fuente.capturas == 0


def test_sin_politica_la_camara_local_sigue_funcionando_como_antes():
    """La cámara local de AURA (su propia plataforma) no necesita política de superficie de red."""
    fuente = _FuenteContada()
    lectura = PercepcionVisual(fuente).percibir("T")
    assert lectura.frame_recibido is True and fuente.capturas == 1
