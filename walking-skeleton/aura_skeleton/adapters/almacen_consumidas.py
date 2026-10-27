"""Anti-replay y ESTADOS PERSISTENTES del nodo (N1, M-3, B-4): órdenes consumidas y ejecuciones en disco.

Dos ficheros JSONL en un directorio propio 0700 (ver `jsonl_durable` para las garantías de E/S):

* `consumidas.jsonl` — `{"id","epoch"}` por orden aceptada. Se relee entero bajo `flock` en cada consumo, así dos
  instancias (o un proceso nuevo tras reiniciar) ven siempre el mismo estado. `epoch_hc1` >= máximo visto.
* `ejecuciones.jsonl` — `{"id","estado"[, "resultado"]}`: máquina de estados por `id_ejecucion`
  CONSUMIDA -> EJECUTANDO -> COMPLETADA (con el resultado FIRMADO guardado) | FALLIDA.

Semántica *at-most-once*: la orden se da por consumida de forma durable ANTES de ejecutarla. Si el nodo cae tras
`iniciar_ejecucion` y antes de `completar`, el estado persistido queda EJECUTANDO; tras el reinicio se lee como
AMBIGUA y **nunca se re-ejecuta automáticamente** (solo HC-1, por la vía explícita `resolver_ambigua`, decide). Una
orden CONSUMIDA que nunca llegó a EJECUTANDO tampoco se re-ejecuta: el nodo no conserva la orden, y reponerla exige
una orden NUEVA de HC-1 (otro `id_ejecucion`).

Línea final truncada por caída (B-4): se detecta (`bytes_recuperados`), se recorta y se conservan todos los
consumos válidos. Línea ilegible en el medio, permisos inseguros o fichero ajeno: fallo CERRADO (`ALMACEN_ILEGIBLE`).

LÍMITE declarado: quien pueda borrar o editar estos ficheros (mismo uid) puede reabrir el replay o fabricar estados;
la integridad física exige otro usuario o almacenamiento protegido. Con `emitida_en` y el arranque del nodo, una
orden anterior al arranque se rechaza igualmente (segunda barrera).
"""

from __future__ import annotations

import base64
import binascii
import threading
from pathlib import Path
from typing import Any

from ..core.delegacion import EstadoNodo, Motivo, RechazoOrden
from .jsonl_durable import ErrorDurable, abrir_bloqueado, anexar, asegurar_directorio, leer_registros

NOMBRE = "consumidas.jsonl"
NOMBRE_EJECUCIONES = "ejecuciones.jsonl"
_EJECUTANDO, _COMPLETADA, _FALLIDA = "ejecutando", "completada", "fallida"


def _ilegible(detalle: str) -> RechazoOrden:
    return RechazoOrden(Motivo.ALMACEN_ILEGIBLE, detalle)


class AlmacenConsumidas:
    def __init__(self, directorio: Path) -> None:
        self._dir = Path(directorio)
        try:
            asegurar_directorio(self._dir)
        except ErrorDurable as e:
            raise _ilegible(str(e)) from e
        self._ruta = self._dir / NOMBRE
        self._ruta_ejecuciones = self._dir / NOMBRE_EJECUCIONES
        self._hilo = threading.Lock()
        self._mias: set[str] = set()
        """Ejecuciones iniciadas por ESTA instancia y aún sin cerrar: las únicas que están EJECUTANDO de verdad."""
        self.bytes_recuperados = 0
        """Bytes de línea final truncada descartados al leer (B-4). 0 = nunca hubo truncamiento."""

    @property
    def ruta(self) -> Path:
        return self._ruta

    # -- consumo de órdenes ---------------------------------------------------------------------------------
    def _leer_consumidas(self, fd: int) -> tuple[set[str], int]:
        try:
            registros, descartados = leer_registros(fd)
        except ErrorDurable as e:
            raise _ilegible(str(e)) from e
        self.bytes_recuperados += descartados
        ids: set[str] = set()
        epoch = -1
        for o in registros:
            ident, ep = o.get("id"), o.get("epoch")
            if not isinstance(ident, str) or not isinstance(ep, int) or isinstance(ep, bool):
                raise _ilegible("línea inválida")
            ids.add(ident)
            epoch = max(epoch, ep)
        return ids, epoch

    def consumir(self, id_ejecucion: str, epoch: int) -> None:
        with self._hilo:
            try:
                with abrir_bloqueado(self._ruta) as fd:
                    ids, maximo = self._leer_consumidas(fd)
                    if epoch < maximo:
                        raise RechazoOrden(Motivo.EPOCH_ANTIGUO, "epoch_hc1")
                    if id_ejecucion in ids:
                        raise RechazoOrden(Motivo.ORDEN_REPETIDA, "id_ejecucion")
                    anexar(fd, {"id": id_ejecucion, "epoch": epoch})
            except ErrorDurable as e:
                raise _ilegible(str(e)) from e

    # -- estados de ejecución (M-3) ---------------------------------------------------------------------------
    def _leer_ejecuciones(self, fd: int) -> dict[str, dict[str, Any]]:
        try:
            registros, descartados = leer_registros(fd)
        except ErrorDurable as e:
            raise _ilegible(str(e)) from e
        self.bytes_recuperados += descartados
        ultimo: dict[str, dict[str, Any]] = {}
        for o in registros:
            ident, estado = o.get("id"), o.get("estado")
            if not isinstance(ident, str) or estado not in (_EJECUTANDO, _COMPLETADA, _FALLIDA):
                raise _ilegible("línea inválida")
            ultimo[ident] = o
        return ultimo

    def _fue_consumida(self, id_ejecucion: str) -> bool:
        with abrir_bloqueado(self._ruta) as fd:
            return id_ejecucion in self._leer_consumidas(fd)[0]

    def iniciar_ejecucion(self, id_ejecucion: str) -> None:
        """CONSUMIDA -> EJECUTANDO, de forma durable y exclusiva entre hilos y procesos. Cualquier otro estado previo
        rechaza: `EJECUCION_REPETIDA` (ya se ejecutó o se está ejecutando aquí) o `EJECUCION_AMBIGUA`."""
        with self._hilo:
            try:
                with abrir_bloqueado(self._ruta_ejecuciones) as fd:
                    previo = self._leer_ejecuciones(fd).get(id_ejecucion)
                    if previo is not None:
                        ambigua = previo["estado"] == _EJECUTANDO and id_ejecucion not in self._mias
                        raise RechazoOrden(
                            Motivo.EJECUCION_AMBIGUA if ambigua else Motivo.EJECUCION_REPETIDA, "id_ejecucion"
                        )
                    if not self._fue_consumida(id_ejecucion):
                        raise RechazoOrden(Motivo.EJECUCION_DESCONOCIDA, "id_ejecucion")
                    anexar(fd, {"id": id_ejecucion, "estado": _EJECUTANDO})
                    self._mias.add(id_ejecucion)
            except ErrorDurable as e:
                raise _ilegible(str(e)) from e

    def _cerrar(self, id_ejecucion: str, registro: dict[str, Any]) -> None:
        with self._hilo:
            try:
                with abrir_bloqueado(self._ruta_ejecuciones) as fd:
                    previo = self._leer_ejecuciones(fd).get(id_ejecucion)
                    if previo is None or previo["estado"] != _EJECUTANDO:
                        raise RechazoOrden(Motivo.EJECUCION_NO_EN_CURSO, "no estaba ejecutándose")
                    anexar(fd, registro)
                    self._mias.discard(id_ejecucion)
            except ErrorDurable as e:
                raise _ilegible(str(e)) from e

    def completar(self, id_ejecucion: str, resultado_firmado: bytes) -> None:
        """EJECUTANDO -> COMPLETADA guardando el resultado FIRMADO (para reenviarlo idempotentemente)."""
        self._cerrar(
            id_ejecucion,
            {
                "id": id_ejecucion,
                "estado": _COMPLETADA,
                "resultado": base64.b64encode(resultado_firmado).decode("ascii"),
            },
        )

    def fallar(self, id_ejecucion: str) -> None:
        self._cerrar(id_ejecucion, {"id": id_ejecucion, "estado": _FALLIDA})

    def _estado_de(self, id_ejecucion: str) -> tuple[EstadoNodo | None, bytes | None]:
        with self._hilo:
            try:
                with abrir_bloqueado(self._ruta_ejecuciones) as fd:
                    previo = self._leer_ejecuciones(fd).get(id_ejecucion)
                if previo is None:
                    return (EstadoNodo.CONSUMIDA if self._fue_consumida(id_ejecucion) else None), None
            except ErrorDurable as e:
                raise _ilegible(str(e)) from e
            estado = previo["estado"]
            if estado == _FALLIDA:
                return EstadoNodo.FALLIDA, None
            if estado == _COMPLETADA:
                try:
                    return EstadoNodo.COMPLETADA, base64.b64decode(previo["resultado"], validate=True)
                except (KeyError, TypeError, binascii.Error) as e:
                    raise _ilegible("resultado guardado ilegible") from e
            return (EstadoNodo.EJECUTANDO if id_ejecucion in self._mias else EstadoNodo.AMBIGUA), None

    def estado(self, id_ejecucion: str) -> EstadoNodo | None:
        """`None` si la orden nunca se consumió aquí. Un EJECUTANDO ajeno a esta instancia se lee como AMBIGUA."""
        return self._estado_de(id_ejecucion)[0]

    def resultado_guardado(self, id_ejecucion: str) -> bytes | None:
        """El resultado FIRMADO si la ejecución está COMPLETADA; si no, `None`."""
        return self._estado_de(id_ejecucion)[1]
