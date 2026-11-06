"""Firmador de órdenes de HC-1 (N2): proceso aparte que custodia la clave y aplica POLÍTICA antes de firmar.

* La clave Ed25519 vive en un fichero 0600 de un directorio 0700; solo este proceso la lee y NUNCA se devuelve, se
  registra ni aparece en una excepción.
* Escucha en un socket Unix 0600 dentro de un directorio 0700 y comprueba `SO_PEERCRED` (uid del par permitido).
* **Nunca firma bytes arbitrarios.** El cliente envía CAMPOS de una petición cerrada; el firmador construye él mismo
  la orden (emisor, kid, `id_ejecucion` uuid4, `emitida_en`, `epoch_hc1`) y solo firma si: la capacidad está
  registrada y permitida, los argumentos cumplen su esquema, el destinatario es conocido y la vida (`vida_s`) es > 0
  y <= el tope. Todo lo demás se rechaza con un motivo del catálogo cerrado.
* Cada firma (y cada rechazo) queda en su PROPIO log append-only (`firmador.log.jsonl`) con hash y momento, ENCADENADO:
  cada entrada lleva `prev` = sha256 de la línea anterior, y `verificar_cadena_log` detecta una línea editada, borrada
  o intercalada. NO detecta el recorte de las últimas líneas: eso exige un ancla externa (D-LOG-1).
* Límite de TASA configurable (ventana deslizante): superado, rechaza con `tasa_excedida` y lo registra. TODA petición
  consume cupo, también las rechazadas (BAJO c: un par que inunde con peticiones inválidas se frena igual), y para no
  inflar el log las escrituras de RECHAZO tienen un tope por ventana (`rechazos_log_max`): el resto se cuenta y la
  siguiente entrada de rechazo o de fallo escrita lo declara en `suprimidos`. Los FALLOS inesperados (`registrar_fallo`:
  petición ilegible, error interno) comparten ese mismo tope (3.ª revisión, MEDIO-6).
* El log se abre con `flock` exclusivo y `O_NOFOLLOW`, y el `prev` de cada entrada se toma del FICHERO bajo el cerrojo.
* `epoch_hc1` MONÓTONO y persistido: al arrancar el firmador lee `epoch.jsonl` (append-only, fsync); si el configurado es
  MENOR que el último usado, se NIEGA a arrancar; si no, usa `max(configurado, último + 1)` y lo anota ANTES de firmar
  nada. Cada reinicio sube el epoch, así que una orden vieja no se cuela.
* Un fallo de codificación (surrogates sueltos, JSON profundo, etc.) es un rechazo REGISTRADO, nunca mata el hilo.

LIMITACIÓN DECLARADA (demostrada en `tests/unit/test_firmador_hc1.py`): con el MISMO uid, cualquier otro proceso
puede leer el fichero de clave. Esta separación de procesos protege contra errores y contra código que no pueda leer
ficheros del usuario, no contra un atacante con el mismo uid. La custodia física exige un usuario de sistema
distinto (crear usuarios requiere root: dependencia externa) o un HSM/TPM.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import socket
import socketserver
import stat
import struct
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.delegacion import (
    ALG,
    CAPACIDADES,
    DOMINIO_ORDEN,
    V_ACTUAL,
    VIDA_MAX_S,
    Motivo,
    RechazoOrden,
    capacidad_registrada,
    hash_de,
    leer_json_estricto,
    payload_orden,
)
from .firma_delegacion import ErrorClave, Firmante, cargar_clave_privada
from .jsonl_durable import ErrorDurable, abrir_bloqueado, anexar, leer_registros

PETICION_CAMPOS = frozenset({"tarea", "intento", "destinatario", "capacidad", "argumentos", "vida_s"})
LINEA_MAX = 16 * 1024
LOG_NOMBRE = "firmador.log.jsonl"
EPOCH_NOMBRE = "epoch.jsonl"
CADENA_INICIAL = "0" * 64
TASA_MAX_DEFECTO = 60
TASA_VENTANA_S_DEFECTO = 60.0
RECHAZOS_LOG_MAX_DEFECTO = 20
_COLA_LOG_MAX = 64 * 1024


class ErrorFirmador(Exception):
    """El firmador se niega a arrancar o a continuar (epoch que retrocede, log roto, ruta insegura)."""


def verificar_cadena_log(ruta: Path) -> tuple[int, str]:
    """Recorre el log verificando la cadena de hashes. Devuelve `(entradas, hash_de_la_última)` o lanza `ErrorFirmador`.
    Un log inexistente es una cadena vacía válida."""
    previo = CADENA_INICIAL
    n = 0
    try:
        crudo = Path(ruta).read_bytes()
    except FileNotFoundError:
        return 0, previo
    except OSError as e:
        raise ErrorFirmador("log del firmador ilegible") from e
    if crudo and not crudo.endswith(b"\n"):
        raise ErrorFirmador("log del firmador truncado")
    for linea in crudo.splitlines():
        try:
            entrada = json.loads(linea)
            ok = isinstance(entrada, dict) and entrada.get("prev") == previo
        except (ValueError, RecursionError):
            ok = False
        if not ok:
            raise ErrorFirmador(f"cadena del log rota en la entrada {n + 1}")
        previo = hashlib.sha256(linea).hexdigest()
        n += 1
    return n, previo


@dataclass(frozen=True)
class PoliticaFirmador:
    emisor: str
    kid: str
    destinatarios: frozenset[str]
    capacidades: frozenset[str]
    epoch: int
    vida_max_s: float = VIDA_MAX_S
    tasa_max: int = TASA_MAX_DEFECTO
    """Máximo de firmas dentro de `tasa_ventana_s`."""
    tasa_ventana_s: float = TASA_VENTANA_S_DEFECTO
    rechazos_log_max: int = RECHAZOS_LOG_MAX_DEFECTO
    """Máximo de entradas de RECHAZO escritas en el log dentro de `tasa_ventana_s` (el resto se cuenta)."""


class Firmador:
    """Lógica de política + firma + log. Sin sockets: se prueba directamente."""

    def __init__(
        self,
        firmante: Firmante,
        politica: PoliticaFirmador,
        ruta_log: Path,
        ahora: Callable[[], float] = time.time,
        ruta_epoch: Path | None = None,
    ) -> None:
        if firmante.kid != politica.kid:
            raise ValueError("el kid de la clave no coincide con la política")
        if politica.tasa_max < 1 or not politica.tasa_ventana_s > 0 or politica.rechazos_log_max < 1:
            raise ValueError("límite de tasa inválido")
        self._firmante = firmante
        self._pol = politica
        self._log = Path(ruta_log)
        self._ahora = ahora
        self._hilo = threading.Lock()
        self._hilo_tasa = threading.Lock()
        self._firmas: deque[float] = deque()
        self._rechazos_escritos: deque[float] = deque()
        self.rechazos_suprimidos = 0
        """Rechazos NO escritos en el log por el tope de la ventana (se declaran en la siguiente entrada escrita)."""
        verificar_cadena_log(self._log)  # un firmador NO arranca sobre un log roto
        self._ruta_epoch = Path(ruta_epoch) if ruta_epoch else self._log.with_name(EPOCH_NOMBRE)
        self._epoch = self._arrancar_epoch()

    @property
    def epoch(self) -> int:
        """El epoch EFECTIVO de esta ejecución (monótono entre arranques)."""
        return self._epoch

    def _arrancar_epoch(self) -> int:
        """Epoch MONÓTONO persistido (diario append-only `epoch.jsonl`, fsync de fichero y directorio): niega arrancar
        con uno menor que el último y registra el efectivo ANTES de firmar nada. Sin `rename`/`replace`: solo se añade."""
        try:
            with abrir_bloqueado(self._ruta_epoch) as fd:
                registros, _ = leer_registros(fd)
                ultimo: int | None = None
                for r in registros:
                    e = r.get("epoch")
                    if not isinstance(e, int) or isinstance(e, bool) or e < 0:
                        raise ErrorDurable("registro de epoch inválido")
                    ultimo = e if ultimo is None else max(ultimo, e)
                if ultimo is None:
                    efectivo = self._pol.epoch
                elif self._pol.epoch < ultimo:
                    raise ErrorFirmador("el epoch configurado es menor que el último usado: el firmador no arranca")
                else:
                    efectivo = max(self._pol.epoch, ultimo + 1)
                anexar(fd, {"epoch": efectivo})
        except ErrorDurable as e:
            raise ErrorFirmador("fichero de epoch ilegible") from e
        return efectivo

    @staticmethod
    def _hash_ultima_linea(fd: int) -> str:
        """sha256 de la última línea COMPLETA del fichero (la cadena se continúa desde el disco, no desde la memoria)."""
        tam = os.fstat(fd).st_size
        if tam == 0:
            return CADENA_INICIAL
        inicio = max(0, tam - _COLA_LOG_MAX)
        cola = os.pread(fd, tam - inicio, inicio)
        if not cola.endswith(b"\n"):
            raise ErrorFirmador("log del firmador truncado")
        cuerpo = cola[:-1]
        if inicio > 0 and b"\n" not in cuerpo:
            raise ErrorFirmador("log del firmador con una línea desmesurada")
        return hashlib.sha256(cuerpo.rsplit(b"\n", 1)[-1]).hexdigest()

    def _registrar(self, entrada: dict[str, Any]) -> None:
        with self._hilo:
            try:
                with abrir_bloqueado(self._log) as fd:  # flock exclusivo + O_NOFOLLOW + 0600 propio
                    registro = {**entrada, "prev": self._hash_ultima_linea(fd)}
                    anexar(fd, registro)
            except ErrorDurable as e:
                raise ErrorFirmador("el log del firmador no se puede escribir") from e

    def _cupo_de_log(self, ahora: float) -> int | None:
        """Cupo COMPARTIDO de escrituras no-firma (rechazos y fallos) por ventana. `None` = tope alcanzado: la escritura se
        suprime y se cuenta; si no, devuelve los suprimidos acumulados (y los pone a cero) para declararlos en la entrada."""
        with self._hilo_tasa:
            limite = ahora - self._pol.tasa_ventana_s
            while self._rechazos_escritos and self._rechazos_escritos[0] <= limite:
                self._rechazos_escritos.popleft()
            if len(self._rechazos_escritos) >= self._pol.rechazos_log_max:
                self.rechazos_suprimidos += 1
                return None
            self._rechazos_escritos.append(ahora)
            suprimidos, self.rechazos_suprimidos = self.rechazos_suprimidos, 0
            return suprimidos

    def registrar_fallo(self, tipo: str, uid_par: int | None = None) -> None:
        """Deja constancia de un fallo inesperado en el procesamiento de una petición (el hilo sigue vivo). Comparte el
        TOPE de escrituras por ventana con los rechazos (MEDIO-6): un par que provoque fallos no infla el log."""
        ahora = self._ahora()
        suprimidos = self._cupo_de_log(ahora)
        if suprimidos is None:
            return
        entrada: dict[str, Any] = {"tipo": "fallo", "momento": ahora, "causa": tipo, "uid_par": uid_par}
        if suprimidos:
            entrada["suprimidos"] = suprimidos
        self._registrar(entrada)

    def _reservar_tasa(self, ahora: float) -> None:
        with self._hilo_tasa:
            limite = ahora - self._pol.tasa_ventana_s
            while self._firmas and self._firmas[0] <= limite:
                self._firmas.popleft()
            if len(self._firmas) >= self._pol.tasa_max:
                raise RechazoOrden(Motivo.TASA_EXCEDIDA, "demasiadas firmas en la ventana")
            self._firmas.append(ahora)

    def _registrar_rechazo(self, ahora: float, rechazo: RechazoOrden, uid_par: int | None) -> None:
        """Escribe el rechazo en el log salvo que se haya alcanzado el tope de la ventana (entonces solo se cuenta)."""
        suprimidos = self._cupo_de_log(ahora)
        if suprimidos is None:
            return
        entrada: dict[str, Any] = {
            "tipo": "rechazo",
            "momento": ahora,
            "motivo": rechazo.motivo.value,
            "uid_par": uid_par,
        }
        if suprimidos:
            entrada["suprimidos"] = suprimidos
        self._registrar(entrada)

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
        rechazo: RechazoOrden | None = None
        try:
            self._reservar_tasa(ahora)  # TODAS las peticiones consumen cupo, también las que luego se rechazan
            vida = self._validar(peticion)
            id_ejecucion = str(uuid.uuid4())
            campos = {
                "v": V_ACTUAL,
                "alg": ALG,
                "emisor": self._pol.emisor,
                "destinatario": peticion["destinatario"],
                "tarea": peticion["tarea"],
                "intento": peticion["intento"],
                "id_ejecucion": id_ejecucion,
                "capacidad": peticion["capacidad"],
                "argumentos": peticion["argumentos"],
                "emitida_en": ahora,
                "caduca_en": ahora + vida,
                "epoch_hc1": self._epoch,
                "kid": self._pol.kid,
            }
            payload = payload_orden(campos)  # esquema completo: lo que no sea una orden no se firma
            sobre = self._firmante.firmar(DOMINIO_ORDEN, payload)
        except RechazoOrden as e:
            rechazo = e
        except (ValueError, TypeError, RecursionError) as e:  # surrogates sueltos, JSON profundo, tipos raros
            rechazo = RechazoOrden(Motivo.CAMPO_INVALIDO, "codificación")
            rechazo.__cause__ = e
        if rechazo is not None:
            self._registrar_rechazo(ahora, rechazo, uid_par)
            raise rechazo
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
                    peticion = leer_json_estricto(linea)  # profundidad acotada: nunca RecursionError
                except ValueError:
                    firmador.registrar_fallo("peticion_ilegible", uid)
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
            except Exception as e:  # noqa: BLE001 - un fallo inesperado se REGISTRA y el servidor sigue vivo
                try:
                    firmador.registrar_fallo(type(e).__name__)
                    _responder(self.wfile, {"ok": False, "motivo": "error_interno"})
                except (OSError, ErrorFirmador):
                    pass

    return Manejador


class ServidorFirmador(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def crear_servidor(firmador: Firmador, ruta_socket: Path, permitidos: frozenset[int]) -> ServidorFirmador:
    """Socket 0600 en directorio 0700. Fallo CERRADO si el directorio es más permisivo."""
    dir_ = ruta_socket.parent
    try:
        st_dir = os.lstat(dir_)  # lstat: un enlace simbólico al directorio NO se sigue
    except OSError as e:
        raise ErrorClave("el directorio del socket no es accesible") from e
    if not stat.S_ISDIR(st_dir.st_mode) or st_dir.st_mode & 0o077 or st_dir.st_uid != os.getuid():
        raise ErrorClave("el directorio del socket debe ser 0700 y propio")
    try:
        existente: os.stat_result | None = os.lstat(ruta_socket)
    except FileNotFoundError:
        existente = None
    if existente is not None:
        # G-1 (Ruta Única de Mutación) no autoriza a este módulo a BORRAR nada: ni un fichero ni un socket residual. Un
        # objeto que no sea un socket propio es una anomalía; un socket propio muerto exige retirarlo a mano. En ambos
        # casos se falla CERRADO y no se toca lo que ocupa la ruta (retirar el residual solo desde aquí requeriría
        # una exclusión `opera = ["unlink"]` en architecture_manifest.toml: decisión del CEO, no tomada).
        if not stat.S_ISSOCK(existente.st_mode) or existente.st_uid != os.getuid():
            raise ErrorClave("la ruta del socket existe y no es un socket propio")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sonda:
            sonda.settimeout(1)
            try:
                sonda.connect(str(ruta_socket))
            except OSError:
                raise ErrorClave("socket residual de un arranque anterior: retírelo manualmente") from None
        raise ErrorClave("ya hay un firmador escuchando en ese socket")
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
        int(conf.get("tasa_max", TASA_MAX_DEFECTO)),
        float(conf.get("tasa_ventana_s", TASA_VENTANA_S_DEFECTO)),
        int(conf.get("rechazos_log_max", RECHAZOS_LOG_MAX_DEFECTO)),
    )
    try:
        firmador = Firmador(firmante, politica, Path(conf["log"]))
    except ErrorFirmador as e:
        print(f"firmador: {e}", file=sys.stderr)
        return 4
    permitidos = frozenset(conf.get("uids") or [os.getuid()])
    try:
        servidor = crear_servidor(firmador, Path(conf["socket"]), permitidos)
    except ErrorClave as e:
        print(f"firmador: {e}", file=sys.stderr)
        return 5
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=servidor.shutdown, daemon=True).start())
    print("listo", flush=True)
    servidor.serve_forever()
    servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
