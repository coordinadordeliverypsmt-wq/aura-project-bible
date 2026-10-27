"""Lado NODO de la delegación: aceptar una orden firmada, acusar y ejecutar (A1/A2/N7/M5/M-3). Módulo PURO.

Flujo: `aceptar` valida la orden (firma sobre bytes exactos, destinatario, capacidad LOCAL, esquema, frescura) y la
consume de forma durable; devuelve el acuse FIRMADO. `ejecutar` corre la capacidad desde la TABLA fija
(`core.delegacion.CAPACIDADES`; nunca `exec`, shell ni interpolación) y devuelve el resultado FIRMADO ligado por
`hash_tarea` a los bytes de la orden. El nodo NO tiene autoridad: lo que declara lo valida después HC-1.

Estados persistentes por `id_ejecucion` (M-3): CONSUMIDA -> EJECUTANDO -> COMPLETADA (resultado firmado guardado) |
FALLIDA. `ejecutar` solo corre UNA vez por orden (aunque se llame dos veces sobre la misma instancia, o desde dos
procesos): la segunda llamada se rechaza. Tras un reinicio, una ejecución EJECUTANDO sin COMPLETADA es AMBIGUA y no se
re-ejecuta sola; si estaba COMPLETADA, `reenviar_resultado` devuelve el MISMO resultado firmado (idempotente).

La firma se inyecta (`Firmar`): este módulo no conoce claves. La delegación real sigue DESHABILITADA: nada de esto
está cableado al agente de producción.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .delegacion import (
    CAPACIDADES,
    DOMINIO_ACUSE,
    DOMINIO_RESULTADO,
    AlmacenOrdenes,
    EstadoNodo,
    Motivo,
    OrdenValida,
    PoliticaNodo,
    RechazoOrden,
    Verificador,
    payload_acuse,
    payload_resultado,
    revalidar_para_ejecutar,
    validar_orden,
)

Firmar = Callable[[bytes, bytes], bytes]
"""(dominio, payload) -> sobre firmado."""


class AlmacenNodo(AlmacenOrdenes, Protocol):
    """Almacén durable del nodo: consumo de órdenes + estados de ejecución."""

    def iniciar_ejecucion(self, id_ejecucion: str) -> None: ...
    def completar(self, id_ejecucion: str, resultado_firmado: bytes) -> None: ...
    def fallar(self, id_ejecucion: str) -> None: ...
    def estado(self, id_ejecucion: str) -> EstadoNodo | None: ...
    def resultado_guardado(self, id_ejecucion: str) -> bytes | None: ...
    def hash_consumido(self, id_ejecucion: str) -> str | None: ...


@dataclass(frozen=True)
class OrdenAceptada:
    orden: OrdenValida
    acuse: bytes
    """Sobre del acuse firmado por el nodo (N7)."""


class NodoDelegado:
    def __init__(self, politica: PoliticaNodo, verificar: Verificador, almacen: AlmacenNodo, firmar: Firmar) -> None:
        self._politica = politica
        self._verificar = verificar
        self._almacen = almacen
        self._firmar = firmar

    def aceptar(self, sobre: bytes) -> OrdenAceptada:
        """Lanza `RechazoOrden` (catálogo cerrado) si la orden no es aceptable; no ejecuta nada."""
        orden = validar_orden(sobre, politica=self._politica, verificar=self._verificar, almacen=self._almacen)
        acuse = self._firmar(DOMINIO_ACUSE, payload_acuse(orden, self._politica.id_nodo, self._politica.reloj.ahora()))
        return OrdenAceptada(orden, acuse)

    def ejecutar(self, orden: OrdenValida) -> bytes:
        """Ejecuta la capacidad REGISTRADA (ya validada en `aceptar`) UNA sola vez y devuelve el resultado firmado.

        Marca EJECUTANDO de forma durable antes de correr nada: una segunda llamada (misma instancia, otra instancia u
        otro proceso) lanza `RechazoOrden(EJECUCION_REPETIDA|EJECUCION_AMBIGUA)` y no ejecuta."""
        ident = orden.campos["id_ejecucion"]
        revalidar_para_ejecutar(self._politica, orden)  # caducidad, revocación y coherencia, ANTES de marcar nada
        if self._almacen.hash_consumido(ident) != orden.hash_tarea:
            raise RechazoOrden(Motivo.VINCULO_ROTO, "la orden no es la consumida")
        self._almacen.iniciar_ejecucion(ident)
        try:
            cap = CAPACIDADES[orden.campos["capacidad"]]
            salida = cap.ejecutar(cap.validar_argumentos(orden.campos["argumentos"]))
            resultado = self._firmar(DOMINIO_RESULTADO, payload_resultado(orden, self._politica.id_nodo, salida))
        except BaseException:
            self._almacen.fallar(ident)
            raise
        self._almacen.completar(ident, resultado)
        return resultado

    def estado(self, id_ejecucion: str) -> EstadoNodo | None:
        return self._almacen.estado(id_ejecucion)

    def reenviar_resultado(self, id_ejecucion: str) -> bytes | None:
        """El resultado firmado YA producido (idempotente: mismos bytes), o `None` si no hay COMPLETADA. Nunca ejecuta."""
        return self._almacen.resultado_guardado(id_ejecucion)
