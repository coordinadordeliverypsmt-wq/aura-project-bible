"""RED · SEXTA FUENTE DE DESCUBRIMIENTO — deteccion de ESTANCAMIENTO/FRICCION.

DP-SELF-EVOLUTION-01 · Fase A (aprobada por el CEO). La Fase B (registrar ids en el log) NO fue
aprobada, y esta bateria no la asume.

La fuente `estancamiento` cierra el unico tramo que hoy exige que un humano nombre la carencia:
observa el historial, detecta que el ciclo lleva K vueltas sin progreso con trabajo bloqueado sin
resolver, y ELEVA una `DECISION_REQUIRED` para el CEO. Nunca ejecuta, nunca se autoriza, nunca
genera `OPORTUNIDAD_REAL`.

Garantias que esta bateria hace verificables:

- **solo lectura**, comprobado sobre el arbol sintactico (no sobre el comportamiento);
- **no ejecutable**: `DECISION_REQUIRED -> planificador.a_tarea() -> None`;
- **no se autodetecta**: si lo unico que queda es su propia elevacion, no hay estancamiento;
- **id estable**: la misma racha produce el mismo id, aunque se alargue;
- **K no es un numero arbitrario escondido**: no tiene valor por defecto y la fuente es INERTE
  mientras el acta no lo fije (fail-closed), igual que `REVIEW_HABILITADO=False`.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import control_plane as cp
import descubrimiento as des
import planificador as plan
import estancamiento as est


# ============================================================ ayudas --
# Construyen historiales de ciclos tal y como los escribe `motor_autonomia`. Fixtures aislados en
# `tmp_path`: NUNCA se toca el historial real (lo garantiza ademas el conftest).

def _ciclo_estancado(d, *, encontradas=8, bloqueadas=6, elevadas=2):
    """Un ciclo real y estancado: se descubrio trabajo, todo bloqueado/elevado, 0 ejecutadas,
    ningun efecto."""
    cp.registrar_evento(d, "motor_iniciado", {"raiz": str(d), "review": True, "tope": 3})
    cp.registrar_evento(d, "descubrimiento_realizado", {
        "encontradas": encontradas, "fuentes": ["bloqueos_registrados"], "fuentes_con_error": [],
        "por_clase": {"OPORTUNIDAD_REAL": 0, "BLOQUEADA": bloqueadas,
                      "DECISION_REQUIRED": elevadas, "FALSO_HUECO": 0},
        "raiz": str(d)})
    cp.registrar_evento(d, "ciclo_detenido", {"ejecutadas": 0, "bloqueadas": bloqueadas,
                                              "elevadas": elevadas, "motivo": "cola agotada",
                                              "detenida_en": None})


def _ciclo_ocioso(d):
    """Ocio sano: no se descubrio nada. NO es estancamiento."""
    cp.registrar_evento(d, "motor_iniciado", {"raiz": str(d), "review": True, "tope": 3})
    cp.registrar_evento(d, "descubrimiento_realizado", {
        "encontradas": 0, "fuentes": ["bloqueos_registrados"], "fuentes_con_error": [],
        "por_clase": {"OPORTUNIDAD_REAL": 0, "BLOQUEADA": 0, "DECISION_REQUIRED": 0,
                      "FALSO_HUECO": 0},
        "raiz": str(d)})
    cp.registrar_evento(d, "ciclo_detenido", {"ejecutadas": 0, "bloqueadas": 0, "elevadas": 0,
                                              "motivo": "cola agotada", "detenida_en": None})


def _ciclo_con_progreso(d, ident="P-1", fichero="x.py", simbolo="_muerta"):
    """Un ciclo con EFECTO real: propuesta -> autorizada -> cambio aplicado, verificado y no
    revertido. Es exactamente el predicado `_efecto_real` que reutiliza la fuente."""
    cp.registrar_evento(d, "motor_iniciado", {"raiz": str(d), "review": True, "tope": 3})
    cp.registrar_evento(d, "descubrimiento_realizado", {
        "encontradas": 1, "fuentes": ["codigo_muerto"], "fuentes_con_error": [],
        "por_clase": {"OPORTUNIDAD_REAL": 1, "BLOQUEADA": 0, "DECISION_REQUIRED": 0,
                      "FALSO_HUECO": 0},
        "raiz": str(d)})
    cp.registrar_evento(d, "propuesta_registrada", {
        "id": ident, "fichero": fichero, "simbolo": simbolo, "forma": "funcion",
        "estado": "PROPUESTA", "autorizada": False, "linea": None, "motivo": "bajo REVIEW"})
    cp.registrar_evento(d, "propuesta_autorizada", {
        "id": ident, "autorizada_por": "REVIEW:auditor-consistencia", "acta": "acta"})
    cp.registrar_evento(d, "cambio_aplicado", {
        "id": ident, "fichero": fichero, "simbolo": simbolo, "efecto_verificado": True,
        "verificacion_sana": True, "revertido": False, "autoridad": "orquestador"})
    cp.registrar_evento(d, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0, "elevadas": 0,
                                              "motivo": "cola agotada", "detenida_en": None})


# `k` ILUSTRATIVO para las pruebas: se PASA explicitamente. NO es el valor contractual de produccion
# —ese lo fija el acta del CEO—; aqui solo demuestra el mecanismo.
K = 3


# ============================================================ 1 · detecta estancamiento real --

def test_detecta_estancamiento_real(tmp_path):
    for _ in range(K):
        _ciclo_estancado(tmp_path)
    op = est.estancamiento(tmp_path, tmp_path, k=K)
    assert len(op) == 1, "K ciclos consecutivos sin progreso con backlog deben elevar una senal"
    assert op[0].estado == des.DECISION_REQUIRED
    assert op[0].accion == "revisar_estancamiento"


# ============================================================ 2 · no detecta ocio sano --

def test_no_detecta_ocio_sano(tmp_path):
    for _ in range(K + 2):
        _ciclo_ocioso(tmp_path)
    assert est.estancamiento(tmp_path, tmp_path, k=K) == [], (
        "descubiertas=0 es cola agotada sana, no estancamiento: elevarla seria inventar friccion")


# ============================================================ 3 · no detecta si hubo progreso --

def test_no_detecta_estancamiento_si_hubo_progreso(tmp_path):
    """El progreso rompe la racha. Con progreso dentro de la ventana no hay K consecutivos."""
    _ciclo_estancado(tmp_path)
    _ciclo_estancado(tmp_path)
    _ciclo_con_progreso(tmp_path)          # progreso: resetea
    _ciclo_estancado(tmp_path)
    _ciclo_estancado(tmp_path)             # racha vigente = 2 < K
    assert est.estancamiento(tmp_path, tmp_path, k=K) == []


def test_progreso_en_el_ultimo_ciclo_anula_la_senal(tmp_path):
    for _ in range(K):
        _ciclo_estancado(tmp_path)
    _ciclo_con_progreso(tmp_path)          # el mas reciente tuvo efecto -> racha 0
    assert est.estancamiento(tmp_path, tmp_path, k=K) == []


def test_no_eleva_sobre_historial_inconsistente(tmp_path):
    """Robustez: un ciclo cuyo `encontradas=0` contradice un `por_clase` con backlog es un historial
    incoherente (solo posible con el log manipulado a mano, riesgo ya documentado). Ante datos que se
    contradicen NO se eleva: el guardian `descubiertas>0` exige que de verdad se descubriera algo."""
    for _ in range(K + 1):
        cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "review": True,
                                                         "tope": 3})
        cp.registrar_evento(tmp_path, "descubrimiento_realizado", {
            "encontradas": 0, "fuentes": ["bloqueos_registrados"], "fuentes_con_error": [],
            "por_clase": {"OPORTUNIDAD_REAL": 0, "BLOQUEADA": 6, "DECISION_REQUIRED": 0,
                          "FALSO_HUECO": 0},
            "raiz": str(tmp_path)})
        cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 0, "bloqueadas": 6,
                                                         "elevadas": 0, "motivo": "cola agotada",
                                                         "detenida_en": None})
    assert est.estancamiento(tmp_path, tmp_path, k=K) == []


def test_no_cuenta_si_hay_trabajo_real_pendiente(tmp_path):
    """Si el ciclo descubrio OPORTUNIDAD_REAL, NO es estancamiento: el motor la ejecutaria. Un ciclo
    con trabajo real —aunque no se ejecutara esa vuelta— no cuenta para la racha."""
    for _ in range(K):
        cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "review": True,
                                                         "tope": 3})
        cp.registrar_evento(tmp_path, "descubrimiento_realizado", {
            "encontradas": 4, "fuentes": ["codigo_muerto"], "fuentes_con_error": [],
            "por_clase": {"OPORTUNIDAD_REAL": 1, "BLOQUEADA": 3, "DECISION_REQUIRED": 0,
                          "FALSO_HUECO": 0},
            "raiz": str(tmp_path)})
        cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 0, "bloqueadas": 3,
                                                         "elevadas": 0, "motivo": "cola agotada",
                                                         "detenida_en": None})
    assert est.estancamiento(tmp_path, tmp_path, k=K) == []


# ============================================================ 4 · mismo estancamiento, mismo id --

def test_misma_racha_mismo_id_aunque_se_alargue(tmp_path):
    for _ in range(K):
        _ciclo_estancado(tmp_path)
    id_1 = est.estancamiento(tmp_path, tmp_path, k=K)[0].id
    _ciclo_estancado(tmp_path)             # la racha se alarga; su INICIO no cambia
    id_2 = est.estancamiento(tmp_path, tmp_path, k=K)[0].id
    assert id_1 == id_2, "la misma racha debe conservar id estable; no puede depender del seq actual"


# ============================================================ 5 · no se autodetecta --

def test_no_se_autodetecta(tmp_path):
    """Si lo unico bloqueado/elevado es su PROPIA elevacion (elevadas=1, bloqueadas=0), el backlog
    ajeno es 0 y no hay estancamiento. Sin esto, la fuente se sostendria a si misma para siempre."""
    for _ in range(K + 2):
        _ciclo_estancado(tmp_path, bloqueadas=0, elevadas=1)
    assert est.estancamiento(tmp_path, tmp_path, k=1) == [], (
        "una elevacion propia recurrente no puede contar como estancamiento propio")


# ============================================================ 6 · solo lectura por AST --

_PROHIBIDOS = ("registrar_evento", "transicion", "guardar", "actualizar_estado",
               "completar_tarea", "fijar_estado_tarea", "write_text", "write_bytes",
               "autorizar", "habilitar", "ejecutar", "proponer", "mkdir")


def test_la_fuente_es_solo_lectura_por_ast():
    arbol = ast.parse(pathlib.Path(est.__file__).read_text(encoding="utf-8"))
    nombres = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    nombres |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for prohibido in _PROHIBIDOS:
        assert prohibido not in nombres, (
            f"la fuente de estancamiento nombra {prohibido!r}: debe ser estrictamente de solo lectura")


# ============================================================ 7 · fuente verificable --

def test_la_oportunidad_declara_fuente_verificable(tmp_path):
    for _ in range(K):
        _ciclo_estancado(tmp_path)
    op = est.estancamiento(tmp_path, tmp_path, k=K)[0]
    assert des.fuente_verificable(op.fuente), (
        "la procedencia debe poder irse a mirar; si no, es indistinguible de una inventada")


# ============================================================ 8 · DECISION_REQUIRED no ejecutable --

def test_la_senal_nunca_es_ejecutable(tmp_path):
    for _ in range(K):
        _ciclo_estancado(tmp_path)
    op = est.estancamiento(tmp_path, tmp_path, k=K)[0]
    assert plan.a_tarea(op) is None, (
        "un DECISION_REQUIRED jamas puede convertirse en tarea: solo OPORTUNIDAD_REAL es ejecutable")


def test_la_fuente_nunca_genera_oportunidad_real(tmp_path):
    for _ in range(K + 3):
        _ciclo_estancado(tmp_path)
    for op in est.estancamiento(tmp_path, tmp_path, k=K):
        assert op.estado != des.OPORTUNIDAD_REAL


# ============================================================ 9 · motor_autonomia sin cambios --

def test_motor_autonomia_no_conoce_la_fuente():
    """El motor debe permanecer agnostico: recoge la fuente SOLO via el dict `FUENTES`, sin nombrarla.
    Si el motor la nombrara, habria hecho falta tocarlo — y eso el DP lo prohibe."""
    fuente_motor = pathlib.Path(
        pathlib.Path(est.__file__).parent / "motor_autonomia.py").read_text(encoding="utf-8")
    assert "estancamiento" not in fuente_motor, (
        "motor_autonomia.py no debe mencionar la nueva fuente: se cablea solo en descubrimiento.FUENTES")


# ============================================================ 10 · K no arbitrario --

def test_K_no_queda_fijado_arbitrariamente_en_codigo():
    """**La garantia no era «K es None»: era «K no es un numero escondido en codigo».**

    Su propio mensaje lo decia —*«su valor lo fija el acta del CEO»*—, y mientras no hubo acta el
    unico valor legal era `None`. Con el acta `DR-D` registrada (2026-09-07), comprobar `is None`
    dejaria fuera de la ley la decision humana que la garantia existia para exigir.

    Asi que ahora se verifica **lo que la garantia siempre quiso decir**, y es mas fuerte: si K tiene
    valor, ese valor tiene que aparecer literalmente en un acta del historial. Un numero puesto a
    mano en el codigo seguiria cayendo aqui, que es de lo que habia que protegerse."""
    if est.K_ESTANCAMIENTO is not None:
        actas = [e for e in cp.leer_eventos(pathlib.Path(est.__file__).parent)
                 if e["tipo"] == "review_habilitado"]
        respaldo = [a for a in actas
                    if f"K_ESTANCAMIENTO = {est.K_ESTANCAMIENTO}" in str(a["datos"].get("acta", ""))]
        assert respaldo, (
            f"K = {est.K_ESTANCAMIENTO} sin acta que lo respalde: un numero escondido en codigo es "
            f"exactamente lo que esta garantia prohibe")
    firma = inspect.signature(est.hay_estancamiento)
    assert firma.parameters["k"].default is inspect._empty, (
        "hay_estancamiento debe exigir k explicito, sin valor por defecto")


def test_la_fuente_es_inerte_sin_K(tmp_path):
    """Fail-closed: sin K fijado, la fuente no eleva nada aunque el historial este estancado."""
    for _ in range(10):
        _ciclo_estancado(tmp_path)
    assert est.estancamiento(tmp_path, tmp_path) == [], "sin K (None) la fuente debe ser inerte"


# ============================================================ wiring + cota --

def test_la_fuente_esta_cableada_en_FUENTES():
    assert "estancamiento" in des.FUENTES
    assert callable(des.FUENTES["estancamiento"])


def test_a_lo_sumo_una_oportunidad(tmp_path):
    """Cota que sostiene la auto-exclusion: la fuente emite como mucho UNA oportunidad, la de la racha
    vigente."""
    for _ in range(10):
        _ciclo_estancado(tmp_path)
    assert len(est.estancamiento(tmp_path, tmp_path, k=2)) <= est._APORTE_PROPIO_MAXIMO
