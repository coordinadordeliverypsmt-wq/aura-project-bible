"""Integracion (Etapa 4): la composicion obtiene el ActivationContext del Builder, no a mano.

El comportamiento observable ya lo cubren las pruebas de memoria (identicas antes y despues). Lo que
NO puede demostrarse por comportamiento es la sustitucion del ensamblaje provisional por el definitivo:
esta prueba lo hace cumplir estructuralmente, por AST (precedente D41/MA.5-a).

Es anti-regresion, no congelacion de implementacion: si alguien volviera a construir el contexto a mano
en la composicion, el flujo aprobado —Detectores -> Builder -> ActivationContext -> Manager— quedaria
puenteado sin que ninguna prueba de comportamiento lo notara.
"""

import ast
import pathlib


def _arbol() -> ast.Module:
    from aura_skeleton import composicion

    return ast.parse(pathlib.Path(composicion.__file__).read_text(encoding="utf-8"))


def _llamadas(arbol: ast.Module) -> set[str]:
    """Nombres invocados en la composicion (deteccion por AST, no por texto)."""
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            f = nodo.func
            if isinstance(f, ast.Name):
                nombres.add(f.id)
            elif isinstance(f, ast.Attribute):
                nombres.add(f.attr)
    return nombres


def test_la_composicion_obtiene_el_contexto_del_builder():
    llamadas = _llamadas(_arbol())
    assert "ActivationContextBuilder" in llamadas, "la composicion debe construir el contexto via Builder"
    assert "construir" in llamadas, "la composicion debe invocar Builder.construir()"


def test_la_composicion_ya_no_construye_el_contexto_a_mano():
    llamadas = _llamadas(_arbol())
    assert "ActivationContext" not in llamadas, (
        "el ensamblaje provisional sigue vivo: la composicion construye ActivationContext directamente"
    )
