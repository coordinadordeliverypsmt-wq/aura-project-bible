"""Conector de contexto: computador principal (M3.0).

Segunda fuente de M3. Deriva patrones de uso del audit log que escribe `AdaptadorComputador`.
"""

from __future__ import annotations

from .auditoria import ConectorDeAuditoria


class ConectorComputador(ConectorDeAuditoria):
    nombre = "computador"
    _MODULO = "computador"
