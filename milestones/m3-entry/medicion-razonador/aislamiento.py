"""Experimento de aislamiento: ¿puede el modelo decidir `sustituir`?

Instrumentacion. No compone AURORA, no invoca al motor, no ejecuta ninguna accion, no importa nada del
producto. Solo habla con el endpoint local y valida LEYENDO.

Se prescinde de `_SYSTEM` A PROPOSITO: es lo que impone la seleccion de accion y el formato, es decir,
justo lo que este experimento retira. Consecuencia declarada: esto NO mide la ruta del producto.

Uso:  python3 aislamiento.py <modelo>
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
URL = "http://127.0.0.1:11434/api/generate"
TIMEOUT_S = 1800
MIN_RAM_ANTES_MB = 1400
MIN_SWAP_LIBRE_MB = 600
MIN_RAM_TRAS_CARGA_MB = 150

# ------------------------------------------------------------------ CASO Y VERDAD DE REFERENCIA --
OBJETIVO = "def cobrar(x):\n    if not autorizado(x):\n        raise PermisoDenegado\n    return x\n"
PATRON_OBSOLETO = "    if not tiene_permiso(x):"
PATRON_CORRECTO = "    if not autorizado(x):"

# ------------------------------------------------------------------------- PROMPT CONGELADO --
# Fijado en el DP ANTES de ejecutar. Si cambia, la tanda se anula y se repite.
PROMPT = (
    "En un fichero de declaraciones hay un patron declarado que ya no aparece en el fichero objetivo.\n"
    "\n"
    "Patron declarado que ya no aparece:\n"
    "    if not tiene_permiso(x):\n"
    "\n"
    "Contenido actual del fichero objetivo (laboratorio_objetivo.py):\n"
    "def cobrar(x):\n"
    "    if not autorizado(x):\n"
    "        raise PermisoDenegado\n"
    "    return x\n"
    "\n"
    "Responde UNICAMENTE con la linea del fichero objetivo que debe sustituir al patron declarado.\n"
    "Sin explicaciones, sin formato, sin comillas."
)


def _mem() -> dict:
    d = {}
    for linea in pathlib.Path("/proc/meminfo").read_text().splitlines():
        k, _, resto = linea.partition(":")
        if k in ("MemFree", "MemAvailable", "SwapFree", "SwapTotal"):
            d[k] = int(resto.strip().split()[0]) // 1024
    d["load1"] = os.getloadavg()[0]
    return d


def clasificar(respuesta: str) -> dict:
    """Criterio binario del DP, en dos niveles. Se evalua LEYENDO; no se ejecuta nada."""
    limpio = respuesta.strip()
    apariciones = OBJETIVO.count(limpio) if limpio else 0
    v = {
        "respuesta_limpia": limpio,
        "apariciones_en_el_objetivo": apariciones,
        "contiene_autorizado": "autorizado" in limpio,
        "es_el_patron_obsoleto": limpio == PATRON_OBSOLETO.strip(),
    }
    v["pass_estricto"] = limpio == PATRON_CORRECTO.strip()
    v["pass_funcional"] = apariciones == 1 and v["contiene_autorizado"]
    # FABRICACION se registra APARTE de FAIL: devolver texto ausente del fichero es el dato mas grave.
    v["fabricacion"] = bool(limpio) and apariciones == 0
    if v["pass_estricto"]:
        v["veredicto"] = "PASS_ESTRICTO"
    elif v["pass_funcional"]:
        v["veredicto"] = "PASS_FUNCIONAL"
    elif v["fabricacion"]:
        v["veredicto"] = "FABRICACION"
    else:
        v["veredicto"] = "FAIL"
    return v


def _guarda_de_diseno() -> dict:
    """Comprobacion exigida por el CEO ANTES de ejecutar: el criterio de PASS NO puede satisfacerse
    devolviendo el patron antiguo. Se verifica, no se afirma."""
    c = clasificar(PATRON_OBSOLETO)
    return {
        "devolviendo_el_patron_antiguo": c["veredicto"],
        "no_pasa_estricto": not c["pass_estricto"],
        "no_pasa_funcional": not c["pass_funcional"],
        "guarda_valida": not c["pass_estricto"] and not c["pass_funcional"],
    }


def main() -> int:
    modelo = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:0.5b"
    r: dict = {
        "modelo": modelo,
        "instante": _dt.datetime.now().isoformat(timespec="seconds"),
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "objetivo_sha256": hashlib.sha256(OBJETIVO.encode()).hexdigest(),
        "patron_obsoleto": PATRON_OBSOLETO,
        "patron_correcto_esperado": PATRON_CORRECTO,
        "prompt": PROMPT,
        "fichero_objetivo": OBJETIVO,
        "timeout_s": TIMEOUT_S,
        "usa_system": False,
        "guarda_de_diseno": _guarda_de_diseno(),
    }

    if not r["guarda_de_diseno"]["guarda_valida"]:
        r["abandono"] = "el criterio de PASS se satisface con el patron antiguo: experimento invalido"
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 2

    r["mem_antes"] = _mem()
    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    r["residente_al_empezar"] = modelo in ps.stdout
    if not r["residente_al_empezar"]:
        if r["mem_antes"]["MemAvailable"] < MIN_RAM_ANTES_MB or r["mem_antes"]["SwapFree"] < MIN_SWAP_LIBRE_MB:
            r["abandono"] = (
                f"umbral previo: disponible {r['mem_antes']['MemAvailable']} MB / "
                f"swap {r['mem_antes']['SwapFree']} MB"
            )
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return 1
    elif r["mem_antes"]["MemAvailable"] < MIN_RAM_TRAS_CARGA_MB:
        r["abandono"] = f"umbral tras carga: {r['mem_antes']['MemAvailable']} MB"
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 1

    cuerpo = {"model": modelo, "prompt": PROMPT, "stream": False}
    req = urllib.request.Request(
        URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}
    )
    t0 = time.monotonic()
    resp: dict = {}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as f:  # noqa: S310 — endpoint local (D24)
            resp = json.load(f)
        r["error"] = None
    except Exception as exc:  # noqa: BLE001 — el modo de fallo es un dato
        r["error"] = f"{type(exc).__name__}: {exc}"
    r["latencia_pared_s"] = round(time.monotonic() - t0, 2)
    r["mem_despues"] = _mem()

    if resp:
        ns = 1e9
        entrada, salida = resp.get("prompt_eval_count", 0), resp.get("eval_count", 0)
        t_in, t_out = resp.get("prompt_eval_duration", 0) / ns, resp.get("eval_duration", 0) / ns
        r.update(
            carga_s=round(resp.get("load_duration", 0) / ns, 2),
            tokens_entrada=entrada,
            tokens_generados=salida,
            ingesta_s=round(t_in, 2),
            generacion_s=round(t_out, 2),
            ingesta_tok_s=round(entrada / t_in, 2) if t_in else None,
            generacion_tok_s=round(salida / t_out, 2) if t_out else None,
            inferencia_total_s=round(resp.get("total_duration", 0) / ns, 2),
            respuesta_cruda=resp.get("response", ""),
        )
        r["clasificacion"] = clasificar(r["respuesta_cruda"])

    subprocess.run(["ollama", "stop", modelo], capture_output=True)
    r["mem_tras_descargar"] = _mem()

    marca = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    salida_f = AQUI / f"evidencia-aislamiento-{modelo.replace(':', '-')}-{marca}.json"
    salida_f.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print(f"\n[evidencia] {salida_f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
