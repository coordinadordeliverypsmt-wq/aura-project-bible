"""Reintento gobernado — **`tarea_planificada` no es `tarea_completada`**.

## El defecto

`planificador.cola()` excluia toda tarea con un evento `tarea_planificada`. La constancia se deja
**antes** de ejecutar —y debe seguir siendo asi: es lo que impide que un proceso muerto a mitad
reejecute—, pero tratarla como resultado quema la tarea aunque el intento **revirtiera y no dejara
nada**. Es la misma clase de defecto que `registrar_planificada` ya documenta en su propio docstring
—*«marcar el resultado antes de tenerlo… quemaba toda tarea AUTO en su primer intento»*—, reaparecida
un escalon mas arriba.

## La regla, y de donde sale

No se inventa una politica de reintentos: el plano ya la tiene escrita. `agentes.ejecutar_tarea` acota
con `max_intentos=2`, y `revisores.py:379` la enuncia — *«reintento **acotado**, luego
DECISION_REQUIRED»*, con su motivo: *«un reintento sin tope es un bucle»*. Se reutiliza ese tope.

Asi que una reversion **no** concede permiso permanente: concede el resto de un presupuesto acotado.
Agotado, la tarea se apaga y hace falta evidencia nueva —una oportunidad distinta, con otra
identidad— para volver a intentarlo.

## El enlace intento -> resultado

No hace falta ningun campo nuevo. El historial es secuencial y append-only: entre una
`tarea_planificada` y la siguiente, el `cambio_aplicado` que aparezca pertenece a la primera. Se
comprueba contra el log real, que lo cumple en los cuatro intentos que existen.
"""

import autoconstruccion as ac
import control_plane as cp
import planificador as pl


def _planificar(d, id_tarea, accion="eliminar_codigo_muerto"):
    pl.registrar_planificada(d, {"id": id_tarea, "origen": "OP-x", "accion": accion,
                                 "fichero": "m.py", "riesgo": "bajo"})


def _resultado(d, propuesta, *, revertido):
    cp.registrar_evento(d, "cambio_aplicado", {"id": propuesta, "fichero": "m.py",
                                               "simbolo": "_x", "efecto_verificado": True,
                                               "verificacion_sana": not revertido,
                                               "revertido": revertido, "autoridad": "orquestador"})


# --------------------------------------------------------------------- la semantica nueva --

def test_1_una_tarea_COMPLETADA_no_se_reintenta(tmp_path):
    _planificar(tmp_path, "TA-1")
    _resultado(tmp_path, "P-1", revertido=False)
    assert pl.completada(tmp_path, "TA-1") is True
    assert pl.elegible(tmp_path, "TA-1") is False


def test_2_una_tarea_PENDIENTE_no_se_duplica(tmp_path):
    """Planificada y sin resultado: puede estar corriendo. **Fail-closed**: no se reofrece."""
    _planificar(tmp_path, "TA-2")
    assert pl.resultado_de(tmp_path, "TA-2") is None
    assert pl.elegible(tmp_path, "TA-2") is False


def test_3_una_tarea_REVERTIDA_no_es_una_tarea_completada(tmp_path):
    _planificar(tmp_path, "TA-3")
    _resultado(tmp_path, "P-3", revertido=True)
    assert pl.completada(tmp_path, "TA-3") is False


def test_4_una_tarea_revertida_vuelve_a_ser_elegible_dentro_del_presupuesto(tmp_path):
    _planificar(tmp_path, "TA-4")
    _resultado(tmp_path, "P-4", revertido=True)
    assert pl.intentos_de(tmp_path, "TA-4") == 1
    assert pl.elegible(tmp_path, "TA-4") is True


def test_7_dos_reversiones_agotan_el_presupuesto_y_NO_hay_bucle(tmp_path):
    """La proteccion contra el bucle, ejercida: reversion tras reversion se apaga sola."""
    for n in range(pl.TOPE_DE_REINTENTOS):
        assert pl.elegible(tmp_path, "TA-7") is True, f"intento {n + 1} deberia poder correr"
        _planificar(tmp_path, "TA-7")
        _resultado(tmp_path, f"P-7{n}", revertido=True)
    assert pl.intentos_de(tmp_path, "TA-7") == pl.TOPE_DE_REINTENTOS
    assert pl.elegible(tmp_path, "TA-7") is False, "un reintento sin tope es un bucle"


def test_el_tope_no_es_un_numero_inventado():
    """Sale del modelo que ya existe en este plano, no de una preferencia."""
    import inspect
    import agentes as ag
    assert pl.TOPE_DE_REINTENTOS == inspect.signature(ag.ejecutar_tarea).parameters["max_intentos"].default


def test_8_fail_closed_si_la_evidencia_no_alcanza(tmp_path):
    """Sin ningun evento, una tarea nunca planificada es elegible; con planificacion y sin
    resultado, no. La duda nunca concede."""
    assert pl.elegible(tmp_path, "TA-NUEVA") is True
    _planificar(tmp_path, "TA-NUEVA")
    assert pl.elegible(tmp_path, "TA-NUEVA") is False


def test_6_el_historial_del_primer_intento_permanece(tmp_path):
    _planificar(tmp_path, "TA-6")
    _resultado(tmp_path, "P-6", revertido=True)
    _planificar(tmp_path, "TA-6")
    _resultado(tmp_path, "P-6b", revertido=False)
    planificadas = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "tarea_planificada"]
    resultados = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "cambio_aplicado"]
    assert len(planificadas) == 2 and len(resultados) == 2, "no se borra ni se reescribe nada"
    assert resultados[0]["datos"]["revertido"] is True, "el primer intento sigue diciendo la verdad"
    assert pl.completada(tmp_path, "TA-6") is True


def test_5_el_segundo_intento_recibe_una_propuesta_NUEVA(tmp_path):
    """La identidad de la **tarea** es la misma —es el mismo trabajo—; la del **intento** no: cada
    ejecucion crea su propia propuesta `P-NNN`. No se reutiliza la historica."""
    objetivo = tmp_path / "entorno" / "control-plane" / "m.py"
    objetivo.parent.mkdir(parents=True)
    objetivo.write_text("def _a():\n    return 1\n", encoding="utf-8")
    p1 = ac.proponer(tmp_path, {"fichero": str(objetivo), "simbolo": "_a"})
    p2 = ac.proponer(tmp_path, {"fichero": str(objetivo), "simbolo": "_a"})
    assert p1["id"] != p2["id"], "cada intento es una propuesta distinta"


def test_el_enlace_intento_resultado_sale_del_orden_del_log(tmp_path):
    """Entre una planificacion y la siguiente, el resultado pertenece a la primera. Sin campos
    nuevos: el historial ya es secuencial y append-only (`ADR-0023`)."""
    _planificar(tmp_path, "TA-A")
    _resultado(tmp_path, "P-A", revertido=True)
    _planificar(tmp_path, "TA-B")
    _resultado(tmp_path, "P-B", revertido=False)
    assert pl.resultado_de(tmp_path, "TA-A")["id"] == "P-A"
    assert pl.resultado_de(tmp_path, "TA-B")["id"] == "P-B"


def test_la_cola_respeta_la_nueva_elegibilidad(tmp_path, monkeypatch):
    """La regla no vive en dos sitios: `cola()` pregunta a `elegible()`."""
    import inspect
    fuente = inspect.getsource(pl.cola)
    assert "elegible(" in fuente and "ya_planificada(" not in fuente


def test_ya_planificada_sigue_existiendo_y_sigue_diciendo_la_verdad(tmp_path):
    """No se retira: sigue respondiendo «¿se planifico alguna vez?», que es su pregunta."""
    _planificar(tmp_path, "TA-Z")
    assert pl.ya_planificada(tmp_path, "TA-Z") is True
