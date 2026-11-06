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

import json
import os
import shutil
import subprocess
from collections.abc import Callable

from .microfono import DispositivoNoDisponible

_NOMBRE = "aurora"
_SALUDOS = frozenset({"oye", "hola", "hey", "eh", "ey"})

#: Gramática cerrada: el nombre y las palabras con las que se confunde. Los distractores dan a las
#: frases parecidas un sitio al que ir en vez de forzarlas a «aurora».
GRAMATICA = [
    "aurora",
    "hora",
    "ora",
    "oye",
    "hola",
    "a",
    "la",
    "el",
    "me",
    "que",
    "de",
    "por",
    "no",
    "vamos",
    "comer",
    "[unk]",
]

_MUESTREO = 16000


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
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

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
    ) -> None:
        self._modelo = modelo
        self._abrir_flujo = abrir_flujo or _FlujoDelMicrofono
        self._reconocedor = reconocedor or self._reconocedor_vosk
        self._bloque = bloque
        self._vosk_modelo = None
        self._flujo_activo: object | None = None  # el flujo de `esperar_llamada` en curso, para `detener`

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

    def esperar_llamada(self) -> bool:
        """Escucha hasta oír su nombre (True) o hasta que el flujo se acabe (False)."""
        rec = self._reconocedor()
        flujo = self._abrir_flujo()
        self._flujo_activo = flujo
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
            self._flujo_activo = None
            cerrar = getattr(flujo, "close", None)
            if cerrar:
                cerrar()

    def detener(self) -> None:
        """Corta la escucha en curso desde otro hilo: cierra el flujo y `esperar_llamada` devuelve False.

        Sin esto, una parada por SIGTERM dejaba el hilo de Vosk bloqueado en `read` y el proceso no podía
        terminar (`asyncio.run` espera a sus hilos). Cerrar es lo mismo que ya hace el `finally`."""
        flujo = self._flujo_activo
        cerrar = getattr(flujo, "close", None)
        if cerrar:
            cerrar()
