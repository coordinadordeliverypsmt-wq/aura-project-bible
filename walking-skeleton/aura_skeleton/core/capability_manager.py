"""Capability Manager (C1, ADR-0021 / D45 / Bible 3.1 P-ARQ-9).

El UNICO componente autorizado para decidir el estado de una capacidad (regla permanente del CEO): ningun
modulo se autoactiva. Es **agnostico**: recibe SOLO un `PerfilEfectivo` (metricas de recursos y de pruebas
reales, D44) y produce un `PlanActivacion` determinista. Nunca inspecciona marcas, modelos ni sistema
operativo; esa inteligencia de deteccion es del futuro `DetectorPerfil`.

Reglas de decision (por capacidad):
- `prevista` (sin implementacion) -> LATENTE siempre (I6, D34/D38): no se finge capacidad no construida.
- `activable`: promocion -> ACTIVA; si no, degradacion -> DEGRADADA; si no -> LATENTE.
- Una activa/degradada cuya dependencia no esta disponible cae a LATENTE (I4), en cascada hasta punto fijo.
- Autonomia efectiva = techo declarado si opera (activa/degradada), OBSERVACION si latente. Nunca supera el
  techo ni escala con el hardware (I1, D33); el gate HITL sigue siendo la autoridad de lista roja.
El plan se emite en orden determinista (por nombre), independiente del orden de registro (I3).
"""

from __future__ import annotations

import operator
from collections.abc import Callable

from .capability_registry import CapabilityRegistry
from .capacidades import (
    Capacidad,
    Condicion,
    Decision,
    Estado,
    GradoLatencia,
    NivelAutonomia,
    Operador,
    PerfilEfectivo,
    PlanActivacion,
    Regla,
)

# Interpretacion de los operadores declarativos. La logica vive aqui (en el Manager), no en la Capacidad.
_OPS: dict[Operador, Callable[[float, float], bool]] = {
    Operador.GE: operator.ge,
    Operador.LE: operator.le,
    Operador.GT: operator.gt,
    Operador.LT: operator.lt,
    Operador.EQ: operator.eq,
}


def _cumple_condicion(c: Condicion, perfil: PerfilEfectivo) -> bool:
    return _OPS[c.operador](perfil.valor(c.fuente, c.metrica), c.valor)


def _cumple(regla: Regla | None, perfil: PerfilEfectivo) -> bool:
    """Interpreta una regla declarativa contra el perfil. Sin regla o sin condiciones -> no se cumple."""
    if regla is None or not regla.condiciones:
        return False
    return all(_cumple_condicion(c, perfil) for c in regla.condiciones)


class CapabilityManager:
    def __init__(self, registro: CapabilityRegistry) -> None:
        self._registro = registro

    def planificar(self, perfil: PerfilEfectivo) -> PlanActivacion:
        capacidades = sorted(self._registro.todas(), key=lambda c: c.nombre)

        # 1) Estado base por capacidad, sin resolver dependencias todavia.
        estado: dict[str, Estado] = {}
        motivo: dict[str, str] = {}
        for c in capacidades:
            e, m = self._estado_base(c, perfil)
            estado[c.nombre] = e
            motivo[c.nombre] = m

        # 2) Resolver dependencias: una activa/degradada cuya dependencia no opera cae a latente.
        #    Iterar hasta punto fijo (monotono: solo pasa cosas a LATENTE, luego converge).
        presentes = self._registro.nombres()
        cambio = True
        while cambio:
            cambio = False
            for c in capacidades:
                if estado[c.nombre] == Estado.LATENTE:
                    continue
                for dep in c.dependencias:
                    if dep not in presentes or estado[dep] == Estado.LATENTE:
                        estado[c.nombre] = Estado.LATENTE
                        motivo[c.nombre] = f"dependencia {dep!r} no disponible"
                        cambio = True
                        break

        # 3) Emitir decisiones con autonomia efectiva acotada (I1), en orden determinista.
        decisiones = tuple(
            Decision(
                nombre=c.nombre,
                estado=estado[c.nombre],
                autonomia_efectiva=self._autonomia_efectiva(c, estado[c.nombre]),
                motivo=motivo[c.nombre],
            )
            for c in capacidades
        )
        return PlanActivacion(decisiones)

    @staticmethod
    def _estado_base(c: Capacidad, perfil: PerfilEfectivo) -> tuple[Estado, str]:
        if c.latencia is GradoLatencia.PREVISTA:
            # I6: una capacidad prevista no se enciende aunque el perfil diera; no hay implementacion.
            return Estado.LATENTE, "capacidad prevista: sin implementacion, permanece latente"
        if _cumple(c.promocion, perfil):
            return Estado.ACTIVA, "criterio de promocion cumplido"
        if _cumple(c.degradacion, perfil):
            return Estado.DEGRADADA, "criterio de degradacion cumplido: opera en modo reducido"
        return Estado.LATENTE, "perfil insuficiente para promocion o degradacion"

    @staticmethod
    def _autonomia_efectiva(c: Capacidad, estado: Estado) -> NivelAutonomia:
        # Nunca supera el techo declarado (campo 10) ni escala con el hardware (I1/D33).
        if estado is Estado.LATENTE:
            return NivelAutonomia.OBSERVACION
        return c.autonomia_maxima
