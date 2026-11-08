"""Voz sin habla (E2E físico 2026-10-04): un turno casi vacío no puede convertirse en texto inventado.

Medido por el aire [EJEC]: tras «Oye Aurora», un «sí» de una sílaba en ~5 s de grabación llegó a Whisper como
«¡¿¡¡¡¡ … rainbow! …» y tardó 61 s (el bucle de reintentos por temperatura); un turno en silencio respondió
«No tengo ningún recuerdo registrado sobre eso». Causa raíz: Whisper recibe sobre todo silencio. Corrección:
el detector de voz local de faster-whisper (Silero, sin red) recorta la grabación a donde hay habla; sin habla
no se transcribe nada y AURA dice que no ha oído, sin consultar memoria ni modelo.
"""

from __future__ import annotations

import asyncio
import struct
import wave
from types import SimpleNamespace

import numpy as np

from aura_skeleton.adapters import voice_real
from aura_skeleton.adapters.voice_real import WhisperPiperVoice


def _wav(ruta, muestras: int = 16000 * 5) -> str:
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * muestras)
    return str(ruta)


def _modelo(monkeypatch, visto: dict):
    import faster_whisper

    class _Modelo:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, audio, **kw):
            visto["muestras"] = len(audio)
            visto["llamado"] = True
            return [SimpleNamespace(text="sí", no_speech_prob=0.05, avg_logprob=-0.4)], None

    monkeypatch.setattr(faster_whisper, "WhisperModel", _Modelo)


def test_sin_habla_no_se_transcribe_nada_ni_se_llama_al_modelo(monkeypatch, tmp_path):
    visto: dict = {}
    _modelo(monkeypatch, visto)
    monkeypatch.setattr(voice_real, "_tramos_de_habla", lambda audio: [])
    voz = WhisperPiperVoice(piper_voice="x")
    assert voz._stt_sync(_wav(tmp_path / "a.wav")) == ""
    assert "llamado" not in visto, "sin habla, Whisper no debe ni ejecutarse (es donde alucina y tarda 60 s)"
    assert voz.ultima_confianza is None


def test_con_habla_se_recorta_al_tramo_y_se_conserva_el_margen(monkeypatch, tmp_path):
    visto: dict = {}
    _modelo(monkeypatch, visto)
    # habla de 1,0 s a 1,5 s en una grabación de 5 s
    monkeypatch.setattr(voice_real, "_tramos_de_habla", lambda audio: [(16000, 24000)])
    voz = WhisperPiperVoice(piper_voice="x")
    assert voz._stt_sync(_wav(tmp_path / "a.wav")) == "sí"
    margen = voice_real._MUESTREO * voice_real._MARGEN_S
    assert visto["muestras"] == 8000 + 2 * margen, "se transcribe solo el tramo con habla, más el margen de siempre"


def test_si_el_detector_no_esta_disponible_no_se_recorta(monkeypatch, tmp_path):
    visto: dict = {}
    _modelo(monkeypatch, visto)
    monkeypatch.setattr(voice_real, "_tramos_de_habla", lambda audio: None)
    voz = WhisperPiperVoice(piper_voice="x")
    assert voz._stt_sync(_wav(tmp_path / "a.wav")) == "sí"
    margen = voice_real._MUESTREO * voice_real._MARGEN_S
    assert visto["muestras"] == 16000 * 5 + 2 * margen, "sin detector no se inventa silencio: se transcribe todo"


def test_silero_real_no_ve_habla_en_el_silencio():
    assert voice_real._tramos_de_habla(np.zeros(16000 * 3, dtype=np.float32)) == []


def test_un_turno_hablado_vacio_dice_que_no_oyo_y_no_consulta_memoria_ni_modelo(tmp_path):
    from aura_skeleton.composicion import Configuracion, componer

    sistema = componer(Configuracion(datos=str(tmp_path)))
    orq = sistema.orquestador
    llamadas: list = []

    async def _router(*a, **k):
        llamadas.append("llm")
        return {"say": "inventado", "provider": "llm"}

    orq.router.route = _router  # type: ignore[method-assign]

    class _Voz:
        ultima_confianza = None

        async def stt(self, audio, trace_id="-"):
            return ""

        async def tts(self, texto, trace_id="-"):
            return None

    orq.voice = _Voz()

    async def _turno():
        await orq.handle_utterance("usuario", "/tmp/aura/entrada_x.wav", "T-vacio", activado=True)
        await orq.wait("T-vacio")
        return orq._results["T-vacio"]

    res = asyncio.run(_turno())
    assert "no te he oído" in res["say"].lower()
    assert llamadas == [], "un turno sin habla no puede llegar al modelo"


def test_el_detector_conserva_margen_suficiente_para_no_morder_la_primera_silaba():
    """Medido por el aire: con 200 ms de margen «enciende» llegó como «Enciente» / «No fiende». El margen no puede
    volver a ser tan corto."""
    assert voice_real._RELLENO_VAD_MS >= 500


def test_una_entrada_SATURADA_se_dice_y_no_se_transcribe(monkeypatch, tmp_path):
    """Causa raíz del E2E fallido (2026-10-04, medida): la ganancia del micrófono pasó de 27 % a 150 %; en silencio el
    74 % de las muestras quedaban recortadas y Whisper recibía una señal destruida («No fiende», «telencia»). AURA no
    puede transcribir eso como si fuera voz: lo dice para que se corrija."""
    import pytest as _pytest

    visto: dict = {}
    _modelo(monkeypatch, visto)
    monkeypatch.setattr(voice_real, "_tramos_de_habla", lambda audio: [(0, len(audio))])
    ruta = tmp_path / "saturada.wav"
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 32767) * 16000 + struct.pack("<h", 0) * 16000)  # 50 % recortado
    voz = WhisperPiperVoice(piper_voice="x")
    with _pytest.raises(voice_real.VozNoDisponible, match="saturad"):
        voz._stt_sync(str(ruta))
    assert "llamado" not in visto, "no se transcribe una señal recortada"


def test_una_entrada_con_poca_saturacion_se_transcribe(monkeypatch, tmp_path):
    """Control: a 50 % de ganancia la voz llegó con hasta 7,5 % de muestras al tope y se entendió (2/3)."""
    visto: dict = {}
    _modelo(monkeypatch, visto)
    monkeypatch.setattr(voice_real, "_tramos_de_habla", lambda audio: [(0, len(audio))])
    ruta = tmp_path / "leve.wav"
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 32767) * 800 + struct.pack("<h", 1000) * 15200)  # 5 %
    assert WhisperPiperVoice(piper_voice="x")._stt_sync(str(ruta)) == "sí"
