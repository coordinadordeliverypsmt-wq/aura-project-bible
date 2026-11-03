"""El vocabulario constructivo — **no se invento: ya existia y estaba en el plano equivocado**.

`herramientas/mutar.py` lleva meses aplicando transformaciones de codigo de forma gobernada:
`buscar`/`sustituir` exactos, **patron unico** (`contenido.count(buscar)`), rechazo del no-op
(`buscar == sustituir`), aplicacion acotada (`replace(..., 1)`) y **restauracion verificada byte a
byte**. Son exactamente las nueve propiedades que exige una operacion ejecutable. Pero vive en
`walking-skeleton/herramientas/`, es un arnes de pruebas y cruza el plano: no se importa, se
**reimplanta** donde `ejecutar()` ya aporta zona, autorizacion, relectura, verificacion y reversion.

## Lo que este vocabulario NO es

No es un generador. No hay `eval`, ni shell, ni plantillas, ni «ejecuta esta descripcion». El
contrato declara **texto exacto** a buscar y texto exacto con que sustituirlo; el ejecutor comprueba
que el patron aparece **una sola vez** y aplica esa unica sustitucion. Una operacion que no este en
`OPERACIONES` no se interpreta: se rechaza.
"""

import pathlib

import autoconstruccion as ac
import contrato as ct
import pytest
import review as rv

PLANO = pathlib.Path(__file__).parent
RAIZ = PLANO.resolve().parents[1]

_ANTES = "def _uno():\n    return 1\n"
_DESPUES = "def _uno():\n    return 2\n"


# ------------------------------------------------------------------ la operacion, acotada --

def test_el_vocabulario_es_cerrado_y_declarado():
    assert ac.OPERACIONES == ("eliminar_codigo_muerto", "sustituir_texto")


def test_A_una_operacion_desconocida_se_rechaza_sin_interpretarla(tmp_path):
    """Con la propuesta **ya autorizada**, para que el rechazo sea del vocabulario y no del permiso:
    la autorizacion es la puerta mas fuerte y por eso va antes."""
    objetivo = tmp_path / "entorno" / "control-plane" / "m.py"
    objetivo.parent.mkdir(parents=True)
    objetivo.write_text(_ANTES, encoding="utf-8")
    p = ac.proponer(tmp_path, {"fichero": str(objetivo), "operacion": "haz_lo_que_puedas"})
    ac.autorizar(tmp_path, p["id"], por="ceo", acta="acta")
    with pytest.raises(ac.OperacionDesconocida):
        ac.ejecutar(tmp_path, p, autoridad="ceo")


def test_B_una_operacion_incompleta_se_rechaza():
    puede, motivo = ac.es_sustituible(_ANTES, "", "algo")
    assert puede is False and "vacio" in motivo


def test_el_patron_tiene_que_ser_UNICO():
    """Dos apariciones = ambiguedad. Sustituir «la primera» seria elegir por cuenta propia."""
    doble = _ANTES + _ANTES
    puede, motivo = ac.es_sustituible(doble, "return 1", "return 2")
    assert puede is False and "2 veces" in motivo


def test_un_patron_ausente_se_rechaza():
    puede, motivo = ac.es_sustituible(_ANTES, "no_esta_aqui", "x")
    assert puede is False and "no aparece" in motivo


def test_una_sustitucion_que_no_cambia_nada_se_rechaza():
    puede, motivo = ac.es_sustituible(_ANTES, "return 1", "return 1")
    assert puede is False and "identic" in motivo


def test_una_sustitucion_que_rompe_el_fichero_se_rechaza():
    puede, motivo = ac.es_sustituible(_ANTES, "return 1", "return (((")
    assert puede is False and "no compila" in motivo


def test_F_una_sustitucion_valida_es_ejecutable():
    puede, motivo = ac.es_sustituible(_ANTES, "return 1", "return 2")
    assert puede is True, motivo
    assert ac.sustituir_texto(_ANTES, "return 1", "return 2") == _DESPUES


# ------------------------------------------------------------------- gobierno del ejecutor --

def _propuesta_autorizada(tmp_path, contenido=_ANTES, **extra):
    objetivo = tmp_path / "entorno" / "control-plane" / "m.py"
    objetivo.parent.mkdir(parents=True, exist_ok=True)
    objetivo.write_text(contenido, encoding="utf-8")
    p = ac.proponer(tmp_path, {"fichero": str(objetivo), "motivo": "prueba",
                               "operacion": "sustituir_texto",
                               "buscar": "return 1", "sustituir": "return 2", **extra})
    ac.autorizar(tmp_path, p["id"], por='ceo', acta="acta de prueba")
    return objetivo, p


def test_G_la_operacion_valida_se_ejecuta_y_se_verifica_el_efecto(tmp_path):
    objetivo, p = _propuesta_autorizada(tmp_path)
    r = ac.ejecutar(tmp_path, p, autoridad="CEO", verificacion=lambda: True)
    assert r["efecto_verificado"] is True and r["revertido"] is False
    assert objetivo.read_text(encoding="utf-8") == _DESPUES


def test_H_si_la_verificacion_falla_se_revierte(tmp_path):
    objetivo, p = _propuesta_autorizada(tmp_path)
    r = ac.ejecutar(tmp_path, p, autoridad="CEO", verificacion=lambda: False)
    assert r["revertido"] is True
    assert objetivo.read_text(encoding="utf-8") == _ANTES, "el rollback no dejo el original"


def test_E_sin_autorizacion_no_se_ejecuta(tmp_path):
    objetivo = tmp_path / "entorno" / "control-plane" / "m.py"
    objetivo.parent.mkdir(parents=True)
    objetivo.write_text(_ANTES, encoding="utf-8")
    p = ac.proponer(tmp_path, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                               "buscar": "return 1", "sustituir": "return 2"})
    with pytest.raises(ac.SinAutorizacion):
        ac.ejecutar(tmp_path, p, autoridad="CEO")


def test_C_fuera_de_perimetro_no_se_ejecuta(tmp_path):
    fuera = tmp_path / "walking-skeleton" / "m.py"
    fuera.parent.mkdir(parents=True)
    fuera.write_text(_ANTES, encoding="utf-8")
    p = ac.proponer(tmp_path, {"fichero": str(fuera), "operacion": "sustituir_texto",
                               "buscar": "return 1", "sustituir": "return 2"})
    ac.autorizar(tmp_path, p["id"], por='ceo', acta="acta")
    with pytest.raises(ac.ZonaProhibida):
        ac.ejecutar(tmp_path, p, autoridad="CEO")


@pytest.mark.parametrize("intocable", ["politica-orquestador.toml", "orquestador.py",
                                       "control_plane.py", "conftest.py"])
def test_D_J_K_no_se_puede_tocar_lo_intocable(intocable):
    """La barrera es la existente: `orquestador._INTOCABLES`, consultada por el contrato."""
    import orquestador as orq
    assert intocable in orq._INTOCABLES
    r = ct.evaluar({"perimetro": {"modificables": [str(PLANO / intocable)]}}, directorio=PLANO)
    assert any("intocable" in b for b in r["bloqueos"])


def test_I_la_operacion_no_puede_modificar_su_propio_contrato():
    """`CONTRATOS` esta fuera de la zona: no hay operacion que lo alcance."""
    assert ac.zona_permitida(ct.CONTRATOS) is False
    assert ac.zona_permitida(ct.CONTRATOS / "010.toml") is False


# --------------------------------------------------------------- el contrato lo expresa --

def test_el_contrato_acepta_una_operacion_estructurada():
    regla = {"operacion": "sustituir_texto", "buscar": "a", "sustituir": "b"}
    assert ct.operacion_valida(regla) is True


def test_el_contrato_rechaza_una_operacion_fuera_del_vocabulario():
    assert ct.operacion_valida({"operacion": "inventada"}) is False


# ------------------------------------------ la mejor candidata siguiente, y por que no pasa --

def test_la_sexta_fuente_quedo_ARMADA_por_la_primera_evolucion():
    """`DP-SELF-EVOLUTION-01` Fase A, cerrada **por AURA**: la fuente ya no es inerte. Su umbral lo
    fijo el acta `DR-D` y lo aplico el circuito gobernado, no una edicion a mano."""
    import estancamiento as est
    assert est.K_ESTANCAMIENTO == 100
    assert isinstance(est.K_ESTANCAMIENTO, int), "un entero, no una cadena ni un octal"


def test_el_valor_armado_tiene_respaldo_en_un_acta_del_historial():
    """La garantia que sobrevive intacta: un numero escondido en codigo seguiria cayendo aqui."""
    import control_plane as cp
    import estancamiento as est
    actas = [e for e in cp.leer_eventos(PLANO) if e["tipo"] == "review_habilitado"]
    assert any(f"K_ESTANCAMIENTO = {est.K_ESTANCAMIENTO}" in str(a["datos"].get("acta", ""))
               for a in actas), "K sin acta que lo respalde"


def test_el_contrato_de_esa_capacidad_existe_y_su_tarea_quedo_COMPLETADA():
    """El contrato sigue siendo la fuente de verdad, y la tarea no vuelve a la cola."""
    import planificador as pl
    cap = ct.contrato_de("sexta-fuente-estancamiento")
    assert cap is not None and len(cap) == 15
    assert pl.completada(PLANO, "TA-4c50255a4c70") is True
    assert pl.elegible(PLANO, "TA-4c50255a4c70") is False, "una completada no vuelve a la cola"


def test_la_autoridad_solo_se_movio_donde_el_acta_la_movio():
    """El acta `DR-D` delego el verbo. Lo que ningun acta ha tocado sigue exactamente igual."""
    assert rv.ACCION_DE_EVOLUCION in rv.TODO_LO_DELEGABLE
    assert rv.en_alcance(PLANO, rv.ACCION_DE_EVOLUCION) is True
    assert len(rv._MATERIA_RESERVADA) == 10
    assert rv.REVIEW_HABILITADO is False
