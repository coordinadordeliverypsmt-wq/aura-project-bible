"""Event Bus in-process (contrato de 3.3). Implementa el mismo contrato que NATS (ADR-0006):
at-least-once conceptual, orden por trace_id, correlación. Swap a NATS = cambiar esta clase, no los consumidores."""

from __future__ import annotations

from collections import defaultdict

from . import observability as obs
from .contracts import Event


class InProcessEventBus:
    def __init__(self):
        self._subs = defaultdict(list)
        self._delivered: set[str] = set()  # deduplicación por event_id (idempotencia, 3.3 §3)

    def subscribe(self, type_prefix: str, handler):
        self._subs[type_prefix].append(handler)

    async def publish(self, event: Event) -> None:
        obs.log("EVENT", "event-bus", f"publish {event.type}", event.trace_id, event_id=event.event_id)
        obs.metric_inc("eventos.publicados")  # metrica basica P-ARQ-7 (Bible 7.4); local, en memoria
        handlers = [h for pref, hs in self._subs.items() if event.type.startswith(pref) for h in hs]
        for h in handlers:
            # idempotencia: cada (handler,event_id) se entrega una vez
            key = f"{id(h)}:{event.event_id}"
            if key in self._delivered:
                continue
            self._delivered.add(key)
            await h(event)
