"""Sonda: latencia del turno determinista del orquestador con TTS espeak (monkeypatch SOLO en la sonda)."""
import asyncio, os, sys, tempfile, time, wave, statistics as st
D = tempfile.mkdtemp(prefix="aura-cm1-"); B = os.path.dirname(os.path.abspath(__file__))
os.environ.update(AURA_DATOS=D, AURA_STACK_REAL="1", AURA_PIPER_VOICE="/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx")
sys.path.insert(0, os.getcwd()); sys.path.insert(0, B)
from aura_skeleton.composicion import Configuracion, componer
from espeak_tts import Espeak
async def main():
    t = time.perf_counter(); orq = componer(Configuracion(datos=D)).orquestador; print(f"componer {1000*(time.perf_counter()-t):.0f} ms")
    e = Espeak(b"es", 175)
    def tts_sync(text, out):
        pcm, _, _ = e.synth(text)
        with wave.open(out, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(e.sr); w.writeframes(pcm)
    orq.voice._tts_sync = tts_sync
    async def turno(txt):
        tid = f"t{time.perf_counter_ns()}"; t = time.perf_counter()
        await orq.handle_utterance("u", txt, tid); await orq.wait(tid); r = orq._results[tid]
        ms = 1000*(time.perf_counter()-t)
        if r.get("audio"): os.remove(r["audio"])
        return ms, r
    for txt in ["Me llamo Mauricio y me gusta el color verde."]: print(await turno(txt))
    for txt in ["¿Cómo me llamo?", "¿Cuál es mi color favorito?", "¿Qué hora es?", "¿Qué día es hoy?", "¿Cuánto es tres por cuatro?"]:
        ms = [];
        for _ in range(4): m, r = await turno(txt); ms.append(m)
        print(f"{txt!r:32} p50={st.median(ms[1:]):7.1f} ms  prov={r['provider']} dom={r['dominio']} est={r['estatus']} say={r['say'][:60]!r} marks={ {k: round(v) for k, v in r['marks'].items()} }", flush=True)
asyncio.run(main())
