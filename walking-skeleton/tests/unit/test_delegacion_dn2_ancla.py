"""DN-2 (2026-10-27) — el añadido al ancla de revocados pasa por `anexar`, que detecta la escritura PARCIAL.

Antes, `_anotar_ancla` hacía `os.write(fd, linea)` ignorando el retorno: una escritura corta (p. ej. ENOSPC)
dejaba el ancla truncada SIN error, y desde ese momento la lista de revocados fallaba cerrada para siempre
(«ancla truncada»). Al reutilizar `anexar` del propio paquete (`jsonl_durable`), una escritura parcial se
convierte en `ErrorDurable` y `revocar` la propaga como `ErrorClave`: el fallo se ve en el momento de escribir.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import aura_skeleton.adapters.jsonl_durable as jd
from aura_skeleton.adapters.firma_delegacion import ErrorClave
from tests.unit.test_delegacion_revision2 import _lista, _revocar


def test_dn2_control_una_revocacion_normal_deja_el_ancla_legible(tmp_path: Path) -> None:
    """Control: sin escritura parcial, `revocar` ancla y la lista vuelve a leerse."""
    lista, ruta, ancla = _lista(tmp_path)
    _revocar(ruta, "kid-a")
    assert lista() == {"kid-a"}
    assert ancla.exists()


def test_dn2_una_escritura_parcial_del_ancla_falla_cerrado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Si `os.write` escribe menos bytes de los pedidos al anotar el ancla, `revocar` falla con `ErrorClave`
    en vez de dejar el ancla truncada en silencio."""
    lista, ruta, _ancla = _lista(tmp_path)
    real_write = os.write

    def write_corta(fd: int, data: bytes) -> int:
        # Solo la LÍNEA DEL ANCLA lleva "sha256"; la línea de la lista ({"kid":...}) se escribe entera.
        if b'"sha256"' in data:
            return real_write(fd, data[:-1])  # una menos: escritura parcial
        return real_write(fd, data)

    monkeypatch.setattr(jd.os, "write", write_corta)
    with pytest.raises(ErrorClave):
        _revocar(ruta, "kid-a")
