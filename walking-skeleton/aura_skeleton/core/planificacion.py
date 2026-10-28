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
solo el trabajo originado por una decision (CEO o asistencia externa) puede engendrar trabajo derivado;
una tarea DERIVADA no puede engendrar
otra. La profundidad maxima es 1 **por construccion**, y eso se demuestra, no se vigila.
"""

from __future__ import annotations

import hashlib

from .estado_operativo import CLAVE_CONTEXTO, AlmacenEstadoOperativo, Tarea, solo_ejecutable_completo

# ORIGENES clasifica el ORIGEN DE UNA DECISION, nunca a una persona ni a una herramienta concreta
# (CEO, 2026-08-04). Con el tiempo habra mas herramientas externas, y la metrica no puede depender del
# nombre de ningun modelo: lo que se registra es DE DONDE VINO la decision de que ese trabajo exista.
#
#   CEO ................. decision estrategica humana. Es el proposito del sistema, no algo a reducir.
#   ASISTENCIA_EXTERNA .. propuesta o cambio formulado por un modelo externo, sea cual sea.
#   DERIVADO ............ lo creo una politica interna de AURORA a partir de evidencia propia.
#
# Por que desaparecio "humano": englobaba al CEO y a la asistencia externa en la misma etiqueta, y por
# tanto BORRABA la unica distincion que la metrica de dependencia externa necesita medir. Un valor que
# destruye la informacion que se quiere observar no es un valor por defecto comodo: es un punto ciego.
CEO = "ceo"
ASISTENCIA_EXTERNA = "asistencia_externa"
DERIVADO = "derivado"
ORIGENES = (CEO, ASISTENCIA_EXTERNA, DERIVADO)

# Origenes que PUEDEN engendrar trabajo derivado. El corte estructural de ciclos (D-A-3) sigue vigente:
# lo derivado no deriva mas, asi que la profundidad maxima es 1 por construccion.
_PUEDEN_DERIVAR = (CEO, ASISTENCIA_EXTERNA)


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
    origen: str = CEO,
    causa: Tarea | None = None,
    args: dict | None = None,
) -> Tarea:
    """UNICA puerta de creacion de trabajo. Devuelve la tarea admitida (nueva o ya existente).

    `causa` es la tarea de cuya evidencia nace esta. Es obligatoria para el trabajo derivado: sin
    causa no hay forma de comprobar el corte de ciclos.
    """
    if origen not in ORIGENES:
        # No hay origen implicito, desconocido ni vacio: toda tarea pertenece EXACTAMENTE a uno. Un
        # origen generico devolveria el punto ciego que este desdoble vino a eliminar.
        raise AdmisionRechazada(f"origen no valido: {origen!r}; esperado exactamente uno de {ORIGENES}")
    if not evidencia:
        raise AdmisionRechazada("toda tarea necesita una causa verificable: falta evidencia")
    if not objetivo_id or not responsable or not descripcion:
        raise AdmisionRechazada("toda tarea necesita objetivo padre, responsable y descripcion")

    if origen == DERIVADO:
        # EL CORTE ESTRUCTURAL. No se cuenta profundidad ni se detectan bucles: sencillamente el
        # trabajo derivado no puede derivar mas trabajo. La cadena mide como maximo 1, siempre.
        if causa is None:
            raise AdmisionRechazada("una tarea derivada debe declarar la tarea que la causo")
        if causa.origen not in _PUEDEN_DERIVAR:
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


def oyente_de_transiciones(estado: AlmacenEstadoOperativo):
    """Oyente que convierte transiciones a `bloqueada` en trabajo de correccion.

    CIERRA EL BUCLE DE REALIMENTACION sin acoplar componentes: el Director informa el resultado de una
    transicion (llamando a `transitar`), el PROTOCOLO notifica que ocurrio, y este oyente decide si
    procede admitir trabajo. El Director no conoce la planificacion ni la planificacion al Director.

    Solo reacciona a `bloqueada`: una tarea terminada no necesita correccion, y reaccionar a todo
    convertiria cada avance en trabajo nuevo.
    """

    def reaccionar(anterior: Tarea, actual: Tarea) -> None:
        if actual.estado != "bloqueada" or actual.origen not in _PUEDEN_DERIVAR:
            # El corte estructural sigue vigente: el trabajo derivado no engendra mas trabajo.
            return
        motivo = actual.bloqueos[-1] if actual.bloqueos else "bloqueo sin motivo declarado"
        # EL CONTEXTO VIAJA (acta del CEO, 2026-08-15). Hasta aqui la tarea derivada nacia con
        # `args={}` y moria en el dry-run con "un cambio necesita fichero y patron a sustituir",
        # aunque AURORA supiera perfectamente cual era el fichero: lo habia descartado el auditor y
        # lo que quedaba era prosa. Ahora el director adjunta el veredicto en `args` y aqui se
        # traslada a la tarea derivada, con las MISMAS claves que el ejecutor lee.
        #
        # La evidencia NO cambia: sigue siendo `{tarea}:bloqueada:{motivo}`. Es deliberado -de ella
        # sale el identificador, y si el contexto entrase ahi cada matiz del veredicto crearia una
        # tarea nueva en vez de reutilizar la misma-.
        # Se FILTRA en el punto de paso, no se confia en quien lo adjunto: `solo_ejecutable_completo`
        # impide que un contexto con claves de ejecucion incompletas se convierta en argumentos que un
        # ejecutor leera. La proteccion pertenece al sistema, no a un llamador concreto.
        contexto = solo_ejecutable_completo(actual.args.get(CLAVE_CONTEXTO) or {})
        try:
            admitir(
                estado,
                objetivo_id=actual.objetivo_id,
                descripcion=f"desbloquear: {motivo}",
                responsable="programador",
                evidencia=f"{actual.tarea_id}:bloqueada:{motivo}",
                prioridad=1,
                origen=DERIVADO,
                causa=actual,
                args=dict(contexto) or {"motivo": motivo},
            )
        except AdmisionRechazada:
            # Que la admision rechace es una decision legitima, no un fallo del ciclo.
            return

    return reaccionar
