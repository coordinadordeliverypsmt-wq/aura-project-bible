"""Unit: Memoria como primera capacidad real del Capability Registry (C2, ADR-0020/0011, Bible 4.1).

Patron obligatorio (D46): la capacidad se DECLARA completamente (10 campos) y el CapabilityManager decide
su estado SOLO desde el PerfilHardware. Aqui se verifica ese comportamiento observable con Memoria, sin
implementar aun el cableado del motor por nivel (eso es un paso posterior).

Modelo de Memoria (ADR-0020): siempre opera. Perfil alto -> ACTIVA (motor avanzado, N2/N3); perfil modesto
-> DEGRADADA (almacen minimo N1, mismo contrato 4.1). NUNCA latente: N1 corre en presupuesto cero.
"""

import dataclasses

from aura_skeleton.core.capability_manager import CapabilityManager
from aura_skeleton.core.capability_registry import CapabilityRegistry
from aura_skeleton.core.capacidades import (
    ActivationContext,
    Estado,
    GradoLatencia,
    NivelAutonomia,
    PerfilHardware,
)
from aura_skeleton.core.catalogo_capacidades import MEMORIA

ALTO = PerfilHardware(recursos={"ram_mb": 32000})
MODESTO = PerfilHardware(recursos={"ram_mb": 2000})


def _plan(perfil):
    # Memoria decide solo por hardware: el conjunto de capacidades soportadas es irrelevante para ella.
    contexto = ActivationContext(hardware=perfil, capacidades_soportadas=frozenset())
    return CapabilityManager(CapabilityRegistry([MEMORIA])).planificar(contexto)


def test_memoria_declarada_completa():
    # Los diez campos, con los valores que ADR-0020/Bible 4.1 fijan para memoria.
    assert MEMORIA.nombre == "memoria"
    assert MEMORIA.contrato.startswith("memoria-4.1")
    assert MEMORIA.latencia is GradoLatencia.ACTIVABLE  # implementada (MA.2): no es prevista
    assert MEMORIA.promocion is not None and MEMORIA.degradacion is not None
    assert MEMORIA.autonomia_maxima == NivelAutonomia.OBSERVACION  # la memoria no ejecuta acciones
    # Seguridad declarada (ADR-0001): local/cifrado y aislamiento por usuario.
    assert any("ADR-0001" in g or "local" in g.lower() for g in MEMORIA.garantias_seguridad)


def test_memoria_activa_en_perfil_alto():
    plan = _plan(ALTO)
    assert plan.activas == ("memoria",)


def test_memoria_degradada_en_perfil_modesto():
    plan = _plan(MODESTO)
    assert plan.degradadas == ("memoria",)  # N1 minimo, no latente
    assert "degrad" in plan.motivo("memoria").lower()


def test_memoria_nunca_latente():
    # Para cualquier perfil realista, memoria opera (al menos N1); nunca queda latente.
    for ram in (0, 1, 500, 2000, 8000, 64000, 1_000_000):
        d = _plan(PerfilHardware(recursos={"ram_mb": ram})).decision("memoria")
        assert d.estado is not Estado.LATENTE, f"memoria latente con ram_mb={ram}"


def test_memoria_es_serializable():
    # Declaracion pasiva (D45/independencia del catalogo): datos puros, JSON-ready.
    d = dataclasses.asdict(MEMORIA)
    assert d["nombre"] == "memoria"
    assert not any(callable(v) for v in vars(MEMORIA).values())
