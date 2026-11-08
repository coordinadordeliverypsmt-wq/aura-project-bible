"""Audio de cámara por RTSP usando **PyAV** (bloque multimodal, acta CEO 2026-09-28).

`FuenteDeAudio`: abre el stream RTSP, decodifica la pista de audio (típicamente PCMA/G.711) a **PCM 16 kHz
mono** para el STT, bajo demanda y por una ventana acotada. Local-first (D24): PyAV trae ffmpeg embebido,
sin binario externo ni descargas. El PCM es TRANSITORIO (para el STT); no se guarda en disco ni en la
observación. La URL lleva credenciales -> no se expone ni se loggea; se sanea en errores.

Nota de factibilidad [EJEC 2026-09-28]: el decode PCMA->PCM por PyAV está demostrado; la cámara .110 no
entrega hoy pista de audio en el stream accesible (device), así que el E2E cámara->AURA queda pendiente de
acción física del propietario. Este adapter es correcto y probado con fuentes inyectadas.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable

from ..core.percepcion import AudioPCM

_OPC = {"rtsp_transport": "tcp", "stimeout": "5000000"}
_RATE = 16000


def _sanear(e: Exception, url: str) -> str:
    texto = str(e).replace(url, "«stream oculto»")
    return re.sub(r"rtsp://[^\s]*@", "rtsp://«oculto»@", texto)


class AudioRTSP:
    """`FuenteDeAudio` sobre RTSP con PyAV. Captura una ventana de `ventana_s` segundos de audio -> PCM16k."""

    def __init__(self, url: str, nombre: str, ventana_s: float = 2.0, abrir: Callable | None = None) -> None:
        self.nombre = nombre
        self.__url = url
        self._ventana_s = ventana_s
        self._abrir = abrir

    def _abridor(self) -> Callable:
        if self._abrir is not None:
            return self._abrir
        av = importlib.import_module("av")  # perezoso (D24): importlib evita que mypy siga PyAV->numpy

        av.logging.set_level(av.logging.PANIC)
        return lambda u: av.open(u, options=_OPC, timeout=8)

    def capturar_audio(self) -> AudioPCM | None:
        av = importlib.import_module("av")  # perezoso (D24): importlib evita que mypy siga PyAV->numpy
        np = importlib.import_module("numpy")  # ídem: el stub de numpy usa sintaxis 3.12 y mypy aborta

        try:
            cont = self._abridor()(self.__url)
        except Exception as e:
            raise OSError(f"no se pudo abrir audio de «{self.nombre}»: {_sanear(e, self.__url)}") from None
        try:
            if not [s for s in cont.streams if s.type == "audio"]:
                return None  # el stream no trae pista de audio (condición del dispositivo)
            resampler = av.AudioResampler(format="s16", layout="mono", rate=_RATE)
            trozos = []
            total = 0
            objetivo = int(_RATE * self._ventana_s)
            for frame in cont.decode(audio=0):
                for rf in resampler.resample(frame):
                    a = rf.to_ndarray().reshape(-1)
                    trozos.append(a)
                    total += a.shape[0]
                if total >= objetivo:
                    break
            if total == 0:
                return None
            pcm = np.concatenate(trozos)[:objetivo]
            # a float32 [-1,1] para faster-whisper; transitorio, no se guarda
            pcm_f = pcm.astype("float32") / 32768.0
            return AudioPCM(
                rate=_RATE, muestras=int(pcm_f.shape[0]), duracion_s=round(pcm_f.shape[0] / _RATE, 3), pcm=pcm_f
            )
        except Exception as e:
            raise OSError(f"fallo leyendo audio de «{self.nombre}»: {_sanear(e, self.__url)}") from None
        finally:
            try:
                cont.close()
            except Exception:
                pass

    def liberar(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"AudioRTSP(nombre={self.nombre!r}, ventana_s={self._ventana_s})"

    __str__ = __repr__
