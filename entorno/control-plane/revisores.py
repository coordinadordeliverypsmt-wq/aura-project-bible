"""**F4** — `C5` con `RevisorSubagente` / `RevisorHumano`. Contrato de `§8.2` y `§8.3` del DP.

Autorizada porque `§20` la hace depender de `F3 + §25.2`, y **§25.2 es `D-ORCH-2`, aprobada por el
CEO el 2026-08-26**.

## El veredicto, literal del contrato

Cuatro valores —`conforme` · `objeciones` · `rechazo` · `fuera_de_alcance`—, motivos, **evidencia
citada**, revisor e instante. Y el comentario del DP que vale por toda una decision: *«NO existe campo
"autoriza". **Deliberadamente**.»*

**Sin cita, no cuenta.** Un «conforme» sin rutas ni lineas es una opinion, y una opinion no mueve una
tarea. `cuenta()` lo aplica.

## Degradacion (`§8.3`), que es la garantia central

*«Si no hay revisor disponible, la tarea que exige revision pasa a `WAITING_FOR_REVIEW` y **espera**.
**No se autoaprueba jamas.** Las tareas `AUTO` siguen avanzando: el sistema no se detiene entero
porque falte el revisor.»*

Las dos mitades importan por igual. Sin la primera, la falta de revisor se convertiria en permiso.
Sin la segunda, un revisor caido paralizaria trabajo que no lo necesita.

## Los cuatro revisores, con su estado real

| Revisor | Hoy | Por que |
|---|---|---|
| `RevisorSubagente` | **disponible** | usa `auditor-consistencia` / `arquitecto-evaluador`, que **ya existen** |
| `RevisorHumano` | **disponible** | buzon asincrono: pedir revision a una persona no produce un veredicto, produce una espera |
| `RevisorLocal` | **sin capacidad** | previsto sobre Ollama; devolver un veredicto inventado seria fingir capacidad (INV-9) |
| `RevisorExterno` | **bloqueado** | `§25.1` sin resolver y D24 sin enmendar |
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import pathlib

import control_plane as cp

import autoconstruccion as ac
import review as rv

VEREDICTOS = ("conforme", "objeciones", "rechazo", "fuera_de_alcance")
RAIZ_AGENTES = ac.RAIZ_AGENTES
NOMBRE_BUZON = "buzon_revision.jsonl"

# Acciones que **no** exigen revision: las de lectura ya autorizadas por `D-ORCH-3`. `§8.3`: sin
# revisor, estas siguen avanzando.
_SIN_REVISION = ("ejecutar_pruebas", "verificar_calidad", "auditar_garantias", "diagnosticar_estado")


class RevisorBloqueado(RuntimeError):
    """`RevisorExterno`: `§25.1` sin resolver y D24 sin enmendar."""


class RevisorSinCapacidad(RuntimeError):
    """`RevisorLocal`: previsto, sin capacidad hoy. **No se finge** (INV-9)."""


class RespuestaDuplicada(RuntimeError):
    """Llego una segunda respuesta al mismo `review_id`. `§12`: *«Respuesta duplicada -> mismo
    review_id -> segunda descartada por idempotencia»*.

    **Manda la primera.** Si mandase la ultima, quien quisiera cambiar un veredicto solo tendria que
    volver a responder, y un veredicto revisable a voluntad no es un veredicto."""


class RevisorNoHumano(RuntimeError):
    """Alguien que no es una persona intento responder el buzon humano."""


def _ahora() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


@dataclasses.dataclass(frozen=True)
class Veredicto:
    """Literal de `§8.2`. **Sin campo `autoriza`, deliberadamente.**"""
    veredicto: str
    motivos: tuple[str, ...]
    evidencia_citada: tuple[str, ...]
    revisor: str
    instante: str

    def __post_init__(self) -> None:
        if self.veredicto not in VEREDICTOS:
            raise ValueError(f"veredicto invalido: {self.veredicto!r}; validos: {VEREDICTOS}")


def cuenta(veredicto: Veredicto | None) -> bool:
    """*«rutas y lineas; **sin cita, no cuenta**»*."""
    return veredicto is not None and bool(veredicto.evidencia_citada)


def autoriza(_veredicto) -> bool:
    """Siempre False. `1.1:93`: la autoridad final del CEO no es delegable a ningun agente, y
    `D-ORCH-2` no cambio eso — permitio **ejecutar dentro de un alcance ya autorizado**."""
    return False


@dataclasses.dataclass(frozen=True)
class Expediente:
    """Lo que el revisor necesita, y nada mas. No viaja ninguna credencial."""
    tarea_id: str
    accion: str
    fichero: str
    diagnostico: str
    criterios: dict

    def como_dict(self) -> dict:
        return {"tarea_id": self.tarea_id, "accion": self.accion, "fichero": self.fichero,
                "diagnostico": self.diagnostico, "criterios": dict(self.criterios)}


def exige_revision(accion: str) -> bool:
    return accion not in _SIN_REVISION


# --------------------------------------------------------------- los revisores --

class RevisorSubagente:
    """Usa los agentes que **ya existen**. `§275`: *«Se usan esos. No se crea un revisor nuevo ni se
    contrata un proveedor»*."""

    def __init__(self, nombre: str = "auditor-consistencia") -> None:
        self.nombre = nombre

    def disponible(self) -> bool:
        return (pathlib.Path(RAIZ_AGENTES) / f"{self.nombre}.md").exists()

    def revisar(self, expediente: Expediente) -> Veredicto:
        if rv.es_materia_reservada(expediente.accion) or not ac.zona_permitida(expediente.fichero):
            return Veredicto("fuera_de_alcance",
                             (f"{expediente.accion} sobre {expediente.fichero} no es delegable",),
                             (f"{expediente.fichero}:0",), self.nombre, _ahora())
        juicio = rv.aplicar_criterios({"accion": expediente.accion, **expediente.criterios})
        cita = (f"{expediente.fichero}:0", f"criterios D22: {','.join(rv.CRITERIOS_D22)}")
        if juicio["cumple"]:
            return Veredicto("conforme", (), cita, self.nombre, _ahora())
        return Veredicto("objeciones", tuple(f"incumple {f} (D22)" for f in juicio["fallos"]),
                         cita, self.nombre, _ahora())


class RevisorHumano:
    """Buzon **asincrono**: pedir revision a una persona no produce un veredicto, produce una espera.
    Devolver algo aqui seria inventar una respuesta que nadie ha dado."""

    nombre = "humano"

    def __init__(self, directorio=None) -> None:
        self.directorio = pathlib.Path(directorio) if directorio else None

    def disponible(self) -> bool:
        return True

    def revisar(self, expediente: Expediente):
        if self.directorio is None:
            return None
        ruta = self.directorio / NOMBRE_BUZON
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**expediente.como_dict(), "pedido_en": _ahora(),
                                 "review_id": review_id(expediente),
                                 "respondido": False}, ensure_ascii=False) + "\n")
        return None


class RevisorLocal:
    """Previsto sobre Ollama, **hoy sin capacidad** (`§8.2`). No se finge (INV-9)."""

    nombre = "local"

    def disponible(self) -> bool:
        return False

    def revisar(self, _expediente: Expediente) -> Veredicto:
        raise RevisorSinCapacidad(
            "el revisor local esta previsto pero hoy no tiene capacidad; devolver un veredicto "
            "inventado seria fingir una capacidad no construida (INV-9)")


class RevisorExterno:
    """**Bloqueado** por `§25.1` + enmienda de D24 pendiente."""

    nombre = "externo"

    def disponible(self) -> bool:
        return False

    def revisar(self, _expediente: Expediente) -> Veredicto:
        raise RevisorBloqueado(
            "el revisor externo exige resolver §25.1 (D-ORCH-1) y una enmienda documentada de D24; "
            "ninguna consta")


# ------------------------------------------------------------------- el buzon --

def review_id(expediente: Expediente) -> str:
    """Identificador **derivado** de la peticion de revision, no aleatorio.

    La misma razon que el `--session-id` del `§13`: si fuese aleatorio, reconocer una respuesta
    duplicada dependeria de que alguien guardase el id y no lo perdiera. Derivado, dos peticiones del
    mismo expediente **son** la misma peticion y se reconocen solas."""
    canonico = json.dumps(expediente.como_dict(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:32]


def respuesta_ya_registrada(directorio, identificador: str) -> bool:
    return any(e["tipo"] == "respuesta_de_revision" and e["datos"].get("review_id") == identificador
               for e in cp.leer_eventos(pathlib.Path(directorio)))


def intentos_de_revision(directorio, tarea_id: str) -> int:
    """Cuantas veces se pidio revision de esa tarea **sin obtener veredicto**. Cuenta ausencias, no
    revisiones: un revisor que responde no gasta reintentos."""
    return sum(1 for e in cp.leer_eventos(pathlib.Path(directorio))
               if e["tipo"] == "revision_sin_respuesta" and e["datos"].get("id") == tarea_id)


def _leer_buzon(directorio) -> list[dict]:
    ruta = pathlib.Path(directorio) / NOMBRE_BUZON
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def buzon_pendientes(directorio) -> list[dict]:
    return [p for p in _leer_buzon(directorio) if not p.get("respondido")]


def responder_buzon(directorio, tarea_id: str, veredicto: str, por: str,
                    evidencia_citada: tuple[str, ...], motivos: tuple[str, ...] = ()) -> Veredicto:
    """Solo una persona responde el buzon humano, y **con cita**."""
    if por not in ac.AUTORIDADES_HUMANAS:
        raise RevisorNoHumano(
            f"{por!r} no es una persona: el buzon humano existe precisamente para lo que un agente "
            f"no puede responder")
    if not evidencia_citada:
        raise ValueError("sin cita, no cuenta (§8.2): un veredicto sin evidencia es una opinion")
    directorio = pathlib.Path(directorio)
    lineas = _leer_buzon(directorio)
    pendiente = next((x for x in lineas if x["tarea_id"] == tarea_id), None)
    identificador = (pendiente or {}).get("review_id") or tarea_id
    if respuesta_ya_registrada(directorio, identificador):
        raise RespuestaDuplicada(
            f"ya hay una respuesta registrada para la revision {identificador!r} de {tarea_id!r}: "
            f"manda la primera (§12). Un veredicto que se puede reescribir respondiendo otra vez no "
            f"es un veredicto")
    for linea in lineas:
        if linea["tarea_id"] == tarea_id:
            linea["respondido"] = True
    (directorio / NOMBRE_BUZON).write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lineas), encoding="utf-8")
    emitido = Veredicto(veredicto, motivos, tuple(evidencia_citada), por, _ahora())
    cp.registrar_evento(directorio, "respuesta_de_revision",
                        {"id": tarea_id, "review_id": identificador, "veredicto": veredicto,
                         "por": por})
    cp.registrar_evento(directorio, "veredicto_emitido", {
        "id": tarea_id, "revisor": por, "veredicto": veredicto,
        "motivos": list(motivos), "evidencia_citada": list(evidencia_citada)})
    return emitido


# ------------------------------------------------------- §8.3 · degradacion --

def pedir_revision(directorio, expediente: Expediente, revisores, autoridad: str,
                   max_reintentos: int | None = None) -> dict:
    """Recorre la cadena y usa el **primer revisor que pueda**. Si ninguno puede, la tarea pasa a
    `WAITING_FOR_REVIEW` y **espera**: la ausencia de revisor no es una aprobacion."""
    directorio = pathlib.Path(directorio)
    for revisor in revisores:
        if not revisor.disponible():
            continue
        veredicto = revisor.revisar(expediente)
        if veredicto is None:            # el humano: queda en el buzon, no hay veredicto todavia
            continue
        if not cuenta(veredicto):
            continue                     # sin cita no cuenta: se sigue buscando
        cp.registrar_evento(directorio, "veredicto_emitido", {
            "id": expediente.tarea_id, "revisor": veredicto.revisor,
            "veredicto": veredicto.veredicto, "motivos": list(veredicto.motivos),
            "evidencia_citada": list(veredicto.evidencia_citada)})
        return {"veredicto": veredicto, "estado": "REVISADA"}

    # **No se autoaprueba jamas.**
    cp.registrar_evento(directorio, "revision_sin_respuesta",
                        {"id": expediente.tarea_id, "review_id": review_id(expediente)})
    if cp.estado_de(directorio, expediente.tarea_id) == "WORKING":
        cp.transicion(directorio, expediente.tarea_id, cp.ESTADO_REVISION, autoridad=autoridad,
                      causa="ningun revisor disponible: la tarea espera, no se autoaprueba (§8.3)")

    # `§12`: *«Respuesta del revisor perdida -> reintento **acotado**, luego DECISION_REQUIRED»*.
    # Acotado es la palabra: un reintento sin tope es un bucle, y el `§14` no autoriza ninguno.
    # Y escalar **no es aprobar** (`1.1:85`): la tarea sube a una decision humana, no a COMPLETED.
    # Esperar en silencio para siempre era lo que hacia antes, y es la peor de las tres opciones:
    # no aprueba, pero tampoco avisa a nadie.
    if max_reintentos is not None and intentos_de_revision(directorio, expediente.tarea_id) > int(max_reintentos):
        if cp.estado_de(directorio, expediente.tarea_id) == cp.ESTADO_REVISION:
            cp.transicion(directorio, expediente.tarea_id, "DECISION_REQUIRED", autoridad=autoridad,
                          causa=f"agotados {max_reintentos} reintentos de revision sin respuesta")
        return {"veredicto": None, "estado": "DECISION_REQUIRED"}
    return {"veredicto": None, "estado": cp.ESTADO_REVISION}
