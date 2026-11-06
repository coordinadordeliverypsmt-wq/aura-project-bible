"""E2E FÍSICO voz→acción (DP-VOZ-ACCION opción C): voz humana real → AURA real → Motor Único → HA real → TV real.

Herramienta de DESARROLLO, no runtime. Lanza AURA en escucha continua con el stack real (Whisper, Piper, Vosk,
Home Assistant) y AURA_DATOS temporal (no toca ~/.aura). Mientras una persona habla, registra:
  - cada línea que AURA imprime (oído / respuesta), con marca de tiempo;
  - el estado de la TV de la sala leído DIRECTAMENTE de la API de HA (fuera de AURA), con marca de tiempo.
No guarda audio. El token de HA se lee del fichero de secretos y nunca se imprime.

Uso:  python3 arnes_e2e_voz_accion.py SALIDA.jsonl [segundos]
"""

import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ENTIDAD = "media_player.tv_sala_fmilia_medina_un43ru7100fxza"
USB = f"/media/{os.environ.get('USER', 'majo1230')}/AURORA_EXT"
WS = pathlib.Path(__file__).resolve().parents[3] / "walking-skeleton"
TOKEN = pathlib.Path("~/aura-hogar/secretos/ha_token").expanduser().read_text().strip()
salida = open(sys.argv[1], "a", encoding="utf-8")
duracion = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
cerrojo = threading.Lock()
fin = threading.Event()


def anotar(tipo: str, dato: str) -> None:
    with cerrojo:
        salida.write(json.dumps({"t": round(time.time(), 3), "tipo": tipo, "dato": dato}, ensure_ascii=False) + "\n")
        salida.flush()
    print(f"[{time.strftime('%H:%M:%S')}] {tipo}: {dato}", flush=True)


def estado_tv() -> str:
    pet = urllib.request.Request(f"http://127.0.0.1:8123/api/states/{ENTIDAD}", headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(pet, timeout=5) as r:
            return json.load(r)["state"]
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}"


def ram_disponible_mb() -> int:
    for linea in open("/proc/meminfo"):
        if linea.startswith("MemAvailable:"):
            return int(linea.split()[1]) // 1024
    return -1


def vigilar_ram() -> None:
    while not fin.is_set():
        anotar("ram_disponible_mb", str(ram_disponible_mb()))
        fin.wait(5.0)


def vigilar_tv() -> None:
    previo = None
    while not fin.is_set():
        e = estado_tv()
        if e != previo:
            anotar("tv", e)
            previo = e
        fin.wait(0.5)


entorno = dict(os.environ)
entorno.update({
    "AURA_STACK_REAL": "1", "AURA_LLM_MODEL": entorno.get("AURA_LLM_MODEL", "qwen2.5:0.5b"),
    "AURA_PIPER_VOICE": f"{USB}/piper_voices/es_MX-ald-medium.onnx", "HF_HUB_CACHE": f"{USB}/hf_cache/hub",
    "HF_HUB_OFFLINE": "1", "AURA_VOSK_MODEL": f"{USB}/vosk-model-small-es-0.42",
    "AURA_HA_URL": "http://127.0.0.1:8123", "AURA_HA_TOKEN": TOKEN,
    "AURA_DATOS": tempfile.mkdtemp(prefix="aura-e2e-voz-"), "PYTHONUNBUFFERED": "1",
})
subprocess.run(["pactl", "set-source-volume", "@DEFAULT_SOURCE@", os.environ.get("AURA_GANANCIA_MICRO", "27%")])
ganancia = subprocess.run(["pactl", "get-source-volume", "@DEFAULT_SOURCE@"], capture_output=True, text=True).stdout
anotar("ganancia_micro", ganancia.split(",")[0].strip())
anotar("inicio", f"entidad={ENTIDAD} estado_inicial={estado_tv()} datos={entorno['AURA_DATOS']}")
aura = subprocess.Popen([sys.executable, "-m", "aura_skeleton", "--escuchar", "--continuo", "--telemetria"], cwd=WS, env=entorno,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
threading.Thread(target=vigilar_tv, daemon=True).start()
threading.Thread(target=vigilar_ram, daemon=True).start()


def leer() -> None:
    for linea in aura.stdout:
        linea = linea.rstrip()
        if linea and "TOKEN" not in linea.upper():
            anotar("aura", linea)


threading.Thread(target=leer, daemon=True).start()
signal.signal(signal.SIGTERM, lambda *_: fin.set())
signal.signal(signal.SIGINT, lambda *_: fin.set())
fin.wait(duracion)
fin.set()
aura.terminate()
try:
    aura.wait(timeout=15)
except subprocess.TimeoutExpired:
    aura.kill()
anotar("fin", f"estado_final={estado_tv()}")
