"""Unit M1.1: Memoria persistente con backups y recuperacion (Bible 4.1/3.5, prioridad M1)."""

import pytest

from aura_skeleton.modules.memory import PersistentMemory


@pytest.mark.asyncio
async def test_persistencia_sobrevive_reinicio(tmp_path):
    p = str(tmp_path / "mem.json")
    m1 = PersistentMemory(p)
    await m1.write("u", "semantica", "prefiere la luz tenue", {"trace_id": "t"})
    m2 = PersistentMemory(p)  # simula reinicio: nueva instancia carga del disco
    hits = await m2.recall("u", "luz")
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_backup_y_verificacion_integridad(tmp_path):
    m = PersistentMemory(str(tmp_path / "mem.json"))
    await m.write("u", "s", "dato importante", {})
    name = m.backup()
    assert m.verify(name) is True


@pytest.mark.asyncio
async def test_restore_rechaza_backup_corrupto(tmp_path):
    m = PersistentMemory(str(tmp_path / "mem.json"))
    await m.write("u", "s", "dato", {})
    name = m.backup()
    # corromper el archivo de backup
    bpath = tmp_path / "mem.json.backups" / name
    bpath.write_text(bpath.read_text() + "corrupcion")
    assert m.verify(name) is False
    assert await _restore(m, name) is False  # recuperacion segura: no restaura datos corruptos


@pytest.mark.asyncio
async def test_recuperacion_ante_perdida(tmp_path):
    p = str(tmp_path / "mem.json")
    m = PersistentMemory(p)
    await m.write("u", "s", "recuerdo valioso de anos", {})
    name = m.backup()
    # simular perdida: vaciar la memoria en caliente
    m._items = []
    m._persist()
    assert m.restore(name) is True
    hits = await m.recall("u", "recuerdo")
    assert len(hits) == 1  # activo irremplazable recuperado


async def _restore(m, name):
    return m.restore(name)
