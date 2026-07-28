"""Unit: SemanticMemory (N2, ADR-0020) — memoria de indice semantico tras el contrato MemoryStore.

N2 es el segundo nivel de la capacidad Memoria ya declarada (ADR-0020: N1 almacen minimo / N2 indice
embebido / N3 motor especializado). Este modulo prueba que N2:
  - cumple EXACTAMENTE el mismo contrato que N1 (write/recall async), sin romperlo;
  - es CONDUCTUALMENTE DISTINTA de N1: recall semantico (coseno de embeddings) frente al recall lexico
    (solapamiento de terminos) de N1. Esa diferencia es el "delta observable" que hace que el plan, al
    elegir entre N1 y N2, gobierne una materializacion real (cierre de E1);
  - reutiliza el almacenamiento persistente de N1 (no reimplementa persistencia): menor riesgo.

Alcance (Decision Package aprobado): NO se mide ni se exige calidad del recall en espanol (el embedder
disponible es de calidad limitada en espanol; mejorarlo es seguimiento de PRODUCTO, fuera de este trabajo).
Aqui solo se verifica el CONTRATO y el DELTA conductual frente a N1.

Requiere el modelo de embeddings presente; si no esta, las pruebas hacen skip (patron del stack real).
"""

import os

import pytest

MODELO = None
for _cand in (
    os.environ.get("AURA_EMBED_MODEL_DIR", ""),
    os.path.expanduser("~/.aura/models/all-MiniLM-L6-v2"),
    os.path.expanduser("~/.ruvector/models/all-MiniLM-L6-v2"),
):
    if (
        _cand
        and os.path.exists(os.path.join(_cand, "model.onnx"))
        and os.path.exists(os.path.join(_cand, "tokenizer.json"))
    ):
        MODELO = _cand
        break

pytestmark = pytest.mark.skipif(MODELO is None, reason="modelo de embeddings no presente (N2 latente)")


def _semantica(tmp_path):
    from aura_skeleton.modules.memory_semantic import SemanticMemory

    return SemanticMemory(str(tmp_path / "mem.jsonl"), MODELO)


def _lexica(tmp_path):
    from aura_skeleton.modules.memory import PersistentMemory

    return PersistentMemory(str(tmp_path / "mem_n1.jsonl"))


# Corpus con parafrasis: las consultas NO comparten terminos exactos con su recuerdo afin, de modo que el
# recall LEXICO (N1) y el SEMANTICO (N2) no pueden coincidir por construccion en al menos un caso.
_CORPUS = [
    "trabaja durante la madrugada y descansa por el dia",
    "tiene un felino domestico que se llama Mateo",
    "abona los servicios del hogar mediante transferencia bancaria",
    "prefiere la iluminacion tenue en el salon por la noche",
]


async def _sembrar(mem):
    for i, texto in enumerate(_CORPUS):
        await mem.write("u1", "semantica", texto, {"trace_id": f"t{i}"})


@pytest.mark.asyncio
async def test_cumple_el_contrato_memorystore(tmp_path):
    """N2 expone write/recall async y recall devuelve dicts con la misma forma que N1."""
    mem = _semantica(tmp_path)
    await mem.write("u1", "semantica", "prefiere luz tenue", {"trace_id": "t"})
    hits = await mem.recall("u1", "iluminacion suave", k=3)
    assert isinstance(hits, list)
    assert all(isinstance(h, dict) and "content" in h and "user_id" in h for h in hits)


@pytest.mark.asyncio
async def test_recall_semantico_difiere_del_lexico(tmp_path):
    """DELTA OBSERVABLE: sobre el MISMO corpus, N2 (semantico) y N1 (lexico) NO devuelven lo mismo.

    Es la propiedad que hace util al plan: elegir N1 o N2 materializa comportamientos distintos. No se
    exige que N2 acierte (calidad = seguimiento de producto), solo que DIFIERA de N1.
    """
    n1, n2 = _lexica(tmp_path), _semantica(tmp_path)
    await _sembrar(n1)
    await _sembrar(n2)
    consultas = [
        "pagar la factura de la luz por internet",  # afin a "abona los servicios..."; sin tokens comunes
        "esta despierto de noche",  # afin a "trabaja durante la madrugada..."
        "el gato de la casa",  # afin a "tiene un felino domestico..."
    ]
    difieren = 0
    for q in consultas:
        top1_n1 = (await n1.recall("u1", q, k=1)) or [{}]
        top1_n2 = (await n2.recall("u1", q, k=1)) or [{}]
        if top1_n1[0].get("content") != top1_n2[0].get("content"):
            difieren += 1
    assert difieren >= 1, "N2 debe ser conductualmente distinta de N1 en al menos una consulta parafraseada"


@pytest.mark.asyncio
async def test_aislamiento_por_usuario(tmp_path):
    """P-ARQ-5: recall solo devuelve recuerdos del usuario consultado (se preserva la garantia de N1)."""
    mem = _semantica(tmp_path)
    await mem.write("u1", "semantica", "dato del usuario uno", {"trace_id": "t"})
    await mem.write("u2", "semantica", "dato del usuario dos", {"trace_id": "t"})
    hits = await mem.recall("u1", "dato", k=5)
    assert hits and all(h["user_id"] == "u1" for h in hits)


@pytest.mark.asyncio
async def test_reutiliza_la_persistencia_de_n1(tmp_path):
    """N2 no reimplementa persistencia: lo escrito sobrevive al reconstruir la memoria desde disco."""
    ruta = str(tmp_path / "persist.jsonl")
    from aura_skeleton.modules.memory_semantic import SemanticMemory

    mem = SemanticMemory(ruta, MODELO)
    await mem.write("u1", "semantica", "recuerdo que debe persistir", {"trace_id": "t"})
    mem2 = SemanticMemory(ruta, MODELO)  # nueva instancia sobre la misma ruta
    hits = await mem2.recall("u1", "recuerdo persistente", k=3)
    assert any("persistir" in h["content"] for h in hits)
