"""Órdenes de hogar interpretadas por el CORE, con confirmación explícita.

EL DEFECTO QUE CIERRA, MEDIDO `[EJEC]` (2026-09-27): «enciende la tele» lo interpretaba el MODELO local,
que contestaba «encendí la luz de la sala» y ejecutaba `encender_dispositivo` sobre un dispositivo que
nadie había nombrado. ADR-0014 §4: una garantía no puede depender de que un modelo se comporte. El Core
reconoce la orden y el dispositivo; el modelo no decide qué se ejecuta.

GOBIERNO. Encender y apagar ya son lista verde (D4, Bible 6.3): el catálogo permite ejecutarlos sin
preguntar. Esta superficie hace algo MÁS estricto: propone la acción y solo la ejecuta tras un «sí»
explícito en el turno siguiente, siempre por el Motor Único (permisos, kill switch, auditoría) y con la
confirmación del efecto que hace el adaptador de Home Assistant. No amplía ninguna autoridad; la reduce.

CÓMO RECONOCE. Por frase completa y conservador: una orden negada («no apagues…»), compuesta («…y
borra…») o con varios dispositivos no se reconoce, y el turno sigue su camino de siempre (ADR-0003:
ante la duda, no).
"""

from __future__ import annotations

import re
from datetime import datetime

from .intencion import normalizar

_VERBOS = {
    # «enciente»: variante de transcripción OBSERVADA por el aire (2026-10-04, Whisper `base`, voz humana) para
    # «enciende». Mismo verbo, misma acción; sigue exigiendo activación y confirmación. Solo variantes medidas.
    "encender_dispositivo": ("enciende", "prende", "encienda", "prenda", "encender", "prender", "enciente"),
    "apagar_dispositivo": ("apaga", "apague", "apagar"),
}
_INFINITIVO = {
    "encender_dispositivo": "encender",
    "apagar_dispositivo": "apagar",
    "subir_volumen": "subir el volumen de",
    "bajar_volumen": "bajar el volumen de",
    "silenciar": "silenciar",
    "quitar_silencio": "quitar el silencio a",
}
_VERBO_A_CAPACIDAD = {v: c for c, vs in _VERBOS.items() for v in vs}

_ORDEN = re.compile(
    r"^(?:(?:oye\s+)?aurora\s+)?(?:por favor\s+)?(?:puedes\s+|podrias\s+)?"
    r"(" + "|".join(sorted(_VERBO_A_CAPACIDAD, key=len, reverse=True)) + r")\s+"
    r"(?:el|la|los|las)\s+(.+?)(?:\s+por favor)?$"
)

#: Señales de que la frase no es UNA orden limpia sobre UN dispositivo.
_NO_ES_UNA_SOLA = re.compile(r"\s(?:y|e|o|pero|luego|despues|tambien)\s|,|;")

_SI = frozenset(
    {
        "si",
        "si hazlo",
        "hazlo",
        "adelante",
        "vale",
        "claro",
        "ok",
        "de acuerdo",
        "confirmo",
        "si por favor",
        "si claro",
        "venga",
    }
)
_NO = frozenset({"no", "no dejalo", "dejalo", "cancela", "cancelalo", "mejor no", "no gracias", "no lo hagas", "para"})


def _limpiar(texto: str) -> str:
    t = normalizar(texto)
    for signo in "¿?¡!.":
        t = t.replace(signo, " ")
    return " ".join(t.replace(",", " , ").split()).replace(" ,", ",").strip(" ,")


#: Órdenes de VOLUMEN y SILENCIO (acta `decisiones/2026-10-22-acta-ecosistema-domestico.md` §4). Gramática aparte de
#: encender/apagar, igual de cerrada: verbo en imperativo + «el volumen» / «el silencio» + dispositivo opcional. Sin
#: dispositivo se entiende la TV («sube el volumen»): es lo único con volumen que el hogar integra, y si hay varias TV
#: el adaptador lo dice y pregunta cuál, no elige.
_PREFIJO = r"^(?:(?:oye\s+)?aurora\s+)?(?:por favor\s+)?(?:puedes\s+|podrias\s+)?"
_SUFIJO = r"(?:\s+por favor)?$"
_DE_DISPOSITIVO = r"(?:\s+(?:del|al|(?:de|a|en)\s+(?:el|la|los|las))\s+(.+?))?"
_ORDENES_DE_VOLUMEN = (
    (
        "subir_volumen",
        re.compile(_PREFIJO + r"(?:sube|subele|subir|aumenta)\s+el\s+volumen" + _DE_DISPOSITIVO + _SUFIJO),
    ),
    (
        "bajar_volumen",
        re.compile(_PREFIJO + r"(?:baja|bajale|bajar|disminuye)\s+el\s+volumen" + _DE_DISPOSITIVO + _SUFIJO),
    ),
    (
        "silenciar",
        re.compile(_PREFIJO + r"(?:silencia|silenciar|pon\s+en\s+silencio)\s+(?:el|la|los|las)\s+(.+?)" + _SUFIJO),
    ),
    ("quitar_silencio", re.compile(_PREFIJO + r"(?:quita|quitale|quitar)\s+el\s+silencio" + _DE_DISPOSITIVO + _SUFIJO)),
)


def _reconocer_volumen(limpio: str) -> tuple[str, str] | None:
    for capacidad, patron in _ORDENES_DE_VOLUMEN:
        hallado = patron.match(limpio)
        if hallado:
            dispositivo = (hallado.group(1) or "tele").strip()
            if _NO_ES_UNA_SOLA.search(f" {dispositivo} "):
                return None
            return capacidad, dispositivo
    return None


def reconocer(texto: str) -> tuple[str, str] | None:
    """(capacidad, dispositivo) si la frase es UNA orden de hogar sobre UN dispositivo; si no, None."""
    limpio = _limpiar(texto)
    hallado = _ORDEN.match(limpio.replace(",", "") if limpio.startswith(("aurora,", "oye aurora,")) else limpio)
    if not hallado:
        # «…, por favor» es cortesía, no una segunda orden; cualquier otra coma sí corta (ADR-0003).
        sin_vocativo = limpio.replace(",", "", 1) if limpio.startswith(("aurora,", "oye aurora,")) else limpio
        return _reconocer_volumen(sin_vocativo.replace(", por favor", " por favor"))
    dispositivo = hallado.group(2).strip()
    if not dispositivo or _NO_ES_UNA_SOLA.search(f" {dispositivo} "):
        return None
    # El dispositivo se devuelve con la ortografía del usuario (tildes incluidas) para nombrarlo bien.
    original = " ".join(texto.replace("¿", " ").replace("?", " ").split())
    m = re.search(re.escape(dispositivo), normalizar(original))
    if m:
        dispositivo = original[m.start() : m.end()]
    return _VERBO_A_CAPACIDAD[hallado.group(1)], dispositivo.strip(" .").lower()


#: Palabras con las que una persona nombra la TV (lista cerrada; sin «teléfono» ni parecidos).
_PALABRAS_TV = frozenset({"tele", "television", "televisor", "tv"})

#: Lo que responde AURA cuando una orden HABLADA para la TV no se entiende (E2E físico 2026-10-04: Whisper
#: escribió «¿No fiende la televisión?» y AURA contestó «No tengo ningún recuerdo», que engaña sobre lo que pasó).
ORDEN_NO_ENTENDIDA = (
    "He oído que hablas de la televisión, pero no entendí la orden, así que no he hecho nada. "
    "Llámame otra vez y di «enciende la televisión» o «apaga la televisión»."
)


def menciona_tv_sin_orden(texto: str) -> bool:
    """True si la frase nombra la TV pero NO es una orden reconocible: se dice que no se entendió, no se adivina."""
    if reconocer(texto) is not None:
        return False
    return bool(set(_limpiar(texto).replace(",", " ").split()) & _PALABRAS_TV)


def confirmacion(texto: str) -> bool | None:
    """True si confirma, False si rechaza, None si el turno no es una respuesta a la propuesta."""
    limpio = _limpiar(texto).replace(",", "")
    if limpio in _SI:
        return True
    if limpio in _NO:
        return False
    return None


def proponer(capacidad: str, dispositivo: str) -> str:
    return f"Voy a {_INFINITIVO[capacidad]} «{dispositivo}». ¿Lo hago? (sí o no)"


def proponer_humano(capacidad: str, nombre_humano: str) -> str:
    """La propuesta por voz con el nombre FAMILIAR de la entidad («la TV de la sala»), sin comillas ni
    nombres técnicos (CEO 2026-10-04)."""
    return f"Voy a {_INFINITIVO[capacidad]} {nombre_humano}. ¿Lo hago?"


#: Las capacidades de hogar del catálogo (lista verde D4, y volumen/silencio por el acta del 2026-10-22).
CAPACIDADES = frozenset(_VERBOS) | frozenset(c for c, _ in _ORDENES_DE_VOLUMEN)

#: Lo que la VOZ puede proponer y ejecutar: solo encender/apagar (opción C, `DP-VOZ-ACCION.md` §8). El volumen por voz
#: espera su propia decisión (acta 2026-10-22 §5).
CAPACIDADES_DE_VOZ = frozenset(_VERBOS)

#: Lo que dice el Core cuando una orden HABLADA de volumen llega a la frontera de la opción C.
VOLUMEN_POR_VOZ_PENDIENTE = (
    "Por voz todavía solo enciendo o apago la TV de la sala: cambiar el volumen o silenciarla por voz espera una "
    "decisión. No he hecho nada; si quieres, escríbemelo."
)

#: Palabras que no distinguen un dispositivo de otro al compararlo con su nombre humano.
_SIN_SIGNIFICADO = frozenset({"el", "la", "los", "las", "de", "del", "al", "a", "en", "mi"})


def _rasgos(nombre: str) -> frozenset[str]:
    palabras = _limpiar(nombre).replace(",", " ").split()
    return frozenset("tv" if p in _PALABRAS_TV else p for p in palabras if p not in _SIN_SIGNIFICADO)


def entidad_por_nombre_humano(dispositivo: str, nombres: dict[str, str]) -> str | None:
    """La entidad cuyo nombre HUMANO («la TV de la sala») dice lo mismo que la persona («la tele de la sala»).

    Mismas palabras significativas, con tele/tv/televisión/televisor como una sola; si casan varias o ninguna, None y la
    resolución sigue como siempre. No adivina: solo usa los nombres que el CEO fijó (`NOMBRE_HUMANO_DE_VOZ`)."""
    buscado = _rasgos(dispositivo)
    halladas = [entidad for entidad, nombre in nombres.items() if buscado and _rasgos(nombre) == buscado]
    return halladas[0] if len(halladas) == 1 else None


#: Lo que dice el Core cuando el modelo quiso tocar un dispositivo que la persona no nombró.
SIN_DISPOSITIVO_CLARO = (
    "No he hecho nada: no me quedó claro qué dispositivo quieres. Dímelo con su nombre, por ejemplo «apaga la tele»."
)

_VACIAS = frozenset({"el", "la", "los", "las", "de", "del", "al", "a", "en", "un", "una"})


def dispositivo_nombrado(dispositivo: str, texto: str) -> bool:
    """True si TODAS las palabras significativas del dispositivo están en lo que dijo la persona.

    Es la guarda para el camino del modelo: el modelo puede proponer una acción, pero no puede elegir
    sobre qué dispositivo actúa si la persona no lo nombró (ADR-0014 §4)."""
    palabras = {p for p in _limpiar(dispositivo).replace(",", " ").split() if p not in _VACIAS}
    dichas = set(_limpiar(texto).replace(",", " ").split())
    return bool(palabras) and palabras <= dichas


def pendiente_de_decision(capacidad: str, args: dict, nombre_humano: str | None = None) -> str:
    """Lo que dice AURA cuando la orden hablada está confirmada pero la voz aún no puede actuar."""
    objetivo = nombre_humano or f"«{args.get('nombre') or args.get('device')}»"
    return (
        f"Lo tengo todo listo para {_INFINITIVO[capacidad]} {objetivo}, pero "
        "que una orden HABLADA cambie algo en esa entidad todavía espera una decisión. No lo he hecho. Si "
        "quieres, escríbemelo y lo hago."
    )


#: Confianza del STT (contrato C4, DP-VOZ-ACCION §8). Un turno hablado por encima del primero o por debajo
#: del segundo NO propone ni confirma una orden de hogar: AURA pide repetirlo.
#: MEDIDOS (2026-10-04, `evidencia-voz-accion/medicion-confianza-stt.md`, Whisper `base`, 135 casos sin audio en disco):
#: frenan 11/11 de no-habla (silencio, ruido, tonos) y conservan 22/22 entendidas (máx. nsp 0,071; mín. logprob -1,032).
#: NO bastan solos: un «Vale.» fabricado (nsp 0,018; logprob -0,797) cae dentro del rango de voz real. La defensa frente a
#: eso es la palabra de activación exigida en el turno (C1), no el umbral.
UMBRAL_NO_HABLA = 0.15
UMBRAL_LOGPROB = -1.2


def confianza_baja(confianza: object) -> bool:
    """True si el STT dudó de lo que oyó (`ultima_confianza` del adaptador de voz, contrato C4).

    Sin medición (None, no es un dict) NO se rechaza: no hay cifra que lo justifique; la activación y la
    llave por entidad siguen mandando. Los bordes (== umbral) no rechazan."""
    if not isinstance(confianza, dict):
        return False
    return bool(
        confianza.get("no_speech_prob", 0.0) > UMBRAL_NO_HABLA or confianza.get("avg_logprob", 0.0) < UMBRAL_LOGPROB
    )


#: Lo que dice el Core, sin modelo, en cada rechazo de la frontera voz -> acción (DP-VOZ-ACCION §8).
PIDE_ACTIVACION = "Para actuar en casa por voz, llámame primero por mi nombre: di «Oye Aurora»."
PIDE_REPETIR = "No te he oído con suficiente claridad para actuar en casa. No he hecho nada; repítemelo, por favor."
FUERA_DE_ALCANCE = (
    "Eso queda fuera de lo que puedo hacer por voz: por voz solo actúo sobre la TV de la sala. "
    "No he hecho nada; si quieres, escríbemelo."
)
HA_NO_RESPONDE = "No he podido consultar Home Assistant (no respondió); no he hecho nada."


# --------------------------------------------------------------------------- consulta de ESTADO --
#: Preguntas por el estado ACTUAL de la TV (acta `decisiones/2026-10-22-acta-ecosistema-domestico.md` §4). Es una
#: LECTURA: no pasa por el Motor ni cambia nada. Gramática cerrada, y el dispositivo tiene que nombrar la TV: «¿qué hay
#: en la nevera?» no es esto, y el turno sigue su camino de siempre.
_VOCATIVO = r"^(?:(?:oye\s+)?aurora,?\s+)?"
_CONSULTAS = (
    (
        "encendida",
        re.compile(
            _VOCATIVO + r"(?:esta\s+(?:encendid[ao]|prendid[ao]|apagad[ao])\s+(?:el|la)\s+(.+)"
            r"|(?:el|la)\s+(.+?)\s+esta\s+(?:encendid[ao]|prendid[ao]|apagad[ao]))$"
        ),
    ),
    (
        "volumen",
        re.compile(
            _VOCATIVO + r"(?:a\s+que\s+volumen\s+esta\s+(?:el|la)\s+(.+)|que\s+volumen\s+tiene\s+(?:el|la)\s+(.+))$"
        ),
    ),
    (
        "contenido",
        re.compile(
            _VOCATIVO + r"(?:que\s+esta\s+poniendo\s+(?:el|la)\s+(.+)|que\s+hay\s+en\s+(?:el|la)\s+(.+)"
            r"|que\s+se\s+esta\s+viendo\s+en\s+(?:el|la)\s+(.+))$"
        ),
    ),
)

#: Estados de un `media_player` de HA que significan encendido o apagado. Cualquier otro («unavailable»…) es no saberlo.
# CONTRATO DE EQUIVALENCIAS (por OPERACIÓN, no globales; el mismo criterio para consultar y para verificar):
#   encender  -> verificado si HA ve el dispositivo en ESTADOS_ENCENDIDA y antes NO lo estaba.
#   apagar    -> verificado si HA ve el dispositivo en ESTADOS_APAGADA y antes NO lo estaba.
#   volumen / silencio -> exige estado de ESTADOS_ENCENDIDA; con ESTADOS_APAGADA no se envía y se dice «apagada».
#   cualquier otro estado (unavailable, unknown, no reconocido) -> no se envía nada y nunca se verifica.
# «Verificado» significa «Home Assistant lo reporta así tras la orden»: NO es confirmación física.
ESTADOS_ENCENDIDA = frozenset({"on", "playing", "paused", "idle"})
ESTADOS_APAGADA = frozenset({"off", "standby"})
#: Alias conservados: las consultas y la verificación de órdenes comparten UN solo criterio (los públicos).
_ENCENDIDOS = ESTADOS_ENCENDIDA
_APAGADOS = ESTADOS_APAGADA

#: Lo que se dice cuando no hay un Home Assistant real que leer.
CONSULTA_SIN_HOGAR_REAL = (
    "El hogar está en modo simulado: no hay ningún dispositivo real conectado, así que no sé cómo está la TV."
)


def reconocer_consulta(texto: str) -> tuple[str, str] | None:
    """(aspecto, dispositivo) si la frase pregunta por el estado de UNA TV: «encendida», «apagada», «volumen» o
    «contenido»."""
    limpio = _limpiar(texto)
    for aspecto, patron in _CONSULTAS:
        hallado = patron.match(limpio)
        if not hallado:
            continue
        dispositivo = next(g for g in hallado.groups() if g).strip()
        if _NO_ES_UNA_SOLA.search(f" {dispositivo} ") or "tv" not in _rasgos(dispositivo):
            return None
        # «¿está APAGADA?» pide el «sí» si está apagada: la polaridad de la pregunta se conserva (revisión ECC, ALTO).
        if aspecto == "encendida" and "apagad" in limpio:
            aspecto = "apagada"
        return aspecto, dispositivo
    return None


def _cuando(last_changed: object) -> str:
    """«desde las 21:05 del 21-10» en hora LOCAL, o «» si HA no dio una marca legible (no se inventa)."""
    try:
        momento = datetime.fromisoformat(str(last_changed)).astimezone()
    except (TypeError, ValueError):
        return ""
    return f", desde las {momento:%H:%M} del {momento:%d-%m}"


def texto_seguro(valor: object, tope: int = 60) -> str:
    """Un dato que viene de fuera (estado, nombre de Home Assistant) antes de entrar en un texto para la persona:
    sin caracteres de control (p. ej. secuencias ESC) y acotado. Nunca se interpola crudo."""
    limpio = " ".join("".join(c if ord(c) >= 32 and ord(c) != 127 else " " for c in str(valor)).split())
    return limpio if len(limpio) <= tope else limpio[:tope] + "…"


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def describir_estado(aspecto: str, nombre: str, estado: dict, por_voz: bool) -> str:
    """Lo que AURA dice del estado leído; si Home Assistant lo da por ASUMIDO (`assumed_state`, p. ej. SmartIR: no
    puede leer el aparato), lo dice en vez de presentarlo como observado."""
    texto = _describir_estado_leido(aspecto, nombre, estado, por_voz)
    atributos = estado.get("attributes")
    if not (isinstance(atributos, dict) and atributos.get("assumed_state") is True):
        return texto
    valor = str(estado.get("state", "?"))
    if aspecto in ("encendida", "apagada") and valor in _ENCENDIDOS | _APAGADOS:
        como = "encendida" if valor in _ENCENDIDOS else "apagada"
        return texto.replace(
            "(según Home Assistant", f"(según Home Assistant, que la da por {como} sin poder leerla", 1
        )
    return f"{texto} Ojo: es un estado asumido por Home Assistant, que no puede leer el aparato."


def _describir_estado_leido(aspecto: str, nombre: str, estado: dict, por_voz: bool) -> str:
    """Lo que AURA dice del estado leído: lo observado, con su fuente; lo que falta, como desconocido.

    Con la TV apagada no se da ningún volumen ni contenido, aunque HA conserve un valor anterior: no es el actual. El
    título de lo que se ve no se dice por VOZ (en voz alta lo oye cualquiera en la sala)."""
    valor = str(estado.get("state", "?"))
    atributos = estado.get("attributes") or {}
    if valor not in _ENCENDIDOS | _APAGADOS:
        return f"No lo sé: Home Assistant da {nombre} como «{valor}», así que no puedo decirte cómo está."
    encendida = valor in _ENCENDIDOS
    if aspecto in ("encendida", "apagada"):
        afirma = encendida if aspecto == "encendida" else not encendida
        como = "encendida" if encendida else "apagada"
        return (
            f"{'Sí' if afirma else 'No'}: {nombre} está {como} "
            f"(según Home Assistant{_cuando(estado.get('last_changed'))})."
        )
    if not encendida:
        que = "el volumen" if aspecto == "volumen" else "qué está poniendo"
        return f"{_mayuscula(nombre)} está apagada (según Home Assistant): no puedo decirte {que}, porque no lo sé."
    if aspecto == "volumen":
        nivel = atributos.get("volume_level")
        if not isinstance(nivel, (int, float)) or isinstance(nivel, bool):
            return f"{_mayuscula(nombre)} está encendida, pero Home Assistant no expone su volumen: no lo sé."
        silencio = atributos.get("is_volume_muted")
        sonido = (
            "silenciada" if silencio is True else "con sonido" if silencio is False else "sin saber si está silenciada"
        )
        return f"{_mayuscula(nombre)} está a {round(nivel * 100)} de volumen, {sonido} (según Home Assistant)."
    partes = []
    if atributos.get("source"):
        partes.append(f"la fuente «{atributos['source']}»")
    if atributos.get("app_name"):
        partes.append(f"la aplicación «{atributos['app_name']}»")
    titulo = atributos.get("media_title")
    if not partes and not titulo:
        return f"{_mayuscula(nombre)} está encendida, pero Home Assistant no dice qué está poniendo: no lo sé."
    frase = f"{_mayuscula(nombre)} está encendida"
    if partes:
        frase += " en " + " y ".join(partes)
    if titulo and not por_voz:
        frase += f", con «{titulo}»"
    frase += " (según Home Assistant)."
    if titulo and por_voz:
        frase += " El título solo te lo digo por escrito."
    return frase
