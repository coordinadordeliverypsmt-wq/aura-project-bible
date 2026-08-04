"""Integracion: AURORA se evalua a si misma con evidencia propia, no con una narrativa.

REGLA DEL CEO: no se inventa ningun dato. Una dimension que no puede medirse automaticamente NO
recibe una puntuacion estimada: declara que instrumentacion le falta.
"""

import tempfile

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.ima import evaluar, informe


def _dims():
    return evaluar(componer(Configuracion(datos=tempfile.mkdtemp())))


def test_la_medicion_sale_del_sistema_real():
    """No hay constantes escritas a mano: cada dimension se mide por introspeccion."""
    d = {x.nombre: x for x in _dims()}
    assert d["Capacidad de validacion"].logrado >= 3, "el QA cableado debe contarse"
    assert "puede ejecutar sus pruebas" in d["Capacidad de validacion"].evidencias


def test_una_capacidad_ausente_baja_la_puntuacion():
    """CONTROL: la medicion refleja la realidad, no la aspiracion.

    `ejecutar_mutacion` no esta autorizada, y eso DEBE verse en el indice.
    """
    val = {x.nombre: x for x in _dims()}["Capacidad de validacion"]
    assert val.porcentaje < 100.0, "una capacidad no construida no puede puntuar como lograda"
    assert any("MUTACION" in f for f in val.faltan), "el hueco debe nombrarse, no ocultarse"


def test_lo_que_no_se_puede_medir_se_declara_en_vez_de_estimarse():
    """LA REGLA CENTRAL: un indice rellenado a mano es una opinion, no una metrica."""
    dep = {x.nombre: x for x in _dims()}["Dependencia de asistencia externa"]
    assert dep.medible is False
    assert dep.porcentaje is None, "no puede haber porcentaje sin instrumentacion"
    assert "instrumentacion" in dep.instrumentacion_ausente.lower()


def test_cada_dimension_declara_su_cuello_de_botella():
    for d in _dims():
        if d.medible and d.logrado < d.total:
            assert d.faltan, f"{d.nombre} tiene huecos y no declara cual"


def test_el_informe_es_reproducible():
    """Dos evaluaciones del mismo sistema producen la misma matriz."""
    assert informe(_dims()) == informe(_dims())


def test_el_global_solo_cuenta_lo_medible():
    """No se diluye el indice repartiendo lo desconocido: lo no medible se excluye y se declara."""
    txt = informe(_dims())
    assert "solo dimensiones medibles" in txt
    # La CIFRA, no solo el texto: si lo no medible se colara en el global, el contador de
    # dimensiones sin instrumentar caeria a 0 y el indice pareceria completo. Lo detecto la
    # mutacion (M4 sobrevivia porque la prueba solo miraba que la frase estuviera).
    # La CIFRA, no solo el texto: si lo no medible se colara en el global, el contador caeria a 0 y el
    # indice pareceria completo. Se deriva del propio informe para que no envejezca al añadir
    # dimensiones -paso al derivar el IMA: eran 1 y pasaron a 3-.
    sin_medir = sum(1 for d in _dims() if not d.medible)
    assert f"{sin_medir} dimension(es) sin instrumentar" in txt, f"debe declararse cuantas:\n{txt}"
    assert sin_medir > 0, "si todo fuera medible, esta garantia no probaria nada"
