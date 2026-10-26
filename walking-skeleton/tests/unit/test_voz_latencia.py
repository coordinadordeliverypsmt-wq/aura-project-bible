"""Latencia de la voz (perfil E2E real 2026-10-04): captura con fin de habla, «¿Sí?» cacheado,
precarga del STT e instrumentación por etapa. Pruebas con dobles: sin micrófono ni modelos."""

from __future__ import annotations

import asyncio
import os
import stat
import wave

import pytest

from aura_skeleton import __main__ as principal
from aura_skeleton import observability as obs
from aura_skeleton.adapters.microfono import Microfono

BLOQUE = 4000  # 125 ms a 16 kHz mono s16le
SILENCIO = (b"\x0a\x00") * (BLOQUE // 2)  # amplitud 10: ruido de fondo
VOZ = (b"\xb8\x0b") * (BLOQUE // 2)  # amplitud 3000: habla


class _Flujo:
    """Doble del flujo del micrófono: entrega los bloques dados y luego silencio sin fin."""

    def __init__(self, bloques, falla_en=None):
        self._bloques = list(bloques)
        self.leidos = 0
        self.cerrado = False
        self._falla_en = falla_en

    def read(self, n):
        assert n == BLOQUE
        self.leidos += 1
        if self._falla_en is not None and self.leidos == self._falla_en:
            raise OSError("tubería rota")
        return self._bloques.pop(0) if self._bloques else SILENCIO

    def close(self):
        self.cerrado = True


def _mic(tmp_path):
    return Microfono(directorio=str(tmp_path), segundos=5, ejecutar=lambda *a, **k: None, disponible=lambda _p: True)


# ------------------------------------------------------------------ O1: fin de habla --


def test_corta_tras_700_ms_de_silencio_una_vez_que_hubo_habla(tmp_path):
    flujo = _Flujo([SILENCIO] * 2 + [VOZ] * 4 + [SILENCIO] * 20)
    mic = _mic(tmp_path)

    ruta = mic.escuchar_hasta_silencio("t1", flujo=flujo)

    # 2 de calibrado + 4 de voz + 6 de silencio (750 ms >= 700 ms) = 12 bloques
    assert flujo.leidos == 12, flujo.leidos
    assert mic.ultimo_corte == "silencio"
    assert os.path.isfile(ruta)


def test_una_pausa_breve_entre_palabras_NO_corta(tmp_path):
    flujo = _Flujo([SILENCIO] * 2 + [VOZ] * 3 + [SILENCIO] * 5 + [VOZ] * 3 + [SILENCIO] * 20)
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    # 5 bloques = 625 ms < 700 ms: sigue; corta tras la segunda palabra: 2+3+5+3+6 = 19
    assert flujo.leidos == 19, flujo.leidos
    assert mic.ultimo_corte == "silencio"


def test_sin_voz_graba_los_5_segundos_de_siempre(tmp_path):
    """Sin habla detectada no se ahorra nada pero tampoco se empeora: los 5 s de la grabación fija de antes.
    Medido 2026-10-04: a 27 % de ganancia la voz llegó con RMS 930-2150 y la sala con 1265-2179; un corte
    temprano por «sin voz» habría tirado órdenes reales (regresión). Solo se corta antes con evidencia."""
    flujo = _Flujo([])
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    assert flujo.leidos == 40, flujo.leidos  # 5 s / 125 ms
    assert mic.ultimo_corte == "sin_voz"


def test_un_golpe_aislado_de_ruido_no_provoca_un_corte_prematuro(tmp_path):
    """Un solo bloque fuerte (un golpe, una tos lejana) seguido de calma NO es una frase: no se corta a los
    ~1 s antes de que la persona empiece a hablar; se sigue escuchando."""
    flujo = _Flujo([SILENCIO] * 2 + [VOZ] + [SILENCIO] * 10 + [VOZ] * 4 + [SILENCIO] * 20)
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    # no corta tras el golpe (habría sido en el bloque 2+1+6=9): oye la frase real y corta después de ella
    assert flujo.leidos == 2 + 1 + 10 + 4 + 6, flujo.leidos
    assert mic.ultimo_corte == "silencio"


def test_con_voz_continua_el_tope_es_6_segundos(tmp_path):
    flujo = _Flujo([SILENCIO] * 2 + [VOZ] * 200)
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    assert flujo.leidos == 48, flujo.leidos  # 6 s / 125 ms
    assert mic.ultimo_corte == "tope"


def test_el_umbral_se_adapta_al_ruido_de_fondo(tmp_path):
    """CONTROL: con un ruido de fondo alto y constante, ese ruido NO es habla."""
    ruidoso = (b"\x90\x01") * (BLOQUE // 2)  # amplitud 400 (> umbral mínimo) constante
    flujo = _Flujo([ruidoso] * 100)
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    assert mic.ultimo_corte == "sin_voz", "el ruido constante se tomó por habla"


def test_el_golpe_de_arranque_de_parecord_no_ensordece_ni_cuenta_como_habla(tmp_path):
    """`[EJEC]` HC-1: parecord arranca con ~19000/9000/1900 RMS y luego el ambiente (~300)."""
    golpe = [(b"\xe8\x4a") * (BLOQUE // 2), (b"\xc4\x24") * (BLOQUE // 2), (b"\x84\x07") * (BLOQUE // 2)]
    flujo = _Flujo(golpe + [SILENCIO] * 2 + [VOZ] * 3 + [SILENCIO] * 20)
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    assert mic.ultimo_corte == "silencio"
    assert flujo.leidos == 3 + 2 + 3 + 6, flujo.leidos  # el golpe no fue habla; la voz sí se oyó


def test_el_wav_contiene_el_audio_leido_y_es_privado(tmp_path):
    flujo = _Flujo([SILENCIO] * 2 + [VOZ] * 4 + [SILENCIO] * 20)
    mic = _mic(tmp_path)

    ruta = mic.escuchar_hasta_silencio("t9", flujo=flujo)

    assert os.path.basename(ruta) == "entrada_t9.wav"
    assert os.path.dirname(ruta) == str(tmp_path)
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600
    with wave.open(ruta) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() == 12 * (BLOQUE // 2)
        datos = w.readframes(w.getnframes())
    assert datos == SILENCIO * 2 + VOZ * 4 + SILENCIO * 6


def test_el_flujo_se_cierra_siempre_tambien_si_falla(tmp_path):
    ok = _Flujo([SILENCIO] * 2 + [VOZ] * 2)
    _mic(tmp_path).escuchar_hasta_silencio("t1", flujo=ok)
    assert ok.cerrado

    roto = _Flujo([SILENCIO] * 2, falla_en=3)
    with pytest.raises(Exception):  # noqa: B017, PT011
        _mic(tmp_path).escuchar_hasta_silencio("t2", flujo=roto)
    assert roto.cerrado
    assert not os.path.exists(os.path.join(str(tmp_path), "entrada_t2.wav")), "quedó audio a medias"


def test_flujo_sin_audio_se_declara_como_el_micro_vacio(tmp_path):
    from aura_skeleton.adapters.microfono import DispositivoNoDisponible

    class _Vacio(_Flujo):
        def read(self, n):
            self.leidos += 1
            return b""

    flujo = _Vacio([])
    with pytest.raises(DispositivoNoDisponible):
        _mic(tmp_path).escuchar_hasta_silencio("t1", flujo=flujo)
    assert flujo.cerrado


# ------------------------------------------------- O1: _turno_de_voz elige la captura --


class _MicDoble:
    def __init__(self):
        self.eventos = []
        self.ultimo_corte = "silencio"

    def escuchar(self, tid):
        self.eventos.append("fija")
        return "/tmp/aura/f.wav"

    def escuchar_hasta_silencio(self, tid):
        self.eventos.append("hasta_silencio")
        return "/tmp/aura/s.wav"

    def reproducir(self, ruta):
        pass

    def descartar(self, ruta):
        pass


class _Sist:
    orquestador = object()


@pytest.fixture
def turno_vacio(monkeypatch):
    async def _t(orq, texto, tid, activado=False):
        return {"say": "", "audio": None}

    monkeypatch.setattr(principal, "_turno", _t)


def test_turno_activado_usa_la_captura_con_fin_de_habla(turno_vacio):
    mic = _MicDoble()
    asyncio.run(principal._turno_de_voz(_Sist(), mic, "t1", activado=True))
    assert mic.eventos == ["hasta_silencio"]


def test_pulsar_para_hablar_sigue_con_duracion_fija(turno_vacio):
    mic = _MicDoble()
    asyncio.run(principal._turno_de_voz(_Sist(), mic, "t1", activado=False))
    assert mic.eventos == ["fija"]


def test_activado_sin_el_metodo_cae_a_la_captura_fija(turno_vacio):
    class _Viejo(_MicDoble):
        escuchar_hasta_silencio = None  # type: ignore[assignment]

    mic = _Viejo()
    asyncio.run(principal._turno_de_voz(_Sist(), mic, "t1", activado=True))
    assert mic.eventos == ["fija"]


# ------------------------------------------------------------------ O2: «¿Sí?» cacheado --


class _VozContada:
    def __init__(self, directorio):
        self.llamadas = 0
        self._dir = directorio
        self.falla = False

    async def tts(self, texto, tid):
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("piper caído")
        ruta = os.path.join(self._dir, f"resp_{tid}.wav")
        with open(ruta, "wb") as f:
            f.write(b"RIFFfake")
        return ruta


class _MicAcuse:
    def __init__(self):
        self.reproducidos = []
        self.descartados = []

    def reproducir(self, ruta):
        self.reproducidos.append(ruta)

    def descartar(self, ruta):
        self.descartados.append(ruta)


def _sistema_con(voz):
    class _O:
        voice = voz

    class _S:
        orquestador = _O()

    return _S()


def test_el_acuse_se_sintetiza_una_sola_vez_y_se_reproduce_las_dos(tmp_path):
    voz = _VozContada(str(tmp_path))
    mic = _MicAcuse()
    sistema = _sistema_con(voz)

    asyncio.run(principal._acusar_llamada(sistema, mic, "a1"))
    asyncio.run(principal._acusar_llamada(sistema, mic, "a2"))

    assert voz.llamadas == 1
    assert len(mic.reproducidos) == 2 and mic.reproducidos[0] == mic.reproducidos[1]
    assert mic.descartados == [], "el acuse es una frase constante de AURA: no se descarta"
    assert os.path.isfile(mic.reproducidos[0])


def test_si_el_wav_cacheado_desaparece_se_regenera(tmp_path):
    voz = _VozContada(str(tmp_path))
    mic = _MicAcuse()
    sistema = _sistema_con(voz)
    asyncio.run(principal._acusar_llamada(sistema, mic, "a1"))
    os.remove(mic.reproducidos[0])

    asyncio.run(principal._acusar_llamada(sistema, mic, "a2"))

    assert voz.llamadas == 2
    assert os.path.isfile(mic.reproducidos[1])


def test_un_fallo_del_tts_no_rompe_el_turno_ni_se_cachea(tmp_path):
    voz = _VozContada(str(tmp_path))
    voz.falla = True
    mic = _MicAcuse()
    sistema = _sistema_con(voz)

    asyncio.run(principal._acusar_llamada(sistema, mic, "a1"))  # no propaga
    voz.falla = False
    asyncio.run(principal._acusar_llamada(sistema, mic, "a2"))

    assert mic.reproducidos and voz.llamadas == 2


def test_la_purga_de_arranque_borra_la_voz_del_usuario(tmp_path):
    """El acuse cacheado vive solo lo que dura el proceso (se re-sintetiza una vez al arrancar); la purga sigue
    borrando lo que importa: la voz del usuario que un proceso muerto dejó en disco."""
    (tmp_path / "entrada_old.wav").write_bytes(b"x")
    _mic(tmp_path)
    assert not (tmp_path / "entrada_old.wav").exists()


def test_escuchar_continuo_presintetiza_y_precarga_antes_de_declararse_atenta(tmp_path, monkeypatch, capsys):
    orden = []

    class _V(_VozContada):
        def precargar(self):
            orden.append("precargar")

        async def tts(self, texto, tid):
            orden.append("tts")
            return await super().tts(texto, tid)

    voz = _V(str(tmp_path))
    monkeypatch.setattr(principal, "_informe", lambda _s: "")

    class _Oido:
        def esperar_llamada(self):
            return False

    asyncio.run(principal._escuchar_continuo(_sistema_con(voz), _MicAcuse(), _Oido(), telemetria=True))

    assert orden == ["precargar", "tts"] or orden == ["tts", "precargar"], orden
    assert voz.llamadas == 1
    assert capsys.readouterr().out.index("AURA está atenta") > 0


# ------------------------------------------------------------------ O3: precarga STT --


def test_precargar_carga_whisper_una_vez_y_el_primer_stt_no_lo_reconstruye(monkeypatch, tmp_path):
    import faster_whisper

    from aura_skeleton.adapters import voice_real as vr

    construidos = []

    class _Modelo:
        def __init__(self, nombre, **kw):
            construidos.append(nombre)

        def transcribe(self, wav, **kw):
            return ([], None)

    monkeypatch.setattr(faster_whisper, "WhisperModel", _Modelo)
    monkeypatch.setattr(vr, "_tramos_de_habla", lambda audio: [(0, len(audio))])
    cargas_piper = []
    voz = vr.WhisperPiperVoice(piper_voice="x", out_dir=str(tmp_path))
    monkeypatch.setattr(voz, "_ruta_de_voz", lambda: "ruta.onnx")
    monkeypatch.setattr(voz, "_voz_cargada", lambda ruta: cargas_piper.append(ruta))

    voz.precargar()
    assert construidos == ["base"] and cargas_piper == ["ruta.onnx"]

    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    voz._stt_sync(str(wav))
    assert construidos == ["base"], "el primer turno volvió a construir el modelo"


# ------------------------------------------------------------------ O4: perfil LAT --


def _lat():
    return [r for r in obs._records if r["level"] == "LAT" and r["module"] == "voz"]


def test_se_registra_la_latencia_por_etapa_sin_audit_ni_texto(tmp_path, monkeypatch):
    antes = len(_lat())

    async def _t(orq, texto, tid, activado=False):
        return {"say": "secreto del usuario", "audio": None}

    monkeypatch.setattr(principal, "_turno", _t)
    mic = _MicDoble()
    voz = _VozContada(str(tmp_path))
    asyncio.run(principal._acusar_llamada(_sistema_con(voz), _MicAcuse(), "L1"))
    asyncio.run(principal._turno_de_voz(_Sist(), mic, "L1", activado=True))

    nuevos = _lat()[antes:]
    etapas = [r["msg"].split()[0] for r in nuevos]
    # «respuesta» = fin de la reproducción de la respuesta hablada (T10 del perfil E2E).
    assert etapas == ["acuse", "captura", "turno", "respuesta"], etapas
    for r in nuevos:
        assert "ms=" in r["msg"] or r.get("ms") is not None
        assert not r.get("audit")
        assert "secreto" not in str(r) and "/tmp/aura" not in str(r)
    assert "corte=silencio" in nuevos[1]["msg"]


def test_un_golpe_de_arranque_tras_un_primer_bloque_tranquilo_no_abre_el_corte(tmp_path):
    """La ventana de calibración (los 2 primeros bloques no cuentan como habla) protege el caso que el mínimo
    de ruido NO cubre: un primer bloque tranquilo y LUEGO el golpe de parecord. Sin ella, el golpe del bloque 2
    y su cola en el 3 sumarían 250 ms de «habla» y AURA cortaría la escucha antes de que la persona hable."""
    tranquilo = (b"\x2c\x01") * (BLOQUE // 2)  # ~300 RMS, el ambiente de HC-1
    golpe = (b"\xe8\x4a") * (BLOQUE // 2)  # ~19000 RMS, el golpe de arranque medido
    flujo = _Flujo([tranquilo, golpe, golpe] + [SILENCIO] * 60)
    mic = _mic(tmp_path)

    mic.escuchar_hasta_silencio("t1", flujo=flujo)

    assert mic.ultimo_corte == "sin_voz", "el golpe de arranque se tomó por una frase"
    assert flujo.leidos == 40, flujo.leidos  # sigue escuchando los 5 s de siempre
