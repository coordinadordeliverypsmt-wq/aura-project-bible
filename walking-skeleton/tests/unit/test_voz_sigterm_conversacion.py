"""SIGTERM en pulsar-para-hablar y en el modo texto: AURA se detiene limpia y no deja audio del usuario.

Continuación de `test_voz_sigterm.py` (escucha continua). Aquí la espera es un `input()` SÍNCRONO en el hilo
principal y la grabación es un `subprocess.run` síncrono: un manejador de asyncio no se ejecutaría hasta que la
persona pulsara Enter. Por eso SIGTERM se trata como Ctrl-C —el camino de salida que ya existe— y la grabación
interrumpida se borra en el propio micrófono.

La señal es REAL (`os.kill` al propio proceso), con red de seguridad: sin manejador, la prueba FALLA en vez de
matar a pytest.
"""

from __future__ import annotations

import asyncio
import builtins
import os
import signal
import time

import pytest

from aura_skeleton import __main__ as principal
from aura_skeleton.adapters.microfono import Microfono


class _SigtermSinManejar(RuntimeError):
    pass


def _falla(*_a):
    raise _SigtermSinManejar("SIGTERM llegó sin manejador: AURA habría muerto sin limpiar")


@pytest.fixture
def red_de_seguridad():
    anterior = signal.signal(signal.SIGTERM, _falla)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, anterior)


def _enviar_sigterm():
    os.kill(os.getpid(), signal.SIGTERM)


class _Voz:
    async def tts(self, texto, tid):
        return None


def _sistema():
    class _O:
        voice = _Voz()

    class _S:
        orquestador = _O()

    return _S()


class _Mic:
    """Pulsar-para-hablar doble: graba (devuelve una ruta) y anota lo descartado y el estado de SIGTERM al limpiar."""

    def __init__(self):
        self.descartados = []
        self.sigterm_al_limpiar = []

    def escuchar(self, tid):
        return f"/tmp/aura/entrada_{tid}.wav"

    def reproducir(self, ruta):
        pass

    def descartar(self, ruta):
        self.sigterm_al_limpiar.append(signal.getsignal(signal.SIGTERM))
        self.descartados.append(ruta)


def _entradas(monkeypatch, *respuestas):
    """`input()` doble: cada respuesta es un texto o una función (que puede enviar SIGTERM y esperar).

    Al agotarse, Ctrl-D (EOFError): una prueba nunca puede quedarse en bucle si la parada no llega —ese bucle
    colgó 48 min el arnés de mutación con el mutante VC-M6—."""
    cola = list(respuestas)

    def _input(_prompt=""):
        if not cola:
            raise EOFError
        r = cola.pop(0)
        if callable(r):
            return r()
        return r

    monkeypatch.setattr(builtins, "input", _input)


def _sigterm_y_esperar():
    _enviar_sigterm()
    time.sleep(5)  # como un `input()` bloqueado: la señal tiene que interrumpirlo
    return "no debería llegar"


@pytest.fixture
def sin_informe(monkeypatch):
    monkeypatch.setattr(principal, "_informe", lambda _s: "")


# ------------------------------------------------------- modo texto --


def test_texto_sigterm_mientras_espera_la_entrada_sale_limpio(red_de_seguridad, sin_informe, monkeypatch, capsys):
    _entradas(monkeypatch, _sigterm_y_esperar)
    t0 = time.monotonic()

    rc = principal._ejecutar_conversacion(_sistema(), None, telemetria=True)

    assert rc == 0
    assert time.monotonic() - t0 < 3, "SIGTERM esperó a que la persona pulsara Enter"
    assert signal.getsignal(signal.SIGTERM) is _falla, "el manejador anterior no se restauró"


def test_texto_sigterm_a_mitad_de_un_turno_sale_limpio(red_de_seguridad, sin_informe, monkeypatch):
    async def _turno(orq, texto, tid, activado=False):
        _enviar_sigterm()
        await asyncio.sleep(30)
        return {"say": "", "audio": None}

    monkeypatch.setattr(principal, "_turno", _turno)
    _entradas(monkeypatch, "hola")
    t0 = time.monotonic()

    rc = principal._ejecutar_conversacion(_sistema(), None, telemetria=True)

    assert rc == 0 and time.monotonic() - t0 < 5


# -------------------------------------------------- pulsar-para-hablar --


def test_ptt_sigterm_a_mitad_del_turno_descarta_la_grabacion(red_de_seguridad, sin_informe, monkeypatch):
    async def _turno(orq, texto, tid, activado=False):
        _enviar_sigterm()
        await asyncio.sleep(30)  # el STT/turno en curso
        return {"say": "", "audio": None}

    monkeypatch.setattr(principal, "_turno", _turno)
    _entradas(monkeypatch, "")  # Enter vacío = pulsar para hablar
    mic = _Mic()

    rc = principal._ejecutar_conversacion(_sistema(), mic, telemetria=True)

    assert rc == 0
    assert len(mic.descartados) == 1 and mic.descartados[0].startswith("/tmp/aura/entrada_"), mic.descartados
    assert mic.sigterm_al_limpiar == [signal.SIG_IGN], "un segundo SIGTERM podría cortar la limpieza"


def test_ptt_sigterm_durante_la_grabacion_borra_el_wav_parcial(red_de_seguridad, sin_informe, monkeypatch, tmp_path):
    """El caso real: `parecord` está escribiendo el WAV cuando llega SIGTERM."""

    def _grabador_interrumpido(orden, **_k):
        with open(orden[-1], "wb") as f:  # `parecord` ya ha escrito parte del audio
            f.write(b"RIFF....WAVEfmt parcial")
        _enviar_sigterm()
        time.sleep(5)  # la grabación seguía en curso

    mic = Microfono(directorio=str(tmp_path), segundos=5, ejecutar=_grabador_interrumpido, disponible=lambda _p: True)
    _entradas(monkeypatch, "")
    t0 = time.monotonic()

    rc = principal._ejecutar_conversacion(_sistema(), mic, telemetria=True)

    assert time.monotonic() - t0 < 3, "SIGTERM esperó a que terminara la grabación"
    assert rc == 0
    assert [n for n in os.listdir(tmp_path) if n.startswith("entrada_")] == [], "quedó audio del usuario en disco"


def test_sin_sigterm_ctrl_d_sigue_saliendo_igual(red_de_seguridad, sin_informe, monkeypatch, capsys):
    """Control: el envoltorio no cambia la salida normal."""

    def _eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", _eof)

    assert principal._ejecutar_conversacion(_sistema(), None, telemetria=True) == 0
    assert "hasta luego" in capsys.readouterr().out
    assert signal.getsignal(signal.SIGTERM) is _falla


# ------------------------------------------------------------- micrófono --


def test_escuchar_interrumpido_borra_el_wav_parcial_y_propaga(tmp_path):
    def _grabador(orden, **_k):
        with open(orden[-1], "wb") as f:
            f.write(b"RIFFparcial")
        raise KeyboardInterrupt

    mic = Microfono(directorio=str(tmp_path), segundos=5, ejecutar=_grabador, disponible=lambda _p: True)

    with pytest.raises(KeyboardInterrupt):
        mic.escuchar("t1")

    assert os.listdir(tmp_path) == []


# ------------------------------------------------------------------ main --


def test_main_sin_escucha_continua_entra_por_la_conversacion_que_se_detiene_con_sigterm(monkeypatch, tmp_path):
    class _Config:
        usar_stack_real = False
        datos = str(tmp_path)

    llamadas = []
    monkeypatch.setattr(principal.Configuracion, "desde_entorno", staticmethod(lambda: _Config()))
    monkeypatch.setattr(principal, "componer", lambda config, confirmador=None: object())
    monkeypatch.setattr(principal, "_ejecutar_conversacion", lambda s, m, telemetria=False: llamadas.append(m) or 9)

    assert principal.main([]) == 9
    assert llamadas == [None]


# ------------------------------------------- ventana síncrona frente a cancelación --


def test_fuera_de_la_ventana_sigterm_no_corta_codigo_sincrono_a_medias(red_de_seguridad, sin_informe, monkeypatch):
    """Fuera de `input()`/grabación/reproducción, SIGTERM CANCELA en el siguiente `await`: no lanza una excepción
    en mitad de código síncrono (p. ej. escribiendo el audit forense). Si lanzara, «tras» no se anotaría."""
    hechos = []

    async def _turno(orq, texto, tid, activado=False):
        _enviar_sigterm()
        hechos.append("tras")  # código síncrono justo después de la señal
        await asyncio.sleep(30)
        return {"say": "", "audio": None}

    monkeypatch.setattr(principal, "_turno", _turno)
    _entradas(monkeypatch, "hola")

    assert principal._ejecutar_conversacion(_sistema(), None, telemetria=True) == 0
    assert hechos == ["tras"]


def test_ptt_sigterm_durante_la_reproduccion_borra_la_respuesta(red_de_seguridad, sin_informe, monkeypatch):
    async def _turno(orq, texto, tid, activado=False):
        return {"say": "hola", "audio": f"/tmp/aura/resp_{tid}.wav"}

    class _MicQueSuena(_Mic):
        def reproducir(self, ruta):
            _enviar_sigterm()
            time.sleep(5)  # `paplay` en curso

    monkeypatch.setattr(principal, "_turno", _turno)
    _entradas(monkeypatch, "")
    mic = _MicQueSuena()
    t0 = time.monotonic()

    rc = principal._ejecutar_conversacion(_sistema(), mic, telemetria=True)

    assert rc == 0 and time.monotonic() - t0 < 3
    assert any(r.startswith("/tmp/aura/resp_") for r in mic.descartados), mic.descartados
    assert any(r.startswith("/tmp/aura/entrada_") for r in mic.descartados), mic.descartados


# ---------------------------------------------- el grabador no queda huérfano --


def _pids_con(args: str) -> list[int]:
    """PIDs cuyo comando es EXACTAMENTE `args`: acotado al hijo de esta prueba, nunca un patrón genérico."""
    import subprocess

    salida = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout
    pids = []
    for linea in salida.splitlines():
        pid, _, comando = linea.strip().partition(" ")
        if comando.strip() == args:
            pids.append(int(pid))
    return pids


def test_una_grabacion_interrumpida_no_deja_al_grabador_huerfano():
    """`[EJEC]` 2026-10-06: `subprocess.run` mata a `timeout` con SIGKILL y su hijo (`parecord`) seguía grabando.
    El ejecutor del micrófono termina el GRUPO entero. Se usa `sleep` como hijo para no abrir el micrófono."""
    from aura_skeleton.adapters.microfono import _ejecutar_en_grupo

    hijo = "sleep 77.25"
    import threading

    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGUSR1)).start()
    anterior = signal.signal(signal.SIGUSR1, lambda *_a: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        with pytest.raises(KeyboardInterrupt):
            _ejecutar_en_grupo(["timeout", "30", "sleep", "77.25"], check=False, capture_output=True)
    finally:
        signal.signal(signal.SIGUSR1, anterior)
    time.sleep(0.3)
    huerfanos = _pids_con(hijo)
    for pid in huerfanos:  # si la garantía falla, la prueba no deja el proceso vivo
        os.kill(pid, signal.SIGKILL)

    assert huerfanos == [], "el grabador siguió vivo tras interrumpir la grabación"


def test_el_ejecutor_en_grupo_conserva_la_semantica_de_subprocess_run():
    import subprocess

    from aura_skeleton.adapters.microfono import _ejecutar_en_grupo

    ok = _ejecutar_en_grupo(["true"], check=True, capture_output=True)
    assert ok.returncode == 0
    with pytest.raises(subprocess.CalledProcessError):
        _ejecutar_en_grupo(["false"], check=True, capture_output=True)
    with pytest.raises(subprocess.TimeoutExpired):
        _ejecutar_en_grupo(["sleep", "5"], check=False, capture_output=True, timeout=0.3)


def test_el_microfono_usa_por_defecto_el_ejecutor_que_termina_el_grupo(tmp_path):
    from aura_skeleton.adapters.microfono import _ejecutar_en_grupo

    assert Microfono(directorio=str(tmp_path), disponible=lambda _p: True)._ejecutar is _ejecutar_en_grupo


# ------------------------------------- la respuesta sintetizada tras la cancelación --


def test_ptt_sigterm_mientras_se_sintetiza_no_deja_la_respuesta_en_disco(
    red_de_seguridad, sin_informe, monkeypatch, tmp_path
):
    """El TTS corre en un hilo: si llega SIGTERM mientras sintetiza, el hilo escribe `resp_<tid>.wav` DESPUÉS de la
    cancelación, cuando `_turno_de_voz` ya pasó por su `finally` sin saber la ruta. Hallazgo de la revisión ECC."""
    import threading

    async def _turno(orq, texto, tid, activado=False):
        ruta = tmp_path / f"resp_{tid}.wav"

        def _sintetizar():
            time.sleep(0.5)  # Piper trabajando
            ruta.write_bytes(b"RIFFrespuesta")

        hilo = threading.Thread(target=_sintetizar)
        hilo.start()
        _enviar_sigterm()
        await asyncio.get_running_loop().run_in_executor(None, hilo.join)
        return {"say": "hola", "audio": str(ruta)}

    def _graba(orden, **_k):
        with open(orden[-1], "wb") as f:
            f.write(b"RIFF" + b"\0" * 40)

    monkeypatch.setattr(principal, "_turno", _turno)
    monkeypatch.setattr("aura_skeleton.adapters.microfono._frames", lambda _r: 16000)
    mic = Microfono(directorio=str(tmp_path), segundos=5, ejecutar=_graba, disponible=lambda _p: True)
    _entradas(monkeypatch, "")

    rc = principal._ejecutar_conversacion(_sistema(), mic, telemetria=True)

    assert rc == 0
    assert [n for n in os.listdir(tmp_path) if n.endswith(".wav")] == [], os.listdir(tmp_path)
