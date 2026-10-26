"""Agente de nodo de AURA (DP-NODO-01 §3-§5): `python3 -m aura_skeleton.nodo_agente`.

Corre en el segundo PC (Atom N450, runit). Cada `intervalo_s` mide el hardware, construye un latido
`nodo.latido/1` y lo publica por NATS+TLS en `nodo.latido.<nodo_id>`. Es infraestructura: no tiene LLM, ni voz,
ni Core. Solo importa identidad, detector de hardware, latido, contrato `Event` y el bus NATS.

Datos (`AURA_NODO_DATOS`, por defecto `~/.aura-nodo`):
    nodo.conf        JSON {servidores: [str], usuario: str, nombre: str, intervalo_s: número}
    credencial       contraseña del usuario NATS; se RECHAZA si el grupo u otros pueden leerla, o vacía
    ca.crt           CA privada de HC-1
    nodo/identidad.json   (lo crea `identidad_nodo`)
    estado_local.json     (lo escribe el agente: escritura atómica, 0600)

Modos: sin flags = bucle de servicio; `--identidad` imprime solo el nodo_id; `--informe` imprime un latido
construido localmente (sin red); `--estado` imprime `estado_local.json`.

Decisiones de diseño:
- `secuencia` sube 1 por latido INTENTADO (publicado o con fallo de publicación), nunca baja ni se repite dentro de
  un arranque. Un hueco en la secuencia significa «intentado y no entregado»; el receptor descarta solo
  repeticiones/viejos (`secuencia <=` la última), así que un hueco es inocuo. Si el bus está reconectando NO se
  publica (nats-py acumularía latidos viejos que luego llegarían en ráfaga) y tampoco se consume secuencia.
- La conexión inicial que falla NO mata el proceso: espera 2, 4, 8… máx. 30 s y reintenta indefinidamente,
  escribiendo `estado_local.json` con `conectado=false`. Tras conectar, la reconexión la hace nats-py.
- Errores de configuración: mensaje a stderr, espera (`AURA_NODO_ESPERA_ERROR_S`, 10 s por defecto) y código 2:
  runit relanza, y la espera evita martillear.
- Nunca se imprime ni se guarda la contraseña; los errores se registran SOLO por tipo de excepción.
- Memoria acotada: `observability._records` crece con cada `obs.log`; el agente lo recorta (ver `_acotar_registros`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import signal
import ssl
import sys
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from . import observability as obs
from .adapters.identidad_nodo import IdentidadCorrupta, cargar_o_crear
from .adapters.resolutor_mdns import resolver_ipv4
from .contracts import Event
from .core.capacidades import PerfilHardware
from .core.nodos import construir_latido, subject_de

AGENTE_VERSION = "nodo-agente/1"
NOMBRE_POR_DEFECTO = "sin-configurar"
INTERVALO_POR_DEFECTO = 10.0
ESPERA_MIN_S = 2.0
ESPERA_MAX_S = 30.0
#: Tope de la conexión INICIAL (nats-py con reconexión infinita no devuelve nunca si HC-1 no responde).
TOPE_CONEXION_INICIAL_S = 20.0
CODIGO_CONFIGURACION = 2
ESPERA_ERROR_POR_DEFECTO_S = 10.0
_CIERRE_TIMEOUT_S = 5.0
_REGISTROS_MAX = 400
_REGISTROS_TRAS_RECORTE = 100
_MODULO = "nodo-agente"
_INTERVALO_MIN = 1.0
_INTERVALO_MAX = 3600.0
_NOMBRE_MAX = 64


class ErrorConfiguracion(Exception):
    """Falta o es inválido algún fichero de configuración. El mensaje nunca contiene secretos."""


@dataclass(frozen=True)
class ConfigAgente:
    datos: str
    nodo_id: str
    servidores: list[str]
    usuario: str
    nombre: str
    intervalo_s: float


class Publicador(Protocol):
    @property
    def conectado(self) -> bool: ...
    async def publish(self, event: Event) -> None: ...
    async def close(self) -> None: ...


class Detector(Protocol):
    def detectar_con_omisiones(self) -> tuple[PerfilHardware, tuple[str, ...]]: ...


# --- configuración ----------------------------------------------------------------------------------------


def _ruta_datos(entorno: Mapping[str, str]) -> str:
    return os.path.expanduser(entorno.get("AURA_NODO_DATOS") or "~/.aura-nodo")


def _es_numero(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _leer_json_conf(datos: str) -> dict[str, Any]:
    ruta = os.path.join(datos, "nodo.conf")
    if not os.path.isfile(ruta):
        raise ErrorConfiguracion(f"falta nodo.conf en {datos}")
    try:
        with open(ruta, encoding="utf-8") as f:
            conf = json.load(f)
    except (OSError, ValueError) as e:
        raise ErrorConfiguracion(f"nodo.conf no es JSON válido ({type(e).__name__})") from e
    if not isinstance(conf, dict):
        raise ErrorConfiguracion("nodo.conf debe ser un objeto JSON")
    return conf


def _texto(conf: dict[str, Any], campo: str) -> str:
    valor = conf.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorConfiguracion(f"nodo.conf: {campo} debe ser un texto no vacío")
    return valor


def _validar_conf(conf: dict[str, Any]) -> tuple[list[str], str, str, float]:
    servidores = conf.get("servidores")
    if (
        not isinstance(servidores, list)
        or not servidores
        or not all(isinstance(s, str) and s.strip() for s in servidores)
    ):
        raise ErrorConfiguracion("nodo.conf: servidores debe ser una lista no vacía de textos")
    usuario = _texto(conf, "usuario")
    nombre = _texto(conf, "nombre")
    if len(nombre) > _NOMBRE_MAX or not nombre.isprintable():
        raise ErrorConfiguracion(f"nodo.conf: nombre debe ser imprimible de 1 a {_NOMBRE_MAX} caracteres")
    intervalo = conf.get("intervalo_s")
    if not _es_numero(intervalo) or not _INTERVALO_MIN <= intervalo <= _INTERVALO_MAX:  # type: ignore[operator]
        raise ErrorConfiguracion(
            f"nodo.conf: intervalo_s debe ser un número entre {_INTERVALO_MIN:g} y {_INTERVALO_MAX:g}"
        )
    return list(servidores), usuario, nombre, float(intervalo)  # type: ignore[arg-type]


def _leer_credencial(datos: str) -> str:
    ruta = os.path.join(datos, "credencial")
    if not os.path.isfile(ruta):
        raise ErrorConfiguracion(f"falta el fichero credencial en {datos}")
    if os.stat(ruta).st_mode & 0o077:
        raise ErrorConfiguracion(f"permisos inseguros en {ruta}: debe ser 0600 (legible solo por su dueño)")
    with open(ruta, encoding="utf-8") as f:
        password = f.read().strip()
    if not password:
        raise ErrorConfiguracion(f"la credencial está vacía: {ruta}")
    return password


def cargar_config(datos: str) -> tuple[ConfigAgente, str]:
    """Lee y valida la configuración. Devuelve (config, contraseña): la contraseña NO va dentro de la config."""
    conf = _leer_json_conf(datos)
    servidores, usuario, nombre, intervalo = _validar_conf(conf)
    password = _leer_credencial(datos)
    if not os.path.isfile(os.path.join(datos, "ca.crt")):
        raise ErrorConfiguracion(f"falta el fichero ca.crt en {datos}")
    try:
        nodo_id = cargar_o_crear(datos)
    except IdentidadCorrupta as e:
        raise ErrorConfiguracion(f"identidad del nodo no confiable: {e}") from e
    return ConfigAgente(datos, nodo_id, servidores, usuario, nombre, intervalo), password


# --- agente -----------------------------------------------------------------------------------------------


def _acotar_registros() -> None:
    """`obs.log` acumula cada registro en una lista global sin tope: en un proceso de meses la memoria (986 MiB en
    el nodo) crecería sin límite. El agente solo necesita la salida impresa, así que conserva los últimos."""
    if len(obs._records) > _REGISTROS_MAX:
        del obs._records[:-_REGISTROS_TRAS_RECORTE]


class AgenteNodo:
    def __init__(
        self,
        config: ConfigAgente,
        publicador_factory: Callable[[], Awaitable[Publicador]],
        detector: Detector,
        reloj: Callable[[], float] = time.time,
        dormir: Callable[[float], Awaitable[None]] | None = None,
        tope_conexion_s: float = TOPE_CONEXION_INICIAL_S,
    ) -> None:
        self._tope_conexion_s = tope_conexion_s
        self._config = config
        self._fabrica = publicador_factory
        self._detector = detector
        self._reloj = reloj
        self._dormir = dormir or self._dormir_interrumpible
        self._arranque = uuid.uuid4().hex
        self._secuencia: int | None = None
        self._parada = asyncio.Event()
        self._conectado = False
        self._ultimo_envio_ok: float | None = None
        self._ultimo_error: str | None = None
        self._espera_reconexion = ESPERA_MIN_S

    @property
    def secuencia(self) -> int | None:
        """Secuencia del último latido intentado (`None` si aún no hubo ninguno)."""
        return self._secuencia

    def detener(self) -> None:
        self._parada.set()

    async def _dormir_interrumpible(self, segundos: float) -> None:
        try:
            await asyncio.wait_for(self._parada.wait(), timeout=segundos)
        except TimeoutError:
            pass

    # -- estado local --------------------------------------------------------------------------------------

    def _escribir_estado(self) -> None:
        cuerpo = {
            "nodo_id": self._config.nodo_id,
            "nombre": self._config.nombre,
            "arranque": self._arranque,
            "secuencia": self._secuencia,
            "conectado": self._conectado,
            "ultimo_envio_ok": self._ultimo_envio_ok,
            "ultimo_error": self._ultimo_error,
            "actualizado": self._reloj(),
        }
        destino = os.path.join(self._config.datos, "estado_local.json")
        temporal = f"{destino}.tmp"
        try:
            os.makedirs(self._config.datos, mode=0o700, exist_ok=True)
            fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cuerpo, f)
            os.replace(temporal, destino)
        except OSError as e:
            obs.log("WARN", _MODULO, f"no se pudo escribir estado_local.json: {type(e).__name__}")

    # -- bucle ---------------------------------------------------------------------------------------------

    def _registrar_error(self, error: BaseException | str) -> None:
        self._ultimo_error = error if isinstance(error, str) else type(error).__name__

    async def _conectar_acotado(self) -> Publicador | None:
        """Una conexión inicial NUNCA bloquea: nats-py con reconexión infinita reintenta la inicial sin devolver.

        Se acota con un tope (TimeoutError) y se interrumpe con la parada (`None`, sin error).
        """
        conexion = asyncio.ensure_future(self._fabrica())
        parada = asyncio.ensure_future(self._parada.wait())
        try:
            hechas, _ = await asyncio.wait(
                {conexion, parada}, timeout=self._tope_conexion_s, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            pendientes = [t for t in (conexion, parada) if not t.done()]
            for t in pendientes:
                t.cancel()
            await asyncio.gather(*pendientes, return_exceptions=True)
        if conexion in hechas:
            return conexion.result()
        if parada in hechas:
            return None
        raise TimeoutError

    async def _conectar(self) -> Publicador | None:
        try:
            publicador = await self._conectar_acotado()
        except Exception as e:  # noqa: BLE001 - HC-1 apagado u otro fallo: el agente NO muere
            self._conectado = False
            self._registrar_error(e)
            obs.log(
                "WARN",
                _MODULO,
                f"sin conexión con HC-1 ({type(e).__name__}); reintento en {self._espera_reconexion:g} s",
            )
            return None
        if publicador is None:  # parada solicitada durante la conexión: no es un error
            return None
        self._espera_reconexion = ESPERA_MIN_S
        obs.log("INFO", _MODULO, f"conectado a HC-1 como {self._config.usuario}")
        return publicador

    async def _latir(self, publicador: Publicador) -> None:
        if not publicador.conectado:
            self._conectado = False
            self._registrar_error("SinConexion")
            return
        self._conectado = True
        perfil, omitidas = self._detector.detectar_con_omisiones()
        self._secuencia = 0 if self._secuencia is None else self._secuencia + 1
        latido = construir_latido(
            self._config.nodo_id,
            self._config.nombre,
            self._secuencia,
            self._arranque,
            self._config.intervalo_s,
            perfil.recursos,
            omitidas,
            AGENTE_VERSION,
        )
        evento = Event(
            type=subject_de(self._config.nodo_id), trace_id=uuid.uuid4().hex, user_id="sistema", payload=latido
        )
        try:
            await publicador.publish(evento)
        except Exception as e:  # noqa: BLE001 - un publish fallido se registra; el agente sigue vivo
            self._registrar_error(e)
            obs.log("WARN", _MODULO, f"publicación fallida ({type(e).__name__}) secuencia={self._secuencia}")
            return
        self._ultimo_envio_ok = self._reloj()
        self._ultimo_error = None

    async def _cerrar(self, publicador: Publicador | None) -> None:
        if publicador is not None:
            try:
                await asyncio.wait_for(publicador.close(), timeout=_CIERRE_TIMEOUT_S)
            except Exception as e:  # noqa: BLE001 - cerrar es mejor esfuerzo
                obs.log("WARN", _MODULO, f"cierre del bus con error ({type(e).__name__})")
        self._conectado = False
        self._escribir_estado()
        obs.log("INFO", _MODULO, "agente detenido")

    async def ejecutar(self) -> None:
        obs.log(
            "INFO", _MODULO, f"arranque {self._arranque[:8]} nodo {self._config.nodo_id[:8]} '{self._config.nombre}'"
        )
        publicador: Publicador | None = None
        try:
            self._escribir_estado()  # visible desde el arranque, aunque la primera conexión tarde hasta el tope
            while not self._parada.is_set():
                espera = self._config.intervalo_s
                if publicador is None:
                    publicador = await self._conectar()
                    if publicador is None:
                        espera = self._espera_reconexion
                        self._espera_reconexion = min(self._espera_reconexion * 2, ESPERA_MAX_S)
                if publicador is not None:
                    await self._latir(publicador)
                self._escribir_estado()
                _acotar_registros()
                await self._dormir(espera)
        finally:
            await self._cerrar(publicador)


# --- producción -------------------------------------------------------------------------------------------


Resolutor = Callable[[str], str | None]
_ESQUEMA_TLS = "tls://"
_SUFIJO_LOCAL = ".local"


def _traducir_servidor(url: str, resolutor: Resolutor) -> str:
    """`tls://<x>.local:<p>` -> `tls://<ip>:<p>` si mDNS resuelve; si no, la URL original (nunca falla)."""
    if not url.startswith(_ESQUEMA_TLS):
        return url
    host, separador, puerto = url[len(_ESQUEMA_TLS) :].partition(":")
    if not host.casefold().endswith(_SUFIJO_LOCAL):
        return url
    try:
        ip = resolutor(host)
    except Exception as e:  # noqa: BLE001 - un resolutor roto no impide conectar con las demás URL
        obs.log("WARN", _MODULO, f"mDNS no disponible para {host} ({type(e).__name__})")
        return url
    if ip is None:
        obs.log("WARN", _MODULO, f"mDNS no resolvió {host}; se conserva la URL original")
        return url
    obs.log("INFO", _MODULO, f"mDNS: {host} -> {ip}")
    return f"{_ESQUEMA_TLS}{ip}{separador}{puerto}"


def traducir_servidores(servidores: list[str], resolutor: Resolutor = resolver_ipv4) -> list[str]:
    """Traduce los servidores `.local` conservando el orden (mDNS primero) y el resto como respaldo."""
    return [_traducir_servidor(s, resolutor) for s in servidores]


def _fabrica_nats(
    config: ConfigAgente, password: str, resolutor: Resolutor = resolver_ipv4
) -> Callable[[], Awaitable[Publicador]]:
    from .bus_nats import NatsEventBus

    async def fabrica() -> Publicador:
        # En cada intento de CONEXIÓN (no en cada latido): la IP de HC-1 cambia por DHCP. El resolutor bloquea (red).
        servidores = await asyncio.to_thread(traducir_servidores, config.servidores, resolutor)
        ctx = ssl.create_default_context(cafile=os.path.join(config.datos, "ca.crt"))
        # La IP de HC-1 cambia por DHCP: la confianza la da la CA privada, no el nombre (DP §4.5).
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        # Explícito: Python 3.13 lo activa por defecto; así HC-1 (3.12) y el nodo (3.13) verifican igual.
        ctx.verify_flags |= ssl.VERIFY_X509_STRICT

        async def error_cb(e: Exception) -> None:
            # nats-py imprime la traza completa en cada intento (ruido y posible filtración): solo el tipo.
            obs.log("WARN", _MODULO, f"nats: {type(e).__name__}")

        return await NatsEventBus.connect(  # type: ignore[no-any-return]
            servidores,
            user=config.usuario,
            password=password,
            tls=ctx,
            allow_reconnect=True,
            max_reconnect_attempts=-1,
            reconnect_time_wait=2,
            connect_timeout=5,
            error_cb=error_cb,
            name=f"aura-nodo-{config.nodo_id[:8]}",
        )

    return fabrica


async def _servir(config: ConfigAgente, password: str) -> None:
    from .adapters.detector_hardware import DetectorHardwareLocal

    agente = AgenteNodo(config, _fabrica_nats(config, password), DetectorHardwareLocal(config.datos))
    bucle = asyncio.get_running_loop()
    for senal in (signal.SIGTERM, signal.SIGINT):
        bucle.add_signal_handler(senal, agente.detener)
    await agente.ejecutar()


def _informe(datos: str) -> dict[str, Any]:
    from .adapters.detector_hardware import DetectorHardwareLocal

    nombre, intervalo = NOMBRE_POR_DEFECTO, INTERVALO_POR_DEFECTO
    try:
        _, _, nombre, intervalo = _validar_conf(_leer_json_conf(datos))
    except ErrorConfiguracion:
        pass
    perfil, omitidas = DetectorHardwareLocal(datos).detectar_con_omisiones()
    return construir_latido(
        cargar_o_crear(datos), nombre, 0, uuid.uuid4().hex, intervalo, perfil.recursos, omitidas, AGENTE_VERSION
    )


def _fallar_configuracion(mensaje: str, espera_s: float) -> int:
    print(f"AURA nodo: {mensaje}", file=sys.stderr, flush=True)
    time.sleep(espera_s)
    return CODIGO_CONFIGURACION


def _espera_error(entorno: Mapping[str, str]) -> float:
    try:
        return max(0.0, float(entorno.get("AURA_NODO_ESPERA_ERROR_S", ESPERA_ERROR_POR_DEFECTO_S)))
    except ValueError:
        return ESPERA_ERROR_POR_DEFECTO_S


def main(argv: list[str] | None = None, entorno: Mapping[str, str] | None = None) -> int:
    entorno = os.environ if entorno is None else entorno
    ap = argparse.ArgumentParser(prog="aura_skeleton.nodo_agente", description="Agente de nodo de AURA")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--identidad", action="store_true", help="imprime solo el nodo_id")
    modo.add_argument("--informe", action="store_true", help="imprime un latido construido localmente (sin red)")
    modo.add_argument("--estado", action="store_true", help="imprime estado_local.json")
    args = ap.parse_args(argv)
    datos = _ruta_datos(entorno)

    if args.identidad or args.informe or args.estado:
        try:
            if args.identidad:
                print(cargar_o_crear(datos))
            elif args.informe:
                print(json.dumps(_informe(datos), ensure_ascii=False))
            else:
                ruta = os.path.join(datos, "estado_local.json")
                if not os.path.isfile(ruta):
                    print(f"AURA nodo: no hay estado local en {ruta}", file=sys.stderr)
                    return 1
                with open(ruta, encoding="utf-8") as f:
                    print(f.read().strip())
        except IdentidadCorrupta as e:
            print(f"AURA nodo: identidad no confiable: {e}", file=sys.stderr)
            return CODIGO_CONFIGURACION
        return 0

    # Servicio: runit lleva stdout a svlogd. Con una tubería Python bufferiza por bloques: línea a línea.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    obs.configurar_salida(sys.stdout)
    try:
        config, password = cargar_config(datos)
    except ErrorConfiguracion as e:
        return _fallar_configuracion(str(e), _espera_error(entorno))
    try:
        asyncio.run(_servir(config, password))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
