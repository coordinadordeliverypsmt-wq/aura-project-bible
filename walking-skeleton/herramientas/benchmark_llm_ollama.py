"""Benchmark del LLM local por la API de Ollama (herramienta de DESARROLLO, no runtime; no cambia el modelo de AURA).

Mide por modelo: carga en frío (descarga explícita antes con keep_alive=0), carga en caliente, ingesta del prompt,
tokens/s de generación, tiempo total, RAM del runner (ps) y la respuesta (para juzgar calidad). Las frases son las
del flujo real de AURA. Uso: python3 -m herramientas.benchmark_llm_ollama SALIDA.json modelo [modelo...]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

URL = "http://127.0.0.1:11434"
SISTEMA = (
    "Eres AURA, un asistente doméstico local. Responde en español, en una o dos frases, sin inventar datos. "
    "Si te piden actuar sobre un dispositivo, NO digas que lo hiciste: solo el sistema ejecuta acciones."
)
FRASES = [
    "enciende la televisión",
    "apaga la televisión",
    "sí",
    "no",
    "¿qué hiciste?",
    "enciende la televisión de la sala",
    "¿cuál es la capital de Francia y por qué es importante?",
]


def _post(ruta: str, cuerpo: dict, tope: float = 900.0) -> dict:
    pet = urllib.request.Request(
        URL + ruta, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pet, timeout=tope) as r:
        return json.load(r)


def _rss_runner_mb() -> int:
    salida = subprocess.run(["ps", "-eo", "rss,args"], capture_output=True, text=True).stdout
    return (
        sum(int(fila.split()[0]) for fila in salida.splitlines()[1:] if "ollama" in fila and "runner" in fila) // 1024
    )


def medir(modelo: str) -> dict:
    _post("/api/generate", {"model": modelo, "keep_alive": 0})  # descarga: la primera llamada mide el frío
    time.sleep(2)
    filas = []
    for i, frase in enumerate(FRASES):
        t0 = time.perf_counter()
        r = _post(
            "/api/generate",
            {
                "model": modelo,
                "system": SISTEMA,
                "prompt": frase,
                "stream": False,
                "options": {"temperature": 0},
                "keep_alive": "10m",
            },
        )
        filas.append(
            {
                "frase": frase,
                "frio": i == 0,
                "total_s": round(time.perf_counter() - t0, 2),
                "carga_s": round(r.get("load_duration", 0) / 1e9, 2),
                "ingesta_tok": r.get("prompt_eval_count"),
                "ingesta_tok_s": round(
                    r.get("prompt_eval_count", 0) / max(r.get("prompt_eval_duration", 1) / 1e9, 1e-9), 1
                ),
                "gen_tok": r.get("eval_count"),
                "gen_tok_s": round(r.get("eval_count", 0) / max(r.get("eval_duration", 1) / 1e9, 1e-9), 2),
                "respuesta": r.get("response", "").strip()[:240],
            }
        )
        print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
    return {"modelo": modelo, "rss_runner_mb": _rss_runner_mb(), "filas": filas}


def main() -> None:
    salida, modelos = sys.argv[1], sys.argv[2:]
    disp = subprocess.run(["grep", "MemAvailable", "/proc/meminfo"], capture_output=True, text=True).stdout.split()[1]
    datos = {
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ram_disponible_mb_inicio": int(disp) // 1024,
        "resultados": [medir(m) for m in modelos],
    }
    json.dump(datos, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
