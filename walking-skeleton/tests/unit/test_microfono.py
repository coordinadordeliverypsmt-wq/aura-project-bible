"""El micrófono y el altavoz de AURA, reales y gobernados (campaña, 2026-09-27).

MEDIDO ANTES DE ESCRIBIRLO `[EJEC]`: la máquina tiene micrófono interno (HDA Intel, entrada
analógica en PulseAudio, 2 s capturados a 16 kHz con RMS 1694) y la cadena Whisper -> AURA -> Piper
funcionaba con los modelos de la USB. Lo que no existía era el primer y el último eslabón: nadie
grababa del micrófono y nadie reproducía el WAV que Piper generaba —la ruta se tiraba—.

LO QUE ESTE ADAPTADOR NO HACE, A PROPÓSITO:
- **No escucha por su cuenta.** Graba solo cuando se le pide, durante un tiempo acotado. La escucha
  continua con palabra de activación está autorizada (`Bible 6.2`) pero es otra pieza; empezar por
  pulsar-para-hablar es la opción más estricta.
- **No conserva lo que oye.** La grabación se descarta tras transcribirla: un directorio de WAV del
  usuario sería un archivo de voz que nadie ha decidido crear.
- **No sale de la máquina.** `parecord` y `paplay` son locales (`D24`).
"""

from __future__ import annotations

import os
import wave

import pytest

from aura_skeleton.adapters.microfono import DispositivoNoDisponible, Microfono


class _Ejecutor:
    """Doble de `subprocess.run`: registra la orden y, si es una grabación, escribe un WAV."""

    def __init__(self, frames: int = 16000, falla: bool = False):
        self.ordenes: list[list[str]] = []
        self._frames = frames
        self._falla = falla

    def __call__(self, orden, **kw):
        self.ordenes.append(list(orden))
        self.kw = kw
        if self._falla:
            raise OSError("dispositivo ocupado")
        if "parecord" in orden:
            with wave.open(orden[-1], "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(b"\x01\x00" * self._frames)
        return None


def _mic(tmp_path, **kw):
    return Microfono(directorio=str(tmp_path), segundos=3, ejecutar=_Ejecutor(**kw), disponible=lambda _p: True)


def test_graba_mono_a_16kHz_con_un_tiempo_acotado(tmp_path):
    mic = _mic(tmp_path)
    ruta = mic.escuchar("T1")
    orden = mic._ejecutar.ordenes[0]
    assert os.path.isfile(ruta)
    assert "--rate=16000" in orden and "--channels=1" in orden
    assert orden[:2] == ["timeout", "3"], f"la grabacion no tiene tope: {orden}"


def test_una_grabacion_vacia_se_declara_no_disponible(tmp_path):
    """Sin esto, Whisper recibe un WAV vacío y alucina texto sobre el silencio."""
    with pytest.raises(DispositivoNoDisponible):
        _mic(tmp_path, frames=0).escuchar("T2")


def test_un_fallo_del_grabador_se_declara_no_disponible(tmp_path):
    with pytest.raises(DispositivoNoDisponible):
        _mic(tmp_path, falla=True).escuchar("T3")


def test_descartar_borra_la_grabacion(tmp_path):
    mic = _mic(tmp_path)
    ruta = mic.escuchar("T4")
    mic.descartar(ruta)
    assert not os.path.exists(ruta), "la voz del usuario quedo guardada en disco"


def test_reproducir_usa_el_altavoz_con_tope(tmp_path):
    mic = _mic(tmp_path)
    wav = tmp_path / "resp.wav"
    wav.write_bytes(b"RIFF")
    assert mic.reproducir(str(wav)) is True
    orden = mic._ejecutar.ordenes[-1]
    assert "paplay" in orden and str(wav) in orden
    assert mic._ejecutar.kw.get("timeout"), "la reproduccion no tiene tope de espera"


def test_reproducir_sin_audio_no_invoca_al_altavoz(tmp_path):
    mic = _mic(tmp_path)
    assert mic.reproducir(None) is False
    assert mic._ejecutar.ordenes == []


def test_sin_herramientas_de_audio_el_arranque_lo_dice(tmp_path):
    mic = Microfono(directorio=str(tmp_path), disponible=lambda _p: False)
    with pytest.raises(DispositivoNoDisponible):
        mic.comprobar()


# ---------------------------------------------- el ciclo completo en la consola (`--escuchar`) --

import asyncio  # noqa: E402

from aura_skeleton import __main__ as principal  # noqa: E402


class _Sistema:
    orquestador = object()


_SISTEMA = _Sistema()


class _MicDoble:
    def __init__(self):
        self.eventos: list[str] = []

    def escuchar(self, tid):
        self.eventos.append("escuchar")
        return "/tmp/aura/entrada_doble.wav"

    def reproducir(self, ruta):
        self.eventos.append(f"reproducir:{ruta}")
        return True

    def descartar(self, ruta):
        self.eventos.append(f"descartar:{ruta}")


def test_enter_vacio_graba_conversa_descarta_y_reproduce(monkeypatch):
    entradas = iter(["", EOFError])

    def _input(_prompt):
        e = next(entradas)
        if e is EOFError:
            raise EOFError
        return e

    visto: dict = {}

    async def _turno(orq, texto, tid, activado=False):
        visto["texto"] = texto
        visto["activado"] = activado
        return {"say": "Te llamas Mauricio.", "audio": "/tmp/aura/resp_x.wav"}

    monkeypatch.setattr("builtins.input", _input)
    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    mic = _MicDoble()

    asyncio.run(principal._conversar(_SISTEMA, telemetria=True, microfono=mic))

    assert visto["texto"] == "/tmp/aura/entrada_doble.wav", "el turno no recibio la grabacion"
    assert visto["activado"] is False, (
        "pulsar-para-hablar NO es activación por palabra (C1): no puede abrir la llave de voz"
    )
    assert mic.eventos == [
        "escuchar",
        "reproducir:/tmp/aura/resp_x.wav",
        "descartar:/tmp/aura/entrada_doble.wav",
        "descartar:/tmp/aura/resp_x.wav",
    ], mic.eventos


def test_la_grabacion_se_descarta_aunque_el_turno_falle(monkeypatch):
    """La privacidad no puede depender de que todo vaya bien."""
    entradas = iter(["", EOFError])

    def _input(_prompt):
        e = next(entradas)
        if e is EOFError:
            raise EOFError
        return e

    async def _turno(orq, texto, tid, activado=False):
        raise RuntimeError("fallo del turno")

    monkeypatch.setattr("builtins.input", _input)
    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    mic = _MicDoble()

    asyncio.run(principal._conversar(_SISTEMA, telemetria=True, microfono=mic))

    assert "descartar:/tmp/aura/entrada_doble.wav" in mic.eventos


def test_CONTROL_sin_microfono_un_enter_vacio_no_graba_nada(monkeypatch):
    entradas = iter(["", EOFError])

    def _input(_prompt):
        e = next(entradas)
        if e is EOFError:
            raise EOFError
        return e

    llamado = []

    async def _turno(orq, texto, tid, activado=False):
        llamado.append(texto)
        return {"say": ""}

    monkeypatch.setattr("builtins.input", _input)
    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")

    asyncio.run(principal._conversar(_SISTEMA, telemetria=True, microfono=None))

    assert llamado == [], "sin microfono, un Enter vacio produjo un turno"


# -------------------------------------- hallazgos de la auditoría de seguridad (2026-09-27)


def test_el_audio_de_la_RESPUESTA_tambien_se_descarta(monkeypatch):
    """ALTO: `resp_*.wav` se acumulaba en /tmp/aura con lo que AURA recita («tu color favorito es…»)."""
    entradas = iter(["", EOFError])

    def _input(_prompt):
        e = next(entradas)
        if e is EOFError:
            raise EOFError
        return e

    async def _turno(orq, texto, tid, activado=False):
        return {"say": "Te llamas Mauricio.", "audio": "/tmp/aura/resp_x.wav"}

    monkeypatch.setattr("builtins.input", _input)
    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    mic = _MicDoble()

    asyncio.run(principal._conversar(_SISTEMA, telemetria=True, microfono=mic))

    assert "descartar:/tmp/aura/resp_x.wav" in mic.eventos, mic.eventos


def test_el_directorio_de_audio_es_privado(tmp_path):
    """MEDIO: /tmp/aura quedaba 775 y los WAV 664: cualquier usuario local podía leer la voz."""
    d = tmp_path / "audio"
    Microfono(directorio=str(d), ejecutar=_Ejecutor(), disponible=lambda _p: True)
    assert (d.stat().st_mode & 0o777) == 0o700


def test_un_directorio_de_audio_que_es_un_ENLACE_se_rechaza(tmp_path):
    """MEDIO: un enlace plantado en /tmp haría escribir la voz del usuario donde decida otro."""
    real = tmp_path / "otro"
    real.mkdir()
    enlace = tmp_path / "audio"
    enlace.symlink_to(real)
    with pytest.raises(DispositivoNoDisponible, match="enlace"):
        Microfono(directorio=str(enlace), ejecutar=_Ejecutor(), disponible=lambda _p: True)


def test_descartar_no_propaga_un_fallo_de_borrado(tmp_path, monkeypatch):
    """BAJO: un fallo al borrar dentro del `finally` enmascararía el error original del turno."""
    mic = _mic(tmp_path)
    monkeypatch.setattr(os, "remove", lambda _p: (_ for _ in ()).throw(PermissionError("x")))
    mic.descartar(str(tmp_path / "x.wav"))


def test_en_modo_TEXTO_el_audio_de_la_respuesta_tambien_se_borra(monkeypatch, tmp_path):
    """Encontrado en la demo física `[EJEC]`: con el stack real, un turno ESCRITO también sintetiza la
    respuesta, y sin micrófono nadie la reproducía ni la borraba: `resp_*.wav` se acumulaba con lo que
    AURA recitaba. El mismo hallazgo ALTO de la auditoría, por el camino de texto."""
    wav = tmp_path / "resp_texto.wav"
    wav.write_bytes(b"RIFF")

    async def _turno(orq, texto, tid, activado=False):
        return {"say": "Te llamas Mauricio.", "audio": str(wav)}

    monkeypatch.setattr(principal, "_turno", _turno)
    asyncio.run(principal._turno_de_voz(_SISTEMA, None, "T1", "¿cómo me llamo?"))

    assert not wav.exists(), "el audio de una respuesta escrita quedo en disco"


def test_al_arrancar_se_purga_el_audio_de_una_sesion_interrumpida(tmp_path):
    """Encontrado `[EJEC]` en la demo de la semana 2: un tope mató el proceso a mitad de turno y la
    grabación del usuario quedó en disco —un `finally` no corre si el proceso muere—. Al abrir el
    micrófono se purgan los audios efímeros que hubieran quedado; lo demás del directorio no se toca."""
    for nombre in ("entrada_viejo.wav", "resp_viejo.wav", "otra_cosa.txt"):
        (tmp_path / nombre).write_bytes(b"x")

    Microfono(directorio=str(tmp_path), ejecutar=_Ejecutor(), disponible=lambda _p: True)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["otra_cosa.txt"]


def test_reproducir_pide_latencia_de_30_ms_antes_de_la_ruta(tmp_path):
    """`[EJEC]` 2026-09-29 HC-1: con `--latency-msec=20` en captura y `30` en `paplay`, la ida y vuelta
    altavoz->aire->micrófono es P50 85 ms; con la latencia por defecto el audio llegaba ~2000 ms tarde."""
    mic = _mic(tmp_path)
    wav = tmp_path / "resp.wav"
    wav.write_bytes(b"RIFF")
    mic.reproducir(str(wav))
    orden = mic._ejecutar.ordenes[-1]
    assert orden == ["paplay", "--latency-msec=30", str(wav)]
