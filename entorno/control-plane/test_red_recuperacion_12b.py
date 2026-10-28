"""RED · las tres filas del `§12 · Recuperación` que quedaban declaradas y sin implementar.

Medido `[EJEC]` con `grep` sobre los módulos de producción antes de escribir este fichero:

| Fila del `§12` | Estado |
|---|---|
| *«Tarea ejecutada dos veces → mismo `--session-id` derivado → **detectada; la segunda no se registra**»* | el id ya se deriva bien —se arregló al cerrar el `§13`— pero **nada lo consulta**. *Detectable* no es *detectado* |
| *«Respuesta duplicada → mismo `review_id` → **segunda descartada por idempotencia**»* | `review_id` **no existe** en ninguna parte. `responder_buzon` devuelve un veredicto nuevo cada vez que se la llama |
| *«Respuesta del revisor perdida → sin evento → **reintento acotado, luego `DECISION_REQUIRED`**»* | sin contador de reintentos ni ruta a `DECISION_REQUIRED`, aunque la tabla de `§6` la permite |

Las tres son idempotencia, y la idempotencia es lo que distingue un sistema que se puede reintentar
sin miedo de uno en el que cada reintento es una apuesta. `§13` lo dice del `--session-id`: *«la doble
ejecución es **detectable**, no una cuestión de disciplina»*. Hoy dependía de la disciplina.
"""

from __future__ import annotations

import control_plane as cp
import orquestador as orq
import pytest
import revisores as rev


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


TAREA = {"id": "T-1", "accion": "ejecutar_pruebas", "objetivo": "batería en verde",
         "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}}


def _expediente(tarea_id="T-R"):
    return rev.Expediente(tarea_id=tarea_id, accion="eliminar_codigo_muerto",
                          fichero="entorno/control-plane/orquestador.py",
                          diagnostico="función privada sin uso", criterios={"cumple": True})


def _en_curso(d, ident="T-R", accion="eliminar_codigo_muerto"):
    cp.registrar_evento(d, "tarea_registrada", {"id": ident, "accion": accion})
    cp.transicion(d, ident, "WORKING", autoridad="ceo", causa="empieza")


# ================== §12 · TAREA EJECUTADA DOS VECES --


def test_una_sesion_ya_ejecutada_se_DETECTA(tmp_path):
    """`§13` promete que la doble ejecución es *«detectable, no una cuestión de disciplina»*. Para
    que lo sea hace falta que alguien **mire**."""
    sesion = orq.WorkerAdapter().session_id(TAREA)
    assert not orq.sesion_ya_ejecutada(tmp_path, sesion)
    orq.registrar_sesion(tmp_path, TAREA["id"], sesion)
    assert orq.sesion_ya_ejecutada(tmp_path, sesion)


def test_la_segunda_ejecucion_de_la_MISMA_tarea_con_el_MISMO_sobre_NO_se_registra(tmp_path):
    """*«Detectada; la segunda no se registra»*, literal. Dos ciclos seguidos sobre la misma tarea
    intacta: se invoca **una vez**."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    invocadas = []
    for _ in range(2):
        o = orq.Orquestador(tmp_path)
        o.worker.invocar = lambda t: invocadas.append(t["id"])
        o.ciclo(max_iteraciones=3)
    assert invocadas == ["T-1"], f"la ejecutó {len(invocadas)} veces: {invocadas}"


def test_el_ciclo_dice_POR_QUE_se_detuvo_cuando_la_sesion_ya_corrio(tmp_path):
    """Un ciclo que no hace nada y dice «sin tareas ejecutables» miente: la tarea está ahí y es
    ejecutable — lo que pasa es que ya se ejecutó. Confundir las dos causas hace que un operador
    busque el problema donde no está."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    o = orq.Orquestador(tmp_path)
    o.worker.invocar = lambda _t: None
    o.ciclo(max_iteraciones=3)
    segundo = orq.Orquestador(tmp_path)
    segundo.worker.invocar = lambda _t: None
    assert segundo.ciclo(max_iteraciones=3)["motivo"] == "sesión ya ejecutada"


def test_si_el_SOBRE_cambia_la_tarea_SI_se_vuelve_a_ejecutar(tmp_path):
    """Caso de control, y la mitad que da sentido al `§13`: el id deriva del sobre, así que cambiar
    el criterio de finalización **es otra ejecución** y debe correr. Sin esto, la detección sería un
    «una vez y nunca más» que impediría reintentar con otros parámetros."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    o = orq.Orquestador(tmp_path)
    o.worker.invocar = lambda _t: None
    o.ciclo(max_iteraciones=3)

    otra = {**TAREA, "id": "T-2", "criterio_de_finalizacion": {"capacidad": "verificar_calidad"}}
    cp.registrar_evento(tmp_path, "tarea_registrada", otra)
    invocadas = []
    dos = orq.Orquestador(tmp_path)
    dos.worker.invocar = lambda t: invocadas.append(t["id"])
    dos.ciclo(max_iteraciones=3)
    assert invocadas == ["T-2"]


def test_la_deteccion_de_sesion_sobrevive_al_REINICIO(tmp_path):
    """Vive en el log, no en memoria. Un contador en memoria se pierde con el proceso, y el caso que
    `§12` cubre es precisamente el proceso que se murió."""
    sesion = orq.WorkerAdapter().session_id(TAREA)
    orq.registrar_sesion(tmp_path, TAREA["id"], sesion)
    assert orq.sesion_ya_ejecutada(tmp_path, sesion), "otro proceso lo lee del historial"


# ================== §12 · RESPUESTA DE REVISOR DUPLICADA --


def test_cada_peticion_de_revision_lleva_un_review_id_DERIVADO(tmp_path):
    """Derivado y no aleatorio, por la misma razón que el `--session-id`: dos peticiones del mismo
    expediente tienen que ser reconocibles como la misma, o la idempotencia depende de que nadie se
    equivoque."""
    uno = rev.review_id(_expediente())
    otro = rev.review_id(_expediente())
    assert uno == otro
    assert uno != rev.review_id(_expediente("T-OTRA"))


def test_la_SEGUNDA_respuesta_al_mismo_review_id_se_DESCARTA(tmp_path):
    """`§12`: *«Respuesta duplicada → mismo `review_id` → segunda descartada por idempotencia»*."""
    _en_curso(tmp_path)
    expediente = _expediente()
    rev.pedir_revision(tmp_path, expediente, [rev.RevisorHumano(tmp_path)], autoridad="orquestador")
    primera = rev.responder_buzon(tmp_path, "T-R", "conforme", por="ceo",
                                  evidencia_citada=("orquestador.py:1",))
    with pytest.raises(rev.RespuestaDuplicada):
        rev.responder_buzon(tmp_path, "T-R", "rechazo", por="ceo",
                            evidencia_citada=("orquestador.py:2",))
    assert primera.veredicto == "conforme", "manda la primera: la segunda no la reescribe"


def test_la_respuesta_duplicada_NO_cambia_el_veredicto_registrado(tmp_path):
    """La garantía por el **efecto**, no por la excepción: si el segundo veredicto llegara a
    escribirse antes de rechazarse, quien lea el log vería el rechazo y no el conforme."""
    _en_curso(tmp_path, "T-D")
    rev.pedir_revision(tmp_path, _expediente("T-D"), [rev.RevisorHumano(tmp_path)],
                       autoridad="orquestador")
    rev.responder_buzon(tmp_path, "T-D", "conforme", por="ceo", evidencia_citada=("x.py:1",))
    with pytest.raises(rev.RespuestaDuplicada):
        rev.responder_buzon(tmp_path, "T-D", "rechazo", por="ceo", evidencia_citada=("x.py:2",))
    emitidos = [e["datos"] for e in cp.leer_eventos(tmp_path)
                if e["tipo"] == "veredicto_emitido" and e["datos"]["id"] == "T-D"]
    assert len(emitidos) == 1 and emitidos[0]["veredicto"] == "conforme"


def test_dos_tareas_distintas_pueden_responderse_las_dos(tmp_path):
    """Caso de control: la idempotencia es por `review_id`, no un candado global."""
    for ident in ("T-A", "T-B"):
        _en_curso(tmp_path, ident)
        rev.pedir_revision(tmp_path, _expediente(ident), [rev.RevisorHumano(tmp_path)],
                           autoridad="orquestador")
        veredicto = rev.responder_buzon(tmp_path, ident, "conforme", por="ceo",
                                        evidencia_citada=("x.py:1",))
        assert veredicto.veredicto == "conforme"


# ================== §12 · RESPUESTA DEL REVISOR PERDIDA --


def test_sin_respuesta_se_REINTENTA_de_forma_acotada(tmp_path):
    """`§12`: *«Reintento acotado»*. Acotado es la palabra: un reintento sin tope es un bucle, y el
    `§14` prohíbe los bucles sin cota."""
    _en_curso(tmp_path, "T-P")
    expediente = _expediente("T-P")
    for _ in range(2):
        resultado = rev.pedir_revision(tmp_path, expediente, [rev.RevisorLocal()],
                                       autoridad="orquestador", max_reintentos=3)
        assert resultado["estado"] == cp.ESTADO_REVISION
    assert rev.intentos_de_revision(tmp_path, "T-P") == 2


def test_agotados_los_reintentos_la_tarea_pasa_a_DECISION_REQUIRED(tmp_path):
    """*«…luego `DECISION_REQUIRED`»*. Y es lo correcto: si nadie puede revisarla y ya se intentó
    cuanto se acordó, la decisión de qué hacer con ella es humana. Lo que **no** puede pasar es que
    espere para siempre en silencio, que es lo que hacía."""
    _en_curso(tmp_path, "T-Q")
    expediente = _expediente("T-Q")
    for _ in range(3):
        rev.pedir_revision(tmp_path, expediente, [rev.RevisorLocal()], autoridad="orquestador",
                           max_reintentos=3)
    final = rev.pedir_revision(tmp_path, expediente, [rev.RevisorLocal()], autoridad="orquestador",
                              max_reintentos=3)
    assert final["estado"] == "DECISION_REQUIRED"
    assert cp.estado_de(tmp_path, "T-Q") == "DECISION_REQUIRED"


def test_pasar_a_DECISION_REQUIRED_no_es_aprobar(tmp_path):
    """`1.1:85`. Agotar los reintentos escala la decisión; **no** la resuelve. Si esto acabara en
    `COMPLETED`, el timeout habría producido una aprobación por cansancio."""
    _en_curso(tmp_path, "T-Z")
    for _ in range(4):
        rev.pedir_revision(tmp_path, _expediente("T-Z"), [rev.RevisorLocal()],
                           autoridad="orquestador", max_reintentos=3)
    assert cp.estado_de(tmp_path, "T-Z") != "COMPLETED"
    assert cp.estado_de(tmp_path, "T-Z") == "DECISION_REQUIRED"


def test_un_revisor_que_SI_responde_no_gasta_reintentos(tmp_path):
    """Caso de control: el contador cuenta ausencias, no revisiones."""
    _en_curso(tmp_path, "T-OK")
    resultado = rev.pedir_revision(tmp_path, _expediente("T-OK"), [rev.RevisorSubagente()],
                                   autoridad="orquestador", max_reintentos=3)
    assert resultado["veredicto"] is not None
    assert rev.intentos_de_revision(tmp_path, "T-OK") == 0
