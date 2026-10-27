"""Anti-replay PERSISTENTE del nodo (N1): órdenes consumidas en disco.

Fichero `consumidas.jsonl` en un directorio dado (0700). Cada consumo es UNA línea añadida con `O_APPEND`, bajo
`flock` exclusivo y con `fsync` ANTES de devolver: la orden se da por consumida de forma durable antes de ejecutarla
(semántica *at-most-once*: si el nodo cae tras consumir y antes de ejecutar, HC-1 decide; nunca se ejecuta dos veces).

Cada consumo relee el fichero entero bajo el cerrojo, así dos instancias (o un proceso nuevo tras reiniciar) ven
siempre el mismo estado. Fallo CERRADO: una línea ilegible o truncada rechaza todo (`ALMACEN_ILEGIBLE`).
Además se exige `epoch_hc1` >= el máximo visto.

LÍMITE declarado: quien pueda borrar o editar este fichero (mismo uid) puede reabrir el replay; la integridad física
exige otro usuario o almacenamiento protegido. Con la hora de HC-1 en `emitida_en` y el arranque del nodo, una orden
anterior al arranque se rechaza igualmente (segunda barrera).
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from pathlib import Path

from ..core.delegacion import Motivo, RechazoOrden

NOMBRE = "consumidas.jsonl"


class AlmacenConsumidas:
    def __init__(self, directorio: Path) -> None:
        self._dir = Path(directorio)
        self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._ruta = self._dir / NOMBRE
        self._hilo = threading.Lock()

    @property
    def ruta(self) -> Path:
        return self._ruta

    def _leer(self, fd: int) -> tuple[set[str], int]:
        os.lseek(fd, 0, os.SEEK_SET)
        trozos = []
        while True:
            b = os.read(fd, 1 << 16)
            if not b:
                break
            trozos.append(b)
        datos = b"".join(trozos)
        if datos and not datos.endswith(b"\n"):
            raise RechazoOrden(Motivo.ALMACEN_ILEGIBLE, "línea truncada")
        ids: set[str] = set()
        epoch = -1
        for linea in datos.splitlines():
            try:
                o = json.loads(linea)
                ident, ep = o["id"], o["epoch"]
            except (ValueError, KeyError, TypeError) as e:
                raise RechazoOrden(Motivo.ALMACEN_ILEGIBLE, "línea ilegible") from e
            if not isinstance(ident, str) or not isinstance(ep, int) or isinstance(ep, bool):
                raise RechazoOrden(Motivo.ALMACEN_ILEGIBLE, "línea inválida")
            ids.add(ident)
            epoch = max(epoch, ep)
        return ids, epoch

    def consumir(self, id_ejecucion: str, epoch: int) -> None:
        with self._hilo:
            try:
                fd = os.open(self._ruta, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
            except OSError as e:
                raise RechazoOrden(Motivo.ALMACEN_ILEGIBLE, "no se puede abrir") from e
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                ids, maximo = self._leer(fd)
                if epoch < maximo:
                    raise RechazoOrden(Motivo.EPOCH_ANTIGUO, "epoch_hc1")
                if id_ejecucion in ids:
                    raise RechazoOrden(Motivo.ORDEN_REPETIDA, "id_ejecucion")
                linea = json.dumps({"id": id_ejecucion, "epoch": epoch}, separators=(",", ":")) + "\n"
                try:
                    os.write(fd, linea.encode("utf-8"))
                    os.fsync(fd)
                except OSError as e:
                    raise RechazoOrden(Motivo.ALMACEN_ILEGIBLE, "no se puede escribir") from e
            finally:
                os.close(fd)  # libera el flock
