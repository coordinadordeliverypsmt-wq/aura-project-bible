"""Ejecutor interno de las AUTOMATIZACIONES del usuario — F4 tramo 2 · `DP-D-M-8 §7`.

`AlmacenReglas.crear` escribia `reglas.jsonl` **sin motor, sin permisos y sin kill switch**: era el
rojo `test_g2_el_kill_switch_armado_no_detiene_la_creacion_de_reglas`. Este adaptador es el punto
por el que esas dos operaciones entran al camino unico, igual que `EjecutorModeloUsuario` lo es para
la soberania.

Atiende la capacidad `automatizacion`, que **ya existia** en el catalogo —*«definir regla (no
ejecutarla)»*—: no se amplia el catalogo ni se toca `D23`. La operacion concreta (`crear` /
`desactivar`) viaja en los argumentos, no en la capacidad, porque ambas son la misma capacidad de
gobierno sobre las automatizaciones del propio usuario.
"""

from __future__ import annotations

from dataclasses import asdict

from .. import observability as obs
from .reglas import ReglaUsuario

#: Unica capacidad que atiende. La declara el catalogo desde M1.
ACCIONES = ("automatizacion",)


class EjecutorReglas:
    name = "reglas"
    capabilities = ACCIONES

    def __init__(self, almacen) -> None:
        self._almacen = almacen

    def para(self, accion: str):
        return self if accion in ACCIONES else None

    async def simular(self, accion: str, args: dict, trace_id: str) -> dict:
        """Dry-run: que pasaria. **No escribe.**"""
        operacion = args.get("operacion")
        if operacion == "crear":
            return {"viable": True, "efecto": f"crearia la automatizacion {args.get('rule_id')!r}"}
        vigente = self._almacen._vigente(args.get("user_id", ""), args.get("rule_id", ""))
        return {"viable": True,
                "efecto": ("desactivaria la automatizacion" if vigente is not None
                           else "no hay automatizacion activa que desactivar")}

    async def execute(self, accion: str, args: dict, trace_id: str, event_id: str) -> dict:
        user_id = args.get("user_id", "")
        if args.get("operacion") == "crear":
            self._almacen._crear_en_disco(ReglaUsuario(**args["regla"]))
            obs.log("REGLA", "ejecutor-reglas",
                    f"creada {args['regla']['rule_id']!r} para '{user_id}'", trace_id, audit=True)
            return {"creada": True}
        desactivada = self._almacen._desactivar_en_disco(user_id, args.get("rule_id", ""))
        obs.log("REGLA", "ejecutor-reglas",
                f"desactivada={desactivada} {args.get('rule_id')!r} para '{user_id}'", trace_id, audit=True)
        return {"desactivada": desactivada}


def como_argumentos(regla: ReglaUsuario) -> dict:
    """Los argumentos con los que una creacion viaja por el motor."""
    return {"operacion": "crear", "user_id": regla.user_id, "rule_id": regla.rule_id,
            "regla": asdict(regla)}
