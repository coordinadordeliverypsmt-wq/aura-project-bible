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
    r"\bmi (amig|herman|jef|vecin|madre|padre|hij|espos|pareja)\w*\b",
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


def _es_hecho_declarado(texto_norm: str) -> bool:
    """Marcador de declaracion sobre uno mismo, SIN marca temporal y que no sea una PREGUNTA.

    La tercera condicion de la regla -sujeto = el usuario- la aplica `_habla_de_tercero` en
    `recoger`, igual que para el resto de clases: no se duplica aqui.

    LA GUARDA INTERROGATIVA la destapo una prueba, no el diseno: "¿Como me llamo?" contiene el
    marcador "me llamo" y se estaba capturando como hecho. Preguntar por un dato habria escrito la
    pregunta EN EL MODELO DE USUARIO -- el usuario contaminaria su propio perfil cada vez que
    consultase algo. Preguntar no es declarar, y la distincion tiene que ser explicita.
    """
    if "?" in texto_norm or "¿" in texto_norm:
        return False
    if any(re.search(p, texto_norm) for p in _INTERROGATIVOS_INICIALES):
        return False
    if any(re.search(p, texto_norm) for p in _TEMPORAL):
        return False
    return any(re.search(p, texto_norm) for p in _HECHO)


def _clasificar(texto_norm: str) -> ClaseSenal | None:
    """Una sola clase por enunciado, de la mas especifica a la mas general.

    `HECHO_DECLARADO` va ANTES que la preferencia porque es mas especifico: exige una construccion
    declarativa completa, mientras que la preferencia se reconoce por un marcador suelto.
    """
    if any(m in texto_norm for m in _FEEDBACK):
        return ClaseSenal.FEEDBACK_DIRECTO
    if any(m in texto_norm for m in _CORRECCION):
        return ClaseSenal.CORRECCION
    if _es_hecho_declarado(texto_norm):
        return ClaseSenal.HECHO_DECLARADO
    if any(m in texto_norm for m in _PREFERENCIA):
        return ClaseSenal.PREFERENCIA_DECLARADA
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
