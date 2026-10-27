"""Firmador de órdenes de HC-1 (N2): proceso aparte que custodia la clave y aplica POLÍTICA antes de firmar.

* La clave Ed25519 vive en un fichero 0600 de un directorio 0700; solo este proceso la lee y NUNCA se devuelve, se
  registra ni aparece en una excepción.
* Escucha en un socket Unix 0600 dentro de un directorio 0700 y comprueba `SO_PEERCRED` (uid del par permitido).
* **Nunca firma bytes arbitrarios.** El cliente envía CAMPOS de una petición cerrada; el firmador construye él mismo
  la orden (emisor, kid, `id_ejecucion` uuid4, `emitida_en`, `epoch_hc1`) y solo firma si: la capacidad está
  registrada y permitida, los argumentos cumplen su esquema, el destinatario es conocido y la vida (`vida_s`) es > 0
  y <= el tope. Todo lo demás se rechaza con un motivo del catálogo cerrado.
* Cada firma (y cada rechazo) queda en su PROPIO log append-only (`firmador.log.jsonl`) con hash y momento.

LIMITACIÓN DECLARADA (demostrada en `tests/unit/test_firmador_hc1.py`): con el MISMO uid, cualquier otro proceso
puede leer el fichero de clave. Esta separación de procesos protege contra errores y contra código que no pueda leer
ficheros del usuario, no contra un atacante con el mismo uid. La custodia física exige un usuario de sistema
distinto (crear usuarios requiere root: dependencia externa) o un HSM/TPM.
"""

from __future__ import annotations

import base64
import json
import os
import signal
import socket
import socketserver
import struct
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.delegacion import (
    CAPACIDADES,
    DOMINIO_ORDEN,
    V_ACTUAL,
    VIDA_MAX_S,
    Motivo,
    RechazoOrden,
    capacidad_registrada,
    hash_de,
    payload_orden,
)
from .firma_delegacion import ErrorClave, Firmante, cargar_clave_privada

PETICION_CAMPOS = frozenset({"tarea", "intento", "destinatario", "capacidad", "argumentos", "vida_s"})
LINEA_MAX = 16 * 1024
LOG_NOMBRE = "firmador.log.jsonl"


@dataclass(frozen=True)
class PoliticaFirmador:
    emisor: str
    kid: str
    destinatarios: frozenset[str]
    capacidades: frozenset[str]
    epoch: int
    vida_max_s: float = VIDA_MAX_S


class Firmador:
    """Lógica de política + firma + log. Sin sockets: se prueba directamente."""

    def __init__(
        self,
        firmante: Firmante,
        politica: PoliticaFirmador,
        ruta_log: Path,
        ahora: Callable[[], float] = time.time,
    ) -> None:
        if firmante.kid != politica.kid:
            raise ValueError("el kid de la clave no coincide con la política")
        self._firmante = firmante
        self._pol = politica
        self._log = Path(ruta_log)
        self._ahora = ahora
        self._hilo = threading.Lock()

    def _registrar(self, entrada: dict[str, Any]) -> None:
        linea = json.dumps(entrada, sort_keys=True, separators=(",", ":")) + "\n"
        with self._hilo:
            fd = os.open(self._log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, linea.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)

    def _validar(self, p: Mapping[str, Any]) -> float:
        if not isinstance(p, dict) or set(p) != PETICION_CAMPOS:
            raise RechazoOrden(Motivo.CAMPOS_DESCONOCIDOS, "petición cerrada")
        if p["destinatario"] not in self._pol.destinatarios:
            raise RechazoOrden(Motivo.DESTINATARIO_AJENO, "destinatario desconocido")
        cap = capacidad_registrada(str(p["capacidad"]), self._pol.capacidades)
        if not isinstance(p["argumentos"], dict):
            raise RechazoOrden(Motivo.ARGUMENTOS_INVALIDOS, "argumentos")
        cap.validar_argumentos(p["argumentos"])
        vida = p["vida_s"]
        if isinstance(vida, bool) or not isinstance(vida, (int, float)) or not vida > 0:
            raise RechazoOrden(Motivo.CAMPO_INVALIDO, "vida_s")
        if vida > self._pol.vida_max_s:
            raise RechazoOrden(Motivo.CADUCIDAD_EXCESIVA, "vida_s")
        return float(vida)

    def firmar(self, peticion: Mapping[str, Any], uid_par: int | None = None) -> tuple[bytes, str]:
        """Devuelve (sobre firmado, id_ejecucion) o lanza `RechazoOrden`. Registra la firma o el rechazo."""
        ahora = self._ahora()
        try:
            vida = self._validar(peticion)
            id_ejecucion = str(uuid.uuid4())
            campos = {
                "v": V_ACTUAL,
                "emisor": self._pol.emisor,
                "destinatario": peticion["destinatario"],
                "tarea": peticion["tarea"],
                "intento": peticion["intento"],
                "id_ejecucion": id_ejecucion,
                "capacidad": peticion["capacidad"],
                "argumentos": peticion["argumentos"],
                "emitida_en": ahora,
                "caduca_en": ahora + vida,
                "epoch_hc1": self._pol.epoch,
                "kid": self._pol.kid,
            }
            payload = payload_orden(campos)  # esquema completo: lo que no sea una orden no se firma
            sobre = self._firmante.firmar(DOMINIO_ORDEN, payload)
        except RechazoOrden as e:
            self._registrar({"tipo": "rechazo", "momento": ahora, "motivo": e.motivo.value, "uid_par": uid_par})
            raise
        self._registrar(
            {
                "tipo": "firma",
                "momento": ahora,
                "hash": hash_de(payload),
                "id_ejecucion": id_ejecucion,
                "destinatario": campos["destinatario"],
                "capacidad": campos["capacidad"],
                "uid_par": uid_par,
            }
        )
        return sobre, id_ejecucion


def uid_autorizado(uid: int, permitidos: frozenset[int]) -> bool:
    return uid in permitidos


def credenciales_del_par(conexion: socket.socket) -> tuple[int, int, int]:
    """(pid, uid, gid) del proceso al otro lado, según el kernel (`SO_PEERCRED`)."""
    datos = conexion.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", datos)
    return int(pid), int(uid), int(gid)


def _responder(wfile: Any, obj: dict[str, Any]) -> None:
    wfile.write((json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8"))
    wfile.flush()


def _fabrica_manejador(firmador: Firmador, permitidos: frozenset[int]) -> type[socketserver.StreamRequestHandler]:
    class Manejador(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            self.request.settimeout(5)
            try:
                _, uid, _ = credenciales_del_par(self.request)
                if not uid_autorizado(uid, permitidos):
                    _responder(self.wfile, {"ok": False, "motivo": "par_no_autorizado"})
                    return
                linea = self.rfile.readline(LINEA_MAX + 1)
                if len(linea) > LINEA_MAX:
                    _responder(self.wfile, {"ok": False, "motivo": Motivo.SOBRE_MALFORMADO.value})
                    return
                try:
                    peticion = json.loads(linea)
                except ValueError:
                    _responder(self.wfile, {"ok": False, "motivo": Motivo.SOBRE_MALFORMADO.value})
                    return
                try:
                    sobre, ident = firmador.firmar(peticion, uid)
                except RechazoOrden as e:
                    _responder(self.wfile, {"ok": False, "motivo": e.motivo.value})
                    return
                _responder(
                    self.wfile, {"ok": True, "sobre": base64.b64encode(sobre).decode("ascii"), "id_ejecucion": ident}
                )
            except (OSError, TimeoutError):
                return

    return Manejador


class ServidorFirmador(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def crear_servidor(firmador: Firmador, ruta_socket: Path, permitidos: frozenset[int]) -> ServidorFirmador:
    """Socket 0600 en directorio 0700. Fallo CERRADO si el directorio es más permisivo."""
    dir_ = ruta_socket.parent
    if dir_.stat().st_mode & 0o077:
        raise ErrorClave("el directorio del socket debe ser 0700")
    if ruta_socket.exists():
        ruta_socket.unlink()
    previo = os.umask(0o177)
    try:
        servidor = ServidorFirmador(str(ruta_socket), _fabrica_manejador(firmador, permitidos))
    finally:
        os.umask(previo)
    os.chmod(ruta_socket, 0o600)
    return servidor


def pedir_firma(ruta_socket: Path, peticion: Mapping[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """Cliente: envía una petición y devuelve `{"ok": True, "sobre": bytes, "id_ejecucion": str}` o `{"ok": False, ...}`."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(ruta_socket))
        s.sendall((json.dumps(peticion, separators=(",", ":")) + "\n").encode("utf-8"))
        datos = b""
        while not datos.endswith(b"\n"):
            trozo = s.recv(65536)
            if not trozo:
                break
            datos += trozo
    try:
        r = json.loads(datos)
    except ValueError:
        return {"ok": False, "motivo": Motivo.SOBRE_MALFORMADO.value}
    if r.get("ok"):
        r["sobre"] = base64.b64decode(r["sobre"])
    return dict(r)


def main(argv: list[str] | None = None) -> int:
    """`python -m aura_skeleton.adapters.firmador_hc1 <config.json>`. La config NO contiene la clave, solo su ruta."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("uso: firmador_hc1 <config.json>", file=sys.stderr)
        return 2
    conf = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    try:
        firmante = Firmante(conf["kid"], cargar_clave_privada(Path(conf["clave"])))
    except ErrorClave as e:
        print(f"firmador: {e}", file=sys.stderr)  # sin material de clave
        return 3
    politica = PoliticaFirmador(
        conf["emisor"],
        conf["kid"],
        frozenset(conf["destinatarios"]),
        frozenset(conf["capacidades"]) & frozenset(CAPACIDADES),
        int(conf["epoch"]),
        float(conf.get("vida_max_s", VIDA_MAX_S)),
    )
    firmador = Firmador(firmante, politica, Path(conf["log"]))
    permitidos = frozenset(conf.get("uids") or [os.getuid()])
    servidor = crear_servidor(firmador, Path(conf["socket"]), permitidos)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=servidor.shutdown, daemon=True).start())
    print("listo", flush=True)
    servidor.serve_forever()
    servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
