"""EVENTO — detección propia de movimiento sobre frames RTSP (bloque multimodal, acta CEO 2026-09-28).

NO depende de ONVIF Events (.110 los entrega rotos: investigado 2026-09-28). AURA compara frames y emite
una señal de movimiento. Imagen-cero en la frontera del Core: los píxeles quedan en el detector; solo
cruzan `detectado` y `magnitud`. Separado por construcción: `evento ≠ persona ≠ identidad ≠ intención`.
Bajo demanda y gated por política (procesamiento visual, deny-by-default). Detectores inyectados (fakes).
"""

from __future__ import annotations

from aura_skeleton.core.percepcion import (
    EventoMovimiento,
    PercepcionDeEventoBajoDemanda,
    describir_evento,
    es_consulta_evento,
)
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie


def _sup(sid, visual=True):
    return Superficie(
        surface_id=sid,
        device_id="dev",
        channel_id=None,
        zona="interior",
        proposito="evento",
        autorizado=visual,
        visual_processing_allowed=visual,
    )


class _Detector:
    nombre = "cam_mov"

    def __init__(self, detectado=True, magnitud=0.42):
        self._d = detectado
        self._m = magnitud
        self.llamado = False

    def detectar(self):
        self.llamado = True
        return self._d, self._m


def test_evento_solo_senal_sin_persona_ni_identidad():
    campos = set(EventoMovimiento.__dataclass_fields__)
    assert "persona" not in campos and "identidad" not in campos and "quien" not in campos
    assert "intencion" not in campos
    assert {"superficie", "detectado", "trace_id"} <= campos


def test_observar_evento_superficie_autorizada_detecta():
    det = _Detector(detectado=True, magnitud=0.7)
    p = PercepcionDeEventoBajoDemanda(fuentes={"s1": (det, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1")]))
    ev = p.observar_evento("s1", "T")
    assert ev is not None and ev.detectado is True and ev.magnitud == 0.7
    assert ev.superficie == "s1" and det.llamado


def test_observar_evento_sin_movimiento_dice_no_detectado():
    det = _Detector(detectado=False, magnitud=0.01)
    p = PercepcionDeEventoBajoDemanda(fuentes={"s1": (det, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1")]))
    ev = p.observar_evento("s1", "T")
    assert ev is not None and ev.detectado is False


def test_observar_evento_superficie_NO_autorizada_no_procesa():
    det = _Detector()
    p = PercepcionDeEventoBajoDemanda(
        fuentes={"s1": (det, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1", visual=False)])
    )
    ev = p.observar_evento("s1", "T")
    assert ev is None
    assert det.llamado is False, "superficie no autorizada: no se procesa el frame"


def test_observar_evento_superficie_desconocida_None():
    p = PercepcionDeEventoBajoDemanda(fuentes={}, politica=RegistroDeSuperficies([]))
    assert p.observar_evento("x", "T") is None


def test_construir_no_procesa_no_hay_bucle():
    det = _Detector()
    PercepcionDeEventoBajoDemanda(fuentes={"s1": (det, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1")]))
    assert det.llamado is False  # construir NO procesa; solo observar_evento() lo hace


def test_reconocedor_evento_exige_camara_y_nombre():
    assert es_consulta_evento("¿hay movimiento en la cámara sala?") == "sala"
    assert es_consulta_evento("¿se mueve algo en la cámara patio?") == "patio"
    assert es_consulta_evento("¿qué ves en la cámara sala?") is None
    assert es_consulta_evento("¿qué hora es?") is None


def test_describir_evento_honesto_no_afirma_quien():
    ev = EventoMovimiento(superficie="sala", detectado=True, magnitud=0.6, trace_id="T")
    txt = describir_evento(ev)
    assert "movimiento" in txt.lower()
    assert "no sé quién" in txt.lower() or "no se quien" in txt.lower() or "no identifico" in txt.lower()


def test_describir_evento_sin_movimiento():
    ev = EventoMovimiento(superficie="sala", detectado=False, magnitud=0.0, trace_id="T")
    txt = describir_evento(ev)
    assert "no" in txt.lower() and "movimiento" in txt.lower()
