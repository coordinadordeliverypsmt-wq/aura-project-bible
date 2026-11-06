"""Fijación de la clave pública (SPKI) del servidor TLS de HC-1 (A3, DP-DELEGACION-NODOS §11).

Hoy el nodo solo ancla el servidor a la CA privada: cualquier certificado de esa CA serviría. Esta fijación exige
que el sha256 de la `SubjectPublicKeyInfo` del certificado del par esté en un conjunto fijado (actual + SIGUIENTE,
para rotar sin desactivar la validación). Reglas:

* Fallo CERRADO: huella fuera del conjunto, certificado caducado/aún no válido, certificado ilegible o fijación
  exigida sin ningún pin => `ErrorFijacion` y la conexión se cierra. Nunca se vuelve a "solo CA".
* Se comprueba DENTRO del handshake (antes de que el cliente envíe nada, p. ej. la credencial NATS de `CONNECT`),
  no después: `aplicar_fijacion` sustituye las clases `SSLObject`/`SSLSocket` del contexto por variantes que
  verifican al terminar `do_handshake`. Un fallo se propaga como `ssl.SSLCertVerificationError`.
* TLS 1.3 como mínimo (A3) cuando hay fijación, `CERT_REQUIRED` y `VERIFY_X509_STRICT`. Un contexto sin verificación
  o sin CA cargada se rechaza al construir: la fijación se SUMA a la validación de la CA, nunca la sustituye.
* Aprovisionamiento inicial FUERA DE BANDA (TOFU prohibido): este módulo no aprende pines, solo los aplica.
"""

from __future__ import annotations

import hashlib
import re
import ssl
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization

_RE_PIN = re.compile(r"[0-9a-f]{64}")
MAX_PINES = 2
"""Actual + siguiente. Más de dos ampliaría la ventana de aceptación sin motivo."""


class ErrorFijacion(Exception):
    """La identidad del servidor no coincide con la fijada. El mensaje no incluye huellas ni valores del par."""


def huella_spki(cert_der: bytes) -> str:
    """sha256 (hex) de la SubjectPublicKeyInfo DER del certificado."""
    try:
        cert = x509.load_der_x509_certificate(cert_der)
    except ValueError as e:
        raise ErrorFijacion("certificado ilegible") from e
    spki = cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki).hexdigest()


def normalizar_pines(pines: Iterable[str] | None, exigida: bool = True) -> frozenset[str]:
    lista = list(pines or ())
    if not all(isinstance(p, str) for p in lista):
        raise ErrorFijacion("pin mal formado o repetido")
    conjunto = frozenset(p.lower() for p in lista)
    if any(_RE_PIN.fullmatch(p) is None for p in conjunto) or len(conjunto) != len(lista):
        raise ErrorFijacion("pin mal formado o repetido")
    if len(conjunto) > MAX_PINES:
        raise ErrorFijacion("demasiados pines (máximo actual + siguiente)")
    if exigida and not conjunto:
        raise ErrorFijacion("fijación exigida pero sin ningún pin configurado")
    return conjunto


def verificar_fijacion(
    cert_der: bytes | None,
    pines: Iterable[str] | None,
    *,
    exigida: bool = True,
    ahora: float | None = None,
) -> str:
    """Comprueba pin y vigencia. Devuelve la huella aceptada o lanza `ErrorFijacion` (fallo cerrado)."""
    conjunto = normalizar_pines(pines, exigida)
    if not cert_der:
        raise ErrorFijacion("el par no presentó certificado")
    huella = huella_spki(cert_der)
    cert = x509.load_der_x509_certificate(cert_der)
    t = time.time() if ahora is None else ahora
    desde = _utc(getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before)
    hasta = _utc(getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after)
    if t > hasta:
        raise ErrorFijacion("certificado del servidor caducado")
    if t < desde:
        raise ErrorFijacion("certificado del servidor aún no es válido")
    if conjunto and huella not in conjunto:
        raise ErrorFijacion("la clave pública del servidor no es la fijada")
    return huella


def _utc(dt: datetime) -> float:
    # cryptography >= 42 ofrece `not_valid_*_utc` (con tzinfo); < 42 devuelve datetimes naive en UTC
    return dt.replace(tzinfo=UTC).timestamp() if dt.tzinfo is None else dt.timestamp()


def _comprobador(
    pines: frozenset[str], exigida: bool, reloj: Callable[[], float] | None
) -> Callable[[bytes | None], None]:
    def comprobar(cert_der: bytes | None) -> None:
        try:
            verificar_fijacion(cert_der, pines, exigida=exigida, ahora=reloj() if reloj else None)
        except ErrorFijacion as e:
            raise ssl.SSLCertVerificationError(1, f"fijación SPKI: {e}") from e

    return comprobar


def aplicar_fijacion(
    ctx: ssl.SSLContext,
    pines: Iterable[str] | None,
    *,
    exigida: bool = True,
    reloj: Callable[[], float] | None = None,
) -> ssl.SSLContext:
    """Endurece `ctx` (TLS >= 1.3 y verificación del pin al terminar el handshake). Pines inválidos o ausentes con
    `exigida` => `ErrorFijacion` AL CONSTRUIR (no se llega a conectar)."""
    conjunto = normalizar_pines(pines, exigida)
    if ctx.verify_mode != ssl.CERT_REQUIRED:
        raise ErrorFijacion("el contexto debe exigir verificación de certificado (CERT_REQUIRED)")
    if not ctx.get_ca_certs():
        raise ErrorFijacion("el contexto no tiene ninguna CA cargada")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.verify_flags |= ssl.VERIFY_X509_STRICT
    comprobar = _comprobador(conjunto, exigida, reloj)

    class ObjetoFijado(ssl.SSLObject):
        def do_handshake(self) -> None:
            super().do_handshake()  # SSLWantRead/Write se propagan hasta completar
            comprobar(self.getpeercert(binary_form=True))

    class ZocaloFijado(ssl.SSLSocket):
        def do_handshake(self, block: bool = False) -> None:
            super().do_handshake(block)
            try:
                comprobar(self.getpeercert(binary_form=True))
            except ssl.SSLCertVerificationError:
                self.close()
                raise

    ctx.sslobject_class = ObjetoFijado  # type: ignore[misc]
    ctx.sslsocket_class = ZocaloFijado  # type: ignore[misc]
    return ctx
