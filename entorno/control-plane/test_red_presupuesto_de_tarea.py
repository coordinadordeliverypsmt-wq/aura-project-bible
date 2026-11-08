"""Agotar el presupuesto de una tarea deja constancia (CEO, 2026-09-20).

EL SILENCIO, MEDIDO. `planificador.elegible()` concede una tarea revertida *«mientras quede
presupuesto»* y la apaga al llegar a `TOPE_DE_REINTENTOS`. A partir de ahí devuelve `False` para
siempre y la tarea **desaparece de la cola sin que nada lo diga**: no hay evento, no hay motivo, no
hay id. Un humano auditando `eventos.jsonl` tendría que reconstruir a mano
`intentos_de(t) >= TOPE and not completada(t)` sobre cada tarea del historial para descubrir que una
oportunidad autorizada quedó abandonada.

POR QUÉ ES UN DEFECTO Y NO UNA OMISIÓN MENOR. Es el patrón «declarado ≠ real» que este proyecto ya
ha pagado ocho veces, aplicado al **trabajo pendiente** en vez de a la capacidad declarada: el
diagnóstico sigue informando de una oportunidad real que el motor ya nunca va a intentar. El propio
plano se lo exige a todo lo demás —*«un ciclo sin rastro no es auditable»*—, y aquí faltaba.

QUÉ NO CAMBIA ESTE FICHERO. No cambia el tope, no cambia `elegible()`, no reabre ninguna tarea
apagada y no concede autoridad: **solo hace visible una decisión que el motor ya tomaba en
silencio**. La tarea sigue apagándose exactamente cuando se apagaba.

QUÉ QUEDA FUERA, A PROPÓSITO. Que una tarea revertida detenga el ciclo ENTERO —incluso cuando las
demás tocan ficheros ajenos— es una decisión de diseño declarada: *«el árbol roto es peor que no
haber hecho nada»*. Relajarla es frontera del CEO, no trabajo técnico, y no se toca aquí.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import descubrimiento as des
import motor_autonomia as motor
import planificador as plan
import review
import pytest

#: El tipo de evento que da constancia. Se afirma sobre la constante del módulo y no sobre el
#: literal: si alguien la renombra, esta prueba viaja con ella en vez de quedarse mirando un texto.
TIPO = "presupuesto_de_tarea_agotado"


@pytest.fixture(autouse=True)
def _el_arnes_no_esta_corriendo(monkeypatch):
    import orquestador as orq
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _plano_con_una_tarea(base: pathlib.Path) -> pathlib.Path:
    """Un plano mínimo con UNA sola oportunidad, para que el presupuesto se agote sin ruido."""
    zona = base / "entorno" / "control-plane"
    zona.mkdir(parents=True, exist_ok=True)
    (zona / "modulo.py").write_text(
        "def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n", encoding="utf-8")
    review.habilitar(zona, alcance=("eliminar_codigo_muerto",), por="ceo",
                     acta="DEC-ORCH-2 del CEO")
    return zona


def _agotar(zona: pathlib.Path) -> None:
    """Gasta el presupuesto entero: tantas vueltas como reintentos permite el tope, todas fallando.

    Cada llamada a `trabajar()` consume un intento porque la verificación siempre dice que no. No se
    fuerza nada: es el camino real del motor con una batería en rojo.
    """
    for _ in range(plan.TOPE_DE_REINTENTOS):
        motor.trabajar(zona, zona, verificacion=lambda raiz: False, max_tareas=1)


def _eventos(zona: pathlib.Path, tipo: str) -> list:
    return [e for e in cp.leer_eventos(zona) if e["tipo"] == tipo]


# ============================================================ LA CONSTANCIA --


def test_al_agotar_el_presupuesto_queda_constancia_en_el_historial(tmp_path):
    """RED el 2026-09-20: la tarea se apagaba y el log no decía nada."""
    zona = _plano_con_una_tarea(tmp_path)

    _agotar(zona)

    registrados = _eventos(zona, TIPO)
    assert registrados, (
        f"la tarea agoto sus {plan.TOPE_DE_REINTENTOS} intentos y desaparecio de la cola sin dejar "
        f"rastro: nadie puede saber que una oportunidad autorizada quedo abandonada")


def test_la_constancia_dice_QUE_tarea_y_CUANTOS_intentos(tmp_path):
    """«Se agoto algo» no es un informe. Sin identidad ni cuenta, el evento no se puede auditar."""
    zona = _plano_con_una_tarea(tmp_path)

    _agotar(zona)

    datos = _eventos(zona, TIPO)[-1]["datos"]
    assert datos.get("id"), "el evento no dice QUE tarea se apago"
    assert datos.get("intentos") == plan.TOPE_DE_REINTENTOS, "el evento no dice cuantos intentos costo"
    assert datos.get("origen"), "el evento no enlaza con la oportunidad de la que vino"


def test_la_constancia_coincide_con_lo_que_elegible_decide(tmp_path):
    """La prueba de control del propio evento: lo que se registra tiene que ser lo que pasa.

    Un evento que dijera «agotado» mientras `elegible()` sigue concediendo la tarea sería peor que
    el silencio — un informe que miente cuesta más que uno que falta.
    """
    zona = _plano_con_una_tarea(tmp_path)

    _agotar(zona)

    id_agotada = _eventos(zona, TIPO)[-1]["datos"]["id"]
    assert plan.elegible(zona, id_agotada) is False, "se registro agotada una tarea que sigue viva"
    assert plan.completada(zona, id_agotada) is False, "no estaba completada: estaba abandonada"


# ============================================================ NI ANTES, NI DE MAS --


def test_ANTES_de_agotarlo_no_se_registra_nada(tmp_path):
    """Un solo intento fallido deja presupuesto: registrarlo ya sería declarar muerta a una viva."""
    zona = _plano_con_una_tarea(tmp_path)

    motor.trabajar(zona, zona, verificacion=lambda raiz: False, max_tareas=1)

    assert _eventos(zona, TIPO) == [], "se declaro agotada una tarea que todavia tenia presupuesto"


def test_una_tarea_que_SE_COMPLETA_no_deja_constancia_de_agotamiento(tmp_path):
    """Caso de control. Sin esto, la garantía se cumpliría registrando el evento siempre."""
    zona = _plano_con_una_tarea(tmp_path)

    motor.trabajar(zona, zona, verificacion=lambda raiz: True, max_tareas=1)

    assert _eventos(zona, TIPO) == []
    assert "_muerta" not in (zona / "modulo.py").read_text(encoding="utf-8"), (
        "la prueba no ejercito el camino feliz: el codigo muerto sigue ahi")


def test_no_se_registra_DOS_VECES_la_misma_tarea(tmp_path):
    """Volver a mirar no es volver a agotar. Un log que repite el mismo hecho deja de ser un conteo."""
    zona = _plano_con_una_tarea(tmp_path)
    _agotar(zona)
    cuantos = len(_eventos(zona, TIPO))

    motor.trabajar(zona, zona, verificacion=lambda raiz: False, max_tareas=1)

    assert len(_eventos(zona, TIPO)) == cuantos, "el agotamiento se registro por duplicado"


# ============================================================ NO CONCEDE NADA --


def test_la_constancia_no_reabre_la_tarea_ni_amplia_nada(tmp_path):
    """Dejar constancia es informar, no perdonar: la tarea sigue apagada y la cola, sin ella."""
    zona = _plano_con_una_tarea(tmp_path)
    _agotar(zona)
    id_agotada = _eventos(zona, TIPO)[-1]["datos"]["id"]

    oportunidades = des.descubrir(zona, zona)
    cola = plan.cola(zona, oportunidades)

    assert id_agotada not in [t["id"] for t in cola], "la tarea agotada volvio a la cola"
    assert plan.TOPE_DE_REINTENTOS == 2, "el tope no se toca en este incremento"


def test_el_evento_de_agotamiento_NO_es_un_evento_gobernado(tmp_path):
    """No concede estado ni autoridad: es trazabilidad. Gobernarlo seria confundir informar con permitir."""
    assert TIPO not in cp.EVENTOS_GOBERNADOS


def test_registrar_DOS_VECES_no_duplica_la_constancia(tmp_path):
    """La idempotencia, ejercida donde de verdad se puede ejercer.

    Por la vía del ciclo el guardia es inalcanzable: al agotar el presupuesto la tarea deja de ser
    elegible, así que el motor nunca vuelve a revertirla y nunca vuelve a llamar aquí. Lo descubrió
    el mutante PP-M3 al sobrevivir. Pero la función **promete** no duplicar, y una promesa que nadie
    comprueba es la clase de garantía que este proyecto llama declarada y no real: se comprueba
    llamándola dos veces, que es exactamente lo que dice que soporta.
    """
    zona = _plano_con_una_tarea(tmp_path)
    _agotar(zona)
    cuantos = len(_eventos(zona, TIPO))
    assert cuantos == 1, "el montaje no dejo la constancia que esta prueba necesita"

    tarea = {"id": _eventos(zona, TIPO)[-1]["datos"]["id"], "origen": "OP-x"}
    motor._registrar_si_agoto_su_presupuesto(zona, tarea)
    motor._registrar_si_agoto_su_presupuesto(zona, tarea)

    assert len(_eventos(zona, TIPO)) == cuantos, "la constancia se duplico al volver a registrarla"
