"""Sintetizador espeak-ng por ctypes — motor de voz OPCIONAL y rápido (CM1, Bible 2.5 §5.1).

**NO CIERRA CM1 POR SÍ SOLO.** Rompe el muro de la SÍNTESIS, pero el turno completo medido por el aire con
AURA real siguió por encima de 800 ms (P50 995-1070 ms en los turnos válidos): el cuello pasa al fin de
habla y al reconocimiento (`milestones/m3-entry/RESULTADO-CM1-HW-ACCEL.md`). Decirlo aquí evita que
alguien active este motor creyendo que con eso AURA cumple CM1 (INV-9).

POR QUÉ EXISTE. CM1 exige P50 <= 800 ms de fin-de-habla a inicio-de-respuesta hablada. Medido `[EJEC]`
2026-09-29 en HC-1 (Celeron N4020, solo SSE4.2): Piper es_MX-ald-medium ya precargado (onnxruntime CPU)
tarda 626 ms para «Sí.», 2222 ms para «Te llamas Mauricio.» y 3406 ms para 34 caracteres (P50 de la
inferencia); la voz x_low tiene un suelo >= 550 ms; la iGPU por OpenVINO cuelga el i915 (GPU HANG) y
OpenVINO en CPU tarda 50-58 s por inferencia (kernels de referencia de oneDNN sin AVX). Ningún camino Piper
cabe en el presupuesto. espeak-ng (`libespeak-ng.so.1`, la misma librería que Piper usa para fonemizar), con
la configuración por defecto de este módulo (voz «es», 175 ppm), sintetiza las mismas frases en
0,56 / 2,3 / 5,1 ms (P50).

LA REGRESIÓN DE CALIDAD ES REAL, Y POR ESO ES OPCIONAL. Inteligibilidad medida por ida y vuelta
TTS -> Vosk sobre 12 frases (indicador de máquina, no oyentes): voz «es» a 175 ppm, WER 0,33-0,35;
voz «es-419», ~0,51; Piper medium, 0,18. El defecto sigue siendo Piper; este motor se elige con
`AURA_TTS_MOTOR=espeak`.

Evidencia: `milestones/m3-entry/evidencia-cm1-hw/mediciones/` (`baseline_cpu_ort.json`,
`xlow_cpu_ort.json`, `espeak_es_175.json`, `wer_inteligibilidad.txt`, `kernel_i915_gpu_hang.log`,
`salidas_consola.md`).

DISEÑO. libespeak-ng guarda voz, velocidad, callback y búfer como estado de TODO EL PROCESO: no admite
dos "instancias". Auditado `[EJEC]` 2026-09-29 con la librería real: un segundo sintetizador dejaba al
primero sin audio y sin error (WAV vacío) y, al liberar el segundo, el primero acababa en SIGSEGV. Por eso
ese estado vive a nivel de MÓDULO —librería, frecuencia, el ÚNICO callback (retenido para siempre), búfer y
UN cerrojo— y `espeak_Initialize` se llama UNA vez por proceso. Cada `SintetizadorEspeak` solo guarda su voz
y su velocidad, y las FIJA en cada síntesis bajo el cerrojo: dos instancias con voces distintas producen
cada una su audio. El cerrojo es imprescindible porque `tts()` sintetiza en `run_in_executor`.

La librería se carga de forma perezosa y la síntesis es en memoria: el único audio a disco es el WAV de la
ruta que pide el llamador, la misma ruta efímera de siempre, que él borra.
"""

from __future__ import annotations

import ctypes
import threading
import wave
from collections.abc import Callable
from typing import Any

from .voice_real import VozNoDisponible

_LIBRERIA = "libespeak-ng.so.1"

#: Constantes de la API C de espeak-ng (`speak_lib.h`).
_AUDIO_OUTPUT_SYNCHRONOUS = 2
_BUFFER_MS = 60
_ESPEAK_RATE = 1
_POS_CHARACTER = 1
_ESPEAK_CHARS_UTF8 = 1

_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

# ---- Estado de PROCESO de libespeak-ng (ver el docstring del módulo). Todo bajo `_CERROJO`. ----
_CERROJO = threading.Lock()
_lib: Any = None
_frecuencia = 0
_muestras = bytearray()
#: El callback vive mientras viva el proceso: si el GC lo libera, espeak llama a memoria muerta (SIGSEGV).
_callback: Any = None
#: Callbacks de una librería descartada por `_reiniciar_para_pruebas`: nunca se liberan (la real seguiría
#: apuntándoles).
_callbacks_huerfanos: list[Any] = []


def _acumular(wav, n, _eventos) -> int:
    if n > 0:
        _muestras.extend(ctypes.string_at(wav, n * 2))
    return 0


def _declarar_tipos(lib: Any) -> None:
    """`argtypes`/`restype` de lo que se usa: sin ellos ctypes pasaría `len` como int de 32 bits."""
    firmas = {
        "espeak_Initialize": ([ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
        "espeak_SetVoiceByName": ([ctypes.c_char_p], ctypes.c_int),
        "espeak_SetParameter": ([ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_int),
        "espeak_SetSynthCallback": ([_CALLBACK], None),
        "espeak_Synth": (
            [
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_uint),
                ctypes.c_void_p,
            ],
            ctypes.c_int,
        ),
    }
    for nombre, (argtypes, restype) in firmas.items():
        funcion = getattr(lib, nombre)
        funcion.argtypes = argtypes
        funcion.restype = restype


def _iniciar_libreria(cargar: Callable[[str], Any]) -> None:
    """Carga e inicializa la librería UNA vez por proceso. Llamar con `_CERROJO` tomado."""
    global _lib, _frecuencia, _callback
    if _lib is not None:
        return
    try:
        lib = cargar(_LIBRERIA)
    except OSError as e:
        raise VozNoDisponible(f"no se pudo cargar {_LIBRERIA} (¿falta libespeak-ng1?): {e}") from e
    _declarar_tipos(lib)
    frecuencia = lib.espeak_Initialize(_AUDIO_OUTPUT_SYNCHRONOUS, _BUFFER_MS, None, 0)
    if frecuencia <= 0:
        raise VozNoDisponible(f"espeak-ng no se pudo inicializar (código {frecuencia})")
    _callback = _CALLBACK(_acumular)
    lib.espeak_SetSynthCallback(_callback)
    _frecuencia = frecuencia
    _lib = lib


def _reiniciar_para_pruebas() -> None:
    """SOLO para pruebas: olvida la librería para poder inyectar otra. No libera el callback anterior."""
    global _lib, _frecuencia, _callback
    if _callback is not None:
        _callbacks_huerfanos.append(_callback)
    _lib, _frecuencia, _callback = None, 0, None
    _muestras.clear()


class SintetizadorEspeak:
    def __init__(self, voz: str = "es", velocidad: int = 175, cargar: Callable[[str], Any] = ctypes.CDLL) -> None:
        self._voz = voz
        self._velocidad = velocidad
        self._cargar = cargar

    def comprobar(self) -> str:
        """Inicializa si hace falta; `VozNoDisponible` si no hay con qué hablar (`INV-9`)."""
        with _CERROJO:
            self._preparar()
            return f"espeak-ng (voz {self._voz}, {self._velocidad} ppm, {_frecuencia} Hz)"

    def sintetizar_wav(self, texto: str, ruta: str) -> None:
        """Sintetiza en memoria y escribe un WAV mono de 16 bits en `ruta`."""
        with _CERROJO:
            self._preparar()
            _muestras.clear()
            datos = texto.encode("utf-8") + b"\0"
            estado = _lib.espeak_Synth(datos, len(datos), 0, _POS_CHARACTER, 0, _ESPEAK_CHARS_UTF8, None, None)
            if estado != 0:
                raise VozNoDisponible(f"espeak-ng no pudo sintetizar (código {estado})")
            pcm = bytes(_muestras)
            frecuencia = _frecuencia
        with wave.open(ruta, "wb") as destino:
            destino.setnchannels(1)
            destino.setsampwidth(2)
            destino.setframerate(frecuencia)
            destino.writeframes(pcm)

    def _preparar(self) -> None:
        """Inicializa la librería (una vez) y fija MI voz y MI velocidad. Con `_CERROJO` tomado."""
        _iniciar_libreria(self._cargar)
        if _lib.espeak_SetVoiceByName(self._voz.encode("utf-8")) != 0:
            raise VozNoDisponible(f"la voz de espeak-ng {self._voz!r} no existe")
        _lib.espeak_SetParameter(_ESPEAK_RATE, self._velocidad, 0)
