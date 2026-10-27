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
import contextlib
import dataclasses
import fcntl
import fnmatch
import hashlib
import inspect
import json
import math
import os
import pathlib
import re
import secrets
import shutil
import stat
import tempfile
import time

import control_plane as cp
import orquestador  # para `parada_solicitada`: una sola fuente de verdad del kill switch, no una copia

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

#: La raiz del repositorio, para resolver el perimetro declarado por acta contra rutas absolutas.
_RAIZ_REPO = pathlib.Path(__file__).resolve().parents[2]

#: **Ampliacion quirurgica del perimetro — acta del CEO 2026-09-07.** UN fichero, nombrado por su
#: ruta relativa COMPLETA. No es un prefijo ni un directorio: el acta dice *«esta autorizacion NO se
#: extiende a ningun otro fichero ni directorio»*, y un prefijo habria concedido `milestones/`
#: entero. La accion sigue siendo `eliminar_codigo_muerto`; no se crea autoridad, capacidad ni
#: excepcion por funcion. Gobernanza y producto siguen ganando siempre, antes de mirar esta lista.
_FICHEROS_AUTORIZADOS = frozenset({
    "milestones/m3-entry/medicion-razonador/heuristicas_deterministas.py",
})


class SinAutorizacion(RuntimeError):
    """Se intento ejecutar sin autoridad humana registrada, o autorizar sin acta."""


#: **El vocabulario de transformaciones, cerrado.** No se inventa: `herramientas/mutar.py` lleva
#: meses aplicando `buscar`/`sustituir` de forma gobernada —patron exacto, unico, no-op rechazado,
#: aplicacion acotada y restauracion verificada—. Aquello es un arnes de pruebas y vive en el
#: producto; esto es la misma semantica en el plano donde `ejecutar()` ya aporta zona, autorizacion,
#: relectura, verificacion y reversion. Una operacion que no este aqui **no se interpreta**.
OPERACIONES = ("eliminar_codigo_muerto", "sustituir_texto")


class OperacionDesconocida(RuntimeError):
    """La propuesta declara una operacion que no esta en `OPERACIONES`. No se intenta adivinar."""


class NoSustituible(RuntimeError):
    """La segunda barrera se nego para una sustitucion: el patron no es aplicable sin ambiguedad."""


class NoEliminable(RuntimeError):
    """La segunda barrera se nego: el simbolo no es eliminable, lo diga quien lo diga."""


class FicheroIntocable(RuntimeError):
    """El destino decide la autoridad del propio anillo (`_INTOCABLES`). No se toca por tarea."""


class ParadaActiva(RuntimeError):
    """La PARADA esta armada: no se escribe nada. Kill switch fuera de banda (Bible 5.3)."""


class ZonaProhibida(RuntimeError):
    """El destino esta fuera de alcance. **Ni con autorizacion**, si es gobernanza."""


class PromocionesBloqueadas(RuntimeError):
    """Hay un diario de promocion ambiguo o una restauracion fallida: no se promueve nada mas hasta
    que una persona lo resuelva y retire la marca `BLOQUEADO`. Ante la duda, roja (ADR-0003)."""


class RestauracionFallida(RuntimeError):
    """La promocion fallo Y el fichero vivo no pudo devolverse al original verificado. Jamas es exito:
    el respaldo y el diario se conservan."""


class CandidatoNoAislable(RuntimeError):
    """El destino no puede verificarse en una copia (fuera del directorio, o excluido de la copia por
    ser sensible). Fail-closed: sin aislamiento no se escribe."""


class VerificadorSinRaiz(RuntimeError):
    """El verificador no acepta la raiz de la copia (p. ej. `lambda: True`): mediria el arbol VIVO, que
    aun contiene el original, no el candidato. Fail-closed: no se ejecuta nada (ni copia ni verificador)
    y el vivo queda intacto. Un verificador debe declarar un parametro obligatorio (`def v(raiz)`)."""


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
    # **El perimetro que el acta anade.** Va aqui a proposito: DESPUES de gobernanza, producto y
    # actas —que siguen rechazandose siempre, tambien para estos ficheros— y ANTES de `raiz`, porque
    # el ciclo llama con `raiz=<control-plane>` y el fichero autorizado no cuelga de ahi. Se compara
    # la ruta relativa entera, nunca un prefijo.
    # **Y solo cuando se opera SOBRE ESTE REPOSITORIO** (incidente del 2026-09-20). El atajo concedia
    # el fichero con cualquier `raiz`, incluida una ajena: una medicion del motor montada en un
    # sandbox temporal borro 49 lineas del fichero REAL: `ficheros_autorizados()` devuelve rutas
    # absolutas del repositorio, asi que montar un sandbox no protegia nada — la ruta concedida
    # apuntaba fuera de el. El acta amplio el perimetro para trabajar sobre este repositorio, no
    # «desde cualquier raiz»; con una raiz ajena, el acta no tiene nada que decir. Esto RESTRINGE: el
    # camino de produccion —`raiz=<control-plane>` del repo real— no cambia.
    def _la_raiz_es_de_este_repositorio() -> bool:
        if raiz is None:
            return True
        try:
            pathlib.Path(raiz).resolve().relative_to(_RAIZ_REPO)
        except ValueError:
            return False
        return True

    try:
        if (real.relative_to(_RAIZ_REPO).as_posix() in _FICHEROS_AUTORIZADOS
                and _la_raiz_es_de_este_repositorio()):
            return True
    except ValueError:                                # fuera del repositorio: no es asunto del acta
        pass
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


def ficheros_autorizados() -> tuple[pathlib.Path, ...]:
    """Los ficheros exactos que el acta anade al perimetro, resueltos y **solo si existen**.

    Ampliar la zona no amplia el barrido: son dos cosas distintas —que se puede tocar y donde se
    mira—. El descubridor consulta esta lista para llegar a ellos, y la lista vive en un solo sitio."""
    return tuple(sorted(r for r in (_RAIZ_REPO / f for f in _FICHEROS_AUTORIZADOS) if r.is_file()))


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

def _correlacion_valida(tarea, intento) -> bool:
    """`tarea` cadena no vacia e `intento` entero (no booleano) y positivo. Tipo estricto. (El DP pedia la forma
    `TA-…`, pero el `review` manual usa ids propios —`T-A1`, `AUT-001`— y exigirla dejaria sin correlacion
    justo esas tareas: la identidad la garantiza el `seq` de la `tarea_planificada`, no el prefijo.)"""
    return (isinstance(tarea, str) and bool(tarea.strip())
            and isinstance(intento, int) and not isinstance(intento, bool) and intento > 0)


def proponer(directorio, hallazgo: dict, *, tarea: str | None = None, intento: int | None = None,
             via: str | None = None) -> dict:
    """Una propuesta es una **peticion**, no una decision. Nace sin autorizar, y nada la concede por
    el paso del tiempo: `1.1:85`.

    **Correlacion (DP-AUTOCONSTRUCCION D1).** `tarea` e `intento` (el `seq` de su `tarea_planificada`)
    viajan con la propuesta y, desde ella, en el diario y en cada `cambio_aplicado`. `via="ciclo"` marca
    la API `ciclo()`, que no tiene tarea: sus eventos llevan `tarea: None, intento: None` y el
    planificador nunca los atribuye a ninguna.

    **Id sin carrera (D3).** `P-NNN` se calcula **y** se anade bajo el mismo `lock_estado`, derivandolo
    dentro de `registrar_evento_si`: dos `proponer` concurrentes no pueden obtener el mismo."""
    directorio = pathlib.Path(directorio)
    if (tarea is None) != (intento is None):
        raise ValueError("`tarea` e `intento` van juntos: una correlacion a medias no correlaciona")
    if tarea is not None and not _correlacion_valida(tarea, intento):
        raise ValueError(f"correlacion mal formada: tarea={tarea!r} (cadena), intento={intento!r} (entero > 0)")
    propuesta: dict = {}

    def derivar() -> dict:
        existentes = [e for e in cp.leer_eventos(directorio) if e["tipo"] == "propuesta_registrada"]
        propuesta.update({
            "id": f"P-{len(existentes) + 1:03d}", "estado": "PROPUESTA", "autorizada": False,
            # `forma` viaja con la propuesta desde que la capacidad cubre las cinco formas del
            # codigo muerto: sin ella el ejecutor volveria a suponer «funcion» y no borraria
            # nada, que es exactamente lo que pasaba —en silencio y revirtiendo— antes de esto.
            **{k: hallazgo.get(k) for k in ("simbolo", "fichero", "motivo", "linea",
                                             "buscar", "sustituir")},
            # La operacion viaja con la propuesta. Por defecto la de siempre: sin esto, una
            # propuesta antigua cambiaria de comportamiento al aparecer el vocabulario nuevo.
            "operacion": hallazgo.get("operacion", "eliminar_codigo_muerto"),
            "forma": hallazgo.get("forma", "funcion")})
        if tarea is not None:
            propuesta.update({"tarea": tarea, "intento": intento})
        if via is not None:
            propuesta.update({"tarea": None, "intento": None, "via": via})
        return dict(propuesta)

    cp.registrar_evento_si(directorio, "propuesta_registrada", None, lambda: True, derivar=derivar)
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
    # Por la puerta gobernada (acta del CEO, 2026-09-20): el evento dejo de aceptarse en crudo, y
    # esta funcion no puede ser la excepcion que justifique mantener abierta la via.
    return cp.registrar_propuesta_autorizada(pathlib.Path(directorio), id_propuesta,
                                             autorizada_por=por, acta=acta)["datos"]


def esta_autorizada(directorio, id_propuesta: str) -> bool:
    return any(e["tipo"] == "propuesta_autorizada" and e["datos"]["id"] == id_propuesta
               for e in cp.leer_eventos(pathlib.Path(directorio)))


# ------------------------------------------------------- 5-7 · EJECUTAR / VERIFICAR / REGISTRAR --

def _exportados(arbol) -> set:
    """Los nombres que el modulo publica en `__all__`. Son cadenas dentro de una lista, no `Name`,
    asi que ningun analisis de uso los ve — y borrarlos deja `import *` roto con `AttributeError`."""
    exportados = set()
    for n in arbol.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(x, ast.Name) and x.id == "__all__" for x in n.targets):
            exportados |= {e.value for e in ast.walk(n.value)
                           if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return exportados


def es_eliminable(fuente: str, simbolo: str, forma: str) -> tuple[bool, str]:
    """**La segunda barrera.** ¿Es este simbolo eliminable, mire quien lo mire?

    El detector responde a otra pregunta —*¿parece que nadie lo usa?*— y el 2026-08-31 se equivoco
    tres veces: AURA borro `from __future__ import annotations` de tres ficheros haciendo exactamente
    lo que se le pidio. Y lo que aquello destapo es mayor que los tres nombres:

        La verificacion de efecto comprueba que el simbolo DESAPARECIO, no que DEBIERA desaparecer.

    Contra un falso positivo del detector, el revisor, el acta, la verificacion y la reversion **no
    protegen**: todos dan por buena la premisa. El unico punto que puede refutarla es uno que vuelva a
    mirar el arbol y pregunte otra cosa.

    Esta funcion es **la unica fuente de verdad** sobre lo eliminable, y la consultan el descubridor
    —para que un falso positivo no llegue ni a proponerse— y el ejecutor —para que nada que llegue por
    otra via se borre—. Escribirla dos veces seria la copia que falta convertida en ruta abierta.

    Devuelve `(puede, motivo)`. Un rechazo sin motivo obliga a quien lo lea a averiguarlo."""
    try:
        arbol = ast.parse(fuente)
    except SyntaxError as exc:
        return False, f"el fichero no compila antes de tocarlo: {exc}"

    corto = simbolo.split(".")[-1]

    # 1 · Protocolo del lenguaje. Es la **propiedad**, no una lista de tres nombres: excluir solo los
    #     conocidos seria volver a una lista escrita a mano.
    if corto.startswith("__") and corto.endswith("__"):
        return False, f"{corto!r} es protocolo del lenguaje, no una constante privada"

    # 2 · Directiva del compilador. Su efecto ocurre al parsear, asi que su uso no aparece en el
    #     arbol y cualquier analisis de uso la ve muerta siempre.
    if forma == "import":
        for n in arbol.body:
            if isinstance(n, ast.ImportFrom) and n.module == "__future__":
                if any((a.asname or a.name) == corto for a in n.names):
                    return False, (f"{corto!r} viene de `__future__`: es una directiva del compilador "
                                   f"y su efecto no es un uso que se pueda contar")

    # 3 · Exportado. El modulo lo publica, aunque nadie lo use aqui dentro.
    if corto in _exportados(arbol):
        return False, (f"{corto!r} esta en `__all__`: el modulo lo exporta, y borrarlo dejaria "
                       f"`import *` fallando con AttributeError sin que ninguna prueba lo viera")

    # 4 · Tiene que existir. Fail-closed: borrar «aproximadamente» deja el arbol en un estado que
    #     nadie pidio y que la verificacion tendria que descubrir despues.
    nodo = _nodo_de(arbol, simbolo, forma)
    if nodo is None:
        return False, f"{simbolo!r} no consta como {forma} en este fichero"

    # 5 · **Decorado.** Un decorador es codigo que se ejecuta sobre la definicion, y lo que hace con
    #     ella no se deduce de su nombre: puede inscribirla en un registro, y entonces el simbolo
    #     esta VIVO aunque nadie lo llame nunca. Lo destapo el fichero que el acta del 2026-09-07
    #     anadio al perimetro: sus 17 heuristicas `_r_*` llevan `@_regla(...)`, que las mete en
    #     `REGLAS` por efecto lateral. Las cinco comprobaciones anteriores las daban por eliminables
    #     y el ejecutor las habria borrado verificando el efecto correcto —el simbolo desaparece—,
    #     que es el fallo descrito arriba con un disfraz nuevo.
    #
    #     Y la comprobacion estructural no cubre este caso: al quitar la funcion, su decorador queda
    #     huerfano y se **apila sobre la siguiente**, asi que el fichero sigue compilando y ademas
    #     queda corrompido en silencio. Se rechaza por la **propiedad** —estar decorado—, no por una
    #     lista de decoradores conocidos, que seria la lista escrita a mano que este proyecto ya ha
    #     pagado otras veces. Solo puede REDUCIR lo que se borra: ninguna garantia se relaja.
    if getattr(nodo, "decorator_list", []):
        nombres = ", ".join(ast.unparse(d).split("(")[0] for d in nodo.decorator_list)
        return False, (f"{simbolo!r} esta decorado ({nombres}): un decorador puede registrarlo por "
                       f"efecto lateral, asi que «nadie lo llama» no significa que este muerto")

    # 6 · **La comprobacion estructural**, y la unica que protege de errores aun no cometidos: si
    #     quitarlo deja un fichero que Python ya no acepta, no se quita. Ejemplo real: una clase cuyo
    #     unico cuerpo es el metodo que se pretende borrar.
    try:
        ast.parse(quitar_simbolo(fuente, simbolo, forma))
    except SyntaxError as exc:
        return False, f"quitar {simbolo!r} deja un fichero que no compila: {exc}"
    return True, ""


def es_sustituible(fuente: str, buscar: str, sustituir: str) -> tuple[bool, str]:
    """**La segunda barrera de la operacion constructiva.** ¿Es esta sustitucion aplicable sin que
    nadie tenga que elegir nada?

    Las cuatro condiciones son las que `mutar.py` ya exigia, y cada una cierra una forma de que la
    operacion deje de ser determinista:

    1. un patron vacio no selecciona: selecciona **todo**;
    2. un patron que aparece N veces obliga a elegir cual, y elegir es interpretar;
    3. una sustitucion identica no cambia nada y sin embargo se registraria como cambio aplicado;
    4. si el resultado no compila, el arbol queda roto — el mismo criterio estructural que protege
       a `es_eliminable`.

    Devuelve `(puede, motivo)`. Un rechazo sin motivo obliga a quien lo lea a averiguarlo."""
    if not buscar:
        return False, "el patron a buscar esta vacio: no selecciona nada, o lo selecciona todo"
    if buscar == sustituir:
        return False, "'buscar' y 'sustituir' son identicos: no habria cambio que verificar"
    apariciones = fuente.count(buscar)
    if apariciones == 0:
        return False, "el patron no aparece en el fichero"
    if apariciones > 1:
        return False, (f"el patron aparece {apariciones} veces: elegir cual sustituir seria "
                       f"interpretar, y esta operacion tiene que ser determinista")
    try:
        ast.parse(sustituir_texto(fuente, buscar, sustituir))
    except SyntaxError as exc:
        return False, f"la sustitucion deja un fichero que no compila: {exc}"
    return True, ""


def sustituir_texto(texto: str, buscar: str, sustituir: str) -> str:
    """**Una sola aparicion, la que `es_sustituible` verifico que era unica.** Sabe *como* sustituir,
    no *si* se debe: eso lo decide la barrera, y vive en un solo sitio."""
    return texto.replace(buscar, sustituir, 1)


def _nodo_de(arbol, simbolo: str, clase: str):
    """El nodo que ocupa el simbolo, o `None`. `metodo` viene como `Clase.metodo`."""
    if clase == "metodo" and "." in simbolo:
        contenedor, nombre = simbolo.split(".", 1)
        for c in arbol.body:
            if isinstance(c, ast.ClassDef) and c.name == contenedor:
                for m in c.body:
                    if isinstance(m, ast.FunctionDef) and m.name == nombre:
                        return m
        return None
    for n in arbol.body:
        if clase == "funcion" and isinstance(n, ast.FunctionDef) and n.name == simbolo:
            return n
        if clase == "clase" and isinstance(n, ast.ClassDef) and n.name == simbolo:
            return n
        if clase == "constante" and isinstance(n, ast.Assign):
            if any(isinstance(x, ast.Name) and x.id == simbolo for x in n.targets):
                return n
        if clase == "import" and isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if (a.asname or a.name.split(".")[0]) == simbolo:
                    return n
    return None


def _existe_simbolo(texto: str, simbolo: str, clase: str) -> bool:
    """Si el simbolo sigue **declarado** en el fuente, segun el parser. Un fichero que ya no compila
    se trata como «no se sabe», y quien pregunta debe revertir: afirmar que el simbolo desaparecio
    porque el fichero se rompio seria dar por buena una destruccion."""
    try:
        return _nodo_de(ast.parse(texto), simbolo, clase) is not None
    except SyntaxError:                                # pragma: no cover - fichero roto
        return False


def quitar_simbolo(texto: str, simbolo: str, clase: str = "funcion") -> str:
    """Borra **el rango de lineas que el parser dice que ocupa el simbolo**, ni una mas.

    Sabe **como** borrar, no **si** se debe: eso lo decide `es_eliminable()`, y vive en un solo sitio.
    Tener aqui una copia de sus reglas dejo sobrevivir un mutante —cada guardia tapaba al otro, asi
    que quitar uno no cambiaba nada— y ese es el defecto que este proyecto lleva cinco auditorias
    corrigiendo: la regla escrita dos veces, con la copia que falta convertida en ruta abierta.

    La version anterior usaba una expresion regular que buscaba «hasta el siguiente `def` o `class`».
    Para una funcion suelta funciona; para un metodo dentro de una clase, o para un import en medio
    de un bloque, no hay patron fiable y lo que hay en medio se va por delante.

    **Fail-closed:** si el simbolo no aparece, el texto vuelve intacto. Un borrado aproximado es peor
    que ninguno — deja el arbol roto y la verificacion tendria que descubrirlo despues."""
    try:
        arbol = ast.parse(texto)
    except SyntaxError:                                # pragma: no cover - fichero ya roto
        return texto
    nodo = _nodo_de(arbol, simbolo, clase)
    if nodo is None:
        return texto

    if clase == "import" and len(nodo.names) > 1:
        # Un `import a, b` del que solo sobra uno: se reescribe la linea sin el, en vez de borrarla
        # entera y llevarse por delante el que si se usa.
        quedan = [a for a in nodo.names if (a.asname or a.name.split(".")[0]) != simbolo]
        nueva = ("from " + (nodo.module or "") + " import " if isinstance(nodo, ast.ImportFrom)
                 else "import ") + ", ".join(
                     a.name + (f" as {a.asname}" if a.asname else "") for a in quedan)
        lineas = texto.splitlines(keepends=True)
        lineas[nodo.lineno - 1] = nueva + "\n"
        return "".join(lineas)

    lineas = texto.splitlines(keepends=True)
    inicio, fin = nodo.lineno - 1, (nodo.end_lineno or nodo.lineno)
    # Se arrastran las lineas en blanco que quedan justo detras: dejarlas produce tres saltos
    # seguidos y un `ruff` en rojo, y una limpieza que ensucia el formato no esta limpia.
    while fin < len(lineas) and not lineas[fin].strip():
        fin += 1
    return "".join(lineas[:inicio] + lineas[fin:])


# ----------------------------------------------- candidato aislado (DP-CANDIDATO-AISLADO, alt. A) --
#
# `ejecutar` escribia el candidato SOBRE el arbol vivo y verificaba alli: cualquier lector concurrente
# veia codigo sin verificar y un SIGKILL durante la verificacion lo dejaba sin respaldo ni rastro
# (`milestones/m3-entry/evidencia-candidato-aislado-2026-10-22/`). Ahora el candidato se escribe y se
# verifica en una COPIA fuera del repo, y el vivo solo se toca al promover: temporal en el mismo
# directorio + `os.replace`, con un diario de intencion (original incluido) en disco ANTES de tocarlo.
# La atomicidad es **por fichero**: `ejecutar` modifica uno solo; esto no es una transaccion multi-fichero.
#
# **Limites declarados** (no se ocultan, se publican en el resultado y en el evento):
# - `verificacion_aislada`: solo es True si el verificador RECIBIO la raiz de la copia. Uno heredado sin
#   parametros mide el arbol vivo, que aun tiene el original: no es evidencia del candidato.
# - `ejecucion_confinada`: lo declara la verificacion (`informe.confinada`; este modulo NO la deriva de
#   nada propio). POLITICA: la verificacion por contrato (`review._verificador_de_review`) es CONFINADA
#   ESTRICTA OBLIGATORIA (`aislamiento.preparar_estricto`, FASE B). Lo que GARANTIZA, tambien para hijos
#   y nietos: ESCRITURA solo en la copia (+ el temporal del informe, que es su TMPDIR) y `/dev/null`;
#   LECTURA solo del interprete, la stdlib, las librerias dinamicas, los paquetes de pytest y la copia
#   (no `/etc`, `/proc`, `$HOME`, `sys.path` del padre ni el plano vivo); RED denegada (Landlock TCP +
#   seccomp: TCP, UDP, unix, netlink, packet, io_uring); senales y sockets unix abstractos acotados.
#   Sin TODOS esos controles no se ejecuta ninguna prueba y se rechaza (`confinamiento_no_disponible`).
#   Limites no mitigados: ver `aislamiento.py`. Un `bool` heredado o un verificador explicito del
#   llamante no declaran confinamiento: False.
# - El rechazo se registra como `cambio_aplicado` con `revertido=True` (compatibilidad con los lectores
#   actuales), no como el `cambio_rechazado` que propone el DP; el porque va en `motivo`.

#: Los estados que una verificacion puede declarar. Cualquier otro se trata como fallo (fail-closed).
ESTADOS_VERIFICACION = ("sano", "fallo", "error_infraestructura", "no_aislable", "sin_confinamiento")


@dataclasses.dataclass(frozen=True)
class ResultadoVerificacion:
    """Lo que una verificacion DICE que ocurrio (no lo que se pretendia): `ejecutar` deriva de aqui
    `verificacion_aislada`, `ejecucion_confinada`, `verificacion_sana` y `motivo`.

    `estado`: `sano` | `fallo` (las pruebas no pasan) | `error_infraestructura` (excepcion, plazo
    agotado: no se midio) | `no_aislable` (las pruebas no caben en la copia: no se ejecutaron) | `sin_confinamiento` (no hay
    Landlock efectivo: no se ejecutaron, no se rebaja en silencio).
    Una verificacion que devuelve un simple `bool` sigue valiendo (compatibilidad)."""
    estado: str
    aislada: bool
    confinada: bool = False
    detalle: str = ""


_COPIA_SIN_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git",
                             ".venv", "node_modules", "secrets", ".ssh"})
#: Estado real y kill switch: no viajan a la copia (la copia no debe poder leerlos ni escribirlos).
_COPIA_SIN_FICHEROS = frozenset({".control-plane.lock", "PARADA"})
#: Se copian (solo LECTURA del real: lo que se escriba queda en la copia) para que las pruebas que leen
#: el log del directorio de su modulo vean lo mismo, pero NO entran en la precondicion de hashes: el
#: real crece legitimamente mientras se verifica.
_COPIA_SOLO_LECTURA = frozenset({"estado.json", "eventos.jsonl"})
_COPIA_SENSIBLE = (".env*", "*secret*", "*token*", "*.key", "*.pem", "credentials*", ".netrc",
                   "id_rsa*", "*.p12", "*.pfx")
_MARCA_COPIA = ".aura-candidato-marca"
_BLOQUEO = "BLOQUEADO"
_CERROJO = ".cerrojo"
_SUBDIR_ESTADO = "aura-autoconstruccion"
_EDAD_COPIA_HUERFANA_S = 3600
_REINTENTOS_CERROJO = 5
_CLAVES_DIARIO = ("id_op", "directorio", "ruta", "propuesta", "sha_original", "sha_candidato", "tmp",
                  "estado")


class _DiarioInvalido(Exception):
    """El diario no se puede creer: ruta, temporal, identidad o forma no son los que escribimos."""


class _BaseCambiada(Exception):
    """El vivo ya no es el original sobre el que se derivo el candidato verificado."""


def _sha(datos: bytes | None) -> str | None:
    return None if datos is None else hashlib.sha256(datos).hexdigest()


def _sha_de(ruta) -> str | None:
    try:
        return _sha(pathlib.Path(ruta).read_bytes())
    except FileNotFoundError:
        return None


def _es_sensible(nombre: str) -> bool:
    return any(fnmatch.fnmatch(nombre.lower(), patron) for patron in _COPIA_SENSIBLE)


def _fsync_dir(directorio: pathlib.Path) -> None:
    fd = os.open(directorio, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _escribir_atomico(destino: pathlib.Path, datos: bytes, tmp: pathlib.Path, modo: int) -> None:
    """Temporal EN EL MISMO DIRECTORIO, creado con `O_EXCL|O_NOFOLLOW` (un enlace plantado con ese nombre
    no se sigue: la creacion falla), fsync, `os.replace` y fsync del directorio. Solo se borra el
    temporal si lo creo esta llamada."""
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(datos)
            fh.flush()
            os.fchmod(fh.fileno(), modo)
            os.fsync(fh.fileno())
        os.replace(tmp, destino)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(destino.parent)


def _escribir_privado(destino: pathlib.Path, datos: bytes) -> None:
    """Fichero 0600, atomico, con temporal de nombre unico."""
    _escribir_atomico(destino, datos, destino.with_name(f"{destino.name}.{secrets.token_hex(4)}.tmp"),
                      0o600)


def _raiz_estado() -> pathlib.Path:
    """Estado de las promociones, FUERA del repo. Con `AURA_AUTOCONSTRUCCION_ESTADO` se trabaja en un
    subdirectorio PROPIO: nunca se cambian permisos de un directorio que ya existia."""
    base = os.environ.get("AURA_AUTOCONSTRUCCION_ESTADO")
    if base:
        return pathlib.Path(base) / _SUBDIR_ESTADO
    xdg = os.environ.get("XDG_STATE_HOME") or str(pathlib.Path.home() / ".local" / "state")
    return pathlib.Path(xdg) / "aura" / "autoconstruccion"


def _dir_estado(directorio) -> pathlib.Path:
    clave = hashlib.sha256(str(pathlib.Path(directorio).resolve()).encode()).hexdigest()[:16]
    return _raiz_estado() / clave


def _es_dir_propio(ruta: pathlib.Path) -> bool:
    """Directorio real (no enlace) y nuestro."""
    try:
        st = os.lstat(ruta)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()


def _asegurar_dir(ruta: pathlib.Path) -> None:
    """Crea `ruta` 0700 si no existe (chmod SOLO de lo que se creo aqui); si existia, exige que sea un
    directorio real y propio."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.mkdir(ruta, 0o700)
        os.chmod(ruta, 0o700)
    except FileExistsError:
        pass
    if not _es_dir_propio(ruta):
        raise PromocionesBloqueadas(f"{ruta} no es un directorio propio (enlace u otro dueño): no se usa")


def _asegurar_estado(estado: pathlib.Path) -> None:
    _asegurar_dir(estado.parent)
    _asegurar_dir(estado)


@contextlib.contextmanager
def _cerrojo(estado: pathlib.Path, bloqueante: bool):
    """`flock` sobre un centinela del directorio de estado. Cede `True` si se tomo; con
    `bloqueante=False` cede `False` (sin tomarlo) si otro proceso lo tiene o el estado no existe.

    Como el estado vacio se retira (`_retirar_si_vacio`), tras obtener el `flock` se comprueba que el
    inodo del descriptor sigue siendo el del path: si otro proceso lo borro y recreo, el cerrojo que
    tenemos ya no excluye a nadie y se reintenta (bucle acotado)."""
    ruta = estado / _CERROJO
    for _ in range(_REINTENTOS_CERROJO):
        if bloqueante:
            _asegurar_estado(estado)
        try:
            fd = os.open(ruta, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        except FileNotFoundError:
            if bloqueante:
                continue
            yield False
            return
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | (0 if bloqueante else fcntl.LOCK_NB))
            except BlockingIOError:
                yield False
                return
            try:
                vigente = os.fstat(fd).st_ino == os.lstat(ruta).st_ino
            except FileNotFoundError:
                vigente = False
            if not vigente:
                continue
            yield True
            return
        finally:
            os.close(fd)                                  # cerrar el descriptor libera el cerrojo
    if bloqueante:
        raise PromocionesBloqueadas(f"no se pudo tomar el cerrojo de {estado}")
    yield False


def _retirar_si_vacio(estado: pathlib.Path) -> None:
    """Con el cerrojo tomado: si el directorio de estado de este directorio solo contiene el centinela
    (sin operaciones ni BLOQUEADO), se retira. El directorio base, que puede ser compartido, no."""
    try:
        if [q.name for q in estado.iterdir()] == [_CERROJO]:
            (estado / _CERROJO).unlink()
            estado.rmdir()
    except OSError:
        pass


def _guardar_diario(op: pathlib.Path, diario: dict) -> None:
    _escribir_privado(op / "diario.json", json.dumps(diario, sort_keys=True).encode("utf-8"))


def _bloquear(estado: pathlib.Path, motivo: str, id_op: str) -> None:
    _asegurar_estado(estado)
    _escribir_privado(estado / _BLOQUEO, json.dumps({"id_op": id_op, "motivo": motivo}).encode("utf-8"))


def _restaurar(destino: pathlib.Path, original: bytes, id_op: str) -> bool:
    """Devuelve el original al vivo y VERIFICA el sha. `False` si no se pudo o no coincide."""
    try:
        modo = stat.S_IMODE(destino.stat().st_mode) if destino.exists() else 0o644
        tmp = destino.with_name(f".{destino.name}.aura-rest-{id_op}-{secrets.token_hex(4)}.tmp")
        _escribir_atomico(destino, original, tmp, modo)
        return _sha_de(destino) == _sha(original)
    except Exception:                                     # noqa: BLE001 — fallar aqui = no restaurado
        return False


def _validar_diario(directorio: pathlib.Path, op: pathlib.Path) -> tuple[dict, pathlib.Path, bytes]:
    """**El diario esta en disco y se puede forjar o corromper: no se confia en el.** Antes de actuar,
    todo lo que dice debe ser lo que `_promover` escribe. Lanza `_DiarioInvalido` con el motivo."""
    if op.is_symlink() or not op.is_dir():
        raise _DiarioInvalido("la operacion no es un directorio real")
    try:
        diario = json.loads((op / "diario.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _DiarioInvalido(f"diario ilegible o corrupto: {exc}") from None
    if not isinstance(diario, dict) or any(not isinstance(diario.get(k), str) for k in _CLAVES_DIARIO):
        raise _DiarioInvalido("faltan claves del diario o tienen un tipo inesperado")
    if diario["estado"] not in ("preparado", "promovido"):
        raise _DiarioInvalido(f"estado desconocido {diario['estado']!r}")
    if not (re.fullmatch(r"[0-9a-f]{64}", diario["sha_original"])
            and re.fullmatch(r"[0-9a-f]{64}", diario["sha_candidato"])):
        raise _DiarioInvalido("los sha no tienen forma de sha256")
    if not re.fullmatch(r"[0-9a-f]{16}", diario["id_op"]) or diario["id_op"] != op.name:
        raise _DiarioInvalido("id_op no coincide con el directorio de la operacion")
    raiz = directorio.resolve()
    if diario["directorio"] != str(raiz):
        raise _DiarioInvalido("el diario es de otro directorio")
    destino = pathlib.Path(diario["ruta"]).resolve()
    try:
        rel = destino.relative_to(raiz)
    except ValueError:
        raise _DiarioInvalido("la ruta cae fuera del directorio") from None
    # La misma zona que `ejecutar` exige: gobernanza y producto no se escriben ni desde un diario.
    if not zona_permitida(destino, raiz=directorio):
        raise _DiarioInvalido("la ruta esta fuera de la zona permitida")
    if (str(destino) != diario["ruta"] or destino.name in orquestador._INTOCABLES
            or destino.name in _COPIA_SIN_FICHEROS or _es_sensible(destino.name)
            or any(c.lower() in _COPIA_SIN_DIRS for c in rel.parts[:-1])):
        raise _DiarioInvalido("la ruta es intocable, excluida o no esta resuelta")
    if diario["tmp"] != str(destino.with_name(f".{destino.name}.aura-cand-{diario['id_op']}.tmp")):
        raise _DiarioInvalido("el temporal no es el que se habria creado")
    respaldo = op / "original"
    try:
        original = respaldo.read_bytes() if not respaldo.is_symlink() else None
    except OSError:
        original = None
    if original is None or _sha(original) != diario["sha_original"]:
        raise _DiarioInvalido("el respaldo `original` falta o no coincide con su sha")
    return diario, destino, original


def _vivo(pid: int) -> bool:
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _barrer_copias_huerfanas() -> None:
    """Borra SOLO copias `aura-candidato-*` propias: marca valida, dueño nuestro, pid muerto y mas de
    una hora. Cualquier duda => no se toca."""
    for copia in pathlib.Path(tempfile.gettempdir()).glob("aura-candidato-*"):
        try:
            if copia.is_symlink() or not _es_dir_propio(copia):
                continue
            marca = json.loads((copia / _MARCA_COPIA).read_text(encoding="utf-8"))
            if (not isinstance(marca.get("marca"), str) or not isinstance(marca.get("pid"), int)
                    or not isinstance(marca.get("t"), (int, float)) or not math.isfinite(marca["t"])):
                continue
            if time.time() - marca["t"] < _EDAD_COPIA_HUERFANA_S or _vivo(marca["pid"]):
                continue
            shutil.rmtree(copia, ignore_errors=True)
        except (OSError, ValueError):
            continue


def recuperar(directorio) -> dict:
    """Resuelve los diarios de promocion pendientes de ESTE directorio. **Idempotente.**

    `preparado`: vivo == original -> nada que deshacer; vivo == candidato -> se restaura el original
    (ADR-0003); cualquier otro contenido es AMBIGUO -> marca `BLOQUEADO`, se conserva todo.
    `promovido`: vivo == candidato -> se confirma (y se registra `cambio_aplicado` si no constaba).
    Un diario que no supera `_validar_diario` (forjado, corrupto, parcial) bloquea sin tocar nada.
    Con PARADA armada NO escribe: solo informa. Si otro proceso tiene el cerrojo, no toca sus diarios.
    Barre ademas las copias `aura-candidato-*` huerfanas propias (pid muerto, > 1 h)."""
    directorio = pathlib.Path(directorio)
    estado = _dir_estado(directorio)
    informe = {"pendientes": 0, "resultados": [], "escribio": False, "bloqueado": False,
               "ocupado": False}
    if orquestador.parada_solicitada(directorio):
        return {**informe, "bloqueado": (estado / _BLOQUEO).exists(),
                "pendientes": len(_operaciones_de(estado))}
    _barrer_copias_huerfanas()
    if not estado.exists() and not estado.is_symlink():
        return informe
    if not _es_dir_propio(estado) or (estado / _BLOQUEO).exists():
        return {**informe, "bloqueado": True}
    with _cerrojo(estado, bloqueante=False) as tomado:
        if not tomado:
            return {**informe, "ocupado": True}
        for op in _operaciones_de(estado):
            informe["pendientes"] += 1
            if not _resolver(directorio, estado, op, informe):
                break
        _retirar_si_vacio(estado)
    return informe


def _operaciones_de(estado: pathlib.Path) -> list[pathlib.Path]:
    if not _es_dir_propio(estado):
        return []
    return sorted(p for p in estado.iterdir() if p.is_symlink() or p.is_dir())


def _bloqueo_de_recuperacion(directorio, estado, op, informe, motivo, evento="promociones_bloqueadas",
                             datos=None) -> bool:
    cp.registrar_evento(directorio, evento, {"id_op": op.name, "motivo": motivo, **(datos or {})})
    _bloquear(estado, motivo, op.name)
    informe.update(bloqueado=True, escribio=True)
    return False


#: Valor de `correlacion` que marca un `cambio_aplicado` POSTERIOR al contrato sin tarea/intento: el planificador
#: no lo atribuye nunca (ni por orden). Solo un evento SIN ninguna clave de correlacion es anterior al contrato.
_SIN_CORRELACION = "ninguna"


def _correlacion_del_diario(diario: dict) -> dict:
    """Lo que el `cambio_aplicado` recuperado debe llevar para no atribuirse mal. `{tarea, intento}` si el diario
    los trae bien formados (via review/motor); si no, la ausencia EXPLICITA (`tarea`/`intento` nulos,
    `correlacion: "ninguna"` y la `via` del diario). `{}` solo para un diario anterior al contrato (sin ninguna
    de las claves): ese sigue recuperandose como siempre."""
    if _correlacion_valida(diario.get("tarea"), diario.get("intento")):
        return {"tarea": diario["tarea"], "intento": diario["intento"]}
    if (diario.get("correlacion") == _SIN_CORRELACION or diario.get("via") is not None
            or "tarea" in diario or "intento" in diario):          # mal formada = ausente, pero explicita
        explicita = {"tarea": None, "intento": None, "correlacion": _SIN_CORRELACION}
        if diario.get("via") is not None:
            explicita["via"] = diario["via"]
        return explicita
    return {}


def _verificacion_del_diario(diario: dict) -> dict | None:
    """La verificacion que `_promover` midio, o `None` si falta algo o no es del tipo exacto. Estricto:
    `efecto_verificado` y `verificacion_sana` solo valen si son `True` (un diario promovido solo existe si
    ambos lo fueron) y los otros dos deben ser booleanos reales; cualquier otra cosa se trata como ausente."""
    if diario.get("efecto_verificado") is not True or diario.get("verificacion_sana") is not True:
        return None
    aislada, confinada = diario.get("verificacion_aislada"), diario.get("ejecucion_confinada")
    if not isinstance(aislada, bool) or not isinstance(confinada, bool):
        return None
    return {"efecto_verificado": True, "verificacion_sana": True, "verificacion_aislada": aislada,
            "ejecucion_confinada": confinada}


def _es_el_cambio_de(evento: dict, id_propuesta: str, correlacion: dict) -> bool:
    """I2 · un intento, un desenlace. Con correlacion, la clave es `(tarea, intento)`; sin ella (diario
    anterior al contrato), la propuesta, como siempre."""
    if evento["tipo"] != "cambio_aplicado":
        return False
    d = evento["datos"]
    if isinstance(correlacion.get("tarea"), str):
        return d.get("tarea") == correlacion["tarea"] and d.get("intento") == correlacion["intento"]
    return d.get("id") == id_propuesta and not d.get("revertido")


def _resolver(directorio, estado, op, informe) -> bool:
    """Resuelve UN diario. `False` si hay que parar (bloqueo)."""
    try:
        diario, destino, original = _validar_diario(directorio, op)
    except _DiarioInvalido as exc:
        return _bloqueo_de_recuperacion(directorio, estado, op, informe, str(exc))
    vivo = _sha_de(destino)
    datos = {"id": diario["propuesta"], "fichero": str(destino), "id_op": diario["id_op"]}
    if diario["estado"] == "preparado" and vivo == diario["sha_original"]:
        resultado = "sin_cambios"
        tmp = pathlib.Path(diario["tmp"])
        if tmp.is_file() and not tmp.is_symlink():          # temporal huerfano que registro el diario
            tmp.unlink(missing_ok=True)
    elif diario["estado"] == "preparado" and vivo == diario["sha_candidato"]:
        if not _restaurar(destino, original, diario["id_op"]):
            return _bloqueo_de_recuperacion(directorio, estado, op, informe,
                                            "restauracion fallida al arranque",
                                            evento="restauracion_fallida", datos=datos)
        resultado = "restaurado"
    elif diario["estado"] == "promovido" and vivo == diario["sha_candidato"]:
        correlacion = _correlacion_del_diario(diario)
        constaba = any(_es_el_cambio_de(e, datos["id"], correlacion) for e in cp.leer_eventos(directorio))
        if not constaba:
            # I3: la verificacion es COPIA LITERAL de lo que midio `_promover`; si el diario no la trae
            # (anterior al contrato, o mal formada) no se inventa: `verificacion_no_registrada` y la tarea
            # queda `resultado_ambiguo`. `recuperado: true` hace auditable toda finalizacion por esta via.
            verif = _verificacion_del_diario(diario)
            cp.registrar_evento(directorio, "cambio_aplicado",
                                {**datos, "revertido": False, "promovido": True, "recuperado": True,
                                 **correlacion,
                                 **(verif if verif is not None else {"verificacion_no_registrada": True})})
        resultado = "promocion_confirmada"
    else:
        return _bloqueo_de_recuperacion(directorio, estado, op, informe, "contenido ambiguo",
                                        datos={**datos, "estado": diario["estado"]})
    cp.registrar_evento(directorio, "recuperacion_al_arranque", {**datos, "resultado": resultado})
    shutil.rmtree(op, ignore_errors=True)                 # solo despues de registrar el evento
    informe["resultados"].append(resultado)
    informe["escribio"] = True
    return True


def _crear_copia(directorio: pathlib.Path, rel: pathlib.PurePath):
    """Copia el arbol a un `mkdtemp` fuera del repo. Devuelve `(raiz_copia, marca, manifiesto, omitidos)`.

    Sin symlinks (ni se siguen ni se copian), sin cache, sin estado real, sin PARADA y sin nombres
    sensibles. El manifiesto (ruta relativa -> sha256 de lo COPIADO) es la precondicion de la promocion.
    Si algo falla a mitad, la copia propia se borra."""
    copia = pathlib.Path(tempfile.mkdtemp(prefix="aura-candidato-"))
    marca = secrets.token_hex(16)
    manifiesto: dict[str, str] = {}
    omitidos = 0
    try:
        (copia / _MARCA_COPIA).write_text(
            json.dumps({"marca": marca, "pid": os.getpid(), "t": time.time()}), encoding="utf-8")
        for raiz, dirs, ficheros in os.walk(directorio, followlinks=False):
            base = pathlib.Path(raiz)
            conservar = []
            for n in dirs:
                if n.lower() in _COPIA_SIN_DIRS:
                    continue
                if (base / n).is_symlink():
                    omitidos += 1
                    continue
                conservar.append(n)
            dirs[:] = conservar
            for n in ficheros:
                origen = base / n
                if n in _COPIA_SIN_FICHEROS or n.endswith(".pyc"):
                    continue
                if origen.is_symlink() or _es_sensible(n):
                    omitidos += 1
                    continue
                relativa = origen.relative_to(directorio)
                (copia / relativa).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origen, copia / relativa)
                # Solo los de la RAIZ de la copia quedan fuera del manifiesto: uno anidado es codigo/datos
                # de verdad y si cambia entre la copia y la promocion la base ya no es la verificada.
                if relativa.as_posix() not in _COPIA_SOLO_LECTURA or relativa.as_posix() == rel.as_posix():
                    manifiesto[relativa.as_posix()] = _sha_de(copia / relativa)
        if rel.as_posix() not in manifiesto:
            raise CandidatoNoAislable(
                f"{rel} no puede copiarse para verificarse aislado (nombre sensible, enlace o excluido)")
    except BaseException:
        shutil.rmtree(copia, ignore_errors=True)
        raise
    return copia, marca, manifiesto, omitidos


def _base_intacta(directorio: pathlib.Path, manifiesto: dict) -> list[str]:
    """Rutas copiadas cuyo sha en el vivo ya no es el de la copia."""
    return [r for r, sha in manifiesto.items() if _sha_de(directorio / r) != sha]


def _acepta_raiz(verificacion) -> bool:
    try:
        parametros = inspect.signature(verificacion).parameters.values()
    except (TypeError, ValueError):
        return False
    # Un parametro con valor por defecto (`timeout=5`) no es la raiz; solo cuenta uno obligatorio o
    # uno llamado `raiz`.
    return any(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
               and (p.default is p.empty or p.name == "raiz") for p in parametros)


def _exigir_raiz(verificacion) -> None:
    """`VerificadorSinRaiz` si hay un verificador que no acepta la raiz de la copia. `None` (sin
    verificador: «no se midio») no es un verificador y se rechaza despues, por `no_medido`."""
    if verificacion and not _acepta_raiz(verificacion):
        raise VerificadorSinRaiz(
            f"el verificador {getattr(verificacion, '__name__', repr(verificacion))!r} no acepta la raiz "
            f"de la copia: mediria el arbol vivo (que aun tiene el original), no el candidato. "
            f"Declare un parametro obligatorio, p. ej. `lambda raiz: ...`. No se ejecuta nada")


def _promover(directorio: pathlib.Path, destino: pathlib.Path, propuesta: dict, candidato: bytes,
              efecto_en, sha_esperado: str, verif: dict | None = None) -> pathlib.Path | None:
    """Promueve el candidato al vivo (con el cerrojo ya tomado). Devuelve el directorio del diario si
    quedo promovido (lo cierra quien llama, DESPUES de registrar el evento); `None` si se revirtio (y
    verifico). `_BaseCambiada` si el vivo ya no es el original verificado. `RestauracionFallida` si no
    pudo devolver el original. Solo `Exception` se gestiona aqui: una muerte (SystemExit,
    KeyboardInterrupt, SIGKILL) la resuelve `recuperar` desde el diario."""
    original = destino.read_bytes()
    if _sha(original) != sha_esperado:
        raise _BaseCambiada()                             # no se guarda en el diario algo no verificado
    id_op = secrets.token_hex(8)
    estado = _dir_estado(directorio)
    op = estado / id_op
    _asegurar_dir(op)
    tmp = destino.with_name(f".{destino.name}.aura-cand-{id_op}.tmp")
    diario = {"id_op": id_op, "directorio": str(directorio.resolve()), "ruta": str(destino),
              "propuesta": propuesta["id"], "sha_original": _sha(original),
              "sha_candidato": _sha(candidato), "tmp": str(tmp), "estado": "preparado"}
    if _correlacion_valida(propuesta.get("tarea"), propuesta.get("intento")):
        diario.update({"tarea": propuesta["tarea"], "intento": propuesta["intento"]})
    else:
        # La AUSENCIA de correlacion tambien se guarda: un recuperado sin ella no se atribuye a ninguna tarea.
        diario["correlacion"] = _SIN_CORRELACION
    if propuesta.get("via") is not None:
        diario["via"] = propuesta["via"]
    _escribir_privado(op / "original", original)
    _guardar_diario(op, diario)                           # ANTES de tocar el vivo
    datos = {"id": propuesta["id"], "fichero": str(destino), "id_op": id_op}
    try:
        _escribir_atomico(destino, candidato, tmp, stat.S_IMODE(destino.stat().st_mode))
        tras = destino.read_bytes()
        if _sha(tras) != diario["sha_candidato"] or not efecto_en(tras.decode("utf-8")):
            raise OSError("la relectura del vivo no coincide con el candidato verificado")
    except Exception as exc:                              # noqa: BLE001 — cualquier fallo => restaurar
        if not _restaurar(destino, original, id_op):
            cp.registrar_evento(directorio, "restauracion_fallida", {**datos, "motivo": str(exc)})
            _bloquear(estado, "restauracion fallida", id_op)
            raise RestauracionFallida(
                f"{destino.name}: la promocion fallo ({exc}) y NO se pudo restaurar el original; "
                f"respaldo conservado en {op}") from exc
        cp.registrar_evento(directorio, "promocion_revertida", {**datos, "motivo": str(exc)})
        shutil.rmtree(op, ignore_errors=True)
        return None
    # D2: el diario promovido guarda lo que se MIDIO (valores reales; nunca un `true` por defecto). Sin
    # `verif` no se escribe ningun campo: un diario sin ellos se recupera como resultado ambiguo.
    _guardar_diario(op, {**diario, "estado": "promovido", **(verif or {})})
    return op


def ejecutar(directorio, propuesta: dict, autoridad: str, verificacion=None) -> dict:
    """Verifica el cambio en una COPIA aislada y solo lo promueve al fichero vivo si el efecto y la
    verificacion son buenos. **El vivo nunca contiene un candidato sin verificar.**

    `verificacion` es lo que decide si el arbol quedo sano —la bateria de pruebas, en uso real—. Se
    llama `verificacion(raiz_copia)`; **un verificador que no acepta la raiz lanza `VerificadorSinRaiz`**
    (antes de crear la copia y sin llamarlo: el vivo queda intacto). La via heredada `lambda: ...`
    media el vivo y se retiro (PROMPT 03, Fase A). Si devuelve falso, lanza o no existe, el vivo queda byte a byte como estaba. La promocion es atomica
    (temporal + `os.replace`) con diario de intencion en disco y precondicion de hashes; si falla se
    restaura el original y se verifica su sha (`RestauracionFallida` si no se puede). La atomicidad es
    **por fichero**: `ejecutar` modifica uno solo; no es una transaccion multi-fichero.

    **Lo que el resultado declara, y no hay que suponer:** `verificacion_aislada` es True solo si el
    verificador recibio la raiz de la copia (siempre, salvo un `bool` heredado que ya no se admite
    sin raiz); `ejecucion_confinada` es False (no hay Landlock); si se rechaza, `motivo` dice por que, y
    el rechazo se registra como `cambio_aplicado` con `revertido=True` (compatibilidad), no como el
    `cambio_rechazado` del DP."""
    directorio = pathlib.Path(directorio)
    ruta = pathlib.Path(propuesta["fichero"])
    if not zona_permitida(ruta, raiz=directorio):
        raise ZonaProhibida(
            f"{ruta} esta fuera de alcance. La gobernanza no se modifica ni con autorizacion: "
            f"cambiarla es un acto del CEO por acta, no una tarea que se encargue a un ejecutor")
    if not esta_autorizada(directorio, propuesta["id"]):
        raise SinAutorizacion(
            f"la propuesta {propuesta['id']!r} no tiene autorizacion humana registrada")
    # **LA PARADA SE COMPRUEBA DONDE PASA TODO EL MUNDO (ALERTA-005; CEO, 2026-09-16).** Estaba
    # consultada al DESPERTAR (`motor_autonomia`, `despertador`, `observatorio`) pero no aqui, que es
    # la unica puerta de escritura. Medido: con `PARADA` armada, `ejecutar()` escribia el fichero. Una
    # parada que solo impide empezar no es una parada: es un horario. Se comprueba DESPUES de zona y
    # autorizacion —para que el motivo del rechazo sea el mas especifico— y ANTES de tocar el disco.
    # **LOS INTOCABLES SE RESPETAN DONDE SE ESCRIBE (ALERTA-005; CEO, 2026-09-16).** `_INTOCABLES`
    # existia desde F2 y NO protegia nada en esta ruta: `ejecutar` nunca la miraba. Demostrado
    # ejecutando en una auditoria independiente: el ejecutor reescribio un fichero llamado
    # `orquestador.py` —que si esta en la tupla— porque la lista solo se consultaba en la
    # clasificacion de `contrato.evaluar` y en `Orquestador.puede_tocar`, que no tiene ningun llamante
    # de produccion. `orquestador.py:56-58` ya decia por que existe: *«un ejecutor que puede reescribir
    # cualquiera de los tres puede concederse lo que quiera en la iteracion siguiente»*. Aqui esa frase
    # se vuelve verdadera.
    #
    # **Se CONSULTA la tupla, no se copia** (lo fija `test_red_f5_evolucion_autonoma`: una segunda
    # lista seria una segunda verdad), y se compara el nombre RESUELTO, porque un symlink con otro
    # nombre apuntando al fichero real burlaria una comparacion del nombre escrito.
    #
    # **NO se amplia la lista aqui.** Ampliarla cambia un invariante publicado con cardinalidad en dos
    # actas cerradas y reduce el alcance operativo del anillo: eso es del CEO. Esto solo hace cumplir
    # la que ya estaba decidida.
    #
    # El CEO la amplio a OCHO el 2026-09-20 —en `orquestador.py`, donde vive, no aqui— anadiendo
    # `autoconstruccion.py` (este fichero), `review.py`, `ciclo_autonomo.py` y `planificador.py`. El
    # motivo esta escrito junto a la tupla; en una linea: el mecanismo que decide que se puede tocar
    # no se protegia a si mismo, y su proteccion dependia de que nunca existiera un contrato que lo
    # nombrara. **Los documentos que publicaron «4 entradas» siguen sin reconciliar** —dos actas
    # cerradas y el contrato de DR-E—: esa reconciliacion es del CEO y queda como DECISION_REQUIRED.
    try:
        nombre_real = ruta.resolve().name
    except OSError:                                   # enlace roto: se juzga el nombre escrito
        nombre_real = ruta.name
    if nombre_real in orquestador._INTOCABLES or ruta.name in orquestador._INTOCABLES:
        raise FicheroIntocable(
            f"{ruta.name} es intocable: decide la autoridad del propio anillo. Cambiarlo es un acto "
            f"del CEO por acta, no una tarea que se encargue a un ejecutor")
    if orquestador.parada_solicitada(directorio):
        raise ParadaActiva(
            f"PARADA armada en {directorio}: no se escribe nada. La parada detiene la ejecucion "
            f"efectiva, no solo el despertar")
    # Un diario huerfano de una ejecucion anterior se resuelve ANTES de seguir; si queda ambiguo o la
    # restauracion fallo, no se promueve nada mas (ADR-0003). Va tras PARADA: con ella armada no se escribe.
    if recuperar(directorio)["bloqueado"]:
        cp.registrar_evento(directorio, "promocion_rechazada_por_bloqueo",
                            {"id": propuesta["id"], "fichero": str(ruta)})
        raise PromocionesBloqueadas(
            f"hay una promocion pendiente o ambigua para {directorio}: una persona debe resolverla "
            f"y retirar la marca {_BLOQUEO} de {_dir_estado(directorio)}")

    # **Un verificador sin raiz mediria el vivo: se rechaza ANTES de leer, de crear la copia y de llamarlo.**
    _exigir_raiz(verificacion)

    # Bytes: el candidato deriva EXACTAMENTE de lo que se lee (sin traducir CRLF) y se compara por sha.
    original_b = ruta.read_bytes() if ruta.exists() else b""
    original = original_b.decode("utf-8")
    forma = propuesta.get("forma", "funcion")

    # **El despacho es cerrado.** Una operacion que no esta en el vocabulario no se interpreta: se
    # rechaza antes de leer nada mas. Fail-closed, y con el valor por defecto de siempre para que la
    # ruta de codigo muerto quede byte a byte como estaba.
    operacion = propuesta.get("operacion", "eliminar_codigo_muerto")
    if operacion not in OPERACIONES:
        raise OperacionDesconocida(
            f"{operacion!r} no esta en el vocabulario {OPERACIONES}: no se adivina que hacer")

    # **Segunda barrera, y va aqui porque por el ejecutor pasa cualquier ruta.** Es `ALERTA-005`
    # aplicada al contenido en vez de al estado: la puerta va donde pasa todo el mundo. Cada
    # operacion tiene la suya; ninguna se ejecuta sin pasar una.
    if operacion == "sustituir_texto":
        buscar, sustituir = propuesta.get("buscar", ""), propuesta.get("sustituir", "")
        puede, motivo = es_sustituible(original, buscar, sustituir)
        if not puede:
            cp.registrar_evento(directorio, "sustitucion_rechazada",
                                {"id": propuesta.get("id"), "fichero": str(ruta), "motivo": motivo})
            raise NoSustituible(f"no se sustituye en {ruta.name}: {motivo}")
        nuevo = sustituir_texto(original, buscar, sustituir)
    else:
        puede, motivo = es_eliminable(original, propuesta["simbolo"], forma)
        if not puede:
            cp.registrar_evento(directorio, "eliminacion_rechazada",
                                {"id": propuesta.get("id"), "simbolo": propuesta["simbolo"],
                                 "forma": forma, "fichero": str(ruta), "motivo": motivo})
            raise NoEliminable(
                f"no se elimina {propuesta['simbolo']!r} de {ruta.name}: {motivo}")
        nuevo = quitar_simbolo(original, propuesta["simbolo"], forma)
    # **El candidato se escribe SOLO en una copia fuera del repo** y se verifica alli; el vivo no se
    # toca hasta promover. Un destino que no cabe en la copia (fuera del directorio, o excluido por ser
    # sensible) no se puede aislar: fail-closed.
    destino = ruta.resolve()
    try:
        rel = destino.relative_to(directorio.resolve())
        copia, marca, manifiesto, _omitidos = _crear_copia(directorio.resolve(), rel)
    except (ValueError, CandidatoNoAislable) as exc:
        motivo = (f"{ruta} esta fuera de {directorio}: no se puede verificar aislado"
                  if isinstance(exc, ValueError) else str(exc))
        cp.registrar_evento(directorio, "candidato_no_aislable",
                            {"id": propuesta["id"], "fichero": str(ruta), "motivo": motivo})
        raise CandidatoNoAislable(motivo) from None
    try:
        if manifiesto[rel.as_posix()] != _sha(original_b):
            # El vivo cambio entre leer el original (del que sale el candidato) y copiarlo: lo que se
            # verificaria no derivaria de lo que se promueve. Se aborta sin escribir (actualizacion perdida).
            cp.registrar_evento(directorio, "promocion_abortada_base_cambiada",
                                {"id": propuesta["id"], "fichero": str(destino), "rutas": [rel.as_posix()]})
            registro = _registro(propuesta, ruta, False, None, autoridad, False, "base_cambiada")
            cp.registrar_evento(directorio, "cambio_aplicado", registro)
            return registro
        return _aplicar_en_copia(directorio, ruta, destino, rel, copia, manifiesto, propuesta,
                                 autoridad, verificacion, original, nuevo, operacion)
    finally:
        # Solo se borra lo que ESTA ejecucion creo: la copia lleva su marcador propio.
        try:
            leida = json.loads((copia / _MARCA_COPIA).read_text(encoding="utf-8"))
            if leida.get("marca") == marca:
                shutil.rmtree(copia, ignore_errors=True)
        except (OSError, ValueError):
            pass


#: Motivo publicado segun lo que declaro la verificacion (`None` = no hubo verificador).
_MOTIVOS = {None: "no_medido", "fallo": "verificacion", "error_infraestructura": "error_infraestructura",
            "no_aislable": "pruebas_fuera_de_la_copia",
            "sin_confinamiento": "confinamiento_no_disponible"}


def _verificar(verificacion, copia) -> "ResultadoVerificacion | None":
    """Ejecuta la verificacion y la normaliza. `None` = no hay verificador («no se midio»)."""
    if not verificacion:
        return None
    _exigir_raiz(verificacion)                       # defensa en profundidad (ya se exige en `ejecutar`)
    acepta = True
    bruto = verificacion(copia)
    if isinstance(bruto, ResultadoVerificacion):
        if bruto.estado not in ESTADOS_VERIFICACION:
            return ResultadoVerificacion("fallo", bool(bruto.aislada), bool(bruto.confinada),
                                         f"estado desconocido {bruto.estado!r}")
        return bruto
    return ResultadoVerificacion("sano" if bruto else "fallo", acepta, False, "")


def _registro(propuesta, ruta, efecto, sano, autoridad, aislada, motivo=None, promovido=False,
              confinada=False) -> dict:
    """El dict de siempre (compatibilidad) mas `promovido`, `verificacion_aislada`, `ejecucion_confinada`
    y, si se rechazo, `motivo` (`verificacion`, `no_medido`, `efecto_no_verificado`, `base_cambiada`,
    `promocion_revertida`). `revertido` significa «el vivo no cambio»."""
    registro = {"id": propuesta["id"], "fichero": str(ruta), "simbolo": propuesta["simbolo"],
                "efecto_verificado": bool(efecto), "verificacion_sana": sano,
                "revertido": not promovido, "autoridad": autoridad, "promovido": promovido,
                "verificacion_aislada": bool(aislada), "ejecucion_confinada": bool(confinada)}
    if not promovido:
        registro["motivo"] = motivo
    # D1: la correlacion viaja en CADA cambio_aplicado (normal, rechazado) de la via review/motor.
    for clave in ("tarea", "intento", "via"):
        if clave in propuesta:
            registro[clave] = propuesta[clave]
    return registro


def _aplicar_en_copia(directorio, ruta, destino, rel, copia, manifiesto, propuesta, autoridad,
                      verificacion, original, nuevo, operacion) -> dict:
    """Escribe y verifica el candidato en la copia; promueve al vivo solo si efecto y sano."""
    en_copia = copia / rel
    en_copia.write_text(nuevo, encoding="utf-8", newline="")
    candidato = nuevo.encode("utf-8")
    forma = propuesta.get("forma", "funcion")
    buscar, sustituir = propuesta.get("buscar", ""), propuesta.get("sustituir", "")

    def efecto_en(tras_el_cambio: str) -> bool:
        # **El efecto se comprueba releyendo el arbol, no buscando texto.** Un `in` sobre el fuente
        # confunde el simbolo con su mencion en un comentario; preguntarle al parser vale para las
        # cinco formas. Se aplica a la copia y otra vez al vivo tras promover.
        if operacion == "sustituir_texto":
            # Doble y releyendo: el patron dejo de estar **y** el texto nuevo esta.
            return (buscar not in tras_el_cambio) and (sustituir in tras_el_cambio)
        return _existe_simbolo(original, propuesta["simbolo"], forma) \
            and not _existe_simbolo(tras_el_cambio, propuesta["simbolo"], forma)

    # **Se relee el fichero.** Que la sustitucion «se haya hecho» no es evidencia de nada.
    efecto = efecto_en(en_copia.read_bytes().decode("utf-8"))
    try:
        # **«NO SE MIDIO» NO ES «SALIO BIEN» (CEO, 2026-09-16).** Sin verificador no se sabe y se
        # rechaza: ADR-0003, ante la duda, roja. `verificacion(raiz)` recibe la raiz de la COPIA; las
        # heredadas sin parametros se llaman sin argumentos (y miden el vivo). Los campos que se
        # publican se DERIVAN de lo que la verificacion dice que ocurrio (`ResultadoVerificacion`); un
        # `bool` heredado solo cuenta como aislado si recibio la raiz.
        resultado_v = _verificar(verificacion, copia)
    except BaseException:
        # La verificacion **revento** (cuota, el proceso murio): «no se sabe». El vivo nunca se toco.
        cp.registrar_evento(directorio, "cambio_revertido_por_error",
                            {"id": propuesta["id"], "fichero": str(ruta),
                             "motivo": "la verificacion no pudo completarse"})
        raise
    sano = (None if resultado_v is None else
            True if resultado_v.estado == "sano" else
            False if resultado_v.estado == "fallo" else None)
    aislada = bool(resultado_v and resultado_v.aislada)
    confinada = bool(resultado_v and resultado_v.confinada)
    if not (efecto and sano):
        motivo = _MOTIVOS.get(resultado_v.estado if resultado_v else None, "verificacion")
        if sano and not efecto:
            motivo = "efecto_no_verificado"
        registro = _registro(propuesta, ruta, efecto, sano, autoridad, aislada, motivo,
                              confinada=confinada)
        cp.registrar_evento(directorio, "cambio_aplicado", registro)
        return registro
    estado = _dir_estado(directorio)
    _asegurar_estado(estado)
    with _cerrojo(estado, bloqueante=True):               # hasta cerrar el diario
        try:
            resultado, cierre = _promover_si_procede(
                directorio, destino, rel, propuesta, candidato, efecto_en, manifiesto,
                verif={"efecto_verificado": bool(efecto), "verificacion_sana": sano,
                       "verificacion_aislada": aislada, "ejecucion_confinada": confinada})
            registro = _registro(propuesta, ruta, efecto, sano, autoridad, aislada,
                                 None if cierre else resultado, promovido=bool(cierre),
                             confinada=confinada)
            cp.registrar_evento(directorio, "cambio_aplicado", registro)
            if cierre:
                shutil.rmtree(cierre, ignore_errors=True)  # cierra el diario, DESPUES del evento
        finally:
            _retirar_si_vacio(estado)                     # no dejar un directorio de estado por tmp
    return registro


def _promover_si_procede(directorio, destino, rel, propuesta, candidato, efecto_en, manifiesto,
                         verif=None):
    """PARADA otra vez, precondicion de hashes y promocion. Devuelve `(motivo, None)` si no se promovio
    o `("promovido", directorio_del_diario)`."""
    datos = {"id": propuesta["id"], "fichero": str(destino)}
    if orquestador.parada_solicitada(directorio):
        cp.registrar_evento(directorio, "promocion_abortada_parada", datos)
        raise ParadaActiva(f"PARADA armada en {directorio} durante la verificacion: no se promueve nada")
    # Con el cerrojo ya tomado, otro proceso pudo dejar un bloqueo o una operacion pendiente (de un
    # proceso muerto) mientras se verificaba: eso lo resuelve `recuperar`, no se promueve por encima.
    estado = _dir_estado(directorio)
    if (estado / _BLOQUEO).exists():
        cp.registrar_evento(directorio, "promocion_rechazada_por_bloqueo", datos)
        raise PromocionesBloqueadas(f"hay un bloqueo en {estado}: no se promueve")
    if _operaciones_de(estado):
        cp.registrar_evento(directorio, "promocion_abortada_diario_pendiente", datos)
        return "diario_pendiente_ajeno", None
    cambiadas = _base_intacta(directorio.resolve(), manifiesto)
    try:
        if cambiadas:
            raise _BaseCambiada()
        op = _promover(directorio, destino, propuesta, candidato, efecto_en, manifiesto[rel.as_posix()],
                       verif)
    except _BaseCambiada:
        cp.registrar_evento(directorio, "promocion_abortada_base_cambiada",
                            {**datos, "rutas": (cambiadas or [rel.as_posix()])[:20]})
        return "base_cambiada", None
    return ("promovido", op) if op else ("promocion_revertida", None)


# ---------------------------------------------------------------------- 8 · CONTINUAR --

def ciclo(directorio, ficheros, autoridad_humana: str | None, acta: str,
          verificacion=None, max_cambios: int = 5) -> dict:
    """El ciclo entero, **finito**, deteniendose en la frontera si no hay autoridad.

    Sin acta humana llega hasta `proponer` y para. Eso no es un fallo: es la garantia."""
    directorio = pathlib.Path(directorio)
    hallazgos = diagnosticar(observar(ficheros))
    informe = {"observados": len(hallazgos), "propuestos": 0, "autorizados": 0, "aplicados": 0,
               "revertidos": 0, "detenido_en": "continuar"}
    propuestas = [proponer(directorio, h, via="ciclo") for h in hallazgos]
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
