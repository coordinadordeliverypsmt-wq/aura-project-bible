"""Demostracion de UN ciclo autonomo real de AURORA en un sandbox desechable FUERA del repositorio.

Cadena real de produccion (motor_autonomia.trabajar): descubrir -> planificar -> review -> autoconstruccion (copia,
verificacion, promocion atomica) -> registro encadenado -> segunda invocacion (continuidad desde el log).
Verificador INDEPENDIENTE real: pytest del modulo bajo confinamiento estricto (Landlock + seccomp), no `lambda: True`.
La autoridad `por="ceo"` solo existe en el log desechable de este sandbox (igual que en las pruebas del proyecto).
"""
import json, os, pathlib, sys, tempfile
import aislamiento as ais, control_plane as cp, motor_autonomia as motor, review, verificador as vf

base = pathlib.Path(tempfile.mkdtemp(prefix="aura-e2e-"))
zona = base / "entorno" / "control-plane"
zona.mkdir(parents=True)
(zona / "modulo_inocuo.py").write_text("def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n")
(zona / "test_modulo_inocuo.py").write_text("from modulo_inocuo import viva\n\n\ndef test_viva():\n    assert viva() == 2\n")
review.habilitar(base, por="ceo", acta="SANDBOX desechable 2026-10-26: no es un acta real", alcance=("eliminar_codigo_muerto",))
llamadas = []

def verificar(raiz):
    """Ejecuta la prueba REAL del modulo en la COPIA candidata, confinada en modo estricto."""
    raiz = pathlib.Path(raiz)
    # `raiz` es la COPIA candidata del DIRECTORIO de trabajo: conserva `entorno/control-plane/...` (defecto del
    # primer intento de este script: buscaba la prueba en la raiz y pytest salia con codigo 4).
    prueba = raiz / "entorno" / "control-plane" / "test_modulo_inocuo.py"
    inf = vf.ejecutar_pruebas([str(prueba)], prueba.parent, confinar=ais.preparar_estricto(raiz))
    llamadas.append({"raiz_es_copia": raiz.resolve() != zona.resolve(), "sano": inf.sano,
                     "raiz": str(raiz), "contenido": sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*.py"))[:8],
                     "salida": inf.salida[-600:], "codigo": inf.codigo})
    return inf.sano

print("estricto_disponible:", ais.estricto_disponible())
i1 = motor.trabajar(base, zona, verificacion=verificar, max_tareas=3)
print("CICLO 1:", json.dumps({k: i1.get(k) for k in ("ejecutadas", "motivo_de_parada")}, ensure_ascii=False))
print("  modulo tras el ciclo 1:", repr((zona / "modulo_inocuo.py").read_text()))
i2 = motor.trabajar(base, zona, verificacion=verificar, max_tareas=3)
print("CICLO 2:", json.dumps({k: i2.get(k) for k in ("ejecutadas", "motivo_de_parada")}, ensure_ascii=False))
ev = cp.leer_eventos(base)
print("verificaciones:", llamadas)
print("eventos:", [e["tipo"] for e in ev])
aplic = [e["datos"] for e in ev if e["tipo"] == "cambio_aplicado"]
print("cambio_aplicado:", json.dumps([{k: d.get(k) for k in ("promovido", "efecto_verificado", "verificacion_sana", "revertido", "verificacion_aislada", "motivo")} for d in aplic], ensure_ascii=False))
print("integridad del log del sandbox:", cp.verificar_integridad_log(base))
print("SANDBOX", base)
