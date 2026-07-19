"""Orquestador (nucleo, Bible 3.2/4.2/4.3). Coordina memoria, router y permisos.
Los eventos son SERIALIZABLES (contrato 3.3): el estado de temporizacion se guarda por trace_id,
no en el payload. Asi el MISMO orquestador corre sobre el bus in-process o sobre NATS real."""

from __future__ import annotations

import asyncio

from .. import observability as obs
from ..contracts import Event
from ..observability import Timer


def _parse_decision(out: str, tid: str) -> tuple[str, dict, str]:
    """Parsing defensivo de la salida del LLM (resiliencia; los modelos reales a veces devuelven
    JSON imperfecto o con texto alrededor). Nunca crashea: ante fallo, decision segura (consulta)."""
    import json as _j

    for candidate in (out, _extract_json(out)):
        if not candidate:
            continue
        try:
            d = _j.loads(candidate)
            action = str(d.get("action", "consulta")) or "consulta"
            args = d.get("args", {}) if isinstance(d.get("args", {}), dict) else {}
            say = str(d.get("say", "")) or "Entendido."
            return action, args, say
        except (ValueError, TypeError):
            continue
    obs.log("WARN", "orchestrator", "salida del LLM no parseable -> decision segura (consulta)", tid, audit=True)
    return "consulta", {}, "No entendi bien; puedes reformularlo?"


def _extract_json(s: str) -> str:
    a, b = s.find("{"), s.rfind("}")
    return s[a : b + 1] if 0 <= a < b else ""


class Orchestrator:
    def __init__(self, bus, memory, router, permissions, voice, ha):
        self.bus, self.memory, self.router = bus, memory, router
        self.perm, self.voice, self.ha = permissions, voice, ha
        self._timers: dict[str, Timer] = {}
        self._done: dict[str, asyncio.Event] = {}
        self._results: dict[str, dict] = {}
        self._dialogue: dict[str, list[tuple[str, str]]] = {}  # memoria de trabajo por usuario
        self._DIALOG_N = 6
        bus.subscribe("perception.turn_end", self.on_turn)

    async def handle_utterance(self, user_id, audio_text, trace_id):
        t = Timer()
        self._timers[trace_id] = t
        self._done[trace_id] = asyncio.Event()
        text = await self.voice.stt(audio_text, trace_id)
        t.mark("stt")
        await self.bus.publish(Event("perception.turn_end", trace_id, user_id, {"text": text}))

    async def wait(self, trace_id, timeout=10):
        await asyncio.wait_for(self._done[trace_id].wait(), timeout)
        return self._results.get(trace_id)

    async def on_turn(self, ev: Event):
        tid = ev.trace_id
        uid = ev.user_id
        text = ev.payload["text"]
        t = self._timers.get(tid) or Timer()
        hits = await self.memory.recall(uid, text)
        t.mark("memory")
        ctx = " | ".join(h["content"] for h in hits) if hits else "(sin recuerdos relevantes)"
        buffer = self._dialogue.get(uid, [])
        recent = "\n".join(f"(previo) tu: {u} | AURA: {a}" for u, a in buffer) or "(inicio de la conversacion)"
        prompt = f"[contexto memoria: {ctx}]\n[conversacion reciente:\n{recent}]\nUsuario: {text}"
        prov, out = await self.router.route(prompt, tid)
        t.mark("llm")
        action, args, say = _parse_decision(out, tid)
        if action != "consulta":  # FIX seguridad: TODA accion con efecto pasa por Permisos/HITL (ADR-0003/5.3)
            ok, reason = await self.perm.authorize(action, args, tid)
            if ok and action in self.ha.capabilities:
                cmd_ev = Event("action.command", tid, uid, {"action": action, "args": args}, causation_id=ev.event_id)
                await self.ha.execute(action, args, tid, cmd_ev.event_id)
                say = say + f" [accion {action} ejecutada: {reason}]"
            elif ok:
                say = say + f" [accion {action} autorizada: {reason}]"
            else:
                say = "No ejecute la accion." + f" [accion {action} {reason}]"
        await self.memory.write(uid, "episodica", f"usuario dijo: {text}", {"trace_id": tid, "fuente": "conversacion"})
        buffer = self._dialogue.setdefault(uid, [])
        buffer.append((text, say))
        del buffer[: max(0, len(buffer) - self._DIALOG_N)]  # conserva las ultimas N (memoria de trabajo)
        await self.voice.tts(say, tid)
        t.mark("tts")
        total = t.total_ms()
        obs.log("LAT", "orchestrator", f"latencia total {total:.1f} ms (proveedor={prov})", tid, audit=True)
        self._results[tid] = {"say": say, "provider": prov, "latency_ms": total, "marks": dict(t.marks)}
        if tid in self._done:
            self._done[tid].set()
