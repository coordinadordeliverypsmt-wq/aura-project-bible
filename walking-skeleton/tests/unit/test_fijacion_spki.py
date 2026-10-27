"""A3 — fijación SPKI del servidor TLS (§11 A3). Servidor TLS local en 127.0.0.1; fallo CERRADO en cada caso."""

from __future__ import annotations

import asyncio
import socket
import ssl
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from aura_skeleton.adapters.fijacion_spki import (
    ErrorFijacion,
    aplicar_fijacion,
    huella_spki,
    normalizar_pines,
    verificar_fijacion,
)
from tests.tls_apoyo import AcPrueba, ServidorTls, contexto_cliente


@pytest.fixture
def ac(tmp_path: Path) -> AcPrueba:
    return AcPrueba(tmp_path)


@pytest.fixture
def servidores() -> Iterator[list[ServidorTls]]:
    lista: list[ServidorTls] = []
    yield lista
    for s in lista:
        s.cerrar()


def _hablar(puerto: int, ctx: ssl.SSLContext) -> bytes:
    with socket.create_connection(("127.0.0.1", puerto), timeout=3) as crudo, ctx.wrap_socket(crudo) as tls:
        tls.sendall(b"ping")
        return tls.recv(16)


def test_certificado_con_la_clave_fijada_se_acepta(ac: AcPrueba, servidores: list[ServidorTls]) -> None:
    par = ac.servidor("hc1")
    s = ServidorTls(par)
    servidores.append(s)
    ctx = aplicar_fijacion(contexto_cliente(ac.ca_pem), [huella_spki(par.der)])
    assert _hablar(s.puerto, ctx) == b"pong"


def test_misma_ca_pero_otra_clave_se_rechaza_y_no_se_envia_ni_un_byte(
    ac: AcPrueba, servidores: list[ServidorTls]
) -> None:
    legitimo, impostor = ac.servidor("hc1"), ac.servidor("impostor")
    s = ServidorTls(impostor)
    servidores.append(s)
    # control: sin fijación, el impostor (misma CA) SÍ pasa. Esa es la brecha que A3 cierra.
    assert _hablar(s.puerto, contexto_cliente(ac.ca_pem)) == b"pong"
    s.recibido.clear()
    ctx = aplicar_fijacion(contexto_cliente(ac.ca_pem), [huella_spki(legitimo.der)])
    with pytest.raises(ssl.SSLCertVerificationError):
        _hablar(s.puerto, ctx)
    time.sleep(0.3)
    assert s.recibido == [] or all(r == b"" for r in s.recibido), "el cliente envió datos a un servidor no fijado"


def test_certificado_caducado_se_rechaza_aunque_el_pin_coincida(ac: AcPrueba, servidores: list[ServidorTls]) -> None:
    par = ac.servidor("viejo", caducado=True)
    s = ServidorTls(par)
    servidores.append(s)
    # sin verificar la cadena (para aislar NUESTRA comprobación de la de OpenSSL) y con el pin correcto
    ctx = contexto_cliente(ac.ca_pem)
    ctx.verify_mode = ssl.CERT_NONE
    aplicar_fijacion(ctx, [huella_spki(par.der)])
    with pytest.raises(ssl.SSLCertVerificationError, match="caducado"):
        _hablar(s.puerto, ctx)


def test_verificar_fijacion_directa_caducado_futuro_y_vigente(ac: AcPrueba) -> None:
    caducado, vigente = ac.servidor("a", caducado=True), ac.servidor("b")
    pin = [huella_spki(vigente.der)]
    assert verificar_fijacion(vigente.der, pin) == huella_spki(vigente.der)  # control
    with pytest.raises(ErrorFijacion, match="caducado"):
        verificar_fijacion(caducado.der, [huella_spki(caducado.der)])
    with pytest.raises(ErrorFijacion, match="aún no es válido"):
        verificar_fijacion(vigente.der, pin, ahora=time.time() - 86400 * 365)
    with pytest.raises(ErrorFijacion, match="caducado"):
        verificar_fijacion(vigente.der, pin, ahora=time.time() + 86400 * 365)


def test_rotacion_con_doble_pin_acepta_el_actual_y_el_siguiente(ac: AcPrueba, servidores: list[ServidorTls]) -> None:
    actual, siguiente, otro = ac.servidor("actual"), ac.servidor("siguiente"), ac.servidor("otro")
    pines = [huella_spki(actual.der), huella_spki(siguiente.der)]
    for par in (actual, siguiente):
        s = ServidorTls(par)
        servidores.append(s)
        assert _hablar(s.puerto, aplicar_fijacion(contexto_cliente(ac.ca_pem), pines)) == b"pong"
    s = ServidorTls(otro)  # control: un tercero de la misma CA sigue rechazado durante la rotación
    servidores.append(s)
    with pytest.raises(ssl.SSLCertVerificationError):
        _hablar(s.puerto, aplicar_fijacion(contexto_cliente(ac.ca_pem), pines))


def test_fijacion_exigida_sin_pin_falla_cerrado_al_construir(ac: AcPrueba) -> None:
    for vacio in (None, [], ()):
        with pytest.raises(ErrorFijacion, match="sin ningún pin"):
            aplicar_fijacion(contexto_cliente(ac.ca_pem), vacio)
        with pytest.raises(ErrorFijacion, match="sin ningún pin"):
            verificar_fijacion(ac.servidor("x").der, vacio)


def test_pines_mal_formados_repetidos_o_de_mas_se_rechazan() -> None:
    bueno = "a" * 64
    assert normalizar_pines([bueno]) == {bueno}
    assert normalizar_pines([bueno, "b" * 64]) == {bueno, "b" * 64}
    for malo in (["xyz"], [bueno, bueno], [bueno, "b" * 64, "c" * 64], ["A" * 63], [5]):
        with pytest.raises(ErrorFijacion):
            normalizar_pines(malo)  # type: ignore[arg-type]


def test_sin_certificado_del_par_falla_cerrado() -> None:
    with pytest.raises(ErrorFijacion, match="no presentó"):
        verificar_fijacion(None, ["a" * 64])
    with pytest.raises(ErrorFijacion, match="ilegible"):
        verificar_fijacion(b"no es un certificado", ["a" * 64])


def test_se_exige_tls13_como_minimo(ac: AcPrueba, servidores: list[ServidorTls]) -> None:
    par = ac.servidor("hc1")
    s = ServidorTls(par, solo_tls12=True)
    servidores.append(s)
    assert _hablar(s.puerto, contexto_cliente(ac.ca_pem)) == b"pong"  # control: sin fijación, TLS 1.2 pasaría
    with pytest.raises(ssl.SSLError):
        _hablar(s.puerto, aplicar_fijacion(contexto_cliente(ac.ca_pem), [huella_spki(par.der)]))


def test_la_fijacion_tambien_actua_en_asyncio_donde_conecta_nats_py(
    ac: AcPrueba, servidores: list[ServidorTls]
) -> None:
    par, impostor = ac.servidor("hc1"), ac.servidor("impostor")
    bueno, malo = ServidorTls(par), ServidorTls(impostor)
    servidores += [bueno, malo]
    pines = [huella_spki(par.der)]

    async def conectar(puerto: int) -> bytes:
        ctx = aplicar_fijacion(contexto_cliente(ac.ca_pem), pines)
        r, w = await asyncio.open_connection("127.0.0.1", puerto, ssl=ctx)
        w.write(b"ping")
        await w.drain()
        dato = await r.read(8)
        w.close()
        return dato

    assert asyncio.run(conectar(bueno.puerto)) == b"pong"
    with pytest.raises(ssl.SSLCertVerificationError):
        asyncio.run(conectar(malo.puerto))
