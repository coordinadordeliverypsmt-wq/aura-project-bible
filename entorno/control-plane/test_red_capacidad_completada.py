"""E0 — distinguir **«todavia implementable»** de **«ya completada»**.

## El defecto

Tras `P-018` la capacidad de la sexta fuente quedo construida y verificada, y sin embargo:

    evaluador      -> IMPLEMENTABLE
    descubrimiento -> OPORTUNIDAD_REAL

Lo unico que impedia rehacer el trabajo era el filtro `elegible()` del planificador. La consecuencia
practica: cada diagnostico seguiria informando «1 ejecutable» para siempre.

## Donde vive la verdad, y por que ahi

**El historial de ejecucion**, no el contrato ni el fichero. `ADR-0023` lo fija —*«la unica
informacion persistente con valor semantico es el historial de eventos»*— y el mecanismo ya existia:
`planificador.completada()`, que lee el `cambio_aplicado` enlazado por orden del log.

Las otras tres alternativas se descartan con evidencia, no por gusto:

- **el contrato** no puede saberlo: es una especificacion, y lo unico que sabria decir es que su
  patron ya no aparece —*«el patron ya no esta»* no es *«el trabajo se hizo bien»*—;
- **el fichero** tampoco: un cambio a mano produciria el mismo texto sin ninguna ejecucion gobernada
  detras, y eso es exactamente lo que no debe contar como completada;
- **`estado.json`** es proyeccion (`ADR-0023`), no autoridad.

## La identidad no se inventa

`id_de_tarea(oportunidad)` es `sha256(oportunidad.id)`, determinista. Del contrato sale su
oportunidad, y de la oportunidad su tarea: **la misma cadena que ya usaba el ciclo**, sin identidad
paralela.
"""

import pathlib

import contrato as ct
import control_plane as cp
import descubrimiento as des
import formacion as fm
import planificador as pl

PLANO = pathlib.Path(__file__).parent


def _resultado(d, id_tarea, propuesta, *, efecto=True, sano=True, revertido=False):
    pl.registrar_planificada(d, {"id": id_tarea, "origen": "OP-x", "accion": fm.ACCION,
                                 "fichero": "m.py", "riesgo": "bajo"})
    cp.registrar_evento(d, "cambio_aplicado", {"id": propuesta, "fichero": "m.py", "simbolo": "",
                                               "efecto_verificado": efecto,
                                               "verificacion_sana": sano,
                                               "revertido": revertido, "autoridad": "orquestador"})


# ------------------------------------------------------------------------- fail-closed --

def test_1_sin_ejecucion_no_hay_completada(tmp_path):
    assert pl.completada(tmp_path, "TA-SIN") is False


def test_2_ejecucion_sin_efecto_verificado_no_completa(tmp_path):
    _resultado(tmp_path, "TA-A", "P-A", efecto=False, sano=True, revertido=True)
    assert pl.completada(tmp_path, "TA-A") is False


def test_3_ejecucion_revertida_no_completa(tmp_path):
    _resultado(tmp_path, "TA-B", "P-B", efecto=True, sano=False, revertido=True)
    assert pl.completada(tmp_path, "TA-B") is False


def test_4_efecto_verificado_pero_verificacion_NO_sana_no_completa(tmp_path):
    """Aunque el campo `revertido` dijera lo contrario: **las tres condiciones, no una.**"""
    _resultado(tmp_path, "TA-C", "P-C", efecto=True, sano=False, revertido=False)
    assert pl.completada(tmp_path, "TA-C") is False


def test_5_las_tres_condiciones_juntas_SI_completan(tmp_path):
    _resultado(tmp_path, "TA-D", "P-D", efecto=True, sano=True, revertido=False)
    assert pl.completada(tmp_path, "TA-D") is True


def test_6_evidencia_incompleta_no_completa(tmp_path):
    """Un `cambio_aplicado` sin los campos: la duda nunca concede."""
    pl.registrar_planificada(tmp_path, {"id": "TA-E", "origen": "OP-x", "accion": fm.ACCION,
                                        "fichero": "m.py", "riesgo": "bajo"})
    cp.registrar_evento(tmp_path, "cambio_aplicado", {"id": "P-E", "fichero": "m.py"})
    assert pl.completada(tmp_path, "TA-E") is False


def test_7_un_cambio_MANUAL_del_fichero_no_completa_nada(tmp_path):
    """**El fichero no es evidencia de ejecucion.** Sin historial gobernado detras, no hay completada
    por mucho que el texto coincida."""
    objetivo = tmp_path / "m.py"
    objetivo.write_text("K_ESTANCAMIENTO = 100\n", encoding="utf-8")
    assert pl.completada(tmp_path, "TA-MANUAL") is False


# ---------------------------------------------------- el evaluador y el descubrimiento --

def test_el_evaluador_dice_COMPLETADA_cuando_el_historial_lo_dice(tmp_path):
    _resultado(tmp_path, "TA-F", "P-F", efecto=True, sano=True, revertido=False)
    r = ct.evaluar({"id": "x"}, directorio=tmp_path, tarea="TA-F")
    assert r["estado"] == ct.COMPLETADA


def test_el_evaluador_no_inventa_COMPLETADA_sin_tarea(tmp_path):
    r = ct.evaluar({"id": "x"}, directorio=tmp_path, tarea=None)
    assert r["estado"] == ct.BLOQUEADA


def test_la_capacidad_de_E0_esta_COMPLETADA():
    """El caso real: `P-018` la termino, y el evaluador tiene que decirlo."""
    cap = ct.contrato_de("sexta-fuente-estancamiento")
    assert cap is not None
    assert ct.evaluar(cap, directorio=PLANO,
                      tarea="TA-4c50255a4c70")["estado"] == ct.COMPLETADA


def test_P017_revertido_NO_completaba_y_P018_SI():
    """Los dos intentos del historial real, sin tocarlos."""
    ev = [e["datos"] for e in cp.leer_eventos(PLANO)
          if e["tipo"] == "cambio_aplicado" and e["datos"].get("id") in ("P-017", "P-018")]
    p17 = next(d for d in ev if d["id"] == "P-017")
    p18 = next(d for d in ev if d["id"] == "P-018")
    assert p17["revertido"] is True and p17["verificacion_sana"] is False
    assert p18["revertido"] is False and p18["verificacion_sana"] is True
    assert pl.completada(PLANO, "TA-4c50255a4c70") is True


def test_el_descubrimiento_ya_NO_la_propone_como_trabajo():
    ops = {o.detalle["numero"]: o for o in fm.formacion(PLANO, PLANO)}
    op = ops["sexta-fuente-estancamiento"]
    assert op.estado != des.OPORTUNIDAD_REAL
    assert op.detalle["contrato"] == ct.COMPLETADA


def test_la_cola_esta_vacia_y_sigue_vacia_en_el_siguiente_despertar():
    """Idempotencia: la capacidad completada permanece completada."""
    for _ in range(2):
        assert pl.cola(PLANO, fm.formacion(PLANO, PLANO)) == []


def test_no_se_contaminan_los_sandboxes(tmp_path):
    """La regresion de rutas absolutas no reaparece: un contrato cuyo objetivo vive fuera del arbol
    de trabajo no entra en el descubrimiento de ese arbol."""
    assert [o for o in fm.formacion(tmp_path, tmp_path)
            if o.detalle.get("estado_en_el_plan") == "con contrato"] == []
