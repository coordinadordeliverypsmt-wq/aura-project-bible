"""Firmas Ed25519 de la delegación (A1/A2): claves, firma con separación de dominio y verificador.

Adaptador de la biblioteca `cryptography`. La CLAVE PRIVADA nunca se serializa en un mensaje, un log ni una
excepción de este módulo. Las claves de prueba se generan en directorios temporales: nada aquí escribe secretos
en el repositorio.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from collections.abc import Iterable, Mapping
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ..core.delegacion import Motivo, RechazoOrden, Verificador, empaquetar_sobre, es_texto_id, mensaje_con_dominio
from .jsonl_durable import ErrorDurable, abrir_bloqueado, anexar, fsync_directorio


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
    return _kids_de(crudo)


def _kids_de(crudo: bytes) -> frozenset[str]:
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


_RE_SHA256 = re.compile(r"[0-9a-f]{64}")


def _ilegible_ancla(detalle: str) -> RechazoOrden:
    return RechazoOrden(Motivo.REVOCACION_ILEGIBLE, detalle)


def _leer_ancla(ancla: Path) -> tuple[int, str] | None:
    """`(tam, sha256)` del ancla MÁS ALTA anotada, o `None` si el ancla no existe. Ancla vacía (caída tras crearla y antes
    de escribir) = existencia sin tamaño. Cualquier anomalía (enlace, ajena, escribible, línea mal formada) => ilegible."""
    try:
        fd = os.open(ancla, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise _ilegible_ancla("ancla ilegible") from e
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
            raise _ilegible_ancla("ancla con permisos inseguros, ajena o no regular")
        trozos = []
        while True:
            b = os.read(fd, 1 << 16)
            if not b:
                break
            trozos.append(b)
    except OSError as e:
        raise _ilegible_ancla("ancla ilegible") from e
    finally:
        os.close(fd)
    crudo = b"".join(trozos)
    if crudo and not crudo.endswith(b"\n"):
        raise _ilegible_ancla("ancla truncada")
    mejor: tuple[int, str] = (0, hashlib.sha256(b"").hexdigest())
    for linea in crudo.splitlines():
        try:
            o = json.loads(linea)
        except (ValueError, RecursionError) as e:
            raise _ilegible_ancla("ancla no válida") from e
        if not isinstance(o, dict) or set(o) != {"tam", "sha256"}:
            raise _ilegible_ancla("ancla mal formada")
        tam, h = o["tam"], o["sha256"]
        if not isinstance(tam, int) or isinstance(tam, bool) or tam < 0 or not isinstance(h, str):
            raise _ilegible_ancla("ancla mal formada")
        if not _RE_SHA256.fullmatch(h):
            raise _ilegible_ancla("ancla mal formada")
        if tam == mejor[0] and h != mejor[1] and tam > 0:
            raise _ilegible_ancla("ancla contradictoria")
        if tam > mejor[0]:
            mejor = (tam, h)
    return mejor


def _anotar_ancla(ancla: Path, contenido: bytes) -> None:
    """Comprueba la lista contra el ancla y, si CRECIÓ, añade al ancla (append-only, sin borrar ni renombrar nada) el
    tamaño y el hash ACTUALES. Lista más corta que lo anclado, o con el prefijo anclado cambiado (truncada, vaciada,
    reescrita) => `REVOCACION_ILEGIBLE`."""
    previo = _leer_ancla(ancla)
    if previo is not None:
        tam, h = previo
        if len(contenido) < tam or hashlib.sha256(contenido[:tam]).hexdigest() != h:
            raise _ilegible_ancla("la lista de revocados se truncó o se alteró tras anclarla")
        if len(contenido) == tam and os.lstat(ancla).st_size > 0:
            return  # nada nuevo que anclar
    linea = (
        json.dumps({"tam": len(contenido), "sha256": hashlib.sha256(contenido).hexdigest()}, sort_keys=True) + "\n"
    ).encode()
    try:
        creada = not os.path.lexists(ancla)
        fd = os.open(ancla, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    except OSError as e:
        raise _ilegible_ancla("no se puede anclar la existencia de la lista") from e
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
            raise _ilegible_ancla("ancla con permisos inseguros, ajena o no regular")
        os.write(fd, linea)
        os.fsync(fd)
        if creada:
            fsync_directorio(ancla.parent)
    except OSError as e:
        raise _ilegible_ancla("no se puede anclar la existencia de la lista") from e
    finally:
        os.close(fd)


def revocar(ruta: Path, kid: str, ancla: Path) -> None:
    """Añade un kid a la lista de forma durable (append + fsync, y fsync del directorio si se crea el fichero) y anota el
    ANCLA (existencia + tamaño + hash) bajo el mismo cerrojo: revocar también crea el ancla (3.ª revisión, BAJO 2)."""
    if not es_texto_id(kid):
        raise ErrorClave("kid de revocación mal formado")
    try:
        with abrir_bloqueado(ruta) as fd:
            anexar(fd, {"kid": kid})
            os.lseek(fd, 0, os.SEEK_SET)
            trozos = []
            while True:
                b = os.read(fd, 1 << 16)
                if not b:
                    break
                trozos.append(b)
            _anotar_ancla(ancla, b"".join(trozos))
    except ErrorDurable as e:
        raise ErrorClave("no se puede registrar la revocación") from e
    except RechazoOrden as e:
        raise ErrorClave("no se puede anclar la revocación (lista o ancla ilegibles)") from e


class ListaRevocados:
    """Lista de revocados VIVA con ANCLA DE EXISTENCIA Y TAMAÑO (C2, 3.ª revisión). Se llama como `Callable[[], frozenset[str]]`.

    * Se RELEE en cada llamada (bajo `flock` compartido, con `O_NOFOLLOW|O_NONBLOCK`; un FIFO o dispositivo se rechaza):
      una revocación posterior al arranque surte efecto en la siguiente verificación, sin reiniciar nada.
    * La primera vez que el fichero EXISTE (o al `revocar`) se anota el ANCLA: existencia, tamaño y sha256 del contenido
      (append-only, durable). Si después el fichero desaparece, queda ilegible, ajeno o corrupto, o se TRUNCA/VACÍA/
      reescribe por debajo de lo anclado => `RechazoOrden(REVOCACION_ILEGIBLE)`: FALLO CERRADO, no «sin revocados». Un nodo
      que nunca tuvo lista (ni ancla) sigue funcionando con la lista vacía.

    LÍMITE declarado: con el mismo uid, quien borre el fichero Y el ancla reabre el hueco; la integridad física exige
    otro usuario o almacenamiento protegido.
    """

    def __init__(self, ruta: Path, ancla: Path) -> None:
        self._ruta = Path(ruta)
        self._ancla = Path(ancla)

    @staticmethod
    def _ilegible(detalle: str) -> RechazoOrden:
        return RechazoOrden(Motivo.REVOCACION_ILEGIBLE, detalle)

    def _hay_ancla(self) -> bool:
        try:
            os.lstat(self._ancla)
        except FileNotFoundError:
            return False
        except OSError as e:
            raise self._ilegible("ancla ilegible") from e
        return True

    def __call__(self) -> frozenset[str]:
        try:
            fd = os.open(self._ruta, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            if self._hay_ancla():
                raise self._ilegible("la lista de revocados existía y ya no está") from None
            return frozenset()
        except OSError as e:
            raise self._ilegible("lista ilegible") from e
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
                raise self._ilegible("lista con permisos inseguros, ajena o no regular")
            fcntl.flock(fd, fcntl.LOCK_SH)
            trozos = []
            while True:
                b = os.read(fd, 1 << 16)
                if not b:
                    break
                trozos.append(b)
            crudo = b"".join(trozos)
            kids = _kids_de(crudo)
            _anotar_ancla(self._ancla, crudo)
        except ErrorClave as e:
            raise self._ilegible(str(e)) from e
        except OSError as e:
            raise self._ilegible("lista ilegible") from e
        finally:
            os.close(fd)
        return kids
