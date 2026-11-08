"""Regla léxica de SUJETO: ¿una frase versa sobre un tercero, o sobre el propio usuario?

**Una sola definición, en el Core.** Antes vivía en `conectores/conversacion.py` y solo gobernaba la
CAPTURA (qué se escribe como hecho). El Memory Context Builder (`core/contexto_memoria.py`, D-AMP-2)
la necesita también en la SALIDA —qué eco se muestra al modelo—, y `core` no puede importar de
`conectores` (regla de dirección de dependencias, `orchestrator.py`). Por eso la regla se trasladó
aquí y `conectores/conversacion.py` la reimporta: lo que la captura no guarda como hecho es
exactamente lo que el Builder no deja pasar al modelo, con **una sola** fuente de verdad léxica
(evita el patrón «regla escrita en N sitios» que `CHECKPOINT-CONTINUIDAD.md` §0 marca como defecto).
"""

from __future__ import annotations

import re
import unicodedata

# Indicios de que la frase versa sobre otra persona. Se comprueba ANTES que las preferencias:
# "a Ana le gusta el cafe" contiene "me gusta"... no, contiene "le gusta"; pero "a mi hermana y a mi
# nos gusta" mezcla sujetos. Ante la mezcla, no se captura.
TERCERO = (
    r"\ba (?!mi\b)\w+ le (gusta|encanta|molesta)",
    r"\b(el|ella|ellos|ellas) (prefiere|prefieren|suele|suelen)\b",
    # RELACIONES AMPLIADAS (CEO, 2026-09-10), condicion de la apertura posesiva de `_HECHO`. Medido
    # antes de ampliarla: «mi abuela es enfermera», «mi primo es piloto» y «mi tio es abogado» daban
    # `tercero=False`; hasta ahora no se guardaban solo porque `_HECHO` era una lista cerrada que no
    # los nombraba. Al abrir la construccion posesiva, esa proteccion accidental desaparece y habria
    # convertido a AURA en un registro sobre la familia del usuario (restriccion 3 / ALERTA-002).
    #
    # `prim[oa]s?\b` y `ti[oa]s?\b` llevan borde a proposito: `prim\w*` casaria «mi primera vez» y
    # `ti[oa]\w*` casaria «mi tiovivo», y cada falso positivo aqui es un hecho del usuario que se
    # pierde. La lista se amplia con lo que el comportamiento demostro necesario, nada mas.
    r"\bmi (abuel\w*|prim[oa]s?|ti[oa]s?|amig\w*|herman\w*|jef\w*|vecin\w*|madre|padre|hij\w*|espos\w*|pareja)\b",
    r"\ba \w+ le\b",
)


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def habla_de_tercero(texto_norm: str) -> bool:
    return any(re.search(p, texto_norm) for p in TERCERO)
