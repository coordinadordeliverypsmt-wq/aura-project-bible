"""Hito D: interrupcion REAL (SIGKILL a mitad de la verificacion) y recuperacion por un proceso nuevo."""
import json, os, pathlib, signal, sys
import aislamiento as ais, autoconstruccion as ac, control_plane as cp, motor_autonomia as motor, review, verificador as vf

base, fase = pathlib.Path(sys.argv[1]), sys.argv[2]
zona = base / "entorno" / "control-plane"
ORIGINAL = "def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n"

def verificar(raiz):
    raiz = pathlib.Path(raiz)
    if fase == "matar":
        os.kill(os.getpid(), signal.SIGKILL)  # muerte abrupta con el candidato a medio verificar
    prueba = raiz / "entorno" / "control-plane" / "test_modulo_inocuo.py"
    return vf.ejecutar_pruebas([str(prueba)], prueba.parent, confinar=ais.preparar_estricto(raiz)).sano

if fase == "matar":
    zona.mkdir(parents=True)
    (zona / "modulo_inocuo.py").write_text(ORIGINAL)
    (zona / "test_modulo_inocuo.py").write_text("from modulo_inocuo import viva\n\n\ndef test_viva():\n    assert viva() == 2\n")
    review.habilitar(base, por="ceo", acta="SANDBOX desechable 2026-10-26: no es un acta real", alcance=("eliminar_codigo_muerto",))
    motor.trabajar(base, zona, verificacion=verificar, max_tareas=3)
    print("NO DEBERIA LLEGAR AQUI")
else:
    print("fichero tras el SIGKILL (original intacto?):", (zona / "modulo_inocuo.py").read_text() == ORIGINAL)
    print("recuperar():", json.dumps(ac.recuperar(base), ensure_ascii=False, default=str)[:300])
    i = motor.trabajar(base, zona, verificacion=verificar, max_tareas=3)
    print("CICLO tras la recuperacion:", {k: i.get(k) for k in ("ejecutadas", "motivo_de_parada")})
    i2 = motor.trabajar(base, zona, verificacion=verificar, max_tareas=3)
    print("CICLO siguiente:", {k: i2.get(k) for k in ("ejecutadas", "motivo_de_parada")})
    print("modulo final:", repr((zona / "modulo_inocuo.py").read_text()))
    ev = cp.leer_eventos(base)
    print("eventos:", [e["tipo"] for e in ev])
    print("promociones:", sum(1 for e in ev if e["tipo"] == "cambio_aplicado" and e["datos"].get("promovido")))
    print("integridad:", cp.verificar_integridad_log(base))
    print("residuos aura-candidato en /tmp:", len(list(pathlib.Path("/tmp").glob("aura-candidato-*"))))
