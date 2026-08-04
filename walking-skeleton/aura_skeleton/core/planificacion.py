"""Planificacion: la POLITICA DE ADMISION al backlog. No es un modulo que cree trabajo aparte.

POR QUE NO HAY UN "PLANIFICADOR" COMO COMPONENTE (CEO, 2026-08-03). `EstadoOperativo.registrar` ya era
la unica via de escritura del backlog —`actualizar` delega en ella y en todo el paquete solo el Director
la invoca, y solo para actualizar—. La puerta ya estaba sola: lo que faltaba no era un guardian nuevo,
sino una **politica** sobre esa puerta. Igual que el Motor Unico es la unica ruta de ejecucion, esta es
la unica ruta de creacion. Una segunda ruta convertiria el backlog en algo escribible desde cualquier
sitio, que es la clase de defecto que ALERTA-005 y ALERTA-006 costaron.

QUE EXIGE ADMITIR UNA TAREA. Los cinco requisitos del CEO: causa verificable (evidencia), objetivo
padre, prioridad, responsable y condicion de cierre. Sin ellos no se admite: una tarea sin causa no es
trabajo, es una ocurrencia.

EL CORTE DE CICLOS ES ESTRUCTURAL, NO UN CONTADOR (decision del CEO). Se reutiliza el patron que ya
resolvio D-A-3: alli las acciones disparadas por una regla **no republican eventos**, asi que encadenar
es imposible por construccion y no hace falta detectar bucles. Aqui el equivalente es el campo `origen`:
solo el trabajo de origen HUMANO puede engendrar trabajo derivado; una tarea DERIVADA no puede engendrar
otra. La profundidad maxima es 1 **por construccion**, y eso se demuestra, no se vigila.
"""

from __future__ import annotations

import hashlib

from .estado_operativo import AlmacenEstadoOperativo, Tarea

HUMANO = "humano"  # lo pidio una persona: puede engendrar trabajo derivado
DERIVADO = "derivado"  # nacio de la evidencia de otra tarea: NO puede engendrar mas
ORIGENES = (HUMANO, DERIVADO)


class AdmisionRechazada(Exception):
    """La tarea no cumple los requisitos para entrar al backlog. Se rechaza declarando el motivo."""


def id_desde_evidencia(evidencia: str) -> str:
    """Identificador ESTABLE derivado de la causa.

    Es el mismo mecanismo que `rule_id` en las automatizaciones: si la misma evidencia vuelve a
    aparecer, produce la misma clave, y la proyeccion por `(objetivo_id, tarea_id)` actualiza en vez
    de acumular. La deduplicacion es entonces una propiedad del identificador, no codigo que recordar.
    """
    return "auto-" + hashlib.sha256(evidencia.encode("utf-8")).hexdigest()[:12]


def admitir(
    estado: AlmacenEstadoOperativo,
    *,
    objetivo_id: str,
    descripcion: str,
    responsable: str,
    evidencia: str,
    prioridad: int = 5,
    origen: str = HUMANO,
    causa: Tarea | None = None,
    args: dict | None = None,
) -> Tarea:
    """UNICA puerta de creacion de trabajo. Devuelve la tarea admitida (nueva o ya existente).

    `causa` es la tarea de cuya evidencia nace esta. Es obligatoria para el trabajo derivado: sin
    causa no hay forma de comprobar el corte de ciclos.
    """
    if origen not in ORIGENES:
        raise AdmisionRechazada(f"origen no valido: {origen!r}; esperado uno de {ORIGENES}")
    if not evidencia:
        raise AdmisionRechazada("toda tarea necesita una causa verificable: falta evidencia")
    if not objetivo_id or not responsable or not descripcion:
        raise AdmisionRechazada("toda tarea necesita objetivo padre, responsable y descripcion")

    if origen == DERIVADO:
        # EL CORTE ESTRUCTURAL. No se cuenta profundidad ni se detectan bucles: sencillamente el
        # trabajo derivado no puede derivar mas trabajo. La cadena mide como maximo 1, siempre.
        if causa is None:
            raise AdmisionRechazada("una tarea derivada debe declarar la tarea que la causo")
        if causa.origen != HUMANO:
            raise AdmisionRechazada(
                f"el trabajo derivado no puede engendrar mas trabajo (causa '{causa.tarea_id}' "
                f"ya es de origen '{causa.origen}'): asi no puede existir generacion infinita"
            )

    tarea_id = id_desde_evidencia(evidencia)
    ya = estado.tarea(objetivo_id, tarea_id)
    if ya is not None:
        # Misma evidencia, misma tarea: se reutiliza en vez de duplicar (requisito del CEO).
        return ya

    return estado.registrar(
        Tarea(
            objetivo_id=objetivo_id,
            tarea_id=tarea_id,
            descripcion=descripcion,
            estado="abierta",
            responsable=responsable,
            prioridad=prioridad,
            origen=origen,
            evidencias=[evidencia],
            args=dict(args or {}),
        )
    )


def desde_verificacion(estado: AlmacenEstadoOperativo, causa: Tarea, resultado: dict) -> Tarea | None:
    """Traduce el resultado de una verificacion en trabajo, cuando corresponde. None si no corresponde.

    Simetria que cierra el ciclo: el Director convierte tareas en resultados; esto convierte resultados
    en tareas. El QA no crea trabajo —solo produce evidencia estructurada—; la decision de que ese
    resultado merezca una tarea se toma AQUI, en la unica puerta de admision.
    """
    if resultado.get("ok", True):
        return None  # una verificacion en verde no genera trabajo: no hay nada que corregir
    evidencia = f"{causa.tarea_id}:{resultado.get('capacidad', '?')}:{resultado.get('resumen', '')}"
    return admitir(
        estado,
        objetivo_id=causa.objetivo_id,
        descripcion=f"corregir el fallo detectado por {resultado.get('capacidad', 'la verificacion')}",
        responsable="programador",
        evidencia=evidencia,
        prioridad=1,  # un fallo de verificacion bloquea el avance: se atiende antes que lo demas
        origen=DERIVADO,
        causa=causa,
    )
