"""Empaqueta el agente de nodo (DP-NODO-01 §5): SOLO lo que `aura_skeleton.nodo_agente` importa + `nats-py`.

    python3 empaquetar_nodo.py WALKING_SKELETON DESTINO

Deja en DESTINO: `aura_skeleton/` (los módulos que el agente alcanza, calculados con `modulefinder`: nada de
LLM, voz, Core cognitivo ni composición), `nats/` (el paquete de nats-py del Python que ejecuta esto; es Python
puro y sin dependencias obligatorias) y `MANIFIESTO.txt` (`<sha256>  <ruta>` por fichero, orden estable).
Sin `__pycache__`. Es reproducible: el mismo origen produce el mismo manifiesto. Solo stdlib.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from modulefinder import ModuleFinder
from pathlib import Path

PUNTO_DE_ENTRADA = "aura_skeleton.nodo_agente"
MANIFIESTO = "MANIFIESTO.txt"


def modulos_del_agente(ws: Path) -> list[Path]:
    """Ficheros de `aura_skeleton` alcanzables desde el agente (incluye los `__init__` de los paquetes)."""
    buscador = ModuleFinder(path=[str(ws), *sys.path])
    buscador.import_hook(PUNTO_DE_ENTRADA)
    raiz = (ws / "aura_skeleton").resolve()
    ficheros: set[Path] = set()
    for nombre, modulo in buscador.modules.items():
        archivo = getattr(modulo, "__file__", None)
        if nombre.split(".")[0] != "aura_skeleton" or not archivo:
            continue
        ruta = Path(archivo).resolve()
        if raiz in ruta.parents:
            ficheros.add(ruta)
    faltan = [n for n in buscador.badmodules if n.startswith("aura_skeleton")]
    if faltan:
        raise SystemExit(f"módulos del agente no resueltos: {sorted(faltan)}")
    return sorted(ficheros)


def _copiar(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origen, destino)


def _directorio_nats() -> Path:
    spec = importlib.util.find_spec("nats")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("nats-py no está instalado en este Python")
    return Path(next(iter(spec.submodule_search_locations)))


def _preparar_destino(destino: Path) -> None:
    if destino.exists():
        if not (destino / MANIFIESTO).is_file():
            raise SystemExit(f"{destino} existe y no es un paquete previo (no tiene {MANIFIESTO}): no lo toco")
        shutil.rmtree(destino)
    destino.mkdir(parents=True)


def empaquetar(ws: Path, destino: Path) -> list[str]:
    ws = ws.resolve()
    _preparar_destino(destino)
    for ruta in modulos_del_agente(ws):
        _copiar(ruta, destino / "aura_skeleton" / ruta.relative_to(ws / "aura_skeleton"))
    nats = _directorio_nats()
    for ruta in sorted(nats.rglob("*")):
        if ruta.is_file() and "__pycache__" not in ruta.parts and ruta.suffix != ".pyc":
            _copiar(ruta, destino / "nats" / ruta.relative_to(nats))
    rutas = sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*") if p.is_file())
    lineas = [f"{hashlib.sha256((destino / r).read_bytes()).hexdigest()}  {r}" for r in rutas]
    (destino / MANIFIESTO).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return rutas


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("uso: empaquetar_nodo.py WALKING_SKELETON DESTINO", file=sys.stderr)
        return 2
    rutas = empaquetar(Path(argv[1]), Path(argv[2]))
    print(f"paquete: {len(rutas)} ficheros en {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
