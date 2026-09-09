"""Octava fuente — **AURA lee su propio plan de formacion**.

Hasta hoy las siete fuentes sabian mirar lo que EXISTE: codigo muerto, invocables sin clasificar,
eventos sin puerta, decisiones registradas, bloqueos registrados, estancamiento, entorno. Ninguna
podia expresar una **ausencia de capacidad** —«AURA no sabe hablar»—, y sin embargo ese conocimiento
existe, se mantiene al dia y esta escrito: `PLAN-DE-FORMACION-AURORA.md`. Era el unico documento de
su propia evolucion que le era invisible.

## El techo es `DECISION_REQUIRED`, y lo fija el propio documento

El plan cierra con una regla que gobierna todo lo que contiene:

    «El resultado es un **plan**, nunca una implementacion.
     Ninguna capacidad se desarrolla automaticamente.»

Y la correccion del 2026-08-17 anade que mover una capacidad entre tablas *«exige la regla de
admision —evidencia repetida del uso real—»* y que *«esa decision no la toma la asistencia
externa»*. Por eso el techo de esta fuente **no es configurable**: no hay bandera, constante ni acta
que la haga emitir `OPORTUNIDAD_REAL`. Emitir trabajo ejecutable desde este documento seria
contradecir literalmente la unica regla que el documento se dio a si mismo.

Lo que aporta, entonces, no es autonomia: es **vision**. AURA pasa de no saber que le falta a poder
enumerarlo con su numero, su estado y su linea, en cada vuelta, sin que nadie se lo escriba.

## El vocabulario no se traduce

Las tres tablas del plan son ✅ / 🟡 / 🔴, y aqui se conservan tal cual —`aprendida`,
`en observacion`, `bloqueada`—. Inventar un vocabulario propio y mapear el suyo al mio habria creado
dos verdades sobre el mismo hecho, que es como nacen las discrepancias que este proyecto lleva once
veces corrigiendo.

**Solo lectura.** Ni escribe el plan, ni escribe `estado.json`, ni ejecuta nada. Una prueba lo fija
leyendo este mismo fuente.
"""

from __future__ import annotations

import hashlib
import pathlib
import re

#: El documento. Es la fuente de verdad sobre la formacion de AURORA, y vive en la raiz.
PLAN = "PLAN-DE-FORMACION-AURORA.md"

#: **La raiz del repositorio, resuelta desde este modulo.** El motor invoca las fuentes con
#: `raiz=<control-plane>` —el arbol que AURA puede tocar—, pero el plan de formacion vive en la raiz
#: del repositorio y NO es un fichero que ella toque: es el que la describe. Deducirlo del `raiz` que
#: llega habria dejado la fuente muda en produccion mientras las pruebas la veian funcionar, que es
#: exactamente el «declarado != real» que este proyecto lleva once veces pagando. Mismo patron que
#: `review.RAIZ_GOBERNANZA` y `revisores._RAIZ`.
_RAIZ_REPO = pathlib.Path(__file__).resolve().parents[2]

#: Los tres estados **del documento**, en su propio vocabulario.
ESTADOS = ("aprendida", "en observacion", "bloqueada")

#: Que cabecera abre cada tabla. Se reconoce por el emoji, que es lo que el documento usa.
_SECCIONES = (("✅", "aprendida"), ("🟡", "en observacion"), ("🔴", "bloqueada"))

#: El verbo que un acta podria delegar para construir una capacidad. Aqui solo se **nombra**: esta
#: fuente nunca produce trabajo ejecutable, asi que el verbo aparece como lo que haria falta, no como
#: lo que se va a hacer.
ACCION = "implementar_incremento_especificado"

#: `| 001 | **Nombre de la capacidad** | ... |`
_FILA = re.compile(r"^\|\s*(\d{3})\s*\|\s*\*\*(.+?)\*\*\s*\|(.*)$")


def capacidades(raiz) -> list[dict]:
    """Las capacidades del plan, con su numero, su nombre, su estado y su linea. **Lectura pura.**

    Si el plan no esta, no hay capacidades: devolver algo inventado seria peor que devolver nada."""
    ruta = pathlib.Path(raiz) / PLAN
    if not ruta.is_file():
        return []
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError:                                    # pragma: no cover - fichero ilegible
        return []

    halladas, estado = [], None
    # **La cita se guarda resuelta.** El meta-control de procedencia comprueba la fuente con
    # `is_file()`, que es relativo al directorio del proceso; el plan vive en la raiz y el ciclo
    # corre desde el control-plane, asi que una ruta relativa "no llevaria a ninguna parte" siendo
    # perfectamente valida. Es la misma forma que ya usa `codigo_muerto`.
    ruta = ruta.resolve()
    for numero_de_linea, linea in enumerate(texto.splitlines(), start=1):
        if linea.startswith("## "):
            estado = next((e for emoji, e in _SECCIONES if emoji in linea), None)
            continue
        if estado is None:
            continue
        fila = _FILA.match(linea)
        if fila:
            halladas.append({"numero": fila.group(1), "nombre": fila.group(2).strip(),
                             "estado": estado, "linea": numero_de_linea, "ruta": str(ruta),
                             "resto": fila.group(3).strip(" |")})
    return halladas


def formacion(raiz, directorio) -> list:
    """La fuente. **Solo lectura**, y su techo es `DECISION_REQUIRED` por construccion.

    Ni `raiz` ni `directorio` se usan: el plan no esta en la zona de trabajo ni en el historial —esta
    en la raiz del repositorio, y es el documento que describe a AURA, no uno que AURA edite—. Se
    aceptan para respetar la firma `(raiz, directorio)` que `descubrir()` invoca en toda fuente."""
    # **El import va dentro y no arriba.** `descubrimiento` enchufa esta fuente en su dict, asi que
    # un import de modulo aqui cierra el ciclo: `import formacion` primero reventaba con
    # `partially initialized module`. La suite no lo veia porque siempre llegaba por `descubrimiento`.
    # Sin dependencia de modulo, las dos ordenes de import funcionan.
    import contrato as ct
    import descubrimiento as des

    oportunidades = []
    # **La raiz ESTRECHA, tambien aqui.** El plan se lee siempre del repositorio —describe a AURA, no
    # a un sandbox—, pero un contrato apunta a un fichero concreto, y ese fichero tiene que estar
    # DENTRO del arbol sobre el que se trabaja. Sin esta condicion, la rama de contratos inyectaba
    # una oportunidad ejecutable del repositorio real en cada prueba con `tmp_path`: 24 pruebas del
    # motor y de la segunda barrera cayeron por eso, con un `KeyError: simbolo` que lo delato.
    try:
        ambito = pathlib.Path(directorio).resolve()
    except OSError:                                    # pragma: no cover - directorio ilegible
        ambito = None


    # **Las capacidades que ya tienen contrato escrito.** Un contrato en `CONTRATOS` es, por
    # construccion, declaracion + especificacion + puntero a su acta: lo escribe el CEO en un
    # directorio que AURA no puede tocar. Sin esta rama, `F4` seria un buzon que nadie abre.
    for ruta in sorted(ct.CONTRATOS.glob("*.toml")) if ct.CONTRATOS.is_dir() else ():
        cap = ct.contrato_de(ruta.stem)
        if not cap:
            continue
        regla = cap.get("regla_de_transformacion") or {}
        objetivo = (cap.get("perimetro") or {}).get("modificables", [""])[0]
        if ambito is None or not objetivo or not pathlib.Path(objetivo).resolve().is_relative_to(ambito):
            continue
        # La identidad no se inventa: del contrato sale su oportunidad, y de la oportunidad su
        # tarea —`id_de_tarea` es `sha256(oportunidad.id)`, determinista—. Es la misma cadena que ya
        # usaba el ciclo, asi que el evaluador puede preguntar por ESTA tarea y no por otra.
        id_op = des._id_de(str(ruta), cap["id"], ACCION, cap["nombre"])
        veredicto = ct.evaluar(cap, directorio=ambito,
                               tarea="TA-" + hashlib.sha256(id_op.encode("utf-8")).hexdigest()[:12])
        implementable = veredicto["estado"] == ct.IMPLEMENTABLE
        completada = veredicto["estado"] == ct.COMPLETADA
        oportunidades.append(des.Oportunidad(
            id=id_op,
            fuente=f"{ruta}:1",
            justificacion=(f"ya construida y verificada: {cap['intencion']}" if completada
                           else cap["intencion"]),
            alcance=objetivo or str(ruta), accion=ACCION,
            autoridad=(cap.get("autoridad") or {}).get("acta", "CEO"),
            criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
            evidencia_requerida={"tipo": "fichero_existe", "ruta": objetivo or str(ruta)},
            riesgo=("bajo: reversible y verificable segun su contrato" if implementable
                    else "ninguno: no se ejecuta"),
            # **Completada no es trabajo, y tampoco es una decision pendiente.** `FALSO_HUECO` es
            # exactamente su clase: *«parece un hueco y no lo es; se descarta con su motivo»*.
            estado=(des.FALSO_HUECO if completada
                    else des.OPORTUNIDAD_REAL if implementable
                    else des.DECISION_REQUIRED),
            detalle={"numero": cap["id"], "nombre": cap["nombre"],
                     "estado_en_el_plan": "con contrato",
                     "contrato": veredicto["estado"],
                     "operacion": regla.get("operacion", "eliminar_codigo_muerto"),
                     "buscar": regla.get("buscar"), "sustituir": regla.get("sustituir")}))

    del raiz
    for cap in capacidades(_RAIZ_REPO):
        if cap["estado"] == "aprendida":
            # Ya adquirida: no hay nada que construir, y proponerla seria fabricar trabajo.
            continue
        # **El puente F5** (acta del CEO 2026-09-07). Una capacidad se vuelve trabajo **solo** si su
        # contrato pasa las nueve condiciones: campos completos, regla determinista, fuentes que
        # existen, perimetro en zona, acta registrada, ejecutor construido, efecto reversible y
        # pruebas declaradas. La evaluacion es POR CAPACIDAD: que F5 exista no autoriza nada.
        #
        # Hoy `contrato_de()` devuelve None para todas —`F4`, donde vive el contrato de cada
        # capacidad, sigue sin decidirse—, asi que el techo real sigue siendo `DECISION_REQUIRED`.
        # La rama existe, esta probada con fixtures y **no se ha ejercido con ninguna capacidad
        # real**: preferimos decir eso a fabricar una para estrenarla.
        contrato = ct.contrato_de(cap["numero"])
        veredicto = ct.evaluar(contrato, directorio=_RAIZ_REPO / "entorno" / "control-plane") \
            if contrato else None
        implementable = bool(veredicto and veredicto["estado"] == ct.IMPLEMENTABLE)
        fuente = f"{cap['ruta']}:{cap['linea']}"
        oportunidades.append(des.Oportunidad(
            id=des._id_de(fuente, cap["numero"], ACCION, cap["nombre"]),
            fuente=fuente,
            justificacion=(f"capacidad {cap['numero']} «{cap['nombre']}» esta declarada como "
                           f"{cap['estado']} y no adquirida: construirla exige un acta del CEO, "
                           f"porque el plan dice que ninguna capacidad se desarrolla automaticamente"),
            alcance=f"capacidad-{cap['numero']}", accion=ACCION, autoridad="CEO",
            criterio_de_finalizacion={"capacidad": "diagnosticar_estado"},
            evidencia_requerida={"tipo": "salida_contiene", "patron": cap["numero"]},
            riesgo=("bajo: reversible y verificable segun su contrato" if implementable
                    else "ninguno: no se ejecuta"),
            estado=des.OPORTUNIDAD_REAL if implementable else des.DECISION_REQUIRED,
            detalle={"numero": cap["numero"], "nombre": cap["nombre"],
                     "estado_en_el_plan": cap["estado"],
                     "contrato": veredicto["estado"] if veredicto else "SIN_CONTRATO"}))
    return oportunidades


__all__ = ["capacidades", "formacion", "ESTADOS", "ACCION", "PLAN"]
