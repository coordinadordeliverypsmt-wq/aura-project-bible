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

from .estatus import Estatus
from .intencion import _PIDE_CANTIDAD as _PIDE_CANTIDAD_COGNITIVA
from .intencion import _SUPOSICION_COGNITIVA

# Las dos de arriba se REUTILIZAN, no se duplican: son las MISMAS listas que gobiernan la rama
# numerica de `es_cognicion_general` (comprobado: `intencion.py` no importa `aritmetica`, no hay
# ciclo). Que `resolver_formal` cubra esa rama por completo deja de depender de mantener dos copias
# en sincronia.

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


# ============================================================================================
# RAZONAMIENTO FORMAL EN LENGUAJE NATURAL (D-FC-4 = A, CEO 2026-09-13)
#
# El defecto medido: «si tengo 4 manzanas y me como una, cuantas manzanas me quedan?» no lo
# reconocia `resolver` -no es una expresion, es una frase- y caia en el LLM qwen2.5:0.5b, que
# tardo 248 s y contesto «0» en vez de 3. La decision del CEO es tajante: el razonamiento formal
# en lenguaje natural pertenece al Core CUANDO SE EXTRAE CON CERTEZA; si esta infradeterminado,
# el Core pregunta -nunca adivina, y el LLM deja de usarse como calculadora.
#
# LA GRAMATICA ES DELIBERADAMENTE PEQUENA. No es un parser de lenguaje natural: reconoce UNA
# forma -«(si )?tengo N <objeto>» seguido de UNA clausula de operacion con un verbo de una lista
# CERRADA y UNA cantidad, y una pregunta que pide cantidad-. Todo lo que no encaja en esa forma
# exacta, pero TIENE forma cuantitativa (cifra + pregunta de cantidad + premisa), se responde con
# ACLARACION: nunca se adivina cual de las lecturas posibles es la correcta.
#
# POR QUE TIENE QUE CUBRIR LA RAMA NUMERICA DE `intencion.es_cognicion_general`. Esa funcion deja
# pasar al LLM «suposicion + cifra + pide cantidad» (su rama de `_SUPOSICION_COGNITIVA`). Como
# `resolver_formal` se evalua ANTES en la cascada del orquestador, todo lo que esa rama acepta
# tiene que salir de aqui como HECHO o ACLARACION: si `resolver_formal` devolviera `None` para uno
# de esos casos, el turno seguiria cayendo en el LLM y el defecto medido seguiria vivo.
#
# HUECO REAL MEDIDO Y CERRADO (arquitecto, 2026-09-13): la primera version de la compuerta exigia
# que la pregunta de cantidad terminara en «quedan/queda/tengo/tendre/hay». La rama numerica de
# `intencion` no exige eso -solo que la SUBCADENA «cuanto/cuantos/cuantas/cuanta» aparezca en
# CUALQUIER posicion, junto a una suposicion y un digito-, asi que frases como «si un coche cuesta
# 2000 euros al mes, cuanto cuesta en un ano?» activaban esa rama pero `resolver_formal` devolvia
# `None`: el LLM seguia de calculadora. La compuerta de abajo reutiliza las MISMAS constantes de
# `intencion` -no las duplica- para que ser al menos tan ancha como esa rama sea una propiedad
# verificable, no una coincidencia entre dos listas mantenidas por separado.
#
# LIMITACIONES DECLARADAS (no se implementan, y no se finge que si): fechas y unidades de medida.
# «tengo 2 kilos de manzanas y como 1 manzana» no detecta el cambio de unidad -kilos vs manzanas-;
# el sustantivo capturado es el que sigue inmediatamente a la cantidad, sin normalizar unidades.
# Un valor numerico que no puede derivarse con certeza de la gramatica declarada aqui no se
# publica como HECHO: eso es exactamente lo que produce ACLARACION.

#: Numerales en palabras que la gramatica reconoce, ademas de las cifras. Lista CERRADA: un
#: numeral que no este aqui no se interpreta -y por construccion del cierre (ver mas abajo) eso
#: hace fallar la extraccion y termina en ACLARACION, nunca en una cifra inventada.
_NUMERALES = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}

#: Verbos que RESTAN de la posesion inicial. Lista positiva y cerrada -igual que `ENTRADILLAS`
#: arriba-: un verbo que no este aqui no se reconoce como operacion.
_VERBOS_RESTAR = ("me como", "como", "pierdo", "regalo", "doy", "gasto", "vendo", "uso", "rompo")

#: Verbos que SUMAN a la posesion inicial. Misma politica: cerrada y positiva.
_VERBOS_SUMAR = ("compro", "me dan", "me regalan", "encuentro", "gano", "recibo", "consigo")

#: Palabras que introducen un PRECIO. La gramatica no calcula dinero -no distingue precio unitario
#: de precio total-, asi que su sola presencia basta para pedir ACLARACION en vez de adivinar
#: cual de las dos lecturas es la que el usuario queria.
_PALABRAS_PRECIO = ("cuesta", "cuestan", "vale", "valen", "precio")

#: Marca de que el turno trae una PREMISA sobre la que razonar. `_SUPOSICION_COGNITIVA` -importada
#: de `intencion`, no copiada- ya trae «si », «supongamos que», «supon que», «imagina que», «si
#: fuera», «si todos», «si cada»; aqui solo se anaden las marcas que esa lista no nombra: `tengo`
#: -la premisa de posesion de esta gramatica-, y las de precio (`compro/cuesta/cuestan/vale/valen`)
#: -que abajo disparan ACLARACION en vez de un calculo de dinero que esta gramatica no hace-. Sin
#: ninguna marca, una cifra suelta con una pregunta de cantidad no es un problema formal -es, por
#: ejemplo, «¿cuantos hijos tengo?», que no trae ningun dato para calcular y su sitio es la
#: memoria personal, no el razonamiento formal.
_MARCA_PREMISA = ("tengo", "compro", "cuesta", "cuestan", "vale", "valen") + _SUPOSICION_COGNITIVA

#: La pregunta tiene que pedir CANTIDAD. Reutiliza -no copia- `_PIDE_CANTIDAD` de `intencion`:
#: exactamente la misma prueba de sustancia, «cuanto/cuantos/cuantas/cuanta» en CUALQUIER
#: posicion, que decide si la rama numerica de `es_cognicion_general` se activa. Una version mas
#: estrecha -exigir que la pregunta terminara en «quedan/tengo/hay»- fue el hueco medido: dejaba
#: pasar al LLM frases como «si un coche cuesta 2000 euros al mes, cuanto cuesta en un ano?», que
#: la rama numerica SI aceptaba. Ser al menos tan ancha como esa rama es la propiedad que este
#: modulo tiene que sostener, y `test_razonamiento_formal.py` la fija con una bateria.


def _patron_verbo(frase: str) -> str:
    """`"me como"` -> `r"me\\s+como"`: tolera el espacio exacto que separe las palabras."""
    return r"\s+".join(re.escape(palabra) for palabra in frase.split())


#: Alternancia de numerales, mas larga primero para que un prefijo compartido no oculte a otro
#: -aunque los bordes de palabra (`\b`) ya bastarian, el orden hace la intencion explicita-.
_ALT_NUMERAL = "|".join(sorted((re.escape(p) for p in _NUMERALES), key=len, reverse=True))
_CIFRA = rf"(?:\d+|{_ALT_NUMERAL})"

#: La premisa de posesion: «(si )?tengo N <objeto>». El objeto es UNA palabra -sin ella la
#: gramatica tendria que decidir donde termina un sustantivo compuesto, y eso es exactamente el
#: tipo de ambiguedad que esta capacidad prefiere declarar como limitacion antes que adivinar.
_RE_PREMISA = re.compile(rf"\btengo\s+(?P<cifra>{_CIFRA})\s+(?P<obj>[a-z]+)")

#: Una clausula de operacion: uno de los verbos cerrados seguido de una cantidad. Restar y sumar
#: viven en grupos con nombre distinto para que el signo salga de QUE grupo caso, nunca de mirar
#: el texto capturado -evita tener que volver a comparar contra las dos listas.
_ALT_RESTAR = "|".join(_patron_verbo(v) for v in sorted(_VERBOS_RESTAR, key=len, reverse=True))
_ALT_SUMAR = "|".join(_patron_verbo(v) for v in sorted(_VERBOS_SUMAR, key=len, reverse=True))
_RE_OPERACION = re.compile(
    rf"\b(?:(?P<restar>{_ALT_RESTAR})\s+(?P<cifra_r>{_CIFRA})"
    rf"|(?P<sumar>{_ALT_SUMAR})\s+(?P<cifra_s>{_CIFRA}))\b"
)

#: La respuesta cuando la forma es cuantitativa pero no se puede resolver con certeza. NUNCA
#: afirma un dato personal -no repite cifras ni objetos del turno-, y sugiere reformular como una
#: operacion pura, que es el camino que `resolver` ya sabe resolver sin ambiguedad.
_PREGUNTA_ACLARACION = (
    "No puedo calcularlo con certeza a partir de esa frase. "
    "¿Qué operación quieres exactamente? Por ejemplo: «cuánto es 4 - 1»."
)


def _plegar(texto: str) -> str:
    """Version del texto para reconocer patrones: minusculas, sin tildes, sin signos de pregunta
    o exclamacion. Cada caracter se sustituye por exactamente un caracter -nunca se recorta el
    texto-, asi que un indice encontrado aqui senala el MISMO caracter en `texto`. Eso es lo que
    permite recortar el sustantivo del texto ORIGINAL, con su mayuscula y su tilde, tal como lo
    escribio el usuario (ADR-0017)."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    for signo in "¿?¡!":
        t = t.replace(signo, " ")
    return t


def _numero(token: str) -> int | None:
    """El valor de una cifra o un numeral en palabras, o `None` si no se reconoce ninguno de los
    dos -que con la gramatica cerrada de arriba no deberia ocurrir, pero declarar el `None` es mas
    honesto que asumir que el regex nunca se equivoca."""
    if token.isdigit():
        if len(token) > MAX_DIGITOS:
            return None
        return int(token)
    return _NUMERALES.get(token)


def _forma_cuantitativa(texto: str, plegado: str) -> bool:
    """La frase TIENE forma de problema cuantitativo: hay cifra, se pide una cantidad y hay una
    premisa sobre la que razonar. A partir de aqui, `resolver_formal` ya no puede devolver `None`
    -es la condicion que hace que la rama numerica de `intencion.es_cognicion_general` quede
    cubierta por completo: lo que ella acepta, esta funcion lo detecta primero."""
    tiene_cifra = any(ch.isdigit() for ch in texto) or any(
        f" {n} " in f" {plegado} " for n in _NUMERALES
    )
    pide_cantidad = any(p in plegado for p in _PIDE_CANTIDAD_COGNITIVA)
    tiene_premisa = any(marca in plegado for marca in _MARCA_PREMISA)
    return tiene_cifra and pide_cantidad and tiene_premisa


def resolver_formal(texto: str) -> tuple[str, str] | None:
    """Razonamiento formal en lenguaje natural: `(estatus, respuesta)` o `None`.

    * `None` — no es un problema formal. El turno sigue su cascada de siempre.
    * `(Estatus.HECHO.value, respuesta)` — resuelto con certeza: una expresion pura (identica a
      `resolver`) o un problema verbal de UNA premisa y UNA operacion, ambas dentro de la
      gramatica cerrada declarada arriba.
    * `(Estatus.ACLARACION.value, pregunta)` — la frase TIENE forma cuantitativa -cifra, premisa y
      pregunta de cantidad- pero esta infradeterminada para esta gramatica: mas de una operacion,
      un verbo fuera de las listas cerradas, un precio (unitario o total, ambiguo por construccion)
      o un resultado negativo en un consumo. Nunca se adivina cual era la lectura correcta.

    Vease el bloque de comentarios que antecede a este modulo para el porque de la gramatica, sus
    limites deliberados (fechas y unidades no se implementan) y por que cubre la rama numerica de
    `intencion.es_cognicion_general`.
    """
    if not texto or len(texto) > MAX_CARACTERES:
        return None

    # 1. Expresion pura: EXACTAMENTE el mismo camino y la misma respuesta que hoy.
    respuesta = resolver(texto)
    if respuesta is not None:
        return (Estatus.HECHO.value, respuesta)

    plegado = _plegar(texto)
    if not _forma_cuantitativa(texto, plegado):
        return None

    # A partir de aqui la frase TIENE forma de problema cuantitativo: la unica salida honesta es
    # HECHO o ACLARACION. `None` dejaria caer el turno en el LLM, que es justo lo que D-FC-4 = A
    # prohibe: el modelo nunca se usa como calculadora.

    # 2. Un precio (unitario o total) es ambiguo por construccion: esta gramatica no hace dinero.
    if any(palabra in plegado for palabra in _PALABRAS_PRECIO):
        return (Estatus.ACLARACION.value, _PREGUNTA_ACLARACION)

    # 3. La premisa de posesion: «tengo N <objeto>».
    m_premisa = _RE_PREMISA.search(plegado)
    if m_premisa is None:
        return (Estatus.ACLARACION.value, _PREGUNTA_ACLARACION)

    cantidad = _numero(m_premisa.group("cifra"))
    if cantidad is None:
        return (Estatus.ACLARACION.value, _PREGUNTA_ACLARACION)
    sustantivo = texto[m_premisa.start("obj"):m_premisa.end("obj")]

    # 4. Exactamente UNA clausula de operacion, buscada solo DESPUES de la premisa -para que la
    # propia cifra de «tengo N» nunca se cuente a si misma como si fuera una operacion.
    operaciones = list(_RE_OPERACION.finditer(plegado, m_premisa.end()))
    if len(operaciones) != 1:
        # Cero es tan infradeterminado como dos: la gramatica declarada exige UNA operacion, y
        # «ningun verbo reconocido» y «mas de un verbo reconocido» son las dos formas de faltar a
        # eso -incluye el verbo desconocido, que sencillamente no genera ninguna coincidencia.
        return (Estatus.ACLARACION.value, _PREGUNTA_ACLARACION)

    operacion = operaciones[0]
    if operacion.group("restar") is not None:
        cantidad_operacion = _numero(operacion.group("cifra_r"))
        signo = -1
    else:
        cantidad_operacion = _numero(operacion.group("cifra_s"))
        signo = 1
    if cantidad_operacion is None:
        return (Estatus.ACLARACION.value, _PREGUNTA_ACLARACION)

    resultado = cantidad + signo * cantidad_operacion
    if resultado < 0:
        # Un consumo que deja un conteo negativo no es un hecho del mundo: es una premisa que no
        # cuadra, y adivinar cual de los datos esta mal seria fabricar.
        return (Estatus.ACLARACION.value, _PREGUNTA_ACLARACION)

    return (Estatus.HECHO.value, f"Te quedan {resultado} {sustantivo}.")


__all__ = ["resolver", "resolver_formal", "expresion_en", "evaluar", "formatear",
           "NoEsAritmetica", "DivisionPorCero", "ENTRADILLAS", "PALABRAS",
           "MAX_CARACTERES", "MAX_OPERADORES", "MAX_DIGITOS"]
