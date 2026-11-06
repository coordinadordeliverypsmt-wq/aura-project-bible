"""ESCUCHAR — percepción auditiva de cámara bajo demanda (bloque multimodal, aprobado CEO 2026-09-28).

Simetría con la percepción visual: AURA recibe AUDIO de una fuente de cámara SOLO cuando se le pide,
lo reduce a una observación (metadatos + transcripción opcional), SIN persistir el audio crudo, SIN
identidad, SIN escucha continua, gated por `politica_superficie` (flag de audio, deny-by-default).

El audio de la cámara se prueba con fuentes INYECTADAS (fakes), como la visual: no toca hardware.
"""

from __future__ import annotations

from aura_skeleton.core.percepcion import (
    AudioPCM,
    LecturaAuditiva,
    ObservacionAuditiva,
    PercepcionAuditivaBajoDemanda,
    describir_observacion_auditiva,
    es_consulta_auditiva,
    observacion_auditiva_de,
)
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie


def _sup(sid, audio=True):
    return Superficie(
        surface_id=sid,
        device_id="dev",
        channel_id=None,
        zona="interior",
        proposito="escucha",
        autorizado=audio,
        audio_processing_allowed=audio,
    )


class _FuenteAudio:
    nombre = "cam_mic"

    def __init__(self, pcm=None):
        self._pcm = pcm if pcm is not None else AudioPCM(rate=16000, muestras=16000, duracion_s=1.0)
        self.liberada = False

    def capturar_audio(self):
        return self._pcm

    def liberar(self):
        self.liberada = True


# --------------------------------------------------------------- contrato ObservacionAuditiva --


def test_observacion_auditiva_solo_metadatos_sin_persona_ni_identidad_ni_pcm():
    obs = observacion_auditiva_de(
        LecturaAuditiva(audio_recibido=True, fuente="cam_mic", duracion_s=1.0, transcripcion="hola"),
        superficie="s1",
        tipo_fuente="rtsp",
        trace_id="T",
    )
    assert isinstance(obs, ObservacionAuditiva)
    assert obs.superficie == "s1" and obs.fuente == "cam_mic" and obs.tipo_fuente == "rtsp"
    assert obs.audio_recibido is True and obs.duracion_s == 1.0 and obs.transcripcion == "hola"
    campos = set(ObservacionAuditiva.__dataclass_fields__)
    assert "pcm" not in campos and "audio" not in campos and "muestras_crudas" not in campos
    assert "persona" not in campos and "identidad" not in campos and "evento" not in campos


def test_sin_audio_la_observacion_lo_dice_y_no_inventa():
    obs = observacion_auditiva_de(
        LecturaAuditiva(audio_recibido=False, fuente="cam_mic"), superficie="s1", tipo_fuente="rtsp", trace_id="T"
    )
    assert obs.audio_recibido is False and obs.duracion_s is None and obs.transcripcion is None


# ------------------------------------------------ consumidor bajo demanda + política de audio --


def test_observar_audio_superficie_autorizada_devuelve_observacion():
    fuente = _FuenteAudio()

    def stt(pcm, tid):
        return "buenos dias"

    p = PercepcionAuditivaBajoDemanda(
        fuentes={"s1": (fuente, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1")]), transcriptor=stt
    )
    obs = p.observar_audio("s1", "T")
    assert obs is not None and obs.audio_recibido is True
    assert obs.transcripcion == "buenos dias"
    assert fuente.liberada


def test_observar_audio_superficie_NO_autorizada_no_captura():
    fuente = _FuenteAudio()
    p = PercepcionAuditivaBajoDemanda(
        fuentes={"s1": (fuente, "rtsp")},
        politica=RegistroDeSuperficies([_sup("s1", audio=False)]),
        transcriptor=lambda pcm, tid: "no deberia",
    )
    obs = p.observar_audio("s1", "T")
    assert obs is None, "superficie sin permiso de audio no produce observación"
    assert fuente.liberada is False  # no se tocó el micrófono


def test_observar_audio_superficie_desconocida_devuelve_None():
    p = PercepcionAuditivaBajoDemanda(fuentes={}, politica=RegistroDeSuperficies([]), transcriptor=lambda pcm, tid: "x")
    assert p.observar_audio("inexistente", "T") is None


def test_construir_no_captura_no_hay_escucha_continua():
    fuente = _FuenteAudio()
    PercepcionAuditivaBajoDemanda(
        fuentes={"s1": (fuente, "rtsp")},
        politica=RegistroDeSuperficies([_sup("s1")]),
        transcriptor=lambda pcm, tid: "x",
    )
    assert fuente.liberada is False  # construir NO captura; solo observar_audio() lo hace, una vez


def test_sin_audio_no_transcribe():
    # fuente devuelve None (sin audio) -> no debe llamar al STT ni inventar transcripción
    class _Vacia:
        nombre = "cam_mic"
        liberada = False

        def capturar_audio(self):
            return None

        def liberar(self):
            self.liberada = True

    llamado = []
    p = PercepcionAuditivaBajoDemanda(
        fuentes={"s1": (_Vacia(), "rtsp")},
        politica=RegistroDeSuperficies([_sup("s1")]),
        transcriptor=lambda pcm, tid: llamado.append(1) or "NO",
    )
    obs = p.observar_audio("s1", "T")
    assert obs is not None and obs.audio_recibido is False and obs.transcripcion is None
    assert not llamado, "sin audio no se debe invocar el STT"


# ------------------------------------------------------------------------- reconocedor + texto --


def test_reconocedor_exige_camara_y_nombre():
    assert es_consulta_auditiva("¿qué se oye en la cámara sala?") == "sala"
    assert es_consulta_auditiva("¿qué escuchas en la cámara cocina?") == "cocina"
    assert es_consulta_auditiva("¿qué ves en la cámara sala?") is None  # eso es visual, no auditivo
    assert es_consulta_auditiva("¿qué hora es?") is None


def test_describir_es_honesto_sin_identidad():
    obs = observacion_auditiva_de(
        LecturaAuditiva(audio_recibido=True, fuente="cam_mic", duracion_s=1.0, transcripcion="hola casa"),
        superficie="sala",
        tipo_fuente="rtsp",
        trace_id="T",
    )
    txt = describir_observacion_auditiva(obs)
    assert "hola casa" in txt
    assert "identifico a nadie" in txt.lower() or "no identifico" in txt.lower()


def test_describir_sin_audio_no_inventa():
    obs = observacion_auditiva_de(
        LecturaAuditiva(audio_recibido=False, fuente="cam_mic"), superficie="sala", tipo_fuente="rtsp", trace_id="T"
    )
    txt = describir_observacion_auditiva(obs)
    assert "no" in txt.lower() and "None" not in txt


def test_audio_no_transcrito_se_dice_sin_afirmar_contenido():
    # transcriptor None (no hay STT disponible): audio recibido pero sin interpretar
    fuente = _FuenteAudio()
    p = PercepcionAuditivaBajoDemanda(
        fuentes={"s1": (fuente, "rtsp")}, politica=RegistroDeSuperficies([_sup("s1")]), transcriptor=None
    )
    obs = p.observar_audio("s1", "T")
    assert obs is not None and obs.audio_recibido is True and obs.transcripcion is None
    txt = describir_observacion_auditiva(obs)
    assert "no" in txt.lower()  # honesto: recibí audio pero no lo interpreto
