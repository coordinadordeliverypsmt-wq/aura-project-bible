import json, statistics as st, sys
sys.path.insert(0, sys.path[0]); from espeak_tts import Espeak
e = Espeak(); FR = ["Sí.", "Te llamas Mauricio.", "Tienes dos recordatorios para hoy."]; out = {"sr": e.sr, "frases": {}}
for f in FR:
    rs = [e.synth(f) for _ in range(11)][1:]
    out["frases"][f] = {"audio_s": round(len(rs[0][0]) / 2 / e.sr, 2), "p50_primer_audio_ms": round(st.median(r[1] for r in rs), 1),
                        "p50_total_ms": round(st.median(r[2] for r in rs), 1), "p95_total_ms": round(sorted(r[2] for r in rs)[9], 1)}
print(json.dumps(out, ensure_ascii=False))
