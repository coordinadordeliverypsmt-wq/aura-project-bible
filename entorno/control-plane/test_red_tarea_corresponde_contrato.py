"""OBJETIVO 4.2 — que la TAREA que llega al ejecutor corresponda al CONTRATO que la autoriza.

**Diagnostico medido (no se repite el analisis, se fija en la prueba):**
`planificador.a_tarea()` construye la tarea copiando `fichero`, `operacion`, `buscar`, `sustituir`
desde `oportunidad.detalle` y `oportunidad.alcance` -pero NO copia ningun identificador de contrato-.
Sin embargo `formacion.formacion()` SI mete el id del contrato en
`oportunidad.detalle["numero"] = cap["id"]` para la rama de contratos ya escritos. La perdida ocurre
en el punto medio: `a_tarea()` no traslada `detalle["numero"]` a la tarea. Esa parte esta en
`planificador.py`, fuera de esta superficie (prohibido tocarlo en esta mision), y queda registrada
como DECISION_REQUIRED / trabajo del integrador en el informe de entrega.

**Lo que SI cabe en `contrato.py` y se implementa aqui:** una funcion PURA,
`corresponde_tarea_a_contrato(tarea, contrato)`, que decide si una tarea (con la forma que
`planificador.a_tarea()` produce hoy: `fichero`, `operacion`, `buscar`, `sustituir`) es consistente
con lo que un contrato concreto autoriza -mismo fichero dentro de `perimetro.modificables` y fuera de
`perimetro.fuera_de_alcance`, misma operacion, mismos textos `buscar`/`sustituir` cuando la regla los
declara-. No identifica CUAL contrato autorizo la tarea -eso exige el campo perdido en
`planificador.py`-, pero SI verifica que una tarea dada no se sale de lo que un contrato dado
permite, y falla cerrado ante cualquier ambiguedad (ADR-0003)."""

import pathlib

import contrato as ct

PLANO = pathlib.Path(__file__).parent


def _contrato_sustituir(**cambios):
    base = {
        "perimetro": {"modificables": [str(PLANO / "observatorio.py")], "fuera_de_alcance": []},
        "regla_de_transformacion": {"operacion": "sustituir_texto",
                                     "buscar": "\"Trabajo ejecutado (total)\"",
                                     "sustituir": "\"Trabajo ejecutado con efecto acreditado (total)\""},
    }
    base.update(cambios)
    return base


def _tarea_sustituir(**cambios):
    base = {
        "fichero": str(PLANO / "observatorio.py"),
        "operacion": "sustituir_texto",
        "buscar": "\"Trabajo ejecutado (total)\"",
        "sustituir": "\"Trabajo ejecutado con efecto acreditado (total)\"",
    }
    base.update(cambios)
    return base


def test_tarea_que_coincide_en_todo_corresponde():
    assert ct.corresponde_tarea_a_contrato(_tarea_sustituir(), _contrato_sustituir()) is True


def test_tarea_sobre_otro_fichero_no_corresponde(tmp_path):
    otro = tmp_path / "otro.py"
    otro.write_text("# nada\n")
    tarea = _tarea_sustituir(fichero=str(otro))
    assert ct.corresponde_tarea_a_contrato(tarea, _contrato_sustituir()) is False


def test_tarea_sobre_fichero_declarado_fuera_de_alcance_no_corresponde():
    contrato = _contrato_sustituir(perimetro={
        "modificables": [str(PLANO / "observatorio.py")],
        "fuera_de_alcance": [str(PLANO / "observatorio.py")],
    })
    assert ct.corresponde_tarea_a_contrato(_tarea_sustituir(), contrato) is False


def test_tarea_con_buscar_manipulado_no_corresponde():
    """Si el `buscar` de la tarea no es el que el contrato autorizo, no corresponde -aunque el
    fichero y la operacion coincidan-. Esto es lo que detecta una tarea alterada entre planificacion
    y ejecucion."""
    tarea = _tarea_sustituir(buscar="\"otra cosa por completo\"")
    assert ct.corresponde_tarea_a_contrato(tarea, _contrato_sustituir()) is False


def test_tarea_con_sustituir_manipulado_no_corresponde():
    tarea = _tarea_sustituir(sustituir="\"un texto que el contrato nunca autorizo\"")
    assert ct.corresponde_tarea_a_contrato(tarea, _contrato_sustituir()) is False


def test_tarea_con_operacion_distinta_a_la_regla_no_corresponde():
    tarea = _tarea_sustituir(operacion="eliminar_codigo_muerto", buscar=None, sustituir=None)
    assert ct.corresponde_tarea_a_contrato(tarea, _contrato_sustituir()) is False


def test_regla_que_exige_inferencia_nunca_corresponde_a_ninguna_tarea():
    contrato = _contrato_sustituir(regla_de_transformacion=ct.REQUIERE_INFERENCIA)
    assert ct.corresponde_tarea_a_contrato(_tarea_sustituir(), contrato) is False


def test_regla_en_prosa_de_eliminar_codigo_muerto_corresponde_sin_buscar_ni_sustituir():
    contrato = {
        "perimetro": {"modificables": [str(PLANO / "review.py")], "fuera_de_alcance": []},
        "regla_de_transformacion": "es_eliminable() decide, quitar_simbolo() ejecuta",
    }
    tarea = {"fichero": str(PLANO / "review.py"), "operacion": "eliminar_codigo_muerto",
              "buscar": None, "sustituir": None}
    assert ct.corresponde_tarea_a_contrato(tarea, contrato) is True


def test_regla_en_prosa_no_corresponde_si_la_tarea_lleva_buscar_o_sustituir():
    """Una eliminacion no lleva texto de sustitucion: si lo lleva, no es la misma operacion que
    autorizo la regla en prosa, aunque el nombre de la operacion coincida."""
    contrato = {
        "perimetro": {"modificables": [str(PLANO / "review.py")], "fuera_de_alcance": []},
        "regla_de_transformacion": "es_eliminable() decide, quitar_simbolo() ejecuta",
    }
    tarea = {"fichero": str(PLANO / "review.py"), "operacion": "eliminar_codigo_muerto",
              "buscar": "algo", "sustituir": None}
    assert ct.corresponde_tarea_a_contrato(tarea, contrato) is False


def test_contrato_sin_modificables_declarados_nunca_corresponde():
    contrato = _contrato_sustituir(perimetro={"modificables": [], "fuera_de_alcance": []})
    assert ct.corresponde_tarea_a_contrato(_tarea_sustituir(), contrato) is False


def test_tarea_sin_fichero_nunca_corresponde():
    tarea = _tarea_sustituir(fichero=None)
    assert ct.corresponde_tarea_a_contrato(tarea, _contrato_sustituir()) is False


def test_entradas_no_diccionario_fallan_cerrado():
    assert ct.corresponde_tarea_a_contrato(None, _contrato_sustituir()) is False
    assert ct.corresponde_tarea_a_contrato(_tarea_sustituir(), None) is False
    assert ct.corresponde_tarea_a_contrato([], {}) is False
