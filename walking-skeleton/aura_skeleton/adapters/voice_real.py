"""Adaptador de voz REAL: faster-whisper (STT, ADR-0012) + Piper (TTS, ADR-0013).
Mismo contrato que VoiceAdapterMock (stt/tts). Local, sin terceros (D24). Modelos se cargan de forma perezosa."""

from __future__ import annotations

import asyncio
import os
import subprocess

from .. import observability as obs


class WhisperPiperVoice:
    name = "voice"
    capabilities = ["stt", "tts"]

    def __init__(self, whisper_model: str = "base", piper_voice: str = "", out_dir: str = "/tmp/aura") -> None:
        self._wm_name = whisper_model
        self._voice = piper_voice  # ruta al .onnx de la voz Piper (es_MX/es_ES)
        self._out = out_dir
        self._model: object = None  # WhisperModel perezoso (Any por import diferido)
        os.makedirs(self._out, exist_ok=True)

    async def stt(self, audio_ref: str, trace_id: str) -> str:
        # Si audio_ref es un WAV existente, se transcribe; si no, se trata como texto (passthrough para --text).
        if isinstance(audio_ref, str) and audio_ref.lower().endswith(".wav") and os.path.exists(audio_ref):
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._stt_sync, audio_ref)
        else:
            text = audio_ref
        obs.log("VOICE", "whisper-stt", f"transcripcion: '{text[:50]}'", trace_id)
        return text

    def _stt_sync(self, wav: str) -> str:
        from faster_whisper import WhisperModel  # import perezoso (D24)

        if self._model is None:
            self._model = WhisperModel(self._wm_name, device="auto", compute_type="int8")
        model = self._model
        segments, _ = model.transcribe(wav)  # type: ignore[attr-defined]
        return " ".join(s.text for s in segments).strip()

    async def tts(self, text: str, trace_id: str) -> str:
        out = os.path.join(self._out, f"resp_{trace_id}.wav")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._tts_sync, text, out)
        obs.log("VOICE", "piper-tts", f"audio generado: {out}", trace_id)
        return out

    def _tts_sync(self, text: str, out: str) -> None:
        # Piper via CLI (robusto entre versiones); requiere la voz .onnx (ver Entorno de Desarrollo).
        subprocess.run(
            ["piper", "--model", self._voice, "--output_file", out],
            input=text.encode(),
            check=True,
        )
