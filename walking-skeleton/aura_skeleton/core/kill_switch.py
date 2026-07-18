"""Kill Switch (Bible 5.3 §5): parada de emergencia reversible y auditable, con disparo
fuera de banda (presencia de un archivo). Cuando esta activado, NINGUNA accion se ejecuta."""

from __future__ import annotations

import os

from .. import observability as obs


class KillSwitch:
    def __init__(self, trigger_file: str = "/tmp/aura/KILL"):
        self._file = trigger_file
        self._engaged = False
        os.makedirs(os.path.dirname(trigger_file) or ".", exist_ok=True)

    def engage(self, reason: str = "manual") -> None:
        self._engaged = True
        with open(self._file, "w", encoding="utf-8") as f:
            f.write(reason)
        obs.log("KILL", "kill-switch", f"ACTIVADO ({reason}) — toda accion suspendida", "-", audit=True)

    def disengage(self) -> None:
        self._engaged = False
        if os.path.exists(self._file):
            os.remove(self._file)
        obs.log("KILL", "kill-switch", "desactivado — operacion reanudada", "-", audit=True)

    def is_engaged(self) -> bool:
        # fuera de banda: el archivo tambien activa (p.ej. si AURA misma esta comprometida)
        return self._engaged or os.path.exists(self._file)
