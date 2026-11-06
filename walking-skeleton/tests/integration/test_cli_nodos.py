"""CLI `--nodos` y `--receptor-nodos` ejecutados como subproceso real (sin red)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from aura_skeleton.core.nodos import RegistroNodos, construir_latido, validar_latido

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ID_A = "c" * 32


def _ejecutar(args, red, extra_env=None):
    env = {**os.environ, "AURA_RED": str(red), "PYTHONPATH": RAIZ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "-m", "aura_skeleton", *args], capture_output=True, text=True, env=env, cwd=RAIZ, timeout=60
    )


def _escribir_registro(red, receptor_latido):
    reg = RegistroNodos()
    ahora = time.time()
    latido = validar_latido(
        construir_latido(ID_A, "nodo-cli", 1, "d" * 32, 10.0, {"ram_mb": 986.0, "nucleos": 2.0}, [], "1.0")
    )
    reg.registrar(latido, ahora - 2)
    datos = {"receptor": {"latido": receptor_latido, "pid": 1}, **reg.a_dict()}
    (red / "nodos").mkdir(parents=True)
    (red / "nodos" / "registro.json").write_text(json.dumps(datos), encoding="utf-8")


def test_nodos_muestra_estado_y_nombre(tmp_path):
    _escribir_registro(tmp_path, time.time() - 1)
    r = _ejecutar(["--nodos"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "AURA — nodos y sobres de capacidad" in r.stdout
    assert "receptor de nodos: VIVO" in r.stdout
    assert f"nodo-cli [{ID_A[:8]}…]  ONLINE" in r.stdout
    assert "memoria=DEGRADADA" in r.stdout


def test_nodos_con_receptor_caido_dice_unknown(tmp_path):
    _escribir_registro(tmp_path, time.time() - 3600)
    r = _ejecutar(["--nodos"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "NO ESCUCHA" in r.stdout and "UNKNOWN" in r.stdout


def test_nodos_sin_registro_no_crea_nada(tmp_path):
    red = tmp_path / "red"
    r = _ejecutar(["--nodos"], red)
    assert r.returncode == 0, r.stderr
    assert "ningún nodo registrado" in r.stdout
    assert not red.exists()


def test_receptor_sin_credencial_sale_con_error_claro(tmp_path):
    r = _ejecutar(["--receptor-nodos"], tmp_path)
    assert r.returncode != 0
    assert "receptor.credencial" in r.stderr
    assert "Traceback" not in r.stderr


def test_receptor_con_credencial_legible_por_otros_se_rechaza(tmp_path):
    cred = tmp_path / "receptor.credencial"
    cred.write_text("secreto-xyz", encoding="utf-8")
    cred.chmod(0o644)
    r = _ejecutar(["--receptor-nodos"], tmp_path)
    assert r.returncode != 0
    assert "permisos" in r.stderr and "Traceback" not in r.stderr
    assert "secreto-xyz" not in r.stderr + r.stdout


def test_receptor_sin_ca_sale_con_error_claro(tmp_path):
    cred = tmp_path / "receptor.credencial"
    cred.write_text("secreto-xyz", encoding="utf-8")
    cred.chmod(0o600)
    r = _ejecutar(["--receptor-nodos"], tmp_path)
    assert r.returncode != 0
    assert "ca.crt" in r.stderr and "Traceback" not in r.stderr


def test_nodos_con_registro_corrupto_falla_con_mensaje_claro_y_sin_traza(tmp_path):
    (tmp_path / "nodos").mkdir()
    (tmp_path / "nodos" / "registro.json").write_text("{no es json", encoding="utf-8")
    r = _ejecutar(["--nodos"], tmp_path)
    assert r.returncode == 1
    assert "no puedo leer el registro de nodos" in r.stderr and "Traceback" not in r.stderr
    assert r.stdout == ""
