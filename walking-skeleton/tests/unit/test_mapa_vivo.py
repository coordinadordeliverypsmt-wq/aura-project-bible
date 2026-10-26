"""Mapa vivo del entorno + presencia distribuida (misión CEO, 2026-09-27).

Diagnóstico `[EJEC]` en la casa: AURA solo veía 4-5 equipos. El pipeline no perdía nada; la pérdida
estaba en el DESCUBRIMIENTO (ARP es una caché, mDNS/SSDP solo muestran a quien se anuncia) y en la
CLASIFICACIÓN (Spotify Connect se convertía en «altavoz»: era la PS5). Estas pruebas fijan el modelo
corregido con la evidencia literal medida en la red real.
"""

from __future__ import annotations

from aura_skeleton.core.entorno import (
    CARACTERIZADO,
    CONTROLABLE,
    DESCUBIERTO,
    IDENTIFICADO,
    InventarioEntorno,
    Observacion,
    capacidades_de,
    describir,
    identificar,
)

PS5 = Observacion(
    ip="192.168.20.36",
    nombre="PS5-825",
    modelo="PS5",
    tipo_declarado="consola de videojuegos",
    identidad="ddp:0C70430CBFD1",
    fuentes=frozenset({"ddp"}),
)
SPOTIFY = Observacion(
    ip="192.168.20.36",
    nombre="SpZc-0CBFD1",
    servicios=frozenset({"_spotify-connect._tcp"}),
    fuentes=frozenset({"mdns"}),
)
DVR = Observacion(
    ip="192.168.20.80",
    nombre="NETSurveillance WEB",
    tipo_declarado="grabador de vídeo (DVR)",
    capacidades=frozenset({"video_entrada"}),
    fuentes=frozenset({"http", "rtsp"}),
)
CAMARA = Observacion(
    ip="192.168.20.110",
    tipo_declarado="cámara",
    capacidades=frozenset({"video_entrada"}),
    identidad="onvif:urn:uuid:1234",
    fuentes=frozenset({"onvif"}),
)
TV = Observacion(
    ip="192.168.20.29",
    nombre="[TV] Tv sala",
    fabricante="Samsung Electronics",
    modelo="UN43",
    tipo_upnp="MediaRenderer",
    fuentes=frozenset({"ssdp"}),
)
LOCAL = Observacion(
    ip="192.168.20.38",
    nombre="este equipo",
    tipo_declarado="computador",
    identidad="local",
    capacidades=frozenset({"audio_entrada", "audio_salida", "video_entrada", "video_salida"}),
    fuentes=frozenset({"local"}),
)
SOLO_ARP = Observacion(ip="192.168.20.32", mac="02:0b:fa:05:a2:62", fuentes=frozenset({"arp"}))


def _por_ip(inv, ip):
    return next(d for d in inv.dispositivos() if d.ip == ip)


# ------------------------------------------------------------------ clasificación honesta --


def test_spotify_connect_NO_es_un_altavoz():
    """[EJEC]: .36 anunciaba Spotify Connect y AURA decía «altavoz». Era una PS5 (DDP)."""
    assert identificar(SPOTIFY) == "desconocido"
    assert "audio_salida" in capacidades_de(SPOTIFY), "reproducir audio sí lo anuncia"


def test_la_PS5_se_identifica_por_su_propio_protocolo_y_gana_al_anuncio_de_spotify():
    inv = InventarioEntorno()
    inv.actualizar([SPOTIFY, PS5])
    d = _por_ip(inv, "192.168.20.36")
    assert d.tipo == "consola de videojuegos" and d.nombre == "PS5-825", (d.tipo, d.nombre)


def test_el_DVR_es_un_grabador_que_ofrece_video_y_esta_CARACTERIZADO():
    inv = InventarioEntorno()
    inv.actualizar([DVR])
    d = _por_ip(inv, "192.168.20.80")
    assert d.tipo == "grabador de vídeo (DVR)" and d.nivel == CARACTERIZADO and "video_entrada" in d.capacidades


def test_una_TV_que_se_anuncia_como_renderizador_ofrece_pantalla_y_sonido():
    assert {"audio_salida", "video_salida"} <= capacidades_de(TV)


def test_CONTROL_lo_que_solo_responde_a_ARP_sigue_DESCUBIERTO_y_sin_capacidades():
    inv = InventarioEntorno()
    inv.actualizar([SOLO_ARP])
    d = _por_ip(inv, "192.168.20.32")
    assert d.nivel == DESCUBIERTO and d.tipo == "desconocido" and not d.capacidades


def test_identificado_sin_capacidades_conocidas_no_se_da_por_caracterizado():
    inv = InventarioEntorno()
    inv.actualizar([PS5])
    assert _por_ip(inv, "192.168.20.36").nivel == IDENTIFICADO


def test_integrado_sigue_por_encima_de_caracterizado():
    inv = InventarioEntorno()
    inv.actualizar([TV], entidades_ha=[("media_player.tv_sala", "Tv sala (UN43)")])
    assert _por_ip(inv, "192.168.20.29").nivel == CONTROLABLE


# ----------------------------------------------------------------------- identidad viva --


def test_un_equipo_que_cambia_de_IP_por_DHCP_sigue_siendo_EL_MISMO():
    inv = InventarioEntorno()
    inv.actualizar([PS5])
    transiciones = inv.actualizar([Observacion(**{**PS5.__dict__, "ip": "192.168.20.44"})])
    assert [(t.ip, t.cambio) for t in transiciones] == [("192.168.20.44", "cambia_ip")], transiciones
    assert [d.ip for d in inv.dispositivos()] == ["192.168.20.44"], "se duplicó en vez de moverse"


def test_CONTROL_sin_identidad_declarada_otra_IP_es_otro_equipo():
    inv = InventarioEntorno()
    inv.actualizar([SOLO_ARP])
    inv.actualizar([Observacion(ip="192.168.20.33", mac=SOLO_ARP.mac, fuentes=frozenset({"arp"}))])
    assert len(inv.dispositivos()) == 2, "la MAC compartida del repetidor no es identidad"


def test_una_identidad_NUEVA_no_se_apropia_de_otro_equipo_por_compartir_la_MAC_del_repetidor():
    inv = InventarioEntorno()
    inv.actualizar([SOLO_ARP])
    inv.actualizar(
        [
            Observacion(
                ip="192.168.20.33",
                mac=SOLO_ARP.mac,
                identidad="ddp:OTRO",
                tipo_declarado="consola de videojuegos",
                fuentes=frozenset({"ddp"}),
            )
        ]
    )
    assert {d.ip for d in inv.dispositivos()} == {"192.168.20.32", "192.168.20.33"}


# ------------------------------------------------------------ presencia: modelo, no activación --


def test_la_descripcion_dice_donde_puede_estar_AURA_HOY_y_que_solo_es_posible():
    inv = InventarioEntorno()
    inv.actualizar([LOCAL, TV, CAMARA, DVR])
    texto = describir(inv)
    assert "Dónde puedo estar hoy" in texto and "este equipo" in texto.split("Dónde puedo estar hoy")[1]
    posible = texto.split("Superficies posibles")[1]
    assert "192.168.20.29" in posible and "192.168.20.110" in posible
    assert "autorización" in posible, "una cámara ajena no se presenta como utilizable"


def test_ningun_equipo_AJENO_aparece_como_superficie_disponible_hoy():
    """Ni la TV (altavoz, pantalla) ni una cámara con micrófono: describir no es poder usar."""
    camara_con_audio = Observacion(**{**CAMARA.__dict__, "capacidades": frozenset({"video_entrada", "audio_entrada"})})
    inv = InventarioEntorno()
    inv.actualizar([TV, camara_con_audio])
    hoy = describir(inv).split("Dónde puedo estar hoy")[1].split("\n")[0]
    assert "192.168.20.110" not in hoy and "192.168.20.29" not in hoy and "ninguna" in hoy, hoy


def test_sin_superficie_local_no_se_afirma_que_AURA_este_en_ningun_sitio():
    inv = InventarioEntorno()
    inv.actualizar([TV])
    hoy = describir(inv).split("Dónde puedo estar hoy")[1].split("\n")[0]
    assert "ninguna" in hoy.lower(), hoy


def test_la_descripcion_declara_como_miro_y_lo_que_no_puedo_ver():
    inv = InventarioEntorno()
    inv.actualizar([SOLO_ARP])
    texto = describir(inv)
    assert "Cómo miro" in texto and "Bluetooth" in texto
    # Solo los métodos que el descubridor REAL usa: nombrar otros sería «declarado ≠ real».
    from aura_skeleton.adapters import red_local

    fuente = open(red_local.__file__, encoding="utf-8").read()
    for metodo in ("ONVIF", "PlayStation", "RTSP"):
        assert metodo not in texto.split("Cómo miro")[1] or metodo.lower() in fuente.lower(), metodo


def test_el_equipo_local_no_se_describe_a_la_vez_como_presente_y_pendiente_de_autorizar():
    """[EJEC] demo real: «este equipo — caracterizado… falta integrarlo y autorizarlo» y a la vez «Dónde
    puedo estar hoy: este equipo». Una de las dos era falsa."""
    inv = InventarioEntorno()
    inv.actualizar([LOCAL])
    linea = next(x for x in describir(inv).splitlines() if x.startswith("• 192.168.20.38"))
    assert "donde corro" in linea and "autorizarlo" not in linea, linea
    assert "no la uso" in linea, "la cámara local existe pero no se usa hasta la decisión de visión"
