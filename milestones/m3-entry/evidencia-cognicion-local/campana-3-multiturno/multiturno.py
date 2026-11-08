#!/usr/bin/env python3
"""Conversacion MULTITURNO real contra Ollama, a traves del ORQUESTADOR real.

Pregunta que deja abierta la campana 2: en una conversacion el system prompt es constante y queda en la
cache de prefijo, pero `[conversacion reciente: ...]` va delante de la pregunta y CAMBIA en cada turno.
¿Cuanto crece la ingesta a medida que se llena el buffer de 6 turnos?

- Composicion REAL del producto con voz MOCK: el stack real usa `WhisperPiperVoice` y, sin voz Piper
  configurada, el TTS revienta y descarta el turno (DECISION-REQUERIDA-VOZ-NO-DISPONIBLE, abierta).
- El proveedor envia el MISMO cuerpo que `OllamaProvider._infer_sync` (mismos simbolos importados) y
  ademas guarda las metricas que devuelve la API. No estima nada.

Uso: PYTHONPATH=<walking-skeleton> python3 multiturno.py <salida.json> [n_turnos]
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import urllib.request
import uuid

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.modules.providers_real import _ESQUEMA_COGNITIVO, _SYSTEM, _SYSTEM_COGNITIVO

PREGUNTAS = [
    "que es la fotosintesis?",
    "por que el cielo es azul?",
    "que es un agujero negro?",
    "que es un volcan?",
    "que significa la palabra resiliencia?",
    "que es la materia oscura?",
    "por que llueve?",
    "que es un numero primo?",
]


class ProveedorMedido:
    """Mismo contrato que `OllamaProvider`: `infer(prompt, modo)`. Registra metricas por llamada."""

    name = "ollama"

    def __init__(self) -> None:
        self.medidas: list[dict] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        return await asyncio.get_event_loop().run_in_executor(None, self._sync, prompt, modo)

    def _sync(self, prompt: str, modo: str) -> str:
        system = _SYSTEM_COGNITIVO if modo == "cognitivo" else _SYSTEM
        formato = _ESQUEMA_COGNITIVO if modo == "cognitivo" else "json"
        cuerpo = {"model": "qwen2.5:0.5b", "prompt": prompt, "system": system, "stream": False, "format": formato}
        pet = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps(cuerpo).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(pet, timeout=900) as r:  # noqa: S310 (local)
            crudo = json.loads(r.read())
        ns = 1_000_000_000
        self.medidas.append({
            "modo": modo, "reloj_s": round(time.monotonic() - t0, 2),
            "prompt_caracteres": len(prompt),
            "ingesta_tokens": crudo.get("prompt_eval_count", 0),
            "ingesta_s": round(crudo.get("prompt_eval_duration", 0) / ns, 2),
            "generacion_tokens": crudo.get("eval_count", 0),
            "generacion_s": round(crudo.get("eval_duration", 0) / ns, 2),
            "total_s": round(crudo.get("total_duration", 0) / ns, 2),
            "carga_s": round(crudo.get("load_duration", 0) / ns, 2),
        })
        return str(crudo["response"])


async def main() -> int:
    salida = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    datos = tempfile.mkdtemp(prefix="multiturno-")
    s = componer(Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=False))
    prov = ProveedorMedido()
    s.orquestador.router.providers = [prov]

    turnos = []
    for i, pregunta in enumerate(PREGUNTAS[:n], 1):
        antes = len(prov.medidas)
        tid = uuid.uuid4().hex[:12]
        await s.orquestador.handle_utterance("mauricio", pregunta, tid)
        r = await s.orquestador.wait(tid)
        medida = prov.medidas[-1] if len(prov.medidas) > antes else None
        fila = {"turno": i, "pregunta": pregunta, "provider": r.get("provider"), "dominio": r.get("dominio"),
                "say": r.get("say", "")[:200], "medida": medida}
        turnos.append(fila)
        m = medida or {}
        print(f"T{i} {pregunta!r:42s} prov={r.get('provider'):6s} prompt={m.get('prompt_caracteres')}c "
              f"ing={m.get('ingesta_tokens')}tok/{m.get('ingesta_s')}s gen={m.get('generacion_tokens')}tok/"
              f"{m.get('generacion_s')}s total={m.get('total_s')}s", flush=True)
        with open(salida, "w") as f:
            json.dump({"datos": datos, "turnos": turnos}, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
