"""Marco generico de habilitacion y transparencia de conectores externos (MA.4, ADR-0019, D37).

Sin logica de ningun proveedor concreto: el Core **no gana conocimiento especifico de fuentes**
(ADR-0015). Un conector se auto-declara `externo`; los externos se activan SOLO por opt-in del usuario
y deben declarar el recorrido de sus datos. Ningun conector externo es requisito: la degradacion limpia
ya la garantiza `RegistroContexto` (ADR-0015). Este modulo se demuestra con un DOBLE; no construye,
simula ni integra ningun conector real.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

ESQUEMA_TRANSPARENCIA = 1  # version del contrato; futuros ADR lo amplian de forma aditiva (ADR-0004 regla 11)


@dataclass(frozen=True)
class DeclaracionTransparencia:
    """Contrato ESTABLE del recorrido de datos de un conector externo (esquema generico y versionado).

    Su CONTENIDO lo fija el ADR propio de cada conector futuro; aqui solo el esquema. Es ampliable sin
    romper compatibilidad: los campos nuevos se anaden con valor por defecto (regla 11).
    """

    destino: str
    proposito: str
    datos_locales: tuple[str, ...] = ()
    datos_que_salen: tuple[str, ...] = ()
    version_esquema: int = ESQUEMA_TRANSPARENCIA


@dataclass(frozen=True)
class Habilitacion:
    """Resultado del gate: proveedores activos, nombres rechazados y el informe de transparencia."""

    activos: tuple[Any, ...]
    rechazados: tuple[str, ...]
    informe: str


def es_externo(proveedor: Any) -> bool:
    """Un conector es externo solo si lo declara. Atributo generico: el Core no hardcodea fuentes (ADR-0015)."""
    return bool(getattr(proveedor, "externo", False))


def _linea(proveedor: Any) -> str:
    d = proveedor.transparencia
    return (
        f"{proveedor.nombre}: sale [{', '.join(d.datos_que_salen)}] -> {d.destino} "
        f"({d.proposito}); local [{', '.join(d.datos_locales)}]"
    )


def habilitar(proveedores: Iterable[Any], habilitados: frozenset[str]) -> Habilitacion:
    """Aplica las condiciones de D37 a una lista de proveedores.

    - LOCALES: siempre activos (no dependen del opt-in).
    - EXTERNOS: activos solo si (a) declaran su transparencia y (b) su nombre esta en `habilitados`
      (opt-in del usuario). En otro caso, rechazados.
    El informe es determinista: externos activos ordenados por nombre, independiente del orden de entrada.
    """
    activos: list[Any] = []
    rechazados: list[str] = []
    for p in proveedores:
        if not es_externo(p):
            activos.append(p)  # local: siempre activo
            continue
        if not isinstance(getattr(p, "transparencia", None), DeclaracionTransparencia):
            rechazados.append(p.nombre)  # externo sin transparencia: no se habilita (D37.2)
            continue
        if p.nombre not in habilitados:
            rechazados.append(p.nombre)  # no habilitado por el usuario: apagado por defecto (D37.1)
            continue
        activos.append(p)
    externos_activos = sorted((p for p in activos if es_externo(p)), key=lambda p: p.nombre)
    informe = "\n".join(_linea(p) for p in externos_activos)
    return Habilitacion(tuple(activos), tuple(sorted(rechazados)), informe)
