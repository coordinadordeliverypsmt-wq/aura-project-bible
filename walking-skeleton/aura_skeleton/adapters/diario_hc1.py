"""Diario DURABLE de seguimiento de HC-1 (M-2): una capa PROPIA, distinta del log del control-plane.

Es un JSONL append-only (`seguimiento.jsonl`) en un directorio propio 0700 (garantías de E/S en `jsonl_durable`:
fsync de fichero y de directorio, un `write` por registro, línea final truncada detectada y recortada sin perder
registros válidos). `SeguimientoHC1` escribe aquí CADA transición ANTES de aplicarla en memoria y, al arrancar, la
reconstruye con `recuperar()`.

CABLEADO FUTURO (hoy NO cableado): el callback `registrar` de `SeguimientoHC1.incorporar` (el hecho auditable
`resultado_remoto`) irá al log de HC-1 con ANCLA (D-LOG-1), no a este diario. Este diario solo sostiene el estado
operativo para sobrevivir a un reinicio; no es la fuente de verdad auditable. Ventana de incorporación (cerrada en
la 2.ª revisión, C1): `incorporando` se anota ANTES de `registrar` y, tras una caída, «incorporando sin incorporado» es el
estado explícito INCORPORACION_INCIERTA, que se resuelve con `ya_registrado(id_ejecucion)` del destino (idempotente).
INSTANCIA ÚNICA (3.ª revisión, ALTO-1): un `RLock` solo ordena hilos de UN proceso. Construir un `DiarioHC1` toma un
`flock` exclusivo no bloqueante sobre el centinela `seguimiento.instancia` del directorio y lo mantiene mientras el
diario viva: un segundo `DiarioHC1` (o `SeguimientoHC1`) sobre el mismo directorio, del mismo proceso o de otro, falla
cerrado con `INSTANCIA_DUPLICADA`. El kernel libera el cerrojo si el proceso muere; `cerrar()` lo libera a propósito.
Al releer, `SeguimientoHC1` re-verifica las firmas y las transiciones: un diario manipulado falla cerrado.
"""

from __future__ import annotations

import fcntl
import os
import stat
import threading
import weakref
from pathlib import Path
from typing import Any

from ..core.delegacion import Motivo, RechazoOrden
from .jsonl_durable import ErrorDurable, abrir_bloqueado, anexar, asegurar_directorio, leer_registros

NOMBRE = "seguimiento.jsonl"
NOMBRE_CENTINELA = "seguimiento.instancia"
"""Centinela de INSTANCIA ÚNICA del diario (ALTO-1): `flock` exclusivo no bloqueante mantenido toda la vida del `DiarioHC1`."""


def _soltar(fd: int) -> None:
    try:
        os.close(fd)  # cerrar el descriptor libera el flock; si el proceso muere, lo libera el kernel
    except OSError:
        pass


def _tomar_centinela(ruta: Path) -> int:
    """Abre (0600, `O_NOFOLLOW`, sin crear enlaces ni borrar nada) y toma `flock` EXCLUSIVO no bloqueante.

    Otra instancia (mismo proceso u otro) que ya lo tenga => `INSTANCIA_DUPLICADA`: fallo cerrado al construirse."""
    try:
        fd = os.open(ruta, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    except OSError as e:
        raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, "centinela de instancia inseguro o ilegible") from e
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, "centinela de instancia inseguro")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RechazoOrden(
                Motivo.INSTANCIA_DUPLICADA, "ya hay otra instancia de seguimiento sobre este diario"
            ) from None
        except OSError as e:
            raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, "no se puede bloquear el centinela de instancia") from e
    except BaseException:
        os.close(fd)
        raise
    return fd


class DiarioHC1:
    def __init__(self, directorio: Path) -> None:
        self._dir = Path(directorio)
        try:
            asegurar_directorio(self._dir)
        except ErrorDurable as e:
            raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, str(e)) from e
        self._ruta = self._dir / NOMBRE
        self._hilo = threading.Lock()
        self._centinela: int | None = _tomar_centinela(self._dir / NOMBRE_CENTINELA)
        self._liberador = weakref.finalize(self, _soltar, self._centinela)

    @property
    def abierto(self) -> bool:
        return self._centinela is not None

    def cerrar(self) -> None:
        """Suelta la instancia única (idempotente). Tras cerrar, `anotar`/`recuperar` fallan cerrados y otra instancia
        puede arrancar. Un proceso que muere suelta el cerrojo solo (lo hace el kernel)."""
        with self._hilo:
            self._centinela = None
            self._liberador()

    def _exigir_abierto(self) -> None:
        if self._centinela is None:
            raise RechazoOrden(Motivo.INSTANCIA_DUPLICADA, "el diario está cerrado: ya no es la instancia única")

    def __enter__(self) -> DiarioHC1:
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrar()

    @property
    def ruta(self) -> Path:
        return self._ruta

    def anotar(self, registro: dict[str, Any]) -> None:
        """Añade un registro de forma durable o lanza `RechazoOrden(DIARIO_NO_DURABLE)`: sin durabilidad no hay estado."""
        with self._hilo:
            self._exigir_abierto()
            try:
                with abrir_bloqueado(self._ruta) as fd:
                    # Si una caída previa dejó una línea parcial, se recorta ANTES de añadir (si no, el registro
                    # nuevo se pegaría al fragmento y ambos quedarían ilegibles).
                    leer_registros(fd)
                    anexar(fd, registro)
            except ErrorDurable as e:
                raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, str(e)) from e

    def recuperar(self) -> tuple[list[dict[str, Any]], int]:
        """`(registros, bytes_truncados_descartados)`. Una línea ilegible en el medio lanza `DIARIO_ILEGIBLE`."""
        with self._hilo:
            self._exigir_abierto()
            try:
                with abrir_bloqueado(self._ruta) as fd:
                    return leer_registros(fd)
            except ErrorDurable as e:
                raise RechazoOrden(Motivo.DIARIO_ILEGIBLE, str(e)) from e
