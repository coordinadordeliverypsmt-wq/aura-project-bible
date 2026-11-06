"""Apoyo TLS de las pruebas de delegación: CA y certificados de servidor de PRUEBA, generados en tmp_path."""

from __future__ import annotations

import datetime as dt
import ipaddress
import socket
import ssl
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _nombre(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


@dataclass
class ParCert:
    cert: Path
    clave: Path
    der: bytes


class AcPrueba:
    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self._clave = ec.generate_private_key(ec.SECP256R1())
        ahora = dt.datetime.now(dt.UTC)
        self._cert = (
            x509.CertificateBuilder()
            .subject_name(_nombre("CA de prueba"))
            .issuer_name(_nombre("CA de prueba"))
            .public_key(self._clave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(ahora - dt.timedelta(days=1))
            .not_valid_after(ahora + dt.timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )  # fmt: skip
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(self._clave.public_key()), critical=False)
            .sign(self._clave, hashes.SHA256())
        )
        self.ca_pem = raiz / "ca.crt"
        self.ca_pem.write_bytes(self._cert.public_bytes(serialization.Encoding.PEM))

    def servidor(self, nombre: str, *, caducado: bool = False) -> ParCert:
        clave = ec.generate_private_key(ec.SECP256R1())
        ahora = dt.datetime.now(dt.UTC)
        desde, hasta = (
            (ahora - dt.timedelta(days=10), ahora - dt.timedelta(days=1))
            if caducado
            else (ahora - dt.timedelta(minutes=5), ahora + dt.timedelta(days=30))
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(_nombre(nombre))
            .issuer_name(self._cert.subject)
            .public_key(clave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(desde)
            .not_valid_after(hasta)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )  # fmt: skip
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(self._clave.public_key()), False)
            .sign(self._clave, hashes.SHA256())
        )
        cpem, kpem = self.raiz / f"{nombre}.crt", self.raiz / f"{nombre}.key"
        cpem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        kpem.write_bytes(
            clave.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        kpem.chmod(0o600)
        return ParCert(cpem, kpem, cert.public_bytes(serialization.Encoding.DER))


def contexto_cliente(ca: Path) -> ssl.SSLContext:
    """Exactamente lo que construye el nodo hoy (CA privada, sin nombre, modo estricto)."""
    ctx = ssl.create_default_context(cafile=str(ca))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.verify_flags |= ssl.VERIFY_X509_STRICT
    return ctx


class ServidorTls:
    """Servidor TLS en 127.0.0.1:puerto-libre. Registra los bytes de aplicación recibidos. Se cierra con `cerrar`."""

    def __init__(self, par: ParCert, *, solo_tls12: bool = False) -> None:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(par.cert), str(par.clave))
        if solo_tls12:
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        self._ctx = ctx
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self._sock.settimeout(0.2)
        self.puerto = self._sock.getsockname()[1]
        self.recibido: list[bytes] = []
        self._fin = threading.Event()
        self._hilo = threading.Thread(target=self._servir, daemon=True)
        self._hilo.start()

    def _servir(self) -> None:
        while not self._fin.is_set():
            try:
                crudo, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            try:
                crudo.settimeout(2)
                with self._ctx.wrap_socket(crudo, server_side=True) as tls:
                    datos = tls.recv(1024)
                    self.recibido.append(datos)
                    tls.sendall(b"pong")
            except (OSError, ssl.SSLError):
                pass

    def cerrar(self) -> None:
        self._fin.set()
        self._hilo.join(3)
        self._sock.close()
