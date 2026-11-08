"""Adaptador REAL de Home Assistant (Bible 6.3: HA como hub, contrato 6.1).

Hasta la campaña del 2026-09-27 AURA solo tenía `HomeAssistantMock`: «encender_dispositivo» contestaba
`ok` sin tocar nada del mundo. Descubierto `[EJEC]` en la red de la casa: una TV Samsung real y ningún
Home Assistant. La Bible 6.3 manda integrarse con HA, «no con cada dispositivo directamente», así que el
camino es este adaptador, no uno por dispositivo.

**Una orden no está hecha porque se envió.** Tras llamar al servicio, el adaptador relee el estado del
dispositivo y solo devuelve `ok` si CAMBIÓ al esperado. Si HA acepta la llamada y el dispositivo no se
mueve —apagado a medias, integración que ignora la orden—, el resultado es `sin_efecto`, que el
redactor ya cuenta como lo que es. `comando -> dispositivo -> efecto -> confirmación`.

LO QUE NO HACE, A PROPÓSITO:
- **No amplía nada.** Implementa las capacidades que el catálogo declara en lista verde: encender y
  apagar (D4, Bible 6.3) y el volumen de un `media_player` (acta del ecosistema doméstico, 2026-10-22,
  §4). Cualquier otra orden se rechaza.
- **No adivina el dispositivo.** Si el nombre no casa con una entidad de HA, lo dice.
- **No muestra el token.** Viaja en la cabecera y en ningún resultado ni registro.
- **Sin dependencias nuevas.** `urllib` de la biblioteca estándar; HA vive fuera de AURA.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .. import observability as obs
from ..core.hogar import ESTADOS_APAGADA, ESTADOS_ENCENDIDA, texto_seguro
from ..core.operaciones import ErrorDeValidacion

_SERVICIO = {"encender_dispositivo": ("turn_on", "on"), "apagar_dispositivo": ("turn_off", "off")}

#: Órdenes de ATRIBUTO (volumen de la TV): servicio de `media_player`, cuerpo extra, atributo que se relee
#: y sentido esperado. A diferencia de encender/apagar, el efecto no es el `state` sino un atributo, y si HA
#: no lo expone la orden no se envía: sin poder releerlo, «enviada» nunca podría pasar a «hecha».
_ATRIBUTO = {
    "subir_volumen": ("volume_up", None, "volume_level", "sube"),
    "bajar_volumen": ("volume_down", None, "volume_level", "baja"),
    "silenciar": ("volume_mute", True, "is_volume_muted", True),
    "quitar_silencio": ("volume_mute", False, "is_volume_muted", False),
}

#: Dominios de Home Assistant que la lista verde alcanza. **Hallazgo ALTO de la auditoría independiente
#: (2026-09-27):** el catálogo marca encender/apagar como verde pensando en LUCES (Bible 6.3, D4), pero el
#: adaptador llamaba a `turn_off` sobre cualquier entidad: «apaga el congelador» sobre `switch.congelador`
#: habría pasado como si fuera una luz. Un `switch` puede ser cualquier cosa —una bomba, una estufa—, así
#: que queda fuera. Ante la duda, fuera de la lista verde (ADR-0003).
_DOMINIOS_VERDES = frozenset({"light", "media_player"})


#: Nombres genéricos con los que la gente se refiere a un TIPO de dispositivo, y su dominio en HA.
_TIPO_GENERICO = {
    "tele": "media_player",
    "tv": "media_player",
    "televisor": "media_player",
    "television": "media_player",
    "tele de la sala": "media_player",
    "luz": "light",
    "lampara": "light",
    "foco": "light",
}


def _sin_tildes(texto: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _sin_articulo(texto: str) -> str:
    palabras = texto.split()
    return " ".join(palabras[1:]) if palabras and palabras[0] in ("el", "la", "los", "las") else texto


#: Cuánto se relee el estado esperando que el dispositivo cambie. `[EJEC]` cierre de la semana 2: una TV
#: Samsung despertada por red confirmó a los 5,2 s una vez y a los 5 s no la siguiente. El bucle sale en
#: cuanto el estado cambia: la espera larga solo se paga cuando la orden NO surte efecto.
ESPERA_CONFIRMACION_S = 15.0


class HogarSinRespuesta(ErrorDeValidacion):
    """Home Assistant dejó de responder a mitad de una orden. Sin esto el `TimeoutError` subía como
    `OSError` y el Motor Único lo contaba como «fallo del sistema de archivos» (`[EJEC]`, semana 2)."""


class HogarCredencialRechazada(ErrorDeValidacion, PermissionError):
    """Home Assistant rechazó el token de AURA (HTTP 401/403). Es `ErrorDeValidacion` para que el Motor
    Único lo cuente como rechazo con su motivo real, y `PermissionError` (un `OSError`) para que quien ya
    tolera un HA caído —el arranque, el entorno— lo tolere igual. Nunca «no respondió»: sí respondió."""


class HogarOrdenRechazada(ErrorDeValidacion):
    """Home Assistant RESPONDIÓ al envío con un error HTTP (4xx/5xx distinto de 401/403): rechazó la orden. No es
    «no respondió» (sí contestó) ni credencial inválida; el código HTTP viaja en el motivo y en el audit log."""


class HogarNoDisponible(RuntimeError):
    """Home Assistant no responde (se usa en el ARRANQUE). Se dice, no se finge (`INV-9`)."""


class OrdenNoAdmisible(ErrorDeValidacion):
    """Dispositivo inexistente o capacidad que el hogar no atiende.

    Hereda de `ErrorDeValidacion` porque es el idioma que el Motor Único convierte en `estado: error`.
    Encontrado `[EJEC]` contra el HA real: con una excepción propia, el error se ESCAPABA del motor y
    habría tumbado el turno en vez de decir «ese dispositivo no existe».
    """


def _http(metodo: str, url: str, cuerpo: dict | None = None, token: str = "", tope_s: float = 10):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(
        url, data=datos, method=metodo, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(peticion, timeout=tope_s) as r:  # noqa: S310 (URL de configuracion local)
        return json.loads(r.read().decode() or "null")


class HomeAssistantReal:
    name = "home_assistant"
    capabilities = ["encender_dispositivo", "apagar_dispositivo", *_ATRIBUTO]

    def __init__(self, url: str, token: str, http: Callable = _http, espera_s: float = ESPERA_CONFIRMACION_S) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._http = http
        self._espera_s = espera_s
        self._hechos: set[str] = set()
        self._enviados: set[str] = set()  # eventos cuya orden HA aceptó (o pudo aceptar): ya no se reintentan

    # ----------------------------------------------------------------------------- arranque --

    def comprobar(self) -> str:
        """Para que el arranque diga la verdad sobre el hogar antes del primer turno."""
        try:
            respuesta = self._llamar("GET", "/api/")
        except OSError as e:  # incluye la credencial rechazada, que también es un PermissionError
            raise HogarNoDisponible(f"Home Assistant no responde en {self._url}: {e}") from e
        return f"{self._url} ({(respuesta or {}).get('message', '?')})"

    def entidades(self) -> list[tuple[str, str]]:
        """(entity_id, nombre visible) de todo lo que Home Assistant integra. Solo lectura: no actúa."""
        return [
            (e["entity_id"], str(e.get("attributes", {}).get("friendly_name", "")))
            for e in self._llamar("GET", "/api/states") or []
        ]

    def estado_actual(self, dispositivo: str) -> dict:
        """Estado ACTUAL de un dispositivo, tal como lo da Home Assistant. Solo lectura: no actúa ni pasa por el Motor
        (es lo mismo que `entidades()`, para una sola entidad). Conserva `last_changed` para decir desde cuándo."""
        entidad = self._entidad(dispositivo, None)
        atributos = _atributos(entidad)
        return {
            "entity_id": entidad["entity_id"],
            "nombre": str(atributos.get("friendly_name") or entidad["entity_id"]),
            "state": entidad.get("state", "?"),
            "attributes": atributos,
            "last_changed": entidad.get("last_changed"),
        }

    # ------------------------------------------------------------------------------ contrato --

    async def simular(self, command: str, args: dict, trace_id: str) -> dict:
        """Dry-run: qué pasaría, leyendo el estado real, SIN actuar."""
        if command in _ATRIBUTO:
            _servicio, _extra, atributo, sentido = _ATRIBUTO[command]
            entidad, estado = await asyncio.to_thread(self._resolver, args.get("device", ""))
            return {"viable": True, "efecto": f"{entidad}: {atributo} {sentido} (estado {estado})"}
        _servicio, esperado = self._servicio(command)
        entidad, estado = await asyncio.to_thread(self._resolver, args.get("device", ""))
        return {"viable": True, "efecto": f"{entidad}: {estado} -> {esperado}"}

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        servicio, esperado = ("", "") if command in _ATRIBUTO else self._servicio(command)
        if event_id in self._hechos:  # idempotencia (3.3 §3): mismo evento, un solo efecto físico
            return {"status": "duplicate"}
        self._hechos.add(event_id)  # reservado mientras se actúa; se libera si NINGÚN envío fue aceptado
        try:
            if command in _ATRIBUTO:
                return await asyncio.to_thread(
                    self._actuar_atributo, command, args.get("device", ""), trace_id, event_id
                )
            return await asyncio.to_thread(self._actuar, servicio, esperado, args.get("device", ""), trace_id, event_id)
        except BaseException as e:
            if event_id not in self._enviados:
                self._hechos.discard(event_id)  # un rechazo previo al envío no quema el evento: se puede reintentar
            if isinstance(e, urllib.error.HTTPError) and e.code not in (401, 403):
                raise HogarSinRespuesta(
                    f"Home Assistant respondió HTTP {e.code} al buscar «{args.get('device', '')}»; no he ejecutado nada"
                ) from e
            if isinstance(e, ValueError) and not isinstance(e, ErrorDeValidacion):
                raise HogarSinRespuesta(
                    f"Home Assistant dio una respuesta ilegible al buscar «{args.get('device', '')}» ({e}); "
                    "no he ejecutado nada"
                ) from e
            if isinstance(e, OSError) and not isinstance(e, (HogarCredencialRechazada, urllib.error.HTTPError)):
                raise HogarSinRespuesta(
                    f"Home Assistant no respondió al buscar «{args.get('device', '')}» ({e}); no he ejecutado nada"
                ) from e
            raise

    # ----------------------------------------------------------------------------- interior --

    def _servicio(self, command: str) -> tuple[str, str]:
        if command not in _SERVICIO:
            raise OrdenNoAdmisible(f"el hogar no atiende '{command}'")
        return _SERVICIO[command]

    def _llamar(self, metodo: str, ruta: str, cuerpo: dict | None = None):
        try:
            return self._http(metodo, self._url + ruta, cuerpo, token=self._token)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise HogarCredencialRechazada(
                    f"Home Assistant rechazó la credencial de AURA (HTTP {e.code}); revisa el token"
                ) from e
            raise

    def resolver_dispositivo(self, dispositivo: str, dentro_de: frozenset[str] | None = None) -> tuple[str, str]:
        """(entity_id, nombre visible) del dispositivo, buscando SOLO entre `dentro_de` si se da.

        Es la misma resolución de `_resolver`, expuesta para que el Core sepa SOBRE QUÉ entidad va a
        actuar antes de proponer (DP-VOZ-ACCION C2/C3). No hay un segundo resolutor."""
        entidad = self._entidad(dispositivo, dentro_de)
        return entidad["entity_id"], str(_atributos(entidad).get("friendly_name") or entidad["entity_id"])

    def _resolver(self, dispositivo: str) -> tuple[str, str]:
        """(entity_id, estado) del dispositivo. Nunca adivina."""
        entidad = self._entidad(dispositivo, None)
        return entidad["entity_id"], entidad.get("state", "?")

    def _entidad(self, dispositivo: str, dentro_de: frozenset[str] | None) -> dict:
        """La entidad de HA que la persona quiso decir. Nunca adivina.

        Primero por entity_id o nombre visible exactos. Si no, un nombre GENÉRICO («la tele», «la luz»)
        vale solo cuando en Home Assistant hay EXACTAMENTE UN dispositivo de ese tipo: la persona dice
        «apaga la tele», no «apaga Tv sala fmilia medina». Con dos televisores, se dice y no se elige.
        Con `dentro_de`, solo cuentan las entidades de ese conjunto: «la tele» es la que está dentro.
        """
        buscado = dispositivo.strip().lower()
        entidades = self._llamar("GET", "/api/states") or []
        if dentro_de is not None:
            entidades = [e for e in entidades if e["entity_id"] in dentro_de]
        for e in entidades:
            nombre = str(_atributos(e).get("friendly_name", "")).strip().lower()
            if buscado and buscado in (e["entity_id"].lower(), nombre):
                return e
        dominio = _TIPO_GENERICO.get(_sin_articulo(_sin_tildes(buscado)))
        if dominio:
            candidatas = [e for e in entidades if e["entity_id"].split(".", 1)[0] == dominio]
            if len(candidatas) == 1:
                return candidatas[0]
            if len(candidatas) > 1:
                nombres = ", ".join(
                    texto_seguro(_atributos(c).get("friendly_name") or c["entity_id"]) for c in candidatas
                )
                raise OrdenNoAdmisible(f"hay varios dispositivos que pueden ser '{dispositivo}': {nombres}; dime cuál")
        raise OrdenNoAdmisible(f"el dispositivo '{dispositivo}' no existe en Home Assistant")

    def _enviar(
        self, dominio: str, servicio: str, cuerpo: dict, entidad: str, trace_id: str, event_id: str = ""
    ) -> None:
        """Envía la orden al servicio de HA. El estado que importa es el releído después, no este envío."""
        try:
            self._llamar("POST", f"/api/services/{dominio}/{servicio}", cuerpo)
            self._enviados.add(event_id)
            obs.log("ACT", "ha-real", f"EJECUTA {servicio} sobre {entidad}", trace_id, audit=True)
        except HogarCredencialRechazada:
            raise
        except urllib.error.HTTPError as e:
            # HTTPError es un OSError: sin esta rama se contaba como «no respondió». HA contestó y dijo que no.
            que = "falló al procesar" if e.code >= 500 else "rechazó"
            raise HogarOrdenRechazada(
                f"Home Assistant {que} la orden para «{entidad}» (HTTP {e.code}); no la doy por ejecutada"
            ) from e
        except ValueError:
            self._enviados.add(event_id)
            # El POST salió pero la respuesta no es JSON legible: no dice nada del efecto. Se relee el estado.
            obs.log(
                "WARN", "ha-real", f"{servicio} sobre {entidad}: respuesta ilegible; se relee", trace_id, audit=True
            )
        except TimeoutError:
            self._enviados.add(event_id)
            # La orden SALIÓ; HA tardó en contestar (la TV arrancando). Lo que cuenta es el estado releído.
            obs.log(
                "WARN", "ha-real", f"{servicio} sobre {entidad} sin respuesta a tiempo; se relee", trace_id, audit=True
            )
        except OSError as e:
            # Conexión rechazada / HA caído (auditoría independiente, cierre S2): la orden NO salió.
            # «No la doy por ejecutada», no «no la ejecuté»: un corte a mitad de envío no dice si llegó.
            raise HogarSinRespuesta(
                f"Home Assistant no respondió al enviar la orden a «{entidad}» ({e}); no la doy por ejecutada"
            ) from e

    def _actuar_atributo(self, orden: str, dispositivo: str, trace_id: str, event_id: str = "") -> dict:
        """Volumen/silencio de un `media_player`: se envía solo si el efecto podrá comprobarse."""
        servicio, extra, atributo, esperado = _ATRIBUTO[orden]
        entidad, antes, atributos = self._leer_entidad(dispositivo)
        dominio = entidad.split(".", 1)[0]
        nombre = texto_seguro(atributos.get("friendly_name") or entidad)
        if dominio != "media_player":
            raise OrdenNoAdmisible(
                f"el volumen solo se maneja en un media_player, y '{entidad}' es del dominio '{dominio}'"
            )
        if antes in ESTADOS_APAGADA:
            espera = " (Home Assistant la ve en espera)" if antes == "standby" else ""
            raise OrdenNoAdmisible(f"{nombre} está apagada{espera}: no puedo cambiar el volumen")
        if antes not in ESTADOS_ENCENDIDA:
            raise OrdenNoAdmisible(_no_accesible(nombre, antes))
        if not _legible(atributo, atributos.get(atributo)):
            raise OrdenNoAdmisible(
                f"Home Assistant no expone el {'volumen' if atributo == 'volume_level' else 'silencio'} de {nombre}: "
                "al no poder comprobar el cambio, no lo hago"
            )
        valor_antes = atributos[atributo]
        cuerpo = {"entity_id": entidad} if extra is None else {"entity_id": entidad, "is_volume_muted": extra}
        self._enviar(dominio, servicio, cuerpo, entidad, trace_id, event_id)
        limite = time.monotonic() + self._espera_s
        while True:
            actual = self._releer(entidad)
            valor_despues = _atributos(actual).get(atributo)  # sin relectura legible NO hay valor: nunca el anterior
            cambio = _cambio_esperado(esperado, valor_antes, valor_despues)
            if cambio or time.monotonic() >= limite:
                break
            time.sleep(min(0.5, self._espera_s))
        despues = str(actual.get("state") or "?")
        evidencia = _evidencia(despues) if _legible(atributo, valor_despues) else "ninguna"
        asumido = _atributos(actual).get("assumed_state") is True  # SmartIR y similares: HA no lee el aparato
        if asumido:
            evidencia = "estado_asumido_por_ha"
        # `ya_en_estado`: el silencio YA estaba como se pedía. Se envió igualmente (el estado de HA puede estar
        # obsoleto) pero no se observó ningún cambio: no es un efecto verificado.
        ya_en_estado = (
            cambio and evidencia == "estado_ha_tras_orden" and isinstance(esperado, bool) and valor_antes == esperado
        )
        verificado = cambio and evidencia == "estado_ha_tras_orden" and not ya_en_estado
        obs.log(
            "ACT",
            "ha-real",
            f"{entidad}: {atributo} {valor_antes} -> {valor_despues} (verificado={verificado})",
            trace_id,
            audit=True,
        )
        return {
            "status": "ok" if verificado else "sin_efecto",
            "device": entidad,
            "verificado": verificado,
            "ya_en_estado": ya_en_estado,
            "atributo": atributo,
            "valor_antes": valor_antes,
            "valor_despues": valor_despues,
            "estado_antes": antes,
            "estado_despues": despues,
            "evidencia": evidencia,
        }

    def _leer_entidad(self, dispositivo: str) -> tuple[str, str, dict]:
        entidad = self._entidad(dispositivo, None)
        return entidad["entity_id"], entidad.get("state", "?"), _atributos(entidad)

    def _releer(self, entidad: str) -> dict:
        try:
            leido = self._llamar("GET", f"/api/states/{entidad}")
        except HogarCredencialRechazada:
            raise
        except ValueError:
            return {}  # respuesta ilegible: estado desconocido, nunca verificado
        except urllib.error.HTTPError as e:
            raise HogarSinRespuesta(
                f"Home Assistant respondió HTTP {e.code} al comprobar «{entidad}»; no sé si la orden surtió efecto"
            ) from e
        except OSError as e:
            raise HogarSinRespuesta(_no_comprobado(entidad, e)) from e
        if not isinstance(leido, dict) or ("attributes" in leido and not isinstance(leido["attributes"], dict)):
            return {}  # malformada: estado desconocido, nunca verificado
        return leido

    def _actuar(self, servicio: str, esperado: str, dispositivo: str, trace_id: str, event_id: str = "") -> dict:
        entidad, antes = self._resolver(dispositivo)
        dominio = entidad.split(".", 1)[0]
        if dominio not in _DOMINIOS_VERDES:
            raise OrdenNoAdmisible(f"el dominio '{dominio}' ({entidad}) no esta en la lista verde del hogar")
        if antes not in ESTADOS_ENCENDIDA | ESTADOS_APAGADA:
            # `unavailable`/`unknown`/otro: ni se sabe si está encendido ni apagado, y enviar no podría comprobarse.
            raise OrdenNoAdmisible(_no_accesible(entidad, antes))
        # «Pedido» = el conjunto de estados que Home Assistant usa para encendido/apagado (el mismo que las consultas).
        pedido = ESTADOS_ENCENDIDA if esperado == "on" else ESTADOS_APAGADA
        self._enviar(dominio, servicio, {"entity_id": entidad}, entidad, trace_id, event_id)
        # CONFIRMACIÓN: se relee el estado hasta que cambie o se agote la espera.
        limite = time.monotonic() + self._espera_s
        despues = antes
        while True:
            leido = self._releer(entidad)
            despues = str(leido.get("state") or "?")
            if despues in pedido or time.monotonic() >= limite:
                break
            time.sleep(min(0.5, self._espera_s))
        # Verificado = HA REPORTA el estado pedido tras la orden y antes NO lo estaba (si ya lo estaba, no se
        # observó ningún cambio: no se cuenta como efecto verificado). Es lo que HA reporta, no un efecto físico.
        asumido = _atributos(leido).get("assumed_state") is True  # HA publica un estado optimista, no lee el aparato
        ya_en_estado = antes in pedido and despues in pedido and not asumido
        verificado = despues in pedido and antes not in pedido and not asumido
        obs.log("ACT", "ha-real", f"{entidad}: {antes} -> {despues} (verificado={verificado})", trace_id, audit=True)
        return {
            "status": "ok" if verificado else "sin_efecto",
            "device": entidad,
            "estado_antes": antes,
            "estado_despues": despues,
            "verificado": verificado,
            "ya_en_estado": ya_en_estado,
            "evidencia": "estado_asumido_por_ha" if asumido else _evidencia(despues),
        }


def _atributos(entidad: dict) -> dict:
    """Los atributos de una entidad de HA, o `{}` si no son un objeto (respuesta malformada)."""
    atributos = entidad.get("attributes")
    return atributos if isinstance(atributos, dict) else {}


def _evidencia(estado_despues: str) -> str:
    """Nivel de evidencia del resultado: el estado que HA reporta tras la orden, o ninguna si no se pudo leer."""
    return "estado_ha_tras_orden" if estado_despues != "?" else "ninguna"


def _no_comprobado(entidad: str, error: OSError) -> str:
    a_tiempo = " a tiempo" if isinstance(error, TimeoutError) else ""
    return f"Home Assistant no respondió{a_tiempo} al comprobar «{entidad}» ({error}); no sé si la orden surtió efecto"


def _no_accesible(nombre: str, estado: str) -> str:
    return (
        f"{texto_seguro(nombre)} no está accesible ahora: Home Assistant la ve «{texto_seguro(estado)}». No envío nada"
    )


def _legible(atributo: str, valor: object) -> bool:
    """¿El valor sirve para COMPROBAR? HA puede exponer la clave con `None` (TV encendida sin DMR, revisión ECC
    2026-10-22, MEDIO): eso no es un volumen. El silencio tiene que ser un booleano; el volumen, un número."""
    if atributo == "is_volume_muted":
        return isinstance(valor, bool)
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _cambio_esperado(esperado, antes, despues) -> bool:
    """¿El atributo releído se movió en el sentido pedido? `sube`/`baja` comparan con el valor previo. Un valor
    releído ilegible nunca cuenta como cambio."""
    atributo = "is_volume_muted" if isinstance(esperado, bool) else "volume_level"
    if not _legible(atributo, despues):
        return False
    if esperado == "sube":
        return despues > antes
    if esperado == "baja":
        return despues < antes
    return despues == esperado
