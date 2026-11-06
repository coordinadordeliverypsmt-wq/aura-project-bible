"""Pruebas del AURA Maturity Index. La fórmula tiene que ser reproducible y no admitir niveles sin evidencia."""

import json

import pytest

from indice_madurez import IndiceInvalido, calcular, cargar


def _cap(dim="B", nivel=3, alcance="MVP", evidencia="ruta.py:1 [EJEC]"):
    return {"dim": dim, "capacidad": f"c{nivel}{dim}", "nivel": nivel, "alcance": alcance,
            "evidencia": evidencia, "bloqueo": ""}


def test_core_mide_hasta_implementada_y_ready_desde_ahi():
    r = calcular([_cap(nivel=6)])
    assert r["core"] == 1.0 and r["ready"] == 1.0
    r = calcular([_cap(nivel=3)])
    assert r["core"] == 1.0 and r["ready"] == 0.0
    r = calcular([_cap(nivel=0, evidencia="")])
    assert r["core"] == 0.0 and r["ready"] == 0.0


def test_el_indice_es_la_media_de_core_y_ready():
    """Identidad de la fórmula: nivel/6 = (min(n,3) + max(n-3,0)) / 6."""
    caps = [_cap(dim="B", nivel=5), _cap(dim="F", nivel=2)]
    r = calcular(caps)
    assert r["indice"] == pytest.approx((r["core"] + r["ready"]) / 2)


def test_cada_dimension_pesa_lo_mismo_aunque_tenga_mas_capacidades():
    """Sin esto, una dimensión con 10 capacidades menores aplastaría a una con 2 esenciales."""
    caps = [_cap(dim="B", nivel=6)] * 10 + [_cap(dim="F", nivel=0, evidencia="")]
    assert calcular(caps)["indice"] == pytest.approx(0.5)


def test_el_ambito_de_lanzamiento_excluye_lo_que_la_Bible_deja_fuera_del_MVP():
    caps = [_cap(dim="B", nivel=6), _cap(dim="F", nivel=0, alcance="R4", evidencia="")]
    assert calcular(caps, ambito="MVP")["indice"] == 1.0
    assert calcular(caps, ambito=None)["indice"] == pytest.approx(0.5)


def test_un_nivel_sin_evidencia_se_rechaza():
    with pytest.raises(IndiceInvalido, match="evidencia"):
        calcular([_cap(nivel=4, evidencia="")])


def test_un_nivel_fuera_de_escala_se_rechaza():
    with pytest.raises(IndiceInvalido, match="nivel"):
        calcular([_cap(nivel=7)])


def test_cargar_lee_el_fichero_de_datos(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"capacidades": [_cap()]}), encoding="utf-8")
    assert len(cargar(str(f))) == 1
