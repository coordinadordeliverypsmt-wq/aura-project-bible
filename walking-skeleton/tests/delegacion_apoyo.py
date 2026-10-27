"""Apoyo de las pruebas de delegación: HC-1 y nodo SIMULADOS, relojes y claves de prueba (siempre en tmp_path)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aura_skeleton.adapters.firma_delegacion import Firmante, generar_firmante, verificador_de
from aura_skeleton.core.delegacion import (
    DOMINIO_ORDEN,
    DOMINIO_RESOLUCION,
    PoliticaNodo,
    SinRevocacion,
    bytes_canonicos,
    empaquetar_sobre,
    hash_de,
    payload_orden,
    payload_resolucion,
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


KID_AUTORIDAD = "autoridad-k1"


class RegistroSintetico(list):  # type: ignore[type-arg]
    """Destino SINTÉTICO del hecho auditable: IDEMPOTENTE por `id_ejecucion` (contrato de `Registrar`). Es una lista
    (los hechos) y es invocable: `hc1.incorporar(ident, registro)`."""

    def __call__(self, hecho: dict[str, Any]) -> None:
        if not self.ya_registrado(hecho["id_ejecucion"]):
            self.append(hecho)

    def ya_registrado(self, id_ejecucion: str) -> bool:
        return any(h["id_ejecucion"] == id_ejecucion for h in self)


class AlmacenMemoria:
    """Doble de prueba SOLO para pruebas que no ejercitan la persistencia (misma semántica de estados que el real)."""

    def __init__(self) -> None:
        self.vistas: set[str] = set()
        self.estados: dict[str, str] = {}
        self.resultados: dict[str, bytes] = {}
        self.hashes: dict[str, str | None] = {}

    def hash_consumido(self, id_ejecucion: str) -> str | None:
        return self.hashes.get(id_ejecucion)

    def consumir(self, id_ejecucion: str, epoch: int, hash_tarea: str | None = None) -> None:
        from aura_skeleton.core.delegacion import Motivo, RechazoOrden

        if id_ejecucion in self.vistas:
            raise RechazoOrden(Motivo.ORDEN_REPETIDA)
        self.vistas.add(id_ejecucion)
        self.hashes[id_ejecucion] = hash_tarea

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

    def dejar_ambigua(self, id_ejecucion: str) -> None:
        self.estados[id_ejecucion] = "ambigua"

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
    autoridad: Firmante
    """Clave de la AUTORIDAD HUMANA: distinta de la de HC-1 y de las de los nodos."""

    def verificador_hc1(self):  # type: ignore[no-untyped-def]
        return verificador_de({"hc1-k1": self.hc1.publica()})

    def verificador_nodos(self):  # type: ignore[no-untyped-def]
        return verificador_de({NODO: self.nodo.publica(), OTRO_NODO: self.otro_nodo.publica()})

    def verificador_autoridad(self):  # type: ignore[no-untyped-def]
        return verificador_de({KID_AUTORIDAD: self.autoridad.publica()})

    def config_hc1(self, **kw: Any) -> dict[str, Any]:
        """Configuración EXPLÍCITA y completa de `SeguimientoHC1` (sin defaults abiertos); `kw` la sobrescribe."""
        base: dict[str, Any] = {
            "verificar_hc1": self.verificador_hc1(),
            "kid_hc1": "hc1-k1",
            "fuente_revocados": SinRevocacion(),
            "kids_autoridad": frozenset({KID_AUTORIDAD}),
            "verificar_autoridad": self.verificador_autoridad(),
        }
        base.update(kw)
        return base

    def autorizacion(
        self,
        id_ejecucion: str,
        resultado_firmado: bytes,
        motivo: str = "el nodo guardó el resultado firmado",
        **kw: Any,
    ) -> bytes:
        """Autorización de resolución FIRMADA por la autoridad, ligada al `hash` de ESE resultado firmado y vigente
        respecto al reloj de la escena."""
        ahora = self.reloj.ahora()
        campos: dict[str, Any] = {
            "id_ejecucion": id_ejecucion,
            "hash_resultado": hash_de(resultado_firmado),
            "motivo": motivo,
            "emitida_en": ahora,
            "caduca_en": ahora + 120,
            "nonce": str(uuid.uuid4()),
        }
        campos.update(kw)
        firmante = campos.pop("firmante", self.autoridad)
        return firmante.firmar(DOMINIO_RESOLUCION, payload_resolucion(**campos))

    def politica(self, **kw: Any) -> PoliticaNodo:
        base: dict[str, Any] = {
            "id_nodo": NODO,
            "emisores": {"hc1-k1": "hc1"},
            "capacidades": frozenset({"calcular_resumen_sha256"}),
            "reloj": self.reloj,
            "arranque": T0 - 10,
            "fuente_revocados": SinRevocacion(),
        }
        base.update(kw)
        return PoliticaNodo(**base)


def mundo() -> Mundo:
    return Mundo(
        generar_firmante("hc1-k1"),
        generar_firmante(NODO),
        generar_firmante(OTRO_NODO),
        RelojFalso(),
        generar_firmante(KID_AUTORIDAD),
    )


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
