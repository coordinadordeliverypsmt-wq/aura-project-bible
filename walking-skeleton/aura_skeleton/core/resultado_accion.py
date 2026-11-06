"""Registro de resultado de acción — la UNICA representación persistente de lo que AURA hizo (punto D).

DISEÑO APROBADO por el CEO Operativo (2026-11-06): `DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md` §7 v2 y
acta `decisiones/2026-11-06-acta-continuidad-de-resultados-punto-d.md`.

QUÉ ES. Un registro de **metadatos** (`campo=valor;…`, no JSON: ver `_serializar`) con esquema cerrado en campos Y en valores, que se escribe en `memoria.json`
como `kind="resultado_accion"` (episódico de acción, no un cuarto tipo de memoria) para que, tras reiniciar,
AURA pueda contestar «¿qué hiciste antes de reiniciarte?» sin volver a ejecutar nada.

QUÉ NO ES, Y ES DELIBERADO:

- **Nunca el `say`** (la frase que se le dijo a la persona), nunca el payload de la capacidad, nunca el motivo
  libre del motor, nunca un texto de Home Assistant. Lo único que viaja son valores de un enum o de un patrón
  fijo; un valor externo que no encaje se degrada a `"desconocido"`, no se copia. La inyección no tiene dónde
  caber.
- **No es recuperable por `recall`** (`contracts.KINDS_NO_RECUPERABLES`) ni entra en el prompt ni en el modelo del
  usuario (`_TIPOS`) ni en la población de CM2. Se lee SOLO por este módulo, a petición del usuario.
- **No es una prueba**: `memoria.json` es texto plano y un proceso local podría anexar una línea. Por eso se valida
  al escribir Y al leer, y lo recuperado se presenta como «consta en mi registro local», no como hecho
  verificado del Core. No hay firma criptográfica (límite declarado: custodia de clave = decisión aparte).

UNA SOLA REPRESENTACIÓN (lección de ALERTA-005): construir, validar, serializar y leer viven AQUÍ. El orquestador
no vuelve a interpretar el formato.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Iterable

from .. import observability as obs
from ..contracts import RESULTADO_ACCION
from .operaciones import ESPECIFICACIONES
from .permissions import CATALOGO

#: `kind` del registro en `memoria.json`. Su exclusión de `recall` está en `contracts.KINDS_NO_RECUPERABLES`.
KIND = RESULTADO_ACCION

#: Qué le pasó a la orden. Los cinco primeros salen del motor y del adaptador; `desconocido` es lo que se
#: escribe cuando algo no se sabe interpretar —nunca se adivina—.
DESENLACES = ("ejecutada", "no_limpia", "detenida", "error", "duplicada", "desconocido")

#: Estados de dispositivo admitidos. Cualquier otro valor que devuelva Home Assistant se escribe `desconocido`.
ESTADOS = frozenset({"on", "off", "unavailable", "unknown", "playing", "paused", "idle", "standby"})
DESCONOCIDO = "desconocido"

#: Volumen en escala 0-100 (HA lo da en 0-1). Es el dominio de la propia magnitud, no una elección.
VOLUMEN_MAXIMO = 100

#: Tope de los contadores (`elementos`, `ts`): un entero de 32 bits con signo. Cierra el esquema —ningún valor
#: arbitrario cabe— sin pretender ser un techo del sistema; ningún adaptador lo alcanza.
ENTERO_MAXIMO = 2**31 - 1

#: Un identificador (capacidad, dominio y objeto de entidad, trace_id) mide como mucho esto. UN tope para todos:
#: el de `capacidad`, que el catálogo ya acota. De él se deriva el tamaño máximo de línea.
IDENTIFICADOR_MAXIMO = 64

#: Dominios cuya acción NO deja rastro persistente: cerraduras, alarma y cámaras. Que «abrí la cerradura a las
#: 23:10» viva en un fichero plano es un patrón de vida y una ayuda a un intruso.
DOMINIOS_DE_SEGURIDAD = ("lock.", "alarm_control_panel.", "camera.")

#: Capacidades de la familia hogar (la única donde `entidad`, `antes` y `despues` tienen sentido).
CAPACIDADES_DE_HOGAR = frozenset(
    {"encender_dispositivo", "apagar_dispositivo", "subir_volumen", "bajar_volumen", "silenciar", "quitar_silencio"}
)
CAPACIDADES_DE_VOLUMEN = frozenset({"subir_volumen", "bajar_volumen"})
CAPACIDADES_DE_SILENCIO = frozenset({"silenciar", "quitar_silencio"})

#: Orden FIJO de los campos: es el orden de serialización y lo que `validar` exige que sea exacto. **`ts` y `trace_id`
#: van PRIMERO a propósito**: el arranque de `PersistentMemory` falla en alto ante un fragmento truncado que pudiera
#: ser el comienzo de una lápida (P2-B), y eso incluye cualquier corte cuyo prefijo coincida con el de otro registro.
#: Con lo que varía entre registros al principio, un corte a mitad de línea casi nunca es ambiguo.
CAMPOS = (
    "ts",
    "trace_id",
    "capacidad",
    "desenlace",
    "entidad",
    "antes",
    "despues",
    "verificado",
    "evidencia",
    "elementos",
)

#: Con qué evidencia se cerró una orden de hogar. Es lo que permite que la redacción recuperada vaya a la MISMA rama
#: que la en vivo (verificada por relectura, estado asumido por HA, ya estaba así, hogar simulado, no se pudo leer).
EVIDENCIAS = ("verificada", "asumida", "ya_en_estado", "simulada", "no_leida", "ninguna")

#: Capacidades que un registro puede nombrar: el catálogo REAL del sistema (operaciones de ficheros + catálogo de
#: permisos + familia hogar). Una capacidad inventada no es un registro.
CAPACIDADES_CONOCIDAS = frozenset(ESPECIFICACIONES) | frozenset(CATALOGO) | CAPACIDADES_DE_HOGAR

_PATRON_CAPACIDAD = re.compile(rf"[a-z_]{{1,{IDENTIFICADOR_MAXIMO}}}")
_PATRON_ENTIDAD = re.compile(rf"[a-z_]{{1,{IDENTIFICADOR_MAXIMO}}}\.[a-z0-9_]{{1,{IDENTIFICADOR_MAXIMO}}}")
_PATRON_TRACE = re.compile(rf"[A-Za-z0-9_.:-]{{1,{IDENTIFICADOR_MAXIMO}}}")

_SEGUNDOS_POR_MINUTO = 60

#: Como se escribe un valor ausente (`None`) en la forma canónica.
_NULO = "-"

#: Motivos por los que `construir` no devuelve registro.
MOTIVO_DOMINIO_DE_SEGURIDAD = "dominio_de_seguridad"
MOTIVO_INVALIDO = "invalido"


def _a_texto(valor: object) -> str:
    if valor is None:
        return _NULO
    if isinstance(valor, bool):
        return "1" if valor else "0"
    return str(valor)


def _serializar(registro: dict) -> str:
    """La forma canónica: `campo=valor` separados por `;`, en orden fijo. Lo que se escribe es SIEMPRE esto.

    **No es JSON a propósito**: sin comillas ni barras no hay nada que escapar, y el arranque de `PersistentMemory`
    falla en alto si un corte de escritura cae justo dentro de un escape (`\\"`). Un registro se escribe con cada
    acción; que un corte no pueda dejar un fragmento ambiguo es una propiedad de disponibilidad que importa."""
    return ";".join(f"{c}={_a_texto(registro[c])}" for c in CAMPOS)


def _desde_texto(campo: str, texto: str) -> object:
    if texto == _NULO:
        return None
    if campo == "verificado":
        return {"0": False, "1": True}.get(texto, texto)
    if campo in ("ts", "elementos") or (campo in ("antes", "despues") and texto.isdigit()):
        return int(texto) if texto.isascii() and texto.isdigit() else texto
    return texto


def _peor_caso() -> dict:
    """El registro más largo que el esquema admite: de él sale el límite de línea, no de un número elegido."""
    return {
        "capacidad": max(CAPACIDADES_DE_HOGAR, key=len),  # entidad solo cabe en hogar: el peor caso es hogar + entidad
        "desenlace": max(DESENLACES, key=len),
        "entidad": "a" * IDENTIFICADOR_MAXIMO + "." + "a" * IDENTIFICADOR_MAXIMO,
        "antes": max((*ESTADOS, DESCONOCIDO), key=len),
        "despues": max((*ESTADOS, DESCONOCIDO), key=len),
        "verificado": False,
        "evidencia": max(EVIDENCIAS, key=len),
        "elementos": ENTERO_MAXIMO,
        "trace_id": "a" * IDENTIFICADOR_MAXIMO,
        "ts": ENTERO_MAXIMO - ENTERO_MAXIMO % _SEGUNDOS_POR_MINUTO,
    }


#: Longitud máxima de una línea de registro, DERIVADA del esquema (el peor caso serializado). Una línea más
#: larga no puede ser un registro válido y ni se parsea: acota el coste de leer un fichero hostil.
LONGITUD_MAXIMA = len(_serializar(_peor_caso()))


def _es_entero(valor: object, minimo: int, maximo: int) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


def _es_estado(valor: object) -> bool:
    if valor is None or valor == DESCONOCIDO:
        return True
    if isinstance(valor, str):
        return valor in ESTADOS
    return _es_entero(valor, 0, VOLUMEN_MAXIMO)


def _es_texto(valor: object, patron: re.Pattern[str]) -> bool:
    return isinstance(valor, str) and patron.fullmatch(valor) is not None


def _entidad_valida(registro: dict) -> bool:
    entidad = registro["entidad"]
    if entidad is None:
        return True
    if not _es_texto(entidad, _PATRON_ENTIDAD) or entidad.startswith(DOMINIOS_DE_SEGURIDAD):
        return False
    # La entidad es SOLO del hogar: ninguna otra capacidad (ficheros, auditorías…) la lleva.
    return registro["capacidad"] in CAPACIDADES_DE_HOGAR


def validar(registro: object) -> bool:
    """True solo si `registro` es EXACTAMENTE un registro del esquema cerrado. Se usa al escribir y al leer."""
    if not isinstance(registro, dict) or set(registro) != set(CAMPOS):
        return False
    return (
        _es_texto(registro["capacidad"], _PATRON_CAPACIDAD)
        and registro["capacidad"] in CAPACIDADES_CONOCIDAS
        and registro["desenlace"] in DESENLACES
        and _entidad_valida(registro)
        and _es_estado(registro["antes"])
        and _es_estado(registro["despues"])
        and isinstance(registro["verificado"], bool)
        and registro["evidencia"] in EVIDENCIAS
        and (registro["elementos"] is None or _es_entero(registro["elementos"], 0, ENTERO_MAXIMO))
        and _es_texto(registro["trace_id"], _PATRON_TRACE)
        and _es_entero(registro["ts"], 0, ENTERO_MAXIMO)
        and registro["ts"] % _SEGUNDOS_POR_MINUTO == 0
    )


def a_contenido(registro: dict) -> str:
    """El `content` que se escribe en memoria. Solo de un registro válido."""
    if not validar(registro):
        raise ValueError("registro de resultado de accion invalido: no se serializa")
    return _serializar(registro)


def desde_contenido(contenido: object) -> dict | None:
    """El registro que `contenido` contiene, o `None` si no es EXACTAMENTE lo que este módulo escribiría.

    Triple barrera: límite de longitud (antes de analizar), esquema cerrado y forma canónica (re-serializar tiene
    que reproducir el texto byte a byte, así que nada oculto —ceros a la izquierda, espacios, campos repetidos— pasa)."""
    if not isinstance(contenido, str) or len(contenido) > LONGITUD_MAXIMA:
        return None
    partes = contenido.split(";")
    if len(partes) != len(CAMPOS):
        return None
    registro: dict = {}
    for campo, parte in zip(CAMPOS, partes, strict=True):
        nombre, separador, texto = parte.partition("=")
        if nombre != campo or not separador:
            return None
        registro[campo] = _desde_texto(campo, texto)
    if not validar(registro) or _serializar(registro) != contenido:
        return None
    return registro


# ------------------------------------------------------------------------------------ construir --


def desenlace_de(res: object) -> str:
    """Qué le pasó a la orden, leído del contrato real de `MotorAutomatizacion.ejecutar` (no supuesto)."""
    if not isinstance(res, dict):
        return "desconocido"
    estado = res.get("estado")
    if estado in ("detenida", "error"):
        return str(estado)
    if estado != "ejecutada":
        return "desconocido"
    detalle = res.get("resultado")
    if isinstance(detalle, dict):
        # MISMO orden que la redaccion en vivo: el veredicto del adaptador (`ok`) manda sobre `duplicate`.
        if detalle.get("ok") is False:
            return "no_limpia"
        if detalle.get("status") == "duplicate":
            return "duplicada"
    return "ejecutada"


def _estado(valor: object) -> str | None:
    """Estado de dispositivo de Home Assistant -> valor del enum. Lo que no encaje es `desconocido`, nunca copiado."""
    if valor is None:
        return None
    return valor if isinstance(valor, str) and valor in ESTADOS else DESCONOCIDO


def _volumen(valor: object) -> int | str | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 <= valor <= 1:
        return DESCONOCIDO
    return round(valor * VOLUMEN_MAXIMO)


def _silencio(valor: object) -> str | None:
    """`is_volume_muted` (bool) -> `on` (silenciada) / `off`. Cualquier otra cosa, `desconocido`."""
    if valor is None:
        return None
    return ("on" if valor else "off") if isinstance(valor, bool) else DESCONOCIDO


def elementos_de(detalle: object) -> int | None:
    """Cuántas entradas listó o cuántas líneas leyó. Solo el NÚMERO: jamás un nombre ni una línea."""
    if not isinstance(detalle, dict):
        return None
    entradas = detalle.get("entradas")
    if isinstance(entradas, (list, tuple)):
        return min(len(entradas), ENTERO_MAXIMO)
    contenido = detalle.get("contenido")
    if isinstance(contenido, str):
        return min(len(contenido.splitlines()), ENTERO_MAXIMO)
    return None


def _antes_despues(capacidad: str, detalle: dict) -> tuple[object, object]:
    if capacidad in CAPACIDADES_DE_VOLUMEN:
        return _volumen(detalle.get("valor_antes")), _volumen(detalle.get("valor_despues"))
    if capacidad in CAPACIDADES_DE_SILENCIO:
        return _silencio(detalle.get("valor_antes")), _silencio(detalle.get("valor_despues"))
    return _estado(detalle.get("estado_antes")), _estado(detalle.get("estado_despues"))


def _evidencia(capacidad: str, detalle: dict, despues: object) -> str:
    """Con que evidencia se cerro la orden, en el MISMO orden en que la redaccion en vivo elige su rama: en
    encender/apagar «verificada» gana a «ya estaba»; en volumen y silencio, al reves."""
    if capacidad not in CAPACIDADES_DE_HOGAR:
        return "ninguna"
    if detalle.get("evidencia") == "estado_asumido_por_ha":
        return "asumida"
    verificada = detalle.get("verificado") is True
    ya = bool(detalle.get("ya_en_estado"))
    if capacidad in CAPACIDADES_DE_VOLUMEN | CAPACIDADES_DE_SILENCIO:
        if ya:
            return "ya_en_estado"
        if verificada:
            return "verificada"
    else:
        if verificada:
            return "verificada"
        if ya:
            return "ya_en_estado"
    if detalle.get("status") == "sin_efecto":
        return "ninguna" if despues not in (None, DESCONOCIDO) else "no_leida"
    return "simulada"


def construir(capacidad: str, res: object, trace_id: str, ahora: float | None = None) -> tuple[dict | None, str | None]:
    """(registro, None) o (None, motivo). El registro sale SOLO de campos tipados del resultado del motor.

    `say`, `motivo`, `plan` y cualquier texto libre no se leen: no hay forma de que lleguen al registro."""
    detalle = res.get("resultado") if isinstance(res, dict) else None
    detalle = detalle if isinstance(detalle, dict) else {}
    entidad = None
    antes = despues = None
    if capacidad in CAPACIDADES_DE_HOGAR:
        candidata = detalle.get("device")
        if isinstance(candidata, str) and candidata.startswith(DOMINIOS_DE_SEGURIDAD):
            return None, MOTIVO_DOMINIO_DE_SEGURIDAD
        # Una entidad que no es un entity_id (p. ej. «la tele») no se copia: es texto de fuera.
        entidad = candidata if _es_texto(candidata, _PATRON_ENTIDAD) else None
        antes, despues = _antes_despues(capacidad, detalle)
    registro = {
        "capacidad": capacidad,
        "desenlace": desenlace_de(res),
        "entidad": entidad,
        "antes": antes,
        "despues": despues,
        "verificado": detalle.get("verificado") is True,
        "evidencia": _evidencia(capacidad, detalle, despues),
        "elementos": elementos_de(detalle),
        "trace_id": trace_id,
        "ts": int(ahora if ahora is not None else time.time()) // _SEGUNDOS_POR_MINUTO * _SEGUNDOS_POR_MINUTO,
    }
    return (registro, None) if validar(registro) else (None, MOTIVO_INVALIDO)


# ---------------------------------------------------------------------------------------- leer --


def leer(memoria: object, user_id: str, ahora: float | None = None) -> tuple[list[dict], int]:
    """(registros válidos del usuario, cuántos se rechazaron). Orden estable por `ts`.

    Solo el usuario pedido: dos personas no se ven. Se rechazan y se cuentan (el llamador audita
    `resultado.rechazado`): lo que no valida, lo que viene del FUTURO (más allá del margen del redondeo al minuto)
    y TODOS los registros que comparten `trace_id` con contenido distinto (fallo cerrado: no se elige uno por
    inferencia). Un mismo contenido repetido (doble escritura) cuenta una sola vez. **No se completa ni se corrige
    nada por inferencia.**"""
    items: Iterable[dict] = getattr(memoria, "_items", ()) or getattr(getattr(memoria, "_store", None), "_items", ())
    limite = (ahora if ahora is not None else time.time()) + _SEGUNDOS_POR_MINUTO
    por_trace: dict[str, list[dict]] = {}
    rechazados = 0
    for item in items:
        if item.get("kind") != KIND or item.get("user_id") != user_id:
            continue
        registro = desde_contenido(item.get("content"))
        if registro is None or registro["ts"] > limite:
            rechazados += 1
            continue
        por_trace.setdefault(registro["trace_id"], []).append(registro)
    validos: list[dict] = []
    for grupo in por_trace.values():
        if any(r != grupo[0] for r in grupo):
            rechazados += len(grupo)
            continue
        validos.append(grupo[0])
    return sorted(validos, key=lambda r: r["ts"]), rechazados


def leer_auditando(memoria: object, user_id: str, trace_id: str = "-") -> list[dict]:
    """`leer` + el rastro `resultado.rechazado` (sin contenido). UNA puerta para la recuperacion, `ver` y `exportar`."""
    registros, rechazados = leer(memoria, user_id)
    if rechazados:
        obs.log(
            "WARN",
            "resultado",
            f"{rechazados} registro(s) de resultado de accion rechazado(s) al leer: no cumplen el esquema",
            trace_id,
            audit=True,
            evento="resultado.rechazado",
            cantidad=rechazados,
        )
    return registros


def detalle_reconstruido(registro: dict) -> dict:
    """El `detalle` de hogar/volumen que el redactor ya conoce, reconstruido SOLO con lo que el registro conserva.

    `evidencia` lleva la redacción a la MISMA rama que tuvo en vivo (verificada, asumida, ya estaba, simulada, no se
    pudo leer, sin cambio). Así la recuperación tras reinicio reutiliza la redacción en vez de tener la suya."""
    capacidad, antes, despues = registro["capacidad"], registro["antes"], registro["despues"]
    evidencia = registro["evidencia"]
    detalle: dict = {
        "device": registro["entidad"] or "el dispositivo",
        "verificado": evidencia == "verificada",
        "ya_en_estado": evidencia == "ya_en_estado",
        "estado_antes": antes if antes is not None else "?",
        "estado_despues": despues if despues is not None else "?",
    }
    if evidencia != "simulada":  # el hogar simulado ni siquiera devuelve `status`
        detalle["status"] = "ok" if evidencia == "verificada" else "sin_efecto"
        detalle["evidencia"] = {
            "asumida": "estado_asumido_por_ha",
            "no_leida": "ninguna",
        }.get(evidencia, "estado_ha_tras_orden")
    if capacidad in CAPACIDADES_DE_VOLUMEN:
        detalle["atributo"] = "volume_level"
        detalle["valor_antes"] = antes / VOLUMEN_MAXIMO if isinstance(antes, int) else None
        detalle["valor_despues"] = despues / VOLUMEN_MAXIMO if isinstance(despues, int) else None
    elif capacidad in CAPACIDADES_DE_SILENCIO:
        detalle["atributo"] = "is_volume_muted"
        detalle["valor_antes"] = antes == "on" if antes in ("on", "off") else None
        detalle["valor_despues"] = despues == "on" if despues in ("on", "off") else None
    return detalle


def exportable(registro: dict) -> dict:
    """Lo que `ver` y `exportar` muestran al usuario: lista blanca de campos (sin `trace_id`, que es interno)."""
    return {
        "tipo": KIND,
        "capacidad": registro["capacidad"],
        "desenlace": registro["desenlace"],
        "entidad": registro["entidad"],
        "antes": registro["antes"],
        "despues": registro["despues"],
        "verificado": registro["verificado"],
        "evidencia": registro["evidencia"],
        "elementos": registro["elementos"],
        "ts": registro["ts"],
    }


def hora_legible(registro: dict) -> str:
    """`ts` en UTC, al minuto: «2026-11-06 10:15 UTC». Sin zona local: el fichero no sabe dónde vive la persona."""
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(registro["ts"]))


# ---------------------------------------------------------------------- olvido de las acciones --

#: Frases que piden olvidar lo que AURA HIZO (T19). Conjunto CERRADO, comparado por turno COMPLETO normalizado:
#: «olvida lo que hiciste con mi madre» no es esto. Ante la duda, no se reconoce (ADR-0003): sigue su camino.
_FORMAS_OLVIDO_DE_ACCIONES = frozenset(
    {
        "olvida lo que hiciste",
        "olvida lo que has hecho",
        "olvida lo que ejecutaste",
        "olvida lo que hiciste antes",
        "olvida las acciones que hiciste",
        "olvida las acciones que has hecho",
        "olvida mis acciones",
        "olvida tus acciones",
        "borra el historial de acciones",
        "borra tu historial de acciones",
        "borra lo que hiciste",
        "borra lo que has hecho",
        "borra las acciones que hiciste",
        "borra el registro de acciones",
        "borra tu registro de acciones",
    }
)


def es_peticion_de_olvido_de_acciones(texto: str) -> bool:
    """True si el turno COMPLETO pide olvidar el registro de acciones."""
    plano = unicodedata.normalize("NFD", texto.lower())
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    for signo in "¿?¡!.,;:…":
        plano = plano.replace(signo, " ")
    palabras = plano.split()
    while palabras and palabras[0] in ("aurora", "aura"):
        palabras.pop(0)
    while palabras and palabras[-1] in ("aurora", "aura"):
        palabras.pop()
    return " ".join(palabras) in _FORMAS_OLVIDO_DE_ACCIONES
