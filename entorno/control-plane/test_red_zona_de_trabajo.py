"""RED · DEC-ZONA-POR-FICHERO-DE-TRABAJO. **Una falla de contencion, no una mejora.**

MEDIDO: los 11 rojos de Linea A salian `AUTO_EXECUTABLE`. Su `fichero` es `tests/unit/...` y las
zonas se calculaban sobre el; el trabajo real vive en `aura_skeleton/`, zona bloqueada, que no
aparecia por ningun lado. **La contencion miraba donde esta la PRUEBA, no donde esta el TRABAJO.**

**Lo que el contrato NO determina** —y por eso no se implementa—: derivar automaticamente que
fichero hay que modificar para arreglar una prueba roja. No existe ninguna fuente que lo mapee;
deducirlo del nombre del test seria la heuristica que la decision prohibe.

**Lo que el contrato SI determina** es que hacer cuando no se sabe: la condicion de seguridad del
CEO del 2026-08-25 —*«si falta una condicion esencial: NO AUTO_EXECUTABLE»*— y la forma ya aprobada
para `apertura`: un dato se DECLARA, y su ausencia es fail-closed, nunca permiso.
"""
from __future__ import annotations

import copy

import control_plane as cp
import pytest


ZONAS = ("aprobar", "m9", "d-cp-4", "d-cp-8", "orquestador", "aura_skeleton", "delegar.sh")


def _estado():
    e = cp.estado_inicial()
    e["zonas_bloqueadas_para_discovery"] = list(ZONAS)
    e["tareas_AUTO"] = []
    return e


def _hallazgo(**kw):
    """Un hallazgo de red roja como lo produce `descubrir()`: con fichero y prueba de la PRUEBA."""
    h = {"origen": "red_roja", "ref": "tests/unit/test_g1_ruta_unica.py::test_g1_ra",
         "fichero": "tests/unit/test_g1_ruta_unica.py",
         "prueba": "tests/unit/test_g1_ruta_unica.py::test_g1_ra",
         "descripcion": "roja medida", "determinado_por": "contrato existente"}
    h.update(kw)
    return h


# ======================================== LA FALLA MEDIDA, EN SU FORMA EXACTA --


def test_red_1_prueba_fuera_pero_trabajo_DENTRO_de_zona_no_es_AUTO():
    """**El caso real de Linea A.** La prueba esta en `tests/unit/`, que no toca ninguna zona; el
    trabajo esta en `aura_skeleton/`, que las toca todas las alarmas."""
    h = _hallazgo(fichero_de_trabajo="walking-skeleton/aura_skeleton/memoria/almacen.py")
    assert cp.clasificar(h, _estado()) != "AUTO_EXECUTABLE"


def test_red_2_el_trabajo_en_zona_bloqueada_es_DECISION_REQUIRED():
    h = _hallazgo(fichero_de_trabajo="walking-skeleton/aura_skeleton/memoria/almacen.py")
    assert cp.clasificar(h, _estado()) == "DECISION_REQUIRED"


def test_red_3_el_trabajo_fuera_de_zona_conserva_su_clasificacion():
    """**Caso de control.** Sin el, todo lo anterior pasaria con un `clasificar()` averiado que
    devolviese DECISION_REQUIRED siempre, y la contencion seria indistinguible de un bloqueo total."""
    h = _hallazgo(fichero_de_trabajo="entorno/control-plane/calculadora.py")
    assert cp.clasificar(h, _estado()) == "AUTO_EXECUTABLE"


def test_red_4_el_fichero_de_la_prueba_no_autoriza_sobre_el_de_trabajo():
    """Dos hallazgos con **la misma prueba** y distinto trabajo deben clasificarse distinto. Si el
    veredicto no cambia, el fichero de trabajo no se esta mirando."""
    e = _estado()
    dentro = cp.clasificar(_hallazgo(fichero_de_trabajo="walking-skeleton/aura_skeleton/nucleo.py"), e)
    fuera = cp.clasificar(_hallazgo(fichero_de_trabajo="entorno/control-plane/calculadora.py"), e)
    assert dentro != fuera, "la prueba, identica en ambos, esta decidiendo por el trabajo"
    assert dentro == "DECISION_REQUIRED" and fuera == "AUTO_EXECUTABLE"


@pytest.mark.parametrize("ajeno", ["aura_skeletonx.py", "mi_aura.py", "md-cp-8x.py",
                                   "dcp9_otro.py", "aprobaciones_previas.py"])
def test_red_5_un_identificador_PARECIDO_pero_ajeno_no_se_bloquea(ajeno):
    """El otro lado del riesgo: normalizar de mas convierte la contencion en bloqueo indiscriminado.
    `aura_skeletonx` NO es `aura_skeleton`."""
    h = _hallazgo(fichero_de_trabajo=f"entorno/otro/{ajeno}")
    assert cp.clasificar(h, _estado()) == "AUTO_EXECUTABLE", ajeno


def test_red_6_sin_fichero_de_trabajo_falla_cerrado_y_nunca_es_AUTO():
    """**La garantia que sostiene todo lo demas.** El contrato no puede derivar donde esta el
    trabajo; entonces no saberlo NO puede valer como permiso."""
    assert cp.clasificar(_hallazgo(), _estado()) != "AUTO_EXECUTABLE"
    assert cp.clasificar(_hallazgo(fichero_de_trabajo=None), _estado()) != "AUTO_EXECUTABLE"
    assert cp.clasificar(_hallazgo(fichero_de_trabajo=""), _estado()) != "AUTO_EXECUTABLE"


# ==================================== CONTENCION CRITICA · los DOS sentidos --


def test_contencion_prueba_DENTRO_de_zona_y_trabajo_FUERA_manda_el_trabajo():
    """El sentido inverso, exigido por el CEO. La zona protege el TRABAJO, no el fichero de prueba:
    si el trabajo real esta fuera, el veredicto lo da el trabajo.

    Sin este caso, una implementacion que bloquease por prueba **o** por trabajo pasaria todo lo
    anterior y seguiria sin mirar donde esta el trabajo de verdad."""
    h = _hallazgo(ref="test_red_dcp8_cableado.py::test_x", fichero="test_red_dcp8_cableado.py",
                  prueba="test_red_dcp8_cableado.py::test_x",
                  fichero_de_trabajo="entorno/control-plane/calculadora.py")
    assert cp.clasificar(h, _estado()) == "AUTO_EXECUTABLE"


def test_contencion_sin_trabajo_declarado_la_zona_de_la_prueba_sigue_bloqueando():
    """Compatibilidad: mientras nadie declare el trabajo, lo unico que se sabe es donde esta la
    prueba, y esa contencion —ya probada— no se retira."""
    h = _hallazgo(ref="test_red_dcp8_cableado.py::test_x", fichero="test_red_dcp8_cableado.py",
                  prueba="test_red_dcp8_cableado.py::test_x")
    assert cp.clasificar(h, _estado()) == "DECISION_REQUIRED"


def test_descubrir_propaga_el_fichero_de_trabajo_declarado_en_la_evidencia():
    """`descubrir()` no mide: clasifica lo medido. Si quien mide sabe donde esta el trabajo, el dato
    debe llegar intacto al hallazgo — y si no lo sabe, no se rellena solo."""
    e = _estado()
    ev = {"reds_rojas": [{"nodeid": "tests/unit/t.py::x", "fichero": "tests/unit/t.py",
                          "fichero_de_trabajo": "walking-skeleton/aura_skeleton/nucleo.py",
                          "motivo": "roja"},
                         {"nodeid": "tests/unit/t.py::y", "fichero": "tests/unit/t.py",
                          "motivo": "roja sin trabajo declarado"}]}
    h = cp.descubrir(e, ev)
    assert h[0]["fichero_de_trabajo"] == "walking-skeleton/aura_skeleton/nucleo.py"
    assert not h[1].get("fichero_de_trabajo")
    assert cp.clasificar(h[0], e) == "DECISION_REQUIRED"
    assert cp.clasificar(h[1], e) != "AUTO_EXECUTABLE"


def test_la_correccion_no_toca_tareas_AUTO():
    e = _estado()
    antes = copy.deepcopy(e["tareas_AUTO"])
    cp.registrar_propuestas(e, [_hallazgo(fichero_de_trabajo="x.py")])
    assert e["tareas_AUTO"] == antes
