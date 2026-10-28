"""B2 · el ciclo completo TASK -> RESULT -> ACK, ejercitado con DOBLES locales.

**Ninguna prueba invoca `claude -p`. Coste: cero.** El objetivo es que, cuando el CEO autorice la
invocacion real, la unica incognita que quede sea **si el agente sigue la instruccion**; todo lo
demas —transporte, enlace, veredicto del envoltorio, rechazo de un resultado falso y ausencia de
respuesta— queda demostrado antes y gratis.

Los dos ayudantes de abajo son **la logica de P1**, el emisor-verificador. Se prueban aqui y se
promoveran a modulo el dia que B2 se autorice; hoy viven en la prueba para no ampliar el alcance de
B1, que el CEO delimito en once simbolos.

**La trampa que la escenario 2 vigila esta MEDIDA, no supuesta:** `claude -p --output-format json`
devolvio `is_error: true` **junto a** `subtype: "success"` con codigo de retorno 1. Un verificador
que mire `subtype` da por buena una ejecucion fallida.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import communication_plane as cp  # noqa: E402, I001

A, B, SUMA_ESPERADA = 17, 25, 42


# ------------------------------------------------------------------ logica de P1 --


def veredicto_de_envoltorio(sobre: dict) -> tuple[bool, str]:
    """El exito se decide por `is_error`, NUNCA por `subtype`.

    Ausencia de dato no es dato: si falta `is_error`, el resultado es desconocido, no bueno."""
    if "is_error" not in sobre:
        raise ValueError("el envoltorio no trae `is_error`: el resultado es desconocido")
    if sobre["is_error"]:
        return False, f"is_error=true (terminal_reason={sobre.get('terminal_reason')!r})"
    return True, "ejecucion correcta"


def verificar_respuesta(canal: cp.Canal, id_tarea: str, esperado: int) -> tuple[bool, str]:
    """Los criterios 3-6 del plan, sin juicio: existe, esta enlazado, el valor es el correcto y la
    secuencia sigue siendo monotona."""
    respuestas = [m for m in canal.leer_desde(seq=1)
                  if m["tipo"] == "RESULT" and m.get("in_reply_to") == id_tarea]
    if not respuestas:
        return False, "sin RESULT enlazado a la tarea"
    r = respuestas[-1]
    if r["cuerpo"].get("suma") != esperado:
        return False, f"suma incorrecta: {r['cuerpo'].get('suma')!r} != {esperado}"
    seqs = [m["seq"] for m in canal.leer_desde(seq=1)]
    if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
        return False, "la secuencia dejo de ser monotona"
    return True, r["id"]


def _publicar_tarea(canal: cp.Canal) -> str:
    return canal.publicar(
        tipo="TASK", de="orquestador-local", para="claude-code",
        cuerpo={"objetivo": "sumar", "a": A, "b": B,
                "instruccion": "publica un RESULT con in_reply_to a este mensaje y cuerpo.suma"})


def _ciclo(canal: cp.Canal, doble) -> tuple[str | None, str]:
    """Ejecuta el ciclo de P1. Devuelve (id del ACK o None, motivo).

    **Nunca cierra la tarea si algo falla**, que es la garantia que separa esto de un teatro."""
    id_tarea = _publicar_tarea(canal)
    sobre = doble(canal, id_tarea)
    correcta, motivo = veredicto_de_envoltorio(sobre)
    if not correcta:
        return None, motivo
    valida, detalle = verificar_respuesta(canal, id_tarea, SUMA_ESPERADA)
    if not valida:
        return None, detalle
    ack = canal.publicar(tipo="ACK", de="orquestador-local", para="claude-code",
                         cuerpo={"verificado": True}, in_reply_to=detalle)
    return ack, "ok"


# ------------------------------------------------------------------ los cuatro dobles --


def doble_cumplidor(canal: cp.Canal, id_tarea: str) -> dict:
    tarea = canal.leer(id_tarea)
    canal.publicar(tipo="RESULT", de="claude-code", para="orquestador-local",
                   cuerpo={"suma": tarea["cuerpo"]["a"] + tarea["cuerpo"]["b"]},
                   in_reply_to=id_tarea)
    return {"is_error": False, "subtype": "success", "total_cost_usd": 0.0}


def doble_que_falla_pero_dice_success(canal: cp.Canal, id_tarea: str) -> dict:
    """Publica un RESULT PERFECTO y aun asi el envoltorio dice que fallo. Si P1 mirase el canal en
    vez del envoltorio, daria por buena una ejecucion que la herramienta declaro fallida."""
    canal.publicar(tipo="RESULT", de="claude-code", para="orquestador-local",
                   cuerpo={"suma": SUMA_ESPERADA}, in_reply_to=id_tarea)
    return {"is_error": True, "subtype": "success", "terminal_reason": "api_error"}


def doble_con_resultado_incorrecto(canal: cp.Canal, id_tarea: str) -> dict:
    canal.publicar(tipo="RESULT", de="claude-code", para="orquestador-local",
                   cuerpo={"suma": SUMA_ESPERADA - 1}, in_reply_to=id_tarea)
    return {"is_error": False, "subtype": "success"}


def doble_que_no_responde(canal: cp.Canal, id_tarea: str) -> dict:
    """Timeout: el proceso murio o expiro. No escribe nada."""
    return {"is_error": False, "subtype": "success"}


# ------------------------------------------------------------------ los cuatro escenarios --


def test_escenario_1_ciclo_completo_task_result_ack(tmp_path):
    """El caso feliz, extremo a extremo sobre disco real."""
    canal = cp.abrir(tmp_path)
    ack, motivo = _ciclo(canal, doble_cumplidor)

    assert ack is not None, f"el ciclo no se cerro: {motivo}"
    mensajes = canal.leer_desde(seq=1)
    assert [m["tipo"] for m in mensajes] == ["TASK", "RESULT", "ACK"]
    assert canal.leer(ack)["cuerpo"]["verificado"] is True
    assert [m["seq"] for m in mensajes] == [1, 2, 3]


def test_escenario_2_is_error_true_con_subtype_success_no_cierra(tmp_path):
    """**La trampa medida.** El RESULT es correcto y aun asi NO se acepta: manda `is_error`."""
    canal = cp.abrir(tmp_path)
    ack, motivo = _ciclo(canal, doble_que_falla_pero_dice_success)

    assert ack is None, "se cerro una tarea cuya ejecucion la herramienta declaro fallida"
    assert "is_error" in motivo
    assert not [m for m in canal.leer_desde(seq=1) if m["tipo"] == "ACK"]


def test_escenario_3_resultado_incorrecto_no_cierra(tmp_path):
    """El envoltorio dice que todo fue bien; el contenido no cumple el criterio."""
    canal = cp.abrir(tmp_path)
    ack, motivo = _ciclo(canal, doble_con_resultado_incorrecto)

    assert ack is None, "se cerro una tarea con un resultado que no cumple el criterio"
    assert "suma incorrecta" in motivo
    assert not [m for m in canal.leer_desde(seq=1) if m["tipo"] == "ACK"]


def test_escenario_4_sin_respuesta_no_marca_completed(tmp_path):
    """Ausencia de respuesta. **Nunca `COMPLETED`**: sin evidencia, el estado honesto es el que dice
    que no hubo respuesta."""
    canal = cp.abrir(tmp_path)
    ack, motivo = _ciclo(canal, doble_que_no_responde)

    assert ack is None
    assert motivo == "sin RESULT enlazado a la tarea"
    assert [m["tipo"] for m in canal.leer_desde(seq=1)] == ["TASK"]
    assert "COMPLETED" not in motivo.upper()


def test_un_envoltorio_sin_is_error_no_se_interpreta_como_exito():
    """CASO DE CONTROL. Sin el, los cuatro escenarios no distinguirian «el veredicto funciona» de
    «el veredicto siempre dice que si»."""
    with pytest.raises(ValueError, match="is_error"):
        veredicto_de_envoltorio({"subtype": "success"})


def test_control_el_verificador_acepta_lo_que_debe_aceptar(tmp_path):
    """CASO DE CONTROL simetrico: si `verificar_respuesta` rechazara siempre, los escenarios 2-4
    pasarian por el motivo equivocado."""
    canal = cp.abrir(tmp_path)
    id_tarea = _publicar_tarea(canal)
    doble_cumplidor(canal, id_tarea)
    valida, _ = verificar_respuesta(canal, id_tarea, SUMA_ESPERADA)
    assert valida is True
