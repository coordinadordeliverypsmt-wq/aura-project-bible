"""Integracion (B1): cadena Detectores -> Builder -> ActivationContext -> Manager -> Plan, sin metricas.

Un fallo del detector de hardware no puede detener AURA: debe producir una **degradacion limpia**. El
sistema opera al nivel que puede (principio de capacidad latente, INV-11), nunca deja de operar.

Complementa a las pruebas unitarias del Builder: alli se verifica que el contexto se construye; aqui, que
la cadena completa llega hasta un `PlanActivacion` utilizable con el catalogo REAL.
"""

from aura_skeleton.core.activation_context_builder import ActivationContextBuilder
from aura_skeleton.core.capability_manager import CapabilityManager
from aura_skeleton.core.capability_registry import CapabilityRegistry
from aura_skeleton.core.capacidades import Estado, PerfilHardware
from aura_skeleton.core.catalogo_capacidades import catalogo


class _HardwareAveriado:
    """Detector de hardware que no consigue medir el equipo (sonda ausente, permiso denegado, timeout)."""

    def detectar(self) -> PerfilHardware:
        raise OSError("no se pudo medir el equipo")


def _plan(detector_hardware):
    contexto = ActivationContextBuilder(detector_hardware, ()).construir()
    return CapabilityManager(CapabilityRegistry(catalogo())).planificar(contexto)


def test_sin_metricas_el_sistema_degrada_pero_opera():
    """Sin metricas no hay promocion posible, pero memoria conserva su PISO (N1): opera en modo reducido."""
    decision = _plan(_HardwareAveriado()).decision("memoria")

    assert decision is not None, "el fallo de deteccion no puede dejar al sistema sin plan"
    assert decision.estado is Estado.DEGRADADA
    assert decision.motivo, "toda decision del plan explica su motivo"


def test_un_equipo_amplio_sigue_promocionando():
    """Contraprueba: el aislamiento no puede degradar a quien SI tiene metricas (anti-regresion)."""

    class _HardwareAmplio:
        def detectar(self) -> PerfilHardware:
            return PerfilHardware(recursos={"ram_mb": 16000.0})

    decision = _plan(_HardwareAmplio()).decision("memoria")
    assert decision is not None and decision.estado is Estado.ACTIVA
