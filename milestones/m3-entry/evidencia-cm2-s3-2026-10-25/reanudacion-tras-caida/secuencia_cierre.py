"""Demostracion de cierre (DP-RECUPERACION-TRAS-CAIDAS) en sandbox, con el prototipo FINAL. Nada del arbol vivo."""
import json, os, pathlib, signal, subprocess, sys, tempfile
import control_plane as cp, planificador as pl, motor_autonomia as motor
import test_red_reanudacion_tras_caida as t
raiz = pathlib.Path(sys.argv[1])
def preparar(nombre, guion_txt):
    d = raiz / nombre; d.mkdir(); (d / "tmp").mkdir()
    g = d / "guion.py"; g.write_text(guion_txt)
    env = {**os.environ, "PYTHONPATH": str(t.PLANO), "AURA_AUTOCONSTRUCCION_ESTADO": str(d / "estado"), "TMPDIR": str(d / "tmp")}
    return d / "sandbox", g, env
def correr(g, base, fase, env):
    r = subprocess.run([sys.executable, str(g), str(base), fase], env=env, capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout.strip()
def tid(base): return [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"]["id"]
def promos(base): return sum(1 for e in cp.leer_eventos(base) if e["tipo"] == "cambio_aplicado" and e["datos"].get("promovido"))

print("== A. SIGKILL durante la verificacion, DOS supervisores a la vez, segunda ejecucion")
base, g, env = preparar("A", t._GUION)
rc, _ = correr(g, base, "matar", env); i = tid(base)
print("1-3. SIGKILL rc =", rc, "| ejecutor registrado:", "ejecutor" in [e for e in cp.leer_eventos(base) if e["tipo"] == "tarea_planificada"][0]["datos"])
print("4.   estado =", pl.estado_de(base, i), "| fichero intacto:", "_muerta" in (base / "entorno/control-plane/modulo_inocuo.py").read_text())
ps = [subprocess.Popen([sys.executable, str(g), str(base), "seguir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
salidas = [(p.wait(timeout=300), p.communicate()[0].strip()) for p in ps]
print("5-7. dos supervisores simultaneos:", salidas, "| suma ejecutadas =", sum(int(s.split()[0]) for _, s in salidas if s))
print("8.   estado =", pl.estado_de(base, i), "| intentos =", pl.intentos_de(base, i), "| promociones =", promos(base),
      "| motivos:", [e["datos"]["motivo"] for e in cp.leer_eventos(base) if e["tipo"] == "ciclo_detenido"][-2:], "| log integro:", cp.verificar_integridad_log(base)["integro"])
rc, out = correr(g, base, "seguir", env)
print("9-10. segunda ejecucion:", out, "| promociones =", promos(base), "| intentos =", pl.intentos_de(base, i))

print("== B. Muerte ENTRE promover y registrar (§8)")
base, g, env = preparar("B", t._GUION_REGISTRO)
rc, _ = correr(g, base, "matar_al_registrar", env); i = tid(base)
print("     SIGKILL rc =", rc, "| promovido en disco:", "_muerta" not in (base / "entorno/control-plane/modulo_inocuo.py").read_text(), "| cambio_aplicado en log:", promos(base))
rc, out = correr(g, base, "seguir", env)
print("     supervisor nuevo:", out, "| recuperacion:", [e["datos"]["resultado"] for e in cp.leer_eventos(base) if e["tipo"] == "recuperacion_al_arranque"],
      "| promociones =", promos(base), "| intentos =", pl.intentos_de(base, i), "| estado =", pl.estado_de(base, i), "| elegible =", pl.elegible(base, i))

print("== C. Dos interrupciones: AGOTADA y observable")
base, g, env = preparar("C", t._GUION)
for _ in range(2):
    fase = "matar" if not (base).exists() else "matar_otra"
    rc, _ = correr(g, base, "matar", env) if not base.exists() else (None, None)
i = tid(base)
# segundo intento interrumpido: replanificar en un proceso que muere durante la verificacion
g2 = g.parent / "guion2.py"; g2.write_text(t._GUION.replace('if fase == "matar":\n    zona.mkdir', 'if fase == "nunca":\n    zona.mkdir'))
rc2, _ = correr(g2, base, "matar", env)
print("     dos SIGKILL rc =", rc, rc2, "| intentos =", pl.intentos_de(base, i), "| estado =", pl.estado_de(base, i))
rc, out = correr(g, base, "seguir", env)
ag = [e["datos"] for e in cp.leer_eventos(base) if e["tipo"] == motor.EVENTO_PRESUPUESTO_AGOTADO]
rc, out2 = correr(g, base, "seguir", env)
ag2 = [e for e in cp.leer_eventos(base) if e["tipo"] == motor.EVENTO_PRESUPUESTO_AGOTADO]
print("     supervisor:", out, "/", out2, "| eventos de agotamiento:", len(ag), "->", len(ag2), "|", ag[0] if ag else None)
print("residuos aura-candidato fuera de los tmp de la demo:", len(list(pathlib.Path("/tmp").glob("aura-candidato-*"))))
