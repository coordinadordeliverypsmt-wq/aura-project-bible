"""Comparación de razonadores — réplica del prompt exacto en ambos modelos.

Instrumentación, no producto. Aislada del producto **por construcción**: no compone AURA, no invoca
al motor, no toca el disco del repositorio. Sólo lee `_SYSTEM` y el catálogo para (a) reproducir el
prompt byte a byte y (b) validar la respuesta LEYENDO.

POR QUE UNA REPLICA Y NO EL PRODUCTO. `qwen2.5:3b` no puede ejecutarse dentro del producto en esta
maquina: tres intentos, tres modos de fallo, todos compatibles con presion de memoria. Comparar su
resultado obtenido de una forma contra el del `0.5b` obtenido de otra no seria una comparacion.
Reenviando el prompto capturado, ambos modelos reciben LOS MISMOS BYTES y difieren solo en el modelo.

EL CALENTAMIENTO NO LLEVA `system`, A PROPOSITO. Ollama cachea prefijos de prompt; si el calentamiento
compartiera el prompt de sistema, la medicion real heredaria ese prefijo cacheado y no seria
comparable con los humos. Se calienta con un prompt trivial y sin `system`.
"""

from __future__ import annotations

import datetime as _dt
import glob
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
URL = "http://127.0.0.1:11434/api/generate"

# CORRECCION INSTRUMENTAL (2026-08-15, defecto de secuenciacion). La primera tanda ejecuto los dos
# modelos en el mismo proceso y en orden: `0.5b` consumio el margen de memoria y `3b` fue abandonado
# en su puerta con 1.103 MB, cuando al empezar habia 1.727 MB. El abandono NO fue del entorno: fue del
# orden. Ahora los modelos se eligen por argumento, de modo que una medicion no puede quedar
# condicionada por la anterior.
#
# Es un cambio del INSTRUMENTO. No toca prompt, catalogo, umbrales, protocolo ni producto.
MODELOS_POR_DEFECTO = ["qwen2.5:0.5b", "qwen2.5:3b"]
TIMEOUT_S = 1800

# Umbrales declarados en el DP §11, ANTES de ejecutar.
MIN_RAM_ANTES_MB = 1400
MIN_SWAP_LIBRE_MB = 600
MIN_RAM_TRAS_CARGA_MB = 150

REQUERIDOS = ("fichero", "buscar", "sustituir")


def _mem() -> dict:
    d = {}
    for linea in pathlib.Path("/proc/meminfo").read_text().splitlines():
        k, _, resto = linea.partition(":")
        if k in ("MemFree", "MemAvailable", "SwapFree", "SwapTotal"):
            d[k] = int(resto.strip().split()[0]) // 1024
    d["load1"] = os.getloadavg()[0]
    return d


def _post(cuerpo: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — endpoint local (D24)
        return json.load(r)


def main() -> int:
    modelos = sys.argv[1:] or MODELOS_POR_DEFECTO
    sys.path.insert(0, str(RAIZ / "walking-skeleton"))
    from aura_skeleton.core.permissions import CATALOGO
    from aura_skeleton.modules.providers_real import _SYSTEM

    # El prompt de usuario, LITERAL, tal como el producto lo envió en el humo ya ejecutado.
    ev_previa = max(glob.glob(str(AQUI / "evidencia-humo-2026*.json")), key=os.path.getmtime)
    previa = json.load(open(ev_previa, encoding="utf-8"))
    prompt_usuario = previa["evidencia"]["llamadas_al_modelo"][0]["prompt_enviado"]
    contexto = previa["evidencia"]["args_literales_de_la_derivada"]

    informe = {
        "instante": _dt.datetime.now().isoformat(timespec="seconds"),
        "origen_del_prompt": os.path.basename(ev_previa),
        "prompt_usuario_sha256": hashlib.sha256(prompt_usuario.encode()).hexdigest(),
        "system_sha256": hashlib.sha256(_SYSTEM.encode()).hexdigest(),
        "prompt_completo_sha256": hashlib.sha256((_SYSTEM + prompt_usuario).encode()).hexdigest(),
        "contexto_sha256": hashlib.sha256(
            json.dumps(contexto, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "contexto": contexto,
        "timeout_s": TIMEOUT_S,
        "umbrales": {
            "ram_antes_mb": MIN_RAM_ANTES_MB,
            "swap_libre_mb": MIN_SWAP_LIBRE_MB,
            "ram_tras_carga_mb": MIN_RAM_TRAS_CARGA_MB,
        },
        "resultados": {},
    }

    informe["modelos_de_esta_tanda"] = modelos

    for modelo in modelos:
        r: dict = {"modelo": modelo}
        r["mem_antes"] = _mem()

        # --- Umbral 1: no se inicia sin margen ---
        if r["mem_antes"]["MemAvailable"] < MIN_RAM_ANTES_MB or r["mem_antes"]["SwapFree"] < MIN_SWAP_LIBRE_MB:
            r["abandono"] = (
                f"umbral previo: disponible {r['mem_antes']['MemAvailable']} MB "
                f"(min {MIN_RAM_ANTES_MB}) / swap libre {r['mem_antes']['SwapFree']} MB (min {MIN_SWAP_LIBRE_MB})"
            )
            informe["resultados"][modelo] = r
            continue

        # --- Carga, SIN `system` para no cachear el prefijo real ---
        t0 = time.monotonic()
        try:
            calienta = _post(
                {"model": modelo, "prompt": "ok", "stream": False, "keep_alive": "20m",
                 "options": {"num_predict": 1}},
                TIMEOUT_S,
            )
            r["carga_s"] = round(calienta.get("load_duration", 0) / 1e9, 2)
            r["calentamiento_s"] = round(time.monotonic() - t0, 2)
        except Exception as exc:  # noqa: BLE001 — el modo de fallo ES un dato
            r["abandono"] = f"fallo al cargar: {type(exc).__name__}: {exc}"
            r["mem_despues"] = _mem()
            informe["resultados"][modelo] = r
            continue

        r["mem_tras_carga"] = _mem()

        # --- Umbral 2: cargado pero sin margen para el contexto ---
        if r["mem_tras_carga"]["MemAvailable"] < MIN_RAM_TRAS_CARGA_MB:
            r["abandono"] = (
                f"umbral tras carga: disponible {r['mem_tras_carga']['MemAvailable']} MB "
                f"(min {MIN_RAM_TRAS_CARGA_MB}); no se envia el prompt"
            )
            subprocess.run(["ollama", "stop", modelo], capture_output=True)
            r["mem_despues"] = _mem()
            informe["resultados"][modelo] = r
            continue

        # --- La medicion: mismos bytes para los dos modelos ---
        t0 = time.monotonic()
        try:
            resp = _post(
                {"model": modelo, "prompt": prompt_usuario, "system": _SYSTEM,
                 "stream": False, "format": "json"},
                TIMEOUT_S,
            )
            r["error"] = None
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"
            resp = {}
        r["latencia_pared_s"] = round(time.monotonic() - t0, 2)
        r["mem_despues"] = _mem()

        if resp:
            ns = 1e9
            entrada, salida = resp.get("prompt_eval_count", 0), resp.get("eval_count", 0)
            t_in = resp.get("prompt_eval_duration", 0) / ns
            t_out = resp.get("eval_duration", 0) / ns
            r["tokens_entrada"] = entrada
            r["tokens_generados"] = salida
            r["ingesta_s"] = round(t_in, 2)
            r["generacion_s"] = round(t_out, 2)
            r["ingesta_tok_s"] = round(entrada / t_in, 2) if t_in else None
            r["generacion_tok_s"] = round(salida / t_out, 2) if t_out else None
            r["inferencia_total_s"] = round(resp.get("total_duration", 0) / ns, 2)
            r["carga_en_esta_llamada_s"] = round(resp.get("load_duration", 0) / ns, 2)
            r["respuesta_cruda"] = resp.get("response", "")

            # --- Validacion LEYENDO. No se ejecuta nada. ---
            v: dict = {}
            try:
                d = json.loads(r["respuesta_cruda"])
                accion = d.get("action")
                args = d.get("args") or {}
                v["action"] = accion
                v["args"] = args
                v["accion_existe_en_catalogo"] = accion in CATALOGO
                v["accion_inventada"] = accion not in CATALOGO
                v["campos_presentes"] = [c for c in REQUERIDOS if c in args]
                v["campos_faltantes"] = [c for c in REQUERIDOS if c not in args]
                v["tiene_los_tres_campos"] = not v["campos_faltantes"]
                v["fichero_es_el_declarado"] = args.get("fichero") == contexto["fichero_declarado"]
                v["json_valido"] = True
            except (json.JSONDecodeError, AttributeError) as exc:
                v = {"json_valido": False, "error_parseo": str(exc)}
            r["validacion"] = v

        subprocess.run(["ollama", "stop", modelo], capture_output=True)
        informe["resultados"][modelo] = r

    marca = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    salida_f = AQUI / f"evidencia-comparacion-{marca}.json"
    salida_f.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    print(f"\n[evidencia] {salida_f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
