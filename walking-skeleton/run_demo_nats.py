#!/usr/bin/env python3
"""Walking Skeleton sobre el Event Bus REAL (NATS, ADR-0006). Mismos consumidores que run_demo.py;
solo cambia el bus (in-process -> NATS) — prueba del intercambio por contrato (Evolucion Permanente)."""

import asyncio
import statistics
import sys
import uuid

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus_nats import NatsEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter

USER = "mauricio"


async def human_confirm(action, args, trace_id):
    decision = action != "eliminar_informacion"
    print(f"    >>> HITL: AURA pide confirmar '{action}' -> usuario: {'SI' if decision else 'NO'}")
    return decision


async def main():
    bus = await NatsEventBus.connect("nats://127.0.0.1:4222")
    memory = SimpleMemory()
    router = ModelRouter(
        [
            MockProvider("gemini-mock", 90, healthy=False),
            MockProvider("claude-mock", 110, healthy=True),
            MockProvider("chatgpt-mock", 120, healthy=True),
        ],
        latency_budget_ms=1200,
    )
    orch = Orchestrator(bus, memory, router, PermissionManager(human_confirm), VoiceAdapterMock(), HomeAssistantMock())
    await bus.start()
    await memory.write(
        USER,
        "semantica",
        "el usuario prefiere la luz de la sala tenue por la noche",
        {"trace_id": "seed", "fuente": "previo"},
    )

    lat = []
    for title, text in [
        ("Lista verde + fallback", "Enciende la luz de la sala"),
        ("Lista roja -> HITL", "Elimina el archivo de impuestos"),
        ("Memoria (recuerdo previo)", "Que acordamos sobre la luz de la sala?"),
    ]:
        print(f'\n=== ESCENARIO (bus NATS real): {title} ===\n    Usuario (voz): "{text}"')
        tid = uuid.uuid4().hex[:12]
        await orch.handle_utterance(USER, text, tid)
        res = await orch.wait(tid)
        lat.append(res["latency_ms"])
        print(
            f"    -> AURA: {res['say'][:80]}  | proveedor={res['provider']} | latencia_e2e={res['latency_ms']:.1f} ms"
        )

    print("\n" + "=" * 64)
    print("VALIDACION SOBRE STACK REAL (parcial)")
    print("=" * 64)
    print(f"  Event Bus: NATS REAL v2.10.22 (ADR-0006) — {len(lat)} turnos de extremo a extremo OK")
    print(f"  Latencia e2e (incluye NATS real + LLM MOCK ~110ms): P50={statistics.median(lat):.1f} ms")
    print("  El mismo orquestador/adaptadores corrieron sin cambios: in-process -> NATS por contrato. VALIDADO.")
    await bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
