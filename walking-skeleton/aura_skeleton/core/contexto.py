"""Registro de proveedores de contexto (M3.0, decision de arquitectura del CEO 2026-07-21).

> *"Toda captura de senales debera implementarse mediante un sistema de conectores o proveedores de
> contexto. M3 solo instrumentara las fuentes actuales (conversacion, PC y Home Assistant), pero la
> arquitectura debera permitir incorporar posteriormente camaras, wearables, sensores biometricos y
> otros dispositivos sin modificar el nucleo del sistema."*

La consecuencia de diseno es que **el nucleo no conoce ninguna fuente concreta**. No hay en este
modulo —ni debe haberlo nunca— una lista de fuentes admitidas, un `if fuente == "camara"` ni un
import de un conector. El nucleo sabe que existen proveedores y que producen senales; qué proveedores
existan es configuracion, no codigo del Core.

Es el mismo principio que el `RegistroAdaptadores` de M2.5 aplicado a la entrada de datos en lugar
de a la salida de acciones: **una fuente, un dueno; sin dueno, nada ocurre en silencio.**

Diferencia deliberada con aquel: aqui **un proveedor que falla no interrumpe a los demas**. Un
adaptador que falla debe detener la accion —el usuario espera un efecto—; un sensor que se
desconecta no puede dejar ciego al sistema entero. La leccion viene de M2, donde un `OSError`
propagado desde un adaptador derribaba el turno completo.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from .. import observability as obs
from .senales import Senal


@runtime_checkable
class ProveedorContexto(Protocol):
    """Contrato de una fuente de senales. Lo cumple cualquier conector, presente o futuro.

    `recoger` devuelve las senales observadas desde la ultima llamada. Es **pasivo por contrato**:
    un proveedor observa y reporta, nunca actua sobre el sistema ni decide nada (restriccion 2).
    """

    nombre: str

    async def recoger(self, trace_id: str) -> list[Senal]: ...


class FuenteDuplicada(Exception):
    """Dos proveedores comparten nombre: la procedencia de sus senales seria ambigua."""


class RegistroContexto:
    def __init__(self, proveedores: Iterable[ProveedorContexto] = ()) -> None:
        self._proveedores: list[ProveedorContexto] = []
        self.fuentes_con_error: list[str] = []
        for p in proveedores:
            self.registrar(p)

    def registrar(self, proveedor: ProveedorContexto) -> None:
        if any(p.nombre == proveedor.nombre for p in self._proveedores):
            raise FuenteDuplicada(f"ya existe un proveedor llamado {proveedor.nombre!r}")
        self._proveedores.append(proveedor)

    def observar(self, texto: str) -> None:
        """Ofrece un enunciado a los proveedores que sepan observar conversacion.

        Los proveedores que no observan texto —una camara, un wearable— simplemente no implementan
        `observar`: el nucleo no necesita saber de que tipo es cada fuente.
        """
        for p in self._proveedores:
            observador = getattr(p, "observar", None)
            if observador is not None:
                observador(texto)

    async def recoger_todas(self, trace_id: str) -> list[Senal]:
        """Recoge de todas las fuentes. Una fuente caida degrada la captura, no la derriba."""
        self.fuentes_con_error = []
        senales: list[Senal] = []
        for p in self._proveedores:
            try:
                senales.extend(await p.recoger(trace_id))
            except Exception as e:
                # Un sensor desconectado es una condicion del entorno, no un error de programa.
                self.fuentes_con_error.append(p.nombre)
                obs.log("CTX", "contexto", f"fuente '{p.nombre}' no disponible: {e}", trace_id)
        return senales

    @property
    def fuentes(self) -> list[str]:
        return [p.nombre for p in self._proveedores]
