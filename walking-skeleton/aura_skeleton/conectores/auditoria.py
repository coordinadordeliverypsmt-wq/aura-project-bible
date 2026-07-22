"""Base comun de los conectores que derivan senales del audit log (M3.0).

M2 ya escribia un registro forense persistente de toda accion con efecto. Esa es la materia prima de
las senales implicitas: **no se instrumenta nada nuevo del sistema de archivos ni del hogar**, solo
se lee lo que ya se registraba. Es la razon por la que "patrones de uso" era la senal mejor
posicionada de las seis del inventario de deuda.

Dos decisiones de diseno:

- **Solo cuentan las acciones EJECUTADAS.** Una accion detenida por Permisos o por dry-run no es un
  patron de uso: es algo que el usuario no llego a hacer. Contarla ensuciaria el modelo del usuario
  con intenciones frustradas, y peor, con las que el propio sistema bloqueo.

- **El cursor es un `seq` PERSISTENTE (MA.3), no el numero de lineas en memoria.** Sobrevive al
  reinicio (antes `self._leidas` volvia a 0 y reprocesaba todo el historial) y a la rotacion por
  archivo del audit log (antes un offset de lineas se invalidaba al sellar un segmento, perdiendo
  eventos). Se lee por `seq` de activo + segmentos, y se avanza al mayor `seq` visto.
"""

from __future__ import annotations

import os

from .. import observability as obs
from ..core.senales import ClaseSenal, Senal


def _ruta_cursor(ruta_audit: str, modulo: str) -> str:
    base = os.path.dirname(ruta_audit) or "."
    return os.path.join(base, "cursores", f"{modulo or 'sin-modulo'}.cursor")


def _cargar_cursor(ruta_audit: str, modulo: str) -> int:
    try:
        with open(_ruta_cursor(ruta_audit, modulo), encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0  # sin cursor previo: se empieza desde el principio del historial con seq


def _guardar_cursor(ruta_audit: str, modulo: str, seq: int) -> None:
    ruta = _ruta_cursor(ruta_audit, modulo)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(seq))
    os.replace(tmp, ruta)  # atomico: un corte no deja un cursor a medias


class ConectorDeAuditoria:
    """Lee el audit log y emite `PATRON_DE_USO` para las acciones de su dominio."""

    nombre = "auditoria"
    _MODULO = ""  # subclase: modulo del audit log que le corresponde

    def __init__(self, ruta_audit: str) -> None:
        self._ruta = ruta_audit
        self._cursor = _cargar_cursor(ruta_audit, self._MODULO)

    def _describir(self, msg: str) -> str:
        return msg.removeprefix("EJECUTA ").strip()

    async def recoger(self, trace_id: str) -> list[Senal]:
        nuevos = obs.leer_audit_desde(self._ruta, self._cursor)
        senales: list[Senal] = []
        maximo = self._cursor
        for rec in nuevos:
            maximo = max(maximo, rec.get("seq", 0))
            if rec.get("module") != self._MODULO:
                continue
            msg = str(rec.get("msg", ""))
            if not msg.startswith("EJECUTA "):
                continue  # detenidas, denegadas y avisos no son patrones de uso
            senales.append(
                Senal(
                    ClaseSenal.PATRON_DE_USO,
                    self._describir(msg),
                    self.nombre,
                    trace_id,
                    ts=rec.get("ts"),
                )
            )
        if maximo > self._cursor:
            self._cursor = maximo
            _guardar_cursor(self._ruta, self._MODULO, maximo)
        return senales
