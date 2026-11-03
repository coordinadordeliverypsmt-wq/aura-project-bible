"""`DR-E` — representacion generica **Oportunidad -> Propuesta**.

## Que cierra

El diagnostico anterior encontro un bloqueo de **forma**, no de permiso: el circuito de propuesta solo
sabia representar una clase de hallazgo —codigo muerto—, porque nacio para ella. Pasarle cualquier
otra oportunidad producia una propuesta con todos los campos a `None`: una peticion vacia que decia
borrar el simbolo `None` del fichero `None`. Esto construye la forma que faltaba.

## La unica regla dura

**Transcribe lo observado; no inventa lo que exige juicio.**

Lo que AURA sabe se copia tal cual. Lo que no sabe se marca `REQUIERE_REVISION_HUMANA` — no se
rellena con un default plausible. La diferencia importa mas de lo que parece: un «riesgo: bajo»
puesto por costumbre es indistinguible de un riesgo evaluado, y quien lea la propuesta no tiene forma
de saber que nadie lo penso. Rellenarlo seria fingir capacidad (`INV-9`).

Por eso esta representacion **no razona**. No puede: el unico razonador previsto sigue sin capacidad,
y `DR-E` no lo habilita.

## Por que es una generalizacion AL LADO y no una sustitucion

`autoconstruccion.proponer` no se toca. Sigue siendo el camino del codigo muerto, con su registro de
evento y su ruta a la autorizacion, exactamente como estaba. Este modulo ni siquiera lo importa: dos
caminos que se cruzan acaban siendo una ruta alternativa, y de eso este proyecto ya tiene una alerta
con nombre propio (`ALERTA-005`).

## Por que es una funcion pura

No registra eventos, no escribe, no autoriza. Registrar es un **acto**, y representar no lo es. Que
esta pieza no pueda actuar es lo que permite construirla sin ampliar ninguna autoridad: no esta
cableada en el ciclo autonomo, porque cablearla seria habilitar trabajo autonomo nuevo, y `DR-E` no
lo autoriza.
"""
from __future__ import annotations

import descubrimiento as des
import orquestador as orq
import planificador as plan
import review as rv

#: Centinela unico. Un campo con este valor dice **«nadie ha pensado esto todavia»**, que es una
#: afirmacion verdadera; cualquier otro valor por defecto seria una falsa.
REQUIERE_REVISION_HUMANA = "REQUIERE_REVISION_HUMANA"

#: Lo que no se deriva de la observacion. `riesgo_de_actuar` no es el riesgo que declara la fuente
#: —ese es el de *observar*, y es un hecho—: es el de **hacer algo con lo observado**, y ese depende
#: de una intencion que esta pieza no tiene y no debe suponer.
CAMPOS_DE_JUICIO = ("riesgo_de_actuar", "criterio_de_rollback", "pruebas_necesarias", "decision")

#: Claves de `detalle` que describen un objeto de codigo concreto. Si no hay ninguna, la oportunidad
#: no afecta a un objeto — y eso es un **hecho observado**, no un hueco de juicio: por eso `None` y
#: no el centinela.
_CLAVES_DE_OBJETO = ("simbolo", "forma", "linea")


def _objeto_afectado(detalle: dict):
    presentes = {k: detalle.get(k) for k in _CLAVES_DE_OBJETO if detalle.get(k) is not None}
    return presentes or None


def de_oportunidad(oportunidad) -> dict:
    """La propuesta estructurada. **Pura**: no registra, no autoriza, no ejecuta.

    Nace `PROPUESTA` y sin autorizar, y nada aqui puede cambiarlo: `1.1:85` —el silencio no aprueba—
    y `1.1:93` —la autoridad del CEO no es delegable—. Lo unico que hace esta funcion es dejar la
    peticion en una forma que un humano pueda leer y decidir sin volver a mirarlo todo."""
    if not isinstance(oportunidad, des.Oportunidad):
        raise TypeError(
            f"solo se representa una Oportunidad construida, no {type(oportunidad).__name__}: lo que "
            f"no paso la barrera de procedencia no puede entrar por aqui")

    detalle = dict(oportunidad.detalle)
    return {
        # 10 · estado — nace sin autorizar, y esta pieza no tiene forma de concederlo
        "id": f"P-{oportunidad.id}",
        "estado": "PROPUESTA",
        "autorizada": False,

        # 1 · identidad · 2 · accion propuesta
        "origen": oportunidad.id,
        "accion": oportunidad.accion,

        # 4 · fuente/origen — verificable: lleva a un fichero o a un mecanismo declarado
        "fuente": oportunidad.fuente,

        # 3 · evidencia observada — transcrita, no reinterpretada
        "evidencia": {
            "clase": oportunidad.estado,
            "alcance": oportunidad.alcance,
            "criterio_de_finalizacion": dict(oportunidad.criterio_de_finalizacion),
            "evidencia_requerida": dict(oportunidad.evidencia_requerida),
            #: El riesgo **de observar**, tal como lo declaro la fuente. No es el de actuar.
            "riesgo_declarado_por_la_fuente": oportunidad.riesgo,
            "detalle": detalle,
        },

        # 5 · objeto afectado, si existe
        "objeto": _objeto_afectado(detalle),

        # 6 · justificacion — la de la oportunidad, literal. Reformularla ya seria interpretar
        "justificacion": oportunidad.justificacion,

        # 7 · nivel de autorizacion — se **lee** del orquestador, no se decide aqui
        "nivel_de_autorizacion": orq.nivel_de(oportunidad.accion),
        "autoridad_declarada": oportunidad.autoridad,

        # 8 · limites conocidos — hechos comprobables contra el estado real, no opiniones
        "limites": {
            "es_ejecutable_hoy": plan.a_tarea(oportunidad) is not None,
            "en_acciones_AUTO": oportunidad.accion in orq.acciones_de_nivel("AUTO"),
            "en_todo_lo_delegable": oportunidad.accion in rv.TODO_LO_DELEGABLE,
        },

        # 9 · lo que exige juicio humano — marcado, nunca rellenado
        "requiere_juicio_humano": {campo: REQUIERE_REVISION_HUMANA for campo in CAMPOS_DE_JUICIO},
    }


__all__ = ["de_oportunidad", "REQUIERE_REVISION_HUMANA", "CAMPOS_DE_JUICIO"]
