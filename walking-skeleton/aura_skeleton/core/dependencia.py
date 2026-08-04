"""Tablero de dependencia externa: cuanto del trabajo lo origina AURORA y donde se detiene.

MIDE EL PROCESO, NO EL PRODUCTO. El IMA mide de que es capaz AURORA; esto mide cuanto de su propio
trabajo hizo sola. Son metricas independientes a proposito (CEO, 2026-08-04).

TODO SE DERIVA DEL HISTORIAL. Se lee el JSONL directamente —no la proyeccion en memoria— y no se
persiste ningun resultado: por ADR-0023, una metrica almacenada seria una segunda fuente de verdad que
podria divergir del historial del que salio.

NO HAY PUNTUACION UNICA (decision del CEO). Las dimensiones son heterogeneas —una razon, un recuento
sin denominador y una indefinida—, y promediarlas produciria un numero que sube cuando el sistema
trabaja mas, no cuando depende menos. Un tablero pequeño y auditable antes que un porcentaje opaco.

CRITERIO METODOLOGICO QUE ESTE MODULO ENCARNA (CEO, 2026-08-04). Durante el diseño se afirmo que la
generacion de trabajo propio tenia un techo del 50 % "por arquitectura". La demostracion formal lo
refuto: una sola tarea bloqueada por tres motivos distintos produce tres derivadas, es decir 75 %, y el
limite tiende a 100 % segun k/(1+k). El 50 % era una propiedad DEL ESCENARIO DE PRUEBA —suponia un
bloqueo por tarea—, no del modelo. De ahi la regla: **nunca se documenta como propiedad arquitectonica
un valor numerico que no pueda derivarse formalmente del modelo**; si depende del comportamiento
observado, se calcula del historial o no se publica.

Lo que SI es propiedad de la arquitectura, y esta demostrado: el trabajo derivado no genera mas trabajo
derivado, la deduplicacion impide dos tareas para la misma evidencia estable, y por tanto converge.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

NO_MEDIBLE = "NO_MEDIBLE"
_DECISORIOS = ("ceo", "asistencia_externa")


@dataclass
class Indicador:
    nombre: str
    numerador: int | None = None
    denominador: int | None = None
    detalle: dict = field(default_factory=dict)
    estado: str = "medible"
    motivo: str = ""

    @property
    def porcentaje(self) -> float | None:
        if self.estado != "medible" or not self.denominador or self.numerador is None:
            return None
        return round(100.0 * self.numerador / self.denominador, 1)


def _vigentes(ruta: str) -> list[dict]:
    """Proyecta el historial: ultima version de cada (objetivo, tarea). Se lee del fichero, no de RAM."""
    p = Path(ruta)
    if not p.exists():
        return []
    proyeccion: dict[tuple[str, str], dict] = {}
    for linea in p.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            t = json.loads(linea)
        except ValueError:
            continue  # una linea ilegible no puede impedir medir el resto
        proyeccion[(t.get("objetivo_id"), t.get("tarea_id"))] = t
    return list(proyeccion.values())


def generacion_de_trabajo_propio(ruta: str) -> Indicador:
    """Fraccion de tareas que AURORA creo a partir de evidencia propia.

    El TECHO no se publica como constante: se DERIVA del historial. Con `k` motivos de bloqueo
    distintos por tarea decisoria, el maximo alcanzable es k/(1+k). Codificar un 50 % convertiria una
    hipotesis en criterio de interpretacion permanente.
    """
    tareas = _vigentes(ruta)
    if not tareas:
        return Indicador("Generacion de trabajo propio", estado=NO_MEDIBLE, motivo="no hay historial que leer")

    derivadas = [t for t in tareas if t.get("origen") == "derivado"]
    decisorias = [t for t in tareas if t.get("origen") in _DECISORIOS]
    k = _motivos_distintos_por_tarea(derivadas, decisorias)
    techo = round(100.0 * k / (1 + k), 1) if k else None

    return Indicador(
        "Generacion de trabajo propio",
        numerador=len(derivadas),
        denominador=len(tareas),
        detalle={
            "tareas_decisorias": len(decisorias),
            "motivos_distintos_observados": k,
            "techo_derivado_del_historial": techo,
            "techo_es_constante_de_arquitectura": False,
        },
    )


def _motivos_distintos_por_tarea(derivadas: list[dict], decisorias: list[dict]) -> int:
    """Mayor numero de derivadas que ha producido una sola tarea decisoria. Es el `k` observado."""
    if not decisorias:
        return 0
    por_causa: Counter = Counter()
    for d in derivadas:
        for e in d.get("evidencias", []):
            if ":" in e:
                por_causa[e.split(":", 1)[0]] += 1
                break
    return max(por_causa.values(), default=0)


def puntos_de_rendicion(ruta: str) -> Indicador:
    """Veces que el ciclo se detuvo esperando a un humano, POR MOTIVO. Recuento absoluto, no razon.

    Convertirlo en porcentaje lo haria mejorable trabajando mas, no dependiendo menos: un sistema que
    hace mil tareas triviales y se rinde diez veces pareceria mas autonomo que uno que hace diez y se
    rinde una. Cada punto es una dependencia concreta que algun dia podra eliminarse.
    """
    tareas = _vigentes(ruta)
    motivos: Counter = Counter()
    for t in tareas:
        if t.get("estado") == "bloqueada":
            for b in t.get("bloqueos", []) or ["bloqueo sin motivo declarado"]:
                motivos[b.split(":")[0][:60]] += 1
    return Indicador(
        "Puntos de rendicion",
        numerador=sum(motivos.values()),
        denominador=None,  # deliberadamente sin denominador
        detalle={"por_motivo": dict(motivos.most_common())},
    )


def autonomia_de_decision(ruta: str) -> Indicador:
    """NO_MEDIBLE mientras solo exista una autoridad capaz de transitar.

    Hoy solo el Director llama a `transitar`, asi que el cociente daria 100 % por construccion: seria
    tecnicamente correcto y metodologicamente engañoso. Pasara a ser informativo cuando existan varias
    autoridades legitimas.
    """
    autoridades = set()
    for t in _vigentes(ruta):
        for e in t.get("evidencias", []):
            if ":" in e and "->" in e:
                autoridades.add(e.split(":", 1)[0])
    if len(autoridades) <= 1:
        return Indicador(
            "Autonomia de decision",
            estado=NO_MEDIBLE,
            motivo=f"una sola autoridad posible ({sorted(autoridades) or 'ninguna'}): el cociente no informaria",
            detalle={"autoridades_observadas": sorted(autoridades)},
        )
    internas = sum(1 for a in autoridades if a == "director")
    return Indicador("Autonomia de decision", numerador=internas, denominador=len(autoridades))


def tablero(ruta: str) -> list[Indicador]:
    return [generacion_de_trabajo_propio(ruta), puntos_de_rendicion(ruta), autonomia_de_decision(ruta)]


def informe(indicadores: list[Indicador]) -> str:
    filas = []
    for i in indicadores:
        if i.estado == NO_MEDIBLE:
            filas.append(f"{i.nombre:<32} NO_MEDIBLE — {i.motivo}")
        elif i.denominador is None:
            filas.append(f"{i.nombre:<32} {i.numerador} punto(s)")
            for m, n in i.detalle.get("por_motivo", {}).items():
                filas.append(f"{'':<34} · {n}× {m}")
        else:
            techo = i.detalle.get("techo_derivado_del_historial")
            t = f" (techo derivado del historial: {techo}%)" if techo is not None else " (sin techo demostrable)"
            filas.append(f"{i.nombre:<32} {i.numerador}/{i.denominador} = {i.porcentaje}%{t}")
    return "\n".join(filas)
