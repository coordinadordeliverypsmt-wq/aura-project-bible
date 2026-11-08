"""Empaquetado del agente de nodo (DP-NODO-01 §5): solo lo que el agente importa, y funciona AISLADO del repo."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aura_skeleton.core.nodos import validar_latido

_WS = Path(__file__).resolve().parents[2]
_SCRIPT = _WS.parent / "entorno" / "nodos" / "empaquetar_nodo.py"

# El script de arranque aislado: sin el repo ni el site-packages del usuario. Solo stdlib + DESTINO.
_ARRANQUE = """
import sys, os
destino = sys.argv[1]
sys.path[:] = [destino] + [p for p in sys.path if 'site-packages' not in p and 'dist-packages' not in p]
import aura_skeleton.nodo_agente as agente
import nats
assert agente.__file__.startswith(destino), agente.__file__
assert nats.__file__.startswith(destino), nats.__file__
sys.exit(agente.main(['--informe']))
"""


@pytest.fixture(scope="module")
def paquete(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destino = tmp_path_factory.mktemp("paquete") / "app"
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), str(_WS), str(destino)], capture_output=True, text=True, check=False
    )
    assert r.returncode == 0, r.stderr
    return destino


def _ficheros(paquete: Path) -> set[str]:
    return {p.relative_to(paquete).as_posix() for p in paquete.rglob("*") if p.is_file()}


def test_el_agente_corre_aislado_del_repo_y_produce_un_latido_valido(paquete: Path, tmp_path: Path) -> None:
    entorno = {"PATH": os.environ.get("PATH", ""), "AURA_NODO_DATOS": str(tmp_path / "datos")}
    r = subprocess.run(
        [sys.executable, "-I", "-B", "-c", _ARRANQUE, str(paquete)],
        cwd=tmp_path,
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert validar_latido(json.loads(r.stdout)).nombre == "sin-configurar"


def test_no_se_empaquetan_modulos_cognitivos(paquete: Path) -> None:
    nombres = {Path(f).stem for f in _ficheros(paquete)}
    for prohibido in ("orchestrator", "providers_real", "voice_real", "composicion", "memory", "__main__"):
        assert prohibido not in nombres, prohibido


def test_se_empaquetan_los_modulos_que_el_agente_necesita(paquete: Path) -> None:
    ficheros = _ficheros(paquete)
    for esperado in (
        "aura_skeleton/__init__.py",
        "aura_skeleton/nodo_agente.py",
        "aura_skeleton/bus_nats.py",
        "aura_skeleton/core/nodos.py",
        "aura_skeleton/adapters/identidad_nodo.py",
        "aura_skeleton/adapters/detector_hardware.py",
        "nats/__init__.py",
    ):
        assert esperado in ficheros, esperado


def test_sin_pycache_ni_ficheros_ajenos(paquete: Path) -> None:
    assert not [f for f in _ficheros(paquete) if "__pycache__" in f or f.endswith(".pyc")]
    assert not [f for f in _ficheros(paquete) if f.startswith("aura_skeleton/") and "test" in f]


def test_el_manifiesto_lista_cada_fichero_con_su_sha256(paquete: Path) -> None:
    lineas = (paquete / "MANIFIESTO.txt").read_text().splitlines()
    entradas = dict(reversed(linea.split("  ", 1)) for linea in lineas if linea and not linea.startswith("#"))
    assert set(entradas) == _ficheros(paquete) - {"MANIFIESTO.txt"}
    for ruta, huella in entradas.items():
        assert hashlib.sha256((paquete / ruta).read_bytes()).hexdigest() == huella, ruta


def test_el_paquete_es_reproducible(paquete: Path, tmp_path: Path) -> None:
    otro = tmp_path / "otro"
    subprocess.run([sys.executable, str(_SCRIPT), str(_WS), str(otro)], check=True, capture_output=True)
    assert (otro / "MANIFIESTO.txt").read_text() == (paquete / "MANIFIESTO.txt").read_text()
