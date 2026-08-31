"""RED · `D-ORCH-2` — el nivel `REVIEW`, **construido y con la puerta cerrada**.

## Lo que dicen las fuentes, y por qué la respuesta se parte en dos

**A · Determinado por contrato:**

- El **CTO es Fable (IA)** `[EJEC]` (`1.1:94`), y `D22` **ya le delegó** la aprobación de capítulos
  de ejecución con criterios: *«sin cambio de alcance, respeto de decisiones previas, cinco preguntas
  D21»*. Delegar en un agente **no es inédito en este proyecto**.
  *(El `DP §10.3` afirma que «D22 delegó en un **CTO humano**». **Es falso**, y esto lo corrige.)*
- **«No aprueba su propio trabajo»** (`1.1:94`, límite del CTO). Regla dura y ya vigente.
- La autoridad de aprobación **final** del CEO *«no es delegable a ningún agente»* (`1.1:93`).

**B · Derivable sin autoridad nueva:** el mecanismo — clasificar a `REVIEW`, pedir veredicto a un
revisor **distinto del proponente**, exigir los criterios de `D22`, registrar todo. Es instrumentar
reglas existentes, no crear ninguna.

**C · Concesión nueva, que NO tomo:** que ese veredicto **sustituya el acta humana** para ejecutar.
`ADR-0003:33`: *«los niveles superiores de autonomía solo se habilitan por política y decisión del
usuario/CEO, **nunca automáticamente**»*. Y `D22` delega sobre **documentos**, no sobre ejecución de
código.

Por eso el mecanismo queda **completo y apagado**: `REVIEW_HABILITADO` es `False` y solo un acta lo
enciende.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import pytest

import autoconstruccion as ac
import review as rv


# ================================================ LA PUERTA — cerrada hasta acta del CEO --


def test_REVIEW_nace_DESHABILITADO():
    """`ADR-0003:33`: *«nunca automáticamente»*. Nacer encendido sería concederse el nivel a sí mismo."""
    assert rv.REVIEW_HABILITADO is False
    assert rv.habilitado() is False


def test_sin_habilitacion_una_tarea_REVIEW_no_se_ejecuta(tmp_path):
    d = pathlib.Path(tmp_path)
    tarea = {"id": "T-1", "accion": "eliminar_codigo_muerto", "fichero": "entorno/control-plane/x.py"}
    # `match` preciso: hay dos puertas que lanzan la misma excepción —nivel apagado y acción fuera
    # de alcance— y un patrón laxo las confundía, dejando sobrevivir un mutante que abría la primera.
    with pytest.raises(rv.ReviewNoHabilitado, match="REVIEW no esta habilitado"):
        rv.ejecutar_bajo_review(d, tarea, propuesto_por="aura", autoridad="orquestador")


def test_solo_un_ACTA_del_CEO_habilita_el_nivel(tmp_path):
    """No un agente, no una variable de entorno, no el paso del tiempo."""
    d = pathlib.Path(tmp_path)
    for no_humano in ("aura", "orquestador", "auditor-consistencia", "fable"):
        with pytest.raises(rv.ReviewNoHabilitado, match="humana|CEO"):
            rv.habilitar(d, por=no_humano, acta="me habilito yo", alcance=("eliminar_codigo_muerto",))
    with pytest.raises(rv.ReviewNoHabilitado, match="acta"):
        rv.habilitar(d, por="ceo", acta="", alcance=("eliminar_codigo_muerto",))
    registro = rv.habilitar(d, por="ceo", acta="DEC-ORCH-2 aprobada",
                            alcance=("eliminar_codigo_muerto",))
    assert rv.habilitado(d) is True
    assert registro["alcance"] == ("eliminar_codigo_muerto",)


def test_un_acta_NO_puede_habilitar_materia_reservada(tmp_path):
    """Ni el CEO delega por esta vía lo que `D22` se reserva: para eso están las actas, no un
    parámetro de alcance. Sin este caso, la comprobación del alcance al habilitar no se ejercitaba."""
    d = pathlib.Path(tmp_path)
    for reservada in ("modificar_adr", "modificar_d24", "alerta_de_arquitectura",
                      "seleccionar_tecnologia", "guardrail_etico"):
        with pytest.raises(rv.MateriaReservada, match="reservada"):
            rv.habilitar(d, por="ceo", acta="acta", alcance=("eliminar_codigo_muerto", reservada))
    assert rv.habilitado(d) is False, "un intento rechazado no deja el nivel encendido"


def test_la_habilitacion_tiene_ALCANCE_CERRADO(tmp_path):
    """Habilitar `REVIEW` no es un cheque en blanco: el acta dice **qué** acciones cubre. Una acción
    fuera del alcance sigue exigiendo acta individual."""
    d = pathlib.Path(tmp_path)
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2", alcance=("eliminar_codigo_muerto",))
    assert rv.en_alcance(d, "eliminar_codigo_muerto") is True
    assert rv.en_alcance(d, "refactorizar_modulo") is False
    assert rv.en_alcance(d, "modificar_adr") is False


# ================================ LO DERIVABLE — los criterios de D22, instrumentados --


def test_el_veredicto_aplica_los_CUATRO_criterios_de_D22():
    """`D22` literal: *«sin cambio de alcance, respeto de decisiones previas, cinco preguntas D21»*,
    más materia reservada. Los cuatro se comprueban, no se dan por buenos."""
    assert rv.CRITERIOS_D22 == ("alcance", "consistencia", "cinco_preguntas_d21", "materia_reservada")
    juicio = rv.aplicar_criterios({"accion": "eliminar_codigo_muerto", "cambia_alcance": False,
                                   "respeta_decisiones": True, "d21_afirmativas": True,
                                   "materia_reservada": False})
    assert juicio["cumple"] is True and juicio["fallos"] == ()


def test_basta_UN_criterio_incumplido_para_que_no_cumpla():
    for roto in ("cambia_alcance", "respeta_decisiones", "d21_afirmativas", "materia_reservada"):
        base = {"accion": "x", "cambia_alcance": False, "respeta_decisiones": True,
                "d21_afirmativas": True, "materia_reservada": False}
        base[roto] = not base[roto]
        juicio = rv.aplicar_criterios(base)
        assert juicio["cumple"] is False, f"{roto} debía bastar para rechazar"
        assert juicio["fallos"], "y debe decir cuál falló"


def test_MATERIA_RESERVADA_nunca_pasa_por_REVIEW(tmp_path):
    """`D22` reserva al CEO: *«tecnología con alternativas (D3), guardrails éticos, decisiones de
    rango 1 y Alertas de Arquitectura»*. Ninguna es delegable, ni con `REVIEW` habilitado."""
    d = pathlib.Path(tmp_path)
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2", alcance=rv.TODO_LO_DELEGABLE)
    for reservada in ("modificar_adr", "modificar_d24", "alerta_de_arquitectura",
                      "seleccionar_tecnologia", "guardrail_etico"):
        assert rv.es_materia_reservada(reservada) is True
        with pytest.raises(rv.MateriaReservada):
            rv.ejecutar_bajo_review(d, {"id": "T", "accion": reservada, "fichero": "x.py"},
                                    propuesto_por="aura", autoridad="orquestador")


def test_EL_QUE_PROPONE_NO_REVISA(tmp_path):
    """`1.1:94`, límite del CTO: **«No aprueba su propio trabajo»**. Es la misma regla que CLAUDE.md
    aplica a los incrementos —*«el que implementa nunca audita»*— y sin ella `REVIEW` sería un sello
    que el proponente se pone a sí mismo."""
    d = pathlib.Path(tmp_path)
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2", alcance=("eliminar_codigo_muerto",))
    with pytest.raises(rv.RevisorNoIndependiente, match="propio trabajo|independiente"):
        rv.pedir_veredicto(d, {"id": "T", "accion": "eliminar_codigo_muerto"},
                           propuesto_por="auditor-consistencia", revisor="auditor-consistencia")
    veredicto = rv.pedir_veredicto(d, {"id": "T", "accion": "eliminar_codigo_muerto"},
                                   propuesto_por="aura", revisor="auditor-consistencia")
    assert isinstance(veredicto, ac.Veredicto)


def test_el_veredicto_SIGUE_sin_poder_autorizar():
    """Lo que `D-ORCH-2` no cambia. `1.1:93`: la autoridad final del CEO no es delegable. `REVIEW`
    permite **ejecutar dentro de un alcance ya autorizado**; no convierte un veredicto en permiso."""
    v = ac.Veredicto(revisor="auditor-consistencia", objeciones=(), resumen="sin objeciones")
    assert ac.autoriza(v) is False
    assert "autorizado" not in set(v.__dataclass_fields__)


def test_una_objecion_DETIENE_la_ejecucion(tmp_path):
    """Un revisor que objeta para el trabajo. Si no lo parase, revisar no serviría de nada."""
    d = pathlib.Path(tmp_path)
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2", alcance=("eliminar_codigo_muerto",))
    objetor = ac.Veredicto(revisor="auditor-consistencia", objeciones=("rompe una garantía",),
                           resumen="objeto")
    assert rv.permite_seguir(objetor) is False
    assert rv.permite_seguir(ac.Veredicto("auditor-consistencia", (), "sin objeciones")) is True
    assert rv.permite_seguir(None) is False, "el silencio no habilita nada (1.1:85)"


# ================================================= EL CIRCUITO, CON LA PUERTA ABIERTA --


def test_circuito_REVIEW_completo_cuando_el_CEO_lo_habilita(tmp_path):
    """Demuestra que el mecanismo **funciona**, sin concederse nada: la habilitación vive en este
    directorio temporal y desaparece con él."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "modulo.py"
    objetivo.write_text("def viva():\n    return 1\n\n\ndef _muerta():\n    return 2\n",
                        encoding="utf-8")
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2 aprobada", alcance=("eliminar_codigo_muerto",))

    resultado = rv.ejecutar_bajo_review(
        d, {"id": "T-R", "accion": "eliminar_codigo_muerto", "fichero": str(objetivo),
            "simbolo": "_muerta", "cambia_alcance": False, "respeta_decisiones": True,
            "d21_afirmativas": True, "materia_reservada": False},
        propuesto_por="aura", autoridad="orquestador", verificacion=lambda: True)

    assert resultado["ejecutado"] is True and resultado["efecto_verificado"] is True
    assert resultado["revisor"] != "aura", "revisor independiente del proponente"
    texto = objetivo.read_text(encoding="utf-8")
    assert "_muerta" not in texto and "def viva" in texto

    tipos = [e["tipo"] for e in cp.leer_eventos(d)]
    for exigido in ("review_habilitado", "veredicto_emitido", "cambio_aplicado"):
        assert exigido in tipos, f"falta el registro {exigido}"
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_bajo_REVIEW_el_cambio_sigue_siendo_REVERSIBLE(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "m.py"
    fuente = "def _muerta():\n    return 1\n"
    objetivo.write_text(fuente, encoding="utf-8")
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2", alcance=("eliminar_codigo_muerto",))
    resultado = rv.ejecutar_bajo_review(
        d, {"id": "T", "accion": "eliminar_codigo_muerto", "fichero": str(objetivo),
            "simbolo": "_muerta", "cambia_alcance": False, "respeta_decisiones": True,
            "d21_afirmativas": True, "materia_reservada": False},
        propuesto_por="aura", autoridad="orquestador", verificacion=lambda: False)
    assert resultado["revertido"] is True
    assert objetivo.read_text(encoding="utf-8") == fuente


def test_bajo_REVIEW_la_gobernanza_SIGUE_intocable(tmp_path):
    """La frontera dura no se mueve porque `REVIEW` esté encendido."""
    d = pathlib.Path(tmp_path)
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2", alcance=rv.TODO_LO_DELEGABLE)
    for prohibido in ("CLAUDE.md", "adr/0003.md", "docs/libro-01/1.1.md", "ROADMAP.md"):
        with pytest.raises((ac.ZonaProhibida, rv.MateriaReservada)):
            rv.ejecutar_bajo_review(
                d, {"id": "T", "accion": "eliminar_codigo_muerto", "fichero": prohibido,
                    "simbolo": "_x", "cambia_alcance": False, "respeta_decisiones": True,
                    "d21_afirmativas": True, "materia_reservada": False},
                propuesto_por="aura", autoridad="orquestador")


def test_la_habilitacion_NO_se_hereda_entre_directorios(tmp_path):
    """Habilitar `REVIEW` para un trabajo no lo habilita para todos: el registro vive con su log."""
    uno = pathlib.Path(tmp_path) / "a"
    otro = pathlib.Path(tmp_path) / "b"
    uno.mkdir()
    otro.mkdir()
    rv.habilitar(uno, por="ceo", acta="DEC-ORCH-2", alcance=("eliminar_codigo_muerto",))
    assert rv.habilitado(uno) is True
    assert rv.habilitado(otro) is False
