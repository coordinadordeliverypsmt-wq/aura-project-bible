"""Pruebas del Development Control Plane.

**Esto NO es AURORA.** Es infraestructura de desarrollo: sirve para que el trabajo sobre AURORA
pueda continuar entre sesiones sin que un humano copie mensajes de una herramienta a otra. No
concede ninguna capacidad al producto y no toca `walking-skeleton/`.

El control mas importante de este fichero es `test_nunca_afirma_cuota_desconocida`: el CEO prohibio
expresamente inventar porcentajes de cuota, y Claude Code **no expone** el consumo restante. Un
control plane que estimara «queda un 30 %» seria exactamente el patron `declarado != real` que este
proyecto lleva ocho veces persiguiendo, esta vez en la herramienta que vigila el trabajo.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

# Importacion dura, no `importorskip`: si el modulo falta, esto debe FALLAR. Un `skip` haria
# invisible la ausencia y la suite saldria verde sin haber comprobado nada.
import control_plane as cp  # noqa: E402


# ================================ VOCABULARIO DE ESTADOS · fijado por el CEO 2026-08-17 --


def test_existen_los_siete_estados_declarados_por_el_ceo():
    exigidos = {"WORKING", "WAITING_FOR_QUOTA", "WAITING_FOR_ENVIRONMENT", "DECISION_REQUIRED",
                "WAITING_FOR_HUMAN", "COMPLETED", "FAILED"}
    assert exigidos <= set(cp.ESTADOS), f"faltan: {exigidos - set(cp.ESTADOS)}"


def test_waiting_for_quota_exige_evidencia_observada():
    """Regla explicita del CEO: «No uses WAITING_FOR_QUOTA simplemente porque no puedas observar la
    cuota». Desconocerla no es haberla agotado — y confundirlo detendria el trabajo sin motivo."""
    e = cp.estado_inicial()
    e["status"] = "WAITING_FOR_QUOTA"
    with pytest.raises(ValueError, match="evidencia"):
        cp.validar(e)


def test_waiting_for_quota_es_valido_con_evidencia_observada():
    e = cp.estado_inicial()
    e["cuota"] = cp.registrar_señal_de_limite(e["cuota"], "monthly spend limit", "weekly")
    e["status"] = "WAITING_FOR_QUOTA"
    cp.validar(e)


def test_cuota_desconocida_no_impide_seguir_trabajando():
    """Si la cuota es desconocida pero se puede trabajar, el estado sigue siendo WORKING."""
    e = cp.estado_inicial()
    e["status"] = "WORKING"
    cp.validar(e)
    assert e["cuota"]["rolling_window"]["estado"] == "UNKNOWN"


def test_un_bloqueo_de_entorno_no_se_disfraza_de_cuota():
    """El bloqueo actual es de RAM, no de cuota. Etiquetarlo mal enviaria al siguiente agente a
    esperar una renovacion que no va a desbloquear nada."""
    e = cp.estado_inicial()
    e["status"] = "WAITING_FOR_ENVIRONMENT"
    e["motivo_pausa"] = "RAM disponible por debajo del umbral de carga"
    cp.validar(e)


# ============================================================== MODELO DE ESTADO --


def test_el_estado_nuevo_tiene_todos_los_campos_exigidos():
    """Los quince campos que el CEO enumero. Si falta uno, el handoff no sirve."""
    e = cp.estado_inicial()
    exigidos = {
        "status", "tarea_actual", "git", "verificacion", "defectos",
        "decisiones_pendientes", "aprobaciones", "siguiente_tarea", "checkpoint",
        "sesion_claude", "estado_ejecucion", "motivo_pausa", "cuota", "actualizado", "version",
    }
    assert exigidos <= set(e), f"faltan: {exigidos - set(e)}"


@pytest.mark.parametrize("status", list(cp.ESTADOS))
def test_todos_los_estados_declarados_son_validos(status):
    e = cp.estado_inicial()
    if status == "WAITING_FOR_QUOTA":
        # Unico estado con precondicion: exige evidencia observada de limite (ver la regla del CEO).
        e["cuota"] = cp.registrar_señal_de_limite(e["cuota"], "limite observado", "weekly")
    e["status"] = status
    cp.validar(e)


def test_un_status_inventado_se_rechaza():
    e = cp.estado_inicial()
    e["status"] = "CASI_TERMINADO"
    with pytest.raises(ValueError, match="status"):
        cp.validar(e)


def test_el_estado_va_y_vuelve_del_disco_sin_perder_nada(tmp_path):
    e = cp.estado_inicial()
    e["tarea_actual"] = {"id": "T-1", "descripcion": "probar", "alcance": ["x.py"]}
    destino = tmp_path / "estado.json"
    cp.guardar(e, destino)
    assert cp.cargar(destino)["tarea_actual"]["id"] == "T-1"


def test_la_escritura_es_atomica_y_no_deja_residuo(tmp_path):
    destino = tmp_path / "estado.json"
    cp.guardar(cp.estado_inicial(), destino)
    cp.guardar(cp.estado_inicial(), destino)
    assert list(tmp_path.glob("*.tmp")) == []
    json.loads(destino.read_text(encoding="utf-8"))


def test_cargar_un_estado_inexistente_no_inventa_uno(tmp_path):
    """Que no exista estado es informacion, no un motivo para fabricarlo."""
    assert cp.cargar(tmp_path / "no-existe.json") is None


# =========================================================== CUOTA · honestidad --


def test_nunca_afirma_un_porcentaje_de_cuota():
    """EL control central. Claude Code no expone consumo restante; afirmarlo seria inventarlo."""
    c = cp.observar_cuota()
    texto = json.dumps(c)
    assert c["usage_known"] is False
    for prohibido in ("porcentaje", "restante_pct", "consumido_pct", "%"):
        assert prohibido not in texto, f"el modelo de cuota insinua consumo: {prohibido}"


def test_las_dos_ventanas_se_modelan_por_separado():
    c = cp.observar_cuota()
    assert "rolling_window" in c and "weekly" in c
    assert c["rolling_window"] is not c["weekly"]
    for v in ("rolling_window", "weekly"):
        assert c[v]["estado"] in cp.ESTADOS_CUOTA


def test_sin_señal_observable_el_estado_de_cuota_es_desconocido():
    """No se puede saber si queda cuota semanal: el estado por defecto debe decirlo, no suponerlo."""
    c = cp.observar_cuota()
    assert c["weekly"]["estado"] == "UNKNOWN"


def test_la_ventana_movil_se_estima_solo_desde_marcas_observables(tmp_path):
    """`history.jsonl` da CUANDO hubo actividad, no cuanto se consumio. La estimacion debe
    declararse como limite de ventana, jamas como consumo."""
    hist = tmp_path / "history.jsonl"
    hist.write_text('{"timestamp": 1000000, "sessionId": "s"}\n', encoding="utf-8")
    v = cp.estimar_ventana_movil(hist, ahora_ms=1000000 + 60_000)
    assert v["estado"] in cp.ESTADOS_CUOTA
    assert "consumo" not in json.dumps(v)
    assert v["fuente"].endswith("history.jsonl")


def test_sin_history_la_ventana_es_desconocida(tmp_path):
    v = cp.estimar_ventana_movil(tmp_path / "no-existe.jsonl", ahora_ms=0)
    assert v["estado"] == "UNKNOWN"


def test_una_señal_de_limite_observada_marca_PAUSED():
    """La unica evidencia real de agotamiento es el error que devuelve la herramienta. Es una
    observacion a posteriori, no una prediccion, y asi debe registrarse."""
    c = cp.registrar_señal_de_limite(cp.observar_cuota(), "monthly spend limit", "weekly")
    assert c["weekly"]["estado"] == "PAUSED"
    assert c["weekly"]["observado_en"] and "monthly spend limit" in c["weekly"]["senal"]


# ==================================================== DECISION DE ARRANCAR TRABAJO --


def test_no_se_arranca_trabajo_costoso_con_la_ventana_pausada():
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "PAUSED"
    puede, motivo = cp.puede_empezar(c, coste="alto")
    assert puede is False and "rolling_window" in motivo


def test_la_semanal_pausada_detiene_incluso_con_ventana_normal():
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "NORMAL"
    c["weekly"]["estado"] = "PAUSED"
    assert cp.puede_empezar(c, coste="alto")[0] is False


def test_con_cuota_desconocida_se_permite_trabajo_barato_y_no_el_caro():
    """Desconocer la cuota no es tenerla: se permite lo barato y se exige prudencia con lo caro."""
    c = cp.observar_cuota()
    assert cp.puede_empezar(c, coste="bajo")[0] is True
    assert cp.puede_empezar(c, coste="alto")[0] is False


def test_las_tres_ventanas_normales_permiten_trabajo_caro():
    """Actualizada al aparecer la tercera ventana (2026-08-17): con dos en NORMAL ya no basta.
    Si bastara, el trabajo caro arrancaria con el limite mensual desconocido — que es justamente
    el que se observo agotado."""
    c = cp.observar_cuota()
    for v in cp.CLAVES_DE_CUOTA:
        c[v]["estado"] = "NORMAL"
    assert cp.puede_empezar(c, coste="alto")[0] is True


# ============================================================== GIT OBSERVADO --


def test_el_estado_de_git_se_observa_no_se_declara():
    g = cp.observar_git(AQUI)
    assert set(g) >= {"rama", "ultimo_commit", "ficheros_modificados", "limpio"}
    assert isinstance(g["ficheros_modificados"], list)


def test_los_nombres_de_fichero_no_se_truncan():
    """Un recorte por posicion fija se comia el primer caracter del nombre segun el estado del
    fichero. Se vio en un handoff real: «HECKPOINT-CONTINUIDAD.md». Un handoff con nombres
    truncados envia al siguiente agente a buscar ficheros que no existen."""
    g = cp.observar_git(AQUI.parents[1])
    for nombre in g["ficheros_modificados"]:
        assert not nombre.startswith(" ")
        assert (AQUI.parents[1] / nombre).exists() or nombre.endswith("/"), (
            f"nombre truncado o inexistente: {nombre!r}"
        )


# ================================================================== HANDOFF --


def test_el_handoff_contiene_los_trece_bloques():
    texto = cp.render_handoff(cp.estado_inicial())
    for bloque in ("STATUS", "CURRENT_TASK", "COMPLETED", "EVIDENCE", "TESTS", "QUALITY_GATE",
                   "COMMIT", "FILES_CHANGED", "DECISIONS_PENDING", "BLOCKERS", "QUOTA_STATE",
                   "NEXT_TASK", "NEXT_TASK_RATIONALE"):
        assert bloque in texto, f"falta el bloque {bloque}"


def test_el_handoff_declara_la_cuota_como_desconocida():
    """Otro agente que lea el handoff no debe deducir que hay cuota disponible."""
    assert "usage_known: false" in cp.render_handoff(cp.estado_inicial()).lower()


# ================================= TRABAJO COMPLETADO · no repetir lo ya hecho --


def test_una_tarea_completada_queda_registrada_con_su_evidencia():
    _e = cp.estado_inicial()
    cp.fijar_estado_tarea(_e, "T-1", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(_e, "T-1", "hecho", evidencia={"tests": 27}, autoridad="ceo")
    hechas = e["trabajo_completado"]
    assert len(hechas) == 1
    assert hechas[0]["id"] == "T-1" and hechas[0]["evidencia"] == {"tests": 27}
    assert hechas[0]["cuando"]


def test_una_tarea_ya_completada_no_debe_reejecutarse():
    """Requisito 14. Sin esto, un agente que reanuda repite trabajo ya hecho y lo presenta como
    nuevo — que es la forma mas cara de `declarado != real` en un relevo."""
    _e = cp.estado_inicial()
    cp.fijar_estado_tarea(_e, "T-1", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(_e, "T-1", "hecho", autoridad="ceo")
    puede, motivo = cp.debe_ejecutar(e, "T-1")
    assert puede is False and "completada" in motivo
    assert cp.debe_ejecutar(e, "T-2")[0] is True


def test_completar_dos_veces_la_misma_tarea_no_la_duplica():
    _e = cp.estado_inicial()
    cp.fijar_estado_tarea(_e, "T-1", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(_e, "T-1", "hecho", autoridad="ceo")
    e = cp.completar_tarea(e, "T-1", "hecho otra vez", autoridad="ceo")
    assert len(e["trabajo_completado"]) == 1


def test_se_registran_inicio_y_duracion_de_la_tarea():
    """El CEO pidio expresamente marca de inicio, marca de checkpoint y duracion."""
    e = cp.iniciar_tarea(cp.estado_inicial(), "T-9", "probar el registro")
    assert e["status"] == "WORKING"
    assert e["tarea_actual"]["id"] == "T-9" and e["tarea_actual"]["iniciada_en"]
    cp.fijar_estado_tarea(e, "T-9", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(e, "T-9", "listo", autoridad="ceo")
    assert e["trabajo_completado"][0]["duracion_s"] is not None


# ============================================================ LEER EL CHECKPOINT --


def test_el_control_plane_lee_el_checkpoint(tmp_path):
    """Requisito 1. Si no puede leerlo, el estado y la narrativa se separan y alguien acaba
    trabajando sobre la version equivocada."""
    doc = tmp_path / "CHECKPOINT-CONTINUIDAD.md"
    doc.write_text("# CHECKPOINT\n\n## 1 · Uno\ntexto\n\n## 2 · Dos\nmas\n", encoding="utf-8")
    info = cp.leer_checkpoint(doc)
    assert info["existe"] is True
    assert info["lineas"] == 7
    assert "1 · Uno" in info["secciones"] and "2 · Dos" in info["secciones"]
    assert info["sha256"]


def test_un_checkpoint_ausente_se_declara_ausente(tmp_path):
    info = cp.leer_checkpoint(tmp_path / "no-existe.md")
    assert info["existe"] is False and info["secciones"] == []


def test_el_estado_detecta_que_el_checkpoint_cambio(tmp_path):
    """Si el checkpoint cambio desde que se escribio el estado, el estado describe otra realidad."""
    doc = tmp_path / "CHECKPOINT-CONTINUIDAD.md"
    doc.write_text("uno\n", encoding="utf-8")
    e = cp.estado_inicial()
    e["checkpoint"] = cp.leer_checkpoint(doc)
    doc.write_text("uno\ndos\n", encoding="utf-8")
    vigente, motivo = cp.checkpoint_sin_cambios(e, doc)
    assert vigente is False and "checkpoint" in motivo.lower()


# ============================== CONTINUIDAD ENTRE SESIONES · los 8 puntos del CEO --


def test_el_estado_sobrevive_a_un_proceso_nuevo(tmp_path):
    """Puntos 1 y 6. No basta con leerlo en memoria: otra sesion de Claude Code es **otro
    proceso**, y si el estado no sobrevive a eso no sirve para continuidad."""
    import subprocess
    destino = tmp_path / "estado.json"
    e = cp.iniciar_tarea(cp.estado_inicial(), "T-VIVA", "sobrevivir a un proceso nuevo")
    e["status"] = "WAITING_FOR_ENVIRONMENT"
    e["motivo_pausa"] = "RAM insuficiente"
    cp.guardar(e, destino)

    guion = (
        "import sys; sys.path.insert(0, %r)\n"
        "import control_plane as cp, pathlib\n"
        "e = cp.cargar(pathlib.Path(%r))\n"
        "print(e['status'], e['tarea_actual']['id'], e['motivo_pausa'])\n"
    ) % (str(AQUI), str(destino))
    r = subprocess.run([sys.executable, "-c", guion], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "WAITING_FOR_ENVIRONMENT T-VIVA RAM insuficiente"


def test_esperar_entorno_no_se_convierte_en_esperar_cuota_al_persistir(tmp_path):
    """Punto 3. Confundirlos mandaria al siguiente agente a esperar una renovacion de cuota que no
    desbloquea nada: el bloqueo es de memoria."""
    destino = tmp_path / "estado.json"
    e = cp.estado_inicial()
    e["status"] = "WAITING_FOR_ENVIRONMENT"
    cp.guardar(e, destino)
    vuelto = cp.cargar(destino)
    assert vuelto["status"] == "WAITING_FOR_ENVIRONMENT"
    assert vuelto["cuota"]["senales_observadas"] == []


def test_el_handoff_no_deja_huecos_en_los_campos_criticos():
    """Punto 2. Un handoff con «(sin registrar)» donde importa obliga al siguiente agente a leer la
    conversacion entera, que es justo lo que este mecanismo evita."""
    e = cp.iniciar_tarea(cp.estado_inicial(), "T-1", "tarea")
    e["siguiente_tarea"] = {"descripcion": "lo siguiente", "motivo": "porque si"}
    e["git"] = {"rama": "r", "ultimo_commit": "abc1234", "ficheros_modificados": ["a.py"],
                "limpio": False}
    e["verificacion"] = {"tests": {"total": 1}, "quality_gate": {"resultado": "PASS"}}
    texto = cp.render_handoff(e)
    assert "(sin registrar)" not in texto.split("BLOCKERS")[0], texto


def test_el_handoff_declara_que_no_se_debe_repetir():
    """Mejora del punto 7: sin esto, el siguiente agente puede reconstruir lo ya hecho."""
    e = cp.estado_inicial()
    cp.fijar_estado_tarea(e, "T-HECHA", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(e, "T-HECHA", "listo", autoridad="ceo")
    assert "T-HECHA" in cp.render_handoff(e)


# ================================ DECISIONES · bloquean su tarea, no todo el trabajo --


def test_una_decision_pendiente_bloquea_solo_su_tarea():
    """Punto 5. `DECISION_REQUIRED` como estado global detendria tareas independientes que si
    pueden avanzar, y el trabajo se pararia entero por una decision acotada."""
    e = cp.estado_inicial()
    e["decisiones_pendientes"] = [{"id": "D-N3", "asunto": "n=3", "bloquea": ["EXP-CAMPANA"]}]
    assert cp.debe_ejecutar(e, "EXP-CAMPANA")[0] is False
    assert "D-N3" in cp.debe_ejecutar(e, "EXP-CAMPANA")[1]
    assert cp.debe_ejecutar(e, "OTRA-TAREA")[0] is True


def test_una_decision_que_bloquea_todo_se_declara_explicitamente():
    e = cp.estado_inicial()
    e["decisiones_pendientes"] = [{"id": "D-X", "asunto": "todo", "bloquea": "todo"}]
    assert cp.debe_ejecutar(e, "CUALQUIERA")[0] is False


def test_una_decision_sin_campo_bloquea_no_detiene_nada():
    """Una decision pendiente que no declara a quien afecta es informacion, no un freno: frenar por
    defecto pararia el trabajo por decisiones meramente anotadas."""
    e = cp.estado_inicial()
    e["decisiones_pendientes"] = [{"id": "D-Y", "asunto": "anotada"}]
    assert cp.debe_ejecutar(e, "CUALQUIERA")[0] is True


def test_completada_pesa_mas_que_bloqueada():
    """Si ya se hizo, no hay nada que decidir sobre ejecutarla: no se repite."""
    e = cp.estado_inicial()
    e["decisiones_pendientes"] = [{"id": "D-Z", "bloquea": ["T-1"]}]
    cp.fijar_estado_tarea(e, "T-1", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(e, "T-1", "hecho", autoridad="ceo")
    puede, motivo = cp.debe_ejecutar(e, "T-1")
    assert puede is False and "completada" in motivo


# ========================= ESTADO POR TAREA · el global no oculta el individual --
#
# Regla del CEO, 2026-08-17: pueden coexistir `EXP-REPRO: WAITING_FOR_ENVIRONMENT` y
# `EXP-CAMPANA: DECISION_REQUIRED`. **No es una contradiccion.** El estado global describe la tarea
# que el agente intenta ejecutar; las demas conservan el suyo. Colapsarlos haria que un agente
# esperase memoria por una decision pendiente, o pidiese una decision por falta de memoria.


def test_dos_tareas_conservan_estados_distintos_a_la_vez():
    e = cp.fijar_estado_tarea(cp.estado_inicial(), "EXP-REPRO", "WAITING_FOR_ENVIRONMENT", "RAM", autoridad="ceo")
    cp.fijar_estado_tarea(e, "EXP-CAMPANA", "WORKING", "empieza", autoridad="ceo")
    e = cp.fijar_estado_tarea(e, "EXP-CAMPANA", "DECISION_REQUIRED", "D-N3", autoridad="ceo")
    assert cp.estado_de_tarea(e, "EXP-REPRO")["estado"] == "WAITING_FOR_ENVIRONMENT"
    assert cp.estado_de_tarea(e, "EXP-CAMPANA")["estado"] == "DECISION_REQUIRED"


def test_una_decision_en_otra_tarea_no_cambia_la_que_espera_entorno():
    """«Nunca convertir WAITING_FOR_ENVIRONMENT → DECISION_REQUIRED solo porque existe otra tarea
    con una decision pendiente.»"""
    e = cp.fijar_estado_tarea(cp.estado_inicial(), "EXP-REPRO", "WAITING_FOR_ENVIRONMENT", "RAM", autoridad="ceo")
    e["decisiones_pendientes"] = [{"id": "D-N3", "bloquea": ["EXP-CAMPANA"]}]
    cp.fijar_estado_tarea(e, "EXP-CAMPANA", "WORKING", "empieza", autoridad="ceo")
    e = cp.fijar_estado_tarea(e, "EXP-CAMPANA", "DECISION_REQUIRED", "D-N3", autoridad="ceo")
    assert cp.estado_de_tarea(e, "EXP-REPRO")["estado"] == "WAITING_FOR_ENVIRONMENT"


def test_una_tarea_sin_estado_propio_no_hereda_el_global():
    """Heredar el global haria creer que una tarea nueva ya esta bloqueada."""
    e = cp.estado_inicial()
    e["status"] = "WAITING_FOR_ENVIRONMENT"
    assert cp.estado_de_tarea(e, "TAREA-NUEVA")["estado"] == "UNKNOWN"


def test_una_tarea_completada_se_refleja_en_su_estado_individual():
    _e = cp.estado_inicial()
    cp.fijar_estado_tarea(_e, "T-1", "WORKING", "empieza", autoridad="ceo")
    e = cp.completar_tarea(_e, "T-1", "hecho", autoridad="ceo")
    assert cp.estado_de_tarea(e, "T-1")["estado"] == "COMPLETED"


def test_un_estado_de_tarea_invalido_se_rechaza():
    with pytest.raises(ValueError):
        cp.fijar_estado_tarea(cp.estado_inicial(), "T-1", "CASI", "x", autoridad="ceo")


# ================================================ BLOQUEO POR CUOTA · dos ventanas --


def test_un_bloqueo_de_cuota_registra_todo_lo_exigido():
    e = cp.registrar_bloqueo_de_cuota(
        cp.estado_inicial(), mensaje="You've hit your monthly spend limit",
        ventana="WEEKLY", tarea="EXP-REPRO", siguiente_paso="reintentar tras renovacion")
    b = e["quota_block"]
    for campo in ("timestamp", "ventana", "mensaje", "tarea_pausada", "ultimo_paso_completado",
                  "siguiente_paso", "archivos_modificados", "pruebas_realizadas"):
        assert campo in b, f"falta {campo}"
    assert e["status"] == "WAITING_FOR_QUOTA"
    assert cp.estado_de_tarea(e, "EXP-REPRO")["estado"] == "WAITING_FOR_QUOTA"


def test_sin_evidencia_de_que_ventana_se_agoto_se_registra_UNKNOWN():
    e = cp.registrar_bloqueo_de_cuota(cp.estado_inicial(), mensaje="limit reached",
                                      ventana=None, tarea="T-1")
    assert e["quota_block"]["ventana"] == "UNKNOWN"


def test_una_ventana_no_arrastra_a_la_otra():
    """«Una renovacion de SHORT_4H30 NO implica renovacion de WEEKLY.» Si una arrastrase a la otra,
    el agente reanudaria trabajo que la cuota semanal sigue bloqueando."""
    e = cp.registrar_bloqueo_de_cuota(cp.estado_inicial(), mensaje="limit", ventana="SHORT_4H30",
                                      tarea="T-1")
    assert e["cuota"]["rolling_window"]["estado"] == "PAUSED"
    assert e["cuota"]["weekly"]["estado"] == "UNKNOWN", "la semanal no debe deducirse de la corta"


def test_una_ventana_invalida_se_rechaza():
    with pytest.raises(ValueError, match="ventana"):
        cp.registrar_bloqueo_de_cuota(cp.estado_inicial(), mensaje="x", ventana="MENSUAL",
                                      tarea="T-1")


# ================================= INTERRUPCION · nunca un COMPLETED falso --


@pytest.mark.parametrize("momento", [
    "espera_ambiental", "primera_inferencia", "segunda_inferencia", "escritura_evidencia",
    "agotamiento_cuota", "cierre_de_claude",
])
def test_una_interrupcion_no_marca_completed(momento):
    """Sin evidencia suficiente, NO se marca COMPLETED. Un COMPLETED falso hace que el siguiente
    agente de por hecho un trabajo que nunca ocurrio — y nadie lo vuelve a mirar."""
    e = cp.iniciar_tarea(cp.estado_inicial(), "EXP-REPRO", "dos inferencias")
    e = cp.interrumpir(e, "EXP-REPRO", momento)
    assert cp.estado_de_tarea(e, "EXP-REPRO")["estado"] != "COMPLETED"
    assert cp.debe_ejecutar(e, "EXP-REPRO")[0] is True, "una tarea interrumpida debe poder repetirse"
    assert "EXP-REPRO" not in [t["id"] for t in e["trabajo_completado"]]


def test_una_interrupcion_por_cuota_queda_como_esperando_cuota():
    e = cp.iniciar_tarea(cp.estado_inicial(), "T-1", "algo")
    e = cp.interrumpir(e, "T-1", "agotamiento_cuota")
    assert cp.estado_de_tarea(e, "T-1")["estado"] == "WAITING_FOR_QUOTA"


# ======================================================== AISLAMIENTO DEL PRODUCTO --


def test_el_control_plane_no_importa_nada_del_producto():
    """Regla de seguridad mas importante del encargo: esto es infraestructura externa, y AURORA
    Core no debe recibir ninguna capacidad por este trabajo."""
    fuente = (AQUI / "control_plane.py").read_text(encoding="utf-8")
    for prohibido in ("aura_skeleton", "walking-skeleton", "walking_skeleton"):
        assert prohibido not in fuente


def test_el_control_plane_vive_fuera_del_producto():
    assert "walking-skeleton" not in str(AQUI)
    assert AQUI.name == "control-plane" and AQUI.parent.name == "entorno"


def test_no_reanuda_una_tarea_sin_verificar_que_el_estado_sigue_vigente(tmp_path):
    """«No asumir que un proceso anterior termino correctamente solo porque existe un archivo de
    estado.» Si el commit registrado no es el actual, el estado esta obsoleto y debe decirlo."""
    e = cp.estado_inicial()
    e["git"]["ultimo_commit"] = "aaaaaaa"
    vigente, motivo = cp.estado_vigente(e, commit_actual="bbbbbbb")
    assert vigente is False and "commit" in motivo
    assert cp.estado_vigente(e, commit_actual="aaaaaaa")[0] is True


# ====================== TERCERA VENTANA · limite mensual de gasto, observado 2026-08-17 --
#
# Evidencia real de esta sesion: un agente auditor murio con «You've hit your monthly spend limit».
# Ese limite NO es la ventana movil de ~4 h 30 ni la semanal: se renueva por su cuenta y con otro
# criterio. Modelarlo como una de las otras dos haria que el siguiente agente dedujera una
# renovacion falsa —«ya paso el lunes, la semanal se renovo»— y volviera a chocar contra el mismo
# muro. Orden del CEO 2026-08-17: distinguir SHORT_4H30, WEEKLY y MONTHLY_SPEND_LIMIT, y marcar
# agotada **solo** la ventana de la que exista evidencia.


def test_existen_las_tres_ventanas_de_cuota_mas_la_desconocida():
    for v in ("SHORT_4H30", "WEEKLY", "MONTHLY_SPEND_LIMIT", "UNKNOWN"):
        assert v in cp.VENTANAS_CUOTA, f"falta la ventana {v}"


def test_el_limite_mensual_de_gasto_se_modela_como_ventana_propia():
    c = cp.observar_cuota()
    assert "monthly_spend" in c, "el limite mensual de gasto necesita su propia ventana"
    assert c["monthly_spend"]["estado"] == "UNKNOWN"
    assert c["monthly_spend"] is not c["weekly"] and c["monthly_spend"] is not c["rolling_window"]


def test_el_limite_mensual_observado_pausa_solo_su_ventana():
    """La evidencia observada es del limite mensual. Las otras dos NO se han observado agotadas:
    deducirlas seria inventar un bloqueo, y el agente siguiente esperaria una renovacion irreal."""
    e = cp.registrar_bloqueo_de_cuota(
        cp.estado_inicial(), mensaje="You've hit your monthly spend limit",
        ventana="MONTHLY_SPEND_LIMIT", tarea="AUDITORIA-DP-CP")
    assert e["cuota"]["monthly_spend"]["estado"] == "PAUSED"
    assert e["cuota"]["rolling_window"]["estado"] == "UNKNOWN"
    assert e["cuota"]["weekly"]["estado"] == "UNKNOWN"


def test_el_limite_mensual_no_declara_fecha_de_renovacion():
    """«No calcules una fecha de renovacion. No inventes porcentaje restante.» El unico valor
    honesto es UNKNOWN: el producto no publica cuando se renueva el limite de gasto."""
    e = cp.registrar_bloqueo_de_cuota(
        cp.estado_inicial(), mensaje="You've hit your monthly spend limit",
        ventana="MONTHLY_SPEND_LIMIT", tarea="AUDITORIA-DP-CP")
    b = e["quota_block"]
    assert b["renovacion"] == "UNKNOWN"
    assert b["tipo"] == "QUOTA_LIMIT_OBSERVED"
    texto = json.dumps(e, ensure_ascii=False)
    assert "%" not in texto.replace("100%", ""), "no se declara porcentaje de cuota"


def test_el_bloqueo_conserva_el_estado_persistente_anterior():
    """WAITING_FOR_QUOTA describe la accion; el estado que la cuota interrumpio sigue siendo cierto.
    Perderlo haria que al renovarse la cuota el agente creyera que ya no hay decisiones pendientes."""
    e = cp.estado_inicial()
    e["status"] = "DECISION_REQUIRED"
    e = cp.registrar_bloqueo_de_cuota(e, mensaje="limit", ventana="MONTHLY_SPEND_LIMIT",
                                      tarea="AUDITORIA-DP-CP")
    assert e["status"] == "WAITING_FOR_QUOTA"
    assert e["quota_block"]["estado_previo"] == "DECISION_REQUIRED"


def test_observar_el_limite_mensual_no_convierte_la_cuota_en_conocida():
    """Saber que UNA ventana se agoto no revela el consumo de ninguna. `usage_known` sigue false."""
    e = cp.registrar_bloqueo_de_cuota(cp.estado_inicial(), mensaje="limit",
                                      ventana="MONTHLY_SPEND_LIMIT", tarea="T-1")
    assert e["cuota"]["usage_known"] is False


def test_la_renovacion_del_limite_mensual_no_renueva_las_otras_dos():
    """Simetrico al caso corta/semanal: ninguna ventana arrastra a otra en ningun sentido."""
    e = cp.registrar_bloqueo_de_cuota(cp.estado_inicial(), mensaje="limit",
                                      ventana="MONTHLY_SPEND_LIMIT", tarea="T-1")
    e["cuota"]["monthly_spend"]["estado"] = "NORMAL"
    for otra in ("rolling_window", "weekly"):
        assert e["cuota"][otra]["estado"] == "UNKNOWN", (
            f"{otra} no puede heredar la renovacion del limite mensual")


def test_el_limite_mensual_pausado_solo_detiene_el_trabajo_que_lo_necesita():
    """CORREGIDA con la evidencia visual del CEO (2026-08-17): la version anterior de esta prueba
    afirmaba que agotar el uso adicional detiene TODO el trabajo. Es falso, y era una prueba que
    protegia una creencia equivocada — el peor tipo de prueba, porque impide corregir el defecto.

    Uso adicional agotado (USD 21,84 / USD 20,00) con sesion al 26 % y semanal al 56 %, ambas
    DISPONIBLES: el trabajo que cabe en la capacidad incluida **puede seguir**."""
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "NORMAL"
    c["weekly"]["estado"] = "NORMAL"
    c["monthly_spend"]["estado"] = "PAUSED"
    assert cp.puede_empezar(c, coste="alto")[0] is True, "la capacidad incluida sigue disponible"
    assert cp.puede_empezar(c, coste="bajo")[0] is True
    puede, motivo = cp.puede_empezar(c, coste="alto", requiere_uso_adicional=True)
    assert puede is False and "monthly_spend" in motivo


def test_registrar_señal_de_limite_acepta_la_ventana_mensual():
    c = cp.registrar_señal_de_limite(cp.observar_cuota(), "monthly spend limit", "monthly_spend")
    assert c["monthly_spend"]["estado"] == "PAUSED"
    assert c["monthly_spend"]["observado_en"] is not None


def test_un_estado_antiguo_sin_ventana_mensual_se_carga_como_desconocida(tmp_path):
    """Los estados escritos antes de existir esta ventana deben seguir cargando. Ausencia de dato
    es UNKNOWN — nunca NORMAL, que seria afirmar margen que nadie ha observado."""
    e = cp.estado_inicial()
    del e["cuota"]["monthly_spend"]
    destino = tmp_path / "estado.json"
    destino.write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    recargado = cp.cargar(destino)
    assert recargado["cuota"]["monthly_spend"]["estado"] == "UNKNOWN"
    cp.validar(recargado)


def test_el_handoff_declara_las_tres_ventanas():
    e = cp.registrar_bloqueo_de_cuota(cp.estado_inicial(), mensaje="monthly spend limit",
                                      ventana="MONTHLY_SPEND_LIMIT", tarea="AUDITORIA-DP-CP")
    texto = cp.render_handoff(e)
    for etiqueta in ("rolling_window", "weekly", "monthly_spend"):
        assert etiqueta in texto, f"el handoff no menciona {etiqueta}"


def test_una_tarea_parada_por_cuota_no_bloquea_una_tarea_independiente():
    """Requisito 5 del CEO: el bloqueo por cuota es de la tarea que lo sufrio, no del proyecto.
    Si contagiara, el trabajo local y determinista —documentar, revisar, ordenar— se pararia sin
    motivo justo cuando es lo unico que todavia se puede hacer."""
    e = cp.estado_inicial()
    e = cp.fijar_estado_tarea(e, "TAREA-LOCAL", "WORKING", "trabajo local sin llamadas", autoridad="ceo")
    e = cp.registrar_bloqueo_de_cuota(e, mensaje="monthly spend limit",
                                      ventana="MONTHLY_SPEND_LIMIT", tarea="AUDITORIA-DP-CP")
    assert cp.estado_de_tarea(e, "AUDITORIA-DP-CP")["estado"] == "WAITING_FOR_QUOTA"
    assert cp.estado_de_tarea(e, "TAREA-LOCAL")["estado"] == "WORKING"
    puede, _ = cp.debe_ejecutar(e, "TAREA-LOCAL")
    assert puede is True, "una tarea independiente no se frena por la cuota de otra"


# ============ TRES VENTANAS INDEPENDIENTES · evidencia visual del CEO, 2026-08-17 --
#
# Pagina oficial de uso del plan Pro, leida por el CEO:
#   sesion actual .... 26 % usado · se restablece en ~4 h 8 min · DISPONIBLE
#   limite semanal ... 56 % usado · se restablece el domingo a las 3:59 a. m. · DISPONIBLE
#   uso adicional .... USD 21,84 gastados sobre un limite mensual de USD 20,00 = 109 % · PAUSADO
#
# Esto REFUTA la lectura que se hizo del mensaje «You've hit your monthly spend limit». No
# significaba «Claude Code agotado»: significaba «el uso adicional de pago esta agotado», con la
# capacidad incluida del plan todavia disponible. La distincion no es academica — la lectura
# equivocada para el trabajo que si se puede hacer.


def test_la_capacidad_incluida_y_el_uso_adicional_son_grupos_distintos():
    assert cp.CAPACIDAD_INCLUIDA == ("rolling_window", "weekly")
    assert cp.USO_ADICIONAL == ("monthly_spend",)
    assert set(cp.CAPACIDAD_INCLUIDA) | set(cp.USO_ADICIONAL) == set(cp.CLAVES_DE_CUOTA)


def test_el_uso_adicional_agotado_no_bloquea_el_trabajo_barato():
    """El caso exacto de esta sesion. Si bloqueara, el unico trabajo que todavia es posible
    —documentar, revisar, ordenar el estado— se pararia sin ningun motivo real."""
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "NORMAL"
    c["weekly"]["estado"] = "NORMAL"
    c["monthly_spend"]["estado"] = "PAUSED"
    assert cp.puede_empezar(c, coste="bajo")[0] is True


def test_el_uso_adicional_desconocido_no_impide_usar_capacidad_incluida_conocida():
    """Desconocer el uso adicional no es haberlo agotado, y menos aun agota lo incluido."""
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "NORMAL"
    c["weekly"]["estado"] = "NORMAL"
    assert c["monthly_spend"]["estado"] == "UNKNOWN"
    assert cp.puede_empezar(c, coste="alto")[0] is True


def test_una_ventana_incluida_pausada_si_detiene_aunque_el_uso_adicional_este_normal():
    """Simetria: pagar uso adicional no resucita una sesion agotada dentro del modelo. Sin
    evidencia de que lo haga, afirmarlo seria inventar una capacidad."""
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "PAUSED"
    c["weekly"]["estado"] = "NORMAL"
    c["monthly_spend"]["estado"] = "NORMAL"
    puede, motivo = cp.puede_empezar(c, coste="bajo")
    assert puede is False and "rolling_window" in motivo


def test_un_porcentaje_observado_se_registra_con_su_fuente_y_su_instante():
    """El CEO leyo porcentajes reales en la pagina oficial: registrarlos NO es inventarlos. Pero
    son una INSTANTANEA que caduca — sin fuente e instante volverian a leerse manana como si
    siguieran siendo ciertos."""
    c = cp.registrar_uso_observado(cp.observar_cuota(), "rolling_window", porcentaje_usado=26,
                                   fuente="pagina oficial de uso, leida por el CEO",
                                   observado_en="2026-08-17", estado="NORMAL")
    v = c["rolling_window"]
    assert v["porcentaje_usado_observado"] == 26
    assert v["fuente"] and v["observado_en"]
    assert v["caduca"] is True, "una instantanea no es un estado permanente"
    assert v["estado"] == "NORMAL"


def test_registrar_uso_observado_no_convierte_la_cuota_en_publicada_por_la_herramienta():
    """`usage_known` describe si CLAUDE CODE publica el consumo. Sigue sin hacerlo: el dato vino de
    un humano mirando una web. Ponerlo en true haria creer al siguiente agente que puede
    consultarlo por su cuenta."""
    c = cp.registrar_uso_observado(cp.observar_cuota(), "weekly", porcentaje_usado=56,
                                   fuente="pagina oficial de uso", observado_en="2026-08-17",
                                   estado="NORMAL")
    assert c["usage_known"] is False


def test_no_se_registra_un_porcentaje_sin_fuente():
    with pytest.raises(ValueError, match="fuente"):
        cp.registrar_uso_observado(cp.observar_cuota(), "weekly", porcentaje_usado=56,
                                   fuente="", observado_en="2026-08-17", estado="NORMAL")


def test_el_handoff_distingue_uso_adicional_bloqueado_de_capacidad_incluida_agotada():
    """Quien retome el trabajo debe poder leer en una linea que puede seguir trabajando."""
    c = cp.observar_cuota()
    c["rolling_window"]["estado"] = "NORMAL"
    c["weekly"]["estado"] = "NORMAL"
    c["monthly_spend"]["estado"] = "PAUSED"
    e = cp.estado_inicial()
    e["cuota"] = c
    texto = cp.render_handoff(e)
    assert "capacidad incluida: DISPONIBLE" in texto
    assert "uso adicional: BLOQUEADO" in texto
