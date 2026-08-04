"""Estado Operativo: la memoria de trabajo persistente de AURORA (primer bloque del SO Interno).

PROBLEMA QUE RESUELVE. Hasta hoy el ciclo de trabajo del proyecto solo sobrevivia porque un humano y
un modelo escribian un checkpoint a mano: el objetivo activo, su descomposicion en tareas y el estado
de cada una vivian en el contexto de una conversacion y se perdian al terminarla. Eso incumple el
principio del CEO (2026-08-03): *toda capacidad importante debe sobrevivir al reinicio de una sesion;
si desaparece cuando termina la conversacion, no pertenece a AURORA*.

QUE NO ES. No es "guardar informacion". El criterio de aceptacion es mas duro: AURORA debe poder
**detenerse, apagarse, arrancar de nuevo y continuar exactamente donde estaba** sin depender de Claude,
del contexto de una conversacion ni de un checkpoint escrito a mano. Por eso la prueba que lo valida
mata el proceso de verdad y arranca otro (`tests/integration/test_estado_operativo_reinicio.py`).

POR QUE NO ES UN COMPONENTE NUEVO. `AlmacenReglas` (core/reglas.py) ya resolvio este patron para las
automatizaciones: log JSONL **append-only**, **proyeccion por clave** donde la ultima linea gana, y
**carga desde disco en el constructor**. Aqui se generaliza ese patron cambiando la clave
`(user_id, rule_id)` por `(objetivo_id, tarea_id)`. Reutilizar antes que crear (CEO, 2026-08-03).

FUENTE UNICA DE VERDAD. Los futuros roles del SO Interno —Director General, Planificador, Programador,
QA, Auditor, Investigador, Arquitecto, Documentacion— **comparten este almacen**. No se admiten estados
paralelos ni almacenes alternativos: un segundo estado convertiria la coordinacion en una negociacion
entre copias, que es la clase de defecto que ALERTA-005 y ALERTA-006 ya costaron.

TRAMPA HEREDADA, YA PAGADA. `AlmacenReglas._proyectar` documenta que `crear` anexaba sin proyectar
mientras `desactivar` si lo hacia: tras crear -> desactivar -> crear la misma clave quedaban DOS
entradas y la busqueda encontraba siempre la vieja. Aqui la proyeccion es la UNICA responsable del
estado vigente y se aplica en el mismo metodo que escribe, para que no puedan divergir.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from .. import observability as obs

# Estados posibles de una tarea. `bloqueada` es distinto de `abierta`: una tarea bloqueada NO es la
# siguiente accion, aunque no este terminada. Sin esa distincion, reanudar elegiria trabajo imposible.
ESTADOS = ("abierta", "en_curso", "bloqueada", "terminada", "descartada")
_ABIERTOS = ("abierta", "en_curso")

# PROTOCOLO DE TRANSICIONES (CEO, 2026-08-03). Un unico protocolo valido para TODOS los agentes
# —Director, QA, y los futuros Programador, Arquitecto, Investigador, Seguridad, Documentacion—: no hay
# reglas distintas por agente. Es el mismo principio que el Motor Unico aplica a la ejecucion y la
# politica de admision al nacimiento, ahora extendido al resto de la vida de la tarea.
#
# `terminada` y `descartada` son ESTADOS FINALES: no figuran como origen. Antes de esto cualquier
# componente podia reabrir una tarea cerrada sin declarar por que, porque `actualizar` hacia
# `replace(...)` sin validar nada. El log append-only dejaba rastro, pero auditar no es impedir.
TRANSICIONES: dict[str, tuple[str, ...]] = {
    "abierta": ("en_curso", "bloqueada", "terminada", "descartada"),
    "en_curso": ("bloqueada", "terminada", "descartada"),
    "bloqueada": ("abierta", "en_curso", "descartada"),
    "terminada": (),
    "descartada": (),
}


class TransicionInvalida(Exception):
    """La transicion no esta permitida, o no declara autoridad y causa."""


@dataclass(frozen=True)
class Tarea:
    """Una unidad de trabajo del ciclo, con todo lo necesario para retomarla sin contexto externo."""

    objetivo_id: str
    tarea_id: str
    objetivo: str = ""  # el objetivo activo al que pertenece
    plan: str = ""  # plan actual del que forma parte
    descripcion: str = ""
    estado: str = "abierta"
    responsable: str = ""  # agente del SO Interno: director, planificador, programador, qa, auditor...
    evidencias: list[str] = field(default_factory=list)  # commits, ficheros, resultados de pruebas
    decisiones_pendientes: list[str] = field(default_factory=list)
    bloqueos: list[str] = field(default_factory=list)
    proxima_accion: str = ""
    punto_reanudacion: str = ""  # donde retomar EXACTAMENTE: fichero, funcion, comando
    args: dict = field(default_factory=dict)  # argumentos con los que el Director despacha la tarea
    prioridad: int = 5  # menor = mas urgente. Desempata antes que el identificador.
    origen: str = "ceo"  # ORIGEN DE LA DECISION, no de la persona. Ver ORIGENES en planificacion.py.
    intentos: int = 0  # cuantas veces se ha trabajado. Material para que AURORA aprenda de su historial.

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError(f"estado no valido: {self.estado!r}; esperado uno de {ESTADOS}")


class AlmacenEstadoOperativo:
    """Log append-only del estado del trabajo, proyectado por `(objetivo_id, tarea_id)`.

    El fichero NUNCA se reescribe ni se trunca: cada cambio es una linea nueva y el estado vigente se
    deriva del log. Asi el historial completo queda como evidencia y la reanudacion no depende de que
    nadie haya guardado un resumen.
    """

    def __init__(self, ruta: str, observadores=(), kill_switch=None) -> None:
        self._ruta = Path(ruta)
        # GOBIERNO EN LA PUERTA UNICA (D-M-8). El estado del ciclo era la ultima mutacion persistente
        # que escapaba al control: el Director transitaba tareas sin que el kill switch las alcanzara,
        # de modo que el sistema con el que AURORA evoluciona era el unico fuera de su propio gobierno.
        #
        # Se aplica AQUI y no enrutando por el Motor Unico —que gobierna acciones sobre adaptadores—
        # porque `registrar` ya era la unica puerta de escritura: poner el control en la puerta cubre a
        # TODOS los llamadores, presentes y futuros, sin crear una segunda ruta que mantener. Enrutar
        # por el motor habria exigido un adaptador y una capacidad nuevos para gobernar algo que ya
        # tenia un solo punto de paso.
        self._kill = kill_switch
        self._tareas: list[Tarea] = []
        # Observadores del PROTOCOLO, no del almacen: se les notifica cada transicion consumada. El
        # almacen no sabe quien escucha ni que haran; solo que la transicion ocurrio. Asi el Director
        # no necesita conocer a la planificacion, ni la planificacion al Director (CEO, 2026-08-03).
        self._observadores = list(observadores)
        self._cargar()

    def observar(self, handler) -> None:
        """Registra un oyente de transiciones. `handler(anterior, actual)`."""
        self._observadores.append(handler)

    def _cargar(self) -> None:
        """Reconstruye el estado vigente leyendo el log. Es lo que hace posible reanudar tras un
        reinicio: el constructor no necesita que nadie le pase el contexto anterior."""
        if not self._ruta.exists():
            return
        proyeccion: dict[tuple[str, str], Tarea] = {}
        with open(self._ruta, encoding="utf-8") as f:
            for linea in f:
                if not linea.strip():
                    continue
                try:
                    t = Tarea(**json.loads(linea))
                except (ValueError, TypeError) as e:
                    # Una linea corrupta no puede impedir el arranque: se descarta y se deja constancia.
                    # Es disponibilidad, no integridad: el append-only garantiza que nada mas se pierde.
                    obs.log("WARN", "estado-operativo", f"linea ilegible descartada al cargar: {e}", "-", audit=True)
                    continue
                proyeccion[(t.objetivo_id, t.tarea_id)] = t
        self._tareas = list(proyeccion.values())

    def _proyectar(self, t: Tarea) -> None:
        """Reemplaza la entrada de esta clave; nunca acumula (misma semantica para todas las escrituras)."""
        self._tareas = [x for x in self._tareas if (x.objetivo_id, x.tarea_id) != (t.objetivo_id, t.tarea_id)]
        self._tareas.append(t)

    def registrar(self, tarea: Tarea) -> Tarea:
        """Anexa el estado de una tarea y actualiza la proyeccion. Unica ruta de escritura."""
        self._proyectar(tarea)
        with open(self._ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(tarea), ensure_ascii=False) + "\n")
        obs.log("EST", "estado-operativo", f"{tarea.tarea_id} -> {tarea.estado}", "-", audit=True)
        return tarea

    def actualizar(self, objetivo_id: str, tarea_id: str, **campos) -> Tarea | None:
        """Cambia campos de una tarea vigente anexando una linea nueva. None si no existe."""
        vigente = self.tarea(objetivo_id, tarea_id)
        if vigente is None:
            return None
        return self.registrar(replace(vigente, **campos))

    def transitar(self, objetivo_id: str, tarea_id: str, nuevo: str, *, autoridad: str, causa: str, **campos) -> Tarea:
        """UNICA ruta de cambio de estado. Exige transicion valida, autoridad y causa verificable.

        Simetria con el nacimiento: si crear trabajo exige causa, cerrarlo o reabrirlo tambien. Sin
        esto, la parte gobernada del ciclo de vida era solo la primera.
        """
        if not autoridad or not causa:
            raise TransicionInvalida("toda transicion debe declarar autoridad y causa verificable")
        if self._kill is not None and self._kill.is_engaged():
            # Bible 5.3 §5 / RN-3: con la parada armada NINGUNA accion se ejecuta, tampoco las del
            # propio ciclo de trabajo. Sin esto, AURORA seguiria avanzando tareas con el switch echado.
            raise TransicionInvalida("sistema detenido: el kill switch impide mutar el estado del trabajo")
        vigente = self.tarea(objetivo_id, tarea_id)
        if vigente is None:
            raise TransicionInvalida(f"no existe la tarea {objetivo_id}/{tarea_id}")
        permitidas = TRANSICIONES.get(vigente.estado, ())
        if nuevo not in permitidas:
            final = "" if permitidas else " (es un estado FINAL: no admite salida)"
            raise TransicionInvalida(f"transicion no permitida: {vigente.estado} -> {nuevo}{final}")
        campos.setdefault("evidencias", [*vigente.evidencias, f"{autoridad}:{vigente.estado}->{nuevo}:{causa}"])
        # `intentos` es material de aprendizaje: cuantas veces se ha trabajado esta tarea. Sin el,
        # AURORA puede repetir trabajo pero no mejorar en el.
        campos.setdefault("intentos", vigente.intentos + (1 if nuevo in ("terminada", "bloqueada") else 0))
        actualizada = self.actualizar(objetivo_id, tarea_id, estado=nuevo, **campos)
        assert actualizada is not None  # existe: se comprobo arriba
        for observar in self._observadores:
            # La transicion ya esta consumada y persistida: lo que ocurra despues no puede
            # deshacerla. Un observador que falle no corrompe el estado, solo se pierde su reaccion.
            observar(vigente, actualizada)
        return actualizada

    def tarea(self, objetivo_id: str, tarea_id: str) -> Tarea | None:
        return next((t for t in self._tareas if (t.objetivo_id, t.tarea_id) == (objetivo_id, tarea_id)), None)

    def tareas(self, objetivo_id: str) -> list[Tarea]:
        return [t for t in self._tareas if t.objetivo_id == objetivo_id]

    def abiertas(self, objetivo_id: str) -> list[Tarea]:
        """Tareas que siguen siendo trabajo pendiente. Excluye bloqueadas: no son accionables."""
        return [t for t in self.tareas(objetivo_id) if t.estado in _ABIERTOS]

    def bloqueadas(self, objetivo_id: str) -> list[Tarea]:
        return [t for t in self.tareas(objetivo_id) if t.estado == "bloqueada"]

    def objetivos_activos(self) -> list[str]:
        """Objetivos con al menos una tarea abierta o bloqueada: lo que AURORA aun no ha cerrado."""
        vivos = {t.objetivo_id for t in self._tareas if t.estado in _ABIERTOS or t.estado == "bloqueada"}
        return sorted(vivos)

    def reanudar(self, objetivo_id: str) -> Tarea | None:
        """LA operacion que justifica este modulo: ¿por donde sigo?

        Ordena por PRIORIDAD y desempata por `tarea_id`, de modo que dos arranques del mismo estado
        elijan SIEMPRE lo mismo: sin determinismo, reanudar seria una decision distinta en cada
        reinicio y nada de esto seria auditable.
        """
        return min(self.abiertas(objetivo_id), key=lambda t: (t.prioridad, t.tarea_id), default=None)
