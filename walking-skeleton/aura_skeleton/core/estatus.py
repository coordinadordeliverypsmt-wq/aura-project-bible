"""Estatus epistemico de una respuesta — frontera cognitiva (D-FC-1..8, CEO 2026-09-13).

**La regla que este modulo existe para hacer cumplir:** el estatus de lo que AURA dice lo asigna el
Core segun la RUTA que produjo la respuesta. Nunca el modelo, nunca el texto generado, nunca una
confianza que el modelo declare sobre si mismo (ADR-0014 §4: una garantia no puede depender de que un
modelo se comporte como se espera).

Por eso `asignar` es el UNICO sitio que decide, y su invariante es verificable con un espia: si la
respuesta la produjo un proveedor que no es el Core, el estatus es PROPUESTA — sin excepcion, pida lo
que pida quien llame. Una salida probabilistica no puede llegar a HECHO por ningun camino.

Cinco estatus y ninguno mas:

    HECHO       el Core lo sabe: hecho declarado vigente, calculo formal, estado real de AURA
    AUSENCIA    el Core sabe que NO tiene el dato (ADR-0014)
    ACLARACION  el problema esta infradeterminado: el Core pregunta en vez de adivinar
    ABSTENCION  el Core decide no transmitir una respuesta del modelo (dominio sensible, D-FC-2)
                o no puede obtenerla (proveedor no disponible)
    PROPUESTA   texto del modelo: sin autoridad, sin memoria, sin accion
"""

from __future__ import annotations

from enum import StrEnum

#: Nombre del proveedor que designa al nucleo. Es el mismo literal que el orquestador ya usa.
CORE = "core"


class Estatus(StrEnum):
    HECHO = "hecho"
    AUSENCIA = "ausencia"
    ACLARACION = "aclaracion"
    ABSTENCION = "abstencion"
    PROPUESTA = "propuesta"


#: Marca que el CORE antepone a una propuesta del modelo. La escribe el Core, no el modelo: si la
#: redactara el modelo, un modelo que la omitiera convertiria su texto en afirmacion de AURA.
MARCA_PROPUESTA = "Esto lo genera mi modelo local y no está verificado:"

#: Etiqueta con la que cada respuesta anterior reentra en el prompt como conversacion reciente
#: (D-FC-8 = B). Una propuesta NUNCA reentra desnuda: siempre lleva su etiqueta.
ETIQUETA_CONTEXTO = {
    Estatus.HECHO: "HECHO",
    Estatus.AUSENCIA: "AUSENCIA",
    Estatus.ACLARACION: "ACLARACION",
    Estatus.ABSTENCION: "ABSTENCION",
    Estatus.PROPUESTA: "PROPUESTA_NO_VERIFICADA",
}


def asignar(proveedor: str, solicitado: Estatus | None = None) -> Estatus:
    """El unico punto que decide el estatus de un turno.

    * Respondio un proveedor que no es el Core -> PROPUESTA, ignorando `solicitado`.
    * Respondio el Core -> el estatus que la ruta declara; si no declara ninguno, HECHO.
    * El Core no fabrica propuestas: pedir PROPUESTA con `proveedor == CORE` es un error de cableado.
    """
    if proveedor != CORE:
        return Estatus.PROPUESTA
    if solicitado is Estatus.PROPUESTA:
        raise ValueError("el Core no emite PROPUESTAS: una propuesta solo puede venir del modelo")
    return solicitado if solicitado is not None else Estatus.HECHO


def presentar(say: str, estatus: Estatus) -> str:
    """Lo que ve el usuario. Solo la PROPUESTA cambia de forma: lleva delante la marca del Core."""
    if estatus is Estatus.PROPUESTA and say:
        return f"{MARCA_PROPUESTA} {say}"
    return say


def linea_de_contexto(usuario: str, aura: str, estatus: Estatus) -> str:
    """Como reentra un turno previo en el prompt: SIEMPRE con su estatus explicito."""
    return f"(previo) tu: {usuario} | AURA [{ETIQUETA_CONTEXTO[estatus]}]: {aura}"
