"""Delegación segura de tareas a nodos: formato, catálogo y validación (DP-DELEGACION-NODOS §2, §11, §12.6).

Módulo PURO: sin E/S, sin red, sin reloj implícito (el reloj es un parámetro) y sin criptografía propia (la
verificación de firmas es un `Verificador` inyectado). **La delegación real está DESHABILITADA**: esto es una
biblioteca probada en aislamiento; nada la cablea al receptor ni al agente de producción.

Principios (cada uno tiene prueba con caso de control):

* A1 — La orden va firmada por HC-1 (Ed25519, ver `adapters/firma_delegacion.py`) sobre **bytes canónicos** y con
  **separación de dominio**. El nodo verifica sobre los BYTES EXACTOS recibidos y solo DESPUÉS lee los campos
  (HAL-043-1). Esquema cerrado: campos desconocidos o ausentes se rechazan; `v` menor que la mínima se rechaza
  sin negociar (N8).
* Solo **capacidades registradas** (CEO 2026-08-03), nombradas por el resultado que ofrecen. Nunca una orden del
  sistema operativo: el ejecutor es una tabla de funciones fija (M5), sin `exec`, sin `shell`.
* N1 — Frescura: reloj sincronizado obligatorio, `emitida_en` posterior al arranque, caducidad acotada, `epoch_hc1`
  monótono y órdenes consumidas persistentes (el almacén vive en `adapters/almacen_consumidas.py`).

Los motivos de rechazo son un catálogo CERRADO (`Motivo`). Los mensajes nombran el campo y la regla, **nunca el
valor recibido**: la orden llega de la red y su contenido es arbitrario.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

# --- versiones y dominios ---------------------------------------------------------------------------------

V_ACTUAL = 1
"""Versión de esquema que emite y entiende esta biblioteca."""

DOMINIO_ORDEN = b"aura.delegacion.orden/1\n"
DOMINIO_RESULTADO = b"aura.delegacion.resultado/1\n"
DOMINIO_ACUSE = b"aura.delegacion.acuse/1\n"
DOMINIOS = frozenset({DOMINIO_ORDEN, DOMINIO_RESULTADO, DOMINIO_ACUSE})

SALIDA_MAX_BYTES = 64 * 1024
SOBRE_MAX_BYTES = 192 * 1024
VIDA_MAX_S = 300.0
"""Techo de la caducidad de una orden (`caduca_en - emitida_en`)."""
TOLERANCIA_FUTURO_S = 5.0
"""Cuánto puede adelantarse `emitida_en` respecto al reloj del nodo."""

CAMPOS_ORDEN = frozenset(
    {
        "v",
        "emisor",
        "destinatario",
        "tarea",
        "intento",
        "id_ejecucion",
        "capacidad",
        "argumentos",
        "emitida_en",
        "caduca_en",
        "epoch_hc1",
        "kid",
    }
)
CAMPOS_RESULTADO = frozenset({"v", "tarea", "intento", "id_nodo", "id_ejecucion", "hash_tarea", "salida"})
CAMPOS_ACUSE = frozenset({"v", "tarea", "intento", "id_nodo", "id_ejecucion", "hash_tarea", "recibida_en"})
CAMPOS_SOBRE = frozenset({"p", "f", "kid"})

_RE_ID_NODO = re.compile(r"^[0-9a-f]{32}$")
_RE_TEXTO_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RE_HASH = re.compile(r"^[0-9a-f]{64}$")
INTENTO_MAX = 100


class Motivo(StrEnum):
    """Catálogo cerrado de motivos de rechazo (orden, resultado y acuse). Añadir uno exige tocar este catálogo."""

    RELOJ_NO_SINCRONIZADO = "reloj_no_sincronizado"
    SOBRE_MALFORMADO = "sobre_malformado"
    FIRMA_INVALIDA = "firma_invalida"
    KID_DESCONOCIDO = "kid_desconocido"
    NO_CANONICO = "no_canonico"
    CAMPOS_DESCONOCIDOS = "campos_desconocidos"
    CAMPOS_FALTANTES = "campos_faltantes"
    CAMPO_INVALIDO = "campo_invalido"
    VERSION_MENOR = "version_menor"
    VERSION_NO_SOPORTADA = "version_no_soportada"
    EMISOR_DESCONOCIDO = "emisor_desconocido"
    DESTINATARIO_AJENO = "destinatario_ajeno"
    CAPACIDAD_NO_REGISTRADA = "capacidad_no_registrada"
    ARGUMENTOS_INVALIDOS = "argumentos_invalidos"
    ORDEN_CADUCADA = "orden_caducada"
    CADUCIDAD_EXCESIVA = "caducidad_excesiva"
    EMITIDA_EN_EL_FUTURO = "emitida_en_el_futuro"
    EMITIDA_ANTES_DEL_ARRANQUE = "emitida_antes_del_arranque"
    EPOCH_ANTIGUO = "epoch_antiguo"
    ORDEN_REPETIDA = "orden_repetida"
    ALMACEN_ILEGIBLE = "almacen_ilegible"
    # resultados / acuses (lado HC-1)
    NODO_AJENO = "nodo_ajeno"
    EJECUCION_DESCONOCIDA = "ejecucion_desconocida"
    EJECUCION_NO_EN_CURSO = "ejecucion_no_en_curso"
    HASH_NO_CORRESPONDE = "hash_no_corresponde"
    RESULTADO_DUPLICADO = "resultado_duplicado"
    ACUSE_DUPLICADO = "acuse_duplicado"
    SALIDA_EXCESIVA = "salida_excesiva"
    VINCULO_ROTO = "vinculo_roto"


class RechazoOrden(Exception):
    """Orden, resultado o acuse rechazado. `motivo` es del catálogo cerrado; el texto nunca incluye valores recibidos."""

    def __init__(self, motivo: Motivo, detalle: str = "") -> None:
        super().__init__(f"{motivo.value}: {detalle}" if detalle else motivo.value)
        self.motivo = motivo


class Reloj(Protocol):
    def ahora(self) -> float: ...
    def sincronizado(self) -> bool: ...


class AlmacenOrdenes(Protocol):
    def consumir(self, id_ejecucion: str, epoch: int) -> None:
        """Marca la orden como consumida de forma DURABLE o lanza `RechazoOrden` (repetida/epoch/ilegible)."""
        ...


Verificador = Callable[[str, bytes, bytes], bool]
"""(kid, mensaje_con_dominio, firma) -> ¿válida? No lanza: ante cualquier fallo devuelve False."""


# --- JSON canónico ----------------------------------------------------------------------------------------


def bytes_canonicos(obj: Any) -> bytes:
    """JSON canónico: claves ordenadas, sin espacios, UTF-8, sin NaN/inf."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _par_sin_duplicados(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    claves = [k for k, _ in pares]
    if len(claves) != len(set(claves)):
        raise ValueError("clave duplicada")
    return dict(pares)


def _constante_prohibida(_: str) -> Any:
    raise ValueError("constante no permitida")


def leer_json_estricto(datos: bytes) -> Any:
    """Decodifica JSON rechazando NaN/Infinity y claves duplicadas. Lanza `ValueError` si no es válido."""
    return json.loads(datos.decode("utf-8"), object_pairs_hook=_par_sin_duplicados, parse_constant=_constante_prohibida)


def hash_de(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def mensaje_con_dominio(dominio: bytes, payload: bytes) -> bytes:
    """Lo que realmente se firma: dominio || payload. Una firma de un tipo no vale para otro."""
    if dominio not in DOMINIOS:
        raise ValueError("dominio desconocido")
    return dominio + payload


# --- sobre firmado ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SobreAbierto:
    kid: str
    payload: bytes
    firma: bytes


def empaquetar_sobre(kid: str, payload: bytes, firma: bytes) -> bytes:
    """Sobre de cable: `{"f": b64(firma), "kid": kid, "p": b64(payload)}` (canónico)."""
    return bytes_canonicos(
        {
            "p": base64.b64encode(payload).decode("ascii"),
            "f": base64.b64encode(firma).decode("ascii"),
            "kid": kid,
        }
    )


def abrir_sobre(sobre: bytes) -> SobreAbierto:
    """Separa kid/payload/firma SIN interpretar el payload. Esquema cerrado."""
    if not isinstance(sobre, bytes) or len(sobre) > SOBRE_MAX_BYTES:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "tamaño")
    try:
        obj = leer_json_estricto(sobre)
    except (ValueError, UnicodeDecodeError) as e:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "json") from e
    if not isinstance(obj, dict) or set(obj) != CAMPOS_SOBRE:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "campos")
    kid, p, f = obj["kid"], obj["p"], obj["f"]
    if not (isinstance(kid, str) and isinstance(p, str) and isinstance(f, str)) or not _RE_TEXTO_ID.match(kid):
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "tipos")
    try:
        return SobreAbierto(kid, base64.b64decode(p, validate=True), base64.b64decode(f, validate=True))
    except (binascii.Error, ValueError) as e:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "base64") from e


def verificar_y_leer(
    sobre: bytes, dominio: bytes, verificar: Verificador, kid_esperado: str | None = None
) -> tuple[SobreAbierto, dict[str, Any]]:
    """Verifica la firma sobre los BYTES EXACTOS y solo entonces interpreta el payload (HAL-043-1).

    Exige además que el payload sea exactamente su forma canónica: un payload equivalente pero distinto en bytes
    no es lo que se firmó (o es una malleabilidad) y se rechaza.
    """
    abierto = abrir_sobre(sobre)
    if kid_esperado is not None and abierto.kid != kid_esperado:
        raise RechazoOrden(Motivo.KID_DESCONOCIDO, "kid")
    if not verificar(abierto.kid, mensaje_con_dominio(dominio, abierto.payload), abierto.firma):
        raise RechazoOrden(Motivo.FIRMA_INVALIDA, "firma")
    try:
        campos = leer_json_estricto(abierto.payload)
    except (ValueError, UnicodeDecodeError) as e:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "payload") from e
    if not isinstance(campos, dict):
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "payload")
    try:
        canonico = bytes_canonicos(campos)
    except (ValueError, TypeError) as e:
        raise RechazoOrden(Motivo.NO_CANONICO, "payload") from e
    if canonico != abierto.payload:
        raise RechazoOrden(Motivo.NO_CANONICO, "payload")
    return abierto, campos


# --- validadores de campo ---------------------------------------------------------------------------------


def _es_entero(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _es_tiempo(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0


def _es_uuid4(x: object) -> bool:
    if not isinstance(x, str):
        return False
    try:
        u = uuid.UUID(x)
    except ValueError:
        return False
    return u.version == 4 and str(u) == x


def _exigir(cond: bool, campo: str) -> None:
    if not cond:
        raise RechazoOrden(Motivo.CAMPO_INVALIDO, campo)


def _exigir_esquema_cerrado(campos: Mapping[str, Any], permitidos: frozenset[str]) -> None:
    extra = set(campos) - permitidos
    if extra:
        raise RechazoOrden(Motivo.CAMPOS_DESCONOCIDOS, "campos desconocidos")
    if permitidos - set(campos):
        raise RechazoOrden(Motivo.CAMPOS_FALTANTES, "campos faltantes")


def exigir_version(campos: Mapping[str, Any], v_minima: int) -> None:
    """N8: versión mínima fijada, sin negociación. Menor => rechazo; mayor que la soportada => rechazo."""
    v = campos["v"]
    _exigir(_es_entero(v), "v")
    if v < v_minima:
        raise RechazoOrden(Motivo.VERSION_MENOR, "v")
    if v > V_ACTUAL:
        raise RechazoOrden(Motivo.VERSION_NO_SOPORTADA, "v")


def _validar_comunes(c: Mapping[str, Any]) -> None:
    _exigir(isinstance(c["tarea"], str) and bool(_RE_TEXTO_ID.match(c["tarea"])), "tarea")
    _exigir(_es_entero(c["intento"]) and 1 <= c["intento"] <= INTENTO_MAX, "intento")
    _exigir(_es_uuid4(c["id_ejecucion"]), "id_ejecucion")


def validar_campos_orden(c: Mapping[str, Any], v_minima: int = V_ACTUAL) -> None:
    """Esquema de una orden (sin firma ni frescura). Lanza `RechazoOrden`."""
    _exigir_esquema_cerrado(c, CAMPOS_ORDEN)
    exigir_version(c, v_minima)
    _validar_comunes(c)
    _exigir(isinstance(c["emisor"], str) and bool(_RE_TEXTO_ID.match(c["emisor"])), "emisor")
    _exigir(isinstance(c["destinatario"], str) and bool(_RE_ID_NODO.match(c["destinatario"])), "destinatario")
    _exigir(isinstance(c["capacidad"], str) and bool(_RE_TEXTO_ID.match(c["capacidad"])), "capacidad")
    _exigir(isinstance(c["argumentos"], dict), "argumentos")
    _exigir(_es_tiempo(c["emitida_en"]) and _es_tiempo(c["caduca_en"]), "tiempos")
    _exigir(_es_entero(c["epoch_hc1"]) and c["epoch_hc1"] >= 0, "epoch_hc1")
    _exigir(isinstance(c["kid"], str) and bool(_RE_TEXTO_ID.match(c["kid"])), "kid")


# --- catálogo de capacidades REGISTRADAS ------------------------------------------------------------------


@dataclass(frozen=True)
class Capacidad:
    """Capacidad delegable. El nombre describe el RESULTADO, no la herramienta (CEO 2026-08-03).

    `validar_argumentos` devuelve los argumentos normalizados o lanza `RechazoOrden(ARGUMENTOS_INVALIDOS)`.
    `ejecutar` es una función pura de tabla (nunca un comando). `verificar` es el verificador de HC-1 (M3): si una
    capacidad no lo declara, no es delegable.
    """

    nombre: str
    validar_argumentos: Callable[[Mapping[str, Any]], dict[str, Any]]
    ejecutar: Callable[[Mapping[str, Any]], str]
    verificar: Callable[[Mapping[str, Any], str], bool]


TEXTO_MAX = 4096


def _validar_resumen(args: Mapping[str, Any]) -> dict[str, Any]:
    if set(args) != {"texto"}:
        raise RechazoOrden(Motivo.ARGUMENTOS_INVALIDOS, "claves")
    texto = args["texto"]
    if not isinstance(texto, str) or not 1 <= len(texto) <= TEXTO_MAX:
        raise RechazoOrden(Motivo.ARGUMENTOS_INVALIDOS, "texto")
    return {"texto": texto}


def _ejecutar_resumen(args: Mapping[str, Any]) -> str:
    return hash_de(args["texto"].encode("utf-8"))


def _verificar_resumen(args: Mapping[str, Any], salida: str) -> bool:
    # N14 (declarado): esta capacidad de PRUEBA se verifica RECOMPUTANDO. Con <= 4 KiB cuesta microsegundos, pero
    # una capacidad real solo es delegable si se verifica más barato que ejecutarla o de forma independiente.
    return isinstance(salida, str) and salida == hash_de(str(args["texto"]).encode("utf-8"))


CAPACIDADES: Mapping[str, Capacidad] = MappingProxyType(
    {
        "calcular_resumen_sha256": Capacidad(
            "calcular_resumen_sha256", _validar_resumen, _ejecutar_resumen, _verificar_resumen
        )
    }
)
"""Catálogo CERRADO de capacidades delegables. Una capacidad nueva exige acta del CEO y su verificador."""


def capacidad_registrada(nombre: str, permitidas: frozenset[str] | None = None) -> Capacidad:
    cap = CAPACIDADES.get(nombre)
    if cap is None or (permitidas is not None and nombre not in permitidas):
        raise RechazoOrden(Motivo.CAPACIDAD_NO_REGISTRADA, "capacidad")
    return cap


# --- política y validación de la orden en el nodo ---------------------------------------------------------


@dataclass(frozen=True)
class PoliticaNodo:
    id_nodo: str
    emisores: Mapping[str, str]
    """kid -> nombre de emisor confiado (aprovisionado fuera de banda)."""
    capacidades: frozenset[str]
    """Lista LOCAL de capacidades que este nodo acepta (M5): nunca la del sobre ni la de HC-1."""
    reloj: Reloj
    arranque: float
    v_minima: int = V_ACTUAL
    vida_max_s: float = VIDA_MAX_S
    tolerancia_futuro_s: float = TOLERANCIA_FUTURO_S


@dataclass(frozen=True)
class OrdenValida:
    campos: Mapping[str, Any]
    bytes_firmados: bytes
    hash_tarea: str
    """sha256 de los bytes firmados de la orden: ata el resultado a ESTA orden (HAL-041-2)."""


def _validar_frescura(c: Mapping[str, Any], pol: PoliticaNodo, ahora: float) -> None:
    if c["caduca_en"] <= ahora:
        raise RechazoOrden(Motivo.ORDEN_CADUCADA, "caduca_en")
    if c["caduca_en"] - c["emitida_en"] > pol.vida_max_s or c["caduca_en"] <= c["emitida_en"]:
        raise RechazoOrden(Motivo.CADUCIDAD_EXCESIVA, "caduca_en")
    if c["emitida_en"] > ahora + pol.tolerancia_futuro_s:
        raise RechazoOrden(Motivo.EMITIDA_EN_EL_FUTURO, "emitida_en")
    if c["emitida_en"] < pol.arranque:
        raise RechazoOrden(Motivo.EMITIDA_ANTES_DEL_ARRANQUE, "emitida_en")


def validar_orden(
    sobre: bytes, *, politica: PoliticaNodo, verificar: Verificador, almacen: AlmacenOrdenes
) -> OrdenValida:
    """Validación completa de una orden en el NODO. Devuelve la orden SOLO si todo se cumple; el consumo en el
    almacén durable es lo ÚLTIMO (una orden rechazada no se quema, pero una aceptada no se puede repetir)."""
    if not politica.reloj.sincronizado():  # N1/N5: sin hora fiable se rechaza TODO, antes de mirar nada
        raise RechazoOrden(Motivo.RELOJ_NO_SINCRONIZADO)
    abierto = abrir_sobre(sobre)
    emisor = politica.emisores.get(abierto.kid)
    if emisor is None:
        raise RechazoOrden(Motivo.KID_DESCONOCIDO, "kid")
    _, c = verificar_y_leer(sobre, DOMINIO_ORDEN, verificar)  # firma ANTES de leer ningún campo
    validar_campos_orden(c, politica.v_minima)
    if c["kid"] != abierto.kid:
        raise RechazoOrden(Motivo.KID_DESCONOCIDO, "kid del sobre distinto del firmado")
    if c["emisor"] != emisor:
        raise RechazoOrden(Motivo.EMISOR_DESCONOCIDO, "emisor")
    if c["destinatario"] != politica.id_nodo:
        raise RechazoOrden(Motivo.DESTINATARIO_AJENO, "destinatario")
    cap = capacidad_registrada(c["capacidad"], politica.capacidades)
    cap.validar_argumentos(c["argumentos"])
    _validar_frescura(c, politica, politica.reloj.ahora())
    almacen.consumir(c["id_ejecucion"], c["epoch_hc1"])
    return OrdenValida(MappingProxyType(dict(c)), abierto.payload, hash_de(abierto.payload))


# --- construcción (lado HC-1 / firmador y lado nodo) ------------------------------------------------------


def payload_orden(campos: Mapping[str, Any]) -> bytes:
    """Bytes canónicos de una orden. Valida el esquema completo: no se firma lo que no sea una orden."""
    validar_campos_orden(campos)
    return bytes_canonicos(campos)


def payload_resultado(orden: OrdenValida, id_nodo: str, salida: str) -> bytes:
    if len(salida.encode("utf-8")) > SALIDA_MAX_BYTES:
        raise RechazoOrden(Motivo.SALIDA_EXCESIVA, "salida")
    return bytes_canonicos(
        {
            "v": V_ACTUAL,
            "tarea": orden.campos["tarea"],
            "intento": orden.campos["intento"],
            "id_nodo": id_nodo,
            "id_ejecucion": orden.campos["id_ejecucion"],
            "hash_tarea": orden.hash_tarea,
            "salida": salida,
        }
    )


def payload_acuse(orden: OrdenValida, id_nodo: str, recibida_en: float) -> bytes:
    return bytes_canonicos(
        {
            "v": V_ACTUAL,
            "tarea": orden.campos["tarea"],
            "intento": orden.campos["intento"],
            "id_nodo": id_nodo,
            "id_ejecucion": orden.campos["id_ejecucion"],
            "hash_tarea": orden.hash_tarea,
            "recibida_en": recibida_en,
        }
    )


def validar_campos_resultado(c: Mapping[str, Any]) -> None:
    _exigir_esquema_cerrado(c, CAMPOS_RESULTADO)
    exigir_version(c, V_ACTUAL)
    _validar_comunes(c)
    _exigir(isinstance(c["id_nodo"], str) and bool(_RE_ID_NODO.match(c["id_nodo"])), "id_nodo")
    _exigir(isinstance(c["hash_tarea"], str) and bool(_RE_HASH.match(c["hash_tarea"])), "hash_tarea")
    _exigir(isinstance(c["salida"], str), "salida")
    if len(c["salida"].encode("utf-8")) > SALIDA_MAX_BYTES:
        raise RechazoOrden(Motivo.SALIDA_EXCESIVA, "salida")


def validar_campos_acuse(c: Mapping[str, Any]) -> None:
    _exigir_esquema_cerrado(c, CAMPOS_ACUSE)
    exigir_version(c, V_ACTUAL)
    _validar_comunes(c)
    _exigir(isinstance(c["id_nodo"], str) and bool(_RE_ID_NODO.match(c["id_nodo"])), "id_nodo")
    _exigir(isinstance(c["hash_tarea"], str) and bool(_RE_HASH.match(c["hash_tarea"])), "hash_tarea")
    _exigir(_es_tiempo(c["recibida_en"]), "recibida_en")
