import json, time, numpy as np, statistics as st
from vosk import Model, KaldiRecognizer, SetLogLevel
from piper import PiperVoice
SetLogLevel(-1)
M = Model("/media/majo1230/AURORA_EXT/vosk-model-small-es-0.42"); pv = PiperVoice.load("/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx")
FR = ["¿Cuál es mi color favorito?", "Me llamo Mauricio.", "¿Cómo me llamo?"]
GRAM = json.dumps(["cómo me llamo", "cuál es mi color favorito", "me llamo mauricio", "mi color favorito es el verde", "[unk]"], ensure_ascii=False)
def pcm16k(f):
    a = np.concatenate([c.audio_int16_array for c in pv.synthesize(f)]).astype(np.float32); sr = pv.config.sample_rate
    y = np.interp(np.linspace(0, len(a)-1, int(len(a)*16000/sr)), np.arange(len(a)), a).astype(np.int16)
    z = np.zeros(8000, np.int16); return np.concatenate([z, y, z]).tobytes()
for nombre, mk in (("libre", lambda: KaldiRecognizer(M, 16000)), ("gramatica", lambda: KaldiRecognizer(M, 16000, GRAM))):
    for f in FR:
        b = pcm16k(f); dur = len(b)/32000; acc, fin = [], []
        for _ in range(3):
            r = mk(); t = time.perf_counter()
            for i in range(0, len(b), 640): r.AcceptWaveform(b[i:i+640])
            t1 = time.perf_counter(); txt = json.loads(r.FinalResult())["text"]; t2 = time.perf_counter()
            acc.append(t1 - t); fin.append((t2 - t1) * 1000)
        print(f"{nombre:9} {f[:28]:28} audio={dur:.2f}s RTF={st.median(acc)/dur:.2f} FinalResult={st.median(fin):.0f} ms -> {txt!r}", flush=True)
