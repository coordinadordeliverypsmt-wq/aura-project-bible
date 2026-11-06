"""Descubrimiento REAL de la red local, solo pasivo o dirigido (semana 2). Datos sintéticos con formato real."""

from __future__ import annotations

from aura_skeleton.adapters import red_local
from aura_skeleton.adapters.red_local import (
    descubrir,
    informacion_onvif,
    leer_mdns,
    leer_vecinos,
    observacion_ddp,
    observacion_ssdp,
    observacion_wsd,
    parsear_informacion_onvif,
)

#: Dobles de las búsquedas WSD/DDP: ninguna prueba envía tráfico real a la red.
_SIN_RED = {"buscar_wsd": lambda: [], "buscar_ddp": lambda: [], "informacion": lambda ip, xaddr: None}

VECINOS = """10.0.0.29 dev wlan0 lladdr 02:aa:bb:cc:dd:ee STALE
10.0.0.1 dev wlan0 lladdr 14:00:00:00:00:20 REACHABLE
10.0.0.77 dev wlan0  FAILED
fe80::1 dev wlan0 lladdr 14:00:00:00:00:20 router REACHABLE
"""

MDNS = """+;wlan0;IPv4;Tv\\032sala;AirPlay Remote Video;local
=;wlan0;IPv4;Tv\\032sala;AirPlay Remote Video;local;TIZEN.local;10.0.0.29;43447;"x=1"
=;wlan0;IPv6;router;SSH Remote Terminal;local;router.local;2800::20;22;
"""

DESCRIPCION = """<root><device><deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
<friendlyName>[TV] Tv sala</friendlyName><manufacturer>Samsung Electronics</manufacturer>
<modelName>UN43</modelName></device></root>"""


def test_vecinos_ARP_validos_y_solo_IPv4():
    obs = leer_vecinos(VECINOS)
    assert [(o.ip, o.mac) for o in obs] == [("10.0.0.29", "02:aa:bb:cc:dd:ee"), ("10.0.0.1", "14:00:00:00:00:20")]


def test_mdns_decodifica_nombres_y_servicios():
    (o,) = leer_mdns(MDNS)
    assert o.ip == "10.0.0.29" and o.nombre == "Tv sala" and "AirPlay Remote Video" in o.servicios


def test_ssdp_lee_la_descripcion_que_publica_el_dispositivo():
    o = observacion_ssdp("10.0.0.29", "http://10.0.0.29:9197/dmr", leer=lambda url: DESCRIPCION)
    assert o.tipo_upnp == "MediaRenderer" and o.fabricante == "Samsung Electronics" and o.nombre == "[TV] Tv sala"


def test_ssdp_NO_sigue_una_descripcion_que_apunta_a_OTRA_maquina():
    """SSRF: un anuncio SSDP es texto que cualquiera en la red puede enviar. Si su LOCATION apunta a otra
    máquina —interna o externa—, AURA no la pide: se queda con la IP del que respondió y nada más."""
    pedidas = []
    o = observacion_ssdp(
        "10.0.0.29", "http://169.254.169.254/latest/meta-data", leer=lambda url: pedidas.append(url) or DESCRIPCION
    )
    assert pedidas == [] and o.tipo_upnp is None and "ssdp" in o.fuentes


def test_una_descripcion_ilegible_no_rompe_el_descubrimiento():
    o = observacion_ssdp("10.0.0.29", "http://10.0.0.29:9197/dmr", leer=lambda url: "<<no es xml")
    assert o.ip == "10.0.0.29" and o.tipo_upnp is None


def test_descubrir_junta_las_tres_fuentes_y_tolera_que_una_falle():
    def _ejecutar(orden, **kw):
        class R:
            stdout = VECINOS if orden[0] == "ip" else (_ for _ in ()).throw(FileNotFoundError("sin avahi"))

        return R()

    obs = descubrir(
        ejecutar=_ejecutar,
        buscar_ssdp=lambda: [("10.0.0.29", "http://10.0.0.29/d")],
        leer=lambda url: DESCRIPCION,
        **_SIN_RED,
    )
    fuentes = {f for o in obs for f in o.fuentes}
    assert {"arp", "ssdp"} <= fuentes, "una fuente caida tumbo el descubrimiento entero"


def test_mdns_conserva_lo_oido_aunque_avahi_agote_su_tope():
    """Medido `[EJEC]`: `avahi-browse` resolviendo todo supera cualquier tope razonable y, con el tope de
    `subprocess`, la salida se PERDÍA entera. Con `timeout` externo, lo oído hasta el tope se conserva."""
    visto = {}

    def _ejecutar(orden, **kw):
        visto.setdefault("ordenes", []).append(orden)

        class R:
            stdout = MDNS if "avahi-browse" in orden else ""
            returncode = 124 if "avahi-browse" in orden else 0

        return R()

    obs = descubrir(ejecutar=_ejecutar, buscar_ssdp=lambda: [], leer=lambda url: "", **_SIN_RED)
    avahi = next(o for o in visto["ordenes"] if "avahi-browse" in o)
    assert avahi[0] == "timeout", f"avahi sin tope externo: {avahi}"
    assert any("mdns" in o.fuentes for o in obs), "lo oido por mDNS se perdio"


def test_se_leen_TODAS_las_descripciones_que_anuncia_una_IP():
    """La misma TV anuncia varias descripciones (pantalla compartida, renderizador…). Quedarse con la primera
    perdía justo la que decía qué era."""
    leidas = []
    descubrir(
        ejecutar=lambda o, **k: type("R", (), {"stdout": "", "returncode": 0})(),
        buscar_ssdp=lambda: [("10.0.0.20", "http://10.0.0.20:9119/a"), ("10.0.0.20", "http://10.0.0.20:9197/dmr")],
        leer=lambda url: leidas.append(url) or DESCRIPCION,
        **_SIN_RED,
    )
    assert len(leidas) == 2


def test_una_fuente_caida_no_revienta_su_hilo_con_una_traza():
    """Lo que de verdad protege el `except` de cada fuente (encontrado por S2-M13, que sobrevivía): cada una
    corre en su hilo, así que un fallo sin capturar no tumba la ronda, pero SÍ vuelca una traza en la
    pantalla de quien está conversando con AURA."""
    import threading

    vistas = []
    anterior = threading.excepthook
    threading.excepthook = lambda args: vistas.append(args.exc_value)
    try:

        def _ejecutar(orden, **kw):
            raise FileNotFoundError(f"no instalado: {orden[0]}")

        descubrir(ejecutar=_ejecutar, buscar_ssdp=lambda: [], leer=lambda url: "", **_SIN_RED)
    finally:
        threading.excepthook = anterior
    assert vistas == [], f"una fuente caida revento su hilo: {vistas}"


# ------------------------------------- hallazgos ALTOS de la auditoría independiente (semana 2) --


def test_una_descripcion_que_REDIRIGE_a_otra_maquina_no_se_sigue():
    """ALTO de la auditoría: `urllib` sigue los 302 solo; un dispositivo hostil pasaba la comprobación de
    host y redirigía a AURA a otra máquina. Se prueba el COMPORTAMIENTO con un servidor real: el destino
    de la redirección nunca recibe la petición."""
    import http.server
    import threading

    import pytest as _pytest

    from aura_skeleton.adapters.red_local import _leer_url

    pedidas = []

    class _Servidor(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            pedidas.append(self.path)
            if self.path == "/descripcion":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.2:{self.server.server_port}/secreto")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<root/>")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("0.0.0.0", 0), _Servidor)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    try:
        with _pytest.raises(OSError):
            _leer_url(f"http://127.0.0.1:{srv.server_port}/descripcion")
    finally:
        srv.shutdown()
    assert "/secreto" not in pedidas, f"se siguio la redireccion hacia otra maquina: {pedidas}"


def test_un_XML_con_entidades_se_rechaza_sin_expandirlo():
    """ALTO: «billion laughs». Un DOCTYPE de pocos KB se expandía a gigas al parsear."""
    bomba = (
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;">]>'
        "<root><device><friendlyName>&b;</friendlyName></device></root>"
    )
    o = observacion_ssdp("10.0.0.29", "http://10.0.0.29:9197/dmr", leer=lambda url: bomba)
    assert o.nombre is None and o.tipo_upnp is None


def test_un_nombre_anunciado_enorme_o_con_caracteres_de_control_se_acota():
    """BAJO: el nombre lo pone quien se anuncia; acaba en la pantalla y en la voz de AURA."""
    desc = DESCRIPCION.replace("[TV] Tv sala", "[TV] " + "x" * 500 + "\u202e")
    o = observacion_ssdp("10.0.0.29", "http://10.0.0.29:9197/dmr", leer=lambda url: desc)
    assert len(o.nombre) <= 60 and "\u202e" not in o.nombre


# ------------------------------------------- el propio equipo como superficie (mapa vivo) --

_ADDR = "2: wlp0s12f0    inet 192.168.20.38/24 brd 192.168.20.255 scope global dynamic wlp0s12f0\n"
_FUENTES_AUDIO = "72\talsa_output.pci.analog-stereo.monitor\tPipeWire\n73\talsa_input.pci.analog-stereo\tPipeWire\n"
_SALIDAS_AUDIO = "72\talsa_output.pci.analog-stereo\tPipeWire\n"


def _ejecutar_local(fuentes=_FUENTES_AUDIO, salidas=_SALIDAS_AUDIO):
    def _ejecutar(orden, **kw):
        class R:
            stdout = {"ip": _ADDR, "sources": fuentes, "sinks": salidas}[orden[0] if orden[0] == "ip" else orden[-1]]

        return R()

    return _ejecutar


def test_el_equipo_local_declara_lo_que_su_hardware_tiene_de_verdad():
    from aura_skeleton.adapters.red_local import equipo_local

    o = equipo_local(_ejecutar_local(), camaras=lambda: ["/dev/video0"])
    assert o.ip == "192.168.20.38" and "local" in o.fuentes and o.tipo_declarado == "computador"
    assert o.capacidades == frozenset({"audio_entrada", "audio_salida", "video_entrada"}), o.capacidades


def test_CONTROL_un_monitor_de_salida_NO_es_un_microfono():
    """PipeWire lista el «.monitor» de cada salida como fuente: no es un micrófono."""
    from aura_skeleton.adapters.red_local import equipo_local

    o = equipo_local(_ejecutar_local(fuentes="72\talsa_output.x.monitor\tPipeWire\n"), camaras=lambda: [])
    assert "audio_entrada" not in o.capacidades and "video_entrada" not in o.capacidades, o.capacidades


# --------------------------------------------- fuentes preparadas pero no disponibles (mapa vivo) --


def test_bluetooth_bloqueado_por_software_se_declara_bloqueado_sin_fingir_que_no_hay_wearables():
    from aura_skeleton.adapters.red_local import estado_de_fuentes

    def _ejecutar(orden, **kw):
        class R:
            stdout = "0: hci0: Bluetooth\n\tSoft blocked: yes\n\tHard blocked: no\n"

        return R()

    fuentes = {f.nombre: f for f in estado_de_fuentes(_ejecutar)}
    assert fuentes["Bluetooth"].estado == "bloqueada" and "software" in fuentes["Bluetooth"].detalle


def test_el_router_es_una_fuente_preparada_pero_NO_autorizada_por_defecto():
    from aura_skeleton.adapters.red_local import estado_de_fuentes

    fuentes = {f.nombre: f for f in estado_de_fuentes(lambda *a, **k: type("R", (), {"stdout": ""})())}
    assert fuentes["router"].estado == "no_autorizada"


def test_CONTROL_con_bluetooth_encendido_no_se_declara_bloqueado():
    from aura_skeleton.adapters.red_local import estado_de_fuentes

    def _ejecutar(orden, **kw):
        class R:
            stdout = "0: hci0: Bluetooth\n\tSoft blocked: no\n\tHard blocked: no\n"

        return R()

    fuentes = {f.nombre: f for f in estado_de_fuentes(_ejecutar)}
    assert fuentes["Bluetooth"].estado != "bloqueada"


# --- WS-Discovery (ONVIF) y DDP (PlayStation): descubrimiento dirigido, sin credenciales ---

PROBEMATCH = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
<s:Body><d:ProbeMatches><d:ProbeMatch>
<a:EndpointReference><a:Address>urn:uuid:11111111-2222-3333-4444-555555555555</a:Address></a:EndpointReference>
<d:Types>dn:NetworkVideoTransmitter tds:Device</d:Types>
<d:Scopes>onvif://www.onvif.org/type/video_encoder onvif://www.onvif.org/name/Camara%20patio onvif://www.onvif.org/hardware/IPC-X1</d:Scopes>
<d:XAddrs>http://10.0.0.50/onvif/device_service</d:XAddrs>
</d:ProbeMatch></d:ProbeMatches></s:Body></s:Envelope>"""


def test_wsd_un_ProbeMatch_de_camara_declara_tipo_identidad_y_nombre():
    o = observacion_wsd("10.0.0.50", PROBEMATCH)
    assert o is not None
    assert o.tipo_declarado == "cámara" and o.capacidades == frozenset({"video_entrada"})
    assert o.identidad == "urn:uuid:11111111-2222-3333-4444-555555555555"
    assert o.nombre == "Camara patio" and o.modelo == "IPC-X1"
    assert o.fuentes == frozenset({"onvif"}) and o.mac is None


def test_wsd_un_ProbeMatch_que_no_es_videocamara_no_declara_tipo():
    o = observacion_wsd("10.0.0.50", PROBEMATCH.replace("NetworkVideoTransmitter", "Printer"))
    assert o is not None and o.tipo_declarado is None and not o.capacidades


def test_wsd_rechaza_DOCTYPE_y_ENTITY_sin_expandirlos():
    hostil = '<!DOCTYPE x [<!ENTITY a "jaja">]>' + PROBEMATCH
    assert observacion_wsd("10.0.0.50", hostil) is None
    assert observacion_wsd("10.0.0.50", PROBEMATCH.replace("<s:Body>", '<!ENTITY a "b"><s:Body>')) is None


def test_wsd_rechaza_cuerpos_de_mas_de_64KB():
    assert observacion_wsd("10.0.0.50", PROBEMATCH + " " * 70_000) is None


def test_wsd_un_XML_que_no_es_WSD_o_esta_roto_da_None():
    assert observacion_wsd("10.0.0.50", "<html><body>hola</body></html>") is None
    assert observacion_wsd("10.0.0.50", "<s:Envelope><sin cerrar") is None
    assert observacion_wsd("10.0.0.50", "") is None


def test_wsd_un_nombre_con_control_o_enorme_se_acota():
    sucio = PROBEMATCH.replace("Camara%20patio", "Cam%00%07ara" + "x" * 200)
    o = observacion_wsd("10.0.0.50", sucio)
    assert o is not None and o.nombre is not None
    assert o.nombre.isprintable() and len(o.nombre) <= 60 and o.nombre.startswith("Camara")


def test_wsd_NO_sigue_los_XAddrs(monkeypatch):
    import urllib.request

    def _prohibido(*a, **k):
        raise AssertionError("WSD no debe abrir ninguna URL")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _prohibido)
    assert observacion_wsd("10.0.0.50", PROBEMATCH) is not None


DDP_200 = (
    "HTTP/1.1 200 Ok\nhost-id:AABBCCDDEEFF\nhost-type:PS5\nhost-name:PS5-Sala\n"
    "host-request-port:997\ndevice-discovery-protocol-version:00030010\n"
    "running-app-name:Juego Secreto de la Familia\nrunning-app-titleid:CUSA99999\n"
)
DDP_620 = "HTTP/1.1 620 Server Standby\nhost-id:AABBCCDDEEFF\nhost-type:PS4\nhost-name:PS4-Cuarto\n"


def test_ddp_200_declara_consola_con_nombre_modelo_e_identidad():
    o = observacion_ddp("10.0.0.80", DDP_200)
    assert o is not None
    assert o.tipo_declarado == "consola de videojuegos" and o.modelo == "PS5" and o.nombre == "PS5-Sala"
    assert o.identidad == "AABBCCDDEEFF" and o.fuentes == frozenset({"ddp"}) and o.mac is None


def test_ddp_620_en_reposo_tambien_es_consola():
    o = observacion_ddp("10.0.0.81", DDP_620)
    assert (
        o is not None
        and o.tipo_declarado == "consola de videojuegos"
        and o.modelo == "PS4"
        and o.nombre == "PS4-Cuarto"
    )


def test_ddp_PRIVACIDAD_la_app_en_ejecucion_no_aparece_en_ningun_campo():
    o = observacion_ddp("10.0.0.80", DDP_200)
    assert o is not None
    volcado = repr(o)
    for secreto in ("Juego Secreto", "CUSA99999", "running-app"):
        assert secreto not in volcado


def test_ddp_texto_que_no_es_DDP_o_consola_desconocida_da_None():
    assert observacion_ddp("10.0.0.80", "HTTP/1.1 404 Not Found\nhost-type:PS5\n") is None
    assert observacion_ddp("10.0.0.80", "hola mundo") is None
    assert observacion_ddp("10.0.0.80", "HTTP/1.1 200 Ok\nhost-type:Xbox\n") is None
    assert observacion_ddp("10.0.0.80", "") is None


def test_ddp_un_nombre_con_control_se_acota():
    o = observacion_ddp("10.0.0.80", DDP_200.replace("PS5-Sala", "PS5\x07" + "y" * 200))
    assert o is not None and o.nombre is not None and o.nombre.isprintable() and len(o.nombre) <= 60


def test_descubrir_integra_WSD_y_DDP_con_dobles_y_tolera_que_fallen():
    def _ejecutar(orden, **kw):
        class R:
            stdout = ""

        return R()

    obs = descubrir(
        ejecutar=_ejecutar,
        buscar_ssdp=lambda: [],
        leer=lambda url: "",
        buscar_wsd=lambda: [("10.0.0.50", PROBEMATCH), ("10.0.0.51", "<basura/>")],
        buscar_ddp=lambda: [("10.0.0.80", DDP_200)],
        informacion=lambda ip, xaddr: None,
    )
    por_ip = {o.ip: o for o in obs}
    assert (
        por_ip["10.0.0.50"].tipo_declarado == "cámara"
        and por_ip["10.0.0.80"].tipo_declarado == "consola de videojuegos"
    )
    assert "10.0.0.51" not in por_ip, "una respuesta WSD ilegible no es un dispositivo"

    def _cae():
        raise OSError("sin red")

    obs = descubrir(
        ejecutar=_ejecutar,
        buscar_ssdp=lambda: [],
        leer=lambda url: "",
        buscar_wsd=_cae,
        buscar_ddp=_cae,
        informacion=_cae,
    )
    assert any(o.nombre == "este equipo" for o in obs), "las fuentes caidas tumbaron al resto"
    obs = descubrir(
        ejecutar=_ejecutar,
        buscar_ssdp=lambda: [],
        leer=lambda url: "",
        buscar_wsd=_cae,
        buscar_ddp=lambda: [("10.0.0.80", DDP_620)],
        informacion=_cae,
    )
    assert any(o.tipo_declarado == "consola de videojuegos" for o in obs)


def test_wsd_un_DOCTYPE_VALIDO_con_entidad_usada_se_rechaza_por_la_guarda():
    """Mutante D1: el caso de arriba lo rechaza el propio parser (DOCTYPE antes de `<?xml`). Aquí el XML es VÁLIDO y la
    entidad se usa en la identidad: sin la guarda, ElementTree la expandiría y devolvería una Observacion."""
    cabecera, cuerpo = PROBEMATCH.split("\n", 1)
    hostil = (
        cabecera
        + '\n<!DOCTYPE s:Envelope [<!ENTITY e "urn:uuid:inyectada">]>\n'
        + cuerpo.replace("urn:uuid:11111111-2222-3333-4444-555555555555", "&e;")
    )
    assert observacion_wsd("10.0.0.50", hostil) is None


class _SocketFalso:
    """Entrega datagramas preparados y luego solo agota la espera."""

    def __init__(self, datagramas):
        self._pendientes = list(datagramas)

    def recvfrom(self, _tope):
        if self._pendientes:
            return self._pendientes.pop(0)
        raise TimeoutError


def test_recoger_datagramas_guarda_como_mucho_dos_por_IP():
    """Mutante D6: una IP que inunda de respuestas no ocupa más de 2 huecos; las demás IP siguen entrando."""
    s = _SocketFalso([(f"r{i}".encode(), ("10.0.0.9", 3702)) for i in range(5)] + [(b"otra", ("10.0.0.7", 3702))])

    vistos = red_local._recoger_datagramas(s, espera_s=0.05)

    assert [ip for ip, _ in vistos].count("10.0.0.9") == 2
    assert ("10.0.0.7", "otra") in vistos


def test_recoger_datagramas_tiene_un_tope_GLOBAL_y_solo_acepta_la_red_privada():
    """MEDIO de security-reviewer: con IP de origen falsificada, 2 por IP no limitaba nada. Tope global + solo LAN."""
    muchos = [(b"x", (f"10.0.{i // 250}.{i % 250 + 1}", 3702)) for i in range(500)]
    publica = [(b"fuera", ("8.8.8.8", 3702))]
    s = _SocketFalso(publica + muchos)

    vistos = red_local._recoger_datagramas(s, espera_s=0.2)

    assert len(vistos) == red_local._TOPE_RESPUESTAS
    assert all(ip != "8.8.8.8" for ip, _ in vistos)


def test_descubrir_sobrevive_a_una_fuente_que_lanza_cualquier_excepcion():
    """MEDIO: solo se capturaban OSError/SubprocessError/ValueError; otra excepción mataba la fuente sin decirlo."""

    def revienta():
        raise RuntimeError("fallo inesperado de una fuente")

    import threading

    trazas = []
    anterior = threading.excepthook
    threading.excepthook = lambda args: trazas.append(args.exc_value)
    try:
        obs = red_local.descubrir(
            ejecutar=lambda *a, **k: type("R", (), {"stdout": ""})(),
            buscar_ssdp=lambda: [],
            buscar_wsd=revienta,
            buscar_ddp=lambda: [("192.168.20.36", "HTTP/1.1 200 Ok\nhost-type:PS5\nhost-name:PS5-1\nhost-id:AB\n")],
            informacion=lambda ip, xaddr: None,
        )
    finally:
        threading.excepthook = anterior
    # Mutante D17: con `except (OSError, ValueError)` el hilo de WSD revienta con una traza en la pantalla.
    assert trazas == [], f"una fuente con un fallo no previsto revento su hilo: {trazas}"
    assert any(o.tipo_declarado == "consola de videojuegos" for o in obs)


# --- ONVIF GetDeviceInformation: la MISMA IP que respondió, sin credenciales ---

INFO_ONVIF = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
<s:Body><tds:GetDeviceInformationResponse><tds:Manufacturer>EYEPLUS</tds:Manufacturer>
<tds:Model>EYEPLUS_DEV</tds:Model><tds:FirmwareVersion>3.5.1.1108</tds:FirmwareVersion>
<tds:SerialNumber>SN-SECRETO-123</tds:SerialNumber><tds:HardwareId>HW-SECRETO-456</tds:HardwareId>
</tds:GetDeviceInformationResponse></s:Body></s:Envelope>"""
XADDR = "http://10.0.0.50/onvif/device_service"


def _enviar_registrando(respuesta=INFO_ONVIF):
    llamadas = []

    def enviar(url, cuerpo):
        llamadas.append((url, cuerpo))
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    return enviar, llamadas


def test_onvif_una_respuesta_valida_da_fabricante_modelo_y_firmware():
    enviar, llamadas = _enviar_registrando()
    info = informacion_onvif("10.0.0.50", XADDR, enviar=enviar)
    assert info == {"fabricante": "EYEPLUS", "modelo": "EYEPLUS_DEV", "firmware": "3.5.1.1108"}
    assert len(llamadas) == 1 and llamadas[0][0] == XADDR
    # Sin credenciales: ni cabecera de seguridad WS-Security ni usuario.
    cuerpo = llamadas[0][1].decode()
    assert "GetDeviceInformation" in cuerpo and "Security" not in cuerpo and "Password" not in cuerpo
    # Control: una respuesta sin Manufacturer/Model no inventa nada.
    assert parsear_informacion_onvif("<a><b/></a>") is None


def test_onvif_DOCTYPE_y_ENTITY_dan_None():
    assert parsear_informacion_onvif('<!DOCTYPE x [<!ENTITY a "b">]>' + INFO_ONVIF) is None
    assert parsear_informacion_onvif(INFO_ONVIF.replace("<s:Body>", '<!entity a "b"><s:Body>')) is None
    assert parsear_informacion_onvif(INFO_ONVIF) is not None


def test_onvif_mas_de_64KB_da_None():
    assert parsear_informacion_onvif(INFO_ONVIF + " " * 70_000) is None
    enviar, _ = _enviar_registrando(INFO_ONVIF + " " * 70_000)
    assert informacion_onvif("10.0.0.50", XADDR, enviar=enviar) is None


def test_onvif_el_numero_de_serie_y_el_hardware_id_no_aparecen_en_ninguna_salida():
    info = parsear_informacion_onvif(INFO_ONVIF)
    assert info is not None
    salida = repr(info)
    assert "SECRETO" not in salida and set(info) == {"fabricante", "modelo", "firmware"}
    assert "EYEPLUS" in salida  # control: lo que sí hace falta sigue


def test_onvif_un_XAddr_hacia_otra_IP_no_envia_nada():
    enviar, llamadas = _enviar_registrando()
    assert informacion_onvif("10.0.0.50", "http://10.0.0.99/onvif/device_service", enviar=enviar) is None
    assert informacion_onvif("10.0.0.50", "http://evil.example/onvif", enviar=enviar) is None
    assert llamadas == []
    assert informacion_onvif("10.0.0.50", XADDR, enviar=enviar) is not None  # control


def test_onvif_esquema_https_o_ftp_o_puerto_absurdo_no_envia_nada():
    enviar, llamadas = _enviar_registrando()
    for xaddr in ("https://10.0.0.50/onvif", "ftp://10.0.0.50/onvif", "http://10.0.0.50:22/onvif"):
        assert informacion_onvif("10.0.0.50", xaddr, enviar=enviar) is None
    assert llamadas == []
    assert informacion_onvif("10.0.0.50", "http://10.0.0.50:8080/onvif", enviar=enviar) is not None  # control


def test_onvif_un_401_da_None_y_no_reintenta():
    import urllib.error

    err = urllib.error.HTTPError(XADDR, 401, "Unauthorized", {}, None)  # type: ignore[arg-type]
    enviar, llamadas = _enviar_registrando(err)
    assert informacion_onvif("10.0.0.50", XADDR, enviar=enviar) is None
    assert len(llamadas) == 1, "reintentó tras un 401"
    enviar, llamadas = _enviar_registrando("<s:Envelope><s:Body><s:Fault/></s:Body></s:Envelope>")
    assert informacion_onvif("10.0.0.50", XADDR, enviar=enviar) is None and len(llamadas) == 1


def _descubrir_con(buscar_wsd, informacion):
    return descubrir(
        ejecutar=lambda *a, **k: type("R", (), {"stdout": ""})(),
        buscar_ssdp=lambda: [],
        leer=lambda url: "",
        buscar_wsd=buscar_wsd,
        buscar_ddp=lambda: [],
        informacion=informacion,
    )


def test_descubrir_enriquece_la_camara_con_fabricante_y_modelo_una_vez_por_IP():
    consultas = []

    def informacion(ip, xaddr):
        consultas.append((ip, xaddr))
        return {"fabricante": "EYEPLUS", "modelo": "EYEPLUS_DEV", "firmware": "3.5.1.1108"}

    obs = _descubrir_con(lambda: [("10.0.0.50", PROBEMATCH), ("10.0.0.50", PROBEMATCH)], informacion)
    cams = [o for o in obs if o.ip == "10.0.0.50"]
    assert cams and all(o.fabricante == "EYEPLUS" and o.modelo == "EYEPLUS_DEV" for o in cams)
    assert consultas == [("10.0.0.50", XADDR)], "más de una consulta por IP"
    # Control: sin información, la observación conserva solo lo que declaró el ProbeMatch.
    sin = [o for o in _descubrir_con(lambda: [("10.0.0.50", PROBEMATCH)], lambda ip, x: None) if o.ip == "10.0.0.50"]
    assert sin[0].fabricante is None and sin[0].modelo == "IPC-X1"


def test_descubrir_si_informacion_falla_la_observacion_WSD_sigue_saliendo():
    def revienta(ip, xaddr):
        raise RuntimeError("fallo inesperado")

    obs = _descubrir_con(lambda: [("10.0.0.50", PROBEMATCH)], revienta)
    cam = next(o for o in obs if o.ip == "10.0.0.50")
    assert cam.tipo_declarado == "cámara" and cam.fabricante is None


# ------------------------------- GetDeviceInformation: lo que protege `_enviar_soap` (mutación O4/O5/O6/O12/O13) --


class _Respuesta:
    def __init__(self, registro):
        self._registro = registro

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=None):
        self._registro["leido_con"] = n
        self._registro["lecturas"] = self._registro.get("lecturas", 0) + 1
        return b"<x/>" if self._registro["lecturas"] == 1 else b""


class _AbridorEspia:
    """Sustituye `_OPENER` (el abridor SIN redirecciones): si el código usa otro, este no se llama."""

    def __init__(self):
        self.registro: dict = {}

    def open(self, peticion, timeout=None):
        self.registro.update(peticion=peticion, timeout=timeout)
        return _Respuesta(self.registro)


def test_enviar_soap_usa_el_abridor_SIN_redirecciones_con_tope_y_sin_credenciales(monkeypatch):
    espia = _AbridorEspia()
    monkeypatch.setattr(red_local, "_OPENER", espia)

    red_local._enviar_soap("http://192.0.2.10/onvif/device_service", b"<soap/>")

    peticion = espia.registro["peticion"]
    assert espia.registro["timeout"] == 2
    assert 0 < espia.registro["leido_con"] <= red_local._TOPE_CUERPO + 1, "la lectura no está acotada"
    cabeceras = {k.lower() for k, _ in peticion.header_items()}
    assert "authorization" not in cabeceras and b"UsernameToken" not in (peticion.data or b"")


def test_la_informacion_ONVIF_con_DOCTYPE_VALIDO_y_entidad_usada_se_rechaza():
    xml = (
        '<?xml version="1.0"?>\n<!DOCTYPE e [<!ENTITY f "Inyectado">]>\n'
        '<e xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><tds:Manufacturer>&f;</tds:Manufacturer>'
        "<tds:Model>M</tds:Model></e>"
    )
    assert red_local.parsear_informacion_onvif(xml) is None


def test_descubrir_no_consulta_un_XAddr_que_apunta_a_OTRA_IP():
    llamadas = []
    probe = PROBEMATCH  # su XAddr es 10.0.0.50; la respuesta llega desde OTRA IP
    red_local.descubrir(
        ejecutar=lambda *a, **k: type("R", (), {"stdout": ""})(),
        buscar_ssdp=lambda: [],
        buscar_ddp=lambda: [],
        buscar_wsd=lambda: [("10.0.0.99", probe)],
        informacion=lambda ip, x: llamadas.append((ip, x)) or {"fabricante": "X", "modelo": "Y"},
    )
    assert llamadas == [], f"se consultó un XAddr de otra máquina: {llamadas}"


# ---------------- Endurecimiento de seguridad (security-reviewer, 2026-10-22): lo que protegen los nuevos topes --

_CAMARA = "192.168.20.110"
_XADDR_CAMARA = f"http://{_CAMARA}/onvif/device_service"
_SIN_PROPIAS = frozenset({"192.168.20.5"})  # «este equipo» inyectado: la prueba no depende de la máquina real


def _valido(ip, xaddr, propias=_SIN_PROPIAS):
    return red_local._xaddr_valido(ip, xaddr, propias=propias)


def test_xaddr_acepta_la_camara_110_en_el_puerto_80_implicito_y_en_los_puertos_de_la_lista():
    assert _valido(_CAMARA, _XADDR_CAMARA)
    for puerto in (80, 8000, 8080, 8899):
        assert _valido(_CAMARA, f"http://{_CAMARA}:{puerto}/onvif/device_service"), puerto


def test_xaddr_rechaza_los_puertos_fuera_de_la_lista_cerrada():
    for puerto in (22, 9000, 1024, 8081, 554):
        assert not _valido(_CAMARA, f"http://{_CAMARA}:{puerto}/x"), puerto


def test_xaddr_rechaza_el_DVR_no_tocar_por_defecto_y_con_control(monkeypatch):
    monkeypatch.delenv("AURA_RED_NO_TOCAR", raising=False)
    assert "192.168.20.80" in red_local._no_tocar()
    assert not _valido("192.168.20.80", "http://192.168.20.80/onvif/device_service")
    assert _valido("192.168.20.81", "http://192.168.20.81/onvif/device_service")  # control: otra IP privada


def test_xaddr_no_tocar_se_lee_de_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("AURA_RED_NO_TOCAR", "192.168.20.7, 192.168.20.8")
    assert red_local._no_tocar() == frozenset({"192.168.20.7", "192.168.20.8"})
    assert not _valido("192.168.20.7", "http://192.168.20.7/x")
    assert not _valido("192.168.20.8", "http://192.168.20.8/x")
    # Control: la variable SUSTITUYE al valor por defecto, y una IP no listada sigue valiendo.
    assert _valido("192.168.20.80", "http://192.168.20.80/x")


def test_xaddr_rechaza_loopback_link_local_e_ip_propia():
    for ip in ("127.0.0.1", "169.254.10.20", "192.168.20.5"):
        assert not _valido(ip, f"http://{ip}/x"), ip
    assert _valido("192.168.20.6", "http://192.168.20.6/x")  # control: privada, no propia
    assert not _valido("8.8.8.8", "http://8.8.8.8/x")  # control: pública


def test_las_IPs_propias_se_detectan_sin_fallar_aunque_la_resolucion_falle(monkeypatch):
    def falla(*a, **k):
        raise OSError("sin resolución")

    monkeypatch.setattr(red_local.socket, "gethostbyname_ex", falla)
    monkeypatch.setattr(red_local.socket, "gethostbyname", falla)
    assert isinstance(red_local._ips_propias(), frozenset)
    monkeypatch.setattr(red_local.socket, "gethostbyname_ex", lambda n: (n, [], ["192.168.20.9"]))
    assert "192.168.20.9" in red_local._ips_propias()


def test_el_abridor_no_usa_proxies_del_entorno(monkeypatch):
    import urllib.request

    monkeypatch.setenv("http_proxy", "http://proxy.hostil.example:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.hostil.example:3128")
    abridor = urllib.request.build_opener(red_local._SinRedirecciones)  # control: el abridor ingenuo SÍ lo usa
    assert any(getattr(h, "proxies", None) for h in abridor.handlers if isinstance(h, urllib.request.ProxyHandler))
    proxys = [h for h in red_local._OPENER.handlers if isinstance(h, urllib.request.ProxyHandler)]
    assert all(not h.proxies for h in proxys), "el abridor de red_local usaría el proxy del entorno"


def _wsd_n(n):
    return [(f"192.168.20.{100 + i}", PROBEMATCH.replace("10.0.0.50", f"192.168.20.{100 + i}")) for i in range(n)]


def test_enriquecer_wsd_con_una_consulta_lenta_termina_a_plazo_y_entrega_la_observacion_sin_enriquecer(monkeypatch):
    import threading
    import time

    liberar = threading.Event()
    monkeypatch.setattr(red_local, "_PLAZO_ENRIQUECER_S", 0.3)
    assert red_local.__dict__["_PLAZO_ENRIQUECER_S"] == 0.3
    try:
        t0 = time.monotonic()
        obs = red_local._enriquecer_wsd(
            _wsd_n(1), lambda ip, x: liberar.wait(10) and {"fabricante": "F", "modelo": "M"}
        )
        assert time.monotonic() - t0 < 2
    finally:
        liberar.set()
    assert len(obs) == 1 and obs[0].tipo_declarado == "cámara" and obs[0].fabricante is None
    # Control: si responde a tiempo, se enriquece.
    rapida = red_local._enriquecer_wsd(_wsd_n(1), lambda ip, x: {"fabricante": "F", "modelo": "M"})
    assert rapida[0].fabricante == "F"


def test_el_plazo_total_de_enriquecer_es_4_segundos_y_el_maximo_de_trabajadores_8():
    assert red_local._PLAZO_ENRIQUECER_S == 4
    assert red_local._MAX_TRABAJADORES_ENRIQUECER == 8


def test_enriquecer_wsd_consulta_las_IPs_en_paralelo():
    import time

    def lenta(ip, xaddr):
        time.sleep(1)
        return {"fabricante": ip, "modelo": "M"}

    t0 = time.monotonic()
    obs = red_local._enriquecer_wsd(_wsd_n(3), lenta)
    assert time.monotonic() - t0 < 2, "las consultas se hicieron en serie"
    assert [o.fabricante for o in obs] == [ip for ip, _ in _wsd_n(3)]  # conserva el orden y cada resultado
    # Control: una IP repetida sigue consultándose una sola vez.
    llamadas = []
    red_local._enriquecer_wsd(_wsd_n(1) * 2, lambda ip, x: llamadas.append(ip) or None)
    assert len(llamadas) == 1


def test_enviar_soap_corta_por_plazo_una_respuesta_que_gotea(monkeypatch):
    reloj = {"t": 0.0}

    class _Gotea:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=None):
            reloj["t"] += 1.0  # cada trozo «tarda» 1 s
            return b"x"

    class _Abridor:
        def open(self, peticion, timeout=None):
            return _Gotea()

    monkeypatch.setattr(red_local, "_OPENER", _Abridor())
    monkeypatch.setattr(red_local, "_reloj", lambda: reloj["t"])
    salida = red_local._enviar_soap("http://192.168.20.110/x", b"<soap/>")
    assert 0 < len(salida) <= 4, f"no cortó por plazo: {len(salida)} bytes"
    assert red_local._PLAZO_LECTURA_S == 3


def test_descubrir_lanza_sus_hilos_como_daemon(monkeypatch):
    creados = []
    real = red_local.threading.Thread

    def espia(*a, **k):
        creados.append(k.get("daemon"))
        return real(*a, **k)

    monkeypatch.setattr(red_local.threading, "Thread", espia)
    _descubrir_con(lambda: [], lambda ip, x: None)
    assert creados and all(d is True for d in creados)


def test_el_abridor_NO_hereda_el_proxy_del_entorno_aunque_exista_al_importar(monkeypatch):
    """Mutante N7: `_OPENER` se construye al importar. Con `http_proxy` en el entorno, un abridor sin `ProxyHandler({})`
    lo heredaría y el POST ONVIF saldría por el proxy, fuera de la LAN."""
    import importlib
    import urllib.request

    monkeypatch.setenv("http_proxy", "http://10.9.9.9:3128")
    try:
        modulo = importlib.reload(red_local)
        con_proxy = [h for h in modulo._OPENER.handlers if isinstance(h, urllib.request.ProxyHandler) and h.proxies]
        assert con_proxy == [], "el abridor del descubrimiento hereda el proxy del entorno"
        # Control: el abridor por defecto SÍ lo hereda, así que la prueba distingue los dos casos.
        ingenuo = urllib.request.build_opener()
        assert any(isinstance(h, urllib.request.ProxyHandler) and h.proxies for h in ingenuo.handlers)
    finally:
        monkeypatch.delenv("http_proxy")
        importlib.reload(red_local)


# ------------------------------------------------------ estado operativo por DDP (lectura, no verificación) --


def test_ddp_200_declara_estado_despierta():
    o = observacion_ddp("10.0.0.80", DDP_200)
    assert o is not None and o.estado_operativo == "despierta"


def test_ddp_620_declara_estado_en_reposo_y_no_apagada():
    o = observacion_ddp("10.0.0.81", DDP_620)
    assert o is not None and o.estado_operativo == "en_reposo"
    assert "apagada" not in repr(o)


def test_ddp_codigo_desconocido_o_malformado_o_vacio_da_None():
    assert observacion_ddp("10.0.0.80", "HTTP/1.1 500 X\nhost-type:PS5\n") is None
    assert observacion_ddp("10.0.0.80", "HTTP/1.1 200\nhost-type:PS5\n") is None
    assert observacion_ddp("10.0.0.80", "basura\x00\xff") is None
    assert observacion_ddp("10.0.0.80", "") is None
    assert observacion_ddp("10.0.0.80", "HTTP/1.1 200 Ok\nhost-type:Xbox\n") is None


def test_ddp_PRIVACIDAD_no_guarda_mas_campos_que_el_estado():
    o = observacion_ddp("10.0.0.80", DDP_200)
    assert o is not None
    assert "running-app" not in repr(o) and "Juego Secreto" not in repr(o) and "CUSA99999" not in repr(o)
    assert "997" not in repr(o)  # host-request-port tampoco se guarda


def test_ddp_la_sonda_solo_envia_SRCH_nunca_wakeup_launch_ni_standby(monkeypatch):
    enviados: list[tuple[bytes, tuple]] = []

    class SocketFalso:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def settimeout(self, _t):
            pass

        def setsockopt(self, *a):
            pass

        def sendto(self, datos, destino):
            enviados.append((datos, destino))

        def recvfrom(self, _n):
            raise TimeoutError

    monkeypatch.setattr(red_local.socket, "socket", SocketFalso)
    assert red_local._buscar_ddp(espera_s=0.0) == []
    assert enviados, "la sonda debe enviar algo (control)"
    assert {d[1][1] for d in enviados} == {9302, 987}
    for datos, _destino in enviados:
        assert datos.startswith(b"SRCH")
        for prohibido in (b"WAKEUP", b"LAUNCH", b"STANDBY"):
            assert prohibido not in datos
