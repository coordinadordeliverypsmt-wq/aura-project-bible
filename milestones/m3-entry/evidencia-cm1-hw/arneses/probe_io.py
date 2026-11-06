"""Latencia E/S por el aire: lanzar paplay(tono) -> primera muestra con energía leída del micrófono."""
import numpy as np, subprocess, time, wave, os, sys, statistics as st
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tono.wav")
sr = 22050; t = np.arange(int(0.25 * sr)) / sr
with wave.open(T, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.sin(2*np.pi*1000*t)*12000).astype(np.int16).tobytes())
def medir(lat_play, lat_rec, n=6):
    rec = subprocess.Popen(["parecord", "--raw", "--channels=1", "--rate=16000", "--format=s16le"] + ([f"--latency-msec={lat_rec}"] if lat_rec else []), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    res = []
    try:
        for _ in range(40): rec.stdout.read(320)  # asentar (~0.4 s)
        for i in range(n):
            base = []
            for _ in range(25): base.append(np.sqrt(np.mean(np.frombuffer(rec.stdout.read(320), np.int16).astype(np.float32)**2)))
            thr = max(np.median(base) * 6, 400)
            t0 = time.perf_counter(); p = subprocess.Popen(["paplay"] + ([f"--latency-msec={lat_play}"] if lat_play else []) + [T])
            while True:
                x = np.frombuffer(rec.stdout.read(320), np.int16).astype(np.float32)
                if np.sqrt(np.mean(x**2)) > thr: res.append((time.perf_counter() - t0) * 1000); break
                if time.perf_counter() - t0 > 3: res.append(None); break
            p.wait()
            for _ in range(30): rec.stdout.read(320)
    finally: rec.terminate()
    ok = [r for r in res if r is not None]
    return f"play={lat_play} rec={lat_rec}: p50={st.median(ok):.0f} ms min={min(ok):.0f} max={max(ok):.0f} ({len(ok)}/{n})" if ok else f"play={lat_play} rec={lat_rec}: sin detección"
for cfg in [(None, None), (None, 20), (30, 20)]: print(medir(*cfg), flush=True)
os.remove(T)
