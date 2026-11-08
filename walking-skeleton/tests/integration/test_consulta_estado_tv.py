"""«¿Está encendida la tele?», «¿a qué volumen está?», «¿qué está poniendo?» — leído de Home Assistant, sin el modelo.

Es una LECTURA: no pasa por el Motor ni cambia nada, y responde también con la PARADA echada (lo dice). El título de lo
que se ve no se escribe en el audit log ni se dice por voz (rastro del consumo de la familia; acta 2026-10-22).
Todo con dobles: ni Home Assistant ni la TV reales.
"""

from __future__ import annotations

import os
import time

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.core import hogar
from tests.integration.test_volumen_tv import SALA, TV20, _aura, _di, _HAVolumen


def _ha(**atributos):
    ha = _HAVolumen()
    ha.estados[SALA]["last_changed"] = "2026-10-22T02:05:00+00:00"
    ha.estados[SALA]["attributes"].update(atributos)
    return ha


@pytest.mark.asyncio
async def test_esta_encendida_la_tele_de_la_sala_se_lee_de_HA_sin_modelo_ni_acciones(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "America/Bogota")
    time.tzset()
    ha = _ha()
    sis, espia = _aura(tmp_path, ha)

    r = await _di(sis, "¿está encendida la tele de la sala?")

    assert r["say"].startswith("Sí: la TV de la sala está encendida") and "21:05" in r["say"], r["say"]
    assert ha.servicios == [] and espia.llamadas == 0
    monkeypatch.undo()
    time.tzset()


@pytest.mark.asyncio
async def test_a_que_volumen_esta_lee_el_volumen_actual(tmp_path):
    ha = _ha()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿a qué volumen está la tele de la sala?")

    assert "20" in r["say"] and "con sonido" in r["say"] and ha.servicios == [], r["say"]


@pytest.mark.asyncio
async def test_tras_subir_el_volumen_la_consulta_ve_el_valor_NUEVO(tmp_path):
    ha = _ha()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "sube el volumen de la tele de la sala")

    r = await _di(sis, "¿a qué volumen está la tele de la sala?")

    assert "21" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_que_esta_poniendo_dice_lo_expuesto_y_no_deja_el_titulo_en_el_audit(tmp_path):
    ha = _ha(source="HDMI 1", app_name="Netflix", media_title="Serie privada")
    sis, _ = _aura(tmp_path, ha)
    marca = len(obs.audit_records())

    r = await _di(sis, "¿qué está poniendo la tele de la sala?")

    assert "Netflix" in r["say"] and "Serie privada" in r["say"], r["say"]
    assert all("Serie privada" not in str(x) for x in obs.audit_records()[marca:]), "el título quedó en el audit log"


@pytest.mark.asyncio
async def test_por_voz_la_consulta_responde_pero_sin_el_titulo(tmp_path):
    ha = _ha(app_name="Netflix", media_title="Serie privada")
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿qué está poniendo la tele?", voz=True, activado=True)

    assert "Serie privada" not in r["say"] and r["say"] != hogar.ORDEN_NO_ENTENDIDA, r["say"]
    assert ha.servicios == []


@pytest.mark.asyncio
async def test_con_dos_TV_y_sin_decir_cual_pregunta_cual(tmp_path):
    ha = _ha()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿está encendida la tele?")

    assert "cuál" in r["say"] and "Sí:" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_la_PARADA_echada_la_lectura_responde_y_lo_dice(tmp_path):
    ha = _ha()
    sis, _ = _aura(tmp_path, ha)
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    r = await _di(sis, "¿está encendida la tele de la sala?")

    assert r["say"].startswith("Sí:") and "parada" in r["say"].lower() and ha.servicios == [], r["say"]


@pytest.mark.asyncio
async def test_con_HA_caido_no_inventa_el_estado(tmp_path):
    ha = _ha()
    ha.credencial_mala = False
    sis, _ = _aura(tmp_path, ha)

    def caido(*a, **k):
        raise ConnectionRefusedError("HA caído")

    sis.registro_adaptadores.para("encender_dispositivo")._http = caido

    r = await _di(sis, "¿está encendida la tele de la sala?")

    assert "Sí:" not in r["say"] and "No:" not in r["say"] and "Home Assistant" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_la_credencial_rechazada_lo_dice(tmp_path):
    ha = _ha()
    ha.credencial_mala = True
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿está encendida la tele de la sala?")

    assert "credencial" in r["say"] and "Sí:" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_control_la_otra_TV_no_se_mezcla(tmp_path):
    ha = _ha()
    ha.estados[SALA]["state"] = "off"
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿está encendida la tele de la sala?")

    assert r["say"].startswith("No: la TV de la sala está apagada"), r["say"]
    assert ha.estados[TV20]["state"] == "on"


@pytest.mark.asyncio
async def test_que_hay_en_la_nevera_no_consulta_home_assistant(tmp_path):
    """Control de C7: una pregunta que no es por la TV no lee el hogar ni responde como si lo fuera."""
    ha = _ha()
    lecturas = []
    sis, _ = _aura(tmp_path, ha)
    real = sis.registro_adaptadores.para("encender_dispositivo")
    original = real.estado_actual
    real.estado_actual = lambda d: lecturas.append(d) or original(d)

    r = await _di(sis, "¿qué hay en la nevera?")

    assert lecturas == [] and "según Home Assistant" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_esta_apagada_la_tele_con_la_TV_apagada_responde_SI(tmp_path):
    ha = _ha()
    ha.estados[SALA]["state"] = "off"
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "¿está apagada la tele de la sala?")

    assert r["say"].startswith("Sí: la TV de la sala está apagada"), r["say"]
