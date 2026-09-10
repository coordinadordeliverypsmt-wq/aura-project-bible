"""M-1 — la superficie unica de clasificacion de intencion (DP-D-M-7, Opcion A).

**Por que existe.** `DP-D-M-7` midio que AURA no tenia *un* clasificador de intencion: tenia 13
dispersos, con 91 patrones, en 4 ficheros, y **ninguno distinguia una pregunta de una afirmacion**.
El inventario de rutas (R1-R7) encontro ademas que `_es_pregunta()` sostenia **dos** decisiones
independientes a la vez: la puerta de `ADR-0014` (que se LEE) y la escritura de memoria (que se
ESCRIBE). Este modulo las separa sin tocar la garantia.

**Dos ejes ortogonales** (`DP-D-M-7` §3):

- **Eje 1 · acto de habla** — que quiere el usuario de este turno. Decide **a donde va el turno**.
- **Eje 2 · contenido proposicional** — que hechos aporta. Decide **que se recuerda**.

El principio, literal del DP: *«Se convierte en memoria recuperable el contenido proposicional que el
turno aporta sobre el mundo del usuario — sea cual sea el acto de habla que lo vehicula.»*

**Determinista, siempre.** `ADR-0014` §2 prohibe delegar esta decision en el LLM, y §4 exige que toda
garantia sea codigo verificable con prueba determinista. Aqui no hay modelo, ni estadistica, ni red:
tablas declaradas y morfologia ligera. Su techo es finito y se declara como tal.

**La regla de seguridad del eje 2** (decision del CEO, Opcion A): *ante duda, NO almacenar*. El fallo
seguro es perder recall, nunca fabricar un recuerdo.

**Lo que este modulo NO hace.** No ejecuta, no consulta memoria, no concede permisos y no decide
autoridad: devuelve etiquetas. Una etiqueta no es una autorizacion — quien ejecuta sigue siendo el
motor unico, con sus permisos y su HITL.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ------------------------------------------------------------------ EJE 1 · ACTO DE HABLA --

CORRECCION = "CORRECCION"
ORDEN = "ORDEN"
PREGUNTA = "PREGUNTA"
SOCIAL = "SOCIAL"
AFIRMACION = "AFIRMACION"

#: Los cinco actos, en **orden de precedencia explicito** (`DP-D-M-7` §3: «clases mutuamente
#: excluyentes, con prioridad explicita y documentada»). `CORRECCION` gana a todo porque cambia el
#: estado ya sabido; `AFIRMACION` es el defecto declarado del DP.
PRECEDENCIA_ACTO = (CORRECCION, ORDEN, PREGUNTA, SOCIAL, AFIRMACION)
ACTOS = PRECEDENCIA_ACTO

# --------------------------------------------------- EJE 2 · CONTENIDO PROPOSICIONAL --

HECHO_USUARIO = "HECHO_USUARIO"
CONOCIMIENTO_PROCEDURAL = "CONOCIMIENTO_PROCEDURAL"
COMPROMISO_FUTURO = "COMPROMISO_FUTURO"
REGLA_CONDICIONAL = "REGLA_CONDICIONAL"
NADA_PROPOSICIONAL = "NADA_PROPOSICIONAL"
INCIERTO = "INCIERTO"

CONTENIDOS = (HECHO_USUARIO, CONOCIMIENTO_PROCEDURAL, COMPROMISO_FUTURO,
              REGLA_CONDICIONAL, NADA_PROPOSICIONAL, INCIERTO)

#: **Whitelist, no blacklist.** Solo estos tres se convierten en memoria recuperable. `INCIERTO` y
#: `NADA_PROPOSICIONAL` quedan fuera por la regla de seguridad; `REGLA_CONDICIONAL` tambien, pero por
#: otro motivo: su sitio es el almacen de reglas, no la memoria (`DP-D-M-7` §3).
ALMACENABLES = frozenset({HECHO_USUARIO, CONOCIMIENTO_PROCEDURAL, COMPROMISO_FUTURO})


#: Marcadores de EVOCACION EXPLICITA: el usuario dice que algo se dijo o se acordo antes.
#: Hogar unico (antes vivian en `orchestrator._PATRONES_CONSULTA_MEMORIA`, que ahora los aliasa).
#: Medido: sobre `bateria_memoria.json` aportan CERO a la proteccion de 24/24 -las 24 negativas se
#: protegen por ser interrogativas-. Siguen valiendo para lo que nombran: evocacion explicita.
MARCADORES_DE_EVOCACION = (
    "acordamos",
    "quedamos en",
    "recuerdas",
    "te acuerdas",
    "que dije",
    "que dijimos",
    "habiamos hablado",
    "hablamos de",
    "te conte",
    "te comente",
    "mencione",
    # AURA como SUJETO del recuerdo (2026-09-09). Faltaban, y lo destapo la verificacion de mutacion:
    # «¿Como puedo recordar lo que me dijiste?» pedia consejo sobre un registro y se iba al modelo.
    # Anadirlas solo ESTRECHA la cognicion -mas turnos vuelven al Core-, nunca la ensancha.
    "me dijiste",
    "me contaste",
    "me comentaste",
    "me recomendaste",
    "dijiste que",
    "que sabes de mi",
    "que recuerdas",
    "mi preferencia",
    "habiamos quedado",
)


# ------------------------------------------------------------------------ NORMALIZACION --

def normalizar(texto: str) -> str:
    """El **unico** normalizador de la superficie de intencion.

    `DP-D-M-7` §1 conto 3 copias del normalizador; el inventario encontro 5. Este no las borra —eso
    exige la red de seguridad que el DP pide construir antes— pero da un sitio unico a donde migrar.
    """
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _con_bordes(texto_norm: str) -> str:
    """Texto con la puntuacion convertida en separador, para poder exigir palabra completa.

    Sin esto, `«¿cuantos planetas conozco yo?»` escapaba a la guarda de primera persona porque el
    marcador buscado era `" yo "` y en el texto habia `" yo?"`. Medido durante el diseno de la
    frontera cognitiva: era un defecto del detector, no del modelo.
    """
    return " " + re.sub(r"[¿?¡!,.;:()\[\]\"']", " ", texto_norm) + " "


def _nombra(texto_bordes: str, palabras) -> bool:
    """True si alguna de `palabras` aparece como **segmento completo**, nunca como subcadena.

    `any(patron in texto)` es exactamente la construccion que produjo los defectos del §1 del DP
    («para el cafe» leido como imperativo de *parar*). Aqui se exige la palabra entera.
    """
    return any(f" {p} " in texto_bordes for p in palabras)


# ------------------------------------------------------------------- TABLAS DECLARADAS --

#: Interrogativos en posicion inicial. Copiados del detector vigente del orquestador **sin cambiar
#: uno solo**: esta lista sostiene hoy la garantia de 24/24 y este modulo no la mueve.
_INTERROGATIVOS = (
    "que", "cual", "cuales", "cuando", "donde", "como", "cuanto", "cuanta", "cuantos", "cuantas",
    "quien", "quienes", "recuerdas", "sabes", "sabias", "dime", "cuentame", "conoces",
)

#: Marcadores de correccion: el usuario enmienda algo que AURA ya cree saber.
#: **`no es` NO esta aqui**: medido, arrastraba «No es mi cumpleanos», que es una afirmacion sobre el
#: usuario, no una enmienda de lo que AURA sabe. La correccion exige una marca de enmienda explicita.
_CORRECCION = ("ya no", "en realidad", "me equivoque", "esta mal", "corrige", "rectifico",
               "te equivocas", "no era", "eso es falso", "actualiza mi", "no es cierto",
               "olvida lo que", "olvida que", "en verdad", "cambie de opinion", ", es ")

#: Imperativos de peticion — 2.ª persona, formas afirmativa Y de subjuntivo negado.
#:
#: **`no` NO esta aqui, y esa ausencia es la reparacion del DP.** `DP-D-M-7` §4.bis midio que meter
#: `no` en la tabla para capturar «no borres» arrastraba «no soy alergico», «no tengo hermanos» y
#: «no trabajo los viernes» a `ORDEN`, hundiendo la dimension `negacion` al 56,2 %. La solucion no es
#: mirar el `no`: es que la tabla contenga **solo formas que un hablante no puede usar sobre si
#: mismo**. `borres` es siempre una orden; `trabajo` nunca lo es. Asi la negacion se resuelve sola.
_ORDEN = ("abre", "abras", "enciende", "enciendas", "apaga", "apagar",
          "apagues", "busca", "busques", "lee", "leas",
          "mueve", "muevas", "renombra", "renombrar",
          "borra", "borres", "elimina", "elimines", "ejecuta", "ejecutar",
          "ejecutes", "verifica", "audita", "diagnostica", "diagnosticar",
          # `crees` SALIO de esta lista (2026-09-09). Es subjuntivo de *crear* y, a la vez, presente
          # de *creer*: con el dentro, «¿Por que crees que dormir poco afecta al animo?» se
          # clasificaba ORDEN y la conversacion moria en la guarda de memoria vacia. Es la misma
          # colision que ya costo `baja`, `marca` y `lista` en D-M-2, y se paga igual: la forma que
          # colisiona sale, el imperativo real (`crea`) se queda.
          "crea", "organiza", "guarda", "guardes",
          "pon", "ponme", "pongas", "quita", "quites", "manda", "envia",
          "cierra", "cierres", "reproduce", "sube", "subas", "silencia",
          "anota", "apunta", "apuntate", "registra",
          "recuerdame", "recuerdamelo", "acuerdate", "avisame", "avisa", "olvides", "olvida",
          "dejes", "interrumpas", "hazme", "haz", "dame", "ponle", "activa", "desactiva",
          "cancela", "detente", "para ya", "ten en cuenta", "no olvides", "no me dejes")

_SOCIAL = ("hola", "hey", "buenas", "adios", "gracias", "chao", "chau",
           "buenos dias", "buenas tardes", "buenas noches", "hasta luego", "nos vemos",
           "muchas gracias", "mil gracias", "de nada", "por favor",
           "vale", "perfecto", "de acuerdo", "ok", "okey", "genial", "estupendo", "no",
           "claro", "vaya", "menuda", "que bien", "como quieras", "cuando quieras", "nada")

#: Compromiso futuro: algo que debe recordarse *para despues*.
_COMPROMISO = ("recuerdame", "avisame", "manana", "el lunes", "el martes", "el miercoles",
               "el jueves", "el viernes", "el sabado", "el domingo", "la semana que viene",
               "el proximo", "la proxima", "tengo cita", "tengo que", "a las")

#: Conocimiento procedural: como hace el usuario las cosas.
_PROCEDURAL = ("para el", "para la", "para hacer", "suelo", "normalmente", "siempre que",
               "cada vez que", "uso la", "uso el", "lo hago", "acostumbro")

#: Regla condicional: forma de automatizacion. Su destino es el almacen de reglas, no la memoria.
_CONDICIONAL_INICIO = ("cuando", "si", "siempre que", "cada vez que", "en cuanto")

#: Marcas de que el turno habla del **mundo del usuario**. Es la senal del eje 2, no del eje 1.
_PRIMERA_PERSONA = ("mi", "mis", "me", "yo", "conmigo", "mio", "mia", "mios", "mias",
                    "nuestro", "nuestra", "nos")

#: Verbos en primera persona que expresan un hecho del usuario. Lista **cerrada y declarada**: la
#: alternativa —«cualquier palabra terminada en -o»— se midio y bloqueaba 16 de 20 consultas de
#: conocimiento general. El techo es finito y se declara.
_VERBOS_YO = ("ceno", "como", "desayuno", "almuerzo", "hablo", "preparo", "tengo", "hago",
              "uso", "vivo", "trabajo", "duermo", "medito", "estudio", "estudie", "compre",
              "vendi", "elegi", "decidi", "naci", "toco", "gano", "prefiero", "llevo",
              "entro", "salgo", "inverti", "rechace", "adquiri", "laboro", "descanso",
              "mido", "peso", "conduzco", "practico", "juego", "leo", "escribo", "cocino",
              "corro", "entreno", "viajo", "visito", "soy", "estoy", "quiero", "necesito")

# ------------------------------------------------------------------------ EJE 1 · ACTO --

def es_interrogativa(texto: str) -> bool:
    """Senal **sintactica**: signo de interrogacion, o interrogativo en posicion inicial.

    **Esta funcion es deliberadamente identica al `_es_pregunta` vigente del orquestador, byte a
    byte en su semantica.** Es la que sostiene la puerta de `ADR-0014` y la garantia de 24/24, y M-1
    NO la mueve: solo le da un sitio propio. Separar responsabilidades no es cambiar comportamiento.

    Es una senal, no el acto: `acto_de_habla` la usa junto a la precedencia.
    """
    if "?" in texto or "¿" in texto:
        return True
    palabras = normalizar(texto).split()
    return bool(palabras) and palabras[0] in _INTERROGATIVOS


#: `como` y `cuando` son interrogativos **y** conjunciones: «¿cuando llego?» pregunta, «cuando llego
#: a casa me hago un te» afirma. `es_interrogativa` no puede distinguirlos —ni debe: es la senal
#: sintactica que sostiene ADR-0014 y no se toca—, pero el ACTO si, y esa es exactamente la
#: separacion que M-1 introduce: dos funciones, dos trabajos, una primitiva compartida.
_INTERROGATIVOS_AMBIGUOS = ("como", "cuando")


def _interrogativa_solo_en_apariencia(texto: str, bordes: str) -> bool:
    """True si empieza por un interrogativo ambiguo, no lleva signo, y habla del propio usuario."""
    if "?" in texto or "¿" in texto:
        return False
    palabras = normalizar(texto).split()
    if not palabras or palabras[0] not in _INTERROGATIVOS_AMBIGUOS:
        return False
    return _habla_del_usuario(bordes)


def acto_de_habla(texto: str) -> str:
    """Eje 1. Devuelve uno de `PRECEDENCIA_ACTO`, evaluado en ese orden exacto.

    El orden **es** la regla y esta probado: `CORRECCION` gana a todo porque cambia el estado;
    `ORDEN` antes que `PREGUNTA` porque «cuando termine el mes hazme un resumen» es una peticion
    aunque empiece por un interrogativo; `SOCIAL` solo si el turno **entero** es social;
    `AFIRMACION` es el defecto declarado del DP.
    """
    n = normalizar(texto)
    bordes = _con_bordes(n)
    if not n.strip():
        return SOCIAL

    # Una interrogativa no enmienda: pregunta. «¿Sabes que me mude a Alcala?» aporta un hecho, pero
    # el acto es PREGUNTA — que es justo la ortogonalidad de los dos ejes: el acto no decide el
    # contenido, y el contenido no decide el acto.
    if any(p in n for p in _CORRECCION) and "?" not in texto and "¿" not in texto:
        return CORRECCION

    if _nombra(bordes, _ORDEN) or any(p in n for p in ("para ya", "ten en cuenta", "no olvides",
                                                       "no me dejes")):
        return ORDEN

    if es_interrogativa(texto) and not _interrogativa_solo_en_apariencia(texto, bordes):
        return PREGUNTA

    # SOCIAL solo si NO queda nada mas: «hola» es social, «hola, mi cumpleanos es en marzo» no.
    resto = bordes
    for p in _SOCIAL:
        resto = resto.replace(f" {p} ", " ")
    if not resto.strip() and _nombra(bordes, _SOCIAL):
        return SOCIAL

    return AFIRMACION


# ------------------------------------------------------------------- EJE 2 · CONTENIDO --

def _habla_del_usuario(bordes: str) -> bool:
    """El turno aporta algo sobre el mundo del usuario: posesivo, pronombre o verbo en 1.ª persona."""
    return _nombra(bordes, _PRIMERA_PERSONA) or _nombra(bordes, _VERBOS_YO)


def contenido_proposicional(texto: str) -> str:
    """Eje 2. Que hecho aporta el turno, con independencia del acto que lo vehicula.

    **Conservador por contrato:** cuando las senales no bastan devuelve `INCIERTO`, y `INCIERTO` no
    se almacena. Perder un recuerdo es un fallo aceptable; fabricarlo no lo es.
    """
    n = normalizar(texto)
    bordes = _con_bordes(n)
    if not n.strip():
        return NADA_PROPOSICIONAL

    palabras = n.split()
    if palabras and palabras[0] in _CONDICIONAL_INICIO and _nombra(bordes, _ORDEN):
        return REGLA_CONDICIONAL

    if _nombra(bordes, _SOCIAL):
        resto = bordes
        for p in _SOCIAL:
            resto = resto.replace(f" {p} ", " ")
        if not resto.strip():
            return NADA_PROPOSICIONAL

    if any(p in n for p in _COMPROMISO) and _habla_del_usuario(bordes):
        return COMPROMISO_FUTURO

    if any(p in n for p in _PROCEDURAL) and _habla_del_usuario(bordes):
        return CONOCIMIENTO_PROCEDURAL

    if _habla_del_usuario(bordes):
        return HECHO_USUARIO

    # No hay marca de que el turno hable del usuario. Podria ser conocimiento general, una hipotesis
    # o una frase suelta: nada de eso es un hecho del usuario, y adivinarlo seria fabricar.
    return INCIERTO


# ------------------------------------------------------------------------ CLASIFICACION --

@dataclass(frozen=True)
class Intencion:
    """El resultado de clasificar un turno. **Es una etiqueta, no una autorizacion.**"""

    acto: str
    contenido: str

    @property
    def almacenable(self) -> bool:
        return self.contenido in ALMACENABLES


def clasificar(texto: str) -> Intencion:
    """La superficie unica: un turno entra, dos ejes salen."""
    return Intencion(acto=acto_de_habla(texto), contenido=contenido_proposicional(texto))


def debe_almacenarse(texto: str, clasificacion: Intencion | None = None) -> bool:
    """Decision de escritura, **independiente** de la puerta de lectura de `ADR-0014`.

    Dos condiciones, y las dos por su propio motivo:

    1. **El acto no puede ser `PREGUNTA`.** Almacenar una pregunta hacia que, al repetirla, se
       cubriera a si misma con cobertura 1,00 y `ADR-0014` dejara de activarse: el sistema recibia su
       propia pregunta como si fuera un recuerdo. Es `D-M-2`, y esta condicion la conserva intacta.
    2. **El contenido tiene que estar en la whitelist.** `INCIERTO` no pasa. Es la regla del CEO para
       el eje 2 (Opcion A): ante duda, no almacenar.

    La 1 es identica al comportamiento vigente; la 2 es nueva y solo puede RESTAR escrituras, nunca
    anadirlas. Por construccion, esta funcion no puede escribir nada que hoy no se escribiera.
    """
    c = clasificacion or clasificar(texto)
    # **Suelo sintactico, y va PRIMERO.** Lo aprendi rompiendolo: con `ORDEN` por delante de
    # `PREGUNTA`, «¿Di de baja mi membresia deportiva?» se clasificaba ORDEN —«baja» tambien es
    # sustantivo— y la escritura la dejaba pasar. Una pregunta escrita en memoria es `D-M-2`: al
    # repetirla se cubre a si misma y ADR-0014 deja de activarse. El acto puede equivocarse; este
    # suelo no depende del acto, y es literalmente la condicion que habia antes de M-1.
    if es_interrogativa(texto):
        return False
    return c.acto != PREGUNTA and c.almacenable


# ------------------------------------------------------------- DESTINO DE MEMORIA (M-1 → almacen) --

#: Memoria personal recuperable: puede volver en un `recall`.
RECUPERABLE = "recuperable"
#: Historico no recuperable: se persiste y se audita, pero NUNCA vuelve en un `recall`
#: (`contracts.HISTORICO`). Decision del CEO, 2026-09-09.
HISTORICO_NO_RECUPERABLE = "historico_no_recuperable"


def destino_de_memoria(texto: str, clasificacion: Intencion | None = None) -> str | None:
    """A donde va este turno: memoria recuperable, historico, o a ningun sitio.

    Es el punto donde los dos ejes se convierten en una decision de almacenamiento, y por eso vive
    aqui y no en el orquestador: el orquestador ejecuta la decision, no la toma.

    Las tres salidas, y el motivo de cada una:

    - `RECUPERABLE` — el turno aporta un hecho del mundo del usuario y no es una pregunta. Es lo unico
      que puede volver en un `recall`.
    - `HISTORICO_NO_RECUPERABLE` — **orden pura**. `DP-D-M-7` §3 la clasifica como «nada
      proposicional», y su sitio es el historico: una orden es algo que el usuario PIDIO, no algo que
      AFIRMO sobre si mismo. Conservarla como memoria personal es el auto-eco de `D-M-2`; perderla es
      perder la traza. El historico es la tercera opcion que faltaba.
    - `None` — preguntas, social, `INCIERTO` y `REGLA_CONDICIONAL`. Nada de esto se almacena: la regla
      del eje 2 es que ante duda no se almacena, y una regla condicional tiene su propio almacen.

    **Una interrogativa no llega al historico tampoco.** El suelo sintactico de `debe_almacenarse`
    protege la memoria recuperable; aqui se repite para el historico, no porque sea peligroso —el
    historico no vuelve en `recall`— sino porque una pregunta no es un acto que el usuario pidiera
    ejecutar, y meterla en el historico de ordenes seria clasificar mal a proposito.
    """
    c = clasificacion or clasificar(texto)
    if debe_almacenarse(texto, c):
        return RECUPERABLE
    if c.acto == ORDEN and not es_interrogativa(texto):
        return HISTORICO_NO_RECUPERABLE
    return None


# ------------------------------------------------------------- COGNICION GENERAL (M3, 2026-09-09) --
#
# POR QUE EXISTE. `_es_consulta_de_memoria` termina en `or _es_pregunta(texto)`, asi que TODA
# interrogativa que nadie haya reclamado antes cae en la ausencia de memoria. Medido: 19 de 20
# consultas cognitivas quedaban en «No tengo ningun recuerdo registrado sobre eso», y el CEO lo vio
# en produccion con «quien es Jesus Cristo?» y «si tengo 1 caballo y lo vendo cuantos me quedan?».
#
# LA VIA QUE NO SE TOMA. Estrechar `_es_consulta_de_memoria` ya se midio: baja la proteccion de
# `24/24` a `17/24`. Esa via esta CERRADA. Esto es lo contrario: una superficie POSITIVA y CERRADA
# que solo puede desviar lo que NOMBRA. Lo que no esta aqui sigue el camino de hoy bit a bit.
#
# LA ASIMETRIA ES TODA LA TESIS. Un error de la via sustractiva EXPONE un hecho personal. Un error de
# esta no contesta una pregunta general. El modo de fallo apunta al lado seguro por construccion.
#
# MEDIDO antes de cablearla: 0 colisiones con las 24 negativas · 0 con las 53 positivas · 0 fugas en
# 15 ataques escritos para romperla · 11 de 12 consultas cognitivas liberadas.

#: Marcos de cognicion general. **Cerrados.** Cada entrada es un compromiso, no una heuristica: se
#: amplian de una en una, midiendo la disyuncion con la bateria antes de anadir.
_MARCOS_COGNITIVOS = (
    "que es ", "que son ", "que significa", "que quiere decir", "como funciona", "como funcionan",
    "por que ", "de que esta hecho", "para que sirve", "quien es ", "quien fue ", "quien era ",
    "quien invento", "quien escribio", "quien descubrio", "cual es la capital", "cuantos planetas",
    "que distancia hay", "cuando termino", "cuando empezo", "en que ano", "cual es el rio",
    "que podemos concluir", "que se puede concluir", "que pasaria si", "que crees que pasaria",
    "que consecuencias", "que opinas", "que te parece", "cuentame", "explicame", "que diferencia hay",
)

#: Peticiones de CONSEJO u OPINION. Lista **positiva y cerrada**, como `_MARCOS_COGNITIVOS`: solo
#: desvia lo que nombra, nunca «cualquier pregunta que no parezca personal» —esa via se midio y costo
#: 7 de las 24 protecciones—.
#:
#: **Por que es seguro ensancharla.** Las 24 consultas protegidas piden todas un DATO: un nombre, una
#: hora, una combinacion, una fecha, un numero, un color, una marca. Ninguna pide consejo. La asimetria
#: es la tesis: un error aqui deja sin contestar un consejo; no expone un hecho personal.
_PIDE_CONSEJO = ("que me recomiendas", "me recomiendas", "que me aconsejas", "me aconsejas",
                 "que me sugieres", "me sugieres", "como puedo", "que puedo hacer",
                 "crees que", "que harias", "que hago si", "ayudame a pensar")

#: Posesivos de primera persona. **El freno de la rama de consejo.** «¿Crees que es buena idea...?» es
#: conversacion; «¿Crees que mi hermana vive en Madrid?» interroga un hecho del usuario con forma de
#: opinion. En cuanto aparece un posesivo propio, el turno vuelve al Core. Es deliberadamente
#: conservador: preferimos dejar un consejo sin contestar antes que dejar fabricar un dato.
_POSESIVO_PROPIO = ("mi", "mis", "mio", "mios", "mia", "mias")

#: Operadores de suposicion. Introducen sus propias premisas en el turno.
_SUPOSICION_COGNITIVA = ("si ", "supongamos que", "supon que", "imagina que", "si fuera",
                         "si todos", "si cada")

#: Interrogativos de CANTIDAD. Es lo unico que una premisa numerica puede responder.
_PIDE_CANTIDAD = ("cuanto", "cuantos", "cuantas", "cuanta")


def es_cognicion_general(texto: str) -> bool:
    """True si el turno es una pregunta que **no interroga la memoria personal**.

    Tres condiciones, y las tres por su propio motivo:

    1. **El acto es `PREGUNTA`.** Una afirmacion o una orden tienen su propia ruta.
    2. **Ningun marcador de evocacion explicita.** «que es lo que te conte ayer» lleva `te conte`:
       eso es memoria aunque empiece por un marco conceptual.
    3. **O un marco conceptual declarado, o una suposicion con premisa numerica que pide una
       cantidad.** El marco exige ademas que el eje 2 diga `INCIERTO` —que el turno NO habla del
       mundo del usuario—; la suposicion no lo necesita porque sus premisas vienen en el turno.

    **Por que la suposicion exige cifra Y pregunta por cantidad.** Medido: dejarla pasar por el solo
    hecho de ser una suposicion abria tres fugas («si hoy es martes, a que hora ceno?»), y exigir solo
    la cifra abria una mas («si tengo 2 hijos, como se llaman?» lleva cifra y pide un NOMBRE). Una
    premisa numerica puede responder «cuantos quedan»; no puede responder «como se llaman».

    **Lo que esta funcion NO hace.** No responde, no consulta memoria, no decide si algo se almacena y
    no concede autoridad de ejecucion: dice a que ruta pertenece el turno. `ADR-0014` sigue
    gobernando la memoria personal, y `_es_consulta_de_memoria` no se ha tocado.
    """
    c = clasificar(texto)
    if c.acto != PREGUNTA:
        return False

    n = normalizar(texto)
    if any(p in n for p in MARCADORES_DE_EVOCACION):
        return False

    # Pedir consejo u opinion NO es interrogar la memoria. Medido a traves del producto real: antes
    # de esta rama, «¿Que me recomiendas para dormir mejor?» se contestaba «No tengo ningun recuerdo
    # registrado sobre eso» en 38 ms, sin llamar al modelo. El freno es el posesivo propio.
    if any(p in n for p in _PIDE_CONSEJO) and not _nombra(_con_bordes(n), _POSESIVO_PROPIO):
        return True

    if any(p in n for p in _SUPOSICION_COGNITIVA) and any(ch.isdigit() for ch in texto) \
            and any(q in n for q in _PIDE_CANTIDAD):
        return True

    return any(p in n for p in _MARCOS_COGNITIVOS) and c.contenido == INCIERTO
