"""Sonda: segmento captura+VAD+decodificación de la vía rápida, por el aire, con el código de producto."""
import json, os, sys, tempfile, shutil, subprocess, threading, time, wave
sys.path.insert(0, "/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry/walking-skeleton")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e_cm1 as E
from aura_skeleton.adapters import escucha
FRASES = ["¿Cuál es mi color favorito?", "Me llamo Mauricio.", "¿Cómo me llamo?"]
def main():
    priv = tempfile.mkdtemp(prefix="cm1-persona-"); os.chmod(priv, 0o700)
    vol = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, text=True).stdout
    vol_orig = next((w for w in vol.split() if w.endswith("%")), None); obs = None
    try:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "85%"])
        persona = E.sintetizar_persona(FRASES, priv)
        oido = escucha.OidoContinuo(modelo=f"{E.USB}/vosk-model-small-es-0.42"); oido.preparar()
        obs = E.Observador(); obs.start(); W = threading.Event(); W.wait(1.5)
        # Instrumentar FinalResult sin tocar el producto: envolver el reconocedor libre.
        orig = oido._reconocedor
        for hang in (300, 450):
            for f in FRASES:
                for rep in range(2):
                    res = {}
                    def hilo():
                        t = time.perf_counter(); res["texto"] = oido.escuchar_orden(fin_de_habla_ms=hang); res["t_fin"] = time.perf_counter(); res["dur"] = res["t_fin"] - t
                    th = threading.Thread(target=hilo); th.start(); W.wait(0.5)
                    ruta, dur = persona[f]; t_l = time.perf_counter(); E.reproducir(ruta).wait(); th.join(15)
                    i0 = next(i for i, x in enumerate(obs.t) if x >= t_l); base = sorted(obs.rms[max(0, i0-40):i0]) or [300.0]; ruido = base[len(base)//2]; umbral = max(5*ruido, 300)
                    altos = [i for i in range(i0, min(i0 + int(dur*100) + 20, len(obs.rms))) if obs.rms[i] >= umbral]
                    fin = obs.t[altos[-1]] if altos else None
                    print(json.dumps({"hang": hang, "frase": f, "oyo": res.get("texto"), "fin_persona_a_retorno_ms": round((res["t_fin"] - fin) * 1000) if fin and "t_fin" in res else None}, ensure_ascii=False), flush=True)
                    W.wait(1.0)
    finally:
        if obs: obs.cerrar()
        if vol_orig: subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", vol_orig])
        shutil.rmtree(priv, ignore_errors=True)
main()
