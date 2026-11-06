"""El adaptador de voz real: sin salir a internet, sin colgarse y diciendo la verdad — MISIÓN VOZ.

TRES DEFECTOS MEDIDOS EN EL ADAPTADOR (2026-09-15):

1. **`WhisperModel(...)` se construía con `local_files_only=False`** —el defecto de la librería—, así que
   un modelo ausente NO producía un fallo: producía una **descarga desde HuggingFace**. En un sistema
   local-first sin claves de terceros (D24, ADR-0001) eso es una salida a la red que nadie decidió.

2. **`subprocess.run([...], check=True)` sin `timeout`**: un Piper colgado colgaba el turno para siempre.

3. **Con `piper_voice=""` el error era `FileNotFoundError: '..json'`**, críptico y emitido por Piper, no
   por AURA. El adaptador debe saber ANTES de invocar nada que no tiene con qué hablar.

Lo que estas pruebas fijan es el contrato del adaptador con el exterior; la degradación del TURNO ante
estos fallos vive en `test_voz_degrada_con_honestidad.py`.
"""

from __future__ import annotations

import subprocess

import pytest

from aura_skeleton.adapters.voice_real import IDIOMA, VozNoDisponible, WhisperPiperVoice


@pytest.fixture(autouse=True)
def _todo_es_habla(monkeypatch):
    """Estas pruebas miden la TRANSCRIPCIÓN con WAV de silencio sintético: el detector de voz (probado aparte en
    test_voz_sin_habla.py) se sustituye por «todo es habla» para no confundir lo que se mide."""
    from aura_skeleton.adapters import voice_real as _vr

    monkeypatch.setattr(_vr, "_tramos_de_habla", lambda audio: [(0, len(audio))])


@pytest.fixture
def voz_falsa(tmp_path):
    """Un `.onnx` y su `.json` de mentira: Piper exige los dos juntos, así que el adaptador también."""
    onnx = tmp_path / "es_MX-ald-medium.onnx"
    onnx.write_bytes(b"onnx de mentira")
    (tmp_path / "es_MX-ald-medium.onnx.json").write_text("{}", encoding="utf-8")
    return str(onnx)


# ======================================================= STT: NUNCA SALE A INTERNET --


def test_el_transcriptor_nunca_sale_a_internet(monkeypatch, tmp_path):
    """D24 / ADR-0001: local-first. Un modelo ausente debe FALLAR, no descargarse."""
    visto: dict = {}

    class _ModeloFalso:
        def __init__(self, nombre, **kw):
            visto.update(kw)
            visto["nombre"] = nombre

        def transcribe(self, wav, **kw):
            return ([], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloFalso)
    wav = tmp_path / "a.wav"
    _wav_valido(wav)
    WhisperPiperVoice(piper_voice="x")._stt_sync(str(wav))
    assert visto["local_files_only"] is True, "el transcriptor podía descargar el modelo de la red"


def test_un_modelo_de_transcripcion_ausente_se_declara_no_disponible(monkeypatch, tmp_path):
    def _explota(nombre, **kw):
        raise OSError("no se encontró el modelo en la caché local")

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _explota)
    wav = tmp_path / "a.wav"
    _wav_valido(wav)
    with pytest.raises(VozNoDisponible) as exc:
        WhisperPiperVoice(piper_voice="x")._stt_sync(str(wav))
    assert "transcrip" in str(exc.value).lower() or "modelo" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_el_passthrough_de_texto_no_toca_el_transcriptor(monkeypatch):
    """Contrato vigente (T2.b): `stt` acepta texto plano y lo devuelve. No es transcripción."""

    def _no_debe_llamarse(*a, **k):
        raise AssertionError("se cargó el modelo para un texto que no es un WAV")

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _no_debe_llamarse)
    voz = WhisperPiperVoice(piper_voice="x")
    assert await voz.stt("hola, esto es texto", "t") == "hola, esto es texto"


# ============================================== TTS: NI CRÍPTICO NI ETERNO --


def test_una_voz_sin_declarar_falla_sin_invocar_al_sintetizador(monkeypatch, tmp_path):
    def _no_debe_llamarse(*a, **k):
        raise AssertionError("se invocó a Piper sin modelo: el error vendría de Piper, no de AURA")

    monkeypatch.setattr(subprocess, "run", _no_debe_llamarse)
    with pytest.raises(VozNoDisponible) as exc:
        WhisperPiperVoice(piper_voice="", out_dir=str(tmp_path))._tts_sync("hola", str(tmp_path / "o.wav"))
    assert "voz" in str(exc.value).lower()


def test_una_ruta_de_voz_inexistente_nombra_la_ruta(tmp_path):
    """El mensaje debe decir QUE falta, no solo que algo falla.

    Afirmar unicamente `fantasma in mensaje` dejaba pasar un mutante: al borrar esta comprobacion, la
    siguiente —la del `.onnx.json`— producia un mensaje que TAMBIEN contiene la ruta, y la prueba pasaba
    por la razon equivocada. Lo detecto la verificacion de mutacion (VZ-M8, 2026-09-15).
    """
    fantasma = str(tmp_path / "no-existe.onnx")
    with pytest.raises(VozNoDisponible) as exc:
        WhisperPiperVoice(piper_voice=fantasma, out_dir=str(tmp_path))._tts_sync("hola", str(tmp_path / "o.wav"))
    assert "la voz declarada no existe" in str(exc.value), f"confunde qué falta: {exc.value}"
    assert fantasma in str(exc.value), "el mensaje no dice qué ruta falta"


def test_una_voz_sin_su_json_se_detecta_antes_de_invocar_a_piper(tmp_path):
    """Piper exige `<modelo>.onnx.json` junto al `.onnx`; sin él aborta con un error ilegible."""
    onnx = tmp_path / "voz.onnx"
    onnx.write_bytes(b"onnx")
    with pytest.raises(VozNoDisponible) as exc:
        WhisperPiperVoice(piper_voice=str(onnx), out_dir=str(tmp_path))._tts_sync("hola", str(tmp_path / "o.wav"))
    assert ".json" in str(exc.value)


def test_un_sintetizador_colgado_no_espera_para_siempre(monkeypatch, tmp_path, voz_falsa):
    def _se_cuelga(cmd, **kw):
        assert kw.get("timeout"), "la llamada a Piper no lleva timeout: un cuelgue sería eterno"
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(subprocess, "run", _se_cuelga)
    with pytest.raises(VozNoDisponible) as exc:
        WhisperPiperVoice(piper_voice=voz_falsa, out_dir=str(tmp_path))._tts_sync("hola", str(tmp_path / "o.wav"))
    assert "tiempo" in str(exc.value).lower()


def test_un_piper_que_falla_se_declara_como_voz_no_disponible(monkeypatch, tmp_path, voz_falsa):
    def _falla(cmd, **kw):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", _falla)
    with pytest.raises(VozNoDisponible):
        WhisperPiperVoice(piper_voice=voz_falsa, out_dir=str(tmp_path))._tts_sync("hola", str(tmp_path / "o.wav"))


def test_CONTROL_con_una_voz_valida_se_invoca_al_sintetizador_con_su_ruta(monkeypatch, tmp_path, voz_falsa):
    visto: dict = {}

    def _ok(cmd, **kw):
        visto["cmd"] = cmd
        visto["timeout"] = kw.get("timeout")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", _ok)
    salida = str(tmp_path / "o.wav")
    WhisperPiperVoice(piper_voice=voz_falsa, out_dir=str(tmp_path))._tts_sync("hola", salida)
    assert voz_falsa in visto["cmd"] and salida in visto["cmd"], visto
    assert visto["timeout"] and visto["timeout"] > 0


def test_la_transcripcion_declara_el_idioma_en_vez_de_detectarlo(monkeypatch, tmp_path):
    """Medido: detectar el idioma en cada turno costaba 58,0 s frente a 25,6 s declarandolo (mediana,
    orden alternado). AURA habla espanol y eso no cambia turno a turno."""
    visto: dict = {}

    class _ModeloFalso:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, wav, **kw):
            visto.update(kw)
            return ([], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloFalso)
    wav = tmp_path / "a.wav"
    _wav_valido(wav)
    WhisperPiperVoice(piper_voice="x")._stt_sync(str(wav))
    assert visto.get("language") == IDIOMA == "es", visto


@pytest.mark.asyncio
async def test_una_transcripcion_colgada_no_espera_para_siempre(monkeypatch, tmp_path):
    """Hallazgo de la auditoría (2026-09-15): `LIMITE_TRANSCRIPCION_S` existía y NADIE la usaba.

    Declaraba una protección que el código no daba. Una USB que deja de responder a mitad de
    `transcribe()` colgaba el turno indefinidamente, que es justo el defecto que esta misión corrige
    para el sintetizador. El tope libera EL TURNO; el hilo del executor no se puede matar en Python.
    """
    import threading

    suelta = threading.Event()

    class _ModeloColgado:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, wav, **kw):
            suelta.wait(30)  # se cuelga; el turno no debe esperarlo
            return ([], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloColgado)
    wav = tmp_path / "a.wav"
    _wav_valido(wav)
    voz = WhisperPiperVoice(piper_voice="x", limite_transcripcion_s=1)
    try:
        with pytest.raises(VozNoDisponible) as exc:
            await voz.stt(str(wav), "t")
        assert "tiempo limite" in str(exc.value).lower(), exc.value
    finally:
        suelta.set()  # no se deja un hilo colgado en la batería


@pytest.mark.asyncio
async def test_CONTROL_una_transcripcion_normal_no_la_corta_el_tope(monkeypatch, tmp_path):
    class _ModeloRapido:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, wav, **kw):
            class _S:
                text = "hola"

            return ([_S()], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloRapido)
    wav = tmp_path / "a.wav"
    _wav_valido(wav)
    assert await WhisperPiperVoice(piper_voice="x", limite_transcripcion_s=30).stt(str(wav), "t") == "hola"


# ================================================ STT: UNA FRASE CORTA NO SE ALUCINA (2026-09-27) --
#
# Medido `[EJEC]` con los modelos reales de la USB: «¿Cómo me llamo?» sintetizado por Piper (1,2 s)
# llegaba a AURA como «¡Vamos, me llamo!». `faster-whisper-base` alucina con fragmentos muy cortos;
# ni temperatura 0 ni cortar el contexto lo corregían. Con 1 s de silencio a cada lado, la misma
# grabación da «como me llamo». La orden hablada más corta es justo la más habitual.

import wave as _wave  # noqa: E402


def _wav_valido(ruta, segundos=0.5, sr=16000):
    with _wave.open(str(ruta), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(b"\x00\x00" * int(segundos * sr))
    return str(ruta)


def test_la_transcripcion_recibe_el_audio_con_un_margen_de_silencio(monkeypatch, tmp_path):
    recibido: dict = {}

    class _Modelo:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, audio, **kw):
            recibido["audio"] = audio
            return ([], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _Modelo)
    wav = _wav_valido(tmp_path / "corto.wav", segundos=0.5)

    WhisperPiperVoice(piper_voice="x")._stt_sync(wav)

    muestras = len(recibido["audio"])
    assert muestras >= int(0.5 * 16000) + 2 * 16000, (
        f"el audio llego sin margen ({muestras} muestras): las frases cortas se alucinan"
    )


def test_CONTROL_el_margen_no_altera_el_contenido_del_audio(monkeypatch, tmp_path):
    """Sin control, sustituir el audio por silencio de la longitud correcta pasaría la anterior."""
    import numpy as np

    recibido: dict = {}

    class _Modelo:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, audio, **kw):
            recibido["audio"] = audio
            return ([], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _Modelo)
    wav = tmp_path / "tono.wav"
    with _wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes((np.full(8000, 12000, dtype=np.int16)).tobytes())

    WhisperPiperVoice(piper_voice="x")._stt_sync(str(wav))

    assert float(np.abs(recibido["audio"]).max()) > 0.3, "el contenido real del audio se perdio"


def test_la_transcripcion_lleva_el_vocabulario_de_AURA(monkeypatch, tmp_path):
    """Medido `[EJEC]` sobre 15 órdenes cortas sintetizadas: solo margen, 1/15 exactas; margen más
    vocabulario, 12/15. El vocabulario es un texto local que orienta al modelo: no sale de la máquina."""
    visto: dict = {}

    class _Modelo:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, audio, **kw):
            visto.update(kw)
            return ([], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _Modelo)
    WhisperPiperVoice(piper_voice="x")._stt_sync(_wav_valido(tmp_path / "v.wav"))

    prompt = visto.get("initial_prompt") or ""
    assert "¿Cómo me llamo?" in prompt and "¿Qué encontraste?" in prompt, prompt


# ============================================ TTS: LA VOZ SE CARGA UNA VEZ, NO EN CADA FRASE (2026-09-27)
#
# Medido `[EJEC]` en HC-1 con la voz real: el CLI de Piper tardaba 5,9 s por frase porque RECARGA el
# modelo cada vez; con la voz ya cargada, 1,8-2,0 s (carga única: 3,4 s). Es el mayor recorte de
# latencia disponible sin tocar el modelo, sobre el criterio que decide el lanzamiento (CM1, Bible 2.5 §5.1).

import asyncio as _aio  # noqa: E402


class _VozCargada:
    cargas = 0

    def __init__(self, espera=0.0):
        self.espera = espera
        self.frases: list[str] = []

    def synthesize_wav(self, texto, destino):
        import time as _t

        _t.sleep(self.espera)
        self.frases.append(texto)
        destino.setnchannels(1)
        destino.setsampwidth(2)
        destino.setframerate(22050)
        destino.writeframes(b"\x00\x00" * 100)


def _con_voz_cargable(monkeypatch, voz):
    import piper

    def _load(ruta, *a, **kw):
        _VozCargada.cargas += 1
        return voz

    monkeypatch.setattr(piper.PiperVoice, "load", staticmethod(_load))


def test_la_voz_se_carga_UNA_vez_y_no_se_invoca_el_CLI(monkeypatch, tmp_path, voz_falsa):
    voz = _VozCargada()
    _VozCargada.cargas = 0
    _con_voz_cargable(monkeypatch, voz)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("CLI")))
    adaptador = WhisperPiperVoice(piper_voice=voz_falsa, out_dir=str(tmp_path))

    for i in range(3):
        _aio.run(adaptador.tts(f"frase {i}", f"T{i}"))

    assert _VozCargada.cargas == 1, f"la voz se cargo {_VozCargada.cargas} veces"
    assert voz.frases == ["frase 0", "frase 1", "frase 2"]


def test_la_sintesis_con_voz_cargada_TAMBIEN_tiene_tope(monkeypatch, tmp_path, voz_falsa):
    """La garantía del CLI (un Piper colgado no cuelga el turno) no puede perderse en el camino rápido."""
    _con_voz_cargable(monkeypatch, _VozCargada(espera=2.0))
    adaptador = WhisperPiperVoice(piper_voice=voz_falsa, out_dir=str(tmp_path), limite_sintesis_s=0.3)

    with pytest.raises(VozNoDisponible, match="tiempo"):
        _aio.run(adaptador.tts("hola", "T9"))


def test_si_la_voz_no_se_puede_cargar_se_usa_el_CLI(monkeypatch, tmp_path, voz_falsa):
    import piper

    monkeypatch.setattr(
        piper.PiperVoice, "load", staticmethod(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("onnx roto")))
    )
    visto = {}
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: visto.setdefault("cmd", cmd))
    _aio.run(WhisperPiperVoice(piper_voice=voz_falsa, out_dir=str(tmp_path)).tts("hola", "T8"))
    assert "piper" in visto["cmd"], "sin voz cargable no se recurrio al sintetizador de linea de ordenes"


# ------------------------------- el eco del vocabulario de Whisper ([EJEC] cierre semana 2) --


@pytest.mark.parametrize(
    "oido, esperado",
    [
        ("¿Qué hay conectado? ¿Qué hay conectado?", "¿Qué hay conectado?"),
        ("¿Qué? ¿Qué?", "¿Qué?"),
        ("Apaga la tele. apaga la tele.", "Apaga la tele."),
    ],
)
def test_una_frase_repetida_por_el_eco_del_vocabulario_se_oye_una_vez(oido, esperado):
    """[EJEC] por el aire: Whisper devolvió «¿Qué hay conectado? ¿Qué hay conectado?» —eco del
    `initial_prompt`— y la pregunta cayó en la pared de memoria en vez de en el entorno."""
    from aura_skeleton.adapters.voice_real import sin_eco

    assert sin_eco(oido) == esperado


@pytest.mark.parametrize("oido", ["Me llamo Mauricio. ¿Cómo me llamo?", "Sí. No.", "No, no lo hagas.", ""])
def test_CONTROL_frases_distintas_o_repeticion_dentro_de_una_frase_no_se_tocan(oido):
    from aura_skeleton.adapters.voice_real import sin_eco

    assert sin_eco(oido) == oido


def test_la_transcripcion_real_pasa_por_el_filtro_de_eco(monkeypatch, tmp_path):
    """El cableado, no solo la función: lo que devuelve `_stt_sync` ya llega sin el eco."""

    class _Segmento:
        def __init__(self, text):
            self.text = text

    class _ModeloConEco:
        def __init__(self, nombre, **kw):
            pass

        def transcribe(self, wav, **kw):
            return ([_Segmento(" ¿Qué hay conectado?"), _Segmento(" ¿Qué hay conectado?")], None)

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloConEco)
    wav = tmp_path / "a.wav"
    _wav_valido(wav)
    assert WhisperPiperVoice(piper_voice="x")._stt_sync(str(wav)) == "¿Qué hay conectado?"


# ------------------ el vocabulario de pistas no puede FABRICAR una acción ([EJEC] cierre S2) --


def _frases_del_vocabulario():
    import re

    from aura_skeleton.adapters.voice_real import _VOCABULARIO

    return [f for f in re.split(r"(?<=[.?!])\s+", _VOCABULARIO) if f]


def test_ninguna_frase_del_vocabulario_es_por_si_sola_una_orden_o_una_confirmacion():
    """[EJEC] por el aire: ante audio confuso Whisper devolvió frases del `initial_prompt` que nadie dijo
    («Sí.» → «¿Qué hiciste?»). Si el vocabulario contiene una orden o un «sí», Whisper puede fabricar una
    acción o aprobar una propuesta. Se comprueba con los reconocedores REALES del Core, no con una lista."""
    from aura_skeleton.core import hogar, ordenes
    from aura_skeleton.core.operaciones import ESPECIFICACIONES

    disponibles = set(ESPECIFICACIONES)
    peligrosas = [
        f
        for f in _frases_del_vocabulario()
        if hogar.reconocer(f)
        or hogar.confirmacion(f) is not None
        or ordenes.reconocer(f, disponibles)
        or ordenes.reconocer_con_ruta(f, disponibles)
    ]
    assert peligrosas == [], f"el vocabulario puede fabricar una acción: {peligrosas}"


def test_CONTROL_el_vocabulario_sigue_teniendo_las_preguntas_frecuentes():
    frases = _frases_del_vocabulario()
    assert "¿Cómo me llamo?" in frases and "¿Qué hay conectado?" in frases, frases
