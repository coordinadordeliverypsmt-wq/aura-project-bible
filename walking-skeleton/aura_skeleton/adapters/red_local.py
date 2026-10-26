"""Descubrimiento de la red local — SOLO pasivo o dirigido (semana 2, 2026-09-27).

Cinco fuentes, todas locales y sin credenciales:
- **Vecinos ARP** (`ip neigh`): lo que la máquina YA sabe de su red. No envía nada.
- **mDNS** (`avahi-browse`): lo que los dispositivos ANUNCIAN de sí mismos.
- **SSDP/UPnP**: una búsqueda estándar a la dirección multicast y la descripción que cada dispositivo
  PUBLICA en su propia URL.
- **WS-Discovery** (ONVIF, dirigido): UNA sonda multicast a 239.255.255.250:3702 por videocámaras
  (`NetworkVideoTransmitter`). Lee lo que la respuesta DECLARA. Su `XAddrs` solo se usa para UN
  `GetDeviceInformation` en la MISMA IP que respondió, sin credenciales (fabricante y modelo); cualquier
  `XAddrs` hacia otra máquina se ignora.
- **DDP** (PlayStation, dirigido): UN datagrama broadcast en los puertos 9302 y 987. De la respuesta solo se
  conserva qué consola es; el juego o aplicación en ejecución se IGNORA (es el consumo de la familia).

LO QUE NO HACE, A PROPÓSITO: no sondea puertos, no prueba credenciales, no explota nada. Y no sigue una
descripción SSDP que apunte a OTRA máquina: un anuncio SSDP es texto que cualquiera en la red puede
mandar, y seguirlo a ciegas convertiría a AURA en un proxy hacia donde el atacante quiera (SSRF).
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import ipaddress
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable
from urllib.parse import unquote, urlparse

from ..core.entorno import ESTADO_DESPIERTA, ESTADO_EN_REPOSO, Fuente, Observacion

_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def leer_vecinos(texto: str) -> list[Observacion]:
    obs = []
    for linea in texto.splitlines():
        partes = linea.split()
        if not partes or not _IPV4.match(partes[0]) or "lladdr" not in partes:
            continue
        if partes[-1] in ("FAILED", "INCOMPLETE"):
            continue
        obs.append(Observacion(ip=partes[0], mac=partes[partes.index("lladdr") + 1], fuentes=frozenset({"arp"})))
    return obs


def _desescapar(nombre: str) -> str:
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), nombre)


def leer_mdns(texto: str) -> list[Observacion]:
    obs = []
    for linea in texto.splitlines():
        campos = linea.split(";")
        if len(campos) < 9 or campos[0] != "=" or campos[2] != "IPv4" or not _IPV4.match(campos[7]):
            continue
        obs.append(
            Observacion(
                ip=campos[7],
                nombre=_acotar_nombre(_desescapar(campos[3])),
                servicios=frozenset({_desescapar(campos[4])}),
                fuentes=frozenset({"mdns"}),
            )
        )
    return obs


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """Hallazgo ALTO de la auditoría (2026-09-27): `urllib` sigue los 302 automáticamente. Un dispositivo
    hostil respondía desde SU IP —pasando la comprobación de host— y redirigía a AURA a otra máquina. Aquí
    una redirección es un error: la descripción se lee donde el dispositivo dijo, o no se lee."""

    def redirect_request(self, *args, **kwargs):
        return None


# `ProxyHandler({})`: sin proxies. Por defecto `urllib` hereda `http_proxy` del entorno y enviaría la petición
# SOAP a un proxy ajeno, que la reenviaría a donde sea: el destino dejaría de ser la IP validada.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _SinRedirecciones)


def _leer_url(url: str) -> str:
    with _OPENER.open(url, timeout=3) as r:  # noqa: S310 (misma IP que respondio, sin redirecciones)
        return r.read(200_000).decode("utf-8", "ignore")


def _acotar_nombre(texto: str | None) -> str | None:
    """El nombre lo pone quien se anuncia: acaba en pantalla y en la voz. Sin control y con tope."""
    if not texto:
        return texto
    limpio = "".join(c for c in texto if c.isprintable())
    return limpio[:60].strip() or None


def observacion_ssdp(ip: str, ubicacion: str, leer: Callable[[str], str] = _leer_url) -> Observacion:
    """Lo que el dispositivo que respondió publica sobre sí mismo, SOLO si la URL es suya."""
    base = Observacion(ip=ip, fuentes=frozenset({"ssdp"}))
    if urlparse(ubicacion).hostname != ip or urlparse(ubicacion).scheme != "http":
        return base
    try:
        cuerpo = leer(ubicacion)
        # Hallazgo ALTO de la auditoría: `ElementTree` expande entidades internas («billion laughs»). Una
        # descripción UPnP legítima no necesita DOCTYPE ni entidades: si las trae, no se parsea.
        if "<!DOCTYPE" in cuerpo.upper() or "<!ENTITY" in cuerpo.upper():
            return base
        raiz = ET.fromstring(re.sub(r'\sxmlns="[^"]+"', "", cuerpo, count=1))
    except (ET.ParseError, OSError, ValueError):
        return base
    dispositivo = raiz.find(".//device")
    if dispositivo is None:
        return base

    def campo(nombre):
        valor = dispositivo.findtext(nombre)
        return valor.strip() if valor else None

    tipo = (campo("deviceType") or "").split(":")
    return Observacion(
        ip=ip,
        nombre=_acotar_nombre(campo("friendlyName")),
        fabricante=_acotar_nombre(campo("manufacturer")),
        modelo=_acotar_nombre(campo("modelName")),
        tipo_upnp=tipo[3] if len(tipo) > 3 else None,
        fuentes=frozenset({"ssdp"}),
    )


def _buscar_ssdp(espera_s: float = 3.0) -> list[tuple[str, str]]:
    mensaje = (
        b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n'
    )
    # TODAS las descripciones de cada IP (hasta 5): una TV anuncia varias —compartir pantalla,
    # renderizador…— y quedarse con la primera perdía justo la que decía qué era.
    vistos: list[tuple[str, str]] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(0.5)
        s.sendto(mensaje, ("239.255.255.250", 1900))
        fin = time.time() + espera_s
        while time.time() < fin:
            try:
                datos, (ip, _puerto) = s.recvfrom(4096)
            except TimeoutError:
                continue
            for linea in datos.decode("utf-8", "ignore").split("\r\n"):
                if linea.lower().startswith("location:"):
                    par = (ip, linea.split(":", 1)[1].strip())
                    if par not in vistos and sum(1 for v in vistos if v[0] == ip) < 5:
                        vistos.append(par)
    return vistos


_TOPE_CUERPO = 64 * 1024  # un ProbeMatch o un DDP legítimos caben de sobra; más es ruido u hostilidad
_TOPE_POR_IP = 2
#: Tope GLOBAL por búsqueda (revisión de seguridad 2026-10-22): con la IP de origen falsificada, «2 por IP» no
#: limitaba nada. Una casa no tiene 64 cámaras o consolas respondiendo a la vez.
_TOPE_RESPUESTAS = 64


def _nombre_local(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


def observacion_wsd(ip: str, xml: str) -> Observacion | None:
    """Lo que un ProbeMatch de WS-Discovery declara de SÍ MISMO. Función pura: NO sigue `XAddrs` (seguirlo
    sería el mismo SSRF que se cerró en SSDP) y no se autentica. None si no es un ProbeMatch reconocible."""
    if len(xml) > _TOPE_CUERPO or "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        return None
    try:
        raiz = ET.fromstring(xml)
    except (ET.ParseError, ValueError):
        return None
    coincidencia = next((e for e in raiz.iter() if _nombre_local(e.tag) == "ProbeMatch"), None)
    if coincidencia is None:
        return None

    def texto(nombre: str) -> str:
        e = next((x for x in coincidencia.iter() if _nombre_local(x.tag) == nombre), None)
        return (e.text or "").strip() if e is not None else ""

    nombre = modelo = None
    for scope in texto("Scopes").split():
        if scope.startswith("onvif://www.onvif.org/name/"):
            nombre = _acotar_nombre(unquote(scope.rsplit("/", 1)[-1]))
        elif scope.startswith("onvif://www.onvif.org/hardware/"):
            modelo = _acotar_nombre(unquote(scope.rsplit("/", 1)[-1]))
    es_camara = any(t.rsplit(":", 1)[-1] == "NetworkVideoTransmitter" for t in texto("Types").split())
    return Observacion(
        ip=ip,
        nombre=nombre,
        modelo=modelo,
        tipo_declarado="cámara" if es_camara else None,
        identidad=_acotar_nombre(texto("Address")),
        capacidades=frozenset({"video_entrada"}) if es_camara else frozenset(),
        fuentes=frozenset({"onvif"}),
    )


#: Lista CERRADA de puertos ONVIF: el 80 implícito y los habituales de las cámaras. Cualquier otro (22, 445,
#: 9000…) puede ser un servicio que NO es ONVIF y que no debe recibir un POST.
_PUERTOS_ONVIF = frozenset({None, 80, 8000, 8080, 8899})
#: IPs a las que NUNCA se envía nada. El censo de la red marca el DVR 192.168.20.80 como «no tocar»; se puede
#: sustituir con `AURA_RED_NO_TOCAR` (IPs separadas por comas).
_NO_TOCAR_DEFECTO = "192.168.20.80"
_ONVIF_DEVICE_NS = "http://www.onvif.org/ver10/device/wsdl"
_SOAP_INFORMACION = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
    f'<s:Body><tds:GetDeviceInformation xmlns:tds="{_ONVIF_DEVICE_NS}"/></s:Body></s:Envelope>'
).encode()


def _no_tocar() -> frozenset[str]:
    """IPs excluidas (censo: «no tocar»). Se lee en cada llamada para que el entorno mande."""
    crudo = os.environ.get("AURA_RED_NO_TOCAR", _NO_TOCAR_DEFECTO)
    return frozenset(p.strip() for p in crudo.split(",") if p.strip())


def _ips_propias() -> frozenset[str]:
    """Las IPs de ESTE equipo, tolerante a fallos: sin resolución devuelve lo que haya (puede ser vacío)."""
    propias: set[str] = set()
    try:
        propias.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        propias.add(socket.gethostbyname(socket.gethostname()))
    except OSError:
        pass
    try:  # connect UDP no envía nada: solo le pregunta al kernel qué interfaz usaría
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 9))
            propias.add(s.getsockname()[0])
    except OSError:
        pass
    return frozenset(propias)


def _xaddr_valido(ip: str, xaddr: str, propias: frozenset[str] | None = None) -> bool:
    """Anti-SSRF, igual que SSDP: el XAddr lo escribe quien responde, así que solo se usa si apunta a la
    máquina que respondió, por http, a un puerto de la lista cerrada, y esa máquina es una IP privada que no
    sea loopback, link-local, este equipo ni una de `_no_tocar()`."""
    try:
        u = urlparse(xaddr)
        puerto = u.port
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if u.hostname != ip or u.scheme != "http" or puerto not in _PUERTOS_ONVIF:
        return False
    if not direccion.is_private or direccion.is_loopback or direccion.is_link_local:
        return False
    return ip not in _no_tocar() and ip not in (_ips_propias() if propias is None else propias)


def xaddrs_wsd(xml: str) -> list[str]:
    """Los `XAddrs` que declara un ProbeMatch. Función pura; no abre nada. Misma guarda que `observacion_wsd`."""
    if len(xml) > _TOPE_CUERPO or "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        return []
    try:
        raiz = ET.fromstring(xml)
    except (ET.ParseError, ValueError):
        return []
    return [t for e in raiz.iter() if _nombre_local(e.tag) == "XAddrs" for t in (e.text or "").split()]


_PLAZO_LECTURA_S = 3.0  # tiempo TOTAL de lectura: un dispositivo que gotea bytes no retiene a AURA
_TROZO = 4096
_reloj = time.monotonic


def _leer_acotado(r, tope: int, plazo_s: float) -> bytes:
    """Lee en trozos hasta `tope` bytes, EOF o `plazo_s`; si se pasa, devuelve lo leído."""
    fin = _reloj() + plazo_s
    partes: list[bytes] = []
    leido = 0
    while leido < tope and _reloj() < fin:
        trozo = r.read(min(_TROZO, tope - leido))
        if not trozo:
            break
        partes.append(trozo)
        leido += len(trozo)
    return b"".join(partes)


def _enviar_soap(url: str, cuerpo: bytes) -> str:
    peticion = urllib.request.Request(  # noqa: S310 (misma IP que respondio, validada antes)
        url,
        data=cuerpo,
        headers={
            "Content-Type": 'application/soap+xml; charset=utf-8; action="'
            + _ONVIF_DEVICE_NS
            + '/GetDeviceInformation"'
        },
    )
    with _OPENER.open(peticion, timeout=2) as r:  # sin redirecciones
        return _leer_acotado(r, _TOPE_CUERPO + 1, _PLAZO_LECTURA_S).decode("utf-8", "ignore")


def parsear_informacion_onvif(xml: str) -> dict | None:
    """Fabricante, modelo y firmware de una respuesta `GetDeviceInformation`. Función pura. IGNORA
    `SerialNumber` y `HardwareId`: identifican el aparato y no hacen falta. None si no hay nada utilizable."""
    if len(xml) > _TOPE_CUERPO or "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        return None
    try:
        raiz = ET.fromstring(xml)
    except (ET.ParseError, ValueError):
        return None

    def texto(nombre: str) -> str | None:
        e = next((x for x in raiz.iter() if _nombre_local(x.tag) == nombre), None)
        return _acotar_nombre(e.text.strip()) if e is not None and e.text else None

    info = {"fabricante": texto("Manufacturer"), "modelo": texto("Model"), "firmware": texto("FirmwareVersion")}
    return info if info["fabricante"] or info["modelo"] else None


def informacion_onvif(ip: str, xaddr: str, enviar: Callable[[str, bytes], str] = _enviar_soap) -> dict | None:
    """UN `GetDeviceInformation` a la MISMA IP que respondió, SIN WS-Security, usuario ni contraseña (acta de
    percepción §7: ONVIF por vías legítimas, nunca credenciales). Un 401, un fault o cualquier error dan None
    y NO se reintenta con credenciales. Si el XAddr no es de esa IP no se envía nada."""
    if not _xaddr_valido(ip, xaddr):
        return None
    try:
        return parsear_informacion_onvif(enviar(xaddr, _SOAP_INFORMACION))
    except (OSError, ValueError):  # HTTPError (401 incluido) es OSError
        return None


def _recoger_datagramas(s: socket.socket, espera_s: float) -> list[tuple[str, str]]:
    """Respuestas UDP hasta `espera_s`: solo de la red PRIVADA (es una búsqueda en la LAN), como mucho 2 por IP,
    64 en total y 64 KB por datagrama."""
    vistos: list[tuple[str, str]] = []
    por_ip: dict[str, int] = {}
    fin = time.time() + espera_s
    while time.time() < fin and len(vistos) < _TOPE_RESPUESTAS:
        try:
            datos, (ip, _puerto) = s.recvfrom(_TOPE_CUERPO)
        except TimeoutError:
            continue
        if not _es_privada(ip) or por_ip.get(ip, 0) >= _TOPE_POR_IP:
            continue
        por_ip[ip] = por_ip.get(ip, 0) + 1
        vistos.append((ip, datos.decode("utf-8", "ignore")))
    return vistos


def _es_privada(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _buscar_wsd(espera_s: float = 3.0) -> list[tuple[str, str]]:
    sonda = (
        '<?xml version="1.0" encoding="UTF-8"?><e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
        'xmlns:dn="http://www.onvif.org/ver10/network/wsdl"><e:Header>'
        f"<w:MessageID>uuid:{uuid.uuid4()}</w:MessageID>"
        "<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>"
        "<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>"
        "<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body></e:Envelope>"
    ).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(0.5)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)  # no sale de la red local
        s.sendto(sonda, ("239.255.255.250", 3702))
        return _recoger_datagramas(s, espera_s)


_CONSOLAS = frozenset({"PS5", "PS4"})
#: 200 = despierta; 620 = en reposo. Cualquier otra respuesta no se interpreta. DDP no puede demostrar «apagada».
_ESTADO_POR_PRIMERA_LINEA = {
    "HTTP/1.1 200 Ok": ESTADO_DESPIERTA,
    "HTTP/1.1 620 Server Standby": ESTADO_EN_REPOSO,
}


def observacion_ddp(ip: str, texto: str) -> Observacion | None:
    """Lo que una PlayStation declara por DDP: qué consola es. Función pura. PRIVACIDAD: `running-app-name`
    y `running-app-titleid` son lo que la familia está jugando; se IGNORAN, ni se leen ni se guardan."""
    lineas = texto.splitlines()
    estado = _ESTADO_POR_PRIMERA_LINEA.get(lineas[0].strip()) if lineas else None
    if estado is None:
        return None
    campos = {}
    for linea in lineas[1:]:
        clave, sep, valor = linea.partition(":")
        if sep and clave.strip() in ("host-type", "host-name", "host-id"):
            campos[clave.strip()] = valor.strip()
    if campos.get("host-type") not in _CONSOLAS:
        return None
    return Observacion(
        ip=ip,
        nombre=_acotar_nombre(campos.get("host-name")),
        modelo=campos["host-type"],
        tipo_declarado="consola de videojuegos",
        identidad=_acotar_nombre(campos.get("host-id")),
        fuentes=frozenset({"ddp"}),
        estado_operativo=estado,
    )


def _buscar_ddp(espera_s: float = 3.0) -> list[tuple[str, str]]:
    sonda = b"SRCH * HTTP/1.1\ndevice-discovery-protocol-version:00030010\n"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(0.5)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for puerto in (9302, 987):  # PS5, PS4
            s.sendto(sonda, ("255.255.255.255", puerto))
        return _recoger_datagramas(s, espera_s)


def _camaras_locales() -> list[str]:
    import glob

    return sorted(glob.glob("/dev/video*"))


def equipo_local(
    ejecutar: Callable = subprocess.run, camaras: Callable[[], list[str]] = _camaras_locales
) -> Observacion:
    """El propio equipo como superficie de presencia (mapa vivo, 2026-09-27): su IP y el hardware que el
    sistema ve. Solo LEE qué dispositivos existen; no abre el micrófono ni la cámara."""

    def _salida(orden):
        return ejecutar(orden, capture_output=True, text=True, timeout=5).stdout

    ip = next(
        (
            m.group(1)
            for m in re.finditer(
                r"inet (\d{1,3}(?:\.\d{1,3}){3})/", _salida(["ip", "-4", "-o", "addr", "show", "scope", "global"])
            )
        ),
        "este equipo",
    )
    caps = set()
    # PipeWire/PulseAudio listan el «.monitor» de cada salida como fuente: eso no es un micrófono.
    if any(
        linea.split("\t")[1:2] and not linea.split("\t")[1].endswith(".monitor")
        for linea in _salida(["pactl", "list", "short", "sources"]).splitlines()
    ):
        caps.add("audio_entrada")
    if _salida(["pactl", "list", "short", "sinks"]).strip():
        caps.add("audio_salida")
    if camaras():
        caps.add("video_entrada")
    return Observacion(
        ip=ip,
        nombre="este equipo",
        tipo_declarado="computador",
        identidad="local",
        capacidades=frozenset(caps),
        fuentes=frozenset({"local"}),
    )


def estado_de_fuentes(ejecutar: Callable = subprocess.run) -> list[Fuente]:
    """Qué fuentes de evidencia hay y en qué estado. Las activas (ARP, mDNS, SSDP, HA, este equipo) no se
    listan aquí: las aporta `descubrir`. Aquí se declaran las PREPARADAS-PERO-NO-DISPONIBLES, para que su
    ausencia en el mapa no se lea como «la casa está vacía». Solo LEE estado; no autentica ni enciende nada."""
    fuentes: list[Fuente] = []
    # El router podría dar sus clientes DHCP, pero eso exige que el usuario entre: no se intenta solo.
    fuentes.append(Fuente("router", "no_autorizada", "daría los clientes DHCP si tú inicias sesión"))
    try:
        salida = ejecutar(["rfkill", "list", "bluetooth"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        salida = ""
    if "soft blocked: yes" in salida.lower():
        fuentes.append(Fuente("Bluetooth", "bloqueada", "apagado por software en este equipo"))
    elif "bluetooth" in salida.lower():
        fuentes.append(Fuente("Bluetooth", "no_integrada", "encendido, pero aún no lo uso como fuente"))
    else:
        fuentes.append(Fuente("Bluetooth", "no_integrada", "sin controlador visible"))
    return fuentes


_PLAZO_ENRIQUECER_S = 4.0  # plazo TOTAL del enriquecimiento: lo que no termine sale sin enriquecer
_MAX_TRABAJADORES_ENRIQUECER = 8


def _enriquecer_wsd(respuestas: list[tuple[str, str]], informacion: Callable[[str, str], dict | None]):
    """Observaciones WSD con fabricante y modelo de `GetDeviceInformation`: como mucho UNA consulta por IP, en
    PARALELO y con un plazo total. Si falla o no llega a tiempo, la observación sale igual (lo declarado por el
    ProbeMatch): la observación WSD nunca se pierde por el enriquecimiento."""
    pendientes: list[tuple[str, str, Observacion]] = []
    xaddrs: dict[str, str] = {}
    for ip, xml in respuestas:
        obs = observacion_wsd(ip, xml)
        if obs is None:
            continue
        pendientes.append((ip, xml, obs))
        if ip not in xaddrs:
            xaddr = next((x for x in xaddrs_wsd(xml) if _xaddr_valido(ip, x)), None)
            if xaddr is not None:
                xaddrs[ip] = xaddr
    consultas: dict[str, dict | None] = {}
    if xaddrs:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_TRABAJADORES_ENRIQUECER)
        try:
            futuros = {ip: pool.submit(informacion, ip, x) for ip, x in xaddrs.items()}
            concurrent.futures.wait(futuros.values(), timeout=_PLAZO_ENRIQUECER_S)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)  # no espera a los lentos
        for ip, f in futuros.items():
            try:
                consultas[ip] = f.result(timeout=0) if f.done() else None
            except Exception:  # noqa: BLE001 — el enriquecimiento es opcional
                consultas[ip] = None
    salida = []
    for ip, _xml, obs in pendientes:
        info = consultas.get(ip)
        if info:
            obs = dataclasses.replace(
                obs, fabricante=info.get("fabricante") or obs.fabricante, modelo=info.get("modelo") or obs.modelo
            )
        salida.append(obs)
    return salida


def descubrir(
    ejecutar: Callable = subprocess.run,
    buscar_ssdp: Callable = _buscar_ssdp,
    leer: Callable[[str], str] = _leer_url,
    buscar_wsd: Callable = _buscar_wsd,
    buscar_ddp: Callable = _buscar_ddp,
    informacion: Callable[[str, str], dict | None] = informacion_onvif,
) -> list[Observacion]:
    """Una ronda de descubrimiento. Si una fuente falla, las demás siguen: el entorno se ve a trozos, no a ciegas."""
    resultado: list[Observacion] = []
    cerrojo = threading.Lock()

    def _fuente(fn):
        try:
            obs = fn()
        except Exception:  # noqa: BLE001 — una fuente que falla, falle como falle, no se lleva a las demás
            return
        with cerrojo:
            resultado.extend(o for o in obs if o is not None)

    fuentes = [
        lambda: leer_vecinos(ejecutar(["ip", "neigh", "show"], capture_output=True, text=True, timeout=5).stdout),
        # `timeout` EXTERNO: resolver todos los servicios supera cualquier tope razonable, y con el tope de
        # `subprocess` la salida se perdía entera. Así se conserva lo oído hasta el corte.
        lambda: leer_mdns(
            ejecutar(["timeout", "6", "avahi-browse", "-atrp"], capture_output=True, text=True, timeout=10).stdout
        ),
        lambda: [observacion_ssdp(ip, url, leer) for ip, url in buscar_ssdp()],
        lambda: _enriquecer_wsd(buscar_wsd(), informacion),
        lambda: [observacion_ddp(ip, texto) for ip, texto in buscar_ddp()],
        lambda: [equipo_local(ejecutar)],
    ]
    hilos = [threading.Thread(target=_fuente, args=(f,), daemon=True) for f in fuentes]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=12)
    return resultado
