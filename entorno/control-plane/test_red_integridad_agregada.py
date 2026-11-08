"""F3 — INDICADOR AGREGADO de integridad (solo lectura). RED antes que GREEN.

`integridad_del_control_plane(directorio)` consolida F1 (`estado_de_la_proyeccion`) en un veredicto
agregado:

    {integridad: "ok"|"degradada"|"no_verificable", verificable, proyeccion,
     regeneracion_pendiente, seq_confirmado, seq_proyeccion?, motivo}

No regenera (no llama a `regenerar_proyeccion`), no escribe, no es una segunda fuente de verdad
(solo lee F1). Separa INTEGRIDAD de AUTORIZACION (PARADA) y de DISPONIBILIDAD (cola): no las
consulta ni las mezcla en el veredicto.

Reglas de mapeo (ver ficha de evidencia):
  - PROYECCION_ACTUAL         -> integridad="ok",           verificable=True,  pendiente=False
  - PROYECCION_OBSOLETA       -> integridad="degradada",    verificable=True,  pendiente=True
  - PROYECCION_AUSENTE        -> integridad="degradada",    verificable=True,  pendiente=True
  - PROYECCION_INVALIDA       -> integridad="degradada",    verificable=True,  pendiente=True
  - ESTADO_NO_VERIFICABLE     -> integridad="no_verificable", verificable=False, pendiente=False

El estado se construye SIEMPRE en `tmp_path`, con las anclas en un temporal (fixture
`anclas_del_log_en_un_temporal` del conftest). NUNCA se toca `~/.aura` ni el estado real.
"""

from __future__ import annotations

import json
import pathlib

import control_plane as cp
import pytest


# ------------------------------------------------------------------ constructores de estado --
# Reutilizados del mismo patron que test_red_proyeccion_obsoleta.py (F1), sin duplicar logica de
# produccion: solo arman el log/estado.json via la API publica para fijar el escenario.


def _sincronizado(directorio: pathlib.Path) -> dict:
    """Log con una tarea registrada y llevada a WORKING, con `estado.json` AL DIA: debe dar ACTUAL
    en F1 y por tanto "ok" en F3."""
    cp.registrar_evento(directorio, "tarea_registrada", {"id": "T-1", "descripcion": "hacer algo"})
    cp.transicion(directorio, "T-1", "WORKING", autoridad="ceo", causa="empezar")
    return _guardar_desde_proyeccion(directorio)


def _guardar_desde_proyeccion(directorio: pathlib.Path) -> dict:
    proy = cp.proyectar(directorio)
    almacenado = dict(proy)
    almacenado["tareas"] = {
        tid: {**tarea, "previo": "WAITING_FOR_NEXT_TASK"} for tid, tarea in proy["tareas"].items()
    }
    almacenado["git"] = {"ultimo_commit": "deadbeef"}
    cp.guardar(almacenado, directorio / "estado.json")
    return almacenado


def _huellas(directorio: pathlib.Path) -> dict[str, tuple[bytes, float] | None]:
    """Bytes y mtime de estado.json, eventos.jsonl y el ancla, para el control de NO ESCRITURA."""
    rutas = {
        "estado": directorio / "estado.json",
        "eventos": cp.ruta_eventos(directorio),
        "ancla": cp.ruta_ancla(directorio),
    }
    out: dict[str, tuple[bytes, float] | None] = {}
    for nombre, ruta in rutas.items():
        if ruta.exists():
            st = ruta.stat()
            out[nombre] = (ruta.read_bytes(), st.st_mtime_ns)
        else:
            out[nombre] = None
    return out


# -------------------------------------------------------------------------- control positivo: ACTUAL --


def test_actual_es_ok_y_no_pendiente(tmp_path):
    _sincronizado(tmp_path)
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "PROYECCION_ACTUAL"  # control: F1 realmente dice ACTUAL
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "ok"
    assert r["verificable"] is True
    assert r["regeneracion_pendiente"] is False
    assert r["proyeccion"] == "PROYECCION_ACTUAL"


def test_integridad_log_no_pisa_el_veredicto_integridad(tmp_path):
    """Blindaje de la no-colision de claves (auditoria de correccion, condicion 2). El veredicto string
    vive en `integridad`; el subinforme de verificar_integridad_log se expone como `integridad_log`.
    Si alguien escribiera el subinforme bajo la clave `integridad`, pisaria el veredicto (un dict en
    vez del string): esta prueba lo detecta en un estado que SI adjunta subinforme (ACTUAL)."""
    _sincronizado(tmp_path)
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "ok", "el veredicto es el string, no el subinforme"
    assert isinstance(r["integridad"], str)
    assert "integridad_log" in r and isinstance(r["integridad_log"], dict), "el subinforme va en su propia clave"
    assert r["integridad_log"] is not r["integridad"]


def test_actual_reporta_seq_confirmado_y_seq_proyeccion_coincidentes(tmp_path):
    _sincronizado(tmp_path)
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["seq_confirmado"] == f1["seq_confirmado"]
    assert r["seq_proyeccion"] == f1["seq_proyeccion"]
    assert r["seq_proyeccion"] == r["seq_confirmado"]


# -------------------------------------------------------------------------- degradada: OBSOLETA --


def test_obsoleta_es_degradada_y_pendiente(tmp_path):
    _sincronizado(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")  # log avanza
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "PROYECCION_OBSOLETA"  # control
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "degradada"
    assert r["verificable"] is True
    assert r["regeneracion_pendiente"] is True
    assert r["proyeccion"] == "PROYECCION_OBSOLETA"
    assert r["seq_proyeccion"] < r["seq_confirmado"]


# -------------------------------------------------------------------------- degradada: AUSENTE --


def test_ausente_es_degradada_y_pendiente(tmp_path):
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    assert not (tmp_path / "estado.json").exists()
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "PROYECCION_AUSENTE"  # control
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "degradada"
    assert r["verificable"] is True
    assert r["regeneracion_pendiente"] is True
    assert r["proyeccion"] == "PROYECCION_AUSENTE"


# -------------------------------------------------------------------------- degradada: INVALIDA --


def test_invalida_es_degradada_y_pendiente_con_log_verificable(tmp_path):
    """estado.json roto pero el log SI es verificable: degradada, no no_verificable."""
    _sincronizado(tmp_path)
    datos = json.loads((tmp_path / "estado.json").read_text(encoding="utf-8"))
    datos["tareas"]["T-1"].pop("previo", None)  # rompe validar_tareas -> INVALIDA
    (tmp_path / "estado.json").write_text(json.dumps(datos), encoding="utf-8")
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "PROYECCION_INVALIDA"  # control
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "degradada"
    assert r["verificable"] is True
    assert r["regeneracion_pendiente"] is True
    assert r["proyeccion"] == "PROYECCION_INVALIDA"


# ----------------------------------------------------------------------- no_verificable --


def test_no_verificable_por_ancla_ausente(tmp_path):
    """Sin ancla externa, la completitud del log no se puede demostrar: no_verificable, NUNCA ok,
    y NUNCA pendiente de regeneracion (F2 no actua sobre lo no verificable)."""
    _sincronizado(tmp_path)
    cp.ruta_ancla(tmp_path).unlink()
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "ESTADO_NO_VERIFICABLE"  # control
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "no_verificable"
    assert r["verificable"] is False
    assert r["regeneracion_pendiente"] is False
    assert r["proyeccion"] == "ESTADO_NO_VERIFICABLE"


def test_no_verificable_por_cadena_rota(tmp_path):
    """Otra via a NO_VERIFICABLE (seq discontinuo): mismo veredicto agregado, para que el mapeo no
    dependa del motivo concreto del fallo de integridad, sino solo del estado que F1 reporta."""
    _sincronizado(tmp_path)
    ruta = cp.ruta_eventos(tmp_path)
    lineas = [ln for ln in ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
    primero = json.loads(lineas[0])
    primero["seq"] = 99
    lineas[0] = json.dumps(primero, ensure_ascii=False)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "ESTADO_NO_VERIFICABLE"  # control
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "no_verificable"
    assert r["verificable"] is False
    assert r["regeneracion_pendiente"] is False


# ------------------------------------------- el indicador NO refleja PARADA ni disponibilidad --


def test_el_veredicto_no_incluye_claves_de_autorizacion_ni_disponibilidad(tmp_path):
    """Garantia 5/6 del DP: integridad != autorizacion != disponibilidad. El dict de F3 no debe
    traer ninguna clave de PARADA/kill-switch/cola/cuota/espera: solo lo que F1 ya reporta mas el
    veredicto agregado. Si estas claves aparecieran, F3 estaria mezclando planos."""
    _sincronizado(tmp_path)
    r = cp.integridad_del_control_plane(tmp_path)
    claves_prohibidas = {
        "parada", "kill_switch", "autorizado", "autorizacion", "cola", "disponible",
        "disponibilidad", "cuota", "en_espera", "espera",
    }
    assert claves_prohibidas.isdisjoint(r.keys())


def test_actual_sigue_siendo_ok_sin_importar_tareas_pendientes_en_cola(tmp_path):
    """Con tareas registradas pero no transicionadas (equivalente a "cola" en espera) y la
    proyeccion ACTUAL, el veredicto de integridad sigue siendo "ok": disponibilidad no degrada
    integridad. F3 no mira tareas en WAITING_FOR_NEXT_TASK para decidir su veredicto."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-2", "descripcion": "b"})  # "cola"
    _guardar_desde_proyeccion(tmp_path)
    f1 = cp.estado_de_la_proyeccion(tmp_path)
    assert f1["estado"] == "PROYECCION_ACTUAL"  # control
    r = cp.integridad_del_control_plane(tmp_path)
    assert r["integridad"] == "ok"


# ------------------------------------------------------------------- control de NO ESCRITURA --


@pytest.mark.parametrize(
    "preparar",
    [
        pytest.param(lambda d: _sincronizado(d), id="actual"),
        pytest.param(
            lambda d: (_sincronizado(d), cp.transicion(d, "T-1", "COMPLETED", autoridad="ceo",
                                                       causa="x")),
            id="obsoleta",
        ),
        pytest.param(lambda d: cp.registrar_evento(d, "tarea_registrada",
                                                   {"id": "T-1", "descripcion": "a"}), id="ausente"),
        pytest.param(
            lambda d: (_sincronizado(d), cp.ruta_ancla(d).unlink()), id="no_verificable",
        ),
    ],
)
def test_f3_no_escribe_nada(tmp_path, preparar):
    """F3 es PURA: tras llamarla, ni estado.json, ni eventos.jsonl, ni el ancla cambian (bytes y
    mtime). Mismo control que F1 — F3 no es un escritor camuflado de agregador."""
    preparar(tmp_path)
    antes = _huellas(tmp_path)
    cp.integridad_del_control_plane(tmp_path)
    despues = _huellas(tmp_path)
    assert despues == antes


def test_f3_no_crea_estado_json_cuando_esta_AUSENTE(tmp_path):
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    cp.integridad_del_control_plane(tmp_path)
    assert not (tmp_path / "estado.json").exists()


# ------------------------------------------------------- control de que NO llama a regenerar_proyeccion --


def test_f3_no_invoca_regenerar_proyeccion_ni_en_obsoleta(tmp_path, monkeypatch):
    """Monkeypatch que hace fallar la prueba si `regenerar_proyeccion` es invocada. Caso OBSOLETA:
    es exactamente el escenario en que F2 SI actuaria si se le llamara, por eso es el mas
    sensible para detectar una violacion del alcance de solo-lectura."""
    _sincronizado(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")

    llamadas = []

    def _espia(*args, **kwargs):
        llamadas.append((args, kwargs))
        raise AssertionError("integridad_del_control_plane NO debe llamar a regenerar_proyeccion")

    monkeypatch.setattr(cp, "regenerar_proyeccion", _espia)
    r = cp.integridad_del_control_plane(tmp_path)
    assert llamadas == []
    assert r["integridad"] == "degradada"


def test_f3_no_invoca_regenerar_proyeccion_en_ninguno_de_los_cinco_estados(tmp_path, monkeypatch):
    """Mismo espia que arriba, pero cubriendo los cinco estados de F1 en una sola pasada, para que
    el control no dependa de un unico escenario."""

    def _espia(*args, **kwargs):
        raise AssertionError("integridad_del_control_plane NO debe llamar a regenerar_proyeccion")

    monkeypatch.setattr(cp, "regenerar_proyeccion", _espia)

    # AUSENTE
    d_ausente = tmp_path / "ausente"
    d_ausente.mkdir()
    cp.registrar_evento(d_ausente, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    assert cp.integridad_del_control_plane(d_ausente)["proyeccion"] == "PROYECCION_AUSENTE"

    # ACTUAL
    d_actual = tmp_path / "actual"
    d_actual.mkdir()
    _sincronizado(d_actual)
    assert cp.integridad_del_control_plane(d_actual)["proyeccion"] == "PROYECCION_ACTUAL"

    # OBSOLETA
    d_obsoleta = tmp_path / "obsoleta"
    d_obsoleta.mkdir()
    _sincronizado(d_obsoleta)
    cp.transicion(d_obsoleta, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")
    assert cp.integridad_del_control_plane(d_obsoleta)["proyeccion"] == "PROYECCION_OBSOLETA"

    # INVALIDA
    d_invalida = tmp_path / "invalida"
    d_invalida.mkdir()
    _sincronizado(d_invalida)
    datos = json.loads((d_invalida / "estado.json").read_text(encoding="utf-8"))
    datos["tareas"]["T-1"].pop("previo", None)
    (d_invalida / "estado.json").write_text(json.dumps(datos), encoding="utf-8")
    assert cp.integridad_del_control_plane(d_invalida)["proyeccion"] == "PROYECCION_INVALIDA"

    # NO_VERIFICABLE
    d_noverif = tmp_path / "noverif"
    d_noverif.mkdir()
    _sincronizado(d_noverif)
    cp.ruta_ancla(d_noverif).unlink()
    assert cp.integridad_del_control_plane(d_noverif)["proyeccion"] == "ESTADO_NO_VERIFICABLE"
