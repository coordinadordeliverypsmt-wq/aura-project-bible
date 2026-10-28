"""F5 — el puente: una capacidad que cumple el contrato **y esta autorizada** se vuelve trabajo.

## Que resuelve, y que NO

El `CONTRATO-DE-CAPACIDAD` sabe decir si una capacidad esta suficientemente especificada. Lo que
faltaba era la consecuencia: que decir «implementable» sirviera de algo. F5 es exactamente esa
consecuencia y **nada mas**. No crea capacidades, no completa especificaciones, no decide que
significa una capacidad, no inventa perimetros y no fabrica ejecutores.

## Por que no es una autorizacion global

La evaluacion es **por capacidad**, y las nueve condiciones se comprueban una a una contra los
mecanismos que ya existen: `fuente_verificable()`, `zona_permitida()`, el acta del log,
`_EJECUTORES_CONSTRUIDOS` y `_MATERIA_RESERVADA`. Que F5 exista no autoriza nada: cada capacidad
tiene que pasar las nueve por su cuenta, y hoy **ninguna del plan las pasa**.

La consecuencia practica, y es la correcta: como el ejecutor real es hoy `eliminar_codigo_muerto` y
el acta delega solo eso, F5 **no puede producir trabajo fuera de la autoridad vigente**. Amplia lo
que AURA puede *emprender*, no lo que puede *tocar*.
"""

import pathlib

import contrato as ct
import descubrimiento as des
import formacion as fm
import review as rv

PLANO = pathlib.Path(__file__).parent
RAIZ = PLANO.resolve().parents[1]


def _completo(**cambios):
    """Un contrato que pasa las nueve condiciones. Es un **fixture**, no una capacidad real: no se
    registra en el plan, no se ejecuta y no existe fuera de estas pruebas."""
    base = {
        "id": "FIXTURE-1", "nombre": "capacidad de prueba", "version": "1", "estado": "AUTORIZADA",
        "intencion": "ejercitar el contrato sin inventar una capacidad",
        "entradas": [{"nombre": "fichero", "fuente": str(PLANO / "review.py"), "formato": "py"}],
        "salidas": [{"resultado": "simbolo retirado", "destino": str(PLANO / "review.py")}],
        "regla_de_transformacion": "es_eliminable() decide, quitar_simbolo() ejecuta",
        "fuentes_de_verdad": {"autoridad": [str(PLANO / "autoconstruccion.py")], "referencia": []},
        "perimetro": {"modificables": [str(PLANO / "review.py")], "fuera_de_alcance": []},
        "autoridad": {"nivel": "REVIEW", "acta": "DEC-ORCH-2",
                      "parte_de_aura": "ejecutar", "parte_del_ceo": "autorizar"},
        "ejecutor": {"verbo": "eliminar_codigo_muerto"},
        "efectos": {"permitidos": ["retirar un simbolo"], "prohibidos": [], "reversible": True},
        "verificacion": {"invariantes": ["INV-9"],
                         "pruebas_minimas": [str(PLANO / "test_red_autoconstruccion.py")],
                         "criterio_de_aceptacion": "el simbolo ya no consta",
                         "evidencia": "cambio_aplicado con efecto_verificado"},
        "trazabilidad": {"especificacion": "fixture", "autorizacion": "DEC-ORCH-2"},
    }
    base.update(cambios)
    return base


# ------------------------------------------------------------- las ocho barreras exigidas --

def test_A_capacidad_declarada_pero_incompleta_queda_bloqueada():
    r = ct.evaluar({"id": "X", "nombre": "solo un nombre"}, directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert "regla_de_transformacion" in r["faltantes"]


def test_B_capacidad_completa_pero_NO_autorizada_queda_bloqueada():
    """El acta citada no consta en el log: no hay permiso, hay intencion."""
    r = ct.evaluar(_completo(autoridad={"nivel": "REVIEW", "acta": "ACTA-QUE-NO-EXISTE",
                                        "parte_de_aura": "-", "parte_del_ceo": "-"}),
                   directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert any("acta" in b for b in r["bloqueos"])


def test_C_capacidad_fuera_de_perimetro_queda_bloqueada():
    fuera = str(RAIZ / "walking-skeleton" / "aura_skeleton" / "composicion.py")
    r = ct.evaluar(_completo(perimetro={"modificables": [fuera], "fuera_de_alcance": []}),
                   directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert any("zona" in b for b in r["bloqueos"])


def test_D_capacidad_sin_ejecutor_real_queda_bloqueada():
    r = ct.evaluar(_completo(ejecutor={"verbo": "un_verbo_sin_ejecutor"}), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert any("ejecutor" in b for b in r["bloqueos"])


def test_E_capacidad_completa_autorizada_en_perimetro_y_con_ejecutor_es_implementable():
    r = ct.evaluar(_completo(), directorio=PLANO)
    assert r["estado"] == ct.IMPLEMENTABLE, f"{r['faltantes']} · {r['bloqueos']}"


def test_F_materia_reservada_queda_bloqueada():
    r = ct.evaluar(_completo(ejecutor={"verbo": "modificar_adr"}), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert any("reservada" in b for b in r["bloqueos"])


def test_G_con_kill_switch_armado_no_se_ejecuta(tmp_path):
    """F5 no toca el kill switch: sigue siendo el motor quien para. Se comprueba que la barrera
    existe donde ya estaba, no que F5 la duplique."""
    import orquestador as orq
    orq.ruta_parada(tmp_path).write_text("", encoding="utf-8")
    assert orq.parada_solicitada(tmp_path) is True


def test_H_la_capacidad_010_sigue_bloqueada():
    ops = {o.detalle["numero"]: o for o in fm.formacion(PLANO, PLANO)}
    assert ops["010"].estado == des.DECISION_REQUIRED
    assert ops["010"].autoridad == "CEO"


# --------------------------------------- por que todavia no hay primera evolucion real --

def test_las_capacidades_del_plan_siguen_sin_contrato_y_por_eso_no_se_construyen():
    """**El bloqueo estructural, medido.** Las capacidades del plan exigen un verbo constructivo; el
    unico ejecutor que existe es sustractivo. La interseccion es vacia, asi que no hay candidata
    elegible — y no por falta de busqueda, sino por aritmetica.

    Es un tripwire: el dia que el CEO autorice un ejecutor constructivo, esta prueba falla y obliga a
    revisar la frontera en vez de cruzarla en silencio."""
    del_plan = [o for o in fm.formacion(PLANO, PLANO)
                if o.detalle.get("estado_en_el_plan") != "con contrato"]
    assert del_plan, "el plan sigue teniendo capacidades"
    for o in del_plan:
        assert ct.contrato_de(o.detalle["numero"]) is None
        assert o.detalle["contrato"] == "SIN_CONTRATO"


def test_el_ejecutor_de_autoconstruccion_solo_sabe_QUITAR():
    """La otra mitad del bloqueo: el circuito gobernado sabe aplicar un cambio, releerlo, verificarlo
    y revertirlo —toda la maquinaria esta—, pero la unica transformacion cableada es `quitar_simbolo`.
    Falta el **vocabulario del plan de cambio**, no la maquinaria."""
    import autoconstruccion as ac
    assert hasattr(ac, "quitar_simbolo")
    for constructivo in ("insertar_simbolo", "anadir_simbolo", "escribir_simbolo", "generar"):
        assert not hasattr(ac, constructivo), f"apareceria {constructivo}: revisa la frontera"


# ------------------------------------------------- 15 · seguridad contra autoexpansion --

def test_F5_no_puede_tocar_la_gobernanza():
    for prohibido in ("adr/0003-listas-autonomia-hitl.md", "CLAUDE.md",
                      "docs/libro-05-seguridad-y-confianza/5.3-autonomia-gobernada-hitl.md",
                      "entorno/control-plane/politica-orquestador.toml"):
        r = ct.evaluar(_completo(perimetro={"modificables": [str(RAIZ / prohibido)],
                                            "fuera_de_alcance": []}), directorio=PLANO)
        assert r["estado"] == ct.BLOQUEADA, f"{prohibido} no puede entrar en perimetro"


def test_F5_no_amplia_la_autoridad_mas_alla_del_acta():
    """Lo que crecio, crecio por `DR-D`. Lo que nunca crece sin acta sigue igual."""
    assert set(rv.TODO_LO_DELEGABLE) == set(rv._EJECUTORES_CONSTRUIDOS), (
        "nada delegable sin ejecutor construido, y nada construido sin delegar")
    assert len(rv._MATERIA_RESERVADA) == 10
    assert rv.REVIEW_HABILITADO is False


def test_el_evaluador_es_de_solo_lectura():
    import inspect
    fuente = inspect.getsource(ct)
    for prohibido in ("write_text", "registrar_evento", "subprocess", "unlink", "os.remove"):
        assert prohibido not in fuente, f"el evaluador no puede {prohibido}"


def test_una_ruta_inexistente_en_el_perimetro_bloquea():
    r = ct.evaluar(_completo(perimetro={"modificables": [str(PLANO / "no_existe.py")],
                                        "fuera_de_alcance": []}), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA


def test_una_regla_que_exige_inferencia_bloquea():
    r = ct.evaluar(_completo(regla_de_transformacion=ct.REQUIERE_INFERENCIA), directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA
    assert any("inferencia" in b for b in r["bloqueos"])


def test_un_efecto_irreversible_bloquea():
    r = ct.evaluar(_completo(efectos={"permitidos": [], "prohibidos": [], "reversible": False}),
                   directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA


def test_sin_pruebas_minimas_bloquea():
    r = ct.evaluar(_completo(verificacion={"invariantes": [], "pruebas_minimas": [],
                                           "criterio_de_aceptacion": "x", "evidencia": "y"}),
                   directorio=PLANO)
    assert r["estado"] == ct.BLOQUEADA


# ------------------------------------------------------------------ el puente en el ciclo --

# ------------------------------------------------- F4 · la fuente de verdad del contrato --

def test_los_contratos_viven_fuera_de_la_zona_escribible_de_AURA():
    """La eleccion de `F4`: frontera estructural, no guardia. Si el contrato viviera en
    `entorno/control-plane/`, AURA podria escribir el suyo y concederse trabajo."""
    import autoconstruccion as ac
    assert ac.zona_permitida(ct.CONTRATOS) is False
    assert "milestones" in ct.CONTRATOS.parts


def test_contrato_de_lee_del_directorio_de_contratos(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "CONTRATOS", tmp_path)
    (tmp_path / "FIXTURE-2.toml").write_text('id = "FIXTURE-2"\nnombre = "x"\n', encoding="utf-8")
    assert ct.contrato_de("FIXTURE-2")["id"] == "FIXTURE-2"
    assert ct.contrato_de("NO-EXISTE") is None


def test_N_un_toml_ilegible_cuenta_como_ausente(tmp_path, monkeypatch):
    """Fail-closed: un fichero corrupto no pasa por contrato, y no hay segundo sitio donde mirar."""
    monkeypatch.setattr(ct, "CONTRATOS", tmp_path)
    (tmp_path / "ROTO.toml").write_text("esto no es toml [[[", encoding="utf-8")
    assert ct.contrato_de("ROTO") is None


def test_N_una_sola_fuente_de_verdad_y_una_sola_barrera():
    """Sin respaldo silencioso entre ubicaciones, y sin copia local de `_INTOCABLES`."""
    import inspect
    import orquestador as orq
    fuente = inspect.getsource(ct)
    assert not hasattr(ct, "_NUNCA_EN_PERIMETRO"), "la barrera no puede duplicarse"
    assert "orq._INTOCABLES" in fuente, "la barrera se consulta, no se copia"
    assert fuente.count("CONTRATOS /") == 1, "una sola ubicacion, sin fallback"
    assert "politica-orquestador.toml" in orq._INTOCABLES


def test_J_una_candidata_con_contrato_completo_es_implementable():
    assert ct.evaluar(_completo(), directorio=PLANO)["estado"] == ct.IMPLEMENTABLE


def test_K_una_candidata_valida_entra_en_trabajo_autonomo(tmp_path, monkeypatch):
    """El recorrido completo del puente, con un contrato **en fichero**, no en memoria."""
    monkeypatch.setattr(ct, "CONTRATOS", tmp_path)
    monkeypatch.setattr(ct, "contrato_de", lambda n: _completo() if n == "013" else None)
    ops = {o.detalle["numero"]: o for o in fm.formacion(PLANO, PLANO)}
    assert ops["013"].estado == des.OPORTUNIDAD_REAL
    assert ops["013"].detalle["contrato"] == ct.IMPLEMENTABLE
    assert ops["010"].estado == des.DECISION_REQUIRED, "010 no se contagia"


def test_L_el_trabajo_autonomo_pasa_por_el_circuito_existente(monkeypatch):
    """No hay ruta paralela: la oportunidad la convierte en tarea el planificador de siempre."""
    import planificador as pl
    monkeypatch.setattr(ct, "contrato_de", lambda n: _completo() if n == "013" else None)
    op = next(o for o in fm.formacion(PLANO, PLANO) if o.detalle["numero"] == "013")
    tarea = pl.a_tarea(op)
    assert tarea is not None, "una OPORTUNIDAD_REAL tiene que poder planificarse"
    assert tarea["accion"] == op.accion


def test_ninguna_capacidad_DEL_PLAN_tiene_contrato():
    """`F4` sigue abierta: donde vive el contrato de cada capacidad no esta decidido. Mientras no lo
    este, `contrato_de()` devuelve None y **todas** siguen elevandose. Ausencia declarada, no hueco."""
    for o in fm.formacion(PLANO, PLANO):
        if o.detalle.get("estado_en_el_plan") == "con contrato":
            continue
        assert ct.contrato_de(o.detalle["numero"]) is None
        assert o.estado == des.DECISION_REQUIRED


def test_el_puente_convierte_en_trabajo_solo_lo_implementable(monkeypatch):
    """La unica linea que cambia la clase de la maquina, ejercida con un fixture."""
    monkeypatch.setattr(ct, "contrato_de", lambda n: _completo() if n == "010" else None)
    ops = {o.detalle["numero"]: o for o in fm.formacion(PLANO, PLANO)}
    assert ops["010"].estado == des.OPORTUNIDAD_REAL
    assert ops["011"].estado == des.DECISION_REQUIRED


def test_el_puente_no_convierte_lo_bloqueado(monkeypatch):
    roto = _completo(ejecutor={"verbo": "un_verbo_sin_ejecutor"})
    monkeypatch.setattr(ct, "contrato_de", lambda n: roto if n == "010" else None)
    ops = {o.detalle["numero"]: o for o in fm.formacion(PLANO, PLANO)}
    assert ops["010"].estado == des.DECISION_REQUIRED
