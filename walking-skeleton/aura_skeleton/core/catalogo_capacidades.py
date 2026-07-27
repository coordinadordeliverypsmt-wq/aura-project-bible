"""Catalogo de capacidades de AURA (C2, D46).

Declaraciones `Capacidad` de los subsistemas reales, en codigo (fuente valida hoy; manana un Loader podria
producirlas desde JSON/YAML/BD sin tocar el Registry ni el Manager — independencia del catalogo, ADR-0021).
Cada capacidad se declara COMPLETA (los diez campos) desde que existe una decision arquitectonica que la
aprueba, aunque su implementacion funcional llegue despues (D46). El estado (activa/degradada/latente) lo
decide el CapabilityManager a partir del PerfilHardware; aqui solo hay datos pasivos.

Los umbrales de las reglas son **parametros calibrables por D44** (capacidad efectiva verificada con
pruebas reales): los valores actuales son un punto de partida razonable, no una medicion; se ajustaran al
disponer del hardware, sin cambiar la arquitectura.
"""

from __future__ import annotations

from .capacidades import (
    Capacidad,
    Condicion,
    Fuente,
    GradoLatencia,
    NivelAutonomia,
    Operador,
    Regla,
)

# --- Umbrales calibrables (D44). Placeholders razonables, no mediciones. ---
_MEM_MOTOR_AVANZADO_RAM_MB = 8000.0  # a partir de aqui, indice embebido / motor especializado (N2/N3)
_MEM_MINIMO_RAM_MB = 0.0  # N1 (almacen minimo) es viable en cualquier equipo: memoria nunca queda latente


def _ram(op: Operador, mb: float) -> Regla:
    return Regla((Condicion(Fuente.RECURSO, "ram_mb", op, mb),))


# Memoria a largo plazo (Bible 4.1). Aprobada por ADR-0011 y refinada por ADR-0020 (perfiles N1/N2/N3).
# ACTIVABLE: su implementacion base ya existe (MA.2, PersistentMemory). Siempre opera:
#   - perfil con recursos -> ACTIVA (motor avanzado, N2/N3);
#   - perfil modesto       -> DEGRADADA (almacen minimo N1, mismo contrato 4.1);
#   - nunca LATENTE.
MEMORIA = Capacidad(
    nombre="memoria",
    contrato="memoria-4.1",  # (1) contrato funcional de la Bible 4.1 (identico en todos los niveles)
    comportamiento_degradado=(  # (4) DOCUMENTAL: que ofrece si no alcanza el motor avanzado
        "almacen minimo N1 (fuerza bruta o indice ligero), mismo contrato 4.1, sin servicios adicionales"
    ),
    promocion=_ram(Operador.GE, _MEM_MOTOR_AVANZADO_RAM_MB),  # (5) motor avanzado si hay recursos
    # (6) viabilidad reducida (PISO): N1 es viable en cualquier equipo -> memoria nunca queda latente
    degradacion=_ram(Operador.GE, _MEM_MINIMO_RAM_MB),
    latencia=GradoLatencia.ACTIVABLE,  # (7) implementada (MA.2), no prevista
    dependencias=(),  # (8) la memoria base no depende de otra capacidad
    garantias_seguridad=(  # (9) dato de sensibilidad maxima
        "local y cifrada (ADR-0001)",
        "aislamiento por user_id",
    ),
    autonomia_maxima=NivelAutonomia.OBSERVACION,  # (10) la memoria almacena/recupera; no ejecuta acciones
)


def catalogo() -> tuple[Capacidad, ...]:
    """Catalogo actual de capacidades declaradas. Se ira ampliando capacidad a capacidad (D46)."""
    return (MEMORIA,)
