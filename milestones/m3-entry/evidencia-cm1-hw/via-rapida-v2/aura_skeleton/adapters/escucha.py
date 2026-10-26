"""Escucha continua con palabra de activación — AURA acude cuando la llaman por su nombre.

Bible 6.2 §46: «El micrófono siempre-escucha procesa LOCALMENTE (Whisper local, ADR-0008); el audio no
sale del perímetro… El wake word activa; fuera de él no se transmite.» Hasta la campaña del 2026-09-27
AURA solo oía si se pulsaba Enter.

POR QUÉ VOSK Y NO WHISPER PARA ESTO. Whisper tarda ~7 s por fragmento en HC-1: inservible para estar
atento. Vosk con una gramática cerrada trabaja a ~0,1-0,2 s por segundo de audio `[EJEC]`. Whisper
sigue transcribiendo la ORDEN; Vosk solo decide si alguien ha llamado a AURA.

CÓMO EVITA DESPERTARSE SOLA, MEDIDO `[EJEC]` POR EL AIRE (altavoz -> micrófono, HC-1, 24 pruebas):
- Gramática cerrada con distractores («hora», «ora»…). Sin ninguno, «me gusta el color verde» se
  forzaba a «aurora». Con «ahora» COMO distractor, por el aire «Aurora» se oía «ahora» y no
  despertaba nunca (0/3): por eso «ahora» NO está.
- La llamada tiene que ser EXACTA: el nombre solo, o tras un saludo («oye», «hola»). Encaja con el
  diálogo real —«Oye Aurora» -> «¿Sí?» -> orden— y es lo que impide que «ahora vamos a comer», oído
  como «ora vamos comer», o «la aurora boreal» la despierten.
- Resultado: **22/24 correctas y 0 falsos positivos** en 15 frases ajenas y silencio. «Oye Aurora» y
  «Hola Aurora» 3/3; «Aurora» sola 1/3 (se oye «ora ora»): la forma recomendada es «Oye Aurora».

LO QUE NO HACE, A PROPÓSITO:
- **No escribe audio a disco.** El micrófono llega por una tubería y se procesa en memoria.
- **No transmite nada.** Vosk es local; el modelo vive en la USB y no se descarga en marcha.
- **No ejecuta nada.** Solo despierta: la orden sigue el camino de siempre (Motor Único, permisos).
"""

from __future__ import annotations

import array
import json
import math
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence

from .microfono import DispositivoNoDisponible

_NOMBRE = "aurora"
_SALUDOS = frozenset({"oye", "hola", "hey", "eh", "ey"})

#: Gramática cerrada: el nombre y las palabras con las que se confunde. Los distractores dan a las
#: frases parecidas un sitio al que ir en vez de forzarlas a «aurora».
GRAMATICA = ["aurora", "hora", "ora", "oye", "hola", "a", "la", "el", "me", "que", "de", "por", "no",
             "vamos", "comer", "[unk]"]

_MUESTREO = 16000

#: Bloque de la escucha de órdenes: 20 ms a 16 kHz, s16le (2 bytes por muestra).
_BLOQUE_MS = 20
_BLOQUE_BYTES = _MUESTREO * _BLOQUE_MS // 1000 * 2
_BLOQUES_DE_INICIO = 3
_MIN_BLOQUES_DE_RUIDO = 5
_RUIDO_POR_DEFECTO = 100.0
_FACTOR_DE_UMBRAL = 3
_UMBRAL_MINIMO = 300.0


def _rms(datos: bytes) -> float:
    muestras = array.array("h")
    muestras.frombytes(datos[: len(datos) // 2 * 2])
    if not muestras:
        return 0.0
    return math.sqrt(sum(m * m for m in muestras) / len(muestras))


def _umbral(previos: list[float]) -> float:
    """Umbral de habla a partir del ruido de los bloques previos (percentil 20)."""
    if len(previos) < _MIN_BLOQUES_DE_RUIDO:
        ruido = _RUIDO_POR_DEFECTO  # solo informativo: durante el calentamiento no se declara habla
    else:
        ruido = sorted(previos)[int(len(previos) * 0.2)]
    return max(_FACTOR_DE_UMBRAL * ruido, _UMBRAL_MINIMO)


def es_llamada(texto: str) -> bool:
    """True si la frase ES una llamada: «aurora» u «oye/hola aurora», y nada más.

    Exacta a propósito: mencionar el nombre («la aurora boreal») no es llamarla, y una frase que
    empieza parecida («ahora vamos…», oída como «ora vamos…») tampoco."""
    palabras = texto.lower().split()
    if palabras == [_NOMBRE]:
        return True
    return len(palabras) == 2 and palabras[0] in _SALUDOS and palabras[1] == _NOMBRE


class _FlujoDelMicrofono:
    """PCM crudo, mono, 16 kHz, por la salida estándar de `parecord`: nunca toca el disco.

    Cerrar el flujo TERMINA el proceso. Cerrar solo la tubería dejaría a `parecord` vivo, con el
    micrófono abierto y grabando hacia nadie: justo lo que una escucha gobernada no puede hacer.
    """

    def __init__(self, lanzar: Callable = subprocess.Popen) -> None:
        self._proceso = lanzar(
            # `--latency-msec=20`: `[EJEC]` 2026-09-29 (HC-1, PulseAudio sobre PipeWire 1.0.5). Con la
            # latencia por defecto `parecord` entrega el audio con ~2000 ms de retraso (P50 2002 ms);
            # con 20 ms en captura y 30 ms en `paplay`, altavoz->aire->micrófono es P50 85 ms (máx 96).
            ["parecord", "--raw", "--latency-msec=20", "--channels=1", f"--rate={_MUESTREO}", "--format=s16le"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def read(self, n: int) -> bytes:
        return self._proceso.stdout.read(n)

    def close(self) -> None:
        self._proceso.terminate()
        try:
            self._proceso.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proceso.kill()


class OidoContinuo:
    def __init__(
        self,
        modelo: str = "",
        abrir_flujo: Callable | None = None,
        reconocedor: Callable | None = None,
        bloque: int = 4000,
        reconocedor_libre: Callable | None = None,
        gramatica_orden: Sequence[str] | None = None,
        reconocedor_gramatica: Callable | None = None,
    ) -> None:
        self._modelo = modelo
        self._abrir_flujo = abrir_flujo or _FlujoDelMicrofono
        self._reconocedor = reconocedor or self._reconocedor_vosk
        self._reconocedor_libre = reconocedor_libre or self._reconocedor_vosk_libre
        self._gramatica_orden = list(gramatica_orden) if gramatica_orden else None
        self._reconocedor_gramatica = reconocedor_gramatica or self._reconocedor_vosk_gramatica
        self._bloque = bloque
        self._vosk_modelo = None

    def comprobar(self) -> str:
        """Para que el arranque diga la verdad sobre la escucha continua (`INV-9`)."""
        if not self._modelo or not os.path.isdir(self._modelo):
            raise DispositivoNoDisponible(f"no hay modelo de palabra de activación en {self._modelo!r}")
        if not shutil.which("parecord"):
            raise DispositivoNoDisponible("falta parecord para escuchar el micrófono")
        return f"palabra de activación «Aurora» (Vosk local, {os.path.basename(self._modelo)})"

    def preparar(self) -> None:
        """Carga el modelo UNA vez, antes de empezar a escuchar.

        Encontrado en la demo física `[EJEC]` (2026-09-27): el modelo se cargaba en CADA escucha
        —varios segundos leyendo de la USB— y AURA quedaba sorda justo después de cada conversación.
        La persona dijo «Oye Aurora» y no había nadie escuchando."""
        if self._vosk_modelo is None:
            import vosk  # import perezoso: solo quien usa la escucha continua lo necesita

            vosk.SetLogLevel(-1)
            self._vosk_modelo = vosk.Model(self._modelo)

    def _reconocedor_vosk(self):
        import vosk

        self.preparar()
        # El reconocedor sí es nuevo en cada escucha: es barato y no arrastra estado de la anterior.
        return vosk.KaldiRecognizer(self._vosk_modelo, _MUESTREO, json.dumps(GRAMATICA))

    def _reconocedor_vosk_libre(self):
        """Reconocedor SIN gramática para la orden, sobre el MISMO modelo ya cargado (no carga otro)."""
        import vosk

        self.preparar()
        return vosk.KaldiRecognizer(self._vosk_modelo, _MUESTREO)

    def _reconocedor_vosk_gramatica(self):
        """Reconocedor de gramática CERRADA (las órdenes conocidas + `[unk]`) sobre el mismo modelo.

        `ensure_ascii=False` es imprescindible `[EJEC]` 2026-09-29: `json.dumps` escapa «ó» como `\\u00f3`
        y Vosk ignora «cómo» y «cuál» («Ignoring word missing in vocabulary»)."""
        import vosk

        self.preparar()
        gramatica = json.dumps([*(self._gramatica_orden or []), "[unk]"], ensure_ascii=False)
        return vosk.KaldiRecognizer(self._vosk_modelo, _MUESTREO, gramatica)

    def escuchar_orden(self, fin_de_habla_ms: int = 450, max_habla_s: float = 8.0,
                       max_espera_s: float = 5.0) -> str:
        """Transcribe UNA orden con Vosk y devuelve su texto (`""` si no se oyó nada).

        POR QUÉ NO SE USA EL ENDPOINTER DE VOSK. Su endpointer interno espera 0,5-1 s de silencio y
        Vosk 0.3.45 (instalado, `[EJEC]` 2026-09-29) no tiene `SetEndpointerDelays`: no hay API para
        acortarlo. El presupuesto de CM1 (Bible 2.5 §5.1: P50 <= 800 ms) cuenta desde el FIN DE HABLA,
        así que ese medio segundo se comería casi todo. Aquí el fin lo decide un VAD de energía propio y
        Vosk solo transcribe: se le pasan TODOS los bloques y se ignora el valor de `AcceptWaveform`.

        VAD: RMS por bloque de 20 ms (640 bytes a 16 kHz s16le). Ruido de fondo = percentil 20 de los
        bloques ANTERIORES al habla, congelado al empezar ésta. Los 5 primeros bloques (100 ms) son de
        calentamiento: no pueden declarar habla (ver el comentario en el bucle). Umbral =
        max(3 x ruido, 300). Habla = 3 bloques seguidos sobre el umbral; fin = bloques bajo el umbral que
        sumen `fin_de_habla_ms` (450 por defecto: `[EJEC]` 2026-09-29 por el aire, con 300 ms
        «¿Cuál es mi color favorito?» se cortaba tras «cuál es» 4/4 veces; con 450, 0/2).

        GRAMÁTICA (opcional, `gramatica_orden`). Si la hay, un SEGUNDO reconocedor cerrado recibe el mismo
        audio. Al final gana si reconoció algo sin `[unk]`; si no, el libre. Medido `[EJEC]`: el libre
        falla incluso con audio limpio y una orden mal oída puede acabar como dato guardado; el cerrado
        acierta 3/3 en 21-49 ms. Sin gramática el comportamiento es el de siempre. Los tiempos se cuentan en MUESTRAS leídas, no con reloj de pared: es
        determinista y comprobable. Todo en memoria: nada a disco. El flujo se cierra SIEMPRE.
        """
        libre = self._reconocedor_libre()
        gram = self._reconocedor_gramatica() if self._gramatica_orden else None
        recs = (libre,) if gram is None else (libre, gram)
        flujo = self._abrir_flujo()
        max_espera = int(max_espera_s * 1000) // _BLOQUE_MS
        max_habla = int(max_habla_s * 1000) // _BLOQUE_MS
        bloques_de_fin = max(1, -(-fin_de_habla_ms // _BLOQUE_MS))
        previos: list[float] = []
        umbral = 0.0
        habla = False
        seguidos_altos = 0
        seguidos_bajos = 0
        bloques_habla = 0
        try:
            while True:
                datos = flujo.read(_BLOQUE_BYTES)
                if not datos:
                    return self._texto_final(libre, gram) if habla else ""
                for rec in recs:
                    rec.AcceptWaveform(datos)  # su valor de retorno NO decide el fin
                energia = _rms(datos)
                if not habla:
                    umbral = _umbral(previos)
                    # Calentamiento: sin _MIN_BLOQUES_DE_RUIDO bloques no hay ruido medido, y con un
                    # ruido supuesto (100) una sala ruidosa (TV, ~1000) disparaba el «inicio de habla» en
                    # los 3 primeros bloques y nunca llegaba a «fin». 100 ms de calentamiento.
                    listo = len(previos) >= _MIN_BLOQUES_DE_RUIDO
                    seguidos_altos = seguidos_altos + 1 if listo and energia > umbral else 0
                    if seguidos_altos >= _BLOQUES_DE_INICIO:
                        habla = True
                        bloques_habla = seguidos_altos
                        seguidos_bajos = 0
                        continue
                    previos.append(energia)
                    if len(previos) >= max_espera:
                        return ""
                    continue
                bloques_habla += 1
                seguidos_bajos = seguidos_bajos + 1 if energia <= umbral else 0
                if seguidos_bajos >= bloques_de_fin or bloques_habla >= max_habla:
                    return self._texto_final(libre, gram)
        finally:
            cerrar = getattr(flujo, "close", None)
            if cerrar:
                cerrar()

    @staticmethod
    def _texto_final(libre, gram=None) -> str:
        """La gramática gana si reconoció algo SIN `[unk]`; si no, el reconocimiento libre."""
        if gram is not None:
            cerrado = json.loads(gram.FinalResult()).get("text", "").strip()
            if cerrado and "[unk]" not in cerrado:
                return cerrado
        return json.loads(libre.FinalResult()).get("text", "").strip()

    def esperar_llamada(self) -> bool:
        """Escucha hasta oír su nombre (True) o hasta que el flujo se acabe (False)."""
        rec = self._reconocedor()
        flujo = self._abrir_flujo()
        try:
            while True:
                datos = flujo.read(self._bloque)
                if not datos:
                    return False
                # Vosk devuelve True al cerrar una frase (pausa): entonces hay texto final que mirar.
                if rec.AcceptWaveform(datos) and es_llamada(json.loads(rec.Result()).get("text", "")):
                    return True
                # **Ruido CONTINUO (TV encendida): la frase puede no cerrar nunca por falta de silencio**
                # ([EJEC] 2026-09-27, condición problemática). Sin esto, `Result()` no se evalúa y AURA se
                # queda sorda. Se mira también el PARCIAL con la MISMA exactitud (`es_llamada`), así que
                # «la aurora boreal» sigue sin despertar (0 falsos positivos preservados).
                parcial = getattr(rec, "PartialResult", None)
                if parcial is not None and es_llamada(json.loads(parcial()).get("partial", "")):
                    return True
        finally:
            cerrar = getattr(flujo, "close", None)
            if cerrar:
                cerrar()
