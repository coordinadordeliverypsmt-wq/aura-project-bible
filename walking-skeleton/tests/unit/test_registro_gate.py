"""Registro estructurado del Quality Gate (AURA Progress Dashboard, 2026-10-22).

Antes el gate solo escribía en pantalla: su resultado vivía en la prosa del CHECKPOINT y ningún panel podía mostrarlo sin
que alguien lo copiara a mano. Ahora, al terminar, deja UN fichero JSON (fuera del repo, en el estado local del usuario)
con la fecha, el sha, el resultado por paso y los conteos de pytest. El registro es una proyección: si falla, el gate NO
cambia su resultado.
"""

from __future__ import annotations

import json
import os

from herramientas import registro_gate as rg

_RESUMEN = "== 3560 passed, 1 skipped, 17 xfailed in 514.37s (0:08:34) =="


def test_lee_los_conteos_de_la_linea_resumen_de_pytest():
    texto = "....\n.....\n" + _RESUMEN + "\n"
    assert rg.conteos_pytest(texto) == {"passed": 3560, "failed": 0, "skipped": 1, "xfailed": 17, "errors": 0}


def test_con_fallos_y_errores_tambien_los_cuenta():
    texto = "FAILED tests/x.py::t\n== 2 failed, 10 passed, 1 error in 3.1s =="
    assert rg.conteos_pytest(texto) == {"passed": 10, "failed": 2, "skipped": 0, "xfailed": 0, "errors": 1}


def test_sin_linea_resumen_no_inventa_conteos():
    assert rg.conteos_pytest("se colgó a mitad\n") is None


def test_el_resultado_es_PASS_solo_si_todos_los_pasos_son_OK():
    ok = {"formato": "OK", "lint": "OK", "tipado": "OK", "pruebas": "OK", "contratos": "OK"}
    assert rg.resultado(ok) == "PASS"
    assert rg.resultado({**ok, "lint": "FAIL"}) == "FAIL"
    assert rg.resultado({**ok, "pruebas": "?"}) == "FAIL", "un paso desconocido no puede dar PASS"
    assert rg.resultado({"formato": "OK"}) == "FAIL", "faltan pasos: no es un PASS completo"


def test_registrar_escribe_atomico_con_fecha_sha_pasos_y_conteos(tmp_path):
    destino = tmp_path / "estado" / "quality-gate-ultimo.json"
    pasos = {"formato": "OK", "lint": "OK", "tipado": "OK", "pruebas": "OK", "contratos": "OK"}

    rg.registrar(destino, pasos, _RESUMEN, sha="abc1234", cambios_sin_commit=3, fecha="2026-10-22T13:00:00-05:00")

    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["resultado"] == "PASS" and datos["sha"] == "abc1234" and datos["cambios_sin_commit"] == 3
    assert datos["pytest"]["passed"] == 3560 and datos["pasos"] == pasos and datos["fecha"].startswith("2026-10-22")
    assert not list(destino.parent.glob("*.tmp")), "quedó un temporal"


def test_si_la_escritura_falla_el_registro_anterior_queda_intacto(tmp_path, monkeypatch):
    destino = tmp_path / "quality-gate-ultimo.json"
    destino.write_text('{"resultado": "PASS"}', encoding="utf-8")

    def falla(*a, **k):
        raise OSError("disco lleno")

    monkeypatch.setattr(rg.os, "replace", falla)
    try:
        rg.registrar(destino, {"formato": "FAIL"}, "", sha="x", cambios_sin_commit=0, fecha="f")
    except OSError:
        pass
    assert json.loads(destino.read_text(encoding="utf-8")) == {"resultado": "PASS"}


def test_la_cli_nunca_falla_aunque_no_pueda_escribir(tmp_path, capsys):
    """El registro es accesorio: un error suyo no puede tumbar ni cambiar el resultado del gate."""
    salida = tmp_path / "pytest.txt"
    salida.write_text(_RESUMEN, encoding="utf-8")
    bloqueado = tmp_path / "no_es_dir"
    bloqueado.write_text("soy un fichero", encoding="utf-8")

    codigo = rg.main(["--destino", str(bloqueado / "x.json"), "--pytest-salida", str(salida), "--paso", "formato=OK"])

    assert codigo == 0 and "no se pudo registrar" in capsys.readouterr().err


def test_conteos_solo_acepta_una_linea_resumen_real_de_pytest():
    assert rg.conteos_pytest("ran 5 tests in 3s, todo bien\n") is None  # rompe si basta con «in Ns»
    assert rg.conteos_pytest("tardo 2 passed cosas in 4.0s\n") is None
    assert rg.conteos_pytest("3560 passed, 1 skipped in 514.37s (0:08:34)\n")["passed"] == 3560  # forma -q (addopts)
    assert rg.conteos_pytest("== 3 passed, 1 warning in 1.00s ==\n")["passed"] == 3
    assert rg.conteos_pytest("== no tests ran in 0.01s ==\n") == dict.fromkeys(
        ("passed", "failed", "skipped", "xfailed", "errors"), 0
    )


def test_el_temporal_no_sigue_un_symlink_predecible(tmp_path):
    victima = tmp_path / "victima.txt"
    victima.write_text("intacto", encoding="utf-8")
    destino = tmp_path / "q.json"
    os.symlink(victima, tmp_path / "q.json.tmp")  # el nombre que usaba la version anterior
    rg.registrar(destino, {"formato": "OK"}, _RESUMEN, sha="abc", cambios_sin_commit=0, fecha="f")
    assert victima.read_text(encoding="utf-8") == "intacto"
    assert json.loads(destino.read_text(encoding="utf-8"))["sha"] == "abc"


def test_sha_vacio_se_registra_como_desconocido(tmp_path):
    destino = tmp_path / "q.json"
    rg.registrar(destino, {}, "", sha="", cambios_sin_commit=0, fecha="f")
    assert json.loads(destino.read_text(encoding="utf-8"))["sha"] == "desconocido"
    rg.registrar(destino, {}, "", sha="abc", cambios_sin_commit=0, fecha="f")
    assert json.loads(destino.read_text(encoding="utf-8"))["sha"] == "abc"  # control


def test_fallo_al_escribir_no_deja_temporales(tmp_path, monkeypatch):
    destino = tmp_path / "q.json"
    monkeypatch.setattr(rg.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    try:
        rg.registrar(destino, {}, "", sha="a", cambios_sin_commit=0, fecha="f")
    except OSError:
        pass
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_conteos_usa_la_ultima_linea_resumen():
    """R7: si hay dos resumenes (p. ej. una ejecucion previa en el log), valen los de la ULTIMA."""
    texto = "== 1 failed, 2 passed in 1.0s ==\nruido\n== 5 passed in 2.0s ==\n"
    assert rg.conteos_pytest(texto) == {"passed": 5, "failed": 0, "skipped": 0, "xfailed": 0, "errors": 0}
