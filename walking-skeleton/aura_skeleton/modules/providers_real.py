"""Proveedores REALES tras el contrato ModelProvider (Bible 4.2 / ADR-0010).
Reutiliza EXACTAMENTE el contrato de contracts.ModelProvider; no modifica la arquitectura.
Requiere un servicio Ollama local corriendo (127.0.0.1:11434). No usa APIs de terceros (D24)."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
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


#: Prompt de **cognicion**: conversar, razonar, responder conocimiento general. Sin catalogo, sin
#: acciones. Mantiene el mismo contrato de salida para no romper `_parse_decision`, y fija `action`
#: en `consulta` porque por esta via **no se ejecuta nada**: si el usuario pide una accion, el
#: orquestador ya lo habra enrutado por el otro camino.
#: **ESQUEMA DE SALIDA DEL MODO COGNITIVO** (medido el 2026-09-09 en HC-1).
#:
#: EL DEFECTO. `format: "json"` solo obliga a que la salida sea JSON **valido**; no obliga a que tenga
#: las claves que se le piden. Medido con `qwen2.5:0.5b`: devolvia
#: `{"intent":"consulta","action":"consultar","args":{"nombre":"Jesus","tipo":1}}` —JSON impecable, sin
#: `say`, y con una **accion inventada y argumentos fabricados**—. El usuario recibia el fallback. La
#: causa NO era que el modelo no supiera responder: era que nadie le impedia no responder.
#:
#: LA REPARACION. Ollama >= 0.5 acepta un **JSON Schema** en `format` y restringe el decodificado por
#: gramatica: lo que el esquema exige, el modelo no puede omitir. Medido sobre el mismo prompt:
#: `say` presente 1/4 con `format: "json"` -> **4/4 con esquema**, y **0 acciones inventadas**.
#:
#: `action` es una CONSTANTE, no un string libre. Es la parte que importa para la seguridad: en modo
#: cognitivo el modelo no puede nombrar una accion **ni siquiera al decodificar**. No sustituye al
#: catalogo, ni a los permisos, ni al HITL —esos siguen siendo la autoridad—: es una barrera mas,
#: aguas arriba, en el unico sitio donde el problema todavia no existe.
#:
#: `minLength: 1` en `say` es la diferencia entre «la clave esta» y «la clave dice algo».
_ESQUEMA_COGNITIVO = {
    "type": "object",
    "properties": {
        "say": {"type": "string", "minLength": 1},
        "intent": {"type": "string"},
        "action": {"type": "string", "enum": ["consulta"]},
        "args": {"type": "object"},
    },
    "required": ["say", "action"],
}

_SYSTEM_COGNITIVO = (
    "Eres AURA, un asistente personal. Responde UNICAMENTE un objeto JSON con las claves: "
    'intent (string), action (string, siempre "consulta"), args (object vacio), '
    "say (string en espanol, tu respuesta al usuario). "
    "Conversa con naturalidad y razona cuando haga falta. "
    "Si no sabes algo, dilo en `say` en vez de inventarlo. "
    "NUNCA afirmes recordar algo sobre el usuario que no aparezca en el contexto de memoria."
)

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

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        """`modo` es opcional y por defecto conserva el comportamiento anterior.

        El contrato `ModelProvider` declara `infer(prompt)`; un parametro con valor por defecto lo
        sigue satisfaciendo, asi que el puerto **no se toca**."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._infer_sync, prompt, modo)

    def _infer_sync(self, prompt: str, modo: str = "accion") -> str:
        # **El catalogo solo viaja cuando hay algo que ejecutar.** Medido: el prompt de accion son
        # 630 tokens de ingesta, 311 s de los 441 s de una inferencia real —el 71%— y ante una
        # pregunta de conocimiento el modelo respondia eligiendo una accion del catalogo, con `say`
        # vacio. Pedirle que clasifique comandos cuando el usuario esta conversando es pedirle la
        # tarea equivocada, y ademas pagar el contexto de la equivocada.
        system = _SYSTEM_COGNITIVO if modo == "cognitivo" else _SYSTEM
        # **El esquema solo se aplica al modo cognitivo, y es deliberado.** En modo accion la eleccion
        # la gobierna el catalogo, y constrenir `action` a una lista cerrada aqui duplicaria esa
        # autoridad en un segundo sitio —el error que D-M-8 diagnostica en el propio sistema—. Ahi se
        # conserva `format: "json"` byte a byte.
        formato = _ESQUEMA_COGNITIVO if modo == "cognitivo" else "json"
        body = json.dumps(
            {"model": self.model, "prompt": prompt, "system": system, "stream": False,
             "format": formato}
        ).encode()
        req = urllib.request.Request(
            self.url + "/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:  # noqa: S310 (local, D24)
                resp = json.load(r)
        except urllib.error.HTTPError:
            # DEGRADACION, no operacion normal. El esquema necesita Ollama >= 0.5; si el runtime local
            # es mas antiguo lo rechaza con 4xx. Antes de dejar el turno sin respuesta se reintenta con
            # el contrato previo: se pierde la garantia del esquema —y con ella la fiabilidad de `say`—
            # pero el sistema sigue conversando. Nunca se reintenta mas de una vez.
            if formato == "json":
                raise
            body = json.dumps({"model": self.model, "prompt": prompt, "system": system,
                               "stream": False, "format": "json"}).encode()
            req = urllib.request.Request(
                self.url + "/api/generate", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:  # noqa: S310 (local, D24)
                resp = json.load(r)
        return str(resp["response"])  # con format JSON/esquema, ya es un JSON string
