"""Resolutor mDNS mínimo (RFC 6762), solo stdlib: traduce `<host>.local` a IPv4 sin depender del sistema.

Existe porque el nodo (antiX, sin sudo ni libnss-mdns) no resuelve `.local` por el sistema y HC-1 cambia de IP por
DHCP (DP-NODO-01 §4.5: la IP es configuración, nunca identidad). Envía UNA consulta tipo A, clase IN con el bit QU
(respuesta unicast) a 224.0.0.251:5353 desde un puerto efímero y devuelve la primera IPv4 cuyo nombre coincide.

Garantías: nunca lanza hacia fuera; no hace bucles sin límite (`MAX_PAQUETES` y plazo); solo registra el TIPO de error.
El parser es una función pura (`_parsear_respuesta`) y el envío es inyectable (`enviar`).
"""

from __future__ import annotations

import select
import socket
import struct
import time
from collections.abc import Callable, Iterable, Iterator

from .. import observability as obs

GRUPO_MDNS = "224.0.0.251"
PUERTO_MDNS = 5353
TIMEOUT_POR_DEFECTO_S = 2.0
#: Tope de datagramas examinados por resolución: una red ruidosa no puede mantener el bucle vivo.
MAX_PAQUETES = 64
_SUFIJO = ".local"
_TIPO_A = 1
_CLASE_IN_QU = 0x8001
_BIT_RESPUESTA = 0x8000
_MAX_SALTOS = 16
_MAX_UDP = 9000
_MODULO = "resolutor-mdns"

Enviar = Callable[[bytes, float], Iterable[bytes]]


def _normalizar(nombre: str) -> str:
    return nombre.rstrip(".").casefold()


def _construir_consulta(nombre: str) -> bytes:
    cabecera = struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)
    etiquetas = b"".join(bytes([len(p)]) + p.encode("utf-8") for p in nombre.rstrip(".").split("."))
    return cabecera + etiquetas + b"\x00" + struct.pack(">HH", _TIPO_A, _CLASE_IN_QU)


def _leer_nombre(datos: bytes, pos: int) -> tuple[str, int]:
    """Lee un nombre DNS (con compresión). Devuelve (nombre, offset tras el nombre en el flujo original)."""
    etiquetas: list[str] = []
    siguiente: int | None = None
    saltos = 0
    while True:
        largo = datos[pos]
        if largo & 0xC0 == 0xC0:
            destino = ((largo & 0x3F) << 8) | datos[pos + 1]
            if siguiente is None:
                siguiente = pos + 2
            saltos += 1
            if saltos > _MAX_SALTOS:
                raise ValueError("demasiados punteros de compresión")
            pos = destino
        elif largo & 0xC0:
            raise ValueError("etiqueta inválida")
        elif largo == 0:
            return ".".join(etiquetas), (pos + 1 if siguiente is None else siguiente)
        else:
            fin = pos + 1 + largo
            if fin > len(datos):
                raise ValueError("etiqueta truncada")
            etiquetas.append(datos[pos + 1 : fin].decode("utf-8", errors="replace"))
            pos = fin


def _parsear_estricto(datos: bytes, nombre: str) -> str | None:
    flags, preguntas, *registros = struct.unpack(">xxHHHHH", datos[:12])
    if not flags & _BIT_RESPUESTA:
        return None
    pos = 12
    for _ in range(preguntas):
        _, pos = _leer_nombre(datos, pos)
        pos += 4
    objetivo = _normalizar(nombre)
    for _ in range(sum(registros)):
        propietario, pos = _leer_nombre(datos, pos)
        tipo, _clase, _ttl, largo = struct.unpack(">HHIH", datos[pos : pos + 10])
        pos += 10
        fin = pos + largo
        if fin > len(datos):
            raise ValueError("registro truncado")
        if tipo == _TIPO_A and largo == 4 and _normalizar(propietario) == objetivo:
            return socket.inet_ntoa(datos[pos:fin])
        pos = fin
    return None


def _parsear_respuesta(datos: bytes, nombre: str, al_fallar: Callable[[Exception], None] | None = None) -> str | None:
    """Primera IPv4 (registro A) cuyo propietario es `nombre`; `None` si no hay o el paquete es inválido.

    Un paquete inválido nunca lanza: se avisa a `al_fallar` (si existe) y se devuelve `None`.
    """
    try:
        return _parsear_estricto(datos, nombre)
    except (ValueError, IndexError, struct.error) as e:
        if al_fallar is not None:
            al_fallar(e)
        return None


def _enviar_udp(consulta: bytes, timeout_s: float) -> Iterator[bytes]:
    """Envía la consulta y cede los datagramas recibidos hasta agotar el plazo."""
    limite = time.monotonic() + timeout_s
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        s.sendto(consulta, (GRUPO_MDNS, PUERTO_MDNS))
        while (restante := limite - time.monotonic()) > 0:
            listos, _, _ = select.select([s], [], [], restante)
            if listos:
                yield s.recv(_MAX_UDP)


def _avisar_paquete_invalido(error: Exception) -> None:
    obs.log("WARN", _MODULO, f"mDNS: respuesta ignorada ({type(error).__name__})")


def resolver_ipv4(nombre: str, timeout_s: float = TIMEOUT_POR_DEFECTO_S, enviar: Enviar = _enviar_udp) -> str | None:
    """Resuelve `<host>.local` a IPv4 por mDNS. `None` si no es `.local`, si no hay respuesta o si algo falla."""
    if not _normalizar(nombre).endswith(_SUFIJO) or len(_normalizar(nombre)) <= len(_SUFIJO):
        return None
    try:
        for leidos, paquete in enumerate(enviar(_construir_consulta(nombre), timeout_s), start=1):
            ip = _parsear_respuesta(paquete, nombre, _avisar_paquete_invalido)
            if ip is not None:
                return ip
            if leidos >= MAX_PAQUETES:
                break
    except OSError as e:
        obs.log("WARN", _MODULO, f"mDNS: fallo de red ({type(e).__name__})")
    return None
