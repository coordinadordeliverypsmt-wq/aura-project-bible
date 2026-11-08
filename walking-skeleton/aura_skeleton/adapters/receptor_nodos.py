"""Receptor de latidos de nodos en HC-1 (DP-NODO-01 §4.4-§4.5).

Escucha `nodo.latido.*` en el bus NATS, valida cada latido (esquema cerrado), rechaza la suplantación
(el id del subject debe coincidir con el del cuerpo) y persiste el registro en
`<ruta>/nodos/registro.json` con escritura atómica y permisos 0700/0600.

También deja constancia de que EL RECEPTOR está vivo (`receptor.latido`): sin esa señal, un registro
con latidos recientes no prueba nada, porque nadie los estaría recibiendo (estado UNKNOWN).

`informe_nodos` es la presentación pura que usa `python -m aura_skeleton --nodos`.
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import time
from collections.abc import Callable
from typing import Any

from .. import observability as obs
from ..contracts import Event
from ..core.nodos import (
    PREFIJO_SUBJECT,
    LatidoInvalido,
    RegistroNodos,
    capacidades_de,
    estado_nodo,
    nodo_id_de_subject,
    validar_latido,
)

#: 3 × el intervalo de vida del receptor (10 s): pasado este plazo se considera que HC-1 no escucha.
TOLERANCIA_RECEPTOR_S = 30.0

_MODULO = "receptor-nodos"
_SUBDIR = "nodos"
_FICHERO = "registro.json"
_ID_CORTO = 8

NOTA_PRESENCIA = (
    "nota: las métricas de presencia (video_dispositivos, audio_tarjetas, red_interfaces, gpu_render) "
    "indican HARDWARE/INTERFAZ PRESENTE, no capacidad habilitada ni demostrada."
)


def _ruta_registro(ruta: str) -> str:
    return os.path.join(ruta, _SUBDIR, _FICHERO)


def leer_registro(ruta: str) -> dict[str, Any]:
    """Lee `{"receptor": {...} | None, "nodos": {...}}` sin efectos. Lanza `ValueError` si está corrupto."""
    destino = _ruta_registro(ruta)
    if not os.path.exists(destino):
        return {"receptor": None, "nodos": {}}
    try:
        with open(destino, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"registro de nodos ilegible: {type(e).__name__}") from e
    if not isinstance(datos, dict) or not isinstance(datos.get("nodos"), dict):
        raise ValueError("registro de nodos con formato inesperado")
    receptor = datos.get("receptor")
    return {"receptor": receptor if isinstance(receptor, dict) else None, "nodos": datos["nodos"]}


class ReceptorNodos:
    def __init__(self, ruta: str, reloj: Callable[[], float] = time.time) -> None:
        self._ruta = ruta
        self._reloj = reloj
        self._receptor: dict[str, Any] | None = None
        self.registro = self._cargar()

    # --- persistencia -------------------------------------------------------------------------------------

    def _cargar(self) -> RegistroNodos:
        destino = _ruta_registro(self._ruta)
        if not os.path.exists(destino):
            return RegistroNodos()
        try:
            return RegistroNodos.desde_dict(leer_registro(self._ruta))
        except (ValueError, LatidoInvalido):
            apartado = f"{destino}.corrupto-{int(self._reloj())}"
            os.replace(destino, apartado)
            obs.log("WARN", _MODULO, f"registro de nodos corrupto: apartado en {apartado}; empiezo vacío", audit=True)
            return RegistroNodos()

    def _persistir(self) -> None:
        carpeta = os.path.join(self._ruta, _SUBDIR)
        os.makedirs(carpeta, mode=0o700, exist_ok=True)
        os.chmod(carpeta, 0o700)
        destino = _ruta_registro(self._ruta)
        temporal = f"{destino}.tmp"
        contenido = {"receptor": self._receptor, "nodos": self.registro.a_dict()["nodos"]}
        fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False, indent=2)
        os.replace(temporal, destino)

    # --- comportamiento -----------------------------------------------------------------------------------

    async def manejar(self, evento: Event) -> str:
        payload = evento.payload if isinstance(evento.payload, dict) else {}
        id_subject = nodo_id_de_subject(evento.type)
        if id_subject is None or id_subject != payload.get("nodo_id"):
            obs.log(
                "WARN", _MODULO, "latido rechazado: posible suplantación (el id del subject no coincide)", audit=True
            )
            return "rechazado"
        try:
            latido = validar_latido(payload)
        except LatidoInvalido as e:
            obs.log("WARN", _MODULO, f"latido rechazado: {e}", audit=True)
            return "rechazado"
        transicion = self.registro.registrar(latido, self._reloj())
        if transicion in ("nuevo", "reinicio"):
            obs.log("INFO", _MODULO, f"nodo {latido.nombre} [{latido.nodo_id[:_ID_CORTO]}]: {transicion}", audit=True)
        self._persistir()
        return transicion

    def latir(self) -> None:
        """Deja constancia de que el receptor está vivo."""
        self._receptor = {"latido": self._reloj(), "pid": os.getpid()}
        self._persistir()

    def _paso_de_vida(self, bus: Any) -> None:
        """Late solo si el bus está conectado: un receptor desconectado no escucha y no debe parecer vivo."""
        if bus.conectado:
            self.latir()

    async def ejecutar(
        self, servidores: list[str], usuario: str, password: str, ca: str, intervalo_vida: float = 10.0
    ) -> None:
        # El receptor se conecta a localhost y el certificado tiene SAN localhost/127.0.0.1: SÍ se verifica el nombre.
        # Import diferido: `--nodos` solo lee el registro y no debe exigir `nats` instalado.
        from ..bus_nats import NatsEventBus

        ctx = ssl.create_default_context(cafile=ca)
        ctx.verify_flags |= ssl.VERIFY_X509_STRICT  # explícito: 3.12 (HC-1) y 3.13 verifican igual
        bus = await NatsEventBus.connect(
            servidores,
            user=usuario,
            password=password,
            tls=ctx,
            allow_reconnect=True,
            max_reconnect_attempts=-1,
            reconnect_time_wait=2,
        )
        try:
            bus.subscribe(f"{PREFIJO_SUBJECT}.*", self.manejar)
            await bus.start()
            while True:
                self._paso_de_vida(bus)
                await asyncio.sleep(intervalo_vida)
        finally:
            await bus.close()


# --- vigía para los avisos (acta 2026-10-18, R1) ---------------------------------------------------------


#: Topes DEFENSIVOS OPERATIVOS del vigía (no son propiedad arquitectónica): 1 nodo ≈ 1,1 KB medido, así que
#: 1 MiB y 256 nodos dejan holgura de sobra y acotan lo que el proceso principal lee y valida por turno.
MAX_BYTES_REGISTRO = 1024 * 1024
MAX_NODOS_REGISTRO = 256


def _dentro_de_los_topes(destino: str) -> bool:
    """Comprueba el tamaño con `os.stat` ANTES de leer; la ruta completa no se registra."""
    try:
        peso = os.stat(_ruta_registro(destino)).st_size
    except OSError:
        return True  # ausente o ilegible: lo resuelve `leer_registro` como siempre
    if peso > MAX_BYTES_REGISTRO:
        obs.log("WARN", _MODULO, f"vigía de nodos: registro de {peso} bytes supera el tope; se ignora")
        return False
    return True


def crear_vigia_nodos(ruta: str | None = None) -> Callable[[float], tuple[RegistroNodos, bool] | None] | None:
    """Puerto de lectura para los avisos: `(ahora) -> (RegistroNodos, receptor_vivo) | None`.

    Solo LEE `registro.json` (el único escritor es el receptor). Devuelve `None` en el puerto si el registro
    falta, está corrupto o no tiene campo `receptor`: sin conocimiento no hay aviso (nunca uno falso).
    `AURA_RED` declarado y vacío significa «no hay red de nodos» y no crea vigía (patrón de
    `estado_autonomo_cp`; lo usa la batería de pruebas para no leer `~/.aura-red` real).
    """
    if ruta is None:
        declarado = os.environ.get("AURA_RED")
        if declarado is not None and not declarado.strip():
            return None
        ruta = declarado or os.path.expanduser("~/.aura-red")
    destino = ruta

    def vigia(ahora: float) -> tuple[RegistroNodos, bool] | None:
        if not _dentro_de_los_topes(destino):
            return None
        try:
            datos = leer_registro(destino)
            if datos["receptor"] is None:
                return None
            if len(datos["nodos"]) > MAX_NODOS_REGISTRO:
                obs.log("WARN", _MODULO, "vigía de nodos: demasiados nodos en el registro; se ignora")
                return None
            registro = RegistroNodos.desde_dict(datos)
        except (ValueError, LatidoInvalido, OSError, KeyError, TypeError):
            return None
        vivo, _ = _estado_receptor(datos["receptor"], ahora)
        return registro, vivo

    return vigia


# --- presentación -----------------------------------------------------------------------------------------


def _recursos_texto(recursos: dict[str, float]) -> str:
    return " ".join(f"{k}={v:g}" for k, v in sorted(recursos.items())) or "(sin métricas)"


def _capacidades_texto(recursos: dict[str, float]) -> str:
    plan = capacidades_de(recursos)
    return "; ".join(f"{d.nombre}={d.estado.name} ({d.motivo})" for d in plan.decisiones)


def _fecha(instante: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(instante))


def _estado_receptor(receptor: object, ahora: float) -> tuple[bool, str]:
    latido = receptor.get("latido") if isinstance(receptor, dict) else None
    if not isinstance(latido, (int, float)) or isinstance(latido, bool):
        return False, "NO ESCUCHA (último latido nunca)"
    edad = max(0.0, ahora - latido)
    if edad <= TOLERANCIA_RECEPTOR_S:
        return True, f"VIVO (hace {edad:.0f} s)"
    return False, f"NO ESCUCHA (último latido hace {edad:.0f} s)"


def _lineas_nodo(entrada: dict[str, Any], ahora: float, receptor_vivo: bool) -> list[str]:
    registro = RegistroNodos.desde_dict({"nodos": {entrada["latido"]["nodo_id"]: entrada}}).nodos()[0]
    latido = registro.latido
    estado, motivo = estado_nodo(registro, ahora, receptor_vivo)
    edad = max(0.0, ahora - registro.recibido_en)
    return [
        f"{latido.nombre} [{latido.nodo_id[:_ID_CORTO]}…]  {estado}  — {motivo}",
        f"  último latido: hace {edad:.0f} s · primer contacto: {_fecha(registro.primer_contacto)}"
        f" · reinicios: {registro.reinicios} · secuencia {latido.secuencia} · agente {latido.agente}",
        f"  recursos: {_recursos_texto(latido.recursos)}",
        f"  omitidas: {', '.join(latido.omitidas) if latido.omitidas else 'ninguna'}",
        f"  capacidades (CapabilityManager): {_capacidades_texto(latido.recursos)}",
        f"  {NOTA_PRESENCIA}",
    ]


def informe_nodos(registro_dict: dict[str, Any], recursos_hc1: dict[str, float], ahora: float) -> str:
    """Informe de texto de HC-1 y de los nodos registrados. Puro: todo llega por parámetro."""
    receptor_vivo, texto_receptor = _estado_receptor(registro_dict.get("receptor"), ahora)
    lineas = [
        "AURA — nodos y sobres de capacidad",
        "HC-1 (este equipo, medido ahora)",
        f"  recursos: {_recursos_texto(recursos_hc1)}",
        f"  capacidades (CapabilityManager): {_capacidades_texto(recursos_hc1)}",
        f"receptor de nodos: {texto_receptor}",
    ]
    nodos = registro_dict.get("nodos") or {}
    if not nodos:
        lineas.append("ningún nodo registrado")
    for nodo_id in sorted(nodos):
        lineas.extend(_lineas_nodo(nodos[nodo_id], ahora, receptor_vivo))
    return "\n".join(lineas)
