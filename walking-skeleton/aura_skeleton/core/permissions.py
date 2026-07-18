"""Gestor de Permisos y HITL (Bible 5.3 / ADR-0003). Toda accion pasa por aqui antes de
tocar un adaptador. Lista roja = confirmacion humana SIEMPRE, tolerancia cero a falsos negativos (2.5 5.4)."""

from __future__ import annotations

from .. import observability as obs

# ADR-0003 (acta D4) — listas permanentes
GREEN = {
    "encender_dispositivo",
    "apagar_dispositivo",
    "consulta",
    "recordatorio",
    "monitoreo",
    "organizacion",
    "automatizacion",
}
RED = {
    "pago",
    "compra",
    "transferencia",
    "eliminar_informacion",
    "abrir_cerradura",
    "mensaje_a_tercero",
    "accion_legal",
    "accion_financiera",
}


class PermissionManager:
    def __init__(self, human_confirm, kill_switch=None):
        self._confirm = human_confirm  # callable(action, args, trace_id) -> bool  (HITL)
        self._kill = kill_switch  # KillSwitch opcional (Bible 5.3 §5)

    async def authorize(self, action: str, args: dict, trace_id: str) -> tuple[bool, str]:
        if self._kill is not None and self._kill.is_engaged():
            obs.log("KILL", "permissions", f"kill switch activo: {action} BLOQUEADA", trace_id, audit=True)
            return False, "kill switch activo (5.3 §5)"
        if action in RED:
            obs.log(
                "HITL", "permissions", f"accion de LISTA ROJA requiere confirmacion: {action}", trace_id, audit=True
            )
            ok = await self._confirm(action, args, trace_id)
            obs.log(
                "AUDIT",
                "permissions",
                f"lista roja {action} -> {'AUTORIZADA' if ok else 'DENEGADA'}",
                trace_id,
                audit=True,
            )
            return ok, ("confirmada por el usuario" if ok else "denegada por el usuario")
        if action in GREEN:
            obs.log("AUDIT", "permissions", f"lista verde {action} -> auto-ejecucion", trace_id, audit=True)
            return True, "auto (lista verde)"
        obs.log("AUDIT", "permissions", f"accion desconocida {action} -> denegada por defecto", trace_id, audit=True)
        return False, "accion no clasificada (deny por defecto)"
