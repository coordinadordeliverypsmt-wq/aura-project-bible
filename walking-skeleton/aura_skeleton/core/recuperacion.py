"""Reconocer que el usuario pregunta por una EJECUCIÓN ANTERIOR de esta misma conversación.

EL HUECO, MEDIDO ANTES DE CERRARLO `[EJEC]`:

    tu>   lista el directorio ~/.aura
    AURA> Ejecuté «listar_directorio». 7 entrada(s): CENTRO-DE-GOBIERNO.md, audit.jsonl, …
    tu>   ¿cuántas entradas encontraste?
    AURA> No tengo ningun recuerdo registrado sobre eso.

**El dato estaba.** La ventana de trabajo que `DR-4` gobierna (CEO, 2026-09-15) lo retenía entero.
Lo que fallaba era el camino: `_es_consulta_de_memoria` da verdadero para CUALQUIER interrogativa,
`recall` busca en la memoria PERSONAL —donde un resultado de ejecución nunca estuvo, y no debe
estar— no encuentra nada, y dispara la puerta de ausencia de `ADR-0014`. El problema no era de
almacenamiento sino de **recuperación**, y la respuesta era falsa por omisión: AURA decía no tener
ningún recuerdo mientras sostenía la respuesta en la mano.

POR QUÉ NO SE TOCA LA PUERTA. Porque la puerta hace bien su trabajo. Sostiene el `24/24` de las
preguntas por atributos personales nunca declarados, está declarada intocable en
`DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` §10, y ensancharla ya rompió tres pruebas de `DR-2 = A`. La
cascada del orquestador tiene un patrón para esto, usado al menos tres veces —la aritmética, `D-FC-3`
«AURA sobre sí misma» y las órdenes de capacidad—: **una superficie positiva y cerrada, evaluada
después de todas las que ya existían y antes de la pared.** Cuando no reconoce, devuelve `None` y el
turno sigue exactamente el camino que ya tenía.

POR QUÉ ES SEGURO SEPARARLAS. No es una heurística afortunada: son **dos gramáticas distintas**. Las
24 frases que sostienen la pared hablan del MUNDO DEL USUARIO —«¿cuál es el nombre de mi abuela?»,
«¿de qué color son mis ojos?»: posesivos y atributos propios—. Estas hablan de algo que hizo AURA, en
segunda persona del pasado: «¿qué encontraste?», «¿qué ejecutaste?». Ninguna de las 24 tiene esa
forma, y una prueba parametrizada lo comprueba una por una.

LO QUE ESTE MÓDULO NO HACE, Y ES DELIBERADO:

- **No vuelve a ejecutar nada.** Lee lo que AURA ya dijo. No hay segunda ruta de ejecución, no se
  esquiva el Motor Único, ni los permisos, ni el kill switch (`ALERTA-005`).
- **No crea una segunda memoria.** Usa la ventana que ya existe. La única metadata que se añade a
  cada turno retenido es de QUÉ superficie salió, para poder encontrar el último turno de ejecución
  sin adivinarlo releyendo el texto.
- **No decide el desenlace por su cuenta.** El texto retenido YA distingue ejecutada, detenida, con
  error y `duplicate`, porque `_redactar_resultado_de_orden` se corrigió para eso en M7. Repetir ese
  texto conserva la distinción sin duplicar la lógica en un segundo sitio, que es como dos
  implementaciones del mismo control acaban divergiendo.
- **No decide nada sobre privacidad ni retención.** Esa decisión la tomó el CEO Operativo (2026-11-06, punto D,
  `DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md` §7): el contenido de ficheros no reentra en el prompt y no se
  persiste (lo marca `operaciones.CAPACIDADES_QUE_DEVUELVEN_CONTENIDO`), y lo que sobrevive al reinicio es un
  registro de metadatos (`core/resultado_accion.py`). Este módulo solo redacta lo que ese registro conserva.
- **No recupera lo que dijo el MODELO.** Solo turnos que produjo el Core ejecutando una capacidad.
  Repetir una propuesta del modelo como si fuera un hecho del Core la blanquearía, y el estatus
  epistémico existe justamente para impedirlo (`D-FC-8 = B`).
"""

from __future__ import annotations

from typing import NamedTuple

from .estatus import Estatus
from .intencion import normalizar

#: Dominio con el que el orquestador marca un turno resuelto ejecutando una capacidad. Es la única
#: clase de turno que esta superficie puede recuperar.
DOMINIO_EJECUCION = "orden_de_capacidad"

#: Las dos cosas distintas que el usuario puede estar preguntando sobre lo anterior.
PREGUNTA_POR_EL_RESULTADO = "resultado"
PREGUNTA_POR_UN_JUICIO = "juicio"
#: Tercera cosa que se puede preguntar (punto D): lo que AURA hizo ANTES DE REINICIARSE. Solo puede contestarlo el
#: registro persistido (`resultado_accion`), nunca la ventana, que muere con el proceso.
PREGUNTA_ANTES_DEL_REINICIO = "antes_del_reinicio"

_VOCATIVOS = ("aurora", "aura")
_PUNTUACION = "¿?¡!.…"


class Turno(NamedTuple):
    """Un turno retenido en la ventana de trabajo. **No es un almacén nuevo**: es la forma que ya
    tenía la tupla `(usuario, aura, estatus)` con el dominio añadido, para saber de qué superficie
    salió sin tener que deducirlo releyendo el texto —que es adivinar sobre la propia salida—."""

    usuario: str
    aura: str
    estatus: Estatus
    dominio: str = ""
    #: Si no esta vacio, es LO UNICO que de este turno reentra en el prompt de turnos posteriores (punto D). Lo fija
    #: el orquestador cuando la respuesta lleva contenido del usuario (`devuelve_contenido_usuario`) o sale del
    #: registro persistido. La recuperacion a peticion en la misma conversacion sigue usando `aura` entero.
    resumen_prompt: str = ""


#: Formas en las que el usuario pide EL DATO de una ejecución anterior. Coincidencia por SEGMENTO
#: COMPLETO: «¿qué encontraste? y borra el informe» no es esto, y «no me digas qué encontraste»
#: tampoco. Ante la duda no se reconoce (`ADR-0003`), y el turno sigue su camino de siempre.
_FORMAS_RESULTADO = frozenset(
    {
        "que encontraste",
        "que encontrastes",
        "que has encontrado",
        "que encontraste antes",
        "que habias encontrado",
        "que habias encontrado antes",
        "que encontraste al final",
        "cuantas entradas encontraste",
        "cuantas entradas habia",
        "cuantas encontraste",
        "cuantas habia",
        "cuantos encontraste",
        "que ejecutaste",
        "que revisaste",
        "que leiste",
        "que listaste",
        "que hiciste",
        "que decia ese archivo",
        "que decia el archivo",
        "que decia ese fichero",
        "que ponia ese archivo",
        "que ponia el archivo",
        "y que ponia",
        "que habia en el directorio",
        "que habia ahi",
        "que habia alli",
        "que resultado obtuviste",
        "que te salio",
        "que salio",
        "repite lo que encontraste",
        "dime otra vez que encontraste",
        "que me dijiste",
    }
)

#: Preguntas por si AURA actuó sobre la TV («¿apagaste la tele?»). Medido `[EJEC]` (2026-10-21): por voz, la
#: superficie de orden no entendida se las tragaba y AURA respondía que no había entendido la orden, justo
#: después de apagarla. Se contestan igual que «¿qué hiciste?»: repitiendo lo que ocurrió, sin releer la TV ni
#: volver a ejecutar. Producto CERRADO de verbos y nombres de la TV; nada de «la tele está…» ni frases abiertas.
_FORMAS_RESULTADO_TV = frozenset(
    f"{ya}{verbo} {tv}"
    for ya in ("", "ya ")
    for verbo in ("apagaste", "encendiste", "prendiste", "has apagado", "has encendido", "has prendido")
    for tv in ("la tele", "la television", "el televisor", "la tv")
)

#: Preguntas por lo que AURA hizo antes de reiniciarse. Conjunto CERRADO, turno completo (ver `_FORMAS_RESULTADO`).
_FORMAS_ANTES_DEL_REINICIO = frozenset(
    f"{pregunta} antes {de}"
    for pregunta in ("que hiciste", "que has hecho", "que habias hecho", "que ejecutaste", "que habias ejecutado")
    for de in ("de reiniciarte", "del reinicio", "de reiniciar", "de que te reiniciaras")
)

#: Formas que piden una VALORACIÓN de lo anterior, no el dato. Se separan porque se contestan
#: distinto: el Core puede repetir lo que encontró, pero decidir qué fue «lo más importante» sería
#: una inferencia presentada como hecho — lo que `ADR-0014 §4` prohíbe.
_FORMAS_JUICIO = frozenset(
    {
        "que fue lo mas importante",
        "cual fue lo mas importante",
        "que es lo mas importante",
        "que fue lo mas grave",
        "cual fue lo mas grave",
        "que fue lo peor",
    }
)


def _limpiar(texto: str) -> str:
    """Normaliza para COMPARAR, nunca para mostrar: minúsculas, sin tildes, sin signos y sin el
    vocativo. Reutiliza `intencion.normalizar`, que es el normalizador único declarado — añadir aquí
    una sexta copia del mismo bucle es justo lo que `DP-D-M-7` §1 pidió dejar de hacer."""
    limpio = normalizar(texto)
    for signo in _PUNTUACION:
        limpio = limpio.replace(signo, " ")
    palabras = limpio.split()
    # El vocativo puede venir delante o detrás: «Aurora, ¿qué encontraste?» y «¿qué encontraste,
    # Aurora?» son la misma pregunta y no deben duplicar cada forma de la tabla.
    while palabras and palabras[0].rstrip(",") in _VOCATIVOS:
        palabras.pop(0)
    while palabras and palabras[-1].rstrip(",") in _VOCATIVOS:
        palabras.pop()
    return " ".join(palabras).strip(" ,")


def reconocer(texto: str) -> str | None:
    """`PREGUNTA_POR_EL_RESULTADO`, `PREGUNTA_POR_UN_JUICIO` o `None` si no es ninguna de las dos."""
    limpio = _limpiar(texto)
    if limpio in _FORMAS_RESULTADO or limpio in _FORMAS_RESULTADO_TV:
        return PREGUNTA_POR_EL_RESULTADO
    if limpio in _FORMAS_JUICIO:
        return PREGUNTA_POR_UN_JUICIO
    if limpio in _FORMAS_ANTES_DEL_REINICIO:
        return PREGUNTA_ANTES_DEL_REINICIO
    return None


def ultima_ejecucion(ventana) -> Turno | None:
    """El turno de ejecución más reciente de la ventana, o `None` si no hay ninguno.

    **El más reciente y no «el que el usuario quiso decir»**: elegir entre varios exigiría inferir a
    cuál se refiere, y esta superficie no infiere. Si hiciera falta desambiguar, lo correcto es
    preguntar (`ACLARACION`), no acertar."""
    for turno in reversed(list(ventana)):
        if isinstance(turno, Turno) and turno.dominio == DOMINIO_EJECUCION:
            return turno
    return None


#: Lo que AURA antepone al texto recuperado. Dice DE DÓNDE sale y, sobre todo, que **no ha vuelto a
#: ejecutar nada**: sin eso, el usuario podría creer que acaba de mirar otra vez, y actuar sobre un
#: dato que puede llevar varios turnos siendo viejo.
_PROCEDENCIA = "Lo recupero de esta misma conversación; no lo he vuelto a ejecutar:"

#: Cuando la pregunta pide una valoración. El Core recupera el dato y **se niega a jerarquizarlo**:
#: decidir qué fue «lo más importante» es una inferencia, y presentarla como hecho es lo que
#: `ADR-0014 §4` prohíbe. Negarse y entregar el dato es más útil que acertar por casualidad.
_SIN_JUICIO = (
    "No puedo decirte qué fue lo más importante: eso sería un juicio mío, no un hecho. "
    "Esto es lo que encontré, tal como te lo dije:"
)

#: Ausencia PRECISA, y por eso distinta de la de `ADR-0014`. «No tengo ningún recuerdo registrado
#: sobre eso» habla de la memoria personal; esto habla de la conversación. Que las siete situaciones
#: dieran la misma frase era el defecto de fondo, no un detalle de redacción.
#:
#: **Sin «nunca» ni «no he ejecutado nada»** (punto D, decision L): la ventana muere con el proceso y el registro
#: persistido puede haber fallado o no cubrir una accion (caida entre el efecto y la escritura, dominios de
#: seguridad, PARADA). Decir que no hizo nada seria afirmar una ausencia que no puedo demostrar (INV-9).
_SIN_EJECUCION = (
    "No conservo registro de acciones anteriores; podría haber alguna que no consta, "
    "así que no tengo ningún resultado que recuperar."
)

#: Lo que AURA antepone cuando lo que cuenta sale del registro persistido. «Consta en mi registro local» dice la
#: procedencia (un fichero del usuario, sin firma) y NO el estatus de hecho verificado del Core.
_PROCEDENCIA_PERSISTIDA = (
    "Consta en mi registro local (no lo he vuelto a ejecutar ni a comprobar; puede estar incompleto):"
)

#: Lo que reentra en el prompt de turnos posteriores tras recuperar del registro: la existencia de la consulta, no
#: su contenido.
RESUMEN_PROMPT_REGISTRO = "(consulté mi registro local de acciones anteriores)"


def redactar(clase: str, turno: Turno | None) -> tuple[str, Estatus]:
    """Qué contesta AURA, y con qué estatus epistémico.

    **El desenlace no se decide aquí.** El texto retenido ya distingue ejecutada («Ejecuté «X»…»),
    detenida («No he ejecutado «X»: …»), con error («Intenté ejecutar «X» y no pude: …») y
    `duplicate` («ya se había ejecutado…, así que no lo repetí»), porque
    `_redactar_resultado_de_orden` se corrigió para eso en M7. Repetirlo conserva la distinción y
    **garantiza que la recuperación no pueda contradecir lo que AURA dijo en su momento**, que es lo
    que pasaría con una segunda implementación de la misma lógica.

    El estatus es `HECHO` en los dos casos con turno: el Core no está infiriendo nada, está
    informando de algo que ocurrió en esta conversación y que él mismo produjo. Y solo puede tratarse
    de algo que él produjo, porque `ultima_ejecucion` descarta todo lo que no salga de
    `DOMINIO_EJECUCION`: una propuesta del modelo nunca puede salir de aquí convertida en hecho.
    """
    if turno is None:
        return _SIN_EJECUCION, Estatus.AUSENCIA
    if clase == PREGUNTA_POR_UN_JUICIO:
        return f"{_SIN_JUICIO}\n\n{turno.aura}", Estatus.HECHO
    return f"{_PROCEDENCIA}\n\n{turno.aura}", Estatus.HECHO


def redactar_persistido(clase: str, lineas: list[str]) -> tuple[str, Estatus]:
    """Qué contesta AURA con lo que `resultado_accion.leer` devolvió, ya redactado línea a línea por el orquestador
    (con la MISMA redacción del turno en vivo). Con `lineas` vacío, la ausencia sin «nunca».

    El estatus es ABSTENCION y no HECHO a propósito: el registro es un fichero local sin firma. AURA entrega lo que
    consta con su procedencia, pero no lo afirma como hecho verificado por el Core (`ETIQUETA_CONTEXTO`)."""
    if not lineas:
        return redactar(clase, None)
    cuerpo = "\n".join(f"• {linea}" for linea in lineas)
    previo = f"{_SIN_JUICIO}\n\n" if clase == PREGUNTA_POR_UN_JUICIO else ""
    return f"{previo}{_PROCEDENCIA_PERSISTIDA}\n{cuerpo}", Estatus.ABSTENCION


def hubo_ejecucion(ventana) -> bool:
    """True si en la ventana de trabajo de ESTA conversación AURA ejecutó algo.

    Semana 2, encontrado `[EJEC]` con la TV real: tras «apaga la tele», «¿qué hiciste?» lo contestaba el
    historial del ciclo autónomo («mi última tarea es P-018»), también con una pregunta en medio. Si AURA
    actuó en esta conversación, la pregunta es por eso; si no, el historial sigue respondiendo como siempre.
    Solo la ventana (DR-4): tras un reinicio la ventana está vacía y responde el historial. Lo que AURA hizo ANTES de
    reiniciarse lo contesta, aparte, el registro persistido (`resultado_accion`, punto D)."""
    return ultima_ejecucion(ventana) is not None
