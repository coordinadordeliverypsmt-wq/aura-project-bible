"""Bloque multimodal integrado en la conversación (acta CEO 2026-09-28): ESCUCHAR + EVENTO, además del
VER ya integrado. Bajo demanda, gated, sin persistencia, sin identidad. Reutiliza el orchestrator; las
demás superficies siguen intactas. Fuentes inyectadas (fakes): no toca hardware.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.percepcion import (
    AudioPCM,
    PercepcionAuditivaBajoDemanda,
    PercepcionDeEventoBajoDemanda,
)
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie


def _aura(tmp_path):
    sis = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))

    class _Espia:
        name = "espia"

        async def infer(self, *a, **k):
            return '{"intent":"x","action":"consulta","args":{},"say":"Entendido."}'

    sis.orquestador.router.providers = [_Espia()]
    return sis


async def _di(sis, texto):
    tid = uuid.uuid4().hex[:12]
    await sis.orquestador.handle_utterance("u", texto, tid)
    await sis.orquestador.wait(tid)
    return sis.orquestador._results[tid]


def _sup(sid, audio=True, visual=True):
    return Superficie(
        surface_id=sid,
        device_id="d",
        channel_id=None,
        zona="interior",
        proposito="p",
        autorizado=(audio or visual),
        visual_processing_allowed=visual,
        audio_processing_allowed=audio,
    )


class _FuenteAudio:
    nombre = "cam_mic"

    def capturar_audio(self):
        return AudioPCM(rate=16000, muestras=16000, duracion_s=1.0)

    def liberar(self):
        pass


class _Detector:
    nombre = "cam_mov"

    def __init__(self, detectado):
        self._d = detectado

    def detectar(self):
        return self._d, (0.5 if self._d else 0.0)


# ---------------------------------------------------------------------------------- ESCUCHAR --


@pytest.mark.asyncio
async def test_que_se_oye_transcribe_bajo_demanda(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_auditiva = PercepcionAuditivaBajoDemanda(
        fuentes={"sala": (_FuenteAudio(), "rtsp")},
        politica=RegistroDeSuperficies([_sup("sala")]),
        transcriptor=lambda pcm, tid: "hola casa",
    )
    r = await _di(sis, "¿qué se oye en la cámara sala?")
    assert "hola casa" in r["say"]
    assert r["dominio"] == "percepcion_auditiva"


@pytest.mark.asyncio
async def test_audio_NO_se_escribe_en_memoria(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_auditiva = PercepcionAuditivaBajoDemanda(
        fuentes={"sala": (_FuenteAudio(), "rtsp")},
        politica=RegistroDeSuperficies([_sup("sala")]),
        transcriptor=lambda pcm, tid: "secreto de familia",
    )
    await _di(sis, "¿qué se oye en la cámara sala?")
    r = await _di(sis, "¿qué te dije antes?")
    assert "secreto de familia" not in r["say"]


@pytest.mark.asyncio
async def test_audio_superficie_no_autorizada_no_escucha(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_auditiva = PercepcionAuditivaBajoDemanda(
        fuentes={"sala": (_FuenteAudio(), "rtsp")},
        politica=RegistroDeSuperficies([_sup("sala", audio=False, visual=False)]),
        transcriptor=lambda pcm, tid: "no deberia",
    )
    r = await _di(sis, "¿qué se oye en la cámara sala?")
    assert "no deberia" not in r["say"] and "no" in r["say"].lower()


# ------------------------------------------------------------------------------------ EVENTO --


@pytest.mark.asyncio
async def test_hay_movimiento_detecta(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_evento = PercepcionDeEventoBajoDemanda(
        fuentes={"sala": (_Detector(True), "rtsp")}, politica=RegistroDeSuperficies([_sup("sala")])
    )
    r = await _di(sis, "¿hay movimiento en la cámara sala?")
    assert "movimiento" in r["say"].lower()
    assert r["dominio"] == "percepcion_evento"


@pytest.mark.asyncio
async def test_colision_reconocedores_evento_gana_a_visual(tmp_path):
    """Regresión del bug de auditoría 2026-09-28: «hay movimiento» casa con el reconocedor visual («que
    hay») y con el de evento; EVENTO debe ganar (se evalúa antes), no quedar enmascarado por VISUAL."""
    from aura_skeleton.core.percepcion import es_consulta_evento, es_consulta_visual

    frase = "¿qué hay, hay movimiento en la cámara sala?"
    # ambos reconocedores casan (colisión real):
    assert es_consulta_visual(frase) == "sala" and es_consulta_evento(frase) == "sala"
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_evento = PercepcionDeEventoBajoDemanda(
        fuentes={"sala": (_Detector(True), "rtsp")}, politica=RegistroDeSuperficies([_sup("sala")])
    )
    r = await _di(sis, frase)
    assert r["dominio"] == "percepcion_evento", f"debía enrutar a EVENTO, no a {r['dominio']}"
    assert "movimiento" in r["say"].lower()


@pytest.mark.asyncio
async def test_evento_no_autorizado_no_procesa(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_evento = PercepcionDeEventoBajoDemanda(
        fuentes={"sala": (_Detector(True), "rtsp")},
        politica=RegistroDeSuperficies([_sup("sala", audio=False, visual=False)]),
    )
    r = await _di(sis, "¿hay movimiento en la cámara sala?")
    assert "no" in r["say"].lower()


# ------------------------------------------------------------------------------- COMPOSICIÓN --


def test_composicion_cablea_audio_y_evento(tmp_path):
    sis = _aura(tmp_path)
    assert isinstance(sis.orquestador.percepcion_auditiva, PercepcionAuditivaBajoDemanda)
    assert isinstance(sis.orquestador.percepcion_evento, PercepcionDeEventoBajoDemanda)


@pytest.mark.asyncio
async def test_sin_percepcion_no_desvia(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_auditiva = None
    sis.orquestador.percepcion_evento = None
    # cae al camino normal, no rompe ni desvía
    r = await _di(sis, "¿qué se oye en la cámara sala?")
    assert r["dominio"] != "percepcion_auditiva"
