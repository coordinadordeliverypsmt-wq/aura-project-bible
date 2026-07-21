"""Ejecutor unico de acciones y motor de automatizacion (M2.3 + M2.5, Bible 6.4 §2).

M2.3 introdujo el primer punto donde AURA actua **sin un humano delante**: una regla dispara cuando
ocurre un evento, no cuando alguien lo pide. De ahi las tres restricciones que gobiernan cada
disparo:

1. **Dry-run obligatorio** para toda accion que altere el estado. Sin plan previo no hay ejecucion.
2. **Toda accion pasa por Permisos**, incluidas las verdes. Ademas de aplicar las listas, es lo que
   hace que el kill switch alcance al motor de reglas y no solo al turno conversacional (RN-3).
3. **Las acciones de lista roja exigen confirmacion con la previsualizacion delante.** Confirmar a
   ciegas una accion destructiva no es consentimiento informado.

M2.5 (ALERTA-005) amplia su papel: este modulo pasa a ser el **unico camino de ejecucion de acciones
del sistema**, compartido por las tres vias de entrada —conversacion, reglas y centro de
notificaciones—. La alternativa era escribir el flujo por segunda vez dentro del orquestador, y dos
implementaciones del mismo control acaban divergiendo: es exactamente el error que M2.2 evito al
exigir *una unica llamada* a `validar()`. Aqui se aplica el mismo principio a escala del sistema.

Consecuencia deliberada: **la confirmacion informada no depende de por donde entro la peticion.** Sin
esto, AURA seria mas cuidadosa actuando sola que obedeciendo a un humano.

Las automatizaciones son **definidas por el usuario** (M2). Las sugeridas llegan en M3 (4.4).
"""

from __future__ import annotations

from collections.abc import Callable

from .. import observability as obs
from ..contracts import Event
from .operaciones import ErrorDeValidacion
from .permissions import altera_estado
from .registro import RegistroAdaptadores


class Regla:
    """`trigger -> condicion -> accion` sobre eventos del bus (3.3)."""

    def __init__(
        self,
        nombre: str,
        evento: str,
        accion: str,
        args: dict,
        condicion: Callable[[Event], bool] | None = None,
    ) -> None:
        self.nombre = nombre
        self.evento = evento
        self.accion = accion
        self.args = args
        self.condicion = condicion or (lambda _ev: True)

    def aplica(self, ev: Event) -> bool:
        return ev.type.startswith(self.evento) and bool(self.condicion(ev))


class MotorAutomatizacion:
    """Ejecutor unico de acciones. Acepta un `RegistroAdaptadores` o un adaptador suelto."""

    def __init__(self, adaptador_o_registro, permisos, altera: Callable[[str], bool] | None = None) -> None:
        # Un adaptador suelto se envuelve en un registro de uno: asi el resto de la clase tiene un
        # unico camino de resolucion y las pruebas que inyectan un doble siguen siendo validas.
        if hasattr(adaptador_o_registro, "para"):
            self.registro = adaptador_o_registro
        else:
            self.registro = RegistroAdaptadores([adaptador_o_registro])
        self.permisos = permisos
        # El motor no decide que altera el estado: lo consulta al catalogo (fuente unica de verdad).
        self._altera = altera or altera_estado
        self.reglas: list[Regla] = []
        self.ejecutadas: list[dict] = []

    # --------------------------------------------------------------- reglas --

    def agregar(self, regla: Regla) -> None:
        self.reglas.append(regla)

    async def on_event(self, ev: Event) -> None:
        for regla in self.reglas:
            if regla.aplica(ev):
                await self.disparar(regla, ev)

    async def disparar(self, regla: Regla, ev: Event) -> dict:
        """Via de automatizacion: delega en el ejecutor comun."""
        resultado = await self.ejecutar(
            regla.accion,
            regla.args,
            ev.trace_id,
            f"auto-{regla.nombre}-{ev.event_id}",
            origen=f"regla:{regla.nombre}",
        )
        registro = {"regla": regla.nombre, **resultado}
        self.ejecutadas.append(registro)
        return registro

    # ------------------------------------------------------------- ejecutor --

    async def ejecutar(self, accion: str, args: dict, trace_id: str, event_id: str, origen: str) -> dict:
        """Camino UNICO de ejecucion: registro -> dry-run -> permisos -> adaptador -> auditoria.

        Devuelve `estado` en {"ejecutada", "detenida", "error"}. Nunca informa exito sin haber
        obtenido un resultado real del adaptador (ALERTA-005 punto 4).
        """
        plan = None
        adaptador = self.registro.para(accion)

        # 1. Dry-run OBLIGATORIO si la accion altera el estado. Es condicion previa, no un extra:
        #    sin plan viable, la ejecucion no se intenta siquiera.
        if self._altera(accion) and adaptador is not None:
            if not hasattr(adaptador, "simular"):
                return self._detener(
                    accion, trace_id, origen, "el adaptador no soporta dry-run y la accion altera el estado"
                )
            try:
                plan = await adaptador.simular(accion, args, trace_id)
            except ErrorDeValidacion as e:
                return self._detener(accion, trace_id, origen, f"dry-run rechazo la operacion: {e}")
            except OSError as e:
                return self._detener(accion, trace_id, origen, f"dry-run no pudo completarse: {e.strerror or e}")
            if not plan.get("viable"):
                return self._detener(accion, trace_id, origen, f"dry-run no viable: {plan.get('motivo')}")

        # 2. TODA accion pasa por Permisos, ANTES de comprobar si existe quien la ejecute.
        #
        #    El orden importa y se corrigio durante M2.5. Resolver primero el adaptador parecia
        #    razonable —fallar rapido— pero acoplaba el control de gobierno a la topologia de
        #    adaptadores: una accion de lista roja sin adaptador dejaba de pasar por HITL y
        #    desaparecia del registro forense. Un intento de `transferencia` debe quedar auditado
        #    aunque AURA no tenga hoy forma de transferir nada; que no exista la capacidad es una
        #    circunstancia de la instalacion, no una razon para no aplicar el control.
        #
        #    Ademas, aqui se aplica el catalogo: lo no clasificado se deniega por defecto (RN-2),
        #    de modo que `ejecutar_comando` muere en este paso y no por casualidad de que ningun
        #    adaptador lo declare.
        #
        #    La previsualizacion viaja con la peticion para que la confirmacion sea informada; se
        #    pasa SOLO a Permisos, nunca al adaptador, que rechaza argumentos no declarados.
        contexto = dict(args)
        if plan is not None:
            contexto["_previsualizacion"] = plan.get("efecto")
        ok, motivo = await self.permisos.authorize(accion, contexto, trace_id)
        if not ok:
            return self._detener(accion, trace_id, origen, f"permisos: {motivo}")

        # 3. ¿Quien atiende esta accion? Sin dueno, ERROR EXPLICITO.
        #    Antes de M2.5 este caso devolvia la frase de exito del modelo y AURA afirmaba haber
        #    hecho algo que nadie hizo. Un exito sin evidencia de ejecucion queda prohibido.
        if adaptador is None:
            return self._error(accion, trace_id, origen, f"ninguna capacidad del sistema atiende '{accion}'")

        # 4. Ejecucion real, con los argumentos originales.
        try:
            resultado = await adaptador.execute(accion, args, trace_id, event_id)
        except ErrorDeValidacion as e:
            # El adaptador revalida en su propia puerta. Si rechaza, es un fallo, no un exito.
            return self._error(accion, trace_id, origen, f"el adaptador rechazo la operacion: {e}")
        except OSError as e:
            # Entre la confirmacion y la ejecucion el disco pudo cambiar. Un turno conversacional
            # no puede morir por eso: se informa el fallo y el sistema sigue en pie. La DoD de M2
            # exige cero errores NO RECUPERADOS; este queda recuperado y auditado.
            return self._error(accion, trace_id, origen, f"fallo del sistema de archivos: {e.strerror or e}")

        obs.log("AUTO", "ejecutor", f"[{origen}] ejecuto {accion}", trace_id, audit=True)
        return {"accion": accion, "estado": "ejecutada", "plan": plan, "resultado": resultado, "origen": origen}

    # -------------------------------------------------------------- salidas --

    def _detener(self, accion: str, tid: str, origen: str, motivo: str) -> dict:
        """La accion fue frenada por un control (permisos, dry-run): el gobierno funciono."""
        obs.log("AUTO", "ejecutor", f"[{origen}] DETENIDA {accion}: {motivo}", tid, audit=True)
        return {"accion": accion, "estado": "detenida", "motivo": motivo, "origen": origen}

    def _error(self, accion: str, tid: str, origen: str, motivo: str) -> dict:
        """No se pudo ni intentar. Se distingue de "detenida": aquello es gobierno, esto es un fallo."""
        obs.log("ERROR", "ejecutor", f"[{origen}] ERROR {accion}: {motivo}", tid, audit=True)
        return {"accion": accion, "estado": "error", "motivo": motivo, "origen": origen}
