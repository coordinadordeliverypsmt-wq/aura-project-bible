"""RED · trazabilidad DERIVADA EN CONSULTA (decision del CEO 2026-08-25, opcion A).

La cadena `hallazgo -> propuesta -> promocion -> tarea -> resultado` **ya existe** repartida entre
`propuestas`, `tareas_AUTO` y `trabajo_completado`. La opcion A dice: derivarla al consultar, **sin
duplicar el vinculo** dentro del resultado y **sin migrar historia**.

Un trabajo sin procedencia registrada no es un error: es un trabajo anterior al mecanismo. Inventarle
un origen seria fabricar procedencia, que es justo lo que la decision prohibe.
"""
from __future__ import annotations

import control_plane as cp


def _estado_con_cadena_completa():
    """Caso A: propuesta -> promovida -> tarea -> completada. Todo por la via oficial."""
    e = cp.estado_inicial()
    e["zonas_bloqueadas_para_discovery"] = ["m9", "aprobar"]
    # DOS defectos, no uno: con una sola propuesta «la primera» coincide con «la correcta» y
    # ninguna prueba distinguiria un mutante que devolviese cualquiera. Lo destapo TRZ-M4.
    e["defectos"] = [{"id": "DEF-OTRO", "fichero": "z.py", "prueba": "test_z", "apertura": "ABIERTO",
                      "fichero_de_trabajo": "modulo_z.py",
                      "descripcion": "propuesta AJENA que no debe devolverse"},
                     {"id": "DEF-T", "fichero": "x.py", "prueba": "test_x", "apertura": "ABIERTO",
                      "fichero_de_trabajo": "modulo_x.py",
                      "descripcion": "defecto con procedencia completa"}]
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    e = cp.promover_a_auto(e, "defecto:DEF-T", aprobado_por="ceo")
    cp.fijar_estado_tarea(e, "DEF-T", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(e, "DEF-T", "GREEN", autoridad="ceo")
    return e


def test_A_una_cadena_completa_se_deriva_entera():
    t = cp.trazabilidad(_estado_con_cadena_completa(), "DEF-T")
    assert t["tiene_procedencia"] is True
    assert t["propuesta"] == "defecto:DEF-T"
    assert t["origen"] == "defecto"
    assert t["ref"] == "DEF-T", "devolvio una propuesta que no es la de esta tarea"
    assert t["aprobado_por"] == "ceo"
    assert t["coherente"] is True


def test_B_un_trabajo_historico_sin_procedencia_no_se_le_inventa_una():
    """**La garantia que impide fabricar historia.** Debe quedar identificado, no enlazado."""
    e = cp.estado_inicial()
    e["trabajo_completado"] = [{"id": "TAREA-ANTIGUA", "resultado": "hecho", "cuando": "2026-08-01"}]
    t = cp.trazabilidad(e, "TAREA-ANTIGUA")
    assert t["tiene_procedencia"] is False
    assert t["propuesta"] is None
    assert "sin procedencia" in t["motivo"].lower()


def test_C_una_propuesta_que_no_corresponde_no_se_acepta():
    """Si la tarea apunta a una propuesta que no existe, la relacion NO es coherente."""
    e = _estado_con_cadena_completa()
    e["propuestas"] = [p for p in e["propuestas"] if p["id"] != "defecto:DEF-T"]
    t = cp.trazabilidad(e, "DEF-T")
    assert t["coherente"] is False
    assert "no existe" in t["motivo"].lower() or "no corresponde" in t["motivo"].lower()


def test_no_se_deriva_de_un_trabajo_que_no_existe():
    e = cp.estado_inicial()
    t = cp.trazabilidad(e, "NO-EXISTE")
    assert t["tiene_procedencia"] is False
    assert t["completado"] is False


def test_la_consulta_NO_escribe_el_vinculo_en_el_resultado():
    """Opcion A: derivar, no duplicar. La entrada de `trabajo_completado` no gana campos."""
    e = _estado_con_cadena_completa()
    antes = dict(e["trabajo_completado"][0])
    cp.trazabilidad(e, "DEF-T")
    assert e["trabajo_completado"][0] == antes
    assert "origen_propuesta" not in e["trabajo_completado"][0]


def test_la_consulta_no_toca_tareas_auto():
    e = _estado_con_cadena_completa()
    antes = list(e["tareas_AUTO"])
    cp.trazabilidad(e, "DEF-T")
    assert e["tareas_AUTO"] == antes
