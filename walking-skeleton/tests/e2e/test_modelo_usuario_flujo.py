"""E2E MVP Modelo de Usuario: inspeccionar, entender, corregir y OLVIDAR — con REINICIO real.

Criterio definitivo del CEO (2026-07-28): tras "olvida eso" y un reinicio de AURA, el dato NO reaparece.
Si reaparece, el incremento NO está terminado aunque las pruebas estén en verde. Esta prueba reconstruye
la memoria desde disco (el "reinicio") y verifica que el olvido persistió.
"""

import os
import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


async def _deny(a, args, tid):
    return False


def _orq(mem):
    return Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([MockProvider("m", 1)], 1200),
        PermissionManager(_deny),
        VoiceAdapterMock(),
        HomeAssistantMock(),
        modelo_usuario=ModeloUsuario(mem),
    )


async def _di(orq, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return (await orq.wait(tid))["say"]


async def _sembrar(mem):
    # Lo que AURA "sabe" del usuario: uno declarado, uno observado.
    await mem.write(
        "mauricio", "semantica", "prefiere la luz tenue de noche", {"origen": "declarada", "fuente": "usuario"}
    )
    await mem.write(
        "mauricio",
        "semantica",
        "suele pagar las facturas por la app",
        {"origen": "observada", "fuente": "conversacion"},
    )


@pytest.mark.asyncio
async def test_soberania_completa_con_reinicio(tmp_path):
    ruta = os.path.join(tmp_path, "mem.jsonl")
    mem = PersistentMemory(ruta)
    await _sembrar(mem)
    orq = _orq(mem)

    # 1. Inspeccionar: AURA distingue declarado ("me lo dijiste") de observado ("lo he observado").
    r1 = await _di(orq, "¿Qué sabes de mí?")
    assert "prefiere la luz tenue de noche (me lo dijiste)" in r1
    assert "suele pagar las facturas por la app (lo he observado)" in r1

    # 2. Entender: por qué lo sabe (el foco es lo observado, lo cuestionable).
    r2 = await _di(orq, "¿Por qué dices eso?")
    assert "observado" in r2.lower() and "facturas" in r2.lower()

    # 3. Corregir: "eso ya no es cierto".
    r3 = await _di(orq, "Eso ya no es cierto.")
    assert "corrijo" in r3.lower()

    # 4. Olvidar: "olvida eso".
    r4 = await _di(orq, "Olvida eso.")
    assert "hecho" in r4.lower()

    # --- REINICIO: nueva memoria desde disco, nuevo orquestador ---
    orq2 = _orq(PersistentMemory(ruta))
    r5 = await _di(orq2, "¿Qué sabes de mí?")
    assert "luz tenue" in r5, "lo declarado no olvidado debe seguir"
    assert "facturas" not in r5, "lo OLVIDADO no puede reaparecer tras reiniciar"


@pytest.mark.asyncio
async def test_olvidar_un_termino_explicito(tmp_path):
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    r = await _di(orq, "Olvida lo de las facturas.")
    assert "hecho" in r.lower()
    r2 = await _di(orq, "¿Qué sabes de mí?")
    assert "facturas" not in r2 and "luz tenue" in r2
