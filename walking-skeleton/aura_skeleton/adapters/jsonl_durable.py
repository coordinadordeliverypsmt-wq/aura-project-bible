"""Primitivas de ficheros JSONL DURABLES compartidas por el almacén del nodo y el diario de HC-1 (N1, M-2, M-3, B-4).

Garantías (cada una con prueba):

* Directorio propio y 0700. Si existe con permisos más abiertos, o de otro uid, o no es un directorio: FALLO CERRADO.
  Al crearlo se hace `fsync` del directorio padre; al crear el fichero, `fsync` del directorio que lo contiene
  (sin eso la entrada del directorio puede perderse tras una caída aunque el contenido esté en disco).
* Fichero 0600, abierto con `O_NOFOLLOW`, cerrojo `flock` exclusivo durante cada operación.
* Cada registro es UNA línea escrita con un único `os.write` en `O_APPEND` y seguida de `fsync`.
* Línea FINAL truncada (caída a mitad de escritura): se DETECTA (se devuelven los bytes descartados), se recorta el
  fichero a la última línea completa y se conservan TODOS los registros válidos. Esa orden/registro nunca se
  confirmó al llamante (la escritura no había terminado), así que descartarlo no rompe ninguna promesa hecha.
  Una línea ilegible en el MEDIO no es una caída: es corrupción y falla cerrado.

LÍMITE declarado: con el mismo uid, quien pueda editar el fichero puede reescribirlo.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class ErrorDurable(Exception):
    """Fichero o directorio inseguro, ilegible o corrupto. El mensaje nunca incluye contenido leído."""


def fsync_directorio(directorio: Path) -> None:
    fd = os.open(directorio, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def asegurar_directorio(ruta: Path) -> None:
    """Crea (0700, con fsync del padre) o valida un directorio existente: propio, 0700, no enlace simbólico."""
    try:
        os.lstat(ruta)
    except FileNotFoundError:
        try:
            ruta.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(ruta, 0o700)
            fsync_directorio(ruta.parent)
        except OSError as e:
            raise ErrorDurable("no se puede crear el directorio") from e
    try:
        st = os.lstat(ruta)
    except OSError as e:
        raise ErrorDurable("directorio ilegible") from e
    if not stat.S_ISDIR(st.st_mode):
        raise ErrorDurable("la ruta no es un directorio propio")
    if st.st_uid != os.getuid():
        raise ErrorDurable("el directorio no pertenece al usuario del proceso")
    if st.st_mode & 0o077:
        raise ErrorDurable("permisos inseguros: el directorio debe ser 0700")


@contextmanager
def abrir_bloqueado(ruta: Path) -> Iterator[int]:
    """Abre (creando 0600) y bloquea en exclusiva. Al cerrar se libera el cerrojo."""
    creado = False
    try:
        try:
            fd = os.open(ruta, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            creado = True
        except FileExistsError:
            fd = os.open(ruta, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW)
    except OSError as e:
        raise ErrorDurable("no se puede abrir") from e
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or st.st_mode & 0o077 or not stat.S_ISREG(st.st_mode):
            raise ErrorDurable("fichero inseguro: debe ser un fichero propio 0600")
        if creado:
            os.fsync(fd)
            fsync_directorio(ruta.parent)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    except OSError as e:
        raise ErrorDurable("error de E/S") from e
    finally:
        os.close(fd)  # libera el flock


def leer_registros(fd: int) -> tuple[list[dict[str, Any]], int]:
    """Lee todos los registros. Devuelve `(registros, bytes_truncados_descartados)`.

    Recorta una línea final incompleta (y la hace durable). Cualquier otra anomalía lanza `ErrorDurable`."""
    os.lseek(fd, 0, os.SEEK_SET)
    trozos = []
    while True:
        b = os.read(fd, 1 << 16)
        if not b:
            break
        trozos.append(b)
    datos = b"".join(trozos)
    descartados = 0
    if datos and not datos.endswith(b"\n"):
        corte = datos.rfind(b"\n") + 1
        descartados = len(datos) - corte
        os.ftruncate(fd, corte)
        os.fsync(fd)
        datos = datos[:corte]
    registros: list[dict[str, Any]] = []
    for linea in datos.splitlines():
        try:
            o = json.loads(linea)
        except (ValueError, RecursionError) as e:
            raise ErrorDurable("línea ilegible") from e
        if not isinstance(o, dict):
            raise ErrorDurable("línea inválida")
        registros.append(o)
    return registros, descartados


def anexar(fd: int, registro: dict[str, Any]) -> None:
    """Un único `write` de una línea y `fsync` ANTES de volver."""
    linea = (json.dumps(registro, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        escritos = os.write(fd, linea)
        if escritos != len(linea):
            raise ErrorDurable("escritura parcial")
        os.fsync(fd)
    except OSError as e:
        raise ErrorDurable("no se puede escribir") from e
