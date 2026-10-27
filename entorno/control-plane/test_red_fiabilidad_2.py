"""RED · FIABILIDAD 2 (revision independiente APTO CON CONDICIONES + bateria oficial, 2026-10-26).

* MEDIO-1 · un `cambio_aplicado` RECUPERADO de un diario `via=ciclo` (o sin correlacion) no se atribuye por orden
  a la ultima tarea: el diario guarda `via` y la ausencia explicita de correlacion y `_resolver` la copia.
* MEDIO-2 · `review` manual: los eventos de cierre llevan la MISMA clave que su `tarea_planificada`, y una tarea
  manual no elegible NO lanza `TareaNoElegible` (devuelve un resultado gobernado no ejecutado).
* BAJO-1 · un directorio de anclas existente con permisos laxos no es fiable: no se escribe el ancla.
* IL15 · el orden «ancla antes que eventos» de la verificacion, probado de forma DETERMINISTA.

Todo en `tmp_path`, con historiales SINTETICOS. Cada prueba lleva su caso de control.
"""

from __future__ import annotations

import os
import pathlib

import autoconstruccion as ac
import ciclo_autonomo as ca
import control_plane as cp
import planificador as pl
import pytest
import review as rv
from test_red_correlacion_autoconstruccion import (CANDIDATO, ORIGINAL, TAREA, _cambios, _morir_al, _planificar,
                                                   _promovido_y_muerto, mundo)  # noqa: F401  (fixture `mundo`)

# ========================================================================= MEDIO-1 =====


def _ciclo_muerto_tras_promover(d, objetivo, monkeypatch):
    """`ac.ciclo` autorizado que 'muere' tras promover y antes de registrar `cambio_aplicado`."""
    reponer = _morir_al(monkeypatch, "cambio_aplicado")
    with pytest.raises(SystemExit):
        ac.ciclo(d, [objetivo], autoridad_humana="ceo", acta="acta de prueba 2026-10-26",
                 verificacion=lambda raiz: True)
    reponer()
    assert not _cambios(d), "control: sin constancia"


def test_M1_el_cambio_RECUPERADO_de_una_propuesta_del_ciclo_NO_se_atribuye_a_la_ultima_tarea(mundo, monkeypatch):
    d, objetivo, estado = mundo
    objetivo.write_text("def _muerta():\n    return 1\n", encoding="utf-8")
    _planificar(d, objetivo, "TA-AJENA")                  # la ultima tarea planificada: no es la del ciclo
    _ciclo_muerto_tras_promover(d, objetivo, monkeypatch)
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["recuperado"] is True and cambio["promovido"] is True
    assert cambio["via"] == "ciclo", "el recuperado conserva la via del diario"
    assert pl.resultado_de(d, "TA-AJENA") is None
    assert pl.estado_de(d, "TA-AJENA") != "completada", "un cambio del ciclo no completa una tarea ajena"


def test_M1_un_diario_SIN_correlacion_ni_via_tampoco_se_atribuye_por_orden(mundo, monkeypatch):
    """`ac.proponer` a secas (sin tarea ni via): el recuperado lleva la ausencia EXPLICITA de correlacion."""
    d, objetivo, estado = mundo
    _planificar(d, objetivo, "TA-AJENA")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto", "buscar": "VALOR = 1",
                        "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-10-26")
    reponer = _morir_al(monkeypatch, "cambio_aplicado")
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    reponer()
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["recuperado"] is True and cambio["correlacion"] == "ninguna"
    assert pl.estado_de(d, "TA-AJENA") != "completada"


def test_M1_CONTROL_el_recuperado_de_la_via_review_motor_SI_se_atribuye_a_su_tarea_e_intento(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert (cambio["tarea"], cambio["intento"]) == (TAREA, p["intento"])
    assert "via" not in cambio and "correlacion" not in cambio
    assert pl.estado_de(d, TAREA) == "completada"


def test_M1_CONTROL_un_diario_ANTERIOR_al_contrato_sigue_recuperandose_como_siempre(mundo, monkeypatch):
    """Sin ninguna clave nueva en el diario (anterior al contrato), el recuperado tampoco las inventa."""
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    for ruta in estado.rglob("diario.json"):
        import json
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        for k in ("tarea", "intento", "via", "correlacion"):
            datos.pop(k, None)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert not {"tarea", "intento", "via", "correlacion"} & set(cambio)


def test_M1_el_diario_guarda_via_y_la_ausencia_explicita(mundo, monkeypatch):
    import json
    d, objetivo, estado = mundo
    objetivo.write_text("def _muerta():\n    return 1\n", encoding="utf-8")
    _ciclo_muerto_tras_promover(d, objetivo, monkeypatch)
    (ruta,) = list(estado.rglob("diario.json"))
    diario = json.loads(ruta.read_text(encoding="utf-8"))
    assert diario["via"] == "ciclo" and diario["correlacion"] == "ninguna"


def test_M1_planificador_un_cambio_con_correlacion_ninguna_nunca_se_atribuye_por_orden(tmp_path):
    cp.registrar_evento(tmp_path, "tarea_planificada", {"id": "TA-1", "origen": "t", "accion": "a",
                                                        "fichero": "f", "riesgo": "bajo"})
    cp.registrar_evento(tmp_path, "cambio_aplicado", {
        "id": "P-001", "fichero": "x", "efecto_verificado": True, "verificacion_sana": True,
        "revertido": False, "promovido": True, "correlacion": "ninguna"})
    assert pl.resultado_de(tmp_path, "TA-1") is None and pl.estado_de(tmp_path, "TA-1") != "completada"


def test_M1_planificador_un_cambio_con_via_ciclo_y_SIN_tarea_ni_intento_nunca_se_atribuye_por_orden(tmp_path):
    """El caso exacto del recuperado: `via` presente y NINGUNA de las claves `tarea`/`intento` (mata PL2)."""
    cp.registrar_evento(tmp_path, "tarea_planificada", {"id": "TA-1", "origen": "t", "accion": "a",
                                                        "fichero": "f", "riesgo": "bajo"})
    cp.registrar_evento(tmp_path, "cambio_aplicado", {
        "id": "P-001", "fichero": "x", "efecto_verificado": True, "verificacion_sana": True,
        "revertido": False, "promovido": True, "via": "ciclo"})
    assert pl.resultado_de(tmp_path, "TA-1") is None and pl.estado_de(tmp_path, "TA-1") != "completada"


# ========================================================================= MEDIO-2 =====


def _muerta(d, nombre="m.py"):
    f = d / nombre
    f.write_text("def viva():\n    return 1\n\n\ndef _muerta():\n    return 2\n", encoding="utf-8")
    return f


def _hallazgo(f):
    return {"id": "AUT-001", "accion": "eliminar_codigo_muerto", "fichero": str(f), "simbolo": "_muerta",
            "cambia_alcance": False, "respeta_decisiones": True, "d21_afirmativas": True,
            "materia_reservada": False}


def _habilitar(d):
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2 aprobada", alcance=("eliminar_codigo_muerto",))


def _objetar(monkeypatch):
    monkeypatch.setattr(rv, "aplicar_criterios", lambda tarea, **kw: {"cumple": False, "fallos": ["D22-x"]})


def test_M2_un_hallazgo_OBJETADO_en_vueltas_sucesivas_no_lanza_y_el_ciclo_lo_reporta(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path)
    f = _muerta(d)
    _habilitar(d)
    _objetar(monkeypatch)
    for _ in range(3):
        informe = ca.ciclo_autonomo(d, [f], verificacion=lambda raiz: True)
        assert informe["motivo_de_parada"] != "agente no disponible", informe
    assert not [e for e in cp.leer_eventos(d) if e["tipo"] == "agente_no_disponible"]
    clave = rv.clave_de_tarea_manual(_hallazgo(f))
    assert pl.estado_de(d, clave) == "objetada", "el cierre lleva la MISMA clave que la planificada"


def test_M2_un_hallazgo_reintentado_hasta_AGOTADA_no_rompe_el_ciclo(tmp_path):
    d = pathlib.Path(tmp_path)
    f = _muerta(d)
    _habilitar(d)
    informes = [ca.ciclo_autonomo(d, [f], verificacion=lambda raiz: False) for _ in range(4)]
    assert not [e for e in cp.leer_eventos(d) if e["tipo"] == "agente_no_disponible"]
    assert all(i["motivo_de_parada"] == "verificacion fallida" for i in informes), informes
    assert pl.estado_de(d, rv.clave_de_tarea_manual(_hallazgo(f))) == "agotada"
    assert pl.intentos_de(d, rv.clave_de_tarea_manual(_hallazgo(f))) == pl.TOPE_DE_REINTENTOS


def test_M2_ejecutar_bajo_review_manual_no_elegible_devuelve_resultado_gobernado(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path)
    f = _muerta(d)
    fuente = f.read_text(encoding="utf-8")
    _habilitar(d)
    _objetar(monkeypatch)
    rv.ejecutar_bajo_review(d, _hallazgo(f), propuesto_por="aura", autoridad="orquestador")
    r = rv.ejecutar_bajo_review(d, _hallazgo(f), propuesto_por="aura", autoridad="orquestador")
    assert r["ejecutado"] is False and r["revertido"] is False and r["estado"] == "no_elegible"
    assert r["motivo"] == "objetada" and r["efecto_verificado"] is False
    assert f.read_text(encoding="utf-8") == fuente
    assert len([e for e in cp.leer_eventos(d) if e["tipo"] == "tarea_planificada"]) == 1, "sin planificada nueva"


def test_M2_los_eventos_de_cierre_llevan_la_clave_de_correlacion(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path)
    f = _muerta(d)
    _habilitar(d)
    _objetar(monkeypatch)
    rv.ejecutar_bajo_review(d, _hallazgo(f), propuesto_por="aura", autoridad="orquestador")
    clave = rv.clave_de_tarea_manual(_hallazgo(f))
    (veredicto,) = [e for e in cp.leer_eventos(d) if e["tipo"] == "veredicto_emitido"]
    assert veredicto["datos"]["id"] == clave


def test_M2_CONTROL_la_via_del_motor_conserva_TareaNoElegible_con_intento(tmp_path):
    d = pathlib.Path(tmp_path)
    f = _muerta(d)
    _habilitar(d)
    seq = pl.registrar_planificada(d, {"id": "TA-X", "origen": "t", "accion": "eliminar_codigo_muerto",
                                       "fichero": str(f), "riesgo": "bajo"})["seq"]
    with pytest.raises(pl.TareaNoElegible):
        pl.registrar_planificada(d, {"id": "TA-X", "origen": "t", "accion": "eliminar_codigo_muerto",
                                     "fichero": str(f), "riesgo": "bajo"})
    # con `intento` el review NO planifica: ejecuta bajo ese intento (contrato del motor intacto)
    r = rv.ejecutar_bajo_review(d, {**_hallazgo(f), "id": "TA-X"}, propuesto_por="aura",
                                autoridad="orquestador", verificacion=lambda raiz: True, intento=seq)
    assert r["ejecutado"] is True and "estado" not in r


def test_M2_CONTROL_el_review_manual_elegible_sigue_ejecutando(tmp_path):
    d = pathlib.Path(tmp_path)
    f = _muerta(d)
    _habilitar(d)
    r = rv.ejecutar_bajo_review(d, _hallazgo(f), propuesto_por="aura", autoridad="orquestador",
                                verificacion=lambda raiz: True)
    assert r["ejecutado"] is True and "_muerta" not in f.read_text(encoding="utf-8")


# ========================================================================== BAJO-1 =====


def _evento_cualquiera(d):
    return cp.registrar_evento(d, "hecho", {"i": 1})


def test_B1_un_directorio_de_anclas_con_permisos_LAXOS_no_recibe_el_ancla(tmp_path, monkeypatch):
    base = tmp_path / "anclas"
    base.mkdir()
    os.chmod(base, 0o755)
    monkeypatch.setenv("AURA_ANCLA_DIR", str(base))
    d = tmp_path / "h"
    ev = _evento_cualquiera(d)                           # el escritor NO se bloquea
    assert ev["seq"] == 1 and not list(base.iterdir()), "ni ancla ni temporales en un directorio laxo"
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is False and r["motivo_codigo"] == "dir_ancla_permisos_laxos"
    assert r["ancla"]["presente"] is False


@pytest.mark.parametrize("modo", [0o770, 0o707, 0o750, 0o705])
def test_B1_cualquier_bit_de_grupo_u_otros_es_laxo(tmp_path, monkeypatch, modo):
    base = tmp_path / "anclas"
    base.mkdir()
    os.chmod(base, modo)
    monkeypatch.setenv("AURA_ANCLA_DIR", str(base))
    d = tmp_path / "h"
    _evento_cualquiera(d)
    assert not list(base.iterdir())
    assert cp.verificar_integridad_log(d)["motivo_codigo"] == "dir_ancla_permisos_laxos"


def test_B1_el_escritor_de_bajo_nivel_tambien_se_niega_si_el_directorio_se_aflojo_despues(tmp_path, monkeypatch):
    """Defensa en profundidad: aunque la decision del escritor ya se tomo (directorio 0700 al leer), si se afloja
    antes de escribir, `_escribir_ancla` no escribe. Mata el mutante «se acepta un directorio laxo»."""
    base = tmp_path / "anclas"
    base.mkdir()
    os.chmod(base, 0o700)
    monkeypatch.setenv("AURA_ANCLA_DIR", str(base))
    d = tmp_path / "h"
    ev = _evento_cualquiera(d)
    os.chmod(base, 0o770)
    with pytest.raises(cp.AnclaInconsistente):
        cp._escribir_ancla(d, ev, ev["hash"])
    assert cp._anclar_sin_bloquear(d, ev, ev["hash"], 1) is False, "el escritor no se bloquea: devuelve False"
    assert [p.name for p in base.iterdir()] == [cp.ruta_ancla(d).name], "el ancla anterior queda intacta"
    os.chmod(base, 0o700)
    cp._escribir_ancla(d, ev, ev["hash"])                 # CONTROL: con 0700 si escribe


def test_B1_CONTROL_un_directorio_existente_0700_funciona(tmp_path, monkeypatch):
    base = tmp_path / "anclas"
    base.mkdir()
    os.chmod(base, 0o700)
    monkeypatch.setenv("AURA_ANCLA_DIR", str(base))
    d = tmp_path / "h"
    _evento_cualquiera(d)
    assert cp.ruta_ancla(d).is_file()
    r = cp.verificar_integridad_log(d)
    assert r["integro"] is True and r["completitud"] == "demostrada"


# ============================================================================ IL15 =====


def _log_con_n(tmp_path, n=3):
    d = pathlib.Path(tmp_path) / "hist"
    for i in range(n):
        cp.registrar_evento(d, "hecho", {"i": i})
    return d


def _escritura_tras_leer_eventos(monkeypatch, d):
    """Inyecta, UNA vez, un evento justo despues de que la verificacion lea los eventos."""
    real = cp._leer_con_cola
    estado = {"hecho": False}

    def leer(directorio):
        resultado = real(directorio)
        if not estado["hecho"] and pathlib.Path(directorio) == d:
            estado["hecho"] = True
            cp.registrar_evento(d, "hecho", {"inyectado": True})
        return resultado

    monkeypatch.setattr(cp, "_leer_con_cola", leer)
    return estado


def test_IL15_una_escritura_entre_la_lectura_de_eventos_y_la_del_ancla_NO_da_falso_truncamiento(tmp_path,
                                                                                               monkeypatch):
    d = _log_con_n(tmp_path)
    estado = _escritura_tras_leer_eventos(monkeypatch, d)
    r = cp.verificar_integridad_log(d)
    assert estado["hecho"] is True, "control: la escritura se inyecto"
    assert r["integro"] is True and r["completitud"] == "demostrada", r
    assert r["eventos"] == 3 and r["ancla"]["seq"] == 3, "el ancla leida es la ANTERIOR a la escritura"


def test_IL15_CONTROL_leer_el_ancla_DESPUES_de_los_eventos_SI_produce_el_falso_truncamiento(tmp_path, monkeypatch):
    """Reproduce el orden defectuoso a mano: demuestra que la inyeccion basta para provocarlo."""
    d = _log_con_n(tmp_path)
    estado = _escritura_tras_leer_eventos(monkeypatch, d)
    eventos, _ = cp._leer_con_cola(d)                     # primero los eventos (y la escritura inyectada)
    estado_ancla, ancla = cp._leer_ancla(d)               # despues el ancla
    assert estado["hecho"] is True
    assert cp._diagnosticar(d, eventos, estado_ancla, ancla)["completitud"] == cp.COMPLETITUD_TRUNCADA
