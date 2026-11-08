"""Adaptador REAL de Home Assistant (Bible 6.3: HA como hub; contrato 6.1) — campaña, 2026-09-27.

Hasta hoy AURA solo tenía `HomeAssistantMock`: «encender_dispositivo» respondía `ok` sin tocar nada.
Descubierto `[EJEC]` en la red de la casa: una TV Samsung real y ningún Home Assistant. La Bible 6.3
manda integrar a través de HA, «no con cada dispositivo directamente».

Lo que este fichero fija, sobre todo: **una orden no está hecha porque se envió.** Está hecha cuando
el dispositivo CAMBIÓ de estado. `comando -> dispositivo -> efecto -> confirmación`.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from aura_skeleton.adapters.home_assistant_real import (
    HogarNoDisponible,
    HogarSinRespuesta,
    HomeAssistantReal,
    OrdenNoAdmisible,
)


class _HA:
    """Doble del API REST de HA: estado en memoria que los servicios cambian de verdad."""

    def __init__(
        self,
        estados=None,
        efecto=True,
        caido=False,
        post_agota=False,
        mudo_tras_post=False,
        post_rechazado=False,
        token_rechazado_en=None,
    ):
        self.estados = estados or {"media_player.tv_sala": {"state": "on", "attributes": {"friendly_name": "Tv sala"}}}
        self.efecto = efecto
        self.caido = caido
        self.post_agota = post_agota  # el POST del servicio se queda sin respuesta (TimeoutError)
        self.mudo_tras_post = mudo_tras_post
        self.post_rechazado = post_rechazado
        self.token_rechazado_en = token_rechazado_en  # "lectura" | "servicio": HA responde 401 ahí  # la conexión del POST falla (URLError): la orden NO salió  # y después HA deja de contestar también a las lecturas
        self.llamadas: list[tuple[str, str, dict | None]] = []

    def __call__(self, metodo, url, cuerpo=None, token=""):
        self.llamadas.append((metodo, url, cuerpo))
        assert token == "secreto", "el token no viajo en la llamada"
        if self.caido:
            raise OSError("conexion rechazada")
        fase = "servicio" if "/api/services/" in url else "lectura"
        if self.token_rechazado_en == fase:
            import urllib.error

            raise urllib.error.HTTPError(url, 401, "Unauthorized", None, None)
        if self.mudo_tras_post and any(m == "POST" for m, _u, _c in self.llamadas[:-1]):
            raise TimeoutError("timed out")
        if url.endswith("/api/"):
            return {"message": "API running."}
        if url.endswith("/api/states"):
            return [{"entity_id": e, **v} for e, v in self.estados.items()]
        if "/api/states/" in url:
            e = url.rsplit("/", 1)[1]
            return {"entity_id": e, **self.estados[e]}
        if "/api/services/" in url:
            servicio = url.rsplit("/", 1)[1]
            if self.post_agota:
                raise TimeoutError("timed out")
            if self.post_rechazado:
                import urllib.error

                raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
            if self.efecto:
                e = self.estados[cuerpo["entity_id"]]
                if servicio in ("turn_on", "turn_off"):
                    e["state"] = "on" if servicio == "turn_on" else "off"
                elif servicio == "volume_up":
                    e["attributes"]["volume_level"] = round(e["attributes"]["volume_level"] + 0.05, 2)
                elif servicio == "volume_down":
                    e["attributes"]["volume_level"] = round(e["attributes"]["volume_level"] - 0.05, 2)
                elif servicio == "volume_mute":
                    e["attributes"]["is_volume_muted"] = cuerpo["is_volume_muted"]
            return []
        raise AssertionError(url)


def _adaptador(ha, **kw):
    return HomeAssistantReal(url="http://127.0.0.1:8123", token="secreto", http=ha, espera_s=0.05, **kw)


def _ejecutar(ad, orden, dispositivo, evento="E1"):
    return asyncio.run(ad.execute(orden, {"device": dispositivo}, "T", evento))


def test_apagar_cambia_el_estado_y_lo_CONFIRMA():
    ha = _HA()
    r = _ejecutar(_adaptador(ha), "apagar_dispositivo", "Tv sala")
    assert r["status"] == "ok" and r["verificado"] is True
    assert r["estado_antes"] == "on" and r["estado_despues"] == "off"
    assert ha.estados["media_player.tv_sala"]["state"] == "off"


def test_una_orden_SIN_efecto_no_se_declara_hecha():
    """El corazón del adaptador: HA aceptó la llamada, el dispositivo no cambió. Eso no es un éxito."""
    r = _ejecutar(_adaptador(_HA(efecto=False)), "apagar_dispositivo", "Tv sala")
    assert r["status"] == "sin_efecto" and r["verificado"] is False


def test_se_resuelve_por_nombre_o_por_entity_id():
    ha = _HA()
    _ejecutar(_adaptador(ha), "apagar_dispositivo", "media_player.tv_sala")
    assert ha.estados["media_player.tv_sala"]["state"] == "off"


def test_un_dispositivo_desconocido_no_se_adivina():
    with pytest.raises(OrdenNoAdmisible, match="no existe"):
        _ejecutar(_adaptador(_HA()), "apagar_dispositivo", "la nevera")


def test_el_mismo_evento_no_actua_dos_veces():
    ha = _HA()
    ad = _adaptador(ha)
    _ejecutar(ad, "apagar_dispositivo", "Tv sala", "E9")
    r = _ejecutar(ad, "encender_dispositivo", "Tv sala", "E9")
    assert r["status"] == "duplicate"
    assert ha.estados["media_player.tv_sala"]["state"] == "off"


def test_HA_caido_se_declara_no_disponible():
    # Antes bastaba un `OSError`, que el Motor contaba como «sistema de archivos». Ahora se nombra.
    with pytest.raises(HogarSinRespuesta, match="no respondió"):
        _ejecutar(_adaptador(_HA(caido=True)), "apagar_dispositivo", "Tv sala")


def test_el_dry_run_dice_que_pasaria_SIN_actuar():
    ha = _HA()
    plan = asyncio.run(_adaptador(ha).simular("apagar_dispositivo", {"device": "Tv sala"}, "T"))
    assert plan["viable"] is True and "on" in plan["efecto"] and "off" in plan["efecto"]
    assert not any("/api/services/" in u for _m, u, _c in ha.llamadas), "el dry-run actuo"


def test_el_token_nunca_aparece_en_el_resultado():
    r = _ejecutar(_adaptador(_HA()), "apagar_dispositivo", "Tv sala")
    assert "secreto" not in json.dumps(r)


def test_comprobar_verifica_que_el_API_responde():
    assert "API running" in _adaptador(_HA()).comprobar()
    with pytest.raises(HogarNoDisponible):
        _adaptador(_HA(caido=True)).comprobar()


def test_solo_acepta_las_capacidades_del_catalogo():
    """No amplía nada: implementa exactamente lo que el catálogo declara en lista verde (D4) más el volumen
    de la TV autorizado por el acta del ecosistema doméstico (2026-10-22, §4)."""
    ad = _adaptador(_HA())
    assert sorted(ad.capabilities) == sorted(
        [
            "apagar_dispositivo",
            "encender_dispositivo",
            "subir_volumen",
            "bajar_volumen",
            "silenciar",
            "quitar_silencio",
        ]
    )
    with pytest.raises(OrdenNoAdmisible):
        _ejecutar(ad, "abrir_cerradura", "puerta")


# ------------------------------------ el adaptador habla el idioma de errores del Motor Único --


def test_un_dispositivo_inexistente_llega_al_motor_como_ERROR_y_no_tumba_el_turno():
    """Encontrado `[EJEC]` contra el HA real: `HogarNoDisponible` se escapaba del Motor Único, que solo
    convierte en `estado: error` lo que reconoce (`ErrorDeValidacion`, `OSError`). Un turno de voz que
    nombrara mal un dispositivo habría muerto en vez de decir «no existe»."""
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.permissions import PermissionManager

    async def _si(*_a):
        return True

    motor = MotorAutomatizacion(_adaptador(_HA()), PermissionManager(_si))
    r = asyncio.run(motor.ejecutar("apagar_dispositivo", {"device": "la nevera"}, "T", "E1", origen="t"))
    assert r["estado"] == "error" and "no existe" in r["motivo"], r


# ------------------------------------------------- el arranque dice qué hogar hay (`INV-9`) --


def test_sin_configuracion_el_hogar_es_el_doble_y_el_arranque_lo_DICE(monkeypatch):
    from aura_skeleton import composicion
    from aura_skeleton import observability as obs
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock

    monkeypatch.delenv("AURA_HA_URL", raising=False)
    monkeypatch.delenv("AURA_HA_TOKEN", raising=False)
    marca = len(obs.audit_records())
    assert isinstance(composicion._hogar(), HomeAssistantMock)
    assert any("SIMULADO" in r["msg"] for r in obs.audit_records()[marca:])


def test_con_configuracion_el_hogar_es_REAL(monkeypatch):
    from aura_skeleton import composicion

    monkeypatch.setenv("AURA_HA_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("AURA_HA_TOKEN", "x")
    assert isinstance(composicion._hogar(), HomeAssistantReal)


# ------------------------- hallazgo ALTO de la auditoría de seguridad: el dominio importa (2026-09-27)


def test_la_lista_verde_NO_alcanza_a_un_interruptor_cualquiera():
    """Auditoría independiente: el catálogo marca encender/apagar como verde pensando en luces (Bible
    6.3, D4), pero el adaptador llamaba a `turn_off` sobre CUALQUIER entidad. «Apaga el congelador»
    sobre `switch.congelador` habría pasado como una luz. Un `switch` puede ser cualquier cosa."""
    ha = _HA(estados={"switch.congelador": {"state": "on", "attributes": {"friendly_name": "congelador"}}})
    with pytest.raises(OrdenNoAdmisible, match="dominio"):
        _ejecutar(_adaptador(ha), "apagar_dispositivo", "congelador")
    assert ha.estados["switch.congelador"]["state"] == "on", "se apago algo fuera de la lista verde"


def test_CONTROL_una_luz_si_esta_en_la_lista_verde():
    ha = _HA(estados={"light.salon": {"state": "on", "attributes": {"friendly_name": "salon"}}})
    assert _ejecutar(_adaptador(ha), "apagar_dispositivo", "salon")["status"] == "ok"


# ------------------------------- «la tele» es la única TV que hay; si hubiera dos, no se adivina (semana 2)


def _ha_con(*entidades):
    return _HA(estados={e: {"state": "on", "attributes": {"friendly_name": n}} for e, n in entidades})


def test_un_nombre_generico_resuelve_al_UNICO_dispositivo_de_ese_tipo():
    ha = _ha_con(("media_player.tv_sala", "Tv sala fmilia medina"))
    r = _ejecutar(_adaptador(ha), "apagar_dispositivo", "tele")
    assert r["device"] == "media_player.tv_sala" and r["status"] == "ok"


@pytest.mark.parametrize("nombre", ["tv", "televisor", "televisión", "la tele"])
def test_sinonimos_de_television(nombre):
    ha = _ha_con(("media_player.tv_sala", "Tv sala fmilia medina"))
    assert _ejecutar(_adaptador(ha), "apagar_dispositivo", nombre)["device"] == "media_player.tv_sala"


def test_con_DOS_televisores_el_nombre_generico_no_se_adivina():
    ha = _ha_con(("media_player.tv_sala", "Tv sala"), ("media_player.tv_cuarto", "Tv cuarto"))
    with pytest.raises(OrdenNoAdmisible, match="varios"):
        _ejecutar(_adaptador(ha), "apagar_dispositivo", "tele")
    assert all(v["state"] == "on" for v in ha.estados.values()), "se apago uno adivinando"


def test_un_nombre_generico_sin_ningun_dispositivo_de_ese_tipo_dice_que_no_existe():
    ha = _ha_con(("light.salon", "salon"))
    with pytest.raises(OrdenNoAdmisible, match="no existe"):
        _ejecutar(_adaptador(ha), "apagar_dispositivo", "tele")


# ------------------------------- un HA lento no se disfraza de otra cosa ([EJEC] cierre semana 2) --


def _motor(ha):
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.permissions import PermissionManager

    async def _si(*_a):
        return True

    return MotorAutomatizacion(_adaptador(ha), PermissionManager(_si))


def test_si_el_servicio_agota_el_tiempo_se_relee_y_se_informa_lo_que_se_ve():
    """[EJEC] con la TV real: el `turn_off` de HA tardó >10 s (la TV estaba arrancando). El `TimeoutError`
    subía como `OSError` y AURA decía «fallo del sistema de archivos». Lo verdadero: se envió, y el estado
    releído es el que es."""
    r = _ejecutar(_adaptador(_HA(post_agota=True)), "apagar_dispositivo", "Tv sala")
    assert r["status"] == "sin_efecto" and r["verificado"] is False and r["estado_despues"] == "on", r


def test_si_HA_deja_de_responder_el_motor_lo_dice_y_NO_habla_del_sistema_de_archivos():
    r = asyncio.run(
        _motor(_HA(post_agota=True, mudo_tras_post=True)).ejecutar(
            "apagar_dispositivo", {"device": "Tv sala"}, "T", "E1", origen="t"
        )
    )
    assert r["estado"] == "error", r
    assert "Home Assistant no respondió" in r["motivo"] and "archivos" not in r["motivo"], r["motivo"]
    # La orden YA salió: decir «no he ejecutado nada» sería falso (S2-M31 lo reveló).
    assert "no sé si" in r["motivo"] and "no he ejecutado" not in r["motivo"], r["motivo"]


def test_la_espera_de_confirmacion_cubre_el_arranque_de_una_TV_despertada_por_red():
    """[EJEC]: encender la TV por red confirmó a los 5,2 s una vez y no confirmó a los 5 s la siguiente."""
    from aura_skeleton.adapters.home_assistant_real import ESPERA_CONFIRMACION_S

    assert ESPERA_CONFIRMACION_S >= 12
    assert HomeAssistantReal(url="http://x", token="t")._espera_s == ESPERA_CONFIRMACION_S


def test_si_la_conexion_del_servicio_falla_el_motor_dice_que_HA_no_respondio():
    """Hallazgo MEDIO de la auditoría independiente (cierre S2): el POST solo capturaba `TimeoutError`;
    un `URLError` (HA caído, conexión rechazada) seguía llegando al Motor como «fallo del sistema de
    archivos». Aquí la orden NO salió: se dice, y no se relee como si se hubiera enviado."""
    ha = _HA(post_rechazado=True)
    r = asyncio.run(_motor(ha).ejecutar("apagar_dispositivo", {"device": "Tv sala"}, "T", "E1", origen="t"))
    assert r["estado"] == "error", r
    assert "Home Assistant no respondió" in r["motivo"] and "archivos" not in r["motivo"], r["motivo"]
    # Falló AL ENVIAR: no se describe como «al buscar», y no se afirma nada que no se sepa (S2-M36).
    assert "al enviar" in r["motivo"] and "no la doy por ejecutada" in r["motivo"], r["motivo"]
    assert ha.estados["media_player.tv_sala"]["state"] == "on"


# ------------------------------------------ credencial inválida: se dice como tal (misión S2) --


def _orden_por_el_motor(ha):
    return asyncio.run(_motor(ha).ejecutar("apagar_dispositivo", {"device": "Tv sala"}, "T", "E1", origen="t"))


def test_un_token_rechazado_al_buscar_el_dispositivo_se_dice_y_no_se_envia_nada():
    ha = _HA(token_rechazado_en="lectura")
    r = _orden_por_el_motor(ha)
    assert r["estado"] == "error" and "credencial" in r["motivo"] and "archivos" not in r["motivo"], r
    assert not [u for m, u, _c in ha.llamadas if "/api/services/" in u], "se envió una orden sin credencial"


def test_un_token_rechazado_al_enviar_la_orden_no_se_disfraza_de_HA_caido():
    r = _orden_por_el_motor(_HA(token_rechazado_en="servicio"))
    assert r["estado"] == "error" and "credencial" in r["motivo"] and "no respondió" not in r["motivo"], r


def test_HA_caido_al_buscar_el_dispositivo_no_habla_del_sistema_de_archivos():
    r = _orden_por_el_motor(_HA(caido=True))
    assert r["estado"] == "error" and "Home Assistant no respondió" in r["motivo"], r
    assert "archivos" not in r["motivo"] and "no he ejecutado" in r["motivo"], r["motivo"]


def test_el_arranque_con_token_invalido_dice_que_el_hogar_no_esta_disponible_y_por_que():
    with pytest.raises(HogarNoDisponible, match="credencial"):
        _adaptador(_HA(token_rechazado_en="lectura")).comprobar()


def test_explorar_el_entorno_con_token_invalido_sigue_describiendo_la_red():
    from aura_skeleton.core.entorno import ConocimientoDelEntorno, Observacion

    ha = _adaptador(_HA(token_rechazado_en="lectura"))
    c = ConocimientoDelEntorno(
        descubrir=lambda: [Observacion(ip="10.0.0.1", fuentes=frozenset({"arp"}))], entidades_ha=ha.entidades
    )
    assert "10.0.0.1" in c.explorar("T")


# ------------------------- volumen de la TV (acta ecosistema doméstico 2026-10-22, §4) --


def _tv(estado="on", **atributos):
    return _HA(
        estados={"media_player.tv_sala": {"state": estado, "attributes": {"friendly_name": "Tv sala", **atributos}}}
    )


def _servicios(ha):
    return [(u.rsplit("/api/services/", 1)[1], c) for m, u, c in ha.llamadas if "/api/services/" in u]


def test_subir_volumen_se_CONFIRMA_si_volume_level_sube():
    ha = _tv(volume_level=0.30)
    r = _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")
    assert r["status"] == "ok" and r["verificado"] is True and r["atributo"] == "volume_level"
    assert r["valor_antes"] == 0.30 and r["valor_despues"] > 0.30
    assert r["estado_antes"] == "on" and r["estado_despues"] == "on" and r["device"] == "media_player.tv_sala"
    assert _servicios(ha) == [("media_player/volume_up", {"entity_id": "media_player.tv_sala"})]


def test_bajar_volumen_se_CONFIRMA_si_volume_level_baja():
    ha = _tv(volume_level=0.30)
    r = _ejecutar(_adaptador(ha), "bajar_volumen", "Tv sala")
    assert r["status"] == "ok" and r["verificado"] is True and r["valor_despues"] < 0.30
    assert _servicios(ha)[0][0] == "media_player/volume_down"


def test_silenciar_y_quitar_silencio_mandan_is_volume_muted_y_se_CONFIRMAN():
    ha = _tv(is_volume_muted=False)
    ad = _adaptador(ha)
    r = _ejecutar(ad, "silenciar", "Tv sala", "E1")
    assert r["status"] == "ok" and r["atributo"] == "is_volume_muted"
    assert r["valor_antes"] is False and r["valor_despues"] is True
    r2 = _ejecutar(ad, "quitar_silencio", "Tv sala", "E2")
    assert r2["status"] == "ok" and r2["valor_antes"] is True and r2["valor_despues"] is False
    assert [c for _s, c in _servicios(ha)] == [
        {"entity_id": "media_player.tv_sala", "is_volume_muted": True},
        {"entity_id": "media_player.tv_sala", "is_volume_muted": False},
    ]
    assert {s for s, _c in _servicios(ha)} == {"media_player/volume_mute"}


@pytest.mark.parametrize(
    ("orden", "atributo", "valor"),
    [
        ("subir_volumen", "volume_level", 0.3),
        ("bajar_volumen", "volume_level", 0.3),
        ("silenciar", "is_volume_muted", False),
    ],
)
def test_una_orden_de_volumen_que_no_mueve_el_atributo_es_SIN_efecto(orden, atributo, valor):
    """HA aceptó la llamada y el atributo no se movió: enviada no es hecha."""
    r = _ejecutar(_adaptador(_con_efecto_nulo(atributo, valor)), orden, "Tv sala")
    assert r["status"] == "sin_efecto" and r["verificado"] is False and r["valor_despues"] == valor


def _con_efecto_nulo(atributo, valor):
    ha = _tv(**{atributo: valor})
    ha.efecto = False
    return ha


def test_quitar_silencio_con_la_TV_ya_sin_silencio_no_se_declara_hecho_si_no_cambia():
    """Control: el valor esperado ya era False antes de enviar; el adaptador envía igualmente (el estado de HA puede
    estar obsoleto), relee y NO lo cuenta como efecto verificado: `ya_en_estado`."""
    r = _ejecutar(_adaptador(_tv(is_volume_muted=False)), "quitar_silencio", "Tv sala")
    assert r["valor_antes"] is False and r["valor_despues"] is False
    assert r["verificado"] is False and r["ya_en_estado"] is True, r


def test_con_la_TV_APAGADA_no_se_envia_nada_y_se_dice():
    ha = _tv(estado="off", volume_level=0.3)
    with pytest.raises(OrdenNoAdmisible, match="apagada"):
        _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")
    assert _servicios(ha) == [], "se envió una orden de volumen a una TV apagada"


@pytest.mark.parametrize(
    ("orden", "atributos"),
    [
        ("subir_volumen", {"is_volume_muted": False}),  # falta volume_level
        ("bajar_volumen", {}),
        ("silenciar", {"volume_level": 0.3}),  # falta is_volume_muted
        ("quitar_silencio", {}),
    ],
)
def test_si_HA_no_expone_el_atributo_no_se_envia_nada(orden, atributos):
    """Sin poder releer el efecto, enviar sería una orden sin comprobación posible."""
    ha = _tv(**atributos)
    with pytest.raises(OrdenNoAdmisible, match="no expone"):
        _ejecutar(_adaptador(ha), orden, "Tv sala")
    assert _servicios(ha) == []


def test_el_volumen_solo_alcanza_a_media_player():
    ha = _HA(estados={"light.salon": {"state": "on", "attributes": {"friendly_name": "salon", "volume_level": 0.5}}})
    with pytest.raises(OrdenNoAdmisible, match="media_player"):
        _ejecutar(_adaptador(ha), "subir_volumen", "salon")
    assert _servicios(ha) == []


def test_CONTROL_encender_una_luz_sigue_funcionando_con_la_tabla_de_volumen():
    ha = _HA(estados={"light.salon": {"state": "off", "attributes": {"friendly_name": "salon"}}})
    r = _ejecutar(_adaptador(ha), "encender_dispositivo", "salon")
    assert r["status"] == "ok" and "atributo" not in r


def test_volumen_con_token_rechazado_al_enviar_es_credencial_y_no_HA_caido():
    from aura_skeleton.adapters.home_assistant_real import HogarCredencialRechazada

    with pytest.raises(HogarCredencialRechazada):
        _ejecutar(
            _adaptador(_HA(estados=_tv(volume_level=0.3).estados, token_rechazado_en="servicio")),
            "subir_volumen",
            "Tv sala",
        )


def test_volumen_con_HA_que_rechaza_la_conexion_al_enviar_es_HogarSinRespuesta():
    ha = _tv(volume_level=0.3)
    ha.post_rechazado = True
    with pytest.raises(HogarSinRespuesta, match="no la doy por ejecutada"):
        _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")


def test_volumen_si_el_servicio_agota_el_tiempo_se_relee_y_se_verifica():
    """La orden SALIÓ aunque HA no contestó a tiempo: el POST sí aplica el efecto y se relee."""
    ha = _tv(volume_level=0.3)
    original = ha.__call__

    class _TimeoutTrasAplicar:
        llamadas = ha.llamadas

        def __call__(self, metodo, url, cuerpo=None, token=""):
            r = original(metodo, url, cuerpo, token)
            if "/api/services/" in url:
                raise TimeoutError("timed out")
            return r

    r = _ejecutar(_adaptador(_TimeoutTrasAplicar()), "subir_volumen", "Tv sala")
    assert r["status"] == "ok" and r["valor_despues"] > 0.3


def test_volumen_idempotente_por_event_id():
    ha = _tv(volume_level=0.3)
    ad = _adaptador(ha)
    _ejecutar(ad, "subir_volumen", "Tv sala", "E7")
    assert _ejecutar(ad, "subir_volumen", "Tv sala", "E7")["status"] == "duplicate"
    assert len(_servicios(ha)) == 1


def test_el_dry_run_acepta_el_volumen_sin_actuar():
    ha = _tv(volume_level=0.3)
    plan = asyncio.run(_adaptador(ha).simular("subir_volumen", {"device": "Tv sala"}, "T"))
    assert plan["viable"] is True and "volume" in plan["efecto"]
    assert _servicios(ha) == []


def test_el_doble_acepta_las_cuatro_y_responde_como_con_on_off():
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock

    m = HomeAssistantMock()
    for i, c in enumerate(["subir_volumen", "bajar_volumen", "silenciar", "quitar_silencio"]):
        assert c in m.capabilities
        r = asyncio.run(m.execute(c, {"device": "tele"}, "T", f"M{i}"))
        assert r == {"status": "ok", "device": "tele"}


def test_el_catalogo_declara_las_cuatro_como_verde_reversible():
    from aura_skeleton.core.permissions import CATALOGO

    for c in ["subir_volumen", "bajar_volumen", "silenciar", "quitar_silencio"]:
        assert CATALOGO[c]["lista"] == "verde" and CATALOGO[c]["efecto"] == "reversible"


def test_la_notificacion_de_volumen_es_gramatical():
    from aura_skeleton.core.notificaciones import _VERBOS

    assert _VERBOS["subir_volumen"] == ("Subí el volumen de", "subir el volumen de")
    assert _VERBOS["quitar_silencio"][1] == "quitar el silencio de"


# ------------- estados reales de HA, evidencia honesta y rechazos (acta hogar 2026-10-22) --


def _http_error(url, codigo):
    import urllib.error

    return urllib.error.HTTPError(url, codigo, "x", None, None)


class _HASegun(_HA):
    """Doble donde el estado posterior al servicio lo fija la prueba (HA real: `turn_on` -> `playing`...)."""

    def __init__(self, estado_inicial, tras_servicio=None, codigo_post=None, **kw):
        super().__init__(
            estados={"media_player.tv_sala": {"state": estado_inicial, "attributes": {"friendly_name": "Tv sala"}}},
            **kw,
        )
        self.tras_servicio = tras_servicio
        self.codigo_post = codigo_post

    def __call__(self, metodo, url, cuerpo=None, token=""):
        if metodo == "POST" and self.codigo_post:
            self.llamadas.append((metodo, url, cuerpo))
            raise _http_error(url, self.codigo_post)
        r = super().__call__(metodo, url, cuerpo, token)
        if metodo == "POST" and self.tras_servicio:
            self.estados["media_player.tv_sala"]["state"] = self.tras_servicio
        return r


def _posts(ha):
    return [u for m, u, _c in ha.llamadas if m == "POST"]


@pytest.mark.parametrize(
    ("orden", "inicial", "tras"),
    [
        ("encender_dispositivo", "off", "playing"),
        ("encender_dispositivo", "standby", "paused"),
        ("encender_dispositivo", "off", "idle"),
        ("apagar_dispositivo", "on", "standby"),
        ("apagar_dispositivo", "playing", "off"),
    ],
)
def test_los_estados_de_encendido_y_apagado_de_HA_se_VERIFICAN(orden, inicial, tras):
    r = _ejecutar(_adaptador(_HASegun(inicial, tras)), orden, "Tv sala")
    assert r["status"] == "ok" and r["verificado"] is True and r["estado_despues"] == tras, r


@pytest.mark.parametrize(("orden", "tras"), [("encender_dispositivo", "buffering"), ("apagar_dispositivo", "raro")])
def test_un_estado_fuera_de_ambos_conjuntos_NO_se_verifica(orden, tras):
    inicial = "off" if orden == "encender_dispositivo" else "on"
    r = _ejecutar(_adaptador(_HASegun(inicial, tras)), orden, "Tv sala")
    assert r["status"] == "sin_efecto" and r["verificado"] is False, r


def test_la_verificacion_comparte_los_conjuntos_con_las_consultas():
    from aura_skeleton.core import hogar

    assert hogar.ESTADOS_ENCENDIDA == {"on", "playing", "paused", "idle"} == hogar._ENCENDIDOS
    assert hogar.ESTADOS_APAGADA == {"off", "standby"} == hogar._APAGADOS


def test_si_ya_estaba_en_el_estado_pedido_no_se_cuenta_como_efecto_verificado():
    r = _ejecutar(_adaptador(_HASegun("playing", "playing")), "encender_dispositivo", "Tv sala")
    assert r["verificado"] is False and r["status"] == "sin_efecto", r


@pytest.mark.parametrize("estado", ["unavailable", "unknown", "raro"])
@pytest.mark.parametrize("orden", ["encender_dispositivo", "apagar_dispositivo", "subir_volumen"])
def test_un_dispositivo_no_accesible_no_recibe_ninguna_llamada_de_servicio(estado, orden):
    ha = _HASegun(estado)
    ha.estados["media_player.tv_sala"]["attributes"]["volume_level"] = 0.3
    ad = _adaptador(ha)
    ad._espera_s = 30.0  # si esperara, la prueba tardaría: debe fallar antes de enviar
    import time

    t0 = time.monotonic()
    with pytest.raises(OrdenNoAdmisible, match=rf"no está accesible.*«{estado}»"):
        _ejecutar(ad, orden, "Tv sala")
    assert _posts(ha) == [] and time.monotonic() - t0 < 2


@pytest.mark.parametrize("estado", ["playing", "paused", "idle", "on"])
def test_el_volumen_se_acepta_con_la_TV_en_cualquier_estado_de_encendida(estado):
    ha = _HASegun(estado)
    ha.estados["media_player.tv_sala"]["attributes"]["volume_level"] = 0.3
    r = _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")
    assert r["verificado"] is True and len(_posts(ha)) == 1, r


def test_el_volumen_con_la_TV_en_standby_sigue_rechazado_sin_enviar():
    ha = _HASegun("standby")
    ha.estados["media_player.tv_sala"]["attributes"]["volume_level"] = 0.3
    with pytest.raises(OrdenNoAdmisible, match="apagada"):
        _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")
    assert _posts(ha) == []


@pytest.mark.parametrize("codigo", [400, 404, 500, 503])
def test_un_HTTPError_al_enviar_es_RECHAZO_con_su_codigo_y_no_un_no_respondio(codigo):
    ha = _HASegun("on", codigo_post=codigo)
    r = _orden_por_el_motor(ha)
    assert r["estado"] == "error", r
    verbo = "falló al procesar" if codigo >= 500 else "rechazó"
    assert f"HTTP {codigo}" in r["motivo"] and f"Home Assistant {verbo} la orden" in r["motivo"], r["motivo"]
    assert "no respondió" not in r["motivo"] and "no la doy por ejecutada" in r["motivo"], r["motivo"]


@pytest.mark.parametrize("codigo", [401, 403])
def test_401_y_403_al_enviar_siguen_siendo_credencial(codigo):
    r = _orden_por_el_motor(_HASegun("on", codigo_post=codigo))
    assert "credencial" in r["motivo"] and "rechazó la orden" not in r["motivo"], r["motivo"]


def test_un_error_de_red_al_enviar_sigue_siendo_no_respondio():
    r = _orden_por_el_motor(_HA(post_rechazado=True))
    assert "Home Assistant no respondió" in r["motivo"] and "rechazó la orden" not in r["motivo"], r["motivo"]


def test_una_orden_no_admisible_o_no_autorizada_no_produce_llamadas_de_servicio():
    ha = _HA()
    r = asyncio.run(_motor(ha).ejecutar("apagar_dispositivo", {"device": "la nevera"}, "T", "E1", origen="t"))
    assert r["estado"] in ("error", "detenida"), r
    r2 = asyncio.run(_motor(ha).ejecutar("transferencia", {"device": "Tv sala"}, "T", "E2", origen="t"))
    assert r2["estado"] in ("error", "detenida"), r2
    assert _posts(ha) == []


def test_unavailable_no_consume_la_espera_ni_llama_a_sleep(monkeypatch):
    import time as _t

    dormidas = []
    monkeypatch.setattr(_t, "sleep", lambda s: dormidas.append(s))
    ha = _HASegun("unavailable")
    with pytest.raises(OrdenNoAdmisible):
        _ejecutar(_adaptador(ha), "encender_dispositivo", "Tv sala")
    assert dormidas == [] and _posts(ha) == []


def test_el_volumen_en_standby_dice_que_HA_la_ve_en_espera_y_no_envia():
    ha = _HASegun("standby")
    ha.estados["media_player.tv_sala"]["attributes"]["volume_level"] = 0.3
    with pytest.raises(OrdenNoAdmisible, match=r"apagada \(Home Assistant la ve en espera\)"):
        _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")
    assert _posts(ha) == []


def test_un_timeout_real_al_comprobar_dice_no_respondio_a_tiempo():
    r = asyncio.run(
        _motor(_HA(post_agota=True, mudo_tras_post=True)).ejecutar(
            "apagar_dispositivo", {"device": "Tv sala"}, "T", "E1", origen="t"
        )
    )
    assert "Home Assistant no respondió a tiempo" in r["motivo"], r["motivo"]


class _HAIlegible(_HASegun):
    """Tras el POST, la relectura devuelve basura: JSON inválido o un objeto sin `state`."""

    def __init__(self, modo, **kw):
        super().__init__("on", **kw)
        self.modo = modo

    def __call__(self, metodo, url, cuerpo=None, token=""):
        if metodo == "GET" and "/api/states/" in url and any(m == "POST" for m, _u, _c in self.llamadas):
            self.llamadas.append((metodo, url, cuerpo))
            if self.modo == "json":
                raise json.JSONDecodeError("mal", "x", 0)
            return {"entity_id": "media_player.tv_sala"} if self.modo == "sin_state" else ["no", "es", "dict"]
        return super().__call__(metodo, url, cuerpo, token)


@pytest.mark.parametrize("modo", ["json", "sin_state", "lista"])
def test_una_relectura_malformada_es_estado_desconocido_y_nunca_verificada(modo):
    r = _ejecutar(_adaptador(_HAIlegible(modo)), "apagar_dispositivo", "Tv sala")
    assert r["verificado"] is False and r["status"] == "sin_efecto", r
    assert r["estado_despues"] == "?" and r["evidencia"] == "ninguna", r


def test_el_resultado_verificado_declara_que_su_evidencia_es_el_estado_de_HA():
    r = _ejecutar(_adaptador(_HASegun("on", "standby")), "apagar_dispositivo", "Tv sala")
    assert r["verificado"] is True and r["evidencia"] == "estado_ha_tras_orden"


def test_con_la_PARADA_echada_no_se_envia_ninguna_llamada_de_servicio():
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.permissions import PermissionManager

    class _Parada:
        def is_engaged(self):
            return True

    async def _si(*_a):
        return True

    ha = _HA()
    motor = MotorAutomatizacion(_adaptador(ha), PermissionManager(_si, kill_switch=_Parada()))
    r = asyncio.run(motor.ejecutar("apagar_dispositivo", {"device": "Tv sala"}, "T", "E1", origen="t"))
    assert r["estado"] == "detenida" and _posts(ha) == []


# --------------------- revisión independiente 2026-10-22: relecturas ilegibles, «ya estaba», HTTP, acotado --


class _HARelectura(_HASegun):
    """Doble donde la relectura POSTERIOR al servicio (o la lectura inicial) falla o devuelve algo concreto."""

    def __init__(self, estado="on", tras=None, relectura=None, http_relectura=None, http_busqueda=None, **atributos):
        super().__init__(estado, tras)
        self.estados["media_player.tv_sala"]["attributes"].update(atributos)
        self.relectura = relectura
        self.http_relectura = http_relectura
        self.http_busqueda = http_busqueda

    def __call__(self, metodo, url, cuerpo=None, token=""):
        if metodo == "GET" and url.endswith("/api/states") and self.http_busqueda:
            self.llamadas.append((metodo, url, cuerpo))
            raise _http_error(url, self.http_busqueda)
        posterior = any(m == "POST" for m, _u, _c in self.llamadas)
        if metodo == "GET" and "/api/states/" in url and posterior:
            self.llamadas.append((metodo, url, cuerpo))
            if self.http_relectura:
                raise _http_error(url, self.http_relectura)
            if self.relectura is not None:
                return self.relectura
        return super().__call__(metodo, url, cuerpo, token)


@pytest.mark.parametrize("relectura", [{}, {"state": "on"}, {"state": "on", "attributes": {}}])
def test_silenciar_con_la_TV_ya_silenciada_y_relectura_ilegible_NO_se_verifica(relectura):
    ha = _HARelectura("on", relectura=relectura, is_volume_muted=True)
    r = _ejecutar(_adaptador(ha), "silenciar", "Tv sala")
    assert r["verificado"] is False and r["valor_despues"] is None, r
    if "state" not in relectura:
        assert r["evidencia"] == "ninguna"


def test_el_texto_de_una_relectura_ilegible_no_dice_comprobado():
    from aura_skeleton.core.orchestrator import _redactar_efecto_de_volumen

    ha = _HARelectura("on", relectura={}, is_volume_muted=True)
    r = _ejecutar(_adaptador(ha), "silenciar", "Tv sala")
    t = _redactar_efecto_de_volumen("silenciar", r, {})
    assert "comprobado" not in t and "No lo doy por hecho" in t, t


@pytest.mark.parametrize("orden", ["encender_dispositivo", "apagar_dispositivo", "subir_volumen"])
def test_attributes_que_no_es_un_dict_en_la_relectura_no_escapa_del_Motor(orden):
    ha = _HARelectura(
        "on" if orden != "encender_dispositivo" else "off", relectura={"state": "on", "attributes": ["x"]}
    )
    ha.estados["media_player.tv_sala"]["attributes"]["volume_level"] = 0.3
    r = asyncio.run(_motor(ha).ejecutar(orden, {"device": "Tv sala"}, "T", "E1", origen="t"))
    assert r["estado"] in ("ejecutada", "error"), r
    if r["estado"] == "ejecutada":
        assert r["resultado"]["verificado"] is False or orden == "encender_dispositivo"


@pytest.mark.parametrize(
    ("orden", "antes", "tras"),
    [("encender_dispositivo", "playing", "idle"), ("apagar_dispositivo", "standby", "off")],
)
def test_si_antes_ya_estaba_en_el_conjunto_pedido_se_envia_pero_no_es_efecto_verificado(orden, antes, tras):
    ha = _HASegun(antes, tras)
    r = _ejecutar(_adaptador(ha), orden, "Tv sala")
    assert len(_posts(ha)) == 1  # el estado de HA puede estar obsoleto: se envía igualmente
    assert r["verificado"] is False and r["ya_en_estado"] is True, r


def test_ya_en_estado_no_aparece_cuando_si_hubo_cambio():
    r = _ejecutar(_adaptador(_HASegun("off", "playing")), "encender_dispositivo", "Tv sala")
    assert r["verificado"] is True and not r.get("ya_en_estado")


@pytest.mark.parametrize("codigo", [404, 500])
def test_HTTPError_en_la_relectura_dice_que_HA_respondio_ese_codigo(codigo):
    r = _orden_por_el_motor(_HARelectura("on", http_relectura=codigo))
    assert r["estado"] == "error", r
    assert f"respondió HTTP {codigo} al comprobar" in r["motivo"] and "no respondió" not in r["motivo"], r["motivo"]
    assert "no sé si la orden surtió efecto" in r["motivo"]


@pytest.mark.parametrize("codigo", [404, 500])
def test_HTTPError_en_la_busqueda_dice_que_HA_respondio_ese_codigo_y_no_envia(codigo):
    ha = _HARelectura("on", http_busqueda=codigo)
    r = _orden_por_el_motor(ha)
    assert r["estado"] == "error", r
    assert f"respondió HTTP {codigo} al buscar" in r["motivo"] and "no respondió" not in r["motivo"], r["motivo"]
    assert _posts(ha) == []


def test_401_en_la_relectura_sigue_siendo_credencial():
    r = _orden_por_el_motor(_HARelectura("on", http_relectura=401))
    assert "credencial" in r["motivo"], r["motivo"]


def test_un_estado_de_500_caracteres_con_escape_no_llega_entero_ni_con_control_al_usuario():
    sucio = "\x1b[31m" + "x" * 500
    ha = _HASegun(sucio)
    with pytest.raises(OrdenNoAdmisible) as e:
        _ejecutar(_adaptador(ha), "encender_dispositivo", "Tv sala")
    assert "\x1b" not in str(e.value) and len(str(e.value)) < 250, str(e.value)


def test_un_estado_sucio_en_el_texto_del_redactor_va_acotado_y_sin_control():
    from aura_skeleton.core.orchestrator import _redactar_efecto_de_hogar

    sucio = "\x1b[31m" + "y" * 500
    d = {"device": "media_player.tv_sala", "status": "sin_efecto", "estado_antes": "on", "estado_despues": sucio}
    for nombres in ({"media_player.tv_sala": "la TV"}, {}):
        t = _redactar_efecto_de_hogar("apagar_dispositivo", d, nombres)
        assert "\x1b" not in t and len(t) < 300, t


@pytest.mark.parametrize("fallo", ["nombre", "no_accesible", "http_400"])
def test_un_rechazo_antes_de_enviar_no_quema_el_event_id(fallo):
    ha = _HASegun("unavailable" if fallo == "no_accesible" else "on", codigo_post=400 if fallo == "http_400" else None)
    ad = _adaptador(ha)
    dispositivo = "la nevera" if fallo == "nombre" else "Tv sala"
    with pytest.raises(Exception):  # noqa: B017 (cualquier rechazo previo al envío aceptado)
        _ejecutar(ad, "apagar_dispositivo", dispositivo, "E7")
    ha.estados["media_player.tv_sala"]["state"] = "on"
    ha.codigo_post = None
    r = _ejecutar(ad, "apagar_dispositivo", "Tv sala", "E7")
    assert r.get("status") != "duplicate" and r["verificado"] is True, r


def test_tras_un_envio_aceptado_el_mismo_event_id_si_es_duplicado_aunque_la_relectura_falle():
    ha = _HARelectura("on", http_relectura=500)
    ad = _adaptador(ha)
    with pytest.raises(HogarSinRespuesta):
        _ejecutar(ad, "apagar_dispositivo", "Tv sala", "E8")
    assert _ejecutar(ad, "apagar_dispositivo", "Tv sala", "E8")["status"] == "duplicate"
    assert len(_posts(ha)) == 1


@pytest.mark.parametrize("esperado", ["sube", "baja", 0.3, True, False])
@pytest.mark.parametrize("ilegible", [None, "0.9", True])
def test_un_valor_releido_ilegible_nunca_cuenta_como_cambio(esperado, ilegible):
    """Caso de control: el comparador por sí solo (sin apoyarse en la evidencia posterior) rechaza lo ilegible."""
    from aura_skeleton.adapters.home_assistant_real import _cambio_esperado

    antes = False if isinstance(esperado, bool) else 0.5
    if isinstance(esperado, bool) and ilegible is True:
        pytest.skip("True es un booleano legible para el silencio")
    assert _cambio_esperado(esperado, antes, ilegible) is False


@pytest.mark.parametrize("codigo", [400, 404, 500, 503])
def test_un_HTTPError_al_enviar_levanta_HogarOrdenRechazada_y_no_HogarSinRespuesta(codigo):
    """El TIPO importa (el llamante distingue «HA contestó que no» de «HA no contestó»): el texto no basta."""
    from aura_skeleton.adapters.home_assistant_real import HogarOrdenRechazada

    with pytest.raises(HogarOrdenRechazada) as info:
        _ejecutar(_adaptador(_HASegun("on", codigo_post=codigo)), "apagar_dispositivo", "Tv sala")
    assert not isinstance(info.value, HogarSinRespuesta)


def test_un_cambio_de_volumen_sin_estado_legible_tras_la_orden_no_se_verifica():
    """Caso de control de la evidencia: el atributo SÍ cambió pero HA no da el `state` -> evidencia «ninguna»."""
    ha = _tv(volume_level=0.30)
    ad = _adaptador(ha)
    ad._releer = lambda entidad: {"entity_id": entidad, "attributes": {"volume_level": 0.35}}  # sin `state`
    r = _ejecutar(ad, "subir_volumen", "Tv sala")
    assert r["evidencia"] == "ninguna" and r["verificado"] is False and r["status"] == "sin_efecto", r


# ------------- estado ASUMIDO (SmartIR, IE-002): HA publica un estado optimista sin leer el aparato --


class _HAAsumido(_HASegun):
    """Tras el servicio, la entidad sigue diciendo `assumed_state` (o no) en sus atributos."""

    def __init__(self, estado, tras, asumido, **atributos):
        super().__init__(estado, tras)
        self.estados["media_player.tv_sala"]["attributes"].update(atributos)
        self.asumido = asumido

    def __call__(self, metodo, url, cuerpo=None, token=""):
        r = super().__call__(metodo, url, cuerpo, token)
        if metodo == "POST" and self.asumido is not None:
            self.estados["media_player.tv_sala"]["attributes"]["assumed_state"] = self.asumido
        return r


@pytest.mark.parametrize(
    ("orden", "antes", "tras"), [("encender_dispositivo", "off", "on"), ("apagar_dispositivo", "on", "off")]
)
def test_con_estado_asumido_tras_la_orden_NO_se_verifica_aunque_el_estado_sea_el_pedido(orden, antes, tras):
    ha = _HAAsumido(antes, tras, True)
    r = _ejecutar(_adaptador(ha), orden, "Tv sala")
    assert len(_posts(ha)) == 1  # la orden es legítima: se envía
    assert r["verificado"] is False and r["evidencia"] == "estado_asumido_por_ha", r


def test_el_estado_asumido_inicial_no_impide_enviar():
    ha = _HAAsumido("off", "on", True)
    ha.estados["media_player.tv_sala"]["attributes"]["assumed_state"] = True
    assert len(_posts(ha)) == 0
    r = _ejecutar(_adaptador(ha), "encender_dispositivo", "Tv sala")
    assert len(_posts(ha)) == 1 and r["verificado"] is False


@pytest.mark.parametrize("asumido", [False, None])
def test_control_sin_estado_asumido_se_verifica_como_siempre(asumido):
    r = _ejecutar(_adaptador(_HAAsumido("off", "on", asumido)), "encender_dispositivo", "Tv sala")
    assert r["verificado"] is True and r["evidencia"] == "estado_ha_tras_orden", r


@pytest.mark.parametrize("asumido", [True, False])
def test_el_volumen_con_estado_asumido_no_se_verifica(asumido):
    ha = _HAAsumido("on", None, asumido, volume_level=0.3)
    r = _ejecutar(_adaptador(ha), "subir_volumen", "Tv sala")
    if asumido:
        assert r["verificado"] is False and r["evidencia"] == "estado_asumido_por_ha", r
    else:
        assert r["verificado"] is True, r


@pytest.mark.parametrize(
    ("capacidad", "estado", "frase"),
    [
        (
            "encender_dispositivo",
            "on",
            "Envié la orden de encender la TV de la sala. Home Assistant la da por encendida, pero es un estado asumido (no lee el aparato); no puedo confirmarlo.",
        ),
        (
            "apagar_dispositivo",
            "off",
            "Envié la orden de apagar la TV de la sala. Home Assistant la da por apagada, pero es un estado asumido (no lee el aparato); no puedo confirmarlo.",
        ),
    ],
)
def test_el_texto_de_un_estado_asumido_nunca_dice_listo(capacidad, estado, frase):
    from aura_skeleton.core.orchestrator import _redactar_efecto_de_hogar

    d = {
        "device": "media_player.tv_sala",
        "status": "sin_efecto",
        "verificado": False,
        "evidencia": "estado_asumido_por_ha",
        "estado_antes": "x",
        "estado_despues": estado,
    }
    assert _redactar_efecto_de_hogar(capacidad, d, {"media_player.tv_sala": "la TV de la sala"}) == frase
    assert "Listo" not in _redactar_efecto_de_hogar(capacidad, d, {})


def test_el_texto_de_volumen_asumido_nunca_dice_listo_ni_comprobado():
    from aura_skeleton.core.orchestrator import _redactar_efecto_de_volumen

    d = {
        "device": "media_player.tv_sala",
        "status": "sin_efecto",
        "verificado": False,
        "evidencia": "estado_asumido_por_ha",
        "atributo": "volume_level",
        "valor_antes": 0.3,
        "valor_despues": 0.35,
    }
    t = _redactar_efecto_de_volumen("subir_volumen", d, {"media_player.tv_sala": "la TV de la sala"})
    assert "estado asumido" in t and "no puedo confirmarlo" in t and "Listo" not in t and "comprobado" not in t, t
