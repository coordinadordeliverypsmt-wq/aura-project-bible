"""Secuencia de 10 pasos (DP-RECUPERACION-TRAS-CAIDAS) en sandbox, con el planificador PROTOTIPO."""
import json, os, pathlib, signal, subprocess, sys
import control_plane as cp, planificador as pl
G = pathlib.Path(sys.argv[1]); base = pathlib.Path(sys.argv[2]); zona = base / "entorno" / "control-plane"
def correr(fase):
    r = subprocess.run([sys.executable, str(G), str(base), fase], capture_output=True, text=True, env=os.environ)
    return r.returncode, r.stdout.strip()
def id_tarea():
    return [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"]["id"]
rc, _ = correr("matar")
print("1-3. tarea iniciada y proceso muerto por SIGKILL durante la verificacion: rc =", rc)
t = id_tarea(); ej = [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"]["ejecutor"]
print("     identidad del ejecutor registrada:", {k: ej[k] for k in ("pid", "inicio")}, "arranque:", ej["arranque"][:8] + "...")
print("4.   deteccion: estado =", pl.estado_de(base, t), "| fichero intacto:", "_muerta" in (zona / "modulo_inocuo.py").read_text())
rc, out = correr("seguir")
print("5-7. supervisor reiniciado (proceso NUEVO): ejecutadas/parada =", out, "| estado =", pl.estado_de(base, t), "| _muerta retirada:", "_muerta" not in (zona / "modulo_inocuo.py").read_text())
ev = cp.leer_eventos(base)
print("8.   persistido: intentos =", pl.intentos_de(base, t), "| promociones =", sum(1 for e in ev if e["tipo"] == "cambio_aplicado" and e["datos"].get("promovido")), "| log:", cp.verificar_integridad_log(base)["motivo"])
rc, out = correr("seguir")
print("9-10. segunda ejecucion: ejecutadas/parada =", out, "| estado =", pl.estado_de(base, t), "| promociones =", sum(1 for e in cp.leer_eventos(base) if e["tipo"] == "cambio_aplicado" and e["datos"].get("promovido")))
