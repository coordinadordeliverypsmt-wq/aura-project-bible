"""Escalabilidad de la memoria (MA.2a).

Deuda R-1/R-2 medida en la auditoria del 2026-07-21 y cuantificada antes de corregirla:

    100 entradas -> 0,81 ms por escritura
  5.000 entradas -> 15,24 ms por escritura (19x)   | escribirlas todas: 76 segundos

Causa: cada `write` reescribia el JSON COMPLETO, de modo que el coste agregado era cuadratico. Con
~50 turnos diarios, un ano de uso son ~18.000 entradas.

Estas pruebas verifican una PROPIEDAD, no un tiempo absoluto: que el coste por operacion **no crece
con el volumen**. Un umbral en milisegundos seria fragil —depende de la maquina— y ademas mentiria:
lo que importa no es que sea rapido hoy, sino que siga siendolo con anos de historial.

Nota sobre D34: generar datos sinteticos para medir ESCALABILIDAD es legitimo; el volumen es la
variable bajo prueba. Seria ilegitimo usarlos para inferir preferencias, donde lo que importa es el
contenido real.
"""

import time

import pytest

from aura_skeleton.modules.memory import PersistentMemory


async def _sembrar(mem, desde, hasta):
    for i in range(desde, hasta):
        await mem.write("u", "episodica", f"usuario dijo: entrada {i} sobre tema {i % 50}", {"trace_id": str(i)})


def _ms_por_escritura(mem, desde, hasta):
    import asyncio

    t0 = time.perf_counter()
    asyncio.get_event_loop().run_until_complete(_sembrar(mem, desde, hasta))
    return (time.perf_counter() - t0) * 1000 / (hasta - desde)


@pytest.mark.asyncio
async def test_el_coste_de_escritura_no_crece_con_el_volumen(tmp_path):
    """R-2: la escritura debe ser incremental, no reescribir el historial completo."""
    mem = PersistentMemory(str(tmp_path / "m.json"))

    t0 = time.perf_counter()
    await _sembrar(mem, 0, 400)
    primeras = (time.perf_counter() - t0) / 400

    await _sembrar(mem, 400, 2000)  # el historial crece 5x

    t0 = time.perf_counter()
    await _sembrar(mem, 2000, 2400)
    ultimas = (time.perf_counter() - t0) / 400

    assert ultimas < primeras * 3, (
        f"la escritura se degrada con el volumen: {primeras * 1000:.2f} ms -> {ultimas * 1000:.2f} ms. "
        "Sintoma de reescribir el historial completo en cada write (R-2)."
    )


@pytest.mark.asyncio
async def test_el_coste_de_recall_no_crece_linealmente(tmp_path):
    """R-1: el recall debe apoyarse en un indice, no recorrer todos los items."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await _sembrar(mem, 0, 300)

    t0 = time.perf_counter()
    for _ in range(30):
        await mem.recall("u", "tema 25")
    pequeno = (time.perf_counter() - t0) / 30

    await _sembrar(mem, 300, 3000)  # 10x mas historial

    t0 = time.perf_counter()
    for _ in range(30):
        await mem.recall("u", "tema 25")
    grande = (time.perf_counter() - t0) / 30

    assert grande < pequeno * 4, (
        f"el recall se degrada casi linealmente: {pequeno * 1000:.2f} ms -> {grande * 1000:.2f} ms "
        f"con 10x de historial (R-1)."
    )


@pytest.mark.asyncio
async def test_el_historial_sobrevive_al_reinicio_con_volumen(tmp_path):
    """La optimizacion no puede costar la persistencia: es la garantia de M1."""
    ruta = str(tmp_path / "m.json")
    mem = PersistentMemory(ruta)
    await _sembrar(mem, 0, 500)

    otra = PersistentMemory(ruta)  # simula reinicio
    hits = await otra.recall("u", "tema 25")

    assert hits, "el historial no sobrevivio al reinicio"
    assert any("tema 25" in h["content"] for h in hits)


@pytest.mark.asyncio
async def test_el_recall_sigue_siendo_correcto_con_volumen(tmp_path):
    """CONTROL: una optimizacion que devolviera resultados peores no seria una mejora."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await _sembrar(mem, 0, 1000)
    await mem.write("u", "semantica", "prefiere la luz tenue por la noche", {"trace_id": "x"})

    hits = await mem.recall("u", "luz tenue")

    assert hits, "no encontro un recuerdo que existe"
    assert "tenue" in hits[0]["content"], f"el mejor resultado no es el relevante: {hits[0]['content']!r}"
