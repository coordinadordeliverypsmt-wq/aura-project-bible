"""Cámara de red / DVR por RTSP como fuente de visión (misión CEO, 2026-09-27).

Enchufa en el mismo puerto `FuenteDeVision` que la cámara local. Se prueba con un abridor INYECTADO:
ni se conecta a un dispositivo real ni necesita credenciales. Garantía dura: **la contraseña de la
cámara nunca aparece en un log, en `str`/`repr` ni en un mensaje de error** (secreto del propietario).
"""

from __future__ import annotations

from aura_skeleton.adapters.camara_rtsp import CamaraRTSP
from aura_skeleton.core.percepcion import Frame, PercepcionVisual


class _CapFalso:
    def __init__(self, abierta=True, frame=True, ancho=1280, alto=720):
        self._abierta, self._frame = abierta, frame
        self._ancho, self._alto = ancho, alto
        self.liberado = False

    def isOpened(self):
        return self._abierta

    def read(self):
        if not self._frame:
            return False, None

        class _F:
            shape = (self._alto, self._ancho, 3)

        return True, _F()

    def release(self):
        self.liberado = True


def _cam(cap, **kw):
    return CamaraRTSP(
        url="rtsp://admin:s3creto@192.168.20.110:554/stream", nombre="camara_red_110", abrir=lambda _u: cap, **kw
    )


def test_captura_por_rtsp_reporta_metadatos_del_frame():
    frame = _cam(_CapFalso(ancho=1280, alto=720)).capturar()
    assert isinstance(frame, Frame) and frame.ancho == 1280 and frame.alto == 720
    assert frame.fuente == "camara_red_110"


def test_si_el_stream_no_abre_por_credencial_no_hay_frame():
    assert _cam(_CapFalso(abierta=False)).capturar() is None


def test_si_abre_pero_no_entrega_frame_devuelve_None():
    assert _cam(_CapFalso(frame=False)).capturar() is None


def test_la_camara_se_libera_siempre():
    cap = _CapFalso()
    _cam(cap).capturar()
    assert cap.liberado


def test_la_contrasena_NUNCA_aparece_en_str_ni_repr():
    cam = _cam(_CapFalso())
    assert "s3creto" not in str(cam) and "s3creto" not in repr(cam)
    assert "s3creto" not in cam.nombre


def test_un_fallo_de_apertura_no_filtra_la_URL_con_la_contrasena():
    def _abrir_que_revienta(_u):
        raise OSError(f"no pude abrir {_u}")  # cv2 podría incluir la URL en el error

    cam = CamaraRTSP(
        url="rtsp://admin:s3creto@192.168.20.110:554/stream", nombre="camara_red_110", abrir=_abrir_que_revienta
    )
    try:
        cam.capturar()
        fallo = ""
    except Exception as e:  # noqa: BLE001
        fallo = str(e)
    assert "s3creto" not in fallo, "la excepción filtró la contraseña de la cámara"


def test_encaja_en_el_puerto_de_percepcion_sin_persona_ni_identidad():
    lectura = PercepcionVisual(_cam(_CapFalso(ancho=640, alto=480))).percibir("T")
    assert lectura.frame_recibido and lectura.ancho == 640
    assert lectura.persona_detectada is None and lectura.identidad is None


def test_una_URL_de_canal_de_DVR_se_construye_por_canal():
    cam = CamaraRTSP.para_dvr(host="192.168.20.80", usuario="admin", secreto="x", canal=3, abrir=lambda _u: _CapFalso())
    assert cam.canal == 3 and "s3creto" not in repr(cam)
    assert cam.capturar() is not None


def test_el_saneador_elide_una_URL_RTSP_aunque_no_sea_identica_a_la_configurada():
    """cv2 puede reformatear la URL en el error (otro puerto, otra ruta): el `replace` exacto no la
    atrapa, pero la contraseña sigue ahí. El saneo por patrón `rtsp://…@` es lo que la elide."""

    def _abrir_reformatea(_u):
        raise OSError("open rtsp://admin:s3creto@192.168.20.110:8554/live failed")

    cam = CamaraRTSP(
        url="rtsp://admin:s3creto@192.168.20.110:554/stream", nombre="camara_red_110", abrir=_abrir_reformatea
    )
    try:
        cam.capturar()
        fallo = ""
    except Exception as e:  # noqa: BLE001
        fallo = str(e)
    assert "s3creto" not in fallo, fallo
