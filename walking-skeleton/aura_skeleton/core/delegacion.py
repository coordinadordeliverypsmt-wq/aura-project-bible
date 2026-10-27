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
import unicodedata
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

# --- versiones y dominios ---------------------------------------------------------------------------------

V_ACTUAL = 1
"""Versión de esquema que emite y entiende esta biblioteca."""

ALG = "ed25519"
"""Único algoritmo de firma admitido. Va DENTRO del payload firmado y no se negocia: otro valor se rechaza."""
PROFUNDIDAD_MAX = 32
"""Profundidad máxima de anidamiento JSON aceptada de la red (M-1: un `[[[…]]]` de 90 000 niveles cabe en 192 KiB)."""

DOMINIO_ORDEN = b"aura.delegacion.orden/1\n"
DOMINIO_RESULTADO = b"aura.delegacion.resultado/1\n"
DOMINIO_ACUSE = b"aura.delegacion.acuse/1\n"
DOMINIO_RESOLUCION = b"aura.delegacion.resolucion/1\n"
"""Dominio PROPIO de la autorización humana que resuelve una ejecución ambigua (C3): una firma de nodo o de HC-1 no vale."""
DOMINIOS = frozenset({DOMINIO_ORDEN, DOMINIO_RESULTADO, DOMINIO_ACUSE, DOMINIO_RESOLUCION})

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
        "alg",
    }
)
CAMPOS_RESULTADO = frozenset({"v", "alg", "tarea", "intento", "id_nodo", "id_ejecucion", "hash_tarea", "salida"})
CAMPOS_ACUSE = frozenset({"v", "alg", "tarea", "intento", "id_nodo", "id_ejecucion", "hash_tarea", "recibida_en"})
CAMPOS_RESOLUCION = frozenset({"v", "alg", "id_ejecucion", "decision", "motivo", "emitida_en", "caduca_en", "nonce"})
DECISIONES_RESOLUCION = frozenset({"admitir"})
AUTORIZACION_VIDA_MAX_S = 600.0
"""Techo de la vida de una autorización de resolución (`caduca_en - emitida_en`): corta a propósito."""
MOTIVO_MAX = 256
CAMPOS_SOBRE = frozenset({"p", "f", "kid"})

_RE_ID_NODO = re.compile(r"[0-9a-f]{32}")
_RE_TEXTO_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_RE_HASH = re.compile(r"[0-9a-f]{64}")
INTENTO_MAX = 100


def coincide(patron: re.Pattern[str], valor: object) -> bool:
    """Coincidencia EXACTA de toda la cadena. `$` aceptaba un `\n` final (B-1): se usa `fullmatch`, nunca `match`."""
    return isinstance(valor, str) and patron.fullmatch(valor) is not None


def es_texto_id(valor: object) -> bool:
    return coincide(_RE_TEXTO_ID, valor)


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
    KID_REVOCADO = "kid_revocado"
    ALG_NO_SOPORTADO = "alg_no_soportado"
    EJECUCION_REPETIDA = "ejecucion_repetida"
    EJECUCION_AMBIGUA = "ejecucion_ambigua"
    SIN_AUTORIDAD = "sin_autoridad"
    DIARIO_NO_DURABLE = "diario_no_durable"
    DIARIO_ILEGIBLE = "diario_ilegible"
    TASA_EXCEDIDA = "tasa_excedida"
    REVOCACION_ILEGIBLE = "revocacion_ilegible"
    """La lista de revocados existió y ya no se puede leer (borrada, ajena, corrupta): se rechaza TODO."""
    AUTORIZACION_CADUCADA = "autorizacion_caducada"
    NONCE_REUTILIZADO = "nonce_reutilizado"
    TAREA_CON_INTENTO_AMBIGUO = "tarea_con_intento_ambiguo"
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
        self.detalle = detalle


class EstadoNodo(StrEnum):
    """Estado persistente de una orden en el NODO (M-3). AMBIGUA no se escribe: se DEDUCE de un EJECUTANDO que no
    pertenece a esta instancia (el nodo cayó ejecutando). Una ejecución AMBIGUA nunca se re-ejecuta sola."""

    CONSUMIDA = "consumida"
    EJECUTANDO = "ejecutando"
    COMPLETADA = "completada"
    FALLIDA = "fallida"
    AMBIGUA = "ambigua"


class Reloj(Protocol):
    def ahora(self) -> float: ...
    def sincronizado(self) -> bool: ...


class AlmacenOrdenes(Protocol):
    def consumir(self, id_ejecucion: str, epoch: int, hash_tarea: str | None = None) -> None:
        """Marca la orden como consumida de forma DURABLE o lanza `RechazoOrden` (repetida/epoch/ilegible). El
        `hash_tarea` queda ligado al consumo: `ejecutar` comprueba después que ejecuta LO CONSUMIDO."""
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


def _exigir_profundidad(texto: str) -> None:
    """Recuento LINEAL de anidamiento fuera de cadenas, ANTES de `json.loads` (que recurre y lanzaría RecursionError)."""
    profundidad = 0
    en_cadena = escapado = False
    for ch in texto:
        if en_cadena:
            if escapado:
                escapado = False
            elif ch == "\\":
                escapado = True
            elif ch == '"':
                en_cadena = False
        elif ch == '"':
            en_cadena = True
        elif ch in "[{":
            profundidad += 1
            if profundidad > PROFUNDIDAD_MAX:
                raise ValueError("profundidad excesiva")
        elif ch in "]}":
            profundidad -= 1


def leer_json_estricto(datos: bytes) -> Any:
    """Decodifica JSON rechazando NaN/Infinity, claves duplicadas y anidamiento > `PROFUNDIDAD_MAX`.

    Lanza SOLO `ValueError` (UnicodeError incluido) ante cualquier entrada inválida, nunca `RecursionError`."""
    texto = datos.decode("utf-8")
    _exigir_profundidad(texto)
    try:
        return json.loads(texto, object_pairs_hook=_par_sin_duplicados, parse_constant=_constante_prohibida)
    except RecursionError as e:  # defensa en profundidad: no debería alcanzarse tras el recuento
        raise ValueError("profundidad excesiva") from e


def _es_nfc(obj: Any) -> bool:
    """Todas las cadenas (claves y valores) en forma NFC. No se normaliza en silencio: lo que no es NFC se rechaza."""
    if isinstance(obj, str):
        return unicodedata.is_normalized("NFC", obj)
    if isinstance(obj, dict):
        return all(_es_nfc(k) and _es_nfc(v) for k, v in obj.items())
    if isinstance(obj, list):
        return all(_es_nfc(v) for v in obj)
    return True


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
    except (ValueError, RecursionError) as e:  # UnicodeError es ValueError
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "json") from e
    if not isinstance(obj, dict) or set(obj) != CAMPOS_SOBRE:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "campos")
    kid, p, f = obj["kid"], obj["p"], obj["f"]
    if not (isinstance(kid, str) and isinstance(p, str) and isinstance(f, str)) or not coincide(_RE_TEXTO_ID, kid):
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
    except (ValueError, RecursionError) as e:
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "payload") from e
    if not isinstance(campos, dict):
        raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "payload")
    try:
        canonico = bytes_canonicos(campos)
    except (ValueError, TypeError, RecursionError) as e:
        raise RechazoOrden(Motivo.NO_CANONICO, "payload") from e
    if canonico != abierto.payload:
        raise RechazoOrden(Motivo.NO_CANONICO, "payload")
    if not _es_nfc(campos):
        raise RechazoOrden(Motivo.NO_CANONICO, "no NFC")
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


def _exigir_alg(c: Mapping[str, Any]) -> None:
    """A1: algoritmo fijo y firmado. Sin negociación ni degradación: cualquier otro valor se rechaza."""
    if c["alg"] != ALG:
        raise RechazoOrden(Motivo.ALG_NO_SOPORTADO, "alg")


def _validar_comunes(c: Mapping[str, Any]) -> None:
    _exigir(coincide(_RE_TEXTO_ID, c["tarea"]), "tarea")
    _exigir(_es_entero(c["intento"]) and 1 <= c["intento"] <= INTENTO_MAX, "intento")
    _exigir(_es_uuid4(c["id_ejecucion"]), "id_ejecucion")


def validar_campos_orden(c: Mapping[str, Any], v_minima: int = V_ACTUAL) -> None:
    """Esquema de una orden (sin firma ni frescura). Lanza `RechazoOrden`."""
    _exigir_esquema_cerrado(c, CAMPOS_ORDEN)
    exigir_version(c, v_minima)
    _exigir_alg(c)
    _validar_comunes(c)
    _exigir(coincide(_RE_TEXTO_ID, c["emisor"]), "emisor")
    _exigir(coincide(_RE_ID_NODO, c["destinatario"]), "destinatario")
    _exigir(coincide(_RE_TEXTO_ID, c["capacidad"]), "capacidad")
    _exigir(isinstance(c["argumentos"], dict), "argumentos")
    _exigir(_es_tiempo(c["emitida_en"]) and _es_tiempo(c["caduca_en"]), "tiempos")
    _exigir(_es_entero(c["epoch_hc1"]) and c["epoch_hc1"] >= 0, "epoch_hc1")
    _exigir(coincide(_RE_TEXTO_ID, c["kid"]), "kid")


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
    idempotente: bool
    """¿Repetir la ejecución es inocuo? Si NO lo es (efectos), HC-1 no emite otro intento de la misma tarea mientras
    exista uno ambiguo, interrumpido o con incorporación incierta (at-most-once POR TAREA, C3)."""


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
            "calcular_resumen_sha256", _validar_resumen, _ejecutar_resumen, _verificar_resumen, idempotente=True
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
    revocados: frozenset[str] = frozenset()
    """kids REVOCADOS de HC-1 FIJOS (de arranque). Una orden firmada con uno de ellos se rechaza aunque la firma sea
    matemáticamente válida y el kid siga en `emisores`."""
    fuente_revocados: Callable[[], frozenset[str]] | None = None
    """Lista VIVA de revocados (C2): se consulta en CADA validación y antes de CADA ejecución, así que una revocación
    posterior al arranque surte efecto sin reiniciar. Si no se puede leer lanza `RechazoOrden(REVOCACION_ILEGIBLE)` y
    se rechaza todo (`adapters.firma_delegacion.ListaRevocados`)."""


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


def exigir_no_revocado(politica: PoliticaNodo, kid: str) -> None:
    """Consulta la lista de revocados VIGENTE (fija + viva). Lista ilegible => `REVOCACION_ILEGIBLE` (fallo cerrado)."""
    vivos = politica.fuente_revocados() if politica.fuente_revocados is not None else frozenset()
    if kid in politica.revocados or kid in vivos:
        raise RechazoOrden(Motivo.KID_REVOCADO, "kid")


def revalidar_para_ejecutar(politica: PoliticaNodo, orden: OrdenValida) -> None:
    """Justo antes de EJECUTAR (BAJO b): la orden sigue sin caducar, su kid no se revocó entre aceptar y ejecutar y la
    `OrdenValida` entregada es coherente consigo misma (bytes firmados, hash y campos son la misma orden)."""
    if politica.reloj.sincronizado() is not True:
        raise RechazoOrden(Motivo.RELOJ_NO_SINCRONIZADO)
    if orden.hash_tarea != hash_de(orden.bytes_firmados):
        raise RechazoOrden(Motivo.VINCULO_ROTO, "hash_tarea")
    try:
        firmados = leer_json_estricto(orden.bytes_firmados)
    except ValueError as e:
        raise RechazoOrden(Motivo.VINCULO_ROTO, "bytes firmados") from e
    if firmados != dict(orden.campos):
        raise RechazoOrden(Motivo.VINCULO_ROTO, "campos distintos de lo firmado")
    exigir_no_revocado(politica, orden.campos["kid"])
    if orden.campos["caduca_en"] <= politica.reloj.ahora():
        raise RechazoOrden(Motivo.ORDEN_CADUCADA, "caduca_en")


def validar_orden(
    sobre: bytes, *, politica: PoliticaNodo, verificar: Verificador, almacen: AlmacenOrdenes
) -> OrdenValida:
    """Validación completa de una orden en el NODO. Devuelve la orden SOLO si todo se cumple; el consumo en el
    almacén durable es lo ÚLTIMO (una orden rechazada no se quema, pero una aceptada no se puede repetir)."""
    if not politica.reloj.sincronizado():  # N1/N5: sin hora fiable se rechaza TODO, antes de mirar nada
        raise RechazoOrden(Motivo.RELOJ_NO_SINCRONIZADO)
    abierto = abrir_sobre(sobre)
    exigir_no_revocado(politica, abierto.kid)  # lista VIVA: se relee en cada orden (C2)
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
    hash_tarea = hash_de(abierto.payload)
    almacen.consumir(c["id_ejecucion"], c["epoch_hc1"], hash_tarea)
    return OrdenValida(MappingProxyType(dict(c)), abierto.payload, hash_tarea)


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
            "alg": ALG,
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
            "alg": ALG,
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
    _exigir_alg(c)
    _validar_comunes(c)
    _exigir(coincide(_RE_ID_NODO, c["id_nodo"]), "id_nodo")
    _exigir(coincide(_RE_HASH, c["hash_tarea"]), "hash_tarea")
    _exigir(isinstance(c["salida"], str), "salida")
    if len(c["salida"].encode("utf-8")) > SALIDA_MAX_BYTES:
        raise RechazoOrden(Motivo.SALIDA_EXCESIVA, "salida")


def validar_campos_acuse(c: Mapping[str, Any]) -> None:
    _exigir_esquema_cerrado(c, CAMPOS_ACUSE)
    exigir_version(c, V_ACTUAL)
    _exigir_alg(c)
    _validar_comunes(c)
    _exigir(coincide(_RE_ID_NODO, c["id_nodo"]), "id_nodo")
    _exigir(coincide(_RE_HASH, c["hash_tarea"]), "hash_tarea")
    _exigir(_es_tiempo(c["recibida_en"]), "recibida_en")


def validar_campos_resolucion(c: Mapping[str, Any]) -> None:
    """Esquema de la autorización de resolución (C3). El `kid` de la autoridad va en el sobre, no en el payload."""
    _exigir_esquema_cerrado(c, CAMPOS_RESOLUCION)
    exigir_version(c, V_ACTUAL)
    _exigir(c["alg"] == ALG, "alg")
    _exigir(_es_uuid4(c["id_ejecucion"]), "id_ejecucion")
    _exigir(c["decision"] in DECISIONES_RESOLUCION, "decision")
    _exigir(isinstance(c["motivo"], str) and bool(c["motivo"].strip()) and len(c["motivo"]) <= MOTIVO_MAX, "motivo")
    _exigir(_es_tiempo(c["emitida_en"]) and _es_tiempo(c["caduca_en"]), "tiempos")
    _exigir(_es_uuid4(c["nonce"]), "nonce")


def payload_resolucion(
    id_ejecucion: str, motivo: str, emitida_en: float, caduca_en: float, nonce: str, decision: str = "admitir"
) -> bytes:
    """Bytes canónicos de una autorización de resolución (lado de la autoridad humana). Valida el esquema."""
    campos = {
        "v": V_ACTUAL,
        "alg": ALG,
        "id_ejecucion": id_ejecucion,
        "decision": decision,
        "motivo": motivo,
        "emitida_en": emitida_en,
        "caduca_en": caduca_en,
        "nonce": nonce,
    }
    validar_campos_resolucion(campos)
    return bytes_canonicos(campos)
