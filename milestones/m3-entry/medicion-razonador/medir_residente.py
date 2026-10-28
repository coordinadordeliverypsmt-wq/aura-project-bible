"""Paso 4 del DP diagnostico: enviar el prompt congelado con el modelo YA RESIDENTE.

Instrumentacion. No compone AURORA, no invoca al motor, no ejecuta ninguna accion. Solo lee `_SYSTEM`
y el catalogo para reproducir el prompt byte a byte y validar la respuesta LEYENDO.

POR QUE EXISTE COMO SCRIPT APARTE. El DP separa deliberadamente la carga de la medicion: la carga va
en primer plano -unico modo que ha logrado cargar 3b- y la medicion en segundo plano, porque un turno
de 3b excede el tope de 10 minutos del primer plano. Este script hace SOLO el paso 4, asi que no
repite el calentamiento ni vuelve a comprobar el umbral previo a la carga: ese ya se verifico antes
de cargar, como manda el protocolo.

Nada mas cambia: mismo prompt, mismo caso, mismo timeout, misma validacion, un solo intento.
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

MODELO = "qwen2.5:3b"
TIMEOUT_S = 1800
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


def main() -> int:
    sys.path.insert(0, str(RAIZ / "walking-skeleton"))
    from aura_skeleton.core.permissions import CATALOGO
    from aura_skeleton.modules.providers_real import _SYSTEM

    ev_previa = max(glob.glob(str(AQUI / "evidencia-humo-2026*.json")), key=os.path.getmtime)
    previa = json.load(open(ev_previa, encoding="utf-8"))
    prompt_usuario = previa["evidencia"]["llamadas_al_modelo"][0]["prompt_enviado"]
    contexto = previa["evidencia"]["args_literales_de_la_derivada"]

    r: dict = {
        "modelo": MODELO,
        "instante": _dt.datetime.now().isoformat(timespec="seconds"),
        "paso": "4 · prompt congelado con modelo YA RESIDENTE",
        "origen_del_prompt": os.path.basename(ev_previa),
        "prompt_usuario_sha256": hashlib.sha256(prompt_usuario.encode()).hexdigest(),
        "prompt_completo_sha256": hashlib.sha256((_SYSTEM + prompt_usuario).encode()).hexdigest(),
        "contexto_sha256": hashlib.sha256(
            json.dumps(contexto, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "contexto": contexto,
        "timeout_s": TIMEOUT_S,
    }

    # Residencia y umbral 2, comprobados por el propio arnes ademas de a mano.
    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    r["ollama_ps"] = ps.stdout.strip()
    r["residente"] = MODELO in ps.stdout
    r["mem_antes"] = _mem()
    if not r["residente"]:
        r["abandono"] = "el modelo no esta residente: el paso 2 no se cumplio"
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1
    if r["mem_antes"]["MemAvailable"] < MIN_RAM_TRAS_CARGA_MB:
        r["abandono"] = f"umbral tras carga: {r['mem_antes']['MemAvailable']} MB < {MIN_RAM_TRAS_CARGA_MB}"
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1

    cuerpo = {"model": MODELO, "prompt": prompt_usuario, "system": _SYSTEM, "stream": False, "format": "json"}
    req = urllib.request.Request(
        URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}
    )
    t0 = time.monotonic()
    resp: dict = {}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as f:  # noqa: S310 — endpoint local (D24)
            resp = json.load(f)
        r["error"] = None
    except Exception as exc:  # noqa: BLE001 — el modo de fallo ES el dato que discrimina
        r["error"] = f"{type(exc).__name__}: {exc}"
    r["latencia_pared_s"] = round(time.monotonic() - t0, 2)
    r["mem_despues"] = _mem()

    if resp:
        ns = 1e9
        entrada, salida = resp.get("prompt_eval_count", 0), resp.get("eval_count", 0)
        t_in, t_out = resp.get("prompt_eval_duration", 0) / ns, resp.get("eval_duration", 0) / ns
        r.update(
            tokens_entrada=entrada,
            tokens_generados=salida,
            ingesta_s=round(t_in, 2),
            generacion_s=round(t_out, 2),
            ingesta_tok_s=round(entrada / t_in, 2) if t_in else None,
            generacion_tok_s=round(salida / t_out, 2) if t_out else None,
            inferencia_total_s=round(resp.get("total_duration", 0) / ns, 2),
            carga_en_esta_llamada_s=round(resp.get("load_duration", 0) / ns, 2),
            respuesta_cruda=resp.get("response", ""),
        )
        v: dict = {}
        try:
            d = json.loads(r["respuesta_cruda"])
            accion, args = d.get("action"), (d.get("args") or {})
            v = {
                "json_valido": True,
                "action": accion,
                "args": args,
                "accion_existe_en_catalogo": accion in CATALOGO,
                "es_proponer_cambio": accion == "proponer_cambio",
                "campos_presentes": [c for c in REQUERIDOS if c in args],
                "campos_faltantes": [c for c in REQUERIDOS if c not in args],
                "fichero_es_el_declarado": args.get("fichero") == contexto["fichero_declarado"],
            }
            v["tiene_los_tres_campos"] = not v["campos_faltantes"]
        except (json.JSONDecodeError, AttributeError) as exc:
            v = {"json_valido": False, "error_parseo": str(exc)}
        r["validacion"] = v

    subprocess.run(["ollama", "stop", MODELO], capture_output=True)
    r["mem_tras_descargar"] = _mem()

    marca = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    salida_f = AQUI / f"evidencia-3b-residente-{marca}.json"
    salida_f.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print(f"\n[evidencia] {salida_f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
