"""Orquestador (nucleo, Bible 3.2/4.2/4.3). Coordina memoria, router y permisos.
Un turno: percepcion -> memoria -> router (decide) -> permisos -> accion -> respuesta, todo con trace_id."""
from __future__ import annotations
import json
from ..contracts import Event
from ..observability import Timer
from .. import observability as obs

class Orchestrator:
    def __init__(self, bus, memory, router, permissions, voice, ha):
        self.bus, self.memory, self.router = bus, memory, router
        self.perm, self.voice, self.ha = permissions, voice, ha
        bus.subscribe("perception.turn_end", self.on_turn)

    async def handle_utterance(self, user_id, audio_text, trace_id):
        t = Timer()
        text = await self.voice.stt(audio_text, trace_id); t.mark("stt")
        await self.bus.publish(Event("perception.turn_end", trace_id, user_id, {"text": text, "timer": t}))

    async def on_turn(self, ev: Event):
        t: Timer = ev.payload["timer"]; text = ev.payload["text"]; tid = ev.trace_id; uid = ev.user_id
        # 1) memoria: recuperar contexto (no fabrica si vacio)
        hits = await self.memory.recall(uid, text); t.mark("memory")
        ctx = " | ".join(h["content"] for h in hits) if hits else "(sin recuerdos relevantes)"
        # 2) router multi-modelo decide intencion + accion
        prompt = f"[contexto memoria: {ctx}]\nUsuario: {text}"
        prov, out = await self.router.route(prompt, tid); t.mark("llm")
        decision = json.loads(out)
        action, args, say = decision["action"], decision.get("args",{}), decision["say"]
        # 3) permisos / HITL antes de ejecutar (ninguna accion directa)
        result_note = ""
        if action in ("encender_dispositivo","apagar_dispositivo","eliminar_informacion"):
            ok, reason = await self.perm.authorize(action, args, tid)
            if ok and action in self.ha.capabilities:
                cmd_ev = Event("action.command", tid, uid, {"action":action,"args":args}, causation_id=ev.event_id)
                await self.ha.execute(action, args, tid, cmd_ev.event_id)
                result_note = f" [accion {action} ejecutada: {reason}]"
            elif ok:
                result_note = f" [accion {action} autorizada: {reason}]"
            else:
                say = "No ejecute la accion."; result_note = f" [accion {action} {reason}]"
        # 4) memoria: registrar el turno (con procedencia)
        await self.memory.write(uid, "episodica", f"usuario dijo: {text}", {"trace_id":tid,"fuente":"conversacion"})
        # 5) respuesta hablada
        await self.voice.tts(say + result_note, tid); t.mark("tts")
        obs.log("LAT", "orchestrator", f"latencia total {t.total_ms():.0f} ms (proveedor={prov})", tid, audit=True)
        return {"say": say, "provider": prov, "latency_ms": t.total_ms(), "marks": t.marks}
