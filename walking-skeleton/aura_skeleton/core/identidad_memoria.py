"""Qué atributo declara una frase, y cuál pregunta — AMP-AURA etapas 1-2 (CEO, 2026-09-10).

**Por qué existe este módulo y no es un refactor gratuito.** La misma gramática tiene que servir a dos
sitios que no pueden importarse entre sí: el **orquestador** la usa para RESPONDER («¿cual es mi X?» →
el hecho vigente) y el **ejecutor del modelo de usuario** la necesita para ESCRIBIR (saber que «mi
cumpleaños es el 3 de junio» declara el mismo atributo que una entrada anterior, y por tanto la
supersede). `orchestrator` ya importa `EjecutorModeloUsuario`, así que la dirección contraria seria un
import circular; y duplicar las expresiones habria creado dos definiciones de «mismo atributo» que
divergirian en el primer cambio. La logica se mueve aqui SIN alterarla: una sola fuente de verdad.

**Lo que este modulo NO hace**, y es deliberado — son decisiones pospuestas del CEO:
  * no resuelve alias («cumpleaños» = «fecha de nacimiento»): eso es `D-AMP-5`, POSPUESTA;
  * no propone nada ni consulta al modelo: no hay `PROPOSE` en esta etapa (`D-AMP-4`);
  * la identidad NO se persiste como campo: solo se calcula para encontrar la version anterior.
"""

from __future__ import annotations

import re
import unicodedata

#: El valor se extrae del texto ORIGINAL, no del normalizado: el dato es del usuario y se le repite como
#: el lo escribio —«cumpleaños», no «cumpleanos»— (ADR-0017, fidelidad al modelo). De ahi `[^\W\d_]`,
#: que acepta letras acentuadas; la comparacion del atributo si se hace normalizada.
_ATRIBUTO_DECLARADO = re.compile(
    r"\bmi ([^\W\d_]+(?: [^\W\d_]+)?) (?:es|son)\s+(?:el|la|los|las|un|una|unos|unas)?\s*(.+)$", re.IGNORECASE
)

#: «Me llamo X» dice exactamente lo mismo que «mi nombre es X», y hasta la campaña del 2026-09-27 no se
#: reconocia: medido `[EJEC]`, «me llamo Mauricio» + «me llamo Pedro» dejaba LOS DOS vigentes y AURA
#: afirmaba dos nombres a la vez, mientras «mi nombre es» versionaba bien. Anclado al principio de la
#: frase: «¿como me llamo?» es una pregunta, no una declaracion, y no puede coincidir.
_ME_LLAMO = re.compile(r"^\s*(?:yo\s+)?me\s+llamo\s+(.+)$", re.IGNORECASE)

#: La normalizacion del orquestador conserva «¿» —solo quita diacriticos—, asi que el anclaje tiene que
#: admitirlo: sin esto «¿Cual es mi cumpleanos?» no casaba y el turno se iba al modelo.
_ATRIBUTO_PREGUNTADO = re.compile(r"^¿?(?:cual|cuales) (?:es|son) mi ([a-z]+(?: [a-z]+)?)\s*\??$")

# ------------------------------------------------- PREGUNTAS DE HISTORIAL (AMP-AURA etapas 1-2, cont.) --
#
# Tres formas, cada una su propio patron compilado -legible por separado, en vez de una alternativa
# gigante-. Mismo anclaje y mismo grupo de atributo que `_ATRIBUTO_PREGUNTADO`: la coincidencia debe ser
# exacta con la pregunta de historial, nunca una subcadena de otra cosa (CHECKLIST §4.6).
_PASADO_CUAL_ERA = re.compile(r"^¿?(?:cual|cuales) (?:era|eran|fue|fueron) mi ([a-z]+(?: [a-z]+)?)\s*\??$")
_PASADO_QUE_ME_DIJISTE = re.compile(r"^¿?que me dijiste (?:antes )?(?:de|sobre) mi ([a-z]+(?: [a-z]+)?)\s*\??$")
_PASADO_ANTERIOR = re.compile(r"^¿?cual es mi ([a-z]+(?: [a-z]+)?) anterior\s*\??$")

_PATRONES_PASADO = (_PASADO_CUAL_ERA, _PASADO_QUE_ME_DIJISTE, _PASADO_ANTERIOR)

# ------------------------------------------------------ EVOCACION DE HECHOS (DR-1, CEO 2026-09-15) --
#
# «¿te acuerdas de lo que te dije?» caia en la puerta de ADR-0014 y AURA respondia «No tengo ningun
# recuerdo» con el modelo de usuario lleno: la busqueda lexica no encuentra nada en esa frase. Medido: 5
# de 7 evocaciones genericas fallaban. DR-1 = A: una superficie DETERMINISTA que responde desde el Core.
#
# Anclada como todas las gramaticas de este modulo: tiene que SER la frase entera. Y deliberadamente NO
# reconoce «¿de que hablamos?»: eso es evocacion CONVERSACIONAL, no de hechos —la alternativa C, que
# DR-1 no aprobo—, y responderla con hechos seria contestar otra pregunta.
_VERBO_EVOCAR = r"(?:te acuerdas de|recuerdas|sabes)"
_VERBO_DECIR = r"(?:dije|conte|he dicho|he contado)"
_EVOCACION_GENERICA = (
    re.compile(rf"^¿?{_VERBO_EVOCAR} (?:lo que|que) te {_VERBO_DECIR}(?: antes)?\s*\??$"),
    re.compile(rf"^¿?que te {_VERBO_DECIR}(?: antes)?\s*\??$"),
)
#: «¿te acuerdas de mi color favorito?» nombra un atributo concreto: se responde como «¿cual es mi X?».
_EVOCACION_ATRIBUTO = re.compile(r"^¿?(?:te acuerdas de|recuerdas) mi ([a-z]+(?: [a-z]+)?)\s*\??$")


def normalizar(texto: str) -> str:
    """Minusculas sin diacriticos. Identica a la del orquestador: comparar «cumpleaños» con
    «cumpleanos» no puede depender de como se escribio el acento."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def atributo_preguntado(t: str) -> str | None:
    """El atributo que una pregunta posesiva nombra, o None si no es una de ellas."""
    hallado = _ATRIBUTO_PREGUNTADO.match(t.strip())
    return hallado.group(1).strip() if hallado else None


def atributo_preguntado_en_pasado(t: str) -> str | None:
    """El atributo que una pregunta de HISTORIAL nombra, o None si no es una de ellas.

    Reconoce solo la familia POSESIVA («mi X»), y por una razon precisa: `atributo_declarado` -de
    quien depende `identidad_de`- solo reconoce «mi X es Y», asi que SOLO esa familia queda versionada
    con `version`/`supersedes`/`valid_from`/`valid_until`. «Me llamo Mauricio» no encaja en «mi X es
    Y», nunca tiene `version`, y por tanto no tiene historial real del que hablar. Reconocer aqui una
    forma no posesiva prometeria un historial que el sistema no puede tener: fingir capacidad (INV-9).

    Las tres formas reconocidas viven en `_PATRONES_PASADO`, cada una anclada igual que
    `_ATRIBUTO_PREGUNTADO` (`^¿?...\\s*\\??$`): sin eso, una frase que solo CONTUVIERA el patron -no que
    FUERA la pregunta- tambien caeria aqui y le robaria el turno a otra superficie.
    """
    texto = t.strip()
    for patron in _PATRONES_PASADO:
        hallado = patron.match(texto)
        if hallado:
            return hallado.group(1).strip()
    return None


def es_evocacion_generica(t: str) -> bool:
    """True si la frase pide, sin nombrar ningun atributo, lo que el usuario le ha dicho a AURA."""
    texto = t.strip()
    return any(p.match(texto) for p in _EVOCACION_GENERICA)


def atributo_evocado(t: str) -> str | None:
    """El atributo que nombra una evocacion («¿te acuerdas de mi X?»), o None."""
    hallado = _EVOCACION_ATRIBUTO.match(t.strip())
    return hallado.group(1).strip() if hallado else None


def atributo_declarado(contenido: str) -> tuple[str, str] | None:
    """El par (atributo, valor) de una declaracion posesiva, extraido de SU PROPIA frase."""
    hallado = _ATRIBUTO_DECLARADO.search(contenido)
    if not hallado:
        propio = _ME_LLAMO.match(contenido)
        if not propio:
            return None
        valor = re.split(r"\s+(?:y|pero|aunque|porque)\s+|[,;.]", propio.group(1))[0].strip(" .,;:!?")
        return ("nombre", valor) if valor else None
    # No glotona: «mi coche es rojo y viejo» declara el coche, no la coletilla. Se corta en el primer
    # conector o signo.
    bruto = re.split(r"\s+(?:y|pero|aunque|porque)\s+|[,;.]", hallado.group(2))[0]
    valor = bruto.strip(" .,;:!?")
    return (hallado.group(1).strip(), valor) if valor else None


def identidad_de(contenido: str) -> str | None:
    """La IDENTIDAD del hecho que declara una frase, o None si la frase no declara un atributo.

    Es el atributo normalizado, y nada mas: «Mi cumpleaños es el 10 de mayo» y «Mi cumpleaños es el 3
    de junio» comparten identidad `cumpleanos`, que es lo que permite versionar la segunda sobre la
    primera. **No se persiste** —seria el campo de identidad canonica de `D-AMP-5`, pospuesta—: se
    calcula en el momento de escribir para encontrar la version anterior.
    """
    par = atributo_declarado(contenido)
    return normalizar(par[0]) if par else None
