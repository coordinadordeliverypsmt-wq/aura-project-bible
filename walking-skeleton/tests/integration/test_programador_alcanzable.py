"""Integracion: el Programador es alcanzable DESDE EL MOTOR, no solo llamandolo directamente.

EL DEFECTO QUE CIERRA. `proponer_cambio` altera el estado, y el motor exige dry-run para toda accion
que altere. `EjecutorProgramador` no implementaba `simular`, asi que el motor la detenia con "el
adaptador no soporta dry-run": la capacidad estaba cableada, probada e INALCANZABLE desde el ciclo.
Las pruebas la ejercitaban directamente, nunca a traves del motor — por eso pasaban.

Es el patron ALERTA-004/005. Lo destapo AURORA al intentar construir su propio Centro de Gobierno.
"""

import asyncio

import pytest

from aura_skeleton.adapters.programador import EjecutorProgramador
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores


class VerificadorOK:
    async def execute(self, cap, args, tid, eid):
        return {"capacidad": cap, "ok": True, "resumen": "1 passed"}


async def _confirma(a, args, tid):
    return True


def _motor(tmp_path):
    (tmp_path / "m.py").write_text("VALOR = 1\n", encoding="utf-8")
    prog = EjecutorProgramador(str(tmp_path), VerificadorOK())
    return MotorAutomatizacion(RegistroAdaptadores([prog]), PermissionManager(_confirma)), prog


def test_EL_MOTOR_PUEDE_DESPACHAR_UN_CAMBIO(tmp_path):
    """La prueba que faltaba: el camino real, no la llamada directa."""
    motor, _ = _motor(tmp_path)

    res = asyncio.run(
        motor.ejecutar(
            "proponer_cambio",
            {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = 2"},
            "t",
            "e",
            origen="director:programador",
        )
    )

    assert res["estado"] == "ejecutada", f"el motor sigue sin poder despacharlo: {res.get('motivo')}"
    assert (tmp_path / "m.py").read_text(encoding="utf-8") == "VALOR = 2\n"


def test_el_dry_run_declara_el_efecto_antes_de_aplicar(tmp_path):
    """Lista roja: la confirmacion humana debe ser informada (ADR-0003)."""
    _, prog = _motor(tmp_path)

    plan = asyncio.run(
        prog.simular("proponer_cambio", {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = 2"}, "t")
    )

    assert plan["viable"] is True and "m.py" in plan["efecto"]
    assert (tmp_path / "m.py").read_text(encoding="utf-8") == "VALOR = 1\n", "simular NO puede aplicar nada"


def test_el_dry_run_RECHAZA_lo_que_execute_rechazaria(tmp_path):
    """CONTROL: si divergieran, el dry-run aprobaria un cambio y la ejecucion aplicaria otro."""
    motor, prog = _motor(tmp_path)
    args = {"fichero": "m.py", "buscar": "PATRON QUE NO EXISTE", "sustituir": "x"}

    plan = asyncio.run(prog.simular("proponer_cambio", args, "t"))
    res = asyncio.run(motor.ejecutar("proponer_cambio", args, "t", "e", origen="test"))

    assert plan["viable"] is False, "el dry-run debe rechazarlo"
    assert res["estado"] == "detenida", "y el motor debe detenerlo antes de tocar nada"


@pytest.mark.asyncio
async def test_el_dry_run_no_puede_escapar_del_arbol(tmp_path):
    _, prog = _motor(tmp_path)
    (tmp_path.parent / "fuera.py").write_text("X = 1\n", encoding="utf-8")
    plan = await prog.simular(
        "proponer_cambio", {"fichero": "../fuera.py", "buscar": "X = 1", "sustituir": "X = 2"}, "t"
    )
    assert plan["viable"] is False
