"""Ciclo autonomo de desarrollo — `DEC-ORCH-2` aprobada, `REVIEW` encendido.

    observar -> diagnosticar -> proponer -> clasificar -> [REVIEW] revisor + 4 criterios D22
    -> ejecutar -> probar -> verificar efecto -> registrar -> siguiente -> repetir

**Encadena sin ningun acto humano entre tareas.** Esa es la capacidad que el acta concede, y el
informe la mide: `actos_humanos_durante_el_ciclo` debe salir 0.

## Las seis causas de parada, y ninguna mas

`cola agotada` · `tarea HUMAN` · `verificacion fallida` · `agente no disponible` ·
`limite de seguridad` · `zona prohibida`.

Ninguna de ellas se salta en silencio: la que detiene queda **escrita**, con su motivo y con el
trabajo que quedaba. Es lo que permite retomar sin volver a investigar.

## La cola sale del estado real

No se fabrican tareas para aparentar autonomia. Si el repositorio no tiene trabajo, el informe dice
que no lo tiene: `propuestas = 0`. Un ciclo que siempre encuentra algo que hacer no esta observando,
esta inventando.

## Sin agentes externos

El acta no los contempla y las decisiones vigentes los excluyen. Si el ejecutor no puede trabajar, la
tarea queda pendiente y se registra la clase del fallo — **nunca un exito fingido**—, de modo que
otro ejecutor autorizado pueda retomarla leyendo el Control Plane.
"""

from __future__ import annotations

import pathlib

import control_plane as cp

import autoconstruccion as ac
import review as rv

# Acciones de lectura ya autorizadas por `D-ORCH-3`, que no modifican nada.
_ACCIONES_AUTO = ("ejecutar_pruebas", "verificar_calidad", "auditar_garantias",
                  "diagnosticar_estado")

_SENALES_DE_INDISPONIBILIDAD = ("spend limit", "quota", "rate limit", "usage limit")


def clasificar(tarea: dict, directorio) -> str:
    """`AUTO` / `REVIEW` / `HUMAN`. **Ante la duda, `HUMAN`** (ADR-0003).

    El orden importa: primero la zona —una accion delegable sobre gobernanza sigue siendo `HUMAN`—,
    despues la materia reservada, y solo al final el alcance del acta. Invertirlo dejaria que una
    accion «en alcance» arrastrase consigo un fichero que no debe tocarse."""
    accion = tarea.get("accion", "")
    if accion in _ACCIONES_AUTO:
        return "AUTO"
    if not ac.zona_permitida(tarea.get("fichero", ""), raiz=directorio):
        return "HUMAN"
    if rv.es_materia_reservada(accion):
        return "HUMAN"
    if rv.habilitado(pathlib.Path(directorio)) and rv.en_alcance(pathlib.Path(directorio), accion):
        return "REVIEW"
    return "HUMAN"


def _clase_de_fallo(exc: BaseException) -> str:
    texto = str(exc).lower()
    if any(s in texto for s in _SENALES_DE_INDISPONIBILIDAD):
        return "AGENTE_SIN_CUOTA"
    return "AGENTE_NO_DISPONIBLE"


def ciclo_autonomo(directorio, ficheros, verificacion=None, max_tareas: int = 5,
                   inyectar_human: bool = False) -> dict:
    """Un ciclo completo y **acotado**, sin intervencion humana entre tareas.

    `inyectar_human` existe para las pruebas: fuerza que la segunda tarea se clasifique `HUMAN` y
    permite comprobar que el ciclo se detiene ahi de verdad, en vez de confiar en que lo haria."""
    directorio = pathlib.Path(directorio)
    cp.registrar_evento(directorio, "ciclo_autonomo_iniciado",
                        {"max_tareas": max_tareas, "review": rv.habilitado(directorio)})

    hallazgos = ac.diagnosticar(ac.observar(ficheros))
    informe = {"propuestas": len(hallazgos), "ejecutadas": 0, "revertidas": 0,
               "actos_humanos_durante_el_ciclo": 0, "motivo_de_parada": "cola agotada",
               "detenida_en": None, "siguiente": None, "pendientes": 0, "clase": None}

    for indice, hallazgo in enumerate(hallazgos):
        if informe["ejecutadas"] >= max_tareas:
            informe["motivo_de_parada"] = "limite de seguridad"
            break

        tarea = {"id": f"AUT-{indice + 1:03d}", "accion": "eliminar_codigo_muerto",
                 "fichero": hallazgo["fichero"], "simbolo": hallazgo["simbolo"],
                 "cambia_alcance": False, "respeta_decisiones": True,
                 "d21_afirmativas": True, "materia_reservada": False}
        nivel = "HUMAN" if (inyectar_human and indice == 1) else clasificar(tarea, directorio)

        if nivel != "REVIEW":
            # No se salta en silencio: queda escrita, y el ciclo para. Continuar dejando atras una
            # tarea que necesita a una persona convertiria la parada en un olvido.
            cp.registrar_evento(directorio, "decision_requerida",
                                {"id": tarea["id"], "nivel": nivel, "fichero": tarea["fichero"],
                                 "motivo": f"clasificada {nivel}: requiere acto humano"})
            informe["motivo_de_parada"] = "tarea HUMAN"
            informe["detenida_en"] = tarea["id"]
            break

        try:
            resultado = rv.ejecutar_bajo_review(
                directorio, tarea, propuesto_por="aura", autoridad="orquestador",
                verificacion=verificacion)
        except (ac.ZonaProhibida, rv.MateriaReservada, rv.ReviewNoHabilitado) as exc:
            cp.registrar_evento(directorio, "decision_requerida",
                                {"id": tarea["id"], "nivel": "HUMAN", "motivo": str(exc)[:200]})
            informe["motivo_de_parada"] = "zona prohibida"
            informe["detenida_en"] = tarea["id"]
            break
        except Exception as exc:                        # el ejecutor no pudo: nunca exito fingido
            clase = _clase_de_fallo(exc)
            cp.registrar_evento(directorio, "agente_no_disponible",
                                {"id": tarea["id"], "clase": clase, "motivo": str(exc)[:200]})
            informe.update({"motivo_de_parada": "agente no disponible", "clase": clase,
                            "detenida_en": tarea["id"]})
            break

        if resultado["revertido"] or not resultado["efecto_verificado"]:
            informe["revertidas"] += 1
            informe["motivo_de_parada"] = "verificacion fallida"
            informe["detenida_en"] = tarea["id"]
            break
        informe["ejecutadas"] += 1

    # Lo que queda por hacer, medido sobre el estado **posterior** al ciclo: si se contase sobre la
    # lista inicial, el informe describiria un repositorio que ya no existe.
    restantes = ac.observar(ficheros)
    informe["pendientes"] = len(restantes)
    informe["siguiente"] = restantes[0]["simbolo"] if restantes else None
    cp.registrar_evento(directorio, "ciclo_autonomo_terminado", dict(informe))
    return informe
