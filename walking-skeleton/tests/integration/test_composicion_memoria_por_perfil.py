"""Integracion e2e (C2.2/C2.3): flujo Registry -> Manager -> Plan -> Composicion -> Memoria.

Valida que el arranque oficial (composicion) consulta el Capability Registry/Manager, obtiene un
PlanActivacion determinista a partir del PerfilHardware, y SELECCIONA la implementacion de memoria segun
ese plan. Con N2 implementado (ADR-0020), el plan pasa a gobernar una MATERIALIZACION real: perfil alto y
modelo presente -> N2 (SemanticMemory); en otro caso -> N1 (PersistentMemory).
"""

import os

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.capacidades import Estado, PerfilHardware
from aura_skeleton.modules.memory import PersistentMemory

# Artefacto de embeddings gestionado por manifiesto (ADR-0022): model.onnx + tokenizer.json + manifiesto.json.
_MODELO = None
for _cand in (
    os.environ.get("AURA_EMBED_MODEL_DIR", ""),
    os.path.expanduser("~/.aura/models/paraphrase-multilingual-MiniLM-L12-v2"),
):
    if _cand and all(
        os.path.exists(os.path.join(_cand, f)) for f in ("model.onnx", "tokenizer.json", "manifiesto.json")
    ):
        _MODELO = _cand
        break


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
    # El flujo completo deja una memoria REAL y funcional que cumple el contrato MemoryStore,
    # sea N1 o N2 (el tipo lo decide el plan + la disponibilidad del modelo). Se verifica el CONTRATO,
    # no la clase concreta, para que la prueba valga con cualquier nivel materializado.
    sistema = componer(_config(tmp_path, PerfilHardware(recursos={"ram_mb": 32000})))
    await sistema.memoria.write("u", "semantica", "prefiere luz tenue", {"trace_id": "t"})
    recuerdos = await sistema.memoria.recall("u", "luz")
    assert isinstance(recuerdos, list)


def test_el_plan_gobierna_la_materializacion_de_memoria(tmp_path, monkeypatch):
    """CRITERIO DE EXITO: el MISMO escenario produce una materializacion DISTINTA segun el estado del plan.
    Con el artefacto resuelto por manifiesto, perfil alto -> N2, perfil bajo -> N1 (delta observable != 0).
    """
    if _MODELO is None:
        pytest.skip("artefacto de embeddings (con manifiesto) no desplegado")
    from aura_skeleton.modules.memory_semantic import SemanticMemory

    monkeypatch.setenv("AURA_EMBED_MODEL_DIR", _MODELO)

    alto = componer(_config(tmp_path / "alto", PerfilHardware(recursos={"ram_mb": 32000})))
    bajo = componer(_config(tmp_path / "bajo", PerfilHardware(recursos={"ram_mb": 100})))

    assert "memoria" in alto.plan.activas
    assert "memoria" in bajo.plan.degradadas
    assert isinstance(alto.memoria, SemanticMemory)
    assert isinstance(bajo.memoria, PersistentMemory)
    assert type(alto.memoria) is not type(bajo.memoria)


@pytest.mark.asyncio
async def test_n2_multilingue_mejora_recall_espanol(tmp_path, monkeypatch):
    """CRITERIO DE EXITO (Product First): N2 usa el modelo multilingue POR MANIFIESTO y recupera una
    parafrasis en espanol SIN terminos comunes con el recuerdo afin — el caso que all-MiniLM fallaba
    (recall 0/8 en Fase 0). Demostracion funcional por ejecucion de la mejora del recall en espanol.
    """
    if _MODELO is None:
        pytest.skip("artefacto de embeddings (con manifiesto) no desplegado")
    monkeypatch.setenv("AURA_EMBED_MODEL_DIR", _MODELO)  # cambio de modelo por config, sin tocar codigo

    s = componer(_config(tmp_path, PerfilHardware(recursos={"ram_mb": 32000})))
    for texto in (
        "abona los servicios del hogar mediante transferencia bancaria",
        "tiene un felino domestico que se llama Mateo",
        "prefiere la iluminacion tenue en el salon por la noche",
    ):
        await s.memoria.write("u", "semantica", texto, {"trace_id": "t"})

    hits = await s.memoria.recall("u", "pagar las facturas por internet", k=1)  # parafrasis, sin tokens comunes
    assert hits and "servicios del hogar" in hits[0]["content"]


def test_sin_manifiesto_el_arranque_no_se_rompe_y_cae_a_n1(tmp_path, monkeypatch):
    """Robustez: si el ModelResolver no puede resolver el artefacto (ausente o sin manifiesto), perfil alto
    NO rompe el arranque; materializa N1 (degradacion transparente)."""
    monkeypatch.setenv("AURA_EMBED_MODEL_DIR", str(tmp_path / "no_existe"))
    sistema = componer(_config(tmp_path, PerfilHardware(recursos={"ram_mb": 32000})))
    assert isinstance(sistema.memoria, PersistentMemory)
    assert "memoria" in sistema.plan.activas  # el plan decide ACTIVA; solo cambia la materializacion
