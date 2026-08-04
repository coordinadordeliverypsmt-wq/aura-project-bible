"""Integracion: el Centro de Gobierno declara el ORIGEN de cada seccion y sus limites.

PRINCIPIO DEL CEO (2026-08-04): ninguna seccion mostrara contenido generado por un origen distinto al
que declara. "Prefiero una ausencia declarada a una capacidad simulada."
"""

import tempfile

import pytest

from aura_skeleton.core.centro_gobierno import AURORA, INEXISTENTE, Seccion, panel, render
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea


def _estado():
    """Estado con bloqueos REALES, reproducidos sin componer el sistema: las pruebas no deben
    ejecutar el Quality Gate para comprobar como se presenta un panel."""
    alm = AlmacenEstadoOperativo(tempfile.mkdtemp() + "/e.jsonl")
    for i, (r, motivo) in enumerate(
        [
            ("qa", "veredicto negativo: 2 garantias ya no protegen nada"),
            ("programador", "detenida: dry-run no viable: un cambio necesita fichero y patron"),
            ("programador", "detenida: dry-run no viable: un cambio necesita fichero y patron"),
            ("documentacion", "ningun ejecutor atiende al responsable 'documentacion'"),
        ],
        1,
    ):
        alm.registrar(
            Tarea(
                objetivo_id="cg",
                tarea_id=f"t-{i}",
                descripcion=r,
                estado="bloqueada",
                responsable=r,
                origen="ceo",
                bloqueos=[motivo],
            )
        )
    return alm


def test_TODA_seccion_declara_su_origen():
    for s in panel(estado=_estado(), objetivo="cg"):
        assert s.origen, f"'{s.titulo}' no declara origen: el contenido no seria interpretable"


def test_una_capacidad_inexistente_NO_se_rellena_con_contenido_ajeno():
    """EL PRINCIPIO: mostrar propuestas que parecen de AURORA y no lo son seria declarado != real
    en la interfaz con la que el CEO decide."""
    secs = {s.titulo: s for s in panel(estado=_estado(), objetivo="cg")}
    for titulo in ("Backlog propuesto", "Cambios sugeridos"):
        assert secs[titulo].origen == INEXISTENTE
        assert secs[titulo].contenido == "", "una capacidad inexistente no puede traer contenido"
        assert secs[titulo].motivo, "debe declarar POR QUE no existe"


def test_una_capacidad_inexistente_SIN_MOTIVO_es_un_error():
    """No basta con declarar la ausencia: hay que decir por que, o el limite no entra al backlog."""
    with pytest.raises(ValueError, match="motivo"):
        Seccion("X", INEXISTENTE)


def test_una_seccion_con_origen_declarado_DEBE_traer_contenido():
    """CONTROL simetrico: declarar AURORA y no traer nada seria la simulacion inversa."""
    with pytest.raises(ValueError, match="contenido"):
        Seccion("X", AURORA, "")


def test_las_recomendaciones_declaran_la_evidencia_que_las_sustenta():
    """No opiniones: cada recomendacion dice de que dato sale."""
    secs = {s.titulo: s for s in panel(estado=_estado(), objetivo="cg")}
    rec = secs["Recomendaciones derivadas"].contenido
    assert "evidencia:" in rec, f"una recomendacion sin evidencia es una opinion: {rec}"
    assert "programador" in rec, "debe señalar al responsable que mas trabajo detiene"


def test_el_panel_hace_VISIBLES_los_limites():
    txt = render(panel(estado=_estado(), objetivo="cg"))
    assert "[CAPACIDAD INEXISTENTE]" in txt, "los limites deben verse, no ocultarse"
    assert txt.count("[AURORA]") >= 5, "y lo que AURORA si produce debe atribuirsele"


def test_CONTROL_sin_datos_no_se_inventan_secciones():
    """Sin estado ni diagnostico solo quedan las capacidades inexistentes declaradas."""
    secs = panel()
    assert all(s.origen == INEXISTENTE for s in secs), "sin datos no puede haber contenido de AURORA"
