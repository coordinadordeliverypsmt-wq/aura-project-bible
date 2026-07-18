"""Unit: Gestor de Permisos y listas de autonomia (ADR-0003 / Bible 5.3)."""

import pytest

from aura_skeleton.core.permissions import GREEN, RED, PermissionManager


async def _confirm_yes(a, args, t):
    return True


async def _confirm_no(a, args, t):
    return False


@pytest.mark.asyncio
async def test_lista_verde_auto():
    pm = PermissionManager(_confirm_no)
    ok, reason = await pm.authorize("encender_dispositivo", {}, "t")
    assert ok is True and "verde" in reason


@pytest.mark.asyncio
async def test_lista_roja_requiere_confirmacion():
    pm = PermissionManager(_confirm_no)
    ok, _ = await pm.authorize("eliminar_informacion", {}, "t")  # usuario deniega
    assert ok is False  # tolerancia cero a falsos negativos (2.5 5.4)


@pytest.mark.asyncio
async def test_lista_roja_confirmada():
    pm = PermissionManager(_confirm_yes)
    ok, _ = await pm.authorize("pago", {}, "t")
    assert ok is True


@pytest.mark.asyncio
async def test_desconocida_deny_por_defecto():
    pm = PermissionManager(_confirm_yes)
    ok, _ = await pm.authorize("accion_inexistente", {}, "t")
    assert ok is False


def test_listas_no_se_solapan():
    assert GREEN.isdisjoint(RED)
