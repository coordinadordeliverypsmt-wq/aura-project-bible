"""RED · F5/D-ORCH-6 = WAITING_FOR_HUMAN alcanzable y gobernado.

El defecto (ver `.claude/ficha-evidencia.md` del incremento): `TRANSICIONES["WAITING_FOR_HUMAN"]`
ya tenia SALIDAS (`WORKING`, `FAILED`) desde F1, pero ningun estado lo tenia como DESTINO, asi que
era INALCANZABLE desde el flujo real. El CEO autorizo el 2026-11-08 enmendar la tabla para darle
entrada desde `WORKING` (auto-stop legitimo, analogo a `DECISION_REQUIRED`), y exige una guarda
ANTI-AUTOAUTORIZACION: solo una autoridad humana (`AUTORIDADES_HUMANAS`) puede reanudar el trabajo
(`WAITING_FOR_HUMAN -> WORKING`). Abandonar/fallar desde esa espera (`WAITING_FOR_HUMAN -> FAILED`)
sigue abierto a cualquier autoridad, igual que antes de este incremento.

Cada caso positivo lleva su opuesto como control, siguiendo el patron de
`test_red_f1_orquestador.py::test_a5_DECISION_REQUIRED_no_se_resuelve_sin_acto_humano`.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import pytest


def _dir(tmp_path):
    return pathlib.Path(tmp_path)


def _tarea_en_waiting_for_human(d, id_tarea="T-WFH", autoridad_entrada="orquestador"):
    """Lleva una tarea nueva hasta WAITING_FOR_HUMAN por la via legitima: WORKING primero."""
    cp.registrar_evento(d, "tarea_registrada", {"id": id_tarea})
    cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="empieza")
    cp.transicion(d, id_tarea, "WAITING_FOR_HUMAN", autoridad=autoridad_entrada,
                  causa="necesito que un humano decida algo")
    return id_tarea


# =================================== (a) entrada: WORKING -> WAITING_FOR_HUMAN --


def test_a_working_a_waiting_for_human_permitida_con_cualquier_autoridad(tmp_path):
    """Entrada: cualquier autoridad (agente u orquestador) puede declarar que necesita un humano."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    cp.transicion(d, "T-1", "WAITING_FOR_HUMAN", autoridad="orquestador",
                  causa="necesito confirmacion del CEO")
    assert cp.estado_de(d, "T-1") == "WAITING_FOR_HUMAN"


def test_a_control_working_a_estado_no_listado_sigue_rechazada(tmp_path):
    """Control de (a): la tabla sigue siendo selectiva, no "todo vale desde WORKING"."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    with pytest.raises(cp.TransicionInvalida, match="prohibida"):
        cp.transicion(d, "T-1", "WAITING_FOR_NEXT_TASK", autoridad="orquestador", causa="x")


# ============================ (b)/(c) continuacion: WAITING_FOR_HUMAN -> WORKING --


@pytest.mark.parametrize("autoridad_humana", ["ceo", "humano"])
def test_b_waiting_for_human_a_working_con_autoridad_humana_permitida(tmp_path, autoridad_humana):
    """Positiva continuacion humana: cualquier miembro de AUTORIDADES_HUMANAS puede reanudar."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d)
    cp.transicion(d, id_tarea, "WORKING", autoridad=autoridad_humana, causa="decidido")
    assert cp.estado_de(d, id_tarea) == "WORKING"


def test_c_waiting_for_human_a_working_sin_autoridad_humana_rechazada(tmp_path):
    """Negativa autoautorizacion: el propio agente/orquestador NO puede reanudarse a si mismo."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d)
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="sigo solo")
    # Control: el estado NO cambio tras el intento rechazado.
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN"


@pytest.mark.parametrize("autoridad_no_humana", ["agente", "orquestador", "revisor", ""])
def test_c_barrido_ninguna_autoridad_no_humana_reanuda(tmp_path, autoridad_no_humana):
    """Barrido adicional: ninguna cadena fuera de AUTORIDADES_HUMANAS sirve para reanudar."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d, id_tarea=f"T-{autoridad_no_humana or 'vacia'}")
    assert autoridad_no_humana not in cp.AUTORIDADES_HUMANAS
    with pytest.raises(cp.TransicionInvalida):
        cp.transicion(d, id_tarea, "WORKING", autoridad=autoridad_no_humana, causa="sigo")
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN"


# ========================== (d) salida FAILED: no exige autoridad humana --


def test_d_waiting_for_human_a_failed_sin_autoridad_humana_rechazada(tmp_path):
    """SIMETRIA TOTAL con DECISION_REQUIRED (auditoria de seguridad F5): salir de una espera humana
    hacia FAILED TAMBIEN exige autoridad humana. Antes se eximia este caso, y eso componia una
    evasion en dos pasos (ver test_cadena_... abajo). El estado NO cambia tras el intento."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d)
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, id_tarea, "FAILED", autoridad="orquestador", causa="se abandona la espera")
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN"


@pytest.mark.parametrize("autoridad_humana", ["ceo", "humano"])
def test_d_waiting_for_human_a_failed_con_autoridad_humana_permitida(tmp_path, autoridad_humana):
    """Positivo de (d): con autoridad humana, abandonar la espera hacia FAILED si es legal."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d, id_tarea=f"T-FAIL-{autoridad_humana}")
    cp.transicion(d, id_tarea, "FAILED", autoridad=autoridad_humana, causa="el humano decide abortar")
    assert cp.estado_de(d, id_tarea) == "FAILED"


def test_d_control_working_a_failed_sigue_abierto_a_cualquier_autoridad(tmp_path):
    """Control de (d): la restriccion es ESPECIFICA de los ESTADOS_SOLO_HUMANO, no un cerrojo
    general sobre FAILED. Desde WORKING -origen NO solo-humano- cualquier autoridad puede ir a
    FAILED, como siempre. Esto demuestra que no se ha cerrado FAILED en general, solo su entrada
    desde una espera humana."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    cp.transicion(d, "T-1", "FAILED", autoridad="orquestador", causa="fallo tecnico")
    assert cp.estado_de(d, "T-1") == "FAILED"


def test_cadena_waiting_for_human_failed_working_no_evade_la_autoridad_humana(tmp_path):
    """NUCLEO DEL HALLAZGO (auditoria de seguridad + correccion, F5). La evasion que se cierra:
    una autoridad NO humana intentaba componer `WAITING_FOR_HUMAN -> FAILED -> WORKING`
    -cada paso legal por separado- para reanudarse SIN que mediara ningun humano. La correccion
    rompe la cadena en su PRIMER paso: `WAITING_FOR_HUMAN -> FAILED` por autoridad no humana se
    bloquea, asi que la tarea NUNCA llega a FAILED y no hay desde donde encadenar a WORKING."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d, id_tarea="T-CADENA")
    # Paso 1 de la evasion: bloqueado. La tarea sigue en WAITING_FOR_HUMAN.
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, id_tarea, "FAILED", autoridad="orquestador", causa="paso 1 de la evasion")
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN", (
        "si la tarea hubiese llegado a FAILED, FAILED -> WORKING (reintento sin guarda) completaria "
        "la autoautorizacion en dos pasos")

    # CONTROL POSITIVO: con autoridad humana el camino legitimo si existe. Un humano saca la tarea
    # de la espera hacia FAILED, y SOLO ENTONCES el reintento FAILED -> WORKING vuelve a estar
    # disponible -pero ya ha mediado un humano para salir de la espera, que es justo la garantia-.
    cp.transicion(d, id_tarea, "FAILED", autoridad="ceo", causa="el humano decide abortar")
    assert cp.estado_de(d, id_tarea) == "FAILED"
    cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="reintento tras fallo")
    assert cp.estado_de(d, id_tarea) == "WORKING"


# ==================== (e) transicion invalida desde WAITING_FOR_HUMAN --


def test_e_waiting_for_human_a_estado_no_listado_rechazada(tmp_path):
    """Desde WAITING_FOR_HUMAN solo WORKING y FAILED son destinos legales; el resto, rechazado."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d)
    with pytest.raises(cp.TransicionInvalida, match="prohibida"):
        cp.transicion(d, id_tarea, "COMPLETED", autoridad="ceo", causa="se da por cerrada")
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN"


# ==================== (f) creacion directa en WAITING_FOR_HUMAN: rechazada --


def test_f_crear_tarea_directamente_en_waiting_for_human_rechazada(tmp_path):
    """WAITING_FOR_HUMAN sigue sin ser creable: declara espera humana sobre trabajo EN CURSO,
    y crearla ya ahi fabricaria una decision pendiente que nadie pidio."""
    with pytest.raises(cp.TransicionInvalida, match="WAITING_FOR_HUMAN|crear"):
        cp.validar_transicion(cp.ESTADO_SIN_REGISTRAR, "WAITING_FOR_HUMAN",
                               autoridad="ceo", causa="arranca ya esperando")


def test_f_control_waiting_for_quota_si_sigue_siendo_creable(tmp_path):
    """Control de (f): la restriccion es especifica de WAITING_FOR_HUMAN, no general."""
    cp.validar_transicion(cp.ESTADO_SIN_REGISTRAR, "WAITING_FOR_QUOTA",
                           autoridad="ceo", causa="arranca bloqueada por cuota")


# ===================== (g) alcanzabilidad ESTRUCTURAL (barrido, no lista a mano) --


def test_g_waiting_for_human_es_destino_de_al_menos_un_estado():
    """La prueba que falta era exactamente esta: antes de F5/D-ORCH-6, WAITING_FOR_HUMAN tenia
    SALIDAS (TRANSICIONES["WAITING_FOR_HUMAN"]) pero cero ENTRADAS, y por eso era inalcanzable.
    Barre TRANSICIONES.values() -no una lista escrita a mano- para que no quede huerfano otra vez.
    """
    destinos_alcanzables = {destino for destinos in cp.TRANSICIONES.values() for destino in destinos}
    assert "WAITING_FOR_HUMAN" in destinos_alcanzables, (
        "WAITING_FOR_HUMAN no aparece como destino de ningun estado en TRANSICIONES: "
        "sigue siendo inalcanzable desde el flujo")


def test_g_control_completed_sigue_siendo_destino_pero_nunca_origen():
    """Control de (g): COMPLETED es destino (alcanzable) pero su propia entrada en TRANSICIONES
    es la tupla vacia (final, no es origen de nada) - el barrido distingue ambos roles."""
    destinos_alcanzables = {destino for destinos in cp.TRANSICIONES.values() for destino in destinos}
    assert "COMPLETED" in destinos_alcanzables
    assert cp.TRANSICIONES["COMPLETED"] == ()


# ==================== (h) PARADA/kill_switch: fuera de este modulo, no se relaja --


def test_h_la_guarda_humana_no_vive_en_kill_switch_y_no_se_relaja():
    """PARADA/kill-switch NO vive en `control_plane.py` (confirmado por inspeccion: el unico
    hallazgo es una referencia textual a "otros modulos" en un comentario, sin implementacion
    aqui). Esta prueba documenta esa frontera y confirma que la guarda anti-autoautorizacion de
    WAITING_FOR_HUMAN no depende de, ni relaja, ningun mecanismo de parada: es una propiedad de
    `validar_transicion` por si misma, exigida sin condiciones externas."""
    import inspect
    fuente = inspect.getsource(cp)
    assert "kill_switch" not in fuente.lower().replace("kill-switch", "kill_switch") or \
        "otros modulos" in fuente, (
            "si apareciera un kill_switch implementado aqui, esta prueba debe revisarse: "
            "la guarda humana de WAITING_FOR_HUMAN debe seguir exigiendose igual con o sin el")
    # La guarda en si, repetida como control directo: sigue exigiendose sin ninguna bandera de
    # PARADA de por medio (no existe tal parametro en la firma de validar_transicion).
    firma = inspect.signature(cp.validar_transicion)
    assert list(firma.parameters) == ["previo", "valor", "autoridad", "causa"], (
        "validar_transicion no debe ganar un parametro de PARADA que permita relajar la guarda")


def test_h_control_la_guarda_se_exige_igual_sin_ninguna_bandera_adicional(tmp_path):
    """Control de (h): sin kill_switch de por medio, la guarda sigue siendo la misma (c)."""
    d = _dir(tmp_path)
    id_tarea = _tarea_en_waiting_for_human(d, id_tarea="T-PARADA")
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="reanudo sin humano")
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN"
