"""`DR-F-3d-4` — A3 + B2, aprobadas por el CEO tras el diagnóstico de `DR-F-3d-3`.

**A3 · consistencia.** Deja de ser un booleano ciego. Quien propone **enumera qué decisiones aplican
a este cambio** —el precedente es `5.3:113`, donde el CTO acreditó consistencia contra
*«ADR-0001/0004, guardrails de 2.4, permisos D4/D9 y P-ARQ»*, no contra «todas»— y el sistema
verifica **solo las que tienen fuente objetiva**. Lo demás se marca, no se aprueba. Una referencia a
una decisión que no existe es fail-closed: citar autoridad inexistente es peor que no citarla.

**B2 · D21.** Las cinco preguntas de largo plazo siguen protegiendo decisiones estratégicas. Una
tarea técnica acotada dentro de un alcance ya aprobado no las exige. La clasificación **no se
inventa**: `TODO_LO_DELEGABLE` se define en el propio código como *«acciones técnicas, reversibles y
del plano de desarrollo»*, y esa es la fuente. Lo que no pueda demostrarse acotado, no lo es.
"""

from __future__ import annotations

import review as rv

RESERVADA = "modificar_adr"
TECNICA = "eliminar_codigo_muerto"
REAL = "entorno/control-plane/review.py"


def _tarea(**kw):
    base = {"accion": TECNICA, "fichero": REAL, "cambia_alcance": False,
            "materia_reservada": False}
    base.update(kw)
    return base


# ------------------------------------------------------- A3 · la lista explícita --

def test_una_bandera_autodeclarada_no_produce_consistencia_verificada():
    """El defecto original: `respeta_decisiones: True` concedía el criterio sin comprobar nada."""
    juicio = rv.aplicar_criterios(_tarea(respeta_decisiones=True))
    assert "consistencia" not in juicio["verificados"], (
        "una declaración no puede valer como verificación")


def test_una_decision_con_fuente_objetiva_se_verifica():
    juicio = rv.aplicar_criterios(
        _tarea(decisiones_aplicables=("D22-materia-reservada", "D22-alcance-delegable")))
    assert juicio["decisiones"]["D22-materia-reservada"] == rv.VERIFICADO
    assert juicio["decisiones"]["D22-alcance-delegable"] == rv.VERIFICADO
    assert "consistencia" in juicio["verificados"]
    assert juicio["cumple"] is True


def test_una_decision_con_fuente_objetiva_puede_FALLAR():
    """Verificar de verdad significa poder decir que no."""
    juicio = rv.aplicar_criterios(
        _tarea(accion=RESERVADA, decisiones_aplicables=("D22-materia-reservada",)))
    assert juicio["decisiones"]["D22-materia-reservada"] == rv.INCUMPLIDA
    assert "consistencia" in juicio["fallos"]
    assert juicio["cumple"] is False


def test_una_decision_real_pero_no_mecanizable_requiere_revision_humana():
    """`ADR-0001` existe y es vinculante, pero es prosa: ninguna función la comprueba."""
    juicio = rv.aplicar_criterios(_tarea(decisiones_aplicables=("ADR-0001",)))
    assert juicio["decisiones"]["ADR-0001"] == rv.REQUIERE_REVISION_HUMANA
    assert "consistencia" not in juicio["verificados"], "no se verificó: se marcó"
    assert "consistencia" in juicio["declarados"]


def test_una_decision_inexistente_es_fail_closed():
    """Citar autoridad que no existe es peor que no citarla."""
    juicio = rv.aplicar_criterios(_tarea(decisiones_aplicables=("ADR-9999",)))
    assert juicio["decisiones"]["ADR-9999"] == rv.INCUMPLIDA
    assert "consistencia" in juicio["fallos"]
    assert juicio["cumple"] is False


def test_una_declaracion_optimista_nunca_convierte_unknown_en_pass():
    """Aunque se declare todo bien, una decisión no mecanizable sigue sin estar verificada."""
    juicio = rv.aplicar_criterios(
        _tarea(respeta_decisiones=True, decisiones_aplicables=("ADR-0001",)))
    assert "consistencia" not in juicio["verificados"]
    assert juicio["decisiones"]["ADR-0001"] == rv.REQUIERE_REVISION_HUMANA


def test_una_lista_mixta_no_se_verifica_por_la_parte_buena():
    """Una decisión verificada no legitima a las que no lo están."""
    juicio = rv.aplicar_criterios(
        _tarea(decisiones_aplicables=("D22-materia-reservada", "ADR-0001")))
    assert juicio["decisiones"]["D22-materia-reservada"] == rv.VERIFICADO
    assert juicio["decisiones"]["ADR-0001"] == rv.REQUIERE_REVISION_HUMANA
    assert "consistencia" not in juicio["verificados"]


def test_la_lista_de_decisiones_viaja_en_el_expediente():
    """A3 exige transportarla; `Expediente.criterios` ya es la estructura que lo hace."""
    import revisores as rev
    e = rev.Expediente("T-1", TECNICA, REAL, "x",
                       {"decisiones_aplicables": ("D22-materia-reservada",)})
    assert e.como_dict()["criterios"]["decisiones_aplicables"] == ("D22-materia-reservada",)


# ------------------------------------------------------------------ B2 · D21 --

def test_una_tarea_tecnica_acotada_no_exige_las_cinco_preguntas():
    """B2: dentro de alcance aprobado, técnica, reversible y no reservada."""
    juicio = rv.aplicar_criterios(_tarea())
    assert "cinco_preguntas_d21" in juicio["no_aplica"]
    assert "cinco_preguntas_d21" not in juicio["fallos"]
    assert juicio["cumple"] is True, "una tarea acotada no queda bloqueada por D21"


def test_una_decision_estrategica_SIGUE_exigiendo_D21():
    """B2 no toca el gate: lo que no es tarea acotada sigue necesitando las cinco preguntas."""
    juicio = rv.aplicar_criterios(_tarea(accion="seleccionar_tecnologia"))
    assert "cinco_preguntas_d21" not in juicio["no_aplica"]
    assert "cinco_preguntas_d21" in juicio["fallos"], "sin respuesta afirmativa, no pasa"


def test_una_accion_desconocida_no_se_presume_acotada():
    """Si no puede demostrarse acotada, no lo es. Fail-closed sobre la clasificación."""
    juicio = rv.aplicar_criterios(_tarea(accion="refactorizar_el_nucleo"))
    assert "cinco_preguntas_d21" not in juicio["no_aplica"]
    assert "cinco_preguntas_d21" in juicio["fallos"]


def test_una_estrategica_con_las_cinco_afirmativas_pasa_ese_criterio():
    juicio = rv.aplicar_criterios(
        _tarea(accion="desplegar_a_produccion", d21_afirmativas=True))
    assert "cinco_preguntas_d21" not in juicio["fallos"]


def test_el_alcance_del_acta_manda_sobre_la_clasificacion(tmp_path):
    """Con acta, la pertenencia al alcance se mide contra ella."""
    rv.habilitar(tmp_path, por="ceo", acta="DEC-ORCH-2", alcance=())
    juicio = rv.aplicar_criterios(_tarea(), directorio=tmp_path)
    assert "cinco_preguntas_d21" not in juicio["no_aplica"], (
        "fuera del alcance del acta no es tarea acotada")


# --------------------------------------------------- lo que no puede moverse --

def test_la_materia_reservada_se_rechaza_pase_lo_que_pase():
    """Independiente de la evidencia de consistencia y de D21."""
    juicio = rv.aplicar_criterios(
        _tarea(accion=RESERVADA, materia_reservada=False, d21_afirmativas=True,
               decisiones_aplicables=("D22-alcance-delegable",)))
    assert "materia_reservada" in juicio["fallos"]
    assert juicio["cumple"] is False


def test_el_alcance_se_sigue_verificando_objetivamente():
    juicio = rv.aplicar_criterios(_tarea(accion="borrar_todo", cambia_alcance=False))
    assert "alcance" in juicio["verificados"]
    assert "alcance" in juicio["fallos"]


def test_este_trabajo_no_amplia_autoridad():
    import agentes
    import revisores as rev
    assert rv.REVIEW_HABILITADO is False
    assert rv.TODO_LO_DELEGABLE == ("eliminar_codigo_muerto",)
    assert len(rv._MATERIA_RESERVADA) == 10
    assert rv.CRITERIOS_D22 == ("alcance", "consistencia", "cinco_preguntas_d21",
                                "materia_reservada")
    assert agentes._EJECUTORES["claude"](sobre="x").exit_code == 127
    assert rev.RevisorLocal().disponible() is False
    assert "autoriza" not in rev.Veredicto.__dataclass_fields__


def test_el_modulo_no_ejecuta_ni_habla_con_la_red():
    import ast
    import pathlib
    arbol = ast.parse((pathlib.Path(__file__).parent / "review.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                assert alias.name.split(".")[0] not in {"subprocess", "socket", "urllib", "http"}
        elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in {"eval", "exec", "compile"}


# ------------------------------------------- lo que la mutación demostró que faltaba --

def test_la_materia_reservada_no_es_acotada_ni_aunque_entrase_en_el_catalogo(monkeypatch):
    """Defensa en profundidad. Hoy ninguna acción reservada está en `TODO_LO_DELEGABLE`, así que la
    comprobación parece redundante — y por eso el mutante que la borraba sobrevivía. No lo es: el día
    que un acta delegase por error algo reservado, esta guarda es la que impide que esquive `D21`."""
    monkeypatch.setattr(rv, "TODO_LO_DELEGABLE", (RESERVADA,))
    assert rv.es_tarea_tecnica_acotada({"accion": RESERVADA}) is False
    juicio = rv.aplicar_criterios(_tarea(accion=RESERVADA))
    assert "cinco_preguntas_d21" not in juicio["no_aplica"]


def test_el_planificador_enumera_decisiones_y_no_firma_en_blanco():
    """`A3` en la única ruta que las produce de verdad. El mutante que devolvía
    `respeta_decisiones: True` al planificador sobrevivía porque ninguna prueba lo miraba."""
    import descubrimiento as des
    import planificador as plan
    import pathlib
    aqui = pathlib.Path(__file__).resolve().parent
    o = des.Oportunidad(
        id="OP-1", fuente=f"{aqui / 'review.py'}:1",
        alcance="entorno/control-plane/review.py", accion=TECNICA,
        estado=des.OPORTUNIDAD_REAL, justificacion="j",
        detalle={"simbolo": "x", "forma": "funcion", "linea": 1}, riesgo="bajo",
        autoridad="ceo", criterio_de_finalizacion={"c": 1}, evidencia_requerida={"e": 1})
    tarea = plan.a_tarea(o)
    assert tarea["decisiones_aplicables"] == plan.DECISIONES_DE_CODIGO_MUERTO
    for constante in ("respeta_decisiones", "d21_afirmativas", "cambia_alcance",
                      "materia_reservada", "reversible"):
        assert constante not in tarea, f"{constante} volvió a ser una firma en blanco"
    juicio = rv.aplicar_criterios(tarea)
    assert "consistencia" in juicio["verificados"], "las decisiones citadas deben verificarse"
    assert juicio["declarados"] == ()


def test_una_comprobacion_que_revienta_no_aprueba(monkeypatch):
    """Fail-closed en el borde raro: si la propia comprobación falla —un dato con forma inesperada,
    un error de programación— el resultado no puede ser «verificado». Un mecanismo roto no concede."""
    def _explota(_tarea):
        raise RuntimeError("la comprobacion esta rota")

    monkeypatch.setitem(rv._COMPROBACIONES, "D22-alcance-delegable", _explota)
    juicio = rv.aplicar_criterios(_tarea(decisiones_aplicables=("D22-alcance-delegable",)))
    assert juicio["decisiones"]["D22-alcance-delegable"] == rv.INCUMPLIDA
    assert "consistencia" in juicio["fallos"]
    assert juicio["cumple"] is False
