"""Integracion: Event Bus in-process — entrega y idempotencia (Bible 3.3)."""

import pytest

from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.contracts import Event


@pytest.mark.asyncio
async def test_publish_entrega_con_trace_id():
    bus = InProcessEventBus()
    recibidos = []

    async def h(ev):
        recibidos.append(ev)

    bus.subscribe("perception.turn_end", h)
    await bus.publish(Event("perception.turn_end", "T1", "u", {"text": "hola"}))
    assert len(recibidos) == 1 and recibidos[0].trace_id == "T1"


@pytest.mark.asyncio
async def test_idempotencia_mismo_evento_una_entrega():
    bus = InProcessEventBus()
    n = []

    async def h(ev):
        n.append(1)

    bus.subscribe("perception.turn_end", h)
    ev = Event("perception.turn_end", "T2", "u", {})
    await bus.publish(ev)
    await bus.publish(ev)  # mismo event_id
    assert len(n) == 1
