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
Al releer, `SeguimientoHC1` re-verifica las firmas y las transiciones: un diario manipulado falla cerrado.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ..core.delegacion import Motivo, RechazoOrden
from .jsonl_durable import ErrorDurable, abrir_bloqueado, anexar, asegurar_directorio, leer_registros

NOMBRE = "seguimiento.jsonl"


class DiarioHC1:
    def __init__(self, directorio: Path) -> None:
        self._dir = Path(directorio)
        try:
            asegurar_directorio(self._dir)
        except ErrorDurable as e:
            raise RechazoOrden(Motivo.DIARIO_NO_DURABLE, str(e)) from e
        self._ruta = self._dir / NOMBRE
        self._hilo = threading.Lock()

    @property
    def ruta(self) -> Path:
        return self._ruta

    def anotar(self, registro: dict[str, Any]) -> None:
        """Añade un registro de forma durable o lanza `RechazoOrden(DIARIO_NO_DURABLE)`: sin durabilidad no hay estado."""
        with self._hilo:
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
            try:
                with abrir_bloqueado(self._ruta) as fd:
                    return leer_registros(fd)
            except ErrorDurable as e:
                raise RechazoOrden(Motivo.DIARIO_ILEGIBLE, str(e)) from e
