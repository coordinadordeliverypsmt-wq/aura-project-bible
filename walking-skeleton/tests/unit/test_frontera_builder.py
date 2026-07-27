"""Unit: frontera arquitectonica del ActivationContextBuilder (I-A3) — anti-regresion por AST.

La frontera "el Builder no aplica reglas ni decide" no puede quedar en prosa: se hace cumplir aqui.
Si alguien introdujera una decision en el Builder —importando el Registry, el Manager o los tipos de
decision— esta prueba falla en el Quality Gate.

Deteccion por **AST**, no por texto (leccion de D41/MA.5-a): los docstrings pueden mencionar `Estado` o
`Decision` para explicar la frontera sin violarla; lo que se prohibe es **referenciarlos en el codigo**.
"""

import ast
import pathlib

PROHIBIDOS = {
    # Componentes cuya logica no puede entrar en el Builder
    "CapabilityRegistry",
    "CapabilityManager",
    "catalogo",
    # Tipos de DECISION: el Builder no decide (I-A3/I-A1)
    "Estado",
    "Decision",
    "PlanActivacion",
    # Reglas: el Builder no las interpreta
    "Regla",
    "Condicion",
    "Fuente",
    "Operador",
}

MODULOS_PROHIBIDOS = {"capability_registry", "capability_manager", "catalogo_capacidades"}


def _arbol() -> ast.Module:
    from aura_skeleton.core import activation_context_builder as mod

    return ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))


def _nombres_referenciados(arbol: ast.Module) -> set[str]:
    """Identificadores usados en CODIGO (no en docstrings ni comentarios)."""
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
        elif isinstance(nodo, ast.ImportFrom):
            for alias in nodo.names:
                nombres.add(alias.name)
                if alias.asname:
                    nombres.add(alias.asname)
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                nombres.add(alias.name.split(".")[-1])
    return nombres


def test_builder_no_referencia_registry_manager_ni_tipos_de_decision():
    """I-A3: el Builder ensambla; no decide ni interpreta reglas."""
    intrusos = _nombres_referenciados(_arbol()) & PROHIBIDOS
    assert not intrusos, f"el Builder referencia elementos prohibidos (I-A3): {sorted(intrusos)}"


def test_builder_no_importa_modulos_de_decision():
    modulos: set[str] = set()
    for nodo in ast.walk(_arbol()):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.update(nodo.module.split("."))
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                modulos.update(alias.name.split("."))
    intrusos = modulos & MODULOS_PROHIBIDOS
    assert not intrusos, f"el Builder importa modulos de decision (I-A3): {sorted(intrusos)}"


def test_protocolos_de_detector_por_ambito():
    """I-A2: cada detector produce SOLO lo de su ambito, con contratos semanticamente explicitos."""
    from aura_skeleton.core.detectores import DetectorEntorno, DetectorHardware

    assert hasattr(DetectorHardware, "detectar"), "el detector de hardware produce metricas verificadas"
    assert hasattr(DetectorEntorno, "capacidades_soportadas"), (
        "el detector de entorno declara QUE capacidades soporta (contrato semantico, no frozenset anonimo)"
    )
    # Ningun detector invade el ambito del otro.
    assert not hasattr(DetectorHardware, "capacidades_soportadas")
    assert not hasattr(DetectorEntorno, "detectar")
