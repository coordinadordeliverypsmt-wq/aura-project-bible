"""Ejecutor interno del ESTADO PROPIO — F3 · `DP-D-M-8 §7`.

*«F3 · Ejecutor interno | Contrato `simular`/`aplicar` para estado propio + catálogo con `sujeto` |
El andamiaje del resto.»*

Es el adaptador que permite que las operaciones sobre la información de la persona atraviesen el
**motor único** igual que cualquier otra acción: dry-run, permisos, kill switch, auditoría. Antes no
existía, y por eso `ModeloUsuario` mutaba el almacén directamente — el agujero de `ALERTA-006`.

**La auditoría se emite aquí y no en el llamador** porque aquí es donde se sabe *qué* se pierde:
`§5.1` exige que del audit pueda responderse *«¿qué había antes y qué hay ahora?»*, y para eso hay
que leer las entradas **antes** de tocarlas.
"""

from __future__ import annotations

import time

from .. import observability as obs
from .modelo_usuario import _TIPOS

#: Operaciones que este ejecutor atiende. Son exactamente las tres que `§4.2` nombra: ni una más.
ACCIONES = (
    "registrar_informacion_usuario",
    "olvidar_informacion_usuario",
    "refutar_informacion_usuario",
)


def _predicado(user_id: str, contiene: str | None, solo_vivas: bool = False):
    """Aislamiento por usuario (P-ARQ-5) y acotado por contenido, igual que la ruta anterior.

    `solo_vivas` conserva un matiz de `refutar` que la migracion estuvo a punto de perder: refutar
    algo YA refutado no tiene efecto, y sin este filtro devolveria `n > 0` la segunda vez. El
    orquestador leeria ese numero como exito y responderia «Entendido, lo corrijo» **sin haber
    corregido nada** — que es exactamente INV-9 y el punto 4 de ALERTA-005.
    """

    def objetivo(i: dict) -> bool:
        return (
            i["user_id"] == user_id
            and i["kind"] in _TIPOS
            and (contiene is None or contiene in i["content"])
            and not (solo_vivas and i.get("provenance", {}).get("refutada"))
        )

    return objetivo


class EjecutorModeloUsuario:
    """Atiende las operaciones sobre información de la persona. Expone `simular` y `execute`."""

    #: Identidad ante el registro de adaptadores (`RegistroAdaptadores.registrar`).
    name = "modelo_usuario"
    capabilities = ACCIONES

    def __init__(self, memoria) -> None:
        self._memoria = memoria

    # El motor resuelve el adaptador por aquí; devolver None para lo ajeno evita que este ejecutor
    # se convierta en un comodín que atienda acciones que no son suyas.
    def para(self, accion: str):
        return self if accion in ACCIONES else None

    def _afectadas(self, args: dict, solo_vivas: bool = False) -> list[dict]:
        pred = _predicado(args.get("user_id", ""), args.get("contiene"), solo_vivas)
        return [i for i in self._memoria._items if pred(i)]

    async def simular(self, accion: str, args: dict, trace_id: str) -> dict:
        """Dry-run: qué pasaría. **No muta.** Un plan no viable detiene la ejecución antes de empezar."""
        if accion == "registrar_informacion_usuario":
            viable = bool(args.get("contenido"))
            return {"viable": viable, "efecto": "registraria una entrada" if viable else "sin contenido"}
        afectadas = self._afectadas(args, solo_vivas=(accion == "refutar_informacion_usuario"))
        verbo = "olvidaria" if accion == "olvidar_informacion_usuario" else "marcaria como refutadas"
        return {"viable": True, "efecto": f"{verbo} {len(afectadas)} entrada(s)"}

    async def execute(self, accion: str, args: dict, trace_id: str, event_id: str) -> dict:
        user_id = args.get("user_id", "")
        if accion == "registrar_informacion_usuario":
            # `tipo` lo aporta la captura de señales (semantica | procedimental, 4.1 §1). Sin el,
            # una señal procedimental se guardaria como semantica y la taxonomia se perderia.
            await self._memoria.write(
                user_id, args.get("tipo", "semantica"), args["contenido"], args.get("procedencia", {})
            )
            obs.log("MODELO", "ejecutor-modelo", f"registrada sobre '{user_id}': {args['contenido']!r}",
                    trace_id, audit=True)
            return {"n": 1}

        # §5.1 — se leen ANTES de tocar nada: despues de mutar, lo perdido ya no se puede nombrar.
        afectadas = [i["content"] for i in self._afectadas(
            args, solo_vivas=(accion == "refutar_informacion_usuario"))]
        if accion == "olvidar_informacion_usuario":
            n = self._memoria.olvidar(_predicado(user_id, args.get("contiene")))
            obs.log("MODELO", "ejecutor-modelo",
                    f"olvidadas {n} entrada(s) sobre '{user_id}': {afectadas!r}", trace_id, audit=True)
            return {"n": n}

        n = self._memoria.marcar(
            _predicado(user_id, args.get("contiene"), solo_vivas=True),
            {"refutada": True, "refutada_ts": time.time()},
        )
        obs.log("MODELO", "ejecutor-modelo",
                f"refutadas {n} entrada(s) sobre '{user_id}': {afectadas!r}", trace_id, audit=True)
        return {"n": n}
