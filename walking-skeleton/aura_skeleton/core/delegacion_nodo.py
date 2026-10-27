"""Lado NODO de la delegación: aceptar una orden firmada, acusar y ejecutar (A1/A2/N7/M5). Módulo PURO.

Flujo: `aceptar` valida la orden (firma sobre bytes exactos, destinatario, capacidad LOCAL, esquema, frescura) y la
consume de forma durable; devuelve el acuse FIRMADO. `ejecutar` corre la capacidad desde la TABLA fija
(`core.delegacion.CAPACIDADES`; nunca `exec`, shell ni interpolación) y devuelve el resultado FIRMADO ligado por
`hash_tarea` a los bytes de la orden. El nodo NO tiene autoridad: lo que declara lo valida después HC-1.

La firma se inyecta (`Firmar`): este módulo no conoce claves. La delegación real sigue DESHABILITADA: nada de esto
está cableado al agente de producción.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .delegacion import (
    CAPACIDADES,
    DOMINIO_ACUSE,
    DOMINIO_RESULTADO,
    AlmacenOrdenes,
    OrdenValida,
    PoliticaNodo,
    Verificador,
    payload_acuse,
    payload_resultado,
    validar_orden,
)

Firmar = Callable[[bytes, bytes], bytes]
"""(dominio, payload) -> sobre firmado."""


@dataclass(frozen=True)
class OrdenAceptada:
    orden: OrdenValida
    acuse: bytes
    """Sobre del acuse firmado por el nodo (N7)."""


class NodoDelegado:
    def __init__(self, politica: PoliticaNodo, verificar: Verificador, almacen: AlmacenOrdenes, firmar: Firmar) -> None:
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
        """Ejecuta la capacidad REGISTRADA (ya validada en `aceptar`) y devuelve el resultado firmado."""
        cap = CAPACIDADES[orden.campos["capacidad"]]
        salida = cap.ejecutar(cap.validar_argumentos(orden.campos["argumentos"]))
        return self._firmar(DOMINIO_RESULTADO, payload_resultado(orden, self._politica.id_nodo, salida))
