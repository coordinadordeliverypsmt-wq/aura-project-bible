"""Registro de Capacidades (C1, ADR-0021 §2.4).

Almacen autodeclarativo de capacidades-subsistema: una capacidad, un nombre. Es la **fuente unica** de la
clasificacion de capacidades (D41). NO decide estados: eso es competencia exclusiva del CapabilityManager
(regla permanente del CEO). Aqui solo se guardan y consultan declaraciones.

**Agnostico del origen (CEO, 2026-07-26):** recibe declaraciones `Capacidad` YA construidas; no conoce su
procedencia. Hoy el catalogo vive en codigo, pero un cargador externo y futuro podria construir las
`Capacidad` desde JSON, YAML, base de datos o un repositorio remoto sin que el Registry —ni el Manager, que
solo recibe el Registry— lo sepan. Esa carga es responsabilidad de otro componente; asi se preserva la
independencia tecnologica (patron DetectorPerfil -> CapabilityRegistry -> CapabilityManager -> PlanActivacion).
"""

from __future__ import annotations

from collections.abc import Iterable

from .capacidades import Capacidad


class CapacidadDuplicada(Exception):
    """Dos capacidades declaran el mismo nombre (ambiguedad no resoluble)."""


class CapabilityRegistry:
    def __init__(self, capacidades: Iterable[Capacidad] = ()) -> None:
        self._por_nombre: dict[str, Capacidad] = {}
        for c in capacidades:
            self.registrar(c)

    def registrar(self, capacidad: Capacidad) -> None:
        if capacidad.nombre in self._por_nombre:
            raise CapacidadDuplicada(f"la capacidad {capacidad.nombre!r} ya esta registrada")
        self._por_nombre[capacidad.nombre] = capacidad

    def obtener(self, nombre: str) -> Capacidad | None:
        return self._por_nombre.get(nombre)

    def todas(self) -> tuple[Capacidad, ...]:
        return tuple(self._por_nombre.values())

    def nombres(self) -> set[str]:
        return set(self._por_nombre)
