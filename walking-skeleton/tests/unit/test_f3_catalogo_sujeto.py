"""RED · F3 — catálogo de operaciones sobre información del usuario + dimensión `sujeto`.

**`DP-D-M-8 §4.2`** declara dos huecos y su remedio, literalmente: *«No existe entrada para crear
información sobre la persona»* y *«No se distingue el sujeto»*; *«la política se resuelve con el par
`(operacion, sujeto)`. Se añaden como mínimo `registrar_informacion_usuario`,
`olvidar_informacion_usuario`, `refutar_informacion_usuario`»*. Nada de eso se inventa aquí.

**Por qué VERDES y no rojas** — lo determina `§4.3`, no una preferencia: *«un "olvida esto" que
pidiera confirmación sería hostil, y ADR-0017 defiende que el usuario mande sobre sus datos»*, y la
tensión se disuelve porque *«pasar por el motor no es lo mismo que pedir confirmación»*. Atraviesan
el motor —dry-run, permisos, kill switch— **sin** HITL.

**El sujeto es fail-closed:** una operación que recae sobre una persona y no dice sobre quién no se
ejecuta. `§4.2` existe precisamente porque borrar un temporal y borrar un hecho clínico eran
indistinguibles para el catálogo.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.permissions import (
    ALTERA_ESTADO,
    CATALOGO,
    RED,
    SUJETO_REQUERIDO,
    PermissionManager,
)

OPERACIONES = ("registrar_informacion_usuario", "olvidar_informacion_usuario", "refutar_informacion_usuario")


async def _nunca_confirma(accion, args, trace_id):
    """Si algo se autorizara por HITL, esta prueba lo delataría: aquí nadie confirma nada."""
    raise AssertionError(f"no debía pedirse confirmación para {accion}")


def _permisos():
    return PermissionManager(_nunca_confirma)


# ============================================================ EL CATÁLOGO --


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_f3_la_operacion_esta_catalogada(operacion):
    assert operacion in CATALOGO, f"§4.2 la exige: '{operacion}'"


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_f3_declara_su_sujeto(operacion):
    assert CATALOGO[operacion].get("sujeto") == "usuario", (
        f"'{operacion}' recae sobre una persona y debe declararlo (§4.2)")


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_f3_no_es_lista_roja(operacion):
    """§4.3: pasar por el motor no es pedir confirmación. Si fueran rojas, «olvida esto» preguntaría."""
    assert operacion not in RED


def test_f3_olvidar_y_registrar_exigen_dry_run():
    """Alteran estado persistente, luego el motor debe exigirles plan previo (ALERTA-005)."""
    assert "olvidar_informacion_usuario" in ALTERA_ESTADO
    assert "registrar_informacion_usuario" in ALTERA_ESTADO
    assert "refutar_informacion_usuario" in ALTERA_ESTADO


def test_f3_no_hay_segunda_via_de_clasificacion():
    """`SUJETO_REQUERIDO` debe DERIVARSE del catálogo, no ser una lista escrita a mano que pueda
    divergir de él — el mismo criterio con el que ya se derivan `RED` y `ALTERA_ESTADO`."""
    assert SUJETO_REQUERIDO == {a for a, m in CATALOGO.items() if m.get("sujeto") == "usuario"}


# ================================================== EL SUJETO, EN authorize --


@pytest.mark.parametrize("operacion", OPERACIONES)
async def test_f3_con_sujeto_valido_la_operacion_se_autoriza(operacion):
    """**Meta-control del sujeto.** Sin él, un `authorize` que denegara SIEMPRE pasaría las pruebas
    de abajo y el catálogo parecería correcto estando roto."""
    ok, motivo = await _permisos().authorize(operacion, {"user_id": "mauricio"}, "t-f3")
    assert ok is True, f"{operacion} con sujeto válido fue denegada: {motivo}"


@pytest.mark.parametrize("operacion", OPERACIONES)
async def test_f3_sin_sujeto_la_operacion_se_deniega(operacion):
    ok, motivo = await _permisos().authorize(operacion, {}, "t-f3")
    assert ok is False, f"{operacion} se autorizó sin decir sobre quién recae"
    assert "sujeto" in motivo.lower()


@pytest.mark.parametrize("valor", ["", "   ", None])
async def test_f3_un_sujeto_vacio_no_vale_como_sujeto(valor):
    """Presente pero vacío no es «declarado». Sin este caso, `args={"user_id": ""}` pasaría."""
    ok, _ = await _permisos().authorize("olvidar_informacion_usuario", {"user_id": valor}, "t-f3")
    assert ok is False


async def test_f3_una_operacion_sin_sujeto_requerido_no_exige_user_id():
    """El otro lado del riesgo: exigir sujeto a todo convertiría el control en un bloqueo general."""
    ok, _ = await _permisos().authorize("consulta", {}, "t-f3")
    assert ok is True


async def test_f3_control_lo_no_catalogado_se_sigue_denegando():
    """RN-2 intacta: F3 amplía el catálogo, no relaja la regla."""
    ok, motivo = await _permisos().authorize("operacion_que_nadie_declaro", {"user_id": "m"}, "t-f3")
    assert ok is False and "no clasificada" in motivo
