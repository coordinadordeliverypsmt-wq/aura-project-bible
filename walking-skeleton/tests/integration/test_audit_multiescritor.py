"""Audit log con VARIOS escritores (DP-RESIDENCIA-MEDICION-CM2, Fase 1; R1-R5 y adicionales).

Antes de esta fase dos procesos sobre el mismo audit colisionaban en `seq` (cada uno llevaba su contador
en memoria), una cola truncada destruia el evento siguiente y un corte entre renombrar y anotar el
manifiesto dejaba un segmento huerfano. Aqui los escritores son procesos REALES (subprocess), no hilos:
el cerrojo es entre procesos y un hilo no lo ejercita igual.

Cada prueba lleva su caso de control (el mismo escenario sin la condicion que lo rompe), para que una
asercion que nunca pudiera fallar no pase por decorativa. Todos los datos viven en `tmp_path`.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.observability import AuditLog

RAIZ_SKELETON = Path(__file__).resolve().parents[2]

# Escritor hijo: espera la senal de salida (barrera) y anexa N registros. Un proceso nuevo por escritor.
_ESCRITOR = """
import os, sys, time
from aura_skeleton.observability import AuditLog
ruta, n, barrera, umbral, etiqueta = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
a = AuditLog(ruta, umbral_bytes=umbral or None)
open(barrera + ".listo-" + etiqueta, "w").close()
while not os.path.exists(barrera):
    time.sleep(0.001)
for i in range(n):
    a.append({"level": "INFO", "module": "W", "msg": etiqueta + str(i), "trace_id": "-", "audit": True})
"""

# Retenedor hijo: toma el cerrojo (modo dado), avisa y espera a que lo maten.
_RETENEDOR = """
import fcntl, os, sys, time
fd = os.open(sys.argv[1] + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX if sys.argv[2] == "EX" else fcntl.LOCK_SH)
print("listo", flush=True)
time.sleep(60)
"""


def _entorno() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RAIZ_SKELETON)
    env["TMPDIR"] = "/tmp"
    return env


def _lanzar_escritores(ruta: Path, etiquetas: list[str], n: int, umbral: int = 0) -> None:
    barrera = str(ruta) + ".go"
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _ESCRITOR, str(ruta), str(n), barrera, str(umbral), et],
            env=_entorno(),
            cwd=str(RAIZ_SKELETON),
        )
        for et in etiquetas
    ]
    limite = time.time() + 30
    while not all(os.path.exists(f"{barrera}.listo-{et}") for et in etiquetas):
        assert time.time() < limite, "los escritores no llegaron a la barrera"
        time.sleep(0.005)
    open(barrera, "w").close()  # salida simultanea
    for p in procs:
        assert p.wait(timeout=240) == 0


def _retener(ruta: Path, modo: str) -> subprocess.Popen:
    p = subprocess.Popen(
        [sys.executable, "-c", _RETENEDOR, str(ruta), modo],
        env=_entorno(),
        stdout=subprocess.PIPE,
        text=True,
    )
    assert p.stdout is not None
    assert p.stdout.readline().strip() == "listo"
    return p


def _rec(msg: str = "x") -> dict:
    return {"level": "INFO", "module": "T", "msg": msg, "trace_id": "-", "audit": True}


def _seqs(a: AuditLog) -> list[int]:
    return [r["seq"] for r in a.reconstruir()]


# --- R1 ----------------------------------------------------------------------------------------


def test_r1_control_un_proceso_600_appends_son_contiguos(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    _lanzar_escritores(ruta, ["a"], 600)
    assert _seqs(AuditLog(str(ruta))) == list(range(1, 601))


def test_r1_dos_procesos_300_appends_cada_uno_sin_colision_ni_perdida(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    _lanzar_escritores(ruta, ["a", "b"], 300)
    recs = AuditLog(str(ruta)).reconstruir()
    assert len(recs) == 600
    assert [r["seq"] for r in recs] == list(range(1, 601))
    assert {r["msg"] for r in recs} == {f"{e}{i}" for e in "ab" for i in range(300)}


# --- R2 ----------------------------------------------------------------------------------------


def test_r2_dos_procesos_con_rotacion_sin_perdida_y_segmentos_integros(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    _lanzar_escritores(ruta, ["a", "b"], 300, umbral=4000)
    a = AuditLog(str(ruta), umbral_bytes=4000)
    assert _seqs(a) == list(range(1, 601))
    segs = a.segmentos()
    assert len(segs) >= 5, "el umbral bajo debia forzar muchas rotaciones"
    assert all(a.verificar(s["segmento"]) for s in segs)


# --- R3 ----------------------------------------------------------------------------------------


def test_r3_control_sin_cola_truncada_no_hay_constancia(tmp_path: Path) -> None:
    a = AuditLog(str(tmp_path / "audit.jsonl"))
    a.append(_rec("uno"))
    a.append(_rec("dos"))
    assert not [r for r in a.reconstruir() if r.get("evento") == "audit.linea_parcial_cerrada"]


def test_r3_linea_parcial_se_cierra_sin_perder_el_evento_siguiente(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    parcial = b'{"level": "INFO", "module": "T", "msg": "trunc'
    ruta.write_bytes(parcial)  # sin "\n": un corte a mitad de escritura
    a = AuditLog(str(ruta))
    a.append(_rec("sobrevive"))
    recs = a.reconstruir()
    assert [r["msg"] for r in recs if r.get("msg") == "sobrevive"] == ["sobrevive"]
    constancias = [r for r in recs if r.get("evento") == "audit.linea_parcial_cerrada"]
    assert len(constancias) == 1 and constancias[0]["audit"] is True
    contenido = ruta.read_bytes()
    assert contenido.startswith(parcial + b"\n"), "append-only: los bytes parciales no se tocan"
    assert len(contenido) > len(parcial)
    seqs = [r["seq"] for r in recs]
    assert seqs == sorted(set(seqs))


# --- R4 ----------------------------------------------------------------------------------------


def test_r4_segmento_huerfano_se_reconcilia_y_sus_eventos_reaparecen(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    for i in range(3):
        a.append(_rec(f"e{i}"))
    nombre = "audit.jsonl.000000000001-000000000003"
    os.rename(ruta, tmp_path / nombre)  # corte entre renombrar y anotar el manifiesto
    assert not (tmp_path / "audit.jsonl.manifest").exists()

    b = AuditLog(str(ruta))
    recs = b.reconstruir()
    assert [r["msg"] for r in recs if r["msg"].startswith("e")] == ["e0", "e1", "e2"]
    constancias = [r for r in recs if r.get("evento") == "audit.segmento_reconciliado"]
    assert len(constancias) == 1 and constancias[0]["segmento"] == nombre
    entradas = [json.loads(x) for x in (tmp_path / "audit.jsonl.manifest").read_text().splitlines()]
    assert len(entradas) == 1
    e = entradas[0]
    assert set(e) == {"segmento", "sha256", "seq_ini", "seq_fin", "registros", "ts_sellado"}
    assert (e["segmento"], e["seq_ini"], e["seq_fin"], e["registros"]) == (nombre, 1, 3, 3)
    assert b.verificar(nombre)
    assert len(AuditLog(str(ruta)).segmentos()) == 1, "reconciliar es idempotente"


# --- R5 ----------------------------------------------------------------------------------------


def test_r5_escritura_parcial_lanza_error_no_consume_seq_y_cierra_la_cola(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    a.append(_rec("uno"))
    real_write = os.write

    def escritura_corta(fd: int, datos: bytes) -> int:
        real_write(fd, datos[: len(datos) // 2])  # de verdad queda media linea en disco
        return len(datos) - 1

    with monkeypatch.context() as m:
        m.setattr(obs.os, "write", escritura_corta)
        with pytest.raises(obs.ErrorEscrituraParcial):
            a.append(_rec("fallido"))
    a.append(_rec("dos"))  # sin parche
    recs = a.reconstruir()
    assert [r["msg"] for r in recs if r["msg"] in {"uno", "fallido", "dos"}] == ["uno", "dos"]
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1)), "sin hueco: el seq fallido se reutiliza"
    assert any(r.get("evento") == "audit.linea_parcial_cerrada" for r in recs)
    assert ruta.read_bytes().endswith(b"\n")


def test_r5_control_escritura_completa_no_lanza(tmp_path: Path) -> None:
    a = AuditLog(str(tmp_path / "audit.jsonl"))
    a.append(_rec("ok"))
    assert [r["seq"] for r in a.reconstruir()] == [1]


# --- Cerrojo: SIGKILL, espera acotada, modos -------------------------------------------------------


def test_cerrojo_se_libera_tras_sigkill_del_poseedor(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    p = _retener(ruta, "EX")
    p.send_signal(signal.SIGKILL)
    p.wait(timeout=10)
    t0 = time.time()
    a.append(_rec("tras-sigkill"))
    assert time.time() - t0 < 2.0
    assert [r["msg"] for r in a.reconstruir()] == ["tras-sigkill"]


@pytest.mark.parametrize("modo", ["EX", "SH"])
def test_espera_acotada_agotada_lanza_audit_bloqueado_y_no_escribe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modo: str
) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    monkeypatch.setattr(obs, "_ESPERA_CERROJO_S", 0.3)
    p = _retener(ruta, modo)
    try:
        t0 = time.time()
        with pytest.raises(obs.AuditBloqueado):
            a.append(_rec("bloqueado"))
        assert time.time() - t0 < 5.0
        assert not ruta.exists() or b"bloqueado" not in ruta.read_bytes()
    finally:
        p.kill()
        p.wait(timeout=10)
    a.append(_rec("libre"))  # control: sin retencion, entra
    assert [r["msg"] for r in a.reconstruir()] == ["libre"]


def test_lectores_esperan_a_un_escritor_y_fallan_en_voz_alta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    a.append(_rec("x"))
    monkeypatch.setattr(obs, "_ESPERA_CERROJO_S", 0.3)
    p = _retener(ruta, "EX")
    try:
        with pytest.raises(obs.AuditBloqueado):
            obs.leer_audit_desde(str(ruta), -1)
        with pytest.raises(obs.AuditBloqueado):
            a.segmentos()
    finally:
        p.kill()
        p.wait(timeout=10)
    assert len(obs.leer_audit_desde(str(ruta), -1)) == 1  # control


def test_lectores_comparten_el_cerrojo_entre_si(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    a.append(_rec("x"))
    monkeypatch.setattr(obs, "_ESPERA_CERROJO_S", 0.3)
    p = _retener(ruta, "SH")
    try:
        assert len(obs.leer_audit_desde(str(ruta), -1)) == 1
    finally:
        p.kill()
        p.wait(timeout=10)


def test_lector_sin_directorio_no_lo_crea(tmp_path: Path) -> None:
    ruta = tmp_path / "no-existe" / "audit.jsonl"
    assert obs.leer_audit_desde(str(ruta), -1) == []
    assert not (tmp_path / "no-existe").exists()


def test_el_cerrojo_existe_0600_y_nunca_desaparece_ni_cambia_de_inodo(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta), umbral_bytes=300)
    a.append(_rec("crea el lock"))  # el cerrojo nace en la primera escritura, no al construir
    lock = Path(str(ruta) + ".lock")
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600
    ino = lock.stat().st_ino
    for i in range(12):
        a.append(_rec(f"r{i}"))
    assert a.segmentos(), "debia haber rotado"
    assert lock.exists() and lock.stat().st_ino == ino
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600


# --- Rotacion: no se trunca nunca ---------------------------------------------------------------------


def test_tras_sellar_el_activo_no_existe_hasta_el_siguiente_append(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta), umbral_bytes=400)
    a.append(_rec("y" * 500))  # supera el umbral: se sella
    assert len(a.segmentos()) == 1
    assert not ruta.exists(), "sellar no recrea ni trunca el activo (O_CREAT en el siguiente append)"
    a.append(_rec("sig"))
    assert ruta.exists() and [r["seq"] for r in a.reconstruir()] == [1, 2]


def test_la_escritura_hace_fsync_del_fichero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a = AuditLog(str(tmp_path / "audit.jsonl"))
    a.append(_rec("crea"))
    llamadas: list[int] = []
    real = os.fsync
    monkeypatch.setattr(obs.os, "fsync", lambda fd: (llamadas.append(fd), real(fd))[1])
    a.append(_rec("existente"))  # el fichero ya existia: ni fsync de directorio ni de manifiesto
    assert len(llamadas) >= 1


def test_seq_se_recalcula_si_otro_escritor_escribio_entre_medias(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    b = AuditLog(str(ruta))
    a.append(_rec("a1"))
    b.append(_rec("b1"))
    a.append(_rec("a2"))  # la cache de `a` esta obsoleta: debe releer
    b.append(_rec("b2"))
    assert _seqs(a) == [1, 2, 3, 4]


# --- Compatibilidad con el formato de hoy -----------------------------------------------------------


def test_compatibilidad_con_audit_y_manifiesto_previos(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"

    def linea(seq: int, msg: str) -> str:
        return (
            json.dumps(
                {"level": "INFO", "module": "T", "msg": msg, "trace_id": "-", "audit": True, "ts": 1.0, "seq": seq}
            )
            + "\n"
        )

    nombre = "audit.jsonl.000000000001-000000000003"
    segmento = "".join(linea(i, f"s{i}") for i in (1, 2, 3))
    (tmp_path / nombre).write_text(segmento, encoding="utf-8")
    entrada = {
        "segmento": nombre,
        "sha256": hashlib.sha256(segmento.encode()).hexdigest(),
        "seq_ini": 1,
        "seq_fin": 3,
        "registros": 3,
        "ts_sellado": 1.0,
    }
    (tmp_path / "audit.jsonl.manifest").write_text(json.dumps(entrada) + "\n", encoding="utf-8")
    ruta.write_text(linea(4, "a4") + linea(5, "a5"), encoding="utf-8")

    a = AuditLog(str(ruta), umbral_bytes=400)
    assert _seqs(a) == [1, 2, 3, 4, 5]
    assert a.verificar(nombre)
    for i in range(6):
        a.append(_rec(f"n{i}"))
    assert _seqs(a) == list(range(1, 12))
    assert a.verificar(nombre)
    assert all(a.verificar(s["segmento"]) for s in a.segmentos())
    assert a.segmentos()[0] == entrada
    assert not [r for r in a.reconstruir() if r.get("evento", "").startswith("audit.")]


def test_flock_directo_confirma_que_el_cerrojo_es_el_fichero_lock(tmp_path: Path) -> None:
    """Control del metodo de las pruebas: quien toma el `.lock` por su cuenta SI bloquea al escritor."""
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    fd = os.open(str(ruta) + ".lock", os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with pytest.raises(obs.AuditBloqueado):
            old = obs._ESPERA_CERROJO_S
            obs._ESPERA_CERROJO_S = 0.2
            try:
                a.append(_rec("x"))
            finally:
                obs._ESPERA_CERROJO_S = old
    finally:
        os.close(fd)


# --- Sin efectos laterales hasta la primera escritura (decision del Director sobre el cerrojo perezoso) ---


def test_construir_y_leer_en_directorio_vacio_no_crea_ningun_fichero(tmp_path: Path) -> None:
    datos = tmp_path / "datos"
    datos.mkdir()
    a = AuditLog(str(datos / "audit.jsonl"))
    assert a.reconstruir() == [] and a.leer_desde(0) == [] and a.segmentos() == []
    assert not a.verificar("audit.jsonl.000000000001-000000000002")
    assert obs.leer_audit_desde(str(datos / "audit.jsonl"), -1) == []
    assert os.listdir(datos) == []
    a.append(_rec("primera"))  # control: la primera escritura SI crea el cerrojo
    assert sorted(os.listdir(datos)) == ["audit.jsonl", "audit.jsonl.lock"]


def test_los_lectores_no_crean_el_lock_aunque_haya_activo(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    ruta.write_text(json.dumps({"msg": "previo", "seq": 1}) + "\n", encoding="utf-8")
    a = AuditLog(str(ruta))
    assert [r["seq"] for r in a.reconstruir()] == [1]
    assert not Path(str(ruta) + ".lock").exists()


def test_construir_con_huerfano_si_reconcilia_y_crea_el_lock(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    nombre = "audit.jsonl.000000000001-000000000001"
    (tmp_path / nombre).write_text(json.dumps({"msg": "h", "seq": 1}) + "\n", encoding="utf-8")
    a = AuditLog(str(ruta))
    assert [s["segmento"] for s in a.segmentos()] == [nombre]
    assert Path(str(ruta) + ".lock").exists()


# --- Ronda de auditoria: huerfano con escritor vivo, symlinks, validacion, propagacion, fsync de directorio ---


def test_seq_no_se_reutiliza_si_un_huerfano_aparece_con_el_escritor_vivo(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta))
    for i in range(3):
        a.append(_rec(f"e{i}"))
    nombre = "audit.jsonl.000000000001-000000000003"
    os.rename(ruta, tmp_path / nombre)  # otro escritor murio entre renombrar y anotar
    a.append(_rec("nuevo"))  # MISMA instancia, cache invalida
    recs = AuditLog(str(ruta)).reconstruir()  # al construir se reconcilia el huerfano
    seqs = [r["seq"] for r in recs]
    assert len(seqs) == len(set(seqs)), "seq duplicado"
    nuevo = next(r for r in recs if r["msg"] == "nuevo")
    assert nuevo["seq"] > 3
    assert [r["msg"] for r in recs if r["msg"].startswith("e")] == ["e0", "e1", "e2"]


def test_control_sin_huerfano_el_seq_sigue_a_la_cache(tmp_path: Path) -> None:
    a = AuditLog(str(tmp_path / "audit.jsonl"))
    a.append(_rec("a"))
    a.append(_rec("b"))
    assert _seqs(a) == [1, 2]


def test_activo_symlink_no_se_escribe_a_traves_del_enlace(tmp_path: Path) -> None:
    destino = tmp_path / "destino.txt"
    destino.write_bytes(b"intacto\n")
    ruta = tmp_path / "audit.jsonl"
    os.symlink(destino, ruta)
    a = AuditLog(str(ruta))
    with pytest.raises(OSError):
        a.append(_rec("no debe llegar"))
    assert destino.read_bytes() == b"intacto\n"


def test_control_activo_normal_si_escribe(tmp_path: Path) -> None:
    a = AuditLog(str(tmp_path / "audit.jsonl"))
    a.append(_rec("ok"))
    assert len(a.reconstruir()) == 1


def test_lock_symlink_no_se_sigue_para_escribir(tmp_path: Path) -> None:
    destino = tmp_path / "otro"
    destino.write_bytes(b"")
    ruta = tmp_path / "audit.jsonl"
    os.symlink(destino, str(ruta) + ".lock")
    a = AuditLog(str(ruta))
    with pytest.raises(OSError):
        a.append(_rec("x"))
    assert not ruta.exists()
    assert obs.leer_audit_desde(str(ruta), -1) == []  # el lector no se cae: lee sin cerrojo


def _plantar(tmp_path: Path, nombre: str, seqs: list[int]) -> None:
    contenido = "".join(json.dumps({"msg": f"p{s}", "seq": s}) + "\n" for s in seqs)
    (tmp_path / nombre).write_text(contenido, encoding="utf-8")


def test_huerfano_con_rango_de_nombre_distinto_del_contenido_se_rechaza(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    falso = "audit.jsonl.000000000001-000000000999"
    _plantar(tmp_path, falso, [1, 2])
    a = AuditLog(str(ruta))
    assert a.segmentos() == []
    recs = a.reconstruir()
    rechazos = [r for r in recs if r.get("evento") == "audit.segmento_rechazado"]
    assert len(rechazos) == 1 and rechazos[0]["segmento"] == falso and rechazos[0]["motivo"]
    AuditLog(str(ruta))  # otro arranque: no se anota y no se acumula ruido sin limite razonable
    a.append(_rec("sigue"))
    assert max(r["seq"] for r in a.reconstruir()) < 999, "un nombre falso no empuja el seq"


def test_control_huerfano_valido_se_anota_con_constancia_completa(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    bueno = "audit.jsonl.000000000001-000000000002"
    _plantar(tmp_path, bueno, [1, 2])
    a = AuditLog(str(ruta))
    assert [s["segmento"] for s in a.segmentos()] == [bueno]
    (c,) = [r for r in a.reconstruir() if r.get("evento") == "audit.segmento_reconciliado"]
    assert (c["seq_ini"], c["seq_fin"]) == (1, 2) and c["sha256"] == a.segmentos()[0]["sha256"]


def test_huerfano_symlink_no_se_cuenta(tmp_path: Path) -> None:
    fuera = tmp_path / "fuera.txt"
    fuera.write_text(json.dumps({"msg": "x", "seq": 1}) + "\n", encoding="utf-8")
    os.symlink(fuera, tmp_path / "audit.jsonl.000000000001-000000000001")
    a = AuditLog(str(tmp_path / "audit.jsonl"))
    assert a.segmentos() == []


def test_cola_truncada_se_cierra_antes_de_la_constancia_de_reconciliacion(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    _plantar(tmp_path, "audit.jsonl.000000000001-000000000001", [1])
    ruta.write_bytes(b'{"msg": "parc')
    a = AuditLog(str(ruta))
    eventos = {r.get("evento") for r in a.reconstruir()}
    assert {"audit.segmento_reconciliado", "audit.linea_parcial_cerrada"} <= eventos


def test_audit_bloqueado_se_propaga_por_log_y_no_escribe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib

    @contextlib.contextmanager
    def siempre_bloqueado(*_a: object, **_k: object):
        raise obs.AuditBloqueado("forzado")
        yield  # pragma: no cover

    ruta = tmp_path / "audit.jsonl"
    obs.configure_audit(str(ruta))
    try:
        monkeypatch.setattr(obs, "_cerrojo", siempre_bloqueado)
        with pytest.raises(obs.AuditBloqueado):
            obs.log("INFO", "T", "x", audit=True)
    finally:
        obs.reset_audit()
    assert os.listdir(tmp_path) == []


def _fsyncs_de_directorio(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    es_dir: list[bool] = []
    real = os.fsync

    def espia(fd: int) -> None:
        es_dir.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        real(fd)

    monkeypatch.setattr(obs.os, "fsync", espia)
    return es_dir


def test_fsync_de_directorio_al_crear_el_activo_y_tras_sellar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a = AuditLog(str(tmp_path / "audit.jsonl"), umbral_bytes=600)
    es_dir = _fsyncs_de_directorio(monkeypatch)
    a.append(_rec("crea"))
    assert es_dir.count(True) == 1, "crear el activo sincroniza el directorio"
    es_dir.clear()
    a.append(_rec("sin dir"))
    assert es_dir.count(True) == 0 and es_dir.count(False) >= 1, "control: un append normal no toca el directorio"
    es_dir.clear()
    a.append(_rec("z" * 700))  # supera el umbral: sella
    assert a.segmentos() and es_dir.count(True) == 1, "sellar sincroniza el directorio"
