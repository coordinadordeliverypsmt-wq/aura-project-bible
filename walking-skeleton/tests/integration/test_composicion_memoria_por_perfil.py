"""Integracion e2e (C2.2/C2.3): flujo Registry -> Manager -> Plan -> Composicion -> Memoria.

Valida que el arranque oficial (composicion) consulta el Capability Registry/Manager, obtiene un
PlanActivacion determinista a partir del PerfilHardware, y SELECCIONA la implementacion de memoria segun
ese plan. Hoy solo N1 (PersistentMemory) esta implementado; N2/N3 son latente-prevista.
"""

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.capacidades import Estado, PerfilHardware
from aura_skeleton.modules.memory import PersistentMemory


def _config(tmp_path, perfil=None):
    kw = {
        "datos": str(tmp_path),
        "raices_permitidas": (str(tmp_path),),
        "usar_stack_real": False,
    }
    if perfil is not None:
        kw["perfil"] = perfil
    return Configuracion(**kw)


def test_composicion_expone_el_plan_de_capacidades(tmp_path):
    sistema = componer(_config(tmp_path))
    assert sistema.plan is not None
    # Memoria clasificada por el plan y NUNCA latente (N1 siempre viable).
    assert sistema.plan.decision("memoria").estado is not Estado.LATENTE


def test_memoria_activa_con_perfil_alto(tmp_path):
    sistema = componer(_config(tmp_path, PerfilHardware(recursos={"ram_mb": 32000})))
    assert "memoria" in sistema.plan.activas


def test_memoria_degradada_con_perfil_por_defecto(tmp_path):
    # Sin deteccion real, el perfil por defecto es conservador -> memoria en N1 (degradada).
    sistema = componer(_config(tmp_path))
    assert "memoria" in sistema.plan.degradadas


@pytest.mark.asyncio
async def test_memoria_operativa_tras_la_composicion(tmp_path):
    # El flujo completo deja una memoria REAL y funcional (N1, PersistentMemory).
    sistema = componer(_config(tmp_path, PerfilHardware(recursos={"ram_mb": 32000})))
    assert isinstance(sistema.memoria, PersistentMemory)
    await sistema.memoria.write("u", "semantica", "prefiere luz tenue", {"trace_id": "t"})
    recuerdos = await sistema.memoria.recall("u", "luz")
    assert any("tenue" in r["content"] for r in recuerdos)
