"""Capa de conocimiento del entorno (misión CEO, 2026-09-27).

AURA no es dueña de un inventario: es dueña de una CAPA DE CONOCIMIENTO. Las fuentes (ARP, mDNS, SSDP,
Home Assistant, el propio equipo, y mañana router o Bluetooth) aportan EVIDENCIA, no verdad. AURA fusiona
esa evidencia, decide a qué nivel conoce cada equipo, marca los conflictos en vez de adivinar y sabe qué
fuentes no están disponibles todavía. Los equipos reales de la casa son casos de prueba, no un inventario.
"""

from __future__ import annotations

from aura_skeleton.core.entorno import (
    AUTORIZADO,
    CARACTERIZADO,
    CONTROLABLE,
    EFECTO_VERIFICADO,
    INTEGRADO,
    NIVELES,
    ConocimientoDelEntorno,
    Fuente,
    InventarioEntorno,
    Observacion,
    describir,
)

PS5 = Observacion(
    ip="192.168.20.36",
    nombre="PS5-825",
    tipo_declarado="consola de videojuegos",
    identidad="ddp:0C70430CBFD1",
    fuentes=frozenset({"ddp"}),
)
TV = Observacion(
    ip="192.168.20.29",
    nombre="[TV] Tv sala",
    fabricante="Samsung",
    modelo="UN43",
    tipo_upnp="MediaRenderer",
    fuentes=frozenset({"ssdp"}),
)


def _por_ip(inv, ip):
    return next(d for d in inv.dispositivos() if d.ip == ip)


# --------------------------------------------------------- el orden de los estados es estricto --


def test_los_estados_van_de_menos_a_mas_conocimiento_y_no_son_sinonimos():
    assert (
        NIVELES.index(CARACTERIZADO)
        < NIVELES.index(INTEGRADO)
        < NIVELES.index(AUTORIZADO)
        < NIVELES.index(CONTROLABLE)
        < NIVELES.index(EFECTO_VERIFICADO)
    )


# ------------------------------------------------------------------- efecto verificado --


def test_un_efecto_real_verificado_sube_al_dispositivo_a_EFECTO_VERIFICADO():
    inv = InventarioEntorno()
    inv.actualizar([TV], entidades_ha=[("media_player.tv_sala", "Tv sala (UN43)")])
    assert _por_ip(inv, "192.168.20.29").nivel == CONTROLABLE
    inv.registrar_efecto("media_player.tv_sala", verificado=True)
    assert _por_ip(inv, "192.168.20.29").nivel == EFECTO_VERIFICADO


def test_un_intento_SIN_efecto_no_sube_a_EFECTO_VERIFICADO():
    inv = InventarioEntorno()
    inv.actualizar([TV], entidades_ha=[("media_player.tv_sala", "Tv sala (UN43)")])
    inv.registrar_efecto("media_player.tv_sala", verificado=False)
    assert _por_ip(inv, "192.168.20.29").nivel == CONTROLABLE


def test_el_efecto_verificado_no_se_pierde_porque_la_TV_se_apague_en_la_siguiente_ronda():
    """Verificar que puedo afectarlo es un hecho histórico: apagada (solo ARP) no se degrada por debajo."""
    inv = InventarioEntorno()
    ha = [("media_player.tv_sala", "Tv sala (UN43)")]
    inv.actualizar([TV], entidades_ha=ha)
    inv.registrar_efecto("media_player.tv_sala", verificado=True)
    inv.actualizar([Observacion(ip="192.168.20.29", mac="aa", fuentes=frozenset({"arp"}))], entidades_ha=ha)
    assert _por_ip(inv, "192.168.20.29").nivel == EFECTO_VERIFICADO


def test_registrar_un_efecto_sobre_una_entidad_que_no_conozco_no_inventa_un_dispositivo():
    inv = InventarioEntorno()
    inv.registrar_efecto("media_player.fantasma", verificado=True)
    assert inv.dispositivos() == []


# ------------------------------------------------------------------- conflicto, no adivinar --


def test_dos_fuentes_que_dan_TIPOS_distintos_para_la_misma_IP_marcan_conflicto():
    inv = InventarioEntorno()
    inv.actualizar([PS5])
    inv.actualizar([Observacion(ip="192.168.20.36", tipo_declarado="cámara", fuentes=frozenset({"onvif"}))])
    d = _por_ip(inv, "192.168.20.36")
    assert d.conflicto is not None and "cámara" in d.conflicto and "consola" in d.conflicto
    assert d.tipo == "consola de videojuegos", "el conflicto PISÓ el tipo anterior en vez de conservarlo"
    assert "conflicto" in describir(inv).lower()


def test_CONTROL_la_misma_fuente_repetida_no_es_conflicto():
    inv = InventarioEntorno()
    inv.actualizar([PS5])
    inv.actualizar([PS5])
    assert _por_ip(inv, "192.168.20.36").conflicto is None


def test_dos_identidades_declaradas_distintas_en_la_misma_IP_son_conflicto():
    inv = InventarioEntorno()
    inv.actualizar([PS5])
    inv.actualizar(
        [
            Observacion(
                ip="192.168.20.36",
                identidad="ddp:OTRA",
                tipo_declarado="consola de videojuegos",
                fuentes=frozenset({"ddp"}),
            )
        ]
    )
    assert _por_ip(inv, "192.168.20.36").conflicto is not None


# ------------------------------------------------ fuentes de evidencia y su disponibilidad --


def test_la_descripcion_declara_las_fuentes_bloqueadas_sin_fingir_que_no_existen():
    fuentes = [
        Fuente("Home Assistant", "activa"),
        Fuente("router", "no_autorizada", "requiere que entres"),
        Fuente("Bluetooth", "bloqueada", "apagado por software en este equipo"),
    ]
    c = ConocimientoDelEntorno(descubrir=lambda: [PS5], fuentes=fuentes)
    texto = c.explorar("T")
    assert "router" in texto and "no_autorizada".replace("_", " ") in texto.replace("_", " ")
    assert "Bluetooth" in texto and "bloqueada" in texto


def test_una_fuente_que_falla_se_declara_pero_no_tumba_la_exploracion():
    def _revienta():
        raise OSError("avahi no está")

    fuentes = [Fuente("mDNS", "activa")]
    c = ConocimientoDelEntorno(descubrir=lambda: [PS5], fuentes=fuentes, entidades_ha=_revienta_marca(_revienta))
    texto = c.explorar("T")
    assert "192.168.20.36" in texto  # la ronda no muere porque una fuente caiga


def _revienta_marca(fn):
    def _f():
        return fn()

    return _f


# ------------------------------------ vía legítima de integración, sin sondear (resolución de fallos) --

from aura_skeleton.core.entorno import via_de_integracion  # noqa: E402

DVR = Observacion(
    ip="192.168.20.80",
    tipo_declarado="grabador de vídeo (DVR)",
    capacidades=frozenset({"video_entrada"}),
    fuentes=frozenset({"http", "rtsp"}),
)
CAMARA = Observacion(
    ip="192.168.20.110", tipo_declarado="cámara", capacidades=frozenset({"video_entrada"}), fuentes=frozenset({"onvif"})
)


def _dispo(obs, ha=()):
    inv = InventarioEntorno()
    inv.actualizar([obs], entidades_ha=list(ha))
    return _por_ip(inv, obs.ip)


def test_una_TV_no_integrada_propone_el_emparejamiento_con_confirmacion_fisica():
    via, falta = via_de_integracion(_dispo(TV))
    assert "Home Assistant" in via and ("Permitir" in falta or "físic" in falta.lower())


def test_una_camara_propone_ONVIF_RTSP_y_recuerda_la_decision_de_vision():
    via, falta = via_de_integracion(_dispo(CAMARA))
    assert ("ONVIF" in via or "RTSP" in via) and ("credencial" in falta and "visión" in falta.lower())


def test_el_DVR_se_trata_como_camara_grabador_no_como_metodo_desconocido():
    via, _falta = via_de_integracion(_dispo(DVR))
    assert "ONVIF" in via or "RTSP" in via or "cámara" in via.lower()


def test_lo_que_solo_responde_a_ARP_declara_metodo_de_conexion_DESCONOCIDO():
    via, falta = via_de_integracion(_dispo(Observacion(ip="192.168.20.32", mac="aa", fuentes=frozenset({"arp"}))))
    assert "desconocido" in via.lower() and "anuncie" in falta.lower()


def test_un_equipo_YA_integrado_no_tiene_via_pendiente():
    d = _dispo(TV, ha=[("media_player.tv_sala", "Tv sala (UN43)")])
    assert via_de_integracion(d) is None


def test_la_descripcion_dice_como_conectar_lo_que_aun_no_controla_sin_prometer_control():
    inv = InventarioEntorno()
    inv.actualizar([CAMARA, DVR])
    texto = describir(inv)
    bloque = texto.split("Cómo conectar")[1].split("Cómo miro")[0]
    assert "192.168.20.110" in bloque and "192.168.20.80" in bloque
    assert "falta" in bloque.lower()


def test_CONTROL_lo_ya_controlable_no_aparece_en_como_conectar():
    inv = InventarioEntorno()
    inv.actualizar([TV], entidades_ha=[("media_player.tv_sala", "Tv sala (UN43)")])
    texto = describir(inv)
    if "Cómo conectar" in texto:
        assert "192.168.20.29" not in texto.split("Cómo conectar")[1]


LOCAL = Observacion(
    ip="192.168.20.38",
    nombre="este equipo",
    tipo_declarado="computador",
    identidad="local",
    capacidades=frozenset({"audio_entrada", "audio_salida", "video_entrada"}),
    fuentes=frozenset({"local"}),
)


def test_el_equipo_LOCAL_no_se_propone_como_camara_DVR_a_integrar_por_home_assistant():
    """[EJEC] demo real: el propio equipo, por tener webcam (video_entrada), se ofrecía como «cámara/DVR
    por ONVIF/RTSP». No es algo a integrar por HA: es la superficie de AURA, tras la decisión de visión."""
    inv = InventarioEntorno()
    inv.actualizar([LOCAL])
    texto = describir(inv)
    if "Cómo conectar" in texto:
        assert "192.168.20.38" not in texto.split("Cómo conectar")[1].split("Cómo miro")[0]


# ------------------------------------- envenenamiento por una declaración UDP (revisión ECC 2026-10-22) --


def test_una_declaracion_que_contradice_el_tipo_ya_deducido_es_conflicto_y_no_pisa_tipo_ni_nombre():
    """ALTO de security-reviewer: un ProbeMatch falso (UDP, sin autenticar) en la IP de la TV la reescribía como
    «cámara» y le cambiaba el nombre, que luego sirve para casar con entidades de HA. Ahora se marca y no se elige."""
    inv = InventarioEntorno()
    inv.actualizar([TV])
    antes = _por_ip(inv, "192.168.20.29")
    tipo, nombre = antes.tipo, antes.nombre
    falso = Observacion(
        ip="192.168.20.29",
        nombre="Impostor",
        tipo_declarado="cámara",
        identidad="urn:uuid:x",
        fuentes=frozenset({"onvif"}),
    )

    inv.actualizar([TV, falso])
    inv.actualizar([falso])

    d = _por_ip(inv, "192.168.20.29")
    assert d.conflicto is not None and "cámara" in d.conflicto, d.conflicto
    assert d.tipo == tipo and d.nombre == nombre, (d.tipo, d.nombre)


def test_CONTROL_una_declaracion_sobre_algo_que_solo_respondia_a_ARP_si_lo_identifica():
    inv = InventarioEntorno()
    inv.actualizar([Observacion(ip="192.168.20.110", mac="88:e6:28:bb:69:c1", fuentes=frozenset({"arp"}))])
    inv.actualizar(
        [
            Observacion(
                ip="192.168.20.110", tipo_declarado="cámara", identidad="urn:uuid:c", fuentes=frozenset({"onvif"})
            )
        ]
    )
    d = _por_ip(inv, "192.168.20.110")
    assert d.tipo == "cámara" and d.conflicto is None


# --------------------------- fusión DENTRO de una ronda (limitación MEDIA de security-reviewer, 2026-10-22) --
#: Un ProbeMatch falso (UDP, sin autenticar) que llega en la MISMA ronda que el anuncio real de la TV.
_FALSO_EN_LA_TV = Observacion(
    ip="192.168.20.29",
    nombre="Congelador",
    tipo_declarado="cámara",
    identidad="urn:uuid:impostor",
    capacidades=frozenset({"video_entrada"}),
    fuentes=frozenset({"onvif"}),
)
_HA = [("media_player.tv_sala", "Tv sala"), ("switch.congelador", "Congelador")]


def _tv_tras(*rondas, entidades=()):
    inv = InventarioEntorno()
    for ronda in rondas:
        inv.actualizar(list(ronda), entidades_ha=entidades)
    return _por_ip(inv, "192.168.20.29")


def test_en_la_misma_ronda_el_ProbeMatch_falso_NO_reescribe_la_TV_y_queda_en_conflicto():
    d = _tv_tras([TV, _FALSO_EN_LA_TV])
    assert d.tipo == "televisor" and d.nombre == TV.nombre, (d.tipo, d.nombre)
    assert d.conflicto is not None and "cámara" in d.conflicto, d.conflicto
    assert d.identidad != "urn:uuid:impostor" and "video_entrada" not in d.capacidades


def test_el_resultado_no_depende_del_orden_de_llegada():
    a, b = _tv_tras([TV, _FALSO_EN_LA_TV]), _tv_tras([_FALSO_EN_LA_TV, TV])
    assert (a.tipo, a.nombre, a.identidad, a.capacidades) == (b.tipo, b.nombre, b.identidad, b.capacidades)
    assert a.conflicto is not None and b.conflicto is not None


def test_una_etiqueta_falsa_no_se_convierte_en_la_entidad_de_control():
    """El nombre declarado por el impostor casaría con `switch.congelador`; no puede sustituir la entidad de la TV."""
    d = _tv_tras([TV, _FALSO_EN_LA_TV], [TV, _FALSO_EN_LA_TV], entidades=_HA)
    assert d.entidad_ha == "media_player.tv_sala", d.entidad_ha


def test_el_impostor_repetido_ronda_tras_ronda_sigue_sin_ganar():
    d = _tv_tras([TV, _FALSO_EN_LA_TV], [TV, _FALSO_EN_LA_TV], [_FALSO_EN_LA_TV], [TV])
    assert d.tipo == "televisor" and d.nombre == TV.nombre and d.conflicto is not None


def test_dos_declaraciones_distintas_en_la_misma_ronda_no_eligen_ninguna():
    ip = "192.168.20.50"
    consola = Observacion(ip=ip, tipo_declarado="consola de videojuegos", identidad="ddp:A", fuentes=frozenset({"ddp"}))
    camara = Observacion(ip=ip, tipo_declarado="cámara", identidad="urn:uuid:B", fuentes=frozenset({"onvif"}))
    inv = InventarioEntorno()
    inv.actualizar([Observacion(ip=ip, mac="aa:bb:cc:dd:ee:ff", fuentes=frozenset({"arp"})), consola, camara])
    d = _por_ip(inv, ip)
    assert d.conflicto is not None and d.tipo not in ("cámara", "consola de videojuegos"), (d.tipo, d.conflicto)


def test_CONTROL_la_camara_legitima_en_la_misma_ronda_que_su_ARP_se_identifica_y_su_identidad_se_conserva():
    ip = "192.168.20.110"
    arp = Observacion(ip=ip, mac="88:e6:28:bb:69:c1", fuentes=frozenset({"arp"}))
    onvif = Observacion(
        ip=ip,
        tipo_declarado="cámara",
        identidad="urn:uuid:c",
        capacidades=frozenset({"video_entrada"}),
        fuentes=frozenset({"onvif"}),
    )
    inv = InventarioEntorno()
    for ronda in ([arp, onvif], [onvif, arp], [onvif], [arp]):
        inv.actualizar(list(ronda))
    d = _por_ip(inv, ip)
    assert d.tipo == "cámara" and d.identidad == "urn:uuid:c" and d.conflicto is None
    assert "video_entrada" in d.capacidades


def test_CONTROL_la_PS5_que_solo_anuncia_spotify_se_identifica_por_su_DDP():
    """Caso legítimo del comentario de entorno.py: el servicio que publica NO da tipo; su protocolo propio sí."""
    ip = "192.168.20.36"
    mdns = Observacion(
        ip=ip, nombre="PS5-825", servicios=frozenset({"_spotify-connect._tcp"}), fuentes=frozenset({"mdns"})
    )
    inv = InventarioEntorno()
    inv.actualizar([mdns, PS5])
    d = _por_ip(inv, ip)
    assert d.tipo == "consola de videojuegos" and d.conflicto is None


def test_CONTROL_el_mismo_anuncio_repetido_en_la_ronda_no_es_conflicto():
    d = _tv_tras([TV, TV, TV])
    assert d.conflicto is None and d.tipo == "televisor"


def test_dos_declaraciones_del_mismo_tipo_con_identidades_distintas_en_la_ronda_son_conflicto():
    ip = "192.168.20.51"
    a = Observacion(ip=ip, tipo_declarado="cámara", identidad="urn:uuid:A", fuentes=frozenset({"onvif"}))
    b = Observacion(ip=ip, tipo_declarado="cámara", identidad="urn:uuid:B", fuentes=frozenset({"onvif"}))
    inv = InventarioEntorno()
    inv.actualizar([a, b])
    d = _por_ip(inv, ip)
    assert d.conflicto is not None and d.identidad not in ("urn:uuid:A", "urn:uuid:B"), (d.identidad, d.conflicto)


def test_F2_dos_tipos_declarados_distintos_sin_identidad_ni_base_son_conflicto():
    ip = "192.168.20.52"
    inv = InventarioEntorno()
    inv.actualizar(
        [
            Observacion(ip=ip, tipo_declarado="cámara", fuentes=frozenset({"onvif"})),
            Observacion(ip=ip, tipo_declarado="consola de videojuegos", fuentes=frozenset({"ddp"})),
        ]
    )
    d = _por_ip(inv, ip)
    assert d.conflicto is not None and d.tipo == "desconocido", (d.tipo, d.conflicto)


def test_F8_un_conflicto_de_la_ronda_se_marca_en_un_dispositivo_YA_existente():
    ip = "192.168.20.53"
    inv = InventarioEntorno()
    inv.actualizar([Observacion(ip=ip, mac="aa:bb:cc:dd:ee:01", fuentes=frozenset({"arp"}))])
    assert _por_ip(inv, ip).conflicto is None
    inv.actualizar(
        [
            Observacion(ip=ip, tipo_declarado="cámara", fuentes=frozenset({"onvif"})),
            Observacion(ip=ip, tipo_declarado="consola de videojuegos", fuentes=frozenset({"ddp"})),
        ]
    )
    assert _por_ip(inv, ip).conflicto is not None


def test_F9_entre_fuentes_que_no_declaran_el_primer_nombre_no_se_pisa_en_ningun_orden():
    ip = "192.168.20.54"
    ssdp = Observacion(ip=ip, nombre="[TV] Sala", tipo_upnp="MediaRenderer", fuentes=frozenset({"ssdp"}))
    spotify = Observacion(
        ip=ip, nombre="Altavoz Spotify", servicios=frozenset({"_spotify-connect._tcp"}), fuentes=frozenset({"mdns"})
    )
    for primero, segundo in ((ssdp, spotify), (spotify, ssdp)):
        inv = InventarioEntorno()
        inv.actualizar([primero, segundo])
        assert _por_ip(inv, ip).nombre == primero.nombre


def test_D14_la_TV_establecida_resiste_tres_rondas_de_impostor_solo():
    """Sin el SSDP real en esas rondas: el impostor no gana por insistencia (lo enmascaraba el conflicto heredado)."""
    d = _tv_tras([TV], [_FALSO_EN_LA_TV], [_FALSO_EN_LA_TV], [_FALSO_EN_LA_TV])
    assert d.tipo == "televisor" and d.nombre == TV.nombre and d.identidad != "urn:uuid:impostor", (d.tipo, d.nombre)
    assert "video_entrada" not in d.capacidades


def test_un_nombre_que_SOLO_declara_una_fuente_UDP_no_casa_con_una_entidad_de_HA():
    """security-reviewer 2026-10-22: en una IP silenciosa (solo ARP), un impostor que declara el nombre de la TV la
    convertía en CONTROLABLE y `describir` decía en voz alta que la controlo (INV-9). La etiqueta no da control."""
    ip = "192.168.20.60"
    inv = InventarioEntorno()
    inv.actualizar(
        [
            Observacion(ip=ip, mac="aa:bb:cc:dd:ee:60", fuentes=frozenset({"arp"})),
            Observacion(ip=ip, nombre="Tv sala", tipo_declarado="cámara", fuentes=frozenset({"onvif"})),
        ],
        entidades_ha=_HA,
    )
    d = _por_ip(inv, ip)
    assert d.entidad_ha is None and d.nivel != CONTROLABLE, (d.entidad_ha, d.nivel)


def test_CONTROL_la_TV_con_su_SSDP_sigue_casando_con_su_entidad():
    d = _tv_tras([TV], entidades=_HA)
    assert d.entidad_ha == "media_player.tv_sala" and d.nivel == CONTROLABLE


def test_con_solo_declaraciones_en_conflicto_se_conserva_la_evidencia_sin_adoptar_nada():
    """code-reviewer 2026-10-22: la observación quedaba vacía y se perdían fuentes y MAC."""
    ip = "192.168.20.61"
    inv = InventarioEntorno()
    inv.actualizar(
        [
            Observacion(
                ip=ip, mac="aa:bb:cc:dd:ee:61", tipo_declarado="cámara", nombre="X", fuentes=frozenset({"onvif"})
            ),
            Observacion(ip=ip, tipo_declarado="consola de videojuegos", nombre="Y", fuentes=frozenset({"ddp"})),
        ]
    )
    d = _por_ip(inv, ip)
    assert d.fuentes == frozenset({"onvif", "ddp"}) and d.mac == "aa:bb:cc:dd:ee:61", (d.fuentes, d.mac)
    assert d.tipo == "desconocido" and d.nombre is None and d.identidad is None and d.conflicto is not None
