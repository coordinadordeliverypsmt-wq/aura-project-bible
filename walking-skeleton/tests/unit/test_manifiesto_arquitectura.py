"""Prueba anti-regresion de arquitectura (MA.5-a · D40 · D41 · ADR-0018).

Hace cumplir la clasificacion de ejecutables del manifiesto —la FUENTE UNICA DE VERDAD (D41)—:
solo `composicion.py` y los arneses declarados construyen el sistema; el punto de entrada de
produccion lo consume; ningun ejecutable nuevo puede aparecer sin clasificar.

Lee `walking-skeleton/architecture_manifest.toml`. **No duplica la lista** (D41): la deriva del
manifiesto en cada corrida. La deteccion es por AST (construccion real de `Orchestrator`), no por
texto, para no confundir un import o un comentario con un cableado.
"""

import ast
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]  # tests/unit/ -> walking-skeleton/
MANIFIESTO = RAIZ / "architecture_manifest.toml"


def _manifiesto() -> dict:
    with open(MANIFIESTO, "rb") as f:
        return tomllib.load(f)


def _construye_orchestrator(ruta: Path) -> bool:
    """True si el fichero CONSTRUYE `Orchestrator(...)` (llamada), no solo lo importa o lo nombra."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            if isinstance(funcion, ast.Name) and funcion.id == "Orchestrator":
                return True
            if isinstance(funcion, ast.Attribute) and funcion.attr == "Orchestrator":
                return True
    return False


def _ejecutables_del_sistema() -> list[Path]:
    """El paquete y los scripts de nivel superior. Los tests se exclurian a proposito: construir
    `Orchestrator` en una prueba es legitimo."""
    ficheros = list((RAIZ / "aura_skeleton").rglob("*.py"))
    ficheros += list(RAIZ.glob("*.py"))
    return ficheros


def _rel(p: Path) -> str:
    return str(p.relative_to(RAIZ))


def test_todo_constructor_del_sistema_esta_clasificado():
    """Cobertura total (anti-regresion): cualquier ejecutable que construya `Orchestrator` debe estar
    declarado en el manifiesto. Un ejecutable NUEVO sin clasificar dispara esta prueba (D40/D41)."""
    m = _manifiesto()
    clasificados = (
        {m["produccion"]["composicion"]}
        | {a["archivo"] for a in m.get("arneses", [])}
        | {o["archivo"] for o in m.get("obsoletos", [])}
    )
    constructores = {_rel(p) for p in _ejecutables_del_sistema() if _construye_orchestrator(p)}
    sin_clasificar = constructores - clasificados
    assert not sin_clasificar, (
        f"ejecutable(s) que construyen el sistema sin declararse en el manifiesto (D40/D41): "
        f"{sorted(sin_clasificar)}. Deben consumir composicion.componer() o declararse como arnes."
    )


def test_el_punto_de_entrada_de_produccion_consume_composicion():
    """Produccion no reconstruye el sistema: consume `composicion.componer()`, no construye `Orchestrator`."""
    m = _manifiesto()
    for rel in m["produccion"]["entrypoints"]:
        p = RAIZ / rel
        assert p.exists(), f"entrypoint inexistente en el manifiesto: {rel}"
        assert not _construye_orchestrator(p), (
            f"{rel} es punto de entrada de PRODUCCION y construye Orchestrator directamente; "
            f"debe consumir composicion.componer() (D40.2)."
        )
        assert "componer" in p.read_text(encoding="utf-8"), f"{rel} no consume composicion.componer() (D40.2)."


def test_los_que_no_construyen_sistema_no_construyen_orchestrator():
    """Consistencia del manifiesto: los clasificados como 'no construyen sistema' realmente no lo hacen."""
    m = _manifiesto()
    for rel in m["no_construyen_sistema"]["scripts"]:
        p = RAIZ / rel
        assert p.exists(), f"script inexistente en el manifiesto: {rel}"
        assert not _construye_orchestrator(p), (
            f"{rel} esta como 'no construye sistema' pero SI construye Orchestrator; reclasificar."
        )


def test_el_manifiesto_no_tiene_entradas_fantasma():
    """Cada fichero declarado en el manifiesto existe (sin clasificaciones fantasma)."""
    m = _manifiesto()
    referencias = (
        list(m["produccion"]["entrypoints"])
        + [m["produccion"]["composicion"]]
        + [a["archivo"] for a in m.get("arneses", [])]
        + list(m["no_construyen_sistema"]["scripts"])
        + [o["archivo"] for o in m.get("obsoletos", [])]
    )
    faltan = [r for r in referencias if not (RAIZ / r).exists()]
    assert not faltan, f"el manifiesto referencia ficheros inexistentes: {faltan}"
