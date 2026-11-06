"""F1 — DETECCION de proyeccion obsoleta (solo lectura). RED antes que GREEN.

`estado_de_la_proyeccion(directorio)` clasifica la relacion entre el `estado.json` almacenado y el
log (`eventos.jsonl` + ancla) en EXACTAMENTE uno de cinco estados, SIN escribir, SIN regenerar y SIN
tocar el historial ni el ancla:

    PROYECCION_ACTUAL · PROYECCION_OBSOLETA · PROYECCION_AUSENTE · PROYECCION_INVALIDA ·
    ESTADO_NO_VERIFICABLE

Reutiliza `verificar_integridad_log` (autoridad sobre integridad y completitud), `cargar`,
`proyectar`, `validar`/`validar_tareas`. No reimplementa verificacion ni proyeccion.

Precedencia (ver ficha): primero la integridad del log (si no se puede demostrar que esta completo ->
NO_VERIFICABLE, nunca ACTUAL); solo con log integro y completitud demostrada se mira la proyeccion.

El estado se construye SIEMPRE en `tmp_path`, con las anclas en un temporal (fixture
`anclas_del_log_en_un_temporal` del conftest). NUNCA se toca `~/.aura` ni el estado real.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import control_plane as cp
import pytest


# ------------------------------------------------------------------ constructores de estado --


def _sincronizado(directorio: pathlib.Path) -> dict:
    """Log con una tarea registrada y llevada a WORKING, y un `estado.json` que ES la proyeccion de
    ese log (enriquecida solo con `previo` —gobierno— y campos de entorno). La vista derivada del log
    del almacenado coincide con `proyectar()`: esto DEBE clasificar como ACTUAL."""
    cp.registrar_evento(directorio, "tarea_registrada", {"id": "T-1", "descripcion": "hacer algo"})
    cp.transicion(directorio, "T-1", "WORKING", autoridad="ceo", causa="empezar")
    return _guardar_desde_proyeccion(directorio)


def _guardar_desde_proyeccion(directorio: pathlib.Path) -> dict:
    """Arma el `estado.json` a partir de `proyectar()`, como hace un consumidor real: conserva los
    campos derivados del log y anade `previo` (para pasar `validar_tareas`) y ruido de entorno
    (`git`). `guardar` ademas pone `actualizado`; `cargar` pone `cuota`. Todos ellos DEBEN quedar
    fuera de la comparacion de F1."""
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


# -------------------------------------------------------------------------- control positivo --


def test_sincronizada_es_ACTUAL(tmp_path):
    _sincronizado(tmp_path)
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_ACTUAL"


def test_ACTUAL_no_cambia_el_comportamiento_la_proyeccion_sigue_siendo_la_del_log(tmp_path):
    """Control positivo: cuando es ACTUAL, lo que F1 observa como derivado del log es, campo a campo,
    lo que `proyectar()` reconstruye. No reinterpreta el estado; solo lo confirma."""
    _sincronizado(tmp_path)
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_ACTUAL"
    assert r["seq_proyeccion"] == r["seq_confirmado"]


# -------------------------------------------------------------------------- OBSOLETA (atrasada) --


def test_atrasada_es_OBSOLETA_con_seq_proyeccion_menor_que_el_confirmado(tmp_path):
    """Se guarda la proyeccion y DESPUES se registran mas eventos sin re-proyectar: el estado.json
    describe un pasado. La deteccion lo marca OBSOLETA y reporta que la proyeccion va por detras."""
    _sincronizado(tmp_path)  # estado.json fijado aqui (seq hasta 2)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")  # el log avanza
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_OBSOLETA"
    assert r["seq_proyeccion"] < r["seq_confirmado"]


def test_cambio_de_estado_sin_avanzar_seq_tambien_es_OBSOLETA(tmp_path):
    """Control: la obsolescencia no es solo «faltan eventos». Si el contenido derivado difiere aunque
    el numero de eventos aplicados coincidiera, sigue siendo OBSOLETA. Aqui una tarea extra en el log
    que el estado.json no refleja."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    almacenado = _guardar_desde_proyeccion(tmp_path)  # estado.json con solo T-1
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-2", "descripcion": "b"})
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_OBSOLETA"
    # control del control: el almacenado de verdad no tiene T-2
    assert "T-2" not in almacenado["tareas"]


# -------------------------------------------------------------------------------- AUSENTE --


def test_sin_estado_json_es_AUSENTE(tmp_path):
    """Hay log integro pero no hay proyeccion materializada. No es un error ni obsolescencia: falta."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    assert not (tmp_path / "estado.json").exists()
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_AUSENTE"


def test_directorio_completamente_vacio_es_AUSENTE(tmp_path):
    """Borde: ni eventos.jsonl ni ancla ni estado.json (log vacio = genesis integro). No se puede declarar
    ACTUAL algo que no existe, pero tampoco es NO_VERIFICABLE: el log vacio es integro. Debe ser AUSENTE."""
    assert not (tmp_path / "estado.json").exists()
    assert not (tmp_path / "eventos.jsonl").exists()
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_AUSENTE"


# -------------------------------------------------------------------------------- INVALIDA --


def test_estado_json_con_json_roto_es_INVALIDA(tmp_path):
    _sincronizado(tmp_path)
    (tmp_path / "estado.json").write_text("{esto no es json", encoding="utf-8")
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_INVALIDA"


def test_estado_json_que_no_pasa_validar_es_INVALIDA(tmp_path):
    """Un `status` desconocido hace fallar `validar`: el fichero existe y es JSON, pero no es un
    estado legitimo. No se compara contra la proyeccion: no hay nada fiable que comparar."""
    _sincronizado(tmp_path)
    datos = json.loads((tmp_path / "estado.json").read_text(encoding="utf-8"))
    datos["status"] = "ESTADO_QUE_NO_EXISTE"
    (tmp_path / "estado.json").write_text(json.dumps(datos), encoding="utf-8")
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_INVALIDA"


def test_estado_json_con_tarea_sin_gobierno_es_INVALIDA(tmp_path):
    """Una tarea sin los campos de gobierno (`previo`) hace fallar `validar_tareas`: estado
    falsificado que no se persiste limpiamente. F1 no lo trata como ACTUAL ni OBSOLETA: es INVALIDA."""
    _sincronizado(tmp_path)
    datos = json.loads((tmp_path / "estado.json").read_text(encoding="utf-8"))
    datos["tareas"]["T-1"].pop("previo", None)
    (tmp_path / "estado.json").write_text(json.dumps(datos), encoding="utf-8")
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_INVALIDA"


# ----------------------------------------------------------------------------- NO_VERIFICABLE --


def test_ancla_ausente_es_NO_VERIFICABLE(tmp_path):
    """Sin ancla externa, la completitud del log no se puede demostrar: no se puede afirmar que la
    proyeccion sea actual. Fallo seguro -> NO_VERIFICABLE, jamas ACTUAL."""
    _sincronizado(tmp_path)
    cp.ruta_ancla(tmp_path).unlink()  # borra el ancla externa
    v = cp.verificar_integridad_log(tmp_path)
    assert v["completitud"] != cp.COMPLETITUD_DEMOSTRADA  # control: el verificador ya no la demuestra
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "ESTADO_NO_VERIFICABLE"


def test_ancla_en_desacuerdo_con_el_log_es_NO_VERIFICABLE(tmp_path):
    """El ancla dice un `seq`/hash que el log no respalda (truncamiento o alteracion): NO_VERIFICABLE."""
    _sincronizado(tmp_path)
    ruta_ancla = cp.ruta_ancla(tmp_path)
    ancla = json.loads(ruta_ancla.read_text(encoding="utf-8"))
    ancla["hash"] = hashlib.sha256(b"otro").hexdigest()  # hash que no coincide con el evento anclado
    ruta_ancla.write_text(json.dumps(ancla), encoding="utf-8")
    v = cp.verificar_integridad_log(tmp_path)
    assert not v["integro"]  # control
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "ESTADO_NO_VERIFICABLE"


def test_seq_discontinuo_en_el_log_es_NO_VERIFICABLE(tmp_path):
    """Cadena rota: un `seq` que salta. El verificador lo detecta (integridad_eventos falsa) y F1 no
    puede demostrar actualidad. Se reporta el seq del defecto."""
    _sincronizado(tmp_path)
    ruta = cp.ruta_eventos(tmp_path)
    lineas = [ln for ln in ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
    primero = json.loads(lineas[0])
    primero["seq"] = 99  # rompe la continuidad en la PRIMERA linea (no es la ultima -> cadena rota)
    lineas[0] = json.dumps(primero, ensure_ascii=False)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    v = cp.verificar_integridad_log(tmp_path)
    assert v["motivo_codigo"] == "cadena_rota"  # control
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "ESTADO_NO_VERIFICABLE"
    assert r.get("motivo_codigo") == "cadena_rota"


def test_hash_invalido_en_un_evento_es_NO_VERIFICABLE(tmp_path):
    """Un evento cuyo contenido no coincide con su hash: alteracion. Cadena rota -> NO_VERIFICABLE."""
    _sincronizado(tmp_path)
    ruta = cp.ruta_eventos(tmp_path)
    lineas = [ln for ln in ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
    primero = json.loads(lineas[0])
    primero["datos"] = {**primero.get("datos", {}), "descripcion": "ALTERADO"}  # hash deja de cuadrar
    lineas[0] = json.dumps(primero, ensure_ascii=False)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    v = cp.verificar_integridad_log(tmp_path)
    assert not v["integro"]  # control
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "ESTADO_NO_VERIFICABLE"


# ---------------------------------------------------------- .tmp residual de una escritura rota --


def test_un_estado_json_tmp_residual_se_ignora_y_clasifica_por_el_real(tmp_path):
    """Una escritura interrumpida de `estado.json` deja un `estado.json.tmp`. F1 clasifica por el
    `estado.json` real (ACTUAL), sin dejarse confundir por el residuo."""
    _sincronizado(tmp_path)
    (tmp_path / "estado.json.tmp").write_text("{basura a medio escribir", encoding="utf-8")
    r = cp.estado_de_la_proyeccion(tmp_path)
    assert r["estado"] == "PROYECCION_ACTUAL"


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
    ],
)
def test_la_deteccion_no_escribe_nada(tmp_path, preparar):
    """F1 es PURA: tras llamarla, ni estado.json, ni eventos.jsonl, ni el ancla cambian (bytes y
    mtime). Es la garantia de que no hay un segundo escritor camuflado de detector."""
    preparar(tmp_path)
    antes = _huellas(tmp_path)
    cp.estado_de_la_proyeccion(tmp_path)
    despues = _huellas(tmp_path)
    assert despues == antes


def test_la_deteccion_no_crea_estado_json_cuando_esta_AUSENTE(tmp_path):
    """Control fino de la pureza: ante AUSENTE, F1 no cae en la tentacion de materializar la
    proyeccion. Sigue AUSENTE en disco."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "a"})
    cp.estado_de_la_proyeccion(tmp_path)
    assert not (tmp_path / "estado.json").exists()


# ----------------------------------------------- guarda delgada opcional para consumidores --


def test_cargar_si_actual_devuelve_la_proyeccion_solo_si_ACTUAL(tmp_path):
    almacenado = _sincronizado(tmp_path)
    r = cp.cargar_si_actual(tmp_path)
    assert r["estado"] == "PROYECCION_ACTUAL"
    assert r["proyeccion"]["tareas"]["T-1"]["estado"] == almacenado["tareas"]["T-1"]["estado"]


def test_cargar_si_actual_no_entrega_proyeccion_si_OBSOLETA(tmp_path):
    _sincronizado(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")
    r = cp.cargar_si_actual(tmp_path)
    assert r["estado"] == "PROYECCION_OBSOLETA"
    assert r.get("proyeccion") is None
