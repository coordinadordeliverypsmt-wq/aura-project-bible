"""Bench Piper por etapa: phonemize / ids / inferencia / wav. Solo métricas, no guarda audio."""
import io, json, statistics as st, sys, time, wave, resource
from piper import PiperVoice
VOZ = sys.argv[1] if len(sys.argv) > 1 else "/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
FRASES = ["Sí.", "Te llamas Mauricio.", "Tienes dos recordatorios para hoy."]
def ms(t): return round((time.perf_counter() - t) * 1000, 1)
t = time.perf_counter(); v = PiperVoice.load(VOZ); carga = ms(t)
out = {"voz": VOZ.rsplit('/',1)[-1], "carga_ms": carga, "frases": {}}
for f in FRASES:
    fil = []
    for i in range(N + 1):
        t0 = time.perf_counter(); ph = v.phonemize(f); t_ph = ms(t0)
        t1 = time.perf_counter(); ids = [v.phonemes_to_ids(p) for p in ph if p]; t_id = ms(t1)
        t2 = time.perf_counter(); auds = [v.phoneme_ids_to_audio(x) for x in ids]; t_inf = ms(t2)
        t3 = time.perf_counter(); buf = io.BytesIO()
        with wave.open(buf, "wb") as w: v.synthesize_wav(f, w)
        t_wav = ms(t3)
        dur = sum(len(a) for a in auds) / v.config.sample_rate
        fil.append((t_ph, t_id, t_inf, t_wav, dur))
    warm, est = fil[0], fil[1:]
    out["frases"][f] = {"chars": len(f), "audio_s": round(est[0][4], 2), "warmup_inf_ms": warm[2],
        "p50_phonemize_ms": st.median(x[0] for x in est), "p50_inferencia_ms": st.median(x[2] for x in est),
        "p95_inferencia_ms": sorted(x[2] for x in est)[int(0.95 * (len(est) - 1))],
        "p50_synthesize_wav_ms": st.median(x[3] for x in est), "rtf_p50": round(st.median(x[2] for x in est) / 1000 / est[0][4], 2)}
out["maxrss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
print(json.dumps(out, ensure_ascii=False, indent=1))
