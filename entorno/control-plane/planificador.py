"""Planificacion — convertir una oportunidad **autorizada** en una tarea ejecutable.

Entre «he encontrado trabajo» y «voy a hacerlo» hay una decision, y este modulo es donde se toma.
Toma tres, en realidad, y en este orden:

1. **¿Es esto ejecutable?** Solo lo son las `OPORTUNIDAD_REAL`. Una bloqueada o una decision
   pendiente **no se convierten en tarea**: `a_tarea()` devuelve `None`, y eso es una respuesta
   completa, no un fallo.
2. **¿La he planificado ya?** El id de la tarea se **deriva** de la oportunidad, asi que el duplicado
   se reconoce solo. Sin esto, cada vuelta redescubriria lo mismo y el bucle no terminaria.
3. **¿Cual va primero?** Lo mas reversible: si algo va a salir mal, que salga donde se puede deshacer.

## Lo que este modulo NO hace

**No ejecuta.** La ejecucion sigue pasando por `review.ejecutar_bajo_review` y por
`control_plane.transicion`, con sus mismas puertas. Y **no decide autoridad**: eso lo hizo ya el
descubridor preguntando a `ciclo_autonomo.clasificar`, que consulta zona, materia reservada y acta.
Aqui solo se respeta lo que ya se decidio — un planificador que pudiera reclasificar seria una
segunda politica.
"""

from __future__ import annotations

import hashlib
import pathlib

import control_plane as cp
import descubrimiento as des

#: Riesgo -> orden. Lo reversible primero, y lo no evaluable al final: si no se sabe lo que cuesta
#: equivocarse, no puede ir por delante de lo que se sabe barato.
_ORDEN_DE_RIESGO = {"ninguno": 0, "bajo": 1, "medio": 2, "alto": 3}


def _peso(oportunidad) -> tuple[int, str]:
    cabeza = (oportunidad.riesgo or "").split(":")[0].strip().lower()
    return (_ORDEN_DE_RIESGO.get(cabeza, 9), oportunidad.id)


def id_de_tarea(oportunidad) -> str:
    """Derivado de la oportunidad, **no correlativo**.

    Un contador daria ids distintos a la misma oportunidad en dos vueltas, y el duplicado dependeria
    de que alguien lo recordase. Es la misma razon por la que el `--session-id` del `§13` se deriva
    del sobre: la repeticion tiene que ser **detectable**, no una cuestion de disciplina."""
    return "TA-" + hashlib.sha256(oportunidad.id.encode("utf-8")).hexdigest()[:12]


def a_tarea(oportunidad) -> dict | None:
    """La tarea, o `None` si la oportunidad no es ejecutable.

    `None` no es un fallo: es la respuesta correcta para una decision pendiente o para trabajo que
    exige acta. Devolver una tarea igualmente y confiar en que alguien la filtre despues es como se
    construyen las rutas alternativas."""
    if oportunidad.estado != des.OPORTUNIDAD_REAL:
        return None
    return {
        "id": id_de_tarea(oportunidad),
        "origen": oportunidad.id,
        "accion": oportunidad.accion,
        "fichero": oportunidad.alcance,
        "simbolo": oportunidad.detalle.get("simbolo", ""),
        "objetivo": oportunidad.justificacion,
        "criterio_de_finalizacion": dict(oportunidad.criterio_de_finalizacion),
        "evidencia_requerida": dict(oportunidad.evidencia_requerida),
        "riesgo": oportunidad.riesgo,
        # Los cuatro criterios de D22 viajan con la tarea porque el revisor los necesita para
        # juzgarla. Se declaran aqui y no se deducen en la ejecucion: `INV-7`, el plan se interpreta
        # en un solo punto.
        "cambia_alcance": False,
        "respeta_decisiones": True,
        "d21_afirmativas": True,
        "reversible": True,
        "materia_reservada": False,
    }


def ya_planificada(directorio, id_tarea: str) -> bool:
    return any(e["tipo"] == "tarea_planificada" and e["datos"].get("id") == id_tarea
               for e in cp.leer_eventos(pathlib.Path(directorio)))


def registrar_planificada(directorio, tarea: dict) -> dict:
    """Deja constancia **antes** de ejecutar, y con su origen.

    Lo que se registra aqui es la intencion, no el resultado: marcar el resultado antes de tenerlo es
    el defecto que la 3.a auditoria encontro en `registrar_sesion`, y que quemaba toda tarea `AUTO`
    en su primer intento."""
    return cp.registrar_evento(pathlib.Path(directorio), "tarea_planificada", {
        "id": tarea["id"], "origen": tarea["origen"], "accion": tarea["accion"],
        "fichero": tarea["fichero"], "riesgo": tarea["riesgo"]})


def cola(directorio, oportunidades) -> list[dict]:
    """Las tareas ejecutables **no planificadas todavia**, en orden de riesgo."""
    ordenadas = sorted((o for o in oportunidades if o.estado == des.OPORTUNIDAD_REAL), key=_peso)
    tareas = []
    vistos = set()
    for oportunidad in ordenadas:
        tarea = a_tarea(oportunidad)
        if tarea is None or tarea["id"] in vistos or ya_planificada(directorio, tarea["id"]):
            continue
        vistos.add(tarea["id"])
        tareas.append(tarea)
    return tareas


def siguiente(directorio, oportunidades) -> dict | None:
    """La siguiente tarea, o `None` si no hay ninguna.

    `None` significa **«no hay trabajo autorizado ahora mismo»**, que es una afirmacion con evidencia
    detras: se ha vuelto a descubrir y no habia. No significa «no puedo hacer nada», y no existe
    ninguna rama que diga «si no hay tareas, inventar una»."""
    pendientes = cola(directorio, oportunidades)
    return pendientes[0] if pendientes else None


def informe_de_cola(oportunidades) -> dict:
    """Lo que hay que poder decir de la cola sin volver a mirarla."""
    return {
        "ejecutables": sum(1 for o in oportunidades if o.estado == des.OPORTUNIDAD_REAL),
        "bloqueadas": sum(1 for o in oportunidades if o.estado == des.BLOQUEADA),
        "elevadas": sum(1 for o in oportunidades if o.estado == des.DECISION_REQUIRED),
        "falsos_huecos": sum(1 for o in oportunidades if o.estado == des.FALSO_HUECO),
    }


__all__ = ["a_tarea", "cola", "siguiente", "id_de_tarea", "ya_planificada",
           "registrar_planificada", "informe_de_cola"]
