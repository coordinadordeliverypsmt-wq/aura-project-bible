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


def _clasificar(texto_norm: str) -> ClaseSenal | None:
    """Una sola clase por enunciado, de la mas especifica a la mas general."""
    if any(m in texto_norm for m in _FEEDBACK):
        return ClaseSenal.FEEDBACK_DIRECTO
    if any(m in texto_norm for m in _CORRECCION):
        return ClaseSenal.CORRECCION
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
