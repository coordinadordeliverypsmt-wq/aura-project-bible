"""Resolutor mDNS contra el avahi REAL de esta máquina (HC-1): el caso del defecto de 2026-10-04."""

from __future__ import annotations

import ipaddress
import shutil
import socket
import subprocess

import pytest

from aura_skeleton.adapters.resolutor_mdns import resolver_ipv4


def _avahi_activo() -> bool:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return False
    return subprocess.run([systemctl, "is-active", "--quiet", "avahi-daemon"], check=False).returncode == 0


def _ips_locales() -> set[str]:
    ip = shutil.which("ip")
    assert ip is not None, "falta el binario ip"
    salida = subprocess.run([ip, "-4", "-o", "addr"], capture_output=True, text=True, check=True).stdout
    return {linea.split()[3].split("/")[0] for linea in salida.splitlines() if len(linea.split()) > 3}


def _nombre_anunciado() -> str:
    """El nombre `.local` que avahi ANUNCIA de verdad, preguntado a avahi por D-Bus.

    No es siempre `hostname + ".local"`: ante un conflicto de nombre en la red, avahi se renombra solo
    (RFC 6762 §9). Medido 2026-10-25 22:07: «Host name conflict, retrying with …-2», luego «…-3», y desde
    entonces `<hostname>.local` no lo anuncia nadie (`avahi-resolve` agota el tiempo fuera de AURA) mientras
    `<hostname>-3.local` resuelve. Sin `gdbus` se usa el nombre del sistema, que es el caso sin conflicto."""
    gdbus = shutil.which("gdbus")
    if gdbus is not None:
        try:
            r = subprocess.run(
                [
                    gdbus,
                    "call",
                    "--system",
                    "--dest",
                    "org.freedesktop.Avahi",
                    "--object-path",
                    "/",
                    "--method",
                    "org.freedesktop.Avahi.Server.GetHostNameFqdn",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            return socket.gethostname() + ".local"
        # Salida de gdbus: ('nombre.local',)
        if r.returncode == 0 and r.stdout.strip().startswith("('"):
            return r.stdout.strip()[2:].split("'", 1)[0]
    return socket.gethostname() + ".local"


def test_resuelve_el_nombre_local_de_esta_maquina_a_una_de_sus_ipv4():
    if not _avahi_activo():
        pytest.skip("avahi-daemon no está activo: esta máquina no se anuncia por mDNS")
    nombre = _nombre_anunciado()
    assert nombre.endswith(".local"), nombre
    ip = resolver_ipv4(nombre, timeout_s=3.0)
    assert ip is not None, f"avahi activo pero {nombre} no resolvió"
    assert isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
    assert ip in _ips_locales()
