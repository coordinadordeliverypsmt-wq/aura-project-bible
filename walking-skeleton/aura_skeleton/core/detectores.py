"""Contratos de deteccion (Etapa 3, I-A2).

Dos ambitos **separados**, y ningun detector invade el del otro:

- `DetectorHardware` produce **metricas verificadas** (D44): magnitudes medidas con pruebas reales.
- `DetectorEntorno` produce **hechos de dominio**: que capacidades **soporta** el entorno.

Toda la tecnologia concreta (servicios, dependencias, dispositivos, configuracion, credenciales) queda
**encapsulada dentro de cada detector**: su salida se expresa exclusivamente en lenguaje del dominio, de
modo que el Manager permanece agnostico de cualquier tecnologia.

"Soportada" **no** es "activa": es una ENTRADA. La decision de estado (activa/degradada/latente) es
exclusiva del CapabilityManager (I-A1).

Sus implementaciones reales son **latente-prevista**: requieren hardware y entorno para construirse y
validarse (D34/D44). Aqui solo viven los contratos.
"""

from __future__ import annotations

from typing import Protocol

from .capacidades import PerfilHardware


class DetectorHardware(Protocol):
    """Mide la capacidad efectiva del equipo (D44). No opina sobre que capacidades se soportan."""

    def detectar(self) -> PerfilHardware: ...


class DetectorEntorno(Protocol):
    """Reduce su ambito concreto a un hecho del dominio: que capacidades soporta el entorno.

    El nombre del metodo es deliberadamente semantico: el conjunto devuelto **no** es una coleccion
    generica de cadenas, sino los **nombres de capacidades soportadas** (I-AC1).
    """

    def capacidades_soportadas(self) -> frozenset[str]: ...
