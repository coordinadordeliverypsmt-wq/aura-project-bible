"""F4 — lectura agregada de residencia (privacidad-segura). RED antes que GREEN.

`lectura_agregada(directorio, ruta_audit=None) -> dict` produce un informe AGREGADO y SIN CONTENIDO
de la integridad de la residencia: control-plane (siempre) + audit (si `ruta_audit` no es None).
PURA de solo lectura. El dict devuelto contiene SOLO numeros, enums de estado, nombres de tipo e ids
de `seq` — CERO texto libre de msg/datos/descripcion/content/motivo/provenance/tokens/rutas.

Ver ficha: `.claude/ficha-evidencia.md` (diseno de F4). NUNCA se lee `~/.aura` real en estas pruebas:
todos los datos son sinteticos en `tmp_path`.
"""

from __future__ import annotations

import json
import pathlib

import control_plane as cp


# ------------------------------------------------------------------ constructores sinteticos --


def _huellas(directorio: pathlib.Path, ruta_audit: pathlib.Path | None = None) -> dict:
    """Bytes + mtime de estado.json, eventos.jsonl, ancla y (si se da) el audit, para el control de
    PUREZA: nada debe cambiar tras llamar a `lectura_agregada`."""
    rutas = {
        "estado": directorio / "estado.json",
        "eventos": cp.ruta_eventos(directorio),
        "ancla": cp.ruta_ancla(directorio),
    }
    if ruta_audit is not None:
        rutas["audit"] = ruta_audit
    out: dict = {}
    for nombre, ruta in rutas.items():
        if ruta.exists():
            st = ruta.stat()
            out[nombre] = (ruta.read_bytes(), st.st_mtime_ns)
        else:
            out[nombre] = None
    return out


def _listar(directorio: pathlib.Path) -> set[str]:
    """Nombres de todos los ficheros bajo `directorio`, recursivo, para el control de "NO ficheros
    nuevos"."""
    return {str(p.relative_to(directorio)) for p in directorio.rglob("*") if p.is_file()}


def _escribir_audit_sintetico(ruta: pathlib.Path, lineas: list[dict]) -> None:
    """Escribe un .jsonl a mano: NUNCA se instancia AuditLog (su __init__ reconciliaria huerfanos =
    escribe) ni para construir el sintetico de prueba."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        for linea in lineas:
            fh.write(json.dumps(linea, ensure_ascii=False) + "\n")


def _reg_audit(seq: int, evento: str = "demo.evento", module: str = "demo",
               msg: str = "") -> dict:
    return {"seq": seq, "evento": evento, "module": module, "msg": msg, "ts": 0.0}


# -------------------------------------------------------------------------- bloque control-plane --


def test_cuenta_seq_duplicados_del_control_plane_y_lista_los_ids(tmp_path):
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "x", "review": False, "tope": 1})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"detenida_en": None, "ejecutadas": 0,
                                                       "bloqueadas": 0, "elevadas": 0, "motivo": ""})
    # Planta un seq duplicado escribiendo una linea extra con el mismo seq que la ultima.
    ruta = cp.ruta_eventos(tmp_path)
    lineas = [ln for ln in ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ultima = json.loads(lineas[-1])
    duplicada = dict(ultima)
    lineas.append(json.dumps(duplicada, ensure_ascii=False))
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    informe = cp.lectura_agregada(tmp_path)
    bloque = informe["control_plane"]
    assert bloque["seq_duplicados"] >= 1
    assert ultima["seq"] in bloque["seq_duplicados_ids"]


def test_ciclo_abierto_vs_cerrado_motor(tmp_path):
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "x", "review": False, "tope": 1})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"detenida_en": None, "ejecutadas": 0,
                                                       "bloqueadas": 0, "elevadas": 0, "motivo": ""})
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "x", "review": False, "tope": 1})
    # el segundo queda SIN cierre -> abierto

    informe = cp.lectura_agregada(tmp_path)
    bloque = informe["control_plane"]
    assert bloque["ciclos_cerrados"] == 1
    assert bloque["ciclos_abiertos"] == [3]  # seq del motor_iniciado sin cierre


def test_ciclo_abierto_vs_cerrado_autonomo(tmp_path):
    cp.registrar_evento(tmp_path, "ciclo_autonomo_iniciado", {"max_tareas": 1, "review": False})
    cp.registrar_evento(tmp_path, "ciclo_autonomo_terminado", {"clase": "ok", "detenida_en": None,
                                                                  "ejecutadas": 0, "pendientes": 0,
                                                                  "propuestas": 0, "revertidas": 0,
                                                                  "siguiente": None,
                                                                  "actos_humanos_durante_el_ciclo": 0,
                                                                  "motivo_de_parada": ""})
    cp.registrar_evento(tmp_path, "ciclo_autonomo_iniciado", {"max_tareas": 1, "review": False})

    informe = cp.lectura_agregada(tmp_path)
    bloque = informe["control_plane"]
    assert bloque["ciclos_cerrados"] == 1
    assert bloque["ciclos_abiertos"] == [3]


def test_recuento_de_tipos_por_nombre(tmp_path):
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "x", "review": False, "tope": 1})
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "y", "review": False, "tope": 1})

    informe = cp.lectura_agregada(tmp_path)
    bloque = informe["control_plane"]
    assert bloque["recuento_por_tipo"]["motor_iniciado"] == 2


def test_privacidad_un_tipo_libre_con_secreto_no_llega_al_informe(tmp_path):
    """HALLAZGO 1 (CRITICO): `tipo` es cadena LIBRE en `registrar_evento` (solo se rechaza si esta en
    EVENTOS_GOBERNADOS). Usarlo como clave de `recuento_por_tipo` filtra contenido. El vocabulario
    CERRADO cuenta los tipos conocidos por su nombre y agrupa el resto bajo `"otros"`."""
    secreto = "evento_personalizado_IBAN_ES7620770024003102575766_token_XYZ_secreto"
    cp.registrar_evento(tmp_path, secreto, {"x": 1})
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "x", "review": False, "tope": 1})

    informe = cp.lectura_agregada(tmp_path)
    serializado = json.dumps(informe, ensure_ascii=False)
    # El nombre libre NO aparece en ninguna parte del informe.
    assert secreto not in serializado
    assert "ES7620770024003102575766" not in serializado
    recuento = informe["control_plane"]["recuento_por_tipo"]
    # El tipo fuera del vocabulario cerrado se agrupa como "otros", solo con su total.
    assert recuento.get("otros") == 1
    assert secreto not in recuento
    # Un tipo CONOCIDO si aparece por su nombre con su recuento (el vocabulario no rompe lo legitimo).
    assert recuento.get("motor_iniciado") == 1


def test_recuento_por_tipo_solo_expone_claves_del_vocabulario_cerrado_mas_otros(tmp_path):
    """Control fuerte: ninguna clave del recuento puede estar fuera de `_TIPOS_CONOCIDOS_DEL_CP`
    salvo la clave fija `"otros"`. Asi, aunque el secreto no se parezca a un IBAN, no puede colarse."""
    cp.registrar_evento(tmp_path, "ni-idea-de-lo-que-pone-aqui", {"x": 1})
    informe = cp.lectura_agregada(tmp_path)
    claves = set(informe["control_plane"]["recuento_por_tipo"])
    permitidas = set(cp._TIPOS_CONOCIDOS_DEL_CP) | {"otros"}
    assert claves <= permitidas


def test_dos_linea_de_audit_con_anidamiento_profundo_no_lanza(tmp_path):
    """HALLAZGO 2 (ALTO, DoS): una linea con JSON profundamente anidado lanza `RecursionError`, que
    los parsers no capturaban (solo `JSONDecodeError`). Debe descartarse la linea, no propagarse."""
    ruta_audit = tmp_path / "audit.jsonl"
    profundo = "[" * 60000 + "]" * 60000
    with open(ruta_audit, "w", encoding="utf-8") as fh:
        fh.write(profundo + "\n")
        fh.write(json.dumps(_reg_audit(1)) + "\n")

    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    # La linea profunda se descarta; la valida se procesa.
    assert informe["audit"]["lineas"] == 1
    assert informe["audit"]["seq_max"] == 1


def test_dos_linea_de_manifiesto_con_anidamiento_profundo_no_lanza(tmp_path):
    """Igual que el anterior pero en el manifiesto del audit: una linea profunda no debe propagar
    `RecursionError`."""
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(3), _reg_audit(4)])
    nombre_segmento = f"{ruta_audit.name}.{1:012d}-{2:012d}"
    _escribir_audit_sintetico(ruta_audit.parent / nombre_segmento, [_reg_audit(1), _reg_audit(2)])
    manifiesto = pathlib.Path(str(ruta_audit) + ".manifest")
    profundo = "[" * 60000 + "]" * 60000
    with open(manifiesto, "w", encoding="utf-8") as fh:
        fh.write(profundo + "\n")
        fh.write(json.dumps({"segmento": nombre_segmento, "sha256": "x",
                             "seq_ini": 1, "seq_fin": 2}) + "\n")

    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    # El manifiesto se lee pese a la linea profunda: el segmento queda anotado (no huerfano).
    assert informe["audit"]["huerfanos"] == 0
    assert informe["audit"]["segmentos"] == 1


def test_veredicto_de_proyeccion_usa_F1(tmp_path):
    informe = cp.lectura_agregada(tmp_path)
    bloque = informe["control_plane"]
    assert bloque["proyeccion"]["estado"] == cp.estado_de_la_proyeccion(tmp_path)["estado"]


def test_estado_json_solo_metadatos_enum(tmp_path):
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "secreto-no-expuesto"})
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="ceo", causa="una causa con texto libre")
    proy = cp.proyectar(tmp_path)
    almacenado = dict(proy)
    almacenado["tareas"] = {tid: {**t, "previo": "WAITING_FOR_NEXT_TASK"}
                             for tid, t in proy["tareas"].items()}
    almacenado["git"] = {"ultimo_commit": "deadbeef"}
    cp.guardar(almacenado, tmp_path / "estado.json")

    informe = cp.lectura_agregada(tmp_path)
    bloque = informe["control_plane"]["estado_json"]
    assert bloque["status"] == "WAITING_FOR_NEXT_TASK"  # estado_inicial, no el de la tarea
    assert bloque["num_tareas"] == 1
    assert bloque["recuento_por_estado"]["WORKING"] == 1
    assert "descripcion" not in json.dumps(bloque)


def test_sin_estado_json_el_bloque_lo_refleja(tmp_path):
    informe = cp.lectura_agregada(tmp_path)
    assert informe["control_plane"]["estado_json"] is None


# -------------------------------------------------------------------------- bloque audit --


def test_privacidad_el_evento_del_audit_no_se_expone_en_el_informe(tmp_path):
    """El bloque audit NO debe exponer el campo `evento` de los registros: puede llevar texto libre/contenido.
    Mata al mutante que haria aflorar `eventos` en el retorno (LA1)."""
    secreto = "evento_con_IBAN_ES7620770024003102575766_y_token"
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(1, evento=secreto, msg="contenido-secreto-xyz")])
    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    assert secreto not in json.dumps(informe), "el `evento` del audit no debe aflorar"
    assert "contenido-secreto-xyz" not in json.dumps(informe), "el `msg` tampoco"
    assert "eventos" not in informe["audit"], "el bloque audit no expone la lista de eventos"


def test_audit_cuenta_seq_duplicados_y_lista_ids(tmp_path):
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [
        _reg_audit(1), _reg_audit(2), _reg_audit(2), _reg_audit(3),
    ])
    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    bloque = informe["audit"]
    assert bloque["seq_duplicados"] == 1
    assert bloque["seq_duplicados_ids"] == [2]


def test_audit_detecta_huecos(tmp_path):
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(1), _reg_audit(5)])
    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    assert informe["audit"]["huecos"] >= 1


def test_audit_detecta_huerfano(tmp_path):
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(10), _reg_audit(11)])
    # Segmento "huerfano": nombre con forma de segmento (basename + .SEQINI-SEQFIN) SIN entrada en
    # el manifiesto (que no existe en absoluto aqui).
    nombre_segmento = f"{ruta_audit.name}.{1:012d}-{2:012d}"
    _escribir_audit_sintetico(ruta_audit.parent / nombre_segmento, [_reg_audit(1), _reg_audit(2)])

    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    assert informe["audit"]["huerfanos"] == 1


def test_audit_segmento_anotado_en_manifiesto_no_es_huerfano(tmp_path):
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(3), _reg_audit(4)])
    nombre_segmento = f"{ruta_audit.name}.{1:012d}-{2:012d}"
    _escribir_audit_sintetico(ruta_audit.parent / nombre_segmento, [_reg_audit(1), _reg_audit(2)])
    manifiesto = pathlib.Path(str(ruta_audit) + ".manifest")
    _escribir_audit_sintetico(manifiesto, [
        {"segmento": nombre_segmento, "sha256": "x", "seq_ini": 1, "seq_fin": 2},
    ])

    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    assert informe["audit"]["huerfanos"] == 0
    assert informe["audit"]["segmentos"] == 1


def test_audit_omitido_si_ruta_audit_es_none(tmp_path):
    informe = cp.lectura_agregada(tmp_path, ruta_audit=None)
    assert "audit" not in informe


def test_audit_ausente_no_rompe(tmp_path):
    informe = cp.lectura_agregada(tmp_path, ruta_audit=tmp_path / "no-existe.jsonl")
    assert informe["audit"]["lineas"] == 0


# -------------------------------------------------------------------------- PRIVACIDAD (clave) --


def test_privacidad_el_secreto_del_audit_no_aparece_en_el_informe(tmp_path):
    secreto = "IBAN ES7620770024003102575766 clave-secreta token-XYZ-99887"
    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(1, msg=secreto), _reg_audit(2, msg=secreto)])

    informe = cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)
    serializado = json.dumps(informe, ensure_ascii=False)
    assert secreto not in serializado
    assert "clave-secreta" not in serializado
    assert "token-XYZ-99887" not in serializado


def test_privacidad_descripciones_y_causas_sensibles_no_aparecen(tmp_path):
    secreto = "el motivo real es una fusion confidencial con ACME-SECRETA"
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": secreto})
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="ceo", causa=secreto)
    proy = cp.proyectar(tmp_path)
    almacenado = dict(proy)
    almacenado["tareas"] = {tid: {**t, "previo": "WAITING_FOR_NEXT_TASK"}
                             for tid, t in proy["tareas"].items()}
    almacenado["git"] = {"ultimo_commit": "deadbeef"}
    cp.guardar(almacenado, tmp_path / "estado.json")

    informe = cp.lectura_agregada(tmp_path)
    serializado = json.dumps(informe, ensure_ascii=False)
    assert secreto not in serializado
    assert "ACME-SECRETA" not in serializado


def test_privacidad_motivo_de_ciclo_no_aparece(tmp_path):
    secreto_motivo = "bloqueada por decision confidencial del comite X"
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": "x", "review": False, "tope": 1})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"detenida_en": None, "ejecutadas": 0,
                                                       "bloqueadas": 0, "elevadas": 0,
                                                       "motivo": secreto_motivo})
    informe = cp.lectura_agregada(tmp_path)
    serializado = json.dumps(informe, ensure_ascii=False)
    assert secreto_motivo not in serializado


# -------------------------------------------------------------------------- PUREZA --


def test_pureza_no_cambia_bytes_ni_mtime_ni_crea_ficheros(tmp_path):
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "descripcion": "algo"})
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="ceo", causa="empezar")
    proy = cp.proyectar(tmp_path)
    almacenado = dict(proy)
    almacenado["tareas"] = {tid: {**t, "previo": "WAITING_FOR_NEXT_TASK"}
                             for tid, t in proy["tareas"].items()}
    almacenado["git"] = {"ultimo_commit": "deadbeef"}
    cp.guardar(almacenado, tmp_path / "estado.json")

    ruta_audit = tmp_path / "subdir" / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(1), _reg_audit(2)])

    antes_huellas = _huellas(tmp_path, ruta_audit)
    antes_ficheros = _listar(tmp_path)

    cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)

    assert _huellas(tmp_path, ruta_audit) == antes_huellas
    assert _listar(tmp_path) == antes_ficheros


def test_pureza_no_instancia_auditlog_ni_llama_a_escrituras(tmp_path, monkeypatch):
    """Monkeypatch-espia: ni `AuditLog` se instancia, ni `guardar`/`registrar_evento` se llaman desde
    dentro de `lectura_agregada`. `control_plane.py` no importa `observability`/`AuditLog` en
    absoluto hoy (comprobado: ningun `import` de ese modulo en el fichero); la garantia fuerte es
    justo esa ausencia de import, mas espiar las dos funciones de escritura propias del modulo."""
    llamadas: list[str] = []

    guardar_real = cp.guardar
    registrar_real = cp.registrar_evento

    def _espia_guardar(*args, **kwargs):
        llamadas.append("guardar")
        return guardar_real(*args, **kwargs)

    def _espia_registrar(*args, **kwargs):
        llamadas.append("registrar_evento")
        return registrar_real(*args, **kwargs)

    monkeypatch.setattr(cp, "guardar", _espia_guardar)
    monkeypatch.setattr(cp, "registrar_evento", _espia_registrar)

    ruta_audit = tmp_path / "audit.jsonl"
    _escribir_audit_sintetico(ruta_audit, [_reg_audit(1), _reg_audit(2)])

    cp.lectura_agregada(tmp_path, ruta_audit=ruta_audit)

    assert llamadas == []
    # `control_plane.py` nunca importa `AuditLog`: ni como nombre del modulo ni como atributo.
    assert not hasattr(cp, "AuditLog")
