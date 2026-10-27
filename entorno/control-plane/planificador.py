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
import os
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


#: Las decisiones que **de verdad** aplican a borrar codigo muerto en el plano de desarrollo, y que
#: el revisor puede comprobar por si mismo. Ni una mas: enumerar decisiones que no aplican es tan
#: falso como declarar que se respetan todas.
DECISIONES_DE_CODIGO_MUERTO = (
    "D22-materia-reservada",
    "D22-alcance-delegable",
    "separacion-de-planos",
    "gobernanza-intocable",
)


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
        # La **forma** del simbolo viaja con la tarea: sin ella el ejecutor solo sabria borrar
        # funciones, que es lo unico que sabia antes de completar la capacidad.
        "forma": oportunidad.detalle.get("forma", "funcion"),
        # La operacion constructiva y sus dos textos, cuando el contrato la declara. Por defecto no
        # viajan: una tarea de codigo muerto no tiene `buscar` ni `sustituir`, y el ejecutor usa su
        # operacion por defecto.
        "operacion": oportunidad.detalle.get("operacion", "eliminar_codigo_muerto"),
        "buscar": oportunidad.detalle.get("buscar"),
        "sustituir": oportunidad.detalle.get("sustituir"),
        # **La identidad del contrato que autoriza esta tarea** (CEO, 2026-09-20). `formacion` ya la
        # sabia —la guarda en `detalle["numero"]`— y aqui se perdia: la tarea seguia viaje sola y
        # nadie aguas abajo podia comprobar que se correspondiera con ninguna autorizacion.
        # `review.ejecutar_bajo_review` y `autoconstruccion.ejecutar` verifican zona, intocables,
        # alcance del verbo y unicidad del patron —todo correcto— y nada de eso ata la tarea al
        # contrato que la produjo.
        #
        # **Vacio cuando no hay contrato, nunca un relleno.** El codigo muerto no nace de un
        # contrato; declararle uno inventado seria peor que no declarar nada, porque aguas abajo
        # pareceria una autorizacion real. Es el mismo criterio que `detalle`: un campo rellenado
        # por obligacion no informa de nada.
        #
        # Esto solo TRANSPORTA el dato. Verificarlo antes de escribir es
        # `contrato.corresponde_tarea_a_contrato()`, y enchufarlo en la puerta de ejecucion es un
        # acto aparte: toca el circuito de escritura y no se hace de paso.
        "contrato": oportunidad.detalle.get("numero", ""),
        "objetivo": oportunidad.justificacion,
        "criterio_de_finalizacion": dict(oportunidad.criterio_de_finalizacion),
        "evidencia_requerida": dict(oportunidad.evidencia_requerida),
        "riesgo": oportunidad.riesgo,
        # `DR-F-3d-4` (`A3`). Antes viajaban aqui cinco **constantes literales** —`cambia_alcance:
        # False`, `respeta_decisiones: True`, `d21_afirmativas: True`...— y el revisor las leia como
        # si fueran comprobaciones: sobre cualquier tarea real el juicio salia `cumple: True`. No
        # eran criterios, eran una firma en blanco.
        #
        # Ya no hacen falta. `alcance` y `materia_reservada` los deriva el revisor de sus propias
        # fuentes (`TODO_LO_DELEGABLE`, `_MATERIA_RESERVADA`), y `D21` no se le exige a una tarea
        # tecnica acotada (`B2`). Lo unico que el proponente sigue aportando es lo que solo el sabe:
        # **que decisiones aplican a este cambio**, enumeradas, para que el revisor verifique las
        # que tengan fuente objetiva y marque el resto. Es el patron de `5.3:113`.
        "decisiones_aplicables": DECISIONES_DE_CODIGO_MUERTO,
    }


def ya_planificada(directorio, id_tarea: str) -> bool:
    return any(e["tipo"] == "tarea_planificada" and e["datos"].get("id") == id_tarea
               for e in cp.leer_eventos(pathlib.Path(directorio)))


class TareaNoElegible(RuntimeError):
    """Se intento dejar constancia de una tarea que ya no es elegible (en curso por otro, completada o agotada)."""


def _arranque() -> str:
    """Identidad del arranque de la maquina: tras un reinicio, ningun proceso anterior sigue vivo."""
    try:
        return pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


#: `_inicio_de` no puede saberlo (/proc ilegible: `hidepid`, otro espacio de nombres). Ante la duda, VIVO.
_DESCONOCIDO = "?"


def _pid_max() -> int:
    try:
        return int(pathlib.Path("/proc/sys/kernel/pid_max").read_text().strip())
    except (OSError, ValueError):
        return 2 ** 22  # el maximo que admite Linux en 64 bits (PID_MAX_LIMIT)


#: Se lee al importar. Si `pid_max` se sube en caliente, un pid legitimo por encima del valor leido se tomaria por
#: vivo: lado conservador (espera, no duplica) y se corrige al reiniciar el proceso (DP §10.3).
_PID_MAX = _pid_max()


def _existe(pid: int) -> bool:
    """`kill(pid, 0)`: solo `ESRCH` prueba que el proceso no existe; `EPERM` es que existe y es ajeno."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _inicio_de(pid: int) -> str | None:
    """starttime (campo 22 de `/proc/<pid>/stat`); None si el proceso NO existe o es zombi; `_DESCONOCIDO` si
    existe la duda (no se puede leer). Confundir «no puedo leer» con «murio» reabriria la ejecucion duplicada."""
    try:
        campos = pathlib.Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        estado, inicio = campos[0], campos[19]
    except (FileNotFoundError, ProcessLookupError):
        return None if not _existe(pid) else _DESCONOCIDO  # con `hidepid=2` un pid vivo tampoco aparece en /proc
    except (OSError, IndexError):
        return _DESCONOCIDO
    return None if estado == "Z" else inicio


def _identidad_del_ejecutor() -> dict | None:
    """pid + starttime + arranque: el pid SOLO no basta (se reutiliza) y el starttime solo no basta (se repite
    tras un reinicio). Los tres juntos identifican un proceso concreto de un arranque concreto."""
    inicio, arranque = _inicio_de(os.getpid()), _arranque()
    if not inicio or inicio == _DESCONOCIDO or not arranque:
        return None  # sin /proc fiable: mejor «historico» (conservador) que una identidad que atascaria la tarea
    return {"pid": os.getpid(), "inicio": inicio, "arranque": arranque}


def _ejecutor_vivo(ejecutor: dict) -> bool:
    """¿Sigue vivo EXACTAMENTE el proceso que dejo la constancia? Ante la duda (sin datos legibles), si."""
    try:
        pid, inicio, arranque = int(ejecutor["pid"]), str(ejecutor["inicio"]), str(ejecutor["arranque"])
    except (KeyError, TypeError, ValueError):
        return True
    if not arranque or not inicio:
        return True
    if not 0 < pid <= _PID_MAX:
        # Un pid fuera del rango del nucleo no identifica a ningun proceso (y `kill(0|-1, 0)` preguntaria por un
        # GRUPO). Dato malformado o forjado: ante la duda, vivo. Nunca tumba el ciclo ni duplica.
        return True
    if arranque != _arranque():
        return False
    actual = _inicio_de(pid)
    if actual == _DESCONOCIDO:
        return True
    return actual == inicio


def _ultima_planificada(directorio, id_tarea: str) -> dict | None:
    datos = None
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        if evento["tipo"] == "tarea_planificada" and evento["datos"].get("id") == id_tarea:
            datos = evento["datos"]
    return datos


def _cierre_sin_resultado(directorio, id_tarea: str) -> str | None:
    """¿El ultimo intento termino SIN `cambio_aplicado` por una decision del propio ciclo? Elevada a decision humana,
    esperando revisor u objetada: nada de eso es una interrupcion y la tarea NO se reofrece."""
    cierre = None
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        datos = evento.get("datos") or {}
        if datos.get("id") != id_tarea:
            continue
        if evento["tipo"] == "tarea_planificada":
            cierre = None
        elif evento["tipo"] == "decision_requerida":
            cierre = "elevada"
        elif evento["tipo"] == "revision_sin_revisor_capaz":
            cierre = "esperando_revisor"
        elif evento["tipo"] == "veredicto_emitido" and datos.get("cumple") is False:
            cierre = "objetada"
    return cierre


def registrar_planificada(directorio, tarea: dict) -> dict:
    """Deja constancia **antes** de ejecutar, y con su origen.

    Lo que se registra aqui es la intencion, no el resultado: marcar el resultado antes de tenerlo es
    el defecto que la 3.a auditoria encontro en `registrar_sesion`, y que quemaba toda tarea `AUTO`
    en su primer intento.

    **Con la identidad del ejecutor y comprobando bajo el cerrojo del log** (DP-RECUPERACION-TRAS-CAIDAS): una
    tarea interrumpida solo puede volver a planificarse si nadie la ha replanificado ya; dos supervisores que la
    vean interrumpida a la vez no pueden ejecutarla dos veces."""
    directorio = pathlib.Path(directorio)
    datos = {"id": tarea["id"], "origen": tarea["origen"], "accion": tarea["accion"],
             "fichero": tarea["fichero"], "riesgo": tarea["riesgo"]}
    ejecutor = _identidad_del_ejecutor()
    if ejecutor is not None:
        datos["ejecutor"] = ejecutor
    evento = cp.registrar_evento_si(directorio, "tarea_planificada", datos,
                                    lambda: elegible(directorio, tarea["id"]))
    if evento is None:
        raise TareaNoElegible(f"{tarea['id']}: {estado_de(directorio, tarea['id'])}")
    return evento


#: **El tope de intentos, y no es un numero inventado.** Sale del modelo que este plano ya tiene:
#: `agentes.ejecutar_tarea(..., max_intentos=2)`. Y su motivo esta escrito en `revisores.py:380` —
#: *«un reintento sin tope es un bucle, y el §14 no autoriza ninguno»*.
TOPE_DE_REINTENTOS = 2


def _cambios_atribuidos(directorio, id_tarea: str) -> tuple[list[int], list[tuple[int | None, int, dict]]]:
    """`(planificadas, cambios)`: los `seq` de las `tarea_planificada` de esa tarea y, por cada
    `cambio_aplicado` que le pertenece, `(intento, planificadas_hasta_entonces, datos)`.

    **La atribucion sale de la correlacion, no del orden** (DP-AUTOCONSTRUCCION I1):
    * `correlacion == "ninguna"` (un recuperado sin tarea/intento) -> tampoco, ni por orden.
    * `via == "ciclo"` -> JAMAS se atribuye a una tarea, ni por orden.
    * con `tarea`/`intento` -> es de esa tarea solo si coincide el id y `intento` es el `seq` de una de sus
      `tarea_planificada` ya vistas. Un par mal formado o ajeno no se atribuye (ni por orden).
    * sin ninguno de los dos (evento anterior al contrato) -> por orden: el de la ultima planificada."""
    planificadas: list[int] = []
    cambios: list[tuple[int | None, int, dict]] = []
    mio = False
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        datos = evento.get("datos") or {}
        if evento["tipo"] == "tarea_planificada":
            mio = datos.get("id") == id_tarea
            if mio:
                planificadas.append(evento["seq"])
        elif evento["tipo"] == "cambio_aplicado":
            if datos.get("via") == "ciclo" or datos.get("correlacion") == "ninguna":
                continue
            if "tarea" in datos or "intento" in datos:
                intento = datos.get("intento")
                if (datos.get("tarea") == id_tarea and isinstance(intento, int)
                        and not isinstance(intento, bool) and intento in planificadas):
                    cambios.append((intento, len(planificadas), datos))
            elif mio:
                cambios.append((None, len(planificadas), datos))
    return planificadas, cambios


def resultado_de(directorio, id_tarea: str) -> dict | None:
    """El resultado del ultimo intento de esa tarea, o `None` si aun no lo hay.

    Un `cambio_aplicado` con `(tarea, intento)` se atribuye a ese intento; solo los eventos anteriores al
    contrato (sin esos campos) se enlazan por el orden del historial (`ADR-0023`: secuencial y append-only)."""
    planificadas, cambios = _cambios_atribuidos(directorio, id_tarea)
    if not planificadas:
        return None
    resultado = None
    for intento, posicion, datos in cambios:
        if intento == planificadas[-1] or (intento is None and posicion == len(planificadas)):
            resultado = datos
    return resultado


def intentos_de(directorio, id_tarea: str) -> int:
    """Cuantas veces se planifico. La constancia se deja **antes** de ejecutar, asi que esto cuenta
    intentos empezados, que es lo que un presupuesto acotado tiene que contar."""
    return sum(1 for e in cp.leer_eventos(pathlib.Path(directorio))
               if e["tipo"] == "tarea_planificada" and e["datos"].get("id") == id_tarea)


def completada(directorio, id_tarea: str) -> bool:
    """**`tarea_planificada` no es `tarea_completada`.** Completada es haber dejado efecto: un
    intento revertido no cambio nada, y tratarlo como terminado quema trabajo que nunca se hizo.

    **Las tres condiciones, explicitas.** Hoy `ejecutar()` deriva `revertido = not (efecto and sano)`,
    asi que mirar solo `revertido` bastaria; escribirlas las tres es lo que impide que un cambio en
    esa derivacion abra una puerta aqui sin que nadie se entere. Y un evento sin los campos no
    concede: la duda nunca completa."""
    return any(_dejo_efecto(r) for r in _resultados_de(directorio, id_tarea))


def _dejo_efecto(resultado: dict) -> bool:
    return (resultado.get("efecto_verificado") is True
            and resultado.get("verificacion_sana") is True
            and resultado.get("revertido") is False)


def _resultados_de(directorio, id_tarea: str) -> list[dict]:
    """Los resultados de TODOS los intentos. **Completada es monotona**: un efecto verificado no se deshace porque un
    log heredado replanificase la tarea despues (lo que `registrar_planificada` ya no permite)."""
    return [datos for _i, _p, datos in _cambios_atribuidos(directorio, id_tarea)[1]]


def estado_de(directorio, id_tarea: str) -> str:
    """El estado OBSERVABLE de una tarea (DP-RECUPERACION-TRAS-CAIDAS §2), **solo desde el log**. Once respuestas:

    nunca · en_curso (ejecutor vivo) · completada (algun intento dejo efecto; monotona) · revertida_reintentable ·
    interrumpida_reintentable (ejecutor muerto, otro arranque o pid reutilizado) · agotada (sin presupuesto) ·
    elevada · esperando_revisor · objetada (el intento cerro SIN resultado por una decision del ciclo) ·
    sin_resultado_historico (constancia anterior al contrato, sin `ejecutor`) · resultado_ambiguo (ni completada ni
    revertida). Solo `nunca` y los dos `*_reintentable` conceden."""
    intentos = intentos_de(directorio, id_tarea)
    if intentos == 0:
        return "nunca"
    if completada(directorio, id_tarea):
        return "completada"
    resultado = resultado_de(directorio, id_tarea)
    if resultado is not None:
        if not resultado.get("revertido", False):
            return "resultado_ambiguo"  # ni completada ni revertida: ante la duda, no
        return "revertida_reintentable" if intentos < TOPE_DE_REINTENTOS else "agotada"
    cierre = _cierre_sin_resultado(directorio, id_tarea)
    if cierre is not None:
        return cierre
    ejecutor = (_ultima_planificada(directorio, id_tarea) or {}).get("ejecutor")
    if ejecutor is None:
        return "sin_resultado_historico"
    if _ejecutor_vivo(ejecutor):
        return "en_curso"
    return "interrumpida_reintentable" if intentos < TOPE_DE_REINTENTOS else "agotada"


def elegible(directorio, id_tarea: str) -> bool:
    """Si la tarea puede entrar en la cola. **Ante la duda, no.**

    Concede solo `nunca` y los dos `*_reintentable` de `estado_de`: planificada y sin resultado con el ejecutor
    VIVO (o sin poder saberlo) -> no, porque duplicarla es el defecto que `registrar_planificada` existe para
    evitar; revertida o interrumpida -> si, **mientras quede presupuesto**.

    Una reversion no es un permiso permanente: es el resto de un presupuesto acotado. Agotado, la
    tarea se apaga y hace falta evidencia nueva —otra oportunidad, con otra identidad— para volver."""
    return estado_de(directorio, id_tarea) in ("nunca", "revertida_reintentable", "interrumpida_reintentable")


def cola(directorio, oportunidades) -> list[dict]:
    """Las tareas ejecutables **elegibles**, en orden de riesgo. La regla de elegibilidad vive en
    `elegible()` y solo alli: tenerla aqui tambien seria la copia que este proyecto ya ha pagado."""
    ordenadas = sorted((o for o in oportunidades if o.estado == des.OPORTUNIDAD_REAL), key=_peso)
    tareas = []
    vistos = set()
    for oportunidad in ordenadas:
        tarea = a_tarea(oportunidad)
        if tarea is None or tarea["id"] in vistos or not elegible(directorio, tarea["id"]):
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


__all__ = ["a_tarea", "cola", "siguiente", "id_de_tarea", "ya_planificada", "elegible",
           "resultado_de", "intentos_de", "completada", "TOPE_DE_REINTENTOS",
           "registrar_planificada", "informe_de_cola"]
