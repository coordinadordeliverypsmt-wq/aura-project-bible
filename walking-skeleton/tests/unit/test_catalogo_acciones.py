"""H3 (M2.0) — Cobertura parametrizada del catalogo explicito de acciones.

Se recorre el catalogo COMPLETO, no una muestra: en M2 un falso negativo en la lista roja puede
destruir datos irrecuperables (riesgo RN-1 del Architecture Review M2 Entry).
"""

import pytest

from aura_skeleton.core.permissions import CATALOGO, GREEN, RED, PermissionManager


async def _niega(action, args, tid):
    return False


async def _confirma(action, args, tid):
    return True


def test_catalogo_es_la_unica_fuente_de_verdad():
    assert GREEN == {a for a, m in CATALOGO.items() if m["lista"] == "verde"}
    assert RED == {a for a, m in CATALOGO.items() if m["lista"] == "roja"}
    assert GREEN.isdisjoint(RED)
    assert GREEN | RED == set(CATALOGO)


@pytest.mark.parametrize("accion", sorted(RED))
@pytest.mark.asyncio
async def test_toda_accion_roja_exige_confirmacion(accion):
    """Ninguna accion roja se ejecuta sin confirmacion explicita. Tolerancia cero (2.5 §5.4)."""
    ok, _ = await PermissionManager(_niega).authorize(accion, {}, "t")
    assert ok is False, f"'{accion}' se autorizo sin confirmacion (falso negativo HITL)"


@pytest.mark.parametrize("accion", sorted(RED))
@pytest.mark.asyncio
async def test_accion_roja_confirmada_procede(accion):
    """Confirmada por el usuario, la accion roja procede: el guardarrail no es un bloqueo ciego."""
    ok, _ = await PermissionManager(_confirma).authorize(accion, {}, "t")
    assert ok is True


@pytest.mark.parametrize("accion", sorted(GREEN))
@pytest.mark.asyncio
async def test_toda_accion_verde_se_autoejecuta(accion):
    """Las verdes no molestan al usuario: si pidieran confirmacion, el sistema seria inusable."""
    ok, _ = await PermissionManager(_niega).authorize(accion, {}, "t")
    assert ok is True, f"'{accion}' pidio confirmacion siendo de lista verde"


@pytest.mark.parametrize("accion,meta", sorted(CATALOGO.items()))
def test_toda_accion_declara_efecto_y_descripcion(accion, meta):
    """El catalogo debe ser autodescriptivo: sin metadatos no se puede auditar la clasificacion."""
    assert meta["lista"] in ("verde", "roja")
    assert meta["efecto"] in ("ninguno", "interno", "lectura", "reversible", "altera", "destruye", "externo")
    assert meta["desc"], f"'{accion}' sin descripcion"


@pytest.mark.parametrize("accion,meta", sorted(CATALOGO.items()))
def test_criterio_de_reversibilidad_es_coherente(accion, meta):
    """Regla estructural: nada que altere o destruya puede estar en verde.

    Esta prueba impide que una futura ampliacion del catalogo cuele una accion destructiva en la
    lista verde por descuido. Verifica el CRITERIO, no cada caso particular.
    """
    if meta["efecto"] in ("altera", "destruye", "externo"):
        assert meta["lista"] == "roja", f"'{accion}' tiene efecto '{meta['efecto']}' y esta en verde"
