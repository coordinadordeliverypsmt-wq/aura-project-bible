"""La octava fuente — AURA lee su propio plan de formacion, y el verbo que aun no puede conjugar.

## Por que la fuente no puede producir trabajo ejecutable

`PLAN-DE-FORMACION-AURORA.md` termina con una regla que gobierna el documento entero: *«El resultado
es un **plan**, nunca una implementacion. Ninguna capacidad se desarrolla automaticamente»*. Y la
correccion del 2026-08-17 anade: *«Mover una capacidad de 🔴 a 🟡 o a ✅ exige la regla de admision
—evidencia repetida del uso real—. Esa decision no la toma la asistencia externa»*.

Por eso el techo de esta fuente es `DECISION_REQUIRED` **por construccion, no por configuracion**:
no hay valor, bandera ni acta que la haga emitir `OPORTUNIDAD_REAL`. Lo que aporta es que AURA
**vea** lo que le falta, que hasta hoy era el unico conocimiento de su evolucion que le era invisible.

## Por que el verbo nace inerte

`implementar_incremento_especificado` entra en `TODO_LO_DELEGABLE` —lo maximo que un acta *podria*
delegar— pero el acta vigente (`DEC-ORCH-2`) delega exactamente `("eliminar_codigo_muerto",)`. Asi
que `en_alcance()` lo niega y `clasificar()` lo manda a `HUMAN`. Es el mismo patron que
`REVIEW_HABILITADO=False` y `K_ESTANCAMIENTO=None`: construido y a la espera de un acta.

Y el ejecutor lo rechaza **explicitamente** (`INV-9`: no se finge capacidad no construida). Un verbo
en el catalogo sin ejecutor que lo respalde seria exactamente esa mentira.
"""

import pathlib

import ciclo_autonomo as ca
import descubrimiento as des
import formacion as fm
import review as rv

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PLANO = pathlib.Path(__file__).parent


# ------------------------------------------------------------------ la fuente: lo que lee --

def test_lee_las_tres_tablas_del_plan_real():
    caps = fm.capacidades(RAIZ)
    assert caps, "el plan real tiene capacidades y la fuente debe verlas"
    estados = {c["estado"] for c in caps}
    assert estados <= set(fm.ESTADOS), f"vocabulario inventado: {estados - set(fm.ESTADOS)}"


def test_respeta_literalmente_el_vocabulario_del_documento():
    """No se traduce ✅/🟡/🔴 a un vocabulario propio: se usa el que el documento ya tiene."""
    assert fm.ESTADOS == ("aprendida", "en observacion", "bloqueada")
    caps = {c["numero"]: c for c in fm.capacidades(RAIZ)}
    assert caps["001"]["estado"] == "aprendida"
    assert caps["010"]["estado"] == "en observacion"
    assert caps["014"]["estado"] == "bloqueada"


def test_no_propone_lo_ya_aprendido():
    ops = fm.formacion(RAIZ, PLANO)
    numeros = {o.detalle["numero"] for o in ops}
    assert "001" not in numeros and "008" not in numeros


def test_propone_lo_declarado_y_no_adquirido():
    numeros = {o.detalle["numero"] for o in fm.formacion(RAIZ, PLANO)}
    assert {"010", "014", "017", "018"} <= numeros


# -------------------------------------------------------- la fuente: lo que NO puede hacer --

def test_el_techo_de_las_capacidades_DEL_PLAN_es_decision_required():
    """El techo del **plan** no se movio: `F5` solo levanta el de una capacidad **con contrato
    escrito**, y los contratos viven fuera de la zona de AURA."""
    for o in fm.formacion(RAIZ, PLANO):
        if o.detalle.get("estado_en_el_plan") == "con contrato":
            continue
        assert o.estado == des.DECISION_REQUIRED, f"{o.id} escapo del techo"


def test_ninguna_oportunidad_se_convierte_en_tarea():
    import planificador as pl
    for o in fm.formacion(RAIZ, PLANO):
        if o.estado != des.DECISION_REQUIRED:
            continue
        assert pl.a_tarea(o) is None, "una DECISION_REQUIRED no es trabajo"


def test_la_autoridad_de_toda_oportunidad_es_el_ceo():
    for o in fm.formacion(RAIZ, PLANO):
        # Una capacidad con contrato cita **su acta**, que es autoridad mas precisa que «CEO».
        assert o.autoridad == "CEO" or o.autoridad.startswith("DR-")


def test_la_fuente_es_de_solo_lectura():
    """No escribe el plan, no escribe estado.json, no ejecuta."""
    import inspect
    fuente = inspect.getsource(fm)
    for prohibido in ("write_text", "open(", "subprocess", "os.remove", "unlink", "requests"):
        assert prohibido not in fuente, f"la fuente no puede {prohibido}"


def test_cada_oportunidad_trae_las_ocho_piezas():
    for o in fm.formacion(RAIZ, PLANO):
        for pieza in des.PIEZAS_OBLIGATORIAS:
            assert getattr(o, pieza), f"{o.id} sin {pieza}"


def test_la_fuente_cita_el_documento_y_su_linea():
    for o in fm.formacion(RAIZ, PLANO):
        assert ("PLAN-DE-FORMACION-AURORA.md:" in o.fuente
                or o.fuente.endswith(".toml:1")), f"procedencia rara: {o.fuente}"
        assert des.fuente_verificable(o.fuente)


def test_un_plan_ausente_no_revienta_el_descubrimiento(tmp_path):
    """Sin plan no hay capacidades. Devolver algo inventado seria peor que devolver nada."""
    assert fm.capacidades(tmp_path) == []


def test_la_fuente_encuentra_el_plan_aunque_el_motor_corra_desde_el_control_plane():
    """El motor invoca con `raiz=<control-plane>` y el plan vive en la raiz del repositorio.
    Deducirlo del `raiz` recibido dejaba la fuente muda en produccion — medido, no supuesto."""
    assert fm.formacion(PLANO, PLANO), "la fuente no puede quedarse muda en produccion"
    assert len(fm.formacion(PLANO, PLANO)) == len(fm.formacion(RAIZ, PLANO))


def test_la_fuente_se_puede_importar_ANTES_que_el_descubridor():
    """Regresion: `descubrimiento` enchufa esta fuente en su dict, asi que un import de modulo en la
    cabecera de `formacion` cerraba el ciclo — `import formacion` primero reventaba con
    `partially initialized module`. La suite no lo veia porque siempre llegaba por `descubrimiento`.
    Se comprueba en un interprete limpio, que es la unica forma de fijar un orden de import."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-c", "import formacion as f; print(len(f.formacion('.', '.')))"],
                       cwd=str(PLANO), capture_output=True, text=True)
    assert r.returncode == 0, f"importar formacion primero rompe: {r.stderr[-300:]}"
    assert int(r.stdout.strip()) >= 9


def test_esta_enchufada_al_descubridor():
    assert des.FUENTES.get("capacidades_declaradas") is fm.formacion


# ------------------------------------------------------------------------------ el verbo --

def test_el_verbo_esta_declarado():
    assert rv.ACCION_DE_EVOLUCION == "implementar_incremento_especificado"


def test_el_verbo_entro_en_la_lista_blanca_POR_ACTA_y_no_por_edicion():
    """`A10` sigue en pie: lo delegable es una lista BLANCA y entrar exige acta. El verbo entro
    cuando existio `DR-D`; lo que nunca entra es lo que nadie autorizo."""
    assert rv.ACCION_DE_EVOLUCION in rv.TODO_LO_DELEGABLE
    for inventada in ("modificar_D24", "tocar_el_roadmap", "lo_que_sea"):
        assert inventada not in rv.TODO_LO_DELEGABLE


def test_el_verbo_esta_en_el_alcance_del_acta_vigente():
    """`DR-D` lo delego. La garantia que queda: el alcance sale del **log**, no del codigo."""
    assert rv.en_alcance(PLANO, rv.ACCION_DE_EVOLUCION) is True
    assert rv.ACCION_DE_EVOLUCION in rv._alcance(PLANO)


def test_una_tarea_del_verbo_nuevo_sobre_gobernanza_sigue_siendo_human():
    """El acta delego el verbo, no el perimetro: la zona manda y va **antes** que el acta."""
    assert ca.clasificar({"accion": rv.ACCION_DE_EVOLUCION,
                          "fichero": str(RAIZ / "adr" / "0003-x.md")}, PLANO) == "HUMAN"


def test_el_ejecutor_rechaza_un_verbo_sin_ejecutor_construido(tmp_path):
    """INV-9 sigue vigente para lo no construido: el verbo de evolucion ya tiene ejecutor, pero
    cualquier otro declarado delegable sin construirlo se seguiria rechazando."""
    import pytest
    assert rv.ACCION_DE_EVOLUCION in rv._EJECUTORES_CONSTRUIDOS
    with pytest.raises(rv.SinEjecutor):
        rv.ejecutar_bajo_review(tmp_path, {"accion": "un_verbo_sin_ejecutor",
                                           "fichero": "x.py", "simbolo": "_y"},
                                propuesto_por="claude", autoridad="CEO")


def test_el_verbo_no_toco_ninguna_otra_autoridad():
    assert ca._ACCIONES_AUTO == ("ejecutar_pruebas", "verificar_calidad",
                                 "auditar_garantias", "diagnosticar_estado")
    assert len(rv._MATERIA_RESERVADA) == 10
    assert rv.REVIEW_HABILITADO is False
