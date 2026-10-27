"""Lado HC-1 de la delegación: seguimiento de órdenes y validación de acuses/resultados (A2, N6, N7, HAL-041-2).

Módulo PURO (firma, reloj y registro se inyectan). Estados, del más débil al único que cuenta (§12.4):

  EMITIDA -> ACEPTADA (acuse firmado) -> RESULTADO_FIRMADO (el nodo DECLARA ejecución; prueba quién, no corrección)
          -> VALIDADO (verificador PROPIO de la capacidad en HC-1) -> INCORPORADO (registro auditable)

Solo INCORPORADO cuenta como `completada` (N6). Un latido nunca llega aquí. Estados terminales sin trabajo hecho:
INTERRUMPIDA (sin acuse: reintentable), AMBIGUO (hubo acuse: la orden pudo tener efecto), VERIFICACION_FALLIDA.

Vinculación OBLIGATORIA tarea<->orden<->ejecución<->resultado: el resultado debe citar `tarea`, `intento`,
`id_ejecucion` y `hash_tarea` (sha256 de los bytes firmados de la orden) exactos, y su `id_nodo` debe ser el del
subject del que llegó, el de la clave que firma y el destinatario de la orden.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

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

    @property
    def completada(self) -> bool:
        return self.estado is Estado.INCORPORADO


Registrar = Callable[[dict[str, Any]], None]
"""Escribe el hecho auditable (en producción, la cadena de hash de HC-1; en las pruebas, un log sintético)."""


@dataclass
class SeguimientoHC1:
    verificar: Verificador
    """Verificador de firmas de NODO: kid == id_nodo."""
    reloj: Reloj
    _por_id: dict[str, Ejecucion] = field(default_factory=dict)
    rechazos: list[Motivo] = field(default_factory=list)

    # -- emisión --------------------------------------------------------------------------------------------
    def registrar_emision(self, sobre_orden: bytes, techo_total_s: float) -> Ejecucion:
        """Registra una orden recién firmada por NUESTRO firmador. El techo de duración total NO se prorroga."""
        abierto = abrir_sobre(sobre_orden)
        campos = leer_json_estricto(abierto.payload)
        validar_campos_orden(campos)
        if campos["id_ejecucion"] in self._por_id:
            raise RechazoOrden(Motivo.ORDEN_REPETIDA, "id_ejecucion")
        for e in self._por_id.values():
            if e.tarea == campos["tarea"] and (e.estado in _EN_CURSO or e.intento >= campos["intento"]):
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
        self._por_id[ej.id_ejecucion] = ej
        return ej

    def ejecucion(self, id_ejecucion: str) -> Ejecucion | None:
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
        c = self._leer(sobre, DOMINIO_ACUSE, id_nodo_subject)
        ej = self._vincular(c, id_nodo_subject)
        if ej.estado is Estado.ACEPTADA:
            raise self._rechazar(Motivo.ACUSE_DUPLICADO)
        if ej.estado is not Estado.EMITIDA:
            raise self._rechazar(Motivo.EJECUCION_NO_EN_CURSO)
        ej.estado = Estado.ACEPTADA
        ej.recibida_en = c["recibida_en"]  # informativo: el acuse NO prorroga `vence_en`
        return ej

    def recibir_resultado(self, sobre: bytes, id_nodo_subject: str) -> Ejecucion:
        c = self._leer(sobre, DOMINIO_RESULTADO, id_nodo_subject)
        ej = self._vincular(c, id_nodo_subject)
        if ej.estado not in _EN_CURSO:
            motivo = (
                Motivo.RESULTADO_DUPLICADO
                if ej.estado in (Estado.RESULTADO_FIRMADO, Estado.VALIDADO, Estado.INCORPORADO)
                else Motivo.EJECUCION_NO_EN_CURSO
            )
            raise self._rechazar(motivo)
        ej.estado = Estado.RESULTADO_FIRMADO
        ej.sobre_resultado = sobre
        ej.salida = c["salida"]
        return ej

    # -- validación propia e incorporación ----------------------------------------------------------------------
    def validar(self, id_ejecucion: str) -> bool:
        """Corre el verificador PROPIO de la capacidad (nunca se cree el «ok» del nodo)."""
        ej = self._por_id[id_ejecucion]
        if ej.estado is not Estado.RESULTADO_FIRMADO or ej.salida is None:
            raise RechazoOrden(Motivo.EJECUCION_NO_EN_CURSO, "sin resultado firmado que validar")
        cap = CAPACIDADES[ej.capacidad]
        ok = cap.verificar(ej.argumentos, ej.salida)
        ej.estado = Estado.VALIDADO if ok else Estado.VERIFICACION_FALLIDA
        return ok

    def incorporar(self, id_ejecucion: str, registrar: Registrar) -> None:
        """Estado 5: registra el hecho auditable. Si `registrar` falla, la ejecución sigue VALIDADA (se repite)."""
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
        ej.estado = Estado.INCORPORADO

    # -- conectividad ------------------------------------------------------------------------------------------
    def _interrumpir(self, ej: Ejecucion) -> None:
        # Sin acuse: la orden pudo no llegar (reintentable). Con acuse: pudo tener efecto => AMBIGUO.
        ej.estado = Estado.INTERRUMPIDA if ej.estado is Estado.EMITIDA else Estado.AMBIGUO

    def marcar_desconexion(self, id_nodo: str) -> list[Ejecucion]:
        afectadas = [e for e in self._por_id.values() if e.destinatario == id_nodo and e.estado in _EN_CURSO]
        for e in afectadas:
            self._interrumpir(e)
        return afectadas

    def vencer(self) -> list[Ejecucion]:
        """Aplica el techo de duración total: lo que sigue en curso pasado `vence_en` se interrumpe."""
        ahora = self.reloj.ahora()
        vencidas = [e for e in self._por_id.values() if e.estado in _EN_CURSO and ahora > e.vence_en]
        for e in vencidas:
            self._interrumpir(e)
        return vencidas
