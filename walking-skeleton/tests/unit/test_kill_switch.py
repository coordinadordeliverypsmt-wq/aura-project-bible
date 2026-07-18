"""Unit M1.2: Kill Switch — parada de emergencia reversible y auditable (Bible 5.3 §5)."""

import pytest

from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.permissions import PermissionManager


def test_engage_disengage(tmp_path):
    ks = KillSwitch(str(tmp_path / "KILL"))
    assert ks.is_engaged() is False
    ks.engage("prueba")
    assert ks.is_engaged() is True
    ks.disengage()
    assert ks.is_engaged() is False


def test_disparo_fuera_de_banda(tmp_path):
    f = tmp_path / "KILL"
    ks = KillSwitch(str(f))
    f.write_text("activado por archivo")  # fuera de banda (AURA comprometida)
    assert ks.is_engaged() is True


@pytest.mark.asyncio
async def test_kill_switch_bloquea_toda_accion(tmp_path):
    async def yes(a, args, t):
        return True

    ks = KillSwitch(str(tmp_path / "KILL"))
    pm = PermissionManager(yes, kill_switch=ks)
    ks.engage("emergencia")
    ok_verde, _ = await pm.authorize("encender_dispositivo", {}, "t")  # lista verde
    ok_roja, _ = await pm.authorize("pago", {}, "t")  # lista roja
    assert ok_verde is False and ok_roja is False  # NINGUNA accion se ejecuta


@pytest.mark.asyncio
async def test_reanuda_tras_desactivar(tmp_path):
    async def yes(a, args, t):
        return True

    ks = KillSwitch(str(tmp_path / "KILL"))
    pm = PermissionManager(yes, kill_switch=ks)
    ks.engage("x")
    ks.disengage()
    ok, _ = await pm.authorize("encender_dispositivo", {}, "t")
    assert ok is True  # reversible
