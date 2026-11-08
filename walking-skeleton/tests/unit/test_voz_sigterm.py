"""SIGTERM en la escucha continua: AURA se detiene sin dejar audio del usuario en disco.

Defecto observado `[EJEC]` (2026-10-06, cierre del E2E de latencia): al detener AURA con SIGTERM —como hacen
el arnés y runit— en mitad de un turno, quedó `entrada_<tid>.wav` en `/tmp/aura`. SIGTERM mataba el proceso
sin ejecutar los `finally` de `_turno_de_voz`, que son los que descartan la grabación. Regla vigente: el audio
no se almacena. La purga de arranque lo borraba al siguiente inicio, pero hasta entonces quedaba en disco.

Pruebas con dobles: sin micrófono, sin Vosk, sin modelos. La señal es REAL (`os.kill` al propio proceso), con
una red de seguridad: si nadie la maneja, la prueba FALLA en vez de matar a pytest.
"""

from __future__ import annotations

import asyncio
import os
import signal
import threading
import time

import pytest

from aura_skeleton import __main__ as principal
from aura_skeleton.adapters.escucha import OidoContinuo


class _SigtermSinManejar(RuntimeError):
    pass


@pytest.fixture
def red_de_seguridad():
    """Si el código no instala su manejador, SIGTERM levanta esto en vez de terminar el proceso de pruebas."""

    def _falla(*_a):
        raise _SigtermSinManejar("SIGTERM llegó sin manejador: AURA habría muerto sin limpiar")

    anterior = signal.signal(signal.SIGTERM, _falla)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, anterior)


# ----------------------------------------------------------------- dobles --


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
    """Micrófono doble: la captura devuelve una grabación y anota qué se descarta."""

    def __init__(self):
        self.descartados = []
        self.ultimo_corte = "silencio"

    def escuchar_hasta_silencio(self, tid):
        return f"/tmp/aura/entrada_{tid}.wav"

    def escuchar(self, tid):
        return f"/tmp/aura/entrada_{tid}.wav"

    def reproducir(self, ruta):
        pass

    def descartar(self, ruta):
        self.descartados.append(ruta)


class _Oido:
    """Oído doble: atiende `llamadas` veces y después se queda esperando, como Vosk, hasta `detener`."""

    def __init__(self, llamadas=0):
        self._pendientes = llamadas
        self._parado = threading.Event()
        self.detenido = False

    def esperar_llamada(self):
        if self._pendientes:
            self._pendientes -= 1
            return True
        self._parado.wait(timeout=20)  # sin `detener`, esta espera bloquearía el cierre del proceso
        return False

    def detener(self):
        self.detenido = True
        self._parado.set()


def _enviar_sigterm():
    os.kill(os.getpid(), signal.SIGTERM)


# ------------------------------------------------------- escucha continua --


def test_sigterm_en_espera_detiene_la_escucha_sin_colgarse(red_de_seguridad, monkeypatch):
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    oido = _Oido()

    async def _con_sigterm_diferido():
        asyncio.get_running_loop().call_later(0.3, _enviar_sigterm)
        return await principal._escuchar_continuo(_sistema(), _Mic(), oido, telemetria=True)

    t0 = time.monotonic()
    rc = asyncio.run(principal._hasta_sigterm(_con_sigterm_diferido(), al_detener=oido.detener))

    assert rc == 0
    assert oido.detenido, "el hilo de Vosk no se liberó: el proceso no podría terminar"
    assert time.monotonic() - t0 < 5, "el cierre esperó al hilo bloqueado"


def test_sigterm_a_mitad_de_un_turno_descarta_la_grabacion(red_de_seguridad, monkeypatch):
    monkeypatch.setattr(principal, "_informe", lambda _s: "")

    async def _turno_que_recibe_sigterm(orq, texto, tid, activado=False):
        _enviar_sigterm()
        await asyncio.sleep(30)  # el STT/turno en curso: aquí llega la cancelación
        return {"say": "", "audio": None}

    monkeypatch.setattr(principal, "_turno", _turno_que_recibe_sigterm)
    mic = _Mic()
    oido = _Oido(llamadas=1)

    t0 = time.monotonic()
    rc = asyncio.run(
        principal._hasta_sigterm(
            principal._escuchar_continuo(_sistema(), mic, oido, telemetria=True), al_detener=oido.detener
        )
    )

    assert rc == 0
    assert len(mic.descartados) == 1 and mic.descartados[0].startswith("/tmp/aura/entrada_"), mic.descartados
    assert time.monotonic() - t0 < 5


def test_sin_sigterm_la_escucha_termina_con_su_propio_codigo(red_de_seguridad, monkeypatch):
    """Control: el envoltorio no cambia nada cuando no hay señal."""
    monkeypatch.setattr(principal, "_informe", lambda _s: "")

    class _OidoSinAudio(_Oido):
        def esperar_llamada(self):
            return False  # el micrófono dejó de entregar audio

    rc = asyncio.run(principal._hasta_sigterm(principal._escuchar_continuo(_sistema(), _Mic(), _OidoSinAudio())))

    assert rc == 1


def test_el_arranque_de_la_escucha_continua_instala_la_detencion_por_sigterm(red_de_seguridad, monkeypatch):
    """`main` entra por `_ejecutar_escucha_continua`: si dejara de envolver con `_hasta_sigterm`, esto fallaría."""
    monkeypatch.setattr(principal, "_informe", lambda _s: "")
    oido = _Oido()

    async def _sin_preparar(*_a, **_k):
        asyncio.get_running_loop().call_later(0.3, _enviar_sigterm)

    monkeypatch.setattr(principal, "_preparar_voz", _sin_preparar)

    rc = principal._ejecutar_escucha_continua(_sistema(), _Mic(), oido, telemetria=True)

    assert rc == 0 and oido.detenido


# ------------------------------------------------------------- adaptador --


class _FlujoBloqueante:
    """Como `parecord`: `read` bloquea hasta que llega audio; al cerrar, devuelve vacío."""

    def __init__(self):
        self._cerrado = threading.Event()
        self.abierto = threading.Event()

    def read(self, n):
        self.abierto.set()
        self._cerrado.wait(timeout=20)
        return b""

    def close(self):
        self._cerrado.set()


class _NuncaReconoce:
    def AcceptWaveform(self, datos):
        return False

    def PartialResult(self):
        return '{"partial": ""}'


def test_detener_cierra_el_flujo_activo_y_libera_la_espera():
    flujo = _FlujoBloqueante()
    oido = OidoContinuo(abrir_flujo=lambda: flujo, reconocedor=_NuncaReconoce)
    resultado = []
    hilo = threading.Thread(target=lambda: resultado.append(oido.esperar_llamada()), daemon=True)
    hilo.start()
    assert flujo.abierto.wait(timeout=2)

    oido.detener()
    hilo.join(timeout=2)

    assert not hilo.is_alive(), "la espera siguió bloqueada tras detener"
    assert resultado == [False]


def test_detener_sin_escucha_activa_no_hace_nada():
    OidoContinuo(abrir_flujo=_FlujoBloqueante, reconocedor=_NuncaReconoce).detener()


def test_main_con_escucha_continua_entra_por_la_ruta_que_se_detiene_con_sigterm(monkeypatch, tmp_path):
    """Cableado de `main`: el modo `--escuchar --continuo` pasa por `_ejecutar_escucha_continua`.
    Si volviera a `asyncio.run(_escuchar_continuo(...))`, SIGTERM dejaría otra vez el audio en disco."""
    from aura_skeleton.adapters import escucha, microfono

    class _Config:
        usar_stack_real = True
        datos = str(tmp_path)

    class _MicFalso:
        def comprobar(self):
            return "doble"

    class _OidoFalso:
        def __init__(self, modelo=""):
            pass

        def comprobar(self):
            return "doble"

        def preparar(self):
            pass

        def detener(self):
            pass

    llamadas = []
    monkeypatch.setattr(principal.Configuracion, "desde_entorno", staticmethod(lambda: _Config()))
    monkeypatch.setattr(principal, "componer", lambda config, confirmador=None: object())
    monkeypatch.setattr(microfono, "Microfono", _MicFalso)
    monkeypatch.setattr(escucha, "OidoContinuo", _OidoFalso)
    monkeypatch.setattr(
        principal, "_ejecutar_escucha_continua", lambda s, m, o, telemetria=False: llamadas.append(o) or 7
    )

    assert principal.main(["--escuchar", "--continuo"]) == 7
    assert len(llamadas) == 1 and isinstance(llamadas[0], _OidoFalso)


def test_sigterm_mientras_se_sintetiza_en_escucha_continua_no_deja_la_respuesta(
    red_de_seguridad, monkeypatch, tmp_path
):
    """El TTS escribe `resp_<tid>.wav` en un hilo DESPUÉS de la cancelación: se borra al cerrar, por nombre exacto."""
    from aura_skeleton.adapters.microfono import Microfono

    monkeypatch.setattr(principal, "_informe", lambda _s: "")

    async def _turno(orq, texto, tid, activado=False):
        ruta = tmp_path / f"resp_{tid}.wav"

        def _sintetizar():
            time.sleep(0.5)
            ruta.write_bytes(b"RIFFrespuesta")

        hilo = threading.Thread(target=_sintetizar)
        hilo.start()
        _enviar_sigterm()
        await asyncio.get_running_loop().run_in_executor(None, hilo.join)
        return {"say": "hola", "audio": str(ruta)}

    monkeypatch.setattr(principal, "_turno", _turno)
    mic = Microfono(directorio=str(tmp_path), segundos=5, ejecutar=lambda *a, **k: None, disponible=lambda _p: True)
    monkeypatch.setattr(mic, "escuchar_hasta_silencio", lambda tid: str(tmp_path / f"entrada_{tid}.wav"))
    oido = _Oido(llamadas=1)

    rc = principal._ejecutar_escucha_continua(_sistema(), mic, oido, telemetria=True)

    assert rc == 0
    assert [n for n in os.listdir(tmp_path) if n.startswith(("entrada_", "resp_"))] == [], os.listdir(tmp_path)
