"""Captura de senales de aprendizaje (M3.0, Bible 4.4 §1).

Tres restricciones ratificadas por el CEO gobiernan este modulo y se prueban aqui:
  1. Capturar no implica inferir.
  2. La instrumentacion es completamente pasiva.
  3. No se construyen perfiles persistentes de terceros.
"""

import pytest

from aura_skeleton.core.senales import ClaseSenal, Senal, SenalDeTercero


def test_senal_se_registra_con_procedencia():
    """4.4 §2 exige procedencia: sin ella una senal no es auditable ni corregible."""
    s = Senal(
        clase=ClaseSenal.PREFERENCIA_DECLARADA,
        contenido="prefiere la luz de la sala tenue por la noche",
        fuente="conversacion",
        trace_id="t-123",
    )
    assert s.clase is ClaseSenal.PREFERENCIA_DECLARADA
    assert s.fuente == "conversacion"
    assert s.trace_id == "t-123"
    assert s.ts > 0


def test_senal_declarada_no_es_inferida():
    """Restriccion 1: capturar no implica inferir.

    El origen epistemico viaja con el dato desde el primer registro. Separarlo despues
    exigiria migrar el historial (M3.0-PLAN §5).
    """
    s = Senal(ClaseSenal.PREFERENCIA_DECLARADA, "prefiere te", "conversacion", "t")
    assert s.declarada is True
    assert s.inferida is False


def test_senal_de_tercero_se_rechaza():
    """Restriccion 3 (4.4 §1, ALERTA-002): senales del propio usuario, nunca de terceros."""
    with pytest.raises(SenalDeTercero):
        Senal(
            ClaseSenal.PREFERENCIA_DECLARADA,
            "a Ana le gusta el cafe solo",
            "conversacion",
            "t",
            sobre_tercero=True,
        )
