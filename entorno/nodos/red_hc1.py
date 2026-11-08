"""Plano de red de AURA en HC-1: PKI privada, configuración de NATS y alta/baja de nodos (DP-NODO-01 §4.5).

Herramienta de OPERACIÓN, solo stdlib + `openssl`. No es runtime de AURA: prepara el servidor NATS (ADR-0018,
E2) que el receptor y los nodos usan. Todo el material sensible vive en `AURA_RED` (por defecto `~/.aura-red`),
NUNCA en el repositorio: CA, clave del servidor, contraseñas de nodo. Directorios 0700, ficheros 0600.

Uso:
    python3 red_hc1.py preparar              # CA + certificado del servidor + usuario del receptor + nats.conf
    python3 red_hc1.py alta <nodo_id>        # crea el usuario del nodo; imprime su credencial en stdout
    python3 red_hc1.py baja <nodo_id>        # revoca el usuario del nodo
    python3 red_hc1.py conf                  # regenera nats.conf desde usuarios.json
    python3 red_hc1.py regenerar-pki         # mueve pki a pki.anterior-<ts> (sin borrar) y genera otra; usuarios.json intacto

Permisos de NATS:
    receptor          subscribe nodo.latido.>        publish: nada
    nodo-<id>         publish   nodo.latido.<id>     subscribe: nada; sin respuestas
Un nodo NO puede publicar en nombre de otro, ni leer nada.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(os.environ.get("AURA_RED", os.path.expanduser("~/.aura-red")))
PKI = RAIZ / "pki"
NATS = RAIZ / "nats"
USUARIOS = NATS / "usuarios.json"
CONF = NATS / "nats.conf"
PUERTO = int(os.environ.get("AURA_RED_PUERTO", "4222"))
#: Dirección de escucha. 0.0.0.0 en producción (los nodos llegan por la LAN); las pruebas usan 127.0.0.1.
ESCUCHA = os.environ.get("AURA_RED_ESCUCHA", "0.0.0.0")
_ID = re.compile(r"^[0-9a-f]{32}$")


def _privado(ruta: Path) -> None:
    ruta.mkdir(parents=True, exist_ok=True)
    if ruta.is_symlink():
        sys.exit(f"rechazado: {ruta} es un enlace simbólico")
    os.chmod(ruta, 0o700)


def _escribir(ruta: Path, texto: str) -> None:
    """Escritura atómica con 0600 desde el primer byte (umask), nunca visible a medio escribir."""
    tmp = ruta.with_name(ruta.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(texto)
    os.replace(tmp, ruta)
    os.chmod(ruta, 0o600)


def _openssl(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def _pki() -> None:
    _privado(PKI)
    if not (PKI / "ca.crt").exists():
        _openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(PKI / "ca.key"))
        _openssl(
            "req",
            "-x509",
            "-new",
            "-key",
            str(PKI / "ca.key"),
            "-sha256",
            "-days",
            "3650",
            "-subj",
            "/CN=AURA red privada CA",
            "-out",
            str(PKI / "ca.crt"),
            # Python 3.13 verifica en modo estricto (VERIFY_X509_STRICT): la CA debe declararse CA y su uso.
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-addext",
            "subjectKeyIdentifier=hash",
        )
    if not (PKI / "servidor.crt").exists():
        host = socket.gethostname()
        ext = PKI / "servidor.ext"
        _escribir(
            ext,
            f"subjectAltName=DNS:{host},DNS:{host}.local,DNS:localhost,IP:127.0.0.1\n"
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature\n"  # EC (ECDSA): sin keyEncipherment
            "extendedKeyUsage=serverAuth\n"
            "subjectKeyIdentifier=hash\n"
            "authorityKeyIdentifier=keyid,issuer\n",
        )
        _openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(PKI / "servidor.key"))
        _openssl(
            "req", "-new", "-key", str(PKI / "servidor.key"), "-subj", "/CN=aura-hc1", "-out", str(PKI / "servidor.csr")
        )
        _openssl(
            "x509",
            "-req",
            "-in",
            str(PKI / "servidor.csr"),
            "-CA",
            str(PKI / "ca.crt"),
            "-CAkey",
            str(PKI / "ca.key"),
            "-CAcreateserial",
            "-days",
            "825",
            "-sha256",
            "-extfile",
            str(ext),
            "-out",
            str(PKI / "servidor.crt"),
        )
    for f in PKI.iterdir():
        os.chmod(f, 0o600)
    # La CA pública se reparte a los nodos: legible solo por el usuario igualmente.


def regenerar_pki() -> None:
    """Mueve la PKI actual a `pki.anterior-<ts>` (sin borrarla) y genera una nueva. usuarios.json no cambia."""
    _privado(RAIZ)
    if PKI.is_symlink():
        sys.exit(f"rechazado: {PKI} es un enlace simbólico")
    if PKI.exists():
        destino = RAIZ / f"pki.anterior-{time.strftime('%Y%m%dT%H%M%S')}"
        n = 0
        while destino.exists():
            n += 1
            destino = RAIZ / f"pki.anterior-{time.strftime('%Y%m%dT%H%M%S')}-{n}"
        PKI.rename(destino)
        print(f"PKI anterior conservada en {destino}")
    _pki()
    print(f"PKI regenerada: {PKI} (reparte el nuevo ca.crt a los nodos y reinicia nats-server)")


def _cargar() -> dict:
    return json.loads(USUARIOS.read_text()) if USUARIOS.exists() else {}


def _guardar(usuarios: dict) -> None:
    _privado(NATS)
    _escribir(USUARIOS, json.dumps(usuarios, indent=1, sort_keys=True))


def _conf(usuarios: dict) -> str:
    def regla(subjects: list[str]) -> str:
        # Una lista `allow` vacía NO significa «nada» en NATS: se niega todo explícitamente.
        return f"{{allow: {json.dumps(subjects)}}}" if subjects else '{deny: [">"]}'

    def entrada(nombre: str, d: dict) -> str:
        return (
            f'    {{user: "{nombre}", password: "{d["password"]}", permissions: {{'
            f"publish: {regla(d['publish'])}, subscribe: {regla(d['subscribe'])}}}}}"
        )

    lineas = ",\n".join(entrada(n, d) for n, d in sorted(usuarios.items()))
    return (
        "# GENERADO por entorno/nodos/red_hc1.py — no editar a mano.\n"
        f'server_name: "aura-hc1"\nlisten: "{ESCUCHA}:{PUERTO}"\n'
        "max_payload: 65536\nmax_connections: 64\nmax_pending: 1048576\n"
        "tls {\n"
        f'  cert_file: "{PKI / "servidor.crt"}"\n  key_file: "{PKI / "servidor.key"}"\n'
        "  timeout: 5\n}\n"
        f"authorization {{\n  users: [\n{lineas}\n  ]\n}}\n"
    )


def conf() -> None:
    _escribir(CONF, _conf(_cargar()))


def preparar() -> None:
    _privado(RAIZ)
    _pki()
    usuarios = _cargar()
    if "receptor" not in usuarios:
        usuarios["receptor"] = {"password": secrets.token_hex(24), "publish": [], "subscribe": ["nodo.latido.>"]}
        _guardar(usuarios)
    conf()
    _escribir(RAIZ / "receptor.credencial", usuarios["receptor"]["password"] + "\n")
    print(f"listo: {CONF}")


def alta(nodo_id: str) -> None:
    if not _ID.match(nodo_id):
        sys.exit("nodo_id inválido: se esperan 32 hexadecimales")
    usuarios = _cargar()
    nombre = f"nodo-{nodo_id}"
    if nombre not in usuarios:
        usuarios[nombre] = {"password": secrets.token_hex(24), "publish": [f"nodo.latido.{nodo_id}"], "subscribe": []}
        _guardar(usuarios)
    conf()
    # stdout = la credencial: el llamador la canaliza por SSH al nodo sin tocar disco intermedio.
    sys.stdout.write(json.dumps({"usuario": nombre, "password": usuarios[nombre]["password"]}))


def baja(nodo_id: str) -> None:
    if not _ID.match(nodo_id):
        sys.exit("nodo_id inválido: se esperan 32 hexadecimales")
    usuarios = _cargar()
    usuarios.pop(f"nodo-{nodo_id}", None)
    _guardar(usuarios)
    conf()
    print(f"revocado nodo-{nodo_id}")


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "preparar":
        preparar()
    elif orden == "regenerar-pki":
        regenerar_pki()
    elif orden == "conf":
        conf()
    elif orden in ("alta", "baja") and len(sys.argv) == 3:
        (alta if orden == "alta" else baja)(sys.argv[2])
    else:
        sys.exit(__doc__)
