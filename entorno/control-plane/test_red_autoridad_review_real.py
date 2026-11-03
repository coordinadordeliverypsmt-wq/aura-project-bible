"""`DR-F-3g` — `REVIEW_HABILITADO` **no es el estado de REVIEW**, y confundirlo cuesta caro.

Yo lo confundí. En `DR-F-3d-6` leí `REVIEW_HABILITADO = False`, probé el mecanismo en un sandbox
vacío —donde `habilitado()` es `False` por construcción— y concluí que a AURA le faltaba un acta del
CEO para desbloquearse. **El acta existía desde el 2026-08-26**: `DEC-ORCH-2`, registrada como el
evento `seq=1` del log del plano, con alcance `('eliminar_codigo_muerto',)`.

La constante es una **puerta global**, no un estado: su propio comentario dice *«Constante y en
`False`: encenderla exige un acta, no una edición de código»*, y `habilitado()` documenta *«Global
apagado **y** sin acta en este trabajo = apagado. **Ambas cosas, no una**»*. El código estaba bien
escrito y bien documentado; lo que faltaba era una prueba que impidiera leer el nombre en vez de la
semántica.

Hay una segunda trampa del mismo tipo, y también la pisé: `orquestador.nivel_de()` y
`ciclo_autonomo.clasificar()` responden a la misma pregunta con fuentes distintas —la política
estática la primera, el acta del log la segunda— y **pueden divergir**. Usar `nivel_de()` para saber
si algo entra en REVIEW da `HUMAN` aunque el acta lo haya habilitado.

Estas pruebas no cambian comportamiento: fijan la semántica que ya existe, para que el nombre no
vuelva a leerse como si fuera el estado.
"""

from __future__ import annotations

import pathlib

import ciclo_autonomo as ca
import control_plane as cp
import orquestador as orq
import review as rv

PLANO = pathlib.Path(__file__).resolve().parent


def _con_acta(directorio):
    """El mecanismo real: un acta es un evento en el log, no una edición de código."""
    rv.habilitar(directorio, por="ceo", acta="ACTA-DE-PRUEBA",
                 alcance=("eliminar_codigo_muerto",))


def test_la_constante_apagada_no_significa_review_apagado(tmp_path):
    """El corazón del error: `False` en la constante **no** implica `habilitado() is False`."""
    assert rv.REVIEW_HABILITADO is False
    assert rv.habilitado(tmp_path) is False, "sin acta, apagado"
    _con_acta(tmp_path)
    assert rv.habilitado(tmp_path) is True, (
        "con acta registrada está encendido, y la constante sigue en False")
    assert rv.REVIEW_HABILITADO is False, "el acta no toca la constante: son dos vías distintas"


def test_sin_directorio_no_se_puede_saber_y_por_tanto_esta_apagado():
    """Fail-closed: preguntar sin contexto no puede conceder."""
    assert rv.habilitado() is False


def test_las_dos_vias_son_un_O_no_un_Y(tmp_path):
    """`habilitado()` es cierto si la constante lo fuerza **o** si hay acta. Ninguna de las dos es
    necesaria por separado; por eso el docstring dice «ambas cosas» para el caso apagado."""
    assert rv.habilitado(tmp_path) is False
    _con_acta(tmp_path)
    assert rv.habilitado(tmp_path) is True


def test_nivel_de_y_clasificar_no_responden_a_lo_mismo(tmp_path):
    """La segunda trampa. `nivel_de()` **no conoce las actas**: mira la política estática. Quien
    quiera saber si algo entra hoy en REVIEW tiene que preguntar a `clasificar()`, que sí lee el log.

    Esto no es un defecto —cada una responde a su pregunta— pero es exactamente lo que me llevó a
    informar «todo es HUMAN» sobre un plano donde `eliminar_codigo_muerto` estaba en REVIEW."""
    fichero = tmp_path / "modulo.py"
    fichero.write_text("def muerta():\n    return 1\n", encoding="utf-8")
    _con_acta(tmp_path)
    assert orq.nivel_de("eliminar_codigo_muerto") == "HUMAN", "la politica estatica no ve el acta"
    assert ca.clasificar({"accion": "eliminar_codigo_muerto", "fichero": str(fichero)},
                         tmp_path) == "REVIEW", "el clasificador sí lee el acta"


def test_un_acta_no_amplia_lo_que_no_puede_ampliar(tmp_path):
    """Encender REVIEW no abre la materia reservada, ni la gobernanza, ni el plano producto."""
    fichero = tmp_path / "modulo.py"
    fichero.write_text("x = 1\n", encoding="utf-8")
    _con_acta(tmp_path)
    reservada = {"accion": "modificar_adr", "fichero": str(fichero)}
    assert ca.clasificar(reservada, tmp_path) == "HUMAN"
    fuera_de_alcance = {"accion": "desbloquear", "fichero": str(fichero)}
    assert ca.clasificar(fuera_de_alcance, tmp_path) == "HUMAN"
    gobernanza = {"accion": "eliminar_codigo_muerto", "fichero": "adr/0001.md"}
    assert ca.clasificar(gobernanza, tmp_path) == "HUMAN"


def test_si_el_plano_real_tiene_acta_entonces_review_esta_encendido():
    """La ruta que ninguna prueba tocaba: **el plano real**, con su log de verdad.

    Se formula como implicación para no acoplarse a un estado concreto —si algún día no hubiera
    acta, la prueba sigue siendo correcta— pero cierra el hueco que permitió afirmar que REVIEW
    estaba apagado sin haberlo medido nunca sobre el plano que de verdad usa el ciclo."""
    actas = [e for e in cp.leer_eventos(PLANO) if e.get("tipo") == "review_habilitado"]
    if actas:
        assert rv.habilitado(PLANO) is True
        assert rv._alcance(PLANO) == tuple(actas[-1]["datos"]["alcance"])
    else:
        assert rv.habilitado(PLANO) is False


def test_el_alcance_es_el_que_el_acta_dijo_no_el_maximo_delegable(tmp_path):
    """Lo destapó un mutante que sobrevivía. Hoy el acta del plano habilita exactamente
    `('eliminar_codigo_muerto',)`, que **coincide** con `TODO_LO_DELEGABLE`, así que devolver la
    constante en vez de leer el acta parecía inofensivo. No lo es: un acta que habilitase menos
    —o nada— vería su alcance ampliado en silencio hasta el máximo delegable.

    `TODO_LO_DELEGABLE` es el techo de lo que un acta *podría* delegar; el acta dice lo que delega
    *de hecho*. Confundirlos convierte un límite en un permiso."""
    rv.habilitar(tmp_path, por="ceo", acta="ACTA-ALCANCE-VACIO", alcance=())
    assert rv._alcance(tmp_path) == (), "el acta no delegó nada y eso debe respetarse"
    assert rv.en_alcance(tmp_path, "eliminar_codigo_muerto") is False
    fichero = tmp_path / "modulo.py"
    fichero.write_text("x = 1\n", encoding="utf-8")
    assert ca.clasificar({"accion": "eliminar_codigo_muerto",
                          "fichero": str(fichero)}, tmp_path) == "HUMAN"
