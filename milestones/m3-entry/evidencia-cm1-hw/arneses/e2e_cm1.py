"""E2E FÍSICO CM1 [EJEC]: persona (altavoz) -> aire -> micrófono -> AURA real (proceso) -> altavoz -> aire.

Cronómetro (Bible 2.5 §5.1): FIN DE HABLA -> INICIO DE RESPUESTA HABLADA, medido sobre UN solo reloj:
el flujo del micrófono de un OBSERVADOR independiente (parecord propio, 10 ms por trama). Ambos extremos
se ven en la misma señal física, así que los retardos del camino acústico se cancelan.

Privacidad: el observador guarda SOLO la energía RMS por trama (nunca audio). La voz de la «persona» es
sintética (Piper), vive en un directorio privado temporal y se borra al terminar. AURA usa AURA_DATOS
temporal: ~/.aura no se toca.

Uso: python3 e2e_cm1.py <rapido|base> <n_turnos> <salida.json>
"""
import json, os, queue, shutil, subprocess, sys, tempfile, threading, time, wave
import numpy as np

# Portátil para medir en hardware candidato (vía 3): rutas por entorno, HC-1 por defecto.
WS = os.environ.get("AURA_WS", "/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry/walking-skeleton")
USB = os.environ.get("AURA_USB", "/media/majo1230/AURORA_EXT")
VOZ_PERSONA = f"{USB}/piper_voices/es_MX-ald-medium.onnx"
MODO, N, SALIDA = (sys.argv[1], int(sys.argv[2]), sys.argv[3]) if len(sys.argv) > 3 else ("rapido", 0, "")
# (frase, lo que la RESPUESTA debe contener | None, lo que AURA debe OÍR)
TURNOS = [("Me llamo Mauricio.", None, "mauricio"), ("¿Cómo me llamo?", "mauricio", "llamo"),
          ("Mi color favorito es el verde.", None, "verde"), ("¿Cuál es mi color favorito?", "verde", "color")]
if os.environ.get("E2E_TURNOS") == "preguntas":
    # Caso MÁS FAVORABLE: solo preguntas de la gramática del Core. La respuesta correcta sin hechos
    # previos es la ausencia honesta, así que aquí se mide latencia y audición, no el contenido.
    TURNOS = [("¿Cómo me llamo?", None, "llamo"), ("¿Cuál es mi color favorito?", None, "color")]
ESPERA_ACUSE_S = float(os.environ.get("E2E_ESPERA_ACUSE", "1.3"))
TRAMA = 320  # 10 ms a 16 kHz s16le
ESPERA = threading.Event()  # nunca se activa: .wait(s) es una pausa bloqueante
T_RESP_S = 20 if MODO == "rapido" else 90


class Observador(threading.Thread):
    """Micrófono independiente: solo RMS por trama y el instante de lectura de cada trama."""
    def __init__(self):
        super().__init__(daemon=True)
        self.rms, self.t = [], []
        self.p = subprocess.Popen(["parecord", "--raw", "--channels=1", "--rate=16000", "--format=s16le",
                                   "--latency-msec=20"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    def run(self):
        while True:
            b = self.p.stdout.read(TRAMA)
            if len(b) < TRAMA:
                return
            x = np.frombuffer(b, np.int16).astype(np.float32)
            self.rms.append(float(np.sqrt(np.mean(x * x)))); self.t.append(time.perf_counter())
    def cerrar(self):
        self.p.terminate()


class Aura:
    def __init__(self, datos):
        env = dict(os.environ, AURA_DATOS=datos, AURA_STACK_REAL="1", AURA_PIPER_VOICE=VOZ_PERSONA,
                   AURA_VOSK_MODEL=f"{USB}/vosk-model-small-es-0.42", HF_HUB_CACHE=f"{USB}/hf_cache/hub",
                   HF_HUB_OFFLINE="1", PYTHONUNBUFFERED="1")
        env.pop("AURA_TTS_MOTOR", None); env.pop("AURA_ORDEN_VOSK", None)
        if MODO == "rapido":
            env.update(AURA_TTS_MOTOR="espeak", AURA_ORDEN_VOSK="1")
        self.p = subprocess.Popen([sys.executable, "-u", "-m", "aura_skeleton", "--escuchar", "--continuo"],
                                  cwd=WS, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.q = queue.Queue(); self.log = []
        threading.Thread(target=self._leer, daemon=True).start()
    def _leer(self):
        for linea in self.p.stdout:
            linea = linea.rstrip("\n"); self.log.append(linea); self.q.put((time.perf_counter(), linea))
    def esperar(self, pred, timeout):
        fin = time.perf_counter() + timeout
        while time.perf_counter() < fin:
            try:
                t, l = self.q.get(timeout=max(0.01, fin - time.perf_counter()))
            except queue.Empty:
                break
            if pred(l):
                return t, l
        return None, None
    def cerrar(self):
        self.p.terminate()
        try: self.p.wait(5)
        except subprocess.TimeoutExpired: self.p.kill()


def sintetizar_persona(textos, d):
    from piper import PiperVoice
    v = PiperVoice.load(VOZ_PERSONA); rutas = {}
    for i, txt in enumerate(textos):
        r = os.path.join(d, f"p{i}.wav")
        with wave.open(r, "wb") as w: v.synthesize_wav(txt, w)
        with wave.open(r) as w: rutas[txt] = (r, w.getnframes() / w.getframerate())
    return rutas


def reproducir(ruta):
    return subprocess.Popen(["paplay", "--latency-msec=30", ruta])


def medir(obs, t_lanz, dur_s, t_say, t_fin_persona=None):
    """Fin de habla de la persona y primer sonido de la respuesta, en tramas del observador."""
    t = obs.t; i0 = next((i for i, x in enumerate(t) if x >= t_lanz), None)
    if i0 is None or i0 < 50:
        return {"valido": False, "motivo": "sin tramas"}
    ruido = float(np.median(obs.rms[i0 - 40:i0])); umbral = max(5 * ruido, 300.0)
    # La ventana de la persona se cierra cuando su `paplay` TERMINÓ (espera a vaciar el audio) + 250 ms.
    # Con «lanzamiento + duración» el arranque lento de paplay bajo carga (hasta ~600 ms) dejaba a la
    # persona hablando fuera de la ventana y su continuación se tomaba por la respuesta.
    if t_fin_persona is not None:
        fin_ventana = next((i for i, x in enumerate(t) if x >= t_fin_persona + 0.25), len(t))
    else:
        fin_ventana = i0 + int(dur_s * 100) + 20
    altos = [i for i in range(i0, min(fin_ventana, len(obs.rms))) if obs.rms[i] >= umbral]
    if not altos:
        return {"valido": False, "motivo": "persona no oída por el observador", "ruido": ruido}
    fin_habla = altos[-1]
    # La respuesta (espeak) llega más baja que la persona: umbral de inicio propio, más sensible.
    umbral_resp = max(2.5 * ruido, 250.0)
    for j in range(fin_habla + 6, len(obs.rms) - 3):
        if all(obs.rms[k] >= umbral_resp for k in range(j, j + 3)):
            lat = (j - fin_habla) * 10
            # Control: el sonido detectado tiene que ser POSTERIOR a que AURA publique su respuesta.
            # Y AURA no puede haber contestado ANTES de que la persona terminara: eso es interrumpir
            # (corte prematuro del fin de habla), no una latencia buena.
            interrumpe = t_say is not None and t_say < obs.t[fin_habla]
            ok = t_say is not None and obs.t[j] >= t_say - 0.05 and not interrumpe
            desglose = {"fin_habla_a_texto_ms": round((t_say - obs.t[fin_habla]) * 1000) if t_say else None,
                        "texto_a_sonido_ms": round((obs.t[j] - t_say) * 1000) if t_say else None}
            return {"valido": ok, "lat_ms": lat, **desglose, "ruido": round(ruido), "umbral": round(umbral),
                    "motivo": "" if ok else ("AURA contestó antes de que terminara la persona (corte prematuro)" if interrumpe
                                             else "el sonido precede a la respuesta de AURA: no es la respuesta")}
    return {"valido": False, "motivo": "no se detectó respuesta", "ruido": ruido}


def main():
    priv = tempfile.mkdtemp(prefix="cm1-persona-"); os.chmod(priv, 0o700)
    datos = tempfile.mkdtemp(prefix="cm1-datos-")
    vol = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, text=True).stdout
    vol_orig = next((w for w in vol.split() if w.endswith("%")), None)
    resultados = []; aura = obs = None
    try:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "85%"])
        persona = sintetizar_persona(["Oye Aurora."] + [t for t, _, _ in TURNOS], priv)
        obs = Observador(); obs.start()
        aura = Aura(datos)
        t, _ = aura.esperar(lambda l: "AURA está atenta" in l, 240)
        if t is None:
            raise SystemExit("AURA no llegó a estar atenta:\n" + "\n".join(aura.log[-20:]))
        for n in range(N):
            texto, esperado, oir = TURNOS[n % len(TURNOS)]
            fila = {"n": n, "persona": texto}
            acuse = None
            for intento in range(3):
                reproducir(persona["Oye Aurora."][0]).wait()
                acuse, _ = aura.esperar(lambda l: l.startswith("AURA> ¿Sí?"), 6)
                if acuse: break
            if not acuse:
                fila.update(valido=False, motivo="la palabra de activación no despertó a AURA"); resultados.append(fila); continue
            # Dar tiempo a que suene el «¿Sí?» y AURA abra la escucha de la orden.
            ESPERA.wait(ESPERA_ACUSE_S)  # bloqueante: no roba CPU a AURA (2 núcleos)
            ruta, dur = persona[texto]
            t_lanz = time.perf_counter(); reproducir(ruta).wait(); t_fin_persona = time.perf_counter()
            # Las líneas de progreso («AURA> (consultando…)», «AURA> (sigo…)») NO son la respuesta.
            t_say, linea = aura.esperar(lambda l: l.startswith("AURA> ") and "¿Sí?" not in l
                                        and not l.startswith("AURA> ("), T_RESP_S)
            fila["aura_dijo"] = linea[6:] if linea else None
            fila["oido"] = next((l for l in reversed(aura.log) if l.startswith("tú (oído)>")), None)
            if t_say is None:
                fila.update(valido=False, motivo=f"sin respuesta en {T_RESP_S} s"); resultados.append(fila)
                aura.cerrar(); aura = Aura(datos); aura.esperar(lambda l: "AURA está atenta" in l, 240); continue
            ESPERA.wait(4.0)  # que termine de sonar la respuesta antes de medir y seguir
            fila.update(medir(obs, t_lanz, dur, t_say, t_fin_persona))
            fila["correcta"] = (esperado in (linea or "").lower()) if esperado else None
            fila["oyo_bien"] = oir in (fila.get("oido") or "").lower()
            resultados.append(fila); print(json.dumps(fila, ensure_ascii=False), flush=True)
    finally:
        if aura: aura.cerrar()
        if obs: obs.cerrar()
        if vol_orig: subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", vol_orig])
        shutil.rmtree(priv, ignore_errors=True); shutil.rmtree(datos, ignore_errors=True)
    lat = sorted(r["lat_ms"] for r in resultados if r.get("valido"))
    todos = [r.get("lat_ms") if r.get("valido") else float("inf") for r in resultados]
    resumen = {"modo": MODO, "turnos": len(resultados), "validos": len(lat),
               "p50_validos_ms": float(np.median(lat)) if lat else None,
               "p95_validos_ms": float(np.percentile(lat, 95)) if lat else None,
               "p50_todos_ms(fallo=inf)": float(np.median(todos)) if todos else None,
               "correctas": sum(1 for r in resultados if r.get("correcta")),
               "oyo_bien": sum(1 for r in resultados if r.get("oyo_bien")),
               "preguntas": sum(1 for r in resultados if r.get("correcta") is not None)}
    json.dump({"resumen": resumen, "turnos": resultados}, open(SALIDA, "w"), ensure_ascii=False, indent=1)
    print("RESUMEN", json.dumps(resumen, ensure_ascii=False))


def _a_interrupcion(signum, _frame):
    # SIGTERM/SIGINT -> KeyboardInterrupt: el `finally` de main() cierra AURA, el observador,
    # restaura el volumen y borra los temporales. Sin esto, SIGTERM mataba el arnés sin limpiar.
    raise KeyboardInterrupt(f"señal {signum}")


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGTERM, _a_interrupcion); signal.signal(signal.SIGINT, _a_interrupcion)
    signal.signal(signal.SIGALRM, _a_interrupcion); signal.alarm(1500)  # tope interno: sin `timeout` externo
    main()
