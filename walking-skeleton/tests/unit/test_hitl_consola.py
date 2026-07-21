"""HITL por consola (D40 criterio 3: la composicion ensambla, no decide).

Esta politica vivia dentro de `composicion.py`, donde el criterio 3 del CEO no la admite: decidir
como se pide una confirmacion humana es logica funcional, no ensamblaje. Se extrae aqui y, de paso,
se prueba — en `composicion.py` no tenia ninguna prueba.

Lo que se verifica es la propiedad critica de ADR-0003: **ante cualquier duda, NO.**
"""

import builtins

import pytest

from aura_skeleton.adapters.hitl_consola import confirmar_por_consola


@pytest.mark.asyncio
async def test_solo_un_si_explicito_autoriza(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _="": "SI")
    assert await confirmar_por_consola("borrar_archivo", {"_previsualizacion": "se eliminaria x"}, "t") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("respuesta", ["si", "s", "yes", "vale", "", "SI ", "no", "SÍ"])
async def test_cualquier_otra_respuesta_deniega(monkeypatch, respuesta):
    """Tolerancia cero a falsos negativos (2.5 §5.4): la duda no autoriza.

    'SI ' con espacio se acepta porque se aplica strip(); 'SÍ' con tilde NO, para que la
    autorizacion sea inequivoca y no dependa de la disposicion del teclado.
    """
    monkeypatch.setattr(builtins, "input", lambda _="": respuesta)
    autorizado = await confirmar_por_consola("borrar_archivo", {}, "t")
    assert autorizado is (respuesta.strip() == "SI")


@pytest.mark.asyncio
async def test_sin_humano_al_otro_lado_deniega(monkeypatch):
    """CASO CRITICO: en un servicio desatendido, nadie puede confirmar por omision."""

    def _sin_terminal(_=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", _sin_terminal)
    assert await confirmar_por_consola("borrar_archivo", {}, "t") is False


@pytest.mark.asyncio
async def test_interrupcion_deniega(monkeypatch):
    def _interrumpido(_=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", _interrumpido)
    assert await confirmar_por_consola("borrar_archivo", {}, "t") is False


@pytest.mark.asyncio
async def test_la_previsualizacion_se_muestra_al_usuario(monkeypatch, capsys):
    """5.3 §3.1: confirmar sin ver el efecto no es consentimiento informado."""
    monkeypatch.setattr(builtins, "input", lambda _="": "SI")
    await confirmar_por_consola("borrar_archivo", {"_previsualizacion": "se eliminaria /tmp/x (30 bytes)"}, "t")

    salida = capsys.readouterr().out
    assert "se eliminaria /tmp/x (30 bytes)" in salida


@pytest.mark.asyncio
async def test_sin_previsualizacion_se_advierte(monkeypatch, capsys):
    """Si el dry-run no produjo plan, el usuario debe saber que confirma a ciegas."""
    monkeypatch.setattr(builtins, "input", lambda _="": "SI")
    await confirmar_por_consola("borrar_archivo", {}, "t")

    assert "ADVERTENCIA" in capsys.readouterr().out
