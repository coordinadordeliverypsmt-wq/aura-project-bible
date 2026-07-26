"""Gestor de Permisos y HITL (Bible 5.3 / ADR-0003). Toda accion pasa por aqui antes de
tocar un adaptador. Lista roja = confirmacion humana SIEMPRE, tolerancia cero a falsos negativos (2.5 5.4)."""

from __future__ import annotations

from .. import observability as obs

# ADR-0003 (acta D4) — listas permanentes
# ---------------------------------------------------------------------------
# CATALOGO EXPLICITO DE ACCIONES (H3, M2.0)
#
# Hasta M1 las listas eran categorias abstractas ("organizacion", "monitoreo"). En M2 el sistema
# actua sobre archivos y procesos reales, y una categoria no basta para decidir si una operacion
# concreta destruye datos.
#
# CRITERIO DE CLASIFICACION: REVERSIBILIDAD.
#   verde -> no altera el estado del usuario (lectura, consulta) o es trivialmente reversible.
#   roja  -> altera o destruye estado, o produce efectos observables fuera del sistema.
#
# El criterio es deliberadamente conservador: ante la duda, roja. Un falso positivo cuesta una
# confirmacion al usuario; un falso negativo puede destruir datos irrecuperables (riesgo RN-1).
#
# NOTA PARA EL CEO: 6.4 §1 situa "organizar" en lista verde. Al descomponerlo en operaciones
# concretas, `mover_archivo` y `renombrar_archivo` ALTERAN el estado del usuario y pueden perder
# datos si el destino colisiona. Se clasifican en ROJA a la espera de ratificacion. Es una
# divergencia consciente respecto a la Bible, no un descuido.
# ---------------------------------------------------------------------------

CATALOGO: dict[str, dict] = {
    # --- Conversacion y dispositivos (heredado de M1) ---
    "consulta": {"lista": "verde", "efecto": "ninguno", "desc": "responder sin actuar"},
    "recordatorio": {"lista": "verde", "efecto": "interno", "desc": "crear recordatorio propio"},
    "monitoreo": {"lista": "verde", "efecto": "lectura", "desc": "observar estado"},
    "automatizacion": {"lista": "verde", "efecto": "interno", "desc": "definir regla (no ejecutarla)"},
    "organizacion": {"lista": "verde", "efecto": "interno", "desc": "planificar organizacion (dry-run)"},
    "encender_dispositivo": {"lista": "verde", "efecto": "reversible", "desc": "encender dispositivo"},
    "apagar_dispositivo": {"lista": "verde", "efecto": "reversible", "desc": "apagar dispositivo"},
    # --- Computador: solo lectura (M2) ---
    "buscar_archivo": {"lista": "verde", "efecto": "lectura", "desc": "buscar por nombre o patron"},
    "listar_directorio": {"lista": "verde", "efecto": "lectura", "desc": "listar contenido"},
    "leer_archivo": {"lista": "verde", "efecto": "lectura", "desc": "leer contenido"},
    "abrir_archivo": {"lista": "verde", "efecto": "lectura", "desc": "abrir en su aplicacion"},
    "consultar_estado_sistema": {"lista": "verde", "efecto": "lectura", "desc": "disco, memoria, procesos"},
    # --- Computador: alteran estado (M2) ---
    "mover_archivo": {"lista": "roja", "efecto": "altera", "desc": "mover (puede colisionar en destino)"},
    "renombrar_archivo": {"lista": "roja", "efecto": "altera", "desc": "renombrar"},
    "escribir_archivo": {"lista": "roja", "efecto": "altera", "desc": "crear o sobrescribir"},
    "borrar_archivo": {"lista": "roja", "efecto": "destruye", "desc": "eliminar del disco"},
    "modificar_configuracion": {"lista": "roja", "efecto": "altera", "desc": "cambiar configuracion del sistema"},
    "terminar_proceso": {"lista": "roja", "efecto": "altera", "desc": "matar un proceso"},
    "instalar_software": {"lista": "roja", "efecto": "altera", "desc": "instalar o desinstalar"},
    # --- Efectos fuera del sistema (heredado de M1) ---
    "pago": {"lista": "roja", "efecto": "externo", "desc": "realizar un pago"},
    "compra": {"lista": "roja", "efecto": "externo", "desc": "realizar una compra"},
    "transferencia": {"lista": "roja", "efecto": "externo", "desc": "transferir fondos"},
    "eliminar_informacion": {"lista": "roja", "efecto": "destruye", "desc": "eliminar informacion"},
    "abrir_cerradura": {"lista": "roja", "efecto": "externo", "desc": "abrir una cerradura"},
    "mensaje_a_tercero": {"lista": "roja", "efecto": "externo", "desc": "enviar mensaje a otra persona"},
    "accion_legal": {"lista": "roja", "efecto": "externo", "desc": "accion con efecto legal"},
    "accion_financiera": {"lista": "roja", "efecto": "externo", "desc": "accion financiera"},
}

# Fuente unica de verdad: las listas se DERIVAN del catalogo, no se mantienen en paralelo.
GREEN = {a for a, m in CATALOGO.items() if m["lista"] == "verde"}
RED = {a for a, m in CATALOGO.items() if m["lista"] == "roja"}

# Acciones que exigen DRY-RUN antes de confirmarse (M2.5, ALERTA-005).
#
# Se derivan del efecto declarado, no de una lista escrita a mano que pueda divergir del catalogo.
# Quedan dentro `altera`, `destruye` y `externo`: lo que no es trivialmente reversible.
#
# `reversible` (encender/apagar un dispositivo) queda FUERA a proposito. Exigirle previsualizacion
# obligaria a todo adaptador domotico a implementar `simular()` y, si no lo hiciera, el ejecutor
# rechazaria encender una luz: una regresion de la garantia de M1 "lista verde ejecuta" a cambio de
# ninguna proteccion real, porque apagar lo que se encendio cuesta un segundo.
ALTERA_ESTADO = {a for a, m in CATALOGO.items() if m["efecto"] in ("altera", "destruye", "externo")}


def altera_estado(accion: str) -> bool:
    """Criterio unico de "necesita dry-run", consultable por el ejecutor."""
    return accion in ALTERA_ESTADO


def _metrica_resultado(ok: bool) -> None:
    """Metrica basica P-ARQ-7 (Bible 7.4): cuenta cada decision del gate como autorizada o
    denegada. Fuente unica del nombre (D41); observabilidad interna, local y en memoria (ADR-0001)."""
    obs.metric_inc("acciones.autorizadas" if ok else "acciones.denegadas")


class PermissionManager:
    def __init__(self, human_confirm, kill_switch=None):
        self._confirm = human_confirm  # callable(action, args, trace_id) -> bool  (HITL)
        self._kill = kill_switch  # KillSwitch opcional (Bible 5.3 §5)

    async def authorize(self, action: str, args: dict, trace_id: str) -> tuple[bool, str]:
        if self._kill is not None and self._kill.is_engaged():
            obs.log("KILL", "permissions", f"kill switch activo: {action} BLOQUEADA", trace_id, audit=True)
            _metrica_resultado(False)
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
            _metrica_resultado(ok)
            return ok, ("confirmada por el usuario" if ok else "denegada por el usuario")
        if action in GREEN:
            obs.log("AUDIT", "permissions", f"lista verde {action} -> auto-ejecucion", trace_id, audit=True)
            _metrica_resultado(True)
            return True, "auto (lista verde)"
        obs.log("AUDIT", "permissions", f"accion desconocida {action} -> denegada por defecto", trace_id, audit=True)
        _metrica_resultado(False)
        return False, "accion no clasificada (deny por defecto)"
