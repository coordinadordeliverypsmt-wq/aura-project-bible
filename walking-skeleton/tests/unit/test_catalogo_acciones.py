"""H3 (M2.0) — Cobertura parametrizada del catalogo explicito de acciones.

Se recorre el catalogo COMPLETO, no una muestra: en M2 un falso negativo en la lista roja puede
destruir datos irrecuperables (riesgo RN-1 del Architecture Review M2 Entry).
"""

import pytest

from aura_skeleton.core.permissions import CATALOGO, GREEN, RED, SOBERANIA, PermissionManager


async def _niega(action, args, tid):
    return False


async def _confirma(action, args, tid):
    return True


def test_catalogo_es_la_unica_fuente_de_verdad():
    """AMPLIADA 2026-08-25 (D-M8-2 = B). La garantia NO se retira: sigue exigiendo que toda accion
    catalogada tenga **exactamente una** clasificacion valida. Lo que cambia es que ahora hay tres
    clases y no dos, porque el vocabulario anterior no podia expresar la fila que `§4.3` aprobo."""
    assert GREEN == {a for a, m in CATALOGO.items() if m["lista"] == "verde"}
    assert RED == {a for a, m in CATALOGO.items() if m["lista"] == "roja"}
    assert SOBERANIA == {a for a, m in CATALOGO.items() if m["lista"] == "soberania"}
    assert GREEN.isdisjoint(RED) and GREEN.isdisjoint(SOBERANIA) and RED.isdisjoint(SOBERANIA)
    assert GREEN | RED | SOBERANIA == set(CATALOGO)


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
    assert meta["lista"] in ("verde", "roja", "soberania")
    assert meta["efecto"] in ("ninguno", "interno", "lectura", "reversible", "altera", "destruye", "externo")
    assert meta["desc"], f"'{accion}' sin descripcion"


@pytest.mark.parametrize("accion,meta", sorted(CATALOGO.items()))
def test_criterio_de_reversibilidad_es_coherente(accion, meta):
    """Regla estructural: nada que altere o destruya puede estar en verde.

    Esta prueba impide que una futura ampliacion del catalogo cuele una accion destructiva en la
    lista verde por descuido. Verifica el CRITERIO, no cada caso particular.
    """
    # REFORMULADA 2026-08-25 (D-M8-2 = B). El proposito NO cambia: impedir que algo destructivo se
    # cuele en AUTO-EJECUCION SIN CONTROL. Lo que cambia es que ya existe una tercera clase que
    # tampoco es auto-ejecucion libre: `soberania` pasa kill switch, catalogo, sujeto, dry-run,
    # permisos y auditoria — solo se exime de preguntar, porque el usuario lo esta pidiendo (§4.3).
    # Seguir exigiendo `== "roja"` habria obligado a que «olvida esto» pidiera confirmacion, que es
    # exactamente lo que §4.3 declara hostil.
    if meta["efecto"] in ("altera", "destruye", "externo"):
        assert meta["lista"] != "verde", f"'{accion}' tiene efecto '{meta['efecto']}' y esta en verde"
        assert meta["lista"] in ("roja", "soberania")
        if meta["lista"] == "soberania":
            # la exencion de HITL no es gratuita: se paga declarando el sujeto sobre el que recae
            assert meta.get("sujeto") == "usuario", f"'{accion}' es soberania y no declara sujeto"
