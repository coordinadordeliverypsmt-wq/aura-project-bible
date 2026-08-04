"""Integracion: la vida completa de una tarea esta gobernada, no solo su nacimiento.

Antes de este incremento la asimetria era exacta: crear trabajo exigia cinco requisitos, pero
`actualizar` hacia `replace(vigente, **campos)` SIN VALIDAR NADA. Cualquier componente podia reabrir
una tarea cerrada, cambiar su prioridad o su responsable sin declarar por que. El log append-only
dejaba rastro, pero auditar no es impedir.

UN UNICO PROTOCOLO PARA TODOS LOS AGENTES (CEO): Director, QA y los futuros Programador, Arquitecto,
Investigador, Seguridad y Documentacion usan esta misma ruta. No hay reglas distintas por agente.
"""

import pytest

from aura_skeleton.core.estado_operativo import (
    TRANSICIONES,
    AlmacenEstadoOperativo,
    Tarea,
    TransicionInvalida,
)


def _alm(tmp_path, estado="abierta"):
    a = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    a.registrar(Tarea(objetivo_id="obj", tarea_id="t-01", estado=estado, responsable="qa"))
    return a


def test_toda_transicion_exige_autoridad_y_causa(tmp_path):
    """Simetria con el nacimiento: si crear trabajo exige causa, cerrarlo tambien."""
    a = _alm(tmp_path)
    with pytest.raises(TransicionInvalida, match="autoridad y causa"):
        a.transitar("obj", "t-01", "terminada", autoridad="", causa="x")
    with pytest.raises(TransicionInvalida, match="autoridad y causa"):
        a.transitar("obj", "t-01", "terminada", autoridad="director", causa="")


def test_una_tarea_TERMINADA_no_puede_reabrirse(tmp_path):
    """`terminada` es FINAL. Antes se podia revertir sin declarar motivo alguno."""
    a = _alm(tmp_path, estado="terminada")
    with pytest.raises(TransicionInvalida, match="FINAL"):
        a.transitar("obj", "t-01", "abierta", autoridad="programador", causa="quiero rehacerla")


def test_una_tarea_DESCARTADA_es_definitiva(tmp_path):
    a = _alm(tmp_path, estado="descartada")
    with pytest.raises(TransicionInvalida, match="FINAL"):
        a.transitar("obj", "t-01", "en_curso", autoridad="qa", causa="reintento")


def test_una_bloqueada_SI_puede_desbloquearse(tmp_path):
    """CONTROL NEGATIVO: el protocolo no puede congelar el trabajo. Un bloqueo debe poder resolverse.

    Sin esta prueba, todo lo anterior pasaria con un sistema que prohibe cualquier transicion.
    """
    a = _alm(tmp_path, estado="bloqueada")
    t = a.transitar("obj", "t-01", "abierta", autoridad="director", causa="el ejecutor ya esta disponible")
    assert t.estado == "abierta"


def test_la_transicion_deja_evidencia_verificable(tmp_path):
    """Quien la hizo, desde donde, hacia donde y por que: auditable sin leer el codigo."""
    a = _alm(tmp_path)
    t = a.transitar("obj", "t-01", "terminada", autoridad="director", causa="motor:verificar_calidad:ejecutada")
    assert any("director:abierta->terminada" in e for e in t.evidencias)
    assert any("verificar_calidad" in e for e in t.evidencias)


def test_se_registran_los_intentos_para_aprender(tmp_path):
    """Material de aprendizaje: sin historial, AURORA repite trabajo pero no mejora en el."""
    a = _alm(tmp_path)
    a.transitar("obj", "t-01", "bloqueada", autoridad="director", causa="fallo 1")
    a.transitar("obj", "t-01", "abierta", autoridad="director", causa="reintento")
    t = a.transitar("obj", "t-01", "bloqueada", autoridad="director", causa="fallo 2")
    assert t.intentos == 2, f"debe contar los intentos de trabajo, lleva {t.intentos}"


def test_no_se_transita_una_tarea_inexistente(tmp_path):
    a = _alm(tmp_path)
    with pytest.raises(TransicionInvalida, match="no existe"):
        a.transitar("obj", "t-99", "terminada", autoridad="director", causa="x")


def test_los_estados_finales_no_tienen_salida_declarada():
    """La tabla es la fuente de verdad: si alguien añade una salida a un estado final, se rompe."""
    assert TRANSICIONES["terminada"] == () and TRANSICIONES["descartada"] == ()
    assert set(TRANSICIONES) == {"abierta", "en_curso", "bloqueada", "terminada", "descartada"}


def test_el_protocolo_sobrevive_al_reinicio(tmp_path):
    """El estado final persiste: otro proceso tampoco puede reabrir lo cerrado."""
    a = _alm(tmp_path)
    a.transitar("obj", "t-01", "terminada", autoridad="director", causa="hecho")

    otro = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    with pytest.raises(TransicionInvalida, match="FINAL"):
        otro.transitar("obj", "t-01", "abierta", autoridad="otro", causa="reabrir tras reiniciar")
