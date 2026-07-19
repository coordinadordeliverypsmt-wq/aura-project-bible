"""Model Router (Bible 4.2) — orquestacion multi-modelo por contrato. Proveedores mock
implementan el mismo contrato que ChatGPT/Claude/Gemini. Enrutamiento + fallback + circuit breaker."""

from __future__ import annotations

import asyncio
import json

from .. import observability as obs


class MockProvider:
    def __init__(self, name, latency_ms, healthy=True):
        self.name = name
        self._lat = latency_ms
        self.healthy = healthy

    async def infer(self, prompt: str) -> str:
        await asyncio.sleep(self._lat / 1000.0)  # simula latencia del primer token
        if not self.healthy:
            raise RuntimeError(f"{self.name} no disponible")
        # La intencion se clasifica sobre la PETICION DEL USUARIO, no sobre el contexto de memoria:
        # el contexto no debe alterar lo que el usuario pide (leccion del walking skeleton; conecta con 5.2).
        u = prompt.split("Usuario:")[-1].lower() if "Usuario:" in prompt else prompt.lower()
        # Seguridad primero (P-ARQ-1): las intenciones de lista roja se detectan antes que las de lista verde.
        if "elimina" in u or "borra" in u:
            return json.dumps(
                {
                    "intent": "sistema",
                    "action": "eliminar_informacion",
                    "args": {"target": "archivo"},
                    "say": "Eso borrara informacion; necesito tu confirmacion.",
                }
            )
        if "acordamos" in u or "recuerda" in u or "que dijimos" in u:
            recuerdo = ""
            if "contexto memoria:" in prompt:
                recuerdo = prompt.split("contexto memoria:")[-1].split("]")[0].strip()
            return json.dumps(
                {"intent": "memoria", "action": "consulta", "args": {}, "say": f"Segun lo que recuerdo: {recuerdo}"}
            )
        if "luz" in u or "enciende" in u or "prende" in u:
            return json.dumps(
                {
                    "intent": "domotica",
                    "action": "encender_dispositivo",
                    "args": {"device": "luz sala"},
                    "say": "Listo, encendi la luz de la sala.",
                }
            )
        return json.dumps({"intent": "charla", "action": "consulta", "args": {}, "say": "Entendido."})


class ModelRouter:
    def __init__(self, providers, latency_budget_ms):
        self.providers = providers  # ordenados por preferencia (calidad/latencia/privacidad)
        self.budget = latency_budget_ms  # 2.5 5.1 (R1 nube <=1200ms)
        self._open = set()  # circuit breakers abiertos

    async def route(self, prompt, trace_id):
        for prov in self.providers:
            if prov.name in self._open:
                continue
            try:
                out = await prov.infer(prompt)
                obs.log("LLM", "router", f"enrutado a {prov.name}", trace_id)
                return prov.name, out
            except Exception as e:
                obs.log("WARN", "router", f"fallback: {prov.name} fallo ({type(e).__name__}: {e})", trace_id)
                self._open.add(prov.name)  # circuit breaker (4.2 3)
        raise RuntimeError("todos los proveedores fallaron (sin fallback disponible)")
