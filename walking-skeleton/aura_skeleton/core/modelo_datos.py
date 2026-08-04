"""Verificador del MODELO DE DATOS FUNDAMENTAL del Sistema Operativo Interno.

EL PRINCIPIO QUE HACE CUMPLIR (descubierto por convergencia, no decidido de antemano):
**la unica informacion persistente con valor semantico es el historial de eventos.** Todo lo demas
—caches, snapshots, indices, proyecciones, metricas— puede existir, pero NUNCA como segunda fuente de
verdad. El criterio que separa una optimizacion de una fuente de verdad lo fijo el CEO: *un snapshot
debe poder eliminarse por completo y regenerarse desde el historial sin alterar el comportamiento*.

Por que existe este modulo y no una ADR todavia: en este proyecto las mejores decisiones no se
aprobaron por parecer correctas, sino porque el sistema convergio hacia ellas. La garantia va primero;
la ADR describira despues una propiedad que el sistema ya sabe verificar por si mismo.

ES GENERICO A PROPOSITO. No verifica el Estado Operativo: verifica *un componente cualquiera* descrito
por cuatro funciones. Sirve igual para Automatizaciones, Memoria, o cualquier componente futuro.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CUMPLE = "cumple"
CON_EXCEPCIONES = "cumple con excepciones justificadas"
VIOLA = "viola el principio"


@dataclass
class Componente:
    """Descripcion minima de un componente para poder verificarlo."""

    nombre: str
    construir: Callable[[str], Any]  # (ruta) -> instancia nueva que solo conoce la ruta
    operar: Callable[[Any], None]  # ejercita el componente (escribe, borra, marca...)
    observar: Callable[[Any], Any]  # comportamiento observable, comparable con ==
    proyeccion: Callable[[Any], Any]  # el estado derivado en memoria
    # Operacion que RETIRA informacion (borrar, marcar, desactivar). Es la que revela la direccion del
    # flujo: si el historial DECRECE al retirar, el fichero se genero desde la proyeccion y no al reves.
    retirar: Callable[[Any], None] | None = None
    excepcion_justificada: str = ""  # si esta declarada, un incumplimiento no se reporta como violacion


@dataclass
class Veredicto:
    componente: str
    clasificacion: str
    comprobaciones: dict[str, bool] = field(default_factory=dict)
    detalle: str = ""

    @property
    def fallidas(self) -> list[str]:
        return [k for k, v in self.comprobaciones.items() if not v]


def verificar(comp: Componente, ruta: str) -> Veredicto:
    """Ejecuta las cinco comprobaciones del principio sobre un componente real."""
    p = Path(ruta)
    inst = comp.construir(ruta)
    comp.operar(inst)

    c: dict[str, bool] = {}
    detalle = ""

    # 1. ¿Existe una unica fuente de verdad PERSISTENTE?
    c["fuente de verdad persistente"] = p.exists()
    if not p.exists():
        return Veredicto(comp.nombre, VIOLA, c, "el componente no persiste nada: no hay historial")

    lineas_tras_operar = _lineas(p)

    # Se ejercita la retirada ANTES de medir: es el unico momento en que se distingue un historial
    # append-only de un volcado de la proyeccion. Sin esta fase, ambos son indistinguibles.
    if comp.retirar is not None:
        comp.retirar(inst)
    lineas_tras_retirar = _lineas(p)
    esperado = comp.observar(inst)

    # 2. ¿Puede ELIMINARSE por completo la proyeccion? Se descarta la instancia entera: la proyeccion
    #    vive en memoria, asi que soltarla es la forma honesta de borrarla.
    del inst
    c["proyeccion eliminable"] = True

    # 3. ¿Puede RECONSTRUIRSE desde la fuente de verdad, sin mas contexto que la ruta?
    try:
        reconstruido = comp.construir(ruta)
        c["reconstruible desde la fuente"] = True
    except Exception as e:  # noqa: BLE001 - cualquier fallo aqui es un incumplimiento, no un error
        c["reconstruible desde la fuente"] = False
        return Veredicto(comp.nombre, VIOLA, c, f"no se pudo reconstruir: {e}")

    # 4. ¿El comportamiento reconstruido es INDISTINGUIBLE del original?
    obtenido = comp.observar(reconstruido)
    c["comportamiento indistinguible"] = obtenido == esperado
    if obtenido != esperado:
        detalle = f"tras reconstruir cambia el comportamiento: {esperado!r} -> {obtenido!r}"

    # 5. ¿Hay informacion que SOLO viva en la proyeccion? Se detecta por la direccion del flujo: si
    #    operar hizo PERDER lineas al historial, el fichero se genero DESDE la proyeccion y no al
    #    reves. Ese es el sintoma de que la fuente de verdad y la proyeccion estan invertidas.
    c["nada vive solo en la proyeccion"] = lineas_tras_retirar >= lineas_tras_operar

    if all(c.values()):
        return Veredicto(comp.nombre, CUMPLE, c, detalle)
    if comp.excepcion_justificada:
        return Veredicto(comp.nombre, CON_EXCEPCIONES, c, comp.excepcion_justificada)
    return Veredicto(comp.nombre, VIOLA, c, detalle or "; ".join(f"falla: {k}" for k in c if not c[k]))


def _lineas(p: Path) -> int:
    return len([x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()])


def informe(veredictos: list[Veredicto]) -> str:
    filas = [f"{'COMPONENTE':<26} {'CLASIFICACION':<38} COMPROBACION FALLIDA", "-" * 100]
    for v in veredictos:
        fallo = v.fallidas[0] if v.fallidas else "—"
        filas.append(f"{v.componente:<26} {v.clasificacion:<38} {fallo}")
        if v.detalle:
            filas.append(f"{'':<26} └─ {v.detalle[:70]}")
    return "\n".join(filas)
