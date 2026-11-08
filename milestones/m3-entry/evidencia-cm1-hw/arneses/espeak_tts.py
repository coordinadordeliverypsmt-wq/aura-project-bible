"""TTS espeak-ng en memoria vía libespeak-ng.so.1 (paquete del sistema). Sin audio a disco."""
import ctypes, time
_lib = ctypes.CDLL("libespeak-ng.so.1")
_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
class Espeak:
    def __init__(self, voz=b"es-419", rate=None, buf_ms=60):
        self.sr = _lib.espeak_Initialize(2, buf_ms, None, 0)  # AUDIO_OUTPUT_SYNCHRONOUS
        if self.sr <= 0: raise RuntimeError("espeak_Initialize falló")
        if _lib.espeak_SetVoiceByName(voz) != 0: raise RuntimeError(f"voz {voz!r} no disponible")
        if rate: _lib.espeak_SetParameter(1, rate, 0)  # espeakRATE
        self._chunks = []; self._t_first = None
        self._cb = _CB(self._on_audio); _lib.espeak_SetSynthCallback(self._cb)
    def _on_audio(self, wav, n, _ev):
        if n > 0 and wav:
            if self._t_first is None: self._t_first = time.perf_counter()
            self._chunks.append(ctypes.string_at(wav, n * 2))
        return 0
    def synth(self, text):
        """Devuelve (pcm16 bytes, ms_hasta_primer_audio, ms_total)."""
        self._chunks = []; self._t_first = None; b = text.encode("utf-8") + b"\0"
        t = time.perf_counter(); r = _lib.espeak_Synth(b, len(b), 0, 1, 0, 1, None, None)
        if r != 0: raise RuntimeError(f"espeak_Synth={r}")
        tot = (time.perf_counter() - t) * 1000
        first = ((self._t_first or time.perf_counter()) - t) * 1000
        return b"".join(self._chunks), first, tot
