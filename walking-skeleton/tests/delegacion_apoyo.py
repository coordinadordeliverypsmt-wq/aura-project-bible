"""Apoyo de las pruebas de delegación: HC-1 y nodo SIMULADOS, relojes y claves de prueba (siempre en tmp_path)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aura_skeleton.adapters.firma_delegacion import Firmante, generar_firmante, verificador_de
from aura_skeleton.core.delegacion import (
    DOMINIO_ORDEN,
    PoliticaNodo,
    bytes_canonicos,
    empaquetar_sobre,
    payload_orden,
)

NODO = "a" * 32
OTRO_NODO = "b" * 32
T0 = 1_000_000.0


class RelojFalso:
    def __init__(self, t: float = T0, sincronizado: bool = True) -> None:
        self.t = t
        self._sinc = sincronizado

    def ahora(self) -> float:
        return self.t

    def sincronizado(self) -> bool:
        return self._sinc

    def poner_sincronizado(self, valor: bool) -> None:
        self._sinc = valor


class AlmacenMemoria:
    """Doble de prueba SOLO para pruebas que no ejercitan la persistencia (misma semántica de estados que el real)."""

    def __init__(self) -> None:
        self.vistas: set[str] = set()
        self.estados: dict[str, str] = {}
        self.resultados: dict[str, bytes] = {}

    def consumir(self, id_ejecucion: str, epoch: int) -> None:
        from aura_skeleton.core.delegacion import Motivo, RechazoOrden

        if id_ejecucion in self.vistas:
            raise RechazoOrden(Motivo.ORDEN_REPETIDA)
        self.vistas.add(id_ejecucion)

    def iniciar_ejecucion(self, id_ejecucion: str) -> None:
        from aura_skeleton.core.delegacion import Motivo, RechazoOrden

        if id_ejecucion in self.estados:
            raise RechazoOrden(Motivo.EJECUCION_REPETIDA)
        self.estados[id_ejecucion] = "ejecutando"

    def completar(self, id_ejecucion: str, resultado_firmado: bytes) -> None:
        self.estados[id_ejecucion] = "completada"
        self.resultados[id_ejecucion] = resultado_firmado

    def fallar(self, id_ejecucion: str) -> None:
        self.estados[id_ejecucion] = "fallida"

    def estado(self, id_ejecucion: str):  # type: ignore[no-untyped-def]
        from aura_skeleton.core.delegacion import EstadoNodo

        if id_ejecucion not in self.vistas:
            return None
        return EstadoNodo(self.estados.get(id_ejecucion, "consumida"))

    def resultado_guardado(self, id_ejecucion: str) -> bytes | None:
        return self.resultados.get(id_ejecucion)


@dataclass
class Mundo:
    hc1: Firmante
    nodo: Firmante
    otro_nodo: Firmante
    reloj: RelojFalso

    def verificador_hc1(self):  # type: ignore[no-untyped-def]
        return verificador_de({"hc1-k1": self.hc1.publica()})

    def verificador_nodos(self):  # type: ignore[no-untyped-def]
        return verificador_de({NODO: self.nodo.publica(), OTRO_NODO: self.otro_nodo.publica()})

    def politica(self, **kw: Any) -> PoliticaNodo:
        base: dict[str, Any] = {
            "id_nodo": NODO,
            "emisores": {"hc1-k1": "hc1"},
            "capacidades": frozenset({"calcular_resumen_sha256"}),
            "reloj": self.reloj,
            "arranque": T0 - 10,
        }
        base.update(kw)
        return PoliticaNodo(**base)


def mundo() -> Mundo:
    return Mundo(generar_firmante("hc1-k1"), generar_firmante(NODO), generar_firmante(OTRO_NODO), RelojFalso())


def campos_validos(**cambios: Any) -> dict[str, Any]:
    c: dict[str, Any] = {
        "v": 1,
        "alg": "ed25519",
        "emisor": "hc1",
        "destinatario": NODO,
        "tarea": "t-001",
        "intento": 1,
        "id_ejecucion": str(uuid.uuid4()),
        "capacidad": "calcular_resumen_sha256",
        "argumentos": {"texto": "hola aura"},
        "emitida_en": T0,
        "caduca_en": T0 + 60,
        "epoch_hc1": 1,
        "kid": "hc1-k1",
    }
    c.update(cambios)
    return c


def firmar_campos(firmante: Firmante, campos: Mapping[str, Any]) -> bytes:
    """Firma CUALQUIER mapa (sin pasar por la validación del firmador): permite fabricar órdenes hostiles."""
    return firmante.firmar(DOMINIO_ORDEN, bytes_canonicos(dict(campos)))


def orden_firmada(m: Mundo, **cambios: Any) -> bytes:
    return firmante_orden(m.hc1, campos_validos(**cambios))


def firmante_orden(firmante: Firmante, campos: Mapping[str, Any]) -> bytes:
    return firmante.firmar(DOMINIO_ORDEN, payload_orden(campos))


__all__ = ["empaquetar_sobre"]
