"""«¿Qué ves en la cámara?» SIN decir cuál (decisión A, acta 2026-09-27; DP de percepción multimodal).

EL HUECO, MEDIDO `[EJEC]` (2026-10-22, composición real con un modelo que intentaba inventarse una escena): sin
nombre, la pregunta no la reconocía la superficie visual y caía en la pared de memoria: «No tengo ningún recuerdo
registrado sobre eso». No fabricaba nada (el modelo no llegó a usarse), pero hablaba de RECUERDOS ante una pregunta
por una CÁMARA. Ahora el Core pregunta cuál y dice cuáles puede mirar —solo las AUTORIZADAS por la política—, sin
capturar ningún fotograma. Todo con dobles: ninguna cámara real.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core import percepcion
from aura_skeleton.core.percepcion import PercepcionBajoDemanda
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie
from tests.integration.test_observacion_en_conversacion import _aura, _di, _Fuente


def _sup(nombre, autorizado):
    return Superficie(
        surface_id=nombre,
        device_id="d",
        channel_id=None,
        zona="interior",
        proposito="obs",
        autorizado=autorizado,
        visual_processing_allowed=autorizado,
    )


class _Espia(PercepcionBajoDemanda):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.capturas: list[str] = []

    def observar(self, surface_id, trace_id):
        self.capturas.append(surface_id)
        return super().observar(surface_id, trace_id)


def _percepcion():
    return _Espia(
        fuentes={"sala": (_Fuente(), "local"), "garaje": (_Fuente(), "rtsp")},
        politica=RegistroDeSuperficies([_sup("sala", True), _sup("garaje", False)]),
    )


@pytest.mark.parametrize(
    "frase", ["¿qué ves en la cámara?", "Aurora, ¿qué hay en la cámara?", "¿qué se ve en la cámara?"]
)
def test_reconoce_la_pregunta_sin_nombre_de_camara(frase):
    assert percepcion.es_consulta_visual_sin_camara(frase)


@pytest.mark.parametrize(
    "frase", ["¿qué ves en la cámara sala?", "¿qué hay en la nevera?", "la cámara está rota", "¿qué ves?"]
)
def test_no_reconoce_otras_frases(frase):
    assert not percepcion.es_consulta_visual_sin_camara(frase)


@pytest.mark.asyncio
async def test_sin_nombre_pregunta_cual_y_enumera_SOLO_las_autorizadas_sin_capturar(tmp_path):
    sis = _aura(tmp_path)
    pv = _percepcion()
    sis.orquestador.percepcion_visual = pv

    r = await _di(sis, "¿qué ves en la cámara?")

    assert "sala" in r["say"] and "garaje" not in r["say"] and "recuerdo" not in r["say"], r["say"]
    assert pv.capturas == [], "preguntar cuál no puede capturar ningún fotograma"


@pytest.mark.asyncio
async def test_sin_ninguna_camara_autorizada_lo_dice(tmp_path):
    sis = _aura(tmp_path)
    pv = _Espia(fuentes={"garaje": (_Fuente(), "rtsp")}, politica=RegistroDeSuperficies([_sup("garaje", False)]))
    sis.orquestador.percepcion_visual = pv

    r = await _di(sis, "¿qué ves en la cámara?")

    assert "ninguna cámara" in r["say"] and pv.capturas == [], r["say"]


@pytest.mark.asyncio
async def test_una_camara_que_no_puedo_mirar_dice_cuales_si(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_visual = _percepcion()

    r = await _di(sis, "¿qué ves en la cámara cocina?")

    assert "No puedo mirar «cocina»" in r["say"] and "sala" in r["say"] and "garaje" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_control_con_nombre_autorizado_sigue_observando(tmp_path):
    sis = _aura(tmp_path)
    pv = _percepcion()
    sis.orquestador.percepcion_visual = pv

    r = await _di(sis, "¿qué ves en la cámara sala?")

    assert pv.capturas == ["sala"] and "1280" in r["say"], r["say"]


def test_sin_politica_las_autorizadas_son_las_registradas_como_en_observar():
    """code-reviewer 2026-10-22: `observar` admite política None (la cámara local); enumerar no puede reventar."""
    pv = PercepcionBajoDemanda(fuentes={"local": (_Fuente(), "local")}, politica=None)
    assert pv.superficies_autorizadas() == ["local"]
