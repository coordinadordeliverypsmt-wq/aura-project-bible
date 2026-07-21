"""Proveedores REALES tras el contrato ModelProvider (Bible 4.2 / ADR-0010).
Reutiliza EXACTAMENTE el contrato de contracts.ModelProvider; no modifica la arquitectura.
Requiere un servicio Ollama local corriendo (127.0.0.1:11434). No usa APIs de terceros (D24)."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request


def _catalogo_para_prompt() -> str:
    """Construye la lista de acciones DESDE el catalogo del nucleo (M2.5).

    Hasta M2.4 esta lista estaba escrita a mano en el prompt y no incluia ninguna operacion del
    computador: el modelo no podia emitirlas aunque el adaptador existiera. Mantener a mano una
    copia del catalogo garantiza que ambas diverjan —es la misma clase de fallo que ALERTA-005—,
    asi que se deriva. Anadir una accion al catalogo la hace conocida por el modelo sin tocar esto.

    El prompt NO decide permisos: solo informa al modelo de que puede pedir. La clasificacion
    verde/roja la resuelve el nucleo (ADR-0014); se menciona unicamente para que el modelo no
    prometa al usuario cosas que requeriran confirmacion.
    """
    from ..core.operaciones import ESPECIFICACIONES
    from ..core.permissions import CATALOGO

    lineas = []
    for accion, meta in CATALOGO.items():
        spec = ESPECIFICACIONES.get(accion)
        args = f" args: {{{', '.join(spec['args'])}}}" if spec and spec["args"] else ""
        lineas.append(f"- {accion} ({meta['lista']}){args}")
    return "\n".join(lineas)


_SYSTEM = (
    "Eres AURA. Responde UNICAMENTE un objeto JSON con las claves: "
    "intent (string), action (string), args (object), say (string en espanol). "
    "action debe ser EXACTAMENTE una de las de este catalogo:\n" + _catalogo_para_prompt() + "\n"
    "Las marcadas (roja) requeriran confirmacion del usuario; no prometas haberlas hecho. "
    "Para operaciones de archivos usa RUTAS ABSOLUTAS tal y como aparezcan en la peticion. "
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
