"""Nodos y latidos (DP-NODO-01 §4.2-§4.4). Módulo PURO: sin E/S, sin red y sin reloj implícito.

Un *nodo* es un equipo que anuncia su presencia con un **latido** (esquema cerrado `nodo.latido/1`). HC-1
registra cada latido con SU reloj (`recibido_en`), nunca con el del nodo, y deriva el estado del nodo de
forma determinista: `ahora` siempre es un parámetro.

Lo que este módulo NO hace: no mide hardware (eso es de los detectores), no habla con el bus, no persiste
(`a_dict`/`desde_dict` solo producen y consumen estructuras JSON) y no inventa capacidades: las que
corresponden a un nodo las decide **solo** el `CapabilityManager` sobre su `PerfilHardware`.

Los mensajes de `LatidoInvalido` nombran el campo y la regla, **nunca el valor recibido**: el latido llega
de la red y su contenido es arbitrario.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Any

from .activation_context_builder import ActivationContextBuilder
from .capability_manager import CapabilityManager
from .capability_registry import CapabilityRegistry
from .capacidades import ActivationContext, PerfilHardware, PlanActivacion
from .catalogo_capacidades import catalogo

ONLINE = "ONLINE"
DEGRADED = "DEGRADED"
OFFLINE = "OFFLINE"
UNKNOWN = "UNKNOWN"

ESQUEMA_LATIDO = "nodo.latido/1"
TOLERANCIA_INTERVALOS = 3
#: Techo del intervalo que se usa para evaluar OFFLINE: el intervalo lo declara el propio nodo (hasta 3600 s).
INTERVALO_MAX_EVALUACION_S = 60.0
METRICAS_MINIMAS = ("ram_mb", "nucleos")
PREFIJO_SUBJECT = "nodo.latido"

_MAX_CLAVES = 64
_MAX_NOMBRE = 64
_MAX_AGENTE = 32
_INTERVALO_MIN = 1.0
_INTERVALO_MAX = 3600.0

_RE_ID = re.compile(r"[0-9a-f]{32}")
_RE_CLAVE = re.compile(r"[a-z0-9_]{1,40}")

_CAMPOS = (
    "esquema",
    "nodo_id",
    "nombre",
    "secuencia",
    "arranque",
    "intervalo_s",
    "recursos",
    "omitidas",
    "agente",
)


class LatidoInvalido(ValueError):
    """El latido (o el registro persistido) no cumple el esquema. El mensaje nunca contiene el valor."""


@dataclass(frozen=True)
class Latido:
    esquema: str
    nodo_id: str
    nombre: str
    secuencia: int
    arranque: str
    intervalo_s: float
    recursos: dict[str, float]
    omitidas: tuple[str, ...]
    agente: str

    def a_dict(self) -> dict[str, Any]:
        """Forma JSON del latido (la que `validar_latido` acepta de vuelta)."""
        return {
            "esquema": self.esquema,
            "nodo_id": self.nodo_id,
            "nombre": self.nombre,
            "secuencia": self.secuencia,
            "arranque": self.arranque,
            "intervalo_s": self.intervalo_s,
            "recursos": dict(self.recursos),
            "omitidas": list(self.omitidas),
            "agente": self.agente,
        }


# --- validación -------------------------------------------------------------------------------------------


def _fallo(campo: str, regla: str) -> LatidoInvalido:
    return LatidoInvalido(f"latido inválido: campo {campo}: {regla}")


def _es_numero(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _texto_id(datos: dict[str, Any], campo: str) -> str:
    valor = datos[campo]
    if not isinstance(valor, str) or _RE_ID.fullmatch(valor) is None:
        raise _fallo(campo, "debe ser 32 caracteres hexadecimales en minúscula")
    return valor


def _nombre(valor: object) -> str:
    if not isinstance(valor, str) or not 1 <= len(valor) <= _MAX_NOMBRE or not valor.isprintable():
        raise _fallo("nombre", f"debe ser texto imprimible de 1 a {_MAX_NOMBRE} caracteres")
    return valor


def _agente(valor: object) -> str:
    if not isinstance(valor, str) or len(valor) > _MAX_AGENTE:
        raise _fallo("agente", f"debe ser texto de hasta {_MAX_AGENTE} caracteres")
    return valor


def _secuencia(valor: object) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
        raise _fallo("secuencia", "debe ser un entero mayor o igual que 0")
    return valor


def _intervalo(valor: object) -> float:
    if not _es_numero(valor) or not _INTERVALO_MIN <= valor <= _INTERVALO_MAX:  # type: ignore[operator]
        raise _fallo("intervalo_s", f"debe ser un número entre {_INTERVALO_MIN:g} y {_INTERVALO_MAX:g}")
    return float(valor)  # type: ignore[arg-type]


def _clave(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or _RE_CLAVE.fullmatch(valor) is None:
        raise _fallo(campo, "las claves deben cumplir [a-z0-9_]{1,40}")
    return valor


def _recursos(valor: object) -> dict[str, float]:
    if not isinstance(valor, dict) or len(valor) > _MAX_CLAVES:
        raise _fallo("recursos", f"debe ser un diccionario de hasta {_MAX_CLAVES} claves")
    salida: dict[str, float] = {}
    for clave, numero in valor.items():
        _clave(clave, "recursos")
        if not _es_numero(numero):
            raise _fallo("recursos", "los valores deben ser números finitos")
        salida[clave] = float(numero)
    return salida


def _omitidas(valor: object) -> tuple[str, ...]:
    if not isinstance(valor, list) or len(valor) > _MAX_CLAVES:
        raise _fallo("omitidas", f"debe ser una lista de hasta {_MAX_CLAVES} elementos")
    return tuple(_clave(item, "omitidas") for item in valor)


def validar_latido(datos: object) -> Latido:
    """Valida un latido recibido (esquema cerrado, tipos estrictos) o lanza `LatidoInvalido`."""
    if not isinstance(datos, dict):
        raise _fallo("(raíz)", "debe ser un objeto")
    if set(datos) != set(_CAMPOS):
        raise _fallo("(raíz)", "los campos deben ser exactamente los del esquema")
    if datos["esquema"] != ESQUEMA_LATIDO:
        raise _fallo("esquema", f"debe ser {ESQUEMA_LATIDO}")
    return Latido(
        esquema=ESQUEMA_LATIDO,
        nodo_id=_texto_id(datos, "nodo_id"),
        nombre=_nombre(datos["nombre"]),
        secuencia=_secuencia(datos["secuencia"]),
        arranque=_texto_id(datos, "arranque"),
        intervalo_s=_intervalo(datos["intervalo_s"]),
        recursos=_recursos(datos["recursos"]),
        omitidas=_omitidas(datos["omitidas"]),
        agente=_agente(datos["agente"]),
    )


def construir_latido(
    nodo_id: str,
    nombre: str,
    secuencia: int,
    arranque: str,
    intervalo_s: float,
    recursos: dict[str, float],
    omitidas: tuple[str, ...] | list[str],
    agente: str,
) -> dict[str, Any]:
    """Construye el latido como dict JSON listo para enviar. Pasa por la misma validación que el receptor."""
    datos: dict[str, Any] = {
        "esquema": ESQUEMA_LATIDO,
        "nodo_id": nodo_id,
        "nombre": nombre,
        "secuencia": secuencia,
        "arranque": arranque,
        "intervalo_s": intervalo_s,
        "recursos": dict(recursos),
        "omitidas": list(omitidas),
        "agente": agente,
    }
    return validar_latido(datos).a_dict()


# --- subject ----------------------------------------------------------------------------------------------


def subject_de(nodo_id: str) -> str:
    return f"{PREFIJO_SUBJECT}.{nodo_id}"


def nodo_id_de_subject(subject: str) -> str | None:
    """Extrae el `nodo_id` de un subject de latido, o `None` si no tiene la forma esperada."""
    prefijo = PREFIJO_SUBJECT + "."
    if not subject.startswith(prefijo):
        return None
    candidato = subject[len(prefijo) :]
    return candidato if _RE_ID.fullmatch(candidato) is not None else None


# --- registro ---------------------------------------------------------------------------------------------


@dataclass
class RegistroNodo:
    latido: Latido
    recibido_en: float
    primer_contacto: float
    reinicios: int


class RegistroNodos:
    """Último latido aceptado por nodo, con el reloj de HC-1. No persiste por sí mismo."""

    def __init__(self) -> None:
        self._por_id: dict[str, RegistroNodo] = {}

    def registrar(self, latido: Latido, ahora: float) -> str:
        """Devuelve la transición: `nuevo`, `reinicio`, `latido` o `descartado`.

        Un latido repetido o viejo (mismo arranque, secuencia <= la última) se descarta SIN tocar
        `recibido_en`: así un mensaje retrasado no fabrica un ONLINE falso.
        """
        previo = self._por_id.get(latido.nodo_id)
        if previo is None:
            self._por_id[latido.nodo_id] = RegistroNodo(latido, ahora, ahora, 0)
            return "nuevo"
        if latido.arranque != previo.latido.arranque:
            self._por_id[latido.nodo_id] = RegistroNodo(latido, ahora, previo.primer_contacto, previo.reinicios + 1)
            return "reinicio"
        if latido.secuencia <= previo.latido.secuencia:
            return "descartado"
        self._por_id[latido.nodo_id] = RegistroNodo(latido, ahora, previo.primer_contacto, previo.reinicios)
        return "latido"

    def obtener(self, nodo_id: str) -> RegistroNodo | None:
        return self._por_id.get(nodo_id)

    def nodos(self) -> tuple[RegistroNodo, ...]:
        return tuple(self._por_id[k] for k in sorted(self._por_id))

    def a_dict(self) -> dict[str, Any]:
        return {
            "nodos": {
                r.latido.nodo_id: {
                    "latido": r.latido.a_dict(),
                    "recibido_en": r.recibido_en,
                    "primer_contacto": r.primer_contacto,
                    "reinicios": r.reinicios,
                }
                for r in self.nodos()
            }
        }

    @classmethod
    def desde_dict(cls, datos: object) -> RegistroNodos:
        """Reconstruye el registro re-validando cada latido. Cualquier incoherencia lanza `LatidoInvalido`."""
        if not isinstance(datos, dict) or not isinstance(datos.get("nodos"), dict):
            raise _fallo("nodos", "debe ser un objeto con la clave nodos")
        registro = cls()
        for nodo_id, entrada in datos["nodos"].items():
            if not isinstance(entrada, dict) or set(entrada) != {
                "latido",
                "recibido_en",
                "primer_contacto",
                "reinicios",
            }:
                raise _fallo("nodos", "cada entrada debe tener los campos del registro")
            latido = validar_latido(entrada["latido"])
            if latido.nodo_id != nodo_id:
                raise _fallo("nodos", "la clave debe coincidir con el nodo_id del latido")
            reinicios = entrada["reinicios"]
            if not isinstance(reinicios, int) or isinstance(reinicios, bool) or reinicios < 0:
                raise _fallo("reinicios", "debe ser un entero mayor o igual que 0")
            if not _es_numero(entrada["recibido_en"]) or not _es_numero(entrada["primer_contacto"]):
                raise _fallo("recibido_en", "los instantes deben ser números finitos")
            registro._por_id[nodo_id] = RegistroNodo(
                latido, float(entrada["recibido_en"]), float(entrada["primer_contacto"]), reinicios
            )
        return registro


# --- estado -----------------------------------------------------------------------------------------------


def estado_nodo(registro: RegistroNodo | None, ahora: float, receptor_vivo: bool) -> tuple[str, str]:
    """Estado del nodo y su motivo, con la tabla de DP-NODO-01 §4.3 y en ese orden de precedencia."""
    if not receptor_vivo:
        return UNKNOWN, "HC-1 no está escuchando"
    if registro is None:
        return UNKNOWN, "no se ha recibido ningún latido de este nodo"
    # Si el reloj de HC-1 retrocedió la edad sería negativa: se trata como 0 (no es evidencia de caída).
    edad = max(0.0, ahora - registro.recibido_en)
    limite = TOLERANCIA_INTERVALOS * min(registro.latido.intervalo_s, INTERVALO_MAX_EVALUACION_S)
    if edad > limite:
        return OFFLINE, "una conexión antigua no prueba que siga vivo: el último latido es demasiado viejo"
    faltan = [m for m in METRICAS_MINIMAS if m not in registro.latido.recursos]
    if registro.latido.omitidas or faltan:
        partes: list[str] = []
        if registro.latido.omitidas:
            partes.append("métricas omitidas: " + ", ".join(registro.latido.omitidas))
        if faltan:
            partes.append("faltan métricas mínimas: " + ", ".join(faltan))
        return DEGRADED, "; ".join(partes)
    return ONLINE, "latido reciente y métricas mínimas completas"


# --- avisos (acta 2026-10-18, R1: memoria de sesión, sin persistencia) ----------------------------------------

CLAVE_RECEPTOR = "__receptor__"


def titulo_receptor_caido(ahora: float) -> str:
    """Título con la hora de detección: cada caída distinta tiene otra huella en el Centro (no se fusionan)."""
    return f"No se sabe el estado de los nodos: el receptor de HC-1 no está escuchando (detectado a las {_hora(ahora)})"


@dataclass(frozen=True)
class AvisoNodo:
    """Un aviso para el Centro de Notificaciones: `clave` es el nodo (o `CLAVE_RECEPTOR`) y `estado` el que lo motiva."""

    clave: str
    estado: str
    titulo: str
    prioridad: str  # "alta" | "normal", como en notificaciones.py


def _hora_y_dia(instante: float) -> str:
    return time.strftime("%H:%M %d-%m", time.localtime(instante))


def _hora(instante: float) -> str:
    return time.strftime("%H:%M", time.localtime(instante))


def _aviso_de_nodo(r: RegistroNodo, estado: str, previo: str | None, al_abrir: bool) -> AvisoNodo | None:
    """Aviso de un nodo según la transición `previo` -> `estado`, o `None` si no hay nada que decir."""
    nombre = r.latido.nombre
    if estado == OFFLINE and previo != OFFLINE:
        prefijo = "Al abrir AURA" if al_abrir else "Detectado en esta sesión"
        return AvisoNodo(
            r.latido.nodo_id, estado, f"{prefijo}: {nombre} sin latido desde las {_hora_y_dia(r.recibido_en)}", "alta"
        )
    if previo == OFFLINE and estado in (ONLINE, DEGRADED):
        return AvisoNodo(
            r.latido.nodo_id,
            estado,
            f"Detectado en esta sesión: {nombre} conectado de nuevo (latido a las {_hora(r.recibido_en)})",
            "normal",
        )
    return None


def evaluar_avisos_nodos(
    registro: RegistroNodos, ahora: float, receptor_vivo: bool, previos: dict[str, str] | None
) -> tuple[tuple[AvisoNodo, ...], dict[str, str]]:
    """Avisos por TRANSICIÓN entre el estado anterior (`previos`, en memoria) y el actual. Pura: sin E/S.

    `previos=None` significa «al abrir AURA»: sin conocimiento previo solo se avisa de lo anómalo (OFFLINE o
    receptor caído); un nodo ONLINE no genera aviso. Devuelve los avisos y los `previos` NUEVOS, que el
    llamante debe conservar: es lo que impide repetir el mismo aviso en cada turno.

    Receptor caído => solo el aviso del receptor; los nodos quedan UNKNOWN (no se sabe) y su último estado
    conocido se conserva, para no fabricar una caída ni una recuperación por una falta de información.
    """
    al_abrir = previos is None
    nuevos: dict[str, str] = dict(previos or {})
    avisos: list[AvisoNodo] = []

    if not receptor_vivo:
        if nuevos.get(CLAVE_RECEPTOR) != OFFLINE:
            avisos.append(AvisoNodo(CLAVE_RECEPTOR, OFFLINE, titulo_receptor_caido(ahora), "alta"))
        nuevos[CLAVE_RECEPTOR] = OFFLINE
        return tuple(avisos), nuevos
    nuevos[CLAVE_RECEPTOR] = ONLINE

    for r in registro.nodos():
        estado, _ = estado_nodo(r, ahora, receptor_vivo)
        aviso = _aviso_de_nodo(r, estado, nuevos.get(r.latido.nodo_id), al_abrir)
        if aviso is not None:
            avisos.append(aviso)
        nuevos[r.latido.nodo_id] = estado
    return tuple(avisos), nuevos


# --- capacidades ------------------------------------------------------------------------------------------


class _DetectorDelNodo:
    """Detector mínimo: devuelve el perfil que el nodo ya midió. No hay detectores de entorno."""

    def __init__(self, perfil: PerfilHardware) -> None:
        self._perfil = perfil

    def detectar(self) -> PerfilHardware:
        return self._perfil


def capacidades_de(recursos: dict[str, float]) -> PlanActivacion:
    """Plan de activación de un nodo: el MISMO catálogo y Manager que usa HC-1, sobre sus recursos."""
    perfil = PerfilHardware(recursos=dict(recursos))
    contexto: ActivationContext = ActivationContextBuilder(_DetectorDelNodo(perfil), ()).construir()
    return CapabilityManager(CapabilityRegistry(catalogo())).planificar(contexto)
