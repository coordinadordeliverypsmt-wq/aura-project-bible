"""Voz → acción con las transcripciones REALES del E2E físico (2026-10-04) — dónde se rompía la cadena.

Diagnóstico [EJEC]: tras «Oye Aurora» (activación OK) la orden «enciende la televisión» de una persona llegó al Core
como lo que Whisper escribió. Cuando el verbo o el aparato salían deformados, `hogar.reconocer` no la reconocía, el
turno seguía la cascada y —como Whisper la puntuó como PREGUNTA— terminaba en la puerta de memoria de ADR-0014:
«No tengo ningun recuerdo registrado sobre eso». La puerta hacía bien su trabajo; el defecto era que una orden
fallida para la TV se respondiera como una consulta de recuerdos, sin decirle a la persona qué había pasado.

Estas pruebas recorren el orquestador real (Core + llave + Motor Único con HA doble) con el texto EXACTO medido.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core import hogar
from tests.integration.test_voz_accion_opcion_c import _HA, SALA, _aura, _di

#: (momento del E2E, transcripción real registrada por el arnés con --telemetria)
RECONOCIDAS = [
    ("S2 20:02:44", "¿Enciende la televisión?"),
    ("S3 20:15:54", "¿Enciente la televisión?"),  # variante observada, añadida a los verbos del Core
]
ORDEN_TV_NO_ENTENDIDA = [
    ("S4 20:19:06", "¿No fiende la televisión?"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("cuando,texto", RECONOCIDAS)
async def test_las_transcripciones_reales_reconocibles_llegan_a_PROPUESTA(tmp_path, cuando, texto):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)
    r = await _di(sis, texto)
    assert "la TV de la sala" in r["say"] and "encender" in r["say"], f"{cuando}: {r['say']}"
    assert ha.servicios == 0, "proponer no actúa"
    assert espia.llamadas == 0, "el modelo no interviene en una orden de hogar"


@pytest.mark.asyncio
@pytest.mark.parametrize("cuando,texto", ORDEN_TV_NO_ENTENDIDA)
async def test_una_orden_para_la_TV_mal_transcrita_NO_cae_en_la_memoria_y_lo_dice(tmp_path, cuando, texto):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)
    r = await _di(sis, texto)
    assert "recuerdo" not in r["say"].lower(), f"{cuando}: una orden fallida se contestó como memoria: {r['say']}"
    assert r["say"] == hogar.ORDEN_NO_ENTENDIDA
    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on", "no se actúa sobre lo no entendido"
    assert espia.llamadas == 0, "tampoco se le pasa al modelo"


@pytest.mark.asyncio
async def test_sin_activacion_la_orden_mal_transcrita_tampoco_hace_nada(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    r = await _di(sis, "¿No fiende la televisión?", activado=False)
    assert ha.servicios == 0
    assert r["say"] != hogar.ORDEN_NO_ENTENDIDA, "sin activación no se trata como orden de voz"


@pytest.mark.asyncio
async def test_una_pregunta_de_memoria_que_no_habla_de_la_TV_sigue_en_la_puerta_de_ADR_0014(tmp_path):
    """Control: el arreglo no puede robarle preguntas a la puerta de memoria."""
    sis, _ = _aura(tmp_path, _HA())
    r = await _di(sis, "¿qué marca de teléfono tengo?")
    assert "recuerdo" in r["say"].lower()


def test_el_detector_de_orden_de_TV_es_cerrado():
    assert hogar.menciona_tv_sin_orden("¿No fiende la televisión?")
    assert hogar.menciona_tv_sin_orden("¿apagas la tele?")
    assert not hogar.menciona_tv_sin_orden("¿Enciende la televisión?"), "lo reconocible va por el camino normal"
    assert not hogar.menciona_tv_sin_orden("¿qué hora es?")
    assert not hogar.menciona_tv_sin_orden("¿qué marca de teléfono tengo?"), "«teléfono» no es la tele"
