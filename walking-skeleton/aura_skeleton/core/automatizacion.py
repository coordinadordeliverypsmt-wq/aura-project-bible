"""Motor de automatizacion con dry-run obligatorio (M2.3, Bible 6.4 §2).

Este modulo introduce el primer punto del proyecto donde AURA actua **sin un humano delante**: una
regla dispara cuando ocurre un evento, no cuando alguien lo pide. De ahi las tres restricciones que
gobiernan cada disparo:

1. **Dry-run obligatorio** para toda accion que altere el estado. Sin plan previo no hay ejecucion.
2. **Toda accion pasa por Permisos**, incluidas las verdes. Ademas de aplicar las listas, es lo que
   hace que el kill switch alcance al motor de reglas y no solo al turno conversacional (RN-3).
3. **Las acciones de lista roja exigen confirmacion con la previsualizacion delante.** Confirmar a
   ciegas una accion destructiva no es consentimiento informado.

Las automatizaciones son **definidas por el usuario** (M2). Las sugeridas llegan en M3 (4.4).
"""

from __future__ import annotations

from collections.abc import Callable

from .. import observability as obs
from ..contracts import Event
from .operaciones import ErrorDeValidacion


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
    def __init__(self, adaptador, permisos, altera: Callable[[str], bool]) -> None:
        self.adaptador = adaptador
        self.permisos = permisos
        self._altera = altera  # inyectado: el motor no decide que altera, lo consulta al catalogo
        self.reglas: list[Regla] = []
        self.ejecutadas: list[dict] = []

    def agregar(self, regla: Regla) -> None:
        self.reglas.append(regla)

    async def on_event(self, ev: Event) -> None:
        for regla in self.reglas:
            if regla.aplica(ev):
                await self.disparar(regla, ev)

    async def disparar(self, regla: Regla, ev: Event) -> dict:
        tid = ev.trace_id
        plan = None

        # 1. Dry-run OBLIGATORIO si la accion altera el estado. Es condicion previa, no un extra:
        #    sin plan viable, la ejecucion no se intenta siquiera.
        if self._altera(regla.accion):
            if not hasattr(self.adaptador, "simular"):
                return self._rechazar(regla, tid, "el adaptador no soporta dry-run y la accion altera el estado")
            try:
                plan = await self.adaptador.simular(regla.accion, regla.args, tid)
            except ErrorDeValidacion as e:
                return self._rechazar(regla, tid, f"dry-run rechazo la operacion: {e}")
            if not plan.get("viable"):
                return self._rechazar(regla, tid, f"dry-run no viable: {plan.get('motivo')}")

        # 2. TODA accion pasa por Permisos. La previsualizacion viaja con la peticion para que la
        #    confirmacion sea informada; se pasa SOLO a Permisos, nunca al adaptador, que rechaza
        #    argumentos no declarados.
        contexto = dict(regla.args)
        if plan is not None:
            contexto["_previsualizacion"] = plan.get("efecto")
        ok, motivo = await self.permisos.authorize(regla.accion, contexto, tid)
        if not ok:
            return self._rechazar(regla, tid, f"permisos: {motivo}")

        # 3. Ejecucion real, con los argumentos originales.
        resultado = await self.adaptador.execute(regla.accion, regla.args, tid, f"auto-{regla.nombre}-{ev.event_id}")
        registro = {"regla": regla.nombre, "accion": regla.accion, "estado": "ejecutada", "plan": plan}
        self.ejecutadas.append(registro)
        obs.log("AUTO", "automatizacion", f"regla '{regla.nombre}' ejecuto {regla.accion}", tid, audit=True)
        return {**registro, "resultado": resultado}

    def _rechazar(self, regla: Regla, tid: str, motivo: str) -> dict:
        registro = {"regla": regla.nombre, "accion": regla.accion, "estado": "detenida", "motivo": motivo}
        self.ejecutadas.append(registro)
        obs.log("AUTO", "automatizacion", f"regla '{regla.nombre}' DETENIDA: {motivo}", tid, audit=True)
        return registro
