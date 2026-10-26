"""RED: `observar_git` debe devolver RUTAS que existen, tambien con renombrados y nombres raros.

`git status --porcelain` escribe un renombrado como `R  viejo -> nuevo` y entrecomilla las rutas con
espacios o caracteres no ASCII. El recorte por posicion devolvia la linea entera como si fuera un
nombre: el handoff mandaba al siguiente agente a buscar `viejo -> nuevo`, un fichero que no existe.
Se vio el 2026-10-06 con el renombrado preparado de `arnes-validador-comandos.toml`.

Cada prueba usa un repositorio temporal propio: no depende del estado del worktree real.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import control_plane as cp  # noqa: E402


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "prueba@example.invalid")
    _git(repo, "config", "user.name", "prueba")
    (repo / "viejo.toml").write_text("a = 1\n")
    (repo / "intacto.txt").write_text("x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_un_renombrado_preparado_se_observa_como_la_ruta_NUEVA(tmp_path):
    repo = _repo(tmp_path)
    (repo / "retiradas").mkdir()
    _git(repo, "mv", "viejo.toml", "retiradas/viejo.toml")

    g = cp.observar_git(repo)

    assert g["ficheros_modificados"] == ["retiradas/viejo.toml"]
    assert g["limpio"] is False


def test_las_rutas_entrecomilladas_por_git_se_devuelven_tal_cual_existen(tmp_path):
    repo = _repo(tmp_path)
    (repo / "con espacio.md").write_text("x\n")
    (repo / "decisión.md").write_text("x\n")

    g = cp.observar_git(repo)

    assert sorted(g["ficheros_modificados"]) == ["con espacio.md", "decisión.md"]
    for nombre in g["ficheros_modificados"]:
        assert (repo / nombre).exists(), nombre


def test_control_las_rutas_normales_siguen_igual_y_el_arbol_limpio_es_limpio(tmp_path):
    repo = _repo(tmp_path)
    assert cp.observar_git(repo)["limpio"] is True
    assert cp.observar_git(repo)["ficheros_modificados"] == []

    (repo / "intacto.txt").write_text("cambiado\n")
    (repo / "nuevo.txt").write_text("n\n")
    g = cp.observar_git(repo)

    assert sorted(g["ficheros_modificados"]) == ["intacto.txt", "nuevo.txt"]
    assert g["limpio"] is False
