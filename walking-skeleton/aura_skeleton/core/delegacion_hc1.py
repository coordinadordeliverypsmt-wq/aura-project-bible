"""Lado HC-1 de la delegación: seguimiento de órdenes y validación de acuses/resultados (A2, N6, N7, HAL-041-2).

Módulo PURO (firma, reloj y registro se inyectan). Estados, del más débil al único que cuenta (§12.4):

  EMITIDA -> ACEPTADA (acuse firmado) -> RESULTADO_FIRMADO (el nodo DECLARA ejecución; prueba quién, no corrección)
          -> VALIDADO (verificador PROPIO de la capacidad en HC-1) -> INCORPORADO (registro auditable)

Solo INCORPORADO cuenta como `completada` (N6). Un latido nunca llega aquí. Estados terminales sin trabajo hecho:
INTERRUMPIDA (sin acuse: reintentable), AMBIGUO (hubo acuse: la orden pudo tener efecto), VERIFICACION_FALLIDA.

Vinculación OBLIGATORIA tarea<->orden<->ejecución<->resultado: el resultado debe citar `tarea`, `intento`,
`id_ejecucion` y `hash_tarea` (sha256 de los bytes firmados de la orden) exactos, y su `id_nodo` debe ser el del
subject del que llegó, el de la clave que firma y el destinatario de la orden.

Durabilidad (M-2): con un `Diario` inyectado (`adapters/diario_hc1.py`) CADA transición se anota de forma durable
ANTES de aplicarse en memoria, y al construir el seguimiento se reconstruye el estado desde el diario. Las ejecuciones
EMITIDA/ACEPTADA que ya vencieron pasan entonces a INTERRUMPIDA/AMBIGUO explícitos. Un resultado que llega tras
AMBIGUO/INTERRUMPIDA NO se acepta solo: solo `resolver_ambigua` (autoridad declarada + firma + vínculo) lo admite y lo
registra. Todas las operaciones son atómicas entre hilos (`RLock`).
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from .delegacion import (
    CAPACIDADES,
    DOMINIO_ACUSE,
    DOMINIO_RESULTADO,
    Motivo,
    RechazoOrden,
    Reloj,
    Verificador,
    abrir_sobre,
    hash_de,
    leer_json_estricto,
    validar_campos_acuse,
    validar_campos_orden,
    validar_campos_resultado,
    verificar_y_leer,
)


class Estado(StrEnum):
    EMITIDA = "emitida"
    ACEPTADA = "aceptada"
    RESULTADO_FIRMADO = "resultado_firmado"
    VALIDADO = "validado"
    INCORPORADO = "incorporado"
    INTERRUMPIDA = "interrumpida"
    AMBIGUO = "ambiguo"
    VERIFICACION_FALLIDA = "verificacion_fallida"


_EN_CURSO = frozenset({Estado.EMITIDA, Estado.ACEPTADA})


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
    recibida_en: float | None = None
    sobre_resultado: bytes | None = None
    salida: str | None = None
    resuelta_por: str | None = None
    """Quién resolvió una ejecución ambigua por la vía explícita (`resolver_ambigua`), si ocurrió."""
    motivo_resolucion: str | None = None

    @property
    def completada(self) -> bool:
        return self.estado is Estado.INCORPORADO


Registrar = Callable[[dict[str, Any]], None]
"""Escribe el hecho auditable (en producción, la cadena de hash de HC-1; en las pruebas, un log sintético)."""


class Diario(Protocol):
    """Diario durable propio de HC-1. `anotar` lanza `RechazoOrden(DIARIO_NO_DURABLE)` si no logra durabilidad."""

    def anotar(self, registro: dict[str, Any]) -> None: ...
    def recuperar(self) -> tuple[list[dict[str, Any]], int]: ...


MOTIVO_MAX = 256


@dataclass
class SeguimientoHC1:
    verificar: Verificador
    """Verificador de firmas de NODO: kid == id_nodo."""
    reloj: Reloj
    _por_id: dict[str, Ejecucion] = field(default_factory=dict)
    rechazos: list[Motivo] = field(default_factory=list)
    diario: Diario | None = None
    autoridades: frozenset[str] = frozenset()
    """Quiénes pueden resolver una ejecución ambigua (declarado por configuración, nunca por el mensaje)."""
    bytes_truncados: int = 0
    """Bytes de línea final truncada que el diario descartó al recuperar (DETECCIÓN de una caída a mitad de escritura)."""
    recuperadas: int = 0
    _cerrojo: threading.RLock = field(default_factory=threading.RLock, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.diario is not None:
            self._recuperar()

    # -- diario ----------------------------------------------------------------------------------------------
    def _anotar(self, registro: dict[str, Any]) -> None:
        if self.diario is not None:
            self.diario.anotar(registro)

    def _recuperar(self) -> None:
        assert self.diario is not None
        registros, self.bytes_truncados = self.diario.recuperar()
        for r in registros:
            self._aplicar(r)
        self.recuperadas = len(self._por_id)
        self.vencer()  # lo vencido mientras HC-1 estaba caída pasa a INTERRUMPIDA/AMBIGUO, y queda anotado

    def _aplicar(self, r: Mapping[str, Any]) -> None:
        """Reaplica UN registro del diario sobre el estado en memoria (sin volver a anotarlo)."""
        try:
            ev = r["ev"]
            if ev == "emision":
                abierto = abrir_sobre(base64.b64decode(r["sobre"], validate=True))
                campos = leer_json_estricto(abierto.payload)
                validar_campos_orden(campos)
                ej = Ejecucion(
                    campos["id_ejecucion"], campos["tarea"], campos["intento"], campos["destinatario"],
                    campos["capacidad"], campos["argumentos"], hash_de(abierto.payload),
                    base64.b64decode(r["sobre"], validate=True), float(r["vence_en"]),
                )  # fmt: skip
                self._por_id[ej.id_ejecucion] = ej
                return
            ej = self._por_id[r["id"]]
            if ev == "acuse":
                ej.estado, ej.recibida_en = Estado.ACEPTADA, r["recibida_en"]
            elif ev == "resultado" or ev == "resolucion":
                sobre = base64.b64decode(r["sobre"], validate=True)
                ej.sobre_resultado = sobre
                ej.salida = leer_json_estricto(abrir_sobre(sobre).payload)["salida"]
                ej.estado = Estado.RESULTADO_FIRMADO
                if ev == "resolucion":
                    ej.resuelta_por, ej.motivo_resolucion = r["por"], r["motivo"]
            elif ev == "validacion":
                ej.estado = Estado.VALIDADO if r["ok"] is True else Estado.VERIFICACION_FALLIDA
            elif ev == "incorporado":
                ej.estado = Estado.INCORPORADO
            elif ev == "interrupcion":
                ej.estado = Estado(r["estado"])
            else:
                raise KeyError(ev)
        except (KeyError, ValueError, TypeError, RechazoOrden) as e:
            raise RechazoOrden(Motivo.DIARIO_ILEGIBLE, "registro del diario inválido") from e

    # -- emisión --------------------------------------------------------------------------------------------
    def registrar_emision(self, sobre_orden: bytes, techo_total_s: float) -> Ejecucion:
        """Registra una orden recién firmada por NUESTRO firmador. El techo de duración total NO se prorroga."""
        with self._cerrojo:
            return self._registrar_emision(sobre_orden, techo_total_s)

    def _registrar_emision(self, sobre_orden: bytes, techo_total_s: float) -> Ejecucion:
        abierto = abrir_sobre(sobre_orden)
        try:
            campos = leer_json_estricto(abierto.payload)
        except ValueError as e:  # profundidad, UTF-8, duplicados: nunca RecursionError
            raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "payload") from e
        if not isinstance(campos, dict):
            raise RechazoOrden(Motivo.SOBRE_MALFORMADO, "payload")
        validar_campos_orden(campos)
        if campos["id_ejecucion"] in self._por_id:
            raise RechazoOrden(Motivo.ORDEN_REPETIDA, "id_ejecucion")
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
        self.rechazos.append(motivo)
        return RechazoOrden(motivo, detalle)

    def _leer(self, sobre: bytes, dominio: bytes, id_nodo_subject: str) -> dict[str, Any]:
        try:
            _, c = verificar_y_leer(sobre, dominio, self.verificar, kid_esperado=id_nodo_subject)
            if dominio == DOMINIO_RESULTADO:
                validar_campos_resultado(c)
            else:
                validar_campos_acuse(c)
        except RechazoOrden as e:
            raise self._rechazar(e.motivo) from e
        if c["id_nodo"] != id_nodo_subject:
            raise self._rechazar(Motivo.NODO_AJENO, "id_nodo distinto del subject")
        return c

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

    def resolver_ambigua(self, id_ejecucion: str, por: str, motivo: str, resultado_firmado: bytes) -> Ejecucion:
        """ÚNICA vía para admitir un resultado de una ejecución AMBIGUA/INTERRUMPIDA (M-3).

        Exige: `por` entre las `autoridades` declaradas, un `motivo` no vacío, y que el resultado sea un resultado
        FIRMADO válido del nodo destinatario, vinculado a ESA orden (tarea, intento, id_ejecucion, hash_tarea). Deja la
        ejecución en RESULTADO_FIRMADO (sigue pasando por `validar` e `incorporar`) y registra quién y por qué."""
        with self._cerrojo:
            if not isinstance(por, str) or por not in self.autoridades:
                raise self._rechazar(Motivo.SIN_AUTORIDAD, "resolutor sin autoridad declarada")
            if not isinstance(motivo, str) or not motivo.strip() or len(motivo) > MOTIVO_MAX:
                raise self._rechazar(Motivo.CAMPO_INVALIDO, "motivo")
            ej = self._por_id.get(id_ejecucion)
            if ej is None:
                raise self._rechazar(Motivo.EJECUCION_DESCONOCIDA, "id_ejecucion")
            if ej.estado not in (Estado.AMBIGUO, Estado.INTERRUMPIDA):
                raise self._rechazar(Motivo.EJECUCION_NO_EN_CURSO, "solo se resuelve lo ambiguo o interrumpido")
            c = self._leer(resultado_firmado, DOMINIO_RESULTADO, ej.destinatario)
            if c["id_ejecucion"] != id_ejecucion:
                raise self._rechazar(Motivo.VINCULO_ROTO, "id_ejecucion")
            self._vincular(c, ej.destinatario)
            self._anotar(
                {
                    "ev": "resolucion", "id": id_ejecucion, "por": por, "motivo": motivo,
                    "sobre": base64.b64encode(resultado_firmado).decode("ascii"),
                }
            )  # fmt: skip
            ej.sobre_resultado = resultado_firmado
            ej.salida = c["salida"]
            ej.estado = Estado.RESULTADO_FIRMADO
            ej.resuelta_por, ej.motivo_resolucion = por, motivo
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
        ej.estado = Estado.VALIDADO if ok else Estado.VERIFICACION_FALLIDA
        return ok

    def incorporar(self, id_ejecucion: str, registrar: Registrar) -> None:
        """Estado 5: registra el hecho auditable. Si `registrar` falla, la ejecución sigue VALIDADA (se repite)."""
        with self._cerrojo:
            self._incorporar(id_ejecucion, registrar)

    def _incorporar(self, id_ejecucion: str, registrar: Registrar) -> None:
        ej = self._por_id[id_ejecucion]
        if ej.estado is not Estado.VALIDADO or ej.sobre_resultado is None:
            raise RechazoOrden(Motivo.EJECUCION_NO_EN_CURSO, "solo se incorpora lo validado")
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
