"""PKI de HC-1 (`entorno/nodos/red_hc1.py`) frente a la verificación ESTRICTA de Python 3.13.

Python 3.13 activa `ssl.VERIFY_X509_STRICT` en `create_default_context`: una CA sin keyUsage/basicConstraints se
rechaza con «CA cert does not include key usage extension». Aquí se exige explícitamente en cualquier versión, con un
handshake TLS REAL contra nats-server (sin mocks). Todo en 127.0.0.1, puerto libre y AURA_RED en tmp_path.
"""

from __future__ import annotations

import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

_WS = Path(__file__).resolve().parents[2]
_RED_HC1 = _WS.parent / "entorno" / "nodos" / "red_hc1.py"


def _binario() -> str | None:
    return shutil.which("nats-server") or next(
        (str(p) for p in [Path.home() / ".local" / "bin" / "nats-server"] if p.is_file()), None
    )


pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Red:
    def __init__(self, raiz: Path) -> None:
        self.red = raiz / "red"
        self.puerto = _puerto_libre()
        self.entorno = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(raiz / "home"),
            "AURA_RED": str(self.red),
            "AURA_RED_PUERTO": str(self.puerto),
            "AURA_RED_ESCUCHA": "127.0.0.1",
        }
        (raiz / "home").mkdir()

    @property
    def pki(self) -> Path:
        return self.red / "pki"

    def orden(self, *args: str) -> str:
        r = subprocess.run(
            [sys.executable, str(_RED_HC1), *args], env=self.entorno, capture_output=True, text=True, timeout=60
        )
        assert r.returncode == 0, r.stderr
        return r.stdout

    def texto_cert(self, fichero: str) -> str:
        r = subprocess.run(
            ["openssl", "x509", "-in", str(self.pki / fichero), "-noout", "-text"],
            capture_output=True, text=True, check=True,
        )  # fmt: skip
        return r.stdout


@pytest.fixture
def red(tmp_path: Path) -> Red:
    r = Red(tmp_path)
    r.orden("preparar")
    return r


@pytest.fixture
def nats(red: Red, tmp_path: Path) -> Iterator[Red]:
    binario = _binario()
    if binario is None:
        pytest.skip("nats-server no está en el PATH ni en ~/.local/bin")
    log = open(tmp_path / "nats.log", "ab")  # noqa: SIM115 - se cierra en el finally
    proc = subprocess.Popen([binario, "-c", str(red.red / "nats" / "nats.conf")], stdout=log, stderr=subprocess.STDOUT)
    try:
        limite = time.monotonic() + 15
        while True:
            assert proc.poll() is None, "nats-server terminó al arrancar"
            try:
                with socket.create_connection(("127.0.0.1", red.puerto), timeout=0.2):
                    break
            except OSError:
                assert time.monotonic() < limite, "nats-server no abrió el puerto"
                time.sleep(0.05)
        yield red
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log.close()


def _contexto_estricto(ca: Path) -> ssl.SSLContext:
    """Exactamente lo que hace el nodo con Python 3.13, forzado también en 3.12."""
    ctx = ssl.create_default_context(cafile=str(ca))
    ctx.verify_flags |= ssl.VERIFY_X509_STRICT
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _handshake(puerto: int, ctx: ssl.SSLContext) -> str:
    """NATS: INFO en claro y luego upgrade TLS. Devuelve el subject del certificado verificado."""
    with socket.create_connection(("127.0.0.1", puerto), timeout=5) as crudo:
        assert crudo.recv(4096).startswith(b"INFO")
        with ctx.wrap_socket(crudo) as tls:
            return str(tls.getpeercert()["subject"])


def test_handshake_tls_estricto_contra_nats_server_real_acepta_la_pki_generada(nats: Red) -> None:
    ctx = _contexto_estricto(nats.pki / "ca.crt")
    assert ctx.verify_flags & ssl.VERIFY_X509_STRICT
    assert "aura-hc1" in _handshake(nats.puerto, ctx)


def test_la_ca_y_el_servidor_llevan_las_extensiones_que_exige_el_modo_estricto(red: Red) -> None:
    ca = red.texto_cert("ca.crt")
    assert "CA:TRUE" in ca and "Certificate Sign" in ca and "CRL Sign" in ca
    assert "Subject Key Identifier" in ca
    srv = red.texto_cert("servidor.crt")
    assert "CA:FALSE" in srv and "Digital Signature" in srv
    assert "TLS Web Server Authentication" in srv
    assert "Subject Key Identifier" in srv and "Authority Key Identifier" in srv
    assert "IP Address:127.0.0.1" in srv and "DNS:localhost" in srv


def test_regenerar_pki_conserva_la_anterior_y_deja_una_valida_sin_tocar_credenciales(nats: Red) -> None:
    usuarios = nats.red / "nats" / "usuarios.json"
    antes = usuarios.read_text()
    ca_vieja = (nats.pki / "ca.crt").read_bytes()
    nats.orden("regenerar-pki")
    anteriores = [p for p in nats.red.iterdir() if p.name.startswith("pki.anterior-")]
    assert len(anteriores) == 1
    assert (anteriores[0] / "ca.crt").read_bytes() == ca_vieja
    assert (anteriores[0] / "servidor.key").is_file()
    assert (nats.pki / "ca.crt").read_bytes() != ca_vieja
    assert usuarios.read_text() == antes
    assert oct(anteriores[0].stat().st_mode & 0o777) == "0o700"
    assert (nats.pki / "servidor.crt").is_file() and (nats.pki / "servidor.key").is_file()
