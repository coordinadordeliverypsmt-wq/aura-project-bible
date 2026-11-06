"""Registro estructurado del Quality Gate: UN fichero JSON con el último resultado (AURA Progress Dashboard).

Antes `quality-gate.sh` solo escribía en pantalla: su resultado vivía en la prosa del CHECKPOINT y ningún panel podía
mostrarlo sin copiarlo a mano. Al terminar, el gate llama a este módulo y deja en el estado local del usuario —fuera de
cualquier worktree, para no ensuciar git ni el `pre-push` de `main`— la fecha, el sha, el resultado por paso y los
conteos de pytest.

PROYECCIÓN, NO AUTORIDAD. El resultado del gate es su código de salida; esto solo lo copia. Si el registro falla, el gate
no cambia: `main` devuelve siempre 0 y lo dice por stderr. Escritura atómica (temporal + `os.replace`), como
`centro_gobierno.publicar`, para que un corte no deje un registro a medias que un panel lea como completo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PASOS = ("formato", "lint", "tipado", "pruebas", "contratos")


def destino_por_defecto() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(base) / "aura" / "quality-gate-ultimo.json"


_TIPOS = r"(?:passed|failed|skipped|xfailed|xpassed|errors?|warnings?|deselected|rerun)"
# Una linea resumen REAL de pytest, entera: con «=» (modo normal) o sin ellos (`-q`, que es el addopts del
# proyecto): «3560 passed, 1 skipped in 514.37s (0:08:34)» / «no tests ran in 0.01s».
_RESUMEN_PYTEST = re.compile(
    rf"^[= ]*(?:(?:\d+ {_TIPOS}(?:, | and )?)+|no tests ran) in \d+(?:\.\d+)?s(?: \(\d+:\d{{2}}:\d{{2}}\))?[= ]*$"
)


def conteos_pytest(texto: str) -> dict[str, int] | None:
    """Los conteos de la ÚLTIMA línea resumen de pytest. Solo una línea que sea ENTERA un resumen (no basta con
    contener «in 3s»). Sin esa línea, None: no se inventan números de una ejecución que se cortó."""
    lineas = [linea.strip() for linea in texto.splitlines() if _RESUMEN_PYTEST.match(linea.strip())]
    if not lineas:
        return None
    conteos = dict.fromkeys(("passed", "failed", "skipped", "xfailed", "errors"), 0)
    for numero, clase in re.findall(rf"(\d+) ({_TIPOS})\b", lineas[-1]):
        if clase.startswith("error"):
            conteos["errors"] += int(numero)
        elif clase in conteos:
            conteos[clase] += int(numero)
    return conteos


def resultado(pasos: dict[str, str]) -> str:
    """PASS solo si LOS CINCO pasos están y son OK: un paso que falta o es desconocido no es un PASS completo."""
    return "PASS" if all(pasos.get(p) == "OK" for p in PASOS) else "FAIL"


def registrar(
    destino: Path, pasos: dict[str, str], salida_pytest: str, *, sha: str, cambios_sin_commit: int, fecha: str
) -> dict:
    datos = {
        "fecha": fecha,
        "sha": sha or "desconocido",
        "cambios_sin_commit": cambios_sin_commit,
        "resultado": resultado(pasos),
        "pasos": pasos,
        "pytest": conteos_pytest(salida_pytest),
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    # temporal de nombre impredecible en el MISMO directorio (os.replace atomico): no sigue un symlink plantado
    fd, nombre = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(datos, ensure_ascii=False, indent=1))
        os.replace(nombre, destino)
    finally:
        Path(nombre).unlink(missing_ok=True)
    return datos


def _git(*args: str) -> str:
    import subprocess

    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Registra el último resultado del Quality Gate (proyección).")
    ap.add_argument("--destino", type=Path, default=None)
    ap.add_argument("--pytest-salida", type=Path, default=None)
    ap.add_argument("--paso", action="append", default=[], help="nombre=OK|FAIL")
    args = ap.parse_args(argv)
    try:
        from datetime import datetime

        pasos = dict(p.split("=", 1) for p in args.paso if "=" in p)
        salida = args.pytest_salida.read_text(encoding="utf-8", errors="replace") if args.pytest_salida else ""
        cambios = _git("status", "--porcelain")
        registrar(
            args.destino or destino_por_defecto(),
            pasos,
            salida,
            sha=_git("rev-parse", "--short", "HEAD"),
            cambios_sin_commit=len(cambios.splitlines()) if cambios else 0,
            fecha=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
    except (OSError, ValueError) as e:
        print(f"registro del gate: no se pudo registrar ({e}); el resultado del gate NO cambia", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
