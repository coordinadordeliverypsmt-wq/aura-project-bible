"""F2 — regeneracion EXPLICITA y CONTROLADA de la proyeccion (estado.json) desde el log. RED antes
que GREEN.

`regenerar_proyeccion(directorio) -> dict` reconstruye `estado.json` desde el log SOLO si la fuente
es verificable (F1/`verificar_integridad_log`: integro + completitud demostrada), preservando los
campos de ENTORNO del `estado.json` existente y derivando los campos de GOBIERNO por tarea
(`previo`, `creada_sin_origen`, autoridad, causa) DEL LOG, nunca fabricandolos. Valida con
`validar`+`validar_tareas` antes de escribir con el escritor autorizado `guardar` (atomico).

Es EXPLICITA: no se llama desde ninguna lectura (F1 sigue siendo solo deteccion). No es F3.

El estado se construye SIEMPRE en `tmp_path`, con las anclas en un temporal (fixture
`anclas_del_log_en_un_temporal` del conftest, autouse). NUNCA se toca `~/.aura` ni el estado real
(fixture `blindar_el_estado_de_produccion`, autouse)."""

from __future__ import annotations

import hashlib
import json
import pathlib

import control_plane as cp
import pytest


# ------------------------------------------------------------------ constructores de estado --


def _log_sincronizado(directorio: pathlib.Path) -> None:
    """Un log integro con una tarea registrada y llevada a WORKING, con ancla al dia."""
    cp.registrar_evento(directorio, "tarea_registrada", {"id": "T-1", "descripcion": "hacer algo"})
    cp.transicion(directorio, "T-1", "WORKING", autoridad="ceo", causa="empezar")


def _guardar_desde_proyeccion(directorio: pathlib.Path, *, extra_entorno: dict | None = None) -> dict:
    """Arma un `estado.json` ACTUAL a partir de `proyectar()`, como un consumidor real: campos del
    log + `previo` (gobierno) + ruido de entorno."""
    proy = cp.proyectar(directorio)
    almacenado = dict(proy)
    almacenado["tareas"] = {
        tid: {**tarea, "previo": "WAITING_FOR_NEXT_TASK", "creada_sin_origen": False}
        for tid, tarea in proy["tareas"].items()
    }
    almacenado["git"] = {"ultimo_commit": "deadbeef", "rama": "main", "ficheros_modificados": [],
                        "limpio": True}
    if extra_entorno:
        almacenado.update(extra_entorno)
    cp.guardar(almacenado, directorio / "estado.json")
    return almacenado


def _huellas(directorio: pathlib.Path) -> dict[str, tuple[bytes, float] | None]:
    """Bytes y mtime de eventos.jsonl y el ancla, para el control de NO TOCAR el log."""
    rutas = {"eventos": cp.ruta_eventos(directorio), "ancla": cp.ruta_ancla(directorio)}
    out: dict[str, tuple[bytes, float] | None] = {}
    for nombre, ruta in rutas.items():
        if ruta.exists():
            st = ruta.stat()
            out[nombre] = (ruta.read_bytes(), st.st_mtime_ns)
        else:
            out[nombre] = None
    return out


# -------------------------------------------------------------------------------- OBSOLETA --


def test_obsoleta_regenera_y_pasa_a_ACTUAL(tmp_path):
    """Control positivo central: proyeccion atrasada respecto al log -> tras regenerar, F1 la
    clasifica ACTUAL."""
    _log_sincronizado(tmp_path)
    _guardar_desde_proyeccion(tmp_path)  # estado.json hasta seq=2
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")  # log avanza a seq=3
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_OBSOLETA"  # control

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_ACTUAL"
    nuevo = cp.cargar(tmp_path / "estado.json")
    assert nuevo["tareas"]["T-1"]["estado"] == "COMPLETED"


# -------------------------------------------------------------------------------- AUSENTE --


def test_ausente_regenera_y_crea_estado_json_valido(tmp_path):
    """No habia estado.json materializado; el log si es verificable: regenerar debe crear uno
    valido (pasa validar+validar_tareas) y F1 debe verlo ACTUAL despues."""
    _log_sincronizado(tmp_path)
    assert not (tmp_path / "estado.json").exists()
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_AUSENTE"  # control

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    assert (tmp_path / "estado.json").exists()
    nuevo = cp.cargar(tmp_path / "estado.json")
    cp.validar(nuevo)
    cp.validar_tareas(nuevo)
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_ACTUAL"


# -------------------------------------------------------------------------------- ACTUAL (no-op) --


def test_actual_es_no_op_y_no_reescribe(tmp_path):
    """Si la proyeccion ya es ACTUAL, regenerar no hace nada: no reescribe estado.json (bytes y
    mtime intactos) y lo reporta como no regenerado."""
    _log_sincronizado(tmp_path)
    _guardar_desde_proyeccion(tmp_path)
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_ACTUAL"  # control
    ruta = tmp_path / "estado.json"
    antes = (ruta.read_bytes(), ruta.stat().st_mtime_ns)

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is False
    assert informe["estado_detectado"] == "PROYECCION_ACTUAL"
    despues = (ruta.read_bytes(), ruta.stat().st_mtime_ns)
    assert despues == antes


# ----------------------------------------------------------------------------- NO_VERIFICABLE --


def test_no_verificable_no_regenera_y_no_escribe(tmp_path):
    """Ancla ausente -> completitud no demostrada -> ESTADO_NO_VERIFICABLE. F2 NUNCA regenera en
    este caso: ni crea ni modifica estado.json, y lo reporta."""
    _log_sincronizado(tmp_path)
    _guardar_desde_proyeccion(tmp_path)
    cp.ruta_ancla(tmp_path).unlink()
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "ESTADO_NO_VERIFICABLE"  # control
    ruta = tmp_path / "estado.json"
    antes = (ruta.read_bytes(), ruta.stat().st_mtime_ns)

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is False
    assert informe["estado_detectado"] == "ESTADO_NO_VERIFICABLE"
    despues = (ruta.read_bytes(), ruta.stat().st_mtime_ns)
    assert despues == antes


def test_no_verificable_por_ancla_en_desacuerdo_no_regenera(tmp_path):
    """Segundo camino a NO_VERIFICABLE (ancla en desacuerdo con el log): mismo rechazo."""
    _log_sincronizado(tmp_path)
    ruta_ancla = cp.ruta_ancla(tmp_path)
    ancla = json.loads(ruta_ancla.read_text(encoding="utf-8"))
    ancla["hash"] = hashlib.sha256(b"otro").hexdigest()
    ruta_ancla.write_text(json.dumps(ancla), encoding="utf-8")
    assert not cp.verificar_integridad_log(tmp_path)["integro"]  # control

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is False
    assert informe["estado_detectado"] == "ESTADO_NO_VERIFICABLE"
    assert not (tmp_path / "estado.json").exists()


# -------------------------------------------------------------------- preserva campos de entorno --


def test_preserva_campos_de_entorno_del_estado_previo(tmp_path):
    """Git, cuota, trabajo_completado y demas campos de ENTORNO del estado.json existente deben
    sobrevivir intactos a la regeneracion: F2 reconstruye el gobierno/log, no el entorno."""
    _log_sincronizado(tmp_path)  # T-1 en WORKING
    extra = {
        "git": {"ultimo_commit": "cafebabe", "rama": "feature/x", "ficheros_modificados": ["a.py"],
               "limpio": False},
        "trabajo_completado": [{"id": "T-0", "resultado": "ok", "evidencia": {}, "cuando": "x",
                                "duracion_s": None, "creada_sin_origen": False}],
        "decisiones_pendientes": [{"id": "D-1", "nota": "algo"}],
        "sesion_claude": "sesion-123",
        "checkpoint": {"documento": "CHECKPOINT-CONTINUIDAD.md", "commit": "cafebabe"},
    }
    # Se guarda ACTUAL con esos campos de entorno y LUEGO se desactualiza el log para forzar OBSOLETA.
    _guardar_desde_proyeccion(tmp_path, extra_entorno=extra)
    cp.transicion(tmp_path, "T-1", "FAILED", autoridad="ceo", causa="fallo observado")
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_OBSOLETA"  # control

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    nuevo = cp.cargar(tmp_path / "estado.json")
    assert nuevo["git"] == extra["git"]
    assert nuevo["trabajo_completado"] == extra["trabajo_completado"]
    assert nuevo["decisiones_pendientes"] == extra["decisiones_pendientes"]
    assert nuevo["sesion_claude"] == extra["sesion_claude"]
    assert nuevo["checkpoint"] == extra["checkpoint"]
    # Y el log si se reflejo: el estado de gobierno avanzo a FAILED.
    assert nuevo["tareas"]["T-1"]["estado"] == "FAILED"


def test_sin_estado_previo_usa_entorno_de_estado_inicial(tmp_path):
    """AUSENTE sin estado.json previo: los campos de entorno deben salir de `estado_inicial()`, no
    inventarse ad hoc ni quedar ausentes."""
    _log_sincronizado(tmp_path)

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    nuevo = cp.cargar(tmp_path / "estado.json")
    inicial = cp.estado_inicial()
    assert nuevo["checkpoint"] == inicial["checkpoint"]
    assert nuevo["trabajo_completado"] == inicial["trabajo_completado"]
    assert nuevo["decisiones_pendientes"] == inicial["decisiones_pendientes"]
    assert nuevo["aprobaciones"] == inicial["aprobaciones"]
    assert nuevo["defectos"] == inicial["defectos"]


# ---------------------------------------------------- gobierno derivado del log, no inventado --


def test_previo_derivado_del_log_coincide_con_lo_que_registro_el_evento(tmp_path):
    """El `previo` de cada tarea regenerada debe ser EXACTAMENTE el que el evento de transicion
    registro en `datos.previo`, no un valor generico ni constante."""
    _log_sincronizado(tmp_path)  # T-1: WAITING_FOR_NEXT_TASK -> WORKING (previo registrado: WAITING_FOR_NEXT_TASK)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")  # previo: WORKING

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    nuevo = cp.cargar(tmp_path / "estado.json")
    # El ULTIMO evento de T-1 fue WORKING -> COMPLETED: su `previo` registrado en el log es WORKING.
    eventos = [e for e in cp.leer_eventos(tmp_path)
              if e["tipo"] == "estado_de_tarea" and e["datos"]["id"] == "T-1"]
    assert eventos[-1]["datos"]["previo"] == "WORKING"
    assert nuevo["tareas"]["T-1"]["previo"] == "WORKING"
    assert nuevo["tareas"]["T-1"]["autoridad"] == "ceo"


def test_tarea_registrada_sin_transicionar_se_regenera(tmp_path):
    """Una tarea solo `tarea_registrada` (nunca transicionada) es legitima: queda en
    WAITING_FOR_NEXT_TASK. Su gobierno SI deriva del log sin fabricar: su `previo` es
    `ESTADO_SIN_REGISTRAR` ('UNKNOWN'), el estado previo REAL de una tarea recien registrada (su
    origen es el registro). F2 NO debe rechazarla como "no reconstruible"."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "pendiente"})
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_AUSENTE"  # control

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    nuevo = cp.cargar(tmp_path / "estado.json")
    cp.validar_tareas(nuevo)  # no debe lanzar
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_ACTUAL"
    assert nuevo["tareas"]["T-1"]["estado"] == "WAITING_FOR_NEXT_TASK"
    assert nuevo["tareas"]["T-1"]["previo"] == "UNKNOWN"
    assert nuevo["tareas"]["T-1"]["creada_sin_origen"] is False


def test_mezcla_registrada_sin_transicionar_y_transicionada_ambas_se_regeneran(tmp_path):
    """Variante MIXTA: T-1 registrada-sin-transicionar y T-2 registrada+transicionada. Ambas deben
    quedar en el mismo estado.json regenerado, cada una con el gobierno derivado del log: T-1 con
    previo UNKNOWN, T-2 con el previo que registro su evento."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "pendiente"})
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-2", "descripcion": "en curso"})
    cp.transicion(tmp_path, "T-2", "WORKING", autoridad="ceo", causa="empezar")
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_AUSENTE"  # control

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    nuevo = cp.cargar(tmp_path / "estado.json")
    cp.validar_tareas(nuevo)
    assert cp.estado_de_la_proyeccion(tmp_path)["estado"] == "PROYECCION_ACTUAL"
    assert nuevo["tareas"]["T-1"]["estado"] == "WAITING_FOR_NEXT_TASK"
    assert nuevo["tareas"]["T-1"]["previo"] == "UNKNOWN"
    assert nuevo["tareas"]["T-1"]["creada_sin_origen"] is False
    assert nuevo["tareas"]["T-2"]["estado"] == "WORKING"
    assert nuevo["tareas"]["T-2"]["previo"] == "WAITING_FOR_NEXT_TASK"
    assert nuevo["tareas"]["T-2"]["creada_sin_origen"] is False


def test_creada_sin_origen_de_tarea_reconstruida_del_log_es_falso(tmp_path):
    """`transicion()` exige que la tarea exista ya en la proyeccion (no se transiciona lo que no
    existe) y el evento `estado_de_tarea` esta GOBERNADO: solo se escribe desde ahi. Por tanto toda
    tarea reconstruida PURAMENTE del log paso por `tarea_registrada` antes de cualquier cambio de
    estado, y `creada_sin_origen` es necesariamente False — no un valor inventado, sino la unica
    consecuencia posible de las invariantes que el propio log ya impone."""
    _log_sincronizado(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is True
    nuevo = cp.cargar(tmp_path / "estado.json")
    assert nuevo["tareas"]["T-1"]["creada_sin_origen"] is False


# ------------------------------------------------------- COMPLETED no reconstruible -> rechaza --


def test_completed_sin_autoridad_humana_en_el_log_rechaza_y_no_escribe(tmp_path):
    """Si el log registrase una tarea COMPLETED con una autoridad no humana (bypass hipotetico, o
    un evento fabricado a mano para la prueba), `validar_tareas` la rechazaria al escribir. F2 NO
    debe fabricar una autoridad humana para que pase: debe RECHAZAR la regeneracion entera y
    reportar el motivo, sin escribir nada."""
    _log_sincronizado(tmp_path)
    # Evento de estado fabricado directamente en el log (bypass de `transicion`, simulando un
    # defecto de otra capa o un log heredado): COMPLETED con autoridad no humana.
    cp._registrar_sin_lock(tmp_path, "estado_de_tarea", {
        "id": "T-1", "valor": "COMPLETED", "previo": "WORKING", "autoridad": "control_plane",
        "causa": "cierre automatico no gobernado"})

    informe = cp.regenerar_proyeccion(tmp_path)

    assert informe["regenerado"] is False
    assert "no reconstruible" in informe["motivo"] or "T-1" in informe["motivo"]
    assert not (tmp_path / "estado.json").exists()


# ---------------------------------------------------------------- fallo de escritura -> no parcial --


def test_fallo_de_escritura_no_deja_estado_parcial(tmp_path, monkeypatch):
    """Si `guardar` (o su mecanismo atomico) falla a mitad de camino, `estado.json` debe quedar
    integro: o el viejo (si existia), o ausente (si no existia) — nunca un JSON a medio escribir.
    El error debe propagarse, no silenciarse."""
    _log_sincronizado(tmp_path)
    assert not (tmp_path / "estado.json").exists()

    def _replace_que_falla(self, target):
        raise OSError("disco lleno simulado")

    monkeypatch.setattr(pathlib.Path, "replace", _replace_que_falla)

    with pytest.raises(OSError):
        cp.regenerar_proyeccion(tmp_path)

    # Ni el fichero final ni ningun .tmp residual con contenido parcial deben quedar utilizables
    # como estado real: el final sigue ausente.
    assert not (tmp_path / "estado.json").exists()


def test_fallo_de_escritura_preserva_el_estado_json_viejo(tmp_path, monkeypatch):
    """Variante con estado previo: si la escritura falla, el estado.json VIEJO (ACTUAL anterior,
    hoy obsoleto) debe seguir intacto y legible, nunca corrompido a medias."""
    _log_sincronizado(tmp_path)
    viejo = _guardar_desde_proyeccion(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")
    ruta = tmp_path / "estado.json"
    bytes_viejos = ruta.read_bytes()

    def _replace_que_falla(self, target):
        raise OSError("disco lleno simulado")

    monkeypatch.setattr(pathlib.Path, "replace", _replace_que_falla)

    with pytest.raises(OSError):
        cp.regenerar_proyeccion(tmp_path)

    assert ruta.read_bytes() == bytes_viejos
    recargado = json.loads(ruta.read_text(encoding="utf-8"))
    assert recargado["tareas"]["T-1"]["estado"] == viejo["tareas"]["T-1"]["estado"]


# --------------------------------------------------------- pasa validar + validar_tareas --


def test_resultado_regenerado_pasa_validar_y_validar_tareas(tmp_path):
    _log_sincronizado(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")

    cp.regenerar_proyeccion(tmp_path)

    nuevo = cp.cargar(tmp_path / "estado.json")
    cp.validar(nuevo)       # no debe lanzar
    cp.validar_tareas(nuevo)  # no debe lanzar


# ----------------------------------------------------------- no toca eventos.jsonl ni el ancla --


@pytest.mark.parametrize(
    "preparar",
    [
        pytest.param(lambda d: (_log_sincronizado(d),), id="ausente"),
        pytest.param(
            lambda d: (_log_sincronizado(d), _guardar_desde_proyeccion(d),
                      cp.transicion(d, "T-1", "COMPLETED", autoridad="ceo", causa="x")),
            id="obsoleta",
        ),
        pytest.param(
            lambda d: (_log_sincronizado(d), _guardar_desde_proyeccion(d)),
            id="actual",
        ),
    ],
)
def test_no_toca_eventos_ni_ancla(tmp_path, preparar):
    """F2 regenera `estado.json`; NUNCA escribe en `eventos.jsonl` ni mueve el ancla. Control de
    bytes+mtime, igual que el de F1."""
    preparar(tmp_path)
    antes = _huellas(tmp_path)

    cp.regenerar_proyeccion(tmp_path)

    despues = _huellas(tmp_path)
    assert despues == antes


# --------------------------------------------------------------------------- idempotencia --


def test_idempotencia_regenerar_dos_veces_mismo_resultado(tmp_path):
    """Regenerar dos veces en sucesion produce el mismo estado.json derivado del log (la segunda
    vez ya es ACTUAL y es no-op, pero el resultado observable es identico)."""
    _log_sincronizado(tmp_path)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="hecho")

    primero = cp.regenerar_proyeccion(tmp_path)
    assert primero["regenerado"] is True
    estado_tras_primera = cp.cargar(tmp_path / "estado.json")

    segundo = cp.regenerar_proyeccion(tmp_path)
    assert segundo["regenerado"] is False  # ya ACTUAL: no-op
    estado_tras_segunda = cp.cargar(tmp_path / "estado.json")

    def _vista(e):
        return {k: v for k, v in e.items() if k != "actualizado"}

    assert _vista(estado_tras_primera) == _vista(estado_tras_segunda)
