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
from dataclasses import asdict, dataclass, field


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

    def __init__(self, ruta: str) -> None:
        self._ruta = ruta
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        self._reglas: list[ReglaUsuario] = self._cargar()

    def _cargar(self) -> list[ReglaUsuario]:
        if not os.path.exists(self._ruta):
            return []
        reglas: list[ReglaUsuario] = []
        with open(self._ruta, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    reglas.append(ReglaUsuario(**json.loads(linea)))
        return reglas

    def crear(self, regla: ReglaUsuario) -> None:
        self._reglas.append(regla)
        with open(self._ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(regla), ensure_ascii=False) + "\n")

    def listar(self, user_id: str) -> list[ReglaUsuario]:
        """Reglas ACTIVAS del usuario (aislamiento por usuario, P-ARQ-5)."""
        return [r for r in self._reglas if r.user_id == user_id and r.estado == "activa"]

    def aplicables(self, user_id: str, tipo_evento: str) -> list[ReglaUsuario]:
        """Reglas activas del usuario cuyo `evento` coincide con el tipo dado."""
        return [r for r in self.listar(user_id) if tipo_evento.startswith(r.evento)]
