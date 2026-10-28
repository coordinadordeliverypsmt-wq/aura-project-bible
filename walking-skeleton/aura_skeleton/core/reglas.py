"""Reglas de automatización definidas por el usuario (MVP capacidad 5, Bible 6.4).

Una automatización es una regla **`evento → condición → acción`** sobre eventos del bus (6.4:38). Modelo
DEFINITIVO fijado por el CEO (2026-07-28), preparado para crecer sin rediseñarse cuando aparezcan
disparadores externos, reglas sugeridas, prioridades o cadenas:

  - `rule_id`    identificador estable de la regla;
  - `evento`     tipo de evento del bus que la dispara (hoy solo internos: `action.command`);
  - `condicion`  DECLARATIVA — `{campo, op, valor}`, sin lógica arbitraria (serializable, auditable);
  - `accion` + `args`  acción a ejecutar; los `args` son REFERENCIAS al evento (`$evento.ruta`), no valores fijos;
  - `estado`     "activa" / "inactiva";
  - `metadatos`  descripción legible, creada, etc.

La regla es **dato del usuario** y PERSISTE (sobrevive al reinicio). El almacén es JSONL append-only, como
el resto de datos del usuario.

**Fuera del MVP (evolución):** editar reglas, prioridades, resolución de conflictos, prevención de ciclos
en cadenas, disparadores externos y sugerencia automática por aprendizaje.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace


@dataclass
class ReglaUsuario:
    """Automatización definida por el usuario. Datos puros y serializables (sin lógica embebida)."""

    rule_id: str
    user_id: str
    evento: str
    condicion: dict  # {"campo": str, "op": str, "valor": Any}
    accion: str
    args: dict  # {"ruta": "$evento.ruta", ...} — referencias al evento o valores fijos
    estado: str = "activa"
    metadatos: dict = field(default_factory=dict)


# --- Condición declarativa (sin lógica arbitraria) ---------------------------------------------------
_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b if b is not None else False,
}


def evaluar_condicion(condicion: dict, evento: dict) -> bool:
    """Evalúa una condición declarativa contra el evento. Sin código del usuario: solo campo/op/valor.

    Una condición vacía (sin `op`) se cumple siempre: "dispara ante el evento, sin filtro adicional".
    """
    if not condicion:
        return True
    op = _OPS.get(condicion.get("op", "=="))
    if op is None:
        return False
    return bool(op(evento.get(condicion["campo"]), condicion.get("valor")))


# --- Resolución de referencias al evento ($evento.x) -------------------------------------------------
def resolver_args(args: dict, evento: dict) -> dict:
    """Sustituye las referencias `$evento.<clave>` por el valor del evento; deja intactos los valores fijos.

    `$evento.ruta` busca primero en el nivel superior del evento y luego en `evento["args"]`, de modo que
    la acción de la regla opere sobre el dato real del evento que la disparó (no sobre un valor congelado).
    """
    fuente = {**evento.get("args", {}), **{k: v for k, v in evento.items() if k != "args"}}
    resueltos: dict = {}
    for clave, valor in args.items():
        if isinstance(valor, str) and valor.startswith("$evento."):
            resueltos[clave] = fuente.get(valor[len("$evento.") :])
        else:
            resueltos[clave] = valor
    return resueltos


# --- Almacén persistente (dato del usuario) ----------------------------------------------------------
class AlmacenReglas:
    """Persiste las reglas del usuario en JSONL append-only. Sobrevive al reinicio."""

    def __init__(self, ruta: str, motor=None) -> None:
        self._ruta = ruta
        # F4 tramo 2 · el motor unico. Sin el, `crear` y `desactivar` NO mutan (fail-closed): una
        # ruta directa de reserva seria la segunda via que ALERTA-005 prohibe.
        self._motor = motor
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        self._reglas: list[ReglaUsuario] = self._cargar()

    def _cargar(self) -> list[ReglaUsuario]:
        """Proyecta el log append-only: por cada clave (user_id, rule_id) gana la ULTIMA linea.

        El fichero conserva TODAS las lineas (nunca se compacta), pero para decidir el estado
        vigente solo importa la escritura mas reciente de esa clave. La clave incluye user_id ademas
        de rule_id porque dos usuarios pueden reutilizar el mismo rule_id: si se proyectase solo por
        rule_id, la desactivacion de un usuario podria pisar la regla de otro (rompe P-ARQ-5).
        """
        if not os.path.exists(self._ruta):
            return []
        proyeccion: dict[tuple[str, str], ReglaUsuario] = {}
        with open(self._ruta, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    regla = ReglaUsuario(**json.loads(linea))
                    proyeccion[(regla.user_id, regla.rule_id)] = regla
        return list(proyeccion.values())

    def _proyectar(self, regla: ReglaUsuario) -> None:
        """Actualiza self._reglas para la clave (user_id, rule_id): reemplaza, nunca acumula.

        Hallazgo de auditoria independiente (2026-08-02): crear() hacia un append() simple sin
        proyectar, mientras que desactivar() si actualizaba la proyeccion en memoria. Tras
        crear -> desactivar -> crear la MISMA regla en la MISMA sesion, self._reglas quedaba con
        DOS entradas para la misma clave (primero la inactiva, luego la activa). desactivar()
        busca con next(...), que devuelve la PRIMERA coincidencia: encontraba siempre la vieja
        inactiva y devolvia False para siempre (hasta reiniciar el proceso), y la automatizacion
        seguia disparando sin que el usuario pudiera apagarla. La proyeccion por (user_id, rule_id)
        debe ser la UNICA responsable del estado vigente (restriccion explicita): por eso crear y
        desactivar comparten esta misma semantica de reemplazo.
        """
        self._reglas = [r for r in self._reglas if not (r.user_id == regla.user_id and r.rule_id == regla.rule_id)]
        self._reglas.append(regla)

    async def crear(self, regla: ReglaUsuario) -> None:
        """MIGRADA en F4: catalogo -> authorize -> kill switch -> motor -> ejecutor -> persistencia."""
        from .ejecutor_reglas import como_argumentos

        if self._motor is None:
            return
        await self._motor.ejecutar(
            "automatizacion", como_argumentos(regla), regla.user_id or "-",
            f"regla-crear-{regla.rule_id}", origen="reglas",
        )

    def _crear_en_disco(self, regla: ReglaUsuario) -> None:
        """La escritura real. **Solo la invoca el ejecutor**, ya pasados todos los controles."""
        self._proyectar(regla)
        with open(self._ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(regla), ensure_ascii=False) + "\n")

    def _vigente(self, user_id: str, rule_id: str):
        return next((r for r in self._reglas if r.user_id == user_id and r.rule_id == rule_id), None)

    def listar(self, user_id: str) -> list[ReglaUsuario]:
        """Reglas ACTIVAS del usuario (aislamiento por usuario, P-ARQ-5)."""
        return [r for r in self._reglas if r.user_id == user_id and r.estado == "activa"]

    def aplicables(self, user_id: str, tipo_evento: str) -> list[ReglaUsuario]:
        """Reglas activas del usuario cuyo `evento` coincide con el tipo dado."""
        return [r for r in self.listar(user_id) if tipo_evento.startswith(r.evento)]

    async def desactivar(self, user_id: str, rule_id: str) -> bool:
        """MIGRADA en F4, mismo camino que `crear`."""
        if self._motor is None:
            return False
        r = await self._motor.ejecutar(
            "automatizacion", {"operacion": "desactivar", "user_id": user_id, "rule_id": rule_id},
            user_id or "-", f"regla-desactivar-{rule_id}", origen="reglas",
        )
        if r.get("estado") != "ejecutada":
            return False
        return bool((r.get("resultado") or {}).get("desactivada", False))

    def _desactivar_en_disco(self, user_id: str, rule_id: str) -> bool:
        """Desactiva una regla del usuario. True si estaba activa y se desactivo; False si no existia
        o ya estaba inactiva.
        """
        # se busca la version vigente en memoria (ya proyectada por (user_id, rule_id) desde _cargar,
        # o actualizada en memoria por una desactivacion previa en esta misma sesion)
        vigente = next((r for r in self._reglas if r.user_id == user_id and r.rule_id == rule_id), None)
        if vigente is None or vigente.estado != "activa":
            # nada que hacer: no se escribe en el fichero para no dejar ruido de operaciones sin efecto
            return False

        inactiva = replace(vigente, estado="inactiva")

        # PROHIBIDO reescribir o truncar: se aniade una linea nueva; el historial completo queda
        # intacto en disco (evidencia de aceptacion del CEO: el fichero no se toca byte a byte)
        with open(self._ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(inactiva), ensure_ascii=False) + "\n")

        # misma semantica de proyeccion que crear(): reemplaza la entrada de esta clave, nunca
        # acumula, para que listar/aplicables lo reflejen de inmediato sin reiniciar el proceso
        self._proyectar(inactiva)
        return True
