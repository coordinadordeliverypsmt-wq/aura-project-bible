"""Resolutor mDNS propio (DP-NODO-01 §4.5: la IP es configuración, nunca identidad). Sin red: el envío se inyecta."""

from __future__ import annotations

import socket
import struct
from collections.abc import Iterator

from aura_skeleton import observability as obs
from aura_skeleton.adapters import resolutor_mdns as r

NOMBRE = "hc-1.local"
IP = "192.168.20.202"


def _qname(nombre: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode() for p in nombre.split(".")) + b"\x00"


def _registro(nombre_bytes: bytes, tipo: int, rdata: bytes, clase: int = 0x8001) -> bytes:
    return nombre_bytes + struct.pack(">HHIH", tipo, clase, 120, len(rdata)) + rdata


def _respuesta(registros: list[bytes], preguntas: bytes = b"", qd: int = 0, flags: int = 0x8400) -> bytes:
    return struct.pack(">HHHHHH", 0, flags, qd, len(registros), 0, 0) + preguntas + b"".join(registros)


def _a(nombre: str, ip: str) -> bytes:
    return _registro(_qname(nombre), 1, socket.inet_aton(ip))


# --- consulta ----------------------------------------------------------------------------------------------


def test_la_consulta_tiene_cabecera_qname_qtype_a_y_qclass_in_con_bit_qu():
    consulta = r._construir_consulta("Hc-1.local")
    assert consulta[:12] == struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)
    assert consulta[12:] == b"\x04Hc-1\x05local\x00" + struct.pack(">HH", 1, 0x8001)


def test_la_consulta_tolera_el_punto_final():
    assert r._construir_consulta("hc-1.local.") == r._construir_consulta("hc-1.local")


# --- parser ------------------------------------------------------------------------------------------------


def test_el_parser_extrae_la_ipv4_de_un_registro_a():
    assert r._parsear_respuesta(_respuesta([_a(NOMBRE, IP)]), NOMBRE) == IP


def test_el_parser_ignora_mayusculas_y_punto_final():
    assert r._parsear_respuesta(_respuesta([_a("HC-1.Local", IP)]), "hc-1.LOCAL.") == IP


def test_el_parser_sigue_punteros_de_compresion():
    pregunta = _qname(NOMBRE) + struct.pack(">HH", 1, 0x8001)
    puntero = b"\xc0\x0c"  # apunta al QNAME de la pregunta (offset 12)
    paquete = _respuesta([_registro(puntero, 1, socket.inet_aton(IP))], preguntas=pregunta, qd=1)
    assert r._parsear_respuesta(paquete, NOMBRE) == IP


def test_el_parser_sigue_punteros_dentro_de_un_nombre_parcial():
    base = _qname("hc-1.local")  # en offset 12 tras la cabecera
    # el registro es «hc-1» + puntero a «local» (offset 12 + 5)
    nombre = b"\x04hc-1\xc0" + bytes([12 + 5])
    paquete = _respuesta([base + struct.pack(">HHIH", 16, 1, 0, 0), _registro(nombre, 1, socket.inet_aton(IP))])
    # el primer registro (TXT vacío) ocupa el offset 12 con el nombre completo
    assert r._parsear_respuesta(paquete, NOMBRE) == IP


def test_nombre_distinto_devuelve_none():
    assert r._parsear_respuesta(_respuesta([_a("otro.local", IP)]), NOMBRE) is None


def test_un_registro_aaaa_solo_devuelve_none():
    aaaa = _registro(_qname(NOMBRE), 28, socket.inet_pton(socket.AF_INET6, "fe80::1"))
    assert r._parsear_respuesta(_respuesta([aaaa]), NOMBRE) is None


def test_con_varios_registros_elige_el_a_correcto():
    aaaa = _registro(_qname(NOMBRE), 28, socket.inet_pton(socket.AF_INET6, "fe80::1"))
    paquete = _respuesta([_a("otro.local", "10.0.0.9"), aaaa, _a(NOMBRE, IP)])
    assert r._parsear_respuesta(paquete, NOMBRE) == IP


def test_una_consulta_no_es_una_respuesta():
    assert r._parsear_respuesta(_respuesta([_a(NOMBRE, IP)], flags=0x0000), NOMBRE) is None


def test_paquetes_truncados_o_basura_devuelven_none_sin_excepcion():
    valido = _respuesta([_a(NOMBRE, IP)])
    for basura in (b"", b"\x00", valido[:11], valido[:20], valido[:-1], b"\xff" * 64, bytes(range(256))):
        assert r._parsear_respuesta(basura, NOMBRE) is None


def test_un_bucle_de_punteros_no_cuelga_ni_lanza():
    bucle = _respuesta([b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 0, 4) + b"\x01\x02\x03\x04"])
    assert r._parsear_respuesta(bucle, NOMBRE) is None


def test_rdlength_incorrecto_en_un_a_se_ignora():
    malo = _registro(_qname(NOMBRE), 1, b"\x01\x02\x03")
    assert r._parsear_respuesta(_respuesta([malo]), NOMBRE) is None


# --- resolver_ipv4 -----------------------------------------------------------------------------------------


def test_un_nombre_que_no_es_local_devuelve_none_sin_enviar():
    llamadas: list[bytes] = []

    def enviar(consulta: bytes, timeout_s: float) -> Iterator[bytes]:
        llamadas.append(consulta)
        return iter(())

    for nombre in ("example.com", "192.168.20.38", "", "local", "hc-1.localhost", "hc-1.local.example"):
        assert r.resolver_ipv4(nombre, enviar=enviar) is None
    assert llamadas == []


def test_resuelve_con_la_primera_respuesta_valida_y_envia_la_consulta_y_el_timeout():
    vistos: list[tuple[bytes, float]] = []

    def enviar(consulta: bytes, timeout_s: float) -> Iterator[bytes]:
        vistos.append((consulta, timeout_s))
        yield b"basura"
        yield _respuesta([_a("otro.local", "10.0.0.9")])
        yield _respuesta([_a(NOMBRE, IP)])

    assert r.resolver_ipv4(NOMBRE, timeout_s=1.5, enviar=enviar) == IP
    assert vistos == [(r._construir_consulta(NOMBRE), 1.5)]


def test_sin_respuestas_por_timeout_devuelve_none():
    assert r.resolver_ipv4(NOMBRE, enviar=lambda c, t: iter(())) is None


def test_la_basura_se_ignora_y_solo_se_registra_el_tipo_de_error(monkeypatch):
    registros: list[tuple[str, str]] = []
    monkeypatch.setattr(obs, "log", lambda nivel, modulo, msg, *a, **k: registros.append((nivel, msg)))
    resultado = r.resolver_ipv4(NOMBRE, enviar=lambda c, t: iter([b"\x00" * 5, _respuesta([_a(NOMBRE, IP)])]))
    assert resultado == IP
    assert registros and all(n == "WARN" for n, _ in registros)
    assert all("\\x00" not in m for _, m in registros)


def test_hay_un_tope_de_paquetes_leidos():
    leidos = 0

    def infinito(consulta: bytes, timeout_s: float) -> Iterator[bytes]:
        nonlocal leidos
        while True:
            leidos += 1
            yield b"\x00"

    assert r.resolver_ipv4(NOMBRE, enviar=infinito) is None
    assert leidos == r.MAX_PAQUETES


def test_un_fallo_del_envio_devuelve_none_y_registra_solo_el_tipo(monkeypatch):
    registros: list[str] = []
    monkeypatch.setattr(obs, "log", lambda nivel, modulo, msg, *a, **k: registros.append(msg))

    def roto(consulta: bytes, timeout_s: float) -> Iterator[bytes]:
        raise OSError("secreto-de-red")

    assert r.resolver_ipv4(NOMBRE, enviar=roto) is None
    assert registros and all("secreto-de-red" not in m and "OSError" in m for m in registros)
