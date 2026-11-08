"""AURA Maturity Index — cálculo REPRODUCIBLE del estado del ser (mandato del CEO, 2026-09-27).

Uso:  python3 herramientas/indice_madurez.py milestones/mapa-maestro/capacidades.json

No hay porcentajes a ojo: cada capacidad tiene un NIVEL de la escala 0-6 y la EVIDENCIA que lo
sostiene, en un fichero de datos versionado. Cambiar el índice exige cambiar un nivel y su evidencia.

ESCALA
  0 INEXISTENTE · 1 CONCEPTO (solo en Bible/ADR/DP) · 2 PROTOTIPO (parcial o no alcanzable en runtime)
  3 IMPLEMENTADA (código + pruebas) · 4 INTEGRADA (alcanzable al ejecutar AURA)
  5 DEMOSTRADA E2E (ejecución real) · 6 OPERATIVA (además mutación, gobierno, persistencia, uso real)

FÓRMULA
  core(c)  = min(nivel, 3) / 3      cuánto del ser está CONSTRUIDO (diseño -> implementación)
  ready(c) = max(nivel - 3, 0) / 3  cuánto está LISTO (integración -> operación gobernada)
  Por dimensión: media de sus capacidades.  AURA CORE / READY: media de las dimensiones.
  AURA MATURITY INDEX = (CORE + READY) / 2  = media de nivel/6 por dimensión.

PESOS: todas las dimensiones pesan lo mismo. La Bible no ordena sus pilares por importancia, y un
peso inventado sería un porcentaje a ojo disfrazado de fórmula. Lo que sí define la Bible es el
ALCANCE: `ambito="MVP"` mide solo lo que la Bible exige para el lanzamiento (2.2); sin ámbito, el
horizonte completo hasta Release 4.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict


class IndiceInvalido(ValueError):
    """El fichero de datos no respeta la escala o afirma un nivel sin evidencia."""


def cargar(ruta: str) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["capacidades"]


def _validar(c: dict) -> None:
    nivel = c.get("nivel")
    if not isinstance(nivel, int) or not 0 <= nivel <= 6:
        raise IndiceInvalido(f"nivel fuera de la escala 0-6 en {c.get('capacidad')!r}: {nivel!r}")
    if nivel >= 2 and not str(c.get("evidencia", "")).strip():
        raise IndiceInvalido(f"{c.get('capacidad')!r} afirma nivel {nivel} sin evidencia")


def calcular(capacidades: list[dict], ambito: str | None = None) -> dict:
    """{'core','ready','indice','dimensiones':{dim:{core,ready,indice,n}}} en tanto por uno."""
    por_dim: dict[str, list[dict]] = defaultdict(list)
    for c in capacidades:
        _validar(c)
        if ambito is None or c.get("alcance") == ambito:
            por_dim[c["dim"]].append(c)
    dims = {}
    for d, cs in sorted(por_dim.items()):
        core = sum(min(c["nivel"], 3) / 3 for c in cs) / len(cs)
        ready = sum(max(c["nivel"] - 3, 0) / 3 for c in cs) / len(cs)
        dims[d] = {"core": core, "ready": ready, "indice": (core + ready) / 2, "n": len(cs)}
    if not dims:
        return {"core": 0.0, "ready": 0.0, "indice": 0.0, "dimensiones": {}}
    core = sum(v["core"] for v in dims.values()) / len(dims)
    ready = sum(v["ready"] for v in dims.values()) / len(dims)
    return {"core": core, "ready": ready, "indice": (core + ready) / 2, "dimensiones": dims}


def _informe(capacidades: list[dict]) -> str:
    lineas = []
    for titulo, ambito in (("LANZAMIENTO (alcance MVP, Bible 2.2)", "MVP"), ("HORIZONTE COMPLETO (hasta R4)", None)):
        r = calcular(capacidades, ambito)
        lineas.append(f"\n{titulo}")
        lineas.append(f"  AURA CORE  = {r['core']*100:5.1f} %")
        lineas.append(f"  AURA READY = {r['ready']*100:5.1f} %")
        lineas.append(f"  AURA MATURITY INDEX = {r['indice']*100:5.1f} %")
        lineas.append("  | Dim | n | Core % | Ready % | Índice % |")
        for d, v in r["dimensiones"].items():
            lineas.append(f"  | {d} | {v['n']} | {v['core']*100:5.1f} | {v['ready']*100:5.1f} | {v['indice']*100:5.1f} |")
    return "\n".join(lineas)


if __name__ == "__main__":
    print(_informe(cargar(sys.argv[1])))
