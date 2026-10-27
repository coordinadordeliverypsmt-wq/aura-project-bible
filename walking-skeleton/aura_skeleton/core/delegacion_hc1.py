"""Lado HC-1 de la delegación: seguimiento de órdenes y validación de acuses/resultados (A2, N6, N7, HAL-041-2).

Módulo PURO (firma, reloj y registro se inyectan). Estados, del más débil al único que cuenta (§12.4):

  EMITIDA -> ACEPTADA (acuse firmado) -> RESULTADO_FIRMADO (el nodo DECLARA ejecución; prueba quién, no corrección)
          -> VALIDADO (verificador PROPIO de la capacidad en HC-1) -> INCORPORADO (registro auditable)

Solo INCORPORADO cuenta como `completada` (N6). Un latido nunca llega aquí. Estados terminales sin trabajo hecho:
INTERRUMPIDA (sin acuse: reintentable), AMBIGUO (hubo acuse: la orden pudo tener efecto), VERIFICACION_FALLIDA.

Incorporación (C1): VALIDADO -> INCORPORANDO (anotado de forma durable ANTES de registrar) -> `registrar` -> INCORPORADO.
`registrar` debe ser IDEMPOTENTE por `id_ejecucion` y expone `ya_registrado(id)`: `incorporar` lo consulta antes de
registrar, así que ni un fallo del diario ni una caída en cualquier punto duplican el hecho `resultado_remoto`. Tras un
reinicio, «incorporando sin incorporado» es el estado EXPLÍCITO INCORPORACION_INCIERTA y se resuelve consultando
`ya_registrado`: si consta, se cierra sin volver a registrar; si no, se registra UNA vez.

Vinculación OBLIGATORIA tarea<->orden<->ejecución<->resultado: el resultado debe citar `tarea`, `intento`,
`id_ejecucion` y `hash_tarea` (sha256 de los bytes firmados de la orden) exactos, y su `id_nodo` debe ser el del
subject del que llegó, el de la clave que firma y el destinatario de la orden.

Durabilidad (M-2): con un `Diario` inyectado (`adapters/diario_hc1.py`) CADA transición se anota de forma durable
ANTES de aplicarse en memoria, y al construir el seguimiento se reconstruye el estado desde el diario. Las ejecuciones
EMITIDA/ACEPTADA que ya vencieron pasan entonces a INTERRUMPIDA/AMBIGUO explícitos. Un resultado que llega tras
AMBIGUO/INTERRUMPIDA NO se acepta solo: solo `resolver_ambigua` lo admite, y exige una AUTORIZACIÓN FIRMADA por una clave
de autoridad humana distinta de la de HC-1 y de las de los nodos (dominio propio, caducidad corta, nonce de un solo uso
persistido), además de la firma y el vínculo del resultado. Al releer el diario se RE-VERIFICAN las firmas y las
transiciones: un diario manipulado falla cerrado con motivo. Todas las operaciones son atómicas entre hilos (`RLock`).

3.ª revisión (ALTO-1, MEDIO-2..5, BAJOS): INSTANCIA ÚNICA por diario (`flock` del centinela, ver `adapters/diario_hc1.py`;
la secuencia `ya_registrado -> registrar` de `incorporar` va bajo ella); configuración EXPLÍCITA y obligatoria (diario,
`kid_hc1`, `verificar_hc1`, `fuente_revocados`, `kids_autoridad` o `sin_autoridad_humana`); lo no idempotente no se
reemite con CUALQUIER intento previo; al releer se RECALCULA la validación, se re-verifica la firma de HC-1 de cada
emisión y se rechazan tiempos no finitos; la autorización de resolución se liga al `hash` del resultado concreto; los
kids de autoridad retirados solo sirven para releer el historial; `rechazos` es un anillo con contador.
"""

from __future__ import annotations

import base64
import math
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from .delegacion import (
    AUTORIZACION_VIDA_MAX_S,
    CAPACIDADES,
    DOMINIO_ACUSE,
    DOMINIO_ORDEN,
    DOMINIO_RESOLUCION,
    DOMINIO_RESULTADO,
    TOLERANCIA_FUTURO_S,
    Motivo,
    RechazoOrden,
    Reloj,
    SobreAbierto,
    Verificador,
    abrir_sobre,
    es_texto_id,
    exigir_fuente_revocados,
    hash_de,
    validar_campos_acuse,
    validar_campos_orden,
    validar_campos_resolucion,
    validar_campos_resultado,
    verificar_y_leer,
)


class Estado(StrEnum):
    EMITIDA = "emitida"
    ACEPTADA = "aceptada"
    RESULTADO_FIRMADO = "resultado_firmado"
    VALIDADO = "validado"
    INCORPORANDO = "incorporando"
    INCORPORACION_INCIERTA = "incorporacion_incierta"
    INCORPORADO = "incorporado"
    INTERRUMPIDA = "interrumpida"
    AMBIGUO = "ambiguo"
    VERIFICACION_FALLIDA = "verificacion_fallida"


_EN_CURSO = frozenset({Estado.EMITIDA, Estado.ACEPTADA})
_INTERRUPCIONES = frozenset({Estado.INTERRUMPIDA, Estado.AMBIGUO})
"""Únicos estados a los que puede llevar un registro `interrupcion` del diario (cualquier otro => diario manipulado)."""
_BLOQUEA_NO_IDEMPOTENTE = frozenset(Estado)
"""Estados de un intento previo que impiden emitir otro de la misma tarea si la capacidad NO es idempotente (at-most-once
por tarea, MEDIO-2): CUALQUIERA posterior a la emisión (EMITIDA, ACEPTADA, RESULTADO_FIRMADO, VALIDADO,
VERIFICACION_FALLIDA, INCORPORANDO, INCORPORACION_INCIERTA, INCORPORADO, AMBIGUO, INTERRUMPIDA): la orden pudo tener
efecto aunque el resultado no se haya validado o incorporado. Rehacer una tarea con efectos exige una tarea NUEVA."""
RECHAZOS_MEMORIA_MAX = 256
"""Tope del anillo `rechazos` en memoria (BAJO 4): el total real va en `rechazos_total`."""
_RE_ID_NODO = re.compile(r"[0-9a-f]{32}")


@dataclass
class Ejecucion:
    id_ejecucion: str
    tarea: str
    intento: int
    destinatario: str
    capacidad: str
    argumentos: Mapping[str, Any]
    hash_tarea: str
    sobre_orden: bytes
    vence_en: float
    estado: Estado = Estado.EMITIDA
    validacion: bool | None = None
    """Resultado del verificador PROPIO de la capacidad (`None` = aún no validada). Al releer el diario se RECALCULA."""
    recibida_en: float | None = None
    sobre_resultado: bytes | None = None
    salida: str | None = None
    resuelta_por: str | None = None
    """Quién resolvió una ejecución ambigua por la vía explícita (`resolver_ambigua`), si ocurrió."""
    motivo_resolucion: str | None = None

    @property
    def completada(self) -> bool:
        return self.estado is Estado.INCORPORADO


class Registrar(Protocol):
    """Destino del hecho auditable (en producción, la cadena de hash de HC-1; en las pruebas, un log sintético).

    CONTRATO: IDEMPOTENTE por `id_ejecucion`. `ya_registrado` es OBLIGATORIO: `incorporar` lo consulta antes de
    registrar, y es lo único que permite resolver una incorporación incierta sin duplicar el hecho."""

    def __call__(self, hecho: dict[str, Any]) -> None: ...
    def ya_registrado(self, id_ejecucion: str) -> bool: ...


class Diario(Protocol):
    """Diario durable propio de HC-1. `anotar` lanza `RechazoOrden(DIARIO_NO_DURABLE)` si no logra durabilidad."""

    @property
    def abierto(self) -> bool:
        """¿Sigue siendo la INSTANCIA ÚNICA sobre su almacenamiento? (`False` tras `cerrar`)."""
        ...

    def anotar(self, registro: dict[str, Any]) -> None: ...
    def recuperar(self) -> tuple[list[dict[str, Any]], int]: ...
    def cerrar(self) -> None: ...


@dataclass
class SeguimientoHC1:
    """Seguimiento de HC-1. Configuración EXPLÍCITA y obligatoria (MEDIO-3/4): no hay defaults abiertos."""

    verificar: Verificador
    """Verificador de firmas de NODO: kid == id_nodo."""
    reloj: Reloj
    diario: Diario
    """Diario durable OBLIGATORIO (MEDIO-4): sin él no hay seguimiento. Debe ser la INSTANCIA ÚNICA sobre su directorio."""
    verificar_hc1: Verificador
    """Verificador de la firma de HC-1: se re-verifica la `emision` al registrarla y al releer el diario (MEDIO-5)."""
    kid_hc1: str
    """kid de la clave de HC-1, obligatorio y no vacío. La autoridad humana no puede ser ese kid."""
    fuente_revocados: Callable[[], frozenset[str]]
    """Lista VIVA de nodos revocados (C2), OBLIGATORIA: se consulta en CADA acuse/resultado/resolución. Quien no quiera
    revocación pasa `SinRevocacion()`, que lo declara."""
    kids_autoridad: frozenset[str]
    """kids de autoridad aceptados para resolver una ejecución ambigua (configuración, nunca el mensaje). No pueden ser
    el de HC-1 (`kid_hc1`) ni parecerse a un id de nodo: la autoridad es OTRA clave. Vacío SOLO con `sin_autoridad_humana`."""
    verificar_autoridad: Verificador | None = None
    """Verificador de las claves de AUTORIDAD HUMANA (aparte de `verificar`, que es de nodos): sin él nadie resuelve."""
    sin_autoridad_humana: bool = False
    """Declaración EXPLÍCITA de que no hay autoridad humana: `resolver_ambigua` rechaza siempre."""
    kids_autoridad_retirados: frozenset[str] = frozenset()
    """kids de autoridad RETIRADOS (rotación): se aceptan SOLO para re-verificar resoluciones ya registradas en el
    diario, JAMÁS para resolver nada nuevo. Retirar un kid no impide arrancar sobre un diario que ya lo usó."""
    _por_id: dict[str, Ejecucion] = field(default_factory=dict)
    rechazos: list[Motivo] = field(default_factory=list)
    """Últimos `RECHAZOS_MEMORIA_MAX` rechazos (anillo); `rechazos_total` cuenta TODOS."""
    rechazos_total: int = 0
    _nonces: set[str] = field(default_factory=set, repr=False)
    bytes_truncados: int = 0
    """Bytes de línea final truncada que el diario descartó al recuperar (DETECCIÓN de una caída a mitad de escritura)."""
    recuperadas: int = 0
    _cerrojo: threading.RLock = field(default_factory=threading.RLock, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        try:
            self._validar_configuracion()
            self._recuperar()
        except BaseException:
            self.cerrar()  # una construcción fallida NO deja la instancia única retenida (ni a medias)
            raise

    def _validar_configuracion(self) -> None:
        if self.diario is None:
            raise ValueError("el diario es obligatorio: sin diario durable no hay seguimiento")
        if not callable(getattr(self.diario, "anotar", None)) or not callable(getattr(self.diario, "recuperar", None)):
            raise ValueError("el diario debe exponer anotar() y recuperar()")
        if not hasattr(self.diario, "abierto"):
            raise ValueError("el diario debe exponer abierto (instancia única)")
        if not callable(self.verificar_hc1):
            raise ValueError("verificar_hc1 es obligatorio")
        if not es_texto_id(self.kid_hc1):
            raise ValueError("kid_hc1 es obligatorio y debe ser un kid válido")
        exigir_fuente_revocados(self.fuente_revocados)
        if not self.kids_autoridad and not self.sin_autoridad_humana:
            raise ValueError("kids_autoridad vacío exige declarar sin_autoridad_humana=True")
        if self.kids_autoridad and self.sin_autoridad_humana:
            raise ValueError("sin_autoridad_humana contradice kids_autoridad")
        if self.kids_autoridad & self.kids_autoridad_retirados:
            raise ValueError("un kid de autoridad no puede estar vigente y retirado a la vez")
        for kid in self.kids_autoridad | self.kids_autoridad_retirados:
            if kid == self.kid_hc1 or _RE_ID_NODO.fullmatch(kid):
                raise ValueError("la autoridad humana debe tener una clave distinta de la de HC-1 y de la de los nodos")

    def cerrar(self) -> None:
        """Suelta la instancia única del diario (idempotente): otra instancia podrá arrancar; esta deja de operar."""
        close = getattr(self.diario, "cerrar", None)  # un diario ausente (None) ya falló la validación
        if callable(close):
            close()

    def _exigir_instancia(self) -> None:
        if not self.diario.abierto:
            raise RechazoOrden(Motivo.INSTANCIA_DUPLICADA, "la instancia única del diario ya no está vigente")

    # -- diario ----------------------------------------------------------------------------------------------
    def _anotar(self, registro: dict[str, Any]) -> None:
        self._exigir_instancia()
        self.diario.anotar(registro)

    def _recuperar(self) -> None:
        registros, self.bytes_truncados = self.diario.recuperar()
        for r in registros:
            self._aplicar(r)
        self.recuperadas = len(self._por_id)
        # «incorporando sin incorporado»: estado EXPLÍCITO, se resuelve con ya_registrado
        for ej in self._por_id.values():
            if ej.estado is Estado.INCORPORANDO:
                ej.estado = Estado.INCORPORACION_INCIERTA
        self.vencer()  # lo vencido mientras HC-1 estaba caída pasa a INTERRUMPIDA/AMBIGUO, y queda anotado

    def _manipulado(self, detalle: str) -> RechazoOrden:
        return RechazoOrden(Motivo.DIARIO_ILEGIBLE, f"diario manipulado: {detalle}")

    def _aplicar(self, r: Mapping[str, Any]) -> None:
        """Reaplica UN registro del diario sobre el estado en memoria (sin volver a anotarlo).

        Fallo CERRADO: un registro mal formado, con firma que ya no verifica, o cuya transición no es posible desde el
        estado actual (p. ej. `incorporado` sin resultado) es un diario manipulado y se rechaza con motivo."""
        try:
            ev = r["ev"]
            if ev == "emision":
                self._aplicar_emision(r)
                return
            ej = self._por_id[r["id"]]
            if ev == "acuse":
                self._exigir_previo(ej, {Estado.EMITIDA})
                ej.estado, ej.recibida_en = Estado.ACEPTADA, self._tiempo_finito(r["recibida_en"])
            elif ev == "resultado":
                self._exigir_previo(ej, _EN_CURSO)
                self._aplicar_resultado(ej, base64.b64decode(r["sobre"], validate=True))
            elif ev == "resolucion":
                self._exigir_previo(ej, _INTERRUPCIONES)
                self._aplicar_resolucion(ej, r)
            elif ev == "validacion":
                self._exigir_previo(ej, {Estado.RESULTADO_FIRMADO})
                if not isinstance(r["ok"], bool):
                    raise self._manipulado("validación")
                ej.validacion = self._reverificar(ej)  # NO se confía en el «ok» anotado: se recalcula (MEDIO-5)
                if ej.validacion is not r["ok"]:
                    raise self._manipulado("validación distinta de la recalculada")
                ej.estado = Estado.VALIDADO if ej.validacion else Estado.VERIFICACION_FALLIDA
            elif ev == "incorporando":
                self._exigir_previo(ej, {Estado.VALIDADO})
                ej.estado = Estado.INCORPORANDO
            elif ev == "incorporado":
                self._exigir_previo(ej, {Estado.INCORPORANDO})
                ej.estado = Estado.INCORPORADO
            elif ev == "interrupcion":
                nuevo = Estado(r["estado"])
                esperado = {Estado.EMITIDA: Estado.INTERRUMPIDA, Estado.ACEPTADA: Estado.AMBIGUO}.get(ej.estado)
                if nuevo not in _INTERRUPCIONES or nuevo is not esperado:
                    raise self._manipulado("interrupción")
                ej.estado = nuevo
            else:
                raise KeyError(ev)
        except (KeyError, ValueError, TypeError, RechazoOrden) as e:
            if isinstance(e, RechazoOrden) and e.motivo is Motivo.DIARIO_ILEGIBLE:
                raise
            raise RechazoOrden(Motivo.DIARIO_ILEGIBLE, "registro del diario inválido") from e

    def _exigir_previo(self, ej: Ejecucion, permitidos: set[Estado] | frozenset[Estado]) -> None:
        if ej.estado not in permitidos:
            raise self._manipulado("transición imposible")

    @staticmethod
    def _tiempo_finito(valor: object) -> float:
        """Un tiempo releído del diario debe ser un número FINITO (`inf` haría que una ejecución no venciera nunca)."""
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
            raise RechazoOrden(Motivo.DIARIO_ILEGIBLE, "diario manipulado: tiempo no finito")
        return float(valor)

    def _leer_orden(self, sobre: bytes) -> tuple[SobreAbierto, dict[str, Any]]:
        """Verifica la FIRMA DE HC-1 de una orden (kid configurado, dominio de orden, forma canónica) y su esquema."""
        abierto, campos = verificar_y_leer(sobre, DOMINIO_ORDEN, self.verificar_hc1, kid_esperado=self.kid_hc1)
        validar_campos_orden(campos)
        if campos["kid"] != abierto.kid:
            raise RechazoOrden(Motivo.KID_DESCONOCIDO, "kid del sobre distinto del firmado")
        return abierto, campos

    def _reverificar(self, ej: Ejecucion) -> bool:
        """Re-ejecuta el verificador PROPIO de la capacidad sobre el resultado firmado releído."""
        cap = CAPACIDADES.get(ej.capacidad)
        if cap is None or ej.salida is None:
            raise self._manipulado("validación sin capacidad o sin salida")
        try:
            return bool(cap.verificar(ej.argumentos, ej.salida))
        except Exception as e:  # noqa: BLE001 - un verificador que falla al releer es un diario no confiable
            raise self._manipulado("el verificador de la capacidad falla") from e

    def _aplicar_emision(self, r: Mapping[str, Any]) -> None:
        sobre = base64.b64decode(r["sobre"], validate=True)
        abierto, campos = self._leer_orden(sobre)
        if campos["id_ejecucion"] in self._por_id:
            raise self._manipulado("emisión repetida")
        ej = Ejecucion(
            campos["id_ejecucion"], campos["tarea"], campos["intento"], campos["destinatario"],
            campos["capacidad"], campos["argumentos"], hash_de(abierto.payload), sobre,
            self._tiempo_finito(r["vence_en"]),
        )  # fmt: skip
        self._por_id[ej.id_ejecucion] = ej

    def _aplicar_resultado(self, ej: Ejecucion, sobre: bytes) -> None:
        """RE-VERIFICA el sobre de resultado al releerlo: firma del nodo, esquema y vínculo con ESTA ejecución."""
        c = self._leer_sin_contabilizar(sobre, DOMINIO_RESULTADO, ej.destinatario)
        if c["id_ejecucion"] != ej.id_ejecucion or c["tarea"] != ej.tarea or c["intento"] != ej.intento:
            raise self._manipulado("resultado de otra ejecución")
        if ej.hash_tarea != c["hash_tarea"]:
            raise self._manipulado("resultado de otra orden")
        ej.sobre_resultado, ej.salida, ej.estado = sobre, c["salida"], Estado.RESULTADO_FIRMADO

    def _aplicar_resolucion(self, ej: Ejecucion, r: Mapping[str, Any]) -> None:
        """Re-verifica la autorización humana Y el resultado; reconstruye los nonces ya usados."""
        autorizacion = base64.b64decode(r["autorizacion"], validate=True)
        kid, campos = self._leer_autorizacion(autorizacion, historica=True)  # un kid RETIRADO sirve aquí (y solo aquí)
        if campos["id_ejecucion"] != ej.id_ejecucion or campos["nonce"] in self._nonces:
            raise self._manipulado("autorización de otra ejecución o nonce repetido")
        sobre = base64.b64decode(r["sobre"], validate=True)
        if campos["hash_resultado"] != hash_de(sobre):
            raise self._manipulado("la autorización es de otro resultado")
        self._nonces.add(campos["nonce"])
        self._aplicar_resultado(ej, sobre)
        ej.resuelta_por, ej.motivo_resolucion = kid, campos["motivo"]

    # -- emisión --------------------------------------------------------------------------------------------
    def registrar_emision(self, sobre_orden: bytes, techo_total_s: float) -> Ejecucion:
        """Registra una orden recién firmada por NUESTRO firmador. El techo de duración total NO se prorroga."""
        with self._cerrojo:
            return self._registrar_emision(sobre_orden, techo_total_s)

    def _registrar_emision(self, sobre_orden: bytes, techo_total_s: float) -> Ejecucion:
        if (
            isinstance(techo_total_s, bool)
            or not isinstance(techo_total_s, (int, float))
            or not math.isfinite(techo_total_s)
        ):
            raise RechazoOrden(Motivo.CAMPO_INVALIDO, "techo_total_s")  # un techo infinito/NaN nunca vencería
        abierto, campos = self._leer_orden(sobre_orden)  # firma de HC-1 + esquema (no se registra lo que HC-1 no firmó)
        if campos["id_ejecucion"] in self._por_id:
            raise RechazoOrden(Motivo.ORDEN_REPETIDA, "id_ejecucion")
        cap = CAPACIDADES.get(campos["capacidad"])
        if (cap is None or not cap.idempotente) and any(
            o.tarea == campos["tarea"] and o.estado in _BLOQUEA_NO_IDEMPOTENTE for o in self._por_id.values()
        ):  # at-most-once POR TAREA: lo no idempotente con CUALQUIER intento previo NO se reemite (C3, MEDIO-2)
            raise RechazoOrden(Motivo.TAREA_CON_INTENTO_AMBIGUO, "intento previo de una capacidad con efectos")
        for otra in self._por_id.values():
            if otra.tarea == campos["tarea"] and (otra.estado in _EN_CURSO or otra.intento >= campos["intento"]):
                raise RechazoOrden(Motivo.EJECUCION_NO_EN_CURSO, "intento previo vivo o no creciente")
        ej = Ejecucion(
            campos["id_ejecucion"],
            campos["tarea"],
            campos["intento"],
            campos["destinatario"],
            campos["capacidad"],
            campos["argumentos"],
            hash_de(abierto.payload),
            sobre_orden,
            self.reloj.ahora() + techo_total_s,
        )
        self._anotar({"ev": "emision", "sobre": base64.b64encode(sobre_orden).decode("ascii"), "vence_en": ej.vence_en})
        self._por_id[ej.id_ejecucion] = ej
        return ej

    def ejecucion(self, id_ejecucion: str) -> Ejecucion | None:
        with self._cerrojo:
            return self._por_id.get(id_ejecucion)

    # -- entrada de mensajes del nodo ---------------------------------------------------------------------------
    def _rechazar(self, motivo: Motivo, detalle: str = "") -> RechazoOrden:
        self.rechazos_total += 1
        self.rechazos.append(motivo)
        if len(self.rechazos) > RECHAZOS_MEMORIA_MAX:
            del self.rechazos[0]  # anillo: la memoria no crece con un par que inunde de basura
        return RechazoOrden(motivo, detalle)

    def _leer_sin_contabilizar(self, sobre: bytes, dominio: bytes, id_nodo_subject: str) -> dict[str, Any]:
        """Verifica firma (la del `kid` == subject), esquema y que `id_nodo` sea el del subject. Lanza `RechazoOrden`."""
        _, c = verificar_y_leer(sobre, dominio, self.verificar, kid_esperado=id_nodo_subject)
        if dominio == DOMINIO_RESULTADO:
            validar_campos_resultado(c)
        else:
            validar_campos_acuse(c)
        if c["id_nodo"] != id_nodo_subject:
            raise RechazoOrden(Motivo.NODO_AJENO, "id_nodo distinto del subject")
        return c

    def _leer(self, sobre: bytes, dominio: bytes, id_nodo_subject: str) -> dict[str, Any]:
        try:
            if id_nodo_subject in self.fuente_revocados():  # lista VIVA (C2)
                raise RechazoOrden(Motivo.KID_REVOCADO, "nodo revocado")
            return self._leer_sin_contabilizar(sobre, dominio, id_nodo_subject)
        except RechazoOrden as e:
            raise self._rechazar(e.motivo, e.detalle) from e

    def _vincular(self, c: Mapping[str, Any], id_nodo_subject: str) -> Ejecucion:
        ej = self._por_id.get(c["id_ejecucion"])
        if ej is None:
            raise self._rechazar(Motivo.EJECUCION_DESCONOCIDA, "id_ejecucion")
        if ej.destinatario != id_nodo_subject:
            raise self._rechazar(Motivo.NODO_AJENO, "no es el destinatario de la orden")
        if c["tarea"] != ej.tarea or c["intento"] != ej.intento:
            raise self._rechazar(Motivo.VINCULO_ROTO, "tarea/intento")
        if c["hash_tarea"] != ej.hash_tarea:
            raise self._rechazar(Motivo.HASH_NO_CORRESPONDE, "hash_tarea")
        return ej

    def recibir_acuse(self, sobre: bytes, id_nodo_subject: str) -> Ejecucion:
        with self._cerrojo:
            return self._recibir_acuse(sobre, id_nodo_subject)

    def _recibir_acuse(self, sobre: bytes, id_nodo_subject: str) -> Ejecucion:
        c = self._leer(sobre, DOMINIO_ACUSE, id_nodo_subject)
        ej = self._vincular(c, id_nodo_subject)
        if ej.estado is Estado.ACEPTADA:
            raise self._rechazar(Motivo.ACUSE_DUPLICADO)
        if ej.estado is not Estado.EMITIDA:
            raise self._rechazar(Motivo.EJECUCION_NO_EN_CURSO)
        self._anotar({"ev": "acuse", "id": ej.id_ejecucion, "recibida_en": c["recibida_en"]})
        ej.estado = Estado.ACEPTADA
        ej.recibida_en = c["recibida_en"]  # informativo: el acuse NO prorroga `vence_en`
        return ej

    def recibir_resultado(self, sobre: bytes, id_nodo_subject: str) -> Ejecucion:
        with self._cerrojo:
            return self._recibir_resultado(sobre, id_nodo_subject)

    def _recibir_resultado(self, sobre: bytes, id_nodo_subject: str) -> Ejecucion:
        c = self._leer(sobre, DOMINIO_RESULTADO, id_nodo_subject)
        ej = self._vincular(c, id_nodo_subject)
        if ej.estado not in _EN_CURSO:
            motivo = (
                Motivo.RESULTADO_DUPLICADO
                if ej.estado in (Estado.RESULTADO_FIRMADO, Estado.VALIDADO, Estado.INCORPORADO)
                else Motivo.EJECUCION_NO_EN_CURSO
            )
            raise self._rechazar(motivo)
        self._anotar({"ev": "resultado", "id": ej.id_ejecucion, "sobre": base64.b64encode(sobre).decode("ascii")})
        ej.estado = Estado.RESULTADO_FIRMADO
        ej.sobre_resultado = sobre
        ej.salida = c["salida"]
        return ej

    def _leer_autorizacion(self, sobre: bytes, historica: bool = False) -> tuple[str, dict[str, Any]]:
        """Verifica una autorización de resolución: kid de AUTORIDAD configurado, firma con el verificador de
        autoridades y dominio propio, esquema cerrado. NO mira la vigencia (la releída del diario ya caducó).

        `historica=True` (solo al RELEER el diario) acepta además los kids RETIRADOS; una resolución nueva nunca."""
        aceptados = self.kids_autoridad | self.kids_autoridad_retirados if historica else self.kids_autoridad
        if (self.sin_autoridad_humana and not historica) or self.verificar_autoridad is None or not aceptados:
            raise RechazoOrden(Motivo.SIN_AUTORIDAD, "no hay autoridad configurada")
        abierto = abrir_sobre(sobre)
        if abierto.kid not in aceptados:
            raise RechazoOrden(Motivo.SIN_AUTORIDAD, "kid sin autoridad")
        _, c = verificar_y_leer(sobre, DOMINIO_RESOLUCION, self.verificar_autoridad)
        validar_campos_resolucion(c)
        return abierto.kid, c

    def _exigir_vigente(self, a: Mapping[str, Any]) -> None:
        ahora = self.reloj.ahora()
        if a["caduca_en"] <= ahora:
            raise RechazoOrden(Motivo.AUTORIZACION_CADUCADA, "caduca_en")
        if a["caduca_en"] <= a["emitida_en"] or a["caduca_en"] - a["emitida_en"] > AUTORIZACION_VIDA_MAX_S:
            raise RechazoOrden(Motivo.CADUCIDAD_EXCESIVA, "caduca_en")
        if a["emitida_en"] > ahora + TOLERANCIA_FUTURO_S:
            raise RechazoOrden(Motivo.EMITIDA_EN_EL_FUTURO, "emitida_en")

    def resolver_ambigua(self, id_ejecucion: str, autorizacion: bytes, resultado_firmado: bytes) -> Ejecucion:
        """ÚNICA vía para admitir un resultado de una ejecución AMBIGUA/INTERRUMPIDA (M-3, C3).

        Exige una AUTORIZACIÓN FIRMADA por una clave de autoridad humana (kid configurado, distinto de HC-1 y de los
        nodos; dominio `resolucion`; caducidad corta; nonce de un solo uso persistido) que cite ESTA ejecución, y que el
        resultado sea un resultado FIRMADO válido del nodo destinatario vinculado a ESA orden. Deja la ejecución en
        RESULTADO_FIRMADO (sigue pasando por `validar` e `incorporar`) y registra quién (kid) y por qué (firmado)."""
        with self._cerrojo:
            try:
                kid, a = self._leer_autorizacion(autorizacion)
                self._exigir_vigente(a)
            except RechazoOrden as e:
                raise self._rechazar(e.motivo, e.detalle) from e
            if a["id_ejecucion"] != id_ejecucion:
                raise self._rechazar(Motivo.VINCULO_ROTO, "la autorización es de otra ejecución")
            if a["nonce"] in self._nonces:
                raise self._rechazar(Motivo.NONCE_REUTILIZADO, "nonce")
            ej = self._por_id.get(id_ejecucion)
            if ej is None:
                raise self._rechazar(Motivo.EJECUCION_DESCONOCIDA, "id_ejecucion")
            if ej.estado not in _INTERRUPCIONES:
                raise self._rechazar(Motivo.EJECUCION_NO_EN_CURSO, "solo se resuelve lo ambiguo o interrumpido")
            # la autorización es de UN resultado concreto (BAJO 5)
            if a["hash_resultado"] != hash_de(resultado_firmado):
                raise self._rechazar(Motivo.HASH_NO_CORRESPONDE, "la autorización es de otro resultado")
            c = self._leer(resultado_firmado, DOMINIO_RESULTADO, ej.destinatario)
            if c["id_ejecucion"] != id_ejecucion:
                raise self._rechazar(Motivo.VINCULO_ROTO, "id_ejecucion")
            self._vincular(c, ej.destinatario)
            self._anotar(
                {
                    "ev": "resolucion", "id": id_ejecucion,
                    "autorizacion": base64.b64encode(autorizacion).decode("ascii"),
                    "sobre": base64.b64encode(resultado_firmado).decode("ascii"),
                }
            )  # fmt: skip
            self._nonces.add(a["nonce"])
            ej.sobre_resultado = resultado_firmado
            ej.salida = c["salida"]
            ej.estado = Estado.RESULTADO_FIRMADO
            ej.resuelta_por, ej.motivo_resolucion = kid, a["motivo"]
            return ej

    # -- validación propia e incorporación ----------------------------------------------------------------------
    def validar(self, id_ejecucion: str) -> bool:
        """Corre el verificador PROPIO de la capacidad (nunca se cree el «ok» del nodo)."""
        with self._cerrojo:
            return self._validar(id_ejecucion)

    def _validar(self, id_ejecucion: str) -> bool:
        ej = self._por_id[id_ejecucion]
        if ej.estado is not Estado.RESULTADO_FIRMADO or ej.salida is None:
            raise RechazoOrden(Motivo.EJECUCION_NO_EN_CURSO, "sin resultado firmado que validar")
        cap = CAPACIDADES[ej.capacidad]
        ok = cap.verificar(ej.argumentos, ej.salida)
        self._anotar({"ev": "validacion", "id": id_ejecucion, "ok": ok})
        ej.validacion = ok
        ej.estado = Estado.VALIDADO if ok else Estado.VERIFICACION_FALLIDA
        return ok

    def incorporar(self, id_ejecucion: str, registrar: Registrar) -> None:
        """Estado 5: registra el hecho auditable UNA sola vez (C1). Si algo falla a medias, la ejecución queda
        INCORPORANDO (o INCORPORACION_INCIERTA tras un reinicio) y el reintento consulta `ya_registrado`."""
        with self._cerrojo:
            self._incorporar(id_ejecucion, registrar)

    def _incorporar(self, id_ejecucion: str, registrar: Registrar) -> None:
        if not callable(getattr(registrar, "ya_registrado", None)):
            raise TypeError("el Registrar debe exponer ya_registrado(id_ejecucion): el contrato exige idempotencia")
        self._exigir_instancia()  # la secuencia ya_registrado -> registrar va BAJO la instancia única (ALTO-1)
        ej = self._por_id[id_ejecucion]
        incorporable = (Estado.VALIDADO, Estado.INCORPORANDO, Estado.INCORPORACION_INCIERTA)
        if ej.estado not in incorporable or ej.sobre_resultado is None:
            raise RechazoOrden(Motivo.EJECUCION_NO_EN_CURSO, "solo se incorpora lo validado")
        if ej.estado is Estado.VALIDADO:
            self._anotar(
                {"ev": "incorporando", "id": id_ejecucion}
            )  # durable ANTES de registrar: sin esto, una caída duplica
            ej.estado = Estado.INCORPORANDO
        if not registrar.ya_registrado(ej.id_ejecucion):
            registrar(
                {
                    "evento": "resultado_remoto",
                    "verificado": True,
                    "tarea": ej.tarea,
                    "intento": ej.intento,
                    "id_ejecucion": ej.id_ejecucion,
                    "id_nodo": ej.destinatario,
                    "hash_tarea": ej.hash_tarea,
                    "orden_firmada": base64.b64encode(ej.sobre_orden).decode("ascii"),
                    "resultado_firmado": base64.b64encode(ej.sobre_resultado).decode("ascii"),
                }
            )
        self._anotar({"ev": "incorporado", "id": id_ejecucion})
        ej.estado = Estado.INCORPORADO

    # -- conectividad ------------------------------------------------------------------------------------------
    def _interrumpir(self, ej: Ejecucion) -> None:
        # Sin acuse: la orden pudo no llegar (reintentable). Con acuse: pudo tener efecto => AMBIGUO.
        nuevo = Estado.INTERRUMPIDA if ej.estado is Estado.EMITIDA else Estado.AMBIGUO
        self._anotar({"ev": "interrupcion", "id": ej.id_ejecucion, "estado": nuevo.value})
        ej.estado = nuevo

    def marcar_desconexion(self, id_nodo: str) -> list[Ejecucion]:
        with self._cerrojo:
            return self._marcar_desconexion(id_nodo)

    def _marcar_desconexion(self, id_nodo: str) -> list[Ejecucion]:
        afectadas = [e for e in self._por_id.values() if e.destinatario == id_nodo and e.estado in _EN_CURSO]
        for e in afectadas:
            self._interrumpir(e)
        return afectadas

    def vencer(self) -> list[Ejecucion]:
        """Aplica el techo de duración total: lo que sigue en curso pasado `vence_en` se interrumpe."""
        with self._cerrojo:
            return self._vencer()

    def _vencer(self) -> list[Ejecucion]:
        ahora = self.reloj.ahora()
        vencidas = [e for e in self._por_id.values() if e.estado in _EN_CURSO and ahora > e.vence_en]
        for e in vencidas:
            self._interrumpir(e)
        return vencidas
