"""ActivationContextBuilder (Etapa 3, I-A3): el agregador que construye el contexto de activacion.

Tres operaciones, y ninguna mas:
  1. **Ejecutar** los detectores (unica E/S del flujo de activacion).
  2. **Normalizar** sus salidas: union de los conjuntos de soporte. Normalizacion **estructural**, nunca
     interpretativa: sin umbrales, sin comparaciones, sin juicios.
  3. **Construir** el `ActivationContext` inmutable.

Lo que este componente **NO** hace (frontera hecha cumplir por AST en `test_frontera_builder.py`):
no aplica reglas, no decide estados, no conoce el Registry ni el Manager, no produce Estado/Decision/
PlanActivacion. Reunir hechos no es decidir: el juicio *"capacidad X soportada"* lo emite cada detector
en su ambito (I-A2); la decision *activa/degradada/latente* es exclusiva del Manager (I-A1).

**No valida I-AC1** (decision del CEO, 2026-07-27). I-AC1 es un invariante arquitectonico del sistema, no
una responsabilidad de este componente: consultar el Registry para filtrar nombres lo convertiria en algo
mas que un ensamblador y rompería I-A3. El Builder **preserva exactamente** lo que producen los
detectores; el incumplimiento de I-AC1 se detecta por pruebas arquitectonicas y revision de codigo.

**Aislamiento de fallos.** Un detector que falla no contribuye, **no interrumpe a los demas** y no aborta
el arranque: el incidente se **registra** (nunca descarte silencioso) y la ausencia de esa informacion la
resuelve despues el Manager por sus reglas —clasificando latente—, no el Builder.
"""

from __future__ import annotations

from collections.abc import Iterable

from .. import observability as obs
from .capacidades import ActivationContext
from .detectores import DetectorEntorno, DetectorHardware


class ActivationContextBuilder:
    def __init__(self, detector_hardware: DetectorHardware, detectores_entorno: Iterable[DetectorEntorno]) -> None:
        self._hardware = detector_hardware
        self._entorno = tuple(detectores_entorno)

    def construir(self) -> ActivationContext:
        """Ejecuta los detectores, normaliza sus salidas y construye el contexto. Determinista."""
        soportadas: set[str] = set()
        for detector in self._entorno:
            try:
                soportadas |= set(detector.capacidades_soportadas())
            except Exception as e:  # el fallo se aisla en su detector: los demas siguen ejecutandose
                obs.log("WARN", "capability-builder", f"detector de entorno sin respuesta: {e}", "-")
        return ActivationContext(
            hardware=self._hardware.detectar(),
            capacidades_soportadas=frozenset(soportadas),
        )
