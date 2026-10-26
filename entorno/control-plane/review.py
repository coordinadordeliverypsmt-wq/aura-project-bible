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


class TareaSinContratoQueLaAutorice(RuntimeError):
    """La tarea no se corresponde con el contrato que dice autorizarla — o no cita ninguno.

    Es distinto de `ReviewNoHabilitado`: alli el acta no cubre el VERBO; aqui el verbo esta
    autorizado y lo que no encaja es **esta escritura concreta** con lo que el contrato declaro.
    Separarlas importa porque el diagnostico es opuesto: una se arregla con un acta, la otra
    significa que alguien pretende escribir algo que nadie aprobo."""


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
    # **Por la puerta gobernada, no por la primitiva del log** (acta del CEO, 2026-09-20). Las
    # comprobaciones de arriba seguian siendo correctas y dejaron de ser suficientes en cuanto se
    # midio que `cp.registrar_evento` aceptaba el evento en crudo: la garantia no era esta funcion,
    # era que fuese el UNICO camino. La puerta repite autoridad y acta —a proposito: quien escribe
    # el evento es quien tiene que negarse— y anade la monotonicidad del alcance.
    registro = cp.registrar_review_habilitado(pathlib.Path(directorio), por=por, acta=acta,
                                              alcance=tuple(alcance))["datos"]
    return {**registro, "alcance": tuple(registro["alcance"])}


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
    """Delega en `control_plane.alcance_de_review`: **un solo interprete** del mismo hecho (`INV-7`).

    Vive alli porque la puerta que ESCRIBE necesita saber lo mismo que quien LEE —para poder negar
    una ampliacion hay que conocer el alcance vigente—, y dos deducciones del mismo hecho son dos
    verdades esperando a divergir."""
    return cp.alcance_de_review(pathlib.Path(directorio))


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

def _exigir_correspondencia_con_el_contrato(tarea: dict, accion: str) -> dict | None:
    """**La tarea tiene que ser la que su contrato autorizo.** Quinta puerta (CEO, 2026-09-20).

    Las otras cuatro comprueban el VERBO —que sea delegable, que tenga ejecutor, que REVIEW este
    encendido y que el acta lo cubra—. Ninguna mira **esta escritura concreta**. Medido antes de
    escribir esta funcion: una tarea que declaraba venir de un contrato y cambiaba el fichero, la
    operacion o los textos llegaba a la escritura sin que nada lo notara.

    **Por que aqui y no en `autoconstruccion.ejecutar`.** Dos lineas mas abajo, `ac.proponer()`
    convierte la tarea en una `propuesta` que ya NO lleva el identificador del contrato: este es el
    ultimo punto donde el dato existe. Y es la puerta por la que pasa todo el mundo — las dos vias
    de produccion convergen aqui, y `autoconstruccion.ciclo` no tiene llamante (ALERTA-005).

    **Fallo cerrado** (ADR-0003, «ante la duda, roja»): citar un contrato que no existe se rechaza
    igual que uno que no corresponde. Tratar el fichero ausente como «nada que comprobar» haria de
    inventarse un nombre la forma mas barata de saltarse la barrera entera.

    **Lo que NO exige contrato.** El codigo muerto no nace de uno, y obligarlo habria roto la
    capacidad anterior. La linea se traza por el verbo: `implementar_incremento_especificado` solo
    lo produce `formacion.py` a partir de un contrato, asi que ese verbo sin contrato no es «una
    tarea sin contrato» — es una que perdio la autorizacion que la justifica.

    El import es **diferido a proposito**: `contrato` importa `review`, y a nivel de modulo esto
    seria un ciclo. Dentro de la funcion no lo es — para cuando se ejecuta, `review` ya esta
    completo en `sys.modules`—, y es un patron que este plano ya usa en otros modulos.

    **Deuda condicionada** (CLAUDE.md §7): `autoconstruccion.ciclo()` llama a `ejecutar()` por su
    cuenta, sin pasar por aqui. Hoy no tiene ningun llamante de produccion, asi que la barrera cubre
    las dos vias reales. **Si algun dia lo tuviera**, necesitaria su propia comprobacion o dejar de
    llamar a `ejecutar()` directamente: seria la geometria de ALERTA-005 otra vez."""
    import contrato as ct

    identificador = str(tarea.get("contrato") or "").strip()

    if not identificador:
        if accion == ACCION_DE_EVOLUCION:
            raise TareaSinContratoQueLaAutorice(
                f"{accion!r} solo nace de un contrato y esta tarea no cita ninguno: sin el no hay "
                f"forma de saber que escritura se autorizo")
        return None                              # codigo muerto: legitimo sin contrato

    declarado = ct.contrato_de(identificador)
    if declarado is None:
        raise TareaSinContratoQueLaAutorice(
            f"la tarea cita el contrato {identificador!r} y no consta en {ct.CONTRATOS}: una "
            f"autorizacion que no se puede ir a leer es indistinguible de una inventada")

    if not ct.corresponde_tarea_a_contrato(tarea, declarado):
        raise TareaSinContratoQueLaAutorice(
            f"la tarea no se corresponde con el contrato {identificador!r} que dice autorizarla "
            f"(fichero {tarea.get('fichero')!r}, operacion {tarea.get('operacion')!r}): el contrato "
            f"acota QUE se escribe, no solo quien puede escribir")

    # Se devuelve el contrato YA LEIDO. Volver a abrirlo mas abajo seria interpretarlo dos veces, y
    # `INV-7` dice que el plan se interpreta en un solo punto y no se reinterpreta.
    return declarado


def _verificador_de_review(contrato: dict, directorio):
    """El verificador del contrato, atado a la COPIA que reciba. **Cada prueba se remapea a la copia**:
    los contratos reales declaran rutas ABSOLUTAS al arbol vivo, y ejecutarlas tal cual cargaba el
    modulo ORIGINAL (medido), de modo que se verificaba el original y se declaraba aislado. Una prueba
    que no cae dentro de `directorio` no se puede aislar: no se ejecuta nada (`no_aislable`).
    **Confinamiento ESTRICTO OBLIGATORIO** (`aislamiento.preparar_estricto`, FASE B del PROMPT 03): ESCRITURA
    solo en la copia (+ el temporal del informe, que ademas es su `TMPDIR`) y `/dev/null`; LECTURA solo del
    interprete, la stdlib, las librerias dinamicas, los paquetes de pytest y la copia (NO `/etc`, `/proc`,
    `$HOME`, el plano vivo ni `sys.path` del padre); RED denegada (Landlock TCP + seccomp: TCP, UDP, unix,
    netlink, packet, io_uring); senales y sockets unix abstractos acotados al dominio. Tambien para hijos y
    nietos. Si CUALQUIER control falta (ABI<6, sin seccomp, confinador que no declare todos los controles
    de `ais.CONTROLES_ESTRICTOS`) NO se ejecuta nada y el estado es `sin_confinamiento` (rechazo): degradar
    en silencio daria por verificado algo sin aislar. Un fallo al aplicar las reglas en el hijo es
    `error_infraestructura`. Limites no mitigados: ver `aislamiento.py`.
    Devuelve `ac.ResultadoVerificacion`; `confinada=True` solo si la ejecucion ocurrio con TODOS los controles."""
    import aislamiento as ais
    import verificador as vf
    minimas = [str(p) for p in (((contrato or {}).get("verificacion") or {}).get("pruebas_minimas") or [])
               if str(p).strip()]
    base = pathlib.Path(directorio).resolve()

    def verificar(raiz) -> "ac.ResultadoVerificacion":
        raiz = pathlib.Path(raiz)
        remapeadas = []
        for prueba in minimas:
            # Las relativas se interpretan como hoy: contra el directorio (cwd del verificador).
            ruta = pathlib.Path(prueba)
            ruta = (ruta if ruta.is_absolute() else base / ruta).resolve()
            try:
                remapeadas.append(str(raiz / ruta.relative_to(base)))
            except ValueError:
                return ac.ResultadoVerificacion(
                    "no_aislable", False, False, f"la prueba {prueba} esta fuera de {base}")
        try:
            if ais.abi_disponible() <= 0:
                return ac.ResultadoVerificacion("sin_confinamiento", True, False,
                                                "este kernel no ofrece Landlock: no se verifica")
            try:
                confinar = ais.preparar_estricto(raiz)
            except ais.ConfinamientoInsuficiente as exc:
                return ac.ResultadoVerificacion("sin_confinamiento", True, False,
                                                f"confinamiento estricto no disponible: {exc}")
            controles = getattr(confinar, "controles", None) or {}
            faltan = [c for c in ais.CONTROLES_ESTRICTOS if controles.get(c) is not True]
            if getattr(confinar, "abi", 0) <= 0 or getattr(confinar, "completo", False) is not True or faltan:
                return ac.ResultadoVerificacion("sin_confinamiento", True, False,
                                                f"el confinador no declara el modo estricto completo: {faltan}")
            informe = vf.ejecutar_pruebas(remapeadas, raiz, confinar=confinar)
        except ais.ConfinamientoInsuficiente as exc:      # al componer con el temporal del informe
            return ac.ResultadoVerificacion("sin_confinamiento", True, False, str(exc))
        except Exception as exc:  # noqa: BLE001 — no medir no es fallar la prueba
            return ac.ResultadoVerificacion("error_infraestructura", True, False, repr(exc))
        if informe.agotado:
            return ac.ResultadoVerificacion("error_infraestructura", True, True, "plazo agotado")
        return ac.ResultadoVerificacion("sano" if informe.sano else "fallo", True, True,
                                        informe.salida[-500:])

    return verificar


def ejecutar_bajo_review(directorio, tarea: dict, propuesto_por: str, autoridad: str,
                         verificacion=None, revisor: str | None = None) -> dict:
    """`clasificar → revisar → ejecutar → verificar → registrar`, con **cinco** puertas antes de
    tocar nada: materia reservada, ejecutor construido, nivel habilitado, alcance del acta y
    **correspondencia con el contrato** — mas el veredicto sin objeciones."""
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
    contrato_declarado = _exigir_correspondencia_con_el_contrato(tarea, accion)
    # **Validar el verificador al ENTRAR**: antes de veredicto, `proponer` y `registrar_propuesta_autorizada`.
    # Un verificador sin raiz lanzaba `VerificadorSinRaiz` solo DENTRO de `ejecutar`, ya registradas la
    # propuesta y su autorizacion.
    ac._exigir_raiz(verificacion)

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
    cp.registrar_propuesta_autorizada(
        directorio, propuesta["id"], autorizada_por=f"{cp.PREFIJO_REVIEW}{revisor}",
        acta=f"alcance habilitado por acta del CEO; veredicto de {revisor}")
    # **EL LISTON LO PONE EL CONTRATO** (CEO, 2026-09-20). Sin esto, el punto de entrada empaquetado
    # pasa `verificacion=None`, el ejecutor trata «no se sabe» como fallo y **revierte todo cambio**:
    # medido en sandbox, una tarea impecable se aplicaba y se deshacia, asi que ninguna podia
    # completarse jamas. El verificador se deriva de las `pruebas_minimas` del contrato que YA se
    # cargo en la quinta puerta —quien decide que hay que comprobar es quien autorizo el cambio, no
    # el ejecutor—. Un verificador explicito del llamante gana: esto rellena el hueco, no lo pisa.
    if verificacion is None and contrato_declarado is not None:
        # Sobre la raiz que RECIBA: `ejecutar` verifica en una copia aislada, no en el arbol vivo.
        verificacion = _verificador_de_review(contrato_declarado, directorio)
    resultado = ac.ejecutar(directorio, propuesta, autoridad=autoridad, verificacion=verificacion)
    return {"ejecutado": not resultado["revertido"], "revisor": revisor, "objeciones": [],
            "efecto_verificado": resultado["efecto_verificado"],
            "revertido": resultado["revertido"], "propuesta": propuesta["id"],
            # Lo que el ejecutor declara sobre COMO se verifico: no se descarta al subir de nivel.
            **{k: resultado[k] for k in ("verificacion_aislada", "ejecucion_confinada", "promovido",
                                         "motivo") if k in resultado}}
