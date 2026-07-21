"""Conector de contexto: hogar inteligente (M3.0).

Tercera fuente de M3. Deriva patrones de uso del audit log del adaptador de Home Assistant.

En M3 la fuente es todavia el adaptador simulado; el conector no cambia cuando se conecte Home
Assistant real (M3.1), porque lee el audit log y no el dispositivo. Es la ventaja de derivar las
senales del registro forense y no de instrumentar cada integracion por separado.
"""

from __future__ import annotations

from .auditoria import ConectorDeAuditoria


class ConectorHogar(ConectorDeAuditoria):
    nombre = "home_assistant"
    _MODULO = "ha-adapter"
