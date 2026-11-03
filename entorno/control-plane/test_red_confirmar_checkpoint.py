"""RED · registrar que el checkpoint fue releido.

`checkpoint_sin_cambios()` avisa cuando el documento cambio desde que se escribio el estado, y esa
salvaguarda funciona. Lo que falta es la operacion inversa: **no hay forma de registrar que ya se
releyo**, asi que una vez que el CHECKPOINT cambia el aviso queda encendido para siempre.

Una alarma que suena siempre deja de informar. Medido: 3 sesiones seguidas con `False`.

No introduce autoridad ni semantica nueva: registra un hecho observable —se leyo esta version del
documento— usando el mismo sello que la comprobacion ya emplea.
"""
from __future__ import annotations

import control_plane as cp
import pytest


def _doc(tmp_path, texto="## Seccion\ncontenido\n"):
    d = tmp_path / "CHECKPOINT.md"
    d.write_text(texto, encoding="utf-8")
    return d


def test_tras_confirmar_el_checkpoint_deja_de_avisar(tmp_path):
    d = _doc(tmp_path)
    e = cp.estado_inicial()
    e["checkpoint"] = {"sha256": "sello-viejo"}
    assert cp.checkpoint_sin_cambios(e, d)[0] is False
    e = cp.confirmar_checkpoint(e, d)
    assert cp.checkpoint_sin_cambios(e, d)[0] is True


def test_confirmar_registra_la_version_exacta_que_se_leyo(tmp_path):
    d = _doc(tmp_path)
    e = cp.confirmar_checkpoint(cp.estado_inicial(), d)
    assert e["checkpoint"]["sha256"] == cp.leer_checkpoint(d)["sha256"]
    assert e["checkpoint"]["secciones"] == ["Seccion"]


def test_si_el_documento_cambia_DESPUES_vuelve_a_avisar(tmp_path):
    """Confirmar no silencia el futuro: solo acredita la version leida en ese momento."""
    d = _doc(tmp_path)
    e = cp.confirmar_checkpoint(cp.estado_inicial(), d)
    d.write_text("## Seccion\notra cosa\n", encoding="utf-8")
    assert cp.checkpoint_sin_cambios(e, d)[0] is False


def test_no_se_confirma_un_documento_inexistente(tmp_path):
    """Fail-closed: acreditar la lectura de algo que no existe seria fabricar evidencia."""
    with pytest.raises(ValueError):
        cp.confirmar_checkpoint(cp.estado_inicial(), tmp_path / "no_existe.md")


def test_confirmar_no_toca_tareas_auto(tmp_path):
    """La separacion de autoridad no se relaja por una operacion de lectura."""
    e = cp.estado_inicial()
    e["tareas_AUTO"] = [{"id": "T-1"}]
    antes = list(e["tareas_AUTO"])
    e = cp.confirmar_checkpoint(e, _doc(tmp_path))
    assert e["tareas_AUTO"] == antes
