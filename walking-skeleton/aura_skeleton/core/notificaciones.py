"""Centro unico de notificaciones (M2.4, Bible 6.4 §3).

Consolida y prioriza notificaciones de las fuentes del MVP, reduce ruido y permite actuar desde un
solo lugar. Tres restricciones lo gobiernan:

1. **Fuentes cerradas al MVP** (2.2 §4.4): computador principal, Home Assistant y la propia AURA.
   Android y NAS quedan fuera hasta R2. Se rechaza toda fuente no declarada: un centro que acepta
   cualquier origen es un canal de entrada sin control.

2. **Actuar desde el centro NO es un atajo** (riesgo RN-5). Una accion lanzada desde una
   notificacion recorre exactamente el mismo camino que cualquier otra: Permisos, catalogo,
   dry-run si altera estado. El centro no ejecuta nada por su cuenta.

3. **Contenido de terceros con alcance de sesion** (ALERTA-002). El cuerpo de una notificacion puede
   incluir informacion de otra persona. Esa informacion es contextual a la sesion y no se convierte
   en historial persistente: al cerrar sesion se purga el contenido, conservando solo el hecho de
   que hubo una notificacion.
"""

from __future__ import annotations

import hashlib
import time

from .. import observability as obs

FUENTES_MVP = ("computador", "home_assistant", "aura")

PRIORIDADES = {"critica": 0, "alta": 1, "normal": 2, "baja": 3}


class FuenteNoPermitida(Exception):
    """La fuente no pertenece al MVP (2.2 §4.4)."""


class Notificacion:
    def __init__(
        self,
        fuente: str,
        titulo: str,
        cuerpo: str = "",
        prioridad: str = "normal",
        contiene_terceros: bool = False,
        ts: float | None = None,
    ) -> None:
        if fuente not in FUENTES_MVP:
            raise FuenteNoPermitida(f"fuente fuera del MVP: {fuente!r} (permitidas: {FUENTES_MVP})")
        if prioridad not in PRIORIDADES:
            raise ValueError(f"prioridad desconocida: {prioridad!r}")
        self.fuente = fuente
        self.titulo = titulo
        self.cuerpo = cuerpo
        self.prioridad = prioridad
        self.contiene_terceros = contiene_terceros
        self.ts = ts if ts is not None else time.time()
        self.purgada = False

    @property
    def huella(self) -> str:
        """Identidad para deduplicar: misma fuente y mismo titulo son la misma notificacion."""
        return hashlib.sha256(f"{self.fuente}|{self.titulo}".encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        return f"<Notificacion {self.fuente}:{self.titulo!r} {self.prioridad}>"


class CentroNotificaciones:
    def __init__(self, adaptador=None, permisos=None, motor=None) -> None:
        self.adaptador = adaptador
        self.permisos = permisos
        self.motor = motor  # se reutiliza el motor de M2.3 para el dry-run obligatorio
        self._items: list[Notificacion] = []
        self.suprimidas = 0

    # ------------------------------------------------------------ ingesta --

    def recibir(self, n: Notificacion) -> bool:
        """Devuelve False si se suprimio por duplicada (reduccion de ruido, 6.4 §3)."""
        if any(x.huella == n.huella and not x.purgada for x in self._items):
            self.suprimidas += 1
            return False
        self._items.append(n)
        return True

    def listar(self) -> list[Notificacion]:
        """Prioriza: primero por criticidad, despues las mas recientes."""
        return sorted(self._items, key=lambda n: (PRIORIDADES[n.prioridad], -n.ts))

    # ---------------------------------------------------------- privacidad --

    def cerrar_sesion(self) -> int:
        """Purga el contenido de terceros (ALERTA-002: alcance de sesion).

        Se conserva la notificacion como hecho —fuente, momento, prioridad— pero se elimina el
        cuerpo. Asi el usuario mantiene su historial de actividad sin que AURA acumule un historial
        personal de otras personas entre sesiones.
        """
        n = 0
        for item in self._items:
            if item.contiene_terceros and not item.purgada:
                item.cuerpo = ""
                item.purgada = True
                n += 1
        obs.log("PRIV", "notificaciones", f"purgado contenido de terceros: {n} notificacion(es)", "-", audit=True)
        return n

    # ------------------------------------------------------------- accion --

    async def actuar(self, notificacion: Notificacion, accion: str, args: dict, trace_id: str) -> dict:
        """Actuar desde el centro recorre el MISMO camino que cualquier otra accion.

        No hay ejecucion directa: se delega en el motor de automatizacion, que impone dry-run
        obligatorio para lo que altere estado y exige confirmacion para la lista roja. Sin esta
        delegacion, el centro de notificaciones seria una puerta trasera al sistema de archivos.
        """
        if self.motor is None:
            raise RuntimeError("el centro no puede actuar sin motor: no existe ejecucion directa")
        from .automatizacion import Regla

        regla = Regla(f"notificacion:{notificacion.huella}", "notificacion", accion, args)
        ev = _EventoSintetico(trace_id, notificacion.huella)
        return await self.motor.disparar(regla, ev)


class _EventoSintetico:
    """Portador minimo de trace_id/event_id para reutilizar el motor sin publicar en el bus."""

    def __init__(self, trace_id: str, event_id: str) -> None:
        self.trace_id = trace_id
        self.event_id = event_id
        self.type = "notificacion"
        self.payload: dict = {}
