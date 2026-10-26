import sys, numpy as np; sys.path.insert(0, sys.path[0])
import inteligibilidad as I; from espeak_tts import Espeak; from piper import PiperVoice
FR = I.FR + ["Tu próxima reunión es a las diez.", "He apagado la música.", "La temperatura es de veinte grados.", "Te lo recuerdo mañana."]
for rate in (175, 190, 205):
    e = Espeak(b"es", rate); w = [I.wer(f, I.stt(e.synth(f)[0], e.sr)) for f in FR]; print("espeak es", rate, round(sum(w)/len(w), 3), flush=True)
pv = PiperVoice.load("/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"); w = []
for f in FR:
    a = np.concatenate([c.audio_int16_array for c in pv.synthesize(f)]); w.append(I.wer(f, I.stt(a.tobytes(), pv.config.sample_rate)))
print("piper es_MX medium", round(sum(w)/len(w), 3))
