"""A3/B-6 — la fijación SPKI exige un contexto que verifica la cadena, y un corte a mitad de handshake falla CERRADO."""

from __future__ import annotations

import asyncio
import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from aura_skeleton.adapters.fijacion_spki import ErrorFijacion, _utc, aplicar_fijacion, huella_spki
from tests.tls_apoyo import AcPrueba, ServidorTls, contexto_cliente


@pytest.fixture
def ac(tmp_path: Path) -> AcPrueba:
    return AcPrueba(tmp_path)


# --- B-6 ----------------------------------------------------------------------------------------------------------


def test_b6_un_contexto_sin_verificacion_obligatoria_se_rechaza_al_construir(ac: AcPrueba) -> None:
    pin = [huella_spki(ac.servidor("hc1").der)]
    aplicar_fijacion(contexto_cliente(ac.ca_pem), pin)  # control
    for modo in (ssl.CERT_NONE, ssl.CERT_OPTIONAL):
        ctx = contexto_cliente(ac.ca_pem)
        ctx.verify_mode = modo
        with pytest.raises(ErrorFijacion, match="CERT_REQUIRED"):
            aplicar_fijacion(ctx, pin)


def test_b6_un_contexto_sin_ninguna_ca_cargada_se_rechaza_al_construir(ac: AcPrueba) -> None:
    pin = [huella_spki(ac.servidor("hc1").der)]
    vacio = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # CERT_REQUIRED por defecto, pero sin CA: nada validaría
    assert vacio.verify_mode == ssl.CERT_REQUIRED and not vacio.get_ca_certs()
    vacio.check_hostname = False
    with pytest.raises(ErrorFijacion, match="CA"):
        aplicar_fijacion(vacio, pin)


def test_a3_el_contexto_conserva_cert_required_strict_y_tls13_tras_aplicar_la_fijacion(ac: AcPrueba) -> None:
    pin = [huella_spki(ac.servidor("hc1").der)]
    ctx = ssl.create_default_context(cafile=str(ac.ca_pem))  # sin STRICT explícito (Python 3.12 no lo activa)
    ctx.check_hostname = False
    quitar = ssl.VERIFY_X509_STRICT
    ctx.verify_flags &= ~quitar
    assert not ctx.verify_flags & ssl.VERIFY_X509_STRICT
    out = aplicar_fijacion(ctx, pin)
    assert out is ctx
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.verify_flags & ssl.VERIFY_X509_STRICT
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3


def test_b6_utc_es_igual_con_datetimes_ingenuos_y_con_zona() -> None:
    naive = datetime(2030, 1, 2, 3, 4, 5)
    aware = naive.replace(tzinfo=UTC)
    assert _utc(naive) == _utc(aware) == 1893553445.0
    otra_zona = naive.replace(tzinfo=UTC).astimezone(timezone(timedelta(hours=5)))
    assert _utc(otra_zona) == _utc(aware)  # la misma hora absoluta en otra zona


# --- A3: corte a mitad del handshake ---------------------------------------------------------------------------


class ServidorQueCorta:
    """TCP crudo en 127.0.0.1: lee el ClientHello y responde según `modo`; registra los TIPOS de registro TLS recibidos."""

    def __init__(self, modo: str) -> None:
        self.modo = modo
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._sock.settimeout(0.2)
        self.puerto = self._sock.getsockname()[1]
        self.recibido = b""
        self._fin = threading.Event()
        self._hilo = threading.Thread(target=self._servir, daemon=True)
        self._hilo.start()

    def _servir(self) -> None:
        while not self._fin.is_set():
            try:
                c, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            with c:
                c.settimeout(1)
                try:
                    if self.modo != "cierra_antes_de_leer":
                        self.recibido += c.recv(65536)
                    if self.modo == "respuesta_a_medias":
                        c.sendall(b"\x16\x03\x03\x05\x00" + b"\x02\x00\x00")  # cabecera de registro de 1280 B, solo 3
                    elif self.modo == "basura":
                        c.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                except OSError:
                    pass

    def tipos_de_registro(self) -> list[int]:
        """Tipos de los registros TLS completos o cabeceras recibidas (0x16 = handshake, 0x17 = datos de aplicación)."""
        datos, tipos = self.recibido, []
        while len(datos) >= 5:
            tipos.append(datos[0])
            datos = datos[5 + int.from_bytes(datos[3:5], "big") :]
        return tipos

    def cerrar(self) -> None:
        self._fin.set()
        self._hilo.join(3)
        self._sock.close()


@pytest.fixture
def cortador() -> list[ServidorQueCorta]:
    lista: list[ServidorQueCorta] = []
    yield lista  # type: ignore[misc]
    for s in lista:
        s.cerrar()


@pytest.mark.parametrize("modo", ["cierra_antes_de_leer", "cierra_tras_el_clienthello", "respuesta_a_medias", "basura"])
def test_a3_un_corte_a_mitad_del_handshake_falla_cerrado_y_no_envia_datos(
    ac: AcPrueba, cortador: list[ServidorQueCorta], modo: str
) -> None:
    srv = ServidorQueCorta(modo)
    cortador.append(srv)
    ctx = aplicar_fijacion(contexto_cliente(ac.ca_pem), [huella_spki(ac.servidor("hc1").der)])
    enviado = False
    with pytest.raises((ssl.SSLError, OSError, EOFError)):
        with socket.create_connection(("127.0.0.1", srv.puerto), timeout=3) as crudo:
            with ctx.wrap_socket(crudo) as tls:
                enviado = True  # solo se alcanza si el handshake «terminó»
                tls.sendall(b"CONNECT {}")
    assert enviado is False
    assert set(srv.tipos_de_registro()) <= {0x16}  # a lo sumo el ClientHello: ni un registro de aplicación (0x17)


def test_a3_el_corte_tambien_falla_cerrado_con_asyncio_como_nats_py(
    ac: AcPrueba, cortador: list[ServidorQueCorta]
) -> None:
    srv = ServidorQueCorta("respuesta_a_medias")
    cortador.append(srv)
    ctx = aplicar_fijacion(contexto_cliente(ac.ca_pem), [huella_spki(ac.servidor("hc1").der)])

    async def conectar() -> None:
        r, w = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", srv.puerto, ssl=ctx), 8)
        w.write(b"CONNECT {}")  # nunca debe alcanzarse
        await w.drain()
        w.close()

    with pytest.raises((ssl.SSLError, OSError, EOFError, asyncio.IncompleteReadError)):
        asyncio.run(conectar())
    assert set(srv.tipos_de_registro()) <= {0x16}


def test_a3_control_el_servidor_legitimo_con_el_pin_correcto_si_conecta(ac: AcPrueba) -> None:
    par = ac.servidor("hc1")
    s = ServidorTls(par)
    try:
        ctx = aplicar_fijacion(contexto_cliente(ac.ca_pem), [huella_spki(par.der)])
        with socket.create_connection(("127.0.0.1", s.puerto), timeout=3) as crudo, ctx.wrap_socket(crudo) as tls:
            tls.sendall(b"ping")
            assert tls.recv(8) == b"pong"
    finally:
        s.cerrar()
