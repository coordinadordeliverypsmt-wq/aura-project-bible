"""Cámara de red / DVR por RTSP como `FuenteDeVision` (misión CEO, 2026-09-27).

Enchufa en el mismo puerto que la cámara local: `PercepcionVisual` no sabe si el frame vino de la webcam
o de una cámara ONVIF/RTSP del hogar. Import PEREZOSO de OpenCV (como Piper/Whisper): las pruebas y el
Core nunca lo cargan.

SECRETO DEL PROPIETARIO. La URL RTSP lleva `usuario:contraseña`. Esa URL **no se expone como atributo
público, no aparece en `str`/`repr`, no se registra y no viaja en un mensaje de error**: si la apertura
o la lectura fallan, el error se sanea. Local-first: nada sale del hogar. No escribe disco: el frame vive
en memoria y se reduce a metadatos, y la conexión RTSP se libera en cada captura.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ..core.percepcion import Frame


class CamaraRTSP:
    """`FuenteDeVision` sobre un stream RTSP. `abrir` se inyecta (defecto: OpenCV) para poder probar."""

    def __init__(self, url: str, nombre: str, abrir: Callable | None = None, canal: int | None = None) -> None:
        self.nombre = nombre
        self.canal = canal
        self.__url = url  # name-mangled: no se expone; nunca se loggea ni se serializa
        self._abrir = abrir
        self._cap: Any = None  # cv2.VideoCapture (import perezoso, D24): sin tipo estático

    @classmethod
    def para_dvr(
        cls, host: str, usuario: str, secreto: str, canal: int, abrir: Callable | None = None, puerto: int = 554
    ) -> CamaraRTSP:
        """URL de un canal de DVR (patrón común Dahua/XMEye). El secreto no se guarda aparte."""
        url = f"rtsp://{usuario}:{secreto}@{host}:{puerto}/cam/realmonitor?channel={canal}&subtype=0"
        return cls(url=url, nombre=f"dvr_{host}_canal_{canal}", abrir=abrir, canal=canal)

    def _abridor(self) -> Callable:
        if self._abrir is not None:
            return self._abrir
        import cv2  # perezoso (D24)

        return lambda u: cv2.VideoCapture(u, cv2.CAP_FFMPEG)

    def capturar(self) -> Frame | None:
        try:
            self._cap = self._abridor()(self.__url)
        except Exception as e:
            raise OSError(f"no se pudo abrir el stream de «{self.nombre}»: {_sanear(e, self.__url)}") from None
        try:
            if not self._cap.isOpened():
                return None
            ok, frame = self._cap.read()
            if not ok or frame is None:
                return None
            alto, ancho = frame.shape[:2]
            del frame  # no se persiste
            return Frame(ancho=int(ancho), alto=int(alto), fuente=self.nombre)
        except Exception as e:
            raise OSError(f"fallo leyendo «{self.nombre}»: {_sanear(e, self.__url)}") from None
        finally:
            self.liberar()  # RTSP: no se mantiene la conexión abierta entre capturas

    def liberar(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __repr__(self) -> str:
        return f"CamaraRTSP(nombre={self.nombre!r}, canal={self.canal!r})"

    __str__ = __repr__


def _sanear(e: Exception, url: str) -> str:
    """Quita la URL (que lleva la contraseña) de un mensaje de error, dejando el tipo del fallo."""
    texto = str(e).replace(url, "«stream oculto»")
    return re.sub(r"rtsp://[^\s]*@", "rtsp://«oculto»@", texto)
