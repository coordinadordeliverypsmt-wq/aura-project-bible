"""Integracion: AURORA explica POR QUE no pudo continuar, sin cambiar el contrato de Tarea.

EL CEO NO AUTORIZO evolucionar `Tarea.bloqueos` de texto libre a categorias hasta tener evidencia de
que el modelo actual impedia avanzar. La evidencia dice lo contrario: los motivos que el propio ciclo
escribe SON distinguibles, asi que la clasificacion se DERIVA y el contrato no se toca.

Los textos de estas pruebas no son inventados: son los que AURORA produjo al intentar construir su
Centro de Gobierno en los dos experimentos del 2026-08-04.
"""

import pytest

from aura_skeleton.core.autodiagnostico import (
    CAPACIDAD_INEXISTENTE,
    CRITERIO_CEO,
    INFRAESTRUCTURA,
    SIN_CLASIFICAR,
    clasificar_bloqueo,
)

# Motivos REALES observados, con la categoria que les corresponde.
_REALES = [
    ("ningun ejecutor atiende al responsable 'documentacion'", CAPACIDAD_INEXISTENTE),
    ("detenida: dry-run no viable: un cambio necesita fichero y patron a sustituir", CAPACIDAD_INEXISTENTE),
    ("veredicto negativo: 2 garantia(s) declaradas ya no protegen nada", INFRAESTRUCTURA),
    ("detenida: el adaptador no soporta dry-run y la accion altera el estado", INFRAESTRUCTURA),
    ("detenida: permisos: kill switch activo", CRITERIO_CEO),
]


@pytest.mark.parametrize("motivo,esperada", _REALES)
def test_los_bloqueos_REALES_se_clasifican_sin_cambiar_el_contrato(motivo, esperada):
    assert clasificar_bloqueo(motivo) == esperada, f"no supo clasificar: {motivo!r}"


def test_dos_bloqueos_DISTINTOS_no_caen_en_la_misma_categoria():
    """La condicion que el CEO fijo para autorizar el cambio de contrato: si dos bloqueos diferentes
    se expresaran igual, el modelo actual no bastaria. Se comprueba que no ocurre."""
    categorias = {clasificar_bloqueo(m) for m, _ in _REALES}
    assert len(categorias) >= 3, f"los motivos reales colapsan en {categorias}: haria falta estructurarlos"


def test_lo_que_no_encaja_se_declara_SIN_CLASIFICAR_en_vez_de_forzarse():
    """Un bloqueo mal clasificado es peor que uno sin clasificar: dirige el trabajo al sitio equivocado."""
    assert clasificar_bloqueo("algo que nadie previo") == SIN_CLASIFICAR
    assert clasificar_bloqueo("") == SIN_CLASIFICAR


def test_CONTROL_no_clasifica_todo_igual():
    """Sin esto, un clasificador que devolviera siempre la misma categoria pasaria las demas pruebas."""
    assert clasificar_bloqueo("ningun ejecutor atiende") != clasificar_bloqueo("no protegen nada")
