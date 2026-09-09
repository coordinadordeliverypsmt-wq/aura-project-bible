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
    # Sistema Operativo Interno: AURORA se verifica a si misma. VERDES porque solo EXAMINAN el arbol de
    # trabajo, no lo modifican. La superficie ejecutable esta cerrada en adapters/qa.py: el comando es
    # una constante del adaptador, nunca llega por `args` (CEO 2026-08-03).
    "ejecutar_pruebas": {"lista": "verde", "efecto": "lectura", "desc": "ejecutar la bateria de pruebas"},
    "verificar_calidad": {"lista": "verde", "efecto": "lectura", "desc": "verificar la calidad del codigo"},
    "auditar_garantias": {"lista": "verde", "efecto": "lectura", "desc": "revisar que las garantias siguen vigentes"},
    "diagnosticar_estado": {"lista": "verde", "efecto": "lectura", "desc": "informe del propio estado"},
    # --- Computador: alteran estado (M2) ---
    "mover_archivo": {"lista": "roja", "efecto": "altera", "desc": "mover (puede colisionar en destino)"},
    "renombrar_archivo": {"lista": "roja", "efecto": "altera", "desc": "renombrar"},
    # `copiar_archivo` es VERDE por el mismo criterio de REVERSIBILIDAD: solo crea `<ruta>.copia` y el
    # adaptador rechaza sobrescribir, de modo que nunca destruye ni pierde datos (deshacer = borrar la
    # copia, trivial). A diferencia de mover/escribir, no puede colisionar destruyendo el destino. Por eso
    # `efecto` es "reversible" (fuera de ALTERA_ESTADO): no exige dry-run. Es lo que permite que la
    # automatizacion "copia antes de borrar" se ejecute sin pedir confirmacion (respeta 6.4 §4: una regla
    # solo pide confirmacion si TOCA lista roja; copiar no la toca).
    "copiar_archivo": {
        "lista": "verde",
        "efecto": "reversible",
        "desc": "copiar a <ruta>.copia (crea, nunca sobrescribe)",
    },
    "escribir_archivo": {"lista": "roja", "efecto": "altera", "desc": "crear o sobrescribir"},
    # SO Interno: AURORA propone cambios sobre su propio codigo. ROJA aunque el cambio se revierta
    # solo si la verificacion falla: que sea reversible reduce el daño, no la necesidad de
    # consentimiento (ADR-0003, "ante la duda, roja").
    "proponer_cambio": {"lista": "roja", "efecto": "altera", "desc": "proponer un cambio verificado en el codigo"},
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
    # --- F3 · informacion sobre la persona (DP-D-M-8 §4.2, D-M8-2) ---------------------------------
    #
    # §4.2 declaraba dos huecos: no existia entrada para CREAR informacion sobre la persona, y el
    # catalogo no distinguia el SUJETO —borrar un temporal y borrar un hecho clinico eran ambos
    # "borrar"—. `sujeto` cierra el segundo; estas tres entradas, el primero. Son las que el DP
    # nombra literalmente: ni una mas (D23 sigue cerrado).
    #
    # TERCERA CLASE (`soberania`), decision del CEO 2026-08-25 sobre D-M8-2. El vocabulario
    # verde|roja no puede expresar la fila que §4.3 ya aprobo: kill switch SI, catalogo SI, dry-run
    # SI, permisos SI, **HITL NO por defecto**, auditoria SI, reversibilidad SI. En verde chocarian
    # con «nada que altere o destruya puede estar en verde»; en roja, con §4.3 —y ADR-0003 no
    # permite eximir del HITL a una accion roja—. Esta clase expresa la politica sin tocar ninguna
    # de las dos garantias: la regla estructural habla de VERDE, ADR-0003 habla de ROJA.
    "registrar_informacion_usuario": {
        "lista": "soberania", "efecto": "altera", "sujeto": "usuario",
        "desc": "registrar informacion sobre la persona"},
    "olvidar_informacion_usuario": {
        "lista": "soberania", "efecto": "destruye", "sujeto": "usuario",
        "desc": "olvidar informacion sobre la persona"},
    "refutar_informacion_usuario": {
        "lista": "soberania", "efecto": "altera", "sujeto": "usuario",
        "desc": "marcar como refutada informacion sobre la persona"},
}

# Fuente unica de verdad: las listas se DERIVAN del catalogo, no se mantienen en paralelo.
GREEN = {a for a, m in CATALOGO.items() if m["lista"] == "verde"}
RED = {a for a, m in CATALOGO.items() if m["lista"] == "roja"}

# Soberania del usuario sobre sus propios datos: pasa TODOS los controles y no pide confirmacion.
# Derivada del mismo catalogo — una sola fuente de verdad, sin segunda via de clasificacion.
SOBERANIA = {a for a, m in CATALOGO.items() if m["lista"] == "soberania"}

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

# Operaciones que recaen sobre una PERSONA y deben declarar sobre quien (DP-D-M-8 §4.2). Derivada del
# catalogo por el mismo motivo que las anteriores: una lista escrita a mano seria una segunda via de
# clasificacion, y acabaria divergiendo de la primera.
SUJETO_REQUERIDO = {a for a, m in CATALOGO.items() if m.get("sujeto") == "usuario"}


def sujeto_declarado(args: dict) -> bool:
    """¿Los argumentos identifican sobre QUIEN recae la operacion? **Fail-closed.**

    Presente pero vacio no es declarado: `{"user_id": ""}` no dice sobre quien recae, y tratarlo
    como valido convertiria la comprobacion en decorativa.
    """
    valor = (args or {}).get("user_id")
    return isinstance(valor, str) and valor.strip() != ""


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
        # F3 · el par (operacion, sujeto). Va DESPUES del kill switch —I-F2-5 no se toca— y ANTES de
        # cualquier autorizacion: una operacion que recae sobre una persona y no dice sobre quien no
        # puede evaluarse, y lo que no se puede evaluar se deniega (mismo criterio que RN-2).
        if action in SUJETO_REQUERIDO and not sujeto_declarado(args):
            obs.log("AUDIT", "permissions", f"{action} sin sujeto declarado -> denegada", trace_id, audit=True)
            _metrica_resultado(False)
            return False, "la operacion recae sobre una persona y no declara el sujeto"
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
        if action in SOBERANIA:
            # §4.3: «el motor aplica la politica; la politica puede eximir de HITL SIN EXIMIR DE NADA
            # MAS». Llega aqui habiendo pasado ya kill switch y sujeto; le siguen dry-run, motor,
            # ejecutor y auditoria. Lo unico que se omite es preguntar: el usuario lo esta pidiendo.
            obs.log("AUDIT", "permissions", f"soberania {action} -> sin HITL (§4.3)", trace_id, audit=True)
            _metrica_resultado(True)
            return True, "soberania del usuario (§4.3: sin HITL por defecto)"
        if action in GREEN:
            obs.log("AUDIT", "permissions", f"lista verde {action} -> auto-ejecucion", trace_id, audit=True)
            _metrica_resultado(True)
            return True, "auto (lista verde)"
        obs.log("AUDIT", "permissions", f"accion desconocida {action} -> denegada por defecto", trace_id, audit=True)
        _metrica_resultado(False)
        return False, "accion no clasificada (deny por defecto)"
