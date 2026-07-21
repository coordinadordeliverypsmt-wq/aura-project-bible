"""Registro de adaptadores (M2.5, ALERTA-005).

Antes de esta pieza el orquestador tenia un unico adaptador cableado a mano (`self.ha`) y
comprobaba `action in self.ha.capabilities`. Consecuencia: los adaptadores construidos en M2 eran
inalcanzables desde la conversacion, y una accion sin adaptador capaz se reportaba como exito.

El registro resuelve **quien atiende cada capacidad**. Dos reglas lo gobiernan:

1. **Una capacidad, un dueno.** Si dos adaptadores declaran la misma, se rechaza al registrar. Una
   ambiguedad resuelta en tiempo de ejecucion —por orden de insercion, por ejemplo— seria una
   decision invisible sobre que codigo toca los datos del usuario.

2. **Sin dueno no hay ejecucion, y el hecho se declara.** `para()` devuelve None y quien llama debe
   producir un error explicito. Nunca un exito silencioso: esa fue precisamente la parte mas grave
   de ALERTA-005.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..contracts import Adapter


class CapacidadDuplicada(Exception):
    """Dos adaptadores declaran la misma capacidad (ambiguedad no resoluble)."""


class RegistroAdaptadores:
    def __init__(self, adaptadores: Iterable[Adapter] = ()) -> None:
        self._por_capacidad: dict[str, Adapter] = {}
        self._adaptadores: list[Adapter] = []
        for a in adaptadores:
            self.registrar(a)

    def registrar(self, adaptador: Adapter) -> None:
        for cap in adaptador.capabilities:
            dueno = self._por_capacidad.get(cap)
            if dueno is not None:
                raise CapacidadDuplicada(
                    f"la capacidad {cap!r} ya la atiende {dueno.name!r}; la reclama {adaptador.name!r}"
                )
            self._por_capacidad[cap] = adaptador
        self._adaptadores.append(adaptador)

    def para(self, accion: str) -> Adapter | None:
        """Adaptador que atiende `accion`, o None. Quien llama DEBE tratar el None como error."""
        return self._por_capacidad.get(accion)

    def capacidades(self) -> set[str]:
        return set(self._por_capacidad)

    @property
    def adaptadores(self) -> list[Adapter]:
        return list(self._adaptadores)
