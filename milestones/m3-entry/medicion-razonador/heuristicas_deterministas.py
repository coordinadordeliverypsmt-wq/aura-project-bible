"""Bateria adversarial — el guardian del caso experimental, y su propia red de seguridad.

## Dos lecciones pagadas, ambas incorporadas aqui

**Primera.** El caso v1 fue aprobado por revision humana y una regla de tres lineas lo resolvia. De
ahi que la bateria sea ejecutable y bloqueante.

**Segunda, y mas grave.** La bateria del v2 tenia 58 reglas y su control de calidad era un umbral
holgado: «detecta >= 5 roturas en un caso conocido como roto». Un adversarial demostro que ese
control sobrevivia intacto a sabotear `_tokens`, a sabotear `_stem` y **a sustituir 53 de las 58
reglas por `lambda c: []`**. Es decir: la bateria no podia distinguir «el caso es bueno» de «la
bateria esta rota», que es exactamente el patron `declarado != real` del proyecto, cometido dentro
del instrumento que debia impedirlo.

## Como se corrige

1. **Familias, no recuento.** Cada regla pertenece a una FAMILIA. El numero de reglas deja de ser
   una metrica de calidad: lo que se mide es que cada familia siga viva.
2. **Canarios por familia.** Cada familia tiene un caso conocido como roto **por esa familia
   concreta**. Si la familia se sabotea, su canario deja de detectarse y un test falla. Un umbral
   global no puede hacer eso; un canario por familia, si.
3. **Las excepciones no se tragan.** Una regla que falla internamente **propaga**. Antes se
   registraba como `rompe=False` y una regla rota se convertia en silencio en una regla que no
   protege.
4. **Superficies completas.** Se anaden docstrings, cuerpos, puntuacion, n-gramas, TF-IDF, Jaccard,
   recuentos de lineas y rasgos del bloque — el terreno donde cayo el v2.

## Que significa «romper»

Una regla rompe el caso si selecciona **exactamente una** candidata y es la correcta. Seleccionar
una unica candidata **incorrecta** es deseable: castiga al atajista. Seleccionar varias no resuelve
nada.

## Lo que esta bateria NO pretende

No demuestra imposibilidad frente a cualquier algoritmo imaginable — el CEO fijo esa frontera el
2026-08-16. Demuestra que **no hay atajos lexicos, estructurales ni posicionales conocidos** que
seleccionen la respuesta sin usar la relacion semantica entre la garantia y lo que hace el codigo.
"""

from __future__ import annotations

import math
import re
from types import SimpleNamespace
from typing import Callable, NamedTuple

SUFIJOS_ES = ("aciones", "acion", "amiento", "mientos", "miento", "ados", "adas", "ado", "ada",
              "idos", "idas", "ido", "ida", "ar", "er", "ir", "es", "os", "as", "a", "o", "e")

VACIAS = {"la", "el", "los", "las", "un", "una", "de", "del", "que", "no", "se", "ha", "haya",
          "es", "en", "y", "o", "a", "al", "por", "para", "con", "sin", "su", "sus", "lo",
          "puede", "mientras", "hacia", "esa", "este", "esta", "quien", "realmente", "como",
          "mas", "sido", "cada", "otra", "ya", "desde", "hasta"}

FAMILIAS = ("lexico_nombre", "lexico_predicado", "lexico_excepcion", "lexico_docstring",
            "estructural_identificador", "estructural_cuerpo", "posicional",
            "patron_obsoleto", "combinada", "parametros", "llamadas", "estadisticas")


class Regla(NamedTuple):
    nombre: str
    familia: str
    fn: Callable


REGLAS: list[Regla] = []


def _regla(nombre: str, familia: str):
    assert familia in FAMILIAS, familia

    def envoltorio(fn):
        REGLAS.append(Regla(nombre, familia, fn))
        return fn
    return envoltorio


# ------------------------------------------------------------------------------- utilidades --


def _tokens(texto: str) -> list[str]:
    limpio = "".join(c if c.isalnum() or c in " _" else " " for c in texto.lower())
    return [t for t in limpio.replace("_", " ").split() if t not in VACIAS and len(t) > 2]


def _stem(p: str) -> str:
    for s in SUFIJOS_ES:
        if p.endswith(s) and len(p) - len(s) >= 4:
            return p[: -len(s)]
    return p


def _lev(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _lcs(a: str, b: str) -> int:
    mejor = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            mejor = max(mejor, k)
    return mejor


def _ngramas(s: str, n: int) -> set[str]:
    s = s.lower()
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def bloques(caso) -> dict[str, str]:
    """Bloque de codigo completo de cada funcion, indexado por predicado.

    Es la superficie donde cayo el v2: docstrings y cuerpos. Si el caso no trae `CONTENIDO`, se
    devuelve vacio y las reglas de esa familia no seleccionan nada — pero entonces su canario
    tampoco las respalda, y el test de cobertura lo detecta."""
    contenido = getattr(caso, "CONTENIDO", "")
    out = {}
    for f in caso.FUNCIONES:
        m = re.search(rf"def {re.escape(f.nombre)}\(.*?(?=\ndef |\Z)", contenido, re.S)
        if m:
            out[f.predicado] = m.group(0).strip()
    return out


def _docstring(bloque: str) -> str:
    m = re.search(r'"""(.*?)"""', bloque, re.S)
    return m.group(1) if m else ""


def _cuerpo(bloque: str) -> str:
    lineas = [ln for ln in bloque.splitlines() if ln.strip()
              and not ln.strip().startswith(('def ', '"""', "raise ", "if not "))]
    return "\n".join(lineas)


def _linea(f) -> str:
    return f"    if not {f.predicado}({f.argumento}):"


def _sup(f, cual: str) -> str:
    return {"nombre": f.nombre, "predicado": f.predicado, "excepcion": f.excepcion}[cual]


def _extremo(caso, clave, maximo: bool):
    vals = {f.predicado: clave(f) for f in caso.FUNCIONES}
    objetivo = max(vals.values()) if maximo else min(vals.values())
    return [p for p, v in vals.items() if v == objetivo]


def _por_bloque(caso, clave, maximo: bool):
    bl = bloques(caso)
    if not bl:
        return []
    vals = {p: clave(b) for p, b in bl.items()}
    objetivo = max(vals.values()) if maximo else min(vals.values())
    return [p for p, v in vals.items() if v == objetivo]


# ------------------------------------------------------ FAMILIAS LEXICAS · garantia -> X --

for _cual, _fam in (("nombre", "lexico_nombre"), ("predicado", "lexico_predicado"),
                    ("excepcion", "lexico_excepcion")):

    def _mk_pref_completo(k, cual=_cual):
        return lambda c: [f.predicado for f in c.FUNCIONES
                          if _sup(f, cual)[:k].lower() in c.GARANTIA.lower()]

    def _mk_pref_token(k, cual=_cual):
        return lambda c: [f.predicado for f in c.FUNCIONES
                          if any(len(p) >= k and p[:k] in c.GARANTIA.lower()
                                 for p in _sup(f, cual).lower().split("_"))]

    def _mk_raiz(k, cual=_cual):
        return lambda c: [f.predicado for f in c.FUNCIONES
                          if any(w[:k] in _sup(f, cual).lower()
                                 for w in _tokens(c.GARANTIA) if len(w) >= k)]

    def _mk_stem(cual=_cual):
        return lambda c: [f.predicado for f in c.FUNCIONES
                          if {_stem(w) for w in _tokens(c.GARANTIA)}
                          & {_stem(t) for t in _tokens(_sup(f, cual))}]

    def _mk_lcs(cual=_cual):
        def r(c):
            v = {f.predicado: _lcs(c.GARANTIA.lower(), _sup(f, cual).lower().replace("_", ""))
                 for f in c.FUNCIONES}
            m = max(v.values())
            return [p for p, x in v.items() if x == m]
        return r

    def _mk_lev(cual=_cual):
        def r(c):
            ts = _tokens(c.GARANTIA) or [c.GARANTIA.lower()]
            v = {f.predicado: min(_lev(t, _sup(f, cual).lower()) for t in ts) for f in c.FUNCIONES}
            m = min(v.values())
            return [p for p, x in v.items() if x == m]
        return r

    def _mk_ngr(n, cual=_cual):
        def r(c):
            g = _ngramas(c.GARANTIA, n)
            v = {f.predicado: len(g & _ngramas(_sup(f, cual), n)) for f in c.FUNCIONES}
            m = max(v.values())
            return [p for p, x in v.items() if x == m]
        return r

    for _k in (3, 4, 5, 6):
        _regla(f"prefijo k={_k} de {_cual} completo en garantia", _fam)(_mk_pref_completo(_k))
        _regla(f"prefijo k={_k} de token de {_cual} en garantia", _fam)(_mk_pref_token(_k))
    for _k in (5, 6, 7):
        _regla(f"raiz k={_k} de garantia en {_cual}", _fam)(_mk_raiz(_k))
    _regla(f"stem espanol garantia<->{_cual}", _fam)(_mk_stem())
    _regla(f"LCS maxima garantia<->{_cual}", _fam)(_mk_lcs())
    _regla(f"distancia de edicion minima garantia<->{_cual}", _fam)(_mk_lev())
    for _n in (3, 4, 5):
        _regla(f"n-gramas n={_n} garantia<->{_cual}", _fam)(_mk_ngr(_n))


# ----------------------------------------------- FAMILIA LEXICA · garantia <-> docstring --


@_regla("solapamiento de tokens garantia<->docstring", "lexico_docstring")
def _r_overlap_doc(c):
    bl = bloques(c)
    if not bl:
        return []
    g = set(_tokens(c.GARANTIA))
    v = {p: len(g & set(_tokens(_docstring(b)))) for p, b in bl.items()}
    m = max(v.values())
    return [p for p, x in v.items() if x == m] if m else []


@_regla("Jaccard garantia<->docstring", "lexico_docstring")
def _r_jaccard_doc(c):
    bl = bloques(c)
    if not bl:
        return []
    g = set(_tokens(c.GARANTIA))
    v = {}
    for p, b in bl.items():
        d = set(_tokens(_docstring(b)))
        v[p] = len(g & d) / len(g | d) if (g | d) else 0.0
    m = max(v.values())
    return [p for p, x in v.items() if x == m] if m else []


@_regla("TF-IDF garantia<->docstring", "lexico_docstring")
def _r_tfidf_doc(c):
    bl = bloques(c)
    if not bl:
        return []
    docs = {p: _tokens(_docstring(b)) for p, b in bl.items()}
    n = len(docs)
    df: dict[str, int] = {}
    for toks in docs.values():
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    g = set(_tokens(c.GARANTIA))
    v = {p: sum(math.log(n / df[t]) for t in set(toks) & g if df.get(t)) for p, toks in docs.items()}
    m = max(v.values())
    return [p for p, x in v.items() if x == m] if m else []


@_regla("stem garantia<->docstring", "lexico_docstring")
def _r_stem_doc(c):
    bl = bloques(c)
    if not bl:
        return []
    g = {_stem(w) for w in _tokens(c.GARANTIA)}
    v = {p: len(g & {_stem(w) for w in _tokens(_docstring(b))}) for p, b in bl.items()}
    m = max(v.values())
    return [p for p, x in v.items() if x == m] if m else []


@_regla("palabra unica del docstring presente en la garantia", "lexico_docstring")
def _r_palabra_unica(c):
    bl = bloques(c)
    if not bl:
        return []
    conteo: dict[str, int] = {}
    for b in bl.values():
        for t in set(_tokens(_docstring(b))):
            conteo[t] = conteo.get(t, 0) + 1
    g = set(_tokens(c.GARANTIA))
    return [p for p, b in bl.items()
            if any(conteo[t] == 1 and t in g for t in set(_tokens(_docstring(b))))]


# ---------------------------------------- FAMILIA ESTRUCTURAL · identificadores (v2) --

_IDENT = [
    ("predicado mas corto", lambda f: len(f.predicado), False),
    ("predicado mas largo", lambda f: len(f.predicado), True),
    ("predicado con menos tokens", lambda f: f.predicado.count("_"), False),
    ("predicado con mas tokens", lambda f: f.predicado.count("_"), True),
    ("nombre mas corto", lambda f: len(f.nombre), False),
    ("nombre mas largo", lambda f: len(f.nombre), True),
    ("nombre con menos tokens", lambda f: f.nombre.count("_"), False),
    ("nombre con mas tokens", lambda f: f.nombre.count("_"), True),
    ("excepcion mas corta", lambda f: len(f.excepcion), False),
    ("excepcion mas larga", lambda f: len(f.excepcion), True),
    ("argumento mas corto", lambda f: len(f.argumento), False),
    ("argumento mas largo", lambda f: len(f.argumento), True),
    ("linea de guarda mas corta", lambda f: len(_linea(f)), False),
    ("linea de guarda mas larga", lambda f: len(_linea(f)), True),
]
for _n, _cl, _mx in _IDENT:
    _regla(_n, "estructural_identificador")(
        lambda c, cl=_cl, mx=_mx: _extremo(c, cl, mx))

_regla("guarda sin argumento", "estructural_identificador")(
    lambda c: [f.predicado for f in c.FUNCIONES if not f.argumento])
_regla("excepcion repetida", "estructural_identificador")(
    lambda c: [f.predicado for f in c.FUNCIONES
               if [g.excepcion for g in c.FUNCIONES].count(f.excepcion) > 1])


# --------------------------------- FAMILIA ESTRUCTURAL · cuerpo y docstring (nueva, v3) --

_CUERPO = [
    ("bloque mas largo en caracteres", lambda b: len(b), True),
    ("bloque mas corto en caracteres", lambda b: len(b), False),
    ("bloque con mas lineas", lambda b: len(b.splitlines()), True),
    ("bloque con menos lineas", lambda b: len(b.splitlines()), False),
    ("docstring mas largo", lambda b: len(_docstring(b)), True),
    ("docstring mas corto", lambda b: len(_docstring(b)), False),
    ("docstring con mas frases", lambda b: _docstring(b).count("."), True),
    ("docstring con menos frases", lambda b: _docstring(b).count("."), False),
    ("docstring con mas signos de puntuacion", lambda b: sum(_docstring(b).count(s) for s in ",;:-()"), True),
    ("docstring con mas palabras", lambda b: len(_docstring(b).split()), True),
    ("docstring con menos palabras", lambda b: len(_docstring(b).split()), False),
    ("cuerpo mas largo", lambda b: len(_cuerpo(b)), True),
    ("cuerpo mas corto", lambda b: len(_cuerpo(b)), False),
    ("cuerpo con mas comas", lambda b: _cuerpo(b).count(","), True),
    ("cuerpo con mas puntos de atributo", lambda b: _cuerpo(b).count("."), True),
    ("mayor indentacion maxima", lambda b: max((len(ln) - len(ln.lstrip()) for ln in b.splitlines()), default=0), True),
]
for _n, _cl, _mx in _CUERPO:
    _regla(_n, "estructural_cuerpo")(
        lambda c, cl=_cl, mx=_mx: _por_bloque(c, cl, mx))


@_regla("objeto receptor unico en el fichero", "estructural_cuerpo")
def _r_receptor_unico(c):
    bl = bloques(c)
    if not bl:
        return []
    recept = {}
    for p, b in bl.items():
        m = re.findall(r"^\s{4}(\w+)\.", _cuerpo(b), re.M)
        recept[p] = m[0] if m else ""
    conteo: dict[str, int] = {}
    for r in recept.values():
        conteo[r] = conteo.get(r, 0) + 1
    return [p for p, r in recept.items() if r and conteo[r] == 1]


@_regla("receptor con guion bajo", "estructural_cuerpo")
def _r_receptor_guion(c):
    bl = bloques(c)
    return [p for p, b in bl.items() if re.search(r"^\s{4}\w+_\w+\.", _cuerpo(b), re.M)]


@_regla("cuerpo con mas de una llamada", "estructural_cuerpo")
def _r_cuerpo_multiple(c):
    bl = bloques(c)
    return [p for p, b in bl.items() if len([ln for ln in _cuerpo(b).splitlines() if ln.strip()]) > 1]


# ------------------------------------------------------------------ FAMILIA POSICIONAL --

for _n, _ix in (("primera funcion", 0), ("ultima funcion", -1)):
    _regla(_n, "posicional")(lambda c, ix=_ix: [c.FUNCIONES[ix].predicado])
_regla("funcion mediana", "posicional")(
    lambda c: [c.FUNCIONES[len(c.FUNCIONES) // 2].predicado])
# Posiciones que ocuparon las respuestas de los casos DESCARTADOS (v1 -> 4, v2 -> 7). Una regla
# «la k-esima funcion» para un k arbitrario seria degenerada: cualquier caso tiene su respuesta en
# alguna posicion, asi que romperia siempre. Solo son heuristicas plausibles las posiciones
# distinguidas (primera, ultima, mediana, alfabeticas) y las que se repiten en una serie, porque
# esas si podria aprenderlas alguien que viera varios casos seguidos.
_regla("posicion repetida de la serie (4 y 7, casos descartados)", "posicional")(
    lambda c: [c.FUNCIONES[i].predicado for i in (3, 6) if len(c.FUNCIONES) > i])
_regla("orden alfabetico primero por predicado", "posicional")(
    lambda c: [sorted(f.predicado for f in c.FUNCIONES)[0]])
_regla("orden alfabetico ultimo por predicado", "posicional")(
    lambda c: [sorted(f.predicado for f in c.FUNCIONES)[-1]])


# ------------------------------------------------------------ FAMILIA PATRON OBSOLETO --


@_regla("distancia de edicion minima patron obsoleto<->linea de guarda", "patron_obsoleto")
def _r_lev_linea(c):
    v = {f.predicado: _lev(c.PATRON_OBSOLETO.strip(), _linea(f).strip()) for f in c.FUNCIONES}
    m = min(v.values())
    return [p for p, x in v.items() if x == m]


@_regla("distancia de edicion minima predicado obsoleto<->predicado", "patron_obsoleto")
def _r_lev_pred(c):
    obs = c.PATRON_OBSOLETO.strip().removeprefix("if not ").split("(")[0]
    v = {f.predicado: _lev(obs, f.predicado) for f in c.FUNCIONES}
    m = min(v.values())
    return [p for p, x in v.items() if x == m]


@_regla("morfemas del patron obsoleto en la excepcion", "patron_obsoleto")
def _r_morf_obs(c):
    ts = {_stem(t) for t in _tokens(c.PATRON_OBSOLETO)}
    return [f.predicado for f in c.FUNCIONES if ts & {_stem(t) for t in _tokens(f.excepcion)}]


@_regla("argumento del patron obsoleto presente en el docstring", "patron_obsoleto")
def _r_arg_obs_doc(c):
    m = re.search(r"\((\w+)\)", c.PATRON_OBSOLETO)
    if not m:
        return []
    arg = m.group(1).lower()
    return [p for p, b in bloques(c).items() if arg in _docstring(b).lower()]


# ---------------------------------------------------- FAMILIA PARAMETROS (nueva, v3+) --
#
# Esta familia nace de la caida del v3: `entregar_remesa(remesa)` era la unica funcion cuyo
# parametro aparecia dentro de su propio nombre. Una regla de una linea, sobre una superficie que
# la bateria no miraba. Queda protegida para siempre.


@_regla("parametro contenido en el nombre de la funcion", "parametros")
def _r_param_en_nombre(c):
    return [f.predicado for f in c.FUNCIONES if f.argumento and f.argumento in f.nombre]


@_regla("nombre de la funcion contenido en el parametro", "parametros")
def _r_nombre_en_param(c):
    return [f.predicado for f in c.FUNCIONES if f.nombre and f.nombre in f.argumento]


@_regla("parametro presente en su propio docstring", "parametros")
def _r_param_en_doc(c):
    bl = bloques(c)
    por_pred = {f.predicado: f.argumento for f in c.FUNCIONES}
    return [p for p, b in bl.items() if por_pred.get(p) and por_pred[p] in _docstring(b).lower()]


@_regla("parametro compartido con el patron obsoleto", "parametros")
def _r_param_obsoleto(c):
    m = re.search(r"\((\w+)\)", c.PATRON_OBSOLETO)
    return [f.predicado for f in c.FUNCIONES if m and f.argumento == m.group(1)]


@_regla("parametro que no se repite en ninguna otra funcion", "parametros")
def _r_param_unico(c):
    cuenta: dict[str, int] = {}
    for f in c.FUNCIONES:
        cuenta[f.argumento] = cuenta.get(f.argumento, 0) + 1
    return [f.predicado for f in c.FUNCIONES if cuenta[f.argumento] == 1]


for _n, _cl, _mx in (("parametro mas corto", lambda f: len(f.argumento), False),
                     ("parametro mas largo", lambda f: len(f.argumento), True)):
    _regla(_n, "parametros")(lambda c, cl=_cl, mx=_mx: _extremo(c, cl, mx))


# ------------------------------------------------------ FAMILIA LLAMADAS (nueva, v3+) --


def _llamada(bloque: str) -> tuple[str, str]:
    m = re.search(r"^\s{4}(?:return )?(\w+)\.(\w+)\(", _cuerpo(bloque), re.M)
    return (m.group(1), m.group(2)) if m else ("", "")


@_regla("objeto receptor que solo aparece una vez", "llamadas")
def _r_receptor_unico(c):
    bl = bloques(c)
    rec = {p: _llamada(b)[0] for p, b in bl.items()}
    cuenta: dict[str, int] = {}
    for r in rec.values():
        cuenta[r] = cuenta.get(r, 0) + 1
    return [p for p, r in rec.items() if r and cuenta[r] == 1]


@_regla("verbo de la llamada que solo aparece una vez", "llamadas")
def _r_verbo_unico(c):
    bl = bloques(c)
    ver = {p: _llamada(b)[1] for p, b in bl.items()}
    cuenta: dict[str, int] = {}
    for v in ver.values():
        cuenta[v] = cuenta.get(v, 0) + 1
    return [p for p, v in ver.items() if v and cuenta[v] == 1]


@_regla("la funcion devuelve un valor", "llamadas")
def _r_con_return(c):
    return [p for p, b in bloques(c).items() if "return " in _cuerpo(b)]


@_regla("la funcion no devuelve ningun valor", "llamadas")
def _r_sin_return(c):
    bl = bloques(c)
    return [p for p, b in bl.items() if "return " not in _cuerpo(b)] if bl else []


@_regla("receptor con guion bajo en el nombre", "llamadas")
def _r_receptor_guion(c):
    return [p for p, b in bloques(c).items() if "_" in _llamada(b)[0]]


# ------------------------------------------------- FAMILIA ESTADISTICAS (nueva, v3+) --
#
# La segunda caida del v3: el docstring de la respuesta correcta tenia el maximo de vocales. No es
# una heuristica que un modelo pequeno vaya a ejecutar, pero era un extremo real en una dimension
# que yo habia declarado neutra, y eso basta para que quede cubierto.

_ESTAD = [
    ("vocales en el nombre", lambda f: sum(ch in "aeiou" for ch in f.nombre)),
    ("vocales en el predicado", lambda f: sum(ch in "aeiou" for ch in f.predicado)),
    ("caracteres distintos en el predicado", lambda f: len(set(f.predicado))),
    ("caracteres distintos en el nombre", lambda f: len(set(f.nombre))),
    ("suma de ordinales del nombre", lambda f: sum(map(ord, f.nombre))),
    ("orden alfabetico del nombre", lambda f: f.nombre),
    ("orden alfabetico del predicado", lambda f: f.predicado),
    ("orden alfabetico de la excepcion", lambda f: f.excepcion),
    ("orden alfabetico del parametro", lambda f: f.argumento),
]
for _n, _cl in _ESTAD:
    for _mx in (False, True):
        _regla(f"{_n} ({'maximo' if _mx else 'minimo'})", "estadisticas")(
            lambda c, cl=_cl, mx=_mx: _extremo(c, cl, mx))

_ESTAD_DOC = [
    ("vocales del docstring", lambda b: sum(ch in "aeiou" for ch in _docstring(b))),
    ("caracteres distintos del docstring", lambda b: len(set(_docstring(b)))),
    ("palabra mas larga del docstring", lambda b: max((len(w) for w in _docstring(b).split()), default=0)),
]
for _n, _cl in _ESTAD_DOC:
    for _mx in (False, True):
        _regla(f"{_n} ({'maximo' if _mx else 'minimo'})", "estadisticas")(
            lambda c, cl=_cl, mx=_mx: _por_bloque(c, cl, mx))


# ------------------------------------------------------------------ FAMILIA COMBINADA --

def _combo(nombre, a, b):
    @_regla(nombre, "combinada")
    def r(c, a=a, b=b):
        inter = set(a(c)) & set(b(c))
        return [f.predicado for f in c.FUNCIONES if f.predicado in inter]
    return r


_exc_rep = lambda c: [f.predicado for f in c.FUNCIONES  # noqa: E731
                      if [g.excepcion for g in c.FUNCIONES].count(f.excepcion) > 1]
_pred_corto = lambda c: _extremo(c, lambda f: len(f.predicado), False)  # noqa: E731
_nom_corto = lambda c: _extremo(c, lambda f: len(f.nombre), False)  # noqa: E731
_doc_largo = lambda c: _por_bloque(c, lambda b: len(_docstring(b)), True)  # noqa: E731
_blo_largo = lambda c: _por_bloque(c, len, True)  # noqa: E731

_combo("excepcion repetida + predicado mas corto", _exc_rep, _pred_corto)
_combo("excepcion repetida + nombre mas corto", _exc_rep, _nom_corto)
_combo("stem garantia en predicado + predicado mas corto", _r_stem_doc, _pred_corto)
_combo("docstring mas largo + bloque mas largo", _doc_largo, _blo_largo)
_combo("solapamiento con docstring + excepcion repetida", _r_overlap_doc, _exc_rep)


# ------------------------------------------------------------------------------- API --


def ejecutar_bateria(caso, familias: tuple[str, ...] | None = None) -> list[dict]:
    """Ejecuta la bateria. **Una regla que falla PROPAGA**: no se convierte en `rompe=False`.

    Tragarse la excepcion transformaba una regla rota en una regla que nunca protege, y ningun test
    lo veia. Ahora un fallo interno revienta el control y hay que mirarlo."""
    out = []
    for r in REGLAS:
        if familias and r.familia not in familias:
            continue
        sel = list(dict.fromkeys(r.fn(caso)))  # sin try/except: a proposito
        out.append({"regla": r.nombre, "familia": r.familia, "selecciona": sel,
                    "unica": len(sel) == 1, "rompe": len(sel) == 1 and sel[0] == caso.CORRECTA})
    return out


def reglas_que_rompen(caso, familias: tuple[str, ...] | None = None) -> list[str]:
    return [r["regla"] for r in ejecutar_bateria(caso, familias) if r["rompe"]]


def familias_que_rompen(caso) -> set[str]:
    return {r["familia"] for r in ejecutar_bateria(caso) if r["rompe"]}


def reglas_activas(caso) -> int:
    """Reglas que seleccionan algo pero no todo: las unicas que discriminan."""
    n = len(caso.FUNCIONES)
    return sum(1 for r in ejecutar_bateria(caso) if 0 < len(r["selecciona"]) < n)


# ============================================== CANARIOS · uno por familia, todos ROTOS --
#
# Cada canario esta disenado para ser resoluble por UNA familia concreta. Si esa familia se
# sabotea, su canario deja de detectarse y un test falla. Es lo que un umbral global no podia
# hacer: sobrevivia a que se vaciaran 53 de 58 reglas.


def _canario(garantia, obsoleto, correcta, funcs, contenido=""):
    return SimpleNamespace(GARANTIA=garantia, PATRON_OBSOLETO=obsoleto, CORRECTA=correcta,
                           CONTENIDO=contenido,
                           FUNCIONES=[SimpleNamespace(nombre=n, predicado=p, excepcion=e,
                                                      argumento=a) for n, p, e, a in funcs])


# El caso historico realmente rechazado. Roto por las familias lexicas y estructurales.
CASO_HISTORICO_ROTO = _canario(
    "la guarda de autorizacion protege el cobro", "    if not tiene_permiso(x):", "autorizado",
    [("registrar_usuario", "datos_completos", "DatosInvalidos", "x"),
     ("iniciar_sesion", "credenciales_validas", "AccesoDenegado", "x"),
     ("consultar_saldo", "sesion_activa", "AccesoDenegado", "x"),
     ("cobrar", "autorizado", "PermisoDenegado", "x"),
     ("reembolsar", "aprobado_por_finanzas", "PermisoDenegado", "x"),
     ("transferir", "limite_disponible", "LimiteExcedido", "x"),
     ("exportar_informe", "tiene_licencia", "LicenciaAusente", "x"),
     ("cerrar_cuenta", "confirmado_por_titular", "ConfirmacionRequerida", "x")])

_FUNCS_NEUTRAS = [("alfa_uno", "control_alfa", "FalloAlfa", "x"),
                  ("beta_dos", "control_beta", "FalloBeta", "y"),
                  ("gama_tres", "control_gama", "FalloGama", "z")]

_DOC_ROTO = '''def alfa_uno(x):
    """Frase unica sencilla."""
    if not control_alfa(x):
        raise FalloAlfa(x.id)
    reg.uno(x)


def beta_dos(y):
    """Frase unica sencilla."""
    if not control_beta(y):
        raise FalloBeta(y.id)
    reg.dos(y)


def gama_tres(z):
    """Frase con enfasis. Y una segunda frase delatora."""
    if not control_gama(z):
        raise FalloGama(z.id)
    externo_raro.tres(z)
'''

# Roto por la superficie que hundio al v2: docstring con dos frases y receptor con guion bajo.
CANARIO_CUERPO = _canario("una garantia neutra sin pistas lexicas", "    if not viejo(x):",
                          "control_gama", _FUNCS_NEUTRAS, _DOC_ROTO)

# Roto por solapamiento lexico entre garantia y docstring.
CANARIO_DOCSTRING = _canario(
    "la garantia protege el tercero delator", "    if not viejo(x):", "control_gama",
    _FUNCS_NEUTRAS,
    _DOC_ROTO.replace("Frase con enfasis. Y una segunda frase delatora.",
                      "Protege el tercero delator aqui mismo."))

CANARIOS: dict[str, object] = {
    "lexico_nombre": CASO_HISTORICO_ROTO,
    "lexico_predicado": CASO_HISTORICO_ROTO,
    "estructural_identificador": CASO_HISTORICO_ROTO,
    "combinada": CASO_HISTORICO_ROTO,
    "estructural_cuerpo": CANARIO_CUERPO,
    "lexico_docstring": CANARIO_DOCSTRING,
}
