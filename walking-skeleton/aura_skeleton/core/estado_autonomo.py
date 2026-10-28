"""Estado del **ciclo autonomo** de AURORA, para poder contarlo en conversacion.

## El defecto que esto corrige

    tu> ¿en qué estás trabajando ahora?
    AURA> No tengo ningun recuerdo registrado sobre eso.

La pregunta era sobre AURA misma y se contesto desde la memoria del usuario. Dos cosas fallaron a la
vez, y conviene no confundirlas:

1. **El reconocimiento.** La superficie existia, pero su lista de frases era literal y cerrada: bastaba
   escribir «trabajado» en vez de «trabajando» para que la frase cayera al final del recorrido, donde
   una memoria vacia produce la ausencia de recuerdos. Una pregunta sobre uno mismo que no se reconoce
   no se queda sin responder: **se responde mal**, porque el ultimo recurso pertenece a otro dominio.

2. **La fuente.** Aun reconociendola, se leia el tablero de objetivos del producto, que no sabe nada
   del ciclo autonomo: ni que hay en cola, ni que esta bloqueado, ni cuando vuelve el `cron`.

## Por que un puerto y no un import

El nucleo conversacional **no puede** depender del plano de desarrollo. `entorno/control-plane` es
donde AURORA se construye a si misma; `aura_skeleton` es el producto, y tiene que poder instalarse sin
el. Asi que aqui solo vive el **contrato** —un dict— y la redaccion. Quien sabe leer el plano es un
adaptador, y si no esta, la conversacion sigue exactamente igual que antes.

Es el mismo patron que ya usa `estado_operativo` en el orquestador: puerto opcional, inyectado por
`composicion`, y ausencia silenciosa.

## Y por que NO se construye un segundo estado

Porque ya existe. `entorno/control-plane/observatorio.py` calcula todo esto leyendo `eventos.jsonl`,
esta probado y es de solo lectura demostrada. Este modulo **no recalcula nada**: recibe esa
instantanea y la pone en castellano.

## La regla al redactar

Ninguna frase se escribe sin un dato que la sostenga. Cuando un valor no consta, la frase que
dependia de el **no se escribe** —o se dice que no consta—, nunca se rellena con un cero ni con una
suposicion razonable. Inventar un progreso es peor que no dar ninguno: el usuario no tiene forma de
distinguir lo inventado de lo medido.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

#: Lo que el observatorio devuelve cuando un dato no consta. Se reconoce, no se reinterpreta.
NO_DISPONIBLE = "NO DISPONIBLE"


@runtime_checkable
class FuenteEstadoAutonomo(Protocol):
    """Quien sabe decir en que anda el ciclo autonomo.

    Un unico metodo, y devuelve un `dict` plano: cuanto menos superficie tenga este contrato, menos
    ata al nucleo a la forma concreta del plano de desarrollo. Un `{}` significa «no hay fuente», y
    es una respuesta legitima -no un error-."""

    def instantanea(self) -> dict:  # pragma: no cover - contrato
        ...


def _numero(valor) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _hay(valor) -> bool:
    return valor is not None and valor != NO_DISPONIBLE and valor != ""


def redactar_actividad(inst: dict) -> str | None:
    """Que esta haciendo AURORA ahora. `None` si no hay fuente: entonces responde quien respondia.

    Distingue los seis casos que el CEO pidio poder separar —ejecutando, terminado y esperando, sin
    trabajo autorizado, bloqueado, elevado a decision humana, esperando el proximo ciclo—, y los
    distingue **por el dato**, no por una heuristica."""
    if not inst:
        return None
    estado = inst.get("estado", NO_DISPONIBLE)

    # (A) Hay un ciclo en curso. Se dice cual y desde cuando; y si el observatorio sospecha que el
    #     proceso murio -porque lleva abierto mas de lo que tarda el `cron` en volver-, se dice
    #     tambien: presentar un ciclo muerto como actividad seria fingir trabajo.
    if estado == "TRABAJANDO":
        frase = "Ahora mismo tengo un ciclo autónomo en curso"
        numero, desde = inst.get("ultimo_ciclo"), inst.get("hora_ultimo_ciclo")
        if _numero(numero) is not None:
            frase += f" (el número {numero})"
        if _hay(desde):
            frase += f", abierto desde las {desde}"
        partes = [frase + "."]
        if _hay(inst.get("sospecha")):
            partes.append(f"Aviso: {inst['sospecha']}.")
        return " ".join(partes)

    if estado == "BLOQUEADA":
        return ("Estoy detenida: la parada de emergencia está armada. No voy a ejecutar ninguna "
                "tarea hasta que se retire.")

    if estado == "ERROR":
        # No se adorna: algo del historial o del último ciclo pide que alguien lo mire.
        detalle = inst.get("integridad_del_log") or {}
        motivo = detalle.get("motivo") if isinstance(detalle, dict) else None
        cola = ". El historial dice: " + str(motivo) if _hay(motivo) and not detalle.get("integro") else ""
        return f"Mi último ciclo terminó de una forma que alguien tiene que revisar{cola}."

    partes: list[str] = []

    # (C) Sin trabajo autorizado. Es la respuesta correcta cuando no lo hay, y decirlo asi importa:
    #     una cola vacia NO es «no puedo hacer nada».
    reparto = inst.get("cola")
    reales = _numero(reparto.get("OPORTUNIDAD_REAL")) if isinstance(reparto, dict) else None
    if reales == 0:
        partes.append("Ahora mismo no tengo ninguna tarea autorizada disponible para ejecutar.")
    elif reales is not None:
        partes.append(f"Tengo {reales} tarea(s) autorizada(s) en cola, todavía sin empezar.")
    else:
        partes.append("No me consta qué tengo en cola ahora mismo.")

    # (D) Bloqueado: hay trabajo real que no puedo tocar porque nadie me ha autorizado esa zona.
    bloqueado = _numero(inst.get("trabajo_bloqueado"))
    if bloqueado:
        partes.append(f"Tengo {bloqueado} oportunidades bloqueadas por falta de autorización.")

    # (E) Elevado: esto SI lo puede desbloquear una persona, y por eso se nombra.
    elevado = _numero(inst.get("trabajo_elevado"))
    if elevado:
        frase = f"Y {elevado} elevadas a decisión humana"
        pendientes = inst.get("decisiones_pendientes")
        identificadores = [d["id"] for d in pendientes
                           if isinstance(d, dict) and _hay(d.get("id"))] if isinstance(pendientes, list) else []
        if identificadores:
            frase += f" ({', '.join(identificadores)})"
        # «necesitan tu aprobacion» era impreciso, y la imprecision se notaba al chocar con la otra
        # superficie: al intentar aprobarlas, AURA contesta que no se resuelven con un permiso porque
        # tienen opciones. Una DECISION es lo que hace falta; aprobar es solo una de sus formas.
        partes.append(frase + ": necesitan una decisión tuya para avanzar.")

    # (B/F) Terminado y esperando. La hora sale del `cron` real o no sale.
    proximo = inst.get("proximo_despertar")
    if _hay(proximo):
        partes.append(f"Estoy esperando mi próximo ciclo autónomo, previsto para las {proximo}.")
    else:
        partes.append("Estoy esperando mi próximo ciclo autónomo.")
    return " ".join(partes)


def redactar_ultima_tarea(inst: dict) -> str | None:
    """La ultima tarea REALMENTE ejecutada, del historial del ciclo -no de la conversacion.

    «Que hiciste» no se contesta con lo que se dijo hace dos turnos: se contesta con lo que consta
    que se hizo, con su identidad y su fichero, para que se pueda comprobar."""
    if not inst:
        return None
    ultima = inst.get("ultima_tarea")
    if not isinstance(ultima, dict):
        return "No me consta ninguna tarea ejecutada en mi historial."
    import os

    trozos = []
    if _hay(ultima.get("id")):
        trozos.append(f"Mi última tarea registrada es {ultima['id']}")
    else:
        trozos.append("Mi última tarea registrada no tiene identificador")
    objeto, fichero = ultima.get("simbolo"), ultima.get("fichero")
    if _hay(objeto) and _hay(fichero):
        trozos.append(f": {objeto} en {os.path.basename(str(fichero))}")
    elif _hay(fichero):
        trozos.append(f", sobre {os.path.basename(str(fichero))}")
    frase = "".join(trozos) + "."
    partes = [frase]
    if _hay(ultima.get("resultado")):
        partes.append(f"Resultado: {ultima['resultado']}.")
    if _hay(ultima.get("autorizada_por")):
        partes.append(f"Autorizada por {ultima['autorizada_por']}.")
    if _hay(ultima.get("momento")):
        partes.append(f"Ocurrió el {ultima['momento']}.")
    return " ".join(partes)


def redactar_decisiones(inst: dict, identificador: str | None = None) -> str | None:
    """Las decisiones elevadas al humano, o UNA en concreto si se pregunta por ella.

    Antes, «¿que son D-ORCH-6 y D-INT-1?» recorria la cascada entera y la contestaba el proveedor con
    su respuesta enlatada, teniendo el sistema el titulo, las opciones y el motivo delante. No es que
    faltara el dato: faltaba la puerta."""
    if not inst:
        return None
    pendientes = inst.get("decisiones_pendientes")
    if not isinstance(pendientes, list):
        return "No me consta ninguna decisión pendiente en mi estado actual."
    if identificador:
        halladas = [d for d in pendientes
                    if isinstance(d, dict) and str(d.get("id", "")).lower() == identificador.lower()]
        if not halladas:
            return f"No encuentro una decisión llamada {identificador} en mi estado actual."
        return _detallar_decision(halladas[0])
    if not pendientes:
        return "Ahora mismo no tengo ninguna decisión esperando una respuesta tuya."
    partes = [f"Tengo {len(pendientes)} decisión(es) esperando una respuesta tuya:"]
    partes += [f"\n{_detallar_decision(d)}" for d in pendientes if isinstance(d, dict)]
    return "\n".join(partes)


def _detallar_decision(decision: dict) -> str:
    """Una decision con lo que hace falta para poder responderla: que es, que cambia cada opcion y
    por que no la resuelvo yo. Todo sale del registro; aqui no se interpreta nada."""
    lineas = [f"· {decision.get('id', NO_DISPONIBLE)} — {decision.get('titulo', NO_DISPONIBLE)}"]
    if _hay(decision.get("por_que_no_la_resuelvo")):
        lineas.append(f"  Por qué no la resuelvo yo: {decision['por_que_no_la_resuelvo']}")
    opciones = decision.get("opciones")
    if isinstance(opciones, list) and opciones:
        lineas.append("  Opciones:")
        lineas += [f"    {o}" for o in opciones]
    if _hay(decision.get("impacto_hoy")):
        lineas.append(f"  Impacto hoy: {decision['impacto_hoy']}")
    return "\n".join(lineas)


def redactar_oportunidades(inst: dict) -> str | None:
    """Que trabajo hay, en que estado y POR QUE esta donde esta.

    «¿Que oportunidades tengo bloqueadas?» caia en la memoria del usuario, que no sabe nada de esto.
    El reparto por clase y el detalle de cada bloqueo estaban registrados; solo faltaba enseñarlos.

    NO se mezcla con el tablero de objetivos del producto: son dos planos, y sumarlos daria un total
    que no existe en ninguno de los dos."""
    if not inst:
        return None
    partes = []
    reparto = inst.get("cola")
    if isinstance(reparto, dict):
        reales = _numero(reparto.get("OPORTUNIDAD_REAL"))
        if reales == 0:
            partes.append("No tengo ninguna oportunidad ejecutable ahora mismo.")
        elif reales is not None:
            partes.append(f"Tengo {reales} oportunidad(es) ejecutables en cola.")
    else:
        partes.append("No me consta el reparto de mi cola ahora mismo.")

    bloqueadas = inst.get("oportunidades_bloqueadas")
    if isinstance(bloqueadas, list) and bloqueadas:
        partes.append(f"\nBloqueadas ({len(bloqueadas)}):")
        for o in bloqueadas:
            if not isinstance(o, dict):
                continue
            partes.append(f"· {o.get('id', NO_DISPONIBLE)} — {o.get('que', NO_DISPONIBLE)}")
            if _hay(o.get("por_que")):
                partes.append(f"    Por qué: {o['por_que']}")
            if _hay(o.get("quien_desbloquea")):
                partes.append(f"    Lo desbloquea: {o['quien_desbloquea']}")
    elif _numero(inst.get("trabajo_bloqueado")):
        # El recuento consta pero el detalle no. Se dice lo que se sabe y se declara lo que falta,
        # en vez de inventar seis motivos.
        partes.append(f"\nTengo {inst['trabajo_bloqueado']} oportunidades bloqueadas, pero no me "
                      f"consta el detalle de cada una en mi estado actual.")

    elevadas = _numero(inst.get("trabajo_elevado"))
    if elevadas:
        partes.append(f"\nY {elevadas} elevadas a decisión humana. Pregúntame por mis decisiones "
                      f"pendientes y te digo cuáles y qué opciones tienen.")
    return "\n".join(partes)


def redactar_evolucion(inst: dict, dia: str | None = None) -> str | None:
    """Que ha hecho AURORA de verdad: trabajos con efecto verificado, del historial.

    «¿Que hiciste?» no se contesta con lo que se dijo hace dos turnos ni con lo que AURORA se
    propone: se contesta con lo que consta que ocurrio, con su fichero y su resultado."""
    if not inst:
        return None
    trabajos = inst.get("trabajos_recientes")
    if not isinstance(trabajos, list):
        return "No me consta mi historial de trabajos en el estado actual."
    if dia:
        trabajos = [x for x in trabajos if str(x.get("momento", "")).startswith(dia)]
        if not trabajos:
            return f"No me consta ningún trabajo con efecto verificado el {dia}."
    if not trabajos:
        return "No me consta ningún trabajo ejecutado en mi historial."
    import os

    lineas = [f"He completado {len(trabajos)} trabajo(s) con efecto verificado. Los más recientes:"]
    for x in reversed(trabajos[-5:]):
        objeto = x.get("simbolo", NO_DISPONIBLE)
        fichero = os.path.basename(str(x.get("fichero", ""))) or NO_DISPONIBLE
        lineas.append(f"· {x.get('momento', NO_DISPONIBLE)} — {objeto} en {fichero} "
                      f"({x.get('resultado', NO_DISPONIBLE)})")
    return "\n".join(lineas)


__all__ = ["FuenteEstadoAutonomo", "redactar_actividad", "redactar_ultima_tarea",
           "redactar_decisiones", "redactar_oportunidades", "redactar_evolucion", "NO_DISPONIBLE"]
