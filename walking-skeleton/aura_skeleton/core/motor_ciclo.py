"""Motor del Ciclo: el latido de AURORA. La pieza que la convierte en un sistema que funciona solo.

POR QUE ERA EL CUELLO DE BOTELLA. Hasta ahora `DirectorGeneral.ciclo()` no lo invocaba NADIE en
`aura_skeleton/`: cada vuelta existia solo porque un modelo externo la pedia. AURORA tenia
coordinacion, verificacion y generacion de trabajo, y nada las ponia en marcha. Construir mas agentes
antes que esto habria agravado el problema: mas capacidad esperando un latido ajeno.

DELIBERADAMENTE MINIMO (CEO, 2026-08-03). Su UNICA responsabilidad es dar el siguiente latido. No
contiene logica de negocio, ni planificacion, ni decisiones: todas viven en el Director. Si algun dia
este modulo necesita saber que es una tarea, algo se ha puesto en el sitio equivocado.

RESPETA EL KILL SWITCH ANTES DE LATIR. La parada de emergencia se comprueba aqui, no solo dentro del
motor de ejecucion: un latido que arranca trabajo con el switch armado seria una ruta que lo esquiva,
que es exactamente lo que ALERTA-006 encontro en las rutas de mutacion (Bible 5.3 §5, RN-3).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .. import observability as obs

_ESPERA_SIN_TRABAJO_S = 30.0  # cuando no hay nada que hacer, no se gira en vacio quemando CPU


class MotorDelCiclo:
    """Da latidos al Director mientras haya trabajo y el sistema este operativo."""

    def __init__(
        self,
        director,
        kill_switch=None,
        espera_s: float = _ESPERA_SIN_TRABAJO_S,
        dormir: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.director = director
        self.kill_switch = kill_switch
        self.espera_s = espera_s
        # La espera se inyecta para que las pruebas no dependan del reloj real: un sistema cuyo
        # comportamiento solo puede observarse esperando de verdad no es auditable.
        self._dormir = dormir or asyncio.sleep

    def _detenido(self) -> bool:
        return self.kill_switch is not None and self.kill_switch.is_engaged()

    async def latir(self, objetivo_id: str, trace_id: str = "-"):
        """UN latido. Devuelve la tarea atendida, o None si no hubo trabajo o el sistema esta detenido."""
        if self._detenido():
            obs.log("CICLO", "motor-ciclo", "latido omitido: kill switch activo", trace_id, audit=True)
            return None
        return await self.director.ciclo(objetivo_id, trace_id)

    async def correr(self, objetivo_id: str, max_latidos: int | None = None, trace_id: str = "-") -> int:
        """Late hasta que no quede trabajo. Devuelve cuantas tareas se atendieron.

        `max_latidos` acota la corrida: es lo que permite ejercitar el bucle en una prueba sin
        depender de que termine solo, y sirve de red frente a un objetivo que se realimente.
        """
        atendidas = 0
        while max_latidos is None or atendidas < max_latidos:
            if self._detenido():
                obs.log("CICLO", "motor-ciclo", "ciclo detenido: kill switch activo", trace_id, audit=True)
                break
            tarea = await self.director.ciclo(objetivo_id, trace_id)
            if tarea is None:
                break  # sin trabajo accionable: se para, no se gira en vacio
            atendidas += 1
        obs.log("CICLO", "motor-ciclo", f"corrida terminada: {atendidas} tarea(s) atendidas", trace_id, audit=True)
        return atendidas

    async def servir(self, objetivo_id: str, trace_id: str = "-") -> None:
        """Bucle permanente: trabaja mientras haya tareas y espera cuando no las hay.

        No termina por si solo: se detiene cancelando la tarea asincrona o armando el kill switch. Esa
        es la diferencia entre `correr` (una corrida acotada) y el latido continuo de un sistema vivo.
        """
        while True:
            if self._detenido():
                await self._dormir(self.espera_s)
                continue
            if await self.director.ciclo(objetivo_id, trace_id) is None:
                await self._dormir(self.espera_s)
