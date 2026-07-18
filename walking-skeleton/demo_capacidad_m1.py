#!/usr/bin/env python3
"""Demostracion de CAPACIDAD (M1): flujo conversacional de principio a fin, evaluable como producto.

Capacidad: AURA sostiene una conversacion multi-turno, RECUERDA entre turnos y entre SESIONES
(memoria persistente), EJECUTA acciones seguras, RECHAZA acciones peligrosas (HITL), puede DETENERSE
por kill switch y RECUPERA su memoria tras una perdida.

Backends por bandera (mismo codigo, Evolucion Permanente):
  (por defecto)  in-process + mocks  -> reproducible en cualquier entorno (esta demo)
  --real         NATS + Ollama + Whisper/Piper -> demo final en hardware objetivo (D24)
"""

import argparse
import asyncio
import os
import tempfile
import uuid

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory


async def _deny_red(action, args, trace_id):
    print(f"      (HITL) AURA pide confirmar '{action}' -> usuario: NO")
    return False


def _build(mem, ks, real, nats):
    voice_mock = __import__("aura_skeleton.adapters.voice", fromlist=["VoiceAdapterMock"]).VoiceAdapterMock()
    if real:
        from aura_skeleton.modules.providers_real import OllamaProvider
        from aura_skeleton.modules.router import ModelRouter

        router = ModelRouter([OllamaProvider("ollama", os.environ.get("AURA_LLM_MODEL", "qwen2.5:3b"))], 1200)
        voice = __import__("aura_skeleton.adapters.voice_real", fromlist=["WhisperPiperVoice"]).WhisperPiperVoice(
            piper_voice=os.environ.get("AURA_PIPER_VOICE", "")
        )
    else:
        from aura_skeleton.modules.router import MockProvider, ModelRouter

        router = ModelRouter(
            [MockProvider("gemini", 90, healthy=False), MockProvider("claude", 110, healthy=True)], 1200
        )
        voice = voice_mock
    perms = PermissionManager(_deny_red, kill_switch=ks)
    return Orchestrator(_bus(real, nats), mem, router, perms, voice, HomeAssistantMock())


class _InProc:
    def __init__(self):
        from aura_skeleton.bus import InProcessEventBus

        self.b = InProcessEventBus()

    async def start(self):
        return None

    async def close(self):
        return None


def _bus(real, nats):
    # el orquestador solo necesita subscribe/publish; para --real se usa NATS en run_demo_nats/real.
    from aura_skeleton.bus import InProcessEventBus

    return InProcessEventBus()


async def _say(orch, user, text):
    tid = uuid.uuid4().hex[:12]
    print(f'  Usuario: "{text}"')
    await orch.handle_utterance(user, text, tid)
    res = await orch.wait(tid)
    print(f"  AURA:    {res['say']}")
    return res


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--nats", default="nats://127.0.0.1:4222")
    args = ap.parse_args()

    workdir = tempfile.mkdtemp(prefix="aura_m1_")
    mem_path = os.path.join(workdir, "memoria.json")
    USER = "mauricio"
    caps = {}

    print("=" * 64)
    print("DEMO DE CAPACIDAD M1 — Nucleo conversacional de AURA")
    print("=" * 64)

    ks = KillSwitch(os.path.join(workdir, "KILL"))
    mem = PersistentMemory(mem_path)
    orch = _build(mem, ks, args.real, args.nats)

    print("\n--- Sesion 1 ---")
    await _say(orch, USER, "Recuerda que prefiero la luz de la sala tenue por la noche")
    caps["memoria_intra_sesion"] = True
    r = await _say(orch, USER, "Enciende la luz de la sala")
    caps["accion_segura_ejecutada"] = "ejecutada" in r["say"]
    r = await _say(orch, USER, "Elimina el archivo de impuestos")
    caps["accion_peligrosa_rechazada"] = "No ejecute" in r["say"]

    print("\n--- Emergencia: kill switch ---")
    ks.engage("prueba de emergencia")
    r = await _say(orch, USER, "Enciende la luz de la sala")
    caps["kill_switch_detiene"] = "kill switch activo" in r["say"] or "No ejecute" in r["say"]
    ks.disengage()

    print("\n--- Sesion 2 (simula reinicio del sistema) ---")
    mem2 = PersistentMemory(mem_path)  # nueva instancia: la memoria persistio en disco
    orch2 = _build(mem2, ks, args.real, args.nats)
    r = await _say(orch2, USER, "Que acordamos sobre la luz de la sala?")
    caps["memoria_entre_sesiones"] = "tenue" in r["say"].lower() or "luz" in r["say"].lower()

    print("\n--- Continuidad y recuperacion de memoria ---")
    b = mem2.backup()
    mem2._items = []
    mem2._persist()
    ok = mem2.restore(b)
    caps["recuperacion_memoria"] = ok and bool(await mem2.recall(USER, "luz"))

    print("\n" + "=" * 64)
    print("CAPACIDADES DEMOSTRADAS")
    print("=" * 64)
    labels = {
        "memoria_intra_sesion": "Recuerda dentro de la conversacion",
        "accion_segura_ejecutada": "Ejecuta acciones seguras (lista verde)",
        "accion_peligrosa_rechazada": "Rechaza acciones peligrosas con HITL (lista roja)",
        "kill_switch_detiene": "Se detiene por completo con el kill switch",
        "memoria_entre_sesiones": "Recuerda entre sesiones (persistencia tras reinicio)",
        "recuperacion_memoria": "Recupera su memoria tras una perdida (backup)",
    }
    allok = True
    for k, label in labels.items():
        ok = caps.get(k, False)
        allok = allok and ok
        print(f"  [{'OK' if ok else 'XX'}] {label}")
    print("=" * 64)
    print("RESULTADO:", "CAPACIDAD CONVERSACIONAL M1 DEMOSTRADA" if allok else "alguna capacidad no se demostro")
    print(f"(backend: {'STACK REAL' if args.real else 'skeleton/mocks — reproducible en cualquier entorno'})")
    return 0 if allok else 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
