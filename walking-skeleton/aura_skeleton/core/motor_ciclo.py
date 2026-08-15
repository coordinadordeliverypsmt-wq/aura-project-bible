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

# N razonable (CEO, PIEZA 1): absorbe fallos TRANSITORIOS (disco lento, contienda momentanea) sin
# permitir que un demonio sin supervision gire para siempre sobre un fallo ESTRUCTURAL quemando CPU en
# un equipo modesto (Celeron). Ni tan bajo que dos fallos sueltos tumben el servicio, ni tan alto que
# tarde minutos en notar que algo esta roto de verdad. Sin este limite, "no morir en silencio" se
# resolveria cambiando un silencio por otro: un bucle que nunca para tampoco deja rastro util.
_MAX_FALLOS_CONSECUTIVOS = 5


class FallosConsecutivosExcedidos(Exception):
    """El servicio se detuvo: `_MAX_FALLOS_CONSECUTIVOS` latidos seguidos fallaron.

    Detenerse asi es RUIDOSO a proposito (excepcion + registro de auditoria), nunca silencioso: un
    demonio que muere sin dejar rastro es el defecto que este incremento corrige, y "seguir girando
    para siempre" seria la misma clase de defecto con otra forma.
    """


class MotorDelCiclo:
    """Da latidos al Director mientras haya trabajo y el sistema este operativo."""

    def __init__(
        self,
        director,
        kill_switch=None,
        espera_s: float = _ESPERA_SIN_TRABAJO_S,
        dormir: Callable[[float], Awaitable[None]] | None = None,
        al_despertar: Callable[[], int] | None = None,
    ) -> None:
        self.director = director
        self.kill_switch = kill_switch
        self.espera_s = espera_s
        # Gancho que corre ANTES de cada latido. Existe para una sola cosa hoy: devolver al trabajo
        # las tareas cuya decision aprobo el CEO en el buzon mientras AURORA seguia con lo demas
        # (Pieza 2). Se inyecta en vez de importarse para que el motor siga sin conocer el buzon: su
        # unica responsabilidad es dar el siguiente latido.
        self._al_despertar = al_despertar
        # La espera se inyecta para que las pruebas no dependan del reloj real: un sistema cuyo
        # comportamiento solo puede observarse esperando de verdad no es auditable.
        self._dormir = dormir or asyncio.sleep

    def _detenido(self) -> bool:
        return self.kill_switch is not None and self.kill_switch.is_engaged()

    def _despertar(self, trace_id: str) -> None:
        """Aplica lo que haya cambiado fuera mientras AURORA trabajaba. Un fallo aqui no puede tumbar
        el latido: el trabajo debe seguir aunque el buzon este ilegible."""
        if self._al_despertar is None:
            return
        try:
            reabiertas = self._al_despertar()
        except Exception as e:  # noqa: BLE001 -- el latido sobrevive a cualquier fallo del gancho
            obs.log("WARN", "motor-ciclo", f"el gancho de despertar fallo: {e}", trace_id, audit=True)
            return
        if reabiertas:
            obs.log(
                "CICLO", "motor-ciclo", f"{reabiertas} tarea(s) reabiertas por decision del CEO", trace_id, audit=True
            )

    async def latir(self, objetivo_id: str, trace_id: str = "-"):
        """UN latido. Devuelve la tarea atendida, o None si no hubo trabajo o el sistema esta detenido."""
        if self._detenido():
            obs.log("CICLO", "motor-ciclo", "latido omitido: kill switch activo", trace_id, audit=True)
            return None
        self._despertar(trace_id)
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
            self._despertar(trace_id)
            tarea = await self.director.ciclo(objetivo_id, trace_id)
            if tarea is None:
                break  # sin trabajo accionable: se para, no se gira en vacio
            atendidas += 1
        obs.log("CICLO", "motor-ciclo", f"corrida terminada: {atendidas} tarea(s) atendidas", trace_id, audit=True)
        return atendidas

    async def servir(self, objetivo_id: str, trace_id: str = "-") -> None:
        """Bucle permanente: trabaja mientras haya tareas y espera cuando no las hay.

        No termina por si solo: se detiene cancelando la tarea asincrona, armando el kill switch, o
        agotando `_MAX_FALLOS_CONSECUTIVOS` latidos seguidos en error (`FallosConsecutivosExcedidos`).
        Esa es la diferencia entre `correr` (una corrida acotada, vigilada en el momento por quien la
        invoca) y el latido continuo de un sistema vivo: aqui nadie esta mirando en tiempo real, asi
        que una excepcion de `director.ciclo` que antes mataba el bucle EN SILENCIO ahora queda
        registrada en el audit log y el servicio sigue con el siguiente latido -- salvo que el fallo
        sea persistente, en cuyo caso se detiene de forma RUIDOSA en vez de girar para siempre.
        """
        fallos_consecutivos = 0
        while True:
            if self._detenido():
                await self._dormir(self.espera_s)
                continue
            try:
                self._despertar(trace_id)
                tarea = await self.director.ciclo(objetivo_id, trace_id)
            except Exception as e:
                fallos_consecutivos += 1
                obs.log(
                    "ERROR",
                    "motor-ciclo",
                    f"latido fallido ({fallos_consecutivos}/{_MAX_FALLOS_CONSECUTIVOS}): {type(e).__name__}: {e}",
                    trace_id,
                    audit=True,
                )
                if fallos_consecutivos >= _MAX_FALLOS_CONSECUTIVOS:
                    obs.log(
                        "ERROR",
                        "motor-ciclo",
                        f"servicio detenido: {fallos_consecutivos} latidos consecutivos fallaron",
                        trace_id,
                        audit=True,
                    )
                    raise FallosConsecutivosExcedidos(
                        f"{fallos_consecutivos} latidos consecutivos fallaron; ultimo error: {type(e).__name__}: {e}"
                    ) from e
                # No se reintenta en caliente sobre un fallo persistente: la misma espera que evita
                # girar en vacio sin trabajo evita tambien girar en vacio sobre un error que se repite.
                await self._dormir(self.espera_s)
                continue
            fallos_consecutivos = 0  # un latido en verde corta cualquier racha de fallos previa
            if tarea is None:
                await self._dormir(self.espera_s)
            else:
                obs.log("CICLO", "motor-ciclo", "latido con trabajo atendido", trace_id, audit=True)
