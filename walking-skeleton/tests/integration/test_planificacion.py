"""Integracion: AURORA crea su propio trabajo a partir de evidencia, sin que nadie lo escriba.

CRITERIO DE EXITO DEL CEO (2026-08-03): "¿AURORA es capaz de producir una nueva tarea util sin que un
humano la escriba?". Estas pruebas responden esa pregunta, y ademas demuestran que **no puede generar
trabajo infinito** — por construccion, no por un contador.
"""

import pytest

from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.planificacion import (
    CEO,
    DERIVADO,
    AdmisionRechazada,
    admitir,
    desde_verificacion,
    id_desde_evidencia,
)


def _almacen(tmp_path):
    return AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl"))


def _tarea_humana(alm, tid="t-01"):
    return alm.registrar(Tarea(objetivo_id="obj", tarea_id=tid, estado="en_curso", responsable="qa", origen=CEO))


def test_una_verificacion_fallida_PRODUCE_una_tarea_sin_intervencion_humana(tmp_path):
    """EL SALTO: nadie escribio esta tarea. Nacio de la evidencia de un fallo."""
    alm = _almacen(tmp_path)
    causa = _tarea_humana(alm)

    nueva = desde_verificacion(alm, causa, {"ok": False, "capacidad": "verificar_calidad", "resumen": "2 failed"})

    assert nueva is not None, "un fallo de verificacion debe producir trabajo"
    assert nueva.origen == DERIVADO and nueva.responsable == "programador"
    assert nueva.prioridad == 1, "un fallo bloquea el avance: debe atenderse antes que lo demas"
    assert any("2 failed" in e for e in nueva.evidencias), "la tarea debe conservar su causa verificable"
    # y queda en el backlog persistido, no en memoria
    assert AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl")).tarea("obj", nueva.tarea_id) is not None


def test_una_verificacion_EN_VERDE_no_genera_trabajo(tmp_path):
    """CONTROL NEGATIVO: sin fallo no hay nada que corregir. Sin esto, AURORA se daria trabajo sola."""
    alm = _almacen(tmp_path)
    assert desde_verificacion(alm, _tarea_humana(alm), {"ok": True, "capacidad": "verificar_calidad"}) is None


def test_la_misma_evidencia_REUTILIZA_la_tarea_en_vez_de_duplicarla(tmp_path):
    """Deduplicacion determinista por identificador derivado, igual que `rule_id` en las reglas."""
    alm = _almacen(tmp_path)
    causa = _tarea_humana(alm)
    res = {"ok": False, "capacidad": "verificar_calidad", "resumen": "2 failed"}

    a = desde_verificacion(alm, causa, res)
    b = desde_verificacion(alm, causa, res)

    assert a.tarea_id == b.tarea_id
    assert len(alm.tareas("obj")) == 2, "solo la humana y UNA derivada; la segunda vuelta no duplico"


def test_EL_TRABAJO_DERIVADO_NO_PUEDE_ENGENDRAR_MAS_TRABAJO(tmp_path):
    """EL CORTE ESTRUCTURAL (patron de D-A-3): la generacion infinita es IMPOSIBLE, no improbable.

    No hay contador ni limite de iteraciones: sencillamente una tarea derivada no puede derivar otra.
    La cadena mide como maximo 1, siempre.
    """
    alm = _almacen(tmp_path)
    derivada = desde_verificacion(alm, _tarea_humana(alm), {"ok": False, "capacidad": "x", "resumen": "fallo"})

    with pytest.raises(AdmisionRechazada, match="no puede engendrar"):
        desde_verificacion(alm, derivada, {"ok": False, "capacidad": "y", "resumen": "otro fallo"})


def test_no_se_admite_trabajo_sin_causa_verificable(tmp_path):
    alm = _almacen(tmp_path)
    with pytest.raises(AdmisionRechazada, match="causa verificable"):
        admitir(alm, objetivo_id="obj", descripcion="algo", responsable="qa", evidencia="")


def test_no_se_admite_trabajo_sin_objetivo_padre_ni_responsable(tmp_path):
    alm = _almacen(tmp_path)
    with pytest.raises(AdmisionRechazada):
        admitir(alm, objetivo_id="", descripcion="algo", responsable="qa", evidencia="e")
    with pytest.raises(AdmisionRechazada):
        admitir(alm, objetivo_id="obj", descripcion="algo", responsable="", evidencia="e")


def test_una_derivada_debe_declarar_su_causa(tmp_path):
    alm = _almacen(tmp_path)
    with pytest.raises(AdmisionRechazada, match="declarar la tarea que la causo"):
        admitir(alm, objetivo_id="obj", descripcion="x", responsable="qa", evidencia="e", origen=DERIVADO)


def test_la_prioridad_decide_que_se_atiende_primero(tmp_path):
    """El fallo de verificacion (prioridad 1) se atiende antes que el trabajo ordinario (5)."""
    alm = _almacen(tmp_path)
    # El id ordinario ordena ANTES alfabeticamente que el derivado ("a-" < "auto-"): asi la unica
    # forma de que gane el urgente es la PRIORIDAD. Sin este detalle la prueba pasaba por accidente
    # y la mutacion lo detecto (M5 sobrevivia).
    alm.registrar(Tarea(objetivo_id="obj", tarea_id="a-ordinaria", estado="abierta", prioridad=5))
    urgente = admitir(
        alm, objetivo_id="obj", descripcion="urgente", responsable="programador", evidencia="fallo", prioridad=1
    )

    assert alm.reanudar("obj").tarea_id == urgente.tarea_id, "la prioridad no decidio el orden"


def test_el_identificador_es_estable_entre_procesos():
    """Determinista: la misma evidencia produce la misma clave siempre, en cualquier arranque."""
    assert id_desde_evidencia("misma causa") == id_desde_evidencia("misma causa")
    assert id_desde_evidencia("a") != id_desde_evidencia("b")


def test_el_origen_generico_HUMANO_ya_no_existe(tmp_path):
    """Debe fallar si alguien reintroduce un origen generico.

    "humano" englobaba al CEO y a la asistencia externa en la misma etiqueta, y por tanto BORRABA la
    unica distincion que la metrica de dependencia externa necesita medir. Un valor que destruye la
    informacion que se quiere observar no es un valor por defecto comodo: es un punto ciego.
    """
    from aura_skeleton.core.planificacion import ORIGENES

    assert "humano" not in ORIGENES, "el origen generico no puede volver: elimina lo que se quiere medir"
    assert set(ORIGENES) == {"ceo", "asistencia_externa", "derivado"}

    with pytest.raises(AdmisionRechazada, match="exactamente uno"):
        admitir(_almacen(tmp_path), objetivo_id="o", descripcion="x", responsable="qa", evidencia="e", origen="humano")


def test_no_existe_origen_implicito_desconocido_ni_vacio(tmp_path):
    """Toda tarea pertenece EXACTAMENTE a uno de los tres origenes."""
    alm = _almacen(tmp_path)
    for invalido in ("", "desconocido", "otro", None):
        with pytest.raises(AdmisionRechazada, match="origen no valido"):
            admitir(alm, objetivo_id="o", descripcion="x", responsable="qa", evidencia="e", origen=invalido)


def test_la_asistencia_externa_SI_puede_engendrar_trabajo_derivado(tmp_path):
    """Un cambio propuesto por un modelo externo es trabajo legitimo: puede generar correccion."""
    from aura_skeleton.core.planificacion import ASISTENCIA_EXTERNA

    alm = _almacen(tmp_path)
    causa = alm.registrar(
        Tarea(objetivo_id="obj", tarea_id="t-ext", estado="en_curso", responsable="qa", origen=ASISTENCIA_EXTERNA)
    )
    nueva = desde_verificacion(alm, causa, {"ok": False, "capacidad": "verificar_calidad", "resumen": "falla"})
    assert nueva is not None and nueva.origen == DERIVADO
