"""Unit: CapabilityRegistry (C1, ADR-0021 §2.4).

Almacen autodeclarativo de capacidades-subsistema: una capacidad, un nombre (fuente unica, D41). No
decide estados —eso es exclusivo del CapabilityManager (regla permanente del CEO)—; solo guarda y
consulta declaraciones.
"""

import pytest

from aura_skeleton.core.capability_registry import CapabilityRegistry, CapacidadDuplicada
from aura_skeleton.core.capacidades import Capacidad, GradoLatencia


def _cap(nombre: str, **kw) -> Capacidad:
    return Capacidad(nombre=nombre, contrato=kw.pop("contrato", f"{nombre}.v1"), **kw)


def test_registrar_y_obtener():
    reg = CapabilityRegistry()
    c = _cap("memoria")
    reg.registrar(c)
    assert reg.obtener("memoria") is c


def test_obtener_inexistente_es_none():
    assert CapabilityRegistry().obtener("no_existe") is None


def test_nombre_duplicado_se_rechaza():
    reg = CapabilityRegistry([_cap("voz")])
    with pytest.raises(CapacidadDuplicada):
        reg.registrar(_cap("voz"))


def test_todas_y_nombres():
    reg = CapabilityRegistry([_cap("memoria"), _cap("voz", latencia=GradoLatencia.PREVISTA)])
    assert reg.nombres() == {"memoria", "voz"}
    assert {c.nombre for c in reg.todas()} == {"memoria", "voz"}


def test_constructor_acepta_iterable():
    reg = CapabilityRegistry([_cap("a"), _cap("b"), _cap("c")])
    assert len(reg.todas()) == 3
