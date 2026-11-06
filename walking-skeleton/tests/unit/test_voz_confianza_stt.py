"""Confianza del STT (DP-VOZ-ACCION §8 C4): el adaptador expone cuánta fe merece la última transcripción.

El orquestador lee `getattr(voice, "ultima_confianza", None)`: un dict con `no_speech_prob` (MÁXIMO entre
segmentos) y `avg_logprob` (MÍNIMO entre segmentos), o None si no hubo transcripción real. Nunca texto
ni audio: solo dos cifras.
"""

from __future__ import annotations

import struct
import wave
from types import SimpleNamespace

import pytest

from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.adapters.voice_real import VozNoDisponible, WhisperPiperVoice


@pytest.fixture(autouse=True)
def _todo_es_habla(monkeypatch):
    """Estas pruebas miden la TRANSCRIPCIÓN con WAV de silencio sintético: el detector de voz (probado aparte en
    test_voz_sin_habla.py) se sustituye por «todo es habla» para no confundir lo que se mide."""
    from aura_skeleton.adapters import voice_real as _vr

    monkeypatch.setattr(_vr, "_tramos_de_habla", lambda audio: [(0, len(audio))])


def _wav(ruta) -> str:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * 1600)
    return str(ruta)


def _seg(texto: str, nsp: float, lp: float):
    return SimpleNamespace(text=texto, no_speech_prob=nsp, avg_logprob=lp)


def _con_modelo(monkeypatch, transcribe):
    import faster_whisper

    class _Modelo:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, audio, **kw):
            return transcribe()

    monkeypatch.setattr(faster_whisper, "WhisperModel", _Modelo)


def test_antes_de_transcribir_no_hay_confianza():
    assert WhisperPiperVoice(piper_voice="x").ultima_confianza is None


def test_maximo_de_no_habla_y_minimo_de_logprob(monkeypatch, tmp_path):
    segs = [_seg("apaga", 0.10, -0.2), _seg("la tele", 0.60, -1.5), _seg("ya", 0.30, -0.9)]
    _con_modelo(monkeypatch, lambda: (iter(segs), None))  # generador: se materializa una sola vez
    voz = WhisperPiperVoice(piper_voice="x")
    texto = voz._stt_sync(_wav(tmp_path / "a.wav"))
    assert texto == "apaga la tele ya"
    assert voz.ultima_confianza == {"no_speech_prob": 0.60, "avg_logprob": -1.5}


def test_la_confianza_no_contiene_texto(monkeypatch, tmp_path):
    _con_modelo(monkeypatch, lambda: ([_seg(" apaga la tele", 0.1, -0.3)], None))
    voz = WhisperPiperVoice(piper_voice="x")
    voz._stt_sync(_wav(tmp_path / "a.wav"))
    assert set(voz.ultima_confianza) == {"no_speech_prob", "avg_logprob"}
    assert "apaga" not in repr(voz.ultima_confianza)


def test_transcripcion_vacia_deja_none_y_borra_la_anterior(monkeypatch, tmp_path):
    voz = WhisperPiperVoice(piper_voice="x")
    voz.ultima_confianza = {"no_speech_prob": 0.0, "avg_logprob": 0.0}  # resto de un turno previo
    _con_modelo(monkeypatch, lambda: ([], None))
    assert voz._stt_sync(_wav(tmp_path / "a.wav")) == ""
    assert voz.ultima_confianza is None


def test_si_la_transcripcion_falla_es_none(monkeypatch, tmp_path):
    def _explota():
        raise RuntimeError("boom")

    voz = WhisperPiperVoice(piper_voice="x")
    voz.ultima_confianza = {"no_speech_prob": 0.0, "avg_logprob": 0.0}
    _con_modelo(monkeypatch, _explota)
    with pytest.raises(VozNoDisponible):
        voz._stt_sync(_wav(tmp_path / "a.wav"))
    assert voz.ultima_confianza is None


def test_se_actualiza_en_cada_transcripcion(monkeypatch, tmp_path):
    tandas = iter([[_seg("a", 0.1, -0.1)], [_seg("b", 0.9, -2.0)]])
    _con_modelo(monkeypatch, lambda: (next(tandas), None))
    voz = WhisperPiperVoice(piper_voice="x")
    wav = _wav(tmp_path / "a.wav")
    voz._stt_sync(wav)
    assert voz.ultima_confianza == {"no_speech_prob": 0.1, "avg_logprob": -0.1}
    voz._stt_sync(wav)
    assert voz.ultima_confianza == {"no_speech_prob": 0.9, "avg_logprob": -2.0}


@pytest.mark.asyncio
async def test_el_passthrough_de_texto_no_es_transcripcion_real():
    voz = WhisperPiperVoice(piper_voice="x")
    voz.ultima_confianza = {"no_speech_prob": 0.0, "avg_logprob": 0.0}
    assert await voz.stt("apaga la tele", "t") == "apaga la tele"
    assert voz.ultima_confianza is None


def test_el_doble_declara_ultima_confianza_none():
    assert VoiceAdapterMock().ultima_confianza is None
