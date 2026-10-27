"""Revisión de seguridad: B-2 (errores de codificación), B-3 (tasa y epoch monótono), B-5 (socket y log encadenado)."""

from __future__ import annotations

import json
import os
import socket
import stat
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton.adapters.firma_delegacion import ErrorClave, generar_firmante, verificador_de
from aura_skeleton.adapters.firmador_hc1 import (
    CADENA_INICIAL,
    ErrorFirmador,
    Firmador,
    PoliticaFirmador,
    crear_servidor,
    pedir_firma,
    verificar_cadena_log,
)
from aura_skeleton.core.delegacion import DOMINIO_ORDEN, Motivo, RechazoOrden, verificar_y_leer
from tests.delegacion_apoyo import NODO
from tests.unit.test_delegacion_diario_hc1 import _EspiaFsync

PET = {"tarea": "t-1", "intento": 1, "destinatario": NODO, "capacidad": "calcular_resumen_sha256",
       "argumentos": {"texto": "hola"}, "vida_s": 60}  # fmt: skip


class Reloj:
    def __init__(self, t: float = 5000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _politica(**kw: Any) -> PoliticaFirmador:
    base: dict[str, Any] = {"emisor": "hc1", "kid": "hc1-k1", "destinatarios": frozenset({NODO}),
                            "capacidades": frozenset({"calcular_resumen_sha256"}), "epoch": 7}  # fmt: skip
    base.update(kw)
    return PoliticaFirmador(**base)


def _firmador(tmp_path: Path, reloj: Reloj | None = None, **kw: Any) -> tuple[Firmador, Path]:
    d = tmp_path / "f"
    d.mkdir(mode=0o700, exist_ok=True)
    log = d / "log.jsonl"
    return Firmador(generar_firmante("hc1-k1"), _politica(**kw), log, ahora=reloj or Reloj()), log


def _log(ruta: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in ruta.read_text().splitlines()]


# --- B-2: errores de codificación -----------------------------------------------------------------------------


@pytest.mark.parametrize("texto", ["\ud800", "hola \udfff", "\udc80\ud800"])
def test_b2_surrogates_sueltos_son_un_rechazo_registrado_no_una_excepcion(tmp_path: Path, texto: str) -> None:
    fm, log = _firmador(tmp_path)
    with pytest.raises(RechazoOrden) as e:
        fm.firmar({**PET, "argumentos": {"texto": texto}})
    assert e.value.motivo is Motivo.CAMPO_INVALIDO
    ultimo = _log(log)[-1]
    assert ultimo["tipo"] == "rechazo" and ultimo["motivo"] == "campo_invalido"
    assert fm.firmar({**PET, "argumentos": {"texto": "ñ"}})  # control: texto bien codificado se firma


def _servir(tmp_path: Path, fm: Firmador) -> Iterator[Path]:
    d = tmp_path / "s"
    d.mkdir(mode=0o700)
    sock = d / "f.sock"
    srv = crear_servidor(fm, sock, frozenset({os.getuid()}))
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    try:
        yield sock
    finally:
        srv.shutdown()
        srv.server_close()
        hilo.join(3)


def _linea_cruda(sock: Path, datos: bytes) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(str(sock))
        s.sendall(datos + b"\n")
        buf = b""
        while not buf.endswith(b"\n"):
            t = s.recv(65536)
            if not t:
                break
            buf += t
    return json.loads(buf) if buf else {"sin_respuesta": True}


def test_b2_el_servidor_responde_y_sigue_vivo_ante_surrogates_json_profundo_y_fallos_internos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fm, log = _firmador(tmp_path)
    for sock in _servir(tmp_path, fm):
        surrogate = json.dumps({**PET, "argumentos": {"texto": "\ud800"}}).encode()  # ensure_ascii => \ud800 escapado
        assert _linea_cruda(sock, surrogate) == {"ok": False, "motivo": "campo_invalido"}
        profundo = b'{"tarea":' + b"[" * 8000 + b"]" * 8000 + b"}"
        assert _linea_cruda(sock, profundo) == {"ok": False, "motivo": "sobre_malformado"}
        assert _linea_cruda(sock, b"\xff\xfe no es utf8") == {"ok": False, "motivo": "sobre_malformado"}
        real = fm.firmar
        monkeypatch.setattr(fm, "firmar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        assert _linea_cruda(sock, json.dumps(PET).encode()) == {"ok": False, "motivo": "error_interno"}
        monkeypatch.setattr(fm, "firmar", real)
        assert pedir_firma(sock, PET)["ok"] is True  # control: el servidor sigue atendiendo tras todo lo anterior
    tipos = [x["tipo"] for x in _log(log)]
    assert tipos.count("rechazo") == 1 and tipos.count("fallo") >= 3 and tipos.count("firma") == 1
    assert any(x.get("causa") == "RuntimeError" for x in _log(log))
    verificar_cadena_log(log)  # y el log sigue siendo una cadena íntegra


# --- B-3: tasa -----------------------------------------------------------------------------------------------------


def test_b3_limite_de_tasa_con_ventana_rechaza_y_registra(tmp_path: Path) -> None:
    reloj = Reloj(1000.0)
    fm, log = _firmador(tmp_path, reloj, tasa_max=3, tasa_ventana_s=10.0)
    for _ in range(3):
        fm.firmar(PET)
    with pytest.raises(RechazoOrden) as e:
        fm.firmar(PET)
    assert e.value.motivo is Motivo.TASA_EXCEDIDA
    assert _log(log)[-1]["tipo"] == "rechazo" and _log(log)[-1]["motivo"] == "tasa_excedida"
    reloj.t = 1009.9
    with pytest.raises(RechazoOrden):
        fm.firmar(PET)  # aún dentro de la ventana
    reloj.t = 1010.0
    assert fm.firmar(PET)  # control: la ventana se desliza y vuelve a firmar
    assert [x["tipo"] for x in _log(log)].count("firma") == 4


def test_b3_los_rechazos_de_politica_no_consumen_cupo_de_tasa(tmp_path: Path) -> None:
    fm, _ = _firmador(tmp_path, tasa_max=2, tasa_ventana_s=60.0)
    for _ in range(5):
        with pytest.raises(RechazoOrden) as e:
            fm.firmar({**PET, "capacidad": "ejecutar_comando"})
        assert e.value.motivo is Motivo.CAPACIDAD_NO_REGISTRADA
    assert fm.firmar(PET) and fm.firmar(PET)  # el cupo estaba intacto


def test_b3_tasa_invalida_se_rechaza_al_construir(tmp_path: Path) -> None:
    for malo in ({"tasa_max": 0}, {"tasa_max": -1}, {"tasa_ventana_s": 0.0}, {"tasa_ventana_s": -5.0}):
        with pytest.raises(ValueError):
            _firmador(tmp_path, **malo)
    _firmador(tmp_path, tasa_max=1, tasa_ventana_s=0.5)  # control


# --- B-3: epoch monótono persistido --------------------------------------------------------------------------------


def _epoch_en(sobre: bytes, firmador_pub: Any) -> int:
    return int(verificar_y_leer(sobre, DOMINIO_ORDEN, verificador_de({"hc1-k1": firmador_pub}))[1]["epoch_hc1"])


def _epochs(log: Path) -> list[int]:
    return [json.loads(x)["epoch"] for x in (log.parent / "epoch.jsonl").read_text().splitlines()]


def test_b3_el_epoch_sube_en_cada_arranque_y_se_persiste(tmp_path: Path) -> None:
    fm1, log = _firmador(tmp_path, epoch=7)
    assert fm1.epoch == 7  # primer arranque: el configurado
    assert _epochs(log) == [7]
    sobre, _ = fm1.firmar(PET)
    assert _epoch_en(sobre, fm1._firmante.publica()) == 7
    fm2, _ = _firmador(tmp_path, epoch=7)  # mismo config, reinicio
    assert fm2.epoch == 8 and _epochs(log) == [7, 8]
    fm3, _ = _firmador(tmp_path, epoch=20)  # configurado MAYOR que último+1: se respeta
    assert fm3.epoch == 20
    sobre3, _ = fm3.firmar(PET)
    assert _epoch_en(sobre3, fm3._firmante.publica()) == 20


def test_b3_arrancar_con_un_epoch_menor_que_el_ultimo_se_niega(tmp_path: Path) -> None:
    _firmador(tmp_path, epoch=9)
    with pytest.raises(ErrorFirmador, match="menor"):
        _firmador(tmp_path, epoch=8)
    assert _epochs(tmp_path / "f" / "log.jsonl") == [9]  # no se retrocede ni se registra el intento
    assert _firmador(tmp_path, epoch=9)[0].epoch == 10  # control: igual al último sí arranca (y sube)


@pytest.mark.parametrize(
    "contenido", ["no json\n", "[]\n", '{"epoch": "7"}\n', '{"epoch": -1}\n', '{"epoch": true}\n', "{}\n"]
)
def test_b3_fichero_de_epoch_ilegible_falla_cerrado(tmp_path: Path, contenido: str) -> None:
    _firmador(tmp_path, epoch=3)
    (tmp_path / "f" / "epoch.jsonl").write_text(contenido)
    with pytest.raises(ErrorFirmador, match="ilegible"):
        _firmador(tmp_path, epoch=3)


def test_b3_el_epoch_se_persiste_con_fsync_de_fichero_y_directorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    espia = _EspiaFsync(monkeypatch)
    _firmador(tmp_path, epoch=1)
    assert espia.ficheros >= 1 and (tmp_path / "f").stat().st_ino in espia.directorios


# --- B-5: log encadenado ------------------------------------------------------------------------------------------


def test_b5_el_log_esta_encadenado_por_hash_y_se_verifica(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path)
    assert verificar_cadena_log(log) == (0, CADENA_INICIAL)  # log inexistente: cadena vacía válida
    fm.firmar(PET)
    with pytest.raises(RechazoOrden):
        fm.firmar({**PET, "capacidad": "x"})
    fm.firmar({**PET, "tarea": "t-2"})
    entradas = _log(log)
    assert entradas[0]["prev"] == CADENA_INICIAL and len({e["prev"] for e in entradas}) == 3
    n, ultimo = verificar_cadena_log(log)
    assert n == 3 and ultimo != CADENA_INICIAL
    fm2, _ = _firmador(tmp_path, epoch=7)  # un reinicio CONTINÚA la cadena
    fm2.firmar(PET)
    assert verificar_cadena_log(log)[0] == 4


def _manipular(log: Path, operacion: str) -> None:
    lineas = log.read_text().splitlines()
    if operacion == "editar":
        o = json.loads(lineas[1])
        o["motivo"] = "otro"
        lineas[1] = json.dumps(o, sort_keys=True, separators=(",", ":"))
    elif operacion == "borrar":
        del lineas[1]
    elif operacion == "intercalar":
        lineas.insert(1, lineas[0])
    elif operacion == "reordenar":
        lineas[1], lineas[2] = lineas[2], lineas[1]
    log.write_text("\n".join(lineas) + "\n")


@pytest.mark.parametrize("operacion", ["editar", "borrar", "intercalar", "reordenar"])
def test_b5_editar_borrar_intercalar_o_reordenar_una_entrada_rompe_la_cadena(tmp_path: Path, operacion: str) -> None:
    fm, log = _firmador(tmp_path)
    fm.firmar(PET)
    fm.firmar({**PET, "tarea": "t-2"})
    fm.firmar({**PET, "tarea": "t-3"})
    verificar_cadena_log(log)  # control: antes de tocar, íntegra
    _manipular(log, operacion)
    with pytest.raises(ErrorFirmador, match="cadena"):
        verificar_cadena_log(log)
    with pytest.raises(ErrorFirmador):
        _firmador(tmp_path, epoch=7)  # y un firmador NO arranca sobre un log roto


def test_b5_un_log_truncado_o_sin_cadena_falla_cerrado(tmp_path: Path) -> None:
    fm, log = _firmador(tmp_path)
    fm.firmar(PET)
    with open(log, "ab") as f:
        f.write(b'{"tipo":"firma","pre')
    with pytest.raises(ErrorFirmador, match="truncado"):
        verificar_cadena_log(log)
    log.write_text('{"tipo":"firma"}\n')  # formato anterior: sin `prev`
    with pytest.raises(ErrorFirmador, match="cadena"):
        verificar_cadena_log(log)


# --- B-5: crear_servidor -------------------------------------------------------------------------------------------


def _dir(tmp_path: Path, nombre: str = "d") -> Path:
    d = tmp_path / nombre
    d.mkdir(mode=0o700)
    return d


def test_b5_un_socket_propio_y_muerto_falla_cerrado_sin_borrarlo(tmp_path: Path) -> None:
    fm, _ = _firmador(tmp_path)
    ruta = _dir(tmp_path) / "f.sock"
    viejo = socket.socket(socket.AF_UNIX)
    viejo.bind(str(ruta))
    viejo.close()  # resto de un arranque anterior: existe el nodo del sistema de ficheros, nadie escucha
    assert stat.S_ISSOCK(os.lstat(ruta).st_mode)
    with pytest.raises(ErrorClave, match="residual"):
        crear_servidor(fm, ruta, frozenset({os.getuid()}))  # G-1: este módulo no borra; hay que retirarlo a mano
    assert stat.S_ISSOCK(os.lstat(ruta).st_mode)  # intacto
    os.unlink(ruta)  # el operador lo retira...
    srv = crear_servidor(fm, ruta, frozenset({os.getuid()}))  # ...y entonces sí se crea, 0600
    try:
        assert stat.S_IMODE(os.lstat(ruta).st_mode) == 0o600
    finally:
        srv.server_close()


def test_b5_nunca_se_toca_un_fichero_enlace_o_socket_vivo_que_ocupa_la_ruta(tmp_path: Path) -> None:
    fm, _ = _firmador(tmp_path)
    d = _dir(tmp_path)
    fichero = d / "f.sock"
    fichero.write_text("datos importantes")
    with pytest.raises(ErrorClave, match="no es un socket propio"):
        crear_servidor(fm, fichero, frozenset({os.getuid()}))
    assert fichero.read_text() == "datos importantes"  # intacto
    objetivo = d / "objetivo"
    objetivo.write_text("no me borres")
    enlace = d / "enlace.sock"
    enlace.symlink_to(objetivo)
    with pytest.raises(ErrorClave, match="no es un socket propio"):
        crear_servidor(fm, enlace, frozenset({os.getuid()}))
    assert enlace.is_symlink() and objetivo.read_text() == "no me borres"
    vivo = crear_servidor(fm, d / "vivo.sock", frozenset({os.getuid()}))
    hilo = threading.Thread(target=vivo.serve_forever, daemon=True)
    hilo.start()
    try:
        with pytest.raises(ErrorClave, match="ya hay"):
            crear_servidor(fm, d / "vivo.sock", frozenset({os.getuid()}))
        assert pedir_firma(d / "vivo.sock", PET)["ok"] is True  # el vivo no se vio afectado
    finally:
        vivo.shutdown()
        vivo.server_close()
        hilo.join(3)


def test_b5_directorio_del_socket_abierto_o_ajeno_falla_cerrado(tmp_path: Path) -> None:
    fm, _ = _firmador(tmp_path)
    abierto = tmp_path / "abierto"
    abierto.mkdir()
    os.chmod(abierto, 0o755)
    with pytest.raises(ErrorClave):
        crear_servidor(fm, abierto / "f.sock", frozenset({os.getuid()}))
    srv = crear_servidor(fm, _dir(tmp_path, "ok") / "f.sock", frozenset({os.getuid()}))  # control
    srv.server_close()
