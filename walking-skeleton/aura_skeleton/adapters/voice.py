"""Adaptador de Voz (Bible 6.2) — mock STT/TTS en texto. En produccion: Whisper+Piper locales
(ADR-0008), streams por canal dedicado. Aqui validamos la capa de percepcion/accion y el trace_id."""
from __future__ import annotations
from .. import observability as obs

class VoiceAdapterMock:
    name = "voice"
    capabilities = ["stt","tts"]
    async def stt(self, audio_text, trace_id):    # simula transcripcion (canal dedicado, ALERTA-001)
        obs.log("VOICE", "voice-stt", f"transcripcion: '{audio_text}'", trace_id)
        return audio_text
    async def tts(self, text, trace_id):
        obs.log("VOICE", "voice-tts", f"AURA dice: \"{text}\"", trace_id)
        return text
