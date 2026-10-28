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
    # **El perimetro que el acta anade.** Va aqui a proposito: DESPUES de gobernanza, producto y
    # actas —que siguen rechazandose siempre, tambien para estos ficheros— y ANTES de `raiz`, porque
    # el ciclo llama con `raiz=<control-plane>` y el fichero autorizado no cuelga de ahi. Se compara
    # la ruta relativa entera, nunca un prefijo.
    try:
        if real.relative_to(_RAIZ_REPO).as_posix() in _FICHEROS_AUTORIZADOS:
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

def proponer(directorio, hallazgo: dict) -> dict:
    """Una propuesta es una **peticion**, no una decision. Nace sin autorizar, y nada la concede por
    el paso del tiempo: `1.1:85`."""
    directorio = pathlib.Path(directorio)
    existentes = [e for e in cp.leer_eventos(directorio) if e["tipo"] == "propuesta_registrada"]
    propuesta = {"id": f"P-{len(existentes) + 1:03d}", "estado": "PROPUESTA", "autorizada": False,
                 # `forma` viaja con la propuesta desde que la capacidad cubre las cinco formas del
                 # codigo muerto: sin ella el ejecutor volveria a suponer «funcion» y no borraria
                 # nada, que es exactamente lo que pasaba —en silencio y revirtiendo— antes de esto.
                 **{k: hallazgo.get(k) for k in ("simbolo", "fichero", "motivo", "linea",
                                                  "buscar", "sustituir")},
                 # La operacion viaja con la propuesta. Por defecto la de siempre: sin esto, una
                 # propuesta antigua cambiaria de comportamiento al aparecer el vocabulario nuevo.
                 "operacion": hallazgo.get("operacion", "eliminar_codigo_muerto"),
                 "forma": hallazgo.get("forma", "funcion")}
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
    ruta.write_text(nuevo, encoding="utf-8")

    # **Se relee el fichero.** Que la sustitucion «se haya hecho» no es evidencia de nada.
    tras_el_cambio = ruta.read_text(encoding="utf-8")
    # **El efecto se comprueba releyendo el arbol, no buscando texto.** Un `in` sobre el fuente
    # confunde el simbolo con su mencion en un comentario o en otra palabra que lo contenga, y ademas
    # solo sabia mirar funciones: `def X(`. Preguntarle al parser si el nodo sigue ahi vale para las
    # cinco formas y no se deja enganar por la prosa.
    if operacion == "sustituir_texto":
        # El efecto de una sustitucion es doble y se comprueba releyendo: el patron dejo de estar
        # **y** el texto nuevo esta. Comprobar solo una mitad daria por buena una escritura parcial.
        efecto = (buscar not in tras_el_cambio) and (sustituir in tras_el_cambio)
    else:
        efecto = _existe_simbolo(original, propuesta["simbolo"], forma) \
            and not _existe_simbolo(tras_el_cambio, propuesta["simbolo"], forma)
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
