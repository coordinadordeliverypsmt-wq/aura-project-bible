"""Integracion: AURORA lee su propio historial y dice como esta, en una sola operacion.

Antes tenia tres capacidades de autodiagnostico dispersas —IMA, tablero de dependencia, auditoria de
garantias— y ninguna respondia a la pregunta que hace falta para dirigir la propia evolucion:
"¿como estoy y que deberia atender primero?". Y nadie leia el audit log para analizarse.
"""

import json

from aura_skeleton.core.autodiagnostico import diagnosticar, informe_ejecutivo


def _log(tmp_path, registros):
    p = tmp_path / "audit.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")
    return str(p)


def test_agrupa_las_incidencias_por_clase(tmp_path):
    """Un informe que enumera 40 incidencias no ayuda a decidir; uno que las agrupa, si."""
    ruta = _log(tmp_path, [{"kind": "ERROR"}] * 3 + [{"kind": "HITL"}] * 5 + [{"kind": "MEM"}] * 2)

    d = diagnosticar(ruta)

    assert d.eventos == 10
    assert d.incidencias["intervenciones humanas exigidas"] == 5
    assert d.incidencias["errores de ejecucion"] == 3
    assert "MEM" not in d.incidencias, "la actividad normal no es una incidencia"


def test_señala_la_incidencia_DOMINANTE(tmp_path):
    """Lo que convierte un registro en una prioridad: cual se repite mas."""
    ruta = _log(tmp_path, [{"kind": "ERROR"}] * 2 + [{"kind": "HITL"}] * 7)
    assert diagnosticar(ruta).incidencia_dominante == ("intervenciones humanas exigidas", 7)


def test_SIN_DATOS_lo_declara_en_vez_de_inventar_un_informe(tmp_path):
    """Sin uso real, cualquier prioridad seria una hipotesis. Es el caso de hoy."""
    d = diagnosticar(str(tmp_path / "no-existe.jsonl"))
    assert d.sin_datos and d.incidencia_dominante is None
    assert "sin datos" in informe_ejecutivo(d).lower()


def test_un_registro_vacio_tampoco_produce_conclusiones(tmp_path):
    assert diagnosticar(_log(tmp_path, [])).sin_datos


def test_una_linea_ilegible_no_impide_el_diagnostico(tmp_path):
    """Disponibilidad: un caracter dañado no puede dejar a AURORA sin poder analizarse."""
    p = tmp_path / "a.jsonl"
    p.write_text('{"kind": "ERROR"}\n{roto\n{"kind": "ERROR"}\n', encoding="utf-8")
    assert diagnosticar(str(p)).incidencias["errores de ejecucion"] == 2


def test_el_informe_declara_lo_que_NO_pudo_evaluar(tmp_path):
    """Un informe incompleto que no lo dice es peor que uno corto."""
    txt = informe_ejecutivo(diagnosticar(_log(tmp_path, [{"kind": "MEM"}])))
    # Se comprueba CADA bloque por separado: la frase aparece en tres, asi que buscarla suelta
    # pasaria aunque uno se omitiera en silencio. Lo detecto la mutacion (M4 sobrevivia).
    for bloque in ("GARANTIAS", "CAPACIDADES (IMA)", "AUTONOMIA"):
        assert f"{bloque}: no evaluada" in txt.replace("no evaluadas", "no evaluada"), (
            f"el bloque {bloque} se omitio en silencio:\n{txt}"
        )


def test_el_informe_junta_lo_que_hoy_vive_disperso(tmp_path):
    """CONTROL: con todos los bloques presentes, ninguno se declara ausente."""
    txt = informe_ejecutivo(
        diagnosticar(_log(tmp_path, [{"kind": "ERROR"}])),
        ima=[type("D", (), {"medible": True, "logrado": 3, "total": 4})()],
        dependencia=[
            type("I", (), {"estado": "medible", "nombre": "X", "numerador": 1, "denominador": 2, "porcentaje": 50.0})()
        ],
        garantias={"ok": True, "vigentes": 112, "declaradas": 112},
    )
    assert "no evaluadas" not in txt
    assert "112/112" in txt and "3/4" in txt and "50.0%" in txt
