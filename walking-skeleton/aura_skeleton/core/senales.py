"""Senales de aprendizaje (M3.0, Bible 4.4 §1).

Tres restricciones ratificadas por el CEO gobiernan este modulo:

1. **Capturar no implica inferir.** M3.0 registra lo observado; no deduce preferencias. Esa
   inferencia es M3.2. El origen epistemico —declarado frente a inferido— viaja con el dato desde
   el primer registro: si no se distinguieran desde el principio, separarlos despues exigiria migrar
   el historial acumulado.

2. **La instrumentacion es pasiva.** Ninguna senal capturada altera el comportamiento del sistema en
   M3.0. Si la captura resulta mal disenada, el coste es un dato mal etiquetado, nunca una accion
   equivocada.

3. **Sin perfiles de terceros.** 4.4 §1 exige senales del propio usuario. Una conversacion puede
   mencionar a otra persona; su preferencia NO es capturable (ALERTA-002).
"""

from __future__ import annotations

import time
from enum import Enum


class ClaseSenal(Enum):
    """Las siete senales de 4.4 §1, en sus dos familias."""

    # Explicitas: el usuario las expresa.
    PREFERENCIA_DECLARADA = "preferencia_declarada"
    CORRECCION = "correccion"
    FEEDBACK_DIRECTO = "feedback_directo"
    # Un HECHO sobre uno mismo no es una PREFERENCIA (acta del CEO, 2026-08-09, Bible 4.4 §1).
    # Un nombre o una ocupacion no expresan gusto sino identidad o circunstancia: son verdaderos o
    # falsos, no preferidos. Registrarlos como preferencia etiquetaria mal el dato de forma
    # PERMANENTE, y §2 exige que la procedencia viaje con el desde el primer registro -- corregirlo
    # despues obligaria a migrar historial real del usuario. La distincion no anade capacidad:
    # anade veracidad al registro.
    HECHO_DECLARADO = "hecho_declarado"
    # Implicitas: se observan del uso.
    PATRON_DE_USO = "patron_de_uso"
    TEMA_RECURRENTE = "tema_recurrente"
    RESPUESTA_A_SUGERENCIA = "respuesta_a_sugerencia"


# Que familia es cada clase. Las explicitas son DECLARADAS por el usuario; las implicitas se
# observan. Ninguna de las dos es "inferida": inferir es sacar una conclusion nueva, y eso es M3.2.
_EXPLICITAS = {
    ClaseSenal.PREFERENCIA_DECLARADA,
    ClaseSenal.CORRECCION,
    ClaseSenal.FEEDBACK_DIRECTO,
    ClaseSenal.HECHO_DECLARADO,
}


class SenalDeTercero(Exception):
    """La senal versa sobre otra persona: no es capturable (4.4 §1, ALERTA-002)."""


class Senal:
    def __init__(
        self,
        clase: ClaseSenal,
        contenido: str,
        fuente: str,
        trace_id: str,
        sobre_tercero: bool = False,
        ts: float | None = None,
    ) -> None:
        if sobre_tercero:
            raise SenalDeTercero(f"senal sobre un tercero, no capturable: {clase.value}")
        self.clase = clase
        self.contenido = contenido
        self.fuente = fuente  # que proveedor de contexto la produjo
        self.trace_id = trace_id
        self.ts = ts if ts is not None else time.time()

    @property
    def declarada(self) -> bool:
        """El usuario la expreso explicitamente."""
        return self.clase in _EXPLICITAS

    @property
    def inferida(self) -> bool:
        """Siempre False en M3.0: la captura no infiere (restriccion 1)."""
        return False

    def __repr__(self) -> str:
        return f"<Senal {self.clase.value} de {self.fuente!r}>"
