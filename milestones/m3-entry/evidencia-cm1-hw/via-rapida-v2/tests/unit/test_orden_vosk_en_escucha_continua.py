"""Vía rápida opcional (B2): con `AURA_ORDEN_VOSK=1` la orden se transcribe con Vosk y no con Whisper.

`[EJEC]` 2026-09-29: el defecto sigue siendo Whisper (mejor transcripción); la vía Vosk existe para
cumplir CM1 (P50 <= 800 ms desde el fin de habla) en HC-1.
"""

from __future__ import annotations

import asyncio

from aura_skeleton import __main__ as principal


class _Oido:
    def __init__(self, texto, con_orden=True):
        self._llamadas = [True, False]
        self._texto = texto
        self.ordenes = 0

    def esperar_llamada(self):
        return self._llamadas.pop(0)


class _OidoConOrden(_Oido):
    def escuchar_orden(self):
        self.ordenes += 1
        return self._texto


class _OidoSinOrden(_Oido):
    pass


def _correr(monkeypatch, oido, entorno):
    if entorno is None:
        monkeypatch.delenv("AURA_ORDEN_VOSK", raising=False)
    else:
        monkeypatch.setenv("AURA_ORDEN_VOSK", entorno)
    turnos: list[tuple] = []

    async def _acuse(*a):
        turnos.append(("acuse",))

    async def _turno(sistema, mic, tid, *texto):
        turnos.append(("turno", *texto))

    monkeypatch.setattr(principal, "_acusar_llamada", _acuse)
    monkeypatch.setattr(principal, "_turno_de_voz", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    codigo = asyncio.run(principal._escuchar_continuo(object(), object(), oido, telemetria=True))
    return codigo, turnos


def test_con_la_variable_la_orden_sale_de_vosk_y_llega_al_turno(monkeypatch, capsys):
    oido = _OidoConOrden("que hora es")
    codigo, turnos = _correr(monkeypatch, oido, "1")
    assert codigo == 1
    assert oido.ordenes == 1
    assert turnos == [("acuse",), ("turno", "que hora es")]  # control: sin texto iría a grabar
    assert "tú (oído)> que hora es" in capsys.readouterr().out


def test_con_la_variable_y_orden_vacia_dice_no_te_oi_y_no_lanza_turno(monkeypatch, capsys):
    oido = _OidoConOrden("")
    _, turnos = _correr(monkeypatch, oido, "1")
    assert turnos == [("acuse",)]
    assert "No te oí." in capsys.readouterr().out


def test_sin_la_variable_se_usa_el_camino_de_grabacion(monkeypatch):
    oido = _OidoConOrden("no debe usarse")
    _, turnos = _correr(monkeypatch, oido, None)
    assert oido.ordenes == 0
    assert turnos == [("acuse",), ("turno",)]  # sin texto: el turno graba


def test_con_valor_distinto_de_1_tampoco_se_usa(monkeypatch):
    oido = _OidoConOrden("x")
    _, turnos = _correr(monkeypatch, oido, "0")
    assert oido.ordenes == 0 and turnos == [("acuse",), ("turno",)]


def test_con_la_variable_pero_un_oido_sin_escuchar_orden_cae_al_camino_de_grabacion(monkeypatch):
    oido = _OidoSinOrden("x", con_orden=False)
    _, turnos = _correr(monkeypatch, oido, "1")
    assert turnos == [("acuse",), ("turno",)]


def test_la_gramatica_de_orden_solo_se_pasa_con_la_variable():
    from aura_skeleton.core.ordenes_deterministas import ORDENES_DE_VOZ

    assert principal._gramatica_de_orden({"AURA_ORDEN_VOSK": "1"}) == ORDENES_DE_VOZ
    assert principal._gramatica_de_orden({}) is None  # control: el defecto no cambia
    assert principal._gramatica_de_orden({"AURA_ORDEN_VOSK": "0"}) is None
