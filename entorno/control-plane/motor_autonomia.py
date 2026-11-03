"""Motor de autonomia — el ciclo completo, **sin nadie que entregue las tareas**.

    DESCUBRIR -> CLASIFICAR -> VALIDAR AUTORIDAD -> PLANIFICAR -> CREAR TAREA
              -> [EJECUTAR: el circuito gobernado que YA existe] -> VERIFICAR
              -> REGISTRAR -> SELECCIONAR SIGUIENTE -> REPETIR

## Lo que este modulo NO es

**No es un segundo motor de ejecucion.** No escribe un solo fichero: la ejecucion, la verificacion
del efecto y la reversion siguen siendo las de `review.ejecutar_bajo_review`, con sus cuatro puertas
—materia reservada, nivel habilitado, alcance del acta y veredicto sin objeciones— y con el
`control_plane` gobernando cada transicion. Una prueba lo comprueba **leyendo este fuente**: el dia
que aparezca aqui un `write_text`, se vera antes que en una auditoria.

Lo que se anade es el tramo de arriba. `ciclo_autonomo(directorio, ficheros, ...)` recibia la lista
de ficheros desde fuera, y **ese parametro era el traspaso manual**: alguien —hasta hoy, la asistencia
externa— decidia donde mirar.

## Por que una vuelta redescubre en vez de recordar

Cada iteracion vuelve a llamar al descubridor. Es mas caro que guardar la cola, y es a proposito: el
arbol **cambia** con cada tarea ejecutada, asi que una cola calculada al principio describe un mundo
que ya no existe. Y hace que «cola agotada» signifique *«he vuelto a mirar y no hay»*, que es una
afirmacion con evidencia, en vez de *«ya no me quedaban apuntadas»*.

## Las paradas

Una parada **no es un fallo**, y por eso todas dejan escrito su motivo exacto. Lo que si seria un
fallo es una parada silenciosa: obligaria al siguiente a reconstruir por que se paro, y reconstruir es
precisamente lo que el Protocolo de Continuidad existe para evitar.
"""

from __future__ import annotations

import pathlib

import autoconstruccion as ac
import control_plane as cp
import descubrimiento as des
import orquestador as orq
import planificador as plan
import review as rv

#: Tope duro. `§14`: ningun bucle sin cota. La autonomia no es correr sin freno, y un motor que
#: decide cuando parar por su cuenta es exactamente el demonio que este DP no autoriza.
MAX_TAREAS = 25


def _actos_humanos_desde(directorio, seq_inicial: int) -> int:
    """Cuantos actos de autoridad humana se registraron **mientras el ciclo corria**.

    Estaba inicializado a `0` y no se incrementaba nunca: una constante que las pruebas leian como si
    fuera una medicion, y justo la cifra que decide si esto es autonomia o teatro. Lo encontro una
    auditoria independiente.

    Se cuenta del historial, que es donde consta quien hizo que: contarlo en memoria dependeria de que
    el propio ciclo se acordara de anotarse sus interrupciones."""
    return sum(1 for e in cp.leer_eventos(pathlib.Path(directorio))
               if e["seq"] > seq_inicial
               and (e["datos"] or {}).get("autoridad") in cp.AUTORIDADES_HUMANAS)


def _detener(directorio, informe: dict, motivo: str, detenida_en=None, desde: int = 0) -> dict:
    informe["actos_humanos_durante_el_ciclo"] = _actos_humanos_desde(directorio, desde)
    informe["motivo_de_parada"] = motivo
    informe["detenida_en"] = detenida_en
    cp.registrar_evento(pathlib.Path(directorio), "ciclo_detenido",
                        {"motivo": motivo, "detenida_en": detenida_en,
                         "ejecutadas": informe["ejecutadas"],
                         "bloqueadas": informe["bloqueadas"], "elevadas": informe["elevadas"]})
    return informe


def trabajar(directorio, raiz, verificacion=None, max_tareas: int = 5) -> dict:
    """Descubre, planifica, ejecuta y vuelve a empezar, **sin actos humanos entre tareas**.

    `raiz` es donde mirar, no que hacer: el descubridor decide lo segundo. La diferencia parece
    pequena y es toda la diferencia — un arbol es un sitio, una lista de tareas es una instruccion.

    `actos_humanos_durante_el_ciclo` se **cuenta**, no se declara: cualquier tarea que salga
    clasificada fuera de `REVIEW` incrementa el contador de elevadas y no se ejecuta."""
    directorio = pathlib.Path(directorio)
    tope = min(int(max_tareas), MAX_TAREAS)
    informe = {"ejecutadas": 0, "ejecutadas_ids": [], "descubiertas": 0, "bloqueadas": 0,
               "elevadas": 0, "falsos_huecos": 0, "revertidas": 0,
               "actos_humanos_durante_el_ciclo": 0, "motivo_de_parada": "cola agotada",
               "detenida_en": None, "vueltas": 0}

    arranque = cp.registrar_evento(directorio, "motor_iniciado",
                                   {"raiz": str(raiz), "tope": tope,
                                    "review": rv.habilitado(directorio)})["seq"]

    for _ in range(tope + 1):
        # El kill switch, en **cada** vuelta y antes de nada: un interruptor que solo se consulta al
        # arrancar no detiene lo que ya empezo, que es cuando hace falta detenerlo.
        if orq.parada_solicitada(directorio):
            return _detener(directorio, informe, "kill switch activado", desde=arranque)

        oportunidades = des.descubrir(raiz, directorio)
        informe["vueltas"] += 1
        resumen = plan.informe_de_cola(oportunidades)
        informe["descubiertas"] = len(oportunidades)
        informe["bloqueadas"] = resumen["bloqueadas"]
        informe["elevadas"] = resumen["elevadas"]
        informe["falsos_huecos"] = resumen["falsos_huecos"]

        if informe["ejecutadas"] >= tope:
            return _detener(directorio, informe, "limite de seguridad", desde=arranque)

        tarea = plan.siguiente(directorio, oportunidades)
        if tarea is None:
            # **No hay rama «si no hay tareas, inventar una».** Se ha vuelto a mirar y no hay trabajo
            # autorizado; lo bloqueado y lo elevado siguen contados en el informe, que es la
            # diferencia entre «no hay nada que hacer» y «no puedo hacer nada».
            return _detener(directorio, informe, "cola agotada", desde=arranque)

        plan.registrar_planificada(directorio, tarea)
        try:
            resultado = rv.ejecutar_bajo_review(
                directorio, tarea, propuesto_por="aura", autoridad="orquestador",
                verificacion=verificacion)
        except (ac.ZonaProhibida, rv.MateriaReservada, rv.ReviewNoHabilitado) as exc:
            cp.registrar_evento(directorio, "decision_requerida",
                                {"id": tarea["id"], "origen": tarea["origen"],
                                 "motivo": str(exc)[:200]})
            informe["bloqueadas"] += 1
            return _detener(directorio, informe, "zona prohibida", tarea["id"], desde=arranque)

        if resultado.get("estado") == cp.ESTADO_REVISION:
            # `§8.3`: sin revisor capaz la tarea **espera**. Esperar no es fracasar, y sobre todo no
            # es aprobar.
            return _detener(directorio, informe, "sin revisor capaz", tarea["id"], desde=arranque)
        if not resultado.get("ejecutado"):
            if resultado.get("revertido"):
                informe["revertidas"] += 1
                return _detener(directorio, informe, "verificacion fallida", tarea["id"], desde=arranque)
            return _detener(directorio, informe, "objeciones del revisor", tarea["id"], desde=arranque)

        informe["ejecutadas"] += 1
        informe["ejecutadas_ids"].append(tarea["id"])

    return _detener(directorio, informe, "limite de seguridad", desde=arranque)


def diagnostico(directorio, raiz) -> dict:
    """Que ve el motor **sin tocar nada**. Es lo que un humano querria mirar antes de soltarlo.

    Separa las cuatro clases a proposito: un informe que solo dijera «hay N tareas» ocultaria que
    puede haber diez oportunidades reales bloqueadas por falta de un acta, que es justo la
    informacion que decide si merece la pena firmarla."""
    oportunidades = des.descubrir(raiz, pathlib.Path(directorio))
    return {
        "raiz": str(raiz),
        "por_clase": des.resumen(oportunidades),
        "cola": plan.informe_de_cola(oportunidades),
        "hay_trabajo_autorizado": des.hay_trabajo_autorizado(oportunidades),
        "review_habilitado": rv.habilitado(pathlib.Path(directorio)),
        "alcance_del_acta": list(rv.alcance_actual(pathlib.Path(directorio))),
    }


__all__ = ["trabajar", "diagnostico", "MAX_TAREAS"]
