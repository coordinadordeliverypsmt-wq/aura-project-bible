"""Base comun de los conectores que derivan senales del audit log (M3.0).

M2 ya escribia un registro forense persistente de toda accion con efecto. Esa es la materia prima de
las senales implicitas: **no se instrumenta nada nuevo del sistema de archivos ni del hogar**, solo
se lee lo que ya se registraba. Es la razon por la que "patrones de uso" era la senal mejor
posicionada de las seis del inventario de deuda.

Dos decisiones de diseno:

- **Solo cuentan las acciones EJECUTADAS.** Una accion detenida por Permisos o por dry-run no es un
  patron de uso: es algo que el usuario no llego a hacer. Contarla ensuciaria el modelo del usuario
  con intenciones frustradas, y peor, con las que el propio sistema bloqueo.

- **Se lleva la marca de la ultima linea leida.** Sin ella, cada recogida reprocesaria el historial
  completo y multiplicaria las senales en cada turno.
"""

from __future__ import annotations

import json

from ..core.senales import ClaseSenal, Senal


class ConectorDeAuditoria:
    """Lee el audit log y emite `PATRON_DE_USO` para las acciones de su dominio."""

    nombre = "auditoria"
    _MODULO = ""  # subclase: modulo del audit log que le corresponde

    def __init__(self, ruta_audit: str) -> None:
        self._ruta = ruta_audit
        self._leidas = 0

    def _describir(self, msg: str) -> str:
        return msg.removeprefix("EJECUTA ").strip()

    async def recoger(self, trace_id: str) -> list[Senal]:
        try:
            with open(self._ruta, encoding="utf-8") as f:
                lineas = f.readlines()
        except FileNotFoundError:
            # El log puede no existir todavia: es un estado normal, no un fallo.
            return []

        nuevas, self._leidas = lineas[self._leidas :], len(lineas)
        senales: list[Senal] = []
        for linea in nuevas:
            try:
                rec = json.loads(linea)
            except ValueError:
                # Un corte durante la escritura solo puede danar la ultima linea (formato JSONL).
                continue
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
        return senales
