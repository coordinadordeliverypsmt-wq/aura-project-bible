"""Política por superficie de cámara (corrección CEO, 2026-09-28).

Una CÁMARA/DVR no es una unidad indivisible: cada canal es una SUPERFICIE con su propia zona, propósito y
autorización, sin que uno bloquee al otro. Reemplaza el bloqueo GLOBAL anterior.

**La zona es METADATO, nunca una denegación** (acta del CEO `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`).
Sirve para nombrar y dar contexto («habitacion», «garaje»); ninguna regla de este módulo la consulta. Corrige la frase
anterior («un canal privado (dormitorio) queda restringido»), que nunca tuvo código detrás y contradice la decisión del
propietario: todas sus cámaras domésticas son integrables, estén donde estén.

**Deny-by-default.** Una superficie no registrada, o registrada sin autorización, no permite NADA. Y los
niveles NO se heredan: que se permita procesar la imagen (detectar un evento) no permite identificar
personas — la identidad biométrica es una frontera aparte que sigue su propia decisión.

Este módulo es solo la política (datos + reglas puras). Quién captura y procesa es `percepcion.py`, que
pregunta aquí ANTES de tocar la cámara.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Superficie:
    """Un canal/superficie concreto y qué se permite hacer con él. Todo lo no concedido, denegado."""

    surface_id: str
    device_id: str
    channel_id: int | None
    zona: str  # etiqueta del propietario («habitacion», «garaje», «exterior», «desconocida»…); NO da ni quita permisos
    proposito: str
    autorizado: bool
    visual_processing_allowed: bool = False
    audio_processing_allowed: bool = False
    persistence_allowed: bool = False
    identity_processing_allowed: bool = False
    action_allowed: bool = False
    effect_verification_allowed: bool = False


class RegistroDeSuperficies:
    """Consulta de políticas por `surface_id`. Lo no registrado se deniega."""

    def __init__(self, superficies: list[Superficie] | None = None) -> None:
        self._por_id: dict[str, Superficie] = {}
        for s in superficies or []:
            self._por_id[s.surface_id] = s

    def superficie(self, surface_id: str) -> Superficie | None:
        return self._por_id.get(surface_id)

    def _permite(self, surface_id: str, atributo: str) -> bool:
        s = self._por_id.get(surface_id)
        # Deny-by-default: desconocida o no autorizada -> nada, sin importar sus flags.
        if s is None or not s.autorizado:
            return False
        return bool(getattr(s, atributo))

    def puede_procesar_visual(self, surface_id: str) -> bool:
        return self._permite(surface_id, "visual_processing_allowed")

    def puede_procesar_audio(self, surface_id: str) -> bool:
        return self._permite(surface_id, "audio_processing_allowed")

    def puede_persistir(self, surface_id: str) -> bool:
        return self._permite(surface_id, "persistence_allowed")

    def puede_identificar(self, surface_id: str) -> bool:
        return self._permite(surface_id, "identity_processing_allowed")

    def puede_actuar(self, surface_id: str) -> bool:
        return self._permite(surface_id, "action_allowed")

    def puede_verificar_efecto(self, surface_id: str) -> bool:
        return self._permite(surface_id, "effect_verification_allowed")
