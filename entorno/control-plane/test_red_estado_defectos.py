"""RED · DEC-DEFECTO-ESTADO-ESTRUCTURADO = **opcion B** (CEO, 2026-08-25).

Dos garantias, y conviene no confundirlas porque se corrigen en sitios distintos:

1. **La apertura de un defecto es un DATO, no una narracion.** Vive en un campo estructurado con
   vocabulario cerrado. La prosa historica se conserva intacta y **nadie la consulta** para decidir
   si hay trabajo abierto: ni substring, ni parser, ni inferencia. Ausencia -> `NO_CONSTA`, jamas
   `ABIERTO`.

2. **Ver mas no es poder mas.** Al abrir la visibilidad aparecio el problema de verdad, MEDIDO en el
   DP: `DEF-CUERPO-LIBRE` no tiene `fichero` ni `prueba`, y precisamente por eso el texto sobre el
   que se calculan las zonas bloqueadas quedaba vacio, ninguna zona coincidia, y `clasificar()` lo
   devolvia **AUTO_EXECUTABLE**. El fail-closed anterior no ocultaba un defecto: contenia una
   clasificacion erronea. Hacerlo visible sin cerrar esto habria convertido un silencio en permiso.
"""
from __future__ import annotations

import copy
import json
import pathlib

import control_plane as cp


ZONAS = ("aprobar", "m9", "d-cp-4", "d-cp-8", "orquestador", "aura_skeleton")


def _estado(defectos):
    e = cp.estado_inicial()
    e["zonas_bloqueadas_para_discovery"] = list(ZONAS)
    e["defectos"] = list(defectos)
    e["tareas_AUTO"] = []
    return e


def _refs(estado):
    return {h["ref"] for h in cp.descubrir(estado) if h["origen"] == "defecto"}


DETERMINADO = {"id": "DEF-OK", "fichero": "x.py", "prueba": "test_x",
               "fichero_de_trabajo": "modulo_x.py",   # ANADIDO: DEC-ZONA-POR-FICHERO-DE-TRABAJO
               "descripcion": "defecto localizable y determinado"}


# ==================================================== VOCABULARIO DE APERTURA --


def test_red_1_un_defecto_ABIERTO_estructurado_se_descubre():
    e = _estado([dict(DETERMINADO, apertura="ABIERTO")])
    assert _refs(e) == {"DEF-OK"}


def test_red_2_un_defecto_CERRADO_no_es_trabajo_abierto():
    e = _estado([dict(DETERMINADO, apertura="CERRADO")])
    assert _refs(e) == set()


def test_red_3_un_defecto_OBSERVACION_no_es_trabajo_abierto():
    """CLAUDE.md §7: una observacion NO es deuda. Solo es deuda lo que bloquea, compromete la
    arquitectura o pierde informacion; lo demas se registra y no genera trabajo."""
    e = _estado([dict(DETERMINADO, apertura="OBSERVACION")])
    assert _refs(e) == set()


def test_red_4_la_ausencia_del_campo_es_NO_CONSTA_y_no_es_abierto():
    """La regla que sostiene la compatibilidad historica: no consta != abierto. Un registro escrito
    antes del mecanismo no afirmo nada sobre su apertura, y suponerlo seria inventarlo."""
    sin_campo = dict(DETERMINADO)
    assert cp.apertura_de(sin_campo) == "NO_CONSTA"
    assert _refs(_estado([sin_campo])) == set()


def test_red_4bis_un_valor_fuera_del_vocabulario_es_NO_CONSTA():
    """Fail-closed sobre el propio vocabulario: lo que no se reconoce no degrada en permiso.

    Sin este caso, `apertura_de` podria devolver el valor crudo y cualquier cadena distinta de
    ABIERTO/CERRADO/OBSERVACION pasaria a ser un quinto estado tacito."""
    assert cp.apertura_de({"apertura": "medio abierto"}) == "NO_CONSTA"
    assert cp.apertura_de({"apertura": "abierto"}) == "NO_CONSTA"   # el vocabulario es EXACTO
    assert _refs(_estado([dict(DETERMINADO, apertura="ABIERTO?")])) == set()


def test_red_5_la_prosa_no_decide_la_apertura_y_se_conserva_intacta():
    """La prosa dice ABIERTO en mayusculas y el campo dice CERRADO: manda el campo.

    Este es el caso que separa la opcion B de un parser heuristico. Si alguien reintrodujese
    interpretacion de texto —substring, `in`, regex sobre la prosa— esta prueba lo detecta."""
    prosa = "VECTOR 1 CONFIRMADO ABIERTO; vectores 2-4 sin analizar"
    d = dict(DETERMINADO, apertura="CERRADO", estado=prosa)
    e = _estado([d])
    assert _refs(e) == set(), "la prosa no puede abrir un defecto que el dato declara cerrado"
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    assert e["defectos"][0]["estado"] == prosa, "la prosa historica fue alterada"
    # y al reves: la prosa tampoco puede CERRAR lo que el dato declara abierto
    e2 = _estado([dict(DETERMINADO, apertura="ABIERTO", estado="cerrado y resuelto")])
    assert _refs(e2) == {"DEF-OK"}


# ================================================ CONTENCION · ver != poder --


def test_red_6_DEF_CUERPO_LIBRE_no_puede_volverse_AUTO_por_hacerse_visible():
    """**Caso de regresion obligatorio (CEO).** Registro REAL, leido de `estado.json`, no un fixture.

    Sin `fichero` ni `prueba`, el texto de zonas queda vacio y ninguna zona bloqueada coincide. Antes
    de esta contencion, eso bastaba para AUTO_EXECUTABLE."""
    real = json.loads(pathlib.Path("estado.json").read_text())
    d = next(x for x in real["defectos"] if x.get("id") == "DEF-CUERPO-LIBRE")
    assert not d.get("fichero") and not d.get("prueba"), "el fixture real cambio: revisar el caso"
    e = _estado([dict(d, apertura="ABIERTO")])       # visible A PROPOSITO, el peor caso
    hallazgos = cp.descubrir(e)
    assert {h["ref"] for h in hallazgos} == {"DEF-CUERPO-LIBRE"}, "debe ser visible, no invisible"
    assert cp.clasificar(hallazgos[0], e) != "AUTO_EXECUTABLE"


def test_red_7_sin_fichero_no_hay_AUTO_EXECUTABLE():
    d = {"id": "DEF-SF", "prueba": "test_y", "apertura": "ABIERTO", "descripcion": "sin fichero"}
    e = _estado([d])
    assert cp.clasificar(cp.descubrir(e)[0], e) != "AUTO_EXECUTABLE"


def test_red_8_sin_prueba_no_hay_AUTO_EXECUTABLE():
    d = {"id": "DEF-SP", "fichero": "y.py", "apertura": "ABIERTO", "descripcion": "sin prueba"}
    e = _estado([d])
    assert cp.clasificar(cp.descubrir(e)[0], e) != "AUTO_EXECUTABLE"


def test_red_9_un_defecto_determinado_conserva_la_clasificacion_permitida():
    """**Caso de control.** Sin el, las tres pruebas anteriores pasarian con un `clasificar()` que
    devolviese DECISION_REQUIRED siempre: la contencion seria indistinguible de una averia."""
    e = _estado([dict(DETERMINADO, apertura="ABIERTO")])
    assert cp.clasificar(cp.descubrir(e)[0], e) == "AUTO_EXECUTABLE"


def test_red_10_la_zona_bloqueada_sigue_teniendo_prioridad():
    d = {"id": "DEF-Z", "fichero": "entorno/x/test_orquestador.py", "prueba": "test_z",
         "apertura": "ABIERTO", "descripcion": "cae en zona vetada"}
    e = _estado([d])
    assert cp.clasificar(cp.descubrir(e)[0], e) == "DECISION_REQUIRED"


# ================================================================ AUTORIDAD --


def test_la_visibilidad_nueva_no_toca_tareas_AUTO():
    """La garantia central del ciclo, revalidada sobre el camino nuevo: descubrir y registrar no
    escriben en `tareas_AUTO` ni promueven nada."""
    e = _estado([dict(DETERMINADO, apertura="ABIERTO"),
                 dict(DETERMINADO, id="DEF-2", apertura="NO_CONSTA")])
    antes = copy.deepcopy(e["tareas_AUTO"])
    e = cp.registrar_propuestas(e, cp.descubrir(e))
    assert e["tareas_AUTO"] == antes
    assert all(p.get("estado") == "PROPUESTA" for p in e["propuestas"])
