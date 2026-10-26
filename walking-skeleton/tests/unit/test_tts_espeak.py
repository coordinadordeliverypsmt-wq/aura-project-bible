"""Sintetizador espeak-ng por ctypes (CM1, latencia de voz) — motor OPCIONAL.

Medido `[EJEC]` 2026-09-29 en HC-1: espeak-ng sintetiza en 0,6-4,3 ms; Piper medium, 0,6-3,4 s. Pero la
inteligibilidad (ida y vuelta TTS->Vosk) es peor (WER ~0,33 frente a 0,18): por eso es opcional.
Aquí se prueba con una librería FALSA (contrato ctypes) y, si está instalada, con la real.
"""

from __future__ import annotations

import array
import ctypes
import ctypes.util
import gc
import math
import threading
import wave
import weakref

import pytest

from aura_skeleton.adapters import tts_espeak
from aura_skeleton.adapters.tts_espeak import SintetizadorEspeak
from aura_skeleton.adapters.voice_real import VozNoDisponible

_MUESTRAS = [0, 1000, -1000, 32767, -32768, 5]


@pytest.fixture(autouse=True)
def _estado_de_libreria_limpio():
    """libespeak-ng es estado de PROCESO: cada prueba parte de una librería sin inicializar."""
    tts_espeak._reiniciar_para_pruebas()
    yield
    tts_espeak._reiniciar_para_pruebas()


class _LibFalsa:
    """Doble FIEL de libespeak-ng: estado GLOBAL (voz, un único callback), falla si se inicializa dos veces,
    guarda el callback solo por `weakref` (si el código no lo retiene, `gc.collect()` lo invalida) y detecta
    la reentrada en `espeak_Synth`."""

    def __init__(self, init=22050, voz=0, synth=0, muestras=_MUESTRAS, espera_en_synth=None):
        self._init, self._voz_ok, self._synth = init, voz, synth
        self._muestras = muestras
        self.llamadas: list[tuple] = []
        self.inicializaciones = 0
        self.voz_actual = None
        self.velocidad_actual = None
        self._cb_ref = None
        self.activas = 0
        self.max_activas = 0
        self.entrada = threading.Event()
        self._espera = espera_en_synth
        self.espeak_Initialize = self._f("Initialize", self._inicializar)
        self.espeak_SetVoiceByName = self._f("SetVoiceByName", self._poner_voz)
        self.espeak_SetParameter = self._f("SetParameter", self._poner_param)
        self.espeak_SetSynthCallback = self._f("SetSynthCallback", self._registrar)
        self.espeak_Synth = self._f("Synth", self._sintetizar)

    def _f(self, nombre, cuerpo):
        def _llamar(*args):
            # El registro NO puede retener el callback: una referencia fuerte aquí taparía el mutante «no
            # retener el callback» (el `weakref` de `_registrar` no moriría nunca).
            visto = tuple("<callback>" if isinstance(x, ctypes._CFuncPtr) else x for x in args)
            self.llamadas.append((nombre, visto))
            return cuerpo(*args)

        return _llamar

    def _inicializar(self, *a):
        self.inicializaciones += 1
        assert self.inicializaciones == 1, "espeak_Initialize llamado dos veces en el mismo proceso"
        return self._init

    def _poner_voz(self, nombre):
        if self._voz_ok == 0:
            self.voz_actual = nombre
        return self._voz_ok

    def _poner_param(self, param, valor, _rel):
        self.velocidad_actual = valor
        return 0

    def _registrar(self, cb):
        self._cb_ref = weakref.ref(cb)  # nunca la referencia fuerte

    def _sintetizar(self, *args):
        self.activas += 1
        self.max_activas = max(self.max_activas, self.activas)
        try:
            self.entrada.set()
            if self._espera is not None:
                self._espera.wait(0.2)
            if self._synth != 0:
                return self._synth
            cb = self._cb_ref() if self._cb_ref else None
            assert cb is not None, "el callback fue liberado: libespeak llamaría a memoria muerta"
            muestras = self._muestras(self.voz_actual) if callable(self._muestras) else self._muestras
            buf = (ctypes.c_short * len(muestras))(*muestras)
            cb(buf, len(muestras), None)
            cb(None, 0, None)  # espeak cierra con un evento sin muestras
            return 0
        finally:
            self.activas -= 1


def _sint(lib, **kw):
    return SintetizadorEspeak(cargar=lambda _nombre: lib, **kw)


def test_escribe_un_wav_valido_con_las_muestras_y_la_frecuencia_de_espeak(tmp_path):
    ruta = str(tmp_path / "o.wav")
    _sint(_LibFalsa(init=22050)).sintetizar_wav("Hola", ruta)
    with wave.open(ruta) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 22050)
        leidas = array.array("h", w.readframes(w.getnframes()))
    assert list(leidas) == _MUESTRAS  # control: un callback ignorado daría un WAV vacío


def test_usa_la_frecuencia_devuelta_por_initialize(tmp_path):
    ruta = str(tmp_path / "o.wav")
    _sint(_LibFalsa(init=16000)).sintetizar_wav("Hola", ruta)
    with wave.open(ruta) as w:
        assert w.getframerate() == 16000  # control: una constante 22050 fallaría


def test_configura_voz_velocidad_y_pasa_el_texto_utf8_terminado_en_nul(tmp_path):
    lib = _LibFalsa()
    _sint(lib, voz="es-419", velocidad=150).sintetizar_wav("¿Sí?", str(tmp_path / "o.wav"))
    por_nombre = {n: a for n, a in lib.llamadas}
    assert por_nombre["Initialize"][:1] == (2,)  # AUDIO_OUTPUT_SYNCHRONOUS
    assert por_nombre["SetVoiceByName"] == (b"es-419",)
    assert por_nombre["SetParameter"] == (1, 150, 0)  # espeakRATE
    texto, largo = por_nombre["Synth"][0], por_nombre["Synth"][1]
    assert texto == "¿Sí?".encode() + b"\0" and largo == len(texto)


def test_inicializa_una_sola_vez_por_instancia(tmp_path):
    lib = _LibFalsa()
    s = _sint(lib)
    s.sintetizar_wav("a", str(tmp_path / "1.wav"))
    s.sintetizar_wav("b", str(tmp_path / "2.wav"))
    assert [n for n, _ in lib.llamadas].count("Initialize") == 1


def test_comprobar_describe_el_motor():
    assert _sint(_LibFalsa(init=22050), voz="es", velocidad=175).comprobar() == "espeak-ng (voz es, 175 ppm, 22050 Hz)"


def test_libreria_que_no_carga_es_VozNoDisponible():
    def _falla(_n):
        raise OSError("no such file")

    with pytest.raises(VozNoDisponible, match="libespeak"):
        SintetizadorEspeak(cargar=_falla).comprobar()


def test_initialize_fallido_es_VozNoDisponible():
    with pytest.raises(VozNoDisponible, match="inicializ"):
        _sint(_LibFalsa(init=-1)).comprobar()
    with pytest.raises(VozNoDisponible, match="inicializ"):
        _sint(_LibFalsa(init=0)).comprobar()


def test_voz_inexistente_es_VozNoDisponible():
    with pytest.raises(VozNoDisponible, match="voz"):
        _sint(_LibFalsa(voz=1), voz="xx").comprobar()


def test_synth_fallido_es_VozNoDisponible_y_no_deja_wav(tmp_path):
    ruta = tmp_path / "o.wav"
    with pytest.raises(VozNoDisponible, match="sintet"):
        _sint(_LibFalsa(synth=1)).sintetizar_wav("Hola", str(ruta))
    assert not ruta.exists()  # control: escribir antes de comprobar dejaría un WAV vacío


# ------------------------------------------- estado GLOBAL de libespeak-ng (auditoría 2026-09-29) --
#
# `[EJEC]` por el auditor con la librería real: crear un segundo sintetizador dejaba al primero SIN audio
# y sin error, y liberar el segundo provocaba SIGSEGV al usar el primero. Voz, velocidad y callback son
# estado de TODO el proceso: el estado vive a nivel de módulo y cada instancia solo guarda voz y velocidad.


def _por_voz(voz):
    """Muestras distintas según la voz activa en la librería: delata quién sintetizó con qué voz."""
    return [1000] * 4 if voz == b"es" else [3000] * 6


def _leer(ruta):
    with wave.open(ruta) as w:
        return list(array.array("h", w.readframes(w.getnframes())))


def test_dos_instancias_cada_una_con_su_voz_y_su_audio(tmp_path):
    lib = _LibFalsa(muestras=_por_voz)
    a = _sint(lib, voz="es")
    b = _sint(lib, voz="es-419")
    for i, (sint, esperado) in enumerate([(a, [1000] * 4), (b, [3000] * 6), (a, [1000] * 4), (b, [3000] * 6)]):
        ruta = str(tmp_path / f"{i}.wav")
        sint.sintetizar_wav("Hola", ruta)
        assert _leer(ruta) == esperado, (i, "audio de otra voz o vacío")  # control: estado por instancia falla
    assert lib.inicializaciones == 1


def test_cada_instancia_fija_su_velocidad_antes_de_sintetizar(tmp_path):
    lib = _LibFalsa()
    a, b = _sint(lib, velocidad=120), _sint(lib, velocidad=200)
    a.sintetizar_wav("x", str(tmp_path / "1.wav"))
    assert lib.velocidad_actual == 120
    b.sintetizar_wav("x", str(tmp_path / "2.wav"))
    assert lib.velocidad_actual == 200
    a.sintetizar_wav("x", str(tmp_path / "3.wav"))
    assert lib.velocidad_actual == 120


def test_liberar_una_instancia_no_afecta_a_la_otra(tmp_path):
    lib = _LibFalsa()
    a, b = _sint(lib), _sint(lib)
    a.sintetizar_wav("x", str(tmp_path / "1.wav"))
    b.sintetizar_wav("x", str(tmp_path / "2.wav"))
    del b
    gc.collect()
    ruta = str(tmp_path / "3.wav")
    a.sintetizar_wav("x", ruta)  # el callback sigue vivo: la falsa lo comprueba por weakref
    assert _leer(ruta) == _MUESTRAS


def test_el_callback_se_retiene_aunque_pase_el_recolector(tmp_path):
    """M1: si el código no guarda el callback, `gc.collect()` lo libera y libespeak llamaría a memoria muerta
    (SIGSEGV con la librería real). La falsa lo guarda solo por weakref."""
    lib = _LibFalsa()
    s = _sint(lib)
    s.comprobar()
    gc.collect()
    ruta = str(tmp_path / "o.wav")
    s.sintetizar_wav("x", ruta)
    assert _leer(ruta) == _MUESTRAS


def test_la_segunda_sintesis_solo_tiene_sus_muestras(tmp_path):
    """M5: sin limpiar el búfer, la segunda salida arrastraría la primera."""
    largo = [7] * 10
    corto = [9] * 3
    salidas = iter([largo, corto])
    lib = _LibFalsa(muestras=lambda _voz: next(salidas))
    s = _sint(lib)
    s.sintetizar_wav("uno", str(tmp_path / "1.wav"))
    s.sintetizar_wav("dos", str(tmp_path / "2.wav"))
    assert _leer(str(tmp_path / "2.wav")) == corto


def test_la_sintesis_no_es_reentrante_ni_entre_instancias(tmp_path):
    """M4: espeak no es reentrante. Con el cerrojo, dos hilos nunca están a la vez dentro de Synth."""
    espera = threading.Event()  # nunca se activa: Synth espera su tope de 0,2 s con la entrada abierta
    lib = _LibFalsa(espera_en_synth=espera)
    a, b = _sint(lib, voz="es"), _sint(lib, voz="es-419")
    a.comprobar()
    hilo_a = threading.Thread(target=a.sintetizar_wav, args=("x", str(tmp_path / "a.wav")))
    hilo_b = threading.Thread(target=b.sintetizar_wav, args=("x", str(tmp_path / "b.wav")))
    hilo_a.start()
    assert lib.entrada.wait(2)  # A ya está dentro de Synth
    hilo_b.start()
    hilo_a.join()
    hilo_b.join()
    assert lib.max_activas == 1, "dos síntesis simultáneas dentro de libespeak-ng"


def test_declara_argtypes_y_restype_de_las_funciones_que_usa():
    lib = _LibFalsa()
    _sint(lib).comprobar()
    assert lib.espeak_Synth.argtypes[1] is ctypes.c_size_t  # la longitud es size_t, no int
    assert lib.espeak_Synth.restype is ctypes.c_int
    assert lib.espeak_Initialize.restype is ctypes.c_int


def test_reiniciar_para_pruebas_permite_una_libreria_nueva():
    """Control del aislamiento: sin el reinicio la segunda librería falsa no se usaría nunca."""
    l1, l2 = _LibFalsa(), _LibFalsa()
    _sint(l1).comprobar()
    tts_espeak._reiniciar_para_pruebas()
    _sint(l2).comprobar()
    assert l1.inicializaciones == 1 and l2.inicializaciones == 1


@pytest.mark.skipif(ctypes.util.find_library("espeak-ng") is None, reason="libespeak-ng no instalada")
def test_real_hola_no_es_silencio_y_dura_mas_de_una_decima(tmp_path):
    ruta = str(tmp_path / "hola.wav")
    SintetizadorEspeak().sintetizar_wav("Hola", ruta)
    with wave.open(ruta) as w:
        duracion = w.getnframes() / w.getframerate()
        m = array.array("h", w.readframes(w.getnframes()))
    rms = math.sqrt(sum(x * x for x in m) / len(m))
    assert duracion > 0.1 and rms > 100, (duracion, rms)


@pytest.mark.skipif(ctypes.util.find_library("espeak-ng") is None, reason="libespeak-ng no instalada")
def test_real_dos_instancias_intercaladas_y_liberar_una_no_mata_a_la_otra(tmp_path):
    """El caso que el auditor reprodujo: antes el primero se quedaba sin audio y, tras `del` + GC, SIGSEGV."""

    def _rms(ruta):
        m = _leer(ruta)
        return math.sqrt(sum(x * x for x in m) / len(m))

    a, b = SintetizadorEspeak(voz="es"), SintetizadorEspeak(voz="es-419")
    for i, sint in enumerate([a, b, a, b]):
        ruta = str(tmp_path / f"{i}.wav")
        sint.sintetizar_wav("Hola", ruta)
        assert _rms(ruta) > 100, f"la instancia {i % 2} quedó sin audio"
    del b
    gc.collect()
    ruta = str(tmp_path / "final.wav")
    a.sintetizar_wav("Hola de nuevo", ruta)
    assert _rms(ruta) > 100
