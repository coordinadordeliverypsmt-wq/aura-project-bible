"""Procedencia de la evidencia de cada capacidad, para el panel de progreso.

DERIVADA del texto libre del campo `evidencia` (D47): el unico marcador estructurado es `[EJEC]`
(«medido ejecutando»). Nada se infiere: lo que no encaja es `desconocida`. Las pruebas automatizadas
(tests/, mutaciones/) usan dobles y simulaciones, asi que NUNCA se presentan como integracion real.
"""

from __future__ import annotations

import html
import re
from typing import Any

EJECUCION = "ejecucion_real_declarada"
PRUEBAS = "pruebas_automatizadas"
SIN_EVIDENCIA = "sin_evidencia"
DESCONOCIDA = "desconocida"
ORDEN = (EJECUCION, PRUEBAS, DESCONOCIDA, SIN_EVIDENCIA)

ETIQUETAS = {
    EJECUCION: "ejecución real declarada [EJEC] (no implica verificación física salvo que la evidencia lo diga)",
    PRUEBAS: "solo pruebas automatizadas (dobles/simulación)",
    DESCONOCIDA: "procedencia desconocida",
    SIN_EVIDENCIA: "sin evidencia",
}
NIVEL_ALTO = 5
AVISO_NIVEL_ALTO = "nivel alto sin ejecución real declarada"

_EJEC = re.compile(r"\[EJEC\]")
_PRUEBAS = re.compile(r"\btests?/|\btest_\w|mutaciones/")


def clasificar(evidencia: str) -> tuple[str, bool]:
    """(procedencia, con_pruebas) a partir del texto literal de la evidencia."""
    texto = evidencia or ""
    con_pruebas = bool(_PRUEBAS.search(texto))
    if _EJEC.search(texto):
        return EJECUCION, con_pruebas
    if not texto.strip():
        return SIN_EVIDENCIA, False
    return (PRUEBAS if con_pruebas else DESCONOCIDA), con_pruebas


def anotar(c: dict[str, Any]) -> dict[str, Any]:
    """Campos de procedencia de una capacidad (derivados; no cambian su nivel)."""
    procedencia, con_pruebas = clasificar(str(c.get("evidencia", "")))
    alto_sin_ejec = c["nivel"] >= NIVEL_ALTO and procedencia != EJECUCION
    return {
        "procedencia": procedencia,
        "procedencia_etiqueta": ETIQUETAS[procedencia],
        "con_pruebas": con_pruebas,
        "aviso_procedencia": AVISO_NIVEL_ALTO if alto_sin_ejec else "",
    }


def resumen(caps: list[dict[str, Any]]) -> dict[str, Any]:
    """Recuento por procedencia: total, MVP y fuera de MVP (horizonte), mas los avisos de nivel alto."""
    out: dict[str, Any] = {ambito: dict.fromkeys(ORDEN, 0) for ambito in ("total", "mvp", "fuera_mvp")}
    nivel_alto = 0
    for c in caps:
        a = anotar(c)
        ambito = "mvp" if c.get("alcance") == "MVP" else "fuera_mvp"
        for clave in ("total", ambito):
            out[clave][a["procedencia"]] += 1
        nivel_alto += bool(a["aviso_procedencia"])
    out["nivel_alto_sin_ejecucion"] = nivel_alto
    out["derivada"] = True
    return out


def _e(x: object) -> str:
    return html.escape(str(x), quote=True)


def html_resumen(r: dict[str, Any]) -> str:
    """Tabla de recuento por procedencia para la seccion Resumen (todo escapado)."""
    filas = "".join(
        f"<tr><td>{_e(ETIQUETAS[p])}</td><td>{r['total'][p]}</td><td>{r['mvp'][p]}</td><td>{r['fuera_mvp'][p]}</td></tr>"
        for p in ORDEN
    )
    aviso = ""
    if r["nivel_alto_sin_ejecucion"]:
        aviso = f"<p class='aviso'>{r['nivel_alto_sin_ejecucion']} capacidades: {_e(AVISO_NIVEL_ALTO)}</p>"
    return (
        "<h3>Procedencia de la evidencia (derivada)</h3>"
        "<p class='nota'>Derivada del texto de «evidencia»; no cambia ningún nivel ni el índice.</p>"
        "<table><tr><th>Procedencia</th><th>Total</th><th>MVP</th><th>Fuera de MVP</th></tr>"
        f"{filas}</table>{aviso}"
    )


def html_celda(x: dict[str, Any]) -> str:
    """Celda de la tabla de capacidades."""
    t = _e(x["procedencia_etiqueta"])
    if x["con_pruebas"] and x["procedencia"] == EJECUCION:
        t += " · con pruebas automatizadas"
    if x["aviso_procedencia"]:
        t += f" <b class='aviso'>{_e(x['aviso_procedencia'])}</b>"
    return t
