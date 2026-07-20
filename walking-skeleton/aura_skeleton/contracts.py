"""Contratos del núcleo (Bible 3.3/3.4). Independientes de producto: el bus in-process
implementa el mismo contrato que NATS (ADR-0006); los proveedores mock implementan el
mismo contrato que ChatGPT/Claude/Gemini (4.2). Cambiar el producto no toca a los consumidores."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


def _uid() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Event:
    """Sobre de evento común (Bible 3.3 §2). Toda acción discreta viaja por el bus con estos campos."""

    type: str  # p.ej. "perception.turn_end", "action.command"
    trace_id: str  # correlación bus<->stream (ALERTA-001)
    user_id: str  # multi-usuario-ready (P-ARQ-5)
    payload: dict = field(default_factory=dict)
    event_id: str = field(default_factory=_uid)
    causation_id: str | None = None
    schema_version: str = "1.0.0"
    ts: float = field(default_factory=time.time)


@runtime_checkable
class EventBus(Protocol):
    async def publish(self, event: Event) -> None: ...
    def subscribe(self, type_prefix: str, handler: Callable[[Event], Awaitable[None]]) -> None: ...


@runtime_checkable
class MemoryStore(Protocol):
    async def write(self, user_id: str, kind: str, content: str, provenance: dict) -> None: ...
    async def recall(self, user_id: str, query: str, k: int = 3) -> list[dict]: ...


@runtime_checkable
class ModelProvider(Protocol):
    name: str

    async def infer(self, prompt: str) -> str: ...


@runtime_checkable
class Adapter(Protocol):
    """Contrato de adaptador de dominio (Bible 6.1).

    H1 (M2.0): la firma declarada omitia `trace_id` y `event_id`, que el orquestador SI pasa.
    `runtime_checkable` solo comprueba que el metodo exista, no su firma, por lo que la prueba de
    contrato pasaba con una declaracion incorrecta. Quien escribiera un adaptador nuevo siguiendo
    el contrato habria escrito uno roto. Corregido para reflejar el uso real; la verificacion de
    firma vive en `tests/test_contracts.py::test_contrato_adapter_firma`.

    `event_id` es obligatorio: los adaptadores lo usan para idempotencia (3.3 §3), de modo que un
    mismo evento reentregado no produzca dos efectos reales. En M2 esto deja de ser teorico.
    """

    name: str
    capabilities: list[str]

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict: ...


@runtime_checkable
class VoiceAdapter(Protocol):
    """Contrato de voz del Core (T2.b, Bible 6.2).

    Formaliza lo que hasta ahora era convencion: `VoiceAdapterMock` y `WhisperPiperVoice`
    coincidian en `stt`/`tts` por acuerdo tacito, sin contrato verificable. Se define ANTES de
    implementar captura, VAD o barge-in (riesgo RA-2 del plan T2): si esas capacidades se
    construyeran primero, la interfaz quedaria fijada por accidente en vez de por diseno.

    `stt` acepta una ruta a WAV o texto plano. El *passthrough* de texto es deliberado —permite
    ejercitar el nucleo sin audio— pero NO constituye transcripcion: una prueba de STT real debe
    partir de un WAV y verificar que el texto proviene del modelo (leccion de la auditoria T1).

    Nota de evolucion (no vinculante): las capacidades de conversacion continua exigiran
    streaming y cancelacion. Este contrato no las incluye porque aun no estan autorizadas; su
    incorporacion sera una extension versionada, no una ruptura (ADR-0004, interfaces estables).
    """

    name: str
    capabilities: list[str]

    async def stt(self, audio_ref: str, trace_id: str) -> str:
        """Transcribe audio a texto. `audio_ref`: ruta a WAV existente, o texto (passthrough)."""
        ...

    async def tts(self, text: str, trace_id: str) -> str:
        """Sintetiza voz. Devuelve la referencia al audio producido."""
        ...


@runtime_checkable
class AdaptadorSimulable(Protocol):
    """Adaptador capaz de PREVISUALIZAR una operacion sin ejecutarla (M2.3).

    Se define como Protocol SEPARADO en lugar de anadir un parametro a `Adapter`: ese contrato
    acaba de fijarse con prueba de firma (H1) y ampliarlo obligaria a todo adaptador existente a
    implementar simulacion. Aqui la capacidad es opcional y declarada — quien no la implemente,
    simplemente no puede participar en automatizaciones que alteren el estado.

    `simular` NUNCA debe producir efectos. Su resultado es un PLAN: que ocurriria y si seria viable.
    """

    async def simular(self, command: str, args: dict, trace_id: str) -> dict: ...
