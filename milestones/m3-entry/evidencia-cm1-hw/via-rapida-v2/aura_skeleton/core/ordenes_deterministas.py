"""Órdenes habladas que el Core responde de forma DETERMINISTA y sin valores libres (CM1, v2).

PARA QUÉ. La escucha de órdenes con Vosk (`AURA_ORDEN_VOSK=1`) puede reconocer con una gramática CERRADA.
Medido `[EJEC]` 2026-09-29 por el aire con el modelo `vosk-model-small-es-0.42`: el reconocimiento LIBRE
falla incluso con audio limpio («¿Cómo me llamo?» -> «tuvo media hago»; «Mauricio» -> «amor eso», que AURA
llegó a GUARDAR como nombre del usuario); con gramática cerrada, 3/3 correctas y RTF 0,09-0,12
(FinalResult 21-49 ms). Esta lista es esa gramática.

POR QUÉ NO HAY DECLARACIONES. Con gramática cerrada Vosk FUERZA lo que oye a la frase más cercana (el
mismo efecto que `adapters/escucha.py` documenta con «aurora»). «Me llamo Pedro» se convertiría en
«me llamo mauricio» y se GUARDARÍA: corrupción de memoria. Por eso aquí solo hay PREGUNTAS y consultas de
solo lectura, sin ningún valor libre. Tampoco están las que comparten palabras con una declaración
(«quién soy», «en qué trabajo», «qué me gusta»: «soy X», «trabajo en X», «me gusta X» las atraerían).
Lo que no case con ninguna sale como `[unk]` y se resuelve con el reconocimiento libre.

DE DÓNDE SALE CADA GRUPO (formas normalizadas del código, aquí con su tilde: el vocabulario de Vosk las
tiene acentuadas y sin la tilde la palabra se ignora). Ninguna entrada se afirma por lectura: la prueba
`tests/unit/test_ordenes_deterministas.py` pasa CADA una por el orquestador real y exige que la responda el
Core (`provider == "core"`, dominio distinto de la pared de memoria), así que una entrada que el Core deje
de reconocer rompe esa prueba.

- Identidad y hechos propios: `core/orchestrator.py::_CONSULTAS_DE_HECHO` (nombre, trabajo, proyecto,
  color favorito).
- Qué sabe de mí: `core/orchestrator.py::_PAT_MODELO_VER`. Preferencias: `_PAT_CONSULTA_PREFERENCIA`.
- Evocación genérica: `core/identidad_memoria.py::_EVOCACION_GENERICA` y `_EVOCACION_ATRIBUTO`.
- Última tarea / resultados: `core/orchestrator.py::_PAT_ULTIMA_TAREA` y `core/recuperacion.py`.

UBICACIÓN. En `core/` porque es conocimiento de QUÉ superficies deterministas tiene el Core. No importa
nada: el adaptador de escucha recibe la lista inyectada (`OidoContinuo(gramatica_orden=...)`) y quien
cablea es `__main__`, así que el adaptador no depende del Core.
"""

from __future__ import annotations

ORDENES_DE_VOZ: tuple[str, ...] = (
    # `_CONSULTAS_DE_HECHO`: nombre
    "cómo me llamo",
    "cuál es mi nombre",
    "sabes cómo me llamo",
    "recuerdas mi nombre",
    # `_CONSULTAS_DE_HECHO`: trabajo y proyecto
    "qué trabajo hago",
    "cuál es mi trabajo",
    "a qué me dedico",
    "en qué proyecto trabajo",
    "cuál es mi proyecto",
    "cómo se llama mi proyecto",
    # `_CONSULTAS_DE_HECHO`: color favorito
    "cuál es mi color favorito",
    "cuál es mi color preferido",
    # `_PAT_MODELO_VER` y `_PAT_CONSULTA_PREFERENCIA`
    "qué sabes de mí",
    "qué prefiero",
    "cuáles son mis preferencias",
    # `_EVOCACION_GENERICA` y `_EVOCACION_ATRIBUTO`
    "te acuerdas de lo que te dije",
    "qué te dije",
    "qué te dije antes",
    "te acuerdas de mi color favorito",
    # `_PAT_ULTIMA_TAREA` / `recuperacion`
    "qué hiciste",
    "qué encontraste",
)
