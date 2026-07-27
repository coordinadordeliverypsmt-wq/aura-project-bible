"""Unit: ActivationContextBuilder (Etapa 3) — el agregador que construye el ActivationContext.

Responsabilidad UNICA (I-A3): ejecutar detectores, normalizar sus salidas y construir el contexto.
NO aplica reglas, NO decide estados, NO conoce tecnologia (eso vive en cada detector, I-A2).

Propiedades exigidas por el CEO (2026-07-27):
  P1 determinista · P2 conmutativo · P3 idempotente · P4 sin dependencias del Registry/Manager/Estado/
  Decision/Plan (ver test_frontera_builder.py, por AST) · P5 incapaz de emitir decisiones.

Decision del CEO: el Builder **NO valida I-AC1**. I-AC1 es un invariante arquitectonico del sistema,
no una responsabilidad del Builder: consultar el Registry lo convertiria en algo mas que un ensamblador,
acoplaria el agregador al catalogo y rompería I-A3. El Builder **preserva exactamente** lo que producen
los detectores; el incumplimiento de I-AC1 se detecta por pruebas arquitectonicas y revision de codigo,
nunca durante la construccion del contexto.
"""

from aura_skeleton.core.activation_context_builder import ActivationContextBuilder
from aura_skeleton.core.capacidades import ActivationContext, PerfilHardware

PERFIL = PerfilHardware(recursos={"ram_mb": 8000}, pruebas={"embed_ms": 40.0})


class _HardwareDoble:
    """Doble del DetectorHardware: produce SOLO metricas verificadas (I-A2)."""

    def __init__(self, perfil: PerfilHardware = PERFIL) -> None:
        self._perfil = perfil

    def detectar(self) -> PerfilHardware:
        return self._perfil


class _EntornoDoble:
    """Doble de un DetectorEntorno: produce SOLO hechos de dominio (capacidades soportadas)."""

    def __init__(self, *capacidades: str, falla: bool = False) -> None:
        self._caps = frozenset(capacidades)
        self._falla = falla
        self.invocado = False  # permite comprobar que el Builder lo ejecuto

    def capacidades_soportadas(self) -> frozenset[str]:
        self.invocado = True
        if self._falla:
            raise RuntimeError("sonda no disponible")
        return self._caps


def _builder(*entorno, hardware=None):
    return ActivationContextBuilder(hardware or _HardwareDoble(), list(entorno))


# --- Construccion basica ---
def test_construye_contexto_con_metricas_y_soportes():
    ctx = _builder(_EntornoDoble("voz"), _EntornoDoble("hogar")).construir()
    assert isinstance(ctx, ActivationContext)
    assert ctx.hardware == PERFIL
    assert ctx.capacidades_soportadas == frozenset({"voz", "hogar"})


def test_sin_detectores_de_entorno_el_conjunto_es_vacio():
    ctx = _builder().construir()
    assert ctx.capacidades_soportadas == frozenset()
    assert ctx.hardware == PERFIL


# --- P1: determinista ---
def test_determinista():
    b = _builder(_EntornoDoble("voz"), _EntornoDoble("hogar"))
    assert b.construir() == b.construir() == b.construir()


# --- P2: conmutativo (el orden de los detectores no altera el contexto) ---
def test_conmutativo():
    a, b, c = _EntornoDoble("voz"), _EntornoDoble("hogar"), _EntornoDoble("inferencia")
    assert _builder(a, b, c).construir() == _builder(c, a, b).construir() == _builder(b, c, a).construir()


# --- P3: idempotente (ejecutar dos veces el mismo detector no cambia el resultado) ---
def test_idempotente():
    d = _EntornoDoble("voz")
    assert _builder(d).construir() == _builder(d, d).construir()


def test_idempotente_con_solapamiento_parcial():
    # Dos detectores que declaran la misma capacidad no la duplican ni alteran el conjunto.
    assert (
        _builder(_EntornoDoble("voz", "hogar"), _EntornoDoble("hogar")).construir()
        == _builder(_EntornoDoble("voz", "hogar")).construir()
    )


# --- Degradacion limpia: un detector que falla no contribuye y no rompe el arranque ---
def test_detector_que_falla_no_contribuye_ni_rompe():
    ctx = _builder(_EntornoDoble("voz"), _EntornoDoble("hogar", falla=True)).construir()
    assert ctx.capacidades_soportadas == frozenset({"voz"})  # 'hogar' ausente, sin excepcion


def test_el_fallo_de_un_detector_queda_AISLADO_en_ese_detector():
    """El fallo NO se propaga: los demas siguen ejecutandose y el contexto se construye completo.

    Propiedad exigida por el CEO: (a) los detectores restantes se ejecutan —incluidos los POSTERIORES al
    que fallo—, (b) el contexto conserva toda la informacion restante, (c) el Builder se limita a
    REGISTRAR el incidente (no decide, no aborta, no reintenta).
    """
    from aura_skeleton import observability as obs

    antes, falla, despues = (
        _EntornoDoble("voz"),
        _EntornoDoble("hogar", falla=True),
        _EntornoDoble("inferencia"),
    )
    registros_previos = len(obs._records)

    ctx = _builder(antes, falla, despues).construir()

    # (a) todos fueron ejecutados, incluido el posterior al fallo
    assert antes.invocado and falla.invocado and despues.invocado, "el fallo interrumpio la deteccion"
    # (b) el contexto conserva TODA la informacion restante
    assert ctx.capacidades_soportadas == frozenset({"voz", "inferencia"})
    assert ctx.hardware == PERFIL
    # (c) el incidente queda registrado (sin descarte silencioso)
    nuevos = obs._records[registros_previos:]
    assert any("detector" in str(r.get("msg", "")).lower() for r in nuevos), (
        "el Builder debe registrar el incidente del detector que fallo"
    )


# --- P5: incapaz de emitir decisiones (responsabilidad, no numero de metodos) ---
def test_la_responsabilidad_observable_es_producir_un_contexto():
    ctx = _builder(_EntornoDoble("voz")).construir()
    assert type(ctx) is ActivationContext


def test_ningun_metodo_publico_devuelve_tipos_de_decision():
    """El Builder no decide: ningun metodo publico puede producir Estado/Decision/PlanActivacion.

    Se verifica por anotacion de retorno, no por recuento: anadir manana un `diagnostico() -> str` no
    rompe nada; anadir un metodo que devuelva una decision, si. (Que ademas no pueda CONTENER logica de
    decision lo hace cumplir la frontera por AST, en test_frontera_builder.py.)
    """
    import inspect

    from aura_skeleton.core.capacidades import Decision, Estado, PlanActivacion

    prohibidos = {Estado, Decision, PlanActivacion}
    for nombre, metodo in inspect.getmembers(ActivationContextBuilder, callable):
        if nombre.startswith("_"):
            continue
        retorno = inspect.signature(metodo).return_annotation
        assert retorno not in prohibidos, f"{nombre}() devuelve un tipo de decision: {retorno}"


# --- El Builder PRESERVA lo que producen los detectores (no valida I-AC1: decision del CEO) ---
def test_builder_no_valida_ni_filtra_lo_que_producen_los_detectores():
    ctx = _builder(_EntornoDoble("capacidad_no_declarada")).construir()
    assert ctx.capacidades_soportadas == frozenset({"capacidad_no_declarada"})
