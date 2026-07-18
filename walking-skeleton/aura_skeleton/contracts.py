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
    name: str
    capabilities: list[str]

    async def execute(self, command: str, args: dict) -> dict: ...
