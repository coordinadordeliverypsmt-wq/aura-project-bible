"""Unit: el esquema de `Capacidad` es exactamente el de ADR-0021 v1.1.0.

Anti-regresion del modelo declarativo. ADR-0021 v1.1.0 redujo la declaracion de diez campos a **ocho**,
tras la auditoria de consistencia del Registry:

- **ELIMINADO** el antiguo campo 2 (`prerequisitos`): sin diferenciacion estructural ni semantica frente
  al campo 5 (mismo tipo, mismo contexto, mismo significado operativo).
- **ELIMINADO** el antiguo campo 3 (`deteccion`): sin consumidor posible bajo los invariantes —el Manager
  es puro y sin E/S (INV-1), el Builder no puede leer el Registry (INV-4), los detectores no lo conocen
  (INV-3)—.

Esta prueba impide que reaparezcan por inercia y que se anadan campos sin pasar por el ADR.
"""

import dataclasses

from aura_skeleton.core.capacidades import Capacidad
from aura_skeleton.core.catalogo_capacidades import MEMORIA

# Identidad + los OCHO campos de ADR-0021 v1.1.0, con su numero original (no se renumera).
ESQUEMA_ADR_0021_V11 = {
    "nombre",  # identidad en el registro
    "contrato",  # (1) OPERATIVO   -> composicion
    "comportamiento_degradado",  # (4) DOCUMENTAL
    "promocion",  # (5) OPERATIVO   -> Manager
    "degradacion",  # (6) OPERATIVO   -> Manager (criterio de viabilidad reducida: PISO, no techo)
    "latencia",  # (7) OPERATIVO   -> Manager
    "dependencias",  # (8) OPERATIVO   -> Manager
    "garantias_seguridad",  # (9) DOCUMENTAL
    "autonomia_maxima",  # (10) PROVISIONAL (sin consumidor; no gobierna nada)
}

CAMPOS_ELIMINADOS = {"prerequisitos", "deteccion"}


def _campos() -> set[str]:
    return {f.name for f in dataclasses.fields(Capacidad)}


def test_esquema_coincide_exactamente_con_el_adr():
    assert _campos() == ESQUEMA_ADR_0021_V11


def test_los_campos_eliminados_no_reaparecen():
    intrusos = _campos() & CAMPOS_ELIMINADOS
    assert not intrusos, f"campos eliminados por ADR-0021 v1.1.0 reintroducidos: {sorted(intrusos)}"


def test_la_capacidad_de_referencia_no_declara_campos_eliminados():
    d = dataclasses.asdict(MEMORIA)
    assert not (set(d) & CAMPOS_ELIMINADOS)


def test_la_declaracion_sigue_siendo_pasiva_y_serializable():
    """INV-5: datos puros. La simplificacion no puede introducir comportamiento."""
    d = dataclasses.asdict(MEMORIA)
    assert d["nombre"] == "memoria"
    assert not any(callable(v) for v in vars(MEMORIA).values())
    assert MEMORIA == dataclasses.replace(MEMORIA)  # comparable y reconstruible
