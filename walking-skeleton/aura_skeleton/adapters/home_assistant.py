"""Adaptador de dominio Home Assistant (Bible 6.1/6.3) — mock. En produccion: HA + MQTT.
Valida la capa de accion por contrato y la idempotencia por event_id."""
from __future__ import annotations
from .. import observability as obs

class HomeAssistantMock:
    name = "home_assistant"
    capabilities = ["encender_dispositivo","apagar_dispositivo"]
    def __init__(self): self._done: set[str] = set()
    async def execute(self, command, args, trace_id, event_id):
        if event_id in self._done:               # idempotencia (3.3 3): mismo evento -> un solo efecto
            obs.log("ACT", "ha-adapter", f"idempotente: {command} ya ejecutado", trace_id)
            return {"status":"duplicate"}
        self._done.add(event_id)
        dev = args.get("device","?")
        obs.log("ACT", "ha-adapter", f"EJECUTA {command} sobre '{dev}'", trace_id, audit=True)
        return {"status":"ok","device":dev}
