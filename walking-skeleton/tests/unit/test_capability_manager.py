"""Unit: CapabilityManager (C1, ADR-0021 / D45 / Bible 3.1 P-ARQ-9).

Comportamiento observable del mecanismo agnostico: recibe SOLO un `PerfilEfectivo` y decide el estado
(activa/degradada/latente) y el motivo de cada capacidad del registro. No inspecciona marcas, modelos ni
OS. Determinista. Validado por mutacion.

Semantica de decision por capacidad (activable):
  promocion(perfil) True            -> ACTIVA (plena)
  elif degradacion(perfil) True     -> DEGRADADA (modo reducido)
  else                              -> LATENTE (perfil insuficiente)
Una capacidad `prevista` (sin implementacion) es SIEMPRE latente (I6). Una activa/degradada cuya
dependencia no esta disponible cae a latente (I4). La autonomia efectiva nunca supera el techo declarado
ni escala con el hardware (I1).
"""

from aura_skeleton.core.capability_manager import CapabilityManager
from aura_skeleton.core.capability_registry import CapabilityRegistry
from aura_skeleton.core.capacidades import (
    Capacidad,
    Condicion,
    Fuente,
    GradoLatencia,
    NivelAutonomia,
    Operador,
    PerfilEfectivo,
    Regla,
)

POBRE = PerfilEfectivo(recursos={"ram_mb": 2000})
MEDIO = PerfilEfectivo(recursos={"ram_mb": 8000})
RICO = PerfilEfectivo(recursos={"ram_mb": 32000})


def _ram_ge(mb: float) -> Regla:
    """Regla DECLARATIVA (datos, no funcion): ram_mb >= mb. El Manager la interpreta."""
    return Regla((Condicion(Fuente.RECURSO, "ram_mb", Operador.GE, mb),))


def _cap(nombre: str, **kw) -> Capacidad:
    kw.setdefault("contrato", f"{nombre}.v1")
    kw.setdefault("latencia", GradoLatencia.ACTIVABLE)
    return Capacidad(nombre=nombre, **kw)


def _plan(caps, perfil):
    return CapabilityManager(CapabilityRegistry(caps)).planificar(perfil)


# --- 2. Promocion / perfil insuficiente ---
def test_promocion_activable_que_cumple():
    plan = _plan([_cap("memoria", promocion=_ram_ge(16000))], RICO)
    assert plan.activas == ("memoria",)
    assert "promoc" in plan.motivo("memoria").lower()


def test_activable_sin_cumplir_queda_latente():
    plan = _plan([_cap("memoria", promocion=_ram_ge(16000))], POBRE)
    assert plan.latentes == ("memoria",)


# --- 3. Degradacion (I2) ---
def test_degradacion_en_perfil_intermedio():
    plan = _plan([_cap("memoria", promocion=_ram_ge(16000), degradacion=_ram_ge(4000))], MEDIO)
    assert plan.degradadas == ("memoria",)
    assert "degrad" in plan.motivo("memoria").lower()


# --- 4. Dependencias (I4) ---
def test_dependencia_no_disponible_cae_a_latente():
    caps = [
        _cap("base", promocion=_ram_ge(100000)),  # no alcanza -> latente
        _cap("dependiente", promocion=_ram_ge(1000), dependencias=("base",)),
    ]
    plan = _plan(caps, RICO)
    assert "base" in plan.latentes
    assert "dependiente" in plan.latentes
    assert "dependenc" in plan.motivo("dependiente").lower()


def test_dependencia_satisfecha_permite_activar():
    caps = [
        _cap("base", promocion=_ram_ge(1000)),
        _cap("dependiente", promocion=_ram_ge(1000), dependencias=("base",)),
    ]
    plan = _plan(caps, RICO)
    assert set(plan.activas) == {"base", "dependiente"}


# --- 5. Seguridad (I1): la autonomia no escala con el hardware ---
def test_autonomia_no_escala_con_hardware():
    caps = [_cap("x", promocion=_ram_ge(1000), autonomia_maxima=NivelAutonomia.RECOMENDACION)]
    d_pobre = _plan(caps, PerfilEfectivo(recursos={"ram_mb": 1500})).decision("x")
    d_rico = _plan(caps, PerfilEfectivo(recursos={"ram_mb": 999999})).decision("x")
    assert d_pobre.autonomia_efectiva == NivelAutonomia.RECOMENDACION
    assert d_rico.autonomia_efectiva == NivelAutonomia.RECOMENDACION  # NO sube por mas hardware


def test_autonomia_efectiva_nunca_supera_el_techo():
    for techo in NivelAutonomia:
        plan = _plan([_cap("x", promocion=_ram_ge(1000), autonomia_maxima=techo)], RICO)
        assert plan.decision("x").autonomia_efectiva <= techo


# --- 6. Latente-prevista no se enciende (I6) ---
def test_prevista_no_se_enciende_aunque_el_perfil_de():
    plan = _plan([_cap("avatar", latencia=GradoLatencia.PREVISTA, promocion=_ram_ge(1))], RICO)
    assert plan.latentes == ("avatar",)
    assert "prevista" in plan.motivo("avatar").lower()
    assert plan.decision("avatar").autonomia_efectiva == NivelAutonomia.OBSERVACION


# --- 7. Determinismo (I3) ---
def test_determinismo_independiente_del_orden():
    a = _cap("a", promocion=_ram_ge(1000))
    b = _cap("b", promocion=_ram_ge(1000))
    c = _cap("c", latencia=GradoLatencia.PREVISTA)
    assert _plan([a, b, c], RICO) == _plan([c, b, a], RICO)


# --- 8. Simetria reversible (I7); el Manager no retiene estado ---
def test_simetria_promociona_degrada_repromociona():
    caps = [_cap("m", promocion=_ram_ge(16000), degradacion=_ram_ge(4000))]
    mgr = CapabilityManager(CapabilityRegistry(caps))
    assert mgr.planificar(RICO).activas == ("m",)
    assert mgr.planificar(MEDIO).degradadas == ("m",)
    assert mgr.planificar(RICO).activas == ("m",)  # re-promociona, sin estado retenido


# --- 9. Agnosticismo (I5): capacidad nueva sin tocar el Manager ---
def test_capacidad_nueva_sin_tocar_el_manager():
    plan = _plan([_cap("cualquiera_futura", promocion=_ram_ge(1000))], RICO)
    assert plan.activas == ("cualquiera_futura",)


# --- Criterio de exito del CEO: motivo por cada decision ---
def test_cada_decision_lleva_motivo():
    caps = [_cap("activa", promocion=_ram_ge(1000)), _cap("prev", latencia=GradoLatencia.PREVISTA)]
    plan = _plan(caps, RICO)
    assert all(d.motivo for d in plan.decisiones)


def test_registro_vacio_produce_plan_vacio():
    plan = CapabilityManager(CapabilityRegistry()).planificar(RICO)
    assert plan.decisiones == ()


# --- Objetivo arquitectonico (CEO): Capacidad es declaracion PASIVA serializable, sin funciones ---
def test_capacidad_es_declaracion_pasiva_serializable():
    import dataclasses

    cap = _cap("memoria", promocion=_ram_ge(16000), autonomia_maxima=NivelAutonomia.RECOMENDACION)
    # Serializable a estructura de datos anidada (base de JSON/YAML), sin objetos de comportamiento.
    d = dataclasses.asdict(cap)
    assert d["nombre"] == "memoria"
    assert d["promocion"]["condiciones"][0]["metrica"] == "ram_mb"
    # Ningun campo es invocable (no hay logica embebida en la declaracion).
    assert not any(callable(v) for v in vars(cap).values())
    # Comparable e inspeccionable: dos declaraciones identicas son iguales y hashables.
    cap2 = _cap("memoria", promocion=_ram_ge(16000), autonomia_maxima=NivelAutonomia.RECOMENDACION)
    assert cap == cap2
    assert hash(cap) == hash(cap2)
