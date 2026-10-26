"""Percepción visual — primera grada (acta del CEO, 2026-09-27).

El acta autoriza la capacidad visual. Esta grada es la mínima honesta y AMBIENTAL: AURA recibe un FRAME
de una fuente de vídeo y reporta solo sus metadatos (recibido, tamaño, fuente). Deliberadamente NO hace,
porque cada una es una grada posterior con su propia evidencia y —para personas— una decisión de diseño
elevada por su choque con ALERTA-002 (sin perfiles de terceros):

    - NO detecta personas ni objetos;
    - NO identifica a nadie;
    - NO emite señales de aprendizaje (`senales.py`);
    - NO guarda la imagen: el `Frame` son metadatos, los píxeles no entran al Core.

Igual que el registro de proveedores de contexto: **el Core no conoce cámaras concretas.** La fuente se
inyecta; una que falla degrada la lectura, no derriba el turno.

Regla dura del acta: **nunca `CÁMARA → ACCIÓN`.** Esta lectura es entrada; cualquier acción seguiría
después por interpretación → contexto → autorización → Motor Único, nunca desde aquí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .. import observability as obs

#: Nota fija que acompaña a toda lectura: recibir un frame no es ver, detectar ni identificar.
_NOTA = "frame ambiental: la detección de personas y la identidad no están implementadas; no se afirman"


@dataclass(frozen=True)
class Frame:
    """Metadatos de un fotograma. **No lleva los píxeles**: nada que persistir en el Core."""

    ancho: int
    alto: int
    fuente: str


@dataclass(frozen=True)
class LecturaVisual:
    """Lo que AURA puede afirmar honestamente de una captura. Persona e identidad son `None` mientras
    esas gradas no existan: `None` = «no lo sé / no implementado», nunca «no hay»."""

    frame_recibido: bool
    fuente: str
    ancho: int | None = None
    alto: int | None = None
    persona_detectada: bool | None = None
    identidad: str | None = None
    nota: str = _NOTA


import time as _time  # noqa: E402


@dataclass(frozen=True)
class Observacion:
    """Una `LecturaVisual` convertida en dato CONSUMIBLE por el sistema (DP-FRAME-A-OBSERVACION, Alt B).

    Deliberadamente mínima e imagen-cero: solo metadatos. Separa por construcción
    `observación ≠ evento ≠ persona ≠ identidad`: NO tiene campos de persona, identidad, evento ni píxeles.
    """

    superficie: str
    fuente: str
    tipo_fuente: str
    frame_recibido: bool
    trace_id: str
    ancho: int | None = None
    alto: int | None = None
    timestamp: float = field(default_factory=_time.time)


def observacion_de(lectura, superficie: str, tipo_fuente: str, trace_id: str) -> Observacion:
    """Construye la Observación desde una `LecturaVisual`. No añade nada que la lectura no tenga:
    persona/identidad NO se propagan (esta grada no los maneja)."""
    return Observacion(
        superficie=superficie,
        fuente=lectura.fuente,
        tipo_fuente=tipo_fuente,
        frame_recibido=lectura.frame_recibido,
        trace_id=trace_id,
        ancho=lectura.ancho,
        alto=lectura.alto,
    )


def describir_observacion(obs: Observacion) -> str:
    """Texto honesto para la superficie conversacional. Nunca afirma contenido/persona/identidad."""
    if not obs.frame_recibido:
        return f"No recibí imagen de «{obs.superficie}» ahora mismo."
    return (
        f"Recibí un frame de «{obs.superficie}» ({obs.fuente}, {obs.ancho}x{obs.alto}). "
        f"No interpreto su contenido ni identifico a nadie: solo confirmo que hay señal de vídeo."
    )


@runtime_checkable
class FuenteDeVision(Protocol):
    """Contrato de una cámara, presente o futura (local, ONVIF, RTSP, DVR…). Pasiva: observa, no actúa."""

    nombre: str

    def capturar(self) -> Frame | None: ...

    def liberar(self) -> None: ...


class PercepcionVisual:
    """Recibe un frame de una fuente inyectada y lo reduce a una `LecturaVisual` honesta."""

    def __init__(self, fuente: FuenteDeVision, superficie: str | None = None, politica=None) -> None:
        self._fuente = fuente
        self._superficie = superficie
        self._politica = politica  # RegistroDeSuperficies | None

    def percibir(self, trace_id: str) -> LecturaVisual:
        # Política por superficie ANTES de tocar la cámara (corrección CEO 2026-09-28): de una superficie
        # no autorizada NO se captura nada. La cámara local (sin política) sigue igual.
        if self._politica is not None and not self._politica.puede_procesar_visual(self._superficie or ""):
            obs.log(
                "PERC",
                "vision",
                f"superficie '{self._superficie}' sin permiso de proceso visual; no se captura",
                trace_id,
                audit=True,
            )
            return LecturaVisual(
                frame_recibido=False,
                fuente=self._fuente.nombre,
                nota="superficie no autorizada para procesamiento visual",
            )
        try:
            frame = self._fuente.capturar()
        except Exception as e:
            # Un sensor desconectado es condición del entorno, no un crash (misma lección que contexto.py).
            obs.log("PERC", "vision", f"fuente '{self._fuente.nombre}' no disponible: {e}", trace_id)
            return LecturaVisual(frame_recibido=False, fuente=self._fuente.nombre)
        finally:
            liberar = getattr(self._fuente, "liberar", None)
            if liberar is not None:
                liberar()
        if frame is None:
            obs.log("PERC", "vision", f"'{self._fuente.nombre}' no entregó frame", trace_id)
            return LecturaVisual(frame_recibido=False, fuente=self._fuente.nombre)
        obs.log(
            "PERC",
            "vision",
            f"frame {frame.ancho}x{frame.alto} de '{frame.fuente}' (sin guardar)",
            trace_id,
            audit=True,
        )
        return LecturaVisual(frame_recibido=True, fuente=frame.fuente, ancho=frame.ancho, alto=frame.alto)


class PercepcionBajoDemanda:
    """Consumidor BAJO DEMANDA (DP aprobado): dado un `surface_id`, produce una `Observacion` efímera si la
    política autoriza esa superficie. Imagen-cero (reutiliza `PercepcionVisual`, que no guarda píxeles).
    No hay bucle ni captura continua: solo `observar()` captura, y una vez.

    `fuentes`: {surface_id: (FuenteDeVision, tipo_fuente)}. La política decide si se toca la cámara.
    """

    def __init__(self, fuentes: dict, politica) -> None:
        self._fuentes = fuentes
        self._politica = politica

    def superficies(self) -> list[str]:
        return sorted(self._fuentes)

    def superficies_autorizadas(self) -> list[str]:
        """Las cámaras que la política deja MIRAR. Para decírselo a la persona; no toca ninguna cámara."""
        if self._politica is None:  # como `observar`: sin política, la cámara local sigue igual
            return sorted(self._fuentes)
        return [s for s in sorted(self._fuentes) if self._politica.puede_procesar_visual(s)]

    def observar(self, surface_id: str, trace_id: str) -> Observacion | None:
        entrada = self._fuentes.get(surface_id)
        if entrada is None:
            obs.log("PERC", "vision", f"superficie '{surface_id}' no registrada; no observo", trace_id)
            return None
        fuente, tipo = entrada
        # PercepcionVisual comprueba la política ANTES de capturar: superficie no autorizada -> no toca cámara.
        lectura = PercepcionVisual(fuente, superficie=surface_id, politica=self._politica).percibir(trace_id)
        if self._politica is not None and not self._politica.puede_procesar_visual(surface_id):
            return None
        return observacion_de(lectura, superficie=surface_id, tipo_fuente=tipo, trace_id=trace_id)


def es_consulta_visual(texto: str) -> str | None:
    """Reconoce «¿qué ves en la cámara X?» y devuelve X (el nombre de la superficie), o None. Por frase
    cerrada: no roba a otras superficies. Sin nombre de cámara -> None (no desvía)."""
    return _consulta_camara(texto, r"\b(?:que ves|que hay|que se ve|que estas viendo)\b")


def es_consulta_visual_sin_camara(texto: str) -> bool:
    """«¿Qué ves en la cámara?» SIN decir cuál. Frase cerrada: se pregunta cuál, no se elige ni se captura.

    Medido `[EJEC]` (2026-10-22): sin esto caía en la pared de memoria («No tengo ningún recuerdo…»)."""
    import re

    patron = r"(?:(?:oye )?aurora )?(?:que ves|que hay|que se ve|que estas viendo) en la camara"
    return re.fullmatch(patron, _normalizar(texto)) is not None


def pedir_camara(autorizadas: list[str], verbo: str = "mirar", ejemplo: str = "qué ves") -> str:
    """Qué cámaras AUTORIZADAS puede intentar <verbo> AURA, sin haber tocado ninguna.

    No afirma que estén accesibles: la política autoriza, pero no comprueba la conexión."""
    if not autorizadas:
        return f"No tengo ninguna cámara autorizada para {verbo} ahora mismo, así que no puedo responderte."
    lista = ", ".join(f"«{s}»" for s in autorizadas)
    return (
        f"¿Qué cámara? Cámaras que puedo intentar {verbo}: {lista}. "
        f"Dímelo así: «¿{ejemplo} en la cámara {autorizadas[0]}?»."
    )


def _normalizar(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    for signo in "¿?¡!.,":
        t = t.replace(signo, " ")
    return " ".join(t.split())


def _consulta_camara(texto: str, patron_intencion: str) -> str | None:
    """Núcleo común: reconoce «<intención> ... cámara X» y devuelve X. Frase cerrada, sin robar superficies."""
    import re

    t = _normalizar(texto)
    m = re.search(patron_intencion + r".*?\bcamara\b\s+(.+)$", t)
    if not m:
        return None
    nombre = m.group(1).strip()
    for corte in (" por favor", " ahora"):
        if nombre.endswith(corte):
            nombre = nombre[: -len(corte)].strip()
    return nombre or None


# ======================================================================================== ESCUCHAR ==
# Percepción AUDITIVA de cámara bajo demanda (bloque multimodal, acta CEO 2026-09-28). Simetría con la
# visual: AURA recibe AUDIO de una fuente SOLO cuando se le pide, lo reduce a metadatos + transcripción
# opcional, **sin persistir el audio crudo**, sin identidad, sin escucha continua, gated por política.

_NOTA_AUDIO = (
    "audio ambiental bajo demanda: la identidad de quien habla no se determina ni se afirma; no hay escucha continua"
)


@dataclass(frozen=True)
class AudioPCM:
    """Audio decodificado a PCM, TRANSITORIO (para el STT). No se persiste: no entra en la Observación.

    `pcm` (muestras crudas) es opcional y efímero; `muestras`/`duracion_s` son metadatos."""

    rate: int
    muestras: int
    duracion_s: float | None = None
    pcm: object | None = None  # ndarray/bytes transitorios para el STT; NUNCA se guarda


@dataclass(frozen=True)
class LecturaAuditiva:
    """Lo que AURA puede afirmar honestamente de una captura de audio. `transcripcion=None` = no
    interpretado (sin STT o sin audio), nunca «silencio»."""

    audio_recibido: bool
    fuente: str
    duracion_s: float | None = None
    transcripcion: str | None = None
    nota: str = _NOTA_AUDIO


@dataclass(frozen=True)
class ObservacionAuditiva:
    """`LecturaAuditiva` convertida en dato consumible. Audio-cero de persistencia: solo metadatos +
    transcripción efímera. Sin persona, sin identidad, sin evento, sin PCM."""

    superficie: str
    fuente: str
    tipo_fuente: str
    audio_recibido: bool
    trace_id: str
    duracion_s: float | None = None
    transcripcion: str | None = None
    timestamp: float = field(default_factory=_time.time)


def observacion_auditiva_de(lectura, superficie: str, tipo_fuente: str, trace_id: str) -> ObservacionAuditiva:
    return ObservacionAuditiva(
        superficie=superficie,
        fuente=lectura.fuente,
        tipo_fuente=tipo_fuente,
        audio_recibido=lectura.audio_recibido,
        trace_id=trace_id,
        duracion_s=lectura.duracion_s,
        transcripcion=lectura.transcripcion,
    )


def describir_observacion_auditiva(obs: ObservacionAuditiva) -> str:
    """Texto honesto. Nunca afirma identidad; si no hay audio o no se transcribió, lo dice sin inventar."""
    if not obs.audio_recibido:
        return f"No recibí audio de «{obs.superficie}» ahora mismo."
    if obs.transcripcion is None:
        return (
            f"Recibí audio de «{obs.superficie}» ({obs.fuente}) pero no lo interpreto ahora "
            f"(sin transcripción); no identifico a nadie."
        )
    return (
        f"En «{obs.superficie}» se oye: «{obs.transcripcion}». "
        f"Transcribo lo dicho, no identifico a nadie ni infiero intención."
    )


@runtime_checkable
class FuenteDeAudio(Protocol):
    """Contrato de una fuente de audio de cámara (RTSP/ONVIF…). Pasiva: captura bajo demanda, no actúa."""

    nombre: str

    def capturar_audio(self) -> AudioPCM | None: ...

    def liberar(self) -> None: ...


class PercepcionAuditiva:
    """Recibe audio de una fuente inyectada y lo reduce a una `LecturaAuditiva`. Transcribe con un STT
    inyectado (opcional). El audio crudo NO se persiste ni se registra."""

    def __init__(self, fuente: FuenteDeAudio, superficie: str | None = None, politica=None, transcriptor=None) -> None:
        self._fuente = fuente
        self._superficie = superficie
        self._politica = politica
        self._transcriptor = transcriptor

    def percibir_audio(self, trace_id: str) -> LecturaAuditiva:
        if self._politica is not None and not self._politica.puede_procesar_audio(self._superficie or ""):
            obs.log(
                "PERC",
                "audio",
                f"superficie '{self._superficie}' sin permiso de audio; no se captura",
                trace_id,
                audit=True,
            )
            return LecturaAuditiva(
                audio_recibido=False,
                fuente=self._fuente.nombre,
                nota="superficie no autorizada para procesamiento de audio",
            )
        try:
            pcm = self._fuente.capturar_audio()
        except Exception as e:
            obs.log("PERC", "audio", f"fuente '{self._fuente.nombre}' de audio no disponible: {e}", trace_id)
            return LecturaAuditiva(audio_recibido=False, fuente=self._fuente.nombre)
        finally:
            liberar = getattr(self._fuente, "liberar", None)
            if liberar is not None:
                liberar()
        if pcm is None:
            obs.log("PERC", "audio", f"'{self._fuente.nombre}' no entregó audio", trace_id)
            return LecturaAuditiva(audio_recibido=False, fuente=self._fuente.nombre)
        transcripcion = None
        if self._transcriptor is not None:
            transcripcion = self._transcriptor(pcm, trace_id) or None
        # AUDIT: solo metadatos, NUNCA la transcripción (es contenido de un interior; no se persiste).
        obs.log(
            "PERC",
            "audio",
            f"audio {pcm.duracion_s}s de '{self._fuente.nombre}' "
            f"(transcrito={'si' if transcripcion else 'no'}; audio no guardado)",
            trace_id,
            audit=True,
        )
        return LecturaAuditiva(
            audio_recibido=True, fuente=self._fuente.nombre, duracion_s=pcm.duracion_s, transcripcion=transcripcion
        )


class PercepcionAuditivaBajoDemanda:
    """Consumidor BAJO DEMANDA de audio: dado un `surface_id`, produce una `ObservacionAuditiva` efímera si
    la política de AUDIO autoriza esa superficie. Sin bucle, sin escucha continua: solo `observar_audio()`.

    `fuentes`: {surface_id: (FuenteDeAudio, tipo_fuente)}. `transcriptor(pcm, trace_id) -> str|None`.
    """

    def __init__(self, fuentes: dict, politica, transcriptor=None) -> None:
        self._fuentes = fuentes
        self._politica = politica
        self._transcriptor = transcriptor

    def superficies(self) -> list[str]:
        return sorted(self._fuentes)

    def superficies_autorizadas(self) -> list[str]:
        """Las cámaras que la política deja ESCUCHAR (audio). Solo informa; no abre ningún micrófono."""
        if self._politica is None:
            return sorted(self._fuentes)
        return [s for s in sorted(self._fuentes) if self._politica.puede_procesar_audio(s)]

    def observar_audio(self, surface_id: str, trace_id: str) -> ObservacionAuditiva | None:
        entrada = self._fuentes.get(surface_id)
        if entrada is None:
            obs.log("PERC", "audio", f"superficie '{surface_id}' no registrada; no escucho", trace_id)
            return None
        fuente, tipo = entrada
        lectura = PercepcionAuditiva(
            fuente, superficie=surface_id, politica=self._politica, transcriptor=self._transcriptor
        ).percibir_audio(trace_id)
        if self._politica is not None and not self._politica.puede_procesar_audio(surface_id):
            return None
        return observacion_auditiva_de(lectura, superficie=surface_id, tipo_fuente=tipo, trace_id=trace_id)


def es_consulta_auditiva_sin_camara(texto: str) -> bool:
    """«¿Qué oyes en la cámara?» SIN decir cuál. Frase cerrada: se pregunta cuál, no se escucha ninguna."""
    import re

    patron = r"(?:(?:oye )?aurora )?(?:que se oye|que oyes|que escuchas|que se escucha) en la camara"
    return re.fullmatch(patron, _normalizar(texto)) is not None


def es_consulta_auditiva(texto: str) -> str | None:
    """Reconoce «¿qué se oye / qué escuchas en la cámara X?» y devuelve X, o None. Cerrada: no colisiona
    con la consulta visual ni con otras superficies."""
    return _consulta_camara(texto, r"\b(?:que se oye|que escuchas|que se escucha|que oyes)\b")


# ========================================================================================= EVENTO ==
# Detección PROPIA de movimiento sobre frames (NO ONVIF Events, que .110 entrega rotos — investigado
# 2026-09-28). Imagen-cero en la frontera: los píxeles quedan en el detector; al Core solo cruzan
# `detectado` + `magnitud`. Separado por construcción: evento ≠ persona ≠ identidad ≠ intención.


@dataclass(frozen=True)
class EventoMovimiento:
    """Señal de que ALGO cambió entre frames. Deliberadamente NO dice quién/qué/por qué: sin persona, sin
    identidad, sin intención. Solo `detectado` + `magnitud` (metadato), gated y bajo demanda."""

    superficie: str
    detectado: bool
    trace_id: str
    magnitud: float | None = None
    tipo: str = "movimiento"
    timestamp: float = field(default_factory=_time.time)
    hubo_frame: bool = True  # False: no llegó imagen que comparar; NO equivale a «no hay movimiento»


@runtime_checkable
class DetectorDeMovimiento(Protocol):
    """Compara frames y devuelve (detectado, magnitud). Los píxeles NO salen de aquí."""

    nombre: str

    def detectar(self) -> tuple[bool, float | None]: ...


class PercepcionDeEventoBajoDemanda:
    """Consumidor BAJO DEMANDA de eventos: dado un `surface_id`, produce un `EventoMovimiento` si la política
    de procesamiento VISUAL autoriza esa superficie (mover es procesar vídeo). Sin bucle, sin vigilancia
    continua: solo `observar_evento()` procesa, y una vez.

    `fuentes`: {surface_id: (DetectorDeMovimiento, tipo_fuente)}.
    """

    def __init__(self, fuentes: dict, politica) -> None:
        self._fuentes = fuentes
        self._politica = politica

    def superficies(self) -> list[str]:
        return sorted(self._fuentes)

    def superficies_autorizadas(self) -> list[str]:
        """Las cámaras que la política deja procesar como VÍDEO. Solo informa; no procesa ningún fotograma."""
        if self._politica is None:
            return sorted(self._fuentes)
        return [s for s in sorted(self._fuentes) if self._politica.puede_procesar_visual(s)]

    def observar_evento(self, surface_id: str, trace_id: str) -> EventoMovimiento | None:
        entrada = self._fuentes.get(surface_id)
        if entrada is None:
            obs.log("PERC", "evento", f"superficie '{surface_id}' no registrada; no proceso", trace_id)
            return None
        # Gate ANTES de procesar el frame: superficie no autorizada -> no se toca la cámara.
        if self._politica is not None and not self._politica.puede_procesar_visual(surface_id):
            obs.log("PERC", "evento", f"superficie '{surface_id}' sin permiso visual; no proceso", trace_id, audit=True)
            return None
        detector, _tipo = entrada
        try:
            detectado, magnitud = detector.detectar()
        except Exception as e:
            obs.log("PERC", "evento", f"detector '{getattr(detector, 'nombre', '?')}' no disponible: {e}", trace_id)
            return EventoMovimiento(superficie=surface_id, detectado=False, trace_id=trace_id, hubo_frame=False)
        # El detector devuelve (False, None) cuando no pudo comparar dos fotogramas: tampoco hubo imagen.
        hubo_frame = bool(detectado) or magnitud is not None
        obs.log(
            "PERC",
            "evento",
            f"'{surface_id}' movimiento={'si' if detectado else 'no'} magnitud={magnitud}",
            trace_id,
            audit=True,
        )
        return EventoMovimiento(
            superficie=surface_id,
            detectado=bool(detectado),
            trace_id=trace_id,
            magnitud=magnitud,
            hubo_frame=hubo_frame,
        )


def describir_evento(ev: EventoMovimiento) -> str:
    """Texto honesto. Detectar movimiento NO es saber quién/qué: se dice explícitamente."""
    if not ev.detectado and not ev.hubo_frame:
        return f"No recibí imagen de «{ev.superficie}»; no sé si hay movimiento."
    if not ev.detectado:
        return f"No detecté movimiento en «{ev.superficie}» ahora mismo."
    return (
        f"Detecté movimiento en «{ev.superficie}». No sé quién ni qué lo causó: no identifico a nadie "
        f"ni infiero intención, solo que algo cambió entre fotogramas."
    )


def es_consulta_evento_sin_camara(texto: str) -> bool:
    """«¿Hay movimiento en la cámara?» SIN decir cuál. Frase cerrada: se pregunta cuál, no se procesa ninguna."""
    import re

    patron = r"(?:(?:oye )?aurora )?(?:hay movimiento|se mueve algo|detectas movimiento) en la camara"
    return re.fullmatch(patron, _normalizar(texto)) is not None


def es_consulta_evento(texto: str) -> str | None:
    """Reconoce «¿hay movimiento / se mueve algo en la cámara X?» y devuelve X, o None."""
    return _consulta_camara(texto, r"\b(?:hay movimiento|se mueve algo|se mueve|hay alguien|detectas movimiento)\b")
