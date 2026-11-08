"""Micrófono y altavoz: el primer y el último eslabón de la conversación por voz.

Medido antes de escribirlo `[EJEC]` (2026-09-27): la cadena Whisper -> AURA -> Piper funcionaba con
los modelos reales de la USB, pero **nadie grababa del micrófono y nadie reproducía la respuesta** —el
orquestador generaba el WAV y descartaba su ruta—. AURA podía «hablar» a un fichero, no a una
persona.

Tres decisiones de diseño, cada una por una razón:

- **Pulsar para hablar, con tope.** La escucha continua con palabra de activación está autorizada
  (`Bible 6.2`), pero es otra pieza. Empezar por grabar solo cuando el usuario lo pide, durante un
  tiempo acotado, es la opción más estricta y la que no puede quedarse escuchando por un fallo.
- **Lo oído no se conserva.** `descartar` borra la grabación tras transcribirla. Un directorio de WAV
  del usuario sería un archivo de voz que nadie ha decidido crear (`Bible 5.5`).
- **Sin red y sin dependencias nuevas.** `parecord`/`paplay` vienen con PulseAudio/PipeWire y son
  locales (`D24`). Se invocan por `subprocess`, igual que Piper en `voice_real.py`.
"""

from __future__ import annotations

import array
import math
import os
import shutil
import signal
import subprocess
import wave
from collections.abc import Callable

from .. import observability as obs

_GRABADOR = "parecord"
_REPRODUCTOR = "paplay"

# --- Captura con fin de habla (solo escucha continua). Perfil E2E 2026-10-04: la orden cabe en ~1,5 s y la
# grabación fija de 5 s regalaba ~3,5 s de silencio al turno.
_MUESTREO = 16000
_BLOQUE_BYTES = 4000  # 2000 muestras s16le = 125 ms: granularidad suficiente para cortar sin cargar la CPU
_BLOQUE_MS = 125
# Los 2 primeros bloques (250 ms) nunca cuentan como habla y el ruido de fondo es el MÍNIMO visto hasta el
# momento: `[EJEC]` 2026-10-04 (HC-1) `parecord` arranca con un golpe de ~19000/9000/1900 RMS en los 3 primeros
# bloques y el ambiente real ronda 300; calibrar con solo 2 bloques fijaba un umbral de 28000 (sordo).
_BLOQUES_CALIBRADO = 2
_FACTOR_RUIDO = 3  # habla = RMS por encima de 3x el ruido de fondo (se adapta a un entorno ruidoso)
_RMS_MINIMO = 300  # suelo absoluto: en un cuarto casi mudo, 3x ruido seria ruido; el habla ronda 1000+
_SILENCIO_FINAL_MS = 700  # pausa que cierra la frase; una pausa entre palabras (~300-500 ms) no corta
# Sin habla detectada se graban los 5 s de la captura fija de antes: nunca peor que antes. Medido 2026-10-04: a
# 27 % de ganancia la voz llegó con RMS 930-2150 y la sala con 1265-2179, así que un «sin voz» temprano habría
# podido tirar órdenes reales. Solo se ahorra tiempo cuando HAY evidencia de una frase terminada.
_ESPERA_SIN_VOZ_MS = 5000
_HABLA_MINIMA_BLOQUES = 2  # 250 ms seguidos: un golpe aislado de ruido no es una frase ni abre el corte
_TOPE_MS = 6000  # tope duro: la escucha nunca queda abierta por un ruido que no acaba


class DispositivoNoDisponible(RuntimeError):
    """El micrófono o el altavoz no pueden usarse. Se dice, no se finge (`INV-9`)."""


def _ejecutar_en_grupo(orden, check=False, capture_output=False, timeout=None):
    """`subprocess.run`, pero si la llamada se INTERRUMPE termina el grupo de procesos entero.

    `[EJEC]` 2026-10-06: `subprocess.run` mata con SIGKILL solo a su hijo directo. Aquí ese hijo es `timeout`,
    que no reenvía SIGKILL, y `parecord` seguía grabando huérfano (Ctrl-C o SIGTERM a mitad de turno). Con
    sesión propia, el grupo entero (`timeout` + `parecord`) recibe SIGTERM, que `parecord` atiende cerrando el
    fichero; si no termina en 2 s, SIGKILL. Misma semántica que `subprocess.run` para `check`, `capture_output`
    y `timeout`."""
    tubo = subprocess.PIPE if capture_output else None
    with subprocess.Popen(orden, stdout=tubo, stderr=tubo, start_new_session=True) as proceso:
        try:
            salida, errores = proceso.communicate(timeout=timeout)
        except BaseException:
            _terminar_grupo(proceso)
            raise
    if check and proceso.returncode:
        raise subprocess.CalledProcessError(proceso.returncode, orden, salida, errores)
    return subprocess.CompletedProcess(orden, proceso.returncode, salida, errores)


def _terminar_grupo(proceso: subprocess.Popen) -> None:
    for senal, espera in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        try:
            os.killpg(proceso.pid, senal)
        except ProcessLookupError:
            return
        try:
            proceso.wait(timeout=espera)
            return
        except subprocess.TimeoutExpired:
            continue


class Microfono:
    def __init__(
        self,
        directorio: str = "/tmp/aura",
        segundos: int = 5,
        tope_reproduccion_s: int = 60,
        ejecutar: Callable = _ejecutar_en_grupo,
        disponible: Callable[[str], object] = shutil.which,
    ) -> None:
        self._dir = directorio
        self._segundos = segundos
        self._tope_reproduccion_s = tope_reproduccion_s
        self._ejecutar = ejecutar
        self._disponible = disponible
        self.ultimo_corte: str | None = None  # por qué terminó la última captura con fin de habla (perfil LAT)
        _directorio_privado(self._dir)
        # Un turno interrumpido a la fuerza (el proceso muere) no llega a su `finally`: su audio quedaría
        # en disco. Encontrado `[EJEC]` en la demo de la semana 2. Al abrir el micrófono se purga.
        for nombre in os.listdir(self._dir):
            if nombre.endswith(".wav") and nombre.startswith(("entrada_", "resp_")):
                descartar_audio(os.path.join(self._dir, nombre))

    def comprobar(self) -> str:
        """Para que el ARRANQUE diga la verdad sobre el audio antes del primer turno."""
        faltan = [p for p in (_GRABADOR, _REPRODUCTOR) if not self._disponible(p)]
        if faltan:
            raise DispositivoNoDisponible(f"faltan las herramientas de audio: {', '.join(faltan)}")
        return f"{_GRABADOR} + {_REPRODUCTOR}, {self._segundos} s por turno"

    def escuchar(self, trace_id: str) -> str:
        """Graba del micrófono durante `segundos` y devuelve la ruta del WAV (mono, 16 kHz)."""
        ruta = os.path.join(self._dir, f"entrada_{trace_id}.wav")
        orden = [
            "timeout",
            str(self._segundos),
            _GRABADOR,
            "--channels=1",
            "--rate=16000",
            "--format=s16le",
            "--file-format=wav",
            ruta,
        ]
        try:
            # `timeout` termina la grabación con código 124: es el final esperado, no un fallo.
            self._ejecutar(orden, check=False, capture_output=True)
        except OSError as e:
            self.descartar(ruta)
            raise DispositivoNoDisponible(f"no se pudo abrir el micrófono: {e}") from e
        except BaseException:
            # Grabación INTERRUMPIDA (SIGTERM, Ctrl-C): el WAV parcial es audio del usuario y aún no hay nadie
            # que lo descarte —`_turno_de_voz` todavía no tiene la ruta—. Se borra aquí y se propaga.
            self.descartar(ruta)
            raise
        if _frames(ruta) == 0:
            # Un WAV vacío llegaría a Whisper, que alucina texto sobre el silencio.
            self.descartar(ruta)
            raise DispositivoNoDisponible("el micrófono no entregó audio")
        return ruta

    def escuchar_hasta_silencio(self, trace_id: str, flujo=None) -> str:
        """Graba hasta que la persona deja de hablar y devuelve la ruta del WAV (mono, 16 kHz, 0600).

        Solo para la escucha continua; pulsar-para-hablar sigue con duración fija (`escuchar`). Reutiliza
        el flujo de `escucha.py` (`parecord --latency-msec=20`). `flujo` es inyectable: read(n)/close().
        El flujo se cierra SIEMPRE: cerrarlo termina `parecord` y suelta el micrófono."""
        if flujo is None:
            from .escucha import _FlujoDelMicrofono  # import perezoso: escucha.py importa este módulo

            try:
                flujo = _FlujoDelMicrofono()
            except OSError as e:
                raise DispositivoNoDisponible(f"no se pudo abrir el micrófono: {e}") from e
        try:
            bloques, corte = _leer_hasta_silencio(flujo)
        finally:
            flujo.close()
        if not bloques:
            raise DispositivoNoDisponible("el micrófono no entregó audio")
        ruta = os.path.join(self._dir, f"entrada_{trace_id}.wav")
        _escribir_wav_privado(ruta, b"".join(bloques))
        self.ultimo_corte = corte
        return ruta

    def reproducir(self, ruta: str | None) -> bool:
        """Reproduce la respuesta por el altavoz. False si no hay nada que reproducir o falla."""
        if not ruta or not os.path.isfile(ruta):
            return False
        try:
            # `--latency-msec=30`: `[EJEC]` 2026-09-29 (HC-1, PipeWire 1.0.5). Con la latencia por defecto
            # PulseAudio retrasa el audio ~2000 ms (P50 2002 ms en captura); con 20 ms en `parecord` y 30 ms
            # aquí, altavoz->aire->micrófono es P50 85 ms (máx 96). Es UNA etapa del presupuesto de CM1, no
            # el turno: el turno completo sigue por encima de 800 ms (RESULTADO-CM1-HW-ACCEL.md).
            self._ejecutar(
                [_REPRODUCTOR, "--latency-msec=30", ruta],
                check=True,
                capture_output=True,
                timeout=self._tope_reproduccion_s,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def descartar_restos(self, trace_id: str) -> None:
        """Borra el audio de UN turno por su nombre exacto: la grabación y la respuesta sintetizada.

        Para la parada a mitad de turno: el TTS corre en un hilo y puede escribir `resp_<tid>.wav` DESPUÉS de la
        cancelación, cuando el `finally` de `_turno_de_voz` ya pasó sin conocer la ruta. Nombres exactos, nunca
        un patrón: `/tmp/aura` puede tener turnos de otro proceso."""
        for prefijo in ("entrada_", "resp_"):
            self.descartar(os.path.join(self._dir, f"{prefijo}{trace_id}.wav"))

    def descartar(self, ruta: str | None) -> None:
        """Borra un audio del usuario —su grabación o la respuesta que AURA le recitó—: no se archiva.

        Nunca propaga: se llama desde un `finally`, y un fallo al borrar no puede tapar el error del
        turno (hallazgo BAJO de la auditoría). Se registra para que no sea silencioso."""
        descartar_audio(ruta)


def descartar_audio(ruta: str | None) -> None:
    """Borra un audio efímero del usuario. Nunca propaga: se llama desde `finally`.

    Función de módulo, no solo método: un turno ESCRITO con el stack real también sintetiza la
    respuesta, y sin micrófono no hay instancia a la que pedírselo (encontrado en la demo física)."""
    if not ruta:
        return
    try:
        os.remove(ruta)
    except FileNotFoundError:
        pass
    except OSError as e:
        obs.log("WARN", "microfono", f"no se pudo borrar un audio del usuario: {e}", "-", audit=True)


def _directorio_privado(ruta: str) -> None:
    """El audio del usuario vive en un directorio SOLO suyo.

    Hallazgo MEDIO de la auditoría (2026-09-27): `/tmp/aura` quedaba 775 y los WAV 664, así que cualquier
    usuario local podía leer la voz mientras existía. Y `os.makedirs(exist_ok=True)` seguía un enlace
    simbólico plantado de antemano: la voz se habría escrito donde decidiera otro.
    """
    if os.path.islink(ruta):
        raise DispositivoNoDisponible(f"el directorio de audio es un enlace simbólico: {ruta}")
    os.makedirs(ruta, mode=0o700, exist_ok=True)
    estado = os.stat(ruta)
    if estado.st_uid != os.getuid():
        raise DispositivoNoDisponible(f"el directorio de audio pertenece a otro usuario: {ruta}")
    if estado.st_mode & 0o077:
        os.chmod(ruta, 0o700)


def _frames(ruta: str) -> int:
    try:
        with wave.open(ruta) as f:
            return f.getnframes()
    except (OSError, EOFError, wave.Error):
        return 0


def _rms(bloque: bytes) -> float:
    muestras = array.array("h", bloque[: len(bloque) // 2 * 2])
    if not muestras:
        return 0.0
    return math.sqrt(sum(m * m for m in muestras) / len(muestras))


def _leer_hasta_silencio(flujo) -> tuple[list[bytes], str]:
    """Lee bloques de 125 ms hasta fin de habla, 5 s sin voz o 6 s de tope. Devuelve (bloques, motivo)."""
    bloques: list[bytes] = []
    ruido = math.inf
    hubo_habla = False
    racha = 0  # bloques seguidos por encima del umbral
    silencio_ms = 0
    while True:
        datos = flujo.read(_BLOQUE_BYTES)
        if not datos:
            return bloques, "sin_audio" if not bloques else ("silencio" if hubo_habla else "sin_voz")
        bloques.append(datos)
        tiempo_ms = len(bloques) * _BLOQUE_MS
        nivel = _rms(datos)
        ruido = min(ruido, nivel)
        umbral = max(_FACTOR_RUIDO * ruido, _RMS_MINIMO)
        if len(bloques) <= _BLOQUES_CALIBRADO:
            pass
        elif nivel <= umbral and not hubo_habla:
            racha = 0
        elif nivel > umbral:
            racha += 1
            if racha >= _HABLA_MINIMA_BLOQUES:
                hubo_habla = True
            silencio_ms = 0
        elif hubo_habla:
            racha = 0
            silencio_ms += _BLOQUE_MS
            if silencio_ms >= _SILENCIO_FINAL_MS:
                return bloques, "silencio"
        if tiempo_ms >= _TOPE_MS:
            return bloques, "tope"
        if not hubo_habla and tiempo_ms >= _ESPERA_SIN_VOZ_MS:
            return bloques, "sin_voz"


def _escribir_wav_privado(ruta: str, pcm: bytes) -> None:
    """Escribe el WAV con permisos 0600; si falla a medias no deja audio en disco."""
    try:
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f, wave.open(f, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(_MUESTREO)
            w.writeframes(pcm)
    except OSError as e:
        descartar_audio(ruta)
        raise DispositivoNoDisponible(f"no se pudo guardar la grabación: {e}") from e
