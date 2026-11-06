"""Primera grada de percepción visual (acta del CEO, 2026-09-27).

El acta autoriza la capacidad; esta grada es la mínima honesta: AURA recibe un FRAME de una cámara local
y reporta solo sus metadatos ambientales. NO detecta personas, NO identifica, NO emite señales de
aprendizaje (eso colisiona con ALERTA-002 y es una frontera de diseño elevada), NO guarda la imagen.

    frame recibido  ≠  visión  ≠  persona detectada  ≠  persona identificada

Se prueba con una fuente de vídeo INYECTADA: el Core no sabe de cámaras concretas (contexto.py).
"""

from __future__ import annotations

from aura_skeleton.core.percepcion import Frame, LecturaVisual, PercepcionVisual


class _FuenteFalsa:
    """Una fuente de vídeo de prueba: entrega un frame en memoria, sin tocar hardware."""

    nombre = "camara_falsa"

    def __init__(self, frame: Frame | None):
        self._frame = frame
        self.liberada = False

    def capturar(self) -> Frame | None:
        return self._frame

    def liberar(self) -> None:
        self.liberada = True


def test_una_captura_con_frame_reporta_solo_metadatos_ambientales():
    p = PercepcionVisual(_FuenteFalsa(Frame(ancho=640, alto=480, fuente="camara_falsa")))
    lectura = p.percibir("T")
    assert isinstance(lectura, LecturaVisual)
    assert lectura.frame_recibido and lectura.ancho == 640 and lectura.alto == 480


def test_ver_un_frame_NO_es_detectar_una_persona_ni_identificarla():
    p = PercepcionVisual(_FuenteFalsa(Frame(ancho=640, alto=480, fuente="camara_falsa")))
    lectura = p.percibir("T")
    assert lectura.persona_detectada is None, "detección de persona no está implementada: no se afirma"
    assert lectura.identidad is None, "identidad no está implementada: no se afirma"
    assert "no" in lectura.nota.lower() and ("detección" in lectura.nota.lower() or "deteccion" in lectura.nota.lower())


def test_si_la_camara_no_entrega_frame_se_dice_y_no_se_inventa():
    p = PercepcionVisual(_FuenteFalsa(None))
    lectura = p.percibir("T")
    assert lectura.frame_recibido is False and lectura.ancho is None
    assert lectura.persona_detectada is None and lectura.identidad is None


def test_la_percepcion_libera_la_camara_y_no_guarda_la_imagen():
    fuente = _FuenteFalsa(Frame(ancho=320, alto=240, fuente="camara_falsa"))
    p = PercepcionVisual(fuente)
    lectura = p.percibir("T")
    assert fuente.liberada, "la cámara debe liberarse tras capturar"
    # El Frame es solo metadatos: no lleva los píxeles, así que no hay imagen que persistir.
    assert not hasattr(lectura, "pixeles") and not hasattr(lectura, "imagen")
    assert "ancho" in Frame.__dataclass_fields__ and "pixeles" not in Frame.__dataclass_fields__


def test_una_fuente_que_revienta_al_capturar_degrada_sin_derribar():
    class _Rota:
        nombre = "rota"

        def capturar(self):
            raise OSError("cámara desconectada")

        def liberar(self):
            pass

    lectura = PercepcionVisual(_Rota()).percibir("T")
    assert lectura.frame_recibido is False, "un sensor caído es condición del entorno, no un crash"


def test_la_lectura_declara_la_fuente_para_que_la_procedencia_viaje_con_el_dato():
    p = PercepcionVisual(_FuenteFalsa(Frame(ancho=640, alto=480, fuente="camara_local")))
    assert p.percibir("T").fuente == "camara_local"
