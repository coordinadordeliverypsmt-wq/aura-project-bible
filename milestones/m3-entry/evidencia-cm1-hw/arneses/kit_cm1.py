"""Kit de medición CM1 por etapas — para ejecutar IGUAL en HC-1 y en cualquier hardware candidato (vía 3).

Herramienta de DESARROLLO, no runtime de AURA. Mide, con los mismos modelos y las mismas frases, cada etapa
del turno de voz y deja un JSON comparable. La ACEPTACIÓN de CM1 NO sale de aquí (es una suma de etapas):
sale del E2E físico `e2e_cm1.py` (fin de habla → inicio de respuesta hablada, Bible 2.5 §5.1).

Uso:  AURA_USB=/ruta/a/modelos  python3 kit_cm1.py salida.json
      (AURA_USB debe contener piper_voices/es_MX-ald-medium.onnx, vosk-model-small-es-0.42 y hf_cache/hub)
Privacidad: la voz de prueba es SINTÉTICA (Piper) y vive solo en memoria. No se escribe audio a disco.
"""

import json
import os
import platform
import statistics as st
import subprocess
import sys
import time

import numpy as np

USB = os.environ.get("AURA_USB", "/media/majo1230/AURORA_EXT")
VOZ = f"{USB}/piper_voices/es_MX-ald-medium.onnx"
VOSK = f"{USB}/vosk-model-small-es-0.42"
os.environ.setdefault("HF_HUB_CACHE", f"{USB}/hf_cache/hub")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
N = int(os.environ.get("KIT_N", "5"))
ORDENES = ["¿Cómo me llamo?", "¿Cuál es mi color favorito?"]
RESPUESTAS = ["Sí.", "Te llamas Mauricio.", "Tienes dos recordatorios para hoy."]


def ms(t0):
    return round((time.perf_counter() - t0) * 1000, 1)


def p50(xs):
    return round(st.median(xs), 1)


def maquina():
    flags = ""
    try:
        flags = next(l for l in open("/proc/cpuinfo") if l.startswith("flags"))
    except (OSError, StopIteration):
        pass
    isa = [f for f in ("sse4_2", "avx", "avx2", "fma", "avx512f", "avx_vnni", "amx_tile") if f" {f}" in flags]
    try:
        gpus = subprocess.run(["lspci"], capture_output=True, text=True).stdout
        gpus = [l.split(": ", 1)[1] for l in gpus.splitlines() if any(k in l for k in ("VGA", "3D", "Display", "accelerators"))]
    except OSError:
        gpus = []
    mem = next((int(l.split()[1]) // 1024 for l in open("/proc/meminfo") if l.startswith("MemTotal")), None)
    return {"cpu": platform.processor() or next((l.split(":")[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), ""),
            "nucleos_logicos": os.cpu_count(), "isa": isa, "ram_mb": mem, "gpus": gpus, "python": platform.python_version()}


def pcm16k(voz, texto):
    a = np.concatenate([c.audio_int16_array for c in voz.synthesize(texto)]).astype(np.float32)
    sr = voz.config.sample_rate
    return np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / sr)), np.arange(len(a)), a).astype(np.int16)


def medir_tts(voz, out):
    from espeak_tts import Espeak  # arnés local: libespeak-ng del sistema
    piper, esp = {}, {}
    e = Espeak(b"es", 175)
    for f in RESPUESTAS:
        ids = [voz.phonemes_to_ids(p) for p in voz.phonemize(f) if p]
        ts = []
        for _ in range(N + 1):
            t0 = time.perf_counter()
            for x in ids:
                voz.phoneme_ids_to_audio(x)
            ts.append(ms(t0))
        piper[f] = {"calentamiento_ms": ts[0], "p50_ms": p50(ts[1:])}
        esp[f] = {"p50_ms": p50([e.synth(f)[2] for _ in range(N)])}
    out["tts_piper_medium"] = piper
    out["tts_espeak_es_175"] = esp


def medir_stt(voz, out):
    from faster_whisper import WhisperModel
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    audios = {o: pcm16k(voz, o) for o in ORDENES}
    for nombre in ("tiny", "base"):
        t0 = time.perf_counter()
        m = WhisperModel(nombre, device="auto", compute_type="int8", local_files_only=True)
        carga = ms(t0)
        fila = {"carga_ms": carga, "device": str(getattr(m.model, "device", "?"))}
        for o, a in audios.items():
            x = a.astype(np.float32) / 32768.0
            ts, txt = [], ""
            for _ in range(N):
                t0 = time.perf_counter()
                segs, _ = m.transcribe(x, language="es")
                txt = " ".join(s.text for s in segs).strip()
                ts.append(ms(t0))
            fila[o] = {"audio_s": round(len(a) / 16000, 2), "p50_ms": p50(ts), "texto": txt}
        out[f"stt_whisper_{nombre}"] = fila
        del m
    modelo = Model(VOSK)
    fila = {}
    for o, a in audios.items():
        b = a.tobytes()
        ts, fin, txt = [], [], ""
        for _ in range(N):
            r = KaldiRecognizer(modelo, 16000)
            t0 = time.perf_counter()
            for i in range(0, len(b), 640):
                r.AcceptWaveform(b[i:i + 640])
            t1 = time.perf_counter()
            txt = json.loads(r.FinalResult())["text"]
            ts.append(round((t1 - t0) * 1000, 1)); fin.append(ms(t1))
        fila[o] = {"audio_s": round(len(b) / 32000, 2), "rtf": round(st.median(ts) / 1000 / (len(b) / 32000), 2),
                   "p50_final_ms": p50(fin), "texto": txt}
    out["stt_vosk_small_libre"] = fila


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from piper import PiperVoice

    out = {"fecha": time.strftime("%Y-%m-%dT%H:%M:%S"), "maquina": maquina(), "N": N}
    t0 = time.perf_counter()
    voz = PiperVoice.load(VOZ)
    out["piper_carga_ms"] = ms(t0)
    medir_tts(voz, out)
    medir_stt(voz, out)
    json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
