#!/usr/bin/env python3
"""Demuestra, EJECUTANDO el producto, que un hecho redeclarado produce historial y vigencia.

    cd walking-skeleton && PYTHONPATH=. python3 ../milestones/m3-entry/evidencia-amp/verificar_historial_vigencia.py

No hay mocks del Core: se usan el orquestador, el motor unico, el ejecutor del modelo de usuario y el
almacen reales. El unico doble es el PROVEEDOR de modelo, y esta ahi para CONTAR: si responde una sola
vez, la autoridad se le ha delegado y la demostracion falla (ADR-0014).
"""

import asyncio
import json
import uuid

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import _clasificar, _normalizar
from aura_skeleton.core.almacen_senales import AlmacenSenales
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import Senal
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter

UID = "mauricio"
V1, V2 = "Mi cumpleaños es el 10 de mayo", "Mi cumpleaños es el 3 de junio"


class Contador:
    name = "contador"

    def __init__(self):
        self.llamadas = 0

    async def infer(self, prompt, modo="accion"):
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"(el modelo redactando)"}'


async def _si(accion, args, trace_id):
    return True


async def main():
    mem = SimpleMemory()
    espia = Contador()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    modelo = ModeloUsuario(mem, motor=motor)
    orq = Orchestrator(
        InProcessEventBus(), mem, ModelRouter([espia], 1200), PermissionManager(_si),
        VoiceAdapterMock(), HomeAssistantMock(), modelo_usuario=modelo,
    )
    almacen = AlmacenSenales(mem, motor=motor)

    for frase, ts in ((V1, 1000.0), (V2, 2000.0)):
        clase = _clasificar(_normalizar(frase))
        print(f"\n>>> El usuario declara: {frase!r}   (clase={clase.value}, ts={ts})")
        await almacen.guardar(UID, [Senal(clase, frase, "conversacion", "ev-amp", ts=ts)])

    print("\n--- LO QUE QUEDA EN EL ALMACEN (crudo, como lo leeria un inspector):")
    for i in mem._items:
        print("   ", json.dumps(i, ensure_ascii=False))

    print("\n--- LO QUE EL USUARIO PUEDE VER DE SU PROPIO HISTORIAL (`ver`):")
    for e in await modelo.ver(UID):
        estado = "VIGENTE" if e["valid_until"] is None else f"superseded en {e['valid_until']}"
        print(f"    v{e['version']}  supersedes={e['supersedes']}  [{e['valid_from']} → "
              f"{e['valid_until']}]  {estado}\n        {e['contenido']!r}")

    antes = espia.llamadas
    tid = uuid.uuid4().hex[:12]
    print("\n>>> El usuario pregunta: '¿Cuál es mi cumpleaños?'")
    await orq.handle_utterance(UID, "¿Cuál es mi cumpleaños?", tid)
    r = await orq.wait(tid)
    print(f"    AURA responde: {r['say']!r}")
    print(f"    proveedor={r['provider']}  dominio={r['dominio']}  latencia={r['latency_ms']:.2f} ms")
    print(f"    LLAMADAS AL MODELO durante la consulta: {espia.llamadas - antes}")

    vivas = [i for i in mem._items if i["provenance"].get("valid_until") is None]
    ok = ("3 de junio" in r["say"] and "10 de mayo" not in r["say"]
          and espia.llamadas == 0 and len(vivas) == 1 and len(mem._items) == 2)
    print("\n" + ("VEREDICTO: PASS — historial conservado, una sola version vigente, 0 llamadas al LLM"
                  if ok else "VEREDICTO: FALLA"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
