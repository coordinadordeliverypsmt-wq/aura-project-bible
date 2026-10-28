"""RED de `DR-E` — **Oportunidad -> Propuesta** generica.

El bloqueo A1 era de forma, no de permiso: el circuito de propuesta solo sabia representar codigo
muerto. `DR-E` construye la representacion que faltaba, y estas pruebas fijan su unica regla dura:

**puede transcribir lo observado; no puede inventar lo que exige juicio.**

Un campo que AURA no sabe se marca `REQUIERE_REVISION_HUMANA`. Rellenarlo con un default semantico
—«riesgo: bajo», «rollback: revertir»— seria fingir capacidad (INV-9), y ademas es exactamente lo que
`autoconstruccion.diagnosticar` hace hoy con su constante «codigo muerto»: por eso `DR-E` no reusa
ese camino, lo generaliza al lado.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import descubrimiento as des
import entorno_disponible as ent
import orquestador as orq
import planificador as plan
import propuesta as prop
import pytest
import review as rv


def _oportunidad(tmp_path, **cambios):
    """Una oportunidad valida cualquiera. La fuente apunta a un fichero que existe de verdad."""
    testigo = tmp_path / "testigo.py"
    testigo.write_text("# fuente verificable\n")
    campos = {
        "id": "OP-test000000",
        "fuente": str(testigo),
        "justificacion": "lo observado, y nada mas",
        "alcance": "un_alcance",
        "accion": "revisar_capacidad_del_entorno",
        "autoridad": "CEO",
        "criterio_de_finalizacion": {"capacidad": "diagnosticar_estado"},
        "evidencia_requerida": {"tipo": "fichero_existe", "patron": str(testigo)},
        "riesgo": "ninguno: solo observacion",
        "estado": des.DECISION_REQUIRED,
        "detalle": {"capacidad": "razonamiento_local"},
    }
    campos.update(cambios)
    return des.Oportunidad(**campos)


def _oportunidad_de_codigo_muerto(tmp_path):
    """La clase que el circuito ya sabia representar: sigue teniendo que funcionar."""
    testigo = tmp_path / "muerto.py"
    testigo.write_text("def _nadie_me_llama():\n    pass\n")
    return des.Oportunidad(
        id="OP-muerto00000", fuente=f"{testigo}:1", justificacion="funcion privada sin llamadas",
        alcance=str(testigo), accion="eliminar_codigo_muerto", autoridad="AUTO",
        criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
        evidencia_requerida={"tipo": "salida_contiene", "patron": "ok"},
        riesgo="bajo", estado=des.OPORTUNIDAD_REAL,
        detalle={"simbolo": "_nadie_me_llama", "forma": "funcion", "linea": 1})


# ------------------------------------------------------------ 1 · el mecanismo generico existe

def test_representa_las_diez_piezas(tmp_path):
    """Las diez que el acta enumera. Ni una menos: una propuesta incompleta obliga a volver a mirar."""
    p = prop.de_oportunidad(_oportunidad(tmp_path))
    for pieza in ("origen", "accion", "evidencia", "fuente", "objeto", "justificacion",
                  "nivel_de_autorizacion", "limites", "requiere_juicio_humano", "estado"):
        assert pieza in p, f"falta la pieza {pieza!r}"


def test_transcribe_la_identidad_y_el_origen(tmp_path):
    op = _oportunidad(tmp_path)
    p = prop.de_oportunidad(op)
    assert p["origen"] == op.id
    assert p["accion"] == op.accion
    assert p["fuente"] == op.fuente
    assert des.fuente_verificable(p["fuente"])


def test_la_justificacion_no_se_reescribe(tmp_path):
    """Se transcribe la de la oportunidad: reformularla seria interpretar, y eso ya es juicio."""
    op = _oportunidad(tmp_path, justificacion="exactamente esto y nada mas")
    assert prop.de_oportunidad(op)["justificacion"] == "exactamente esto y nada mas"


# --------------------------------------------------- 2 · la regla dura: no inventar razonamiento

def test_los_campos_de_juicio_quedan_marcados(tmp_path):
    """El corazon de DR-E. Lo que AURA no sabe se dice, no se rellena."""
    p = prop.de_oportunidad(_oportunidad(tmp_path))
    juicio = p["requiere_juicio_humano"]
    assert juicio, "no hay ningun campo marcado: alguien los relleno"
    for campo in ("riesgo_de_actuar", "criterio_de_rollback", "pruebas_necesarias", "decision"):
        assert juicio[campo] == prop.REQUIERE_REVISION_HUMANA


def test_no_inventa_riesgo_rollback_ni_pruebas(tmp_path):
    """Ningun campo de juicio puede traer un valor plausible: ni «bajo», ni «revertir», ni una lista."""
    juicio = prop.de_oportunidad(_oportunidad(tmp_path))["requiere_juicio_humano"]
    for campo, valor in juicio.items():
        assert valor == prop.REQUIERE_REVISION_HUMANA, f"{campo} trae un valor inventado: {valor!r}"


def test_el_riesgo_declarado_no_se_confunde_con_el_riesgo_de_actuar(tmp_path):
    """La fuente declara el riesgo de *observar*; el de *actuar* no lo sabe nadie todavia."""
    op = _oportunidad(tmp_path, riesgo="ninguno: solo observacion")
    p = prop.de_oportunidad(op)
    assert p["evidencia"]["riesgo_declarado_por_la_fuente"] == "ninguno: solo observacion"
    assert p["requiere_juicio_humano"]["riesgo_de_actuar"] == prop.REQUIERE_REVISION_HUMANA


def test_no_inventa_la_intencion_del_ceo(tmp_path):
    """La propuesta no puede contener un verbo de decision: describe, no recomienda."""
    p = prop.de_oportunidad(_oportunidad(tmp_path))
    texto = str(p).lower()
    for verbo in ("recomiendo", "deberia", "conviene", "propongo conectar", "hay que"):
        assert verbo not in texto, f"la propuesta recomienda ({verbo!r}): eso es juicio"


# ------------------------------------------------------- 3 · nunca autoriza, nunca es ejecutable

def test_nace_sin_autorizar_y_no_hay_forma_de_autorizarla_aqui(tmp_path):
    p = prop.de_oportunidad(_oportunidad(tmp_path))
    assert p["estado"] == "PROPUESTA"
    assert p["autorizada"] is False
    fuente = pathlib.Path(inspect.getfile(prop)).read_text()
    for prohibido in ("propuesta_autorizada", "autorizada\": True", "autorizada=True"):
        assert prohibido not in fuente


def test_no_convierte_HUMAN_en_AUTO(tmp_path):
    """El nivel se **lee** del orquestador, no se decide aqui."""
    op = _oportunidad(tmp_path, accion="revisar_capacidad_del_entorno")
    p = prop.de_oportunidad(op)
    assert p["nivel_de_autorizacion"] == orq.nivel_de(op.accion) == "HUMAN"
    assert p["accion"] not in orq.acciones_de_nivel("AUTO")
    assert p["accion"] not in rv.TODO_LO_DELEGABLE


def test_la_propuesta_no_es_una_tarea_ejecutable(tmp_path):
    """No basta con que no lo sea: no debe tener la forma de una. El motor no puede confundirla."""
    p = prop.de_oportunidad(_oportunidad(tmp_path))
    assert "simbolo" not in p or p.get("simbolo") is None
    assert plan.a_tarea(_oportunidad(tmp_path)) is None


def test_los_limites_se_declaran_como_hechos(tmp_path):
    """Los limites son comprobables, no opiniones: se derivan del estado real del sistema."""
    limites = prop.de_oportunidad(_oportunidad(tmp_path))["limites"]
    assert limites["es_ejecutable_hoy"] is False
    assert limites["en_acciones_AUTO"] is False
    assert limites["en_todo_lo_delegable"] is False


# ------------------------------------------------------------------- 4 · fail-closed y malformadas

def test_una_oportunidad_malformada_no_produce_propuesta(tmp_path):
    """Fail-closed: lo que no es una oportunidad no se representa «lo mejor que se pueda»."""
    for basura in (None, {}, "OP-1234", 42, object()):
        with pytest.raises((TypeError, AttributeError)):
            prop.de_oportunidad(basura)


def test_un_impostor_con_todos_los_atributos_no_pasa(tmp_path):
    """La barrera de procedencia vive en el constructor de `Oportunidad`, y aceptar cualquier cosa
    que *parezca* una oportunidad la rodearia por completo.

    No basta con que la basura evidente falle —eso ocurre solo, al tropezar con un atributo que no
    existe—: lo que hay que impedir es que un objeto **con todos los atributos** y una fuente que no
    lleva a ninguna parte produzca una propuesta impecable. Ese es el unico camino por el que el
    trabajo inventado podria entrar en el circuito."""
    class Impostora:
        id = "OP-falsa000000"
        fuente = "de la nada"
        justificacion = "trabajo inventado con toda la pinta de real"
        alcance = "un_alcance"
        accion = "eliminar_codigo_muerto"
        autoridad = "AUTO"
        criterio_de_finalizacion = {"capacidad": "ejecutar_pruebas"}
        evidencia_requerida = {"tipo": "salida_contiene", "patron": "ok"}
        riesgo = "bajo"
        estado = des.OPORTUNIDAD_REAL
        detalle = {"simbolo": "_x", "forma": "funcion", "linea": 1}

    assert not des.fuente_verificable(Impostora.fuente)
    with pytest.raises(TypeError):
        prop.de_oportunidad(Impostora())


def test_una_oportunidad_sin_procedencia_no_llega_a_construirse(tmp_path):
    """La barrera de `descubrimiento` sigue siendo la primera: no se puede rodear por aqui."""
    with pytest.raises(des.OportunidadSinProcedencia):
        _oportunidad(tmp_path, fuente="de la nada")


def test_no_escribe_nada(tmp_path):
    """`de_oportunidad` es **pura**: no registra eventos. Registrar seria un acto, no una lectura."""
    arbol = ast.parse(pathlib.Path(inspect.getfile(prop)).read_text())
    nombres = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    nombres |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for prohibido in ("registrar_evento", "write_text", "write_bytes", "open", "mkdir",
                      "autorizar", "ejecutar", "transicion"):
        assert prohibido not in nombres, f"la representacion actua: usa {prohibido!r}"


# ------------------------------------------------ 5 · compatibilidad con el flujo de codigo muerto

def test_tambien_representa_una_oportunidad_de_codigo_muerto(tmp_path):
    """Generalizacion: la clase que ya existia tambien cabe, con su objeto afectado."""
    p = prop.de_oportunidad(_oportunidad_de_codigo_muerto(tmp_path))
    assert p["objeto"]["simbolo"] == "_nadie_me_llama"
    assert p["nivel_de_autorizacion"] == orq.nivel_de("eliminar_codigo_muerto")


def test_el_circuito_de_codigo_muerto_sigue_intacto():
    """`DR-E` es una generalizacion **al lado**, no una sustitucion: `proponer` no se ha tocado."""
    import autoconstruccion as ac
    firma = inspect.signature(ac.proponer)
    assert list(firma.parameters) == ["directorio", "hallazgo"]
    cuerpo = inspect.getsource(ac.proponer)
    assert "registrar_evento" in cuerpo          # sigue registrando, como siempre
    assert "propuesta_registrada" in cuerpo


def test_dr_e_no_toca_autoconstruccion():
    """Ni un import cruzado: si `propuesta` importara `autoconstruccion` habria dos caminos a uno."""
    arbol = ast.parse(pathlib.Path(inspect.getfile(prop)).read_text())
    importados = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            importados |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom) and n.module:
            importados.add(n.module.split(".")[0])
    assert "autoconstruccion" not in importados


def test_el_objeto_ausente_es_un_hecho_no_un_hueco(tmp_path):
    """Sin objeto afectado, `objeto` es `None` —un hecho observado—, no `REQUIERE_REVISION_HUMANA`."""
    p = prop.de_oportunidad(_oportunidad(tmp_path, detalle={}))
    assert p["objeto"] is None
    assert p["objeto"] != prop.REQUIERE_REVISION_HUMANA


# ------------------------------------------------------- 6 · el caso concreto: OP-ce4aa5725674

def test_representa_la_capacidad_del_entorno_realmente_observada(tmp_path):
    """El criterio especial del acta, contra el entorno REAL: solo lo que AURA sabe de verdad."""
    descubiertas = ent.entorno(tmp_path, tmp_path)
    if not descubiertas:
        pytest.skip("no hay razonamiento local observable en esta maquina")
    p = prop.de_oportunidad(descubiertas[0])
    assert p["origen"] == descubiertas[0].id
    assert p["accion"] == "revisar_capacidad_del_entorno"
    assert p["nivel_de_autorizacion"] == "HUMAN"
    assert p["autorizada"] is False
    # lo que sabe: la capacidad y sus senales, transcritas
    detalle = p["evidencia"]["detalle"]
    assert detalle["capacidad"] == "razonamiento_local"
    assert detalle["puerto"] == 11434
    assert "qwen2.5:0.5b" in detalle["modelos"]
    # lo que NO sabe: si conectarla
    assert p["requiere_juicio_humano"]["decision"] == prop.REQUIERE_REVISION_HUMANA
    assert p["limites"]["es_ejecutable_hoy"] is False
