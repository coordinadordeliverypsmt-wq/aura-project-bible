"""Verificador de la garantía G-1 — Ruta Única de Mutación.

Implementa **exactamente** `ESPEC-G-1` §§1–3, §4.1, §4.2 y la corrección §4.5, que es el alcance que
el CEO aprobó el 2026-08-17. **No implementa** `G-2b`, `R-D` ni el plan `M0–M5`: aparecen descritos
en el documento histórico y están marcados NO APROBADOS.

**Vive en `tests/`, no en producción.** Es la misma decisión que ya tomó
`test_manifiesto_arquitectura.py`: una garantía de arquitectura se comprueba desde la capa de
pruebas y **no añade una sola línea a `aura_skeleton/`**.

**Deriva todo del manifiesto** (`architecture_manifest.toml`), fuente única de verdad (D41). No
duplica ninguna lista en código: si aquí hubiera una copia, divergiría — que es el error que D-M-8
diagnostica en el propio sistema.

**La decisión de diseño más importante está en `_resolver_receptor`: ante la duda, calla.** Prefiere
un falso negativo *declarado y contable* a un falso positivo que bloquee el desarrollo (§3.3 capa 4).
La cifra de no resueltos se publica; si crece, es señal de que el código está perdiendo tipado.
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]  # tests/unit/ -> walking-skeleton/
MANIFIESTO = RAIZ / "architecture_manifest.toml"
PAQUETE = RAIZ / "aura_skeleton"

# §4.5 — decisión del CEO 2026-08-17: `write` NO se persigue por nombre en R-A.
#
# Es homónimo de `fichero.write()`, `socket.write()` y `stream.write()`. Medido (§4.4): incluirlo
# hunde la resolución de receptor del 100 % al 40 %, y los 12 casos irresolubles eran TODOS
# `f.write()` sobre ficheros abiertos, ninguno una llamada a un almacén. Sigue clasificado como
# mutante para R-C: lo que cambia es a quién persigue R-A, no qué es `write`.
EXCLUIDAS_DE_RA = frozenset({"write"})

# F2 (§2.2) — escritura directa a disco. Es una lista, y el propio documento declara en FN-2 que
# toda lista es incompleta: no se presenta como exhaustiva.
# Métodos de `pathlib.Path`: inequívocos por nombre — `str` no tiene ninguno de ellos.
ESCRITURAS_DE_PATH = frozenset({"write_text", "write_bytes", "unlink"})
# Funciones de `os`: SOLO cuentan cuando el receptor es literalmente `os`.
#
# `replace` y `remove` son homónimos de `str.replace` y `list.remove`. Sin esta condición, el
# verificador acusaba `resto.replace(marcador, " ")` en `orchestrator.py:375` — un `str.replace` sin
# relación alguna con el disco. Es FP-1 cometido dentro del propio verificador, detectado antes de
# darlo por bueno; por eso la resolución de receptor no es opcional tampoco aquí.
ESCRITURAS_DE_OS = frozenset({"replace", "remove", "unlink", "rename", "rmdir"})
MODOS_DE_ESCRITURA = ("w", "a", "x", "+")


@dataclass(frozen=True)
class Hallazgo:
    """Una violación. **Sin severidad a propósito** (§2.4): *«una garantía con grados deja de ser
    una garantía»*. O es violación, o no lo es."""

    regla: str
    fichero: str
    linea: int
    operacion: str
    detalle: str


# ------------------------------------------------------------------ manifiesto --


def manifiesto() -> dict:
    with open(MANIFIESTO, "rb") as f:
        return tomllib.load(f)


def _mutaciones() -> dict:
    return manifiesto().get("mutaciones", {})


def operaciones_clasificadas_mutantes() -> set[str]:
    """Todo lo declarado mutante en el manifiesto, `write` incluido (R-C)."""
    ops: set[str] = set()
    for almacen in _mutaciones().get("almacen", []):
        ops |= set(almacen.get("mutantes", []))
    return ops


def operaciones_de_ra() -> set[str]:
    """Lo que R-A persigue por nombre: las mutantes MENOS las ambiguas (§4.5)."""
    return operaciones_clasificadas_mutantes() - EXCLUIDAS_DE_RA


def _persistencia_autorizada() -> set[str]:
    return set(_mutaciones().get("persistencia_autorizada", []))


def _excluidos() -> set[str]:
    """Grupo C · modulos que el CEO excluyo del alcance de almacenes, con su motivo escrito en el
    manifiesto (D-G1-2, 2026-08-18). **Excluir no es autorizar:** significa que su escritura no es
    persistencia de datos cuya destruccion deba gobernar esta regla. La exclusion es visible y
    discutible, nunca silenciosa."""
    return {x["modulo"] for x in _mutaciones().get("excluido", [])}


def _excepciones() -> dict[str, set[str]]:
    """Lista blanca: módulo -> operaciones autorizadas. **Solo puede encoger** (§5)."""
    fuera: dict[str, set[str]] = {}
    for exc in _mutaciones().get("excepcion", []):
        fuera.setdefault(exc["modulo"], set()).update(exc.get("opera", []))
    return fuera


def _clases_de_almacen() -> set[str]:
    """Nombres de clase que definen alguna operación mutante en un módulo de almacén declarado.

    Se **derivan** del manifiesto y del código; no se listan a mano. Así, declarar un almacén nuevo
    en el manifiesto basta para que el verificador lo reconozca."""
    mutantes = operaciones_clasificadas_mutantes()
    clases: set[str] = set()
    for almacen in _mutaciones().get("almacen", []):
        ruta = RAIZ / almacen["modulo"]
        if not ruta.exists():
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ClassDef):
                metodos = {h.name for h in nodo.body if isinstance(h, (ast.FunctionDef, ast.AsyncFunctionDef))}
                if metodos & mutantes:
                    clases.add(nodo.name)
    return clases


def ambito() -> list[Path]:
    """Solo el paquete de producción. `tests/` queda fuera (FP-3) y los arneses también (FP-4):
    construir un almacén y llamar a `olvidar` en una prueba es legítimo."""
    return sorted(PAQUETE.rglob("*.py"))


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(RAIZ))
    except ValueError:
        return str(p)


# ----------------------------------------------------- resolución del receptor --


def _mapa_de_receptores(arbol: ast.AST, clases: set[str]) -> tuple[set[str], set[str]]:
    """Devuelve (nombres locales, atributos de `self`) que apuntan a un almacén conocido.

    Capas 1-3 de §3.3, de más fiable a menos: anotación de tipo, construcción visible y atributo de
    instancia resuelto desde `__init__`. Lo que no encaje en ninguna se queda fuera, y por eso
    después el verificador calla."""
    nombres: set[str] = set()
    atributos: set[str] = set()

    for nodo in ast.walk(arbol):
        # Capa 1 — anotación explícita: `mem: PersistentMemory` o `def f(mem: PersistentMemory)`.
        if isinstance(nodo, ast.arg) and isinstance(nodo.annotation, ast.Name):
            if nodo.annotation.id in clases:
                nombres.add(nodo.arg)
        if isinstance(nodo, ast.AnnAssign) and isinstance(nodo.annotation, ast.Name):
            if nodo.annotation.id in clases and isinstance(nodo.target, ast.Name):
                nombres.add(nodo.target.id)
        # Capa 2 — construcción visible: `mem = PersistentMemory(...)`.
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Call):
            fn = nodo.value.func
            # Sin `getattr`: R-D no está aprobada y una llamada a `getattr` aquí, aunque sea
            # sobre un nodo del AST, haría ambigua la comprobación de que no la implementamos.
            if isinstance(fn, ast.Name):
                nombre_clase = fn.id
            elif isinstance(fn, ast.Attribute):
                nombre_clase = fn.attr
            else:
                nombre_clase = None
            if nombre_clase in clases:
                for destino in nodo.targets:
                    if isinstance(destino, ast.Name):
                        nombres.add(destino.id)
                    elif isinstance(destino, ast.Attribute) and _es_self(destino.value):
                        atributos.add(destino.attr)

    # Capa 3 — `self.x = <parametro anotado como almacen>`, resuelto dentro de `__init__`.
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anotados = {a.arg for a in nodo.args.args
                        if isinstance(a.annotation, ast.Name) and a.annotation.id in clases}
            for hijo in ast.walk(nodo):
                if isinstance(hijo, ast.Assign) and isinstance(hijo.value, ast.Name):
                    if hijo.value.id in anotados:
                        for destino in hijo.targets:
                            if isinstance(destino, ast.Attribute) and _es_self(destino.value):
                                atributos.add(destino.attr)
    return nombres, atributos


def _es_self(nodo: ast.AST) -> bool:
    return isinstance(nodo, ast.Name) and nodo.id == "self"


def _receptor(llamada: ast.Call, nombres: set[str], atributos: set[str]) -> str:
    """`"almacen"` si se resuelve a un almacén conocido; `"otro"` si se resuelve a otra cosa;
    `"no_resoluble"` si no hay forma de saberlo."""
    receptor = llamada.func.value  # type: ignore[union-attr]
    if isinstance(receptor, ast.Name):
        return "almacen" if receptor.id in nombres else "no_resoluble"
    if isinstance(receptor, ast.Attribute) and _es_self(receptor.value):
        return "almacen" if receptor.attr in atributos else "no_resoluble"
    return "no_resoluble"


# ------------------------------------------------------------- R-A · R-B · R-C --


# ------------------------------------------- CAPA 5 · conjunto de tipos (D-G1-4) --
#
# Enmienda de ESPEC-G-1 §3.3 aprobada por el CEO el 2026-08-18. Las capas 1-3 son intra-fichero y no
# alcanzan a un atributo que se RECIBE inyectado: su clase la fija la composicion, en otro modulo.
#
# La capa razona sobre el CONJUNTO de tipos posibles, nunca sobre un representante. Si alguno de
# ellos es un almacen conocido, la llamada NO esta gobernada y es violacion. Si el conjunto no puede
# formarse, manda la capa 4: calla.

_CACHE_CLASES: dict[str, tuple[str, frozenset[str]]] | None = None


def _clases_del_paquete() -> dict[str, tuple[str, frozenset[str]]]:
    """Todas las clases del paquete: nombre -> (fichero, metodos). Se cachea: el paquete no cambia
    dentro de una corrida y la capa 5 la consulta muchas veces."""
    global _CACHE_CLASES
    if _CACHE_CLASES is None:
        mapa: dict[str, tuple[str, frozenset[str]]] = {}
        for fichero in ambito():
            for nodo in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
                if isinstance(nodo, ast.ClassDef):
                    metodos = frozenset(
                        h.name for h in nodo.body
                        if isinstance(h, (ast.FunctionDef, ast.AsyncFunctionDef)))
                    mapa[nodo.name] = (_rel(fichero), metodos)
        _CACHE_CLASES = mapa
    return _CACHE_CLASES


def _init_de(clase: str) -> tuple[ast.FunctionDef, Path] | None:
    for fichero in ambito():
        for nodo in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.ClassDef) and nodo.name == clase:
                for h in nodo.body:
                    if isinstance(h, ast.FunctionDef) and h.name == "__init__":
                        return h, fichero
    return None


def _parametro_que_alimenta(init: ast.FunctionDef, atributo: str) -> tuple[str, int] | None:
    """`self.<atributo> = <param>` -> (nombre del parametro, indice posicional sin contar `self`)."""
    for nodo in ast.walk(init):
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Name):
            for destino in nodo.targets:
                if isinstance(destino, ast.Attribute) and _es_self(destino.value) \
                        and destino.attr == atributo:
                    nombres = [a.arg for a in init.args.args[1:]]
                    if nodo.value.id in nombres:
                        return nodo.value.id, nombres.index(nodo.value.id)
    return None


def _returns_en_indice(nombre_funcion: str, indice: int) -> set[str] | None:
    """Clases devueltas por `nombre_funcion` en la posicion `indice` de su tupla de retorno."""
    clases = _clases_del_paquete()
    tipos: set[str] = set()
    visto = False
    for fichero in ambito():
        for nodo in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    or nodo.name != nombre_funcion:
                continue
            visto = True
            for hijo in ast.walk(nodo):
                if not isinstance(hijo, ast.Return) or hijo.value is None:
                    continue
                valor = hijo.value
                if isinstance(valor, ast.Tuple):
                    if indice >= len(valor.elts):
                        return None
                    valor = valor.elts[indice]
                elif indice != 0:
                    return None
                if isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name) \
                        and valor.func.id in clases:
                    tipos.add(valor.func.id)
                else:
                    return None  # un retorno no demostrable envenena el conjunto entero
    return tipos if visto and tipos else None


def _resolver_expresion(expr: ast.AST, arbol: ast.AST) -> tuple[set[str] | None, list[str]]:
    """Conjunto de clases que una expresion puede valer, con su evidencia. `None` = indeterminable."""
    clases = _clases_del_paquete()
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in clases:
        return {expr.func.id}, [f"construccion directa de {expr.func.id} en linea {expr.lineno}"]
    if isinstance(expr, ast.Name):
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Assign):
                continue
            # `n = X(...)`
            for destino in nodo.targets:
                if isinstance(destino, ast.Name) and destino.id == expr.id:
                    if isinstance(nodo.value, ast.Call) and isinstance(nodo.value.func, ast.Name) \
                            and nodo.value.func.id in clases:
                        return ({nodo.value.func.id},
                                [f"asignado desde {nodo.value.func.id}(...) en linea {nodo.lineno}"])
                # `a, b, c = f(...)`
                if isinstance(destino, ast.Tuple):
                    for i, elt in enumerate(destino.elts):
                        if isinstance(elt, ast.Name) and elt.id == expr.id \
                                and isinstance(nodo.value, ast.Call) \
                                and isinstance(nodo.value.func, ast.Name):
                            tipos = _returns_en_indice(nodo.value.func.id, i)
                            if tipos:
                                return tipos, [
                                    f"desempaquetado de {nodo.value.func.id}(...) en linea "
                                    f"{nodo.lineno}, posicion {i}; retornos: {sorted(tipos)}"]
                            return None, ["retorno no demostrable: se calla (capa 4)"]
    return None, ["expresion no resoluble: se calla (capa 4)"]


def tipos_posibles(clase: str, atributo: str) -> tuple[set[str] | None, list[str]]:
    """**Capa 5.** Conjunto de tipos que `clase.atributo` puede recibir por inyeccion, y la
    evidencia de por que. `None` cuando la evidencia no lo demuestra — y entonces se calla."""
    encontrado = _init_de(clase)
    if encontrado is None:
        return None, [f"no existe {clase}.__init__ en el paquete"]
    init, _ = encontrado
    par = _parametro_que_alimenta(init, atributo)
    if par is None:
        return None, [f"{clase}.__init__ no asigna self.{atributo} desde un parametro"]
    nombre_par, indice = par

    conjunto: set[str] = set()
    evidencia: list[str] = []
    for fichero in ambito():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Name) \
                    or nodo.func.id != clase:
                continue
            arg = None
            for kw in nodo.keywords:
                if kw.arg == nombre_par:
                    arg = kw.value
            if arg is None and len(nodo.args) > indice:
                arg = nodo.args[indice]
            if arg is None:
                continue
            tipos, por_que = _resolver_expresion(arg, arbol)
            evidencia += [f"{_rel(fichero)}:{nodo.lineno} · {p}" for p in por_que]
            if tipos is None:
                return None, evidencia  # prohibicion 1: no se asume un tipo
            conjunto |= tipos
    if not conjunto:
        return None, evidencia or [f"nadie construye {clase} en el paquete"]
    faltan = {t for t in conjunto if t in _clases_del_paquete()}
    for t in sorted(faltan):
        evidencia.append(f"tipo posible {t} -> metodos: {sorted(_clases_del_paquete()[t][1])[:6]}...")
    return conjunto, evidencia


def tipos_sin_operacion(clase: str, atributo: str, operacion: str) -> set[str]:
    """Tipos del conjunto que **no implementan** la operacion. Prohibicion 2 de la enmienda: su
    ausencia NO vuelve gobernada la llamada; es una incompatibilidad real y se registra."""
    conjunto, _ = tipos_posibles(clase, atributo)
    if not conjunto:
        return set()
    clases = _clases_del_paquete()
    return {t for t in conjunto if t in clases and operacion not in clases[t][1]}


def _atributos_por_capa5(arbol: ast.AST, almacenes: set[str]) -> set[str]:
    """Atributos de las clases de este fichero cuyo conjunto de tipos incluye algun almacen.

    Regla del CEO: **si ALGUN tipo posible contiene una ruta de mutacion que evade el Motor, es
    violacion.** Basta con que uno del conjunto sea almacen para que la llamada no este gobernada."""
    resueltos: set[str] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ClassDef):
            continue
        for h in nodo.body:
            if not (isinstance(h, ast.FunctionDef) and h.name == "__init__"):
                continue
            for asignacion in ast.walk(h):
                if not (isinstance(asignacion, ast.Assign)
                        and isinstance(asignacion.value, ast.Name)):
                    continue
                for destino in asignacion.targets:
                    if not (isinstance(destino, ast.Attribute) and _es_self(destino.value)):
                        continue
                    conjunto, _ = tipos_posibles(nodo.name, destino.attr)
                    if conjunto and conjunto & almacenes:
                        resueltos.add(destino.attr)
    return resueltos


def analizar_fichero(ruta: Path, autorizado_para: frozenset[str]) -> list[Hallazgo]:
    """R-A y R-B sobre un fichero. `autorizado_para` son las operaciones que este módulo puede usar."""
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    clases = _clases_de_almacen()
    nombres, atributos = _mapa_de_receptores(arbol, clases)
    atributos |= _atributos_por_capa5(arbol, clases)  # capa 5 (D-G1-4)
    perseguidas = operaciones_de_ra()
    autorizado_disco = _rel(Path(ruta)) in (_persistencia_autorizada() | _excluidos())
    hallazgos: list[Hallazgo] = []

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        fn = nodo.func

        # --- R-A: operación de almacén desde módulo no autorizado.
        if isinstance(fn, ast.Attribute) and fn.attr in perseguidas and fn.attr not in autorizado_para:
            if _receptor(nodo, nombres, atributos) == "almacen":
                hallazgos.append(Hallazgo(
                    regla="R-A", fichero=_rel(Path(ruta)), linea=nodo.lineno, operacion=fn.attr,
                    detalle="llamada a una operación mutante de almacén desde un módulo no autorizado"))

        # --- R-B: escritura directa a disco fuera de los módulos de persistencia.
        if autorizado_disco:
            continue
        if isinstance(fn, ast.Name) and fn.id == "open" and _abre_para_escribir(nodo):
            hallazgos.append(Hallazgo(
                regla="R-B", fichero=_rel(Path(ruta)), linea=nodo.lineno, operacion="open",
                detalle="apertura de fichero en modo de escritura"))
        elif isinstance(fn, ast.Attribute) and _es_escritura_de_disco(fn):
            hallazgos.append(Hallazgo(
                regla="R-B", fichero=_rel(Path(ruta)), linea=nodo.lineno, operacion=fn.attr,
                detalle="escritura o borrado directo en disco"))
    return hallazgos


def _es_escritura_de_disco(fn: ast.Attribute) -> bool:
    """Distingue `os.replace(...)` de `texto.replace(...)`. Sin esto, R-B es ruido."""
    if fn.attr in ESCRITURAS_DE_PATH:
        return True
    if fn.attr in ESCRITURAS_DE_OS:
        return isinstance(fn.value, ast.Name) and fn.value.id == "os"
    return False


def _abre_para_escribir(llamada: ast.Call) -> bool:
    modo = None
    if len(llamada.args) >= 2 and isinstance(llamada.args[1], ast.Constant):
        modo = llamada.args[1].value
    for kw in llamada.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            modo = kw.value.value
    if not isinstance(modo, str):
        return False  # sin modo literal, `open` es lectura por defecto
    return any(c in modo for c in MODOS_DE_ESCRITURA)


def no_resueltos(ruta: Path) -> int:
    """Cuenta los receptores que no se pudieron resolver. **El silencio se declara, no se olvida.**"""
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    clases = _clases_de_almacen()
    nombres, atributos = _mapa_de_receptores(arbol, clases)
    atributos |= _atributos_por_capa5(arbol, clases)  # capa 5 (D-G1-4)
    perseguidas = operaciones_de_ra()
    return sum(
        1 for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr in perseguidas
        and _receptor(nodo, nombres, atributos) == "no_resoluble")


def publicos_sin_clasificar(ruta: Path, mutantes: frozenset[str], neutros: frozenset[str]) -> set[str]:
    """R-C · todo `def` público de un almacén debe estar clasificado. Los privados no entran."""
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    publicos = {
        nodo.name for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and not nodo.name.startswith("_")}
    return publicos - set(mutantes) - set(neutros)


def violaciones_ra() -> list[Hallazgo]:
    motor = _mutaciones().get("motor")
    excepciones = _excepciones()
    todas = operaciones_clasificadas_mutantes()
    hallazgos: list[Hallazgo] = []
    for fichero in ambito():
        rel = _rel(fichero)
        if rel == motor:
            continue  # el Motor Único es el autorizado por defecto (§2.2)
        autorizado = set(excepciones.get(rel, set()))
        for almacen in _mutaciones().get("almacen", []):
            if almacen["modulo"] == rel:
                autorizado |= todas  # un almacén es autorizado sobre sí mismo (FP-2)
        hallazgos += [h for h in analizar_fichero(fichero, frozenset(autorizado)) if h.regla == "R-A"]
    return hallazgos


def violaciones_rb() -> list[Hallazgo]:
    excepciones = _excepciones()
    hallazgos: list[Hallazgo] = []
    for fichero in ambito():
        autorizado = frozenset(excepciones.get(_rel(fichero), set()))
        hallazgos += [h for h in analizar_fichero(fichero, autorizado) if h.regla == "R-B"]
    return hallazgos


def violaciones_rc() -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for almacen in _mutaciones().get("almacen", []):
        ruta = RAIZ / almacen["modulo"]
        sin_clasificar = publicos_sin_clasificar(
            ruta, frozenset(almacen.get("mutantes", [])), frozenset(almacen.get("neutros", [])))
        hallazgos += [
            Hallazgo(regla="R-C", fichero=almacen["modulo"], linea=0, operacion=nombre,
                     detalle="método público de un almacén sin clasificar como mutante o neutro")
            for nombre in sorted(sin_clasificar)]
    return hallazgos


def explicar(hallazgos: list[Hallazgo]) -> str:
    """§2.4 · el mensaje nombra fichero, línea, operación y **qué hacer**."""
    if not hallazgos:
        return "sin violaciones"
    lineas = [f"G-1: {len(hallazgos)} violación(es) de la Ruta Única de Mutación:"]
    for h in hallazgos:
        lineas.append(f"  [{h.regla}] {h.fichero}:{h.linea} · {h.operacion} — {h.detalle}")
    lineas.append("  Qué hacer: enrutar la mutación por el Motor Único, o solicitar autorización "
                  "explícita en architecture_manifest.toml con motivo y fecha.")
    return "\n".join(lineas)
