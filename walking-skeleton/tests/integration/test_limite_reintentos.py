"""Capacidad 017 — AURORA usa su historial para dejar de insistir (acta del CEO, 2026-08-10).

EL DEFECTO, MEDIDO tras integrar Pieza 2. Una tarea aprobada que después falla POR OTRA RAZÓN se
bloquea, y en el latido siguiente vuelve a reabrirse porque su decisión sigue aprobada:

    latido 1: reabiertas=1  estado=abierta  intentos=1
    latido 2: reabiertas=1  estado=abierta  intentos=2
    latido 3: reabiertas=1  estado=abierta  intentos=3
    latido 4: reabiertas=1  estado=abierta  intentos=4

En `--servir` gira indefinidamente. No compromete la seguridad -nada se ejecuta sin permiso, y el
permiso es válido-, pero AURORA gasta su latido sin avanzar.

LO QUE HACE ESTE INCREMENTO. `intentos` YA cuenta bien; el único que lo leía era el IMA, y sólo para
comprobar que el campo existe. Aquí se lee para DECIDIR: al alcanzar el límite, la tarea deja de
reabrirse y queda escalada al CEO con su historial intacto. Aritmética sobre un campo existente: sin
LLM, sin inferencia, sin componentes nuevos.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.decisiones import (
    _LIMITE_DE_REINTENTOS,
    AlmacenDecisiones,
    huella_de,
    reabrir_aprobadas,
)
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea


@pytest.fixture
def estado(tmp_path):
    return AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl"))


@pytest.fixture
def almacen(tmp_path):
    return AlmacenDecisiones(str(tmp_path / "decisiones"))


def _tarea_aprobada_y_bloqueada(estado, almacen, tarea_id="t-1", objetivo="obj"):
    """Una tarea que el CEO ya aprobó y que está bloqueada esperando volver al trabajo."""
    estado.registrar(Tarea(objetivo_id=objetivo, tarea_id=tarea_id, descripcion="cambio", estado="abierta"))
    estado.transitar(objetivo, tarea_id, "bloqueada", autoridad="director", causa="permisos: pendiente")
    almacen.solicitar("proponer_cambio", {"t": tarea_id}, "efecto", f"tr:{tarea_id}")
    almacen.aprobar(huella_de("proponer_cambio", {"t": tarea_id}, "efecto"))


def _fallar(estado, tarea_id="t-1", objetivo="obj", motivo="error: el adaptador fallo"):
    """El resultado real de un latido que no salió, TAL COMO lo hace el director: transita a
    bloqueada y ANEXA el motivo a `bloqueos` -- `causa` sola no lo conserva, y sin eso la prueba del
    historial mediría otra cosa."""
    vigente = _tarea(estado, tarea_id, objetivo)
    estado.transitar(
        objetivo,
        tarea_id,
        "bloqueada",
        autoridad="director",
        causa=motivo,
        bloqueos=[*vigente.bloqueos, motivo],
    )


def _tarea(estado, tarea_id="t-1", objetivo="obj") -> Tarea:
    return [t for t in estado.tareas(objetivo) if t.tarea_id == tarea_id][-1]


# ----------------------------------------------------------------- EL UMBRAL ES EXPLÍCITO --


def test_el_limite_de_reintentos_esta_declarado_y_es_el_acordado():
    """Condición 4 del acta: el umbral no puede ser un número mágico dentro de una comparación.

    Fijarlo aquí obliga a que cambiarlo sea una decisión declarada, no un ajuste silencioso -que es
    la regla del CEO sobre valores numéricos (2026-08-04)-."""
    assert _LIMITE_DE_REINTENTOS == 3, "el umbral cambió sin declararlo en el DP"


# ------------------------------------------------------- EL BUCLE MEDIDO SE CIERRA --


def test_el_bucle_medido_se_cierra(estado, almacen):
    """LA PRUEBA QUE JUSTIFICA EL INCREMENTO. Reproduce exactamente la medición del DP §1 y exige que
    a partir del límite deje de reabrirse. Sin esto, `--servir` gira para siempre."""
    _tarea_aprobada_y_bloqueada(estado, almacen)

    reaperturas = []
    for _ in range(6):
        n = reabrir_aprobadas(almacen, estado)
        reaperturas.append(n)
        if _tarea(estado).estado == "abierta":
            _fallar(estado)

    # El bloqueo que deja la tarea esperando aprobación YA cuenta como intento 1, así que un límite
    # de 3 concede DOS reintentos -- que es exactamente lo que el DP declara: «3 da dos reintentos».
    reintentos_concedidos = _LIMITE_DE_REINTENTOS - 1
    assert sum(reaperturas) == reintentos_concedidos, (
        f"se reabrió {sum(reaperturas)} veces; con límite {_LIMITE_DE_REINTENTOS} tocan "
        f"{reintentos_concedidos}: {reaperturas}"
    )
    assert reaperturas[-1] == 0, "seguía reabriéndose al final: el bucle no se cerró"
    assert _tarea(estado).intentos >= _LIMITE_DE_REINTENTOS


def test_por_debajo_del_limite_el_comportamiento_no_cambia(estado, almacen):
    """CONTROL. Sin él, «dejar de reabrir» se cumpliría trivialmente no reabriendo nunca, y Pieza 2
    quedaría anulada."""
    _tarea_aprobada_y_bloqueada(estado, almacen)
    assert reabrir_aprobadas(almacen, estado) == 1, "no reabrió una tarea aprobada en su primer intento"
    assert _tarea(estado).estado == "abierta"


# --------------------------------------------------------------- LA ESCALADA AL CEO --


def test_al_alcanzar_el_limite_la_tarea_queda_escalada_con_su_historial(estado, almacen):
    """Condiciones 5, 6 y 8 del acta. Pararse en silencio sería peor que girar: AURORA dejaría de
    insistir y el CEO no se enteraría de que hay trabajo esperándole."""
    _tarea_aprobada_y_bloqueada(estado, almacen)
    for _ in range(6):
        if reabrir_aprobadas(almacen, estado) and _tarea(estado).estado == "abierta":
            _fallar(estado)

    t = _tarea(estado)
    assert t.estado == "bloqueada"
    assert t.intentos >= _LIMITE_DE_REINTENTOS, f"el historial de intentos se perdió: {t.intentos}"

    escaladas = [b for b in t.bloqueos if "escalada" in b.lower()]
    assert len(escaladas) == 1, f"la escalada no se anexó una sola vez: {t.bloqueos}"
    assert str(_LIMITE_DE_REINTENTOS) in escaladas[0], f"la escalada no dice cuántos intentos hubo: {escaladas[0]!r}"
    assert any("el adaptador fallo" in b for b in t.bloqueos), "se perdieron los motivos de los fallos anteriores"


def test_la_escalada_no_se_repite_en_cada_latido(estado, almacen):
    """Un servicio permanente late muchas veces. Si cada uno anexara una escalada, el historial se
    volvería ilegible justo cuando el CEO más lo necesita: al revisar por qué algo no avanza."""
    _tarea_aprobada_y_bloqueada(estado, almacen)
    for _ in range(15):
        if reabrir_aprobadas(almacen, estado) and _tarea(estado).estado == "abierta":
            _fallar(estado)

    escaladas = [b for b in _tarea(estado).bloqueos if "escalada" in b.lower()]
    assert len(escaladas) == 1, f"{len(escaladas)} escaladas anexadas tras 15 latidos"


def test_una_aprobacion_posterior_no_borra_el_historial(estado, almacen):
    """Condición 8, literal. El CEO puede volver a aprobar tras revisar la escalada; eso no puede
    resetear el contador en silencio, o el límite se esquivaría sin que nadie lo viera."""
    _tarea_aprobada_y_bloqueada(estado, almacen)
    for _ in range(6):
        if reabrir_aprobadas(almacen, estado) and _tarea(estado).estado == "abierta":
            _fallar(estado)
    intentos_antes = _tarea(estado).intentos

    almacen.aprobar(huella_de("proponer_cambio", {"t": "t-1"}, "efecto"))
    reabrir_aprobadas(almacen, estado)

    assert _tarea(estado).intentos >= intentos_antes, "una aprobación posterior reseteó el historial de intentos"


# ------------------------------------------- EL CICLO SIGUE: una escalada no detiene a AURORA --


def test_una_tarea_escalada_no_impide_reabrir_las_demas(estado, almacen):
    """Condición 7 del acta, y la métrica de gobierno: que AURORA se pare en una tarea no puede
    pararla en todas."""
    _tarea_aprobada_y_bloqueada(estado, almacen, tarea_id="t-agotada")
    for _ in range(6):
        if reabrir_aprobadas(almacen, estado) and _tarea(estado, "t-agotada").estado == "abierta":
            _fallar(estado, "t-agotada")

    _tarea_aprobada_y_bloqueada(estado, almacen, tarea_id="t-nueva")
    assert reabrir_aprobadas(almacen, estado) == 1, "la tarea agotada impidió reabrir una tarea sana"
    assert _tarea(estado, "t-nueva").estado == "abierta"
    assert _tarea(estado, "t-agotada").estado == "bloqueada"


@pytest.mark.asyncio
async def test_e2e_una_tarea_que_falla_siempre_no_detiene_el_resto_del_backlog(tmp_path):
    """E2E exigida por el acta (condición 9), sobre el sistema COMPUESTO y su latido real.

    Una tarea cuyo responsable no tiene ejecutor falla en CADA intento -es el modo de fallo más
    reproducible que existe-. El resto del backlog debe terminarse igualmente, y el ciclo debe
    detenerse por falta de trabajo, no por girar sobre la tarea rota.
    """
    from aura_skeleton.composicion import Configuracion, componer

    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(cfg)
    s.estado_operativo.registrar(
        Tarea(objetivo_id="obj", tarea_id="t-rota", descripcion="sin ejecutor", responsable="inexistente")
    )
    # `diagnostico` y no `auditor`: el auditor mide las garantías REALES del repositorio, así que un
    # mutante desapuntado en cualquier arnés hacía fallar esta prueba por una razón ajena -pasó, y
    # AURORA hizo lo correcto: detectó las garantías rotas y bloqueó la tarea-. El diagnóstico no
    # depende del estado del repo, así que aquí mide lo que dice medir.
    s.estado_operativo.registrar(
        Tarea(objetivo_id="obj", tarea_id="t-sana", descripcion="diagnosticar", responsable="diagnostico")
    )
    buzon = AlmacenDecisiones(str(tmp_path / "decisiones"))
    buzon.solicitar("proponer_cambio", {"t": "t-rota"}, "efecto", "tr:t-rota")
    buzon.aprobar(huella_de("proponer_cambio", {"t": "t-rota"}, "efecto"))

    await s.motor_ciclo.correr("obj", max_latidos=20)

    tareas = {t.tarea_id: t for t in s.estado_operativo.tareas("obj")}
    assert tareas["t-sana"].estado == "terminada", "el trabajo sano no salió adelante"
    assert tareas["t-rota"].estado == "bloqueada"
    assert tareas["t-rota"].intentos <= _LIMITE_DE_REINTENTOS + 1, (
        f"la tarea rota se reintentó {tareas['t-rota'].intentos} veces: el límite no cortó el bucle"
    )
    assert any("escalada" in b.lower() for b in tareas["t-rota"].bloqueos), "no quedó escalada al CEO"
