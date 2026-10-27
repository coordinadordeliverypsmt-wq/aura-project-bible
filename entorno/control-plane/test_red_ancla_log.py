"""RED · D-LOG-1 — borrar la cola del log de eventos tenia que dejar de ser indetectable.

`verificar_integridad_log` comprobaba la continuidad interna (seq, hash_anterior, hash), pero nada
anclaba la CABEZA fuera del log: borrar los N ultimos eventos completos dejaba una cadena perfecta.
Medido (DEUDA-LOG-COLA-SIN-ANCLA): con 2 eventos menos devolvia `integro: True`.

Todas las pruebas usan historiales SINTETICOS en `tmp_path` y `AURA_ANCLA_DIR` apuntando tambien a un
temporal (lo fija el conftest): ninguna escribe anclas en `~/.local/state` real.

Cada prueba tiene su caso de control: el mismo guion sin el defecto da `integro: True`.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import pathlib
import shutil
import stat

import control_plane as cp
import pytest


def _log(tmp_path, n: int = 6) -> pathlib.Path:
    d = pathlib.Path(tmp_path) / "hist"
    for i in range(n):
        cp.registrar_evento(d, "hecho", {"i": i})
    return d


def _quitar_ultimos(d: pathlib.Path, k: int) -> None:
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    ruta.write_text("".join(lineas[:-k]), encoding="utf-8")


def _ancla_json(d) -> dict:
    return json.loads(cp.ruta_ancla(d).read_text(encoding="utf-8"))


def _escribir_ancla_cruda(d, contenido) -> None:
    ruta = cp.ruta_ancla(d)
    ruta.write_text(contenido if isinstance(contenido, str) else json.dumps(contenido),
                    encoding="utf-8")


# ===================================================== CONTROL · el log intacto ==


def test_control_el_log_intacto_es_integro_y_completo(tmp_path):
    d = _log(tmp_path, 6)
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is True
    assert r["integridad_eventos"] is True and r["completitud"] == "demostrada"
    assert r["completitud_desde"] == 1
    assert r["eventos"] == 6
    assert r["ancla"]["seq"] == 6 and r["ancla"]["atrasada"] is False


def test_el_resultado_declara_lo_que_NO_garantiza(tmp_path):
    """Mismo uid: quien puede borrar la cola puede reescribir el ancla. Se dice, no se calla."""
    r = cp.verificar_integridad_log(_log(tmp_path, 2))
    assert r["autenticidad_origen"] == "no_garantizada"
    assert r["restauracion_conjunta_log_y_ancla"] == "no_detectable"


# ===================================================== TRUNCAMIENTO DE COLA (RED) ==


@pytest.mark.parametrize("k", [1, 2, 4])
def test_borrar_los_ultimos_k_eventos_YA_NO_pasa_por_integro(tmp_path, k):
    d = _log(tmp_path, 6)
    _quitar_ultimos(d, k)
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False
    assert r["integridad_eventos"] is True, "la cadena restante sigue siendo consistente"
    assert r["completitud"] == "truncada_o_alterada"
    assert r["motivo_codigo"] == "cola_mas_corta_que_el_ancla"
    assert r["eventos"] == 6 - k and r["seq_ancla"] == 6


def test_borrar_todo_el_log_no_pasa_por_vacio_sano(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_eventos(d).write_text("", encoding="utf-8")
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == "cola_mas_corta_que_el_ancla"


def test_alteracion_intermedia_sigue_detectada(tmp_path):
    d = _log(tmp_path, 6)
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    evento = json.loads(lineas[2])
    evento["datos"]["i"] = 999
    lineas[2] = json.dumps(evento)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["integridad_eventos"] is False and r["seq"] == 3


def test_alteracion_del_ultimo_evento_detectada(tmp_path):
    d = _log(tmp_path, 4)
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    evento = json.loads(lineas[-1])
    evento["datos"]["i"] = 777
    lineas[-1] = json.dumps(evento)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["seq"] == 4


def test_el_ultimo_evento_reescrito_con_hash_valido_se_detecta_por_el_ancla(tmp_path):
    """Cadena interna PERFECTA (el atacante recalcula el hash del ultimo) pero distinta del ancla."""
    d = _log(tmp_path, 4)
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    evento = json.loads(lineas[-1])
    evento["datos"]["i"] = 555
    evento["hash"] = cp._hash_de(evento)
    lineas[-1] = cp._canonico(evento)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    r = cp.verificar_integridad_log(d)
    assert r["integridad_eventos"] is True
    assert r["integro"] is False and r["motivo_codigo"] == "hash_distinto_en_el_ancla"


# ===================================================== EL ANCLA EN SI ==


def test_ancla_ausente_con_log_no_vacio_NO_es_integro_y_no_se_inicializa(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).unlink()
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == "ancla_ausente"
    assert r["integridad_eventos"] is True
    assert not cp.ruta_ancla(d).exists(), "verificar no crea el ancla en silencio"


def test_un_escritor_NO_crea_el_ancla_si_falta_con_log_no_vacio(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).unlink()
    cp.registrar_evento(d, "hecho", {"i": 99})
    assert not cp.ruta_ancla(d).exists()
    assert cp.verificar_integridad_log(d)["motivo_codigo"] == "ancla_ausente"


def test_log_vacio_sin_ancla_es_integro_y_el_primer_evento_crea_el_ancla(tmp_path):
    d = pathlib.Path(tmp_path) / "vacio"
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is True and r["eventos"] == 0
    assert not cp.ruta_ancla(d).exists()
    cp.registrar_evento(d, "hecho", {})
    assert _ancla_json(d)["seq"] == 1
    assert cp.verificar_integridad_log(d)["integro"] is True


@pytest.mark.parametrize("contenido,codigo", [
    ("{no es json", "ancla_corrupta"),
    ("[1, 2]", "ancla_corrupta"),
    ({"version": 99, "seq": 1, "hash": "x"}, "ancla_incompatible"),
    ({"version": 1}, "ancla_corrupta"),
])
def test_ancla_corrupta_o_incompatible_no_es_integro(tmp_path, contenido, codigo):
    d = _log(tmp_path, 3)
    _escribir_ancla_cruda(d, contenido)
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == codigo


def test_ancla_de_otro_historial_no_es_integro(tmp_path):
    a = _log(pathlib.Path(tmp_path) / "a", 3)
    b = _log(pathlib.Path(tmp_path) / "b", 3)
    # El ancla de `a` puesta en el sitio del ancla de `b`: la ruta/genesis declaradas no son las de `b`.
    shutil.copyfile(cp.ruta_ancla(a), cp.ruta_ancla(b))
    r = cp.verificar_integridad_log(b)
    assert r["integro"] is False and r["motivo_codigo"] == "ancla_de_otro_historial"


def test_ancla_adelantada_no_es_integro(tmp_path):
    d = _log(tmp_path, 3)
    ancla = _ancla_json(d)
    ancla["seq"] = 9
    _escribir_ancla_cruda(d, ancla)
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == "cola_mas_corta_que_el_ancla"


def test_hash_del_ancla_distinto_al_del_evento_no_es_integro(tmp_path):
    d = _log(tmp_path, 3)
    ancla = _ancla_json(d)
    ancla["hash"] = "0" * 64
    _escribir_ancla_cruda(d, ancla)
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == "hash_distinto_en_el_ancla"


def test_el_ancla_vive_FUERA_del_directorio_del_log_con_permisos_privados(tmp_path):
    d = _log(tmp_path, 2)
    ruta = cp.ruta_ancla(d)
    assert d.resolve() not in ruta.resolve().parents
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(ruta.parent).st_mode) == 0o700
    ancla = _ancla_json(d)
    assert ancla["historial"]["ruta"] == str(d.resolve())
    assert ancla["hash"] == cp.leer_eventos(d)[-1]["hash"]
    assert {"version", "historial", "seq", "hash", "momento"} <= set(ancla)


def test_la_ruta_por_defecto_es_xdg_state_home_aura_anclas_sha16(tmp_path, monkeypatch):
    monkeypatch.delenv("AURA_ANCLA_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    d = pathlib.Path(tmp_path) / "hist"
    clave = hashlib.sha256(str(d.resolve()).encode()).hexdigest()[:16]
    assert cp.ruta_ancla(d) == tmp_path / "xdg" / "aura" / "anclas" / f"{clave}.json"


def test_AURA_ANCLA_DIR_sobreescribe_la_ruta(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_ANCLA_DIR", str(tmp_path / "otro"))
    d = pathlib.Path(tmp_path) / "hist"
    assert cp.ruta_ancla(d).parent == tmp_path / "otro"


def test_la_bateria_NUNCA_escribe_anclas_en_el_estado_real(tmp_path):
    """Control del conftest: si `AURA_ANCLA_DIR` no estuviera fijado, las pruebas escribirian en
    `~/.local/state/aura/anclas`."""
    fijado = os.environ.get("AURA_ANCLA_DIR", "")
    assert fijado, "el conftest tiene que fijar AURA_ANCLA_DIR"
    real = pathlib.Path.home() / ".local" / "state" / "aura" / "anclas"
    assert pathlib.Path(fijado).resolve() != real.resolve()
    assert real.resolve() not in pathlib.Path(fijado).resolve().parents


def test_la_escritura_del_ancla_es_atomica(tmp_path, monkeypatch):
    """Si el `rename` falla, el ancla anterior queda INTACTA (no medio escrita) y -decision del escritor
    sin ancla- el EVENTO se escribe igualmente: el ancla queda atrasada y reconocida, no hay error."""
    d = _log(tmp_path, 3)
    antes = cp.ruta_ancla(d).read_bytes()

    def falla(*a, **k):
        raise OSError("rename fallido")

    with monkeypatch.context() as m:
        m.setattr(cp.os, "replace", falla)
        cp.registrar_evento(d, "hecho", {"i": 50})            # no lanza: el ancla no bloquea la escritura
    assert cp.ruta_ancla(d).read_bytes() == antes
    assert not list(cp.ruta_ancla(d).parent.glob("*.tmp")), "sin temporales huerfanos"
    r = cp.verificar_integridad_log(d)
    assert len(cp.leer_eventos(d)) == 4 and r["integro"] is True and r["ancla"]["atrasada"] is True


# ===================================================== CAIDA ENTRE EVENTO Y ANCLA ==


def _caer_al_anclar(monkeypatch):
    original = cp._escribir_ancla
    estado = {"cae": True}

    def inyectada(*a, **k):
        if estado["cae"]:
            estado["cae"] = False
            raise RuntimeError("caida entre el evento y el ancla")
        return original(*a, **k)

    monkeypatch.setattr(cp, "_escribir_ancla", inyectada)


def test_caida_tras_escribir_el_evento_deja_el_ancla_ATRASADA_y_reconocida(tmp_path, monkeypatch):
    d = _log(tmp_path, 3)
    _caer_al_anclar(monkeypatch)
    with pytest.raises(RuntimeError):
        cp.registrar_evento(d, "hecho", {"i": 10})
    assert len(cp.leer_eventos(d)) == 4 and _ancla_json(d)["seq"] == 3
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is True, "ancla atrasada con cola valida NO es truncamiento"
    assert r["ancla"]["atrasada"] is True and r["ancla"]["eventos_sin_anclar"] == 1


def test_reparar_ancla_la_adelanta_y_es_idempotente(tmp_path, monkeypatch):
    d = _log(tmp_path, 3)
    _caer_al_anclar(monkeypatch)
    with pytest.raises(RuntimeError):
        cp.registrar_evento(d, "hecho", {"i": 10})
    primero = cp.reparar_ancla(d)
    assert primero["reparada"] is True and _ancla_json(d)["seq"] == 4
    bytes1 = cp.ruta_ancla(d).read_bytes()
    segundo = cp.reparar_ancla(d)
    assert segundo["reparada"] is False and cp.ruta_ancla(d).read_bytes() == bytes1
    assert cp.verificar_integridad_log(d)["ancla"]["atrasada"] is False


def test_el_siguiente_escritor_tambien_adelanta_el_ancla(tmp_path, monkeypatch):
    d = _log(tmp_path, 3)
    _caer_al_anclar(monkeypatch)
    with pytest.raises(RuntimeError):
        cp.registrar_evento(d, "hecho", {"i": 10})
    cp.registrar_evento(d, "hecho", {"i": 11})
    assert _ancla_json(d)["seq"] == 5
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_reparar_ancla_SOLO_avanza_nunca_retrocede_ni_arregla_un_truncamiento(tmp_path):
    d = _log(tmp_path, 5)
    _quitar_ultimos(d, 2)
    antes = cp.ruta_ancla(d).read_bytes()
    r = cp.reparar_ancla(d)
    assert r["reparada"] is False and r["motivo_codigo"] == "cola_mas_corta_que_el_ancla"
    assert cp.ruta_ancla(d).read_bytes() == antes, "el ancla no se baja para tapar el borrado"
    assert cp.verificar_integridad_log(d)["integro"] is False


def test_reparar_ancla_no_la_crea_si_falta(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).unlink()
    r = cp.reparar_ancla(d)
    assert r["reparada"] is False and r["motivo_codigo"] == "ancla_ausente"
    assert not cp.ruta_ancla(d).exists()


def test_reparar_ancla_no_avanza_sobre_una_cadena_rota(tmp_path, monkeypatch):
    d = _log(tmp_path, 3)
    _caer_al_anclar(monkeypatch)
    with pytest.raises(RuntimeError):
        cp.registrar_evento(d, "hecho", {"i": 10})
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    evento = json.loads(lineas[-1])
    evento["datos"]["i"] = 4242
    lineas[-1] = json.dumps(evento)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    assert cp.reparar_ancla(d)["reparada"] is False
    assert _ancla_json(d)["seq"] == 3


def test_un_escritor_sobre_un_log_truncado_ESCRIBE_pero_no_adelanta_el_ancla_y_la_deteccion_persiste(tmp_path):
    """Contrato nuevo (reemplaza a `AnclaInconsistente` en el escritor): la escritura no se bloquea, pero el
    ancla no se mueve, asi que el truncamiento sigue detectado por mas eventos que se anadan. Control: sin
    truncar, el mismo escritor SI adelanta el ancla."""
    d = _log(tmp_path, 5)
    _quitar_ultimos(d, 2)
    ancla = cp.ruta_ancla(d).read_bytes()
    for i in range(5):                                     # hasta superar el seq anclado
        cp.registrar_evento(d, "hecho", {"i": 100 + i})
    assert len(cp.leer_eventos(d)) == 8 and cp.ruta_ancla(d).read_bytes() == ancla
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["completitud"] == "truncada_o_alterada"
    assert r["motivo_codigo"] == "hash_distinto_en_el_ancla", "el seq 5 ya no tiene el hash anclado"
    sano = _log(tmp_path / "control", 5)
    cp.registrar_evento(sano, "hecho", {"i": 1})
    assert _ancla_json(sano)["seq"] == 6 and cp.verificar_integridad_log(sano)["integro"] is True


def test_registrar_evento_si_pasa_por_el_mismo_mecanismo(tmp_path):
    d = _log(tmp_path, 2)
    cp.registrar_evento_si(d, "hecho", {"i": 5}, lambda: True)
    assert _ancla_json(d)["seq"] == 3
    # Control: si la condicion es falsa no se escribe nada ni se mueve el ancla.
    assert cp.registrar_evento_si(d, "hecho", {"i": 6}, lambda: False) is None
    assert _ancla_json(d)["seq"] == 3


# ===================================================== ADOPCION EXPLICITA ==


def test_adoptar_ancla_crea_el_ancla_y_deja_constancia_en_el_log(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).unlink()
    r = cp.adoptar_ancla(d, por="CEO", motivo="despliegue de D-LOG-1")
    assert r["adoptada"] is True
    ultimo = cp.leer_eventos(d)[-1]
    assert ultimo["tipo"] == "ancla_adoptada"
    assert ultimo["datos"]["por"] == "CEO" and ultimo["datos"]["motivo"] == "despliegue de D-LOG-1"
    assert _ancla_json(d)["seq"] == ultimo["seq"]
    assert cp.verificar_integridad_log(d)["integro"] is True


@pytest.mark.parametrize("por,motivo", [("", "x"), ("CEO", ""), ("  ", "x"), (None, "x"), ("CEO", None)])
def test_adoptar_ancla_exige_quien_y_por_que(tmp_path, por, motivo):
    d = _log(tmp_path, 2)
    cp.ruta_ancla(d).unlink()
    with pytest.raises(ValueError):
        cp.adoptar_ancla(d, por=por, motivo=motivo)
    assert len(cp.leer_eventos(d)) == 2 and not cp.ruta_ancla(d).exists()


def test_adoptar_ancla_NO_pisa_un_ancla_existente_sin_reemplazar(tmp_path):
    d = _log(tmp_path, 3)
    _quitar_ultimos(d, 1)
    with pytest.raises(cp.AnclaInconsistente):
        cp.adoptar_ancla(d, por="CEO", motivo="intento de tapar un truncamiento")
    assert cp.verificar_integridad_log(d)["integro"] is False


def test_adoptar_ancla_no_se_hace_sobre_una_cadena_rota(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).unlink()
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    evento = json.loads(lineas[1])
    evento["datos"]["i"] = 31337
    lineas[1] = json.dumps(evento)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    with pytest.raises(cp.AnclaInconsistente):
        cp.adoptar_ancla(d, por="CEO", motivo="x")
    assert not cp.ruta_ancla(d).exists()


# ===================================================== RESTAURACION ANTIGUA ==


def test_restaurar_una_copia_antigua_SOLO_del_log_se_detecta(tmp_path):
    d = _log(tmp_path, 4)
    copia = tmp_path / "copia-eventos.jsonl"
    shutil.copyfile(cp.ruta_eventos(d), copia)
    for i in range(3):
        cp.registrar_evento(d, "hecho", {"i": 100 + i})
    shutil.copyfile(copia, cp.ruta_eventos(d))
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == "cola_mas_corta_que_el_ancla"


def test_LIMITE_restaurar_log_Y_ancla_juntos_NO_se_detecta(tmp_path):
    """Limite DECLARADO (mismo uid): un atacante que puede escribir ambos puede devolver el pasado
    completo. La prueba fija que la limitacion es la descrita y que el resultado lo dice."""
    d = _log(tmp_path, 4)
    copia_log = tmp_path / "log.bak"
    copia_ancla = tmp_path / "ancla.bak"
    shutil.copyfile(cp.ruta_eventos(d), copia_log)
    shutil.copyfile(cp.ruta_ancla(d), copia_ancla)
    for i in range(3):
        cp.registrar_evento(d, "hecho", {"i": 100 + i})
    shutil.copyfile(copia_log, cp.ruta_eventos(d))
    shutil.copyfile(copia_ancla, cp.ruta_ancla(d))
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is True
    assert r["restauracion_conjunta_log_y_ancla"] == "no_detectable"


# ===================================================== CONCURRENCIA ==


def _escritor(d, n, k):
    for j in range(k):
        cp.registrar_evento(pathlib.Path(d), "hecho", {"proc": n, "j": j})


def test_escritores_concurrentes_dejan_cadena_y_ancla_coherentes(tmp_path):
    d = pathlib.Path(tmp_path) / "conc"
    ctx = multiprocessing.get_context("fork")
    procs = [ctx.Process(target=_escritor, args=(str(d), n, 12)) for n in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
        assert p.exitcode == 0
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is True and r["eventos"] == 48
    assert r["ancla"]["seq"] == 48 and r["ancla"]["atrasada"] is False


def test_verificar_durante_la_escritura_no_da_falsos_truncamientos(tmp_path):
    """El verificador lee el ancla ANTES que los eventos: un escritor que avanza entre medias solo
    puede dejar el ancla por detras de lo leido, nunca por delante."""
    d = pathlib.Path(tmp_path) / "conc2"
    cp.registrar_evento(d, "hecho", {})
    ctx = multiprocessing.get_context("fork")
    p = ctx.Process(target=_escritor, args=(str(d), 0, 60))
    p.start()
    veredictos = []
    while p.is_alive():
        veredictos.append(cp.verificar_integridad_log(d))
    p.join(60)
    assert veredictos and all(v["integro"] is True for v in veredictos), \
        [v for v in veredictos if not v["integro"]][:1]
