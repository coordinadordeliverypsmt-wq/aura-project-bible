"""Adaptador de voz REAL: faster-whisper (STT, ADR-0012) + Piper (TTS, ADR-0013).
Mismo contrato que VoiceAdapterMock (stt/tts). Local, sin terceros (D24). Modelos se cargan de forma perezosa."""

from __future__ import annotations

import asyncio
import importlib
import os
import re
import subprocess
from typing import Any

from .. import observability as obs


class VozNoDisponible(RuntimeError):
    """El motor de voz no puede operar: modelo ausente, ruta invalida, proceso caido o colgado.

    Es un fallo de DISPONIBILIDAD de un periferico, no de integridad ni de autoridad. Se declara con un
    tipo propio para que el turno pueda degradar a texto con honestidad (MISION VOZ, CEO 2026-09-15) en
    vez de morir con un `CalledProcessError` que nadie sabe leer.
    """


#: Tope de espera al sintetizador. **No es una propiedad de la arquitectura** (regla del CEO,
#: 2026-08-04): es un valor derivado de la medicion en HC-1 con `es_MX-ald-medium` leido desde la USB, y
#: depende de ese hardware, de esa voz y de ese soporte. Medido el 2026-09-15: 13,3 s para una frase
#: corta incluyendo la carga del modelo. El tope existe porque `subprocess.run` sin `timeout` convierte
#: un Piper colgado en un turno colgado para siempre; se fija con holgura amplia sobre lo medido porque
#: su trabajo es cortar un CUELGUE, no disciplinar la latencia.
LIMITE_SINTESIS_S = 120

#: Idem para la transcripcion: 39,5 s medidos para un WAV de ~4 s (carga 10,1 s + transcripcion 27,5 s).
LIMITE_TRANSCRIPCION_S = 300

#: Idioma de la transcripcion. AURA habla espanol (Bible 2.4 §6) y el idioma NO cambia turno a turno, asi
#: que detectarlo en cada uno es coste puro. **Medido en HC-1 el 2026-09-15** sobre el mismo WAV, con
#: calentamiento previo y ORDEN ALTERNADO para que no lo decidiera la cache: mediana 25,6 s declarando el
#: idioma frente a 58,0 s detectandolo (n = 3 pares, el declarado gana los 3). El texto transcrito fue
#: IDENTICO en las seis pasadas: esto ahorra tiempo, **no mejora la exactitud** — y decirlo al reves
#: seria vender una precision que no se midio. Dependiente del hardware y del modelo, no del diseno.
IDIOMA = "es"


#: Frecuencia a la que Whisper trabaja internamente, y margen de silencio que se añade a cada lado.
_MUESTREO = 16000
_MARGEN_S = 1

#: Vocabulario de AURA que orienta al transcriptor. Medido `[EJEC]` el 2026-09-27 sobre 15 órdenes
#: cortas sintetizadas con la voz real: solo con el margen, **1/15** exactas («tomo me llamo», «puno me
#: llavo»); con margen y este texto, **12/15**. Es un texto local: no sale de la máquina (`D24`).
#: RIESGO DECLARADO: sesga la transcripción hacia estas frases. No puede saltarse ninguna barrera
#: —toda orden pasa igual por el Motor Único, sus permisos y su confirmación—, pero una frase ambigua
#: puede acercarse a una orden. Se fija con pruebas de falsos positivos.
_VOCABULARIO = (
    "Conversación con AURA. ¿Cómo me llamo? ¿Qué encontraste? ¿Qué hora es? "
    "Mi nombre es. ¿Qué hay conectado? ¿Qué hiciste? ¿Qué te dije antes?"
)
#: **SIN ÓRDENES NI CONFIRMACIONES (cierre semana 2).** Medido `[EJEC]` por el aire: ante audio confuso
#: Whisper devuelve frases de este vocabulario que nadie dijo («Sí.» → «¿Qué hiciste?»). Una orden o un
#: «sí» aquí dentro podría FABRICAR una acción o aprobar una propuesta. Se pierde algo de precisión en
#: «Apaga la tele» (antes la peor transcrita fuera del vocabulario): una orden mal oída se rechaza; una
#: orden inventada se ejecutaría. La prueba lo comprueba con los reconocedores reales del Core.


def sin_eco(texto: str) -> str:
    """Quita las frases IDÉNTICAS y CONSECUTIVAS de una transcripción.

    `[EJEC]` cierre de la semana 2, por el aire: Whisper devolvió «¿Qué hay conectado? ¿Qué hay
    conectado?» —eco del `initial_prompt` con frases del vocabulario— y la pregunta cayó en la pared de
    memoria. Solo se colapsa la repetición exacta (sin distinguir mayúsculas) de una frase completa; nada
    más del texto se toca, así que no se inventa lo que no se dijo."""
    frases = [f for f in re.split(r"(?<=[.?!])\s+", texto) if f]
    limpias: list[str] = []
    for frase in frases:
        if not limpias or frase.casefold() != limpias[-1].casefold():
            limpias.append(frase)
    return " ".join(limpias)


#: Margen que el detector conserva ALREDEDOR del habla. Medido por el aire (2026-10-04): con 200 ms se mordía el
#: arranque suave de «enciende» («Enciente», «No fiende»); antes del recorte se transcribía bien. 600 ms quita los
#: segundos de silencio (la causa del «rainbow» y de los 60 s) sin cortar la primera sílaba.
_RELLENO_VAD_MS = 600


#: Una muestra «al tope» y la fracción a partir de la cual la entrada se considera saturada. Medido (2026-10-04):
#: silencio a 100 % de ganancia = 11,9 % al tope, a 150 % = 74 %; la voz a 50 % llegó con hasta 7,5 % y se entendió.
_TOPE_SATURACION = 0.98
_MAX_SATURADAS = 0.10


def _tramos_de_habla(audio) -> list[tuple[int, int]] | None:
    """Tramos (muestra inicial, final) donde hay habla, según Silero VAD: local, viene con faster-whisper y no
    descarga nada (D24). `[]` = no hay habla. `None` = el detector no está disponible: entonces NO se recorta
    nada, porque inventar silencio sería tan falso como inventar texto."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        marcas = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=300, speech_pad_ms=_RELLENO_VAD_MS))
    except Exception as e:  # noqa: BLE001 - sin detector se transcribe como antes; se dice, no se calla
        obs.log("WARN", "whisper-stt", f"detector de voz no disponible: {type(e).__name__}", "-")
        return None
    return [(int(m["start"]), int(m["end"])) for m in marcas]


class WhisperPiperVoice:
    name = "voice"
    capabilities = ["stt", "tts"]

    def __init__(
        self,
        whisper_model: str = "base",
        piper_voice: str = "",
        out_dir: str = "/tmp/aura",
        limite_sintesis_s: int = LIMITE_SINTESIS_S,
        idioma: str = IDIOMA,
        limite_transcripcion_s: int = LIMITE_TRANSCRIPCION_S,
        sintetizador: object | None = None,
    ) -> None:
        self._wm_name = whisper_model
        self._voice = piper_voice  # ruta al .onnx de la voz Piper (es_MX/es_ES)
        self._out = out_dir
        self._idioma = idioma
        self._limite_sintesis_s = limite_sintesis_s
        self._limite_transcripcion_s = limite_transcripcion_s
        self._model: object = None  # WhisperModel perezoso (Any por import diferido)
        self._piper: object = None  # PiperVoice perezosa: se carga UNA vez (ver `_voz_cargada`)
        self._piper_fallo = False
        # Confianza de la ULTIMA transcripcion real (DP-VOZ-ACCION §8 C4): {no_speech_prob: MAXIMO entre
        # segmentos, avg_logprob: MINIMO}. None si no hubo transcripcion real. Solo cifras: ni texto ni audio.
        self.ultima_confianza: dict[str, float] | None = None
        # Motor de síntesis alternativo (p. ej. espeak-ng, CM1): objeto con `comprobar()` y
        # `sintetizar_wav(texto, ruta)`. None = Piper, comportamiento de siempre.
        self._sintetizador: Any = sintetizador
        os.makedirs(self._out, exist_ok=True)

    def comprobar(self) -> str:
        """Devuelve la ruta de la voz si la sintesis puede operar; lanza `VozNoDisponible` si no.

        Existe para que el ARRANQUE pueda decir la verdad sobre la voz sin sintetizar nada. Antes,
        AURA anunciaba «stack=real, 21 capacidades» y descubria en el primer turno que no tenia voz:
        el patron «declarado != real» que este proyecto ya ha pagado ocho veces (INV-9).
        """
        if self._sintetizador is not None:
            return self._sintetizador.comprobar()
        return self._ruta_de_voz()

    def _ruta_de_voz(self) -> str:
        """Comprueba que hay con que hablar ANTES de invocar a Piper. Devuelve la ruta del `.onnx`.

        Sin esto, `piper --model ''` abortaba con `FileNotFoundError: '..json'`: un error emitido por
        Piper, sobre un fichero que el usuario nunca nombro, que no dice que la voz no esta instalada.
        Piper exige el `.onnx` y su `.onnx.json` JUNTOS, asi que se comprueban los dos.
        """
        if not self._voice:
            raise VozNoDisponible(
                "no hay ninguna voz declarada (AURA_PIPER_VOICE esta vacia): AURA no puede sintetizar"
            )
        if not os.path.isfile(self._voice):
            raise VozNoDisponible(f"la voz declarada no existe: {self._voice}")
        config = self._voice + ".json"
        if not os.path.isfile(config):
            raise VozNoDisponible(f"falta el fichero de configuracion de la voz: {config}")
        return self._voice

    async def stt(self, audio_ref: str, trace_id: str) -> str:
        # Si audio_ref es un WAV existente, se transcribe; si no, se trata como texto (passthrough para --text).
        if isinstance(audio_ref, str) and audio_ref.lower().endswith(".wav") and os.path.exists(audio_ref):
            loop = asyncio.get_event_loop()
            # **EL TOPE DE LA TRANSCRIPCION ES REAL, NO UN COMENTARIO (auditoria del 2026-09-15).** La
            # constante existia y NADIE la usaba: declaraba una proteccion que el codigo no daba, que es
            # el patron «declarado != real» —y cometido justo en el cambio que viene a corregirlo—. Sin
            # esto, una USB que deja de responder a mitad de `transcribe()` cuelga el turno para siempre.
            #
            # HONESTIDAD SOBRE EL ALCANCE: `wait_for` libera EL TURNO, no el hilo. Python no puede matar
            # un hilo del executor, asi que la transcripcion colgada sigue viva en segundo plano hasta que
            # el proceso termine. Lo que se garantiza aqui —y es lo que importa— es que el usuario recibe
            # una respuesta en vez de esperar indefinidamente.
            try:
                text = await asyncio.wait_for(
                    loop.run_in_executor(None, self._stt_sync, audio_ref), self._limite_transcripcion_s
                )
            except TimeoutError as e:
                raise VozNoDisponible(
                    f"la transcripcion no termino en el tiempo limite de {self._limite_transcripcion_s} s"
                ) from e
        else:
            text = audio_ref
            self.ultima_confianza = None  # el texto plano no es una transcripcion: no hay confianza que medir
        # La confianza viaja junto a lo oído: sin ella, un «sí» leído como «no» no se puede diagnosticar.
        conf = self.ultima_confianza
        detalle = f" (no_habla={conf['no_speech_prob']:.3f}, logprob={conf['avg_logprob']:.3f})" if conf else ""
        obs.log("VOICE", "whisper-stt", f"transcripcion: '{text[:50]}'{detalle}", trace_id)
        return text

    def precargar(self) -> None:
        """Carga Whisper (y Piper si hay voz) SIN transcribir ni sintetizar, para que el primer turno no
        pague la carga (~10 s medidos el 2026-10-04). Un fallo no se traga: el primer turno lo dirá igual."""
        self._cargar_whisper()
        if self._sintetizador is None and self._voice:
            self._voz_cargada(self._ruta_de_voz())

    def _cargar_whisper(self):
        import faster_whisper  # import perezoso (D24)

        if self._model is None:
            try:
                # **`local_files_only=True` NO es una optimizacion: es la frontera local-first.** El
                # defecto de la libreria es `False`, de modo que un modelo ausente no fallaba: se
                # DESCARGABA de HuggingFace. En un sistema que declara local-first y sin claves de
                # terceros (D24, ADR-0001), una salida a la red que nadie decidio es un defecto, no un
                # apano. Si el modelo no esta, el turno lo dice; no lo baja por su cuenta.
                self._model = faster_whisper.WhisperModel(
                    self._wm_name, device="auto", compute_type="int8", local_files_only=True
                )
            except Exception as e:
                raise VozNoDisponible(
                    f"no hay modelo de transcripcion utilizable ({self._wm_name!r}); no se descarga nada: {e}"
                ) from e
        return self._model

    def _stt_sync(self, wav: str) -> str:
        import faster_whisper  # import perezoso (D24)

        model = self._cargar_whisper()
        self.ultima_confianza = None  # un fallo o una transcripcion vacia no heredan la cifra del turno previo
        try:
            # **UN MARGEN DE SILENCIO A CADA LADO (campaña, 2026-09-27).** Medido `[EJEC]` con los
            # modelos reales: «¿Cómo me llamo?» (1,2 s) llegaba como «¡Vamos, me llamo!». El modelo
            # `base` alucina con fragmentos muy cortos; ni temperatura 0 ni cortar el contexto lo
            # corregian, y 1 s de silencio a cada lado si («como me llamo»). La orden hablada mas
            # corta es tambien la mas frecuente, asi que no es un caso limite.
            # Por nombre y no con `import`: el stub de numpy usa sintaxis de Python 3.12 y mypy
            # (python_version 3.11) abortaba sin revisar AURA («errors prevented further checking»).
            np = importlib.import_module("numpy")

            audio = faster_whisper.decode_audio(wav, sampling_rate=_MUESTREO)
            # **SOLO LO QUE ES HABLA (E2E físico, 2026-10-04).** Medido por el aire [EJEC]: un «sí» de una sílaba
            # en ~5 s de grabación llegó como «¡¿¡¡¡¡ … rainbow! …» tras 61 s de reintentos, y un turno en
            # silencio se contestó como si fuera una pregunta. Whisper alucina cuando recibe sobre todo
            # silencio. Sin habla no se transcribe nada; con habla se recorta a ella (y el margen de abajo se
            # conserva, que es lo que salva las frases cortas).
            # **ENTRADA SATURADA (causa raíz del E2E fallido, 2026-10-04, medida).** La ganancia del micrófono pasó
            # de 27 % a 150 % fuera de AURA: en silencio el 74 % de las muestras quedaban al tope y Whisper recibía
            # una señal destruida. No se transcribe como si fuera voz: se dice, para que se corrija (INV-9).
            saturadas = float(np.mean(np.abs(audio) >= _TOPE_SATURACION))
            if saturadas >= _MAX_SATURADAS:
                obs.log(
                    "WARN", "whisper-stt", f"entrada saturada: {saturadas:.0%} de muestras al tope", "-", audit=True
                )
                raise VozNoDisponible(
                    f"el micrófono está saturado ({saturadas:.0%} de la señal recortada): baja su ganancia "
                    "(medido: 27 % transcribe bien; 150 % no)"
                )
            tramos = _tramos_de_habla(audio)
            if tramos == []:
                return ""
            if tramos:
                audio = audio[tramos[0][0] : tramos[-1][1]]
            margen = np.zeros(_MUESTREO * _MARGEN_S, dtype=audio.dtype)
            audio = np.concatenate([margen, audio, margen])
            segments, _ = model.transcribe(  # type: ignore[attr-defined]
                audio, language=self._idioma, initial_prompt=_VOCABULARIO
            )
            segmentos = list(segments)  # el generador se consume UNA vez: texto y confianza salen de aqui
            # Un segmento sin las dos cifras (no es el caso de faster-whisper) no inventa confianza.
            medidos = [s for s in segmentos if hasattr(s, "no_speech_prob") and hasattr(s, "avg_logprob")]
            if medidos:
                self.ultima_confianza = {
                    "no_speech_prob": max(float(s.no_speech_prob) for s in medidos),
                    "avg_logprob": min(float(s.avg_logprob) for s in medidos),
                }
            return sin_eco(" ".join(s.text for s in segmentos).strip())
        except Exception as e:
            raise VozNoDisponible(f"la transcripcion de {wav!r} fallo: {e}") from e

    async def tts(self, text: str, trace_id: str) -> str:
        out = os.path.join(self._out, f"resp_{trace_id}.wav")
        loop = asyncio.get_event_loop()
        # El tope cubre los DOS caminos. En el precargado la sintesis corre en el proceso, asi que
        # `wait_for` libera EL TURNO, no el hilo —la misma honestidad declarada para la transcripcion—.
        try:
            await asyncio.wait_for(loop.run_in_executor(None, self._tts_sync, text, out), self._limite_sintesis_s)
        except TimeoutError as e:
            raise VozNoDisponible(
                f"el sintetizador no termino en el tiempo limite de {self._limite_sintesis_s} s"
            ) from e
        motor = "piper-tts" if self._sintetizador is None else "espeak-ng"
        obs.log("VOICE", motor, f"audio generado: {out}", trace_id)
        return out

    def _voz_cargada(self, ruta: str):
        """La voz Piper en memoria, cargada UNA vez; None si no se puede cargar.

        **Medido `[EJEC]` en HC-1 (2026-09-27):** el CLI tarda 5,9 s por frase porque recarga el modelo
        en cada llamada; con la voz ya cargada, 1,8-2,0 s. Es el mayor recorte de latencia disponible
        sin cambiar el modelo, y CM1 (Bible 2.5 §5.1) es el criterio que decide la aceptacion de R1.
        Si la carga falla se usa el CLI —mas lento, igual de correcto— y se dice una vez.
        """
        if self._piper is None and not self._piper_fallo:
            try:
                # Import perezoso (D24) y por nombre: el paquete de Piper trae tipos que arrastran numpy,
                # cuyo stub hacía abortar a mypy antes de revisar AURA.
                piper = importlib.import_module("piper")
                self._piper = piper.PiperVoice.load(ruta)
            except Exception as e:  # noqa: BLE001 - cualquier fallo de carga cae al CLI declarado
                self._piper_fallo = True
                obs.log("WARN", "piper-tts", f"voz no precargable, se usa el CLI (mas lento): {e}", "-", audit=True)
        return self._piper

    def _tts_sync(self, text: str, out: str) -> None:
        if self._sintetizador is not None:
            try:
                self._sintetizador.sintetizar_wav(text, out)
            except VozNoDisponible:
                raise
            except Exception as e:  # noqa: BLE001
                raise VozNoDisponible(f"el sintetizador fallo: {e}") from e
            return
        voz = self._ruta_de_voz()
        cargada = self._voz_cargada(voz)
        if cargada is not None:
            import wave

            try:
                with wave.open(out, "wb") as destino:
                    cargada.synthesize_wav(text, destino)
                return
            except Exception as e:  # noqa: BLE001
                raise VozNoDisponible(f"el sintetizador fallo: {e}") from e
        self._tts_cli(voz, text, out)

    def _tts_cli(self, voz: str, text: str, out: str) -> None:
        # Respaldo: Piper via CLI (robusto entre versiones), con su propio tope de proceso.

        try:
            subprocess.run(
                ["piper", "--model", voz, "--output_file", out],
                input=text.encode(),
                check=True,
                timeout=self._limite_sintesis_s,
            )
        except subprocess.TimeoutExpired as e:
            raise VozNoDisponible(
                f"el sintetizador no termino en el tiempo limite de {self._limite_sintesis_s} s"
            ) from e
        except (subprocess.CalledProcessError, OSError) as e:
            raise VozNoDisponible(f"el sintetizador fallo: {e}") from e
