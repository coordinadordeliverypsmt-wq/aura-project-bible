"""Adapters PyAV del bloque multimodal: CamaraPyAV (video), DetectorMovimientoPyAV (evento), AudioRTSP
(audio). Con contenedores inyectados; AudioRTSP se prueba con PCMA REAL en memoria (sin cámara).

Verifica además que la credencial de la URL NUNCA aparece en errores/repr (secreto del propietario).
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from aura_skeleton.adapters.audio_rtsp import AudioRTSP
from aura_skeleton.adapters.camara_pyav import CamaraPyAV, DetectorMovimientoPyAV
from aura_skeleton.core.percepcion import AudioPCM, Frame

SECRETO = "rtsp://admin:S3CRETO@192.168.0.9:554/x"


# ------------------------------------------------------------------------------- fakes de video --


class _VFrame:
    def __init__(self, arr, w=1280, h=720):
        self._arr = arr
        self.width = w
        self.height = h

    def reformat(self, width=32, height=32, format="gray"):
        return _Reformatted(self._arr)


class _Reformatted:
    def __init__(self, arr):
        self._arr = arr

    def to_ndarray(self):
        return self._arr


class _ContVideo:
    def __init__(self, frames):
        self._frames = frames
        self.cerrado = False

    def decode(self, video=0):
        yield from self._frames

    def close(self):
        self.cerrado = True


# --------------------------------------------------------------------------------- CamaraPyAV --


def test_camara_pyav_capturar_devuelve_frame_dims():
    cont = _ContVideo([_VFrame(np.zeros((32, 32)), w=1280, h=720)])
    cam = CamaraPyAV(url="rtsp://x/y", nombre="cam", abrir=lambda u: cont)
    f = cam.capturar()
    assert isinstance(f, Frame) and f.ancho == 1280 and f.alto == 720 and f.fuente == "cam"
    assert cont.cerrado, "debe cerrar el contenedor tras capturar"


def test_camara_pyav_sin_frame_devuelve_None():
    cam = CamaraPyAV(url="rtsp://x/y", nombre="cam", abrir=lambda u: _ContVideo([]))
    assert cam.capturar() is None


def test_camara_pyav_error_no_filtra_credencial():
    def _revienta(u):
        raise RuntimeError(f"conexión rechazada a {u}")

    cam = CamaraPyAV(url=SECRETO, nombre="cam", abrir=_revienta)
    with pytest.raises(OSError) as ei:
        cam.capturar()
    assert "S3CRETO" not in str(ei.value) and "admin" not in str(ei.value)
    assert "S3CRETO" not in repr(cam)


# ----------------------------------------------------------------------- DetectorMovimientoPyAV --


def test_detector_movimiento_detecta_cambio():
    a = np.zeros((32, 32))
    b = np.full((32, 32), 200)  # muy distinto
    det = DetectorMovimientoPyAV(url="rtsp://x/y", nombre="cam", abrir=lambda u: _ContVideo([_VFrame(a), _VFrame(b)]))
    detectado, magnitud = det.detectar()
    assert detectado is True and magnitud is not None and magnitud > 0.06


def test_detector_movimiento_sin_cambio_no_detecta():
    a = np.full((32, 32), 100)
    det = DetectorMovimientoPyAV(
        url="rtsp://x/y", nombre="cam", abrir=lambda u: _ContVideo([_VFrame(a), _VFrame(a.copy())])
    )
    detectado, magnitud = det.detectar()
    assert detectado is False and magnitud == 0.0


def test_detector_un_solo_frame_no_concluye():
    a = np.zeros((32, 32))
    det = DetectorMovimientoPyAV(url="rtsp://x/y", nombre="cam", abrir=lambda u: _ContVideo([_VFrame(a)]))
    detectado, magnitud = det.detectar()
    assert detectado is False and magnitud is None


def test_detector_error_no_filtra_credencial():
    def _revienta(u):
        raise RuntimeError(f"fallo con {u}")

    det = DetectorMovimientoPyAV(url=SECRETO, nombre="cam", abrir=_revienta)
    with pytest.raises(OSError) as ei:
        det.detectar()
    assert "S3CRETO" not in str(ei.value) and "S3CRETO" not in repr(det)


# ----------------------------------------------------------------------------------- AudioRTSP --


def _pcma_en_memoria(dur_s=0.5, hz=440):
    import av

    buf = io.BytesIO()
    out = av.open(buf, mode="w", format="wav")
    st = out.add_stream("pcm_alaw", rate=8000)
    st.layout = "mono"
    sr = 8000
    t = np.arange(int(sr * dur_s))
    tono = (0.3 * 32767 * np.sin(2 * np.pi * hz * t / sr)).astype(np.int16).reshape(1, -1)
    fr = av.AudioFrame.from_ndarray(tono, format="s16", layout="mono")
    fr.rate = sr
    for p in st.encode(fr):
        out.mux(p)
    for p in st.encode(None):
        out.mux(p)
    out.close()
    return buf.getvalue()


def test_audio_rtsp_decodifica_pcma_real_a_pcm16k():
    import av

    data = _pcma_en_memoria(dur_s=0.5)
    src = AudioRTSP(url="rtsp://x/y", nombre="cam_mic", ventana_s=0.4, abrir=lambda u: av.open(io.BytesIO(data)))
    pcm = src.capturar_audio()
    assert isinstance(pcm, AudioPCM) and pcm.rate == 16000
    assert pcm.muestras > 0 and pcm.duracion_s is not None
    assert pcm.pcm is not None and pcm.pcm.dtype == np.float32


class _ContSinAudio:
    class _S:
        type = "video"

    streams = [_S()]

    def decode(self, audio=0):
        return iter(())

    def close(self):
        pass


def test_audio_rtsp_sin_pista_de_audio_devuelve_None():
    src = AudioRTSP(url="rtsp://x/y", nombre="cam_mic", abrir=lambda u: _ContSinAudio())
    assert src.capturar_audio() is None


def test_audio_rtsp_error_no_filtra_credencial():
    def _revienta(u):
        raise RuntimeError(f"error {u}")

    src = AudioRTSP(url=SECRETO, nombre="cam_mic", abrir=_revienta)
    with pytest.raises(OSError) as ei:
        src.capturar_audio()
    assert "S3CRETO" not in str(ei.value) and "S3CRETO" not in repr(src)
