"""H2 (M2.0) — El audit log debe sobrevivir a un reinicio.

En M1 era una lista en memoria. En M2 lo auditado son acciones reales sobre archivos del usuario:
el registro deja de ser observabilidad y pasa a ser prueba forense.
"""

import json

from aura_skeleton import observability as obs


def test_audit_log_sobrevive_reinicio(tmp_path):
    """Escribe con una instancia, lee con OTRA: simula el reinicio del proceso."""
    ruta = str(tmp_path / "audit.jsonl")
    log1 = obs.AuditLog(ruta)
    log1.append({"module": "permissions", "msg": "lista roja borrar_archivo -> DENEGADA", "audit": True})
    log1.append({"module": "ha-adapter", "msg": "EJECUTA encender_dispositivo", "audit": True})

    del log1
    log2 = obs.AuditLog(ruta)  # instancia nueva: solo puede leer del disco
    registros = log2.records()

    assert len(registros) == 2
    assert "borrar_archivo" in registros[0]["msg"]
    assert all("ts" in r for r in registros), "cada registro debe llevar marca de tiempo"


def test_linea_truncada_no_invalida_el_historial(tmp_path):
    """Un corte a mitad de escritura pierde esa linea, no el registro completo.

    Es la razon de elegir JSONL append-only frente a un array JSON reescrito.
    """
    ruta = str(tmp_path / "audit.jsonl")
    log = obs.AuditLog(ruta)
    log.append({"msg": "accion 1", "audit": True})
    log.append({"msg": "accion 2", "audit": True})
    with open(ruta, "a", encoding="utf-8") as f:
        f.write('{"msg": "accion 3 truncada por corte de ener')  # sin cerrar ni salto de linea

    registros = obs.AuditLog(ruta).records()
    assert len(registros) == 2, "las dos acciones completas deben sobrevivir"


def test_log_con_audit_persiste_automaticamente(tmp_path):
    """Integracion: obs.log(audit=True) escribe en disco cuando la persistencia esta activa."""
    ruta = str(tmp_path / "audit.jsonl")
    obs.configure_audit(ruta)
    try:
        obs.log("AUDIT", "permissions", "lista roja borrar_archivo -> DENEGADA", "t1", audit=True)
        obs.log("INFO", "router", "esto NO es auditable", "t1")  # sin audit=True
    finally:
        obs.reset_audit()

    with open(ruta, encoding="utf-8") as f:
        lineas = [json.loads(x) for x in f if x.strip()]
    assert len(lineas) == 1, "solo los registros marcados como audit deben persistirse"
    assert "borrar_archivo" in lineas[0]["msg"]
