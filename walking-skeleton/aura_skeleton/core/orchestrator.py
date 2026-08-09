"""Orquestador (nucleo, Bible 3.2/4.2/4.3). Coordina memoria, router y permisos.
Los eventos son SERIALIZABLES (contrato 3.3): el estado de temporizacion se guarda por trace_id,
no en el payload. Asi el MISMO orquestador corre sobre el bus in-process o sobre NATS real."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from .. import observability as obs
from ..contracts import Event
from ..observability import Timer
from .almacen_senales import AlmacenSenales
from .automatizacion import MotorAutomatizacion
from .centro_gobierno import panel
from .modelo_usuario import describir_conocimiento, explicar_entrada
from .notificaciones import notificacion_de_accion
from .registro import RegistroAdaptadores
from .reglas import ReglaUsuario, evaluar_condicion, resolver_args


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
            say = str(d.get("say", "")) or "Entendido."
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
_PATRONES_CONSULTA_MEMORIA = (
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
    "que sabes de mi",
    "que recuerdas",
    "mi preferencia",
    "habiamos quedado",
)


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
    """Intencion interrogativa: signo de interrogacion o interrogativo en posicion inicial."""
    if "?" in texto or "¿" in texto:
        return True
    palabras = _normalizar(texto).split()
    return bool(palabras) and palabras[0] in _INTERROGATIVOS


def _es_consulta_de_memoria(texto: str) -> bool:
    """True si el usuario pregunta por algo supuestamente recordado.

    Dos vias: los marcadores de evocacion explicita ("acordamos", "te conte") O una pregunta. La
    segunda es la que hacia falta: sin ella la garantia de no-fabricacion cubria una fraccion minima
    del espacio real de preguntas.
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


def _es_consulta_de_reglas(texto: str) -> bool:
    """True si el usuario quiere inspeccionar sus automatizaciones ("¿que automatizaciones tengo?")."""
    return any(p in _normalizar(texto) for p in _PAT_REGLAS_VER)


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

_PAT_TAREAS = (
    "que tareas tienes",
    "cuales son tus tareas",
    "en que estas trabajando",
    "en que trabajas",
    "que estas haciendo",
)

_PAT_GOBIERNO = (
    "por que estas bloqueada",
    "por que estas bloqueado",
    "que esta pasando",
)

_PAT_FORMACION = (
    "que aprendiste",
    "que has aprendido",
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
    ):
        self.bus, self.memory, self.router = bus, memory, router
        self.perm, self.voice = permissions, voice
        self.notificaciones = notificaciones  # Centro de Notificaciones (MVP): registra lo que AURA hace
        self.modelo_usuario = modelo_usuario  # Soberania (MVP): ver/entender/corregir/olvidar lo que sabe de ti
        self.automatizaciones = automatizaciones  # AlmacenReglas (MVP cap. 5): reglas del usuario, persistentes
        # Estado Operativo del SO Interno (M3 entry): fuente de "que tareas tienes" / "por que estas
        # bloqueada" en la conversacion. OPCIONAL: sin el, esas preguntas siguen el flujo normal
        # (memoria/LLM), igual que notificaciones/modelo_usuario/automatizaciones cuando no se conectan.
        self.estado_operativo = estado_operativo
        self._foco_modelo: dict[str, dict] = {}  # a que afirmacion se refiere "eso" por usuario
        # M3.0 — captura de senales. OPCIONAL y PASIVA: si no hay registro de contexto, el sistema
        # se comporta exactamente igual que en M2. La captura observa el turno; no participa en
        # ninguna decision (restriccion 2 del gate del CEO).
        self.contexto = contexto
        self.almacen = AlmacenSenales(memory) if contexto is not None else None
        # Un adaptador suelto se envuelve; el resto del codigo trabaja siempre contra un registro.
        if hasattr(adaptadores, "para"):
            self.registro = adaptadores
        else:
            self.registro = RegistroAdaptadores([adaptadores])
        # Sin motor inyectado se construye uno sobre el mismo registro y los mismos permisos: el
        # flujo es identico venga de donde venga la peticion.
        self.motor = motor if motor is not None else MotorAutomatizacion(self.registro, permissions)
        self._timers: dict[str, Timer] = {}
        self._done: dict[str, asyncio.Event] = {}
        self._results: dict[str, dict] = {}
        self._dialogue: dict[str, list[tuple[str, str]]] = {}  # memoria de trabajo por usuario
        self._DIALOG_N = 6
        bus.subscribe("perception.turn_end", self.on_turn)

    async def handle_utterance(self, user_id, audio_text, trace_id):
        t = Timer()
        self._timers[trace_id] = t
        self._done[trace_id] = asyncio.Event()
        text = await self.voice.stt(audio_text, trace_id)
        t.mark("stt")
        await self.bus.publish(Event("perception.turn_end", trace_id, user_id, {"text": text}))

    async def wait(self, trace_id, timeout=10):
        await asyncio.wait_for(self._done[trace_id].wait(), timeout)
        return self._results.get(trace_id)

    async def on_turn(self, ev: Event):
        tid = ev.trace_id
        uid = ev.user_id
        text = ev.payload["text"]
        t = self._timers.get(tid) or Timer()
        # Soberania del modelo del usuario: inspeccionar/entender/corregir/olvidar lo que AURA sabe de ti.
        if self.modelo_usuario is not None:
            resp = await self._atender_modelo_usuario(uid, text)
            if resp is not None:
                await self._finalizar_turno(uid, tid, text, resp, "core", t)
                return
        # Superficie del Centro de Notificaciones: "¿que ha pasado mientras no estaba?" se responde con
        # lo que AURA hizo, sin consultar memoria ni LLM (es un hecho del sistema, no una inferencia).
        if self.notificaciones is not None and _es_consulta_de_notificaciones(text):
            await self._finalizar_turno(uid, tid, text, self._resumen_notificaciones(), "core", t)
            return
        # Automatizaciones del usuario (MVP capacidad 5): inspeccionar y crear reglas. Deterministas como el
        # resto de superficies; el LLM no interviene (definir o listar una regla es un hecho, no una inferencia).
        if self.automatizaciones is not None:
            if _es_consulta_de_reglas(text):
                await self._finalizar_turno(uid, tid, text, self._describir_reglas(uid), "core", t)
                return
            if _es_creacion_de_regla(text):
                await self._finalizar_turno(uid, tid, text, self._crear_regla(uid, text), "core", t)
                return
            # Desactivar una automatizacion (M3 entry): se responde SIEMPRE aqui, tenga o no el
            # usuario alguna activa, para que la frase no caiga en otra superficie (memoria, LLM)
            # y produzca una respuesta enganosa o un efecto no pedido.
            if _es_cancelacion_de_regla(text):
                await self._finalizar_turno(uid, tid, text, self._desactivar_regla(uid, text), "core", t)
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
        resp = await self._atender_conversacion_general(uid, text)
        if resp is not None:
            await self._finalizar_turno(uid, tid, text, resp, "core", t)
            return
        if _es_consulta_de_capacidades(text):
            await self._finalizar_turno(uid, tid, text, self._describir_capacidades(), "core", t)
            return
        if self.estado_operativo is not None:
            if _es_consulta_de_tareas(text):
                await self._finalizar_turno(uid, tid, text, self._describir_tareas(), "core", t)
                return
            if _es_consulta_de_gobierno(text):
                await self._finalizar_turno(uid, tid, text, self._describir_bloqueo(), "core", t)
                return
        if _es_consulta_de_formacion(text):
            await self._finalizar_turno(uid, tid, text, _resumen_formacion(), "core", t)
            return
        hits = await self.memory.recall(uid, text)
        t.mark("memory")
        # ADR-0014: la ausencia de memoria es un HECHO, no una inferencia. Si el usuario
        # pregunta por un recuerdo y no existe registro, responde el nucleo y NO se consulta
        # al LLM: no se le da ocasion de inferir, completar ni reformular lo inexistente.
        if not hits and _es_consulta_de_memoria(text):
            say = "No tengo ningun recuerdo registrado sobre eso."
            obs.log(
                "CORE", "grounding", "memoria vacia -> respuesta determinista (sin llamada al LLM)", tid, audit=True
            )
            await self._finalizar_turno(uid, tid, text, say, "core", t)
            return

        ctx = " | ".join(h["content"] for h in hits) if hits else "(sin recuerdos relevantes)"
        buffer = self._dialogue.get(uid, [])
        recent = "\n".join(f"(previo) tu: {u} | AURA: {a}" for u, a in buffer) or "(inicio de la conversacion)"
        prompt = f"[contexto memoria: {ctx}]\n[conversacion reciente:\n{recent}]\nUsuario: {text}"
        prov, out = await self.router.route(prompt, tid)
        t.mark("llm")
        action, args, say = _parse_decision(out, tid)
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
        if self._sistema_detenido() and (_es_peticion_de_olvido(t) or _cae_en(t, _PAT_MODELO_REFUTA)):
            # Inspeccionar sigue permitido: leer no muta nada. Lo que la parada impide es MODIFICAR.
            obs.log("KILL", "orchestrator", "soberania: mutacion bloqueada por kill switch", "-", audit=True)
            return "Ahora mismo no puedo modificar lo que sé de ti: el sistema está detenido."
        entradas = await self.modelo_usuario.ver(uid)
        vivas = [e for e in entradas if not e.get("refutada")]

        if _cae_en(t, _PAT_MODELO_VER):
            # Foco por defecto para el "eso" siguiente: la primera observada (la cuestionable); si no,
            # la primera declarada. La declarada no suele necesitar explicacion ("me lo dijiste").
            if vivas:
                self._foco_modelo[uid] = next((e for e in vivas if e.get("origen") != "declarada"), vivas[0])
            return describir_conocimiento(entradas)

        if _es_peticion_de_olvido(t):  # antes que refutar/porque: "olvida" es inequivoco
            foco = self._foco(uid, t, vivas, entradas)
            if foco is None:
                # ALERTA-006: antes se elegia `vivas[0]` y se confirmaba el borrado. Ante la duda se
                # pregunta; destruir el dato equivocado no es soberania del usuario, es perdida.
                return _DESAMBIGUAR
            n = await self.modelo_usuario.borrar(uid, foco["contenido"])
            return (
                "Hecho. Ya no lo consideraré parte de lo que sé de ti." if n else "No he encontrado eso para olvidarlo."
            )

        if _cae_en(t, _PAT_MODELO_REFUTA):
            foco = self._foco(uid, t, vivas, entradas)
            if foco is None:
                return _DESAMBIGUAR
            # Se comprueba el retorno: `refutar` puede no mutar nada (p.ej. si ya estaba refutada), y
            # narrar exito sin efecto viola INV-9 / ALERTA-005 punto 4. `borrar` ya lo comprobaba.
            n = await self.modelo_usuario.refutar(uid, foco["contenido"])
            if n:
                return "Entendido, lo corrijo. Dejo de darlo por cierto."
            return "No he encontrado eso para corregirlo."

        if _cae_en(t, _PAT_MODELO_PORQUE):
            foco = self._foco(uid, t, vivas, entradas)
            return explicar_entrada(foco) if foco else "Ahora mismo no estoy afirmando nada sobre ti."

        return None

    def _foco(self, uid: str, t: str, vivas: list[dict], existentes: list[dict] | None = None) -> dict | None:
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
        """
        for e in vivas:
            palabras = [w for w in _normalizar(e["contenido"]).split() if len(w) > 4]
            if any(w in t for w in palabras):
                self._foco_modelo[uid] = e
                return e
        cacheado = self._foco_modelo.get(uid)
        if cacheado is None:
            return None
        universo = vivas if existentes is None else existentes
        return cacheado if any(x["contenido"] == cacheado["contenido"] for x in universo) else None

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
        secciones = self._secciones_del_ciclo()
        if not secciones:
            return "No tengo ningún objetivo activo registrado en el estado operativo ahora mismo."
        resumen = self._resumen_de(secciones, "Que esta haciendo", "Que hara despues", "Progreso")
        return f"Esto es en lo que estoy trabajando:\n{resumen}"

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

    def _crear_regla(self, uid: str, text: str) -> str:
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
        self.automatizaciones.crear(regla)
        obs.log("REGLA", "automatizacion", f"automatizacion creada: {regla.rule_id}", "-", audit=True)
        return "Entendido. Lo haré a partir de ahora."

    def _desactivar_regla(self, uid: str, text: str) -> str:
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
            if existente is not None and self.automatizaciones.desactivar(uid, existente):
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

    async def _finalizar_turno(self, uid, tid, text, say, prov, t):
        """Cierre comun del turno: persistencia, memoria de trabajo, voz, metricas y resultado."""
        if not _es_pregunta(text):
            # Una PREGUNTA no es informacion sobre el usuario: es una peticion de informacion.
            # Almacenarla como recuerdo hacia que, al repetirla, se cubriera a si misma con cobertura
            # 1,00 y ADR-0014 dejara de activarse — el sistema recibia su propia pregunta como si
            # fuera un recuerdo. Se sigue registrando en el audit log: no se pierde la traza.
            await self.memory.write(
                uid, "episodica", f"usuario dijo: {text}", {"trace_id": tid, "fuente": "conversacion"}
            )
        await self._capturar_senales(uid, tid, text)
        buffer = self._dialogue.setdefault(uid, [])
        buffer.append((text, say))
        del buffer[: max(0, len(buffer) - self._DIALOG_N)]  # conserva las ultimas N (memoria de trabajo)
        await self.voice.tts(say, tid)
        t.mark("tts")
        total = t.total_ms()
        obs.log("LAT", "orchestrator", f"latencia total {total:.1f} ms (proveedor={prov})", tid, audit=True)
        self._results[tid] = {"say": say, "provider": prov, "latency_ms": total, "marks": dict(t.marks)}
        if tid in self._done:
            self._done[tid].set()
