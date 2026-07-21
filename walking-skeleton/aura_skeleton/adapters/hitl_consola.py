"""Confirmacion humana por consola (ADR-0003, Bible 5.3).

Extraido de `composicion.py` en cumplimiento de D40 criterio 3: la composicion **ensambla
componentes, no contiene logica de negocio**. Decidir como se solicita una confirmacion humana —y
que respuesta cuenta como autorizacion— es politica funcional, no ensamblaje.

Es la implementacion por defecto del `human_confirm` que espera `PermissionManager`. Otras
interfaces (voz, movil, web) seran otros modulos con la misma firma; ninguna deberia vivir en la
composicion.

**Regla que hace cumplir: ante cualquier duda, NO.** Tolerancia cero a falsos negativos (2.5 §5.4):
un falso positivo cuesta una confirmacion al usuario, un falso negativo puede destruir datos
irrecuperables.
"""

from __future__ import annotations

_AUTORIZACION = "SI"


async def confirmar_por_consola(accion: str, args: dict, trace_id: str) -> bool:
    """Pide confirmacion mostrando la previsualizacion del dry-run.

    La previsualizacion viaja en `args["_previsualizacion"]` (orden canonico de 5.3 §3.1).
    Confirmar sin verla no seria consentimiento informado, de modo que su ausencia se advierte.
    """
    previa = args.get("_previsualizacion")
    print(f"\n  AURA solicita confirmar una accion de lista roja: {accion}")
    if previa:
        print(f"  Efecto previsto: {previa}")
    else:
        print("  ADVERTENCIA: sin previsualizacion disponible; confirmarias a ciegas.")
    try:
        respuesta = input(f"  ¿Autorizas? [escribe {_AUTORIZACION} para confirmar]: ").strip()
    except (EOFError, KeyboardInterrupt):
        # Servicio desatendido: nadie puede confirmar por omision.
        print("  (sin respuesta) -> denegada")
        return False
    return respuesta == _AUTORIZACION
