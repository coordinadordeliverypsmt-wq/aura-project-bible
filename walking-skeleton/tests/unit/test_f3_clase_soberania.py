"""RED · la TERCERA CLASE del catálogo — decisión del CEO 2026-08-25, `D-M8-2 = B`.

El vocabulario `verde|roja` no puede expresar la fila que `DP-D-M-8 §4.3` ya aprobó para «olvida
esto»: **kill switch sí · catálogo sí · dry-run sí · permisos sí · HITL NO por defecto · auditoría
sí · reversibilidad sí**. Verde la haría chocar con *«nada que altere o destruya puede estar en
verde»*; roja la haría chocar con `§4.3`, y `ADR-0003` no permite eximir del HITL a una acción roja.

La clase `soberania` expresa esa fila **sin tocar ninguna de las dos garantías anteriores**: la regla
estructural habla de *verde*, `ADR-0003` habla de *roja*.

**El nombre es consecuencia de la decisión B, no una atribución al contrato.** Se toma del
vocabulario ya usado por `ADR-0017` y por el propio `§4.3` («soberanía del usuario»).
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.permissions import (
    CATALOGO,
    GREEN,
    RED,
    SOBERANIA,
    SUJETO_REQUERIDO,
    PermissionManager,
)

OPERACIONES = ("registrar_informacion_usuario", "olvidar_informacion_usuario", "refutar_informacion_usuario")


async def _nunca_confirma(accion, args, trace_id):
    raise AssertionError(f"HITL no procede para {accion} (§4.3: «No por defecto»)")


async def _confirma(accion, args, trace_id):
    return True


# ================================================== LA CLASE Y SUS FRONTERAS --


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_pertenece_a_la_clase_soberania(operacion):
    assert operacion in SOBERANIA


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_no_es_verde_ni_roja(operacion):
    """Las dos garantías previas siguen intactas **porque estas operaciones no las tocan**."""
    assert operacion not in GREEN, "en verde chocaría con la regla estructural de reversibilidad"
    assert operacion not in RED, "en roja chocaría con §4.3, y ADR-0003 no permite eximir del HITL"


def test_las_tres_clases_particionan_el_catalogo():
    """Reformulación de `GREEN | RED == CATALOGO`: **la garantía no se elimina, se amplía**. Toda
    operación catalogada sigue teniendo exactamente UNA clasificación válida."""
    assert GREEN | RED | SOBERANIA == set(CATALOGO)
    assert GREEN.isdisjoint(RED) and GREEN.isdisjoint(SOBERANIA) and RED.isdisjoint(SOBERANIA)


def test_no_hay_segunda_via_de_clasificacion():
    """Una sola fuente de verdad: las tres clases se DERIVAN del mismo catálogo."""
    assert SOBERANIA == {a for a, m in CATALOGO.items() if m["lista"] == "soberania"}


def test_la_clase_soberania_no_se_extiende_sola():
    """D23 sigue cerrado: la clase existe para las tres operaciones que §4.2 nombra, ni una más."""
    assert SOBERANIA == set(OPERACIONES)


# ============================================================== LA POLÍTICA --


@pytest.mark.parametrize("operacion", OPERACIONES)
async def test_no_pide_confirmacion_por_defecto(operacion):
    """`§4.3`: HITL **No por defecto**. `_nunca_confirma` revienta si alguien pregunta."""
    ok, _ = await PermissionManager(_nunca_confirma).authorize(operacion, {"user_id": "mauricio"}, "t")
    assert ok is True


@pytest.mark.parametrize("operacion", OPERACIONES)
async def test_sigue_exigiendo_sujeto(operacion):
    """Eximir de HITL no exime de nada más — §4.3 lo dice con esas palabras."""
    assert operacion in SUJETO_REQUERIDO
    ok, motivo = await PermissionManager(_confirma).authorize(operacion, {}, "t")
    assert ok is False and "sujeto" in motivo.lower()


@pytest.mark.parametrize("operacion", OPERACIONES)
async def test_sigue_sometida_al_kill_switch(operacion):
    """El Paso 0 no cambia de sitio ni de orden: F2 intacta."""
    from aura_skeleton.core.kill_switch import KillSwitch
    kill = KillSwitch(trigger_file="/tmp/aura-inexistente-soberania")
    kill.engage("prueba")
    ok, motivo = await PermissionManager(_confirma, kill_switch=kill).authorize(
        operacion, {"user_id": "mauricio"}, "t")
    assert ok is False and "kill switch" in motivo


def test_siguen_exigiendo_dry_run():
    """Reversibilidad: §4.3 la marca «Sí». El plan dice QUÉ se va a borrar antes de borrarlo."""
    from aura_skeleton.core.permissions import ALTERA_ESTADO
    for operacion in OPERACIONES:
        assert operacion in ALTERA_ESTADO


# ========================================================== CONTROLES CRUZADOS --


async def _niega(accion, args, trace_id):
    return False


async def test_control_las_rojas_siguen_exigiendo_confirmacion():
    """ADR-0003 intacto: la clase nueva no relaja la roja."""
    ok, _ = await PermissionManager(_niega).authorize("borrar_archivo", {}, "t")
    assert ok is False


async def test_control_lo_no_catalogado_se_sigue_denegando():
    ok, motivo = await PermissionManager(_confirma).authorize("nada_de_esto_existe", {"user_id": "m"}, "t")
    assert ok is False and "no clasificada" in motivo
