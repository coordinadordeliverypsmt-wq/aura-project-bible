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

#: La normalizacion del orquestador conserva «¿» —solo quita diacriticos—, asi que el anclaje tiene que
#: admitirlo: sin esto «¿Cual es mi cumpleanos?» no casaba y el turno se iba al modelo.
_ATRIBUTO_PREGUNTADO = re.compile(r"^¿?(?:cual|cuales) (?:es|son) mi ([a-z]+(?: [a-z]+)?)\s*\??$")


def normalizar(texto: str) -> str:
    """Minusculas sin diacriticos. Identica a la del orquestador: comparar «cumpleaños» con
    «cumpleanos» no puede depender de como se escribio el acento."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def atributo_preguntado(t: str) -> str | None:
    """El atributo que una pregunta posesiva nombra, o None si no es una de ellas."""
    hallado = _ATRIBUTO_PREGUNTADO.match(t.strip())
    return hallado.group(1).strip() if hallado else None


def atributo_declarado(contenido: str) -> tuple[str, str] | None:
    """El par (atributo, valor) de una declaracion posesiva, extraido de SU PROPIA frase."""
    hallado = _ATRIBUTO_DECLARADO.search(contenido)
    if not hallado:
        return None
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
