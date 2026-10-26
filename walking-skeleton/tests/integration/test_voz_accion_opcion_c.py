"""VOZ -> ACCIÓN, opción C (CEO, 2026-10-04) — contrato `milestones/m3-entry/DP-VOZ-ACCION.md` §8.

La casa actúa por voz SOLO si se cumplen a la vez: (C1) la orden llegó tras la palabra de activación,
(C2) la entidad objetivo está en `voz_actua_en`, (C3) se resolvió dentro de esa llave y la propuesta la
nombró, (C4) el STT no dudó de lo que oyó, y la ejecución va por el Motor Único con el efecto releído.
Todo con dobles: ni Home Assistant ni la TV reales.
"""

from __future__ import annotations

import os
import uuid

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.adapters.home_assistant_real import HomeAssistantReal
from aura_skeleton.composicion import NOMBRE_HUMANO_DE_VOZ, VOZ_ACTUA_EN, Configuracion, componer
from aura_skeleton.core import hogar
from aura_skeleton.core.orchestrator import _redactar_efecto_de_hogar

SALA = "media_player.tv_sala_fmilia_medina_un43ru7100fxza"
TV20 = "media_player.samsung_6_series_55_un55ku6000"
CONGELADOR = "switch.congelador"

_AVISO_ACTIVACION = "Oye Aurora"


class _HA:
    """Doble de Home Assistant con DOS televisores (la sala y la .20) y un `switch` (no verde)."""

    def __init__(self, efecto=True, caido=False, servicio_cae=False):
        self.estados = {
            SALA: {"state": "on", "attributes": {"friendly_name": "Tv sala fmilia medina"}},
            TV20: {"state": "on", "attributes": {"friendly_name": "Samsung 6 Series 55 UN55KU6000"}},
            CONGELADOR: {"state": "on", "attributes": {"friendly_name": "Congelador"}},
        }
        self.efecto, self.caido, self.servicio_cae = efecto, caido, servicio_cae
        self.servicios = 0

    def __call__(self, metodo, url, cuerpo=None, token=""):
        if self.caido:
            raise ConnectionRefusedError("HA caído")
        if url.endswith("/api/states"):
            return [{"entity_id": e, **v} for e, v in self.estados.items()]
        if "/api/states/" in url:
            e = url.rsplit("/", 1)[1]
            return {"entity_id": e, **self.estados[e]}
        if "/api/services/" in url:
            if self.servicio_cae:
                raise ConnectionRefusedError("HA cayó al enviar")
            self.servicios += 1
            if self.efecto:
                self.estados[cuerpo["entity_id"]]["state"] = "on" if url.endswith("turn_on") else "off"
            return []
        return {"message": "API running."}


class _Espia:
    name = "espia"

    def __init__(self):
        self.llamadas = 0

    async def infer(self, prompt, *a, **k):
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"Entendido."}'


class _VozConConfianza:
    """Transcriptor de pruebas: «voz:…» se oye como el texto; expone `ultima_confianza` (contrato C4)."""

    def __init__(self, confianza=None):
        self.ultima_confianza = confianza

    async def stt(self, audio, tid):
        return audio[4:] if audio.startswith("voz:") else audio

    async def tts(self, texto, tid):
        return None


def _aura(tmp_path, ha=None):
    sis = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))
    if ha is not None:
        real = HomeAssistantReal(url="http://127.0.0.1:8123", token="t", http=ha, espera_s=0.05)
        for cap in real.capabilities:
            sis.registro_adaptadores._por_capacidad[cap] = real
    espia = _Espia()
    sis.orquestador.router.providers = [espia]
    return sis, espia


async def _di(sis, texto, *, voz=True, activado=True, confianza=None):
    sis.orquestador.voice = _VozConConfianza(confianza)
    tid = uuid.uuid4().hex[:12]
    entrada = f"voz:{texto}" if voz else texto
    await sis.orquestador.handle_utterance("u", entrada, tid, activado=activado)
    await sis.orquestador.wait(tid)
    return sis.orquestador._results[tid]


def _auditoria_desde(marca):
    return [r["msg"] for r in obs.audit_records()[marca:]]


# ----------------------------------------------------------------------------------- camino feliz --


@pytest.mark.asyncio
async def test_activada_la_orden_se_propone_nombrando_la_TV_y_el_si_activado_ejecuta_con_efecto_verificado(tmp_path):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)

    propuesta = await _di(sis, "apaga la tele")
    assert "la TV de la sala" in propuesta["say"] and "apagar" in propuesta["say"]
    assert ha.servicios == 0, "se actuó al proponer"

    r = await _di(sis, "sí")

    assert ha.estados[SALA]["state"] == "off" and ha.servicios == 1
    assert "Home Assistant ve" in r["say"] and "apagada" in r["say"], r["say"]
    assert ha.estados[TV20]["state"] == "on", "la voz tocó la TV .20"
    assert espia.llamadas == 0, "el modelo intervino"


@pytest.mark.asyncio
async def test_despues_de_actuar_por_voz_que_hiciste_lo_recupera_SIN_reejecutar(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    hecho = await _di(sis, "sí")

    r = await _di(sis, "¿qué hiciste?", voz=False, activado=False)

    assert hecho["say"] in r["say"], "no recuperó el resultado real"
    assert ha.servicios == 1, "recordar volvió a ejecutar la acción"


@pytest.mark.asyncio
async def test_encender_la_TV_de_la_sala_tambien_funciona_por_voz(tmp_path):
    ha = _HA()
    ha.estados[SALA]["state"] = "off"
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "enciende la televisión")

    r = await _di(sis, "vale")

    assert ha.estados[SALA]["state"] == "on" and "Home Assistant ve" in r["say"]


# ------------------------------------------------------------------------- C1: la activación --


@pytest.mark.asyncio
async def test_una_orden_hablada_SIN_activacion_no_propone_y_pide_llamar_por_el_nombre(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    marca = len(obs.audit_records())

    r = await _di(sis, "apaga la tele", activado=False)

    assert _AVISO_ACTIVACION in r["say"] and "¿Lo hago?" not in r["say"], r["say"]
    assert r["dominio"] == "hogar" and r["estatus"] == "abstencion", (r["dominio"], r["estatus"])
    assert any("sin activacion" in m or "sin activación" in m for m in _auditoria_desde(marca)), "no se auditó"
    # y un «sí» activado a continuación no tiene nada que ejecutar
    await _di(sis, "sí")
    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"


@pytest.mark.asyncio
async def test_un_si_hablado_SIN_activacion_no_ejecuta_y_consume_la_propuesta(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")  # propuesta legítima, activada

    r = await _di(sis, "sí", activado=False)

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
    assert _AVISO_ACTIVACION in r["say"], r["say"]
    # la propuesta se consumió: ni siquiera un «sí» activado posterior ejecuta
    await _di(sis, "sí")
    assert ha.servicios == 0, "el «sí» sin activación dejó la propuesta viva"


@pytest.mark.asyncio
async def test_por_TEXTO_la_orden_sigue_la_regla_M1_sin_activacion(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "apaga la tv sala fmilia medina", voz=False, activado=False)

    assert ha.estados[SALA]["state"] == "off" and "Home Assistant ve" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_activacion_duplicada_sin_orden_no_hace_nada(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    await _di(sis, "Oye Aurora")
    await _di(sis, "Oye Aurora")

    assert ha.servicios == 0 and sis.orquestador._propuestas_de_hogar == {}


# --------------------------------------------------------------- C2/C3: la llave por entidad --


@pytest.mark.asyncio
async def test_una_orden_sobre_la_TV_20_por_su_nombre_no_se_propone_ni_se_ejecuta(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "apaga la samsung 6 series 55 un55ku6000")
    assert "¿Lo hago?" not in r["say"] and "fuera" in r["say"].lower(), r["say"]
    r2 = await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[TV20]["state"] == "on" and ha.estados[SALA]["state"] == "on"
    assert "Home Assistant ve" not in r2["say"]


@pytest.mark.asyncio
async def test_la_tele_sin_nombre_resuelve_SOLO_dentro_de_la_llave_aunque_haya_dos_TV(tmp_path):
    """Sin llave, «la tele» con dos televisores es ambigua (el adaptador no elige). Con la llave, es la sala."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    propuesta = await _di(sis, "apaga la tele")
    assert "la TV de la sala" in propuesta["say"] and "UN55KU6000" not in propuesta["say"]


@pytest.mark.asyncio
async def test_una_entidad_fuera_de_la_llave_en_la_confirmacion_es_ABSTENCION_auditada(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    sis.orquestador.voz_actua_en = frozenset({TV20})  # la llave ya no incluye la sala
    marca = len(obs.audit_records())

    r = await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
    assert r["estatus"] == "abstencion" and "No lo he hecho" in r["say"], r
    assert any("DETENIDO" in m for m in _auditoria_desde(marca)), "no se auditó la detención"


@pytest.mark.asyncio
async def test_con_la_llave_vacia_ninguna_orden_hablada_se_propone(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    sis.orquestador.voz_actua_en = frozenset()

    r = await _di(sis, "apaga la tele")

    assert "¿Lo hago?" not in r["say"] and sis.orquestador._propuestas_de_hogar == {}
    assert ha.servicios == 0


@pytest.mark.asyncio
async def test_una_accion_no_verde_no_actua_ni_con_la_llave_ampliada(tmp_path):
    """El `switch` no está en la lista verde del hogar: ni siquiera metido en la llave actúa."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    sis.orquestador.voz_actua_en = frozenset({CONGELADOR})
    await _di(sis, "apaga el congelador")

    r = await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[CONGELADOR]["state"] == "on"
    assert "Home Assistant ve" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_el_hogar_SIMULADO_la_voz_no_afirma_ningun_efecto(tmp_path):
    sis, _ = _aura(tmp_path)  # sin HA: el doble
    await _di(sis, "apaga la tele")

    r = await _di(sis, "sí")

    assert "Home Assistant ve" not in r["say"], r["say"]


def test_la_llave_compuesta_es_la_constante_y_NO_incluye_la_TV_20(tmp_path):
    sis, _ = _aura(tmp_path)
    assert sis.orquestador.voz_actua_en == VOZ_ACTUA_EN == frozenset({SALA})
    assert TV20 not in sis.orquestador.voz_actua_en


def test_ninguna_variable_de_entorno_cambia_la_llave(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_VOZ_ACTUA_EN", TV20)
    monkeypatch.setenv("VOZ_ACTUA_EN", TV20)
    sis, _ = _aura(tmp_path)
    assert sis.orquestador.voz_actua_en == frozenset({SALA})


# ------------------------------------------------------------ ambigua, parada, fallos de HA --


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["apaga", "apaga la tele y la luz", "no apagues la tele", "¿está encendida la tele?"])
async def test_una_orden_ambigua_o_incompleta_no_ejecuta(tmp_path, frase):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    await _di(sis, frase)
    await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"


@pytest.mark.asyncio
async def test_con_PARADA_activa_el_si_no_ejecuta(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    r = await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
    assert "kill switch" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_HA_no_disponible_al_proponer_no_se_propone_ni_se_dice_hecho(tmp_path):
    ha = _HA(caido=True)
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "apaga la tele")
    r2 = await _di(sis, "sí")

    assert "¿Lo hago?" not in r["say"] and "no respond" in r["say"].lower(), r["say"]
    assert "Home Assistant ve" not in r2["say"] and ha.servicios == 0


@pytest.mark.asyncio
async def test_con_HA_caido_al_enviar_no_se_dice_hecho(tmp_path):
    ha = _HA(servicio_cae=True)
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")

    r = await _di(sis, "sí")

    assert "Home Assistant ve" not in r["say"] and "no la doy por ejecutada" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_una_accion_SIN_efecto_por_voz_no_se_da_por_hecha(tmp_path):
    ha = _HA(efecto=False)
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")

    r = await _di(sis, "sí")

    assert "no cambió" in r["say"] and "Home Assistant ve" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_la_orden_repetida_en_dos_turnos_ejecuta_UNA_vez_por_confirmacion(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    await _di(sis, "apaga la tele")  # reemplaza la propuesta, no la duplica

    await _di(sis, "sí")
    await _di(sis, "sí")  # ya no hay nada que confirmar

    assert ha.servicios == 1, ha.servicios


# ------------------------------------------------------------------------- C4: confianza STT --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confianza",
    [
        {"no_speech_prob": 0.16, "avg_logprob": -0.2},
        {"no_speech_prob": 0.99, "avg_logprob": -0.2},
        {"no_speech_prob": 0.1, "avg_logprob": -1.21},
        {"no_speech_prob": 0.1, "avg_logprob": -3.0},
    ],
)
async def test_una_orden_con_confianza_baja_pide_repetir_y_no_propone(tmp_path, confianza):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    r = await _di(sis, "apaga la tele", confianza=confianza)

    assert "repít" in r["say"].lower() and "¿Lo hago?" not in r["say"], r["say"]
    assert sis.orquestador._propuestas_de_hogar == {} and ha.servicios == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confianza",
    [{"no_speech_prob": 0.9, "avg_logprob": -0.1}, {"no_speech_prob": 0.0, "avg_logprob": -2.5}],
)
async def test_un_si_con_confianza_baja_no_ejecuta_y_pide_repetir(tmp_path, confianza):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")  # propuesta limpia (sin confianza medida)

    r = await _di(sis, "sí", confianza=confianza)

    assert ha.servicios == 0 and "repít" in r["say"].lower(), r["say"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confianza",
    [
        None,
        {"no_speech_prob": 0.05, "avg_logprob": -0.3},
        {"no_speech_prob": hogar.UMBRAL_NO_HABLA, "avg_logprob": hogar.UMBRAL_LOGPROB},  # el borde NO rechaza
        {},
    ],
)
async def test_con_confianza_suficiente_o_sin_medir_el_camino_sigue(tmp_path, confianza):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele", confianza=confianza)

    await _di(sis, "sí", confianza=confianza)

    assert ha.servicios == 1 and ha.estados[SALA]["state"] == "off"


def test_los_umbrales_medidos_estan_declarados():
    assert hogar.UMBRAL_NO_HABLA == 0.15 and hogar.UMBRAL_LOGPROB == -1.2  # medidos (C4)


@pytest.mark.asyncio
async def test_la_confianza_baja_NO_bloquea_un_no(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")

    r = await _di(sis, "no", confianza={"no_speech_prob": 0.9, "avg_logprob": -2.0})

    assert "no lo hago" in r["say"].lower() and ha.servicios == 0


@pytest.mark.asyncio
async def test_la_confianza_baja_no_afecta_al_texto_escrito(tmp_path):
    """Por teclado no hay STT: una cifra de un turno hablado anterior no puede bloquear una orden escrita."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)

    await _di(sis, "apaga la tv sala fmilia medina", voz=False, activado=False, confianza={"no_speech_prob": 0.99})

    assert ha.estados[SALA]["state"] == "off"


# -------------------------------------------------------------------------- Motor Único (C5) --


@pytest.mark.asyncio
async def test_la_ejecucion_por_voz_pasa_por_el_despachador_unico(tmp_path, monkeypatch):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    llamadas = []
    original = sis.orquestador._despachar_orden

    async def _espia(uid, capacidad, args, tid):
        llamadas.append((capacidad, args))
        return await original(uid, capacidad, args, tid)

    monkeypatch.setattr(sis.orquestador, "_despachar_orden", _espia)
    await _di(sis, "apaga la tele")

    await _di(sis, "sí")

    assert llamadas == [("apagar_dispositivo", {"device": SALA})], llamadas


# ------------------------------------------------------------------------ resolución pura --


def test_la_resolucion_dentro_de_la_llave_no_ve_la_TV_20():
    ha = _HA()
    real = HomeAssistantReal(url="http://x", token="t", http=ha, espera_s=0.05)

    assert real.resolver_dispositivo("la tele", dentro_de=frozenset({SALA})) == (SALA, "Tv sala fmilia medina")
    with pytest.raises(Exception, match="no existe"):
        real.resolver_dispositivo("samsung 6 series 55 un55ku6000", dentro_de=frozenset({SALA}))


# ------------------------------------------------------- lenguaje humano (CEO 2026-10-04) --

_TECNICOS = ("media_player", "UN43RU7100", "Tv sala fmilia medina", "fmilia")


def test_el_nombre_humano_cubre_EXACTAMENTE_las_mismas_claves_que_la_llave_de_voz():
    assert set(NOMBRE_HUMANO_DE_VOZ) == set(VOZ_ACTUA_EN)
    assert NOMBRE_HUMANO_DE_VOZ[SALA] == "la TV de la sala"


def test_el_nombre_humano_se_cablea_en_la_composicion(tmp_path):
    sis, _ = _aura(tmp_path)
    assert sis.orquestador.nombres_de_voz == NOMBRE_HUMANO_DE_VOZ


@pytest.mark.asyncio
async def test_la_propuesta_por_voz_habla_en_humano_y_no_filtra_nombres_tecnicos(tmp_path):
    sis, _ = _aura(tmp_path, _HA())

    p = await _di(sis, "enciende la tele")

    assert p["say"] == "Voy a encender la TV de la sala. ¿Lo hago?", p["say"]
    assert not any(t in p["say"] for t in _TECNICOS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("orden", "estado_final", "palabra"), [("enciende la tele", "on", "encendida"), ("apaga la tele", "off", "apagada")]
)
async def test_tras_el_si_el_resultado_es_breve_humano_y_HA_recibe_el_entity_id_EXACTO(
    tmp_path, orden, estado_final, palabra
):
    ha = _HA()
    ha.estados[SALA]["state"] = "off" if estado_final == "on" else "on"
    llamadas = []
    original = ha.__call__

    def espia(metodo, url, cuerpo=None, token=""):
        if "/api/services/" in url:
            llamadas.append(cuerpo)
        return original(metodo, url, cuerpo, token)

    sis, _ = _aura(tmp_path, espia)
    sis.registro_adaptadores.para("encender_dispositivo")  # el adaptador existe
    await _di(sis, orden)

    r = await _di(sis, "sí")

    assert r["say"] == f"Listo: Home Assistant ve la TV de la sala {palabra}.", r["say"]
    assert not any(t in r["say"] for t in _TECNICOS)
    assert llamadas == [{"entity_id": SALA}], llamadas
    assert ha.estados[SALA]["state"] == estado_final


@pytest.mark.asyncio
async def test_sin_efecto_el_texto_usa_el_nombre_humano_y_no_el_entity_id(tmp_path):
    sis, _ = _aura(tmp_path, _HA(efecto=False))
    await _di(sis, "apaga la tele")

    r = await _di(sis, "sí")

    assert "la TV de la sala" in r["say"] and "no cambió" in r["say"], r["say"]
    assert not any(t in r["say"] for t in _TECNICOS)


def test_el_redactor_con_nombre_humano_cubre_los_tres_casos_sin_el_entity_id():
    nombres = {SALA: "la TV de la sala"}
    casos = [
        {"device": SALA, "verificado": True, "estado_despues": "on"},
        {"device": SALA, "status": "sin_efecto", "estado_antes": "off", "estado_despues": "off"},
        {"device": SALA, "status": "ok"},  # el doble: sin confirmación posible
    ]
    textos = [_redactar_efecto_de_hogar("encender_dispositivo", c, nombres) for c in casos]
    assert all("la TV de la sala" in t and "media_player" not in t for t in textos), textos
    assert "simulado" in textos[2] and "no cambió" in textos[1] and "Home Assistant ve" in textos[0]
    # control: sin nombre humano se dice como siempre
    assert SALA in _redactar_efecto_de_hogar("encender_dispositivo", casos[0], {})


@pytest.mark.asyncio
async def test_con_HA_caido_al_enviar_el_error_no_filtra_el_entity_id(tmp_path):
    sis, _ = _aura(tmp_path, _HA(servicio_cae=True))
    await _di(sis, "apaga la tele")

    r = await _di(sis, "sí")

    assert "media_player" not in r["say"] and "Home Assistant ve" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_que_hiciste_recupera_el_texto_humano_sin_reejecutar(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di(sis, "apaga la tele")
    await _di(sis, "sí")

    r = await _di(sis, "¿qué hiciste?", voz=False, activado=False)

    assert "la TV de la sala" in r["say"] and "apagada" in r["say"], r["say"]
    assert "media_player" not in r["say"] and ha.servicios == 1


@pytest.mark.asyncio
async def test_sin_nombre_humano_se_usa_el_friendly_name_de_siempre(tmp_path):
    sis, _ = _aura(tmp_path, _HA())
    sis.orquestador.nombres_de_voz = {}

    p = await _di(sis, "apaga la tele")

    assert "Tv sala fmilia medina" in p["say"] and "la TV de la sala" not in p["say"], p["say"]


@pytest.mark.asyncio
async def test_la_llave_cerrada_en_la_confirmacion_tambien_habla_en_humano(tmp_path):
    sis, _ = _aura(tmp_path, _HA())
    await _di(sis, "apaga la tele")
    sis.orquestador.voz_actua_en = frozenset({TV20})

    r = await _di(sis, "sí")

    assert "la TV de la sala" in r["say"] and "media_player" not in r["say"], r["say"]
    assert "No lo he hecho" in r["say"]


# ------------------------------------------------- robustez del cierre de latencia (2026-10-04) --
# Huecos señalados por la auditoría independiente del bloque: casos sin prueba propia en el camino hablado.


@pytest.mark.asyncio
async def test_un_si_hablado_sin_ninguna_propuesta_pendiente_no_actua(tmp_path):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)

    r = await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
    assert "Home Assistant ve" not in r["say"] and "Listo" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_si_la_TV_de_la_llave_NO_existe_en_HA_no_se_propone_ni_se_actua(tmp_path):
    ha = _HA()
    del ha.estados[SALA]
    sis, _ = _aura(tmp_path, ha)

    propuesta = await _di(sis, "apaga la tele")
    r = await _di(sis, "sí")

    assert ha.servicios == 0, "se actuó sobre un dispositivo inexistente"
    assert "¿Lo hago?" not in propuesta["say"], propuesta["say"]
    assert "Home Assistant ve" not in r["say"], r["say"]
    assert ha.estados[TV20]["state"] == "on", "cayó sobre la TV .20"


@pytest.mark.asyncio
async def test_una_TV_unavailable_en_HA_nunca_se_da_por_encendida(tmp_path):
    ha = _HA(efecto=False)
    ha.estados[SALA]["state"] = "unavailable"
    sis, _ = _aura(tmp_path, ha)

    await _di(sis, "enciende la tele")
    r = await _di(sis, "sí")

    assert ha.estados[SALA]["state"] == "unavailable"
    assert "Home Assistant ve" not in r["say"] and "está encendida" not in r["say"], r["say"]
    assert SALA not in r["say"], "el entity_id llegó a la persona"


@pytest.mark.asyncio
async def test_con_PARADA_armada_ANTES_de_la_orden_hablada_nada_se_ejecuta(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    await _di(sis, "apaga la tele")
    r = await _di(sis, "sí")

    assert ha.servicios == 0 and ha.estados[SALA]["state"] == "on"
    assert "Home Assistant ve" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_un_turno_hablado_vacio_no_toca_home_assistant_ni_el_modelo(tmp_path):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)

    await _di(sis, "")

    assert ha.servicios == 0 and espia.llamadas == 0


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        ("playing", "encendida (reproduciendo)"),
        ("paused", "encendida (en pausa)"),
        ("idle", "encendida (en reposo)"),
        ("standby", "apagada (en espera)"),
        ("on", "encendida"),
        ("off", "apagada"),
    ],
)
def test_el_redactor_nombra_la_fuente_y_el_estado_concreto_sin_afirmar_efecto_fisico(estado, esperado):
    t = _redactar_efecto_de_hogar(
        "encender_dispositivo",
        {"device": SALA, "verificado": True, "estado_despues": estado},
        {SALA: "la TV de la sala"},
    )
    assert t == f"Listo: Home Assistant ve la TV de la sala {esperado}.", t
    assert "comprobado" not in t


def test_el_redactor_sin_nombre_humano_tambien_nombra_la_fuente():
    t = _redactar_efecto_de_hogar(
        "apagar_dispositivo",
        {"device": SALA, "verificado": True, "estado_antes": "on", "estado_despues": "standby"},
        {},
    )
    assert "Home Assistant ve" in t and "comprobado" not in t, t


@pytest.mark.parametrize(
    ("detalle", "contiene"),
    [
        ({"estado_antes": "off", "estado_despues": "off"}, "Home Assistant sigue viendo la TV de la sala apagada"),
        (
            {"estado_antes": "off", "estado_despues": "standby"},
            "Home Assistant ve la TV de la sala apagada (en espera), no el estado pedido",
        ),
        (
            {"estado_antes": "off", "estado_despues": "?", "evidencia": "ninguna"},
            "no pude leer el estado en Home Assistant",
        ),
    ],
)
def test_sin_efecto_nombra_la_fuente_y_nunca_afirma_efecto_fisico(detalle, contiene):
    t = _redactar_efecto_de_hogar(
        "encender_dispositivo", {"device": SALA, "status": "sin_efecto", **detalle}, {SALA: "la TV de la sala"}
    )
    assert contiene in t and "No lo doy por hecho" in t and "Listo" not in t, t


@pytest.mark.parametrize(
    ("antes", "despues", "frase"),
    [
        (
            "playing",
            "playing",
            "Home Assistant ya veía la TV de la sala encendida (reproduciendo) y la sigue viendo así; no ha cambiado nada.",
        ),
        (
            "idle",
            "playing",
            "Home Assistant ya veía la TV de la sala encendida (en reposo) y ahora la ve encendida (reproduciendo); no ha cambiado nada.",
        ),
    ],
)
def test_el_redactor_dice_ya_veia_cuando_antes_ya_estaba_en_el_conjunto_pedido(antes, despues, frase):
    d = {
        "device": SALA,
        "status": "sin_efecto",
        "verificado": False,
        "ya_en_estado": True,
        "estado_antes": antes,
        "estado_despues": despues,
    }
    assert _redactar_efecto_de_hogar("encender_dispositivo", d, {SALA: "la TV de la sala"}) == frase
    assert "Home Assistant ya veía" in _redactar_efecto_de_hogar("encender_dispositivo", d, {})


def test_no_el_estado_pedido_se_reserva_para_cuando_despues_no_esta_en_el_conjunto():
    d = {"device": SALA, "status": "sin_efecto", "estado_antes": "off", "estado_despues": "buffering"}
    assert "no el estado pedido" in _redactar_efecto_de_hogar("encender_dispositivo", d, {SALA: "la TV de la sala"})


def test_el_redactor_de_volumen_dice_ya_veia_y_no_comprobado():
    from aura_skeleton.core.orchestrator import _redactar_efecto_de_volumen

    d = {
        "device": SALA,
        "status": "sin_efecto",
        "verificado": False,
        "ya_en_estado": True,
        "atributo": "is_volume_muted",
        "valor_antes": False,
        "valor_despues": False,
    }
    t = _redactar_efecto_de_volumen("quitar_silencio", d, {SALA: "la TV de la sala"})
    assert t == "Home Assistant ya veía la TV de la sala con sonido y la sigue viendo así; no he cambiado nada.", t
