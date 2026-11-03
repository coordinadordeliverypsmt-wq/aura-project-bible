"""Conector de contexto: conversacion (M3.0).

Primera de las tres fuentes que M3 instrumenta. Cumple `core.contexto.ProveedorContexto`.

Observa lo que el usuario **dice explicitamente** sobre sus preferencias. No deduce nada: si el
usuario no lo declara, aqui no se registra (restriccion 1, "capturar no implica inferir").

Los patrones son deliberadamente conservadores. Un capturador que marcase demasiadas frases como
preferencia envenenaria el modelo del usuario con ruido, y el coste de ese error se paga mucho
despues —en M3.2, al inferir sobre datos malos—, cuando ya es caro de deshacer. Ante la duda, no se
captura: una senal perdida se vuelve a observar la proxima vez que el usuario lo diga; una senal
falsa se queda.
"""

from __future__ import annotations

import re
import unicodedata

from ..core.senales import ClaseSenal, Senal, SenalDeTercero

_FUENTE = "conversacion"

# Marcadores de preferencia declarada en primera persona. El sujeto importa: "prefiero" es una
# senal del usuario; "a Ana le gusta" versa sobre un tercero y queda excluido (restriccion 3).
_PREFERENCIA = (
    "prefiero",
    "me gusta",
    "no me gusta",
    "odio",
    "suelo",
    "acostumbro",
    "siempre quiero",
    "nunca quiero",
)
_CORRECCION = ("no, ", "asi no", "te equivocas", "esta mal", "no es eso", "corrige")
_FEEDBACK = ("no me gusta que", "deja de", "no vuelvas a", "me molesta")

# Indicios de que la frase versa sobre otra persona. Se comprueba ANTES que las preferencias:
# "a Ana le gusta el cafe" contiene "me gusta"... no, contiene "le gusta"; pero "a mi hermana y a mi
# nos gusta" mezcla sujetos. Ante la mezcla, no se captura.
_TERCERO = (
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


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _habla_de_tercero(texto_norm: str) -> bool:
    return any(re.search(p, texto_norm) for p in _TERCERO)


# HECHOS DECLARADOS SOBRE UNO MISMO (Bible 4.4 §1, acta del CEO 2026-08-09). Alcance cerrado por el
# CEO: nombre, ocupacion y proyecto. La preferencia ya la cubria `_PREFERENCIA`.
#
# Marcadores DE DECLARACION, no de tema: exigen la construccion completa ("me llamo", "trabajo en"),
# nunca la palabra suelta. Es la misma disciplina que ya rige este fichero y que `_es_cancelacion_de_regla`
# aprendio el 2026-08-02: un marcador aislado aparece en frases mundanas que no declaran nada.
_HECHO = (
    r"\bme llamo\b",
    r"\bmi nombre es\b",
    r"\btrabajo en\b",
    r"\btrabajo de\b",
    r"\bproyecto llamado\b",
    r"\bmi proyecto se llama\b",
    # COLOR FAVORITO (CEO, 2026-09-10). Medido antes de esto: el enunciado no se clasificaba -ni hecho
    # ni preferencia-, asi que se guardaba SIN clase y `_responder_hecho` no podia verlo; la pregunta
    # caia al modelo, que devolvio «amarillo» donde el usuario habia dicho «azul».
    #
    # Es un HECHO y no una PREFERENCIA porque exige la CONSTRUCCION DECLARATIVA COMPLETA: es verdadero
    # o falso respecto de lo que el usuario dijo. «me gusta el azul» -marcador suelto de gusto- sigue
    # siendo `PREFERENCIA_DECLARADA`, y la precedencia de `_clasificar` lo garantiza sin tocarla.
    # El patron especifico de «mi color favorito es» ESTUVO AQUI y se retiro el 2026-09-10: la apertura
    # posesiva de abajo lo absorbe por completo, y dejarlo seria codigo muerto que aparenta cobertura
    # -la verificacion de mutacion lo demostro: romperlo no cambiaba nada porque el generico capturaba
    # la frase igual-. La garantia no se pierde: la cubre el mutante del patron generico.
    # APERTURA POSESIVA GENERICA (CEO, 2026-09-10). Sustituye el goteo de un patron por atributo: «mi
    # cumpleanos es el 10 de mayo» o «mi telefono es 600123456» no se guardaban, asi que no habia nada
    # que responder y la pregunta caia al modelo -que ya deformo un hecho: «azul» -> «amarillo»-.
    #
    # UNO O DOS terminos, no mas: acota el atributo a algo nombrable («color favorito», «cumpleanos»)
    # y evita tragarse oraciones enteras. La proteccion contra terceros va DELANTE, en
    # `_es_hecho_declarado`, no solo en la captura.
    r"\bmi [a-z]+(?: [a-z]+)? es\b",
)

# TERCERA CONDICION de la regla de promocion: el atributo debe ser ESTABLE. Un marcador temporal
# delata un estado pasajero, y el CEO lo puso como criterio explicito: "Hoy estoy cansado" puede
# quedar como episodica, pero NO puede convertirse en "el usuario esta cansado permanentemente".
# Tambien protege "hoy trabajo en casa", que SI lleva marcador de hecho pero describe un dia.
_TEMPORAL = (
    r"\bhoy\b",
    r"\bahora\b",
    r"\beste rato\b",
    r"\besta semana\b",
    r"\besta manana\b",
    r"\besta tarde\b",
    r"\bestos dias\b",
    r"\bpor ahora\b",
)


# Sin signos de interrogacion -el dictado por voz no siempre los produce-, una pregunta se reconoce
# por el interrogativo INICIAL. Solo al principio: "trabajo en donde me mandaron" es una declaracion.
_INTERROGATIVOS_INICIALES = (r"^(como|cual|cuales|que|quien|donde|cuando|cuanto|sabes|recuerdas|dime|cuentame)\b",)

# CUARTA CONDICION: la frase debe AFIRMAR el hecho del usuario, en presente y sin intermediarios.
# Todas estas construcciones llevan marcador de hecho y NO declaran nada -- una auditoria las midio
# entrando en el perfil: "No trabajo en logistica" hacia que AURORA afirmase lo contrario de lo
# dicho, y "Me dijo: me llamo Ana" le hacia afirmar el nombre de OTRA persona como si fuera el del
# usuario (INV-9). Un perfil envenenado se paga migrando historial real.
_NO_AFIRMA = (
    r"^no\b",  # negacion: "no trabajo en logistica"
    r"\bno (?:me llamo|trabajo|es)\b",
    r"^si\b",  # condicional: "si trabajo en Madrid me mudo"
    r"\bsi (?:trabajo|me llamo)\b",
    r"\b(?:me|te|le|nos|les) dijo\b",  # cita: el hecho es de otro
    r"\bdijo que\b",
    r"\bantes\b",  # pasado: "antes trabajo en banca"
    r"\bcuando (?:trabajaba|era|estudiaba)\b",
    r"\bojala\b",  # deseo, no hecho
    r"\balgun dia\b",
    r"\bme gustaria\b",
    r"\bcreo que\b",  # opinion, no hecho
    r"\bquizas?\b",
    r"\btal vez\b",
    r"\bya no es cierto\b",  # gobierno del propio modelo: refutar
    r"^olvida\b",  # gobierno del propio modelo: olvidar
    r"\bolvida que\b",
    r"\bcorrige\b",
)


def _es_pregunta(texto_norm: str) -> bool:
    """Signos de interrogacion, o interrogativo INICIAL -el dictado por voz no siempre produce los
    signos-. Solo al principio: "trabajo en donde me mandaron" es una declaracion."""
    if "?" in texto_norm or "¿" in texto_norm:
        return True
    return any(re.search(p, texto_norm) for p in _INTERROGATIVOS_INICIALES)


def _es_hecho_declarado(texto_norm: str) -> bool:
    """Marcador de declaracion sobre uno mismo, SIN marca temporal y que no sea una PREGUNTA.

    La tercera condicion de la regla -sujeto = el usuario- la aplica `_habla_de_tercero` en
    `recoger`, igual que para el resto de clases: no se duplica aqui.

    LA GUARDA INTERROGATIVA la destapo una prueba, no el diseno: "¿Como me llamo?" contiene el
    marcador "me llamo" y se estaba capturando como hecho. Preguntar por un dato habria escrito la
    pregunta EN EL MODELO DE USUARIO -- el usuario contaminaria su propio perfil cada vez que
    consultase algo. Preguntar no es declarar, y la distincion tiene que ser explicita.
    """
    if _es_pregunta(texto_norm):
        return False
    if any(re.search(p, texto_norm) for p in _TEMPORAL):
        return False
    if any(re.search(p, texto_norm) for p in _NO_AFIRMA):
        return False
    # Un hecho sobre un TERCERO no es un hecho declarado del usuario, y la comprobacion va aqui -no
    # solo al construir la senal- porque la apertura posesiva la hace imprescindible: asi la clase
    # nunca llega a ser `HECHO_DECLARADO` para «mi abuela es enfermera».
    if _habla_de_tercero(texto_norm):
        return False
    return any(re.search(p, texto_norm) for p in _HECHO)


def _clasificar(texto_norm: str) -> ClaseSenal | None:
    """Una sola clase por enunciado, de la mas especifica a la mas general.

    `HECHO_DECLARADO` va ANTES que la preferencia porque es mas especifico: exige una construccion
    declarativa completa, mientras que la preferencia se reconoce por un marcador suelto.
    """
    # Preguntar no es declarar, para NINGUNA clase. La guarda interrogativa se corrigio primero solo
    # para los hechos y una auditoria midio el resto: "¿Que prefiero?" se guardaba como preferencia y
    # reaparecia en la respuesta siguiente, creciendo sin limite por el mero acto de consultar.
    if _es_pregunta(texto_norm):
        return None
    if any(m in texto_norm for m in _FEEDBACK):
        return ClaseSenal.FEEDBACK_DIRECTO
    if any(m in texto_norm for m in _CORRECCION):
        return ClaseSenal.CORRECCION
    if any(m in texto_norm for m in _PREFERENCIA):
        # La PREFERENCIA gana cuando ambos marcadores coinciden. "Prefiero el trabajo de noche"
        # contiene "trabajo de", pero declara un gusto, no una ocupacion: clasificarla como hecho
        # producia el etiquetado permanente erroneo que esta misma ampliacion existe para evitar,
        # y ademas vaciaba la respuesta de "¿que prefiero?" (medido en auditoria).
        return ClaseSenal.PREFERENCIA_DECLARADA
    if _es_hecho_declarado(texto_norm):
        return ClaseSenal.HECHO_DECLARADO
    return None


class ConectorConversacion:
    nombre = _FUENTE

    def __init__(self) -> None:
        self._pendientes: list[str] = []

    def observar(self, texto: str) -> None:
        """Registra un enunciado para su proxima recogida. NO lo interpreta todavia."""
        self._pendientes.append(texto)

    async def recoger(self, trace_id: str) -> list[Senal]:
        pendientes, self._pendientes = self._pendientes, []
        senales: list[Senal] = []
        for texto in pendientes:
            norm = _normalizar(texto)
            clase = _clasificar(norm)
            if clase is None:
                continue
            try:
                senales.append(Senal(clase, texto, _FUENTE, trace_id, sobre_tercero=_habla_de_tercero(norm)))
            except SenalDeTercero:
                # No es un error: es la restriccion funcionando. Se descarta en silencio porque
                # registrar "hubo una senal sobre un tercero" ya seria un rastro sobre esa persona.
                continue
        return senales


def es_declaracion_de_hecho_propio(texto: str) -> bool:
    """True si el usuario DECLARA un hecho sobre si mismo («me llamo Mauricio», «trabajo en logistica»).

    Es el MISMO criterio con el que la captura clasifica un enunciado como `HECHO_DECLARADO`: una sola
    definicion, no una segunda lista que pudiera divergir. Por eso excluye lo que la captura excluye
    -hechos de terceros, preferencias, estados de animo, preguntas-.

    Funcion pura y sin estado: no observa, no guarda ni encola nada. Que el hecho se registre sigue
    siendo asunto exclusivo de `ConectorConversacion.recoger`; quien consulta esta funcion solo sabe
    QUE CLASE de enunciado es, nunca si la captura llego a guardarlo.
    """
    return _clasificar(_normalizar(texto)) is ClaseSenal.HECHO_DECLARADO
