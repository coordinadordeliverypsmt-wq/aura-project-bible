"""Aritmetica determinista: `1+1` lo resuelve el nucleo, no el modelo.

## El defecto

    tu> cuanto es 1+1
    AURA> Entendido.

`«cuanto es 1+1»` no tenia superficie propia, asi que recorria la cascada entera y terminaba en el
enrutador. Alli el proveedor devuelve una respuesta enlatada —`router.py:51`— y el usuario recibe
«Entendido.» a una pregunta con UNA respuesta correcta.

Que la respuesta fuera mala en el modo simulado y quiza buena con un modelo real es justamente el
problema: **una suma no es una inferencia**. Es la misma regla que ADR-0014 aplica al resto del
sistema —los hechos los responde el nucleo—, y aqui hay poco margen de duda sobre si `1+1` es un
hecho.

## Por que un parser y no `eval`

`eval("1+1")` funciona, y tambien funciona `eval("__import__('os').system('rm -rf ~')")`. El texto
viene del usuario, asi que la unica postura defendible es la contraria: **se acepta una lista de
nodos y se rechaza todo lo demas**. Aqui solo viven numeros enteros, los cuatro operadores, el signo
unario y los parentesis. Una llamada, un nombre, un atributo o una potencia no se rechazan por una
comprobacion que alguien pueda olvidar: **no tienen caso en el evaluador**, asi que no hay camino.

## Exactitud, y no fingirla

Se calcula con `Fraction`, no con `float`: `0.1 + 0.2` en coma flotante no es `0.3`, y una capacidad
que existe para dar la respuesta correcta no puede empezar por el redondeo. Al presentar:

- entero exacto            -> `12 / 4` = `3`
- decimal que TERMINA      -> `7 / 2` = `3.5`
- decimal que NO termina   -> `1 / 3` = `1/3`, la fraccion exacta

Lo ultimo es deliberado. Escribir `0.3333` seria inventar un final que ese numero no tiene, y este
proyecto ya tiene bastante con los datos que se rellenan solos.

## Cuando NO contesta

Si la frase no es aritmetica —o no se puede resolver con seguridad— devuelve `None` y el turno sigue
su camino de siempre. No se responde «no lo se»: se deja pasar, que es distinto y no roba el turno a
ninguna otra superficie.
"""

from __future__ import annotations

import ast
import re
import unicodedata
from fractions import Fraction

#: Cotas. No son adornos: con `*` encadenado se pueden construir enteros de millones de digitos, y
#: multiplicarlos bloquea el turno. Un limite visible es preferible a descubrirlo colgado.
MAX_CARACTERES = 200
MAX_OPERADORES = 32
MAX_DIGITOS = 15

#: Formas de pedirlo en castellano. La lista es POSITIVA y CERRADA: se retiran del principio de la
#: frase y lo que queda tiene que ser una expresion por si mismo.
ENTRADILLAS = (
    "cuanto es", "cuanto son", "cuanto da", "cuantos son", "cuanto vale",
    "calcula", "calculame", "resultado de", "dime cuanto es",
)

#: Operadores dichos con palabras. El orden importa: «dividido entre» antes que «entre», o la
#: primera se quedaria a medias.
PALABRAS = (
    (" dividido entre ", " / "),
    (" dividido por ", " / "),
    (" multiplicado por ", " * "),
    (" mas ", " + "),
    (" menos ", " - "),
    (" por ", " * "),
    (" entre ", " / "),
)

#: Lo unico que puede quedar tras traducir. Que la comprobacion sea sobre el texto ENTERO es lo que
#: impide que «borra 2 archivos» o «gracias por todo» se cuelen como aritmetica.
_SEGURO = re.compile(r"^[\d\s+\-*/().]+$")

_OPERADORES = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
               ast.Mult: lambda a, b: a * b}


class NoEsAritmetica(Exception):
    """La frase no es una expresion aritmetica que se pueda resolver con seguridad."""


class DivisionPorCero(Exception):
    """Aritmeticamente indefinida. Es un resultado, no un fallo del reconocimiento."""


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("¿", " ").replace("?", " ").replace("¡", " ").replace("!", " ").strip(" .\t\n")


def expresion_en(texto: str) -> str | None:
    """La expresion aritmetica contenida en la frase, ya en simbolos, o `None`.

    Devolver la expresion en vez de un booleano junta las dos preguntas -«¿es aritmetica?» y «¿cual
    es?»- para que no puedan responderse por separado y contradecirse."""
    if not texto or len(texto) > MAX_CARACTERES:
        return None
    t = _normalizar(texto)
    for entradilla in ENTRADILLAS:
        if t.startswith(entradilla):
            t = t[len(entradilla):].strip()
            break
    # Se rodea de espacios para que las palabras-operador casen tambien al principio y al final.
    t = f" {t} "
    for palabra, simbolo in PALABRAS:
        t = t.replace(palabra, simbolo)
    t = t.strip()
    if not t or not _SEGURO.match(t):
        return None
    if not any(c in t for c in "+-*/"):
        # Un numero suelto no es una operacion. Sin esto, «7» se contestaria «7.», que es cierto e
        # inutil, y ademas le robaria el turno a cualquier frase que fuera solo un numero.
        return None
    if sum(t.count(c) for c in "+-*/") > MAX_OPERADORES:
        return None
    if any(len(n) > MAX_DIGITOS for n in re.findall(r"\d+", t)):
        return None
    return t


def _evaluar(nodo) -> Fraction:
    """Evalua SOLO los nodos permitidos. Lo demas no tiene caso: no hay camino, no hay excepcion que
    olvidar poner."""
    if isinstance(nodo, ast.Expression):
        return _evaluar(nodo.body)
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, int) and not isinstance(nodo.value, bool):
            return Fraction(nodo.value)
        raise NoEsAritmetica(f"solo numeros enteros: {nodo.value!r}")
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.UAdd, ast.USub)):
        valor = _evaluar(nodo.operand)
        return -valor if isinstance(nodo.op, ast.USub) else valor
    if isinstance(nodo, ast.BinOp):
        izquierda, derecha = _evaluar(nodo.left), _evaluar(nodo.right)
        if isinstance(nodo.op, ast.Div):
            if derecha == 0:
                raise DivisionPorCero("division por cero")
            return izquierda / derecha
        operador = _OPERADORES.get(type(nodo.op))
        if operador is None:
            raise NoEsAritmetica(f"operador no permitido: {type(nodo.op).__name__}")
        return operador(izquierda, derecha)
    raise NoEsAritmetica(f"nodo no permitido: {type(nodo).__name__}")


def evaluar(expresion: str) -> Fraction:
    """El valor exacto de la expresion. Lanza `NoEsAritmetica` o `DivisionPorCero`."""
    try:
        arbol = ast.parse(expresion, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError) as e:
        raise NoEsAritmetica(str(e)) from e
    return _evaluar(arbol)


def formatear(valor: Fraction) -> str:
    """El numero como lo escribiria una persona, **sin inventar precision**."""
    if valor.denominator == 1:
        return str(valor.numerator)
    resto = valor.denominator
    for primo in (2, 5):
        while resto % primo == 0:
            resto //= primo
    if resto == 1:
        # El decimal TERMINA, asi que se puede escribir entero y sigue siendo exacto.
        texto = f"{float(valor):.10f}".rstrip("0").rstrip(".")
        return texto
    # No termina. Se da la fraccion exacta antes que un decimal recortado que parecería el resultado.
    return f"{valor.numerator}/{valor.denominator}"


def resolver(texto: str) -> str | None:
    """La respuesta a una frase aritmetica, o `None` si no lo es.

    `None` significa «esto no es mio»: el turno sigue su camino. No se contesta «no lo se», que
    ademas de inutil le habria robado el turno a las superficies siguientes."""
    expresion = expresion_en(texto)
    if expresion is None:
        return None
    try:
        numero = formatear(evaluar(expresion))
    except DivisionPorCero:
        # Es aritmetica y su respuesta es que no existe. Devolverla aqui es mas honesto que dejarla
        # caer al modelo, que contestaria cualquier cosa a una operacion sin resultado.
        return "Una división entre cero no está definida."
    except NoEsAritmetica:
        return None
    # El punto es puntuacion de la frase, no del numero: detras de «3.5» sobra y se lee como errata.
    return f"{numero}." if "." not in numero else numero


__all__ = ["resolver", "expresion_en", "evaluar", "formatear",
           "NoEsAritmetica", "DivisionPorCero", "ENTRADILLAS", "PALABRAS",
           "MAX_CARACTERES", "MAX_OPERADORES", "MAX_DIGITOS"]
