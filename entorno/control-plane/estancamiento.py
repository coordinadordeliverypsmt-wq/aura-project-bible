"""Sexta fuente de descubrimiento — deteccion de **ESTANCAMIENTO/FRICCION**.

DP-SELF-EVOLUTION-01 · **Fase A** (aprobada por el CEO). La Fase B —registrar los `id` de las
oportunidades en el log para excluir la propia con precision— **no** fue aprobada, y este modulo no
la asume.

## Que cierra

Hasta hoy AURA solo descubria trabajo (codigo muerto) o releia listas que un humano escribio en
`estado.json`. No tenia forma de observar una **carencia propia**: que el ciclo lleva N vueltas sin
avanzar con trabajo bloqueado sin resolver. Esta fuente convierte ese hecho —ya presente en el
historial— en una **pregunta para el CEO**, sin conceder a AURA ningun apice de autoridad nueva.

## Lo que esta fuente NO hace

**No ejecuta, no autoriza, no escribe.** Es estrictamente de solo lectura: lee el historial a traves
de `observatorio.ciclos` (que no escribe) y **no registra ningun evento** — eso lo hace `descubrir()`
al final, como con cualquier otra fuente. Genera como mucho **una** oportunidad, y siempre
`DECISION_REQUIRED`: nunca `OPORTUNIDAD_REAL`, asi que `planificador.a_tarea` la devuelve como `None`
y jamas puede convertirse en tarea.

## La frontera de la autoevolucion

La fuente detecta la **necesidad**; la **evolucion** —incorporar una capacidad, ampliar un alcance—
la decide el humano por acta. Elevar no es resolver: AURA plantea «esto lleva estancado, ¿merece una
decision?», nunca «he decidido cambiar esto». El roadmap sigue siendo del CEO (ADR-0003, D22, D23,
1.1:93).

## Por que es INERTE hasta que el acta fije K

`K` —cuantas vueltas consecutivas sin progreso cuentan como estancamiento— es una decision, no una
constante tecnica: publicar un numero arquitectonico sin derivarlo del modelo ni de un acta esta
prohibido (CEO, 2026-08-04). Por eso `K_ESTANCAMIENTO` es `None`: su **ausencia declarada**, no un
valor escondido. Mientras sea `None` la fuente no eleva nada — construida pero apagada, igual que
`REVIEW_HABILITADO=False` deja `REVIEW` construido y a la espera de un acta.

## Auto-exclusion

La propia elevacion de esta fuente reaparece en los recuentos del historial de vueltas posteriores.
Sin cuidado, se detectaria a si misma y sostendria el estancamiento para siempre. En Fase A el log
guarda **recuentos, no ids**, asi que la exclusion es conservadora: del backlog de cada vuelta se
descuenta como mucho `_APORTE_PROPIO_MAXIMO` elevacion —lo maximo que esta fuente puede haber
aportado—. Si lo unico que quedaba era su propia elevacion, el backlog ajeno es `0` y no hay
estancamiento.
"""
from __future__ import annotations

import pathlib

import observatorio as obs

#: Umbral de estancamiento. `None` = **sin fijar**: la fuente es inerte (no eleva nada). Su valor
#: contractual lo fija el acta del CEO; NO es un numero arbitrario escondido en codigo.
K_ESTANCAMIENTO = 100

#: Cuantas oportunidades emite esta fuente como maximo: **una**, la de la racha vigente. Es una
#: propiedad demostrada (una prueba la fija), no una conjetura, y de ella depende la auto-exclusion.
_APORTE_PROPIO_MAXIMO = 1

#: Accion informativa. No es ejecutable —el estado es `DECISION_REQUIRED`—; nombra el resultado, no
#: una herramienta.
ACCION = "revisar_estancamiento"

#: Mecanismo declarado y verificable (`hasattr(control_plane, 'leer_eventos')`) que sirve de
#: procedencia: la senal sale de leer el historial, y ahi se puede ir a mirar.
_FUENTE = "control_plane.leer_eventos"


def _sin_progreso(ciclo: dict) -> bool:
    """Progreso = el predicado que **ya existe**. `observatorio` cuenta por ciclo los efectos reales
    (`efecto_verificado ∧ verificacion_sana ∧ ¬revertido`); se reutiliza para no crear una segunda
    definicion de «progreso» (INV-7)."""
    return (ciclo.get("efecto_real") or 0) == 0


def _backlog_ajeno(ciclo: dict) -> int:
    """Trabajo bloqueado/elevado que **no** proviene de esta fuente.

    Se descuenta como mucho `_APORTE_PROPIO_MAXIMO` de las elevadas: es lo maximo que esta fuente pudo
    aportar a esa vuelta. Asi, una elevacion propia recurrente no puede, por si sola, sostener el
    estancamiento."""
    por_clase = ciclo.get("por_clase")
    if not isinstance(por_clase, dict):
        return 0
    bloqueadas = por_clase.get("BLOQUEADA") or 0
    elevadas = por_clase.get("DECISION_REQUIRED") or 0
    return bloqueadas + max(0, elevadas - _APORTE_PROPIO_MAXIMO)


def _sin_trabajo_real(ciclo: dict) -> bool:
    """Sin `OPORTUNIDAD_REAL`: si la hubiera, el motor la ejecutaria y no habria estancamiento."""
    por_clase = ciclo.get("por_clase")
    reales = por_clase.get("OPORTUNIDAD_REAL") if isinstance(por_clase, dict) else 0
    return (reales or 0) == 0


def _es_estancado(ciclo: dict) -> bool:
    """Un ciclo **cerrado** cuenta para la racha si: se descubrio algo, hay backlog ajeno, no hubo
    trabajo real y no hubo progreso. El ocio sano —`descubiertas=0` o backlog `0`— no cuenta."""
    if ciclo.get("abierto"):
        return False
    descubiertas = ciclo.get("descubiertas")
    if not isinstance(descubiertas, int) or descubiertas <= 0:
        return False
    return _backlog_ajeno(ciclo) > 0 and _sin_trabajo_real(ciclo) and _sin_progreso(ciclo)


def _racha_de_estancamiento(ciclos: list) -> list:
    """La racha de ciclos estancados **consecutivos** que termina en el mas reciente. Un ciclo aun
    abierto no decide; un ciclo con progreso o de ocio sano **rompe** la racha."""
    racha = []
    for ciclo in reversed(ciclos):
        if ciclo.get("abierto"):
            continue
        if _es_estancado(ciclo):
            racha.append(ciclo)
        else:
            break
    return list(reversed(racha))


def hay_estancamiento(ciclos: list, k) -> bool:
    """`k` ciclos consecutivos estancados. `k` es **obligatorio y sin valor por defecto**: cuanto es
    «demasiado» es una decision del acta, no una constante de este codigo. `k=None` = inerte."""
    if k is None:
        return False
    return len(_racha_de_estancamiento(ciclos)) >= k


def estancamiento(_raiz, directorio, k=K_ESTANCAMIENTO) -> list:
    """La fuente. **Solo lectura.** Devuelve como mucho una `DECISION_REQUIRED`, o `[]` si no hay
    estancamiento o si `K` no esta fijado (inerte, fail-closed).

    `_raiz` no se usa: el estancamiento se lee del historial, no del arbol de ficheros. Se acepta para
    respetar la firma que `descubrir()` invoca en toda fuente `(raiz, directorio)`."""
    directorio = pathlib.Path(directorio)
    ciclos = obs.ciclos(directorio)
    if not hay_estancamiento(ciclos, k):
        return []
    racha = _racha_de_estancamiento(ciclos)
    primero = racha[0]
    inicio = primero.get("inicio")
    if inicio in (None, obs.NO_DISPONIBLE):
        # Sin ancla temporal estable no se puede dar un id estable: no se eleva (fail-closed) en vez
        # de emitir un id que cambiaria en cada vuelta y romperia la anti-duplicacion.
        return []

    # Perezoso a proposito: `descubrimiento` importa este modulo para su dict `FUENTES`, asi que
    # importarlo aqui arriba cerraria el ciclo. Es el mismo patron con que `observatorio` importa
    # `aura`. En tiempo de ejecucion `descubrimiento` ya esta cargado.
    import descubrimiento as des

    por_clase = primero.get("por_clase") if isinstance(primero.get("por_clase"), dict) else {}
    #: La identidad de la racha es **donde empezo**, no cuanto lleva ni el seq actual: asi la misma
    #: racha conserva su id aunque se alargue vuelta tras vuelta.
    firma = f"desde:{inicio}"
    oportunidad = des.Oportunidad(
        id=des._id_de(_FUENTE, "estancamiento", ACCION, firma),
        fuente=_FUENTE,
        justificacion=(
            f"el ciclo autonomo lleva {len(racha)} vueltas consecutivas sin progreso con trabajo "
            f"bloqueado/elevado sin resolver desde {inicio}: puede ser una carencia de capacidad "
            f"que solo un acta del CEO desbloquea"),
        alcance="ciclo_autonomo",
        accion=ACCION,
        autoridad="CEO",
        criterio_de_finalizacion={"capacidad": "diagnosticar_estado"},
        evidencia_requerida={"tipo": "salida_contiene", "patron": firma},
        riesgo="ninguno: no se ejecuta",
        estado=des.DECISION_REQUIRED,
        detalle={"ciclos_sin_progreso": len(racha), "desde": inicio,
                 "por_clase": dict(por_clase), "k": k})
    return [oportunidad]


__all__ = ["estancamiento", "hay_estancamiento", "K_ESTANCAMIENTO", "ACCION"]
