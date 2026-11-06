"""Reloj de CM2 — mecanismo de medicion de la memoria a 28 dias (resolucion S3 §2.1, CEO 2026-10-06).

CM2 mide si AURA sigue recuperando un hecho que el usuario le declaro, a los 7, 14 y 28 dias. Este
modulo es el MECANISMO; no inicia ninguna medicion: la medicion oficial exige
el evento de auditoria `cm2.inicio`, que solo emite `--iniciar-cm2 --confirmo-inicio`.

**Sin estado propio.** El calendario se reconstruye leyendo el audit log completo (segmentos + activo,
ordenado por `seq`) y deduciendo las sondas ya hechas de sus propios eventos `cm2.sonda`. Sin cursor,
regenerable y idempotente (ADR-0023).

**La sonda solo lee.** Abre la memoria sin escribirla (ni indice, ni migracion, ni backups), construye la
pregunta tipo del atributo y la responde con el Core (`Orchestrator._responder_hecho`), sin LLM. Solo
audita. No ejecuta ninguna accion del Motor Unico, asi que el kill switch (b) no la condiciona: con y sin
el fichero KILL produce las mismas sondas (la PARADA (a) del control-plane no forma parte de este CLI).

**Riesgo heredado de `AuditLog` (no se arregla aqui).** `AuditLog` toma `_max_seq` al abrir; un AURA vivo y
`--medir-cm2` son procesos distintos y pueden emitir el MISMO `seq` para eventos distintos. Este modulo no
deduplica por `seq` sino por la identidad completa del registro; otros consumidores del audit log que
dediquen por `seq` (p. ej. cursores de conectores) pueden perder eventos en esa colision.

**Poblacion**: hechos declarados TIPADOS (con `hecho_id`, ver `EjecutorModeloUsuario`). Los ecos
episodicos quedan fuera: no tienen id, ni evento auditado, ni pregunta tipo.

**Honestidad (INV-9)**: la tasa devuelve «sin datos suficientes» sin sondas a 28 dias o bajo el minimo, y el
informe nunca afirma «cero fabricacion»: sin revision humana por muestreo es «no evidenciada».
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from .. import observability as obs
from ..modules.memory import _lineas_legibles, _proyectar
from .identidad_memoria import atributo_declarado, normalizar
from .modelo_usuario import _TIPOS
from .orchestrator import Orchestrator

# ---------------------------------------------------------------- constantes con nombre --

SEGUNDOS_POR_DIA = 86400.0

#: Dias de la edad del hecho en los que se sondea. 28 es el que alimenta la tasa de CM2.
DIAS_SONDA = (7, 14, 28)
DIA_TASA = 28

#: Dias de tolerancia tras el dia 28 para que una sonda cuente como retencion «a 28 dias».
#: provisional (Q5), revisable: una sonda tardia (p. ej. a los 40 o 200 dias) se registra pero no entra en la tasa.
TOLERANCIA_SONDA_DIAS = 7

#: Minimo de sondas de dia 28 (tras aplicar la politica) para publicar un porcentaje.
#: provisional (Q5), revisable: con menos, la cifra no es estable y se declara «sin datos suficientes».
MINIMO_SONDAS_DIA28 = 20

EV_REGISTRADO = "cm2.hecho_registrado"
EV_RETIRADO = "cm2.hecho_retirado"
EV_SONDA = "cm2.sonda"

#: Causas de retirada INICIADAS POR EL USUARIO (las unicas que la politica por defecto excluye).
CAUSAS_USUARIO = ("olvido", "refutacion")

#: Politicas de retirados de la tasa. Es un PARAMETRO, no una constante enterrada (resolucion S3, Q5a).
EXCLUIR_RETIRADAS_USUARIO = "excluir_retiradas_usuario"  # por defecto
CONTAR_TODAS = "contar_todas"
POLITICAS = (EXCLUIR_RETIRADAS_USUARIO, CONTAR_TODAS)

RESULTADOS = ("vigente", "valor_retirado", "nada", "sin_consulta")
SIN_RETIRADA = "ninguna"

SIN_DATOS = "sin datos suficientes"
MEDIDA = "medida"

EV_INICIO = "cm2.inicio"
_HECHO_DECLARADO = "hecho_declarado"


# ------------------------------------------------------------------------- poblacion --


@dataclass(frozen=True)
class Hecho:
    """Un hecho declarado tal como lo cuentan los eventos de auditoria (sin texto)."""

    hecho_id: str
    origen: float  # max(valid_from de la PRIMERA version, ts del inicio): ni la redeclaracion ni el pasado lo mueven
    version: int  # ultima version registrada
    valid_from_actual: float  # max(valid_from de esa ultima version, ts del inicio)
    causa_retirada: str | None  # causa de la retirada posterior a la ultima declaracion, si la hay
    primer_seq: int  # orden estable de aparicion


def _numero(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _identidad(e: dict) -> str:
    """Identidad COMPLETA del registro (seq, evento, ids, dia/causa/version, ts...): solo lo identico es duplicado."""
    return json.dumps(e, sort_keys=True, default=str)


def _ordenados(eventos: Iterable[dict], nombres: tuple[str, ...]) -> list[dict]:
    """Eventos de `nombres` con `seq` valido, ordenados por `seq`.

    Solo se descartan los duplicados EXACTOS (p. ej. el mismo registro leido de un segmento y del activo).
    Dos eventos distintos con el mismo `seq` (colision entre procesos, ver docstring del modulo) se conservan.
    """
    vistos: set[str] = set()
    salida: list[dict] = []
    candidatos = (e for e in eventos if e.get("evento") in nombres and _numero(e.get("seq")))
    for e in sorted(candidatos, key=lambda e: (e["seq"], e.get("ts") if _numero(e.get("ts")) else 0.0)):
        clave = _identidad(e)
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(e)
    return salida


def _id_valido(e: dict) -> bool:
    return isinstance(e.get("hecho_id"), str) and bool(e["hecho_id"])


def inicio_del_reloj(eventos: Iterable[dict]) -> dict | None:
    """El PRIMER evento `cm2.inicio` (por `seq`) con `ts` valido, o None: sin el no hay calendario."""
    return next((e for e in _ordenados(eventos, (EV_INICIO,)) if _numero(e.get("ts"))), None)


def reconstruir_poblacion(eventos: Iterable[dict]) -> dict[str, Hecho]:
    """La poblacion de hechos, reconstruida desde los eventos. Ignora lo incompleto sin reventar.

    El tiempo anterior al inicio NO cuenta: `origen` y `valid_from_actual` se recortan a `ts_inicio`
    (un hecho declarado 60 dias antes del inicio no se sondea «a 28 dias» el primer dia). Sin inicio no se
    recorta nada (no hay calendario: `sondas_pendientes` devuelve vacio).
    """
    eventos = list(eventos)
    inicio = inicio_del_reloj(eventos)
    suelo = float(inicio["ts"]) if inicio else float("-inf")
    registros: dict[str, list[dict]] = {}
    retiradas: dict[str, dict] = {}
    for e in _ordenados(eventos, (EV_REGISTRADO, EV_RETIRADO)):
        if not _id_valido(e):
            continue
        if e["evento"] == EV_REGISTRADO:
            if _numero(e.get("valid_from")) and isinstance(e.get("version"), int):
                registros.setdefault(e["hecho_id"], []).append(e)
        elif e.get("causa") in CAUSAS_USUARIO:
            retiradas[e["hecho_id"]] = e  # la ultima (por seq) manda
    poblacion: dict[str, Hecho] = {}
    for hid, regs in registros.items():
        primera = min(regs, key=lambda e: (e["version"], e["seq"]))
        ultima = max(regs, key=lambda e: (e["version"], e["seq"]))
        ultimo_seq = max(e["seq"] for e in regs)
        retirada = retiradas.get(hid)
        causa = retirada["causa"] if retirada and retirada["seq"] > ultimo_seq else None
        poblacion[hid] = Hecho(
            hecho_id=hid,
            origen=max(float(primera["valid_from"]), suelo),
            version=ultima["version"],
            valid_from_actual=max(float(ultima["valid_from"]), suelo),
            causa_retirada=causa,
            primer_seq=min(e["seq"] for e in regs),
        )
    return poblacion


# ------------------------------------------------------------------------- calendario --


def _sondeadas(eventos: Iterable[dict]) -> set[tuple[str, int]]:
    return {(e["hecho_id"], e["dia"]) for e in _ordenados(eventos, (EV_SONDA,)) if _id_valido(e) and "dia" in e}


def sondas_pendientes(eventos: Iterable[dict], ahora: float) -> list[tuple[Hecho, int]]:
    """Las sondas vencidas (edad >= dia, contada desde max(valid_from, inicio)) que aun no constan. Idempotente.

    Sin evento `cm2.inicio` no hay calendario: devuelve vacio.
    """
    eventos = list(eventos)
    if inicio_del_reloj(eventos) is None:
        return []
    hechas = _sondeadas(eventos)
    pendientes = []
    for hecho in sorted(reconstruir_poblacion(eventos).values(), key=lambda h: h.primer_seq):
        for dia in DIAS_SONDA:
            if ahora - hecho.origen >= dia * SEGUNDOS_POR_DIA and (hecho.hecho_id, dia) not in hechas:
                pendientes.append((hecho, dia))
    return pendientes


# ---------------------------------------------------------------------------- sonda --


def entradas_de_memoria(items: Iterable[dict]) -> list[dict]:
    """Las entradas del modelo de usuario aplanadas como las ve el Core (`ModeloUsuario.ver`) + `hecho_id`."""
    salida = []
    for i in items:
        if i.get("kind") not in _TIPOS:
            continue
        prov = i.get("provenance") or {}
        salida.append(
            {
                "user_id": i.get("user_id"),
                "hecho_id": prov.get("hecho_id"),
                "contenido": i.get("content"),
                "clase": prov.get("clase"),
                "version": prov.get("version"),
                "refutada": prov.get("refutada", False),
                "valid_until": prov.get("valid_until"),
            }
        )
    return salida


def _pregunta_tipo(contenido: str) -> str | None:
    par = atributo_declarado(contenido)
    return f"¿cual es mi {normalizar(par[0])}?" if par else None


def evaluar_sonda(
    hecho_id: str,
    entradas: list[dict],
    causa_retirada: str | None = None,
    responder: Callable[[str, list[dict]], str | None] = Orchestrator._responder_hecho,
) -> dict:
    """Responde la pregunta tipo del atributo del hecho con el Core y clasifica el resultado.

    `resultado` ∈ {vigente, valor_retirado, nada, sin_consulta}; se registra SIEMPRE, y `estado_retirada` en
    bruto va aparte: un estado de retirada no tapa que se haya recuperado un valor retirado (DP §5.2: eso es
    una fabricacion). Se compara la respuesta real con la que daria CADA version aislada: asi no se
    reimplementa la gramatica del Core ni se compara por subcadena.
    """
    n = len(entradas)
    propias = [e for e in entradas if e.get("hecho_id") == hecho_id]
    pregunta = _pregunta_tipo(str(propias[-1].get("contenido", ""))) if propias else None
    if pregunta is None:
        return {"resultado": "sin_consulta", "estado_retirada": causa_retirada or SIN_RETIRADA, "n_entradas_memoria": n}

    usuario = propias[-1].get("user_id")
    vivas = [e for e in entradas if e.get("user_id") == usuario and not e.get("refutada")]
    respuesta = responder(pregunta, vivas)

    def esperada(e: dict) -> str | None:
        # Siempre con el Core real: `responder` solo es la costura para probar un Core con el filtro roto.
        return Orchestrator._responder_hecho(pregunta, [{**e, "valid_until": None, "refutada": False}])

    vigentes = [e for e in propias if not e.get("refutada") and e.get("valid_until") is None]
    retirados = [e for e in propias if e not in vigentes]
    if respuesta is not None and any(respuesta == esperada(e) for e in vigentes):
        resultado = "vigente"
    elif respuesta is not None and any(respuesta == esperada(e) for e in retirados):
        resultado = "valor_retirado"
    else:
        resultado = "nada"
    # Si el hecho sigue vigente no esta «retirado»: un olvido de una version vieja no lo anula.
    estado = SIN_RETIRADA if resultado == "vigente" else (causa_retirada or SIN_RETIRADA)
    return {"resultado": resultado, "estado_retirada": estado, "n_entradas_memoria": n}


def evento_sonda(hecho: Hecho, dia: int, ahora: float, evaluacion: dict) -> dict:
    """Los campos del evento `cm2.sonda` (contrato §2.1). Sin texto del usuario."""
    return {
        "evento": EV_SONDA,
        "hecho_id": hecho.hecho_id,
        "dia": dia,
        "edad_dias": round((ahora - hecho.origen) / SEGUNDOS_POR_DIA, 2),
        "version_edad_dias": round((ahora - hecho.valid_from_actual) / SEGUNDOS_POR_DIA, 2),
        "estado_retirada": evaluacion["estado_retirada"],
        "resultado": evaluacion["resultado"],
        "n_entradas_memoria": evaluacion["n_entradas_memoria"],
    }


# ------------------------------------------------------------------------------ tasa --


@dataclass(frozen=True)
class Tasa:
    veredicto: str  # SIN_DATOS | MEDIDA
    valor: float | None
    recuperados: int
    denominador: int
    excluidos: int
    valor_retirado: int  # candidatos a fabricacion: pendientes de revision humana
    politica: str
    minimo: int
    fuera_de_ventana: int = 0  # sondas de dia 28 con edad fuera de [28, 28 + TOLERANCIA_SONDA_DIAS]
    version_reciente: int = 0  # sondas de dia 28 cuya version tiene menos de 28 dias
    edad_min: float | None = None  # edad de las CONTADAS
    edad_max: float | None = None


def tasa_dia28(
    eventos: Iterable[dict],
    politica: str = EXCLUIR_RETIRADAS_USUARIO,
    minimo: int = MINIMO_SONDAS_DIA28,
) -> Tasa:
    """Recuperaciones vigentes entre sondas de dia 28. Funcion pura.

    Con la politica por defecto solo se excluyen las retiradas iniciadas por el usuario; cualquier otra
    desaparicion cuenta como NO recuperada. «Sin datos suficientes» sin sondas a 28 dias o bajo `minimo`.
    """
    if politica not in POLITICAS:
        raise ValueError(f"politica de retirados desconocida: {politica!r} (validas: {POLITICAS})")
    por_hecho: dict[str, dict] = {}
    for e in _ordenados(eventos, (EV_SONDA,)):
        if _id_valido(e) and e.get("dia") == DIA_TASA:
            por_hecho.setdefault(e["hecho_id"], e)  # una por (hecho, dia): la primera por seq
    todas = list(por_hecho.values())
    # Solo es retencion a 28 dias una sonda hecha entre el dia 28 y el 28 + tolerancia, sobre un valor que ya
    # llevaba >= 28 dias vigente (DP §5.2: un valor cambiado el dia 27 no retiene a 28 dias).
    en_ventana = [
        s
        for s in todas
        if _numero(s.get("edad_dias")) and DIA_TASA <= s["edad_dias"] <= DIA_TASA + TOLERANCIA_SONDA_DIAS
    ]
    sondas = [s for s in en_ventana if _numero(s.get("version_edad_dias")) and s["version_edad_dias"] >= DIA_TASA]
    excluidas = [
        s for s in sondas if politica == EXCLUIR_RETIRADAS_USUARIO and s.get("estado_retirada") in CAUSAS_USUARIO
    ]
    contadas = [s for s in sondas if s not in excluidas]
    recuperados = sum(1 for s in contadas if s.get("resultado") == "vigente")
    suficiente = bool(contadas) and len(contadas) >= minimo
    return Tasa(
        veredicto=MEDIDA if suficiente else SIN_DATOS,
        valor=recuperados / len(contadas) if suficiente else None,
        recuperados=recuperados,
        denominador=len(contadas),
        excluidos=len(excluidas),
        valor_retirado=sum(1 for s in sondas if s.get("resultado") == "valor_retirado"),
        politica=politica,
        minimo=minimo,
        fuera_de_ventana=len(todas) - len(en_ventana),
        version_reciente=sum(
            1 for s in en_ventana if not (_numero(s.get("version_edad_dias")) and s["version_edad_dias"] >= DIA_TASA)
        ),
        edad_min=min((s["edad_dias"] for s in contadas), default=None),
        edad_max=max((s["edad_dias"] for s in contadas), default=None),
    )


# --------------------------------------------------------------------------- informe --


def informe(
    eventos: Iterable[dict], politica: str = EXCLUIR_RETIRADAS_USUARIO, minimo: int = MINIMO_SONDAS_DIA28
) -> str:
    """Texto del estado de CM2. NUNCA afirma «cero fabricacion»: sin revision humana es «no evidenciada»."""
    eventos = list(eventos)
    t = tasa_dia28(eventos, politica, minimo)
    poblacion = reconstruir_poblacion(eventos)
    inicio = inicio_del_reloj(eventos)
    lineas = [
        (
            f"inicio del reloj: {datetime.fromtimestamp(inicio['ts'], tz=UTC).isoformat(timespec='seconds')} (seq {inicio['seq']})"
            if inicio
            else "inicio: no registrado"
        ),
        f"hechos declarados registrados: {len(poblacion)}",
        f"sondas hechas: {len(_sondeadas(eventos))}",
        f"sondas de dia {DIA_TASA} contadas: {t.denominador} (excluidas por politica: {t.excluidos}; politica: {t.politica})",
    ]
    lineas.append(
        f"sondas de dia {DIA_TASA} fuera de la tasa: {t.fuera_de_ventana} tardia(s) (edad fuera de "
        f"[{DIA_TASA}, {DIA_TASA + TOLERANCIA_SONDA_DIAS}] dias), {t.version_reciente} con version de menos de {DIA_TASA} dias"
    )
    if t.edad_min is not None:
        lineas.append(f"edad de las sondas contadas: min {t.edad_min} dias, max {t.edad_max} dias")
    if t.veredicto == SIN_DATOS:
        lineas.append(f"CM2: {SIN_DATOS} (minimo provisional: {t.minimo} sondas de dia {DIA_TASA})")
    else:
        lineas.append(f"CM2 (indicador preliminar): {t.valor * 100:.1f} % ({t.recuperados}/{t.denominador})")  # type: ignore[operator]
    lineas.append(
        f"fabricacion: no evidenciada (sin revision humana por muestreo); {t.valor_retirado} recuperacion(es) de "
        "valor retirado pendientes de revisar"
    )
    return "\n".join(lineas)


# ----------------------------------------------------------- entrada: medir / iniciar --


class MemoriaNoLegible(Exception):
    """`memoria.json` esta siendo escrita o danada: no se mide (reintentar)."""


class DatosNoValidos(Exception):
    """`AURA_DATOS` no es un directorio de AURA en uso: no se inicia nada."""


class _MemoriaSoloLectura:
    """Las entradas vigentes de `memoria.json`, leidas SIN escribir nada.

    `PersistentMemory` crea directorios, migra el formato antiguo y reescribe: aqui ninguna de las tres.
    La proyeccion (ultima linea por clave, sin lapidas) es la misma que aplica al cargar.
    """

    def __init__(self, ruta: str) -> None:
        self._items: list[dict] = []
        if not os.path.exists(ruta):
            return
        try:
            self._leer(ruta)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise MemoriaNoLegible("memoria en escritura o dañada: no se mide; reintentar") from e

    def _leer(self, ruta: str) -> None:
        with open(ruta, encoding="utf-8") as f:
            contenido = f.read().strip()
        if not contenido:
            return
        if contenido.startswith("["):
            self._items = json.loads(contenido)
            return
        # La MISMA proyeccion y la MISMA lectura de linea que `PersistentMemory._load` (sin tolerar lo que
        # ella no tolera): una lectura distinta podria dar por presente un hecho olvidado (lapida `_olvidada`).
        self._items = _proyectar(_lineas_legibles(contenido)[0])


def _eventos_cm2(datos: str) -> list[dict]:
    return [
        r
        for r in obs.leer_audit_desde(os.path.join(datos, "audit.jsonl"), -1)
        if str(r.get("evento", "")).startswith("cm2.")
    ]


def _ruta_audit(datos: str) -> str:
    """El audit log de AURA_DATOS: el mismo `audit.jsonl` que `composicion.componer` pasa a `configure_audit`."""
    return os.path.join(datos, "audit.jsonl")


def _iniciado(eventos: Iterable[dict]) -> bool:
    """Una sola nocion de «iniciado»: la de `inicio_del_reloj` (cm2.inicio con `seq` y `ts` validos)."""
    return inicio_del_reloj(eventos) is not None


def medir(datos: str, ahora: float | None = None) -> str:
    """`--medir-cm2`. Sin evento `cm2.inicio` informa y NO emite; con el, ejecuta las sondas pendientes."""
    import time

    ahora = time.time() if ahora is None else ahora
    eventos = _eventos_cm2(datos)
    if not _iniciado(eventos):
        return (
            "reloj de CM2: NO iniciado\n"
            f"hechos declarados registrados: {len(reconstruir_poblacion(eventos))}\n"
            "no se emiten sondas: la medicion oficial exige el inicio (--iniciar-cm2 --confirmo-inicio)"
        )
    pendientes = sondas_pendientes(eventos, ahora)
    if pendientes:
        entradas = entradas_de_memoria(_MemoriaSoloLectura(os.path.join(datos, "memoria.json"))._items)
        obs.configure_audit(_ruta_audit(datos))
        for hecho, dia in pendientes:
            evaluacion = evaluar_sonda(hecho.hecho_id, entradas, hecho.causa_retirada)
            obs.log("CM2", "reloj-cm2", "sonda", "-", audit=True, **evento_sonda(hecho, dia, ahora, evaluacion))
        eventos = _eventos_cm2(datos)
    return "reloj de CM2: iniciado\n" + informe(eventos)


def iniciar(datos: str, confirmo: bool) -> str:
    """`--iniciar-cm2`: emite `cm2.inicio` al audit log SOLO con confirmacion explicita. Idempotente.

    El inicio es un evento de auditoria (append-only), no un fichero: este modulo no escribe a disco por su
    cuenta, asi que G-1 R-B no necesita ninguna exclusion.
    """
    if _iniciado(_eventos_cm2(datos)):
        return "reloj de CM2: ya iniciado; no se modifica"
    if confirmo and not (
        os.path.isdir(datos)
        and (os.path.exists(os.path.join(datos, "memoria.json")) or os.path.exists(_ruta_audit(datos)))
    ):
        # No se crea el directorio ni se emite: un AURA_DATOS mal escrito arrancaria el reloj en un sitio vacio.
        raise DatosNoValidos(
            f"reloj de CM2: NO iniciado. {datos!r} no es un directorio de AURA en uso "
            "(falta el directorio, o memoria.json y audit.jsonl): no se crea nada"
        )
    if not confirmo:
        return (
            "reloj de CM2: NO iniciado. Iniciar es una decision del CEO: arranca la ventana oficial de medicion.\n"
            "Para iniciarlo repite con --iniciar-cm2 --confirmo-inicio"
        )
    obs.configure_audit(_ruta_audit(datos))
    obs.log("CM2", "reloj-cm2", "inicio de la medicion", "-", audit=True, evento=EV_INICIO)
    return "reloj de CM2: iniciado"
