"""RED · seleccion automatica de la siguiente tarea AUTO.

Lo que FALTA del ciclo autonomo. Todo lo demas ya existe y esta validado (86/86): `debe_ejecutar`
ya sabe si una tarea concreta puede correr —no completada y no bloqueada por una decision—; lo que
no existe es recorrer las candidatas y devolver la primera ejecutable.

**No introduce autoridad nueva.** El selector NO decide que es AUTO: lee lo que el CEO declaro y
aplica `debe_ejecutar`, que es la regla ya aprobada. Si nadie autorizo nada, devuelve None.
"""
from __future__ import annotations

import control_plane as cp


def _estado(tareas_auto=(), completadas=(), decisiones=()):
    e = cp.estado_inicial()
    e["tareas_AUTO"] = list(tareas_auto)
    e["trabajo_completado"] = [{"id": i, "cuando": "2026-08-25", "resultado": "ok"} for i in completadas]
    e["decisiones_pendientes"] = list(decisiones)
    return e


def test_sin_tareas_autorizadas_no_inventa_ninguna():
    """El caso que mas importa: si el CEO no autorizo nada, AURA NO se inventa trabajo."""
    assert cp.siguiente_auto(_estado()) is None


def test_devuelve_la_primera_tarea_autorizada_ejecutable():
    e = _estado(tareas_auto=[{"id": "T-1", "descripcion": "x"}, {"id": "T-2", "descripcion": "y"}])
    assert cp.siguiente_auto(e)["id"] == "T-1"


def test_no_devuelve_una_tarea_ya_completada():
    """Sin esto, una sesion reanudada repetiria el trabajo de la anterior."""
    e = _estado(tareas_auto=[{"id": "T-1"}, {"id": "T-2"}], completadas=["T-1"])
    assert cp.siguiente_auto(e)["id"] == "T-2"


def test_no_devuelve_una_tarea_bloqueada_por_una_decision_humana():
    """La barrera central: una tarea que espera al CEO NO puede ejecutarse sola."""
    e = _estado(tareas_auto=[{"id": "T-1"}],
                decisiones=[{"id": "D-1", "asunto": "?", "bloquea": ["T-1"]}])
    assert cp.siguiente_auto(e) is None


def test_una_decision_que_bloquea_todo_detiene_la_cadena():
    e = _estado(tareas_auto=[{"id": "T-1"}, {"id": "T-2"}],
                decisiones=[{"id": "D-1", "asunto": "?", "bloquea": "todo"}])
    assert cp.siguiente_auto(e) is None


def test_el_motivo_de_no_haber_tarea_queda_declarado():
    """Detenerse en silencio es indistinguible de un fallo. El motivo debe poder leerse."""
    e = _estado(tareas_auto=[{"id": "T-1"}],
                decisiones=[{"id": "D-1", "asunto": "?", "bloquea": "todo"}])
    tarea, motivo = cp.siguiente_auto_con_motivo(e)
    assert tarea is None
    assert "D-1" in motivo or "decision" in motivo.lower()
