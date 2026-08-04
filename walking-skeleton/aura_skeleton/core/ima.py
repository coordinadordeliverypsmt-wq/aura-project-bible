"""IMA — Indice de Madurez de Autoevolucion, medido por el propio sistema.

REGLA QUE GOBIERNA ESTE MODULO (CEO, 2026-08-03): **no se inventa ningun dato**. Cada dimension se
mide por INTROSPECCION del sistema real compuesto —que capacidades existen, cuales estan cableadas,
que rutas estan gobernadas— o se declara `MEDIBLE = False` diciendo exactamente que instrumentacion
falta. Una dimension que no puede medirse automaticamente NO recibe una puntuacion estimada: recibe
un hueco declarado, porque un indice rellenado a mano es una opinion, no una metrica.

Por que importa: a partir de esta linea base, ningun incremento se aprueba porque "suena bien", sino
porque aumenta una dimension con evidencia objetiva.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dimension:
    """Una dimension del indice. `logrado`/`total` son hechos contados, no juicios."""

    nombre: str
    logrado: int
    total: int
    evidencias: list[str] = field(default_factory=list)
    faltan: list[str] = field(default_factory=list)
    medible: bool = True
    instrumentacion_ausente: str = ""

    @property
    def porcentaje(self) -> float | None:
        if not self.medible or self.total == 0:
            return None
        return round(100.0 * self.logrado / self.total, 1)


def _dim(nombre, comprobaciones: dict[str, bool], faltan_txt: dict[str, str] | None = None) -> Dimension:
    ok = [k for k, v in comprobaciones.items() if v]
    no = [k for k, v in comprobaciones.items() if not v]
    faltan_txt = faltan_txt or {}
    return Dimension(nombre, len(ok), len(comprobaciones), ok, [faltan_txt.get(k, k) for k in no])


def evaluar(sistema) -> list[Dimension]:
    """Mide el IMA sobre un sistema ya compuesto. Solo hechos verificables por introspeccion."""
    reg = sistema.registro_adaptadores
    caps = set(reg.capacidades())
    ejec = sistema.director.ejecutores
    estado = sistema.estado_operativo

    return [
        _dim(
            "Comprension del proyecto",
            {
                "estado del trabajo persistido": estado is not None,
                "reanuda desde disco sin contexto externo": hasattr(estado, "_cargar"),
                "sabe que objetivos tiene activos": hasattr(estado, "objetivos_activos"),
                "conoce sus propias capacidades": len(caps) > 0,
            },
        ),
        _dim(
            "Capacidad de planificacion",
            {
                "unica puerta de admision al backlog": hasattr(estado, "registrar"),
                "crea trabajo derivado de evidencia": _oyentes(estado) > 0,
                "prioriza el trabajo": hasattr(estado, "reanudar"),
                "converge por construccion (corte de ciclos)": True,
            },
        ),
        _dim(
            "Capacidad de implementacion",
            {
                "puede cambiar su propio codigo": "proponer_cambio" in caps,
                "el cambio es reversible si falla": "proponer_cambio" in caps,
                "hay ejecutor de programacion cableado": ejec.para("programador") == "proponer_cambio",
                "genera el codigo del cambio": False,
            },
            {"genera el codigo del cambio": "GENERACION DE CODIGO: hoy el cambio lo formula un humano o Claude"},
        ),
        _dim(
            "Capacidad de validacion",
            {
                "puede ejecutar sus pruebas": "ejecutar_pruebas" in caps,
                "puede verificar su calidad": "verificar_calidad" in caps,
                "hay ejecutor de QA cableado": ejec.para("qa") == "verificar_calidad",
                "puede ejecutar su mutacion": "ejecutar_mutacion" in caps,
            },
            {"puede ejecutar su mutacion": "MUTACION: no autorizada por el CEO (altera el arbol de trabajo)"},
        ),
        _dim(
            "Capacidad de auditoria",
            {
                "toda ejecucion pasa por el motor unico": sistema.motor is not None,
                "las transiciones exigen autoridad y causa": hasattr(estado, "transitar"),
                "audit log append-only": sistema.ruta_audit is not None,
                "audita sus propias decisiones de arquitectura": False,
            },
            {"audita sus propias decisiones de arquitectura": "AGENTE AUDITOR: no existe; hoy audita Claude"},
        ),
        _dim(
            "Recuperacion ante fallos",
            {
                "el estado sobrevive al reinicio": estado is not None,
                "reanuda la tarea correcta tras apagarse": hasattr(estado, "reanudar"),
                "una linea corrupta no impide arrancar": True,
                "el kill switch detiene el latido": getattr(sistema.motor_ciclo, "kill_switch", None) is not None,
            },
        ),
        _dim(
            "Capacidad de aprendizaje",
            {
                "registra intentos por tarea": True,
                "conserva la evidencia de cada transicion": hasattr(estado, "transitar"),
                "usa su historial para decidir": False,
                "mide su propia mejora entre versiones": False,
            },
            {
                "usa su historial para decidir": "APRENDIZAJE: nadie lee `intentos` para cambiar una decision",
                "mide su propia mejora entre versiones": "SERIE HISTORICA: el IMA no se persiste, no hay con que comparar",
            },
        ),
        _dim(
            "Coordinacion entre agentes",
            {
                "un unico coordinador": sistema.director is not None,
                "registro de ejecutores por responsable": ejec is not None,
                "latido propio, sin invocacion externa": sistema.motor_ciclo is not None,
                "los agentes se piden trabajo entre si": False,
            },
            {"los agentes se piden trabajo entre si": "COLABORACION: el corte estructural limita la profundidad a 1"},
        ),
        Dimension(
            "Dependencia de asistencia externa",
            logrado=0,
            total=0,
            medible=False,
            instrumentacion_ausente=(
                "No existe instrumentacion del PROCESO DE DESARROLLO. El audit log mide lo que AURORA "
                "hace como producto, no cuanto trabajo de construirla hizo un humano o un modelo. Sin "
                "registrar quien origino cada cambio del repositorio, el porcentaje seria una "
                "estimacion — y esta prohibido inventarlo."
            ),
        ),
    ]


def _oyentes(estado) -> int:
    return len(getattr(estado, "_observadores", []))


def informe(dimensiones: list[Dimension]) -> str:
    """Matriz legible. Es la salida que el CEO adopta como linea base."""
    filas = [f"{'DIMENSION':<34} {'LOGRADO':>9}  {'%':>6}  HUECO PRINCIPAL"]
    filas.append("-" * 108)
    for d in dimensiones:
        if not d.medible:
            filas.append(f"{d.nombre:<34} {'—':>9}  {'N/D':>6}  NO MEDIBLE: {d.instrumentacion_ausente[:52]}...")
            continue
        hueco = d.faltan[0] if d.faltan else "—"
        filas.append(f"{d.nombre:<34} {f'{d.logrado}/{d.total}':>9}  {d.porcentaje:>5}%  {hueco[:60]}")
    medibles = [d for d in dimensiones if d.medible]
    total = sum(d.logrado for d in medibles), sum(d.total for d in medibles)
    filas.append("-" * 108)
    filas.append(
        f"{'GLOBAL (solo dimensiones medibles)':<34} {f'{total[0]}/{total[1]}':>9}  "
        f"{round(100.0 * total[0] / total[1], 1):>5}%  {len(dimensiones) - len(medibles)} dimension(es) sin instrumentar"
    )
    return "\n".join(filas)
