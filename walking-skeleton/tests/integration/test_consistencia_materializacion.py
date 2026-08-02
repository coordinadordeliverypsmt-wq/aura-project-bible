"""AURA nunca declara activa una capacidad que en realidad está ejecutando degradada.

Decisión del CEO (2026-08-02), tras el Decision Package del artefacto de N2:

    "El problema real es la degradación silenciosa; AURA nunca debe declarar una capacidad activa si
     en realidad está ejecutando otra. Esa inconsistencia debe corregirse antes que cualquier
     movimiento de artefactos."

Y el principio general que la acompaña: **primero se corrigen las inconsistencias entre el estado
declarado y el estado real; después se optimiza la infraestructura.**

El defecto verificado que originó esto (revisión estratégica 2026-08-02): con el artefacto de
embeddings ausente y un perfil de hardware suficiente, el plan seguía declarando `memoria` como
**ACTIVA** mientras el sistema materializaba **N1**, y el aviso ni siquiera llegaba al registro
forense (`obs.log` sin `audit=True`).

**Qué NO se cambia aquí.** El `PlanActivacion` es intocable: INV-7 fija que el plan se interpreta en
un único punto y **nunca se reinterpreta**, y el `CapabilityManager` es el único que decide estados.
El plan dice qué **permite el hardware** — y eso sigue siendo cierto aunque falte un artefacto. Lo que
faltaba era el otro hecho: qué se **consiguió ensamblar** realmente. Esta prueba fija que ese segundo
hecho exista, sea auditable y sea el que AURA declara hacia fuera (INV-9: no se finge capacidad).
"""

import json

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.capacidades import Estado, PerfilHardware

RAM_SUFICIENTE_PARA_N2 = 16000.0  # supera el umbral del catálogo (8000) -> el plan pide N2


@pytest.fixture
def config(tmp_path):
    return Configuracion(
        datos=str(tmp_path / "datos"),
        raices_permitidas=(str(tmp_path),),
        usar_stack_real=False,
        perfil=PerfilHardware(recursos={"ram_mb": RAM_SUFICIENTE_PARA_N2}),
    )


def _materializacion(sistema, capacidad):
    return next((m for m in sistema.materializaciones if m.capacidad == capacidad), None)


def test_declara_degradada_la_capacidad_que_no_pudo_materializarse(config, monkeypatch):
    """El plan permite N2, el artefacto no está: AURA debe declarar DEGRADADA, no ACTIVA."""
    monkeypatch.setenv("AURA_EMBED_MODEL_DIR", "/ruta/que/no/existe")

    sistema = componer(config)

    m = _materializacion(sistema, "memoria")
    assert m is not None, "no se registró qué se materializó para 'memoria'"
    assert m.estado_plan is Estado.ACTIVA, "el plan sí permitía N2 (el perfil tiene RAM de sobra)"
    assert m.degradada is True, "se materializó N1 con el plan pidiendo N2: es una degradación"
    assert m.estado_efectivo is Estado.DEGRADADA, "AURA no puede declarar ACTIVA lo que corre degradado"
    assert "N1" in m.nivel, f"el nivel efectivo debe nombrar lo que de verdad corre: {m.nivel!r}"
    assert m.motivo, "una degradación sin motivo no es explicable al usuario"


def test_la_degradacion_silenciosa_queda_en_el_registro_forense(config, monkeypatch, tmp_path):
    """Sin auditoría, la degradación es invisible: era exactamente el defecto (log sin `audit=True`)."""
    monkeypatch.setenv("AURA_EMBED_MODEL_DIR", "/ruta/que/no/existe")

    sistema = componer(config)
    obs.log("TEST", "cierre", "fuerza el volcado del audit", "-", audit=True)

    contenido = open(sistema.ruta_audit, encoding="utf-8").read()
    lineas = [json.loads(x) for x in contenido.splitlines() if x.strip()]
    # Se busca la entrada ESPECÍFICA de discrepancia. Un `in` laxo sobre todo el volcado daría un falso
    # verde: la línea de arranque ya contiene la palabra "degradadas=[]" aunque no haya discrepancia.
    discrepancias = [
        x for x in lineas if "materializacion" in str(x.get("msg", "")).lower() and "memoria" in str(x.get("msg", ""))
    ]
    assert discrepancias, (
        "la degradación de materialización no llegó al registro forense como entrada propia; "
        f"volcado: {[str(x.get('msg', ''))[:80] for x in lineas]}"
    )
    assert "/ruta/que/no/existe" in str(discrepancias[0]["msg"]), "la entrada no explica la causa"


def test_sin_degradacion_no_se_inventa_una_alerta(config):
    """CONTROL: si no hay discrepancia, no se reporta ninguna. Sin esto, marcar SIEMPRE degradada pasaría."""
    # Perfil modesto: el plan ya decide DEGRADADA por sí mismo; materializar N1 es lo esperado, no un fallo.
    config.perfil = PerfilHardware(recursos={"ram_mb": 2000.0})

    sistema = componer(config)

    m = _materializacion(sistema, "memoria")
    assert m is not None
    assert m.estado_plan is Estado.DEGRADADA
    assert m.degradada is False, "el plan ya pedía N1: materializar N1 NO es una degradación"
    assert m.estado_efectivo is Estado.DEGRADADA, "coincide con el plan"


def test_el_manifiesto_declara_su_procedencia(tmp_path):
    """ADR-0022 + decisión del CEO: el checksum garantiza integridad; `source` garantiza recuperación.

    Sin procedencia, un artefacto perdido se puede verificar pero no reponer: es exactamente lo que la
    revisión estratégica encontró al evaluar el riesgo del modelo de N2.
    """
    from aura_skeleton.artefactos import ArtefactoNoResuelto, cargar_manifiesto

    base = tmp_path / "artefacto"
    base.mkdir()
    campos = {
        "id": "embedder.x",
        "version": "1.0.0",
        "checksum": "0" * 64,
        "licencia": "Apache-2.0",
        "formato": "onnx+tokenizer",
        "dims": 384,
        "source": "https://huggingface.co/sentence-transformers/x",
    }
    (base / "manifiesto.json").write_text(json.dumps(campos), encoding="utf-8")
    assert cargar_manifiesto(str(base)).source == campos["source"]

    # Un manifiesto sin procedencia se rechaza: si se admitiera, el campo sería decorativo.
    sin_source = {k: v for k, v in campos.items() if k != "source"}
    (base / "manifiesto.json").write_text(json.dumps(sin_source), encoding="utf-8")
    with pytest.raises(ArtefactoNoResuelto):
        cargar_manifiesto(str(base))


def test_el_arranque_no_anuncia_como_activa_una_capacidad_degradada(config, monkeypatch, capsys):
    """Lo que el operador LEE al arrancar debe ser el estado efectivo, no el planificado."""
    monkeypatch.setenv("AURA_EMBED_MODEL_DIR", "/ruta/que/no/existe")

    sistema = componer(config)

    assert "memoria" not in sistema.capacidades_activas_efectivas, (
        "AURA sigue anunciando 'memoria' como activa mientras ejecuta N1"
    )
    assert "memoria" in sistema.capacidades_degradadas_efectivas
