"""Primera capacidad de **autoconstruccion gobernada** + `C5 ReviewerAdapter` — `D-ORCH-2` parcial.

## Los ocho pasos, y donde esta la frontera

    OBSERVAR -> DIAGNOSTICAR -> PROPONER -> **AUTORIZAR** -> EJECUTAR -> VERIFICAR -> REGISTRAR -> CONTINUAR

Los tres primeros son lectura y peticion: AURA puede hacerlos sola. El cuarto es la frontera. Los
cuatro ultimos solo ocurren **despues** de una autorizacion humana registrada.

Esa es la diferencia entre automatizacion y autonomia gobernada: no pedir permiso para cada operacion
que ya cae dentro de una autorizacion existente, y no concederselo nunca para las que no.

## Que parte de `D-ORCH-2` implementa esto

**Lo decidido, que no admite diseno alternativo** (`§10.3`, citando la constitucion):

- *«Su autoridad de aprobacion **no es delegable a ningun agente**»* — `1.1:93`.
- *«El silencio o la ausencia de objecion **no** constituye aprobacion»* — `1.1:85`.

De ahi sale `C5` tal como `§5` lo define: **pedir revision y devolver un veredicto estructurado**,
nunca autorizar ni ser requisito para operar. El `Veredicto` **carece de campo de autorizacion** —no
por omision, sino porque tenerlo permitiria que un modelo lo rellenase—.

**Lo no decidido** —si un veredicto puede ser *condicion previa* para ejecutar una tarea `REVIEW`— se
registra como `DECISION_REQUIRED` y no se inventa. `§10.3`: *«solo el CEO puede concederla»*.

## Por que la primera tarea es codigo muerto

Pequena, reversible y **completamente verificable**: se relee el fichero despues de tocarlo, y si la
verificacion falla el cambio se deshace. Dejar el arbol roto es peor que no haber hecho nada.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re

import control_plane as cp

PASOS = ("observar", "diagnosticar", "proponer", "autorizar",
         "ejecutar", "verificar", "registrar", "continuar")

RAIZ_AGENTES = pathlib.Path(__file__).resolve().parents[2] / ".claude" / "agents"

# `§273-277`: «ya define `auditor-consistencia` y `arquitecto-evaluador`. **Se usan esos.** No se crea
# un revisor nuevo ni se contrata un proveedor».
REVISORES = ("auditor-consistencia", "arquitecto-evaluador")

SIN_RESPUESTA = None

AUTORIDADES_HUMANAS = cp.AUTORIDADES_HUMANAS

# Zona donde esta primera capacidad puede escribir: **el plano de desarrollo, y solo el**. El producto
# queda fuera —«no utilizar una tarea peligrosa como primera demostracion»— y la gobernanza queda
# fuera **siempre**, incluso con autorizacion: cambiar D24, la Bible, un ADR o el roadmap no es una
# tarea tecnica que se encargue a un ejecutor, es un acto de gobierno que el CEO hace por acta.
_ZONA_PERMITIDA = "entorno/control-plane/"
# Comparados por **segmento de ruta**, no como substring. Buscar «bible» dentro de la ruta completa
# rechazaba `entorno/control-plane/orquestador.py` porque el repositorio se llama
# `aura-project-bible`: un falso positivo que dejaba la capacidad inservible. Es el mismo error de
# substring que este proyecto ya pago una vez con las zonas de discovery.
_DIRS_GOBERNANZA = frozenset({"docs", "adr", "decisiones", "actas"})
# El PRODUCTO queda fuera **siempre**, igual que la gobernanza, y por la misma via: comparacion por
# segmento de ruta. Estaba solo implicito en la lista blanca, y una auditoria independiente mostro que
# con `raiz` dado la funcion dejaba de mirar la zona y concedia `walking-skeleton/` si la raiz era el
# repositorio. «El producto queda fuera, siempre» tiene que sostenerlo la funcion, no una convencion
# de nombres vigilada por `grep`.
_DIRS_PRODUCTO = frozenset({"walking-skeleton", "aura_skeleton"})
_FICHEROS_GOBERNANZA = frozenset({
    "claude.md", "roadmap.md", "checklist-continuidad.md", "checkpoint-continuidad.md"})


class SinAutorizacion(RuntimeError):
    """Se intento ejecutar sin autoridad humana registrada, o autorizar sin acta."""


class ZonaProhibida(RuntimeError):
    """El destino esta fuera de alcance. **Ni con autorizacion**, si es gobernanza."""


# ------------------------------------------------------- C5 · ReviewerAdapter --

@dataclasses.dataclass(frozen=True)
class Veredicto:
    """Lo que devuelve un revisor. **No lleva campo de autorizacion**: si lo llevara, un modelo
    podria rellenarlo, y `1.1:93` dice que esa autoridad no es delegable a ningun agente."""
    revisor: str
    objeciones: tuple[str, ...]
    resumen: str


def autoriza(_veredicto) -> bool:
    """Siempre False, y existe **para decirlo**.

    Ni el veredicto mas favorable autoriza nada, y la ausencia de veredicto tampoco: `1.1:85`,
    *«el silencio o la ausencia de objecion no constituye aprobacion»*. Tener la funcion y que sea
    constante deja la regla escrita donde alguien la buscaria."""
    return False


def revisor_disponible() -> bool:
    return any((RAIZ_AGENTES / f"{n}.md").exists() for n in REVISORES)


def puede_ejecutarse_sin_revisor(_tarea: dict) -> bool:
    """`§5`: C5 *«NUNCA: ser requisito para operar»*. Sin revisor, el trabajo `AUTO` sigue."""
    return True


def registrar_decision_pendiente(directorio) -> dict:
    """La parte estrecha de `D-ORCH-2`, registrada sin resolver."""
    decision = {
        "id": "D-ORCH-2",
        "estado": "DECISION_REQUIRED",
        "pregunta": ("¿puede el veredicto de un modelo ser CONDICION PREVIA para que el orquestador "
                     "ejecute una tarea clasificada REVIEW, sin que el CEO intervenga en esa "
                     "ejecucion concreta?"),
        "ya_decidido": ["ningun modelo aprueba nada (1.1:93)",
                        "el silencio no es aprobacion (1.1:85)"],
        "por_que_no_la_resuelvo": ("el nivel REVIEW no existe en ADR-0003 —dos listas, no tres— y "
                                   "crearlo es elevar la autonomia: «solo se habilita por politica y "
                                   "decision del CEO, nunca automaticamente» (§10.3)"),
        "implementado_mientras_tanto": ("C5 como interfaz: veredicto estructurado, sin campo de "
                                        "autorizacion, no requisito para operar"),
    }
    cp.registrar_evento(pathlib.Path(directorio), "decision_pendiente", decision)
    return decision


# ------------------------------------------------------------ 1-2 · OBSERVAR / DIAGNOSTICAR --

def zona_permitida(ruta, raiz=None) -> bool:
    """Gobernanza fuera **siempre**; producto fuera en esta primera capacidad.

    **`raiz` solo puede ESTRECHAR, nunca ampliar.** Gobernanza y producto se rechazan antes, pasando
    o no `raiz`: con `raiz` dado la funcion comprobaba unicamente la pertenencia, asi que
    `raiz=<raiz del repo>` concedia el producto entero. Lo encontro una auditoria independiente.

    **`raiz` es para las pruebas y solo para ellas.** Antes, la zona aceptaba de forma incondicional
    cualquier ruta bajo `/tmp/` o que contuviera `/pytest-`, porque las pruebas trabajan en
    directorios temporales. Eso dejaba una barrera de seguridad **abierta en produccion para que las
    pruebas pasaran**: la funcion decia proteger una zona declarada y en realidad protegia esa zona
    *mas todo `/tmp`*. Es el patron `declarado != real` aplicado a un guardarrail.

    Ahora, sin `raiz`, la zona es exactamente la declarada y nada mas. Una prueba que necesite un
    sandbox pasa su propio directorio, de forma **visible en la llamada**; y otra prueba comprueba
    que ningun modulo de produccion pasa nunca ese argumento. La excepcion sigue existiendo, pero
    esta declarada, acotada y vigilada, en vez de escondida dentro del guardarrail."""
    ruta = pathlib.Path(str(ruta).replace("\\", "/"))
    # **Se resuelven los enlaces.** Sin esto, un symlink dentro de la zona que apuntara al producto
    # pasaba: la comparacion era de texto puro. La puerta de escritura usa `raiz` y si resolvia, pero
    # el veredicto de `RevisorSubagente` usa la forma por defecto, y un revisor que opina sobre el
    # fichero equivocado es peor que no tener revisor. Lo encontro la segunda auditoria.
    try:
        real = ruta.resolve()
    except OSError:                                   # enlace roto o permisos: se juzga lo escrito
        real = ruta
    texto = str(ruta).lower()
    segmentos = {s.lower() for s in ruta.parts} | {s.lower() for s in real.parts}
    if segmentos & _DIRS_GOBERNANZA or ruta.name.lower() in _FICHEROS_GOBERNANZA:
        return False
    if segmentos & _DIRS_PRODUCTO:
        return False
    if ruta.name.lower().startswith("acta"):
        return False
    if raiz is not None:
        try:
            relativa = real.relative_to(pathlib.Path(raiz).resolve())
        except ValueError:
            return False
        # **`raiz` ESTRECHA, no amplia.** Con `raiz` dada, la funcion solo comprobaba pertenencia, asi
        # que `raiz=<raiz del repo>` concedia planos vecinos —`entorno/agente-externo/`, por ejemplo—.
        # Lo encontro una auditoria independiente, y el docstring afirmaba justo lo contrario. Si la
        # ruta entra en `entorno/`, el plano tiene que ser el declarado y ningun otro.
        partes = [p.lower() for p in relativa.parts]
        if "entorno" in partes:
            siguiente = partes.index("entorno") + 1
            if siguiente >= len(partes) or partes[siguiente] != "control-plane":
                return False
        return True
    # Lista blanca, no negra. Aceptar «cualquier .py» dejaba pasar el producto entero, que es
    # justamente lo que esta primera capacidad no debe tocar: una zona segura se declara, no se
    # deduce por descarte.
    return _ZONA_PERMITIDA in texto


def observar(ficheros) -> list[dict]:
    """Lectura **pura**: si observar modificara algo, el diagnostico describiria un estado que el
    mismo creo.

    Busca funciones privadas (`_nombre`) que nadie llama dentro del fichero. Las publicas no se
    tocan: pueden usarse desde fuera, y borrarlas seria romper una interfaz sin saberlo."""
    hallazgos = []
    for fichero in ficheros:
        ruta = pathlib.Path(fichero)
        if not ruta.exists() or ruta.suffix != ".py":
            continue
        texto = ruta.read_text(encoding="utf-8")
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            continue
        definidas = {n.name: n for n in ast.walk(arbol)
                     if isinstance(n, ast.FunctionDef) and n.name.startswith("_")
                     and not n.name.startswith("__")}
        usadas = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
        usadas |= {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
        for nombre, nodo in definidas.items():
            if nombre in usadas:
                continue
            hallazgos.append({"simbolo": nombre, "fichero": str(ruta), "linea": nodo.lineno,
                              "motivo": "funcion privada que nadie llama en su propio fichero"})
    return hallazgos


def diagnosticar(hallazgos: list[dict]) -> list[dict]:
    """Anade el juicio tecnico. Tambien lectura pura."""
    return [{**h, "diagnostico": "codigo muerto", "riesgo": "bajo", "reversible": True}
            for h in hallazgos]


# ---------------------------------------------------------------- 3-4 · PROPONER / AUTORIZAR --

def proponer(directorio, hallazgo: dict) -> dict:
    """Una propuesta es una **peticion**, no una decision. Nace sin autorizar, y nada la concede por
    el paso del tiempo: `1.1:85`."""
    directorio = pathlib.Path(directorio)
    existentes = [e for e in cp.leer_eventos(directorio) if e["tipo"] == "propuesta_registrada"]
    propuesta = {"id": f"P-{len(existentes) + 1:03d}", "estado": "PROPUESTA", "autorizada": False,
                 **{k: hallazgo.get(k) for k in ("simbolo", "fichero", "motivo", "linea")}}
    cp.registrar_evento(directorio, "propuesta_registrada", propuesta)
    return propuesta


def autorizar(directorio, id_propuesta: str, por: str, acta: str) -> dict:
    """Solo un acto **humano** y **con acta** autoriza. `1.1:93`: la autoridad de aprobacion del CEO
    no es delegable a ningun agente, asi que ningun nombre de agente vale aqui."""
    if por not in AUTORIDADES_HUMANAS:
        raise SinAutorizacion(
            f"{por!r} no es autoridad humana registrada {AUTORIDADES_HUMANAS}: la autoridad de "
            f"aprobacion no es delegable a ningun agente (1.1:93)")
    if not (acta or "").strip():
        raise SinAutorizacion("la autorizacion exige acta: sin constancia no es explicita (1.1:85)")
    registro = {"id": id_propuesta, "autorizada_por": por, "acta": acta}
    cp.registrar_evento(pathlib.Path(directorio), "propuesta_autorizada", registro)
    return registro


def esta_autorizada(directorio, id_propuesta: str) -> bool:
    return any(e["tipo"] == "propuesta_autorizada" and e["datos"]["id"] == id_propuesta
               for e in cp.leer_eventos(pathlib.Path(directorio)))


# ------------------------------------------------------- 5-7 · EJECUTAR / VERIFICAR / REGISTRAR --

def _quitar_funcion(texto: str, simbolo: str) -> str:
    patron = re.compile(rf"(?:^|\n)def {re.escape(simbolo)}\(.*?(?=\ndef |\nclass |\Z)", re.S)
    return patron.sub("\n", texto, count=1)


def ejecutar(directorio, propuesta: dict, autoridad: str, verificacion=None) -> dict:
    """Aplica el cambio, **verifica el efecto releyendo el fichero** y revierte si algo falla.

    `verificacion` es lo que decide si el arbol quedo sano —la bateria de pruebas, en uso real—. Si
    devuelve falso, el fichero vuelve a como estaba: dejar el arbol roto es peor que no haber hecho
    nada, y ademas rompe la reversibilidad que hace segura esta primera capacidad."""
    directorio = pathlib.Path(directorio)
    ruta = pathlib.Path(propuesta["fichero"])
    if not zona_permitida(ruta, raiz=directorio):
        raise ZonaProhibida(
            f"{ruta} esta fuera de alcance. La gobernanza no se modifica ni con autorizacion: "
            f"cambiarla es un acto del CEO por acta, no una tarea que se encargue a un ejecutor")
    if not esta_autorizada(directorio, propuesta["id"]):
        raise SinAutorizacion(
            f"la propuesta {propuesta['id']!r} no tiene autorizacion humana registrada")

    original = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    nuevo = _quitar_funcion(original, propuesta["simbolo"])
    ruta.write_text(nuevo, encoding="utf-8")

    # **Se relee el fichero.** Que la sustitucion «se haya hecho» no es evidencia de nada.
    tras_el_cambio = ruta.read_text(encoding="utf-8")
    efecto = (f"def {propuesta['simbolo']}(" in original
              and f"def {propuesta['simbolo']}(" not in tras_el_cambio)
    try:
        sano = bool(verificacion() if verificacion else True)
    except BaseException:
        # La verificacion **revento** —el ejecutor se quedo sin cuota, el proceso murio—. Eso no es
        # «no sano»: es «no se sabe». Y con el fichero ya escrito, no saberlo obliga a revertir antes
        # de propagar: dejarlo a medias seria peor que cualquiera de los dos desenlaces.
        ruta.write_text(original, encoding="utf-8")
        cp.registrar_evento(directorio, "cambio_revertido_por_error",
                            {"id": propuesta["id"], "fichero": str(ruta),
                             "motivo": "la verificacion no pudo completarse"})
        raise
    revertido = False
    if not (efecto and sano):
        ruta.write_text(original, encoding="utf-8")
        revertido = True

    registro = {"id": propuesta["id"], "fichero": str(ruta), "simbolo": propuesta["simbolo"],
                "efecto_verificado": bool(efecto), "verificacion_sana": sano,
                "revertido": revertido, "autoridad": autoridad}
    cp.registrar_evento(directorio, "cambio_aplicado", registro)
    return registro


# ---------------------------------------------------------------------- 8 · CONTINUAR --

def ciclo(directorio, ficheros, autoridad_humana: str | None, acta: str,
          verificacion=None, max_cambios: int = 5) -> dict:
    """El ciclo entero, **finito**, deteniendose en la frontera si no hay autoridad.

    Sin acta humana llega hasta `proponer` y para. Eso no es un fallo: es la garantia."""
    directorio = pathlib.Path(directorio)
    hallazgos = diagnosticar(observar(ficheros))
    informe = {"observados": len(hallazgos), "propuestos": 0, "autorizados": 0, "aplicados": 0,
               "revertidos": 0, "detenido_en": "continuar"}
    propuestas = [proponer(directorio, h) for h in hallazgos]
    informe["propuestos"] = len(propuestas)

    if autoridad_humana not in AUTORIDADES_HUMANAS or not (acta or "").strip():
        informe["detenido_en"] = "autorizar"
        return informe

    for propuesta in propuestas[:max_cambios]:
        autorizar(directorio, propuesta["id"], por=autoridad_humana, acta=acta)
        informe["autorizados"] += 1
        resultado = ejecutar(directorio, propuesta, autoridad=autoridad_humana,
                             verificacion=verificacion)
        if resultado["revertido"]:
            informe["revertidos"] += 1
        else:
            informe["aplicados"] += 1
    return informe
