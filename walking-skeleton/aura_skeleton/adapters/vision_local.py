"""Cámara local como fuente de visión (acta del CEO, 2026-09-27).

Import PEREZOSO de OpenCV, igual que Piper y faster-whisper: el Core y las pruebas nunca lo necesitan;
solo se carga cuando de verdad se captura de la cámara física. Local-first (D24): nada sale a la red.
Captura UN frame, lee su tamaño y **libera la cámara**; los píxeles no se guardan ni salen de este método.
"""

from __future__ import annotations

from ..core.percepcion import Frame


class CamaraLocal:
    """`FuenteDeVision` sobre `/dev/videoN` vía OpenCV/V4L2. No escribe disco, no envía nada fuera."""

    def __init__(self, indice: int = 0, nombre: str = "camara_local") -> None:
        self.nombre = nombre
        self._indice = indice
        self._cap = None

    def _abrir(self):
        import cv2  # perezoso (D24): solo quien captura de la cámara real necesita OpenCV

        if self._cap is None:
            self._cap = cv2.VideoCapture(self._indice, cv2.CAP_V4L2)
        return self._cap

    def capturar(self) -> Frame | None:
        cap = self._abrir()
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        alto, ancho = frame.shape[:2]
        del frame  # el fotograma vivió solo en memoria: no se persiste
        return Frame(ancho=int(ancho), alto=int(alto), fuente=self.nombre)

    def liberar(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
