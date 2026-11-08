"""Cámara de red por RTSP usando **PyAV** (bloque multimodal, acta CEO 2026-09-28).

Por qué PyAV y no cv2: en este entorno `cv2` NO está instalado y `ffmpeg` CLI tampoco; **PyAV (`av`) sí**,
y trae las librerías de ffmpeg embebidas. Local-first (D24): abre RTSP y decodifica sin binario externo y
sin descargas. Es una implementación alternativa del mismo puerto `FuenteDeVision` (el Protocol admite
«local, ONVIF, RTSP, DVR…»); NO es una arquitectura paralela.

Imagen-cero: `CamaraPyAV.capturar()` devuelve solo dimensiones (`Frame`), los píxeles no salen. El detector
de movimiento compara fotogramas EN EL ADAPTER y solo expone (detectado, magnitud): los píxeles nunca
cruzan al Core. La URL RTSP lleva credenciales -> no se expone, no se loggea, se sanea en errores.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable

from ..core.percepcion import Frame

_OPC = {"rtsp_transport": "tcp", "stimeout": "5000000"}  # TCP + timeout socket 5s (evita cuelgues)


def _sanear(e: Exception, url: str) -> str:
    texto = str(e).replace(url, "«stream oculto»")
    return re.sub(r"rtsp://[^\s]*@", "rtsp://«oculto»@", texto)


class CamaraPyAV:
    """`FuenteDeVision` sobre RTSP con PyAV. `abrir` se inyecta (defecto: av.open) para poder probar."""

    def __init__(self, url: str, nombre: str, abrir: Callable | None = None) -> None:
        self.nombre = nombre
        self.__url = url  # name-mangled: no se expone ni se serializa
        self._abrir = abrir

    def _abridor(self) -> Callable:
        if self._abrir is not None:
            return self._abrir
        av = importlib.import_module("av")  # perezoso (D24): importlib evita que mypy siga PyAV->numpy

        av.logging.set_level(av.logging.PANIC)
        return lambda u: av.open(u, options=_OPC, timeout=8)

    def capturar(self) -> Frame | None:
        try:
            cont = self._abridor()(self.__url)
        except Exception as e:
            raise OSError(f"no se pudo abrir «{self.nombre}»: {_sanear(e, self.__url)}") from None
        try:
            vframe = next(cont.decode(video=0))
            ancho, alto = int(vframe.width), int(vframe.height)
            del vframe  # no se persiste
            return Frame(ancho=ancho, alto=alto, fuente=self.nombre)
        except StopIteration:
            return None
        except Exception as e:
            raise OSError(f"fallo leyendo «{self.nombre}»: {_sanear(e, self.__url)}") from None
        finally:
            self._cerrar(cont)

    @staticmethod
    def _cerrar(cont) -> None:
        try:
            cont.close()
        except Exception:
            pass

    def liberar(self) -> None:
        # PyAV cierra el contenedor en cada captura; no se mantiene conexión abierta.
        return None

    def __repr__(self) -> str:
        return f"CamaraPyAV(nombre={self.nombre!r})"

    __str__ = __repr__


class DetectorMovimientoPyAV:
    """`DetectorDeMovimiento`: abre el stream, toma DOS fotogramas, los reduce a gris 32x32 y compara.

    Solo cruza (detectado, magnitud). Los píxeles se procesan aquí y se descartan: imagen-cero en el Core.
    `magnitud` = diferencia media absoluta normalizada [0,1]. `detectado` = magnitud > `umbral`.
    """

    def __init__(self, url: str, nombre: str, umbral: float = 0.06, abrir: Callable | None = None) -> None:
        self.nombre = nombre
        self.__url = url
        self._umbral = umbral
        self._abrir = abrir

    def _abridor(self) -> Callable:
        if self._abrir is not None:
            return self._abrir
        av = importlib.import_module("av")  # perezoso (D24): importlib evita que mypy siga PyAV->numpy

        av.logging.set_level(av.logging.PANIC)
        return lambda u: av.open(u, options=_OPC, timeout=8)

    def detectar(self) -> tuple[bool, float | None]:
        np = importlib.import_module("numpy")  # perezoso: el stub de numpy usa sintaxis 3.12 y mypy aborta

        try:
            cont = self._abridor()(self.__url)
        except Exception as e:
            raise OSError(f"no se pudo abrir «{self.nombre}»: {_sanear(e, self.__url)}") from None
        try:
            grises = []
            for vframe in cont.decode(video=0):
                g = vframe.reformat(width=32, height=32, format="gray").to_ndarray().astype("int16")
                grises.append(g)
                if len(grises) >= 2:
                    break
            if len(grises) < 2:
                return False, None
            diff = np.abs(grises[0] - grises[1]).mean() / 255.0
            magnitud = round(float(diff), 4)
            return magnitud > self._umbral, magnitud
        except Exception as e:
            raise OSError(f"fallo detectando en «{self.nombre}»: {_sanear(e, self.__url)}") from None
        finally:
            try:
                cont.close()
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"DetectorMovimientoPyAV(nombre={self.nombre!r}, umbral={self._umbral})"

    __str__ = __repr__
