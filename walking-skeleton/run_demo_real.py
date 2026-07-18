#!/usr/bin/env python3
"""Walking Skeleton con STACK REAL (D24): NATS + Ollama + faster-whisper + Piper, TODO local.
Reutiliza EXACTAMENTE los contratos existentes (ModelProvider, EventBus, voz); no modifica la arquitectura
ni ningun ADR. Mide la latencia real por etapa y total contra HC-1 (R1 <=1200ms / R2 <=800ms).

NO ejecutable en entornos sin Ollama/GPU. Se corre en el hardware objetivo tras `verify-stack` (D24).

Uso:
  python3 run_demo_real.py --text "Enciende la luz de la sala" --iterations 30
  python3 run_demo_real.py --audio muestra.wav --iterations 30
Requiere: nats-server :4222 y ollama serve :11434 corriendo; modelo LLM y voz Piper instalados.
"""

import argparse
import asyncio
import os
import statistics
import sys
import uuid

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice_real import WhisperPiperVoice
from aura_skeleton.bus_nats import NatsEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.providers_real import OllamaProvider
from aura_skeleton.modules.router import ModelRouter

R1, R2 = 1200.0, 800.0


async def _auto_confirm(action, args, trace_id):
    # En validacion no interactiva, la lista roja se DENIEGA por seguridad (no ejecuta).
    return False


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="Enciende la luz de la sala")
    ap.add_argument("--audio", default="")
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--model", default=os.environ.get("AURA_LLM_MODEL", "qwen2.5:3b"))
    ap.add_argument("--voice", default=os.environ.get("AURA_PIPER_VOICE", ""))
    ap.add_argument("--nats", default="nats://127.0.0.1:4222")
    args = ap.parse_args()

    bus = await NatsEventBus.connect(args.nats)
    memory = SimpleMemory()
    router = ModelRouter([OllamaProvider("ollama", args.model)], latency_budget_ms=R1)
    voice = WhisperPiperVoice(piper_voice=args.voice)
    orch = Orchestrator(bus, memory, router, PermissionManager(_auto_confirm), voice, HomeAssistantMock())
    await bus.start()

    entrada = args.audio if args.audio else args.text
    print(f"==> Validacion HC-1 con stack REAL local | modelo={args.model} | N={args.iterations}")
    lat, stt_ms, llm_ms, tts_ms = [], [], [], []
    for _ in range(args.iterations):
        tid = uuid.uuid4().hex[:12]
        await orch.handle_utterance("mauricio", entrada, tid)
        res = await orch.wait(tid, timeout=200)
        m = res["marks"]
        lat.append(res["latency_ms"])
        stt_ms.append(m.get("stt", 0.0))
        llm_ms.append(m.get("llm", 0.0) - m.get("memory", 0.0))
        tts_ms.append(m.get("tts", 0.0) - m.get("llm", 0.0))

    def p(v, q):
        v = sorted(v)
        return v[min(len(v) - 1, int(q * len(v)))]

    print("\n" + "=" * 60)
    print("RESULTADO HC-1 (stack real, local)")
    print("=" * 60)
    print(f"  Etapa STT (whisper): P50={statistics.median(stt_ms):.0f} ms")
    print(f"  Etapa LLM (ollama):  P50={statistics.median(llm_ms):.0f} ms")
    print(f"  Etapa TTS (piper):   P50={statistics.median(tts_ms):.0f} ms")
    e2e_p50, e2e_p95 = statistics.median(lat), p(lat, 0.95)
    print(f"  Extremo a extremo:   P50={e2e_p50:.0f} ms · P95={e2e_p95:.0f} ms")
    ok_r1 = e2e_p50 <= R1
    print(f"  Objetivo R1 (nube-equivalente local) <= {R1:.0f} ms: {'CUMPLE' if ok_r1 else 'NO CUMPLE'}")
    print(
        f"  Objetivo R2 (optimizado/GPU) <= {R2:.0f} ms: {'CUMPLE' if e2e_p50 <= R2 else 'pendiente hardware/optimizacion'}"
    )
    print("=" * 60)
    print("Si un objetivo no se cumple, NO ajustes en silencio: levanta una Alerta de Arquitectura (D15).")
    await bus.close()
    return 0 if ok_r1 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
