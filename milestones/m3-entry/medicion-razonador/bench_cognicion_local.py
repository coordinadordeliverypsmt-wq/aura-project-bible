"""Benchmark reproducible de la cognicion local de AURA en HC-1.

INSTRUMENTACION, NO PRODUCTO. Vive fuera del repositorio (`$CLAUDE_JOB_DIR/tmp/bench/`) y no modifica
ni una linea de `aura_skeleton`. Mide A TRAVES DEL PRODUCTO COMPLETO —orquestador, router, proveedor—
porque es el unico sitio donde el reparto del coste es el real.

Como obtiene las metricas: envuelve `urllib.request.urlopen`, registra el cuerpo ENVIADO (system,
prompt, format, options) y la respuesta COMPLETA de Ollama, que trae `prompt_eval_count`,
`prompt_eval_duration`, `eval_count`, `eval_duration`, `load_duration` y `total_duration`. Asi se
cuentan tambien las LLAMADAS por turno (duplicados incluidos) sin tocar el codigo medido.

Dos cosas que se neutralizan, ambas declaradas:
  * La VOZ. Con `AURA_STACK_REAL=1`, Piper se invoca sin modelo instalado y su error tumba el turno
    completo (DECISION 2, sin resolver por orden del CEO). Aqui se sustituye por un doble inerte para
    poder medir la cognicion; el producto NO se cambia.
  * El DIRECTORIO DE DATOS. `AURA_DATOS` apunta a un temporal: la memoria real del usuario no se toca.

Uso:
    python3 bench_cognicion.py --etiqueta base --casos cognitivos --repeticiones 1
    python3 bench_cognicion.py --etiqueta num_predict-120 --opciones '{"num_predict":120}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
import tempfile
import time
import uuid

RAIZ = "/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry/walking-skeleton"
sys.path.insert(0, RAIZ)

CASOS = {
    "conocimiento": "¿Cuál es la capital de Francia?",
    "matematica": "¿Cuánto es 17 por 23?",
    "razonamiento": "¿Por qué crees que dormir poco afecta al ánimo?",
    "conversacion": "¿Qué me recomiendas para dormir mejor?",
    "memoria_existente": "¿Cuál es mi color favorito?",
    "memoria_ausente": "¿Cuál es el nombre de mi abuela?",
}
COGNITIVOS = ["conocimiento", "matematica", "razonamiento", "conversacion"]
MEMORIA = ["memoria_existente", "memoria_ausente"]
SEMILLA = ("semantica", "Mi color favorito es el azul")


class _Respuesta:
    """Doble de la respuesta de urlopen: el cuerpo ya leido, servido otra vez al codigo medido."""

    def __init__(self, cuerpo: bytes) -> None:
        self._cuerpo = cuerpo

    def read(self, *_a) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def instalar_sonda(opciones: dict | None):
    """Envuelve urlopen. Devuelve la lista donde se acumulan las llamadas al modelo."""
    import urllib.request

    original = urllib.request.urlopen
    llamadas: list[dict] = []

    def _urlopen(req, timeout=None, **kw):
        destino = getattr(req, "full_url", str(req))
        if "/api/generate" not in destino:
            return original(req, timeout=timeout, **kw)

        cuerpo = json.loads(req.data.decode())
        if opciones:
            # EXPERIMENTO, identificado y reversible: los parametros se inyectan AQUI, en la
            # instrumentacion, nunca en el producto. Al terminar el proceso no queda nada.
            cuerpo.setdefault("options", {}).update(opciones)
            req.data = json.dumps(cuerpo).encode()

        t0 = time.monotonic()
        with original(req, timeout=timeout, **kw) as r:
            crudo = r.read()
        dt = time.monotonic() - t0
        resp = json.loads(crudo.decode())
        ns = 1_000_000_000
        llamadas.append({
            "s_medido": round(dt, 2),
            "formato": "esquema" if isinstance(cuerpo.get("format"), dict) else cuerpo.get("format"),
            "options_enviadas": cuerpo.get("options"),
            "car_system": len(cuerpo.get("system") or ""),
            "car_prompt": len(cuerpo.get("prompt") or ""),
            "tokens_prompt": resp.get("prompt_eval_count"),
            "tokens_generados": resp.get("eval_count"),
            "s_prefill": round((resp.get("prompt_eval_duration") or 0) / ns, 2),
            "s_generacion": round((resp.get("eval_duration") or 0) / ns, 2),
            "s_carga": round((resp.get("load_duration") or 0) / ns, 2),
            "s_total_ollama": round((resp.get("total_duration") or 0) / ns, 2),
            "motivo_fin": resp.get("done_reason"),
        })
        return _Respuesta(crudo)

    urllib.request.urlopen = _urlopen
    return llamadas


async def medir(args, salida: pathlib.Path) -> None:
    import aura_skeleton.adapters.voice_real as vr

    class VozNeutra:
        async def stt(self, audio_ref, trace_id):
            return audio_ref

        async def tts(self, text, trace_id):
            return ""

    vr.WhisperPiperVoice = lambda **kw: VozNeutra()

    from aura_skeleton.composicion import Configuracion, componer

    sistema = componer(Configuracion.desde_entorno())
    if args.sembrar:
        kind, contenido = SEMILLA
        await sistema.memoria.write("usuario", kind, contenido,
                                    {"fuente": "siembra de laboratorio", "bench": True})

    nombres = {"cognitivos": COGNITIVOS, "memoria": MEMORIA, "todos": COGNITIVOS + MEMORIA}[args.casos]
    with salida.open("a", encoding="utf-8") as fh:
        for rep in range(1, args.repeticiones + 1):
            for nombre in nombres:
                texto = CASOS[nombre]
                llamadas = instalar_sonda(json.loads(args.opciones) if args.opciones else None)
                tid = uuid.uuid4().hex[:12]
                t0 = time.monotonic()
                try:
                    await sistema.orquestador.handle_utterance("usuario", texto, tid)
                    res = await sistema.orquestador.wait(tid, timeout=1800)
                    fallo = None
                except Exception as e:  # noqa: BLE001
                    res, fallo = {}, f"{type(e).__name__}: {e}"
                fila = {
                    "etiqueta": args.etiqueta, "rep": rep, "caso": nombre, "entrada": texto,
                    "s_turno": round(time.monotonic() - t0, 1),
                    "proveedor": res.get("provider"), "dominio": res.get("dominio"),
                    "say": res.get("say"), "llamadas_al_modelo": len(llamadas),
                    "detalle": llamadas, "error": fallo,
                }
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"[{args.etiqueta}] r{rep} {nombre}: {fila['s_turno']}s "
                      f"prov={fila['proveedor']} llamadas={len(llamadas)}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--casos", default="todos", choices=["cognitivos", "memoria", "todos"])
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--opciones", default="")
    ap.add_argument("--sembrar", action="store_true", help="siembra el hecho de memoria_existente")
    ap.add_argument("--salida", default=str(pathlib.Path(__file__).parent / "resultados.jsonl"))
    args = ap.parse_args()

    os.environ["AURA_STACK_REAL"] = "1"
    os.environ["AURA_LLM_MODEL"] = os.environ.get("AURA_LLM_MODEL", "qwen2.5:0.5b")
    os.environ.setdefault("AURA_DATOS", tempfile.mkdtemp(prefix="aura-bench-"))
    print(f"datos={os.environ['AURA_DATOS']} modelo={os.environ['AURA_LLM_MODEL']} "
          f"opciones={args.opciones or '(ninguna)'}", flush=True)
    asyncio.run(medir(args, pathlib.Path(args.salida)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
