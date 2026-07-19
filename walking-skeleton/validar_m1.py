#!/usr/bin/env python3
"""Arnes de VALIDACION del Milestone M1 (fase de validacion funcional).

Registra AUTOMATICAMENTE: latencia por etapa y total, consumo de CPU/RAM/almacenamiento,
uso de SWAP, y errores/excepciones/recuperaciones. Compara contra los objetivos de la Bible
(HC-1: R1<=1200ms / R2<=800ms) y, si algo no se cumple, avisa de ALERTA DE ARQUITECTURA (D15).

VALIDEZ: si hubo swapping durante la medicion, los numeros NO son representativos (el swap
—archivo, mmc o USB— es ordenes de magnitud mas lento que la RAM) y la medicion se marca invalida.

Backends:  --real  = NATS + Ollama + Whisper/Piper (hardware objetivo, D24)
           (defecto) = skeleton/mocks (autoprueba del arnes; NO valida rendimiento real)
"""

import argparse
import asyncio
import json
import os
import statistics
import uuid
from typing import Any

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter

R1_MS, R2_MS = 1200.0, 800.0


def _resources() -> dict:
    """CPU/RAM. psutil si existe (D26: opcional justificada); si no, stdlib."""
    try:
        import psutil

        p = psutil.Process()
        return {
            "fuente": "psutil",
            "rss_mb": round(p.memory_info().rss / 1e6, 1),
            "cpu_percent": p.cpu_percent(interval=0.2),
            "ram_sistema_pct": psutil.virtual_memory().percent,
        }
    except Exception:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "fuente": "stdlib(resource)",
            "rss_mb": round(ru.ru_maxrss / 1024, 1),
            "cpu_seg": round(ru.ru_utime + ru.ru_stime, 2),
        }


def _swap() -> dict:
    """Estado de swap. Clave para la VALIDEZ de HC-1: swapping durante la medicion la invalida."""
    try:
        import psutil

        sw = psutil.swap_memory()
        return {
            "total_mb": round(sw.total / 1e6, 1),
            "used_mb": round(sw.used / 1e6, 1),
            "sin": sw.sin,
            "sout": sw.sout,
        }
    except Exception:
        d = {"total_mb": 0.0, "used_mb": 0.0, "sin": 0, "sout": 0}
        try:
            mi = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, _, v = line.partition(":")
                    mi[k] = v.strip()
            tot = float(mi.get("SwapTotal", "0 kB").split()[0]) / 1000
            free = float(mi.get("SwapFree", "0 kB").split()[0]) / 1000
            d["total_mb"], d["used_mb"] = round(tot, 1), round(tot - free, 1)
            with open("/proc/vmstat") as f:
                for line in f:
                    if line.startswith("pswpin"):
                        d["sin"] = int(line.split()[1])
                    elif line.startswith("pswpout"):
                        d["sout"] = int(line.split()[1])
        except OSError:
            pass
        return d


def _dir_size_mb(path: str) -> float:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1e6, 3)


async def _build(mem, real, nats) -> tuple[Any, Any]:
    voice: Any
    if real:
        from aura_skeleton.adapters.voice_real import WhisperPiperVoice
        from aura_skeleton.modules.providers_real import OllamaProvider

        router = ModelRouter([OllamaProvider("ollama", os.environ.get("AURA_LLM_MODEL", "qwen2.5:3b"))], R1_MS)
        voice = WhisperPiperVoice(piper_voice=os.environ.get("AURA_PIPER_VOICE", ""))
        from aura_skeleton.bus_nats import NatsEventBus

        bus_obj = await NatsEventBus.connect(nats)
    else:
        router = ModelRouter([MockProvider("m", 110, healthy=True)], R1_MS)
        voice = VoiceAdapterMock()
        bus_obj = InProcessEventBus()

    async def allow(a, args, t):
        return True

    orch = Orchestrator(bus_obj, mem, router, PermissionManager(allow), voice, HomeAssistantMock())
    if real:
        await bus_obj.start()
    return orch, bus_obj


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--iterations", type=int, default=30)
    ap.add_argument("--text", default="Enciende la luz de la sala")
    ap.add_argument("--audio", default="")
    ap.add_argument("--nats", default="nats://127.0.0.1:4222")
    ap.add_argument("--out", default="resultados-m1.json")
    args = ap.parse_args()

    workdir = os.path.abspath("./m1-validacion-datos")
    os.makedirs(workdir, exist_ok=True)
    mem = PersistentMemory(os.path.join(workdir, "memoria.json"))
    orch, _bus = await _build(mem, args.real, args.nats)
    entrada = args.audio or args.text

    res_pre, swap_pre = _resources(), _swap()
    lat, stt, llm, tts = [], [], [], []
    errores, recuperaciones = 0, 0
    for _ in range(args.iterations):
        tid = uuid.uuid4().hex[:12]
        for intento in (1, 2):
            try:
                await orch.handle_utterance("mauricio", entrada, tid)
                r = await orch.wait(tid, timeout=200)
                m = r["marks"]
                lat.append(r["latency_ms"])
                stt.append(m.get("stt", 0.0))
                llm.append(m.get("llm", 0.0) - m.get("memory", 0.0))
                tts.append(m.get("tts", 0.0) - m.get("llm", 0.0))
                if intento == 2:
                    recuperaciones += 1
                break
            except Exception as e:  # noqa: BLE001
                errores += 1
                if intento == 2:
                    print(f"  [ERROR] turno fallido tras reintento: {e}")
    res_post, swap_post = _resources(), _swap()

    def pct(v, q):
        v = sorted(v)
        return round(v[min(len(v) - 1, int(q * len(v)))], 1) if v else 0.0

    e2e_p50 = round(statistics.median(lat), 1) if lat else 0.0
    paginas_in = swap_post.get("sin", 0) - swap_pre.get("sin", 0)
    paginas_out = swap_post.get("sout", 0) - swap_pre.get("sout", 0)
    hubo_swapping = (paginas_in > 0) or (paginas_out > 0)

    reporte = {
        "backend": "stack_real" if args.real else "skeleton_mocks",
        "iteraciones": args.iterations,
        "latencia_ms": {
            "stt_p50": round(statistics.median(stt), 1) if stt else 0.0,
            "llm_p50": round(statistics.median(llm), 1) if llm else 0.0,
            "tts_p50": round(statistics.median(tts), 1) if tts else 0.0,
            "e2e_p50": e2e_p50,
            "e2e_p95": pct(lat, 0.95),
        },
        "recursos": {"antes": res_pre, "despues": res_post, "almacenamiento_memoria_mb": _dir_size_mb(workdir)},
        "swap": {"antes": swap_pre, "despues": swap_post, "paginas_entrada": paginas_in, "paginas_salida": paginas_out},
        "estabilidad": {"errores": errores, "recuperaciones": recuperaciones, "turnos": args.iterations},
        "objetivos_bible": {"R1_ms": R1_MS, "R2_ms": R2_MS},
        "hubo_swapping": hubo_swapping,
        "medicion_valida": bool(lat) and not hubo_swapping,
        "cumple_R1": bool(lat) and e2e_p50 <= R1_MS,
        "cumple_R2": bool(lat) and e2e_p50 <= R2_MS,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("VALIDACION M1 — RESULTADOS")
    print("=" * 60)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    print("=" * 60)

    if hubo_swapping:
        print("\n*** ATENCION: hubo SWAPPING durante la medicion ***")
        print("    El swap (archivo/mmc/USB) es ordenes de magnitud mas lento que la RAM.")
        print("    Estos numeros NO son representativos: la medicion de HC-1 NO es valida.")
        print("    Libera RAM (cierra apps), usa un modelo mas pequeno o mas RAM fisica, y repite.")
    if args.real and not reporte["cumple_R1"]:
        print("\n*** OBJETIVO R1 NO CUMPLIDO -> se requiere ALERTA DE ARQUITECTURA (D15) ***")
        print(f"    e2e P50={e2e_p50} ms > R1={R1_MS} ms. No ajustes objetivos ni implementacion en silencio.")
        print("    Usa decisiones/alertas/plantilla-alerta.md (10 secciones, D16).")
        return 1
    if not args.real:
        print("\nNOTA: backend mocks (autoprueba). La validacion REAL se corre con --real en hardware objetivo.")
    print(f"Reporte guardado en {args.out}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
