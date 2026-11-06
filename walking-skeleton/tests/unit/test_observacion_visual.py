"""FRAME → OBSERVACIÓN (DP-FRAME-A-OBSERVACION, aprobado 2026-09-28: Alt B, bajo demanda, imagen-cero).

Primera capacidad conectada al sistema: una `LecturaVisual` se convierte en una `Observacion` ambiental
CONSUMIBLE (audit + contexto efímero del turno), bajo demanda, sin persistir imagen, sin persona, sin
identidad, sin evento. Se prueba con fuente inyectada + política; no toca hardware.
"""

from __future__ import annotations

from aura_skeleton.core.percepcion import (
    Frame,
    Observacion,
    PercepcionBajoDemanda,
    observacion_de,
)
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie


def _sup(sid, autorizado=True, zona="interior"):
    return Superficie(
        surface_id=sid,
        device_id="dev",
        channel_id=None,
        zona=zona,
        proposito="observacion",
        autorizado=autorizado,
        visual_processing_allowed=autorizado,
    )


class _Fuente:
    nombre = "cam"

    def __init__(self, frame=None):
        self._f = frame or Frame(ancho=1280, alto=720, fuente="cam")
        self.liberada = False

    def capturar(self):
        return self._f

    def liberar(self):
        self.liberada = True


# ------------------------------------------------------------------ contrato Observacion --


def test_observacion_solo_metadatos_sin_persona_ni_identidad_ni_pixeles():
    from aura_skeleton.core.percepcion import LecturaVisual

    obs = observacion_de(
        LecturaVisual(frame_recibido=True, fuente="cam", ancho=1280, alto=720),
        superficie="s1",
        tipo_fuente="rtsp",
        trace_id="T",
    )
    assert isinstance(obs, Observacion)
    assert obs.superficie == "s1" and obs.fuente == "cam" and obs.tipo_fuente == "rtsp"
    assert obs.ancho == 1280 and obs.alto == 720 and obs.frame_recibido is True
    assert obs.timestamp > 0 and obs.trace_id == "T"
    campos = set(Observacion.__dataclass_fields__)
    assert "pixeles" not in campos and "imagen" not in campos and "persona" not in campos
    assert "identidad" not in campos and "evento" not in campos


def test_sin_frame_la_observacion_lo_dice_y_no_inventa():
    from aura_skeleton.core.percepcion import LecturaVisual

    obs = observacion_de(
        LecturaVisual(frame_recibido=False, fuente="cam"), superficie="s1", tipo_fuente="rtsp", trace_id="T"
    )
    assert obs.frame_recibido is False and obs.ancho is None


# --------------------------------------------------- consumidor bajo demanda + política --


def test_observar_una_superficie_autorizada_devuelve_observacion_con_frame():
    fuente = _Fuente()
    p = PercepcionBajoDemanda(fuentes={"s1": (fuente, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1")]))
    obs = p.observar("s1", "T")
    assert obs is not None and obs.frame_recibido is True and obs.ancho == 1280
    assert fuente.liberada


def test_observar_una_superficie_NO_autorizada_no_captura():
    fuente = _Fuente()
    p = PercepcionBajoDemanda(
        fuentes={"s1": (fuente, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1", autorizado=False)])
    )
    obs = p.observar("s1", "T")
    assert obs is None, "una superficie no autorizada no produce observación"
    # y no se tocó la cámara: no hay frame
    assert fuente.liberada is False


def test_observar_una_superficie_desconocida_devuelve_None():
    p = PercepcionBajoDemanda(fuentes={}, politica=RegistroDeSuperficies([]))
    assert p.observar("inexistente", "T") is None


def test_la_observacion_es_bajo_demanda_no_hay_bucle_ni_captura_al_construir():
    fuente = _Fuente()
    PercepcionBajoDemanda(fuentes={"s1": (fuente, "local")}, politica=RegistroDeSuperficies([_sup("s1")]))
    assert fuente.liberada is False  # construir NO captura; solo observar() lo hace


def test_describir_observacion_es_honesto_sobre_lo_que_no_sabe():
    from aura_skeleton.core.percepcion import LecturaVisual, describir_observacion

    obs = observacion_de(
        LecturaVisual(frame_recibido=True, fuente="cam", ancho=1280, alto=720),
        superficie="s1",
        tipo_fuente="rtsp",
        trace_id="T",
    )
    texto = describir_observacion(obs)
    assert "1280" in texto and "720" in texto
    assert "no" in texto.lower() and ("contenido" in texto.lower() or "interpret" in texto.lower())


def test_reconocedor_exige_camara_y_nombre():
    from aura_skeleton.core.percepcion import es_consulta_visual

    assert es_consulta_visual("¿qué ves en la cámara sala?") == "sala"
    assert es_consulta_visual("¿qué ves?") is None
    assert es_consulta_visual("¿cómo me llamo?") is None


def test_describir_sin_frame_no_inventa_dimensiones():
    from aura_skeleton.core.percepcion import LecturaVisual, describir_observacion

    obs = observacion_de(
        LecturaVisual(frame_recibido=False, fuente="cam"), superficie="s1", tipo_fuente="rtsp", trace_id="T"
    )
    texto = describir_observacion(obs)
    assert "no recib" in texto.lower() and "None" not in texto
    assert "x" not in texto.replace("superficie", "").replace("«s1»", "")  # sin "NxM"
