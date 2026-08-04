"""Integracion: el tablero de dependencia externa, derivado solo del historial.

Cada numero debe poder reconstruirse leyendo el JSONL, sin metricas almacenadas (ADR-0023).
"""

from aura_skeleton.core.dependencia import (
    NO_MEDIBLE,
    autonomia_de_decision,
    generacion_de_trabajo_propio,
    informe,
    puntos_de_rendicion,
    tablero,
)
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.planificacion import CEO, oyente_de_transiciones


def _con_ciclo(tmp_path, motivos):
    ruta = str(tmp_path / "e.jsonl")
    alm = AlmacenEstadoOperativo(ruta)
    alm.observar(oyente_de_transiciones(alm))
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="qa", origen=CEO))
    for m in motivos:
        alm.transitar("o", "t-01", "bloqueada", autoridad="director", causa=m, bloqueos=[m])
        alm.transitar("o", "t-01", "abierta", autoridad="director", causa="reintento")
    return ruta


def test_el_indicador_se_calcula_leyendo_el_historial(tmp_path):
    ruta = _con_ciclo(tmp_path, ["falta ejecutor"])
    i = generacion_de_trabajo_propio(ruta)
    assert i.numerador == 1 and i.denominador == 2 and i.porcentaje == 50.0


def test_EL_TECHO_NO_ES_UNA_CONSTANTE_DE_ARQUITECTURA(tmp_path):
    """La correccion metodologica del CEO, convertida en prueba.

    Con tres motivos distintos, una sola tarea decisoria produce tres derivadas: 75 %. El 50 % era una
    propiedad del ESCENARIO, no del modelo. El techo se deriva del historial (k/(1+k)), nunca se
    codifica.
    """
    i = generacion_de_trabajo_propio(_con_ciclo(tmp_path, ["falta ejecutor", "permisos", "dependencia"]))

    assert i.porcentaje == 75.0, f"tres motivos distintos deben dar 75%, dio {i.porcentaje}"
    assert i.detalle["techo_es_constante_de_arquitectura"] is False
    assert i.detalle["techo_derivado_del_historial"] == 75.0, "el techo debe salir del historial, no de una constante"
    assert i.detalle["motivos_distintos_observados"] == 3


def test_los_puntos_de_rendicion_son_recuento_y_motivos_no_porcentaje(tmp_path):
    """Un porcentaje seria mejorable trabajando mas, no dependiendo menos."""
    ruta = _con_ciclo(tmp_path, ["falta ejecutor"])
    AlmacenEstadoOperativo(ruta).transitar(
        "o", "t-01", "bloqueada", autoridad="director", causa="otra vez", bloqueos=["permisos denegados"]
    )
    i = puntos_de_rendicion(ruta)

    assert i.denominador is None, "no puede tener denominador: no es una razon"
    assert i.numerador >= 1 and i.detalle["por_motivo"], "debe declarar POR QUE se detuvo"


def test_la_decision_es_NO_MEDIBLE_con_una_sola_autoridad(tmp_path):
    """100 % por construccion seria correcto y engañoso: se declara en vez de calcularse."""
    i = autonomia_de_decision(_con_ciclo(tmp_path, ["falta ejecutor"]))
    assert i.estado == NO_MEDIBLE and i.porcentaje is None
    assert i.detalle["autoridades_observadas"] == ["director"]


def test_sin_historial_no_se_inventa_una_cifra(tmp_path):
    i = generacion_de_trabajo_propio(str(tmp_path / "no-existe.jsonl"))
    assert i.estado == NO_MEDIBLE and i.porcentaje is None


def test_el_informe_publica_numerador_denominador_y_techo(tmp_path):
    """El CEO exige que nadie pueda leer el porcentaje aislado."""
    txt = informe(tablero(_con_ciclo(tmp_path, ["falta ejecutor", "permisos"])))
    assert "2/3" in txt and "techo derivado del historial" in txt
    assert "NO_MEDIBLE" in txt, "la dimension indefinida debe verse, no ocultarse"
