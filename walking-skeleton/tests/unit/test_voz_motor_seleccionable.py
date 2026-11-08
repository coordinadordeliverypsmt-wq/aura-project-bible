"""El motor de síntesis es seleccionable (CM1): Piper por defecto, espeak-ng opcional.

`[EJEC]` 2026-09-29 HC-1: la SÍNTESIS de ningún camino Piper cabe en el presupuesto de 800 ms; la de
espeak-ng sí, con una regresión de calidad medida (WER 0,33 frente a 0,18). Aun así el turno completo
no baja de 800 ms (CM1 NO ALCANZADO). Por eso el defecto NO cambia.
"""

from __future__ import annotations

import asyncio

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.adapters.tts_espeak import SintetizadorEspeak
from aura_skeleton.adapters.voice_real import VozNoDisponible, WhisperPiperVoice
from aura_skeleton.composicion import _sintetizador_de_entorno


class _Doble:
    def __init__(self, falla: Exception | None = None):
        self.textos: list[str] = []
        self._falla = falla

    def comprobar(self) -> str:
        return "doble (motor de prueba)"

    def sintetizar_wav(self, texto: str, ruta: str) -> None:
        if self._falla:
            raise self._falla
        self.textos.append(texto)
        with open(ruta, "wb") as f:
            f.write(b"RIFFdoble")


def test_comprobar_delega_en_el_sintetizador(tmp_path):
    v = WhisperPiperVoice(out_dir=str(tmp_path), sintetizador=_Doble())
    assert v.comprobar() == "doble (motor de prueba)"  # control: Piper con voz vacía lanzaría


def test_tts_usa_el_sintetizador_y_no_exige_voz_piper(tmp_path):
    doble = _Doble()
    v = WhisperPiperVoice(out_dir=str(tmp_path), piper_voice="", sintetizador=doble)
    ruta = asyncio.run(v.tts("Hola", "t1"))
    assert doble.textos == ["Hola"]
    assert open(ruta, "rb").read() == b"RIFFdoble"


def test_un_fallo_ajeno_del_sintetizador_se_declara_VozNoDisponible(tmp_path):
    v = WhisperPiperVoice(out_dir=str(tmp_path), sintetizador=_Doble(falla=ValueError("boom")))
    with pytest.raises(VozNoDisponible, match="boom"):
        asyncio.run(v.tts("Hola", "t2"))


def test_una_VozNoDisponible_del_sintetizador_se_propaga_tal_cual(tmp_path):
    v = WhisperPiperVoice(out_dir=str(tmp_path), sintetizador=_Doble(falla=VozNoDisponible("sin voz")))
    with pytest.raises(VozNoDisponible, match="^sin voz$"):
        asyncio.run(v.tts("Hola", "t3"))


def test_sin_sintetizador_sigue_exigiendo_la_voz_piper(tmp_path):
    v = WhisperPiperVoice(out_dir=str(tmp_path), piper_voice="")
    with pytest.raises(VozNoDisponible, match="AURA_PIPER_VOICE"):
        v.comprobar()
    with pytest.raises(VozNoDisponible, match="AURA_PIPER_VOICE"):
        asyncio.run(v.tts("Hola", "t4"))


def test_el_tope_de_sintesis_cubre_al_sintetizador_alternativo(tmp_path):
    import time

    class _Lento(_Doble):
        def sintetizar_wav(self, texto, ruta):
            time.sleep(0.5)

    v = WhisperPiperVoice(out_dir=str(tmp_path), sintetizador=_Lento(), limite_sintesis_s=0.05)  # type: ignore[arg-type]
    with pytest.raises(VozNoDisponible, match="tiempo limite"):
        asyncio.run(v.tts("Hola", "t5"))


# ------------------------------------------------------------------ selección desde el entorno --


def test_por_defecto_no_hay_sintetizador_alternativo():
    assert _sintetizador_de_entorno({}) is None


def test_piper_explicito_no_hay_sintetizador_alternativo():
    assert _sintetizador_de_entorno({"AURA_TTS_MOTOR": "piper"}) is None


def test_espeak_construye_SintetizadorEspeak_con_la_voz_pedida():
    s = _sintetizador_de_entorno({"AURA_TTS_MOTOR": "espeak", "AURA_ESPEAK_VOZ": "es-419"})
    assert isinstance(s, SintetizadorEspeak) and s._voz == "es-419"
    assert _sintetizador_de_entorno({"AURA_TTS_MOTOR": "espeak"})._voz == "es"  # type: ignore[union-attr]


def test_motor_desconocido_cae_a_piper_y_lo_dice():
    antes = len(obs._records)
    assert _sintetizador_de_entorno({"AURA_TTS_MOTOR": "festival"}) is None
    nuevos = obs._records[antes:]
    assert any("festival" in r["msg"] and r.get("audit") for r in nuevos), nuevos  # caer en silencio sería INV-9


def test_el_registro_de_tts_nombra_el_motor_real(tmp_path):
    """Con espeak el log no puede decir «piper-tts»: sería declarar un motor que no sintetizó (INV-9)."""
    antes = len(obs._records)
    v = WhisperPiperVoice(out_dir=str(tmp_path), sintetizador=_Doble())
    asyncio.run(v.tts("Hola", "t6"))
    modulos = [r["module"] for r in obs._records[antes:] if r["level"] == "VOICE"]
    assert modulos == ["espeak-ng"], modulos


def test_el_registro_de_tts_sigue_diciendo_piper_sin_sintetizador(tmp_path, monkeypatch):
    """Control: el camino Piper conserva su etiqueta de siempre."""
    v = WhisperPiperVoice(out_dir=str(tmp_path))
    monkeypatch.setattr(v, "_tts_sync", lambda texto, ruta: None)
    antes = len(obs._records)
    asyncio.run(v.tts("Hola", "t7"))
    assert [r["module"] for r in obs._records[antes:] if r["level"] == "VOICE"] == ["piper-tts"]
