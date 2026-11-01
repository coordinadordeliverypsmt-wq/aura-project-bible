"""G-1 · R-B · escrituras de BAJO NIVEL (DN-1, 2026-10-27).

Hasta DN-1, F2 solo veía `open(..., "w")`, `Path.write_*` y `os.replace/remove/...`. Quien escribía con
`os.open(...)` + `os.write(...)` esquivaba R-B por completo. Estas pruebas fijan lo que F2 ve ahora y,
con el mismo peso, lo que NO debe acusar: una regla que acusa lecturas es ruido y se acaba apagando.

Se ejercita sobre código sintético en `tmp_path` (fuera de `aura_skeleton/`, sin exclusiones).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

# Importacion dura, no `importorskip`: si el verificador falta, esto debe FALLAR.
import verificador_g1 as verificador  # noqa: E402, I001


def _rb(tmp_path, fuente: str):
    """Hallazgos R-B de un snippet, con `autorizado_para` vacío y una ruta sin exclusiones."""
    f = tmp_path / "modulo_bajo_nivel.py"
    f.write_text(fuente, encoding="utf-8")
    return [h for h in verificador.analizar_fichero(f, frozenset()) if h.regla == "R-B"]


def _operaciones(tmp_path, fuente: str) -> list[str]:
    return [h.operacion for h in _rb(tmp_path, fuente)]


# ------------------------------------------------------------ NEGATIVAS (acusan) --


@pytest.mark.parametrize(
    ("fuente", "operacion"),
    [
        ("import os\nos.open(p, os.O_WRONLY | os.O_CREAT)\n", "os.open"),
        ("import os\nos.open(p, os.O_RDWR | os.O_APPEND, 0o600)\n", "os.open"),
        ("import os\nos.open(p, flags=os.O_TRUNC)\n", "os.open"),
        ("import os\nos.open(p, os.O_RDONLY | os.O_CREAT)\n", "os.open"),
        ("import os\nbanderas = calcular()\nos.open(p, banderas)\n", "os.open"),  # fail-closed
        ("import os\nos.open(p, os.O_RDONLY | calcular())\n", "os.open"),  # fail-closed
        ("import os\nos.open(p)\n", "os.open"),  # sin flags: no demostrable, se acusa
        ("import os\nos.write(fd, b'x')\n", "os.write"),
        ("import os\nos.ftruncate(fd, 0)\n", "os.ftruncate"),
        ("import os\nos.truncate(p, 0)\n", "os.truncate"),
        ("import os\nos.pwrite(fd, b'x', 0)\n", "os.pwrite"),
        ("import os\nos.writev(fd, [b'x'])\n", "os.writev"),
        ("import os\nos.fdopen(fd, 'wb')\n", "os.fdopen"),
        ("import os\nos.fdopen(fd, 'a')\n", "os.fdopen"),
        ("import os\nos.fdopen(fd, mode='r+')\n", "os.fdopen"),
        ("import tempfile\ntempfile.mkstemp()\n", "tempfile.mkstemp"),
        ("import tempfile\ntempfile.mkdtemp()\n", "tempfile.mkdtemp"),
        ("import tempfile\ntempfile.NamedTemporaryFile(delete=False)\n", "tempfile.NamedTemporaryFile"),
        ("import wave\nwave.open(r, 'wb')\n", "wave.open"),
        ("import wave\nwave.open(r, mode='w')\n", "wave.open"),
        ("import os as o\no.write(fd, b'')\n", "os.write"),
        ("from os import write\nwrite(fd, b'')\n", "os.write"),
        ("from os import ftruncate as t\nt(fd, 0)\n", "os.ftruncate"),
        ("from os import open as abrir\nabrir(p, 1 | 64)\n", "os.open"),
    ],
)
def test_escritura_de_bajo_nivel_se_acusa_con_R_B_y_la_operacion_exacta(tmp_path, fuente, operacion):
    hallazgos = _rb(tmp_path, fuente)
    assert [(h.regla, h.operacion) for h in hallazgos] == [("R-B", operacion)], hallazgos


# ------------------------------------------------------------ POSITIVAS (no acusan) --


@pytest.mark.parametrize(
    "fuente",
    [
        "import os\nos.open(d, os.O_RDONLY | os.O_DIRECTORY)\n",
        "import os\nos.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)\n",
        "import os\nos.open(p, os.O_RDONLY | os.O_CLOEXEC)\n",
        "import os\nos.fdopen(fd, 'rb')\n",
        "import os\nos.fdopen(fd)\n",
        "import os\nos.fdopen(fd, modo)\n",  # modo no literal: se calla, como `open`
        "import wave\nwave.open(r)\n",
        "import wave\nwave.open(r, 'rb')\n",
        "f.write(x)\n",
        "texto.replace('a', 'b')\n",
        "import dataclasses\ndataclasses.replace(o, x=1)\n",
        "import shutil\nshutil.which('x')\n",
        "import os\nos.chmod(p, 0o600)\n",
        "import os\nos.makedirs(d)\n",
        "import os as _os\n_os.environ.get('X')\n",
        "import tempfile\ntempfile.NamedTemporaryFile()\n",
        "import tempfile\ntempfile.NamedTemporaryFile(delete=True)\n",
        "import tempfile\ntempfile.gettempdir()\n",
        "import os\nos.read(fd, 10)\n",
        "otro.write(fd, b'x')\n",  # `write` sin receptor `os`
        "def write(fd, b):\n    pass\nwrite(1, b'')\n",  # nombre propio, no `from os import`
    ],
)
def test_lo_que_no_escribe_no_se_acusa(tmp_path, fuente):
    assert _rb(tmp_path, fuente) == []


# -------------------------------------------- no colisión con el builtin `open` --


def test_una_exclusion_del_builtin_open_NO_exime_os_open(tmp_path, monkeypatch):
    """`core/decisiones.py` y `conectores/auditoria.py` excluyen `open` (builtin). Eso no puede
    cubrir `os.open`: son operaciones distintas con nombres distintos.

    Mecanismo: fuera de `RAIZ`, `_rel` devuelve la ruta absoluta; se sustituye la tabla de exclusiones
    por una que declara `open` para ESE fichero. Es la misma consulta que hace `analizar_fichero`."""
    f = tmp_path / "con_exclusion_open.py"
    f.write_text(
        "import os\nwith open(a, 'w') as g:\n    g.write('x')\nfd = os.open(p, os.O_WRONLY)\n", encoding="utf-8"
    )
    monkeypatch.setattr(verificador, "_excluidos_por_operacion", lambda: {str(f): {"open"}})
    ops = [h.operacion for h in verificador.analizar_fichero(f, frozenset()) if h.regla == "R-B"]
    assert ops == ["os.open"]  # el builtin sigue eximido; os.open sigue acusado


def test_una_exclusion_de_os_open_NO_exime_el_builtin_open(tmp_path, monkeypatch):
    f = tmp_path / "con_exclusion_os_open.py"
    f.write_text("import os\nopen(a, 'w')\nos.open(p, os.O_WRONLY)\n", encoding="utf-8")
    monkeypatch.setattr(verificador, "_excluidos_por_operacion", lambda: {str(f): {"os.open"}})
    ops = [h.operacion for h in verificador.analizar_fichero(f, frozenset()) if h.regla == "R-B"]
    assert ops == ["open"]


def test_la_exclusion_por_operacion_exime_la_operacion_de_bajo_nivel_declarada(tmp_path, monkeypatch):
    f = tmp_path / "declara_os_write.py"
    f.write_text("import os\nos.write(fd, b'')\nos.ftruncate(fd, 0)\n", encoding="utf-8")
    monkeypatch.setattr(verificador, "_excluidos_por_operacion", lambda: {str(f): {"os.write"}})
    ops = [h.operacion for h in verificador.analizar_fichero(f, frozenset()) if h.regla == "R-B"]
    assert ops == ["os.ftruncate"]
