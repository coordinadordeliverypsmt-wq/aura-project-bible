"""El umbral de integración, en conversación real: oír -> proponer -> confirmar -> actuar -> verificar ->
recordar el resultado (semana 2, 2026-09-27).

Todo por el camino gobernado: la orden la reconoce el Core (nunca el modelo), se ejecuta solo tras un
«sí», pasa por el Motor Único (permisos, kill switch, auditoría) y el adaptador de Home Assistant relee
el estado para CONFIRMAR el efecto. Lo que AURA cuenta es lo que el dispositivo hizo.
"""

from __future__ import annotations

import os
import uuid

import pytest

from aura_skeleton.adapters.home_assistant_real import HomeAssistantReal
from aura_skeleton.composicion import VOZ_ACTUA_EN, Configuracion, componer

#: La TV de la sala: la ÚNICA entidad que la voz puede accionar (DP-VOZ-ACCION §8, opción C).
_SALA = "media_player.tv_sala_fmilia_medina_un43ru7100fxza"


class _HA:
    def __init__(self, efecto=True):
        self.estados = {_SALA: {"state": "on", "attributes": {"friendly_name": "Tv sala fmilia medina"}}}
        self.efecto = efecto
        self.servicios = 0

    def __call__(self, metodo, url, cuerpo=None, token=""):
        if url.endswith("/api/states"):
            return [{"entity_id": e, **v} for e, v in self.estados.items()]
        if "/api/states/" in url:
            e = url.rsplit("/", 1)[1]
            return {"entity_id": e, **self.estados[e]}
        if "/api/services/" in url:
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


def _aura(tmp_path, ha=None):
    sis = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))
    if ha is not None:
        real = HomeAssistantReal(url="http://127.0.0.1:8123", token="t", http=ha, espera_s=0.05)
        for cap in real.capabilities:
            sis.registro_adaptadores._por_capacidad[cap] = real
    espia = _Espia()
    sis.orquestador.router.providers = [espia]
    return sis, espia


async def _di(sis, texto, activado=False):
    tid = uuid.uuid4().hex[:12]
    await sis.orquestador.handle_utterance("u", texto, tid, activado=activado)
    await sis.orquestador.wait(tid)
    return sis.orquestador._results[tid]


class _VozDoble:
    """Transcriptor de pruebas: «voz:apaga la tele» se oye como «apaga la tele». El turno queda marcado
    como HABLADO porque la transcripción cambió la entrada, igual que con Whisper."""

    async def stt(self, audio, tid):
        return audio[4:] if audio.startswith("voz:") else audio

    async def tts(self, texto, tid):
        return None


async def _di_voz(sis, texto, activado=True):
    """Un turno HABLADO. `activado=True` es lo que hace la escucha continua tras oír «Aurora»."""
    sis.orquestador.voice = _VozDoble()
    return await _di(sis, f"voz:{texto}", activado=activado)


# ---------------------------------------------------------------- POR TEXTO: regla aprobada de M1 --


@pytest.mark.asyncio
async def test_por_TEXTO_la_orden_la_interpreta_el_Core_y_se_ejecuta_con_efecto_verificado(tmp_path):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)

    r = await _di(sis, "apaga la tele")

    assert ha.estados[_SALA]["state"] == "off"
    assert "Home Assistant ve" in r["say"] and "apagada" in r["say"], r["say"]
    assert espia.llamadas == 0, "la orden de hogar la interpreto el MODELO"


@pytest.mark.asyncio
async def test_despues_recuerda_lo_que_hizo_SIN_volver_a_ejecutarlo(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    hecho = await _di(sis, "apaga la tele")
    servicios = ha.servicios

    r = await _di(sis, "¿qué hiciste?")

    assert hecho["say"] in r["say"], "no recupero el resultado real de la accion"
    assert ha.servicios == servicios, "recordar volvio a ejecutar la accion"


@pytest.mark.asyncio
async def test_con_el_KILL_SWITCH_armado_no_actua(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    r = await _di(sis, "apaga la tele")

    assert ha.servicios == 0 and ha.estados[_SALA]["state"] == "on"
    assert "kill switch" in r["say"]


@pytest.mark.asyncio
async def test_una_accion_SIN_efecto_no_se_da_por_hecha(tmp_path):
    sis, _ = _aura(tmp_path, _HA(efecto=False))

    r = await _di(sis, "apaga la tele")

    assert "no cambió" in r["say"] and "Home Assistant ve" not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_con_el_hogar_SIMULADO_no_se_afirma_ningun_efecto(tmp_path):
    """Deuda D-ADP-1: el doble del hogar contesta `ok` sin tocar nada. AURA no puede presentarlo como hecho."""
    sis, _ = _aura(tmp_path)

    r = await _di(sis, "apaga la tele")

    assert "simulado" in r["say"] and "Home Assistant ve" not in r["say"], r["say"]


# ------------------------------------------ POR VOZ: se propone, se confirma y la FRONTERA detiene --


@pytest.mark.asyncio
async def test_por_VOZ_la_orden_se_PROPONE_y_no_se_ejecuta(tmp_path):
    ha = _HA()
    sis, espia = _aura(tmp_path, ha)

    r = await _di_voz(sis, "apaga la tele")

    assert "¿Lo hago?" in r["say"] and "la TV de la sala" in r["say"] and "Tv sala fmilia" not in r["say"]
    assert ha.servicios == 0 and espia.llamadas == 0


@pytest.mark.asyncio
async def test_por_VOZ_el_si_se_DETIENE_en_la_frontera_de_gobierno(tmp_path):
    """El mandato: fuera de la llave por ENTIDAD, una orden hablada no cambia el mundo. Se detiene JUSTO ahí:
    aquí la llave se cierra DESPUÉS de proponer (la entidad deja de pertenecer a `voz_actua_en`)."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di_voz(sis, "apaga la tele")
    sis.orquestador.voz_actua_en = frozenset()

    r = await _di_voz(sis, "sí")

    assert ha.servicios == 0 and ha.estados[_SALA]["state"] == "on"
    assert "espera una decisión" in r["say"] and "No lo he hecho" in r["say"]


@pytest.mark.asyncio
async def test_por_VOZ_con_la_llave_de_gobierno_el_camino_completo_actua_y_verifica(tmp_path):
    """El camino preparado funciona entero con la llave de AURA compuesta (solo la TV de la sala)."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di_voz(sis, "apaga la tele")

    r = await _di_voz(sis, "sí")

    assert ha.estados[_SALA]["state"] == "off" and "Home Assistant ve" in r["say"]


def test_la_llave_solo_abre_la_TV_de_la_sala(tmp_path):
    sis, _ = _aura(tmp_path)
    assert sis.orquestador.voz_actua_en == VOZ_ACTUA_EN == frozenset({_SALA})


def test_el_orquestador_sin_componer_trae_la_llave_de_voz_CERRADA():
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock
    from aura_skeleton.adapters.voice import VoiceAdapterMock
    from aura_skeleton.bus import InProcessEventBus
    from aura_skeleton.core.orchestrator import Orchestrator
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.modules.memory import SimpleMemory
    from aura_skeleton.modules.router import ModelRouter

    async def _si(a, args, t):
        return True

    orq = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([_Espia()], 1200),
        PermissionManager(_si),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )

    assert orq.voz_actua_en == frozenset(), "el orquestador abre la voz por defecto"


@pytest.mark.asyncio
async def test_por_VOZ_un_no_no_hace_nada(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di_voz(sis, "apaga la tele")

    r = await _di_voz(sis, "no")

    assert ha.servicios == 0 and "no lo hago" in r["say"].lower()


@pytest.mark.asyncio
async def test_por_VOZ_la_propuesta_caduca_si_el_turno_siguiente_es_otra_cosa(tmp_path):
    """Un «sí» que llega DOS turnos después no puede ejecutar una propuesta que ya nadie tiene delante."""
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    await _di_voz(sis, "apaga la tele")
    await _di_voz(sis, "¿cómo me llamo?")

    await _di_voz(sis, "sí")

    assert ha.servicios == 0, "un si tardio ejecuto una propuesta caducada"


# ============================================================ AURA conoce su entorno (semana 2) --

from aura_skeleton.core.entorno import ConocimientoDelEntorno, Observacion  # noqa: E402

_TV = Observacion(
    ip="10.0.0.29",
    nombre="[TV] Tv sala fmilia medina",
    fabricante="Samsung Electronics",
    tipo_upnp="MediaRenderer",
    fuentes=frozenset({"ssdp"}),
)
_MOVIL = Observacion(ip="10.0.0.94", servicios=frozenset({"_nearbypresence._tcp"}), fuentes=frozenset({"mdns"}))


@pytest.mark.asyncio
async def test_que_hay_conectado_se_responde_descubriendo_y_sin_el_modelo(tmp_path):
    sis, espia = _aura(tmp_path)
    sis.orquestador.entorno = ConocimientoDelEntorno(descubrir=lambda: [_TV, _MOVIL])

    r = await _di(sis, "¿Qué hay conectado?")

    assert "televisor" in r["say"] and "teléfono" in r["say"]
    assert "no sé de quién es" in r["say"], "se atribuyo el telefono a una persona o se omitio"
    assert espia.llamadas == 0 and r["dominio"] == "entorno"


@pytest.mark.asyncio
async def test_con_HA_la_TV_aparece_como_CONTROLABLE(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    real = sis.registro_adaptadores.para("encender_dispositivo")
    sis.orquestador.entorno = ConocimientoDelEntorno(descubrir=lambda: [_TV], entidades_ha=real.entidades)

    r = await _di(sis, "¿qué dispositivos ves?")

    assert "controlable" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_tras_apagar_la_TV_el_conocimiento_del_entorno_la_marca_EFECTO_VERIFICADO(tmp_path):
    """El resultado del Motor Único realimenta la capa de conocimiento: lo que AURA comprobó que puede
    afectar sube a EFECTO_VERIFICADO. No se deduce del descubrimiento; se registra del efecto real."""
    from aura_skeleton.core.entorno import EFECTO_VERIFICADO

    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    real = sis.registro_adaptadores.para("encender_dispositivo")
    sis.orquestador.entorno = ConocimientoDelEntorno(descubrir=lambda: [_TV], entidades_ha=real.entidades)
    await _di(sis, "¿qué dispositivos ves?")

    await _di(sis, "apaga la tele")

    d = next(x for x in sis.orquestador.entorno.inventario.dispositivos() if x.ip == _TV.ip)
    assert d.nivel == EFECTO_VERIFICADO, d.nivel


@pytest.mark.asyncio
async def test_CONTROL_una_orden_SIN_efecto_no_marca_EFECTO_VERIFICADO(tmp_path):
    from aura_skeleton.core.entorno import EFECTO_VERIFICADO

    ha = _HA(efecto=False)
    sis, _ = _aura(tmp_path, ha)
    real = sis.registro_adaptadores.para("encender_dispositivo")
    sis.orquestador.entorno = ConocimientoDelEntorno(descubrir=lambda: [_TV], entidades_ha=real.entidades)
    await _di(sis, "¿qué dispositivos ves?")

    await _di(sis, "apaga la tele")

    d = next(x for x in sis.orquestador.entorno.inventario.dispositivos() if x.ip == _TV.ip)
    assert d.nivel != EFECTO_VERIFICADO, d.nivel


@pytest.mark.asyncio
async def test_con_la_red_caida_se_dice_y_no_se_inventa(tmp_path):
    def _caida():
        raise OSError("red caida")

    sis, _ = _aura(tmp_path)
    sis.orquestador.entorno = ConocimientoDelEntorno(descubrir=_caida)

    r = await _di(sis, "¿qué hay en la red?")

    assert "No pude explorar" in r["say"] and "televisor" not in r["say"]


def test_la_composicion_cablea_el_conocimiento_del_entorno(tmp_path):
    sis, _ = _aura(tmp_path)
    assert isinstance(sis.orquestador.entorno, ConocimientoDelEntorno)


# ================= el MODELO no puede actuar sobre un dispositivo que la persona no nombró (semana 2) --
#
# Medido `[EJEC]`: «enciende la tele» la interpretaba el modelo, que «encendió la luz de la sala». La
# superficie de hogar del Core ya reconoce las órdenes limpias; pero cuando no reconoce una (p. ej. por un
# error de transcripción: «Apaga la tele» se oyó «Para la tene»), el turno cae al modelo, que PUEDE
# proponer una acción. ADR-0014 §4: el modelo no decide QUÉ se toca. Si el dispositivo que propone no lo
# nombró la persona, la acción se descarta. No retira ninguna autoridad aprobada: estrecha la que tenía.


def _aura_con_modelo(tmp_path, ha=None):
    """AURA compuesta con el proveedor de pruebas del proyecto, que propone acciones por palabras clave."""
    sis = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))
    if ha is not None:
        real = HomeAssistantReal(url="http://127.0.0.1:8123", token="t", http=ha, espera_s=0.05)
        for cap in real.capabilities:
            sis.registro_adaptadores._por_capacidad[cap] = real
    return sis


@pytest.mark.asyncio
async def test_el_modelo_NO_actua_sobre_un_dispositivo_que_nadie_nombro(tmp_path):
    llamadas = []
    sis = _aura_con_modelo(tmp_path)
    original = sis.motor.ejecutar

    async def _espia(accion, *a, **k):
        llamadas.append(accion)
        return await original(accion, *a, **k)

    sis.motor.ejecutar = _espia

    r = await _di(sis, "enciende todo por favor")  # el modelo de pruebas propone «luz de la sala»

    assert "encender_dispositivo" not in llamadas, "el modelo encendio un dispositivo que nadie nombro"
    assert "encendi" not in r["say"].lower(), f"se afirmo una accion que no ocurrio: {r['say']!r}"


@pytest.mark.asyncio
async def test_CONTROL_si_la_persona_NOMBRA_el_dispositivo_el_camino_del_modelo_sigue_vigente(tmp_path):
    """La garantía aprobada de M1 («lista verde ejecuta») no se retira: solo se exige que el dispositivo
    sea el que la persona dijo."""
    llamadas = []
    sis = _aura_con_modelo(tmp_path)
    original = sis.motor.ejecutar

    async def _espia(accion, *a, **k):
        llamadas.append(accion)
        return await original(accion, *a, **k)

    sis.motor.ejecutar = _espia

    await _di(sis, "enciende luz de la sala ya")

    assert "encender_dispositivo" in llamadas


# ============ «¿qué hiciste?» tras una acción se refiere a ESA acción, no al historial del ciclo (semana 2) --
#
# Encontrado `[EJEC]` con la TV REAL: tras «apaga la tele» (hecho y verificado), «¿qué hiciste?» contestó
# «Mi última tarea registrada es P-018, sobre estancamiento.py»: la superficie del historial autónomo va
# antes en la cascada y se quedaba la pregunta. En una conversación donde AURA ACABA de actuar, la
# pregunta es por eso. Sin una acción en el turno anterior, el historial sigue respondiendo como siempre.


def _con_ciclo_autonomo(sis):
    """La misma fuente de laboratorio que usan las pruebas de la ventana del SO Interno."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ui", "tests/integration/test_ui_limpia_y_estado_autonomo.py")
    ui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ui)
    sis.orquestador.estado_autonomo = ui.FuenteFalsa(ui.COLA_AGOTADA)


@pytest.mark.asyncio
async def test_tras_una_accion_que_hiciste_recupera_ESA_accion_y_no_el_historial_del_ciclo(tmp_path):
    ha = _HA()
    sis, _ = _aura(tmp_path, ha)
    _con_ciclo_autonomo(sis)
    hecho = await _di(sis, "apaga la tele")

    r = await _di(sis, "¿qué hiciste?")

    assert hecho["say"] in r["say"], f"respondio otra cosa: {r['say']!r}"


@pytest.mark.asyncio
async def test_con_una_pregunta_en_medio_que_hiciste_sigue_siendo_la_accion_de_esta_conversacion(tmp_path):
    """[EJEC] con la TV real: «enciende la tele» → «¿qué hay conectado?» → «¿qué hiciste?» contestaba el
    historial del ciclo (P-018). Una pregunta intermedia no borra lo que AURA acaba de hacer por ti."""
    sis, _ = _aura(tmp_path, _HA())
    _con_ciclo_autonomo(sis)
    hecho = await _di(sis, "apaga la tele")
    await _di(sis, "hola")

    r = await _di(sis, "¿qué hiciste?")

    assert hecho["say"] in r["say"], f"respondio otra cosa: {r['say']!r}"


@pytest.mark.asyncio
async def test_CONTROL_sin_accion_previa_que_hiciste_sigue_yendo_al_historial(tmp_path):
    sis, _ = _aura(tmp_path)
    _con_ciclo_autonomo(sis)
    await _di(sis, "hola")

    r = await _di(sis, "¿qué hiciste?")

    assert r["dominio"] == "historial", r["dominio"]
