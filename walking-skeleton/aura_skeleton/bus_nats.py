"""Event Bus sobre NATS real (ADR-0006). Implementa el MISMO contrato EventBus que el bus
in-process (contracts.EventBus). Cambiar de in-process a NATS = cambiar esta clase, no los consumidores."""
from __future__ import annotations
import json, asyncio
import nats
from .contracts import Event
from . import observability as obs

class NatsEventBus:
    def __init__(self, nc):
        self._nc = nc
        self._subs = []

    @classmethod
    async def connect(cls, url="nats://127.0.0.1:4222"):
        nc = await nats.connect(url)
        return cls(nc)

    def subscribe(self, type_prefix, handler):
        subject = type_prefix if "." in type_prefix else type_prefix
        async def _cb(msg):
            d = json.loads(msg.data.decode())
            ev = Event(type=d["type"], trace_id=d["trace_id"], user_id=d["user_id"],
                       payload=d.get("payload",{}), event_id=d["event_id"],
                       causation_id=d.get("causation_id"), schema_version=d.get("schema_version","1.0.0"),
                       ts=d.get("ts",0.0))
            await handler(ev)
        self._subs.append((subject,_cb))

    async def start(self):
        for subject, cb in self._subs:
            await self._nc.subscribe(subject, cb=cb)
        await self._nc.flush()

    async def publish(self, event: Event) -> None:
        obs.log("EVENT", "nats-bus", f"publish {event.type}", event.trace_id, event_id=event.event_id)
        data = json.dumps({"type":event.type,"trace_id":event.trace_id,"user_id":event.user_id,
                           "payload":event.payload,"event_id":event.event_id,"causation_id":event.causation_id,
                           "schema_version":event.schema_version,"ts":event.ts}).encode()
        await self._nc.publish(event.type, data)
        await self._nc.flush()

    async def close(self):
        await self._nc.drain()
