"""FRAME → OBSERVACIÓN integrada en la conversación (DP aprobado 2026-09-28, Alt B / bajo demanda / imagen-cero).

«AURA, ¿qué ves en la cámara sala?» → observación efímera (fuente+dimensiones), sin persona/identidad,
SIN escribir memoria, SIN emitir evento. Superficie no autorizada → no observa. Reutiliza el orchestrator
existente; las demás superficies siguen intactas.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.percepcion import Frame, PercepcionBajoDemanda
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie


class _Fuente:
    nombre = "cam_sala"

    def capturar(self):
        return Frame(ancho=1280, alto=720, fuente="cam_sala")

    def liberar(self):
        pass


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


def _percepcion(autorizado=True):
    return PercepcionBajoDemanda(
        fuentes={"sala": (_Fuente(), "local")},
        politica=RegistroDeSuperficies(
            [
                Superficie(
                    surface_id="sala",
                    device_id="d",
                    channel_id=None,
                    zona="interior",
                    proposito="obs",
                    autorizado=autorizado,
                    visual_processing_allowed=autorizado,
                )
            ]
        ),
    )


@pytest.mark.asyncio
async def test_que_ves_en_la_camara_devuelve_observacion_real(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = _percepcion()

    r = await _di(sis, "¿qué ves en la cámara sala?")

    assert "1280" in r["say"] and "720" in r["say"], r["say"]
    assert "no interpreto" in r["say"].lower() or "no identifico" in r["say"].lower()
    assert r["dominio"] == "percepcion_visual"


@pytest.mark.asyncio
async def test_la_observacion_NO_se_escribe_en_memoria(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = _percepcion()
    await _di(sis, "¿qué ves en la cámara sala?")

    # nada de la observación debe quedar como recuerdo del usuario
    r = await _di(sis, "¿qué te dije antes?")
    assert "1280" not in r["say"] and "cam_sala" not in r["say"]


@pytest.mark.asyncio
async def test_camara_no_autorizada_no_observa(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = _percepcion(autorizado=False)

    r = await _di(sis, "¿qué ves en la cámara sala?")
    assert "1280" not in r["say"]  # no capturó
    assert "no" in r["say"].lower()


@pytest.mark.asyncio
async def test_camara_desconocida_lo_dice_sin_inventar(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = _percepcion()

    r = await _di(sis, "¿qué ves en la cámara garaje?")
    assert "1280" not in r["say"]


@pytest.mark.asyncio
async def test_sin_percepcion_cableada_no_desvia(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = None  # guard None: la pregunta NO debe romper ni desviar
    r = await _di(sis, "¿qué ves en la cámara sala?")
    assert r["dominio"] != "percepcion_visual"


def test_la_composicion_cablea_la_percepcion_bajo_demanda(tmp_path):
    sis = _aura(tmp_path)
    from aura_skeleton.core.percepcion import PercepcionBajoDemanda

    assert isinstance(sis.orquestador.percepcion_visual, PercepcionBajoDemanda)
    assert "local" in sis.orquestador.percepcion_visual.superficies()


@pytest.mark.asyncio
async def test_la_observacion_visual_NO_llama_a_memory_write(tmp_path):
    """Efímera de verdad: el turno de percepción visual no debe escribir memoria (mutante OBS-M4)."""
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = _percepcion()
    escrituras = []
    orig = sis.orquestador.memory.write

    async def _spy(uid, kind, content, provenance):
        escrituras.append((kind, content))
        return await orig(uid, kind, content, provenance)

    sis.orquestador.memory.write = _spy
    await _di(sis, "¿qué ves en la cámara sala?")
    assert not any("frame" in c.lower() or "1280" in c for _k, c in escrituras), escrituras
