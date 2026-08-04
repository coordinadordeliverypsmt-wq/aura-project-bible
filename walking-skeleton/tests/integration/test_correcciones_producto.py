"""Integracion: las tres correcciones deterministas que afectan al usuario real.

Ninguna necesita un LLM mas capaz. Todas se midieron sobre la bateria oficial.
"""

import asyncio
import json
import os
from pathlib import Path

from aura_skeleton.core.orchestrator import _es_consulta_de_memoria, _es_pregunta
from aura_skeleton.modules.memory import PersistentMemory

_B = json.loads((Path(__file__).parent.parent / "datos" / "bateria_memoria.json").read_text(encoding="utf-8"))


def _recall_bateria(tmp_path, prefijo=""):
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    mapa = {r["content"]: r["id"] for r in _B["corpus"]}

    async def correr():
        for r in _B["corpus"]:
            await mem.write(r["user_id"], "sem", r["content"], {})
        ac = tot = 0
        for c in _B["consultas"]:
            if c["esperado"] is None:
                continue
            tot += 1
            ids = [mapa[h["content"]] for h in await mem.recall("u1", prefijo + c["texto"], k=3)]
            ac += c["esperado"] in ids
        return ac, tot

    return asyncio.run(correr())


def test_DM3_una_coletilla_de_cortesia_ya_no_derrumba_el_recall(tmp_path):
    """Antes: «oye AURA por favor dime» dejaba el recall en 0,000. Un usuario hablando con
    naturalidad se quedaba sin memoria."""
    base = _recall_bateria(str(tmp_path))
    for prefijo in ("por favor ", "oye AURA por favor dime ", "oye AURA una cosa que queria preguntarte "):
        assert _recall_bateria(str(tmp_path), prefijo) == base, f"la coletilla {prefijo!r} altero el recall"


def test_DM7_ADR0014_se_activa_ante_una_pregunta_real(tmp_path):
    """Antes reconocia 0 de las 77 consultas de la bateria, incluidas las 24 negativas que la
    garantia de no-fabricacion existe para proteger."""
    reconocidas = sum(1 for c in _B["consultas"] if _es_consulta_de_memoria(c["texto"]))
    assert reconocidas >= 70, f"la garantia solo cubre {reconocidas}/77 consultas"
    for negativa in ("¿Cuál es el nombre de mi abuela?", "¿Cuál es la combinación de mi caja fuerte?"):
        assert _es_consulta_de_memoria(negativa), f"no se activaria ante {negativa!r}"


def test_DM7_una_afirmacion_no_se_confunde_con_una_pregunta():
    """CONTROL: sin esto, la mejora anterior pasaria clasificandolo TODO como consulta."""
    for afirmacion in ("Mi color favorito es el azul", "Trabajo en logistica", "Prefiero la luz tenue"):
        assert not _es_pregunta(afirmacion), f"{afirmacion!r} no es una pregunta"


def test_DM2_una_pregunta_no_se_almacena_como_recuerdo(tmp_path):
    """Antes, repetir una pregunta la hacia cubrirse a si misma con cobertura 1,00 y ADR-0014
    dejaba de activarse: el sistema recibia su propia pregunta como si fuera un recuerdo."""
    assert _es_pregunta("¿Recuerdas cual es el nombre de mi abuela?")
    assert not _es_pregunta("Enciende la luz de la sala")


def test_DM2_repetir_una_pregunta_NO_desactiva_ADR0014(tmp_path):
    """EL EFECTO REAL, no solo el detector: lo detecto la mutacion (M4 sobrevivia).

    Antes, el turno almacenaba la pregunta como recuerdo; al repetirla se cubria a si misma con
    cobertura 1,00, `hits` dejaba de estar vacio y la garantia de no-fabricacion no se activaba.
    """
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock
    from aura_skeleton.adapters.voice import VoiceAdapterMock
    from aura_skeleton.bus import InProcessEventBus
    from aura_skeleton.core.orchestrator import Orchestrator
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.modules.router import MockProvider, ModelRouter

    async def _deny(a, args, tid):
        return False

    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    orq = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([MockProvider("m", 1)], 1200),
        PermissionManager(_deny),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    pregunta = "¿Recuerdas cual es el nombre de mi abuela?"

    async def dos_turnos():
        for _ in range(2):
            await orq._finalizar_turno(
                "u",
                "t",
                pregunta,
                "resp",
                "core",
                __import__("aura_skeleton.observability", fromlist=["Timer"]).Timer(),
            )
        return await mem.recall("u", pregunta)

    hits = asyncio.run(dos_turnos())
    assert hits == [], f"la pregunta se almaceno y volvio a encontrarse: {hits}"
