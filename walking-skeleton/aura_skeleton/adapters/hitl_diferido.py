"""Confirmacion humana DIFERIDA (Pieza 2, ADR-0003 con el acta del CEO de 2026-08-10).

Segunda implementacion del `human_confirm` que espera `PermissionManager`, con la **misma firma**
que la de consola. Lo previo el propio codigo: *«Otras interfaces (voz, movil, web) seran otros
modulos con la misma firma; ninguna deberia vivir en la composicion»* (`hitl_consola.py:7-9`).

CUANDO SE USA. En el servicio desatendido (`--servir`), donde no hay nadie a quien preguntar. La
consola sigue siendo el confirmador por defecto de la sesion interactiva: alli el CEO esta delante y
la respuesta inmediata es mejor que un fichero.

QUE HACE DISTINTO. La de consola pregunta y, sin respuesta, deniega -y la peticion se pierde-. Esta
**escribe la peticion y deniega igual**. La accion no se ejecuta ni un apice antes que antes; lo que
cambia es que la solicitud sobrevive a la ausencia del CEO y el trabajo puede reanudarse despues.

LO QUE NO HACE. No aprueba por omision, no caduca por tiempo, no hay «fail open». Si el CEO no
responde, la respuesta es que no se ejecuta -indefinidamente-. **Ante cualquier duda, NO**, que es
la regla que la de consola tambien hace cumplir.
"""

from __future__ import annotations

from ..core.decisiones import AlmacenDecisiones, huella_de
from ..observability import log


def crear_confirmador_diferido(directorio: str):
    """Devuelve un `human_confirm` que consulta el buzon de decisiones de `directorio`.

    Es una factoria porque la firma que exige `PermissionManager` -`(accion, args, trace_id)`- no
    tiene sitio para la ruta del buzon, y cambiarla obligaria a tocar tambien la de consola.
    """
    almacen = AlmacenDecisiones(directorio)

    async def confirmar_diferido(accion: str, args: dict, trace_id: str) -> bool:
        """True SOLO si el CEO aprobo EXACTAMENTE esta accion, con estos argumentos y este efecto.

        La huella se recalcula aqui, sobre lo que se va a ejecutar de verdad, y se usa para buscar la
        decision. Por eso una aprobacion obsoleta no vale: si los argumentos o el efecto previsto
        cambiaron desde que el CEO dijo que si, la huella es otra, no hay decision para ella, y se
        emite una solicitud NUEVA. El CEO decide otra vez, viendo el efecto nuevo.
        """
        previsualizacion = args.get("_previsualizacion")
        tarea = str(args.get("_tarea", ""))
        huella = huella_de(accion, args, previsualizacion)

        veredicto = almacen.veredicto(huella)
        if veredicto == "aprobada":
            log("HITL", "hitl-diferido", f"{accion}: aprobacion vigente del CEO ({huella[:8]})", trace_id, audit=True)
            return True

        if veredicto is None:
            almacen.solicitar(accion, args, previsualizacion, tarea)
            log(
                "HITL",
                "hitl-diferido",
                f"{accion}: solicitud PENDIENTE anexada al buzon ({huella[:8]})",
                trace_id,
                audit=True,
            )
        else:
            # Pendiente o rechazada: ya esta escrita. No se reescribe -eso borraria la respuesta del
            # CEO- ni se insiste: el silencio y el "no" producen el mismo resultado seguro.
            log("HITL", "hitl-diferido", f"{accion}: decision {veredicto} ({huella[:8]})", trace_id, audit=True)
        return False

    return confirmar_diferido
