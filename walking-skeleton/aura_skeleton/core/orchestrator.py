"""Orquestador (nucleo, Bible 3.2/4.2/4.3). Coordina memoria, router y permisos.
Los eventos son SERIALIZABLES (contrato 3.3): el estado de temporizacion se guarda por trace_id,
no en el payload. Asi el MISMO orquestador corre sobre el bus in-process o sobre NATS real."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from .. import observability as obs
from ..contracts import HISTORICO, RESULTADO_ACCION, Event, es_escritura_pasiva
from ..observability import Timer
from . import contexto_memoria, entorno, hogar, intencion, ordenes, percepcion, recuperacion, resultado_accion
from .almacen_senales import AlmacenSenales
from .aritmetica import resolver_formal
from .automatizacion import MotorAutomatizacion
from .autorizacion import es_autorizacion, resolver
from .autorizacion import identificador_en as identificador_de_decision
from .centro_gobierno import panel
from .ejecutor_modelo_usuario import EjecutorModeloUsuario
from .ejecutor_reglas import EjecutorReglas
from .estado_autonomo import (
    redactar_actividad,
    redactar_decisiones,
    redactar_evolucion,
    redactar_oportunidades,
    redactar_ultima_tarea,
)
from .estatus import CORE, Estatus, asignar, linea_de_contexto, presentar
from .identidad_memoria import (
    atributo_declarado,
    atributo_evocado,
    atributo_preguntado,
    atributo_preguntado_en_pasado,
    es_evocacion_generica,
)
from .modelo_usuario import describir_conocimiento, explicar_entrada
from .nodos import evaluar_avisos_nodos
from .notificaciones import Notificacion, notificacion_de_accion
from .operaciones import CAPACIDADES_QUE_DEVUELVEN_CONTENIDO, ErrorDeValidacion
from .operaciones import ESPECIFICACIONES as _ESPECS
from .registro import RegistroAdaptadores
from .reglas import ReglaUsuario, evaluar_condicion, resolver_args
from .senales import ClaseSenal


def _parse_decision(out: str, tid: str) -> tuple[str, dict, str]:
    """Parsing defensivo de la salida del LLM (resiliencia; los modelos reales a veces devuelven
    JSON imperfecto o con texto alrededor). Nunca crashea: ante fallo, decision segura (consulta)."""
    import json as _j

    for candidate in (out, _extract_json(out)):
        if not candidate:
            continue
        try:
            d = _j.loads(candidate)
            action = str(d.get("action", "consulta")) or "consulta"
            args = d.get("args", {}) if isinstance(d.get("args", {}), dict) else {}
            # UNA CONFIRMACION NO ES UNA RESPUESTA (CEO, 2026-09-01). Cuando el modelo no dice nada,
            # «Entendido.» afirma que se atendio algo -y el usuario no tiene forma de distinguirlo de
            # una respuesta real-. Se declara el hueco, que es lo unico cierto que se puede decir.
            say = str(d.get("say", "")) or "No he sabido qué responder a eso."
            return action, args, say
        except (ValueError, TypeError):
            continue
    obs.log("WARN", "orchestrator", "salida del LLM no parseable -> decision segura (consulta)", tid, audit=True)
    return "consulta", {}, "No entendi bien; puedes reformularlo?"


def _extract_json(s: str) -> str:
    a, b = s.find("{"), s.rfind("}")
    return s[a : b + 1] if 0 <= a < b else ""


# ADR-0014 — El Core es la unica fuente de verdad sobre los hechos del sistema.
# La deteccion de "el usuario pregunta por un recuerdo" es DETERMINISTA: no puede
# delegarse en el LLM, porque el objetivo es precisamente no consultarlo cuando no
# hay nada que recordar. Se normalizan acentos para que "habiamos"/"habíamos" coincidan.
#: **Vive en `intencion.py`, y aqui solo se aliasa.** Son marcadores de INTENCION, asi que su sitio
#: es M-1; `es_cognicion_general` tambien los necesita y duplicarlos seria la regla escrita dos veces que
#: este proyecto ya ha pagado. El nombre se conserva porque lo importan pruebas y un mutante.
_PATRONES_CONSULTA_MEMORIA = intencion.MARCADORES_DE_EVOCACION


def _normalizar(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# Palabra interrogativa inicial. Con los 15 literales de arriba, ADR-0014 reconocia 0 de las 77
# consultas de la bateria oficial —incluidas las 24 negativas que la garantia existe para proteger—:
# "¿cual es el nombre de mi abuela?" no la activaba. La deteccion por INTENCION INTERROGATIVA reconoce
# 70/77 sin falsos positivos sobre afirmaciones (medido). Sigue siendo determinista, como exige
# ADR-0014 punto 2: no se delega en el LLM.
_INTERROGATIVOS = (
    "que",
    "cual",
    "cuales",
    "cuando",
    "donde",
    "como",
    "cuanto",
    "cuanta",
    "cuantos",
    "cuantas",
    "quien",
    "quienes",
    "recuerdas",
    "sabes",
    "sabias",
    "dime",
    "cuentame",
    "conoces",
)


def _es_pregunta(texto: str) -> bool:
    """Intencion interrogativa: signo de interrogacion o interrogativo en posicion inicial.

    **M-1 (DP-D-M-7, Opcion A): esta funcion DELEGA, no decide.** La senal sintactica vive ahora en
    `intencion.es_interrogativa`, que es su unico sitio; aqui se conserva el nombre porque lo importan
    pruebas y otras superficies. El comportamiento es identico —verificado sobre las 77 consultas de
    `bateria_memoria.json`: coinciden 77/77— y por eso la garantia de 24/24 no se mueve.

    Lo que SI cambia es que ya no decide **dos** cosas. Antes gobernaba la puerta de ADR-0014 (que se
    LEE) y ademas la escritura de memoria (que se ESCRIBE). La segunda responsabilidad se fue a
    `intencion.debe_almacenarse`, que es el eje 2. Un detector sintactico no puede decidir si un turno
    aporta un hecho: son preguntas distintas, y mezclarlas hacia que tocar una moviera la otra.
    """
    return intencion.es_interrogativa(texto)


#: Verbos con los que una persona **pide que se haga** algo. Declarados, no deducidos del catalogo:
#: el catalogo dice que SABE hacer el sistema; esto dice como lo PIDE alguien, y son dos vocabularios
#: distintos. Solo decide **que contexto viaja al modelo**, nunca si algo puede ejecutarse: eso lo
#: siguen resolviendo el catalogo, los permisos y el motor unico.
_PIDE_ACCION = (
    "abre",
    "abrir",
    "enciende",
    "encender",
    "apaga",
    "apagar",
    "busca",
    "buscar",
    "lista",
    "listar",
    "lee ",
    "leer ",
    "mueve",
    "mover",
    "copia",
    "copiar",
    "renombra",
    "renombrar",
    "borra",
    "borrar",
    "elimina",
    "eliminar",
    "ejecuta",
    "ejecutar",
    "verifica",
    "verificar",
    "audita",
    "auditar",
    "diagnostica",
    "diagnosticar",
    "recuerdame",
    "crea ",
    "crear ",
    "organiza",
    # Volumen y silencio (acta 2026-10-22 §4): si la gramática del Core no reconoce la frase, el catálogo debe viajar.
    # La guarda del dispositivo nombrado, el Motor Único y la verificación siguen mandando.
    "volumen",
    "silencia",
)


def _es_turno_cognitivo(texto: str) -> bool:
    """La compuerta que deja salir un turno hacia el modelo por la excepcion cognitiva de la pared.

    D-FC-5 (superficie MUNDO positiva y cerrada) + referente: `es_cognicion_general` reconoce la FORMA
    de una pregunta general, pero no DE QUIEN habla; `referente` pone el posesivo y la evocacion por
    delante de la cognicion. Con las dos, un posesivo nunca sale al modelo por esta puerta -«si mi hija
    tiene 7 años, cuantos cumplira...?» es cognicion por forma y del usuario por referente-.

    Es una funcion PURA y de modulo a proposito: hoy otra superficie anterior (`resolver_formal`)
    reclama ese ejemplo antes de llegar aqui, asi que por la cascada la garantia no se veria. Que otra
    ruta lo intercepte antes es una circunstancia del orden, no una proteccion: la compuerta tiene que
    sostenerse sola (verificacion de mutacion FC-M13).
    """
    return intencion.es_cognicion_general(texto) and intencion.referente(texto) == intencion.REFERENTE_MUNDO


def _pide_accion(texto: str) -> bool:
    """Si el usuario esta pidiendo que AURA **haga** algo, no que le responda algo.

    Decide si el catalogo de acciones viaja en el prompt. Es deliberadamente **generoso**: ante la
    duda se manda el catalogo, porque perder una accion seria peor que pagar contexto de mas."""
    t = _normalizar(texto)
    return any(v in t for v in _PIDE_ACCION) or _RE_PIDE_ESCRIBIR.search(t) is not None


#: «escribe»/«escribir» como peticion de accion (frontera cognitiva, 2026-09-13). Hallazgo medido: con
#: el Core forzando `consulta` en modo cognitivo (mandato §20), «Escribe 'version nueva' en notas.txt»
#: caia en modo cognitivo porque el verbo faltaba en `_PIDE_ACCION`, y `escribir_archivo` -capacidad
#: de LISTA ROJA ya catalogada- quedaba inalcanzable; con Ollama real el esquema cognitivo ya descartaba
#: esa accion. NO va en la tupla porque alli se compara por SUBCADENA y «describe» contiene «escribe».
#: Se exige palabra completa, y se excluye la forma impersonal «se escribe» («¿como se escribe hola en
#: ingles?» pregunta por ortografia, no pide escribir nada).
_RE_PIDE_ESCRIBIR = re.compile(r"(?<!\bse )\bescrib(?:e|ir)\b")


def _es_consulta_de_memoria(texto: str) -> bool:
    """True si el usuario pregunta por algo supuestamente recordado.

    Dos vias: los marcadores de evocacion explicita ("acordamos", "te conte") O una pregunta. La
    segunda es la que hacia falta: sin ella la garantia de no-fabricacion cubria una fraccion minima
    del espacio real de preguntas.

    **Medido, y por eso sigue asi (2026-09-08).** Estrechar esta puerta a «marcadores + referencia
    personal» baja la proteccion de `24/24` a `17/24` sobre `tests/datos/bateria_memoria.json`: se
    escapan «¿a que hora ceno normalmente?», «¿que idioma hablo?», «¿que marca de telefono tengo?»
    —hechos personales cuya marca es el VERBO en primera persona, no un pronombre— y **dos casos
    adversariales**. Es el escenario de `ALERTA-004`. La decision de cambiarlo es del CEO.
    """
    t = _normalizar(texto)
    return any(p in t for p in _PATRONES_CONSULTA_MEMORIA) or _es_pregunta(texto)


# El usuario pregunta por lo que AURA hizo: "¿que ha pasado?", "¿tengo algun aviso?", "novedades".
_PATRONES_CONSULTA_NOTIF = (
    "que ha pasado",
    "que paso",
    "mientras no estaba",
    "algun aviso",
    "algun aviso?",
    "tengo avisos",
    "notificacion",
    "novedad",
)


def _es_consulta_de_notificaciones(texto: str) -> bool:
    """True si el usuario pregunta por lo que AURA ha hecho/avisado."""
    t = _normalizar(texto)
    return any(p in t for p in _PATRONES_CONSULTA_NOTIF)


# Soberania del modelo del usuario: inspeccionar, entender, corregir y olvidar lo que AURA sabe de el.
_PAT_MODELO_VER = ("que sabes de mi", "que sabes sobre mi", "que sabes acerca de mi", "que informacion tienes de mi")
# M3.2a opción A (acta 2026-10-11): el usuario se lleva su modelo. Se comprueba ANTES que `_PAT_MODELO_VER`
# porque «exporta lo que sabes de mi» contiene «que sabes de mi» y caería en ver (`_cae_en` es subcadena).
#
# GUARDA DE DOMINIO (hallazgo ECC ALTO 2026-10-11 y su RESIDUAL, mismo precedente que `_PAT_OLVIDO_REFLEXIVO`):
# «exporta» aislado aparece en frases mundanas que NO piden el modelo —«mi empresa exporta café»—; dispararlas
# volcaría datos personales. La petición exige VERBO de exportación/entrega **y** un OBJETO que sea una
# REFERENCIA REFLEXIVA a lo que AURA sabe del usuario. Los objetos genéricos («mis datos», «mi información»,
# «mi memoria», «mi perfil») se excluyen a propósito: son de uso corriente (datos de ventas, memoria USB,
# perfil de videojuego) y combinados con «exporta» reintroducían la fuga por otra superficie (ECC residual).
# Una petición ambigua tipo «quiero mis datos» NO vuelca PII: ante la duda, no se expone (como `_DESAMBIGUAR`).
_PAT_EXPORTAR_VERBO = (
    "exporta",
    "exportar",
    "descarga",
    "descargar",
    "dame",
    "mandame",
    "enviame",
    "quiero una copia",
    "llevarme",
)
_PAT_EXPORTAR_OBJETO = (
    "lo que sabes de mi",
    "lo que sabes sobre mi",
    "lo que sabes acerca de mi",
    "lo que tienes de mi",
    "lo que has aprendido de mi",
    "lo que recuerdas de mi",
    "mi modelo de usuario",
)


def _es_peticion_de_exportar(t: str) -> bool:
    return _cae_en(t, _PAT_EXPORTAR_VERBO) and _cae_en(t, _PAT_EXPORTAR_OBJETO)


# Confirmación afirmativa e inequívoca de un export pendiente. La garantía de privacidad es el
# consentimiento, y se compara por IGUALDAD del turno COMPLETO normalizado, NO por subcadena (ECC CRÍTICO
# 2026-10-11): «exportalo a otro formato de video» o «dale, exporta el informe a PDF» NO confirman, aunque
# contengan un verbo. La detección de `_es_peticion_de_exportar` puede ser imperfecta —a lo sumo
# pregunta—; lo que AUTORIZA el volcado es esta coincidencia exacta. Asimetría: ante la duda, NO se
# exporta (un fallo aquí es un «no exporté», nunca una fuga). La confirmación es un universo pequeño y
# cerrado; por eso puede acotarse con seguridad sin reabrir la carrera de patrones de la detección.
_CONFIRMA_EXPORT_EXACTO = frozenset(
    {
        "si",
        "si exporta",
        "si exportalo",
        "si exportala",
        "exporta",
        "exportalo",
        "exportala",
        "confirmo",
        "si confirmo",
        "adelante",
        "adelante exporta",
        "dale",
        "dale exporta",
        "si hazlo",
        "hazlo",
        "si quiero",
        "exporta mi modelo de usuario",
        "exporta lo que sabes de mi",
    }
)


def _confirma_export(t: str) -> bool:
    # El turno COMPLETO (sin puntuación ni espacios extra) debe ser exactamente una frase de confirmación.
    limpio = " ".join(t.replace(",", " ").replace(".", " ").replace(";", " ").replace("!", " ").split())
    return limpio in _CONFIRMA_EXPORT_EXACTO


_PAT_MODELO_PORQUE = ("por que dices", "por que sabes", "como lo sabes", "como sabes eso", "por que piensas")
_PAT_MODELO_REFUTA = ("ya no es cierto", "no es cierto", "eso esta mal", "eso es falso", "ya no es verdad")
_PAT_MODELO_OLVIDA = ("olvida", "olvidate")

# GUARDA DE DOMINIO del disparador de olvido (contencion de ALERTA-006, CEO 2026-08-03).
#
# "olvida" es subcadena de la construccion reflexiva "se me/te/le olvida", donde el que olvida es una
# PERSONA, no AURA: no hay ninguna orden que obedecer. Sin esta guarda, "Se me olvida siempre tomar la
# pastilla." destruia "tiene alergia a la penicilina" —un dato clinico declarado— y dejaba el fichero
# en 0 lineas (verificado). Es la misma leccion que _es_cancelacion_de_regla aprendio el 2026-08-02:
# un marcador aislado no basta, porque aparece en frases mundanas que no hablan del dominio.
_PAT_OLVIDO_REFLEXIVO = ("se me olvid", "se te olvid", "se le olvid", "se nos olvid", "se les olvid")

# Respuesta unica ante un referente ambiguo, para olvidar y para refutar: se pregunta en vez de actuar.
_DESAMBIGUAR = "¿A qué te refieres? Puedes decirme «¿qué sabes de mí?» y lo revisamos."

# --------------------------------- RECUPERACION POR INTENCION DE HECHOS DECLARADOS (incremento A) --
#
# El defecto que cierra: el CEO decia "Mi nombre es Mauricio" y "¿Cómo me llamo?" respondia "No tengo
# ningun recuerdo registrado sobre eso". Ahora el hecho SI se persiste (`HECHO_DECLARADO`), pero el
# recall es LEXICO: "como me llamo" no comparte ni un termino con "mi nombre es Mauricio", asi que
# nunca lo encontraria. Hace falta preguntarle al Modelo de Usuario POR INTENCION.
#
# Cada categoria declara (1) como se PREGUNTA, (2) como se DECLARO -para localizar el hecho entre lo
# que el modelo sabe- y (3) como se responde. La respuesta sale SIEMPRE del Modelo de Usuario: es lo
# que hace distinguible esta ruta del volcado episodico ("Segun lo que recuerdo: usuario dijo: ...")
# y lo que el candado A de las pruebas verifica.
_CONSULTAS_DE_HECHO: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    (
        ("como me llamo", "cual es mi nombre", "quien soy", "sabes como me llamo", "recuerdas mi nombre"),
        r"(?:me llamo|mi nombre es)\s+(.+)",
        "Te llamas {}.",
        "Todavía no me has dicho cómo te llamas.",
    ),
    (
        ("que trabajo hago", "en que trabajo", "cual es mi trabajo", "a que me dedico", "de que trabajo"),
        r"trabajo (?:en|de)\s+(.+)",
        "Trabajas en {}.",
        "Todavía no me has dicho en qué trabajas.",
    ),
    (
        # "que sabes de mi proyecto" NO se lista: `_PAT_MODELO_VER` contiene "que sabes de mi" y
        # `_cae_en` casa por subcadena, asi que el turno se atiende antes. Declararlo aqui seria
        # codigo muerto que aparenta cobertura.
        ("en que proyecto trabajo", "cual es mi proyecto", "como se llama mi proyecto"),
        r"(?:proyecto llamado|mi proyecto se llama)\s+(.+)",
        "Tu proyecto se llama {}.",
        "Todavía no me has dicho en qué proyecto trabajas.",
    ),
    (
        # Solo las dos formas INEQUIVOCAS. «que color me gusta mas» NO se lista: lleva un marcador de
        # gusto y pertenece a la rama de preferencias; listarla aqui mezclaria las dos familias que el
        # acta del CEO (2026-08-09) existe para separar.
        ("cual es mi color favorito", "cual es mi color preferido"),
        r"mi color (?:favorito|preferido) es\s+(?:el\s+)?(.+)",
        "Tu color favorito es {}.",
        "Todavía no me has dicho cuál es tu color favorito.",
    ),
)

_PAT_CONSULTA_PREFERENCIA = ("que prefiero", "cuales son mis preferencias", "que me gusta")

# ------------------------------------------- EMPAREJAMIENTO GRAMATICAL SIMETRICO (CEO, 2026-09-10) --
#
# La tabla de arriba no escala: cada atributo costaba dos ediciones de producto. Pero «mi X es V» y
# «¿cual es mi X?» **comparten el sujeto posesivo**, y eso basta para emparejar sin enumerar preguntas.
# Se deriva X de los dos lados y se resuelve por IGUALDAD EXACTA -nunca por parecido, que es lo que hace
# el recall y lo que esta ruta existe para evitar-.
#
# Se lee la FRASE LITERAL que la memoria ya guarda: sin metadata nueva, sin migracion, sin tocar
# contratos. Uno o dos terminos en el atributo, los mismos a los dos lados.
# Se aplica sobre el texto ORIGINAL, no sobre el normalizado, por el mismo motivo que `_valor_declarado`:
# el dato es del usuario y se le repite COMO EL LO ESCRIBIO -«cumpleaños», no «cumpleanos»; «Seat León»,
# no «seat leon»- (ADR-0017, fidelidad al modelo). De ahi `[^\W\d_]`, que acepta letras acentuadas; la
# comparacion del atributo si se hace normalizada, para que la pregunta case con la declaracion.
# La gramatica vive en `identidad_memoria` desde AMP-AURA etapas 1-2: el EJECUTOR la necesita para
# versionar al escribir y no puede importar este modulo (seria circular). Una sola fuente de verdad.
_atributo_preguntado = atributo_preguntado
_atributo_declarado = atributo_declarado


def _valor_declarado(contenido: str, patron: str) -> str | None:
    """El valor que el usuario declaro, extraido de SU PROPIA frase tal como la dijo.

    Se busca sobre el texto original -no normalizado- para devolver "Mauricio" y no "mauricio": el
    dato es del usuario y se le repite como el lo escribio (ADR-0017: fidelidad al modelo).
    """
    hallado = re.search(patron, contenido, re.IGNORECASE)
    if not hallado:
        return None
    # No glotona: "trabajo en logistica y me gusta" declara la ocupacion, no la coletilla. Se corta
    # en el primer conector o signo de puntuacion.
    bruto = re.split(r"\s+(?:y|pero|aunque|porque)\s+|[,;.]", hallado.group(1))[0]
    return bruto.strip(" .,;:!?") or None


def _es_peticion_de_olvido(t: str) -> bool:
    """True solo si el usuario ORDENA a AURA olvidar, no si describe un olvido propio.

    Guarda parcial y deliberadamente conservadora: cubre la construccion reflexiva, que es el falso
    positivo demostrado. La discriminacion completa (imperativo dirigido a AURA vs. cualquier otro
    uso de "olvidar") corresponde al clasificador de intencion de D-M-7, no a una tabla mas de
    subcadenas. La red de seguridad real es que un referente ambiguo ya no destruye nada: ver `_foco`.
    """
    if any(p in t for p in _PAT_OLVIDO_REFLEXIVO):
        return False
    return _cae_en(t, _PAT_MODELO_OLVIDA)


def _cae_en(t: str, pats: tuple) -> bool:
    return any(p in t for p in pats)


# Automatizaciones definidas por el usuario (MVP capacidad 5, Bible 6.4). La deteccion es DETERMINISTA en el
# nucleo (ADR-0014), igual que el resto de superficies: crear una regla o consultarla es un HECHO, no una
# inferencia, y no se delega en el LLM. El reconocedor extrae DEL TEXTO que accion del usuario dispara la
# regla, entre un catalogo CERRADO de cuatro (INV-9: no se finge una capacidad no construida). La accion de
# la regla es SIEMPRE "copiar_archivo" —la unica de lista verde, la unica sin riesgo de narrar un exito que
# no ocurrio—; ampliar a otras acciones de regla es deuda registrada, no rearquitectura.
_PAT_REGLAS_VER = ("que automatizaciones", "que automatizacion", "mis automatizaciones", "que reglas", "mis reglas")
_PAT_REGLA_DISPARADOR = ("siempre que", "cada vez que", "cuando ")

# El usuario RECHAZA una automatizacion en vez de pedirla. Sin esto, "no quiero que cuando borres un
# archivo guardes una copia" creaba justo la regla que se estaba rechazando, y "deja de guardar copia"
# respondia "lo hare a partir de ahora": AURA hacia lo contrario de lo pedido (auditoria 2026-08-02).
# Desactivar aun no es posible (deuda D-A-1/D-A-9), asi que lo unico honesto es decirlo.
_PAT_CANCELACION = (
    "no quiero",
    "deja de",
    "ya no ",
    "no guardes",
    "no hagas",
    "para de",
    "quita la",
    "elimina la automatizacion",
)


# Mencion al dominio de automatizaciones: exigirla ademas del marcador de cancelacion evita que
# cualquier frase mundana con "ya no ", "no quiero" o "deja de" secuestre el turno (auditoria
# independiente 2026-08-02): "Ya no tengo hambre, gracias." tiene el marcador "ya no " pero no
# habla de automatizaciones en absoluto.
_PAT_DOMINIO_AUTOMATIZACION = ("copia", "copias", "automatiz", "regla", "reglas")


def _es_cancelacion_de_regla(texto: str) -> bool:
    """True si el usuario pide DEJAR de hacer algo, no empezar a hacerlo.

    Hallazgo de auditoria independiente (2026-08-02): antes bastaba un marcador de cancelacion
    aislado para entrar en esta rama, y esos marcadores aparecen en frases mundanas corrientes
    ("Ya no tengo hambre, gracias.", "No quiero salir hoy.", "Deja de llover.") que no tienen nada
    que ver con automatizaciones. Ahora se exigen DOS cosas: el marcador Y una mencion al dominio
    de automatizaciones (copia/automatizacion/regla). Sin mencion de dominio, el turno sigue su
    flujo normal (memoria/LLM) en vez de que el nucleo responda por una automatizacion que nadie
    menciono.
    """
    t = _normalizar(texto)
    return any(p in t for p in _PAT_CANCELACION) and any(p in t for p in _PAT_DOMINIO_AUTOMATIZACION)


# Accion disparadora -> (palabras que la reconocen en el texto normalizado, sufijo ESTABLE del rule_id).
# Los verbos irregulares cambian de raiz en subjuntivo ("mover" -> "muevas"), de ahi las dos formas para
# mover_archivo. Esta tabla es el UNICO lugar que decide que se reconoce: anadir un disparador nuevo es
# anadir una fila aqui, nunca inventar una accion de regla no soportada por el motor (INV-9).
_PATRONES_ACCION_DISPARADORA: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("borr", "elimin"), "borrar_archivo", "borrar"),
    (("escrib",), "escribir_archivo", "escribir"),
    (("mov", "muev"), "mover_archivo", "mover"),
    (("renombr",), "renombrar_archivo", "renombrar"),
)

# Identificadores HISTORICOS de reglas que hoy se generan con otro nombre. Existen porque el `rule_id`
# es la unica defensa contra duplicar una automatizacion, y renombrarlo dejaria a quien ya la tuviera
# creada con DOS reglas activas identicas: la segunda copia fallaria por destino existente y AURA narraria
# un aviso de error en cada disparo. Nunca se borra una fila de aqui: es compatibilidad hacia atras.
_IDS_HISTORICOS: dict[str, tuple[str, ...]] = {
    "copia-al-borrar": ("copia-antes-de-borrar",),
}


# mover_archivo/renombrar_archivo traen el archivo en "origen", no en "ruta" (ver core/operaciones.py):
# la regla debe leer la clave que la accion disparadora realmente publica en su evento.
_CLAVE_EVENTO_POR_ACCION = {
    "borrar_archivo": "ruta",
    "escribir_archivo": "ruta",
    "mover_archivo": "origen",
    "renombrar_archivo": "origen",
}

# Accion del usuario -> clausula en pasado y primera persona (habla AURA), para narrar "... y luego <esto>".
_CLAUSULA_USUARIO = {
    "borrar_archivo": "lo borré",
    "mover_archivo": "lo moví",
    "renombrar_archivo": "lo renombré",
    "escribir_archivo": "lo escribí",
}


# El unico motivo que significa "no habia nada que respaldar". Es el mensaje literal del sistema
# operativo (errno ENOENT), no una frase del dominio.
#
# ES DELIBERADAMENTE ESTRECHO, y la razon la encontro una auditoria independiente (2026-08-02): el
# motivo de error INCLUYE el nombre del fichero, que elige el USUARIO. Con `cuaderno existente.txt`,
# el motivo de una colision real —"el destino ya existe: 'cuaderno existente.txt.copia'"— contiene
# "no existe" a traves de la frontera de palabras («cuader-NO EXISTE-nte». Buscar frases del dominio
# como "no existe" hacia que AURA silenciara un respaldo que NO se hizo: el archivo se borraba y el
# usuario no se enteraba de que habia perdido la copia. Perdida de datos en silencio.
#
# Por eso solo se acepta el texto del SO, que ningun nombre de fichero razonable contiene, y ademas se
# exige que el motivo NO hable de colision. Cualquier otro fallo —permisos, ambito, colision— se
# comunica siempre: el silencio es la excepcion, y solo para lo que no es un problema.
_MOTIVO_ORIGEN_AUSENTE = "no such file or directory"
_MOTIVOS_QUE_NUNCA_SE_CALLAN = ("ya existe", "permission", "denied", "protegid", "fuera del")


def _nada_que_respaldar(resultado: dict) -> bool:
    """True solo si el respaldo fallo porque el origen aun no existia (crear un archivo nuevo)."""
    motivo = str(resultado.get("motivo", "")).lower()
    if any(m in motivo for m in _MOTIVOS_QUE_NUNCA_SE_CALLAN):
        return False
    return _MOTIVO_ORIGEN_AUSENTE in motivo


#: GUARDA DE DECLARACION del disparador de consulta de reglas (defecto §4.6 del CHECKLIST, abierto
#: desde 2026-08-02 y medido de nuevo el 2026-09-15).
#:
#: «Mis reglas de casa son otras» respondia *«No tienes ninguna automatizacion activa»*: `_PAT_REGLAS_VER`
#: contiene la subcadena «mis reglas», y «regla» es una palabra corriente del español que casi nunca
#: habla de automatizaciones —reglas de casa, del juego, de la vida—. La frase no PREGUNTA nada: AFIRMA.
#:
#: La forma de la guarda copia el precedente que ya vive en este mismo fichero: `_es_cancelacion_de_regla`
#: dejo de bastarse con un marcador aislado y paso a exigir tambien una mencion de dominio, por esta
#: misma clase de falso positivo (auditoria del 2026-08-02). Aqui la asimetria que resuelve el caso es
#: el ORDEN: en una consulta el verbo va DELANTE («¿cuales SON mis reglas?»), y en una declaracion va
#: DETRAS («mis reglas de casa SON otras»). Solo se exige que el verbo caiga en la misma oracion.
#:
#: Sin coincidencia, el turno NO se responde aqui: sigue su flujo normal (declaracion/memoria/LLM), que
#: es exactamente lo que hace el precedente. No se inventa una respuesta nueva para la frase.
_DECLARA_SOBRE_SUS_REGLAS = re.compile(r"\bmis? reglas\b[^.?!¿]*\b(?:son|es|eran|fueron)\b")


def _es_consulta_de_reglas(texto: str) -> bool:
    """True si el usuario quiere inspeccionar sus automatizaciones ("¿que automatizaciones tengo?")."""
    t = _normalizar(texto)
    if _DECLARA_SOBRE_SUS_REGLAS.search(t):
        return False
    return any(p in t for p in _PAT_REGLAS_VER)


#: Marca de recorte. Visible a proposito: el modelo tiene que saber que ve un extracto y no la respuesta
#: entera, igual que la etiqueta de estatus le dice que una propuesta no esta verificada (D-FC-8 = B).
_MARCA_RECORTE = " [...]"


def _recortar_respuesta_previa(say: str, limite: int | None) -> str:
    """Extracto de una respuesta PREVIA de AURA para el prompt. DR-4.

    Solo se recorta lo que dijo AURA: lo que dijo el USUARIO reentra siempre integro, porque es lo que la
    conversacion recuerda de el. El recorte no toca el buffer ni ninguna memoria: solo lo que se ensena
    al modelo en ESTE prompt.
    """
    if limite is None or len(say) <= limite:
        return say
    return say[:limite].rstrip() + _MARCA_RECORTE


#: `k` de la segunda consulta de `recall` cuando los `k=3` por defecto solo trajeron entradas no vigentes.
#: Solo recorta el resultado (las tres implementaciones de `recall` aceptan `k` y no cambian de semantica):
#: es «todas las coincidencias» en la practica, y el limite real del contexto lo pone `len(hits)`.
_K_TODAS_LAS_COINCIDENCIAS = 10_000


def _da_por_cierto(entrada: dict) -> bool:
    """True si el Core sigue afirmando esta entrada de memoria: ni refutada ni superseded.

    Es la misma definicion de «vigente» que ya aplican `_predicado_identidad` (en
    `core/ejecutor_modelo_usuario.py`) para cerrar versiones y `_responder_hecho` para contestar el
    presente. **Deuda declarada:** la regla vive ahora escrita en tres sitios —el patron que
    `CHECKPOINT-CONTINUIDAD.md` §0 identifica como defecto estructural—. No se unifica aqui porque el
    ejecutor queda fuera de la zona que esta correccion puede tocar.
    """
    prov = entrada.get("provenance") or {}
    # `retirada` (DR-2): el eco episodico de un hecho olvidado o refutado. Sigue existiendo como registro
    # de lo que se dijo, pero ya no entra al contexto del modelo como si fuera memoria vigente.
    return not prov.get("refutada") and prov.get("valid_until") is None and not prov.get("retirada")


def _detectar_accion_disparadora(t: str) -> tuple[str, str] | None:
    """Devuelve (accion, sufijo) para la PRIMERA accion disparadora reconocida en el texto normalizado.

    None si el texto no menciona ninguna de las cuatro accion conocidas: fuera de esas cuatro no hay
    reconocimiento posible (INV-9), y el llamador debe seguir el flujo normal hacia el LLM.
    """
    for palabras, accion, sufijo in _PATRONES_ACCION_DISPARADORA:
        if any(p in t for p in palabras):
            return accion, sufijo
    return None


def _detectar_accion_en_cancelacion(t: str) -> tuple[str, str] | None:
    """Detecta la accion disparadora en una frase de CANCELACION, quitando antes el ruido propio
    de la frase de rechazo. Se usa SOLO en el camino de desactivar (`_desactivar_regla`), nunca en
    la creacion: alli el texto no lleva marcador de cancelacion que limpiar.

    Hallazgo de auditoria independiente (2026-08-02): "elimin" es sinonimo de "borrar" en
    _PATRONES_ACCION_DISPARADORA, y tambien es el verbo de la propia frase de cancelacion "elimina
    la automatizacion de escribir archivos". _detectar_accion_disparadora devuelve la PRIMERA fila
    que coincide en la tabla (borrar va antes que escribir), asi que la deteccion caia sobre el
    "elimin" del verbo de la orden, no sobre la accion que el usuario de verdad queria apagar. Al
    quitar antes los marcadores de _PAT_CANCELACION y la palabra "automatizacion"/"automatizaciones",
    el residuo de "elimina la automatizacion de escribir archivos" queda "de escribir archivos":
    ahi "elimin" ya no existe y la deteccion encuentra la accion correcta.
    """
    resto = t
    for marcador in _PAT_CANCELACION:
        resto = resto.replace(marcador, " ")
    resto = resto.replace("automatizaciones", " ").replace("automatizacion", " ")
    return _detectar_accion_disparadora(resto)


def _es_creacion_de_regla(texto: str) -> bool:
    """True si el usuario define una automatizacion "copia antes de <disparador>" en lenguaje natural.

    Reconoce el patron disparador ("siempre que / cada vez que / cuando") + una de las cuatro acciones
    disparadoras conocidas (borrar/escribir/mover/renombrar) + intencion de respaldo (copia). Ninguna
    otra combinacion crea regla: sigue el flujo normal (LLM), nunca una regla "por defecto".
    """
    t = _normalizar(texto)
    if _es_cancelacion_de_regla(texto):
        return False  # rechazar no es crear
    return any(p in t for p in _PAT_REGLA_DISPARADOR) and "copia" in t and _detectar_accion_disparadora(t) is not None


# --- Ventana del SO Interno en la conversacion (M3 entry) -----------------------------------
#
# El chat es la interfaz con la que el usuario consulta el Sistema Operativo de AURORA. Antes de
# esto, preguntas como "¿que capacidades tienes?" o "¿en que estas trabajando?" no tenian
# superficie propia: caian en la ausencia de memoria (ADR-0014) y AURA respondia "No tengo ningun
# recuerdo registrado sobre eso" aunque la respuesta EXISTIERA en el propio sistema (el registro de
# adaptadores, el Estado Operativo, el Centro de Gobierno, el Plan de Formacion). Eso es el mismo
# patron "declarado != real" que este proyecto ya ha pagado 8 veces, aplicado a la interfaz.
#
# Misma disciplina que el resto de superficies (ADR-0014): deteccion DETERMINISTA por patrones en
# el nucleo, JAMAS clasificada por el LLM. Y la misma cautela de INV-9: la fuente se LEE tal cual;
# si esta vacia o ausente, se declara -nunca se rellena con contenido fabricado-.
#
# Se anaden DESPUES de las 8 superficies deterministas previas (modelo de usuario: ver/porque/
# refuta/olvida; notificaciones; reglas: ver/crear/cancelar -- CHECKLIST-CONTINUIDAD.md #4.6) y
# ANTES de la ausencia de memoria: ninguna de sus frases se solapa con las de arriba (comprobado
# frase a frase contra las 8 tablas de patrones existentes; la prueba de no interferencia vive en
# tests/integration/test_conversacion_ventana_so.py).

_PAT_CAPACIDADES = (
    "que capacidades tienes",
    "que capacidades tenes",
    "cuales son tus capacidades",
    "que puedes hacer",
    "que podes hacer",
)

# La lista sigue siendo POSITIVA y CERRADA -solo desvia lo que nombra-, pero deja de exigir la
# inflexion exacta. El CEO escribio "¿en que estas TRABAJADO ahora?" y la frase cayo hasta el final
# del recorrido, donde una memoria vacia contesta "no tengo ningun recuerdo": una pregunta sobre uno
# mismo que no se reconoce no se queda sin responder, se responde MAL, porque el ultimo recurso
# pertenece a otro dominio. Se reconoce por RAIZ ("en que estas trabaj") en lugar de anadir cada
# variante a mano, que es como esta lista se quedaria corta otra vez a la siguiente.
_PAT_TAREAS = (
    "que tareas tienes",
    "cuales son tus tareas",
    "en que estas trabaj",  # trabajando · trabajado · trabajas
    "en que trabaj",
    "que estas haciendo",
    "en que andas",
    "cual es tu estado",
    "que tarea estas ejecutando",
    "que estas ejecutando",
    "que vas a hacer despues",
    "que haras despues",
)

# "¿que hiciste?" mira al pasado y se contesta con el HISTORIAL, no con lo que se dijo hace dos
# turnos: la conversacion reciente no es prueba de que algo ocurriera.
# LOS TRES DOMINIOS QUE CAIAN EN MEMORIA O EN EL PROVEEDOR (CEO, 2026-09-01). Ninguna de estas
# preguntas es «buscar recuerdos»: todas tienen una fuente real registrada, y lo unico que faltaba
# era la puerta que llevara hasta ella.
_PAT_DECISIONES = (
    "que decisiones",
    "decisiones pendientes",
    "que necesitas de mi",
    "necesitan de mi",
    "que tengo que decidir",
    "que opciones tiene",
    "que opciones hay",
    "muestrame las opciones",
    "opciones disponibles",
)

_PAT_OPORTUNIDADES = (
    "que oportunidades",
    "oportunidades bloqueadas",
    "por que estan bloqueadas",
    "por que estan bloqueados",
    "que trabajo tienes",
    "que trabajo podria",
    "que trabajo puedes",
    "que tienes pendiente",
    "que tengo bloqueado",
    "tengo bloqueadas",
)

# MAS ESPECIFICOS que `_PAT_ULTIMA_TAREA` a proposito, y evaluados ANTES: «¿que hiciste?» pregunta
# por LA ultima tarea; «¿que hiciste hoy?» o «¿que mejoraste?» piden el recorrido. Sin esta
# separacion, la mas general se quedaria las dos.
_PAT_EVOLUCION = (
    "que hiciste hoy",
    "que has hecho hoy",
    "que mejoraste",
    "que has mejorado",
    "que hiciste para evolucionar",
    "que has hecho para evolucionar",
    "en que has avanzado",
    "como has evolucionado",
)

_PAT_ULTIMA_TAREA = (
    "que hiciste",
    "que has hecho",
    "cual fue tu ultima tarea",
    "tu ultima tarea",
    "cual ha sido tu ultima tarea",
)

_PAT_GOBIERNO = (
    "por que estas bloqueada",
    "por que estas bloqueado",
    "que esta pasando",
)

_PAT_FORMACION = (
    "que aprendiste",
    "que has aprendido",
    # «cuanto te falta para completarte» pregunta por el ESTADO del producto, y ese estado existe: son
    # las capacidades en observacion y bloqueadas del Plan de Formacion. Enviarla al modelo seria
    # pedirle que opine sobre su propia completitud -fingir capacidad, INV-9-; enviarla a memoria
    # personal seria peor. Su fuente correcta es la que ya se lee aqui.
    "te falta para completarte",
    "cuanto te falta",
    "que te falta",
)


# GUARDA DE DOMINIO (rechazo de auditoria independiente, defecto 2): la misma disciplina que
# `_es_cancelacion_de_regla` (marcador + mencion de dominio) y `_es_peticion_de_olvido` (marcador
# menos la construccion reflexiva) aplicada aqui. "que esta pasando", "que estas haciendo" y "que
# aprendiste"/"que has aprendido" son marcadores DEMASIADO ANCHOS en solitario: aparecen en frases
# mundanas que no hablan del propio sistema, sino de algo que el usuario o un tercero posee.
#
# Verificado por la auditoria: sin esta guarda, "¿que esta pasando con mi pedido de Amazon?" volcaba
# el Centro de Gobierno, "¿que estas haciendo con mis archivos?" volcaba el Estado Operativo, y "¿que
# has aprendido de mi?" volcaba el Plan de Formacion -con notas internas sobre APUS-5- en vez de caer,
# como ANTES de este incremento, en la ausencia de memoria (ADR-0014). Contestar MAL es peor que no
# responder: rompe el principio de que el usuario no debe percibir la arquitectura interna.
#
# `\b` (limite de palabra) evita falsos positivos por sub-cadena ("de mi" no debe reconocer "de
# miedo"). Con objeto ajeno, el turno sigue su flujo normal (memoria/LLM), igual que las otras
# guardas de dominio del fichero.
_RE_OBJETO_AJENO = (
    r"\bcon mi\b",
    r"\bcon mis\b",
    r"\bcon tu\b",
    r"\bcon tus\b",
    r"\bde mi\b",
    r"\bde mis\b",
    r"\bde ti\b",
)


def _tiene_objeto_ajeno(texto_norm: str) -> bool:
    """True si la frase declara algo que el usuario o un tercero posee ("mi pedido", "mis archivos",
    "de mi"): entonces la pregunta no es sobre AURORA misma, y las superficies de la ventana del SO
    no deben interceptarla."""
    return any(re.search(p, texto_norm) for p in _RE_OBJETO_AJENO)


def _es_consulta_de_capacidades(texto: str) -> bool:
    """True si el usuario pregunta que puede hacer AURA ("¿que capacidades tienes?")."""
    return any(p in _normalizar(texto) for p in _PAT_CAPACIDADES)


def _es_consulta_de_tareas(texto: str) -> bool:
    """True si el usuario pregunta por el trabajo en curso del ciclo de AURORA, y no por algo que
    el o un tercero posee (guarda de dominio, ver `_tiene_objeto_ajeno`)."""
    t = _normalizar(texto)
    return any(p in t for p in _PAT_TAREAS) and not _tiene_objeto_ajeno(t)


def _es_consulta_de_decisiones(texto: str) -> bool:
    """True si pregunta por las decisiones que esperan una respuesta suya.

    Ademas de las formas declaradas, **cualquier pregunta que nombre un identificador de decision**
    pertenece a este dominio. Eso es semantica, no una lista: si el texto nombra `D-ORCH-6`, la
    pregunta es sobre esa decision, y contestarla desde la memoria del usuario -que no sabe nada de
    ella- era el defecto."""
    t = _normalizar(texto)
    for patron in _PAT_DECISIONES:
        if patron not in t:
            continue
        # La guarda de dominio se aplica SALVO que el propio patron lleve la primera persona dentro.
        # «¿que decisiones necesitan de mi?» contiene «de mi», y `_tiene_objeto_ajeno` lo leia como
        # una posesion del usuario y mandaba la pregunta a la memoria — que no sabe nada de
        # decisiones. Aqui «de mi» no marca una posesion: es parte de la pregunta.
        if "mi" in patron.split() or not _tiene_objeto_ajeno(t):
            return True
    # NOMBRAR una decision basta, sea pregunta u orden. «Haz D-ORCH-6» y «Autorizo D-ORCH-6 si te
    # parece bien» no autorizan -la orden no es un permiso y lo condicionado no decide-, pero hablan
    # de esa decision: mandarlas al proveedor las dejaba sin la informacion que el sistema tiene
    # delante. La autorizacion inequivoca se evalua ANTES, asi que no se le roba nada.
    return identificador_de_decision(texto) is not None


def _es_consulta_de_oportunidades(texto: str) -> bool:
    t = _normalizar(texto)
    return any(p in t for p in _PAT_OPORTUNIDADES) and not _tiene_objeto_ajeno(t)


def _es_consulta_de_evolucion(texto: str) -> bool:
    t = _normalizar(texto)
    return any(p in t for p in _PAT_EVOLUCION) and not _tiene_objeto_ajeno(t)


def _es_consulta_de_ultima_tarea(texto: str) -> bool:
    """True si el usuario pregunta que hizo AURORA -no que hizo con algo suyo (guarda de dominio).

    La guarda importa mas aqui que en ninguna otra: "¿que hiciste con mis archivos?" es una pregunta
    sobre el usuario, y robarsela para contestar con el historial del ciclo seria exactamente el
    defecto de este incremento, con los dominios cambiados de sitio."""
    t = _normalizar(texto)
    return any(p in t for p in _PAT_ULTIMA_TAREA) and not _tiene_objeto_ajeno(t)


def _es_consulta_de_gobierno(texto: str) -> bool:
    """True si el usuario pregunta por que AURORA esta bloqueada o que esta pasando ahora mismo, y
    no por algo ajeno al sistema (guarda de dominio, ver `_tiene_objeto_ajeno`)."""
    t = _normalizar(texto)
    return any(p in t for p in _PAT_GOBIERNO) and not _tiene_objeto_ajeno(t)


def _es_consulta_de_formacion(texto: str) -> bool:
    """True si el usuario pregunta que ha aprendido AURORA sobre el mundo o sus capacidades -no que
    ha aprendido SOBRE EL USUARIO, eso es Modelo de Usuario (guarda de dominio, `_tiene_objeto_ajeno`)."""
    t = _normalizar(texto)
    return any(p in t for p in _PAT_FORMACION) and not _tiene_objeto_ajeno(t)


# --------------------------------------------- CONVERSACION GENERAL v1 (contrato del CEO, 06f53f3) --
#
# POR QUE EXISTE. El CEO uso AURORA y "¿quien eres?", "¿como puedo ayudarte?" y "buenos dias Aurora,
# ¿que tienes pendiente para hoy?" respondieron "No tengo ningun recuerdo registrado sobre eso":
# `_es_consulta_de_memoria` termina en `or _es_pregunta(texto)`, asi que TODA interrogativa que nadie
# haya reclamado antes cae en la ausencia de memoria.
#
# QUE NO SE TOCA. Ni `_es_consulta_de_memoria` ni la puerta de ADR-0014: esta lista es POSITIVA y
# CERRADA, solo puede desviar lo que nombra. Lo que no esta aqui sigue el camino de hoy bit a bit --
# incluidas las 24 negativas de la bateria oficial, que la garantia existe para proteger.
#
# LA UNIDAD DE RECONOCIMIENTO ES UNA SECUENCIA, NO UNA FRASE (decision del CEO). Un turno puede
# contener varias intenciones: las MODIFICADORAS (saludo, cortesia, despedida) no consumen el turno
# -solo anteponen su respuesta-; las PRINCIPALES deciden quien responde. Por eso "buenos dias Aurora,
# ¿que tienes pendiente para hoy?" no se pierde: el saludo modifica, la consulta manda.
#
# COINCIDENCIA POR SEGMENTO COMPLETO, NUNCA POR SUBCADENA. `any(patron in texto)` es exactamente la
# construccion que produjo el defecto original, y aqui lo recrearia en el otro sentido: "¿que estas
# haciendo con mis archivos?" volveria a robarle el turno al Estado Operativo. Exigir el segmento
# entero ES la guarda de dominio -- la misma disciplina que `_es_cancelacion_de_regla` aprendio el
# 2026-08-02, aplicada con otro mecanismo.

_VOCATIVOS = ("aurora", "aura")

# Fronteras de segmento: puntuacion fuerte. La conjuncion "y" NO parte aqui (ver `_partir_en_partes`):
# solo se prueba como segunda pasada, para no trocear frases que se reconocen enteras.
_SEPARADORES_DE_SEGMENTO = re.compile(r"[,;.!?¿¡\n]+")

# Cada saludo lleva SU redaccion: "buenos dias" no puede contestarse "buenas tardes". El texto sale de
# la variante reconocida, nunca del reloj -- deducir la franja horaria del sistema seria afirmar algo
# que el usuario no ha dicho, y ademas volveria la respuesta no reproducible.
_VAR_SALUDO = {
    "hola": "Hola",
    "hey": "Hola",
    "buenas": "Hola",
    "que tal": "Hola",
    "que tal estas": "Hola",
    "como estas": "Hola",
    "como te va": "Hola",
    "buenos dias": "Buenos días",
    "buen dia": "Buenos días",
    "buenas tardes": "Buenas tardes",
    "buenas noches": "Buenas noches",
}

_VAR_CORTESIA = ("gracias", "muchas gracias", "mil gracias", "te lo agradezco")
_VAR_DESPEDIDA = ("adios", "hasta luego", "hasta manana", "nos vemos", "chao", "chau")

_VAR_IDENTIDAD = ("quien eres", "quien sos", "que eres", "sabes quien eres", "como te llamas")
_VAR_PROPOSITO = ("para que sirves", "para que estas", "cual es tu proposito", "para que existes")

# "¿como puedo ayudarte?" es el usuario OFRECIENDO ayuda, no preguntando que sabe hacer AURORA.
# Contestar aqui el catalogo de capacidades seria responder a otra pregunta.
_VAR_OFRECIMIENTO = (
    "como puedo ayudarte",
    "en que puedo ayudarte",
    "como te puedo ayudar",
    "en que te puedo ayudar",
    "que necesitas de mi",
    "que necesitas",
)

# Mismas frases que ya atiende `_es_consulta_de_capacidades`, mas las que el uso real anadio. Se
# reclaman aqui SOLO para poder componerlas con un saludo: el cuerpo de la respuesta lo sigue dando
# `_describir_capacidades()`, la misma fuente, con el mismo texto.
_VAR_CAPACIDADES = (
    "que puedes hacer",
    "que podes hacer",
    "que sabes hacer",
    "que capacidades tienes",
    "cuales son tus capacidades",
    "en que me puedes ayudar",
    "con que me puedes ayudar",
    "como puedes ayudarme",
)

# SOLO las variantes que hoy FALLAN. Las que ya funcionan ("en que estas trabajando", "que tareas
# tienes", ...) se dejan deliberadamente fuera: las atiende `_es_consulta_de_tareas` inmediatamente
# despues y este incremento no tiene por que cambiar su respuesta.
_VAR_PENDIENTES = (
    "que tienes pendiente",
    "que tienes pendiente para hoy",
    "que tienes pendiente hoy",
    "que tienes para hoy",
    "que hay pendiente",
    "que tal vas",
    "como va todo",
    "que hay de nuevo",
)

# AMBIGÜEDAD REAL (distinta de multiplicidad): UNA frase que pertenece a dos dominios -lo que se de
# ti (Modelo de Usuario) y lo que he aprendido yo trabajando (Plan de Formacion)- donde responder uno
# implica ignorar el otro. El contrato exige preguntar. Sin "de mi" no hay ambiguedad y la superficie
# de formacion que ya existia responde igual que siempre.
_VAR_APRENDIDO_DE_MI = (
    "que has aprendido de mi",
    "que aprendiste de mi",
    "que has aprendido sobre mi",
    "que aprendiste sobre mi",
)

# (clase, nombre, variantes). El ORDEN de esta tabla no fija precedencia alguna: las variantes son
# disjuntas por construccion y la coincidencia es por segmento completo, de modo que un segmento
# activa como mucho una entrada. `test_las_variantes_de_conversacion_general_son_disjuntas` lo exige.
_TABLA_INTENCIONES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("modificadora", "saludo", tuple(_VAR_SALUDO)),
    ("modificadora", "cortesia", _VAR_CORTESIA),
    ("modificadora", "despedida", _VAR_DESPEDIDA),
    ("principal", "identidad", _VAR_IDENTIDAD),
    ("principal", "proposito", _VAR_PROPOSITO),
    ("principal", "ofrecimiento", _VAR_OFRECIMIENTO),
    ("principal", "capacidades", _VAR_CAPACIDADES),
    ("principal", "pendientes", _VAR_PENDIENTES),
    ("ambigua", "aprendido_de_mi", _VAR_APRENDIDO_DE_MI),
)

# Redaccion propia de AURORA, en primera persona (ajuste 2 del CEO). Determinista sigue significando
# "no lo decide el LLM", no "suena a maquina". INV-9: ninguna afirma una capacidad concreta -- las
# capacidades reales las enumera `_describir_capacidades()` leyendo el registro.
_RESPUESTA_IDENTIDAD = (
    "Soy AURORA. Trabajo contigo: guardo lo que me cuentas, sigo el estado de lo que llevamos "
    "entre manos y me ocupo de lo que me pidas dentro de las capacidades que tengo registradas."
)
_RESPUESTA_PROPOSITO = (
    "Estoy para acompañarte en el día a día: recordar lo que me cuentas, mantener a la vista en qué "
    "vamos y encargarme de lo que me pidas dentro de mis capacidades."
)
_RESPUESTA_OFRECIMIENTO = (
    "Me ayudas usándome: cuéntame en qué estás y pídeme lo que necesites. Cuanto más trabajemos "
    "juntos, mejor podré acompañarte."
)
_RESPUESTA_CORTESIA = "De nada."
_RESPUESTA_DESPEDIDA = "Hasta luego."
_OFRECIMIENTO_TRAS_SALUDO = "¿En qué puedo ayudarte hoy?"
_SIN_PENDIENTES = "Por ahora no tengo nada pendiente registrado."
_ACLARACION_APRENDIDO_DE_MI = (
    "Puedo entenderlo de dos formas: lo que sé de ti, o lo que he aprendido yo trabajando. ¿A cuál te refieres?"
)

# EL SALUDO NO LLEVA NOMBRE. RETIRADO POR AUDITORIA INDEPENDIENTE (2026-08-09), y conviene que quede
# escrito por que, porque el contrato lo pedia:
#
# El DP daba por hecho que "cuando el CEO diga como se llama, aparecera solo -y ese sera el primer
# dato real que capture el Modelo de Usuario-". La premisa es FALSA, medido `[EJEC]`: decir "me llamo
# Mauricio" deja el Modelo de Usuario con 0 entradas. Ningun detector de senales reconoce una
# declaracion de nombre.
#
# Con la premisa caida, la version que se implemento -leer "me llamo X" del texto libre de cualquier
# entrada semantica- solo era alcanzable por accidente, y fabricaba: con "No me llamo Pedro, me llamo
# Mauricio" saludaba "Buenos dias, Pedro" (la negacion del usuario perdia), y con "Mi nombre es de
# dominio publico" saludaba "Buenos dias, de". Es el mismo fallo de guarda de dominio que este fichero
# ya pago dos veces, y ademas dejaba codigo probado e INALCANZABLE en produccion (ALERTA-005).
#
# Saludar con el nombre exige antes una capacidad que no existe: que AURORA APRENDA como te llamas.
# Eso es producto nuevo y necesita su Decision Package. Hasta entonces, "Buenos dias" a secas -- que
# es literalmente lo que el propio contrato manda cuando el Modelo de Usuario no lo sabe.


#: El argumento de ruta de cada capacidad, leido de la especificacion del NUCLEO. No se escribe a
#: mano: `buscar_archivo` lo llama `patron` y las otras dos `ruta`, y una copia de ese detalle aqui
#: seria una lista paralela que se desincroniza en silencio.
_ARG_RUTA = {
    nombre: (_ESPECS.get(nombre, {}).get("args") or ("ruta",))[0]
    for nombre in ("listar_directorio", "leer_archivo", "buscar_archivo")
}


def _clasificar_hallazgo(res: dict) -> tuple[str, str]:
    """`(clase, detalle)` de UNA capacidad dentro de una revisión.

    Las clases se mantienen separadas a propósito —`limpio`, `incidencia`, `bloqueado`, `error`,
    `sin_datos`—: fundirlas en «bien / mal» perdería justo lo que el usuario necesita para saber si
    puede fiarse del informe. Un `bloqueado` **no es** un `limpio`, y tampoco es un fallo del
    sistema: es una barrera que funcionó."""
    estado = res.get("estado")
    if estado == "detenida":
        return ("bloqueado", str(res.get("motivo") or "un control lo impidió"))
    if estado == "error":
        return ("error", str(res.get("motivo") or "fallo"))
    if estado != "ejecutada":
        return ("error", f"estado desconocido {estado!r}")
    detalle = res.get("resultado")
    if not isinstance(detalle, dict):
        return ("sin_datos", "no devolvió nada que pueda leer")
    resumen = str(detalle.get("resumen") or "").strip()
    if detalle.get("ok") is False:
        return ("incidencia", resumen or "no quedó limpio")
    if detalle.get("status") == "duplicate":
        return ("sin_datos", "ya se había ejecutado; no hay resultado nuevo")
    return ("limpio", resumen)


def _redactar_revision(hallazgos) -> str:
    """El informe de una revisión compuesta, **sin redondear a favor**.

    La regla dura: *«AURA no puede decir "todo está bien" si el diagnóstico devuelve una
    incidencia»*. Aquí eso se implementa contando, no interpretando — el veredicto sale de cuántas
    capacidades quedaron en cada clase, así que no hay forma de que la síntesis sea más optimista
    que sus partes."""
    if not hallazgos:
        return "No tengo ninguna capacidad de revisión disponible ahora mismo."

    por_clase: dict[str, list[tuple[str, str]]] = {}
    for capacidad, res in hallazgos:
        clase, detalle = _clasificar_hallazgo(res)
        por_clase.setdefault(clase, []).append((capacidad, detalle))

    incidencias = por_clase.get("incidencia", [])
    bloqueados = por_clase.get("bloqueado", [])
    errores = por_clase.get("error", [])
    sin_datos = por_clase.get("sin_datos", [])
    limpios = por_clase.get("limpio", [])

    lineas: list[str] = []
    if incidencias:
        lineas.append(f"He revisado {len(hallazgos)} cosa(s) y **hay {len(incidencias)} con incidencia**:")
    elif bloqueados or errores or sin_datos:
        # `sin_datos` cuenta aquí y no entre los limpios. Lo destapó una prueba: con solo un
        # `duplicate` —el adaptador NO volvió a ejecutar— la revisión decía «está todo limpio»,
        # que es afirmar una comprobación que **no ocurrió**. No mirar no es mirar y no encontrar
        # nada.
        lineas.append(f"He revisado {len(hallazgos)} cosa(s). No encontré incidencias, pero **no pude mirarlo todo**:")
    else:
        lineas.append(f"He revisado {len(hallazgos)} cosa(s) y **está todo limpio**:")

    for capacidad, detalle in incidencias:
        lineas.append(f"• {capacidad}: {_acotar(detalle, 300)}")
    for capacidad, detalle in bloqueados:
        lineas.append(f"• {capacidad}: no lo revisé — {_acotar(detalle, 200)}")
    for capacidad, detalle in errores:
        lineas.append(f"• {capacidad}: falló al revisarlo — {_acotar(detalle, 200)}")
    for capacidad, detalle in sin_datos:
        lineas.append(f"• {capacidad}: sin datos — {_acotar(detalle, 200)}")
    for capacidad, detalle in limpios:
        lineas.append(f"• {capacidad}: sin novedad{(' — ' + _acotar(detalle, 200)) if detalle else ''}")
    return "\n".join(lineas)


_AVISO_SIN_REGISTRO = "No he podido guardar el registro de esta acción: tras un reinicio no la recordaré."


def describir_desenlace(
    capacidad: str,
    desenlace: str,
    *,
    motivo: object = None,
    resumen: str | None = None,
    detalle_hogar: dict | None = None,
    nombres: dict[str, str] | None = None,
    modo: str = "vivo",
    elementos: int | None = None,
    estado: object = None,
    ilegible: bool = False,
) -> str | None:
    """LA redaccion del desenlace de una orden: una sola funcion, tres modos, ninguna segunda implementacion
    (punto D, requisito 10; leccion de ALERTA-005).

    - `vivo`: el turno que acaba de ocurrir. Presente de verificacion («Home Assistant ve…»).
    - `registro`: lo que cuenta el registro persistido tras un reinicio. Pasado: lo que CONSTABA entonces, sin afirmar
      nada que no se haya vuelto a comprobar («registro local, sin verificar ahora»).
    - `prompt`: lo unico que de un resultado con contenido del usuario reentra en el prompt (metadato, sin contenido).

    Devuelve `None` solo cuando el desenlace es `ejecutada` y el texto depende del contenido concreto del adaptador
    (entradas, ficheros) que el modo `vivo` redacta quien lo tiene."""
    registro = modo == "registro"
    if modo in ("prompt", "registro") and capacidad in CAPACIDADES_QUE_DEVUELVEN_CONTENIDO and desenlace == "ejecutada":
        cuantas = f", {elementos} línea(s)" if elementos is not None else ""
        if modo == "prompt":
            return f"Ejecuté «{capacidad}»: leí un archivo{cuantas}. Su contenido no se repite aquí."
        return f"Ejecuté «{capacidad}»: leí un archivo{cuantas}; no conservo su contenido."
    if desenlace == "duplicada":
        # Idempotencia del adaptador: NO se volvió a ejecutar. Contarlo como una ejecución fresca
        # sería afirmar un trabajo que no se hizo.
        return (
            f"«{capacidad}» ya se había ejecutado con esos mismos datos, así que no lo repetí. "
            f"No tengo resultado nuevo que darte."
        )
    if capacidad in _ACCION_DE_HOGAR and desenlace in ("detenida", "error"):
        # Medido `[EJEC]` contra el HA real (2026-10-22): «Intenté ejecutar «subir_volumen» y no pude: el adaptador
        # rechazo la operacion: …». El motivo era cierto; la forma, técnica. En casa se dice QUÉ no se hizo y por qué.
        motivo = str(motivo or "un control lo impidió").removeprefix("el adaptador rechazo la operacion: ")
        return f"No he podido {_ACCION_DE_HOGAR[capacidad]}: {_con_nombres_humanos(motivo, nombres)}."
    if desenlace == "detenida":
        texto = _con_nombres_humanos(str(motivo or "un control lo impidió"), nombres)
        return f"No he ejecutado «{capacidad}»: {texto}."
    if desenlace == "error":
        return f"Intenté ejecutar «{capacidad}» y no pude: {_con_nombres_humanos(str(motivo or 'fallo'), nombres)}."
    if desenlace == "no_limpia":
        return f"Ejecuté «{capacidad}». **No está limpio**: {_acotar(resumen or 'no ha salido bien')}"
    if desenlace == "ejecutada" and detalle_hogar is not None:
        if capacidad in _CAPACIDADES_DE_HOGAR:
            return _redactar_efecto_de_hogar(capacidad, detalle_hogar, nombres, registro)
        if capacidad in _CAPACIDADES_DE_VOLUMEN:
            return _redactar_efecto_de_volumen(capacidad, detalle_hogar, nombres, registro)
    if desenlace == "desconocido":
        if ilegible:
            return f"Ejecuté «{capacidad}», pero no me devolvió un resultado que pueda leer."
        como = f" ({estado!r})" if estado is not None else ""
        return f"Ejecuté «{capacidad}», pero no sé interpretar cómo terminó{como}."
    if registro:  # ejecutada sin nada mas que contar: lo unico que el registro conserva es cuantas entradas hubo
        if elementos is not None:
            return f"Ejecuté «{capacidad}»: {elementos} entrada(s)."
        return f"Ejecuté «{capacidad}» y terminó."
    return None


def _redactar_resultado_de_orden(capacidad: str, res: dict, nombres: dict[str, str] | None = None) -> str:
    """Cuenta lo que el motor DEVOLVIÓ, no lo que se esperaba que hiciera.

    **Esto nació de un bug propio, encontrado ejecutando** `[EJEC]`. La primera versión usaba claves
    que el motor no devuelve (`status`, `reason`), así que caía siempre al caso final y contestaba
    *«Ejecuté «auditar_garantias» y terminó correctamente»* mientras el adaptador devolvía
    `ok=False` y *«5 garantías declaradas que NO protegen nada»*. Es «declarado ≠ real» en la
    superficie que el usuario lee y se cree — la versión más cara del patrón.

    Contrato real de `MotorAutomatizacion.ejecutar`, leído del código y no supuesto:
      `{"accion", "estado": "ejecutada", "plan", "resultado", "origen"}`
      `{"accion", "estado": "detenida"|"error", "motivo", "origen"}`

    `detenida` y `error` se distinguen a propósito, porque el propio motor los distingue: lo primero
    es **el gobierno funcionando** —permisos, dry-run, kill switch— y lo segundo es un fallo. Decirle
    al usuario «falló» cuando en realidad se le negó el permiso sería confundir una barrera con una
    avería."""
    # UNA clasificacion del desenlace, la misma que usa el registro persistido (`resultado_accion.desenlace_de`).
    desenlace = resultado_accion.desenlace_de(res)
    if not isinstance(res, dict):
        return describir_desenlace(capacidad, desenlace, ilegible=True) or ""
    if desenlace in ("detenida", "error"):
        return describir_desenlace(capacidad, desenlace, motivo=res.get("motivo"), nombres=nombres) or ""
    if res.get("estado") != "ejecutada":
        return describir_desenlace(capacidad, desenlace, estado=res.get("estado")) or ""

    detalle = res.get("resultado")
    if not isinstance(detalle, dict):
        return f"Ejecuté «{capacidad}» y terminó."

    # `ok` es el veredicto del ADAPTADOR sobre su propio trabajo, y manda sobre el hecho de que la
    # ejecución llegara a término: una auditoría que corre entera y encuentra cinco garantías rotas
    # se ejecutó **correctamente** y su resultado es **malo**. Son dos cosas distintas y el usuario
    # necesita la segunda.
    resumen = str(detalle.get("resumen") or "").strip()
    if desenlace == "no_limpia":
        return describir_desenlace(capacidad, desenlace, resumen=resumen) or ""
    if desenlace == "duplicada":
        return describir_desenlace(capacidad, desenlace) or ""
    if resumen:
        return f"Ejecuté «{capacidad}». {_acotar(resumen)}"

    # **Los adaptadores NO comparten contrato de salida**, y el redactor tiene que vivir con eso
    # sin mentir. Medido `[EJEC]`: `qa`, `auditor` y `diagnostico` devuelven `{ok, resumen}`;
    # `computador` devuelve `{status, entradas}` o `{status, contenido}`. Leer solo el primer
    # contrato hacía que un listado real se contara como «terminó correctamente» **sin enseñar
    # nada** — cierto, pero inútil, que es la otra forma de que una respuesta no sirva.
    estado_adaptador = str(detalle.get("status") or "").strip()
    del_hogar = describir_desenlace(capacidad, "ejecutada", detalle_hogar=detalle, nombres=nombres)
    if del_hogar is not None:
        return del_hogar
    if estado_adaptador and estado_adaptador != "ok":
        return f"Ejecuté «{capacidad}» y devolvió el estado {estado_adaptador!r}."

    entradas = detalle.get("entradas")
    if isinstance(entradas, (list, tuple)):
        if not entradas:
            return f"Ejecuté «{capacidad}»: está vacío."
        cuerpo = ", ".join(str(e) for e in entradas)
        return f"Ejecuté «{capacidad}». {len(entradas)} entrada(s): {_acotar(cuerpo)}"

    contenido = detalle.get("contenido")
    if contenido is not None:
        # **Un fichero binario no se vuelca.** Encontrado auditando `[EJEC]`: un contenido en bytes
        # salía como `b'\x00\x01…'` — ilegible, y con caracteres de control que pueden desordenar
        # la terminal del usuario. Decir qué es vale más que enseñar lo que no se puede leer.
        if isinstance(contenido, (bytes, bytearray)) or _tiene_control(str(contenido)):
            return (
                f"Ejecuté «{capacidad}», pero el fichero no parece texto legible "
                f"({len(contenido)} bytes). No te lo muestro para no ensuciar la pantalla."
            )
        texto = str(contenido)
        if not texto.strip():
            return f"Ejecuté «{capacidad}»: el fichero está vacío."
        return f"Ejecuté «{capacidad}». Esto es lo que dice:\n{_acotar(texto)}"

    return f"Ejecuté «{capacidad}» y terminó correctamente."


_CAPACIDADES_DE_HOGAR = {"encender_dispositivo": ("encendí", "encender"), "apagar_dispositivo": ("apagué", "apagar")}

#: Lo que AURA dice que NO pudo hacer en casa, sin el nombre técnico de la capacidad.
_ACCION_DE_HOGAR = {
    "encender_dispositivo": "encenderlo",
    "apagar_dispositivo": "apagarlo",
    "subir_volumen": "subir el volumen",
    "bajar_volumen": "bajar el volumen",
    "silenciar": "silenciar",
    "quitar_silencio": "quitar el silencio",
}


def _con_nombres_humanos(texto: str, nombres: dict[str, str] | None) -> str:
    """Sustituye en un texto cualquier identificador técnico con nombre humano por ese nombre: lo que la
    persona lee nunca lleva un entity_id (CEO 2026-10-04). La identidad interna no cambia: esto solo redacta."""
    for entidad, nombre in (nombres or {}).items():
        texto = texto.replace(f"«{entidad}»", nombre).replace(entidad, nombre)
    return texto


_ESTADOS_HUMANOS = {
    "on": "encendida",
    "off": "apagada",
    "playing": "encendida (reproduciendo)",
    "paused": "encendida (en pausa)",
    "idle": "encendida (en reposo)",
    "standby": "apagada (en espera)",
    "unavailable": "no disponible",
    "unknown": "en estado desconocido",
    "?": "en estado desconocido",
}


def _estado_humano(valor: object) -> str:
    """El estado que Home Assistant reporta, en español; si no se conoce, acotado y sin caracteres de control."""
    return _ESTADOS_HUMANOS.get(str(valor)) or f"«{hogar.texto_seguro(valor)}»"


_COLA_YA_IGUAL = {False: " y la sigue viendo así; no ha cambiado nada.", True: "; no cambió nada."}
_COLA_YA_DISTINTO = {
    False: " y ahora la ve {ahora}; no ha cambiado nada.",
    True: " y después la veía {ahora}; no cambió nada.",
}


def _sin_efecto_de_hogar(infinitivo: str, objetivo: str, detalle: dict, registro: bool = False) -> str:
    """Orden enviada sin estado pedido: dice qué VE Home Assistant, nunca qué ocurrió físicamente."""
    if detalle.get("evidencia") == "estado_asumido_por_ha":
        # SmartIR y similares: HA publica un estado optimista (`assumed_state`) porque no lee el aparato.
        como = "encendida" if detalle.get("estado_despues") in hogar.ESTADOS_ENCENDIDA else "apagada"
        return (
            f"Envié la orden de {infinitivo} {objetivo}. Home Assistant la da por {como}, pero es un estado "
            "asumido (no lee el aparato); no puedo confirmarlo."
        )
    antes, despues = detalle.get("estado_antes"), detalle.get("estado_despues")
    ahora = _estado_humano(despues)
    # Modo registro: pasado, sin presente de verificacion (`registro` elige la cola de la frase).
    if detalle.get("ya_en_estado"):
        if antes == despues:
            return f"Home Assistant ya veía {objetivo} {ahora}{_COLA_YA_IGUAL[registro]}"
        return f"Home Assistant ya veía {objetivo} {_estado_humano(antes)}{_COLA_YA_DISTINTO[registro].format(ahora=ahora)}"
    cabecera = f"Envié la orden de {infinitivo} {objetivo}, pero"
    if detalle.get("evidencia") == "ninguna" or despues in (None, "?"):
        return f"{cabecera} no pude leer el estado en Home Assistant después. No lo doy por hecho."
    if antes == despues:
        verbo = "seguía viendo" if registro else "sigue viendo"
        return f"{cabecera} no cambió: Home Assistant {verbo} {objetivo} {ahora}. No lo doy por hecho."
    verbo = "veía" if registro else "ve"
    return f"{cabecera} Home Assistant {verbo} {objetivo} {ahora}, no el estado pedido. No lo doy por hecho."


def _redactar_efecto_de_hogar(
    capacidad: str, detalle: dict, nombres: dict[str, str] | None = None, registro: bool = False
) -> str:
    """Solo se dice «hecho» si el adaptador OBSERVÓ el estado pedido releyendo Home Assistant.

    Casos, y ninguno puede contarse como otro: verificado (HA ve el estado pedido tras la orden), sin efecto o
    «ya estaba» (HA no vio ningún cambio) y sin confirmación posible —el doble del hogar, que contesta `ok` sin
    tocar nada (deuda D-ADP-1)—. La evidencia es lo que HA reporta, nunca un efecto físico confirmado.

    Si la entidad tiene nombre humano (`nombres`, CEO 2026-10-04) se habla de «la TV de la sala», breve y sin
    identificadores técnicos; si no, se dice como siempre. El nombre llega aquí, nunca al adaptador."""
    _hecho, infinitivo = _CAPACIDADES_DE_HOGAR[capacidad]
    dispositivo = detalle.get("device", "el dispositivo")
    humano = (nombres or {}).get(dispositivo)
    objetivo = humano if humano is not None else f"«{hogar.texto_seguro(dispositivo)}»"
    if detalle.get("verificado") is True and detalle.get("evidencia") != "estado_asumido_por_ha":
        # Nivel de evidencia: lo que HOME ASSISTANT reporta tras la orden, no un efecto físico confirmado.
        if registro:  # modo registro: lo que constaba entonces, sin afirmar nada ahora
            estado = _estado_humano(detalle.get("estado_despues"))
            if humano is not None:
                return f"Constaba que Home Assistant veía {humano} {estado} tras la orden (registro local, sin verificar ahora)."
            return (
                f"Constaba que Home Assistant veía {objetivo} en «{hogar.texto_seguro(detalle.get('estado_despues'))}» "
                f"(antes «{hogar.texto_seguro(detalle.get('estado_antes'))}») tras la orden (registro local, sin verificar ahora)."
            )
        if humano is not None:
            return f"Listo: Home Assistant ve {humano} {_estado_humano(detalle.get('estado_despues'))}."
        return (
            f"Listo: Home Assistant ve {objetivo} en «{hogar.texto_seguro(detalle.get('estado_despues'))}» "
            f"(antes «{hogar.texto_seguro(detalle.get('estado_antes'))}»)."
        )
    if detalle.get("status") == "sin_efecto":
        return _sin_efecto_de_hogar(infinitivo, objetivo, detalle, registro)
    return (
        f"Envié la orden de {infinitivo} {objetivo}, pero el hogar está en modo simulado: "
        "no hay ningún dispositivo real conectado y no puedo confirmar que haya pasado nada."
    )


_CAPACIDADES_DE_VOLUMEN = {
    "subir_volumen": ("subí el volumen de", "subir el volumen de"),
    "bajar_volumen": ("bajé el volumen de", "bajar el volumen de"),
    "silenciar": ("silencié", "silenciar"),
    "quitar_silencio": ("le quité el silencio a", "quitar el silencio a"),
}


def _valor_de_volumen(atributo: object, valor: object) -> str:
    if atributo == "is_volume_muted":
        return "silenciada" if valor else "con sonido"
    return f"en {round(float(valor) * 100)}" if isinstance(valor, (int, float)) else f"en «{valor}»"


def _redactar_efecto_de_volumen(
    capacidad: str, detalle: dict, nombres: dict[str, str] | None = None, registro: bool = False
) -> str:
    """Volumen y silencio con el mismo criterio que encender/apagar: «hecho» solo si el adaptador RELEYÓ el atributo y
    cambió en el sentido pedido (acta 2026-10-22 §4). El volumen se dice como HA lo da (0-1) en escala de 0 a 100."""
    hecho, infinitivo = _CAPACIDADES_DE_VOLUMEN[capacidad]
    dispositivo = detalle.get("device", "el dispositivo")
    objetivo = (nombres or {}).get(dispositivo) or f"«{dispositivo}»"
    atributo = detalle.get("atributo")
    if detalle.get("evidencia") == "estado_asumido_por_ha":
        return (
            f"Envié la orden de {infinitivo} {objetivo}. Home Assistant da el cambio por hecho, pero es un estado "
            "asumido (no lee el aparato); no puedo confirmarlo."
        )
    if detalle.get("ya_en_estado"):
        # Silenciar lo ya silenciado: HA ya lo veía así y lo sigue viendo; AURA no cambió nada y no dice que lo hizo.
        ya = _valor_de_volumen(atributo, detalle.get("valor_despues"))
        if registro:
            return f"Home Assistant ya veía {objetivo} {ya}; no cambié nada."
        return f"Home Assistant ya veía {objetivo} {ya} y la sigue viendo así; no he cambiado nada."
    if detalle.get("verificado") is True:
        if atributo == "volume_level":
            antes = _valor_de_volumen(atributo, detalle.get("valor_antes")).removeprefix("en ")
            despues = _valor_de_volumen(atributo, detalle.get("valor_despues")).removeprefix("en ")
            if registro:
                return f"Se ordenó {infinitivo} {objetivo} (de {antes} a {despues}); constaba comprobado en Home Assistant (registro local)."
            return f"Listo: {hecho} {objetivo} (de {antes} a {despues}); lo he comprobado en Home Assistant."
        if registro:
            return f"Se ordenó {infinitivo} {objetivo}; constaba comprobado en Home Assistant (registro local)."
        return f"Listo: {hecho} {objetivo}; lo he comprobado en Home Assistant."
    if detalle.get("status") == "sin_efecto":
        valor_despues = detalle.get("valor_despues")
        if not isinstance(valor_despues, (bool, int, float)):
            que = "el silencio" if atributo == "is_volume_muted" else "el volumen"
            return f"Envié la orden de {infinitivo} {objetivo}, pero después no pude leer {que}. No lo doy por hecho."
        sigue = _valor_de_volumen(atributo, valor_despues)
        return f"Envié la orden de {infinitivo} {objetivo}, pero no cambió: sigue {sigue}. No lo doy por hecho."
    return (
        f"Envié la orden de {infinitivo} {objetivo}, pero el hogar está en modo simulado: "
        "no hay ningún dispositivo real conectado y no puedo confirmar que haya pasado nada."
    )


def _tiene_control(texto: str) -> bool:
    """Caracteres de control que no son separadores normales. Un fichero con ellos no es texto que
    quepa enseñar en una conversación."""
    return any(ord(c) < 32 and c not in "\t\n\r" for c in texto[:4000])


def _acotar(texto: str, tope: int = 900) -> str:
    """La salida de una herramienta puede ser enorme; el turno tiene que seguir siendo legible."""
    limpio = " ".join(str(texto).split())
    return limpio if len(limpio) <= tope else limpio[:tope] + " […]"


def _sin_vocativo(segmento: str) -> str:
    """Quita "aurora"/"aura" al principio o al final. Asi "buenos dias Aurora" y "buenos dias" son la
    misma entrada de la tabla, sin duplicar ninguna variante."""
    palabras = segmento.split()
    while palabras and palabras[0] in _VOCATIVOS:
        palabras.pop(0)
    while palabras and palabras[-1] in _VOCATIVOS:
        palabras.pop()
    return " ".join(palabras)


def _intencion_de_segmento(segmento: str) -> tuple[str, str, str] | None:
    """(clase, nombre, variante) si el segmento COMPLETO es una variante conocida; None si no."""
    for clase, nombre, variantes in _TABLA_INTENCIONES:
        if segmento in variantes:
            return (clase, nombre, segmento)
    return None


def _partir_en_partes(texto: str) -> list[str]:
    """Segmentos normalizados, sin vocativo y sin vacios."""
    partes = []
    for bruto in _SEPARADORES_DE_SEGMENTO.split(_normalizar(texto)):
        segmento = _sin_vocativo(" ".join(bruto.split()))
        if segmento:
            partes.append(segmento)
    return partes


def _separar_saludo_inicial(parte: str) -> tuple[str, str] | None:
    """(variante de saludo, resto) si la parte EMPIEZA por un saludo y queda algo detras; None si no.

    Existe por un defecto medido en auditoria: la entrada llega por transcripcion de voz, y la
    puntuacion es justo lo que menos fiable produce el dictado. Sin esto, "buenos dias Aurora que
    tienes pendiente para hoy" -la frase insignia del contrato, sin la coma- no se reconocia.

    La variante mas LARGA gana ("buenas tardes" antes que "buenas"): con el orden inverso, "buenas
    tardes ..." se partiria como "buenas" + "tardes ...". El resto debe casar ENTERO con otra
    variante, asi que esto no reintroduce la coincidencia por subcadena: "hola que tal la fiesta de
    ayer" sigue sin reclamarse.
    """
    for variante in sorted(_VAR_SALUDO, key=len, reverse=True):
        if parte.startswith(variante + " "):
            resto = _sin_vocativo(parte[len(variante) :].strip())
            if resto:
                return (variante, resto)
    return None


def _sin_repeticiones(secuencia: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """La misma intencion repetida en un turno se responde UNA vez, conservando su primera posicion.

    "hola, Aurora, que tal" contiene dos saludos y "¿que puedes hacer? ¿que puedes hacer?" dos veces
    la misma consulta: sin esto, AURORA contestaba "Hola. Hola." y volcaba el catalogo por duplicado.
    """
    vistas = set()
    unicas = []
    for clase, nombre, variante in secuencia:
        if nombre in vistas:
            continue
        vistas.add(nombre)
        unicas.append((clase, nombre, variante))
    return unicas


def _secuencia_de_intenciones(texto: str) -> list[tuple[str, str, str]] | None:
    """La secuencia de intenciones del turno, o None si ALGUNA parte no se reconoce.

    "None ante lo desconocido" es la propiedad que hace inofensivo este detector: basta con que el
    turno contenga algo fuera de la lista para que siga exactamente el camino de hoy. Es lo que
    mantiene intactas las 24 negativas de ADR-0014 sin tocar su puerta.
    """
    partes = _partir_en_partes(texto)
    if not partes:
        return None
    secuencia: list[tuple[str, str, str]] = []
    for parte in partes:
        directa = _intencion_de_segmento(parte)
        if directa is not None:
            secuencia.append(directa)
            continue
        # Segunda pasada: un saludo pegado a su consulta SIN separador ("buenos dias Aurora que
        # tienes pendiente para hoy"). El resto tiene que casar entero.
        pegado = _separar_saludo_inicial(parte)
        if pegado is not None:
            variante, resto = pegado
            del_resto = _intencion_de_segmento(resto)
            if del_resto is not None:
                secuencia.append(("modificadora", "saludo", variante))
                secuencia.append(del_resto)
                continue
        # Tercera pasada: "¿que puedes hacer y que tienes pendiente?" son DOS principales unidas por
        # "y". Solo se intenta si la parte entera no se reconocia, para no trocear frases legitimas.
        trozos = [_sin_vocativo(t.strip()) for t in parte.split(" y ")]
        if len(trozos) < 2:
            return None
        encontradas = [_intencion_de_segmento(t) for t in trozos]
        if any(e is None for e in encontradas):
            return None
        secuencia.extend(e for e in encontradas if e is not None)
    return secuencia or None


# Ubicacion FIJA del Plan de Formacion: gobierno del proyecto, no dato de usuario, vive junto a
# CLAUDE.md y CHECKLIST-CONTINUIDAD.md. Desde este fichero (aura_skeleton/core/orchestrator.py) son
# tres niveles hacia arriba: core -> aura_skeleton -> walking-skeleton -> raiz del repo. Si el
# repositorio se reubica sin ese vecino, la respuesta correcta es declarar la ausencia (INV-9), no
# fabricar un resumen de lo que AURORA "deberia" haber aprendido.
_NOMBRE_PLAN_FORMACION = "PLAN-DE-FORMACION-AURORA.md"


def _ruta_plan_formacion() -> Path:
    return Path(__file__).resolve().parents[3] / _NOMBRE_PLAN_FORMACION


def _extraer_seccion(md: str, encabezado_contiene: str) -> str | None:
    """El bloque bajo el primer encabezado de nivel 2 (`## `) que contiene `encabezado_contiene`,
    hasta el siguiente encabezado de nivel 2 o el final del documento. None si no aparece."""
    lineas = md.splitlines()
    inicio = next(
        (i for i, linea in enumerate(lineas) if linea.startswith("## ") and encabezado_contiene in linea), None
    )
    if inicio is None:
        return None
    fin = next((i for i in range(inicio + 1, len(lineas)) if lineas[i].startswith("## ")), len(lineas))
    return "\n".join(lineas[inicio:fin]).strip()


def _resumen_formacion() -> str:
    """Responde "¿que aprendiste?" leyendo el Plan de Formacion REAL, no un resumen inventado.

    INV-9: si el fichero no esta donde debe estar, o no tiene seccion de aprendidas, se declara la
    ausencia -nunca se simula contenido-.

    Defecto menor corregido (auditoria independiente): `read_text(encoding="utf-8")` no solo puede
    fallar con `OSError` (fichero ausente/sin permiso) sino con `UnicodeDecodeError` (subclase de
    `ValueError`) si el fichero existe pero su codificacion no es UTF-8 valida. Sin capturarlo, el
    turno entero revienta: ni declara ausencia ni fabrica, explota -- el peor de los tres resultados.
    """
    try:
        md = _ruta_plan_formacion().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "No encuentro el Plan de Formación en el repositorio; no puedo declarar qué he aprendido."
    seccion = _extraer_seccion(md, "Aprendidas")
    if seccion is None:
        return "El Plan de Formación existe pero no tiene una sección de capacidades aprendidas."
    return seccion


# ---------------------------------------------- FRONTERA COGNITIVA · ESTATUS POR RUTA (D-FC-1..8) --
#
# El estatus lo decide `estatus.asignar` en `_finalizar_turno`, y SOLO alli. Las rutas del Core se
# limitan a DECLARAR cual es el suyo (D-FC-1 = A); una ruta que no declara nada es HECHO. Lo que viene
# de un proveedor es PROPUESTA pida lo que pida la ruta: esa parte no la decide este fichero.

#: D-FC-7/f: un router sin proveedor utilizable cierra el turno por el Core. Antes el turno quedaba sin
#: `_done` y `wait` expiraba: un fallo silencioso con apariencia de cuelgue.
_ABSTENCION_SIN_PROVEEDOR = "Mi modelo local no está disponible ahora mismo; inténtalo de nuevo en unos minutos."

#: DR-3 (CEO, 2026-09-15): aviso honesto cuando el modelo SI estaba disponible pero el turno alcanzo un
#: limite. Ninguno de los dos presenta lo que el modelo llevara escrito: una respuesta a medias no se
#: entrega como si hubiera terminado. Claves = el atributo `limite` que declara `LimiteDelProveedor`.
_ABSTENCION_POR_LIMITE = {
    "tiempo": (
        "No he podido completar la respuesta dentro del tiempo límite. "
        "No te doy una respuesta a medias; puedes volver a preguntármelo."
    ),
    "longitud": (
        "Mi respuesta se alargó más de lo que puedo generar de una vez y quedó incompleta. "
        "No te la doy a medias; puedes pedírmela más concreta."
    ),
}

#: MISIÓN VOZ (CEO, 2026-09-15): la transcripción falló, así que NO SE SABE qué dijo el usuario. La única
#: respuesta honesta es decirlo: adivinar seria inventar un turno que nadie pronuncio, y un adaptador
#: periferico no puede poner palabras en boca del usuario (frontera de autoridad, §6 de la mision).
_STT_NO_DISPONIBLE = (
    "No pude transcribir el audio, así que no voy a adivinar qué dijiste. Puedes repetirlo o escribírmelo."
)

#: D-FC-6 = A: acuse por voz antes de esperar al modelo. Lo redacta el Core: no afirma nada del mundo.
_ACUSE_CONSULTA_MODELO = "Déjame consultarlo con mi modelo local; puede tardar un poco."

#: Acuse del Core a una declaracion de hecho propio («me llamo Mauricio»). Deliberadamente NO dice «lo
#: he guardado» ni «lo recordare»: la captura corre despues, puede estar bloqueada por la parada, y la
#: restriccion 2 del gate del CEO prohibe que su resultado influya en lo que AURA contesta.
_ACUSE_DECLARACION = "Entendido."

#: D-FC-2 = B: nombre legible de cada dominio sensible que `intencion.dominio_sensible` puede devolver.
#: Un dominio nuevo sin entrada aqui cae en el texto generico de `_abstencion_sensible`: la abstencion
#: se mantiene aunque la redaccion sea menos precisa (ante la duda, no se transmite).
_TEMA_SENSIBLE = {
    "salud": "salud",
    "derecho": "temas legales",
    "finanzas": "finanzas",
    "personas_reales": "personas reales",
    "religion": "religión",
}


def _abstencion_sensible(dominio: str) -> str:
    tema = _TEMA_SENSIBLE.get(dominio, "este tema")
    return (
        f"Sobre {tema} no te doy respuestas generadas por mi modelo local: no puedo verificarlas y podrían ser falsas."
    )


#: Textos con los que una superficie del Core declara que NO tiene el dato (ADR-0014). **Como distingue
#: la ruta su ausencia, y por que asi:** las superficies (`_atender_modelo_usuario`, `_describir_*`)
#: devuelven `str`, y pruebas existentes las llaman directamente esperando `str`. Cambiarles la firma a
#: `(texto, estatus)` tocaria ~20 retornos y esas pruebas para decir lo mismo. Estos textos son
#: CONSTANTES DEL CORE -no del modelo-, asi que la igualdad exacta es determinista y no interpreta nada.
#: El riesgo es el de siempre, «declarado != real»: que alguien reescriba un retorno y aqui quede el
#: antiguo. `test_estatus_epistemico` lo cierra por ejecucion: cada literal debe seguir apareciendo en el
#: codigo que lo produce, y las ausencias reales de cada superficie deben salir AUSENCIA.
#: DR-1: respuesta de la evocacion generica cuando el Core no conserva ningun hecho DECLARADO y vigente.
#: Es una ausencia sobre lo que el usuario le DIJO, no sobre toda la memoria: no afirma «no se nada».
_SIN_HECHOS_DECLARADOS = "No me consta que me hayas dicho nada que siga dando por cierto."

_AUSENCIAS_DEL_CORE = frozenset(
    {
        *(ausencia for _, _, _, ausencia in _CONSULTAS_DE_HECHO),
        _SIN_HECHOS_DECLARADOS,
        describir_conocimiento([]),
        "Todavía no me has dicho qué prefieres.",
        "Ahora mismo no estoy afirmando nada sobre ti.",
        "No he encontrado eso para olvidarlo.",
        "No he encontrado eso para corregirlo.",
        "No tengo ningún objetivo activo registrado en el estado operativo ahora mismo.",
        "No tengo ningún objetivo activo, así que no hay nada bloqueado ahora mismo.",
        "No me consta ninguna decisión pendiente en mi estado actual.",
        "No me consta el estado de mi cola de trabajo.",
        "No me consta mi historial de trabajos.",
        "No tengo registro de mi propio ciclo de trabajo ahora mismo.",
        "No me consta ninguna tarea ejecutada en mi historial.",
        "No encuentro el Plan de Formación en el repositorio; no puedo declarar qué he aprendido.",
        "El Plan de Formación existe pero no tiene una sección de capacidades aprendidas.",
        _SIN_PENDIENTES,
    }
)

#: Preguntas con las que el Core pide precision en vez de adivinar (D-FC-4 = A).
_ACLARACIONES_DEL_CORE = frozenset({_DESAMBIGUAR, _ACLARACION_APRENDIDO_DE_MI})


def _estatus_del_core(respuesta: str) -> Estatus:
    """Estatus que DECLARA una superficie del Core segun su propio texto. No es `asignar`: no ve el
    proveedor y no puede producir PROPUESTA. Solo traduce las constantes de arriba; lo demas, HECHO."""
    if respuesta in _AUSENCIAS_DEL_CORE:
        return Estatus.AUSENCIA
    if respuesta in _ACLARACIONES_DEL_CORE:
        return Estatus.ACLARACION
    return Estatus.HECHO


NO_TE_OI = "No te he oído. Llámame otra vez («Oye Aurora») y dímelo."


class Orchestrator:
    """Coordina el turno conversacional. NO ejecuta acciones por su cuenta (M2.5, ALERTA-005).

    El sexto parametro admite un adaptador suelto (uso historico de M1) o un `RegistroAdaptadores`
    con varios. En ambos casos la ejecucion se delega en el `MotorAutomatizacion`, que es el unico
    camino de ejecucion del sistema: el orquestador no tiene acceso directo a ningun adaptador.
    """

    def __init__(
        self,
        bus,
        memory,
        router,
        permissions,
        voice,
        adaptadores,
        motor=None,
        contexto=None,
        notificaciones=None,
        modelo_usuario=None,
        automatizaciones=None,
        estado_operativo=None,
        estado_autonomo=None,
        decisiones=None,
        reconocer_declaracion=None,
        vigia_nodos=None,
    ):
        self.bus, self.memory, self.router = bus, memory, router
        # Avisos de NODO-01 (acta 2026-10-18, R1). PUERTO opcional `(ahora) -> (RegistroNodos, bool) | None`;
        # el estado anterior vive SOLO en memoria de la sesion (no se persiste nada). No es tiempo real:
        # se evalua al abrir y al inicio de cada turno.
        self.vigia_nodos = vigia_nodos
        self._estado_nodos: dict[str, str] | None = None
        self.perm, self.voice = permissions, voice
        self.notificaciones = notificaciones  # Centro de Notificaciones (MVP): registra lo que AURA hace
        self.modelo_usuario = modelo_usuario  # Soberania (MVP): ver/entender/corregir/olvidar lo que sabe de ti
        self.automatizaciones = automatizaciones  # AlmacenReglas (MVP cap. 5): reglas del usuario, persistentes
        # Estado Operativo del SO Interno (M3 entry): fuente de "que tareas tienes" / "por que estas
        # bloqueada" en la conversacion. OPCIONAL: sin el, esas preguntas siguen el flujo normal
        # (memoria/LLM), igual que notificaciones/modelo_usuario/automatizaciones cuando no se conectan.
        self.estado_operativo = estado_operativo
        # Ciclo autonomo de AURORA (CEO, 2026-09-01). OPCIONAL, como `estado_operativo`: es un
        # puerto, no un import. Sin el, "¿en que estas trabajando?" responde exactamente lo que
        # respondia antes de este incremento — el producto tiene que poder instalarse sin el plano
        # de desarrollo.
        self.estado_autonomo = estado_autonomo
        # Buzon de decisiones (CEO, 2026-09-01). OPCIONAL, como los dos anteriores. Es el MISMO
        # almacen que usa el confirmador diferido y que `reabrir_aprobadas` lee al despertar: la
        # conversacion no abre una segunda via de autorizacion, se asoma a la que ya existe.
        self.decisiones = decisiones
        self._foco_modelo: dict[str, dict] = {}  # a que afirmacion se refiere "eso" por usuario
        # M3.2a opción A: export del modelo PENDIENTE DE CONFIRMAR, por usuario. Vive UN turno: el
        # siguiente turno lo consume (si confirma) o lo descarta (cualquier otra cosa). La garantía de
        # privacidad es esta confirmación, no la detección de texto (CLAUDE.md §C: consentimiento, no lista).
        self._export_pendiente: set[str] = set()
        # M3.0 — captura de senales. OPCIONAL y PASIVA: si no hay registro de contexto, el sistema
        # se comporta exactamente igual que en M2. La captura observa el turno; no participa en
        # ninguna decision (restriccion 2 del gate del CEO).
        self.contexto = contexto
        # Reconocedor de declaraciones de hecho propio. OPCIONAL, como `contexto`: con None el turno
        # sigue exactamente el camino anterior. Es un PUERTO y no un import porque el criterio vive en
        # `conectores.conversacion` (el mismo que usa la captura) y `core` no depende de `conectores`.
        self.reconocer_declaracion = reconocer_declaracion
        # Un adaptador suelto se envuelve; el resto del codigo trabaja siempre contra un registro.
        if hasattr(adaptadores, "para"):
            self.registro = adaptadores
        else:
            self.registro = RegistroAdaptadores([adaptadores])
        # Sin motor inyectado se construye uno sobre el mismo registro y los mismos permisos: el
        # flujo es identico venga de donde venga la peticion.
        if motor is None:
            # F4 · un motor fabricado aqui debe saber ejecutar las rutas propias del orquestador.
            # Sin esto seria un motor que no atiende ni la soberania ni las automatizaciones, y esas
            # operaciones fallarian por «ninguna capacidad atiende», no por un control de gobierno:
            # un fallo indistinguible de una denegacion legitima. Cuando el motor viene inyectado
            # —produccion, `composicion.py`— los ejecutores ya estan inscritos alli y no se tocan.
            for ejecutor in (
                EjecutorModeloUsuario(memory),
                EjecutorReglas(automatizaciones) if automatizaciones is not None else None,
            ):
                if ejecutor is not None and self.registro.para(ejecutor.capabilities[0]) is None:
                    self.registro.registrar(ejecutor)
            self.motor = MotorAutomatizacion(self.registro, permissions)
        else:
            self.motor = motor
        # F4 tramo 3 · la captura de senales se construye AQUI y no antes porque necesita el motor:
        # §4.2 la señalaba como hueco —«escribe conocimiento sobre el usuario sin correspondencia
        # alguna»— y ahora cada senal entra por `registrar_informacion_usuario`.
        self.almacen = AlmacenSenales(memory, motor=self.motor) if contexto is not None else None
        self._timers: dict[str, Timer] = {}
        self._done: dict[str, asyncio.Event] = {}
        self._results: dict[str, dict] = {}
        # Memoria de trabajo por usuario: (usuario, say SIN marca, estatus). D-FC-8 = B: el estatus viaja
        # con el turno para que una propuesta del modelo nunca pueda reentrar desnuda en el prompt.
        # M8: cada turno retenido lleva ademas DE QUE SUPERFICIE salio. No es una memoria nueva ni
        # retiene nada mas: es la metadata minima para encontrar el ultimo turno de EJECUCION sin
        # tener que deducirlo releyendo el texto —adivinar sobre la propia salida es justo lo que
        # hace que dos implementaciones del mismo dato acaben divergiendo—.
        self._dialogue: dict[str, list[recuperacion.Turno]] = {}
        # Semana 2: la orden de hogar que AURA PROPUSO y espera confirmar, por usuario. Vive UN turno:
        # un «sí» que llega más tarde no puede ejecutar algo que ya nadie tiene delante.
        self._propuestas_de_hogar: dict[str, tuple[str, dict]] = {}
        # Semana 2: FRONTERA DE GOBIERNO. Que una orden HABLADA cambie el mundo es una decisión del CEO, y
        # desde 2026-10-04 (DP-VOZ-ACCION, opción C) es una llave POR ENTIDAD: la voz solo puede accionar las
        # entidades de este conjunto. Vacío por defecto = cerrada. A propósito NO la enciende ninguna variable
        # de entorno: la abre la composición (`composicion.VOZ_ACTUA_EN`), tras una decisión.
        self.voz_actua_en: frozenset[str] = frozenset()
        # Cómo se NOMBRA cada entidad de `voz_actua_en` ante la persona (CEO 2026-10-04): la abre la composición
        # (`composicion.NOMBRE_HUMANO_DE_VOZ`). Solo redacta; el entity_id sigue siendo la identidad interna.
        self.nombres_de_voz: dict[str, str] = {}
        # Semana 2: lo que AURA sabe de su entorno físico. Lo cablea la composición; sin él, la pregunta
        # sigue su camino de siempre.
        self.entorno = None
        self.percepcion_visual = None  # PercepcionBajoDemanda | None (DP FRAME→OBSERVACION, bajo demanda)
        # Bloque multimodal (acta CEO 2026-09-28): ESCUCHAR y PERCIBIR EVENTO, bajo demanda, gated, sin
        # persistencia. Los cablea la composición; sin ellos, la pregunta sigue su camino de siempre.
        self.percepcion_auditiva = None  # PercepcionAuditivaBajoDemanda | None
        self.percepcion_evento = None  # PercepcionDeEventoBajoDemanda | None
        # DR-4 (CEO, 2026-09-15). Politica de la ventana de trabajo, en tres parametros:
        #   _DIALOG_N   turnos que se CONSERVAN siempre tras un descarte: el suelo de lo que AURA recuerda.
        #   _DIALOG_MAX turnos a partir de los cuales se descarta. Con MAX == N la ventana desliza turno a
        #               turno; con MAX > N descarta por BLOQUES y la cache de prefijo de Ollama solo se
        #               rompe en el turno del descarte.
        #   _RECORTE_AURA caracteres de cada respuesta PREVIA de AURA que reentran en el prompt (None: integra).
        # **VALORES MEDIDOS, NO ELEGIDOS** (campana 4, `milestones/m3-entry/evidencia-cognicion-local/`).
        # Cuatro conversaciones reales de 12 turnos en HC-1, comparando los turnos 8-12:
        #
        #   politica                 ingesta mediana   turno mediana   turnos >180 s   recuerda
        #   deslizante 6 (antes)          219,6 s          299,7 s         5 de 5         6
        #   solo recorte 160              128,7 s          178,0 s         2 de 5         6
        #   solo bloques 9->6              28,6 s           93,1 s         0 de 5        6-9
        #   ambas (esta)                   22,1 s           75,9 s         0 de 5        6-9
        #
        # El descarte por BLOQUES es lo decisivo: la cache de prefijo del modelo solo se invalida en el
        # turno del descarte, no en todos. El recorte aporta encima y, sobre todo, ACOTA el buffer, que
        # con respuestas largas crecia sin tope (2.609 -> 1.925 caracteres de maximo).
        #
        # **La memoria conversacional no se sacrifica: aumenta.** Antes se recordaban 6 turnos fijos;
        # ahora entre 6 y 9. Lo que dijo el USUARIO reentra siempre integro; solo las respuestas previas
        # de la propia AURA entran como extracto, y marcado como tal.
        self._DIALOG_N = 6
        self._DIALOG_MAX = 9
        self._RECORTE_AURA: int | None = 160
        # D-FC-6: turnos que ahora mismo esperan al modelo. Lo lee `__main__._esperar_con_acuse`.
        self._en_modelo: set[str] = set()
        bus.subscribe("perception.turn_end", self.on_turn)

    async def handle_utterance(self, user_id, audio_text, trace_id, activado: bool = False):
        t = Timer()
        self._timers[trace_id] = t
        self._done[trace_id] = asyncio.Event()
        # **UN PERIFERICO ROTO NO DESTRUYE EL TURNO (MISION VOZ, CEO 2026-09-15).** Sin esto, un fallo
        # del transcriptor —modelo ausente, USB desmontada, Whisper caido— salia por `handle_utterance`
        # y el turno se quedaba sin `_done`: la superficie esperaba una respuesta que no iba a llegar.
        # Se cierra por el Core, diciendo la verdad, sin transcripcion inventada y SIN llamar al modelo.
        try:
            text = await self.voice.stt(audio_text, trace_id)
        except Exception as e:
            obs.log("WARN", "voice", f"transcripcion fallida; el Core cierra el turno: {e}", trace_id, audit=True)
            # `text=""` es deliberado: no hubo texto del usuario. `destino_de_memoria("")` es None, de
            # modo que no se persiste un turno que nadie pronuncio.
            await self._finalizar_turno(
                user_id, trace_id, "", _STT_NO_DISPONIBLE, "core", t, dominio="voz", estatus=Estatus.ABSTENCION
            )
            return
        t.mark("stt")
        # `voz` (semana 2): el turno fue HABLADO si el transcriptor cambió la entrada. No depende de cómo
        # se llame el fichero ni de qué adaptador de voz haya: solo de que hubo transcripción.
        # `activado` (C1, DP-VOZ-ACCION §8): el turno siguió a la palabra de activación. Lo declara quien
        # escucha (la escucha continua), no el texto: lo que se dice no puede darse a sí mismo la llave.
        await self.bus.publish(
            Event(
                "perception.turn_end",
                trace_id,
                user_id,
                {"text": text, "voz": text != audio_text, "activado": activado},
            )
        )

    async def wait(self, trace_id, timeout=10):
        await asyncio.wait_for(self._done[trace_id].wait(), timeout)
        return self._results.get(trace_id)

    def turno_en_modelo(self, trace_id: str) -> bool:
        """D-FC-6: True mientras el turno espera la respuesta del proveedor; False antes y despues.
        Permite a la superficie decir «estoy consultando mi modelo» solo cuando es verdad."""
        return trace_id in self._en_modelo

    def evaluar_nodos(self) -> int:
        """Entrega al Centro los avisos de NODO-01 que hayan cambiado desde la ultima evaluacion.

        Devuelve cuantos avisos ACEPTO el Centro (no los suprimidos por duplicados). Nunca lanza: un fallo del vigia no puede
        romper la apertura ni un turno (se registra WARN).
        """
        if self.vigia_nodos is None or self.notificaciones is None:
            return 0
        try:
            ahora = time.time()
            lectura = self.vigia_nodos(ahora)
            if lectura is None:
                return 0
            registro, receptor_vivo = lectura
            avisos, nuevo_estado = evaluar_avisos_nodos(registro, ahora, receptor_vivo, self._estado_nodos)
            aceptados = sum(
                1 for a in avisos if self.notificaciones.recibir(Notificacion("aura", a.titulo, prioridad=a.prioridad))
            )
            # El estado se adopta DESPUES de entregar: si la entrega falla, el aviso se reintenta.
            self._estado_nodos = nuevo_estado
            return aceptados
        except Exception as e:
            obs.log(
                "WARN", "nodos", f"no se pudo evaluar el estado de los nodos: {type(e).__name__}: {str(e)[:120]}", "-"
            )
            return 0

    async def on_turn(self, ev: Event):
        tid = ev.trace_id
        self.evaluar_nodos()  # avisos de nodos por turno (nunca rompe el turno)
        uid = ev.user_id
        text = ev.payload["text"]
        t = self._timers.get(tid) or Timer()
        # La propuesta de hogar del turno ANTERIOR se consume AQUÍ, al empezar, sea cual sea la
        # superficie que acabe respondiendo. Encontrado por su prueba de caducidad: consumida a mitad de
        # la cascada, un turno atendido antes («¿cómo me llamo?») la dejaba viva y un «sí» tardío
        # ejecutaba una acción que ya nadie tenía delante.
        propuesta = self._propuestas_de_hogar.pop(uid, None)
        por_voz = bool(ev.payload.get("voz"))
        activado = bool(ev.payload.get("activado"))
        if por_voz:
            # Traza del E2E: sin esto, «¿la segunda frase quedó asociada al turno activado?» no se podía demostrar.
            obs.log("CORE", "voz", f"turno hablado: activado={activado}", tid)
        # Un turno HABLADO sin habla (el STT no oyó nada) no es una pregunta: no va a memoria ni al modelo.
        # Medido por el aire el 2026-10-04: el silencio tras «Oye Aurora» se contestaba «No tengo ningún
        # recuerdo registrado sobre eso».
        if por_voz and not text.strip():
            await self._finalizar_turno(uid, tid, text, NO_TE_OI, "core", t, dominio="voz", estatus=Estatus.ABSTENCION)
            return
        # FRONTERA COGNITIVA (D-FC-1..8): de quien habla el turno. Se calcula UNA vez y se registra al
        # principio para que la auditoria vea el referente aunque el turno lo atienda una superficie
        # anterior. No decide nada por si solo: las ramas de abajo lo consultan.
        ref = intencion.referente(text)
        obs.log("CORE", "referente", f"referente={ref}", tid)
        # Soberania del modelo del usuario: inspeccionar/entender/corregir/olvidar lo que AURA sabe de ti.
        if self.modelo_usuario is not None:
            resp = await self._atender_modelo_usuario(uid, text)
            if resp is not None:
                await self._finalizar_turno(
                    uid, tid, text, resp, "core", t, dominio="modelo_usuario", estatus=_estatus_del_core(resp)
                )
                return
        # Superficie del Centro de Notificaciones: "¿que ha pasado mientras no estaba?" se responde con
        # lo que AURA hizo, sin consultar memoria ni LLM (es un hecho del sistema, no una inferencia).
        if self.notificaciones is not None and _es_consulta_de_notificaciones(text):
            await self._finalizar_turno(
                uid, tid, text, self._resumen_notificaciones(), "core", t, dominio="notificaciones"
            )
            return
        # Automatizaciones del usuario (MVP capacidad 5): inspeccionar y crear reglas. Deterministas como el
        # resto de superficies; el LLM no interviene (definir o listar una regla es un hecho, no una inferencia).
        if self.automatizaciones is not None:
            if _es_consulta_de_reglas(text):
                await self._finalizar_turno(uid, tid, text, self._describir_reglas(uid), "core", t, dominio="reglas")
                return
            if _es_creacion_de_regla(text):
                await self._finalizar_turno(
                    uid, tid, text, await self._crear_regla(uid, text), "core", t, dominio="reglas"
                )
                return
            # Desactivar una automatizacion (M3 entry): se responde SIEMPRE aqui, tenga o no el
            # usuario alguna activa, para que la frase no caiga en otra superficie (memoria, LLM)
            # y produzca una respuesta enganosa o un efecto no pedido.
            if _es_cancelacion_de_regla(text):
                await self._finalizar_turno(
                    uid, tid, text, await self._desactivar_regla(uid, text), "core", t, dominio="reglas"
                )
                return
        # Ventana del SO Interno (M3 entry): "¿que capacidades tienes?" / "¿en que estas trabajando?" /
        # "¿por que estas bloqueada?" / "¿que aprendiste?" se responden desde el propio sistema, nunca
        # desde el LLM. Van DESPUES de las 8 superficies anteriores y ANTES de la ausencia de memoria:
        # si llegaran a caer ahi, el usuario recibiria "no tengo ningun recuerdo" para algo que el
        # sistema si sabe (el defecto de producto que este incremento corrige).
        # Conversacion General v1 (CEO, 06f53f3). Se evalua DESPUES de las 8 superficies anteriores
        # -no puede robarles ninguna frase- y ANTES de las 4 de la ventana del SO, porque un turno
        # como "buenos dias Aurora, ¿que puedes hacer?" es UNA SECUENCIA: si capacidades lo
        # interceptara primero, el saludo se perderia. Cuando no reconoce el turno entero devuelve
        # None y todo sigue exactamente igual que antes de este incremento.
        # **RESPUESTA A UNA PROPUESTA DE HOGAR (semana 2).** Va ANTES de la conversación general porque
        # «sí» es también un turno social que aquella se quedaría. No puede robar ninguna frase: solo
        # actúa si en el turno ANTERIOR se propuso una acción, y la propuesta se consume en cualquier caso.
        if propuesta is not None:
            decision = hogar.confirmacion(text)
            if decision is True:
                capacidad, args = propuesta
                rechazo = self._rechazo_de_voz(por_voz, activado, tid, "confirmacion hablada")
                if rechazo is not None:
                    await self._finalizar_turno(
                        uid, tid, text, rechazo, "core", t, dominio="hogar", estatus=Estatus.ABSTENCION
                    )
                    return
                if args.get("device") not in self.voz_actua_en:
                    obs.log(
                        "CORE",
                        "hogar",
                        f"{capacidad} por voz confirmado y DETENIDO: la entidad {args.get('device')!r} no esta en "
                        "voz_actua_en (DP-VOZ-ACCION C2)",
                        tid,
                        audit=True,
                    )
                    await self._finalizar_turno(
                        uid,
                        tid,
                        text,
                        hogar.pendiente_de_decision(capacidad, args, self.nombres_de_voz.get(args.get("device", ""))),
                        "core",
                        t,
                        dominio="hogar",
                        estatus=Estatus.ABSTENCION,
                    )
                    return
                resp = await self._despachar_orden(uid, capacidad, {"device": args["device"]}, tid)
                await self._finalizar_turno(uid, tid, text, resp, "core", t, dominio="orden_de_capacidad")
                return
            if decision is False:
                await self._finalizar_turno(uid, tid, text, "De acuerdo, no lo hago.", "core", t, dominio="hogar")
                return
        resp = await self._atender_conversacion_general(uid, text)
        if resp is not None:
            await self._finalizar_turno(uid, tid, text, resp, "core", t, dominio="conversacion_general")
            return
        if _es_consulta_de_capacidades(text):
            await self._finalizar_turno(uid, tid, text, self._describir_capacidades(), "core", t, dominio="capacidades")
            return
        # Ordenes de capacidad. Van DESPUES de todas las superficies conversacionales -no pueden
        # robarles ninguna frase- y ANTES del modelo, porque el modelo no decide que se ejecuta
        # (ADR-0014 §4). Cuando no reconocen el turno, devuelven None y todo sigue igual que antes.
        resp = await self._atender_orden_de_capacidad(uid, text, tid)
        if resp is not None:
            await self._finalizar_turno(uid, tid, text, resp, "core", t, dominio="orden_de_capacidad")
            return
        # **ÓRDENES DE HOGAR (semana 2).** Medido `[EJEC]`: «enciende la tele» la interpretaba el MODELO,
        # que «encendía la luz de la sala». Aquí la reconoce el Core, la PROPONE y no la ejecuta hasta un
        # «sí» en el turno siguiente —más estricto que la lista verde, que ni siquiera pregunta—.
        # Ejecutar es `_despachar_orden`: el mismo Motor Único que cualquier otra orden.
        orden_de_hogar = hogar.reconocer(text) if self.motor is not None else None
        if orden_de_hogar is not None:
            capacidad, dispositivo = orden_de_hogar
            if por_voz and capacidad not in hogar.CAPACIDADES_DE_VOZ:
                # Opción C (DP-VOZ-ACCION §8): la voz solo enciende o apaga. Ni propone ni ejecuta (acta 2026-10-22 §5).
                obs.log("CORE", "hogar", f"{capacidad} hablado: fuera de la opcion C, no se propone", tid, audit=True)
                await self._finalizar_turno(
                    uid,
                    tid,
                    text,
                    hogar.VOLUMEN_POR_VOZ_PENDIENTE,
                    "core",
                    t,
                    dominio="hogar",
                    estatus=Estatus.ABSTENCION,
                )
                return
            if not por_voz:
                # POR TEXTO rige la regla aprobada de M1: la lista verde ejecuta sin preguntar (el catálogo
                # lo decidió así a propósito para encender/apagar). Lo nuevo es QUIÉN interpreta: el Core,
                # con el dispositivo que la persona nombró, y la confirmación del efecto por el adaptador.
                # «la tele de la sala» es la entidad cuyo nombre humano lo dice; si no casa, la resolución de siempre.
                dispositivo = hogar.entidad_por_nombre_humano(dispositivo, self.nombres_de_voz) or dispositivo
                resp = await self._despachar_orden(uid, capacidad, {"device": dispositivo}, tid)
                await self._finalizar_turno(uid, tid, text, resp, "core", t, dominio="orden_de_capacidad")
                return
            objetivo = self._rechazo_de_voz(por_voz, activado, tid, "orden hablada")
            if objetivo is None:
                objetivo = await self._entidad_para_voz(capacidad, dispositivo, tid)
            if isinstance(objetivo, str):
                await self._finalizar_turno(
                    uid, tid, text, objetivo, "core", t, dominio="hogar", estatus=Estatus.ABSTENCION
                )
                return
            entidad, nombre = objetivo
            humano = self.nombres_de_voz.get(entidad)
            self._propuestas_de_hogar[uid] = (capacidad, {"device": entidad, "nombre": nombre})
            obs.log("CORE", "hogar", f"propuesta {capacidad} sobre {entidad!r}: espera confirmacion", tid, audit=True)
            await self._finalizar_turno(
                uid,
                tid,
                text,
                hogar.proponer_humano(capacidad, humano) if humano else hogar.proponer(capacidad, nombre),
                "core",
                t,
                dominio="hogar",
                estatus=Estatus.ACLARACION,
            )
            return
        # **CONSULTA DEL ESTADO DE LA TV (acta 2026-10-22 §4).** «¿Está encendida la tele?» es una LECTURA de Home
        # Assistant, sin el modelo y sin el Motor (no cambia nada). Va ANTES de la orden no entendida, que si no se la
        # tragaría por nombrar la TV.
        consulta = hogar.reconocer_consulta(text) if self.motor is not None else None
        if consulta is not None:
            resp, estatus_consulta = await self._consultar_estado_de_hogar(consulta, por_voz, tid)
            await self._finalizar_turno(uid, tid, text, resp, "core", t, dominio="hogar", estatus=estatus_consulta)
            return
        # **ORDEN PARA LA TV NO ENTENDIDA (E2E físico, 2026-10-04).** Una orden hablada y activada que nombra la
        # TV pero no se reconoce (Whisper: «¿No fiende la televisión?») seguía la cascada y, por llegar como
        # pregunta, acababa en la puerta de memoria: «No tengo ningún recuerdo». Ni actúa ni adivina: lo dice.
        # Una PREGUNTA por lo que se hizo con la TV («¿apagaste la tele?») no es una orden mal oída: sigue hacia la
        # recuperación, que repite lo ocurrido sin ejecutar nada (2026-10-21).
        if (
            por_voz
            and activado
            and self.motor is not None
            and hogar.menciona_tv_sin_orden(text)
            and recuperacion.reconocer(text) is None
        ):
            obs.log("CORE", "hogar", "orden hablada para la TV no reconocida: no se actúa ni se consulta memoria", tid)
            await self._finalizar_turno(
                uid, tid, text, hogar.ORDEN_NO_ENTENDIDA, "core", t, dominio="hogar", estatus=Estatus.ABSTENCION
            )
            return
        # **EL ENTORNO FÍSICO (semana 2).** «¿Qué hay conectado?» se responde DESCUBRIENDO la red en ese
        # momento —vecinos, mDNS, SSDP—, no con una lista escrita a mano ni con el modelo. Cada dispositivo
        # sale con su nivel: descubierto, identificado, integrado o controlable.
        if self.entorno is not None and entorno.es_consulta_de_entorno(text):
            resp = await asyncio.to_thread(self.entorno.explorar, tid)
            await self._finalizar_turno(uid, tid, text, resp, "core", t, dominio="entorno")
            return
        # ORDEN DE ESPECIFICIDAD (fix auditoría 2026-09-28): EVENTO y AUDIO se evalúan ANTES que VISUAL. El
        # reconocedor visual incluye «que hay» (genérico), que colisiona con «hay movimiento»/«hay alguien»
        # del evento; evaluar primero los específicos evita que la rama visual enmascare una consulta de
        # movimiento/audio. VISUAL queda como fallback general.
        # PERCIBIR EVENTO — detección PROPIA de movimiento bajo demanda (no ONVIF Events, rotos en .110).
        # «¿Hay movimiento en la cámara X?» -> señal (detectado+magnitud), gated por política VISUAL; sin
        # persona/identidad/intención.
        pe = getattr(self, "percepcion_evento", None)
        if pe is not None and percepcion.es_consulta_evento_sin_camara(text):
            # Sin decir cuál: se pregunta y se enumeran las autorizadas para VÍDEO; no se procesa ninguna.
            resp = percepcion.pedir_camara(pe.superficies_autorizadas(), "vigilar", "hay movimiento")
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="percepcion_evento", estatus=Estatus.ACLARACION
            )
            return
        superficie_evento = percepcion.es_consulta_evento(text) if pe is not None else None
        if pe is not None and superficie_evento is not None:
            evento = await asyncio.to_thread(pe.observar_evento, superficie_evento, tid)
            if evento is None:
                resp = (
                    f"No puedo vigilar «{superficie_evento}»: no la tengo registrada o no está "
                    "autorizada para procesar vídeo."
                )
            else:
                resp = percepcion.describir_evento(evento)
            await self._finalizar_turno(
                uid,
                tid,
                text,
                resp,
                "core",
                t,
                dominio="percepcion_evento",
                estatus=Estatus.HECHO if (evento and evento.detectado) else Estatus.ABSTENCION,
            )
            return
        # ESCUCHAR — audio de cámara bajo demanda (bloque multimodal, acta 2026-09-28). «¿Qué se oye en la
        # cámara X?» -> observación auditiva efímera (transcripción opcional), gated por política de AUDIO;
        # sin persistir audio, sin identidad, sin escucha continua.
        pa = getattr(self, "percepcion_auditiva", None)
        if pa is not None and percepcion.es_consulta_auditiva_sin_camara(text):
            # Sin decir cuál: se pregunta y se enumeran las autorizadas para AUDIO; no se escucha ninguna.
            resp = percepcion.pedir_camara(pa.superficies_autorizadas(), "escuchar", "qué oyes")
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="percepcion_auditiva", estatus=Estatus.ACLARACION
            )
            return
        superficie_audio = percepcion.es_consulta_auditiva(text) if pa is not None else None
        if pa is not None and superficie_audio is not None:
            obs_audio = await asyncio.to_thread(pa.observar_audio, superficie_audio, tid)
            if obs_audio is None:
                resp = (
                    f"No puedo escuchar «{superficie_audio}»: no la tengo registrada o no está autorizada para audio."
                )
            else:
                resp = percepcion.describir_observacion_auditiva(obs_audio)
            await self._finalizar_turno(
                uid,
                tid,
                text,
                resp,
                "core",
                t,
                dominio="percepcion_auditiva",
                estatus=Estatus.HECHO if (obs_audio and obs_audio.audio_recibido) else Estatus.ABSTENCION,
            )
            return
        # **FRAME → OBSERVACIÓN (DP aprobado 2026-09-28, Alt B / bajo demanda / imagen-cero).** «¿Qué ves en
        # la cámara X?» produce una observación EFÍMERA (fuente+dimensiones), gobernada por política; sin
        # persona/identidad/evento, sin guardar imagen, sin escribir memoria. `getattr`: superficie de prueba
        # con `__new__` puede no tener el atributo.
        pv = getattr(self, "percepcion_visual", None)
        if pv is not None and percepcion.es_consulta_visual_sin_camara(text):
            # Sin decir cuál: se pregunta y se enumeran las AUTORIZADAS; no se mira ninguna (2026-10-22).
            resp = percepcion.pedir_camara(pv.superficies_autorizadas())
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="percepcion_visual", estatus=Estatus.ACLARACION
            )
            return
        superficie_visual = percepcion.es_consulta_visual(text) if pv is not None else None
        if pv is not None and superficie_visual is not None:
            observacion = await asyncio.to_thread(pv.observar, superficie_visual, tid)
            if observacion is None:
                resp = f"No puedo mirar «{superficie_visual}»: no la tengo registrada o no está autorizada para ver."
                autorizadas = pv.superficies_autorizadas()
                if autorizadas:
                    resp += " Puedo mirar: " + ", ".join(f"«{s}»" for s in autorizadas) + "."
            else:
                resp = percepcion.describir_observacion(observacion)
            await self._finalizar_turno(
                uid,
                tid,
                text,
                resp,
                "core",
                t,
                dominio="percepcion_visual",
                estatus=Estatus.HECHO if (observacion and observacion.frame_recibido) else Estatus.ABSTENCION,
            )
            return
        # La consulta de tareas ya no exige `estado_operativo`: con el ciclo autonomo cableado
        # tiene fuente propia, y sin ninguna de las dos NO se desvia (cae al camino de siempre).
        # Las superficies de estado declaran AUSENCIA con su propio texto de «no me consta» (D-FC-1).
        if (self.estado_operativo is not None or self.estado_autonomo is not None) and _es_consulta_de_tareas(text):
            resp = self._describir_tareas()
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="estado_autonomo", estatus=_estatus_del_core(resp)
            )
            return
        if self.estado_autonomo is not None and _es_consulta_de_evolucion(text):
            resp = self._describir_evolucion(text)
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="evolucion", estatus=_estatus_del_core(resp)
            )
            return
        # «¿Qué hiciste?» tras actuar en ESTA conversación es por esa acción, no por el historial del ciclo
        # autónomo (semana 2, encontrado `[EJEC]` con la TV real: contestaba «mi última tarea es P-018»).
        # Sin ninguna acción en la ventana, el historial responde igual que antes.
        clase_en_conversacion = recuperacion.reconocer(text)
        if clase_en_conversacion == recuperacion.PREGUNTA_ANTES_DEL_REINICIO:
            # Punto D: solo el registro persistido puede contestarlo, aunque la ventana tenga ejecuciones nuevas.
            await self._responder_recuperacion(uid, tid, text, t, clase_en_conversacion)
            return
        if clase_en_conversacion is not None and recuperacion.hubo_ejecucion(self._dialogue.get(uid, [])):
            await self._responder_recuperacion(uid, tid, text, t, clase_en_conversacion)
            return
        if self.estado_autonomo is not None and _es_consulta_de_ultima_tarea(text):
            resp = self._describir_ultima_tarea()
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="historial", estatus=_estatus_del_core(resp)
            )
            return
        # Autorizacion humana (CEO, 2026-09-01). Va ANTES de la ausencia de memoria y del LLM porque
        # conceder un permiso es un HECHO del sistema, no una inferencia (ADR-0014). Y lo unico que
        # hace es marcar una solicitud del buzon: la accion se vuelve a evaluar en el motor unico.
        identificador = es_autorizacion(text)
        if identificador is not None:
            respuesta = self._registrar_autorizacion(uid, identificador, text, tid)
            await self._finalizar_turno(uid, tid, text, respuesta, "core", t, dominio="autorizacion")
            return
        # Los dos dominios que caian en la memoria del usuario, que no sabe nada de ellos.
        if self.estado_autonomo is not None and _es_consulta_de_decisiones(text):
            resp = self._describir_decisiones(text)
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="decisiones", estatus=_estatus_del_core(resp)
            )
            return
        if self.estado_autonomo is not None and _es_consulta_de_oportunidades(text):
            resp = self._describir_oportunidades()
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="oportunidades", estatus=_estatus_del_core(resp)
            )
            return
        if self.estado_operativo is not None:
            if _es_consulta_de_gobierno(text):
                resp = self._describir_bloqueo()
                await self._finalizar_turno(
                    uid, tid, text, resp, "core", t, dominio="gobierno", estatus=_estatus_del_core(resp)
                )
                return
        if _es_consulta_de_formacion(text):
            resp = _resumen_formacion()
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="formacion", estatus=_estatus_del_core(resp)
            )
            return
        # **AURA SOBRE SI MISMA (D-FC-3 = A).** «que desarrollas en este momento?» (T8) no nombraba
        # ninguna de las superficies de arriba y caia en la pared: «No tengo ningun recuerdo» para una
        # pregunta que no es sobre el usuario. Va DESPUES de las superficies de estado -que ya atienden
        # «que tareas tienes», «por que estas bloqueada» o «que capacidades tienes» y conservan la
        # precedencia- y ANTES de la aritmetica, de la pared y del modelo: el modelo nunca redacta lo
        # que AURA hace. Reutiliza `_describir_tareas`; no hay un segundo calculo del estado.
        #
        # Exige una fuente de estado conectada, con la MISMA disciplina que la consulta de tareas: un
        # orquestador construido a mano sin estado operativo sigue el camino que ya existia -la pared,
        # que tambien es el Core, AUSENCIA y 0 llamadas- y `test_conversacion_ventana_so` lo fija. En
        # produccion `composicion.py` cablea siempre el estado operativo, asi que T8 llega aqui.
        if (self.estado_operativo is not None or self.estado_autonomo is not None) and intencion.es_consulta_sobre_aura(
            text
        ):
            resp = self._describir_aura()
            await self._finalizar_turno(
                uid, tid, text, resp, "core", t, dominio="aura", estatus=_estatus_del_core(resp)
            )
            return
        # Aritmetica determinista (CEO, 2026-09-01). «cuanto es 1+1» no tenia superficie, recorria la
        # cascada entera y la contestaba el enrutador con su respuesta enlatada: «Entendido.». Una
        # suma no es una inferencia -- es la misma regla de ADR-0014 que ya gobierna el resto.
        #
        # VA AQUI, y no antes, por la disciplina que este fichero se aplica desde hace ocho
        # superficies: lo nuevo se evalua DESPUES de lo que ya existia, para que no pueda robarle
        # ninguna frase. Y antes de la memoria y del modelo, que es lo que el defecto pedia. El
        # reconocimiento ademas es estrecho: o la frase empieza por una entradilla declarada, o el
        # texto ENTERO es una expresion -- «borra 2 archivos» no lo es.
        #
        # D-FC-4 = A: `resolver_formal` amplia la misma superficie a problemas verbales de una premisa
        # y una operacion (T6). Para una expresion pura devuelve exactamente lo que devolvia
        # `resolver_aritmetica`. Si la frase tiene forma cuantitativa pero no se puede resolver con
        # certeza, el Core PREGUNTA (ACLARACION): el modelo nunca hace de calculadora.
        formal = resolver_formal(text)
        if formal is not None:
            clase, respuesta = formal
            if clase == Estatus.HECHO.value:
                obs.log("CORE", "aritmetica", f"resuelta en el nucleo, sin LLM: {text[:40]!r}", tid)
                await self._finalizar_turno(
                    uid, tid, text, respuesta, "core", t, dominio="aritmetica", estatus=Estatus.HECHO
                )
            else:
                obs.log("CORE", "formal", f"infradeterminado -> aclaracion, sin LLM: {text[:40]!r}", tid)
                await self._finalizar_turno(
                    uid, tid, text, respuesta, "core", t, dominio="formal", estatus=Estatus.ACLARACION
                )
            return
        # **SUPERFICIE COGNITIVA (M3, 2026-09-09).** `_es_consulta_de_memoria` NO se toca: sigue
        # diciendo que toda interrogativa es una consulta de memoria, y por eso la garantia de 24/24
        # no se mueve. Lo que se anade es una superficie POSITIVA y CERRADA que solo puede desviar lo
        # que NOMBRA —marcos conceptuales declarados, o una suposicion con premisa numerica que pide
        # una cantidad— y que ademas exige que el eje 2 de M-1 diga que el turno no habla del mundo
        # del usuario. Medido antes de cablearla: 0 colisiones con las 24 negativas, 0 con las 53
        # positivas y 0 fugas en 15 ataques escritos para romperla.
        #
        # NO es la via que se descarto. Estrechar la puerta bajaba la proteccion a 17/24; esto la deja
        # intacta y desvia por delante. La asimetria es la tesis: un error aqui no contesta una
        # pregunta general, no expone un hecho personal.
        #
        # D-FC: la excepcion de cognicion exige ADEMAS que el referente sea el MUNDO. La compuerta vive en
        # `_es_turno_cognitivo` para que se pruebe por si misma y no por el orden de la cascada.
        # **PREGUNTA POR UNA EJECUCION ANTERIOR (M8, CEO 2026-09-22).** Medido antes de cablearlo
        # `[EJEC]`: en 8 de 12 escenarios el usuario preguntaba por el resultado del turno anterior
        # —«¿cuántas entradas encontraste?»— y recibia «No tengo ningun recuerdo registrado sobre
        # eso» MIENTRAS la ventana de trabajo lo contenia entero. El problema nunca fue de
        # almacenamiento: `DR-4` ya retiene el turno. Era que la pregunta buscaba en la memoria
        # PERSONAL, donde un resultado de ejecucion no esta —ni debe estar (`Bible 4.1 §1`)—.
        #
        # VA AQUI, y no antes, por la disciplina que esta cascada se aplica desde hace diez
        # superficies: lo nuevo se evalua DESPUES de todo lo que ya existia, para que no pueda
        # quitarle ninguna frase. Y antes de la pared, que es lo que el defecto pedia.
        #
        # NO se toca la puerta de `ADR-0014` ni `_es_consulta_de_memoria`: siguen sosteniendo el
        # 24/24 intactas, y una prueba parametrizada comprueba que este reconocedor no se queda
        # NINGUNA de esas 24. Son dos gramaticas distintas —el mundo del usuario frente a algo que
        # hizo AURA— y por eso pueden separarse sin ensanchar nada.
        #
        # **No ejecuta nada.** Lee la ventana y repite lo que AURA ya dijo, diciendo que lo repite.
        # El Motor Unico no se llama: no hay segunda ruta de ejecucion (`ALERTA-005`).
        clase_de_recuperacion = recuperacion.reconocer(text)
        if clase_de_recuperacion is not None:
            await self._responder_recuperacion(uid, tid, text, t, clase_de_recuperacion)
            return
        cognicion_general = _es_turno_cognitivo(text)
        hits = await self.memory.recall(uid, text)
        t.mark("memory")
        # La puerta decide con lo que AURA da por cierto HOY, no con `hits` crudos (Director Tecnico, por orden ejecutiva del CEO, 2026-10-06,
        # `milestones/m3-entry/RESOLUCION-S3-CM2-ORDEN-CEO-2026-10-06.md` §1 y §2): `recall` devuelve
        # tambien ecos retirados, refutadas y superseded, y si NO queda ninguna vigente la ausencia es un
        # hecho. `recall` no cambia: solo cambia con que se decide. El mismo `vigentes` alimenta el `ctx`.
        vigentes = [h for h in hits if _da_por_cierto(h)]
        if hits and not vigentes:
            # `recall` trunca a k y desempata por antiguedad: con varias versiones de un atributo, las
            # superseded y los ecos pueden ocupar todos los huecos y dejar fuera a la vigente. Antes de
            # afirmar ausencia se mira la consulta ANCHA; solo en este caso (una sola llamada extra).
            # Se conserva el presupuesto de contexto: como mucho `len(hits)` vigentes.
            amplios = await self.memory.recall(uid, text, k=_K_TODAS_LAS_COINCIDENCIAS)
            vigentes = [h for h in amplios if _da_por_cierto(h)][: len(hits)]
        # ADR-0014: la ausencia de memoria es un HECHO, no una inferencia. Si el usuario
        # pregunta por un recuerdo y no existe registro, responde el nucleo y NO se consulta
        # al LLM: no se le da ocasion de inferir, completar ni reformular lo inexistente.
        if not vigentes and _es_consulta_de_memoria(text) and not cognicion_general:
            say = "No tengo ningun recuerdo registrado sobre eso."
            obs.log(
                "CORE", "grounding", "memoria vacia -> respuesta determinista (sin llamada al LLM)", tid, audit=True
            )
            await self._finalizar_turno(uid, tid, text, say, "core", t, dominio="memoria", estatus=Estatus.AUSENCIA)
            return
        # **DECLARACION DE HECHO PROPIO (2026-09-13).** «me llamo Mauricio» no es pregunta ni orden: no
        # tocaba ninguna superficie y caia aqui, al modelo, que en modo cognitivo solo puede devolver un
        # `say` (el Core ya fuerza `consulta`). Medido con Ollama real: 263 s para decir «Entendido.».
        # El hecho NO lo registra esta rama: lo registra la captura en `_finalizar_turno`, igual que
        # antes, y DESPUES de decidir la respuesta (restriccion 2 del gate del CEO: la captura observa,
        # no participa). Por eso el acuse es fijo y no depende de que la captura haya guardado nada.
        # El criterio es el de la captura, INYECTADO (una sola definicion). Va despues de todas las
        # superficies existentes -no les roba ninguna frase- y exige que el turno no pida ademas una
        # accion: «me llamo Mauricio y enciende la luz» conserva su camino hacia el router.
        if self.reconocer_declaracion is not None and self.reconocer_declaracion(text) and not _pide_accion(text):
            obs.log("CORE", "declaracion", "hecho propio declarado -> acuse del Core, sin llamada al LLM", tid)
            await self._finalizar_turno(
                uid, tid, text, _ACUSE_DECLARACION, "core", t, dominio="declaracion", estatus=Estatus.HECHO
            )
            return

        # **SOLO LO QUE AURA DA POR CIERTO HOY ENTRA COMO MEMORIA (D-M-5, 2026-09-15).** `recall` devuelve
        # tambien entradas que el Core ya NO afirma: las REFUTADAS («eso ya no es cierto») y las
        # SUPERSEDED por una redeclaracion (`valid_until`, AMP-AURA etapas 1-2). Unirlas aqui era contarle
        # al modelo, como recuerdo vigente, justo lo que el usuario desmintio o corrigio: medido, tras
        # redeclarar el cumpleaños el contexto llevaba la fecha antigua DOS veces.
        #
        # RESUELTO (Director Tecnico, por orden ejecutiva del CEO, 2026-10-06, `milestones/m3-entry/RESOLUCION-S3-CM2-ORDEN-CEO-2026-10-06.md` §1 y
        # §2, fila «Puerta ADR-0014»): `vigentes` se calcula ANTES de la puerta de ADR-0014 y es lo que
        # esta evalua (`not vigentes`), asi que el filtro ya no se limita al contexto. Antes la puerta
        # decidia con `hits` crudos y, si TODOS eran no vigentes, no disparaba: el turno llegaba al modelo
        # con la memoria vacia en vez de recibir la ausencia determinista. Esa consecuencia se declaro y se
        # elevo como decision; la decision fue tocar la puerta, y `recall` NO cambia.
        # (`DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` §9 / §10 describen el estado anterior.)
        #
        # RESIDUO DECLARADO: el eco episodico «usuario dijo: ...» de una declaracion no lleva ni
        # `refutada` ni `valid_until` —es el registro de lo que se DIJO, que sigue siendo cierto como
        # registro—, asi que este filtro no lo alcanza. Enlazarlo con su version exige tocar el modelo de
        # memoria, y tampoco se hace aqui.
        # Memory Context Builder (D-AMP-2): filtra la MEMORIA RECUPERADA antes del prompt. `vigentes`
        # ya está filtrado por vigencia; el Builder excluye además los ecos de terceros. NO cubre el
        # buffer `recent` de abajo (otra vía al prompt, continuidad conversacional) — límite declarado.
        ctx = contexto_memoria.construir_contexto(vigentes)
        # Punto D: un turno con `resumen_prompt` (contenido de ficheros del usuario, o consulta al registro persistido)
        # reentra SOLO con su resumen. La ventana en RAM conserva el texto entero para la recuperacion a peticion.
        buffer = [t._replace(aura=t.resumen_prompt) if t.resumen_prompt else t for t in self._dialogue.get(uid, [])]
        # D-FC-8 = B: cada turno previo reentra CON su estatus. Una propuesta del modelo aparece como
        # `AURA [PROPUESTA_NO_VERIFICADA]: ...` y nunca desnuda: sin la etiqueta, el modelo leeria su
        # propia salida anterior como si AURA la hubiera afirmado, y la reforzaria turno a turno.
        recent = (
            "\n".join(
                linea_de_contexto(t.usuario, _recortar_respuesta_previa(t.aura, self._RECORTE_AURA), t.estatus)
                for t in buffer
            )
            or "(inicio de la conversacion)"
        )
        prompt = f"[contexto memoria: {ctx}]\n[conversacion reciente:\n{recent}]\nUsuario: {text}"
        # **El catalogo solo si hay accion que pedir.** Ante la duda, `_pide_accion` es generoso:
        # perder una accion seria peor que pagar contexto de mas.
        # Una consulta COGNITIVA nunca carga el catalogo, ni aunque `_pide_accion` sea generoso:
        # medido, el catalogo de acciones era el 71 % del tiempo de ingesta del turno.
        modo = "accion" if (_pide_accion(text) and not cognicion_general) else "cognitivo"
        # **DOMINIO SENSIBLE (D-FC-2 = B).** En salud, derecho, finanzas, personas reales y religion el
        # Core se abstiene de transmitir conocimiento generado: un 0,5 B fabrico una falsedad grave sobre
        # T7 y AURA la habria dicho con su voz. Se decide ANTES de llamar al modelo -0 llamadas, nada que
        # filtrar despues- y solo en modo cognitivo: una orden no es una afirmacion de conocimiento, y
        # sus garantias son las del motor y los permisos.
        sensible = intencion.dominio_sensible(text) if modo == "cognitivo" else None
        if sensible is not None:
            obs.log("CORE", "sensible", f"dominio={sensible} -> abstencion, sin llamada al LLM", tid, audit=True)
            await self._finalizar_turno(
                uid,
                tid,
                text,
                _abstencion_sensible(sensible),
                "core",
                t,
                dominio="sensible",
                estatus=Estatus.ABSTENCION,
            )
            return
        obs.log("LLM", "routing", f"modo={modo}", tid)
        # D-FC-6: acuse inmediato por voz antes de la espera. Es accesorio: si la voz falla, el turno
        # sigue -- perder el acuse no puede costar la respuesta.
        try:
            await self.voice.tts(_ACUSE_CONSULTA_MODELO, tid)
        except Exception as e:
            obs.log("WARN", "voice", f"acuse de espera no emitido (turno no afectado): {e}", tid)
        self._en_modelo.add(tid)
        try:
            try:
                prov, out = await self.router.route(prompt, tid, modo)
            except TypeError:
                # Un router con la firma anterior —los dobles de prueba, por ejemplo— sigue funcionando.
                # El modo es una mejora de contexto, no un cambio de contrato.
                prov, out = await self.router.route(prompt, tid)
        except RuntimeError as e:
            # **LIMITE ALCANZADO != PROVEEDOR CAIDO (DR-3, CEO 2026-09-15).** Antes un timeout llegaba aqui
            # como cualquier fallo y AURA respondia «Mi modelo local no esta disponible» —falso: estaba
            # disponible, solo tardo—. Un limite se dice como lo que es, y el turno NO se rellena con lo
            # que el modelo llevara escrito: una respuesta a medias no se presenta como terminada. Se lee
            # por atributo, igual que la subclase de abajo, para que el nucleo no importe `modules`.
            limite = getattr(e, "limite", None)
            if limite in _ABSTENCION_POR_LIMITE:
                obs.log(
                    "WARN", "router", f"limite '{limite}' alcanzado -> aviso honesto del Core: {e}", tid, audit=True
                )
                self._en_modelo.discard(tid)
                await self._finalizar_turno(
                    uid,
                    tid,
                    text,
                    _ABSTENCION_POR_LIMITE[limite],
                    CORE,
                    t,
                    dominio=f"limite_{limite}",
                    estatus=Estatus.ABSTENCION,
                )
                return
            # `ProveedoresNoDisponibles` es subclase de RuntimeError: se captura por la base para que el
            # nucleo no importe `modules.router` (core no depende de modules). Sin esto el turno moria
            # sin `_done` y `wait` expiraba: el usuario veia un cuelgue, no una respuesta.
            obs.log("WARN", "router", f"sin proveedor utilizable -> abstencion del Core: {e}", tid, audit=True)
            self._en_modelo.discard(tid)
            await self._finalizar_turno(
                uid,
                tid,
                text,
                _ABSTENCION_SIN_PROVEEDOR,
                CORE,
                t,
                dominio="proveedor_no_disponible",
                estatus=Estatus.ABSTENCION,
            )
            return
        finally:
            self._en_modelo.discard(tid)
        t.mark("llm")
        action, args, say = _parse_decision(out, tid)
        # **EL LLM NUNCA EJECUTA (mandato §20: en modo cognitivo, action != ejecutable).** El esquema de
        # `providers_real` ya impide que Ollama nombre una accion al decodificar, pero esa es una
        # barrera DEL PROVEEDOR: otro proveedor, o un doble, podria devolverla igual. ADR-0014 §4: una
        # garantia no puede depender de que un modelo se comporte. Aqui la impone el Core, sin mirar
        # que proveedor respondio: un turno cognitivo nunca llega al motor.
        if modo == "cognitivo" and action != "consulta":
            obs.log("CORE", "cognitivo", f"accion propuesta {action} descartada", tid, audit=True)
            action, args = "consulta", {}
        # **EL MODELO NO ELIGE EL DISPOSITIVO (semana 2).** Medido `[EJEC]`: ante «enciende la tele» el
        # modelo «encendió la luz de la sala». Cuando la superficie de hogar no reconoce la orden (p. ej. un
        # error de transcripción: «Apaga la tele» se oyó «Para la tene»), el turno llega aquí, y el modelo
        # puede proponer encender o apagar. ADR-0014 §4: el modelo no decide QUÉ se toca. Si el dispositivo
        # que propone no lo nombró la persona, no se actúa. No retira la garantía de M1 («lista verde
        # ejecuta»): la limita a lo que el usuario dijo.
        # **POR VOZ, EL MODELO NUNCA ACTÚA EN CASA (opción C, C1-C3).** Medido `[EJEC]` 2026-10-22: una frase hablada sin
        # activación que la gramática del Core no reconocía bajaba aquí y el Motor APAGABA la TV sin propuesta ni «sí».
        # Por voz, la casa solo cambia por la rama del Core: reconocer → proponer nombrando → «sí» activado.
        if por_voz and action in hogar.CAPACIDADES:
            obs.log(
                "CORE", "hogar", f"accion {action} del modelo en turno HABLADO descartada (opcion C)", tid, audit=True
            )
            rechazo = (
                hogar.ORDEN_NO_ENTENDIDA if action in hogar.CAPACIDADES_DE_VOZ else hogar.VOLUMEN_POR_VOZ_PENDIENTE
            )
            await self._finalizar_turno(uid, tid, text, rechazo, CORE, t, dominio="hogar", estatus=Estatus.ABSTENCION)
            return
        if action in hogar.CAPACIDADES and not hogar.dispositivo_nombrado(args.get("device", ""), text):
            obs.log(
                "CORE",
                "hogar",
                f"accion {action} del modelo descartada: {args.get('device')!r} no lo nombro el usuario",
                tid,
                audit=True,
            )
            await self._finalizar_turno(
                uid, tid, text, hogar.SIN_DISPOSITIVO_CLARO, CORE, t, dominio="hogar", estatus=Estatus.ACLARACION
            )
            return
        if action != "consulta":
            evento = {"action": action, "args": args}
            # Las automatizaciones del usuario reaccionan al evento ANTES de ejecutar la accion que lo
            # origino: "guarda ANTES una copia" exige que la copia ocurra antes del borrado. Cada regla
            # disparada recorre el motor (mismo camino, mismos permisos); copiar es verde -> sin confirmacion.
            disparos = await self._disparar_reglas(uid, evento, tid)
            # M2.5 (ALERTA-005): la ejecucion se delega en el motor, unico camino del sistema. El
            # orquestador no llama a ningun adaptador: aqui no hay ruta alternativa que mantener.
            cmd_ev = Event("action.command", tid, uid, evento, causation_id=ev.event_id)
            res = await self.motor.ejecutar(action, args, tid, cmd_ev.event_id, origen="conversacion")
            say = self._redactar_con_reglas(action, args, say, res, disparos)
            # Productor del Centro (MVP): AURA registra, en lenguaje natural, lo que acaba de hacer, para
            # poder contarselo despues al usuario ("¿que ha pasado mientras no estaba?").
            if self.notificaciones is not None:
                self.notificaciones.recibir(notificacion_de_accion(action, args, res))
        await self._finalizar_turno(uid, tid, text, say, prov, t)

    def _sistema_detenido(self) -> bool:
        """True si la parada de emergencia esta armada.

        ALERTA-006: el kill switch solo se comprobaba dentro de `PermissionManager.authorize`, asi que
        alcanzaba unicamente a las rutas que pasan por el motor. La cascada de soberania NO pasa por
        ahi, de modo que con la parada ECHADA AURA seguia borrando datos del usuario —verificado—.
        Bible 5.3 §5 y RN-3 dicen que cuando esta activado NINGUNA accion se ejecuta, sin excepciones.
        """
        kill = getattr(self.perm, "_kill", None)
        return kill is not None and kill.is_engaged()

    async def _atender_modelo_usuario(self, uid: str, text: str) -> str | None:
        """Atiende las cuatro conversaciones de soberania. Devuelve la respuesta, o None si no aplica.

        Fiel al modelo interno (declarado/observado); no infiere ni inventa certezas. "eso" se resuelve
        con el foco: la ultima afirmacion en discusion, o la que el texto mencione explicitamente.
        """
        t = _normalizar(text)
        # M3.2a opción A: resolver primero un export PENDIENTE DE CONFIRMAR. Vive un turno y por `uid`:
        # SOLO una confirmación inequívoca de este usuario lo ejecuta; cualquier otra cosa lo descarta
        # (negativa, cambio de tema, nueva solicitud, afirmación ajena, otro usuario). Exportar es lectura
        # pura: la PARADA no la bloquea (como `ver`). Sin pendiente, una confirmación suelta no hace nada.
        if uid in self._export_pendiente:
            self._export_pendiente.discard(uid)
            if _confirma_export(t):
                obs.log("CORE", "export", "export del modelo CONFIRMADO por el usuario", "-", audit=True)
                return await self.modelo_usuario.exportar(uid)
            # No confirmado: el pendiente queda descartado y el turno sigue su curso normal.
        # Punto D: TODAS las formas del olvido de acciones son una mutacion (T19) y la PARADA las bloquea tambien.
        olvida_acciones = resultado_accion.es_peticion_de_olvido_de_acciones(text)
        if self._sistema_detenido() and olvida_acciones:
            obs.log("KILL", "orchestrator", "soberania: olvido de acciones bloqueado por kill switch", "-", audit=True)
            return "Ahora mismo no puedo modificar lo que sé de ti: el sistema está detenido."
        if self._sistema_detenido() and (_es_peticion_de_olvido(t) or _cae_en(t, _PAT_MODELO_REFUTA)):
            # Inspeccionar sigue permitido: leer no muta nada. Lo que la parada impide es MODIFICAR.
            obs.log("KILL", "orchestrator", "soberania: mutacion bloqueada por kill switch", "-", audit=True)
            return "Ahora mismo no puedo modificar lo que sé de ti: el sistema está detenido."
        if olvida_acciones:
            # T19: «olvida lo que hiciste». Va por la via de soberania (el eco NO se captura: T11) y por el Motor
            # Unico. Antes de `_foco`: no apunta a ninguna entrada del modelo del usuario.
            n = await self.modelo_usuario.olvidar_acciones(uid)
            if n is None:  # el motor NO ejecuto la operacion (detenida o error): no se sabe que habia, y sigue ahi
                return (
                    "No he podido olvidar lo que hice: la operación no se ejecutó (la detuvo un control o falló). "
                    "El registro sigue como estaba."
                )
            if n == 0:
                return "No tenía ningún registro de acciones."
            # Honesto (contrato de olvido §5 / D-AMP-3): es un olvido LOGICO. El borrado fisico no esta implementado.
            return (
                "Hecho. Dejo de usar y de mostrar lo que hice. El borrado físico no está implementado: "
                "el registro sigue en el fichero, aunque ya no lo uso."
            )
        entradas = await self.modelo_usuario.ver(uid)
        vivas = [e for e in entradas if not e.get("refutada")]
        # **PRESENTES: lo que AURA afirma HOY (2026-09-15).** `vivas` incluye las versiones SUPERSEDED de
        # AMP-AURA etapas 1-2, y tiene que incluirlas: el historial se lee de ahi. Pero el foco de «eso»
        # y el blanco de olvidar/refutar NO pueden salir de ellas. Medido: tras redeclarar el cumpleaños,
        # «olvida mi cumpleaños» BORRABA LA VERSION ANTIGUA, respondia «Hecho» y AURA seguia afirmando la
        # vigente —la clase de defecto de ALERTA-006, y una confirmacion falsa (INV-9)—. Aqui se separa lo
        # que se LEE como historial de lo que se PRESENTA y se MODIFICA como presente.
        #
        # Que debe hacer «olvidar» con el historial de un atributo es `D-AMP-3`, SIN DECIDIR: esta
        # separacion no lo decide, solo evita que el olvido caiga sobre una version que ya no era vigente.
        presentes = [e for e in vivas if e.get("valid_until") is None]

        if _es_peticion_de_exportar(t):
            # M3.2a opción A (acta `decisiones/2026-10-11-M3.2a-exportar-confirmacion-opcion-A.md`): la
            # detección NUNCA vuelca el modelo —tres bypass léxicos demostrados (ECC 2026-10-11)—. Pide
            # CONFIRMACIÓN: marca el pendiente y pregunta. Un falso positivo produce a lo sumo esta
            # pregunta, jamás una fuga de PII. El volcado ocurre arriba, solo tras `_confirma_export`.
            self._export_pendiente.add(uid)
            return (
                "Puedo darte una copia de todo lo que sé de ti, en un archivo legible sin AURA. "
                "¿Quieres que la exporte? Dime «sí, exporta» para confirmarlo."
            )

        if _cae_en(t, _PAT_MODELO_VER):
            # Foco por defecto para el "eso" siguiente: la primera observada (la cuestionable); si no,
            # la primera declarada. La declarada no suele necesitar explicacion ("me lo dijiste"). Sale
            # de lo que el listado MUESTRA: un «eso» no puede señalar algo que no se ha dicho en voz alta.
            if presentes:
                self._foco_modelo[uid] = next((e for e in presentes if e.get("origen") != "declarada"), presentes[0])
            return describir_conocimiento(entradas)

        # **EVOCACION DE HECHOS (DR-1 = A, CEO 2026-09-15).** «¿te acuerdas de lo que te dije?» llegaba a
        # la puerta de ADR-0014, que decide con la busqueda LEXICA: sin terminos en comun, 0 resultados y
        # «No tengo ningun recuerdo» —con el modelo de usuario lleno—. Aqui responde el Core desde el
        # modelo de usuario, sin modelo de lenguaje: la existencia de un recuerdo no la decide nunca el
        # LLM (ADR-0014 §2). Solo lo DECLARADO y VIGENTE: ni lo refutado, ni lo superseded, ni lo observado
        # —«lo que te dije» no incluye lo que AURA dedujo—. La puerta de ADR-0014 no se toca.
        if es_evocacion_generica(t):
            declaradas = [e for e in presentes if e.get("origen") == "declarada"]
            if not declaradas:
                return _SIN_HECHOS_DECLARADOS
            # «eso» solo queda enfocado si lo mostrado es UNA sola cosa: con varias, un «olvida eso»
            # posterior seria ambiguo, y ante la duda se pregunta (contencion de ALERTA-006).
            if len(declaradas) == 1:
                self._foco_modelo[uid] = declaradas[0]
            lineas = "\n".join(f"• {e['contenido']}" for e in declaradas)
            return f"Sí. Esto es lo que me has dicho y sigo dando por cierto:\n{lineas}"

        # «¿te acuerdas de mi X?» nombra un atributo: se responde EXACTAMENTE como «¿cual es mi X?», por la
        # misma superficie y con las mismas guardas. Si no hay hecho que dar, cae a la ruta de siempre.
        evocado = atributo_evocado(t)
        if evocado is not None:
            respuesta = self._responder_hecho(f"¿cual es mi {evocado}?", vivas)
            if respuesta is not None:
                return respuesta

        # Consulta de HISTORIAL ("¿cual era mi X?"), ANTES que la del presente. Una pregunta de
        # historial tambien nombra el atributo posesivo, asi que si `_responder_hecho` corriera
        # primero respondiera con el valor VIGENTE y le robaria el turno a esta superficie mas
        # especifica -el usuario pregunto por lo que ERA, no por lo que ES-.
        respuesta = self._responder_historial(t, vivas)
        if respuesta is not None:
            return respuesta

        # Consulta de un ATRIBUTO concreto (incremento A). Va aqui, dentro de la soberania del Modelo
        # de Usuario, porque la fuente es la misma: no se crea ninguna ruta nueva (regla 3 del acta).
        # Solo se leen entradas VIVAS: un hecho refutado dejo de darse por cierto (regla 5).
        respuesta = self._responder_hecho(t, vivas)
        if respuesta is not None:
            return respuesta

        if _es_peticion_de_olvido(t):  # antes que refutar/porque: "olvida" es inequivoco
            foco = self._foco(uid, t, presentes, entradas, vivas)
            if foco is None:
                # ALERTA-006: antes se elegia `vivas[0]` y se confirmaba el borrado. Ante la duda se
                # pregunta; destruir el dato equivocado no es soberania del usuario, es perdida.
                return _DESAMBIGUAR
            # DR-2: se olvida LA entrada señalada, no todo lo que contenga su texto.
            n = await self.modelo_usuario.olvidar_entrada(uid, foco)
            return (
                "Hecho. Ya no lo consideraré parte de lo que sé de ti." if n else "No he encontrado eso para olvidarlo."
            )

        if _cae_en(t, _PAT_MODELO_REFUTA):
            foco = self._foco(uid, t, presentes, entradas, vivas)
            if foco is None:
                return _DESAMBIGUAR
            # Se comprueba el retorno: `refutar` puede no mutar nada (p.ej. si ya estaba refutada), y
            # narrar exito sin efecto viola INV-9 / ALERTA-005 punto 4. `borrar` ya lo comprobaba.
            n = await self.modelo_usuario.refutar_entrada(uid, foco)
            if n:
                return "Entendido, lo corrijo. Dejo de darlo por cierto."
            return "No he encontrado eso para corregirlo."

        if _cae_en(t, _PAT_MODELO_PORQUE):
            foco = self._foco(uid, t, presentes, entradas, vivas)
            return explicar_entrada(foco) if foco else "Ahora mismo no estoy afirmando nada sobre ti."

        return None

    @staticmethod
    def _responder_historial(t: str, vivas: list[dict]) -> str | None:
        """Responde una consulta de HISTORIAL sobre un atributo declarado, o None si no aplica.

        AMP-AURA etapas 1-2: el Core ya versiona un atributo redeclarado -`version`, `valid_until`-,
        pero eso solo se podia INSPECCIONAR con `ModeloUsuario.ver()`, nunca preguntar en conversacion.
        Esta es la superficie de LECTURA de ese historial, simetrica a `_responder_hecho` y con las
        mismas dos guardas: solo `HECHO_DECLARADO` (una observacion no es una declaracion del usuario)
        y solo entradas VIVAS (un hecho refutado dejo de darse por cierto, regla 5 del acta).

        INV-9: sin ninguna entrada del atributo, se devuelve None -no un texto de ausencia propio, que
        le robaria el turno a la puerta de ADR-0014, exactamente el mismo criterio que documenta
        `_responder_hecho`-.
        """
        atributo = atributo_preguntado_en_pasado(t)
        if atributo is None:
            return None
        atributo_norm = _normalizar(atributo)

        # (version, atributo_escrito, valor, vigente). Los VALORES y el nombre del atributo se toman
        # de la frase del propio usuario via `_atributo_declarado`, con SU ortografia (ADR-0017): no
        # se reformula ni se normaliza lo que el usuario dijo.
        pares = []
        for entrada in vivas:
            if entrada.get("clase") != ClaseSenal.HECHO_DECLARADO.value:
                continue
            par = _atributo_declarado(str(entrada.get("contenido", "")))
            if par is None or _normalizar(par[0]) != atributo_norm:
                continue
            version = int(entrada.get("version") or 1)
            pares.append((version, par[0], par[1], entrada.get("valid_until") is None))

        if not pares:
            return None

        anteriores = sorted((p for p in pares if not p[3]), key=lambda p: p[0])
        actuales = [p for p in pares if p[3]]
        # Si hubiera mas de una vigente -no deberia, el ejecutor cierra la anterior al escribir-, la
        # de version mayor es la que manda: mismo criterio de "la ultima declaracion gana" que ya usa
        # `_responder_hecho`.
        actual = max(actuales, key=lambda p: p[0]) if actuales else None

        # La ortografia sale de la entrada de la que sale la respuesta: la actual si existe, si no la
        # ultima anterior.
        atributo_escrito = (actual or anteriores[-1])[1]

        # Una redeclaracion IDENTICA no es otro valor anterior: medido `[EJEC]` el 2026-09-27, «me llamo
        # Mauricio» dicho dos veces daba «Antes me dijiste: Mauricio, Mauricio». Se colapsan solo las
        # repeticiones CONSECUTIVAS, en orden de version: Valencia -> Sevilla -> Valencia SI son tres
        # estados y se cuentan los tres. Es proyeccion (`ADR-0023`): el historial conserva cada
        # declaracion.
        sin_repetir = [p[2] for i, p in enumerate(anteriores) if i == 0 or p[2] != anteriores[i - 1][2]]
        if actual is not None and anteriores:
            valores_anteriores = ", ".join(sin_repetir)
            return f"Ahora tu {atributo_escrito} es {actual[2]}. Antes me dijiste: {valores_anteriores}."
        if actual is None:
            valores_anteriores = ", ".join(sin_repetir)
            return (
                f"Antes me dijiste que tu {atributo_escrito} era {valores_anteriores}. "
                "Ahora mismo no tengo ninguno vigente."
            )
        return f"Solo me has dicho una cosa sobre tu {atributo_escrito}: {actual[2]}. No me habías dicho otra antes."

    @staticmethod
    def _responder_hecho(t: str, vivas: list[dict]) -> str | None:
        """Responde una consulta de atributo desde el MODELO DE USUARIO, o None si no es una de ellas.

        INV-9: si el atributo no se ha declarado, se dice -no se infiere de otras entradas ni se
        deja que la pregunta caiga al recall, que respondería por parecido de texto-.
        """
        # Solo entradas de clase HECHO_DECLARADO: emparejar el regex contra CUALQUIER entrada viva
        # devolvia como hecho lo que era una preferencia o un patron observado, borrando la
        # distincion declarado/observado que la ampliacion de 4.4 §1 existe para preservar.
        # Y solo las VIGENTES: una entrada con `valid_until` fue superseded por una redeclaracion y
        # pertenece al historial, no al presente (AMP-AURA etapas 1-2). Sin este filtro la respuesta
        # correcta dependeria del ORDEN de llegada —el `reversed` de abajo—, que es una coincidencia
        # afortunada, no una garantia: basta que el almacen devuelva otro orden para que AURA afirme
        # un hecho caducado. Las entradas heredadas no tienen el campo, valen None y siguen vigentes.
        hechos = [
            e for e in vivas if e.get("clase") == ClaseSenal.HECHO_DECLARADO.value and e.get("valid_until") is None
        ]
        for preguntas, patron, plantilla, ausencia in _CONSULTAS_DE_HECHO:
            if not _cae_en(t, preguntas):
                continue
            # La ULTIMA declaracion gana: redeclarar es el gesto natural de corregirse, y devolver
            # la primera hacia que "me llamo Pedro" seguido de "mi nombre es Mauricio" respondiera
            # todavia "Pedro".
            for entrada in reversed(hechos):
                valor = _valor_declarado(str(entrada.get("contenido", "")), patron)
                if valor:
                    return plantilla.format(valor)
            return ausencia

        # EMPAREJAMIENTO SIMETRICO. Va al final a proposito: la tabla de arriba conserva su texto de
        # ausencia especifico y las preferencias su rama, y esto solo atiende lo que ninguna cubria.
        atributo = _atributo_preguntado(t)
        if atributo is not None:
            # La ULTIMA declaracion gana, por el mismo motivo que en la tabla: redeclarar es como uno
            # se corrige.
            for entrada in reversed(hechos):
                par = _atributo_declarado(str(entrada.get("contenido", "")))
                # El atributo se compara NORMALIZADO y se responde con la forma que el usuario escribio.
                if par and _normalizar(par[0]) == atributo:
                    return f"Tu {par[0]} es {par[1]}."
            # SIN correspondencia NO se responde aqui: devolver un texto de ausencia propio robaria el
            # turno a la puerta de ADR-0014, que es quien decide que hacer cuando no hay recuerdo. No
            # inventar tambien significa no adelantarse a la ruta segura que ya existe.

        if _cae_en(t, _PAT_CONSULTA_PREFERENCIA):
            declaradas = [e["contenido"] for e in vivas if e.get("clase") == "preferencia_declarada"]
            if not declaradas:
                return "Todavía no me has dicho qué prefieres."
            return "Esto es lo que me has dicho que prefieres:\n" + "\n".join(f"• {d}" for d in declaradas)
        return None

    def _foco(
        self,
        uid: str,
        t: str,
        vivas: list[dict],
        existentes: list[dict] | None = None,
        historial: list[dict] | None = None,
    ) -> dict | None:
        """Resuelve "eso": la entrada que el texto menciona, o la ultima en discusion. None si es ambiguo.

        Contencion de ALERTA-006. Antes terminaba en `vivas[0]`: si el texto no mencionaba nada
        reconocible, se actuaba sobre la PRIMERA entrada viva, que no tiene por que guardar relacion
        alguna con lo pedido. Verificado: "Olvida que a mi hermana le gusta el cafe" borraba una
        preferencia propia del usuario y AURA confirmaba "Hecho".

        Devolver None NO es un fallo: es la respuesta correcta a una peticion ambigua, y quien llama
        debe pedir desambiguacion. "Ante la duda, roja" (ADR-0003) aplicado a los datos del usuario.

        El foco cacheado se valida contra las entradas que EXISTEN, no contra las vivas. La
        distincion importa y costo una regresion: tras "eso ya no es cierto" la entrada queda
        refutada y sale de `vivas`, pero el "olvida eso" siguiente se refiere justamente a ella
        —refutar no es borrar—. Validar contra `vivas` rompia esa secuencia legitima; validar contra
        las existentes solo descarta el foco cuando apunta a algo que ya no esta en el modelo.

        **VIGENCIA (AMP-AURA etapas 1-2, auditoria independiente del 2026-09-15).** Dos reglas mas, ambas
        medidas contra un defecto real:

        1. Al NOMBRAR, lo vigente tiene preferencia y el `historial` va despues. Tras redeclarar un
           atributo las dos versiones comparten palabras; recorrerlas juntas hacia que «olvida mi
           cumpleaños» cayera sobre la version antigua. Pero el historial no puede quedar fuera de alcance:
           si nada vigente coincide y una version superseded si («olvida lo de Bangkok»), se atiende
           —en `6dad6af` se podia, y quitarlo seria una regresion de soberania (ADR-0017)—.
        2. El foco CACHEADO solo vale si su entrada sigue VIGENTE. Si entre el turno que lo fijo y este
           el usuario redeclaro el atributo, «eso» ya no señala nada vigente, y actuar sobre la version
           recien cerrada es la clase de defecto de ALERTA-006. Las refutadas SIGUEN valiendo —refutar no
           cierra la vigencia—, que es lo que mantiene la secuencia «refutar → olvidar eso».

        **SIN AMBIGUEDAD (auditoria independiente del 2026-09-15; defectos preexistentes en `6dad6af`).**
        Se coincide por PALABRA COMPLETA y gana la entrada con MAS palabras coincidentes; un empate se
        pregunta (None). Antes se comparaba por SUBCADENA (`w in t`) y ganaba la primera coincidencia:
        «olvida lo de valenciana» borraba «mi ciudad favorita es Valencia» —«valencia» esta dentro de
        «valenciana»— y «olvida lo de cartagena», con dos entradas que la nombraban, borraba una
        cualquiera. Las dos respondian «Hecho». Un empate DENTRO de lo vigente no cae al historial: la
        ambiguedad no se resuelve buscando en otra parte.
        """
        # Palabras reales, no trozos separados por espacios: «Olvida lo de las facturas.» dejaba «facturas.»
        # con el punto pegado, y la coincidencia por palabra completa fallaba (lo detectaron cuatro pruebas
        # de la contencion de ALERTA-006 en cuanto se cambio la regla).
        palabras_texto = set(re.findall(r"\w+", t))
        for grupo in (vivas, historial or ()):
            puntuadas = []
            for e in grupo:
                palabras = {w for w in re.findall(r"\w+", _normalizar(e["contenido"])) if len(w) > 4}
                coincidencias = len(palabras & palabras_texto)
                if coincidencias:
                    puntuadas.append((coincidencias, e))
            if not puntuadas:
                continue
            mejor = max(p for p, _ in puntuadas)
            ganadoras = [e for p, e in puntuadas if p == mejor]
            if len(ganadoras) > 1:
                return None
            self._foco_modelo[uid] = ganadoras[0]
            return ganadoras[0]
        cacheado = self._foco_modelo.get(uid)
        if cacheado is None:
            return None
        universo = vivas if existentes is None else existentes
        return (
            cacheado
            if any(x["contenido"] == cacheado["contenido"] and x.get("valid_until") is None for x in universo)
            else None
        )

    def _resumen_notificaciones(self) -> str:
        """Lo que AURA hizo desde la ultima vez, en lenguaje natural (comunicable, no un log).

        Orden CRONOLOGICO: "¿que ha pasado?" se narra en el orden en que ocurrio, no por criticidad
        (la priorizacion de `listar()` es para una bandeja, no para contar una secuencia de hechos).
        """
        items = sorted(self.notificaciones.listar(), key=lambda n: n.ts)
        if not items:
            return "No ha pasado nada relevante mientras no estabas."
        lineas = "\n".join(f"• {n.titulo}" for n in items)
        return f"Desde la última vez:\n{lineas}"

    # ----------------------------------------- Conversacion General v1 (CEO, 06f53f3) --

    async def _atender_conversacion_general(self, uid: str, text: str) -> str | None:
        """Compone la respuesta del turno a partir de su SECUENCIA de intenciones, o None si el turno
        no es enteramente reconocible (entonces sigue el camino que ya existia).

        Tres reglas del contrato, en este orden:
          - AMBIGÜEDAD REAL -> se pregunta. Una frase de dos dominios donde responder uno implica
            ignorar el otro no se resuelve adivinando.
          - MULTIPLICIDAD -> se responden TODAS las principales, en el orden formulado, sin
            preguntar: "si las dos intenciones pueden resolverse, prefiero una respuesta mas larga
            antes que interrumpir la conversacion" (CEO).
          - Una principal NO RESOLUBLE (p.ej. pendientes sin Estado Operativo conectado) anula el
            turno entero: mejor seguir como hoy que contestar media pregunta.
        """
        secuencia = _secuencia_de_intenciones(text)
        if secuencia is None:
            return None
        secuencia = _sin_repeticiones(secuencia)

        prefijo = self._prefijo_de_modificadoras(secuencia)

        cuerpos = []
        for clase, nombre, _ in secuencia:
            if clase == "ambigua":
                # La ambigua ocupa SU posicion en la secuencia y no anula el resto: una intencion
                # resoluble no puede perderse porque otra sea ambigua (rechazo de auditoria).
                cuerpos.append(_ACLARACION_APRENDIDO_DE_MI)
                continue
            if clase != "principal":
                continue
            cuerpo = self._responder_intencion(nombre)
            if cuerpo is None:
                return None
            cuerpos.append(cuerpo)

        if not cuerpos:
            if not prefijo:
                return None
            hay_saludo = any(nombre == "saludo" for _, nombre, _ in secuencia)
            return self._unir(prefijo, [_OFRECIMIENTO_TRAS_SALUDO] if hay_saludo else [])
        return self._unir(prefijo, cuerpos)

    @staticmethod
    def _unir(prefijo: list[str], cuerpos: list[str]) -> str:
        return "\n".join([*prefijo, *cuerpos])

    def _responder_intencion(self, nombre: str) -> str | None:
        """Texto de UNA intencion principal, o None si esa intencion no es resoluble ahora mismo.

        Las intenciones que tienen fuente real (capacidades, pendientes) delegan en la MISMA funcion
        que ya las respondia: no se duplica ni se reescribe ningun hecho del sistema (ADR-0014 §1).
        """
        if nombre == "identidad":
            return _RESPUESTA_IDENTIDAD
        if nombre == "proposito":
            return _RESPUESTA_PROPOSITO
        if nombre == "ofrecimiento":
            return _RESPUESTA_OFRECIMIENTO
        if nombre == "capacidades":
            return self._describir_capacidades()
        if nombre == "pendientes":
            # Sin Estado Operativo conectado no se puede afirmar que no hay nada pendiente: se
            # ignora, como ya hace la ventana del SO cuando el componente no esta cableado (INV-9).
            if self.estado_operativo is None:
                return None
            return self._describir_tareas() if self._secciones_del_ciclo() else _SIN_PENDIENTES
        return None

    @staticmethod
    def _prefijo_de_modificadoras(secuencia: list[tuple[str, str, str]]) -> list[str]:
        """Las modificadoras no consumen el turno: aportan las lineas que anteceden a la respuesta.

        Sin nombre propio: ver la nota de `_VAR_SALUDO` sobre por que se retiro (INV-9).
        """
        lineas = []
        for clase, nombre, variante in secuencia:
            if clase != "modificadora":
                continue
            if nombre == "saludo":
                lineas.append(f"{_VAR_SALUDO[variante]}.")
            elif nombre == "cortesia":
                lineas.append(_RESPUESTA_CORTESIA)
            elif nombre == "despedida":
                lineas.append(_RESPUESTA_DESPEDIDA)
        return lineas

    # ----------------------------------------- ventana del SO Interno (M3 entry) --

    async def _atender_orden_de_capacidad(self, uid: str, text: str, tid: str) -> str | None:
        """El usuario PIDE una capacidad registrada: se ejecuta de verdad. `None` si no la pide.

        EL HUECO QUE CIERRA, medido antes de escribirlo `[EJEC]`: AURA declaraba 21 operaciones con
        sus adaptadores montados, y a *«ejecuta las pruebas»* respondía *«Esto lo genera mi modelo
        local y no está verificado: Entendido.»*. Capacidad registrada, ejecutor construido, permiso
        clasificado, Motor Único funcionando — y ninguna ruta desde la conversación hasta ellos.

        **Toda la ejecución pasa por el motor** (`ALERTA-005`): este método no llama a ningún
        adaptador. Reconoce, delega y cuenta el resultado. Si mañana el motor niega la capacidad
        —kill switch, permisos, lista roja—, aquí no hay forma de saltárselo, porque no hay otra
        puerta.

        **Va DESPUÉS de las superficies conversacionales** por la misma razón que ellas van después
        de las de soberanía: una superficie nueva no puede robarle frases a las que ya existían. Y
        cuando no reconoce, devuelve `None` y el turno sigue **exactamente** el camino de antes.
        """
        if self.motor is None or self.registro is None:
            return None
        # **Primero las ordenes CON ruta, y sobre el texto ORIGINAL.** `_partir_en_partes` normaliza
        # —minusculas, sin tildes, partiendo por el punto—, y una ruta que pase por ahi deja de
        # existir: `Documentos` se vuelve `documentos` y `~/Musica/notas.TXT` se parte en dos.
        con_ruta = ordenes.reconocer_con_ruta(text, self.registro.capacidades())
        if con_ruta is not None:
            capacidad, ruta = con_ruta
            return await self._despachar_orden(uid, capacidad, {_ARG_RUTA[capacidad]: ruta}, tid)

        partes = _partir_en_partes(text)
        if len(partes) != 1:
            # Un turno con varias frases no es una orden limpia. Ante la duda, no se ejecuta: es la
            # misma regla que el resto del plano (`ADR-0003`), aplicada a la puerta de entrada.
            return None
        compuesta = ordenes.reconocer_compuesta(partes[0], self.registro.capacidades())
        if compuesta is not None:
            return await self._despachar_revision(uid, compuesta, tid)

        simple = ordenes.reconocer(partes[0], self.registro.capacidades())
        if simple is None:
            return None
        return await self._despachar_orden(uid, simple, ordenes.argumentos_de(simple), tid)

    async def _responder_recuperacion(self, uid: str, tid: str, text: str, t, clase: str) -> None:
        """Recupera lo que AURA hizo, sin volver a ejecutarlo (M8 + punto D). Un solo sitio para los dos puntos de la
        cascada que lo usan. Cascada: ventana de trabajo (M8, sin cambios) -> registro persistido -> ausencia sin
        «nunca». «Antes de reiniciarte» solo puede contestarlo el registro, aunque la ventana tenga ejecuciones
        nuevas. **El motor recibe CERO llamadas**: leer nunca re-ejecuta."""
        turno_previo = recuperacion.ultima_ejecucion(self._dialogue.get(uid, []))
        del_registro = clase == recuperacion.PREGUNTA_ANTES_DEL_REINICIO or turno_previo is None
        if del_registro:
            resp, estatus_rec, resumen = self._recuperar_del_registro(uid, tid, clase)
            origen = "persistido"
        else:
            resp, estatus_rec = recuperacion.redactar(clase, turno_previo)
            resumen = turno_previo.resumen_prompt if turno_previo else ""
            origen = "ventana"
        obs.log(
            "CORE",
            "recuperacion",
            f"pregunta por ejecucion anterior ({clase}): "
            f"{'recuperada' if estatus_rec is not Estatus.AUSENCIA else 'sin ejecucion que recuperar'} "
            f"({origen}), sin LLM",
            tid,
            audit=True,
            origen=origen,
        )
        await self._finalizar_turno(
            uid, tid, text, resp, "core", t, dominio="recuperacion", estatus=estatus_rec, resumen_prompt=resumen
        )

    def _recuperar_del_registro(self, uid: str, tid: str, clase: str) -> tuple[str, Estatus, str]:
        """(respuesta, estatus, resumen para el prompt) desde `resultado_accion`. Cada registro se redacta con
        `describir_desenlace`, la MISMA funcion del turno en vivo. Lo que no valida se ignora y se audita."""
        registros = resultado_accion.leer_auditando(self.memory, uid, tid)
        if clase == recuperacion.PREGUNTA_ANTES_DEL_REINICIO:
            propios = self._persistidos_en_proceso()
            registros = [r for r in registros if r["trace_id"] not in propios]
        # Nunca mas de lo que la ventana de trabajo ya aprobada (DR-4) retendria: sin numero nuevo que justificar.
        lineas = [
            f"{resultado_accion.hora_legible(r)}: {self._texto_de_registro(r)}" for r in registros[-self._DIALOG_MAX :]
        ]
        resp, estatus = recuperacion.redactar_persistido(clase, lineas)
        return resp, estatus, recuperacion.RESUMEN_PROMPT_REGISTRO if lineas else ""

    def _texto_de_registro(self, registro: dict) -> str:
        """Un registro persistido, con la redaccion compartida. Lo que el registro no conserva (el motivo, el
        resumen) se dice que no se conserva: no se inventa."""
        capacidad, desenlace = registro["capacidad"], registro["desenlace"]
        de_hogar = capacidad in resultado_accion.CAPACIDADES_DE_HOGAR
        texto = describir_desenlace(
            capacidad,
            desenlace,
            motivo="no conservo el motivo",
            resumen="no conservo el detalle",
            detalle_hogar=resultado_accion.detalle_reconstruido(registro) if de_hogar else None,
            nombres=getattr(self, "nombres_de_voz", None),
            modo="registro",
            elementos=registro["elementos"],
        )
        return texto or ""

    async def _despachar_revision(self, uid: str, capacidades, tid: str) -> str:
        """Varias capacidades reales, una respuesta. **Cada una por su propia puerta.**

        `Componer no concede autoridad`: no hay un despacho «de revisión» que ejecute en bloque, sino
        el mismo `_despachar_orden` repetido. Si una capacidad queda bloqueada —kill switch,
        permisos—, se bloquea sola y **la revisión lo dice**: presentar un informe completo cuando
        una parte no llegó a mirarse sería «declarado ≠ real» con la firma de AURA debajo."""
        hallazgos: list[tuple[str, dict]] = []
        for capacidad in capacidades:
            ev = Event("action.command", tid, uid, {"action": capacidad, "args": {}})
            res = await self.motor.ejecutar(
                capacidad, ordenes.argumentos_de(capacidad), tid, ev.event_id, origen="conversacion"
            )
            hallazgos.append((capacidad, res if isinstance(res, dict) else {}))
        obs.log("CORE", "orden", f"revision compuesta de {len(hallazgos)} capacidad(es)", tid, audit=True)
        return _redactar_revision(hallazgos)

    def _rechazo_de_voz(self, por_voz: bool, activado: bool, tid: str, que: str) -> str | None:
        """La frontera voz -> accion (DP-VOZ-ACCION C1 y C4): el texto del rechazo, o None si el turno pasa.

        Un turno ESCRITO no pasa por aqui (rige la regla M1). Uno hablado exige que haya seguido a la
        palabra de activacion y que el STT no haya dudado de lo que oyo."""
        if not por_voz:
            return None
        if not activado:
            obs.log("CORE", "hogar", f"{que} sin activacion: no actua ni propone", tid, audit=True)
            return hogar.PIDE_ACTIVACION
        if hogar.confianza_baja(getattr(self.voice, "ultima_confianza", None)):
            obs.log("CORE", "hogar", f"{que} con confianza de STT baja: se pide repetir", tid, audit=True)
            return hogar.PIDE_REPETIR
        return None

    async def _consultar_estado_de_hogar(self, consulta: tuple[str, str], por_voz: bool, tid: str):
        """(respuesta, estatus) de una consulta de estado de la TV. Solo lectura por el puerto del adaptador, como
        `entidades()`; responde también con la PARADA echada, porque leer no muta nada, y lo dice. El título de lo
        que se ve NO va al audit log (rastro del consumo de la familia)."""
        aspecto, dispositivo = consulta
        leer = getattr(self.registro.para("encender_dispositivo"), "estado_actual", None)
        if leer is None:
            return hogar.CONSULTA_SIN_HOGAR_REAL, Estatus.ABSTENCION
        objetivo = hogar.entidad_por_nombre_humano(dispositivo, self.nombres_de_voz) or dispositivo
        try:
            estado = await asyncio.to_thread(leer, objetivo)
        except ErrorDeValidacion as e:  # dispositivo ambiguo o inexistente, credencial rechazada
            return f"No he podido consultarlo: {e}.", Estatus.ABSTENCION
        except Exception as e:
            obs.log("WARN", "hogar", f"Home Assistant no respondio a la consulta de estado: {e}", tid, audit=True)
            return "No he podido consultar Home Assistant (no respondió); no sé cómo está.", Estatus.ABSTENCION
        nombre = self.nombres_de_voz.get(estado["entity_id"]) or estado["nombre"]
        obs.log(
            "CORE",
            "hogar",
            f"consulta {aspecto} de {estado['entity_id']}: {estado.get('state')} (lectura)",
            tid,
            audit=True,
        )
        resp = hogar.describir_estado(aspecto, nombre, estado, por_voz)
        if self._sistema_detenido():
            resp += " La parada de emergencia está echada: no ejecuto acciones, pero leer el estado sí puedo."
        return resp, Estatus.HECHO

    async def _entidad_para_voz(self, capacidad: str, dispositivo: str, tid: str):
        """(entity_id, nombre) sobre el que actuaria una orden HABLADA, resuelto ANTES de proponer y SOLO
        dentro de `voz_actua_en` (C2/C3); o el texto del rechazo. Usa la resolucion del adaptador de hogar:
        no hay un segundo resolutor de Home Assistant."""
        resolver = getattr(self.registro.para(capacidad), "resolver_dispositivo", None)
        if resolver is None or not self.voz_actua_en:
            obs.log("CORE", "hogar", f"{dispositivo!r} fuera de voz_actua_en: no se propone", tid, audit=True)
            return hogar.FUERA_DE_ALCANCE
        try:
            return await asyncio.to_thread(resolver, dispositivo, self.voz_actua_en)
        except ErrorDeValidacion as e:
            obs.log("CORE", "hogar", f"{dispositivo!r} fuera de voz_actua_en ({e}): no se propone", tid, audit=True)
            return hogar.FUERA_DE_ALCANCE
        except Exception as e:
            obs.log("WARN", "hogar", f"Home Assistant no respondio al resolver {dispositivo!r}: {e}", tid, audit=True)
            return hogar.HA_NO_RESPONDE

    async def _despachar_orden(self, uid: str, capacidad: str, args: dict, tid: str) -> str:
        """El despacho, en UN solo sitio para las dos formas de orden —con ruta y sin ella—.

        Tenerlo duplicado habria sido la clase de cableado que se olvida en una rama: la leccion de
        ALERTA-005 y la de `AI-M2`, que sobrevivio justamente porque cada camino conectaba su propia
        proteccion. Aqui hay una puerta y las dos formas pasan por ella."""
        ev = Event("action.command", tid, uid, {"action": capacidad, "args": args})
        # PARADA se lee UNA vez, ANTES del motor (punto D, requisito 4): lo que se persiste depende del estado con
        # el que la orden fue evaluada, no de uno que pudo cambiar mientras el motor trabajaba.
        parada = self._sistema_detenido()
        res = await self.motor.ejecutar(capacidad, args, tid, ev.event_id, origen="conversacion")
        # **El registro forense cuenta lo que PASO, no lo que se pidio.** Esta linea decia
        # «ejecutada» siempre, incluso sobre ordenes que el motor habia DETENIDO o que habian dado
        # ERROR. Encontrado leyendo el audit log real `[EJEC]` el 2026-09-21, dos lineas seguidas
        # del mismo turno:
        #     seq 1047  ERROR ejecutor  ERROR leer_archivo: ruta fuera del ambito permitido
        #     seq 1048  CORE  orden     capacidad leer_archivo ejecutada por orden del usuario
        # Al usuario ya se le contaba bien —`_redactar_resultado_de_orden` distingue los tres
        # estados—, asi que el defecto vivia SOLO en la prueba forense: el sitio donde nadie mira
        # hasta que hay que reconstruir que ocurrio, y donde una mentira dura para siempre.
        # Es `ALERTA-005` punto 4 («nunca informa exito sin resultado real») e `INV-9` aplicados al
        # registro que AURA escribe sobre si misma.
        estado = res.get("estado") if isinstance(res, dict) else None
        desenlace = {"ejecutada": "ejecutada", "detenida": "detenida", "error": "error"}.get(
            str(estado), f"con desenlace no reconocido ({estado!r})"
        )
        obs.log("CORE", "orden", f"capacidad {capacidad} {desenlace} por orden del usuario", tid, audit=True)
        # El efecto real realimenta la capa de conocimiento del entorno (misión CEO 2026-09-27): lo que
        # AURA comprobó que puede afectar sube a EFECTO_VERIFICADO. Solo el efecto real lo fija.
        detalle = res.get("resultado") if isinstance(res, dict) else None
        # `getattr`: una prueba de superficie construye el orquestador con `__new__`, sin `entorno`.
        entorno_vivo = getattr(self, "entorno", None)
        if (
            entorno_vivo is not None
            and (capacidad in _CAPACIDADES_DE_HOGAR or capacidad in _CAPACIDADES_DE_VOLUMEN)
            and isinstance(detalle, dict)
            and detalle.get("device")
        ):
            entorno_vivo.registrar_efecto(detalle["device"], bool(detalle.get("verificado")))
        texto = _redactar_resultado_de_orden(capacidad, res, getattr(self, "nombres_de_voz", None))
        if capacidad in CAPACIDADES_QUE_DEVUELVEN_CONTENIDO:
            # Punto D, requisito 11: el CONTENIDO del fichero no reentra en el prompt de turnos posteriores. La
            # recuperacion a peticion (M8, misma conversacion) sigue repitiendolo desde la ventana.
            self._resumen_del_turno()[tid] = (
                describir_desenlace(
                    capacidad, "ejecutada", modo="prompt", elementos=resultado_accion.elementos_de(detalle)
                )
                or ""
            )
        if not await self._persistir_resultado(uid, capacidad, res, tid, parada):
            texto += " " + _AVISO_SIN_REGISTRO
        return texto

    async def _persistir_resultado(self, uid: str, capacidad: str, res: object, tid: str, parada: bool) -> bool:
        """Escribe el registro de resultado de accion DESPUES del desenlace del motor (requisito 4). `True` si la
        accion queda sin problema de registro (escrito, o no procede escribirlo por diseño); `False` solo si
        FALLO la escritura, caso en el que AURA lo dice (INV-9) y la accion NO pasa a fallida (requisito 5).

        Un solo punto de escritura, con la guarda de PARADA por `es_escritura_pasiva` (no un `if` propio:
        ALERTA-005). `RESULTADO_ACCION` no es pasivo, asi que con PARADA no se persiste nada."""
        if parada and not es_escritura_pasiva(RESULTADO_ACCION):
            obs.log("CORE", "parada", f"escritura NO pasiva bloqueada por PARADA: {RESULTADO_ACCION}", tid, audit=True)
            return True
        registro, motivo = resultado_accion.construir(capacidad, res, tid)
        if registro is None:
            obs.log(
                "CORE",
                "resultado",
                f"registro de {capacidad} no persistido: {motivo}",
                tid,
                audit=True,
                evento="resultado.no_persistido",
                capacidad=capacidad,
                motivo=motivo,
            )
            # Dominio de seguridad: exclusion POR DISEÑO, no un fallo, sin aviso. Un registro invalido si es fallo.
            return motivo == resultado_accion.MOTIVO_DOMINIO_DE_SEGURIDAD
        try:
            await self.memory.write(
                uid, RESULTADO_ACCION, resultado_accion.a_contenido(registro), {"trace_id": tid, "fuente": "ejecucion"}
            )
        except Exception as e:  # noqa: BLE001 - cualquier fallo de disco: la accion YA ocurrio y no se deshace
            obs.log(
                "WARN",
                "resultado",
                f"registro de {capacidad} NO persistido ({type(e).__name__}); la accion no se ve afectada",
                tid,
                audit=True,
                evento="resultado.no_persistido",
                capacidad=capacidad,
                desenlace=registro["desenlace"],
                motivo="fallo_de_escritura",
            )
            return False
        self._persistidos_en_proceso().add(tid)
        obs.log(
            "CORE",
            "resultado",
            f"registro de {capacidad} persistido",
            tid,
            audit=True,
            evento="resultado.persistido",
            capacidad=capacidad,
            desenlace=registro["desenlace"],
        )
        return True

    def _resumen_del_turno(self) -> dict[str, str]:
        """Resumen que SUSTITUYE al texto de AURA en el prompt, por turno (`tid`). Se crea perezosamente: las
        pruebas de superficie construyen el orquestador con `__new__`, sin pasar por `__init__`."""
        return self.__dict__.setdefault("_resumenes_de_prompt", {})

    def _persistidos_en_proceso(self) -> set[str]:
        """`trace_id` de los registros escritos por ESTE proceso: lo que NO es «antes de reiniciarte»."""
        return self.__dict__.setdefault("_registros_de_este_proceso", set())

    def _describir_capacidades(self) -> str:
        """Responde "¿que capacidades tienes?" / "¿que puedes hacer?" con el registro de
        adaptadores REAL (`self.registro`), la misma fuente que `--verificar` imprime al arrancar.
        Ninguna capacidad se afirma sin que un adaptador la haya declarado (ALERTA-005): no se
        inventa una lista, se lee la que existe.
        """
        caps = sorted(self.registro.capacidades())
        if not caps:
            return "Ahora mismo no tengo ninguna capacidad registrada."
        return f"Tengo {len(caps)} capacidad(es) registradas:\n" + "\n".join(f"• {c}" for c in caps)

    def _secciones_del_ciclo(self) -> list:
        """Secciones de `centro_gobierno.panel()` para TODOS los objetivos activos, o `[]` si no
        hay ninguno. Fuente UNICA para las dos preguntas de esta seccion (tareas y bloqueo): ambas
        leen el mismo calculo, nunca lo repiten (CLAUDE.md: reutilizar antes que crear)."""
        activos = self.estado_operativo.objetivos_activos()
        if not activos:
            return []
        return panel(estado=self.estado_operativo, objetivo=activos)

    @staticmethod
    def _resumen_de(secciones: list, *sufijos: str) -> str:
        """Texto de las secciones cuyo TITULO termina en alguno de los sufijos pedidos. El prefijo
        "[objetivo] " que `panel()` antepone cuando hay varios objetivos activos no afecta al
        filtro: el sufijo es el nombre estable de la seccion (ver `centro_gobierno.panel`)."""
        filtradas = [s for s in secciones if any(s.titulo.endswith(suf) for suf in sufijos)]
        return "\n".join(f"• {s.titulo}: {s.contenido}" for s in filtradas)

    def _describir_tareas(self) -> str:
        """Responde "¿que tareas tienes?" / "¿en que estas trabajando?" leyendo el Estado
        Operativo REAL del ciclo de AURORA (`estado_operativo.py`). Fiel al estado interno
        (INV-7: el plan no se reinterpreta): sin ningun objetivo activo, se declara -no se
        inventa trabajo en curso-.
        """
        # El ciclo autonomo manda cuando esta disponible: es donde de verdad ocurre el trabajo de
        # AURORA, y es lo que el CEO pregunta cuando pregunta en que ando. El tablero de objetivos
        # del producto se anade DESPUES si tiene algo que decir; sin fuente autonoma, el
        # comportamiento es bit a bit el de antes de este incremento.
        del_ciclo = self._actividad_autonoma()
        secciones = self._secciones_del_ciclo() if self.estado_operativo is not None else []
        if not secciones:
            return del_ciclo or "No tengo ningún objetivo activo registrado en el estado operativo ahora mismo."
        resumen = self._resumen_de(secciones, "Que esta haciendo", "Que hara despues", "Progreso")
        tablero = f"Esto es en lo que estoy trabajando:\n{resumen}"
        if not del_ciclo:
            return tablero
        # Los dos bloques hablan de PLANOS DISTINTOS -mi ciclo autonomo y el tablero de objetivos del
        # producto- y sin decirlo se leen como una contradiccion: "no tengo tareas" seguido de "esto
        # es en lo que trabajo". Se etiqueta el segundo; unirlos en una sola cuenta seria peor,
        # porque fabricaria un total que no existe en ninguna de las dos fuentes.
        return f"{del_ciclo}\n\nAparte, en el tablero de objetivos del producto:\n{resumen}"

    def _describir_aura(self) -> str:
        """Responde lo que AURA hace ahora mismo desde su estado REAL (D-FC-3 = A, T8).

        No calcula nada nuevo: la parada sale de `_sistema_detenido` y el trabajo de `_describir_tareas`,
        la misma funcion que ya contesta «que tareas tienes» (y cuyo «no tengo ningun objetivo activo»
        es la AUSENCIA honesta, INV-9). Con la parada echada se dice primero: es el hecho que mas cambia
        la lectura del resto, y deja de ser una ausencia.
        """
        tareas = self._describir_tareas()
        if self._sistema_detenido():
            return f"La parada de emergencia está echada: ahora mismo no ejecuto ninguna acción.\n{tareas}"
        return tareas

    def _actividad_autonoma(self) -> str | None:
        """Que dice el ciclo autonomo, o `None` si no hay fuente que lo diga."""
        if self.estado_autonomo is None:
            return None
        return redactar_actividad(self.estado_autonomo.instantanea())

    def _decisiones_de_gobernanza(self) -> list:
        """Las decisiones que el ciclo autonomo tiene elevadas al CEO. Se leen del puerto que ya
        existe: no se abre una segunda ventana al plano de control."""
        if self.estado_autonomo is None:
            return []
        pendientes = (self.estado_autonomo.instantanea() or {}).get("decisiones_pendientes")
        return pendientes if isinstance(pendientes, list) else []

    def _registrar_autorizacion(self, uid: str, identificador: str, texto: str, tid: str) -> str:
        """Registra UNA decision humana explicita. No ejecuta nada, y lo dice.

        Todas las respuestas salen del estado real: si no hay buzon, si la decision no existe, si ya
        estaba aprobada o si pertenece a otra autoridad, se responde lo que el estado permite decir —
        nunca un mensaje tranquilizador escrito de antemano."""
        if self.decisiones is None:
            return "No tengo buzón de decisiones conectado, así que no puedo registrar ninguna autorización desde aquí."

        decision, motivo = resolver(identificador, self.decisiones.pendientes(), self.decisiones.aprobadas())
        if motivo == "ambiguo":
            return (
                f"«{identificador}» coincide con más de una decisión pendiente. No registré "
                f"ninguna autorización: elegir por ti sería autorizar una acción que no me "
                f"pediste. Dime la huella completa."
            )

        if decision is None:
            # Puede ser una decision de GOBERNANZA elevada al CEO. Existe de verdad, pero no se
            # resuelve con un «autorizo»: tiene opciones, y ninguna se elige sola. Decir «registrada»
            # aqui seria afirmar que algo queda desbloqueado cuando no lo queda.
            gobernanza = [
                d
                for d in self._decisiones_de_gobernanza()
                if isinstance(d, dict) and str(d.get("id", "")).lower() == identificador.lower()
            ]
            if gobernanza:
                opciones = gobernanza[0].get("opciones") or []
                detalle = ("\n" + "\n".join(f"  • {o}" for o in opciones)) if opciones else ""
                return (
                    f"No puedo registrar esa autorización con la autoridad disponible. "
                    f"{identificador} es una decisión de gobernanza elevada, y no se resuelve "
                    f"con un permiso: hay que elegir una de sus opciones.{detalle}"
                )
            return (
                f"No encuentro una decisión llamada {identificador} en mi estado actual. "
                f"No registré ninguna autorización."
            )

        if decision.get("estado") == "aprobada":
            return f"{identificador} ya estaba autorizada. No registré una segunda autorización."

        huella = str(decision.get("huella", ""))
        marcada = self.decisiones.aprobar(huella, por=uid, origen="conversacion", evidencia=texto)
        if not marcada:
            return f"No pude registrar la autorización de {identificador}: su solicitud ya no está en el buzón."
        obs.log(
            "HITL",
            "autorizacion",
            f"{decision.get('accion')} autorizada por {uid} desde la "
            f"conversacion ({huella[:8]}): pendiente -> aprobada",
            tid,
            audit=True,
        )
        return (
            f"Autorización registrada para {identificador} ({decision.get('accion')}). "
            f"No ejecuto la tarea desde la conversación: queda disponible para mi próximo "
            f"ciclo autónomo, que volverá a comprobar el permiso antes de actuar."
        )

    def _describir_decisiones(self, texto: str) -> str:
        """Las decisiones elevadas, o LA que se nombre. Fuente: el estado autónomo real."""
        identificador = identificador_de_decision(texto)
        return (
            redactar_decisiones(self.estado_autonomo.instantanea(), identificador)
            or "No me consta ninguna decisión pendiente en mi estado actual."
        )

    def _describir_oportunidades(self) -> str:
        return (
            redactar_oportunidades(self.estado_autonomo.instantanea())
            or "No me consta el estado de mi cola de trabajo."
        )

    def _describir_evolucion(self, texto: str) -> str:
        """Qué ha hecho de verdad. «hoy» acota por fecha; el resto, el historial reciente."""
        dia = None
        if "hoy" in _normalizar(texto):
            import datetime as _dt

            dia = _dt.date.today().isoformat()
        return redactar_evolucion(self.estado_autonomo.instantanea(), dia) or "No me consta mi historial de trabajos."

    def _describir_ultima_tarea(self) -> str:
        """La ultima tarea REALMENTE ejecutada, leida del historial del ciclo autonomo."""
        if self.estado_autonomo is None:
            return "No tengo registro de mi propio ciclo de trabajo ahora mismo."
        return (
            redactar_ultima_tarea(self.estado_autonomo.instantanea())
            or "No me consta ninguna tarea ejecutada en mi historial."
        )

    def _describir_bloqueo(self) -> str:
        """Responde "¿por que estas bloqueada?" / "¿que esta pasando?" reutilizando el MISMO
        Centro de Gobierno que ya lee `estado_operativo.py` (`centro_gobierno.panel()/render()`):
        el calculo de bloqueos no se duplica en el orquestador.
        """
        secciones = self._secciones_del_ciclo()
        if not secciones:
            return "No tengo ningún objetivo activo, así que no hay nada bloqueado ahora mismo."
        resumen = self._resumen_de(secciones, "Que esta bloqueado", "Riesgos activos", "Recomendaciones derivadas")
        return f"Esto es lo que está pasando:\n{resumen}"

    # ----------------------------------------- automatizaciones del usuario --

    def _describir_reglas(self, uid: str) -> str:
        """Responde "¿que automatizaciones tengo?" con lo que hay REALMENTE en el almacen.

        Fiel al estado interno: si no hay ninguna, se dice; no se describe una intencion ni un plan.
        """
        reglas = self.automatizaciones.listar(uid)
        if not reglas:
            return "No tienes ninguna automatización activa."
        cabecera = "1 automatización activa" if len(reglas) == 1 else f"{len(reglas)} automatizaciones activas"
        lineas = "\n".join(f"• {r.metadatos.get('descripcion') or f'{r.accion} cuando {r.evento}'}" for r in reglas)
        return f"Tienes {cabecera}:\n{lineas}"

    async def _crear_regla(self, uid: str, text: str) -> str:
        """Persiste la automatizacion que el usuario acaba de definir y lo confirma.

        El reconocedor identifica CUAL de las cuatro acciones conocidas dispara la regla; lo que se
        guarda es el MODELO GENERAL de regla —evento, condicion declarativa, accion y args por referencia
        al evento—, de modo que ampliar el reconocedor no obligue a migrar los datos ya escritos.
        `rule_id` es estable POR REGLA ("copia-al-<disparador>"): repetir la misma frase no la duplica,
        pero dos disparadores distintos (borrar, escribir, ...) conviven como automatizaciones separadas.
        """
        t = _normalizar(text)
        match = _detectar_accion_disparadora(t)
        if match is None:
            # Defensivo: _es_creacion_de_regla ya garantizo que hay una accion reconocida antes de
            # llamar aqui. Si algun dia dejara de hacerlo, mejor esto que una regla inventada (INV-9).
            return "No he identificado qué acción debo vigilar; ¿puedes reformularlo?"
        accion_disparadora, sufijo = match
        rule_id = f"copia-al-{sufijo}"
        equivalentes = {rule_id, *_IDS_HISTORICOS.get(rule_id, ())}
        if any(r.rule_id in equivalentes for r in self.automatizaciones.listar(uid)):
            return f"Ya lo hago: guardo una copia antes de {sufijo}."
        clave_evento = _CLAVE_EVENTO_POR_ACCION[accion_disparadora]
        regla = ReglaUsuario(
            rule_id=rule_id,
            user_id=uid,
            evento="action.command",
            condicion={"campo": "action", "op": "==", "valor": accion_disparadora},
            accion="copiar_archivo",
            args={"ruta": f"$evento.{clave_evento}"},  # referencia al evento real, no un valor congelado
            metadatos={"descripcion": f"Guardar una copia antes de {sufijo} un archivo", "frase": text},
        )
        await self.automatizaciones.crear(regla)
        obs.log("REGLA", "automatizacion", f"automatizacion creada: {regla.rule_id}", "-", audit=True)
        return "Entendido. Lo haré a partir de ahora."

    async def _desactivar_regla(self, uid: str, text: str) -> str:
        """Desactiva la automatizacion que el usuario nombra al pedir que se deje de hacer algo.

        Usa `_detectar_accion_en_cancelacion`, que limpia el texto del marcador de cancelacion
        antes de reconocer la accion (auditoria independiente 2026-08-02: sin limpiarlo, "elimina
        la automatizacion de escribir" detectaba "borrar" por el "elimin" del propio verbo de la
        orden, y desactivaba la automatizacion equivocada). "cuando escriba" identifica la accion
        disparadora "escribir_archivo", cuyo rule_id es "copia-al-escribir". Se comprueban tambien
        los identificadores HISTORICOS (`_IDS_HISTORICOS`): la regla activa del usuario puede
        seguir guardada con un rule_id antiguo si la creo antes de que el reconocedor cambiara de
        nombre.
        Si no se identifica ninguna accion, o el usuario no tiene esa automatizacion activa, la
        unica respuesta honesta es la verdad -lo que tiene activo ahora mismo-, nunca una
        confirmacion de un exito que no ocurrio (INV-9).
        """
        t = _normalizar(text)
        match = _detectar_accion_en_cancelacion(t)
        if match is not None:
            _, sufijo = match
            rule_id = f"copia-al-{sufijo}"
            equivalentes = {rule_id, *_IDS_HISTORICOS.get(rule_id, ())}
            activas = {r.rule_id for r in self.automatizaciones.listar(uid)}
            existente = next((rid for rid in equivalentes if rid in activas), None)
            if existente is not None and await self.automatizaciones.desactivar(uid, existente):
                obs.log("REGLA", "automatizacion", f"automatizacion desactivada: {existente}", "-", audit=True)
                return "Hecho. He desactivado esa automatización."
        # No se identifico cual (o no existe entre las activas): se cuenta la verdad, nunca "hecho".
        return self._describir_reglas(uid)

    async def _disparar_reglas(self, uid: str, evento: dict, tid: str) -> list[dict]:
        """Ejecuta las automatizaciones del usuario que aplican a este evento. Devuelve lo ocurrido.

        Cada disparo recorre el MISMO camino que cualquier otra accion —el motor— con sus permisos y su
        dry-run: una regla no es un atajo para saltarse el gate (RN-5). El `event_id` distingue el disparo
        del evento del usuario para que la idempotencia del adaptador no confunda ambos.

        DEUDA (fuera del alcance fijado): si un disparo previo falla, la accion del usuario se ejecuta
        igualmente; el MVP no tiene semantica transaccional. El fallo no se silencia: se comunica en la
        respuesta y en el Centro de Notificaciones.
        """
        if self.automatizaciones is None:
            return []
        disparos: list[dict] = []
        for regla in self.automatizaciones.aplicables(uid, "action.command"):
            if not evaluar_condicion(regla.condicion, evento):
                continue
            args = resolver_args(regla.args, evento)
            res = await self.motor.ejecutar(
                regla.accion, args, tid, f"{tid}:regla:{regla.rule_id}", origen=f"regla:{regla.rule_id}"
            )
            obs.log(
                "REGLA",
                "automatizacion",
                f"regla {regla.rule_id} -> {regla.accion} {res.get('estado')}",
                tid,
                audit=True,
            )
            n = notificacion_de_accion(regla.accion, args, res)
            if self.notificaciones is not None:
                self.notificaciones.recibir(n)
            disparos.append({"regla": regla, "args": args, "resultado": res, "mensaje": n.titulo})
        return disparos

    def _redactar_con_reglas(self, action: str, args: dict, say_llm: str, res: dict, disparos: list[dict]) -> str:
        """Narra el turno completo: lo que hizo la automatizacion Y lo que pidio el usuario.

        Sin esto, AURA ejecutaria la regla en silencio y el usuario no sabria que ocurrio. Se reutiliza el
        mismo texto comunicable que va al Centro de Notificaciones, para que AURA cuente lo mismo en el
        momento y despues. Lo que no se ejecuto nunca se narra como hecho (ALERTA-005).
        """
        base = self._redactar(action, say_llm, res)
        if not disparos:
            return base
        hechos = [d for d in disparos if d["resultado"].get("estado") == "ejecutada"]
        # "No habia nada que respaldar" NO es un fallo que comunicar. Una automatizacion de respaldo
        # previo sobre un archivo que aun no existe —el caso normal al CREARLO— falla necesariamente,
        # y avisarlo convertiria la automatizacion en una molestia constante por algo que no es un
        # problema. Se silencia SOLO ese caso: cualquier otro fallo se sigue narrando.
        avisos = [
            d["mensaje"]
            for d in disparos
            if d["resultado"].get("estado") != "ejecutada" and not _nada_que_respaldar(d["resultado"])
        ]
        clausula = _CLAUSULA_USUARIO.get(action)
        if hechos and clausula and res.get("estado") == "ejecutada":
            previo = ", ".join(d["mensaje"].rstrip(".") for d in hechos)
            return " ".join([*avisos, f"{previo} y luego {clausula}. [accion {action} ejecutada]"])
        return " ".join([*avisos, *[d["mensaje"] for d in hechos], base])

    def _redactar(self, action: str, say_llm: str, res: dict) -> str:
        """Construye la respuesta sobre el RESULTADO REAL, no sobre lo que el modelo dijo.

        ALERTA-005 punto 4: queda prohibido responder con exito cuando no hay evidencia de
        ejecucion. Antes de M2.5, una accion autorizada que ningun adaptador podia atender devolvia
        la frase del LLM —"Listo el directorio"— y AURA afirmaba haber hecho algo que no hizo.

        La frase del modelo solo sobrevive cuando el adaptador devolvio un resultado. En cualquier
        otro caso se DESCARTA: el modelo no es autoridad sobre los hechos del sistema (ADR-0014), y
        una frase de exito redactada antes de intentar la accion no es informacion, es ruido con
        apariencia de confirmacion.
        """
        estado = res.get("estado")
        if estado == "ejecutada":
            if action in _CAPACIDADES_DE_HOGAR:
                # Mismo criterio que el camino del Core (semana 2): encender/apagar solo se cuenta como
                # hecho si el adaptador VERIFICÓ el efecto. Cierra la deuda D-ADP-1 también aquí: el doble
                # del hogar contestaba `ok` sin tocar nada y AURA anunciaba «[accion … ejecutada]».
                return _redactar_efecto_de_hogar(
                    action, res.get("resultado") or {}, getattr(self, "nombres_de_voz", None)
                )
            if action in _CAPACIDADES_DE_VOLUMEN:
                return _redactar_efecto_de_volumen(
                    action, res.get("resultado") or {}, getattr(self, "nombres_de_voz", None)
                )
            return f"{say_llm} [accion {action} ejecutada]"
        if estado == "detenida":
            return f"No ejecute la accion. [accion {action} detenida: {res.get('motivo')}]"
        return f"No pude ejecutar la accion. [error en {action}: {res.get('motivo')}]"

    async def _capturar_senales(self, uid, tid, text):
        """Captura pasiva de senales de aprendizaje (M3.0).

        Se ejecuta al CIERRE del turno, despues de que la respuesta ya este decidida: asi es
        estructuralmente imposible que la captura influya en lo que AURA contesta (restriccion 2).

        Un fallo aqui no puede costarle el turno al usuario. La captura es infraestructura para el
        futuro; la conversacion es el producto de hoy.
        """
        if self.contexto is None or self.almacen is None:
            return
        try:
            self.contexto.observar(text)
            senales = await self.contexto.recoger_todas(tid)
            if senales:
                n = await self.almacen.guardar(uid, senales)
                obs.log("CTX", "senales", f"capturadas {n} senal(es) de aprendizaje", tid)
        except Exception as e:
            obs.log("WARN", "senales", f"captura fallida (turno no afectado): {e}", tid)

    async def _finalizar_turno(
        self,
        uid,
        tid,
        text,
        say,
        prov,
        t,
        dominio: str = "",
        estatus: Estatus | None = None,
        resumen_prompt: str = "",
    ):
        """Cierre comun del turno: persistencia, memoria de trabajo, voz, metricas y resultado.

        `dominio` dice QUE FUENTE respondio. `provider` solo distingue nucleo de modelo, y con nueve
        superficies deterministas eso ya no basta para auditar el enrutamiento: «core» no dice si la
        respuesta salio del estado autonomo, de las decisiones o de la aritmetica. Sin este dato, la
        unica forma de comprobar que una pregunta llego a su dominio seria mirarle la cara al texto,
        que es exactamente como se cuela un enrutamiento roto.

        `estatus` es lo que la RUTA declara (D-FC-1 = A). No es la decision: la decision es
        `asignar(prov, estatus)`, aqui y en ningun otro sitio, y con un proveedor que no es el Core
        sale PROPUESTA pida lo que pida la ruta. Todo lo que el usuario ve pasa por `presentar`."""
        e = asignar(prov, estatus)
        self._en_modelo.discard(tid)
        if dominio:
            obs.log("CORE", "routing", f"dominio={dominio}", tid)
        obs.log("CORE", "estatus", f"estatus={e.value}", tid, audit=True)
        # Lo que ve y oye el usuario. La marca de propuesta la escribe el Core (D-FC-2 = B).
        visible = presentar(say, e)
        destino = intencion.destino_de_memoria(text)
        if dominio == "modelo_usuario":
            # **T11 (CONTRATO-OLVIDO-Y-RETENCION.md §2, 2026-10-07): el eco de un turno de soberania
            # NO se persiste.** Inspeccionar, olvidar, refutar y corregir terminan aqui, y el eco
            # `usuario dijo: olvida que mi ciudad favorita es Valencia` se escribia DESPUES de la
            # lapida como `episodica` vigente: el dato olvidado volvia al contexto del modelo y
            # anulaba la ausencia determinista de ADR-0014. Tampoco se guarda como `historico`: seria
            # otra copia en claro del contenido olvidado (contrato §5). G-6 queda cubierto por el
            # audit de la propia operacion. Por la misma regla («un turno de soberania no aporta nada a
            # la memoria») la CAPTURA DE SENALES tampoco corre aqui: «olvidalo, mi cumpleanos es el 3
            # de junio» la guardaba como `semantica` vigente y volvia al contexto del modelo (A1).
            destino = None
        if destino is not None:
            # **M-1, eje 2 (DP-D-M-7) + HISTORICO NO RECUPERABLE (CEO, 2026-09-09).** Antes la
            # condicion era `not _es_pregunta(text)`: un detector SINTACTICO decidiendo una cuestion
            # de CONTENIDO, y con una sola salida —almacenar o no—. Ahora hay tres:
            #
            #   RECUPERABLE               el turno aporta un hecho del usuario -> vuelve en `recall`
            #   HISTORICO_NO_RECUPERABLE  orden pura -> se persiste, se audita, NO vuelve en `recall`
            #   None                      pregunta, social, INCIERTO -> no se almacena
            #
            # El historico es lo que permite conservar la traza de una orden sin convertirla en un
            # recuerdo personal: era el auto-eco de `D-M-2` disfrazado de persistencia. Y la primera
            # salida conserva intacto el motivo original: una PREGUNTA no se almacena nunca, porque al
            # repetirla se cubriria a si misma con cobertura 1,00 y ADR-0014 dejaria de activarse.
            kind = "episodica" if destino == intencion.RECUPERABLE else HISTORICO
            # **PARADA, Opción B (CEO, 2026-09-09).** La parada bloquea las acciones del Motor Único
            # y NO la conversación: con ella armada, AURA puede seguir registrando lo que se dijo.
            # Pero solo lo que esté DECLARADO pasivo — `contracts.es_escritura_pasiva` es una
            # whitelist, así que un `kind` nuevo queda bloqueado hasta que alguien lo declare. El
            # olvido no concede: ése es el sentido de fail-closed.
            if self._sistema_detenido() and not es_escritura_pasiva(kind):
                obs.log("CORE", "parada", f"escritura NO pasiva bloqueada por PARADA: {kind}", tid, audit=True)
                destino = None
            if destino is not None:
                await self.memory.write(uid, kind, f"usuario dijo: {text}", {"trace_id": tid, "fuente": "conversacion"})
        # D-FC-8 = B: la captura de senales y la memoria ven SOLO el texto del usuario (arriba y aqui);
        # el `say` del modelo no alimenta ninguna de las dos por ningun camino.
        if dominio != "modelo_usuario":  # T11/A1: ver el comentario de arriba
            await self._capturar_senales(uid, tid, text)
        buffer = self._dialogue.setdefault(uid, [])
        # Lo unico que de este turno reentra en el prompt si lleva contenido del usuario (punto D, req. 11).
        resumen = resumen_prompt or self._resumen_del_turno().pop(tid, "")
        # Se guarda el say SIN marca y con su estatus: la etiqueta de contexto la pone
        # `linea_de_contexto` al construir el prompt, y una marca duplicada no aportaria nada.
        #
        # **SIN TEXTO DEL USUARIO NO HAY TURNO QUE RECORDAR (auditoria del 2026-09-15).** Cuando la
        # transcripcion falla, `text` es "" — y aunque `destino_de_memoria("")` ya impedia PERSISTIRLO,
        # el buffer de trabajo si lo recibia y reentraba al prompt como un «Usuario:» vacio en los turnos
        # siguientes. Un fallo del microfono no puede ensuciar el contexto de la conversacion.
        if text:
            buffer.append(recuperacion.Turno(text, say, e, dominio))
            if resumen:
                buffer[-1] = buffer[-1]._replace(resumen_prompt=resumen)
            if len(buffer) > self._DIALOG_MAX:
                del buffer[: len(buffer) - self._DIALOG_N]  # conserva las ultimas N (memoria de trabajo)
            # **LO QUE SE RETIENE DEJA RASTRO.** Hasta M7 la ventana de trabajo era el unico almacen
            # del sistema del que NADA constaba: se podia demostrar que una capacidad se ejecuto,
            # pero no que su resultado quedo retenido ni cuantos turnos seguiria ahi. Y `DR-4` —que
            # gobierna esta ventana— se aprobo por latencia y cache, antes de que `leer_archivo`
            # fuera una orden conversacional: hoy lo retenido puede ser contenido de ficheros del
            # usuario, y eso merece constar.
            #
            # Se registra el METADATO, nunca el payload: cuantos turnos hay y cual es el tope. Meter
            # aqui el texto retenido convertiria el registro forense en la copia persistente que la
            # ventana precisamente NO es, y tomaria por accidente la decision que esta elevada.
            if dominio == "orden_de_capacidad":
                obs.log(
                    "CORE",
                    "memoria-trabajo",
                    f"resultado retenido en la ventana de trabajo: {len(buffer)}/{self._DIALOG_MAX} "
                    f"turnos (DR-4); no persiste fuera del proceso",
                    tid,
                    audit=True,
                )
        # **LA RESPUESTA YA ESTA PAGADA CUANDO HABLA EL SINTETIZADOR (MISION VOZ, CEO 2026-09-15).**
        # Esta llamada estaba desnuda y ocurre DESPUES de la inferencia: un fallo de Piper —modelo
        # ausente, USB desmontada— tumbaba el turno entero y tiraba un `say` que habia costado minutos.
        # Medido el 2026-09-10 en HC-1: tres turnos reales, cero completados. La voz es periferica; la
        # respuesta es el producto. Se degrada a texto y el fallo queda AUDITADO y observable en el
        # resultado: degradar en silencio seria fingir una capacidad que no se tuvo (INV-9).
        # La RUTA del audio sintetizado se devuelve con el turno (campaña, 2026-09-27). Se generaba y se
        # tiraba: el WAV existia en disco y nadie que conversara por voz podia saber cual reproducir.
        audio: str | None = None
        voz = "ok"
        try:
            audio = await self.voice.tts(visible, tid)
        except Exception as ex:
            voz = "no_disponible"
            obs.log("WARN", "voice", f"sintesis no emitida; la respuesta se entrega en texto: {ex}", tid, audit=True)
        t.mark("tts")
        total = t.total_ms()
        obs.log("LAT", "orchestrator", f"latencia total {total:.1f} ms (proveedor={prov})", tid, audit=True)
        # `dominio` es ADITIVO: quien ya leia `provider` sigue leyendo lo mismo. Se declara siempre,
        # y vale "llm" cuando respondio el proveedor, para que no haya un hueco silencioso.
        # `estatus` es igual de aditivo (D-FC-1): nadie que leyera las claves anteriores las pierde.
        # `voz` es ADITIVO, como lo fueron `dominio` y `estatus`: quien ya leia las claves anteriores
        # sigue leyendo lo mismo. Dice si la respuesta ademas SONO, que es una propiedad del turno y no
        # de la respuesta -- por eso no contamina el `say` (ADR-0017: lo que se entrega es lo que se dijo).
        self._results[tid] = {
            "say": visible,
            "provider": prov,
            "latency_ms": total,
            "marks": dict(t.marks),
            "dominio": dominio or ("llm" if prov != "core" else ""),
            "estatus": e.value,
            "voz": voz,
            # `audio` es ADITIVO como `voz`: la ruta del WAV de la respuesta, o None si no sono.
            "audio": audio if voz == "ok" else None,
        }
        if tid in self._done:
            self._done[tid].set()
