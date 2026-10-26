"""Identidad persistente de un nodo (DP-NODO-01 §4.1).

`<ruta_datos>/nodo/identidad.json` = `{"nodo_id": <hex32>, "creado": <ISO-8601 UTC>}`. El id lo da un generador
aleatorio (uuid4) y se escribe UNA vez: NO depende de la IP, la MAC, el hostname ni el usuario, así que sobrevive
a cambios de red y a reinicios del proceso.

SEGURIDAD: el directorio `nodo` es 0700 y el fichero 0600; la escritura es atómica (temporal en el mismo
directorio + `os.replace`); si `nodo` o el fichero son enlaces simbólicos se rechaza (no se sigue un enlace hacia
una identidad ajena); permisos más abiertos de lo debido se corrigen.

HONESTIDAD (INV-9): si el fichero existe pero está ilegible o corrupto se lanza `IdentidadCorrupta`. NUNCA se
regenera en silencio: eso crearía «otro nodo» y rompería la continuidad del historial. Decidir qué hacer con una
identidad corrupta es del operador. Un enlace simbólico se trata igual (identidad no confiable).
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

_MODO_DIR = 0o700
_MODO_FICHERO = 0o600
_NODO_ID = re.compile(r"^[0-9a-f]{32}\Z")
_SUBDIR = "nodo"
_FICHERO = "identidad.json"


class IdentidadCorrupta(Exception):  # noqa: N818 - nombre fijado por el contrato DP-NODO-01 §4.1
    """La identidad existe pero no es confiable (corrupta, ilegible o enlace simbólico). No se regenera."""


def _ahora() -> datetime:
    return datetime.now(UTC)


def cargar_o_crear(
    ruta_datos: str,
    generar: Callable[[], uuid.UUID] = uuid.uuid4,
    reloj: Callable[[], datetime] = _ahora,
) -> str:
    """Devuelve el `nodo_id` persistido, creándolo (una sola vez) si no existe."""
    directorio = Path(ruta_datos) / _SUBDIR
    fichero = directorio / _FICHERO
    _preparar_directorio(directorio)
    if os.path.lexists(fichero):
        return _leer(fichero)
    nodo_id = generar().hex
    if not _NODO_ID.match(nodo_id):
        raise ValueError("el generador no produjo un id de 32 hex minúsculas")
    cuerpo = {"nodo_id": nodo_id, "creado": reloj().astimezone(UTC).isoformat()}
    _escribir_atomico(directorio, fichero, cuerpo)
    return nodo_id


def _preparar_directorio(directorio: Path) -> None:
    if directorio.is_symlink():
        raise IdentidadCorrupta("el directorio del nodo es un enlace simbólico")
    directorio.parent.mkdir(parents=True, exist_ok=True)
    try:
        directorio.mkdir(mode=_MODO_DIR)
    except FileExistsError:
        pass
    if not directorio.is_dir():
        raise IdentidadCorrupta("la ruta del nodo no es un directorio")
    if stat.S_IMODE(directorio.stat().st_mode) != _MODO_DIR:  # el umask pudo recortar o relajar el modo
        os.chmod(directorio, _MODO_DIR)


def _leer(fichero: Path) -> str:
    if fichero.is_symlink():
        raise IdentidadCorrupta("el fichero de identidad es un enlace simbólico")
    try:
        # O_NOFOLLOW cierra la carrera entre la comprobación anterior y la apertura.
        fd = os.open(fichero, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as f:
            cuerpo = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError) as e:  # ValueError cubre JSON inválido y UnicodeDecodeError
        raise IdentidadCorrupta(f"identidad ilegible: {type(e).__name__}") from e
    nodo_id = cuerpo.get("nodo_id") if isinstance(cuerpo, dict) else None
    if not isinstance(nodo_id, str) or not _NODO_ID.match(nodo_id):
        raise IdentidadCorrupta("nodo_id ausente o con formato inválido")
    if stat.S_IMODE(fichero.stat().st_mode) != _MODO_FICHERO:
        os.chmod(fichero, _MODO_FICHERO)
    return nodo_id


def _escribir_atomico(directorio: Path, fichero: Path, cuerpo: dict[str, str]) -> None:
    fd, tmp = tempfile.mkstemp(dir=directorio, prefix=".identidad-", suffix=".tmp")  # mkstemp crea con 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cuerpo, f)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, _MODO_FICHERO)
        os.replace(tmp, fichero)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
