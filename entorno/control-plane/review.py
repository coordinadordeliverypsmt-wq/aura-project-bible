"""Nivel `REVIEW` — `D-ORCH-2`. **Construido y apagado.**

## Por que existe apagado

`ADR-0003:33`: *«los niveles superiores de autonomia solo se habilitan por politica y **decision del
usuario/CEO, nunca automaticamente**»*. Un modulo que naciera encendido se estaria concediendo el
nivel a si mismo, que es exactamente lo que esa frase prohibe.

`REVIEW_HABILITADO` es `False`. Solo un acta del CEO, registrada en el log, lo enciende — y con
**alcance cerrado**: el acta dice *que acciones* cubre, no es un cheque en blanco.

## Que instrumenta, y por que eso no es autoridad nueva

Los criterios ya existen. `D22` delego en el **CTO —que es Fable, una IA** (`1.1:94`)— la aprobacion
de capitulos de ejecucion con cuatro comprobaciones: *«sin cambio de alcance, respeto de decisiones
previas, cinco preguntas D21»* y materia no reservada. Este modulo las **aplica**, no las inventa.

*(Nota de correccion: el `DP §10.3` afirma que «D22 delego en un **CTO humano**». Es falso y esta
verificado: el titular del rol CTO es Fable (IA), y ya aprobo capitulos por delegacion D22 —vease la
firma de `5.1`, `5.2`, `5.3`, `5.5` y `5.6`—. Delegar en un agente no es inedito en este proyecto.)*

## Lo que `REVIEW` NO cambia

- **La autoridad final del CEO sigue sin ser delegable** (`1.1:93`). `REVIEW` permite *ejecutar
  dentro de un alcance ya autorizado*; no convierte un veredicto en permiso.
- **«No aprueba su propio trabajo»** (`1.1:94`): el que propone **no** revisa. Sin eso, `REVIEW`
  seria un sello que el proponente se pone a si mismo.
- **Materia reservada al CEO** —tecnologia con alternativas (D3), guardrails eticos, rango 1 y
  Alertas de Arquitectura— no pasa por aqui **ni con el nivel encendido**.
- La gobernanza sigue intocable y el cambio sigue siendo **reversible**.

## Deuda declarada · **dos contratos de `Veredicto`** para lo mismo

`autoconstruccion.Veredicto` tiene tres campos; `revisores.Veredicto`, cinco, y es el que `§8.2`
define **literalmente**. Este modulo usa el primero y `revisores.py` el segundo, asi que hay dos
interpretaciones del mismo hecho — y `INV-7` dice que *«el plan se interpreta en un solo punto y
nunca se reinterpreta»*.

**No se unifica aqui, y el motivo es de riesgo, no de pereza:** este es el circuito que el CEO
aprobo con `DEC-ORCH-2` y vio funcionar encadenando tareas. Cambiarle el contrato al revisor para
quitar una duplicacion seria arriesgar lo que ya opera por arreglar lo que solo molesta.

**Condicion que la promueve a deuda bloqueante:** el dia que una tarea `REVIEW` necesite algo que
solo el contrato de cinco campos ofrece —evidencia citada obligatoria, o los cuatro veredictos de
`§8.2` en vez de «con objeciones / sin objeciones»—, unificar deja de ser opcional.

Lo que si se ha cableado, porque es seguridad y no comodidad: **la degradacion del `§8.3`**. Antes,
este modulo fabricaba un veredicto sin comprobar que existiera un revisor capaz.
"""

from __future__ import annotations

import pathlib

import control_plane as cp

import autoconstruccion as ac

# **La puerta.** Constante y en False: encenderla exige un acta, no una edicion de codigo.
REVIEW_HABILITADO = False

# Los cuatro de `D22`, en el orden en que el propio acta los enumera.
CRITERIOS_D22 = ("alcance", "consistencia", "cinco_preguntas_d21", "materia_reservada")

# Reservado al CEO por `D22`. No delegable ni con `REVIEW` habilitado.
_MATERIA_RESERVADA = (
    "modificar_adr", "modificar_bible", "modificar_d24", "modificar_roadmap",
    "alerta_de_arquitectura", "seleccionar_tecnologia", "guardrail_etico",
    "decision_rango_1", "promover_propuesta", "crear_autoridad",
)

# Lo maximo que un acta podria delegar: acciones tecnicas, reversibles y del plano de desarrollo.
TODO_LO_DELEGABLE = ("eliminar_codigo_muerto",)

REVISORES = ac.REVISORES


class ReviewNoHabilitado(RuntimeError):
    """`REVIEW` no esta encendido, o se intento encenderlo sin acta humana."""


class MateriaReservada(RuntimeError):
    """La accion esta reservada al CEO por `D22`. No pasa por `REVIEW`."""


class RevisorNoIndependiente(RuntimeError):
    """El proponente intento revisarse. `1.1:94`: «No aprueba su propio trabajo»."""


# ------------------------------------------------------------------- la puerta --

def habilitar(directorio, por: str, acta: str, alcance: tuple[str, ...]) -> dict:
    """Enciende `REVIEW` **para este trabajo**, con alcance cerrado y acta registrada."""
    if por not in ac.AUTORIDADES_HUMANAS:
        raise ReviewNoHabilitado(
            f"{por!r} no es autoridad humana: elevar el nivel de autonomia es «decision del "
            f"usuario/CEO, nunca automaticamente» (ADR-0003:33)")
    if not (acta or "").strip():
        raise ReviewNoHabilitado("habilitar REVIEW exige acta: sin constancia no es una decision")
    fuera = [a for a in alcance if es_materia_reservada(a)]
    if fuera:
        raise MateriaReservada(f"el alcance incluye materia reservada al CEO por D22: {fuera}")
    registro = {"por": por, "acta": acta, "alcance": list(alcance)}
    cp.registrar_evento(pathlib.Path(directorio), "review_habilitado", registro)
    return {**registro, "alcance": tuple(alcance)}


def habilitado(directorio=None) -> bool:
    """Global apagado **y** sin acta en este trabajo = apagado. Ambas cosas, no una."""
    if REVIEW_HABILITADO:
        return True
    if directorio is None:
        return False
    return any(e["tipo"] == "review_habilitado"
               for e in cp.leer_eventos(pathlib.Path(directorio)))


def alcance_actual(directorio) -> tuple[str, ...]:
    """El alcance que el acta habilito, en publico.

    Existia solo como `_alcance`, privada, y quien quisiera **informar** de lo que hay habilitado
    tenia que llamar a una privada o volver a leer los eventos. Un dato que hay que rodear una
    barrera para consultar acaba consultandose por otro sitio."""
    return _alcance(directorio)


def _alcance(directorio) -> tuple[str, ...]:
    for evento in reversed(cp.leer_eventos(pathlib.Path(directorio))):
        if evento["tipo"] == "review_habilitado":
            return tuple(evento["datos"].get("alcance", ()))
    return ()


def en_alcance(directorio, accion: str) -> bool:
    return accion in _alcance(directorio) and not es_materia_reservada(accion)


def es_materia_reservada(accion: str) -> bool:
    return accion in _MATERIA_RESERVADA


# ------------------------------------------------- los criterios de D22, aplicados --

def aplicar_criterios(tarea: dict) -> dict:
    """Los cuatro se comprueban. Basta que uno falle para que no cumpla, y el juicio **dice cual**:
    un rechazo sin motivo no es revisable."""
    fallos = []
    if tarea.get("cambia_alcance"):
        fallos.append("alcance")
    if not tarea.get("respeta_decisiones"):
        fallos.append("consistencia")
    if not tarea.get("d21_afirmativas"):
        fallos.append("cinco_preguntas_d21")
    if tarea.get("materia_reservada") or es_materia_reservada(tarea.get("accion", "")):
        fallos.append("materia_reservada")
    return {"cumple": not fallos, "fallos": tuple(fallos), "criterios": CRITERIOS_D22}


def revisores_capaces() -> tuple[str, ...]:
    """Los revisores que **hoy** pueden revisar, medido y no declarado (`§8.1`).

    Un revisor es capaz si su ficha existe, igual que en F4 (`revisores.RevisorSubagente`). Antes
    este modulo no lo preguntaba: construia el veredicto y seguia, asi que el dia que no hubiese
    ninguno habria ejecutado igual — que es exactamente lo que `§8.3` prohibe."""
    return tuple(n for n in REVISORES if (ac.RAIZ_AGENTES / f"{n}.md").exists())


def pedir_veredicto(directorio, tarea: dict, propuesto_por: str, revisor: str) -> ac.Veredicto:
    """Pide revision a un agente **distinto del proponente**."""
    if revisor == propuesto_por:
        raise RevisorNoIndependiente(
            f"{revisor!r} propuso el cambio y no puede revisarlo: «No aprueba su propio trabajo» "
            f"(1.1:94). Un revisor que es el proponente es un sello, no una revision")
    juicio = aplicar_criterios(tarea)
    veredicto = ac.Veredicto(
        revisor=revisor,
        objeciones=tuple(f"incumple {f} (D22)" for f in juicio["fallos"]),
        resumen="sin objeciones" if juicio["cumple"] else f"objeciones: {juicio['fallos']}")
    cp.registrar_evento(pathlib.Path(directorio), "veredicto_emitido",
                        {"id": tarea.get("id"), "revisor": revisor, "propuesto_por": propuesto_por,
                         "objeciones": list(veredicto.objeciones), "cumple": juicio["cumple"]})
    return veredicto


def permite_seguir(veredicto) -> bool:
    """Un veredicto **sin objeciones** deja seguir. Sigue sin autorizar nada: `ac.autoriza()` es
    constante a False, y eso no cambia aqui. El silencio tampoco habilita (`1.1:85`)."""
    return veredicto is not None and not veredicto.objeciones


# ------------------------------------------------------------------ el circuito --

def ejecutar_bajo_review(directorio, tarea: dict, propuesto_por: str, autoridad: str,
                         verificacion=None, revisor: str | None = None) -> dict:
    """`clasificar → revisar → ejecutar → verificar → registrar`, con cuatro puertas antes de tocar
    nada: materia reservada, nivel habilitado, alcance del acta y veredicto sin objeciones."""
    directorio = pathlib.Path(directorio)
    accion = tarea.get("accion", "")

    if es_materia_reservada(accion):
        raise MateriaReservada(
            f"{accion!r} esta reservada al CEO por D22 y no pasa por REVIEW ni habilitado")
    if not habilitado(directorio):
        raise ReviewNoHabilitado(
            "REVIEW no esta habilitado: elevarlo exige un acta del CEO (ADR-0003:33). "
            "Mientras tanto, cada cambio necesita autorizacion individual")
    if not en_alcance(directorio, accion):
        raise ReviewNoHabilitado(
            f"{accion!r} esta fuera del alcance que el acta habilito {_alcance(directorio)}: "
            f"habilitar REVIEW no es un cheque en blanco")

    # `§8.3` · **degradacion**, cableada a la ruta real tras la 3.a auditoria independiente:
    # *«si no hay revisor disponible, la tarea que exige revision pasa a WAITING_FOR_REVIEW y
    # espera. No se autoaprueba jamas»*. Sin esta comprobacion, la ausencia de revisor no detenia
    # nada porque el veredicto se fabricaba de todos modos.
    capaces = [r for r in revisores_capaces() if r != propuesto_por]
    if not capaces:
        cp.registrar_evento(directorio, "revision_sin_revisor_capaz",
                            {"id": tarea.get("id"), "accion": accion, "propuesto_por": propuesto_por})
        return {"ejecutado": False, "revisor": None, "objeciones": [],
                "efecto_verificado": False, "revertido": False, "estado": cp.ESTADO_REVISION}
    if revisor is not None and revisor not in capaces:
        # Nombrar al revisor estaba permitido y no se comprobaba que existiera: se podia emitir un
        # veredicto en nombre de alguien sin ficha. No es alcanzable desde el ciclo real —nunca pasa
        # `revisor=`—, pero un contrato publico que acepta un revisor fabricado es uno que alguien
        # usara mal. Lo encontro la 4.a auditoria.
        raise RevisorNoIndependiente(
            f"{revisor!r} no es un revisor capaz: los que hoy pueden revisar son {capaces}. "
            f"Un veredicto en nombre de quien no existe es un sello, no una revision")
    revisor = revisor or next(r for r in capaces)
    veredicto = pedir_veredicto(directorio, tarea, propuesto_por=propuesto_por, revisor=revisor)
    if not permite_seguir(veredicto):
        return {"ejecutado": False, "revisor": revisor, "objeciones": list(veredicto.objeciones),
                "efecto_verificado": False, "revertido": False}

    # La ejecucion reutiliza la maquinaria ya probada: misma reversibilidad, misma verificacion de
    # efecto releyendo el fichero, mismas zonas prohibidas.
    propuesta = ac.proponer(directorio, {"simbolo": tarea["simbolo"], "fichero": tarea["fichero"],
                                         "motivo": f"{accion} bajo REVIEW"})
    cp.registrar_evento(directorio, "propuesta_autorizada",
                        {"id": propuesta["id"], "autorizada_por": f"REVIEW:{revisor}",
                         "acta": f"alcance habilitado por acta del CEO; veredicto de {revisor}"})
    resultado = ac.ejecutar(directorio, propuesta, autoridad=autoridad, verificacion=verificacion)
    return {"ejecutado": not resultado["revertido"], "revisor": revisor, "objeciones": [],
            "efecto_verificado": resultado["efecto_verificado"],
            "revertido": resultado["revertido"], "propuesta": propuesta["id"]}
