"""RED · B3 — el segundo tipo de agente en el canal (`DEC-B3-QUE-AGENTE` = OpenCode bajo demanda).

Las siete evidencias: las seis de B2 más **quién firma el RESULT**. Esa séptima es la razón de ser
de B3: con dos agentes distintos en el mismo canal, confundir al emisor haría que la respuesta de B2
pasara por el resultado de B3 y el experimento no probaría nada.

**Los dobles ejercen el ciclo entero antes de instalar nada**, igual que hizo B2 antes de gastar su
invocación.
"""

from __future__ import annotations

import communication_plane as cp
from verificador_b3 import AGENTE_B3, publicar_tarea_b3, veredicto, verificar_b3

SOBRE_OK = {"is_error": False, "subtype": "success", "total_cost_usd": 0.0,
            "usage": {"output_tokens": 5}}


def _canal(tmp_path):
    return cp.abrir(str(tmp_path))


def _responde(canal, id_tarea, de=AGENTE_B3, suma=42):
    return canal.publicar(tipo="RESULT", de=de, para="orquestador-local",
                          cuerpo={"suma": suma}, in_reply_to=id_tarea)


# ================================================================ META-CONTROL --


def test_doble_del_segundo_agente_da_las_SIETE_evidencias(tmp_path):
    """Sin este control, un verificador que negara siempre pasaría toda la batería."""
    canal = _canal(tmp_path)
    tid = publicar_tarea_b3(canal)
    _responde(canal, tid)
    ev = verificar_b3(canal, tid, SOBRE_OK, codigo_salida=0)
    assert all(ev.values()), f"faltan: {[k for k, v in ev.items() if not v]}"
    assert veredicto(ev) == "GREEN"


def test_la_TASK_va_dirigida_al_segundo_agente(tmp_path):
    """`para="opencode"`. El canal es agnóstico del destinatario y no se toca por esto."""
    canal = _canal(tmp_path)
    t = canal.leer(publicar_tarea_b3(canal))
    assert t["para"] == AGENTE_B3 and t["cuerpo"]["a"] == 17 and t["cuerpo"]["b"] == 25


# ======================================= LA SÉPTIMA · los agentes no se confunden --


def test_una_respuesta_firmada_por_el_agente_de_B2_no_vale_para_B3(tmp_path):
    """**El falso verde que B3 debe impedir.** El RESULT es correcto en todo salvo en quién lo
    firma: si eso pasara, B3 estaría dando por bueno el trabajo de B2."""
    canal = _canal(tmp_path)
    tid = publicar_tarea_b3(canal)
    _responde(canal, tid, de="claude-code")

    ev = verificar_b3(canal, tid, SOBRE_OK, codigo_salida=0)
    assert ev["suma_correcta"] and ev["responde_a_la_tarea"], "el resto debe estar bien"
    assert not ev["lo_firma_el_segundo_agente"]
    assert veredicto(ev) != "GREEN"


def test_las_seis_evidencias_de_B2_siguen_exigiendose(tmp_path):
    """B3 no relaja B2: hereda sus seis y añade una."""
    canal = _canal(tmp_path)
    tid = publicar_tarea_b3(canal)
    _responde(canal, tid, suma=41)
    ev = verificar_b3(canal, tid, SOBRE_OK, codigo_salida=0)
    assert not ev["suma_correcta"] and veredicto(ev) != "GREEN"


def test_sin_RESULT_el_canal_esta_sano_y_el_agente_no_siguio(tmp_path):
    canal = _canal(tmp_path)
    tid = publicar_tarea_b3(canal)
    ev = verificar_b3(canal, tid, SOBRE_OK, codigo_salida=0)
    assert ev["integridad"] and not ev["hay_result"]
    assert veredicto(ev) == "CANAL_OK_AGENTE_NO_SIGUIO"


def test_un_sobre_con_is_error_no_es_GREEN(tmp_path):
    canal = _canal(tmp_path)
    tid = publicar_tarea_b3(canal)
    _responde(canal, tid)
    ev = verificar_b3(canal, tid, {"is_error": True, "subtype": "success"}, codigo_salida=0)
    assert not ev["sin_error_en_sobre"] and veredicto(ev) != "GREEN"


# ============================ INTEGRACIÓN · B2 y B3 conviven en el mismo canal --


def test_B2_y_B3_conviven_sin_confundirse(tmp_path):
    """`FASE 5`: dos tareas, dos agentes, un solo canal. Cada RESULT debe poder distinguirse, y un
    fallo de uno no puede corromper al otro."""
    canal = _canal(tmp_path)
    from verificador_b2 import publicar_tarea, verificar_b2

    tid_b2 = publicar_tarea(canal)                       # para="claude-code"
    tid_b3 = publicar_tarea_b3(canal)                    # para="opencode"
    canal.publicar(tipo="RESULT", de="claude-code", para="orquestador-local",
                   cuerpo={"suma": 42}, in_reply_to=tid_b2)
    _responde(canal, tid_b3)

    ev_b2 = verificar_b2(canal, tid_b2, SOBRE_OK, codigo_salida=0)
    ev_b3 = verificar_b3(canal, tid_b3, SOBRE_OK, codigo_salida=0)
    assert veredicto(ev_b2) == "GREEN" and veredicto(ev_b3) == "GREEN"
    assert canal.verificar_integridad()["integro"] is True
    assert [m["seq"] for m in canal.leer_desde(seq=0)] == [1, 2, 3, 4], "la secuencia debe ser continua"


def test_un_B3_fallido_no_corrompe_el_resultado_de_B2(tmp_path):
    """El aislamiento que `FASE 5` exige demostrar."""
    canal = _canal(tmp_path)
    from verificador_b2 import publicar_tarea, verificar_b2

    tid_b2 = publicar_tarea(canal)
    canal.publicar(tipo="RESULT", de="claude-code", para="orquestador-local",
                   cuerpo={"suma": 42}, in_reply_to=tid_b2)
    tid_b3 = publicar_tarea_b3(canal)
    _responde(canal, tid_b3, suma=999)                   # B3 responde mal

    assert veredicto(verificar_b2(canal, tid_b2, SOBRE_OK, codigo_salida=0)) == "GREEN"
    assert veredicto(verificar_b3(canal, tid_b3, SOBRE_OK, codigo_salida=0)) != "GREEN"
    assert canal.verificar_integridad()["integro"] is True
