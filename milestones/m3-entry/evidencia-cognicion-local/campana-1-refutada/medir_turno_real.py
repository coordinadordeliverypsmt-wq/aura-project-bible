#!/usr/bin/env python3
"""Mide un turno cognitivo REAL contra Ollama y descompone el tiempo.

No estima: usa las metricas que devuelve la propia API de Ollama
(load_duration, prompt_eval_*, eval_*), que vienen en nanosegundos.

Uso:
    python3 medir_turno_real.py <etiqueta> [ruta_json_salida]

Construye el prompt con las funciones REALES del producto para que lo medido
sea lo que AURA envia, no una aproximacion.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

RAIZ = "/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry/walking-skeleton"
sys.path.insert(0, RAIZ)

from aura_skeleton.modules.providers_real import (  # noqa: E402
    _ESQUEMA_COGNITIVO,
    _SYSTEM_COGNITIVO,
)

HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
MODELO = os.environ.get("AURA_MODELO", "qwen2.5:0.5b")

# Las tres preguntas son de CONOCIMIENTO GENERAL DEL MUNDO: caen en modo
# cognitivo, que es el turno que la inversion quiere acelerar.
CASOS = [
    ("cielo", "por que el cielo es azul?"),
    ("caja", "cuantos litros caben en una caja de 2x3x4 metros?"),
    ("hola", "hola"),
]


def prompt_de(texto: str) -> str:
    """Reproduce el ensamblado de orchestrator.py sin arrancar el sistema.

    Memoria y buffer vacios: es el caso de una pregunta del mundo en una
    conversacion recien empezada, el mas favorable para la ingesta.
    """
    ctx = "(sin recuerdos relevantes)"
    recent = "(inicio de la conversacion)"
    return f"[contexto memoria: {ctx}]\n[conversacion reciente:\n{recent}]\nUsuario: {texto}"


def medir(texto: str, opciones: dict | None, keep_alive: str | None) -> dict:
    cuerpo: dict = {
        "model": MODELO,
        "prompt": prompt_de(texto),
        "system": _SYSTEM_COGNITIVO,
        "stream": False,
        "format": _ESQUEMA_COGNITIVO,
    }
    if opciones:
        cuerpo["options"] = opciones
    if keep_alive is not None:
        cuerpo["keep_alive"] = keep_alive

    datos = json.dumps(cuerpo).encode()
    pet = urllib.request.Request(
        f"http://{HOST}/api/generate",
        data=datos,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(pet, timeout=900) as r:
        crudo = json.loads(r.read())
    reloj = time.monotonic() - t0

    ns = 1_000_000_000
    carga = crudo.get("load_duration", 0) / ns
    ing_tok = crudo.get("prompt_eval_count", 0)
    ing_s = crudo.get("prompt_eval_duration", 0) / ns
    gen_tok = crudo.get("eval_count", 0)
    gen_s = crudo.get("eval_duration", 0) / ns
    total = crudo.get("total_duration", 0) / ns

    return {
        "reloj_s": round(reloj, 2),
        "total_s": round(total, 2),
        "carga_modelo_s": round(carga, 2),
        "ingesta_tokens": ing_tok,
        "ingesta_s": round(ing_s, 2),
        "ingesta_tok_s": round(ing_tok / ing_s, 2) if ing_s else None,
        "generacion_tokens": gen_tok,
        "generacion_s": round(gen_s, 2),
        "generacion_tok_s": round(gen_tok / gen_s, 2) if gen_s else None,
        "pct_generacion": round(100 * gen_s / total, 1) if total else None,
        "respuesta": crudo.get("response", "")[:400],
        "motivo_fin": crudo.get("done_reason"),
    }


def main() -> int:
    etiqueta = sys.argv[1] if len(sys.argv) > 1 else "sin-etiqueta"
    salida = sys.argv[2] if len(sys.argv) > 2 else None

    # Variante configurable por entorno para medir el DESPUES sin tocar el codigo.
    opciones = json.loads(os.environ["MEDIR_OPTIONS"]) if os.environ.get("MEDIR_OPTIONS") else None
    keep_alive = os.environ.get("MEDIR_KEEP_ALIVE") or None

    # Un caso por ejecucion: en HC-1 (3,6 GiB) el servidor del modelo son ~500 MB residentes y medir
    # los tres seguidos agota la memoria. Medir de uno en uno es ademas lo que pide CLAUDE.md.
    solo = os.environ.get("MEDIR_CASO")
    casos = [c for c in CASOS if not solo or c[0] == solo]

    print(f"== {etiqueta} == modelo={MODELO} options={opciones} keep_alive={keep_alive}", flush=True)
    resultados = []
    for nombre, texto in casos:
        print(f"-- caso {nombre}: {texto!r}", flush=True)
        r = medir(texto, opciones, keep_alive)
        r["caso"] = nombre
        resultados.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)

    informe = {"etiqueta": etiqueta, "modelo": MODELO, "options": opciones,
               "keep_alive": keep_alive, "casos": resultados}
    if salida:
        with open(salida, "w") as f:
            json.dump(informe, f, ensure_ascii=False, indent=2)
        print(f"escrito: {salida}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
