"""Ida y vuelta TTS→Vosk (reconocimiento libre) en memoria. Mide inteligibilidad, no guarda audio."""
import json, sys, numpy as np, unicodedata, re
sys.path.insert(0, sys.path[0])
from vosk import Model, KaldiRecognizer, SetLogLevel
from espeak_tts import Espeak
from piper import PiperVoice
SetLogLevel(-1)
FR = ["Sí.", "Te llamas Mauricio.", "Tienes dos recordatorios para hoy.", "Son las cuatro y veinte.",
      "Mañana tienes una cita con el médico.", "No tengo esa información.", "La luz de la cocina está apagada.", "Hoy es martes."]
M = Model("/media/majo1230/AURORA_EXT/vosk-model-small-es-0.42")
def norm(s): s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn"); return re.sub(r"[^a-zñ ]", "", s).split()
def wer(ref, hyp):
    r, h = norm(ref), norm(hyp); d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(h) + 1): p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(1, len(r))
def stt(pcm16, sr):
    x = np.frombuffer(pcm16, np.int16).astype(np.float32); n = int(len(x) * 16000 / sr)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.int16)
    rec = KaldiRecognizer(M, 16000); rec.AcceptWaveform(y.tobytes()); return json.loads(rec.FinalResult())["text"]
if __name__ == '__main__':
    e = Espeak(); pv = PiperVoice.load("/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx")
    res = {"espeak": [], "piper_medium": []}
    for f in FR:
        pcm, _, _ = e.synth(f); h = stt(pcm, e.sr); rms = float(np.sqrt(np.mean(np.frombuffer(pcm, np.int16).astype(np.float32) ** 2)))
        res["espeak"].append((f, h, round(wer(f, h), 2), round(rms)))
        a = np.concatenate([c.audio_int16_array for c in pv.synthesize(f)]); h2 = stt(a.tobytes(), pv.config.sample_rate)
        res["piper_medium"].append((f, h2, round(wer(f, h2), 2), round(float(np.sqrt(np.mean(a.astype(np.float32) ** 2))))))
    for k, v in res.items():
        print(k, "WER medio =", round(sum(x[2] for x in v) / len(v), 3))
        for x in v: print("   ", x)
