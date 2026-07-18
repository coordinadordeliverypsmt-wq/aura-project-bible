"""Unit: Memoria — recall y no-fabricacion (Bible 4.1 / 2.4)."""

import pytest

from aura_skeleton.modules.memory import SimpleMemory


@pytest.mark.asyncio
async def test_write_y_recall():
    m = SimpleMemory()
    await m.write("u", "semantica", "prefiere la luz tenue", {"trace_id": "t"})
    hits = await m.recall("u", "luz")
    assert len(hits) == 1 and hits[0]["provenance"]["trace_id"] == "t"


@pytest.mark.asyncio
async def test_sin_coincidencia_no_fabrica():
    m = SimpleMemory()
    await m.write("u", "semantica", "prefiere la luz tenue", {"trace_id": "t"})
    hits = await m.recall("u", "presupuesto trimestral")
    assert hits == []  # no inventa recuerdos


@pytest.mark.asyncio
async def test_aislamiento_por_usuario():
    m = SimpleMemory()
    await m.write("u1", "s", "dato de u1", {})
    hits = await m.recall("u2", "dato")
    assert hits == []  # multi-usuario (P-ARQ-5)
