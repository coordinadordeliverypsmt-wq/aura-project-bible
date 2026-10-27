"""Firmas Ed25519 de la delegación (A1/A2): claves, firma con separación de dominio y verificador.

Adaptador de la biblioteca `cryptography`. La CLAVE PRIVADA nunca se serializa en un mensaje, un log ni una
excepción de este módulo. Las claves de prueba se generan en directorios temporales: nada aquí escribe secretos
en el repositorio.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ..core.delegacion import Verificador, empaquetar_sobre, es_texto_id, mensaje_con_dominio
from .jsonl_durable import ErrorDurable, abrir_bloqueado, anexar


class ErrorClave(Exception):
    """Clave ilegible o con permisos inseguros. El mensaje nunca contiene material de clave."""


class Firmante:
    """Posee una clave privada Ed25519 y firma `dominio || payload`. No expone la clave."""

    def __init__(self, kid: str, clave: Ed25519PrivateKey) -> None:
        self._kid = kid
        self.__clave = clave

    @property
    def kid(self) -> str:
        return self._kid

    def publica(self) -> Ed25519PublicKey:
        return self.__clave.public_key()

    def firmar(self, dominio: bytes, payload: bytes) -> bytes:
        """Devuelve el SOBRE de cable `{p, f, kid}`."""
        firma = self.__clave.sign(mensaje_con_dominio(dominio, payload))
        return empaquetar_sobre(self._kid, payload, firma)

    def __repr__(self) -> str:  # nunca material de clave en un repr/log
        return f"Firmante(kid={self._kid!r})"


def generar_firmante(kid: str) -> Firmante:
    return Firmante(kid, Ed25519PrivateKey.generate())


def bytes_publica(clave: Ed25519PublicKey) -> bytes:
    return clave.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def publica_desde_bytes(raw: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(raw)


def verificador_de(claves: Mapping[str, Ed25519PublicKey], revocados: Iterable[str] = ()) -> Verificador:
    """Verificador por `kid`. Kid desconocido, REVOCADO, firma mala o entrada rara => False (nunca lanza).

    `revocados` es la lista de kids retirados (p. ej. claves de NODO que HC-1 ya no acepta): una firma matemáticamente
    válida de un kid revocado NO vale."""
    retirados = frozenset(revocados)

    def verificar(kid: str, mensaje: bytes, firma: bytes) -> bool:
        clave = claves.get(kid)
        if clave is None or kid in retirados:
            return False
        try:
            clave.verify(firma, mensaje)
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True

    return verificar


def guardar_clave_privada(ruta: Path, clave: Ed25519PrivateKey) -> None:
    """Escribe PKCS8 PEM con 0600 (O_EXCL: no pisa una clave existente). El directorio debe ser 0700."""
    pem = clave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    try:
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        raise ErrorClave("no se puede crear la clave (¿ya existe?)") from e
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
        f.flush()
        os.fsync(f.fileno())


def cargar_clave_privada(ruta: Path) -> Ed25519PrivateKey:
    """Lee la clave exigiendo fichero 0600 y directorio 0700 propios. Fallo CERRADO."""
    try:
        st = ruta.stat()
        dst = ruta.parent.stat()
    except OSError as e:
        raise ErrorClave("clave ilegible") from e
    if st.st_mode & 0o077 or dst.st_mode & 0o077:
        raise ErrorClave("permisos inseguros: fichero 0600 en directorio 0700")
    if st.st_uid != os.getuid():
        raise ErrorClave("la clave no pertenece al usuario del proceso")
    try:
        clave = serialization.load_pem_private_key(ruta.read_bytes(), password=None)
    except (ValueError, TypeError, OSError) as e:
        raise ErrorClave("clave no válida") from e
    if not isinstance(clave, Ed25519PrivateKey):
        raise ErrorClave("la clave no es Ed25519")
    return clave


def cargar_revocados(ruta: Path) -> frozenset[str]:
    """Lista PERSISTENTE de kids revocados: JSONL append-only, una línea `{"kid": "..."}` por revocación. Fichero ausente
    => lista vacía (aún no se revocó nada); presente pero ilegible, ajeno, escribible por otros, truncado o mal formado =>
    `ErrorClave` (FALLO CERRADO: nunca se ignora una lista de revocación que no se puede leer)."""
    try:
        st = ruta.stat()
    except FileNotFoundError:
        return frozenset()
    except OSError as e:
        raise ErrorClave("lista de revocación ilegible") from e
    if st.st_uid != os.getuid() or st.st_mode & 0o022:
        raise ErrorClave("lista de revocación con permisos inseguros o ajena")
    try:
        crudo = ruta.read_bytes()
    except OSError as e:
        raise ErrorClave("lista de revocación ilegible") from e
    if crudo and not crudo.endswith(b"\n"):
        raise ErrorClave("lista de revocación truncada")
    kids: set[str] = set()
    for linea in crudo.splitlines():
        try:
            o = json.loads(linea)
        except (ValueError, RecursionError) as e:
            raise ErrorClave("lista de revocación no válida") from e
        if not isinstance(o, dict) or set(o) != {"kid"} or not es_texto_id(o["kid"]):
            raise ErrorClave("lista de revocación mal formada")
        kids.add(o["kid"])
    return frozenset(kids)


def revocar(ruta: Path, kid: str) -> None:
    """Añade un kid a la lista de forma durable (append + fsync, y fsync del directorio si se crea el fichero)."""
    if not es_texto_id(kid):
        raise ErrorClave("kid de revocación mal formado")
    try:
        with abrir_bloqueado(ruta) as fd:
            anexar(fd, {"kid": kid})
    except ErrorDurable as e:
        raise ErrorClave("no se puede registrar la revocación") from e
