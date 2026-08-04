"""Ejecutor de Diagnostico: el informe de estado, como capacidad del ciclo.

Convierte el autodiagnostico en algo que el Director puede DESPACHAR y cuyo resultado vuelve al ciclo.
Antes era una funcion que alguien tenia que llamar; ahora es trabajo que AURORA puede pedirse a si
misma, y cuyo veredicto alimenta la planificacion.

EL VEREDICTO ES LO QUE CIERRA EL BUCLE. Devuelve `ok: False` cuando hay una incidencia dominante, de
modo que la validacion en dos niveles bloquea la tarea y el oyente de transiciones genera trabajo de
correccion. Un diagnostico que siempre dijera "ok" seria un informe descartado, que es exactamente el
defecto que corregimos en el incremento anterior.

NO depende de un modelo local: agrupa y cuenta. NO toca el producto: solo lee el audit log.
"""

from __future__ import annotations

from .. import observability as obs
from ..core.autodiagnostico import diagnosticar, informe_ejecutivo


class EjecutorDiagnostico:
    name = "diagnostico"
    capabilities = ["diagnosticar_estado"]

    def __init__(self, ruta_audit: str, auditor=None) -> None:
        # La ruta se fija al construir, NO llega por `args`: nadie puede redirigir el diagnostico.
        self._ruta = ruta_audit
        self._auditor = auditor

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        if command != "diagnosticar_estado":
            raise ValueError(f"capacidad no ofrecida por el ejecutor de Diagnostico: {command!r}")

        diag = diagnosticar(self._ruta)
        garantias = None
        if self._auditor is not None:
            garantias = await self._auditor.execute("auditar_garantias", {}, trace_id, event_id)

        dominante = diag.incidencia_dominante
        # Sin datos NO es un problema que corregir: es ausencia de evidencia. Se informa y se cierra,
        # porque bloquear la tarea generaria trabajo sobre nada.
        hay_problema = dominante is not None or (garantias is not None and not garantias.get("ok", True))

        obs.log(
            "DIAG",
            "ejecutor-diagnostico",
            f"estado: {'con incidencias' if hay_problema else 'sin incidencias'}",
            trace_id,
            audit=True,
        )
        return {
            "capacidad": command,
            "ok": not hay_problema,
            "eventos": diag.eventos,
            "incidencia_dominante": list(dominante) if dominante else None,
            "resumen": _resumen(diag, dominante, garantias),
            "informe": informe_ejecutivo(diag, garantias=garantias),
        }


def _resumen(diag, dominante, garantias) -> str:
    """Accionable en una linea: lo que la planificacion convertira en una tarea."""
    if dominante:
        return f"incidencia dominante: {dominante[0]} ({dominante[1]}x)"
    if garantias is not None and not garantias.get("ok", True):
        return f"{len(garantias.get('rotas', []))} garantia(s) declaradas ya no protegen nada"
    if diag.sin_datos:
        return "sin uso registrado: no hay evidencia sobre la que priorizar"
    return f"{diag.eventos} evento(s) sin incidencias"
