"""«¿Qué oyes / hay movimiento en la cámara?» SIN decir cuál (acta 2026-10-22, simetría con la consulta visual).

Mismo hueco que `test_pregunta_por_camara_sin_nombre.py`, ahora para AUDIO y MOVIMIENTO: el Core pregunta cuál y
enumera SOLO las superficies autorizadas para ESA modalidad (audio o vídeo), sin capturar nada. La lista dice
«que puedo intentar», no «que puedo»: la política no comprueba la conexión. Además, una cámara que no da imagen NO
se confunde con «no hay movimiento». Todo con dobles: ninguna cámara real.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core import percepcion
from aura_skeleton.core.percepcion import (
    AudioPCM,
    EventoMovimiento,
    PercepcionAuditivaBajoDemanda,
    PercepcionBajoDemanda,
    PercepcionDeEventoBajoDemanda,
    describir_evento,
    pedir_camara,
)
from aura_skeleton.core.politica_superficie import RegistroDeSuperficies, Superficie
from tests.integration.test_observacion_en_conversacion import _aura, _di


def _sup(nombre, audio, visual):
    return Superficie(
        surface_id=nombre,
        device_id="d",
        channel_id=None,
        zona="interior",
        proposito="obs",
        autorizado=audio or visual,
        visual_processing_allowed=visual,
        audio_processing_allowed=audio,
    )


# sala: audio y vídeo · patio: SOLO vídeo · garaje: nada
_POLITICA = [_sup("sala", True, True), _sup("patio", False, True), _sup("garaje", False, False)]


class _FuenteAudio:
    nombre = "mic"

    def capturar_audio(self):
        return AudioPCM(rate=16000, muestras=16000, duracion_s=1.0)

    def liberar(self):
        pass


class _Detector:
    nombre = "det"

    def __init__(self, resultado=(False, 0.0), falla=False):
        self._resultado = resultado
        self._falla = falla

    def detectar(self):
        if self._falla:
            raise OSError("sin imagen")
        return self._resultado


class _AudioEspia(PercepcionAuditivaBajoDemanda):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.capturas: list[str] = []

    def observar_audio(self, surface_id, trace_id):
        self.capturas.append(surface_id)
        return super().observar_audio(surface_id, trace_id)


class _EventoEspia(PercepcionDeEventoBajoDemanda):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.capturas: list[str] = []

    def observar_evento(self, surface_id, trace_id):
        self.capturas.append(surface_id)
        return super().observar_evento(surface_id, trace_id)


def _audio(politica=None):
    return _AudioEspia(
        fuentes={n: (_FuenteAudio(), "rtsp") for n in ("sala", "patio", "garaje")},
        politica=RegistroDeSuperficies(_POLITICA if politica is None else politica),
    )


def _evento(detector=None, politica=None):
    return _EventoEspia(
        fuentes={n: (detector or _Detector(), "rtsp") for n in ("sala", "patio", "garaje")},
        politica=RegistroDeSuperficies(_POLITICA if politica is None else politica),
    )


# --------------------------------------------------------------------------------- reconocedores --


@pytest.mark.parametrize(
    "frase",
    ["¿qué oyes en la cámara?", "¿qué se escucha en la cámara?", "Aurora, ¿qué se oye en la cámara?"],
)
def test_reconoce_audio_sin_nombre(frase):
    assert percepcion.es_consulta_auditiva_sin_camara(frase)


@pytest.mark.parametrize("frase", ["¿qué oyes en la cámara sala?", "¿qué oyes?", "¿qué ves en la cámara?"])
def test_audio_sin_nombre_no_reconoce_otras_frases(frase):
    assert not percepcion.es_consulta_auditiva_sin_camara(frase)


@pytest.mark.parametrize("frase", ["¿hay movimiento en la cámara?", "Aurora, ¿se mueve algo en la cámara?"])
def test_reconoce_movimiento_sin_nombre(frase):
    assert percepcion.es_consulta_evento_sin_camara(frase)


@pytest.mark.parametrize("frase", ["¿hay movimiento en la cámara sala?", "¿hay movimiento?", "¿qué oyes en la cámara?"])
def test_movimiento_sin_nombre_no_reconoce_otras_frases(frase):
    assert not percepcion.es_consulta_evento_sin_camara(frase)


# ------------------------------------------------------------------------- superficies_autorizadas --


def test_autorizadas_de_audio_filtran_por_audio_y_de_evento_por_video():
    assert _audio().superficies_autorizadas() == ["sala"]
    assert _evento().superficies_autorizadas() == ["patio", "sala"]


def test_sin_politica_las_autorizadas_son_las_registradas():
    fa = {"local": (_FuenteAudio(), "local")}
    assert PercepcionAuditivaBajoDemanda(fuentes=fa, politica=None).superficies_autorizadas() == ["local"]
    fe = {"local": (_Detector(), "local")}
    assert PercepcionDeEventoBajoDemanda(fuentes=fe, politica=None).superficies_autorizadas() == ["local"]


# ---------------------------------------------------------------------------------- pedir_camara --


def test_la_lista_no_afirma_que_la_camara_este_accesible():
    for txt in (pedir_camara(["sala"]), pedir_camara(["sala"], verbo="escuchar", ejemplo="qué oyes")):
        assert "Puedo mirar" not in txt and "Puedo escuchar" not in txt, txt
        assert "intentar" in txt, txt


def test_pedir_camara_sin_autorizadas_dice_para_que_verbo():
    assert "ninguna cámara autorizada para escuchar" in pedir_camara([], verbo="escuchar", ejemplo="qué oyes")


# ----------------------------------------------------------------------------------- orquestador --


@pytest.mark.asyncio
async def test_audio_sin_nombre_enumera_solo_las_de_audio_y_no_captura(tmp_path):
    sis = _aura(tmp_path)
    pa = _audio()
    sis.orquestador.percepcion_auditiva = pa

    r = await _di(sis, "¿qué oyes en la cámara?")

    assert "«sala»" in r["say"] and "patio" not in r["say"] and "garaje" not in r["say"], r["say"]
    assert "escuchar" in r["say"] and r["dominio"] == "percepcion_auditiva"
    assert pa.capturas == [], "preguntar cuál no puede abrir ningún micrófono"


@pytest.mark.asyncio
async def test_movimiento_sin_nombre_enumera_solo_las_de_video_y_no_captura(tmp_path):
    sis = _aura(tmp_path)
    pe = _evento()
    sis.orquestador.percepcion_evento = pe

    r = await _di(sis, "¿hay movimiento en la cámara?")

    assert "«sala»" in r["say"] and "«patio»" in r["say"] and "garaje" not in r["say"], r["say"]
    assert r["dominio"] == "percepcion_evento" and pe.capturas == []


@pytest.mark.asyncio
async def test_camara_solo_de_video_no_aparece_al_preguntar_que_oyes(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_auditiva = _audio()
    sis.orquestador.percepcion_evento = _evento()

    oyes = await _di(sis, "¿qué oyes en la cámara?")
    mueve = await _di(sis, "¿hay movimiento en la cámara?")

    assert "patio" not in oyes["say"], oyes["say"]  # control: patio SÍ aparece para movimiento
    assert "patio" in mueve["say"], mueve["say"]


@pytest.mark.asyncio
async def test_sin_ninguna_autorizada_lo_dice(tmp_path):
    sis = _aura(tmp_path)
    nada = [_sup("garaje", False, False)]
    pa, pe = _audio(nada), _evento(politica=nada)
    sis.orquestador.percepcion_auditiva, sis.orquestador.percepcion_evento = pa, pe

    oyes = await _di(sis, "¿qué oyes en la cámara?")
    mueve = await _di(sis, "¿hay movimiento en la cámara?")

    assert "ninguna cámara autorizada para escuchar" in oyes["say"], oyes["say"]
    assert "ninguna cámara autorizada para vigilar" in mueve["say"], mueve["say"]
    assert pa.capturas == [] and pe.capturas == []


@pytest.mark.asyncio
async def test_control_las_frases_con_nombre_siguen_a_su_rama(tmp_path):
    sis = _aura(tmp_path)
    pa, pe = _audio(), _evento(_Detector((True, 0.5)))
    sis.orquestador.percepcion_auditiva, sis.orquestador.percepcion_evento = pa, pe

    await _di(sis, "¿qué oyes en la cámara sala?")
    mueve = await _di(sis, "¿hay movimiento en la cámara sala?")

    assert pa.capturas == ["sala"] and pe.capturas == ["sala"]
    assert "Detecté movimiento" in mueve["say"], mueve["say"]


@pytest.mark.asyncio
async def test_camara_sin_imagen_no_dice_que_no_hay_movimiento(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_evento = _evento(_Detector(falla=True))

    r = await _di(sis, "¿hay movimiento en la cámara sala?")

    assert "No detecté movimiento" not in r["say"], r["say"]
    assert "No recibí imagen de «sala»" in r["say"] and "no sé si hay movimiento" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_control_camara_con_imagen_y_sin_cambio_si_dice_que_no_detecto(tmp_path):
    sis = _aura(tmp_path)
    sis.orquestador.percepcion_evento = _evento(_Detector((False, 0.0)))

    r = await _di(sis, "¿hay movimiento en la cámara sala?")

    assert "No detecté movimiento en «sala»" in r["say"] and "No recibí imagen" not in r["say"], r["say"]


def test_describir_evento_distingue_sin_imagen():
    sin = EventoMovimiento(superficie="x", detectado=False, trace_id="T", hubo_frame=False)
    con = EventoMovimiento(superficie="x", detectado=False, trace_id="T")
    assert "No recibí imagen" in describir_evento(sin) and "No detecté" in describir_evento(con)


def test_visual_sigue_enumerando_autorizadas_con_el_texto_nuevo():
    class _F:
        nombre = "f"

    pv = PercepcionBajoDemanda(fuentes={"sala": (_F(), "local")}, politica=None)
    assert "sala" in pedir_camara(pv.superficies_autorizadas())
