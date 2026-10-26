"""Lo que AURA sabe de su entorno físico — y a qué nivel lo sabe (semana 2, 2026-09-27).

Cuatro niveles que NO se confunden:

    DESCUBIERTO   AURA sabe que hay algo en una dirección (vecino ARP, anuncio mDNS o SSDP).
    IDENTIFICADO  sabe QUÉ es, por lo que el propio dispositivo anuncia (tipo UPnP, fabricante, servicios).
    CARACTERIZADO además sabe QUÉ OFRECE: sonido, pantalla, vídeo… por lo que anuncia su protocolo. Ofrecer
                  vídeo NO es poder verlo: una cámara ajena (no del propietario) sigue siendo privada hasta que se
                  autorice; la ZONA de una cámara propia nunca la hace privada (acta 2026-10-22).
    INTEGRADO     tiene una vía legítima para hablar con él: una entidad en Home Assistant (Bible 6.3).
    CONTROLABLE   integrado Y su tipo está en la lista verde del hogar. Aun así, cada acción pasa por el
                  Motor Único y, desde la conversación, por una confirmación explícita.

«Veo 10.0.0.20» no es «sé qué es»; «es una TV Samsung» no es «puedo controlarla»; «puedo controlarla» no
es «puedo hacer cualquier cosa con ella».

REGISTRO VIVO. El inventario recuerda qué vio y marca las transiciones —nuevo, ausente, reaparece— sin
borrar lo ausente. Vive en la memoria del proceso: no es una base de datos nueva. Las transiciones quedan
en el audit log, que es la historia (ADR-0023).

MAPA VIVO (misión CEO, 2026-09-27). Diagnóstico `[EJEC]`: el pipeline no perdía nada; AURA solo veía
4-5 equipos porque sus fuentes eran pasivas y porque clasificaba de más (Spotify Connect → «altavoz»:
era una PS5). Ahora el tipo lo dice el protocolo propio del equipo cuando lo tiene (`tipo_declarado`) y
las CAPACIDADES se separan del tipo. La declaración manda sobre lo que NO dice qué es el equipo («desconocido»);
si contradice el tipo que otras fuentes de la misma IP ya permiten deducir, es un CONFLICTO: se marca y no se
elige (ONVIF y DDP viajan por UDP sin autenticar; revisión de seguridad 2026-10-22). Si un equipo declara una identidad estable (UDN, host-id, ONVIF), un
cambio de IP por DHCP lo MUEVE en vez de duplicarlo.

PRESENCIA. Las capacidades dicen dónde PODRÍA estar AURA (escuchar, hablar, ver, mostrar). Hoy solo el
equipo local es superficie disponible; lo demás se describe como posible y pendiente de integración y
autorización. Describir una superficie no la activa.

INDEXADO POR IP, NO POR MAC. Medido `[EJEC]` en la casa: la TV y otro equipo comparten la MISMA MAC,
localmente administrada (típico de un repetidor Wi-Fi). La MAC no identifica un dispositivo aquí.

PERSONAS. Un teléfono en la red es presencia TÉCNICA. AURA no deduce de quién es: eso es identidad, y la
identidad de personas sigue sus propias reglas (Bible 2.4, decisión B pendiente).
"""

from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any

DESCUBIERTO = "descubierto"
IDENTIFICADO = "identificado"
CARACTERIZADO = "caracterizado"
INTEGRADO = "integrado"
AUTORIZADO = "autorizado"
CONTROLABLE = "controlable"
EFECTO_VERIFICADO = "efecto verificado"

#: El orden estricto de conocimiento. NO son sinónimos: se sube por evidencia, nunca porque una fuente lo
#: anuncie. AUTORIZADO es un estado de gobierno (una acción reversible de lista verde ya está autorizada
#: por D4); EFECTO_VERIFICADO solo lo fija una acción real comprobada por el Motor Único.
#: Estado operativo que un equipo DECLARA por su protocolo (DDP de PlayStation). Es una LECTURA con hora, no una
#: verificación física. Desconocido = None. NO existe «apagada»: DDP no puede demostrarla; no responder no es
#: estar apagada (puede ser un timeout, una red caída o un cortafuegos).
ESTADO_DESPIERTA = "despierta"
ESTADO_EN_REPOSO = "en_reposo"

#: Pasada esta antigüedad (s), una lectura de estado se presenta como «último estado conocido».
ESTADO_VIGENCIA_S = 15 * 60

NIVELES = (DESCUBIERTO, IDENTIFICADO, CARACTERIZADO, INTEGRADO, AUTORIZADO, CONTROLABLE, EFECTO_VERIFICADO)


@dataclass(frozen=True)
class Observacion:
    """Lo que una fuente pasiva dijo de una dirección. Varias observaciones de la misma IP se fusionan."""

    ip: str
    mac: str | None = None
    nombre: str | None = None
    fabricante: str | None = None
    modelo: str | None = None
    tipo_upnp: str | None = None
    servicios: frozenset = frozenset()
    fuentes: frozenset = frozenset()
    #: Lo que el protocolo PROPIO del equipo dice que es (DDP de PlayStation, ONVIF, cabecera del DVR).
    tipo_declarado: str | None = None
    #: Identidad estable que el equipo declara (host-id, UDN, endpoint ONVIF). Nunca la MAC.
    identidad: str | None = None
    #: audio_entrada | audio_salida | video_entrada | video_salida, solo si un protocolo lo anuncia.
    capacidades: frozenset = frozenset()
    #: ESTADO_DESPIERTA | ESTADO_EN_REPOSO si el protocolo propio lo declara en esta lectura; None = desconocido.
    estado_operativo: str | None = None


@dataclass
class Dispositivo:
    ip: str
    mac: str | None
    nombre: str | None
    fabricante: str | None
    modelo: str | None
    tipo: str
    servicios: frozenset
    fuentes: frozenset
    nivel: str
    entidad_ha: str | None = None
    capacidades: frozenset = frozenset()
    identidad: str | None = None
    tipo_declarado: str | None = None
    #: Si dos fuentes contradicen tipo o identidad: se marca y NO se adivina cuál gana.
    conflicto: str | None = None
    #: True cuando el Motor Único comprobó un efecto real sobre este equipo (hecho histórico).
    efecto_verificado: bool = False
    presente: bool = True
    #: Último estado operativo LEÍDO y la hora (time.time() de la ronda) de esa lectura. Ausencia de lectura no lo borra.
    estado_operativo: str | None = None
    estado_visto: float | None = None
    visto_primero: float = field(default_factory=time.time)
    visto_ultimo: float = field(default_factory=time.time)


@dataclass(frozen=True)
class Fuente:
    """Una fuente de EVIDENCIA, no de verdad. `estado`: activa | fallida | no_autorizada | bloqueada."""

    nombre: str
    estado: str
    detalle: str = ""


@dataclass(frozen=True)
class Transicion:
    ip: str
    tipo: str
    cambio: str  # nuevo | ausente | reaparece | cambia_ip


# Servicios mDNS -> tipo. Solo lo que el dispositivo ANUNCIA de sí mismo; nada de puertos sondeados.
_POR_SERVICIO = (
    (("airplay remote video", "_googlecast", "_airplay", "_raop", "roku"), "televisor"),
    (("_nearbypresence", "_companion-link", "_apple-mobdev", "_androidtvremote"), "teléfono"),
    (("_rtsp", "_onvif", "onvif"), "cámara"),
    (("_ipp", "_printer", "_pdl-datastream"), "impresora"),
    (("_sonos",), "altavoz"),
)
# `_spotify-connect` y `_daap` ya NO dan tipo: los anuncian PlayStation, televisores, PCs y teléfonos.
# Medido `[EJEC]`: la PS5 de la casa se presentaba como «altavoz». Dicen QUÉ OFRECE, no QUÉ ES.

#: Servicios anunciados -> capacidad que el equipo ofrece.
_CAPACIDAD_POR_SERVICIO = (
    (("_spotify-connect", "_raop", "_airplay", "airplay remote video", "_googlecast", "_sonos"), "audio_salida"),
    (("airplay remote video", "_googlecast", "_airplay"), "video_salida"),
    (("_rtsp", "_onvif"), "video_entrada"),
)


def capacidades_de(o: Observacion) -> frozenset:
    """Lo que el equipo OFRECE según lo que anuncia. Nada se deduce del tipo ni del fabricante."""
    caps = set(o.capacidades)
    servicios = " ".join(s.lower() for s in o.servicios)
    for claves, capacidad in _CAPACIDAD_POR_SERVICIO:
        if any(c in servicios for c in claves):
            caps.add(capacidad)
    if "mediarenderer" in (o.tipo_upnp or "").lower():
        caps.add("audio_salida")
        if identificar(o) == "televisor":
            caps.add("video_salida")
    return frozenset(caps)


def _norm(texto: str | None) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("[tv]", "").strip()


#: Fuentes que DECLARAN qué es el equipo por UDP sin autenticar: sirven para identificar, no para dar control.
_FUENTES_DECLARATIVAS = frozenset({"onvif", "ddp"})


def _juntar(previa: Observacion, o: Observacion) -> Observacion:
    """Dos observaciones de la MISMA IP en una. Lo que ya se sabía no se pisa, salvo por una declaración adoptada."""
    junta = Observacion(
        ip=o.ip,
        mac=previa.mac or o.mac,
        nombre=previa.nombre or o.nombre,
        fabricante=previa.fabricante or o.fabricante,
        modelo=previa.modelo or o.modelo,
        tipo_upnp=previa.tipo_upnp or o.tipo_upnp,
        servicios=previa.servicios | o.servicios,
        fuentes=previa.fuentes | o.fuentes,
        tipo_declarado=o.tipo_declarado or previa.tipo_declarado,
        identidad=previa.identidad or o.identidad,
        capacidades=previa.capacidades | o.capacidades,
        estado_operativo=o.estado_operativo or previa.estado_operativo,
    )
    # Una declaración ADOPTADA nombra al equipo por encima del nombre que publica otro servicio (Spotify).
    return replace(junta, nombre=o.nombre) if o.tipo_declarado and o.nombre else junta


def _fusionar(observaciones: list[Observacion]) -> tuple[dict[str, Observacion], dict[str, str]]:
    """Una observación por IP y los CONFLICTOS de la ronda. Independiente del orden de llegada.

    Primero se junta lo que no declara tipo (ARP, mDNS, SSDP) y se deduce qué es; después se evalúan las
    declaraciones (ONVIF, DDP). Una declaración se adopta solo si no contradice ese tipo deducido ni a otra
    declaración de la misma ronda. Medido (revisión de seguridad 2026-10-22): un ProbeMatch falso en la misma ronda
    que el SSDP real de la TV la convertía en «cámara» con nombre falso, sin conflicto, y dependía del orden."""
    por_ip: dict[str, list[Observacion]] = {}
    for o in observaciones:
        por_ip.setdefault(o.ip, []).append(o)
    fusion: dict[str, Observacion] = {}
    conflictos: dict[str, str] = {}
    for ip, lista in por_ip.items():
        resto = [o for o in lista if not o.tipo_declarado]
        declaradas = [o for o in lista if o.tipo_declarado]
        base: Observacion | None = None
        for o in resto:
            base = o if base is None else _juntar(base, o)
        deducido = identificar(base) if base is not None else "desconocido"
        tipos = sorted({str(o.tipo_declarado) for o in declaradas})
        identidades = sorted({o.identidad for o in declaradas if o.identidad})
        if len(tipos) > 1:
            conflictos[ip] = f"en la misma ronda unas fuentes dicen «{tipos[0]}» y otras «{tipos[1]}»"
        elif len(identidades) > 1:
            conflictos[ip] = f"dos identidades distintas: «{identidades[0]}» y «{identidades[1]}»"
        elif tipos and deducido not in ("desconocido", tipos[0]):
            conflictos[ip] = f"una fuente dice «{deducido}» y otra «{tipos[0]}»"
        for o in [] if ip in conflictos else declaradas:
            base = o if base is None else _juntar(base, o)
        if base is None:
            # Solo declaraciones, en conflicto: se conserva la EVIDENCIA de que algo respondió (fuentes, MAC, servicios),
            # pero ni tipo, ni nombre, ni identidad de ninguna (code-reviewer 2026-10-22).
            base = Observacion(
                ip=ip,
                mac=next((o.mac for o in declaradas if o.mac), None),
                servicios=frozenset().union(*(o.servicios for o in declaradas)),
                fuentes=frozenset().union(*(o.fuentes for o in declaradas)),
            )
        # Estados distintos en la MISMA ronda: no se adivina cuál gana (ni depende del orden de llegada).
        usadas = resto if ip in conflictos else lista
        estados = {o.estado_operativo for o in usadas if o.estado_operativo}
        fusion[ip] = replace(base, estado_operativo=next(iter(estados)) if len(estados) == 1 else None)
    return fusion, conflictos


def identificar(o: Observacion) -> str:
    """El tipo, SOLO por lo que el dispositivo anuncia. Si no anuncia nada reconocible: desconocido."""
    if o.tipo_declarado:
        return o.tipo_declarado
    upnp = (o.tipo_upnp or "").lower()
    if (o.nombre or "").lower().startswith("[tv]"):
        # El dispositivo ya dice qué es. Medido `[EJEC]`: la segunda TV de la casa anuncia primero su
        # servicio de compartir pantalla, no un MediaRenderer.
        return "televisor"
    if "internetgatewaydevice" in upnp:
        return "router"
    if "mediarenderer" in upnp:
        return (
            "televisor"
            if "samsung" in (o.fabricante or "").lower() or "tv" in _norm(o.nombre)
            else "reproductor multimedia"
        )
    servicios = " ".join(s.lower() for s in o.servicios)
    for claves, tipo in _POR_SERVICIO:
        if any(c in servicios for c in claves):
            return tipo
    return "desconocido"


class InventarioEntorno:
    def __init__(self, dominios_controlables: frozenset = frozenset({"light", "media_player"})) -> None:
        self._dominios = dominios_controlables
        self._dispositivos: dict[str, Dispositivo] = {}

    def dispositivos(self) -> list[Dispositivo]:
        return sorted(
            self._dispositivos.values(), key=lambda d: tuple(int(x) for x in d.ip.split(".") if x.isdigit()) or (0,)
        )

    def actualizar(self, observaciones: list[Observacion], entidades_ha=()) -> list[Transicion]:
        """Incorpora una ronda de descubrimiento y devuelve lo que CAMBIÓ."""
        vistas, conflictos_de_la_ronda = _fusionar(observaciones)
        transiciones: list[Transicion] = []
        ahora = time.time()
        for ip, o in sorted(vistas.items()):
            previo = self._dispositivos.get(ip)
            if previo is None and o.identidad:
                previo = self._mover_si_cambio_de_ip(o, vistas, transiciones)
            tipo = identificar(o)
            caps = capacidades_de(o)
            if previo is not None and tipo == "desconocido":
                # Apagada, una TV solo responde a ARP: lo ya identificado en esta sesión no se degrada.
                tipo = previo.tipo
                caps = caps | previo.capacidades
                o = replace(o, nombre=o.nombre or previo.nombre, modelo=o.modelo or previo.modelo)
            entidad = self._entidad_de(o, entidades_ha)
            if previo is None:
                nivel = self._nivel(tipo, entidad, caps, False)
                transiciones.append(Transicion(ip, tipo, "nuevo"))
                self._dispositivos[ip] = Dispositivo(
                    ip,
                    o.mac,
                    o.nombre,
                    o.fabricante,
                    o.modelo,
                    tipo,
                    o.servicios,
                    o.fuentes,
                    nivel,
                    entidad,
                    caps,
                    o.identidad,
                    o.tipo_declarado,
                    conflicto=conflictos_de_la_ronda.get(ip),
                    estado_operativo=o.estado_operativo,
                    estado_visto=ahora if o.estado_operativo else None,
                )
                continue
            conflicto = _conflicto(previo, o)
            if not previo.presente:
                transiciones.append(Transicion(ip, tipo, "reaparece"))
            previo.presente, previo.visto_ultimo = True, ahora
            previo.conflicto = conflicto or conflictos_de_la_ronda.get(ip) or previo.conflicto
            previo.nivel = self._nivel(tipo, entidad, caps | previo.capacidades, previo.efecto_verificado)
            # Con conflicto de tipo NO se pisa lo anterior: se conserva y se marca.
            previo.tipo = previo.tipo if (conflicto and o.tipo_declarado) else tipo
            previo.entidad_ha = entidad
            previo.servicios, previo.fuentes = previo.servicios | o.servicios, previo.fuentes | o.fuentes
            if not conflicto:
                # Con conflicto, lo que dice la fuente contradictoria NO se adopta: si no, a la ronda siguiente ya no
                # habría contradicción visible y el impostor ganaría igual (revisión ECC 2026-10-22).
                previo.capacidades, previo.identidad = previo.capacidades | caps, previo.identidad or o.identidad
                previo.tipo_declarado = previo.tipo_declarado or o.tipo_declarado
                if o.estado_operativo:
                    # Sin lectura nueva (timeout, solo ARP) se CONSERVA el anterior con su hora: no se borra ni se
                    # convierte en reposo. Con conflicto no se adopta (misma razón que el resto de la fuente).
                    previo.estado_operativo, previo.estado_visto = o.estado_operativo, ahora
            previo.nombre = o.nombre if o.tipo_declarado and o.nombre and not conflicto else (previo.nombre or o.nombre)
        for ip, d in self._dispositivos.items():
            if d.presente and ip not in vistas:
                d.presente = False
                transiciones.append(Transicion(ip, d.tipo, "ausente"))
        return sorted(transiciones, key=lambda t: t.ip)

    def _mover_si_cambio_de_ip(self, o: Observacion, vistas, transiciones) -> Dispositivo | None:
        """Si la identidad DECLARADA ya se conoce en otra IP que ya no responde, es el mismo equipo: DHCP le
        dio otra dirección. Sin identidad declarada no se mueve nada: la MAC no sirve (repetidor)."""
        for ip_vieja, d in list(self._dispositivos.items()):
            if d.identidad == o.identidad and ip_vieja not in vistas:
                del self._dispositivos[ip_vieja]
                d.ip = o.ip
                self._dispositivos[o.ip] = d
                d.presente = True  # no es una reaparición: nunca dejó de existir
                transiciones.append(Transicion(o.ip, d.tipo, "cambia_ip"))
                return d
        return None

    def registrar_efecto(self, entidad_ha: str, verificado: bool) -> None:
        """El Motor Único comprobó (o no) un efecto real sobre la entidad. Es la ÚNICA vía a
        EFECTO_VERIFICADO: no se deduce del descubrimiento. Sobre un equipo que no conozco no inventa nada."""
        if not verificado:
            return
        for d in self._dispositivos.values():
            if d.entidad_ha == entidad_ha:
                d.efecto_verificado = True
                d.nivel = EFECTO_VERIFICADO

    def _entidad_de(self, o: Observacion, entidades_ha) -> str | None:
        """Integrado = HA tiene una entidad con el MISMO nombre que el dispositivo anuncia. No se adivina."""
        nombre = _norm(o.nombre)
        solo_declarado = bool(o.fuentes & _FUENTES_DECLARATIVAS) and not (o.fuentes - _FUENTES_DECLARATIVAS - {"arp"})
        if not nombre or solo_declarado:
            # Un nombre que SOLO llega por una declaración UDP sin autenticar (ONVIF, DDP) no da control: un impostor en
            # una IP silenciosa se haría pasar por la TV y AURA diría que la controla (INV-9; security-reviewer 2026-10-22).
            return None
        # HA titula por nombre + «(MODELO)»: solo se acepta si ese modelo es el que el propio dispositivo anuncia.
        con_modelo = f"{nombre} ({_norm(o.modelo)})" if o.modelo else None
        casan = [entidad for entidad, amigable in entidades_ha if _norm(amigable) in (nombre, con_modelo)]
        # HA crea `remote.X` y `media_player.X` con el mismo nombre para una TV: manda la controlable.
        return next((e for e in casan if e.split(".", 1)[0] in self._dominios), casan[0] if casan else None)

    def _nivel(self, tipo: str, entidad: str | None, capacidades: frozenset, efecto: bool) -> str:
        if entidad is not None:
            if entidad.split(".", 1)[0] not in self._dominios:
                return INTEGRADO
            return EFECTO_VERIFICADO if efecto else CONTROLABLE
        if tipo == "desconocido":
            return DESCUBIERTO
        return CARACTERIZADO if capacidades else IDENTIFICADO


def _conflicto(previo: Dispositivo, o: Observacion) -> str | None:
    """Dos fuentes que contradicen tipo o identidad declarados. Se marca; no se elige a ciegas."""
    if o.tipo_declarado and previo.tipo_declarado and o.tipo_declarado != previo.tipo_declarado:
        return f"una fuente dice «{previo.tipo_declarado}» y otra «{o.tipo_declarado}»"
    # Una declaración (ONVIF, DDP: UDP sin autenticar) que contradice el tipo que OTRA fuente ya dedujo tampoco se
    # elige a ciegas: un ProbeMatch falso en la IP de la TV la reescribía como «cámara» (revisión ECC 2026-10-22).
    if o.tipo_declarado and not previo.tipo_declarado and previo.tipo not in ("desconocido", o.tipo_declarado):
        return f"una fuente dice «{previo.tipo}» y otra «{o.tipo_declarado}»"
    if o.identidad and previo.identidad and o.identidad != previo.identidad:
        return f"dos identidades distintas: «{previo.identidad}» y «{o.identidad}»"
    return None


_QUE_FALTA = {
    DESCUBIERTO: "sé que hay algo, pero no anuncia qué es",
    IDENTIFICADO: "sé qué es; para poder hablar con él falta integrarlo en Home Assistant",
    CARACTERIZADO: "sé qué es y qué ofrece; para poder usarlo falta integrarlo y autorizarlo",
    INTEGRADO: (
        "Home Assistant tiene una entidad con su nombre, pero su tipo no está en la lista verde: no actúo sobre él"
    ),
    AUTORIZADO: (
        "integrado y con una acción de lista verde ya autorizada (D4); aún no he comprobado el efecto sobre este equipo"
    ),
    EFECTO_VERIFICADO: "lo controlo y ya comprobé un efecto real sobre él (encender/apagar con relectura)",
    CONTROLABLE: (
        "Home Assistant tiene una entidad con su nombre: puedo encenderlo o apagarlo por el Motor "
        "Único, actuando siempre sobre la entidad de Home Assistant, no sobre lo que se anuncia"
    ),
}

#: Capacidad -> lo que AURA podría hacer a través de ella. Orden fijo para que la voz lo diga igual.
_VERBO = (
    ("audio_entrada", "escuchar"),
    ("audio_salida", "hablar"),
    ("video_entrada", "ver"),
    ("video_salida", "mostrar"),
)
_OFRECE = {"audio_entrada": "micrófono", "audio_salida": "sonido", "video_entrada": "vídeo", "video_salida": "pantalla"}

#: Cómo mira AURA, y lo que por construcción NO ve. Se dice siempre: la ausencia de un equipo en la lista
#: no significa que no exista.
_COMO_MIRO = (
    "Cómo miro: los vecinos que este equipo ya conoce (ARP) y lo que los dispositivos anuncian "
    "(mDNS y SSDP), sin credenciales. No veo lo que ni se anuncia ni ha hablado con este equipo "
    "—un grabador, una consola o un teléfono pueden estar en casa sin aparecer aquí—, ni lo que "
    "solo habla por Bluetooth: Bluetooth no lo exploro."
)


def _es_local(d: Dispositivo) -> bool:
    return "local" in d.fuentes


def _verbos(capacidades: frozenset, local: bool) -> list[str]:
    # La cámara LOCAL existe, pero ver sigue pendiente de decisión (percepción visual): no se ofrece.
    return [v for c, v in _VERBO if c in capacidades and not (local and c == "video_entrada")]


def _presencia(dispositivos: list[Dispositivo]) -> list[str]:
    """Dónde puede estar AURA HOY y dónde solo PODRÍA. Describir una superficie no la activa."""
    locales = [d for d in dispositivos if _es_local(d) and d.presente and _verbos(d.capacidades, True)]
    hoy = (
        "; ".join(
            f"en {d.nombre or 'este equipo'} ({d.ip}): {', '.join(_verbos(d.capacidades, True))}" for d in locales
        )
        or "ninguna superficie verificada en esta exploración"
    )
    lineas = [f"Dónde puedo estar hoy: {hoy}."]
    posibles = [d for d in dispositivos if not _es_local(d) and d.presente and _verbos(d.capacidades, False)]
    if posibles:
        lineas.append("Superficies posibles, sin integrar ni autorizar (no las activo):")
        for d in posibles:
            privado = (
                " — vídeo o audio privado: exige autorización explícita"
                if {"video_entrada", "audio_entrada"} & d.capacidades
                else " — requiere integración y autorización"
            )
            lineas.append(f"  · {d.ip} {d.tipo}: {', '.join(_verbos(d.capacidades, False))}{privado}")
    return lineas


def via_de_integracion(d: Dispositivo) -> tuple[str, str] | None:
    """Para un equipo NO integrado: la vía LEGÍTIMA de integración y qué falta. Derivado SOLO de lo que el
    equipo ya anuncia y del estado de gobierno; no sondea, no prueba credenciales, no rompe pairing. `None`
    si ya está integrado. Responde a la pregunta «¿cuál es la vía legítima y qué falta?», no «¿puedo colarme?»."""
    if d.entidad_ha is not None:
        return None
    serv = " ".join(s.lower() for s in d.servicios) + " " + " ".join(str(f).lower() for f in d.fuentes)
    if d.tipo == "televisor":
        return (
            "integración de TV en Home Assistant (SamsungTV/DLNA)",
            "que pulses «Permitir» en la propia TV (confirmación física)",
        )
    if (
        d.tipo in ("cámara", "grabador de vídeo (DVR)")
        or "rtsp" in serv
        or "onvif" in serv
        or "video_entrada" in d.capacidades
    ):
        return (
            "integración de cámara/DVR en Home Assistant por ONVIF/RTSP",
            "la credencial del dispositivo y la decisión de gobierno sobre la visión (percepción visual)",
        )
    if "consola" in d.tipo:
        return (
            "integración de consola en Home Assistant si expone un servicio de control",
            "un servicio de control real: hoy solo anuncia presencia, no admite órdenes conocidas",
        )
    if d.tipo != "desconocido":
        return (
            "aún sin vía de control conocida con las fuentes actuales",
            "que el equipo anuncie un servicio de control, u otra fuente que lo caracterice",
        )
    return (
        "método de conexión desconocido: solo responde a ARP",
        "que el equipo anuncie algún servicio, u otra fuente que lo identifique",
    )


def _como_conectar(dispositivos: list) -> str:
    """Para lo que AURA aún no controla: la vía legítima y qué falta. Sin prometer control."""
    # El equipo local NO es algo a integrar por Home Assistant: es la superficie de AURA (su cámara está
    # tras la decisión de visión, se dice en su propia línea). Se excluye de «cómo conectar».
    pendientes = [d for d in dispositivos if d.presente and not _es_local(d)]
    # `via_de_integracion` devuelve None para lo YA integrado: ese None es lo que lo deja fuera de la lista.
    # `Any`: el filtro de abajo es el ÚNICO que quita los None (lo protege un mutante de semana2).
    vias: list[tuple[Dispositivo, Any]] = [(d, via_de_integracion(d)) for d in pendientes]
    vias = [(d, v) for d, v in vias if v is not None]
    if not vias:
        return ""
    lineas = [f"  · {d.ip} ({d.tipo}): {via}; falta: {falta}" for d, (via, falta) in vias]
    return "\nCómo conectar lo que aún no controlo (vía legítima; no lo hago solo):\n" + "\n".join(lineas)


def _antiguedad(segundos: float) -> str:
    minutos = int(max(segundos, 0) // 60)
    if minutos < 1:
        return "hace un momento"
    if minutos < 60:
        return f"hace {minutos} min"
    return f"hace {minutos // 60} h"


def describir_estado_operativo(d: Dispositivo, ahora: float) -> str:
    """Función pura (`ahora` inyectable). Vacío si no hay nada que decir; «estado desconocido» para una consola
    sin lectura. Una lectura de un ausente o de más de 15 min se dice como dato antiguo."""
    if not d.estado_operativo or d.estado_visto is None:
        return "estado desconocido" if "consola" in (d.tipo_declarado or "") else ""
    edad = max(ahora - d.estado_visto, 0)
    estado = d.estado_operativo.replace("_", " ")
    cuando = _antiguedad(edad)
    if not d.presente or edad > ESTADO_VIGENCIA_S:
        return f"último estado conocido, según su protocolo: {estado} {cuando} (lectura, no verificación física)"
    return f"según su protocolo, estaba {estado} {cuando} (lectura, no verificación física)"


def describir(inventario: InventarioEntorno, ahora: float | None = None) -> str:
    ahora = time.time() if ahora is None else ahora
    dispositivos = inventario.dispositivos()
    if not dispositivos:
        return "No he descubierto ningún dispositivo en la red local.\n" + _COMO_MIRO
    lineas = []
    for d in dispositivos:
        quien = d.nombre or d.fabricante or d.tipo
        estado = "" if d.presente else " — ahora AUSENTE"
        detalle = _QUE_FALTA[d.nivel]
        if _es_local(d):
            detalle = "es donde corro: aquí escucho y hablo"
            if "video_entrada" in d.capacidades:
                detalle += "; tiene cámara, pero no la uso: la percepción visual espera una decisión"
        if d.tipo == "teléfono":
            detalle += "; es presencia técnica: no sé de quién es"
        ofrece = ", ".join(_OFRECE[c] for c, _v in _VERBO if c in d.capacidades)
        if ofrece:
            detalle += f"; ofrece: {ofrece}"
        estado_op = describir_estado_operativo(d, ahora)
        if estado_op:
            detalle += f"; {estado_op}"
        if d.conflicto:
            detalle += f"; CONFLICTO de evidencia: {d.conflicto} — no decido cuál es"
        lineas.append(f"• {d.ip}: {d.tipo} ({quien}) — {d.nivel}{estado}. {detalle}.")
    presentes = sum(d.presente for d in dispositivos)
    return (
        f"Esto es lo que conozco de mi entorno ({presentes} presentes de {len(dispositivos)}):\n"
        + "\n".join(lineas)
        + "\n"
        + "\n".join(_presencia(dispositivos))
        + _como_conectar(dispositivos)
        + "\n"
        + _COMO_MIRO
    )


def describir_fuentes(fuentes: list) -> str:
    """Las fuentes que hoy NO aportan evidencia, dichas explícitamente. Sin esto, «no lo veo» se leería
    como «no existe»."""
    faltan = [f for f in fuentes if f.estado != "activa"]
    if not faltan:
        return ""
    lineas = [
        f"  · {f.nombre}: {f.estado.replace('_', ' ')}" + (f" ({f.detalle})" if f.detalle else "") for f in faltan
    ]
    return "\nFuentes que aún no aporto (podrían mostrar más equipos):\n" + "\n".join(lineas)


# ------------------------------------------------------------- la pregunta y el componente --

from collections.abc import Callable  # noqa: E402

from .. import observability as obs  # noqa: E402
from .intencion import normalizar  # noqa: E402

#: Formas cerradas de preguntar qué hay alrededor. Por frase completa: no roba nada a otras superficies.
_CONSULTAS = frozenset(
    {
        "que hay conectado",
        "que hay conectado alrededor",
        "que hay conectado a tu alrededor",
        "que dispositivos hay",
        "que dispositivos ves",
        "que dispositivos conoces",
        "que dispositivos hay en casa",
        "que hay en la red",
        "que conoces de tu entorno",
        "que aparatos hay",
        "que hay a tu alrededor",
        "que ves en la red",
        "que hay en casa conectado",
    }
)


def es_consulta_de_entorno(texto: str) -> bool:
    t = normalizar(texto)
    for signo in "¿?¡!.,":
        t = t.replace(signo, " ")
    palabras = t.split()
    while palabras and palabras[0] in ("aurora", "aura", "oye"):
        palabras.pop(0)
    return " ".join(palabras) in _CONSULTAS


class ConocimientoDelEntorno:
    """Lo que AURA sabe de su entorno: descubre bajo demanda, recuerda en el proceso, registra los cambios.

    No es un almacén nuevo: el inventario vive en memoria y la HISTORIA de los cambios va al audit log
    (ADR-0023). Las piezas de E/S —descubrir la red, leer las entidades de Home Assistant— se inyectan
    desde la composición: el Core no sabe de sockets.
    """

    def __init__(
        self,
        descubrir: Callable[[], list],
        entidades_ha: Callable[[], list] = lambda: [],
        inventario: InventarioEntorno | None = None,
        fuentes: list[Fuente] | None = None,
    ) -> None:
        self._descubrir = descubrir
        self._entidades_ha = entidades_ha
        self.inventario = inventario or InventarioEntorno()
        #: Qué fuentes de evidencia existen y en qué estado. Preparadas-pero-bloqueadas (router, Bluetooth)
        #: se declaran: su ausencia en el mapa NO significa que la casa esté vacía.
        self._fuentes = fuentes or []

    def registrar_efecto(self, entidad_ha: str, verificado: bool) -> None:
        self.inventario.registrar_efecto(entidad_ha, verificado)

    def explorar(self, trace_id: str) -> str:
        try:
            observaciones = self._descubrir()
        except OSError as e:
            obs.log("WARN", "entorno", f"no se pudo explorar la red: {e}", trace_id, audit=True)
            return f"No pude explorar la red local ahora mismo ({e}). No te cuento nada que no haya visto."
        try:
            entidades = self._entidades_ha()
        except OSError as e:
            # Sin Home Assistant se sigue viendo la red: solo no se puede afirmar integración.
            obs.log("WARN", "entorno", f"Home Assistant no respondio al explorar: {e}", trace_id, audit=True)
            entidades = []
        for t in self.inventario.actualizar(observaciones, entidades_ha=entidades):
            obs.log("CORE", "entorno", f"dispositivo {t.cambio}: {t.tipo} en {t.ip}", trace_id, audit=True)
        return describir(self.inventario) + describir_fuentes(self._fuentes)
