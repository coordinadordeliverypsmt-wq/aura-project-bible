import json, statistics as st, sys, time, resource
sys.path.insert(0, sys.path[0])
from piper import PiperVoice
from ov_session import OVSession
VOZ = "/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"
dev, prec, N = sys.argv[1], (sys.argv[2] if sys.argv[2] != "-" else None), int(sys.argv[3])
FRASES = ["Sí.", "Te llamas Mauricio.", "Tienes dos recordatorios para hoy."]
v = PiperVoice.load(VOZ)
s = OVSession(VOZ, dev, prec, cache_dir=sys.argv[4] if len(sys.argv) > 4 else None); v.session = s
out = {"device": dev, "precision": prec, "compile_ms": s.compile_ms, "inputs": s.inputs, "frases": {}}
for f in FRASES:
    ids = [v.phonemes_to_ids(p) for p in v.phonemize(f) if p]
    tiempos = []; dur = 0
    for i in range(N + 1):
        t = time.perf_counter(); auds = [v.phoneme_ids_to_audio(x) for x in ids]; tiempos.append((time.perf_counter() - t) * 1000)
        dur = sum(len(a) for a in auds) / v.config.sample_rate
    est = sorted(tiempos[1:])
    out["frases"][f] = {"audio_s": round(dur, 2), "warmup_ms": round(tiempos[0], 1), "p50_ms": round(st.median(est), 1),
                        "p95_ms": round(est[int(0.95 * (len(est) - 1))], 1), "min_ms": round(est[0], 1)}
out["maxrss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
print(json.dumps(out, ensure_ascii=False))
