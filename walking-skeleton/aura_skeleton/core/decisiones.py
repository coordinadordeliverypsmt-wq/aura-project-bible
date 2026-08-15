"""Buzon de decisiones: aprobacion DIFERIDA de acciones de lista roja (Pieza 2, acta del CEO 2026-08-10).

EL BLOQUEO QUE CIERRA. De los cuatro ejecutores del ciclo de AURORA, tres son de lista verde
-lectura- y el unico que produce trabajo nuevo, `proponer_cambio`, es de lista ROJA. Desatendida,
la confirmacion por consola recibe `EOFError` y deniega: AURORA no podia completar NINGUN trabajo
que alterase nada sin el CEO delante en ese instante.

QUE CAMBIA Y QUE NO. **La autorizacion no se presume ni se sustituye.** Lo que sobrevive a la
ausencia del CEO es la SOLICITUD, no el permiso. Sin aprobacion la accion no se ejecuta, exactamente
igual que antes; la diferencia es que la peticion queda escrita, el ciclo sigue con lo demas, y
cuando el CEO responde el trabajo se reanuda solo.

POR QUE ESTO ES MAS FUERTE QUE CONFIRMAR EN VIVO. Hoy el CEO confirma y se ejecuta lo que el
adaptador haga. Aqui la aprobacion vale para UNA huella -accion + argumentos + efecto previsto-, y
el efecto se recalcula justo antes de ejecutar: si el mundo cambio entre la aprobacion y la
ejecucion, la aprobacion caduca y se vuelve a preguntar. Es una garantia que el HITL sincrono no da.

LO QUE ESTE MODULO NO HACE (reglas 6 y 7 del acta): no hay aprobacion automatica, ni caducidad por
tiempo, ni «fail open». **El silencio no es aprobacion ni rechazo**: la solicitud sigue pendiente
indefinidamente, y eso es una decision, no una carencia.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

_PENDIENTE = "pendiente"
_APROBADA = "aprobada"
_RECHAZADA = "rechazada"

# Claves de uso interno que el motor inyecta en el contexto de permisos. No son argumentos del
# usuario y NO entran en la huella: el identificador de tarea y el trace cambian en cada latido, y
# si contaran, una aprobacion no coincidiria jamas y el mecanismo seria inutil.
_METADATOS = "_"


def argumentos_del_usuario(args: dict) -> dict:
    """Los argumentos reales de la accion, sin los metadatos que el motor anade por el camino."""
    return {k: v for k, v in args.items() if not k.startswith(_METADATOS)}


def huella_de(accion: str, args: dict, previsualizacion: str | None) -> str:
    """SHA-256 de (accion + argumentos + efecto previsto).

    Es el contrato entero de la aprobacion diferida: lo que el CEO aprueba es ESTA huella, y solo
    esta. `sort_keys` la hace independiente del orden de las claves, de modo que dos latidos con los
    mismos datos producen la misma huella aunque el diccionario se construya en otro orden.
    """
    material = json.dumps(
        {"accion": accion, "argumentos": argumentos_del_usuario(args), "previsualizacion": previsualizacion},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AlmacenDecisiones:
    """Un fichero JSON por decision, nombrado por su huella.

    Ficheros sueltos y no una base de datos por una razon concreta: **el CEO aprueba editandolos a
    mano**. El canal tiene que seguir funcionando sin AURA delante, con las herramientas que
    cualquiera tiene. Por eso se escriben con `ensure_ascii=False` e indentados.
    """

    def __init__(self, directorio: str) -> None:
        self._dir = directorio

    # ------------------------------------------------------------- escritura --

    def solicitar(self, accion: str, args: dict, previsualizacion: str | None, tarea: str = "") -> str:
        """Anexa una solicitud PENDIENTE si no existe ya. Devuelve su huella.

        Idempotente por huella: el ciclo reintenta, y si cada latido creara una solicitud nueva el
        buzon del CEO se llenaria de copias de la misma decision y seria inservible.
        """
        huella = huella_de(accion, args, previsualizacion)
        ruta = self._ruta(huella)
        if os.path.exists(ruta):
            return huella
        self._escribir(
            ruta,
            {
                "accion": accion,
                "argumentos": argumentos_del_usuario(args),
                "previsualizacion": previsualizacion,
                "huella": huella,
                "estado": _PENDIENTE,
                "ts": time.time(),
                "tarea": tarea,
            },
        )
        return huella

    def aprobar(self, huella: str) -> bool:
        """Marca una decision como aprobada. En produccion lo hace el CEO editando el fichero; este
        metodo existe para que las pruebas ejerciten el mismo camino y para una futura interfaz."""
        return self._marcar(huella, _APROBADA)

    def rechazar(self, huella: str) -> bool:
        return self._marcar(huella, _RECHAZADA)

    # -------------------------------------------------------------- lectura --

    def veredicto(self, huella: str) -> str | None:
        """El estado de ESTA huella, o None si nunca se pidio.

        La huella se recalcula sobre lo que se va a ejecutar y se usa para LOCALIZAR el fichero; no
        se lee del contenido. Asi, manipular un fichero para que diga "aprobada" describiendo otra
        cosa no autoriza nada: la huella deja de corresponder y no se encuentra.
        """
        decision = self._leer(self._ruta(huella))
        if decision is None:
            return None
        estado = decision.get("estado")
        return str(estado) if estado in (_PENDIENTE, _APROBADA, _RECHAZADA) else None

    def pendientes(self) -> list[dict[str, Any]]:
        return self._todas(_PENDIENTE)

    def aprobadas(self) -> list[dict[str, Any]]:
        return self._todas(_APROBADA)

    # ----------------------------------------------------------------- util --

    def _todas(self, estado: str) -> list[dict[str, Any]]:
        if not os.path.isdir(self._dir):
            return []
        halladas = []
        for nombre in sorted(os.listdir(self._dir)):
            if not nombre.endswith(".json"):
                continue
            decision = self._leer(os.path.join(self._dir, nombre))
            if decision is not None and decision.get("estado") == estado:
                halladas.append(decision)
        return halladas

    def _ruta(self, huella: str) -> str:
        return os.path.join(self._dir, f"{huella}.json")

    def _marcar(self, huella: str, estado: str) -> bool:
        ruta = self._ruta(huella)
        decision = self._leer(ruta)
        if decision is None:
            return False
        decision["estado"] = estado
        decision["ts_respuesta"] = time.time()
        self._escribir(ruta, decision)
        return True

    @staticmethod
    def _leer(ruta: str) -> dict[str, Any] | None:
        """Un fichero corrupto o ilegible NO autoriza: se trata como si no existiera. El CEO edita
        estos ficheros a mano, asi que un JSON mal cerrado es un accidente probable, y el resultado
        seguro de un accidente es que no se ejecute nada."""
        try:
            with open(ruta, encoding="utf-8") as f:
                cargado = json.load(f)
        except (OSError, ValueError):
            return None
        return cargado if isinstance(cargado, dict) else None

    def _escribir(self, ruta: str, decision: dict[str, Any]) -> None:
        """Escritura ATOMICA: el CEO puede estar leyendo el buzon mientras AURORA anexa una
        solicitud, y un fichero a medio escribir se leeria como corrupto."""
        os.makedirs(self._dir, exist_ok=True)
        temporal = f"{ruta}.tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(decision, f, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta)


def _solo_tarea(identificador: Any) -> str:
    """El `tarea_id` dentro de un `event_id` `"<trace>:<tarea_id>"`. Idempotente: si ya viene limpio,
    lo devuelve tal cual."""
    return str(identificador).rsplit(":", 1)[-1]


def reabrir_aprobadas(almacen: AlmacenDecisiones, estado) -> int:
    """Devuelve al trabajo las tareas cuya decision ya aprobo el CEO. Cuantas se reabrieron.

    Este es el paso que convierte «aprobado» en «trabajo reanudado»: sin el, la aprobacion se
    quedaria en el disco y la tarea seguiria bloqueada para siempre.

    NO revalida la huella aqui, y es deliberado: la revalidacion la hace el propio motor al ejecutar,
    porque rehace el dry-run y vuelve a preguntar al confirmador. Comprobarlo tambien aqui obligaria
    a simular la accion fuera del motor unico -una segunda ruta de decision, justo lo que ALERTA-005
    prohibe-. Reabrir solo devuelve la tarea al backlog; el permiso se sigue decidiendo en su sitio.
    """
    reabiertas = 0
    # El motor identifica la unidad de trabajo con el `event_id`, que es `"<trace>:<tarea_id>"`. El
    # trace cambia en cada vuelta, asi que se compara por la parte estable: la tarea. Sin esto, la
    # aprobacion se guardaba con `-:t-cambio` y se buscaba `t-cambio` -- no coincidian NUNCA y el
    # trabajo aprobado no se reanudaba jamas. Lo destapo la demostracion end-to-end, no las pruebas
    # de unidad, que pasaban el identificador ya limpio.
    aprobadas = {_solo_tarea(d.get("tarea")) for d in almacen.aprobadas() if d.get("tarea")}
    if not aprobadas:
        return 0
    for objetivo_id in estado.objetivos_activos():
        for tarea in estado.tareas(objetivo_id):
            if tarea.estado != "bloqueada" or tarea.tarea_id not in aprobadas:
                continue
            estado.transitar(
                objetivo_id,
                tarea.tarea_id,
                "abierta",
                autoridad="ceo",
                causa="decision aprobada por el CEO en el buzon",
            )
            reabiertas += 1
    return reabiertas
