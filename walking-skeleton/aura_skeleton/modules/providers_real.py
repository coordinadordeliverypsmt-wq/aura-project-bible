"""Proveedores REALES tras el contrato ModelProvider (Bible 4.2 / ADR-0010).
Reutiliza EXACTAMENTE el contrato de contracts.ModelProvider; no modifica la arquitectura.
Requiere un servicio Ollama local corriendo (127.0.0.1:11434). No usa APIs de terceros (D24)."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request

_SYSTEM = (
    "Eres AURA. Responde UNICAMENTE un objeto JSON con las claves: "
    "intent (string), action (string), args (object), say (string en espanol). "
    "action debe ser EXACTAMENTE una de estas: "
    "encender_dispositivo, apagar_dispositivo, consulta, recordatorio, monitoreo, organizacion, automatizacion "
    "(acciones de bajo riesgo), o eliminar_informacion, pago, compra, transferencia, abrir_cerradura, "
    "mensaje_a_tercero, accion_legal, accion_financiera (acciones que requieren confirmacion). "
    "Elige la accion que mejor represente la peticion del usuario. No ejecutes nada; solo describe la decision. "
    # ADR-0014 (refuerzo, Alternativa B): el nucleo ya impide llegar aqui sin recuerdos, pero el
    # modelo tampoco debe insinuar lo inexistente si el contexto viene vacio.
    "AUTORIDAD SOBRE LOS HECHOS: el nucleo del sistema es la unica fuente de verdad. Si el contexto de "
    "memoria indica que no hay recuerdos, NUNCA afirmes ni insinues que existe informacion registrada; "
    "di claramente que no tienes registro. No inventes, completes ni reformules recuerdos."
)


class OllamaProvider:
    """Proveedor de inferencia local via Ollama. name/infer cumplen contracts.ModelProvider."""

    # Timeout del cliente HTTP. Por defecto 180 s. Se puede elevar con AURA_OLLAMA_TIMEOUT_S
    # para entornos de desarrollo por debajo del hardware minimo (p.ej. Lenovo 100e: 2 CPU,
    # 3,6 GB RAM, sin GPU, ~8.700 ms/token). NO es una optimizacion: solo evita que el cliente
    # aborte antes de que el modelo termine. El objetivo HC-1 (1.200 ms) sigue sin cumplirse.
    DEFAULT_TIMEOUT_S = 180

    def __init__(
        self, name: str, model: str, url: str = "http://127.0.0.1:11434", timeout_s: int | None = None
    ) -> None:
        self.name = name
        self.model = model
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s or int(os.getenv("AURA_OLLAMA_TIMEOUT_S", self.DEFAULT_TIMEOUT_S))

    async def infer(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._infer_sync, prompt)

    def _infer_sync(self, prompt: str) -> str:
        body = json.dumps(
            {"model": self.model, "prompt": prompt, "system": _SYSTEM, "stream": False, "format": "json"}
        ).encode()
        req = urllib.request.Request(
            self.url + "/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r:  # noqa: S310 (endpoint local, D24)
            resp = json.load(r)
        return str(resp["response"])  # con format=json, ya es un JSON string
