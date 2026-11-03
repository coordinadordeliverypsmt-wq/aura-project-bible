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
#
# **`implementar_incremento_especificado` NO es «programar libremente».** Es construir un incremento
# que YA esta especificado y aprobado, dentro de un perimetro explicito. Entra aqui porque es lo
# maximo que un acta *podria* delegar; **no** porque este delegado: el acta vigente (`DEC-ORCH-2`)
# delega exactamente `("eliminar_codigo_muerto",)`, asi que `en_alcance()` lo niega y `clasificar()`
# lo manda a `HUMAN`. Mismo patron que `REVIEW_HABILITADO=False` y `K_ESTANCAMIENTO=None`:
# construido, declarado y **a la espera de un acta** — nunca encendido por edicion de codigo.
#
# **`implementar_incremento_especificado` entra aqui por el acta del CEO de `DR-D` (2026-09-07)**, no
# por una edicion de conveniencia: hasta que existio esa decision humana el verbo vivia declarado y
# fuera de la lista blanca. Entrar en ella no lo hace ejecutable por si solo —siguen mandando el acta
# registrada (`en_alcance`), el ejecutor construido y el contrato de la capacidad—: solo levanta el
# techo de lo que un acta *puede* delegar hasta donde el CEO ya lo ha delegado.
TODO_LO_DELEGABLE = ("eliminar_codigo_muerto", "implementar_incremento_especificado")

#: **El verbo de la evolucion, DECLARADO y NO DELEGADO.** Construir una capacidad ya especificada y
#: aprobada, dentro de un perimetro explicito. No significa «programar libremente».
#:
#: **No esta en `TODO_LO_DELEGABLE` a proposito.** Esa tupla es la lista BLANCA que la garantia `A10`
#: fija, y es «lo maximo que un acta podria delegar»: meterlo ahi editando codigo agrandaria el techo
#: de la autonomia sin acta, que es exactamente lo que este modulo dice que no puede pasar —*«la
#: puerta: constante y en False; encenderla exige un acta, no una edicion de codigo»*—. Entrar en la
#: lista blanca es un acto del CEO, igual que `REVIEW_HABILITADO` y que el alcance de `DEC-ORCH-2`.
#:
#: Mientras tanto queda aqui: nombrado, contratado y verificable, sin conceder nada. `clasificar()`
#: lo manda a `HUMAN` por dos vias independientes —no esta en la lista blanca y no esta en el acta—.
ACCION_DE_EVOLUCION = "implementar_incremento_especificado"

#: Las acciones para las que existe un ejecutor **de verdad**. `INV-9`: no se finge capacidad no
#: construida. Es la tercera barrera del verbo de evolucion, independiente de las otras dos: aunque
#: un dia un acta lo metiera en la lista blanca y en el alcance, seguiria sin ejecutor y el circuito
#: se negaria en vez de mandarlo al ejecutor de codigo muerto —que espera `simbolo` y `fichero`— a
#: hacer algo que nadie diseno.
_EJECUTORES_CONSTRUIDOS = ("eliminar_codigo_muerto", "implementar_incremento_especificado")

REVISORES = ac.REVISORES


class SinEjecutor(RuntimeError):
    """La accion esta declarada como delegable pero **no existe ejecutor construido** (`INV-9`)."""


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


# ------------------------------------- A3 · las decisiones aplicables, enumeradas --
#
# `DR-F-3d-3` demostro que **no existe** fuente de verdad para *«respeta todas las decisiones
# previas»*: `adr/` y `decisiones/` solo aparecen en el codigo como zona prohibida de escritura, no
# hay indice consultable, y los *«principios»* que `D22` menciona no estan enumerados en ninguna
# parte. El CEO aprobo `A3`: quien propone **enumera que decisiones aplican a este cambio**, como
# hizo el CTO en `5.3:113` acreditando consistencia contra *«ADR-0001/0004, guardrails de 2.4,
# permisos D4/D9 y P-ARQ»* — una lista concreta, no el universo entero.
#
# Aqui no se interpreta ningun Markdown. Una decision se **verifica** solo si ya existe una funcion
# que la comprueba; si existe como documento pero es prosa, se **marca**; y si no existe, **falla**:
# citar una autoridad inexistente es peor que no citar ninguna.

VERIFICADO = "VERIFICADO"
INCUMPLIDA = "INCUMPLIDA"
#: Mismo literal que `propuesta.REQUIERE_REVISION_HUMANA` (`DR-E`): un solo vocabulario para «esto
#: no lo decide una maquina».
REQUIERE_REVISION_HUMANA = "REQUIERE_REVISION_HUMANA"
NO_APLICA = "NO_APLICA"

#: La raiz del repositorio, para comprobar que una decision citada **existe** de verdad.
RAIZ_GOBERNANZA = pathlib.Path(__file__).resolve().parents[2]

#: Las decisiones que **ya** tienen una comprobacion ejecutable. Ninguna es nueva: todas estaban
#: codificadas antes de `DR-F-3d-4`, solo que nadie podia nombrarlas al pedir una revision.
_COMPROBACIONES = {
    "D22-materia-reservada":
        lambda t: not es_materia_reservada(t.get("accion", "")),
    "D22-alcance-delegable":
        lambda t: t.get("accion", "") in TODO_LO_DELEGABLE,
    "ADR-0003-review-no-habilitado":
        lambda _t: REVIEW_HABILITADO is False,
    "separacion-de-planos":
        lambda t: not (set(pathlib.Path(t.get("fichero", "")).parts) & ac._DIRS_PRODUCTO),
    "gobernanza-intocable":
        lambda t: not (set(pathlib.Path(t.get("fichero", "")).parts) & ac._DIRS_GOBERNANZA),
}


def _documento_existe(nombre: str, raiz) -> bool:
    """Si la decision citada **esta** en el repositorio. Solo lectura, y sin interpretar el texto.

    Dos formas, las dos que el proyecto usa: `ADR-00NN` es un fichero de `adr/`, y `D<n>` es un
    epigrafe `## D<n>` dentro de un acta. Nombrar algo que no esta en ninguna de las dos no es una
    decision: es una cita inventada."""
    raiz = pathlib.Path(raiz)
    nombre = nombre.strip()
    if nombre.upper().startswith("ADR-"):
        numero = nombre[4:].split("-")[0]
        return any((raiz / "adr").glob(f"{numero}-*.md"))
    if len(nombre) > 1 and nombre[0].upper() == "D" and nombre[1:].isdigit():
        cabecera = f"## {nombre.upper()} "
        for acta in (raiz / "decisiones").glob("*.md"):
            try:
                if cabecera in acta.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    return False


def evaluar_decisiones(decisiones, tarea: dict, *, raiz=None) -> dict:
    """Cada decision citada, con su estado. **Fail-closed por defecto.**

    `VERIFICADO`/`INCUMPLIDA` cuando hay funcion que lo comprueba · `REQUIERE_REVISION_HUMANA`
    cuando el documento existe pero es prosa · `INCUMPLIDA` cuando la referencia no lleva a ningun
    sitio. Una decision verificada **no legitima** a las demas: se evaluan una por una."""
    raiz = RAIZ_GOBERNANZA if raiz is None else raiz
    resultado = {}
    for nombre in decisiones or ():
        if not isinstance(nombre, str) or not nombre.strip():
            continue
        comprobacion = _COMPROBACIONES.get(nombre)
        if comprobacion is not None:
            try:
                resultado[nombre] = VERIFICADO if comprobacion(tarea) else INCUMPLIDA
            except Exception:            # noqa: BLE001 — una comprobacion que revienta no aprueba
                resultado[nombre] = INCUMPLIDA
        elif _documento_existe(nombre, raiz):
            resultado[nombre] = REQUIERE_REVISION_HUMANA
        else:
            resultado[nombre] = INCUMPLIDA
    return resultado


def es_tarea_tecnica_acotada(tarea: dict, *, directorio=None) -> bool:
    """`B2`. **True solo si puede demostrarse**; lo que no se demuestra acotado, no lo es.

    La fuente no se inventa: `TODO_LO_DELEGABLE` esta definido en este mismo modulo como *«acciones
    tecnicas, reversibles y del plano de desarrollo»*, que son exactamente las tres propiedades que
    `B2` exige. `permissions.CATALOGO` dice lo mismo por reversibilidad, pero vive en el plano
    PRODUCTO y este plano no lo importa.

    No amplia autoridad: una tarea acotada sigue sometida a alcance, materia reservada, zona y
    permisos. Lo unico que cambia es que **no se le exige el gate de las cinco preguntas**, que `D21`
    y `D22` escribieron para capitulos y decisiones estrategicas."""
    accion = tarea.get("accion", "")
    if es_materia_reservada(accion):
        return False
    if accion not in TODO_LO_DELEGABLE:
        return False
    if directorio is not None and not en_alcance(directorio, accion):
        return False
    return True


# ------------------------------------------------- los criterios de D22, aplicados --

def aplicar_criterios(tarea: dict, *, directorio=None, raiz=None) -> dict:
    """Los cuatro se comprueban. Basta que uno falle para que no cumpla, y el juicio **dice cual**:
    un rechazo sin motivo no es revisable.

    `DR-F-3d-2`. Antes los cuatro se leian del **propio dict de la tarea**, y `planificador.a_tarea`
    los escribia como constantes literales: sobre cualquier tarea real esto devolvia `cumple: True`
    salvo materia reservada. El revisor no comprobaba, **transcribia**.

    Ahora cada criterio se mide contra la fuente de verdad que ya existe —`TODO_LO_DELEGABLE` o el
    acta registrada para el alcance, `zona_permitida` para la consistencia, `_MATERIA_RESERVADA` para
    lo reservado— y la bandera del proponente **solo puede anadir fallos, nunca quitarlos**. Una
    declaracion pesimista se respeta; una optimista no sobreescribe una comprobacion objetiva.

    `D21` son cinco preguntas cualitativas de largo plazo —*«¿escala durante los proximos 10 anos?»*—
    y **ninguna funcion puede responderlas**. No se finge que se comprueban: el resultado distingue
    `verificados` de `declarados`, para que nadie vuelva a confundir lo uno con lo otro."""
    accion = tarea.get("accion", "")
    fallos, verificados, declarados, no_aplica = [], [], [], []

    # -- alcance: contra el acta si la hay, y si no contra lo maximo que un acta podria delegar.
    if directorio is not None:
        verificados.append("alcance")
        if not en_alcance(directorio, accion):
            fallos.append("alcance")
    elif accion in TODO_LO_DELEGABLE:
        verificados.append("alcance")
    else:
        verificados.append("alcance")
        fallos.append("alcance")
    if tarea.get("cambia_alcance") and "alcance" not in fallos:
        fallos.append("alcance")

    # -- consistencia (`A3`): contra la **lista enumerada** de decisiones aplicables. Se verifica
    #    solo si TODAS las citadas tienen fuente objetiva y la superan; una sola que exija juicio
    #    humano deja el criterio en «declarado», y una referencia invalida lo hace fallar. Sin lista,
    #    se conserva el comportamiento anterior: declarado, y la bandera solo puede anadir fallos.
    decisiones = evaluar_decisiones(tarea.get("decisiones_aplicables"), tarea, raiz=raiz)
    if decisiones:
        if any(estado == INCUMPLIDA for estado in decisiones.values()):
            fallos.append("consistencia")
            declarados.append("consistencia")
        elif all(estado == VERIFICADO for estado in decisiones.values()):
            verificados.append("consistencia")
        else:
            declarados.append("consistencia")
    else:
        declarados.append("consistencia")
    if not tarea.get("respeta_decisiones", True) and "consistencia" not in fallos:
        fallos.append("consistencia")

    # -- D21 (`B2`): las cinco preguntas siguen siendo el gate de las decisiones estrategicas. Una
    #    tarea tecnica acotada dentro de un alcance ya aprobado **no las exige** —`D21` y `D22` se
    #    escribieron para capitulos, y asi se han aplicado siempre (`2.5`, `5.3`, `5.6`)—. Lo que no
    #    puede demostrarse acotado, no lo es: la clasificacion no se presume.
    if es_tarea_tecnica_acotada(tarea, directorio=directorio):
        no_aplica.append("cinco_preguntas_d21")
    else:
        declarados.append("cinco_preguntas_d21")
        if not tarea.get("d21_afirmativas"):
            fallos.append("cinco_preguntas_d21")

    # -- materia reservada: ya era objetivo antes, y sigue siendolo.
    verificados.append("materia_reservada")
    if tarea.get("materia_reservada") or es_materia_reservada(accion):
        fallos.append("materia_reservada")

    return {"cumple": not fallos, "fallos": tuple(fallos), "criterios": CRITERIOS_D22,
            "verificados": tuple(verificados), "declarados": tuple(declarados),
            "no_aplica": tuple(no_aplica), "decisiones": decisiones}


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
    # **Antes que el acta**: que exista ejecutor no depende de ningun permiso. Un acta que delegara
    # un verbo sin ejecutor no lo haria ejecutable, lo haria mentiroso. Va despues de materia
    # reservada para que la gobernanza mas fuerte siga hablando primero.
    if accion not in _EJECUTORES_CONSTRUIDOS:
        raise SinEjecutor(
            f"{accion!r} esta declarada en TODO_LO_DELEGABLE pero no tiene ejecutor construido: "
            f"los que hoy existen son {_EJECUTORES_CONSTRUIDOS}. INV-9: no se finge capacidad")
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
    # La operacion viaja con la tarea hasta el ejecutor. Sin esto, una tarea constructiva llegaria
    # al ejecutor como si fuera codigo muerto y no haria nada —en silencio—, que es exactamente el
    # defecto que costo completar `forma` cuando la capacidad crecio a cinco formas.
    propuesta = ac.proponer(directorio, {"simbolo": tarea.get("simbolo", ""),
                                         "fichero": tarea["fichero"],
                                         "forma": tarea.get("forma", "funcion"),
                                         "operacion": tarea.get("operacion", "eliminar_codigo_muerto"),
                                         "buscar": tarea.get("buscar"),
                                         "sustituir": tarea.get("sustituir"),
                                         "motivo": f"{accion} bajo REVIEW"})
    cp.registrar_evento(directorio, "propuesta_autorizada",
                        {"id": propuesta["id"], "autorizada_por": f"REVIEW:{revisor}",
                         "acta": f"alcance habilitado por acta del CEO; veredicto de {revisor}"})
    resultado = ac.ejecutar(directorio, propuesta, autoridad=autoridad, verificacion=verificacion)
    return {"ejecutado": not resultado["revertido"], "revisor": revisor, "objeciones": [],
            "efecto_verificado": resultado["efecto_verificado"],
            "revertido": resultado["revertido"], "propuesta": propuesta["id"]}
