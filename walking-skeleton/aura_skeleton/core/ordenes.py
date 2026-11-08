"""Reconocer que el usuario está PIDIENDO una capacidad, sin preguntárselo al LLM.

EL HUECO QUE CIERRA, MEDIDO ANTES DE ESCRIBIRLO `[EJEC]`. AURA arranca declarando 21 operaciones
—entre ellas `ejecutar_pruebas`, `auditar_garantias`, `diagnosticar_estado`— con sus adaptadores
registrados y funcionando. Pero si el usuario escribía *«ejecuta las pruebas»*, la respuesta era:

    AURA> Esto lo genera mi modelo local y no está verificado: Entendido.

La capacidad existía, el ejecutor existía, el permiso existía, el Motor Único existía. **Lo que no
existía era la ruta desde la conversación hasta ellos.** Capacidad registrada y no descubrible: el
patrón «declarado ≠ real» aplicado a lo que el usuario puede pedir.

POR QUÉ NO LO RESUELVE EL LLM, Y NO ES UNA PREFERENCIA. El orquestador degrada a `consulta`
cualquier acción que proponga el modelo en modo cognitivo, y lo hace a propósito: *«una garantía no
puede depender de que un modelo se comporte»* (ADR-0014 §4). Con un `qwen2.5:0.5b` en un Celeron,
además, fiar el reconocimiento de órdenes al modelo sería fiar la ejecución a lo que más falla. El
Core reconoce; el modelo nunca decide qué se ejecuta.

CÓMO RECONOCE, Y POR QUÉ ASÍ DE ESTRECHO. Por **segmento completo** contra una tabla de variantes,
igual que `_TABLA_INTENCIONES` en el orquestador. Nada de subcadenas: *«no ejecutes las pruebas»* no
puede activar `ejecutar_pruebas` por contener la frase. Ante cualquier duda devuelve `None` y el
turno sigue exactamente el camino que ya tenía — **añadir esta superficie no puede quitarle ninguna
frase a las que ya existían**.

LO QUE ESTE MÓDULO NO HACE, Y ES DELIBERADO:

- **No decide permisos.** Reconoce la intención y devuelve el nombre de la capacidad; quien autoriza
  y ejecuta es el Motor Único, con sus permisos, su kill switch y su auditoría (ALERTA-005: *«la
  puerta va donde pasa todo el mundo»*). Aquí no hay ruta alternativa de ejecución.
- **No inventa capacidades.** Solo reconoce las que el catálogo de permisos declara **lista verde y
  efecto lectura**, y además solo si el registro tiene de verdad un adaptador que las sirva. Una
  capacidad declarada sin ejecutor no se reconoce: `INV-9`, no se finge lo que no está construido.
- **No amplía nada.** No toca `permissions.py`, ni el catálogo, ni las listas. Lee.

POR QUÉ SOLO VERDE Y LECTURA. Porque esta superficie ejecuta **sin pedir confirmación**, y una
capacidad que modifica el mundo sin que el usuario confirme es exactamente lo que `ADR-0003`
prohíbe. Ampliar esto a acciones de escritura exigiría HITL y es otra decisión; el filtro se calcula
del catálogo, no se escribe a mano, para que añadir una capacidad roja no la cuele aquí por olvido.
"""

from __future__ import annotations

import unicodedata

from .operaciones import ESPECIFICACIONES
from .permissions import CATALOGO

#: Las variantes que se reconocen para cada capacidad. **Por segmento completo**, normalizadas.
#:
#: Son pocas y explícitas a propósito. Una tabla generosa acabaría robando frases a las superficies
#: que ya existen —y este proyecto ya pagó que una superficie nueva se quedara con turnos ajenos—.
#: Crecer aquí es barato y reversible; equivocarse hacia el lado ancho, no.
_VARIANTES: dict[str, tuple[str, ...]] = {
    "ejecutar_pruebas": (
        "ejecuta las pruebas",
        "ejecuta la bateria",
        "ejecuta la bateria de pruebas",
        "pasa las pruebas",
        "lanza las pruebas",
        "corre las pruebas",
        "ejecuta los tests",
        "pasa los tests",
        "lanza los tests",
        "corre los tests",
    ),
    "verificar_calidad": (
        "verifica la calidad",
        "verifica la calidad del codigo",
        "comprueba la calidad",
        "comprueba la calidad del codigo",
        "revisa la calidad",
        "revisa la calidad del codigo",
        "pasa el quality gate",
        "ejecuta el quality gate",
    ),
    "auditar_garantias": (
        "audita las garantias",
        "auditar las garantias",
        "revisa las garantias",
        "comprueba las garantias",
        "verifica las garantias",
        "siguen vigentes las garantias",
        "estan vigentes las garantias",
    ),
    "diagnosticar_estado": (
        "diagnostica tu estado",
        "diagnostica el estado",
        "haz un diagnostico",
        "diagnosticate",
        "como estas de salud",
        "revisa tu estado",
    ),
    "consultar_estado_sistema": (
        "como esta el sistema",
        "estado del sistema",
        "consulta el estado del sistema",
        "como esta la maquina",
        "cuanta memoria queda",
        "cuanto disco queda",
    ),
}

#: Las órdenes que SÍ llevan un argumento, y solo uno: **una ruta**.
#:
#: Es el salto respecto de las anteriores, y hace falta justificarlo porque el resto de este módulo
#: dice lo contrario para las órdenes sin argumento. La diferencia no es de criterio sino de
#: naturaleza: *«audita las garantías»* no admite objeto —se audita todo—, mientras que *«lista el
#: directorio»* **no significa nada sin decir cuál**. Negarle el argumento no la haría más segura;
#: la haría inservible.
#:
#: **Quién valida la ruta, y por qué no es este módulo.** La valida `operaciones.validar()`, que es
#: la puerta única del sistema de ficheros: comprueba el ámbito (`raices_por_defecto()`, hoy el
#: home), resuelve enlaces y rechaza lo que quede fuera. El adaptador lo dice en su cabecera:
#: *«el adaptador NO revalida por su cuenta: una validación duplicada podría divergir de la del
#: núcleo y crear un camino con reglas distintas»*. Eso vale igual para esta superficie. Aquí se
#: extrae la ruta; el ámbito lo decide quien ya lo decidía.
_PREFIJOS_CON_RUTA: dict[str, tuple[str, ...]] = {
    "listar_directorio": (
        "lista el directorio",
        "lista la carpeta",
        "lista el contenido de",
        "muestrame el directorio",
        "muestrame la carpeta",
        "que hay en el directorio",
        "que hay en la carpeta",
        "contenido del directorio",
        "contenido de la carpeta",
    ),
    "leer_archivo": (
        "lee el fichero",
        "lee el archivo",
        "leeme el fichero",
        "leeme el archivo",
        "muestrame el fichero",
        "muestrame el archivo",
        "que dice el fichero",
        "que dice el archivo",
        "contenido del fichero",
        "contenido del archivo",
    ),
}

#: **`buscar_archivo` queda FUERA de esta superficie, a propósito.** Su especificación en el núcleo
#: pide **dos** argumentos —`patron` y `raiz`—, y de una frase como *«busca el fichero informe.pdf»*
#: solo sale uno. Pasar medio contrato produciría un error del núcleo que el usuario leería como una
#: avería de AURA; y adivinar la raíz sería decidir por él dónde buscar. Se reconocerá el día que se
#: sepa extraer las dos cosas sin inventar ninguna. `_nombre_del_argumento` lo excluye por
#: construcción, así que añadirla a la tabla de arriba no bastaría para colarla.


#: El nombre del argumento que cada capacidad espera para su ruta. **Se lee de la especificación
#: del núcleo**, no se escribe aquí: `listar_directorio` y `leer_archivo` la llaman `ruta` y
#: `buscar_archivo` la llama `patron`, y mantener una copia de ese detalle en este fichero sería
#: exactamente la lista paralela que se desincroniza.
def _nombre_del_argumento(capacidad: str) -> str | None:
    args: tuple[str, ...] = tuple((ESPECIFICACIONES.get(capacidad) or {}).get("args") or ())
    return args[0] if len(args) == 1 else None


def _sin_tildes(texto: str) -> str:
    """Solo para COMPARAR el prefijo. La ruta nunca pasa por aquí: perdería acentos y mayúsculas,
    y `~/Música` dejaría de existir en un sistema de ficheros que distingue ambas cosas."""
    crudo = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in crudo if unicodedata.category(c) != "Mn")


#: Señales de que lo que va detrás del prefijo **no es solo una ruta**: la frase continúa.
#:
#: Encontrado auditando casos límite `[EJEC]`: *«lista el directorio ~/Documentos, gracias»* daba la
#: ruta `'~/Documentos, gracias'`, y *«…y luego dime la hora»* se la tragaba entera. El núcleo las
#: habría rechazado —no existen—, pero el usuario habría leído *«no existe '~/Documentos, gracias'»*
#: para algo que nunca pidió: un mensaje que culpa al sistema de ficheros de un fallo de
#: comprensión.
#:
#: **Ante la duda, no se ejecuta** (`ADR-0003`). Se prefiere no entender a entender de más: una ruta
#: con espacios legítima —`~/Mis Documentos`— sigue funcionando, porque lo que se busca no es el
#: espacio sino la marca de que hay **otra oración** detrás.
_LA_FRASE_SIGUE = (
    ",",
    ";",
    ":",
    "?",
    "!",
    " y ",
    " e ",
    " o ",
    " pero ",
    " luego ",
    " despues ",
    " gracias",
    " porfa",
    " por favor",
    " ademas ",
    " tambien ",
)


def _la_frase_sigue(resto: str) -> bool:
    """`True` si lo que va detrás del prefijo **no es una sola ruta**.

    Dos señales distintas, y las dos hacen falta:

    1. **Arranque de otra oración** (`, gracias`, ` y luego …`).
    2. **Más de un fragmento que parece ruta.** `~/a ~/b` no lleva ninguna marca de la lista y son
       dos rutas: cuál de las dos quiere el usuario no se adivina. Se cuentan los fragmentos que
       empiezan por `~` o `/` o llevan una barra dentro, así que `~/Mis Documentos` —una sola ruta
       con espacio— sigue pasando: `Documentos` no parece una ruta por sí solo.
    """
    marcado = " " + _sin_tildes(resto) + " "
    if any(senal in marcado for senal in _LA_FRASE_SIGUE):
        return True
    candidatas = [p for p in resto.split() if p.startswith("~") or p.startswith("/") or "/" in p]
    return len(candidatas) > 1


def reconocer_con_ruta(texto: str, disponibles) -> tuple[str, str] | None:
    """`(capacidad, ruta)` si el turno pide una capacidad SOBRE una ruta, o `None`.

    **Se compara palabra a palabra, y la ruta se toma del texto ORIGINAL.** Medido antes de
    escribirlo `[EJEC]`: la normalización del orquestador pasa *«lista el directorio Documentos»* a
    minúsculas y parte *«~/Música/notas.TXT»* en dos por el punto. Usarla para la ruta habría
    producido un fallo sutil y difícil de ver — «no existe» sobre un fichero que sí está—, así que
    el prefijo se compara normalizado y **lo que va detrás se conserva literal**.
    """
    if not texto or not texto.strip():
        return None
    servidas = set(disponibles or ())
    palabras = texto.strip().split()
    comparables = [_sin_tildes(p) for p in palabras]

    for capacidad in sorted(_PREFIJOS_CON_RUTA):
        if capacidad not in servidas or capacidad not in capacidades_reconocibles(_PREFIJOS_CON_RUTA):
            continue
        if _nombre_del_argumento(capacidad) is None:
            continue  # la capacidad no espera exactamente un argumento
        for prefijo in _PREFIJOS_CON_RUTA[capacidad]:
            trozos = prefijo.split()
            if comparables[: len(trozos)] != trozos:
                continue
            resto = " ".join(palabras[len(trozos) :]).strip()
            # Sin ruta no hay orden: *«lista el directorio»* a secas no dice cuál, y adivinarlo
            # sería decidir por el usuario dónde mirar.
            if not resto:
                return None
            if _la_frase_sigue(resto):
                return None
            return (capacidad, resto)
    return None


#: **Órdenes COMPUESTAS**: una petición que necesita varias capacidades para contestarse.
#:
#: No es arquitectura nueva: es el patrón que `_atender_conversacion_general` ya aplica a las
#: intenciones —*«si las dos pueden resolverse, prefiero una respuesta más larga antes que
#: interrumpir la conversación»* (CEO)— llevado a las capacidades. *«Haz una revisión»* no pide una
#: cosa: pide que AURA mire lo que sabe mirar y cuente qué encontró.
#:
#: **Componer NO concede autoridad.** Cada capacidad recorre el Motor Único por separado, con sus
#: permisos y su kill switch, y **una denegación no se compensa con los aciertos de las demás**: si
#: una queda bloqueada, la revisión lo dice. Lo contrario —presentar un informe completo cuando una
#: parte no llegó a mirarse— sería exactamente la clase de respuesta que este proyecto llama
#: «declarado ≠ real».
#:
#: Solo se componen capacidades que este módulo ya reconoce por separado: componer algo que no se
#: puede pedir suelto sería una puerta nueva disfrazada de síntesis.
_COMPUESTAS: dict[str, tuple[str, ...]] = {
    "revision": ("diagnosticar_estado", "auditar_garantias", "consultar_estado_sistema"),
}

_VARIANTES_COMPUESTAS: dict[str, tuple[str, ...]] = {
    "revision": (
        "haz una revision",
        "haz una revision completa",
        "revisate",
        "revisa tu estado completo",
        "como estas de todo",
        "hazme una revision",
        "dame un informe de estado",
        "revisa todo",
        "revisalo todo",
        # **«como va todo» NO está aquí, y se midió por qué** `[EJEC]`: la intercepta la superficie
        # de estado autónomo, que va antes y responde con el tablero de objetivos. Declararla sería
        # una variante que nunca se alcanza — código muerto disfrazado de capacidad, y el catálogo
        # prometiendo algo que el runtime no hace. Las superficies previas mandan: esta va detrás y
        # no le quita frases a ninguna.
    ),
}


def reconocer_compuesta(segmento: str, disponibles) -> tuple[str, ...] | None:
    """Las capacidades que hay que ejecutar para contestar esta petición, o `None`.

    Devuelve **solo las que el registro sirve de verdad**, en orden estable. Si no queda ninguna, no
    hay revisión que hacer y se devuelve `None`: inventar un informe sobre capacidades que no están
    montadas sería `INV-9`."""
    if not segmento:
        return None
    servidas = set(disponibles or ())
    reconocibles = set(capacidades_reconocibles())
    for nombre, variantes in _VARIANTES_COMPUESTAS.items():
        if segmento not in variantes:
            continue
        partes = tuple(c for c in _COMPUESTAS[nombre] if c in servidas and c in reconocibles)
        return partes or None
    return None


#: Lo que una orden SIN ruta no lleva: argumentos del usuario. La capacidad se ejecuta con su
#: configuración por defecto, fijada en el adaptador. Es la misma razón por la que `EjecutorQA`
#: construye el comando desde una constante suya — *«el comando es una CONSTANTE de este módulo;
#: `args` no participa en construirlo»*—: si el usuario pudiera parametrizar, la superficie dejaría
#: de ser cerrada.
_SIN_ARGUMENTOS: dict = {}


def capacidades_reconocibles(tabla=None) -> tuple[str, ...]:
    """Las que este módulo puede llegar a reconocer: verde + lectura, y con variantes escritas.

    **El filtro se calcula del catálogo**, no se escribe a mano. Si alguien reclasificara mañana una
    de estas como roja o como escritura, dejaría de reconocerse aquí **sin tocar este fichero** —que
    es lo que impide que una lista paralela se desincronice del catálogo de permisos y conceda por
    su cuenta lo que el catálogo ya no concede."""
    return tuple(
        sorted(
            nombre
            for nombre in (tabla if tabla is not None else _VARIANTES)
            if (ficha := CATALOGO.get(nombre)) is not None
            and ficha.get("lista") == "verde"
            and ficha.get("efecto") == "lectura"
        )
    )


def reconocer(segmento: str, disponibles) -> str | None:
    """La capacidad que pide este segmento, o `None` si no pide ninguna.

    `disponibles` son las capacidades que el registro sirve de verdad. Se exige la coincidencia con
    el mundo real y no solo con el catálogo: una capacidad declarada cuyo adaptador no esté montado
    no se reconoce, porque reconocerla llevaría a un «ninguna capacidad atiende» que el usuario
    leería como un fallo del sistema en vez de como lo que es —algo que no está construido—.

    El segmento llega ya normalizado por el llamante. Aquí no se normaliza otra vez: duplicar esa
    lógica crearía dos definiciones de «la misma frase» que podrían divergir."""
    if not segmento:
        return None
    servidas = set(disponibles or ())
    for nombre in capacidades_reconocibles():
        if nombre in servidas and segmento in _VARIANTES[nombre]:
            return nombre
    return None


def argumentos_de(_capacidad: str) -> dict:
    """Siempre vacíos. Existe como función, y no como un `{}` suelto en el llamante, para que el día
    que alguien quiera parametrizar una orden tenga que pasar por aquí y leer por qué no se hace."""
    return dict(_SIN_ARGUMENTOS)


__all__ = ["reconocer", "reconocer_con_ruta", "reconocer_compuesta", "capacidades_reconocibles", "argumentos_de"]
