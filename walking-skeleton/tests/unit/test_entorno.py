"""AURA conoce su entorno físico: descubrir != identificar != integrar != controlar (semana 2).

Datos SINTÉTICOS con el formato de las fuentes reales medidas el 2026-09-27 (vecinos ARP, mDNS, SSDP/UPnP):
los nombres y direcciones reales de la casa no entran en el repositorio.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from aura_skeleton.core.entorno import (
    CARACTERIZADO,
    CONTROLABLE,
    DESCUBIERTO,
    INTEGRADO,
    InventarioEntorno,
    Observacion,
    describir,
)

TV = Observacion(
    ip="10.0.0.29",
    mac="02:aa:bb:cc:dd:ee",
    nombre="[TV] Tv sala",
    fabricante="Samsung Electronics",
    modelo="UN43",
    tipo_upnp="MediaRenderer",
    servicios=frozenset({"AirPlay Remote Video"}),
    fuentes=frozenset({"ssdp", "mdns", "arp"}),
)
ROUTER = Observacion(
    ip="10.0.0.1",
    mac="14:00:00:00:00:20",
    tipo_upnp="InternetGatewayDevice",
    fabricante="Ubuntu",
    fuentes=frozenset({"ssdp", "arp"}),
)
MOVIL = Observacion(ip="10.0.0.94", servicios=frozenset({"_nearbypresence._tcp"}), fuentes=frozenset({"mdns"}))
RARO = Observacion(ip="10.0.0.20", mac="5c:00:00:00:00:1d", fuentes=frozenset({"arp"}))


def _inv(*obs, ha=(), controlables=frozenset({"media_player", "light"})):
    inv = InventarioEntorno(dominios_controlables=controlables)
    inv.actualizar(list(obs), entidades_ha=list(ha))
    return inv


def _por_ip(inv, ip):
    return next(d for d in inv.dispositivos() if d.ip == ip)


# ------------------------------------------------------------------- los cuatro niveles --


def test_solo_ARP_es_DESCUBIERTO_y_no_se_finge_saber_que_es():
    d = _por_ip(_inv(RARO), "10.0.0.20")
    assert d.nivel == DESCUBIERTO and d.tipo == "desconocido"


def test_SSDP_de_Samsung_MediaRenderer_es_una_TV_IDENTIFICADA():
    # Mapa vivo (2026-09-27): al anunciarse como renderizador además se sabe QUÉ OFRECE -> CARACTERIZADO.
    d = _por_ip(_inv(TV), "10.0.0.29")
    assert d.tipo == "televisor" and d.nivel == CARACTERIZADO and d.entidad_ha is None


def test_la_pasarela_UPnP_es_el_router():
    assert _por_ip(_inv(ROUTER), "10.0.0.1").tipo == "router"


def test_un_telefono_se_identifica_como_DISPOSITIVO_nunca_como_persona():
    d = _por_ip(_inv(MOVIL), "10.0.0.94")
    assert d.tipo == "teléfono"
    assert "de quién es" in describir(_inv(MOVIL)), "se infirio o se omitio la identidad del dueño"


def test_con_su_entidad_en_Home_Assistant_la_TV_esta_INTEGRADA_y_es_CONTROLABLE():
    d = _por_ip(_inv(TV, ha=[("media_player.tv_sala", "Tv sala")]), "10.0.0.29")
    assert d.nivel == CONTROLABLE and d.entidad_ha == "media_player.tv_sala"


def test_integrado_NO_implica_controlable_fuera_de_la_lista_verde():
    d = _por_ip(_inv(TV, ha=[("media_player.tv_sala", "Tv sala")], controlables=frozenset({"light"})), "10.0.0.29")
    assert d.nivel == INTEGRADO


def test_sin_entidad_en_Home_Assistant_la_TV_no_se_da_por_integrada():
    d = _por_ip(_inv(TV, ha=[("light.salon", "salon")]), "10.0.0.29")
    assert d.nivel not in (INTEGRADO, CONTROLABLE) and d.entidad_ha is None, d.nivel


def test_HA_nombra_la_TV_con_su_MODELO_entre_parentesis_y_sigue_siendo_la_misma():
    """[EJEC] cierre semana 2: la TV anuncia «[TV] Tv sala fmilia medina» y HA la titula
    «Tv sala fmilia medina (UN43RU7100FXZA)». Exigir el nombre idéntico dejaba la TV YA controlable como
    «identificada, falta integrarla»."""
    d = _por_ip(_inv(TV, ha=[("media_player.tv_sala", "Tv sala (UN43)")]), "10.0.0.29")
    assert d.nivel == CONTROLABLE and d.entidad_ha == "media_player.tv_sala"


def test_con_una_entidad_remote_y_otra_media_player_del_mismo_nombre_gana_la_controlable():
    """[EJEC]: la integración Samsung de HA crea `remote.X` y `media_player.X` con el MISMO nombre. El
    inventario cogía la primera y decía «su tipo no está en la lista verde» de una TV que sí lo está."""
    ha = [("remote.tv_sala", "Tv sala (UN43)"), ("media_player.tv_sala", "Tv sala (UN43)")]
    d = _por_ip(_inv(TV, ha=ha), "10.0.0.29")
    assert d.nivel == CONTROLABLE and d.entidad_ha == "media_player.tv_sala", (d.nivel, d.entidad_ha)


def test_CONTROL_un_parentesis_que_NO_es_su_modelo_no_casa():
    d = _por_ip(_inv(TV, ha=[("media_player.tv_sala", "Tv sala (cocina)")]), "10.0.0.29")
    assert d.nivel not in (INTEGRADO, CONTROLABLE) and d.entidad_ha is None


def test_la_TV_apagada_deja_de_anunciarse_pero_sigue_siendo_la_TV_que_ya_conoce():
    """Apagada, la TV solo responde a ARP. Lo ya identificado en esta sesión no se degrada a «desconocido»."""
    inv = InventarioEntorno()
    ha = [("media_player.tv_sala", "Tv sala (UN43)")]
    inv.actualizar([TV], entidades_ha=ha)
    inv.actualizar([Observacion(ip="10.0.0.29", mac=TV.mac, fuentes=frozenset({"arp"}))], entidades_ha=ha)
    d = _por_ip(inv, "10.0.0.29")
    assert d.tipo == "televisor" and d.nivel == CONTROLABLE, (d.tipo, d.nivel)


# ---------------------------------------------------------------------- registro vivo --


def test_registro_vivo_nuevo_ausente_y_reaparece():
    inv = InventarioEntorno()
    assert [(t.ip, t.cambio) for t in inv.actualizar([TV, ROUTER])] == [("10.0.0.1", "nuevo"), ("10.0.0.29", "nuevo")]
    assert [(t.ip, t.cambio) for t in inv.actualizar([ROUTER])] == [("10.0.0.29", "ausente")]
    assert _por_ip(inv, "10.0.0.29").presente is False, "un dispositivo ausente se olvida en vez de marcarse"
    assert [(t.ip, t.cambio) for t in inv.actualizar([TV, ROUTER])] == [("10.0.0.29", "reaparece")]


def test_sin_cambios_no_hay_transiciones():
    inv = InventarioEntorno()
    inv.actualizar([TV])
    assert inv.actualizar([TV]) == []


def test_observaciones_de_varias_fuentes_de_la_misma_IP_se_fusionan():
    parcial = Observacion(ip="10.0.0.29", servicios=frozenset({"AirPlay Remote Video"}), fuentes=frozenset({"mdns"}))
    solo_ssdp = Observacion(
        ip="10.0.0.29", tipo_upnp="MediaRenderer", fabricante="Samsung Electronics", fuentes=frozenset({"ssdp"})
    )
    d = _por_ip(_inv(parcial, solo_ssdp), "10.0.0.29")
    assert d.tipo == "televisor" and {"mdns", "ssdp"} <= set(d.fuentes)


# --------------------------------------------------------------------- lo que se cuenta --


def test_la_descripcion_separa_los_niveles_y_dice_que_falta():
    texto = describir(_inv(TV, ROUTER, RARO))
    assert "televisor" in texto and "router" in texto and "desconocido" in texto
    assert "Home Assistant" in texto, "no dice que falta para integrar la TV"


@pytest.mark.parametrize("obs", [TV, ROUTER, MOVIL, RARO])
def test_ningun_dispositivo_sin_integrar_se_presenta_como_controlable(obs):
    assert "puedo controlar" not in describir(_inv(obs)).lower()


def test_un_dispositivo_que_se_anuncia_como_TV_es_un_televisor_aunque_no_sea_MediaRenderer():
    """Medido en la casa `[EJEC]`: la segunda TV anuncia primero su servicio de compartir pantalla, no un
    MediaRenderer. Su nombre es «[TV] Samsung 6 Series (55)»: eso YA dice qué es. El normalizador borraba
    justo esa marca antes de mirarla."""
    o = Observacion(ip="10.0.0.20", nombre="[TV] Samsung 6 Series (55)", fuentes=frozenset({"ssdp"}))
    assert _por_ip(_inv(o), "10.0.0.20").tipo == "televisor"


# ------------------------------------------------ el componente y la pregunta (integración en AURA) --

from aura_skeleton import observability as obs  # noqa: E402
from aura_skeleton.core.entorno import ConocimientoDelEntorno, es_consulta_de_entorno  # noqa: E402


@pytest.mark.parametrize(
    "frase",
    [
        "¿Qué hay conectado?",
        "qué dispositivos ves",
        "Aurora, ¿qué hay en la red?",
        "¿qué conoces de tu entorno?",
        "¿qué hay a tu alrededor?",
    ],
)
def test_reconoce_la_pregunta_por_el_entorno(frase):
    assert es_consulta_de_entorno(frase)


@pytest.mark.parametrize("frase", ["¿qué hay de nuevo?", "enciende la tele", "¿cómo me llamo?", "¿qué encontraste?"])
def test_no_se_queda_frases_ajenas(frase):
    assert not es_consulta_de_entorno(frase)


def test_explorar_describe_y_deja_las_transiciones_en_el_audit_log():
    rondas = iter([[TV, ROUTER], [ROUTER]])
    c = ConocimientoDelEntorno(descubrir=lambda: next(rondas))
    marca = len(obs.audit_records())
    c.explorar("T1")
    texto = c.explorar("T2")
    cambios = [r["msg"] for r in obs.audit_records()[marca:] if r["module"] == "entorno"]
    assert any("nuevo" in m for m in cambios) and any("ausente" in m for m in cambios), cambios
    assert "AUSENTE" in texto


def test_si_Home_Assistant_no_responde_el_entorno_se_describe_igual():
    def _ha_caido():
        raise OSError("conexion rechazada")

    c = ConocimientoDelEntorno(descubrir=lambda: [TV], entidades_ha=_ha_caido)
    assert "televisor" in c.explorar("T3")


def test_si_la_red_falla_se_dice_y_no_se_inventa_nada():
    def _sin_red():
        raise OSError("red caida")

    texto = ConocimientoDelEntorno(descubrir=_sin_red).explorar("T4")
    assert "no pude" in texto.lower() and "televisor" not in texto


# ------------------------------------------------------ estado operativo (lectura de protocolo, con hora) --

from aura_skeleton.core import entorno as _entorno  # noqa: E402
from aura_skeleton.core.entorno import (  # noqa: E402
    ESTADO_DESPIERTA,
    ESTADO_EN_REPOSO,
    describir_estado_operativo,
)


def _consola(estado: str | None = None, ip: str = "10.0.0.80", **kw) -> Observacion:
    return Observacion(
        ip=ip,
        nombre="PS5-Sala",
        modelo="PS5",
        tipo_declarado="consola de videojuegos",
        identidad="AABBCCDDEEFF",
        fuentes=frozenset({"ddp"}),
        estado_operativo=estado,
        **kw,
    )


def _reloj(monkeypatch, t: float) -> None:
    monkeypatch.setattr(_entorno.time, "time", lambda: t)


def test_estado_constantes_publicas_y_sin_apagada():
    assert ESTADO_DESPIERTA == "despierta" and ESTADO_EN_REPOSO == "en_reposo"
    assert Observacion(ip="10.0.0.1").estado_operativo is None


def test_estado_se_toma_de_la_observacion_con_la_hora_de_la_lectura(monkeypatch):
    _reloj(monkeypatch, 1000.0)
    inv = InventarioEntorno()
    inv.actualizar([_consola(ESTADO_DESPIERTA)])
    d = inv.dispositivos()[0]
    assert d.estado_operativo == "despierta" and d.estado_visto == 1000.0


def test_ronda_sin_DDP_conserva_estado_y_su_hora_original(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA)])
    _reloj(monkeypatch, 1300.0)
    inv.actualizar([Observacion(ip="10.0.0.80", mac="aa:bb", fuentes=frozenset({"arp"}))])
    d = inv.dispositivos()[0]
    assert d.estado_operativo == "despierta" and d.estado_visto == 1000.0
    assert d.visto_ultimo == 1300.0  # control: la presencia sí se renovó, el estado no


def test_consola_nueva_solo_por_ARP_tiene_estado_None_y_describir_dice_desconocido():
    inv = InventarioEntorno()
    inv.actualizar([Observacion(ip="10.0.0.80", mac="aa:bb", tipo_declarado="consola de videojuegos")])
    d = inv.dispositivos()[0]
    assert d.estado_operativo is None and d.estado_visto is None
    assert "estado desconocido" in describir(inv)


def test_despierta_y_luego_620_pasa_a_en_reposo_con_hora_nueva(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA)])
    _reloj(monkeypatch, 1600.0)
    inv.actualizar([_consola(ESTADO_EN_REPOSO)])
    d = inv.dispositivos()[0]
    assert d.estado_operativo == "en_reposo" and d.estado_visto == 1600.0


def test_conflicto_de_identidad_no_adopta_el_estado_de_la_fuente_contradictoria(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA)])
    _reloj(monkeypatch, 1200.0)
    impostor = replace(_consola(ESTADO_EN_REPOSO), identidad="OTRA-IDENTIDAD")
    inv.actualizar([impostor])
    d = inv.dispositivos()[0]
    assert d.conflicto is not None
    assert d.estado_operativo == "despierta" and d.estado_visto == 1000.0


def test_ausente_conserva_ultimo_estado_y_hora(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_EN_REPOSO)])
    _reloj(monkeypatch, 1100.0)
    inv.actualizar([Observacion(ip="10.0.0.99", mac="cc:dd")])
    d = next(x for x in inv.dispositivos() if x.ip == "10.0.0.80")
    assert not d.presente and d.estado_operativo == "en_reposo" and d.estado_visto == 1000.0


def test_describir_estado_reciente_dice_segun_su_protocolo_y_que_no_es_verificacion(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA)])
    d = inv.dispositivos()[0]
    txt = describir_estado_operativo(d, ahora=1000.0 + 5 * 60)
    assert "según su protocolo" in txt and "despierta" in txt and "hace 5 min" in txt
    assert "lectura, no verificación física" in txt and "último estado conocido" not in txt
    assert "hace un momento" in describir_estado_operativo(d, ahora=1020.0)
    assert "hace 1 h" in describir_estado_operativo(
        replace(d, estado_visto=1000.0), ahora=1000.0 + 3600.0
    )  # antiguo, pero con la antigüedad en horas


def test_describir_estado_antiguo_mas_de_15_min_dice_ultimo_estado_conocido(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_EN_REPOSO)])
    d = inv.dispositivos()[0]
    txt = describir_estado_operativo(d, ahora=1000.0 + 20 * 60)
    assert "último estado conocido" in txt and "en reposo" in txt and "hace 20 min" in txt
    assert "último estado conocido" not in describir_estado_operativo(d, ahora=1000.0 + 15 * 60)


def test_describir_estado_de_ausente_es_dato_antiguo_aunque_sea_reciente(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA)])
    _reloj(monkeypatch, 1010.0)
    inv.actualizar([Observacion(ip="10.0.0.99", mac="cc:dd")])
    d = next(x for x in inv.dispositivos() if x.ip == "10.0.0.80")
    assert "último estado conocido" in describir_estado_operativo(d, ahora=1020.0)


def test_describir_estado_none_en_dispositivo_no_consola_no_dice_nada():
    inv = InventarioEntorno()
    inv.actualizar([TV])
    assert describir_estado_operativo(inv.dispositivos()[0], ahora=1.0) == ""
    assert "estado desconocido" not in describir(inv)


def test_misma_ronda_con_estados_distintos_no_adopta_ninguno_y_conserva_el_previo(monkeypatch):
    for orden in ((ESTADO_DESPIERTA, ESTADO_EN_REPOSO), (ESTADO_EN_REPOSO, ESTADO_DESPIERTA)):
        inv = InventarioEntorno()
        _reloj(monkeypatch, 1000.0)
        inv.actualizar([_consola(ESTADO_EN_REPOSO)])
        _reloj(monkeypatch, 1200.0)
        inv.actualizar([_consola(orden[0]), _consola(orden[1])])
        d = inv.dispositivos()[0]
        assert d.estado_operativo == "en_reposo" and d.estado_visto == 1000.0


def test_misma_ronda_con_estados_distintos_en_dispositivo_nuevo_queda_desconocido():
    for orden in ((ESTADO_DESPIERTA, ESTADO_EN_REPOSO), (ESTADO_EN_REPOSO, ESTADO_DESPIERTA)):
        inv = InventarioEntorno()
        inv.actualizar([_consola(orden[0]), _consola(orden[1]), _consola(orden[0])])
        d = inv.dispositivos()[0]
        assert d.estado_operativo is None and d.estado_visto is None


def test_misma_ronda_con_estados_iguales_si_se_adopta(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA), _consola(ESTADO_DESPIERTA)])
    assert inv.dispositivos()[0].estado_operativo == "despierta"


def test_dispositivo_nuevo_en_conflicto_de_identidad_no_adopta_ningun_estado_declarado(monkeypatch):
    """Caso de control: las dos declaraciones dicen «despierta»; en conflicto ninguna se adopta (solo el `resto`)."""
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_DESPIERTA), replace(_consola(ESTADO_DESPIERTA), identidad="OTRA-IDENTIDAD")])
    d = inv.dispositivos()[0]
    assert d.conflicto is not None
    assert d.estado_operativo is None and d.estado_visto is None


def test_describir_estado_antiguo_tambien_dice_que_es_lectura_no_verificacion(monkeypatch):
    inv = InventarioEntorno()
    _reloj(monkeypatch, 1000.0)
    inv.actualizar([_consola(ESTADO_EN_REPOSO)])
    txt = describir_estado_operativo(inv.dispositivos()[0], ahora=1000.0 + 20 * 60)
    assert "último estado conocido" in txt and "lectura, no verificación física" in txt
