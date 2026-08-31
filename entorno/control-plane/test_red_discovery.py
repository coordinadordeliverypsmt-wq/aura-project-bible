"""RED · DISCOVERY -> CLASSIFY -> PROPOSE, con la separacion de autoridad como garantia central.

AURA puede DESCUBRIR trabajo. No puede AUTORIZARSELO. Toda esta bateria existe para que esa frase
sea verificable y no una intencion: el descubridor escribe en `propuestas` y **nunca** en
`tareas_AUTO`, que solo el CEO llena mediante una promocion explicita.
"""
from __future__ import annotations

import control_plane as cp
import pytest


ZONAS = ("aprobar", "prueba_de_autoridad", "m9", "ter", "d-cp-4", "d-cp-5", "d-cp-7",
         "orchestrator", "orquestador", "aura_skeleton", "delegar.sh", "d-cp-8")


def _estado(defectos=(), propuestas=None, auto=()):
    e = cp.estado_inicial()
    e["zonas_bloqueadas_para_discovery"] = list(ZONAS)
    e["defectos"] = list(defectos)
    e["tareas_AUTO"] = list(auto)
    if propuestas is not None:
        e["propuestas"] = list(propuestas)
    return e


DEFECTO = {"id": "DEF-1", "fichero": "x.py", "prueba": "test_x", "apertura": "ABIERTO",
           "fichero_de_trabajo": "modulo_x.py",     # ANADIDO: sin el, nada es AUTO_EXECUTABLE
           "descripcion": "una prueba roja con contrato determinado"}


# ============================================================ DESCUBRIMIENTO --


def test_descubre_un_defecto_registrado_abierto():
    hallazgos = cp.descubrir(_estado(defectos=[DEFECTO]))
    assert any(h["origen"] == "defecto" and h["ref"] == "DEF-1" for h in hallazgos)


def test_descubre_una_red_roja_medida():
    """La evidencia se INYECTA: el descubridor clasifica, no mide. Quien mide es quien ejecuta."""
    ev = {"reds_rojas": [{"nodeid": "test_red_x.py::test_y", "motivo": "AttributeError"}]}
    hallazgos = cp.descubrir(_estado(), evidencia=ev)
    assert any(h["origen"] == "red_roja" for h in hallazgos)


def test_descubre_un_mutante_superviviente_medido():
    ev = {"mutantes_supervivientes": [{"id": "M7", "bateria": "cp-g3.toml"}]}
    hallazgos = cp.descubrir(_estado(), evidencia=ev)
    assert any(h["origen"] == "mutante_superviviente" for h in hallazgos)


def test_no_inventa_trabajo_cuando_no_hay_evidencia():
    """**La garantia que impide fabricar ocupacion.** Sin evidencia, cero hallazgos."""
    assert cp.descubrir(_estado()) == []


def test_descubrir_NUNCA_modifica_tareas_auto():
    """El corazon de la separacion de autoridad, comprobado por igualdad exacta."""
    e = _estado(defectos=[DEFECTO], auto=[{"id": "YA-AUTORIZADA"}])
    antes = list(e["tareas_AUTO"])
    cp.descubrir(e, evidencia={"reds_rojas": [{"nodeid": "a::b", "motivo": "x"}]})
    assert e["tareas_AUTO"] == antes


def test_descubrir_es_idempotente_y_no_duplica_propuestas():
    e = _estado(defectos=[DEFECTO])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    n = len(e["propuestas"])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    assert len(e["propuestas"]) == n


# ================================================================ CLASIFICACION --


def test_un_hallazgo_determinado_es_AUTO_EXECUTABLE():
    # `fichero_de_trabajo` ANADIDO 2026-08-25 (DEC-ZONA-POR-FICHERO-DE-TRABAJO): sin saber que
    # fichero habria que tocar no se puede comprobar en que zona cae el trabajo, y esa ignorancia
    # dejo de valer como permiso. El veredicto que esta prueba mide NO cambia.
    h = {"origen": "defecto", "ref": "DEF-1", "fichero": "x.py", "prueba": "test_x",
         "fichero_de_trabajo": "modulo_x.py", "determinado_por": "contrato existente"}
    assert cp.clasificar(h, _estado()) == "AUTO_EXECUTABLE"


def test_un_hallazgo_sin_procedimiento_inequivoco_es_PROPOSAL_ONLY():
    h = {"origen": "mutante_superviviente", "ref": "M7", "determinado_por": None,
         "resoluciones_posibles": 2}
    assert cp.clasificar(h, _estado()) == "PROPOSAL_ONLY"


def test_lo_que_toca_zona_bloqueada_es_DECISION_REQUIRED():
    for zona in ("aprobar", "M9", "D-CP-4", "orchestrator", "aura_skeleton"):
        h = {"origen": "red_roja", "ref": f"test::{zona}", "fichero": f"{zona}.py",
             "determinado_por": "contrato existente"}
        assert cp.clasificar(h, _estado()) == "DECISION_REQUIRED", zona


def test_ante_la_duda_la_clasificacion_es_DECISION_REQUIRED():
    """**Fail-closed.** Un hallazgo que no se entiende no puede degradar en permiso."""
    assert cp.clasificar({}, _estado()) == "DECISION_REQUIRED"
    assert cp.clasificar({"origen": "desconocido"}, _estado()) == "DECISION_REQUIRED"
    # Y sin lista de zonas declarada, TODO es DECISION_REQUIRED: no poder comprobar si algo esta
    # bloqueado no equivale a saber que no lo esta.
    h = {"origen": "defecto", "ref": "DEF-9", "determinado_por": "contrato existente"}
    assert cp.clasificar(h, cp.estado_inicial()) == "DECISION_REQUIRED"


# ==================================================================== PROMOCION --


def test_promover_es_la_UNICA_via_hacia_tareas_auto():
    e = _estado(defectos=[DEFECTO])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    assert e["tareas_AUTO"] == []
    e = cp.promover_a_auto(e, e["propuestas"][0]["id"], aprobado_por="ceo")
    assert len(e["tareas_AUTO"]) == 1


def test_no_se_promueve_un_DECISION_REQUIRED():
    e = _estado()
    e = cp.registrar_propuestas(e, cp.descubrir(
        e, evidencia={"reds_rojas": [{"nodeid": "test::aprobar", "motivo": "x", "fichero": "aprobar.py"}]}))
    with pytest.raises(cp.PromocionInvalida):
        cp.promover_a_auto(e, e["propuestas"][0]["id"], aprobado_por="ceo")
    assert e["tareas_AUTO"] == []


def test_no_se_promueve_un_PROPOSAL_ONLY_sin_aprobacion_expresa():
    e = _estado()
    e = cp.registrar_propuestas(e, cp.descubrir(
        e, evidencia={"mutantes_supervivientes": [{"id": "M7", "bateria": "b.toml"}]}))
    with pytest.raises(cp.PromocionInvalida):
        cp.promover_a_auto(e, e["propuestas"][0]["id"], aprobado_por="ceo")
    e2 = cp.promover_a_auto(e, e["propuestas"][0]["id"], aprobado_por="ceo",
                            aprobacion_expresa=True)
    assert len(e2["tareas_AUTO"]) == 1


def test_la_trazabilidad_hallazgo_propuesta_tarea_queda_registrada():
    e = _estado(defectos=[DEFECTO])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    pid = e["propuestas"][0]["id"]
    e = cp.promover_a_auto(e, pid, aprobado_por="ceo")
    tarea = e["tareas_AUTO"][0]
    assert tarea["origen_propuesta"] == pid
    assert tarea["aprobado_por"] == "ceo"
    assert e["propuestas"][0]["estado"] == "PROMOVIDA"


def test_una_promocion_sin_aprobador_no_es_una_decision_humana():
    """ANADIDA por un mutante SUPERVIVIENTE: todas las pruebas pasaban `aprobado_por="ceo"`, asi que
    nada verificaba que el aprobador sea OBLIGATORIO. Sin el, una promocion es anonima — y una
    promocion anonima es exactamente lo que esta separacion de autoridad existe para impedir."""
    e = _estado(defectos=[DEFECTO])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    for vacio in ("", None):
        with pytest.raises(cp.PromocionInvalida):
            cp.promover_a_auto(e, e["propuestas"][0]["id"], aprobado_por=vacio)
    assert e["tareas_AUTO"] == []


def test_si_la_evidencia_desaparece_la_promocion_falla_cerrada():
    """Una propuesta cuya evidencia ya no existe no puede promoverse: seria trabajo fantasma."""
    e = _estado(defectos=[DEFECTO])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    e["defectos"] = []                       # la evidencia se retira
    with pytest.raises(cp.PromocionInvalida):
        cp.promover_a_auto(e, e["propuestas"][0]["id"], aprobado_por="ceo")


# =================================================== CONTENCION: VARIANTES DE NOMBRE --


@pytest.mark.parametrize("variante", ["d-cp-8", "dcp8", "DCP8", "d_cp_8", "D-CP-8", "D CP 8"])
def test_una_zona_bloqueada_se_reconoce_pese_a_las_variantes_de_nombre(variante):
    """**Correccion de contencion, 2026-08-25.** El matching era por substring exacto, asi que
    `'d-cp-8' in 'dcp8_cableado'` daba False y un hallazgo de una zona VETADA se clasificaba como
    AUTO_EXECUTABLE. El repositorio escribe el mismo identificador de varias formas —`dcp8`,
    `d-cp-8`, `DCP8`— y la contencion no puede depender de cual se use.
    """
    h = {"origen": "red_roja", "ref": f"test_{variante}_algo", "fichero": f"{variante}.py",
         "determinado_por": "contrato existente"}
    assert cp.clasificar(h, _estado()) == "DECISION_REQUIRED", variante


def test_el_hallazgo_REAL_de_dcp8_queda_bloqueado():
    """El caso exacto que la validacion destapo: un fichero real del repositorio."""
    h = {"origen": "red_roja", "ref": "test_red_dcp8_cableado.py::test_x",
         "fichero": "test_red_dcp8_cableado.py", "determinado_por": "contrato existente"}
    assert cp.clasificar(h, _estado()) == "DECISION_REQUIRED"


@pytest.mark.parametrize("ajena", ["test_red_evidencia.py", "calculadora.py", "test_hilo.py",
                                    "dcp9_otro.py", "md-cp-8x.py"])
def test_una_zona_DISTINTA_no_queda_bloqueada_por_coincidencia(ajena):
    """**El otro lado del riesgo.** Normalizar de mas convierte la contencion en un bloqueo
    indiscriminado: si todo queda bloqueado, el descubridor deja de servir. `dcp9` y `md-cp-8x` NO
    son `d-cp-8`, y deben pasar."""
    # `prueba` ANADIDA 2026-08-25 con la contencion de DEC-DEFECTO-ESTADO-ESTRUCTURADO. El
    # veredicto esperado NO cambia —sigue siendo AUTO_EXECUTABLE, que es lo que esta prueba mide—;
    # lo que se completa es el hallazgo, que antes omitia un campo que el productor real SIEMPRE
    # rellena: `descubrir()` pone `prueba = nodeid` en todo hallazgo de red_roja. El fixture
    # describia un hallazgo que el mecanismo no puede producir.
    h = {"origen": "red_roja", "ref": f"test::{ajena}", "fichero": ajena,
         "prueba": f"test::{ajena}", "fichero_de_trabajo": ajena,
         "determinado_por": "contrato existente"}
    assert cp.clasificar(h, _estado()) == "AUTO_EXECUTABLE", ajena
