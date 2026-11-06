"""UMBRAL DE INTEGRACIÓN EN UNA SOLA CONVERSACIÓN HABLADA (mapa maestro §14, opción C de `DP-VOZ-ACCION.md`).

PERSONA habla → AURA oye (activación) → recuerda lo declarado → entiende la orden → la ejecuta por el Motor
Único → el efecto se relee → recuerda el RESULTADO → responde. Hasta hoy cada tramo tenía su prueba, pero la
recuperación del resultado solo se probaba por TEXTO (`voz=False`).

EL HUECO, MEDIDO `[EJEC]` (2026-10-21, sonda con estos mismos dobles): tras apagar la TV por voz,
«¿apagaste la tele?» hablado respondía «He oído que hablas de la televisión, pero no entendí la orden…»: la
superficie de orden no entendida se tragaba una PREGUNTA por el resultado y AURA negaba saber lo que acababa
de hacer. «¿Qué hiciste?» por voz sí funcionaba, pero ninguna prueba lo cubría.

Todo con dobles: ni Home Assistant ni la TV reales.
"""

from __future__ import annotations

import os

import pytest

from aura_skeleton.core import hogar
from tests.integration.test_voz_accion_opcion_c import _HA, SALA, TV20, _aura, _di

_PROCEDENCIA = "no lo he vuelto a ejecutar"


@pytest.mark.asyncio
async def test_la_cadena_completa_cabe_en_UNA_conversacion_hablada(tmp_path):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)

    await _di(sis, "me llamo Mauricio")
    propuesta = await _di(sis, "apaga la tele")
    hecho = await _di(sis, "sí")
    que_hiciste = await _di(sis, "¿qué hiciste?")
    apagaste = await _di(sis, "¿apagaste la tele?")
    nombre = await _di(sis, "¿cómo me llamo?")

    assert "¿Lo hago?" in propuesta["say"]
    assert ha.estados[SALA]["state"] == "off" and "Home Assistant ve" in hecho["say"], hecho["say"]
    assert hecho["say"] in que_hiciste["say"] and _PROCEDENCIA in que_hiciste["say"], que_hiciste["say"]
    assert hecho["say"] in apagaste["say"] and _PROCEDENCIA in apagaste["say"], apagaste["say"]
    assert "Mauricio" in nombre["say"], nombre["say"]
    assert ha.servicios == 1, "recordar volvió a ejecutar la acción"
    assert ha.estados[TV20]["state"] == "on" and espia.llamadas == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pregunta",
    [
        "¿apagaste la tele?",
        "¿Aurora, ya apagaste la televisión?",
        "¿has apagado el televisor?",
        "¿encendiste la tv?",
        "¿has encendido la tele?",
        "¿prendiste la televisión?",
    ],
)
async def test_preguntar_por_voz_si_actuo_sobre_la_TV_recupera_lo_ocurrido_sin_reejecutar(tmp_path, pregunta):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    hecho = await _di(sis, "sí")

    r = await _di(sis, pregunta)

    assert hecho["say"] in r["say"] and _PROCEDENCIA in r["say"], r["say"]
    assert r["say"] != hogar.ORDEN_NO_ENTENDIDA and ha.servicios == 1


@pytest.mark.asyncio
async def test_preguntar_si_apago_la_tele_SIN_haber_actuado_no_afirma_nada_ni_toca_HA(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿apagaste la tele?")

    assert "no he ejecutado nada" in r["say"], r["say"]
    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"


@pytest.mark.asyncio
async def test_la_pregunta_por_el_resultado_no_exige_activacion_porque_no_actua(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    hecho = await _di(sis, "sí")

    r = await _di(sis, "¿apagaste la tele?", activado=False)

    assert hecho["say"] in r["say"] and ha.servicios == 1, r["say"]


@pytest.mark.asyncio
async def test_si_la_accion_NO_tuvo_efecto_preguntar_repite_el_fallo_y_no_la_da_por_hecha(tmp_path):
    ha = _HA(efecto=False)
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    fallo = await _di(sis, "sí")

    r = await _di(sis, "¿apagaste la tele?")

    assert "no cambió" in fallo["say"] and fallo["say"] in r["say"], r["say"]
    assert "comprobado" not in r["say"] and ha.estados[SALA]["state"] == "on"


@pytest.mark.asyncio
async def test_si_HA_cayo_al_enviar_preguntar_repite_que_no_se_dio_por_ejecutada(tmp_path):
    ha = _HA(servicio_cae=True)
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    fallo = await _di(sis, "sí")

    r = await _di(sis, "¿apagaste la tele?")

    assert "no la doy por ejecutada" in fallo["say"] and fallo["say"] in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_PARADA_la_pregunta_por_el_resultado_responde_y_sigue_sin_ejecutar(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    open(os.path.join(str(tmp_path), "KILL"), "w").close()
    detenida = await _di(sis, "sí")

    r = await _di(sis, "¿apagaste la tele?")

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
    assert detenida["say"] in r["say"] and "comprobado" not in r["say"], r["say"]


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["¿No fiende la televisión?", "la tele está rara"])
async def test_control_una_orden_mal_oida_sobre_la_TV_sigue_diciendo_que_no_se_entendio(tmp_path, frase):
    """Caso de control: la corrección no puede abrir la superficie de recuperación a cualquier frase con «tele»."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, frase)

    assert r["say"] == hogar.ORDEN_NO_ENTENDIDA and ha.servicios == 0


@pytest.mark.asyncio
async def test_si_lo_ultimo_ejecutado_NO_fue_la_TV_repite_eso_y_jamas_afirma_haber_tocado_la_TV(tmp_path):
    """Comportamiento FIJADO (revisión ECC 2026-10-21, MEDIO): la recuperación devuelve la ejecución más reciente,
    no «la que el usuario quiso decir» (`recuperacion.ultima_ejecucion`). Ante «¿apagaste la tele?» tras listar un
    directorio, AURA repite el listado con su procedencia; nunca dice que apagó la TV ni la toca."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    listado = await _di(sis, f"lista el directorio {tmp_path}", voz=False, activado=False)

    r = await _di(sis, "¿apagaste la tele?")

    assert listado["say"] in r["say"] and _PROCEDENCIA in r["say"], r["say"]
    assert "apagada" not in r["say"] and "comprobado" not in r["say"], r["say"]
    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
