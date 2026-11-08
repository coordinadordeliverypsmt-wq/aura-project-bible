"""Por VOZ, el MODELO nunca ejecuta una acción de hogar (opción C de `DP-VOZ-ACCION.md` §8, C1-C3).

EL AGUJERO, MEDIDO `[EJEC]` (2026-10-22, sonda con dobles; revisión de seguridad del incremento de volumen): una frase
HABLADA sin palabra de activación (pulsar-para-hablar) que la gramática del Core no reconocía —«por favor ya apaga la tv
sala fmilia medina»— bajaba al modelo; el modelo proponía `apagar_dispositivo`, la guarda solo comprobaba que la persona
hubiera nombrado el dispositivo, y el Motor Único APAGABA la TV: sin activación, sin propuesta, sin «sí» y sin la llave
`voz_actua_en`. Anterior al volumen; el volumen lo heredaba. La opción C se aplicaba solo en la rama determinista.

Lo que la voz puede hacer en casa sigue siendo exactamente lo de la opción C, por el único camino que la cumple: el Core
reconoce, propone nombrando el dispositivo y espera el «sí» activado. Todo con dobles.
"""

from __future__ import annotations

import json

import pytest

from aura_skeleton.core import hogar
from tests.integration.test_volumen_tv import SALA, _aura, _di, _HAVolumen


class _ModeloQueActua:
    name = "modelo-que-actua"

    def __init__(self, accion):
        self.accion = accion

    async def infer(self, prompt, *a, **k):
        return json.dumps(
            {"intent": "x", "action": self.accion, "args": {"device": "Tv sala fmilia medina"}, "say": "Hecho."}
        )


_FRASES = {
    "apagar_dispositivo": "por favor ya apaga la tv sala fmilia medina",
    "subir_volumen": "oye pon el volumen de la tv sala fmilia medina mas alto",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("accion", sorted(_FRASES))
@pytest.mark.parametrize("activado", [False, True])
async def test_por_voz_una_accion_de_hogar_propuesta_por_el_modelo_no_se_ejecuta(tmp_path, accion, activado):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)
    sis.orquestador.router.providers = [_ModeloQueActua(accion)]

    r = await _di(sis, _FRASES[accion], voz=True, activado=activado)

    assert ha.servicios == [] and ha.estados[SALA]["state"] == "on", (ha.servicios, r["say"])
    assert "comprobado" not in r["say"] and "Hecho." not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_por_voz_el_rechazo_del_modelo_dice_como_pedirlo_por_el_camino_valido(tmp_path):
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)
    sis.orquestador.router.providers = [_ModeloQueActua("apagar_dispositivo")]

    r = await _di(sis, _FRASES["apagar_dispositivo"], voz=True, activado=False)

    assert r["say"] == hogar.ORDEN_NO_ENTENDIDA, r["say"]


@pytest.mark.asyncio
async def test_control_por_TEXTO_el_mismo_camino_del_modelo_sigue_actuando_con_efecto_verificado(tmp_path):
    """Caso de control: la guarda es de la VOZ. Por texto rige M1 (lista verde ejecuta) y el resultado se verifica."""
    ha = _HAVolumen()
    sis, _ = _aura(tmp_path, ha)
    sis.orquestador.router.providers = [_ModeloQueActua("apagar_dispositivo")]

    r = await _di(sis, _FRASES["apagar_dispositivo"])

    assert ha.servicios == ["turn_off"] and ha.estados[SALA]["state"] == "off", r["say"]
    assert "Home Assistant ve" in r["say"] and "apagada" in r["say"], r["say"]  # veredicto veraz (antes: «comprobado»)
