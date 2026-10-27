"""RED · DP-AUTOCONSTRUCCION-CORRELACION-Y-RECUPERACION (D1, D2, D3), §2, §11-§13.

* D1 · cada `cambio_aplicado` de la via review/motor lleva `tarea` e `intento` (el `seq` de su
  `tarea_planificada`); el planificador atribuye por esa clave y solo por orden en eventos anteriores.
* D2 · el diario `promovido` guarda la verificacion REAL; `_resolver` la copia (`recuperado: true`); sin
  campos, `verificacion_no_registrada` y la tarea queda `resultado_ambiguo`.
* D3 · el `P-NNN` se calcula y se anade bajo un unico cerrojo.

Todo en `tmp_path`, con historiales SINTETICOS. Cada prueba lleva su caso de control.
"""

from __future__ import annotations

import json
import multiprocessing
import pathlib
import time

import autoconstruccion as ac
import control_plane as cp
import planificador as pl
import pytest
import review as rv

ORIGINAL = "VALOR = 1\n"
CANDIDATO = "VALOR = 2\n"
TAREA = "TA-0123456789ab"


# ------------------------------------------------------------------------------ montaje --


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "s.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    return d, objetivo, tmp_path / "estado"


def _planificar(d, objetivo, id_tarea=TAREA) -> int:
    return pl.registrar_planificada(d, {"id": id_tarea, "origen": "prueba", "accion": "sustituir_texto",
                                        "fichero": str(objetivo), "riesgo": "bajo"})["seq"]


def _propuesta(d, objetivo, id_tarea=TAREA, intento=None, **extra):
    intento = intento if intento is not None else _planificar(d, objetivo, id_tarea)
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto", "buscar": "VALOR = 1",
                        "sustituir": "VALOR = 2", "motivo": "incremento"}, tarea=id_tarea, intento=intento,
                    **extra)
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-10-26")
    return p


def _cambios(d) -> list[dict]:
    return [e["datos"] for e in cp.leer_eventos(d) if e["tipo"] == "cambio_aplicado"]


def _diarios(estado) -> list[pathlib.Path]:
    return sorted(estado.rglob("diario.json")) if estado.exists() else []


def _morir_al(monkeypatch, tipo: str):
    """Simula la muerte (SystemExit, que `_promover` no captura) justo al escribir `tipo`."""
    real = cp.registrar_evento

    def con_muerte(directorio, t, datos=None):
        if t == tipo:
            raise SystemExit(9)
        return real(directorio, t, datos)

    monkeypatch.setattr(cp, "registrar_evento", con_muerte)
    return lambda: monkeypatch.setattr(cp, "registrar_evento", real)


def _promovido_y_muerto(mundo, monkeypatch, verificacion=lambda raiz: True):
    """Promueve el cambio y 'muere' antes de registrar `cambio_aplicado`. Devuelve (d, objetivo, estado, p)."""
    d, objetivo, estado = mundo
    p = _propuesta(d, objetivo)
    reponer = _morir_al(monkeypatch, "cambio_aplicado")
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=verificacion)
    reponer()
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO, "control: la promocion SI llego al disco"
    assert not _cambios(d), "control: sin constancia"
    return d, objetivo, estado, p


def _en_ejecutor_muerto(monkeypatch):
    monkeypatch.setattr(pl, "_ejecutor_vivo", lambda ejecutor: False)


# ============================================================================== D1 =====


def test_D1_cada_cambio_aplicado_lleva_tarea_e_intento_y_coinciden_con_su_planificada(mundo):
    d, objetivo, _ = mundo
    seq = _planificar(d, objetivo)
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto", "buscar": "VALOR = 1",
                        "sustituir": "VALOR = 2", "motivo": "m"}, tarea=TAREA, intento=seq)
    ac.autorizar(d, p["id"], por="ceo", acta="acta 2026")
    registrada = [e for e in cp.leer_eventos(d) if e["tipo"] == "propuesta_registrada"][0]["datos"]
    assert (registrada["tarea"], registrada["intento"]) == (TAREA, seq)
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    (cambio,) = _cambios(d)
    assert (cambio["tarea"], cambio["intento"]) == (TAREA, seq)
    planificada = [e for e in cp.leer_eventos(d) if e["tipo"] == "tarea_planificada"][0]
    assert planificada["seq"] == cambio["intento"] and planificada["datos"]["id"] == cambio["tarea"]


def test_D1_CONTROL_una_propuesta_sin_correlacion_no_inventa_tarea_ni_intento(mundo):
    d, objetivo, _ = mundo
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto", "buscar": "VALOR = 1",
                        "sustituir": "VALOR = 2", "motivo": "m"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta 2026")
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    (cambio,) = _cambios(d)
    assert "tarea" not in cambio and "intento" not in cambio and "via" not in cambio


def test_D1_tambien_el_cambio_RECHAZADO_lleva_la_correlacion(mundo):
    d, objetivo, _ = mundo
    p = _propuesta(d, objetivo)
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: False)
    (cambio,) = _cambios(d)
    assert cambio["revertido"] is True and cambio["tarea"] == TAREA and cambio["intento"] == p["intento"]


def test_D1_el_diario_lleva_tarea_e_intento(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    (diario,) = [json.loads(r.read_text(encoding="utf-8")) for r in _diarios(estado)]
    assert (diario["tarea"], diario["intento"]) == (TAREA, p["intento"])


@pytest.mark.parametrize("tarea,intento", [(TAREA, None), (None, 3), (TAREA, True), (TAREA, 0), (TAREA, "3"),
                                           ("", 3), (7, 3)])
def test_D1_proponer_rechaza_una_correlacion_mal_formada(mundo, tarea, intento):
    d, objetivo, _ = mundo
    with pytest.raises(ValueError):
        ac.proponer(d, {"fichero": str(objetivo)}, tarea=tarea, intento=intento)
    assert not [e for e in cp.leer_eventos(d) if e["tipo"] == "propuesta_registrada"]


def test_D1_ciclo_marca_via_ciclo_y_no_se_atribuye_a_ninguna_tarea(mundo):
    d, objetivo, _ = mundo
    objetivo.write_text("def _muerta():\n    return 1\n", encoding="utf-8")
    informe = ac.ciclo(d, [objetivo], autoridad_humana=None, acta="")
    assert informe["propuestos"] >= 1
    registrada = [e for e in cp.leer_eventos(d) if e["tipo"] == "propuesta_registrada"][0]["datos"]
    assert registrada["via"] == "ciclo" and registrada["tarea"] is None and registrada["intento"] is None


def _evento_cambio(d, **datos):
    base = {"id": "P-001", "fichero": "x", "efecto_verificado": True, "verificacion_sana": True,
            "revertido": False, "promovido": True}
    cp.registrar_evento(d, "cambio_aplicado", {**base, **datos})


def _planificada_sintetica(d, id_tarea) -> int:
    return cp.registrar_evento(d, "tarea_planificada", {"id": id_tarea, "origen": "t", "accion": "a",
                                                        "fichero": "f", "riesgo": "bajo"})["seq"]


def test_D1_un_evento_via_ciclo_NUNCA_se_atribuye_ni_por_orden(tmp_path):
    _planificada_sintetica(tmp_path, "TA-1")
    _evento_cambio(tmp_path, via="ciclo", tarea=None, intento=None)
    assert pl.resultado_de(tmp_path, "TA-1") is None and pl.estado_de(tmp_path, "TA-1") != "completada"


def test_D1_CONTROL_el_mismo_evento_sin_via_ni_correlacion_SI_se_atribuye_por_orden(tmp_path):
    _planificada_sintetica(tmp_path, "TA-1")
    _evento_cambio(tmp_path)
    assert pl.estado_de(tmp_path, "TA-1") == "completada"


def test_D1_R2_dos_tareas_intercaladas_cada_resultado_a_su_tarea(tmp_path):
    """El segundo escribe su `tarea_planificada` JUSTO despues de la propuesta del primero: por orden, el
    resultado de A se lo llevaria B."""
    a = _planificada_sintetica(tmp_path, "TA-A")
    cp.registrar_evento(tmp_path, "propuesta_registrada", {"id": "P-001", "tarea": "TA-A", "intento": a})
    b = _planificada_sintetica(tmp_path, "TA-B")
    _evento_cambio(tmp_path, id="P-001", tarea="TA-A", intento=a)
    assert pl.estado_de(tmp_path, "TA-A") == "completada"
    assert pl.resultado_de(tmp_path, "TA-B") is None and pl.estado_de(tmp_path, "TA-B") != "completada"
    assert pl.resultado_de(tmp_path, "TA-A")["intento"] == a and b > a


def test_D1_R2_CONTROL_sin_correlacion_el_orden_da_el_resultado_a_la_tarea_equivocada(tmp_path):
    _planificada_sintetica(tmp_path, "TA-A")
    _planificada_sintetica(tmp_path, "TA-B")
    _evento_cambio(tmp_path, id="P-001")
    assert pl.estado_de(tmp_path, "TA-B") == "completada", "el defecto que D1 evita"
    assert pl.estado_de(tmp_path, "TA-A") != "completada"


def test_D1_un_intento_que_no_es_de_esa_tarea_no_se_atribuye(tmp_path):
    a = _planificada_sintetica(tmp_path, "TA-A")
    _evento_cambio(tmp_path, tarea="TA-A", intento=a + 99)           # no es ningun seq planificado
    _evento_cambio(tmp_path, tarea="TA-OTRA", intento=a)             # otra tarea
    _evento_cambio(tmp_path, tarea="TA-A", intento=True)             # booleano, no entero
    assert pl.resultado_de(tmp_path, "TA-A") is None and pl.estado_de(tmp_path, "TA-A") != "completada"


def test_D1_resultado_de_usa_el_ULTIMO_intento_y_completada_sigue_siendo_monotona(tmp_path):
    a1 = _planificada_sintetica(tmp_path, "TA-A")
    _evento_cambio(tmp_path, tarea="TA-A", intento=a1, efecto_verificado=False, verificacion_sana=False,
                   revertido=True, promovido=False)
    a2 = _planificada_sintetica(tmp_path, "TA-A")
    assert pl.resultado_de(tmp_path, "TA-A") is None, "el intento nuevo no hereda el resultado del anterior"
    _evento_cambio(tmp_path, tarea="TA-A", intento=a2)
    assert pl.resultado_de(tmp_path, "TA-A")["intento"] == a2 and pl.estado_de(tmp_path, "TA-A") == "completada"


# --------------------------------------------------------------- review manual (C3) y motor --


def _habilitar_review(d):
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2 aprobada", alcance=("eliminar_codigo_muerto",))


def _tarea_manual(objetivo, id_tarea="T-M1"):
    return {"id": id_tarea, "accion": "eliminar_codigo_muerto", "fichero": str(objetivo), "simbolo": "_muerta",
            "cambia_alcance": False, "respeta_decisiones": True, "d21_afirmativas": True,
            "materia_reservada": False}


def test_C3_un_review_manual_registra_su_propia_tarea_planificada_y_correlaciona(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "m.py"
    objetivo.write_text("def viva():\n    return 1\n\n\ndef _muerta():\n    return 2\n", encoding="utf-8")
    _habilitar_review(d)
    r = rv.ejecutar_bajo_review(d, _tarea_manual(objetivo), propuesto_por="aura", autoridad="orquestador",
                                verificacion=lambda raiz: True)
    assert r["ejecutado"] is True
    planificadas = [e for e in cp.leer_eventos(d) if e["tipo"] == "tarea_planificada"]
    assert len(planificadas) == 1 and "ejecutor" in planificadas[0]["datos"]
    (cambio,) = _cambios(d)
    assert (cambio["tarea"], cambio["intento"]) == ("T-M1", planificadas[0]["seq"])
    assert pl.estado_de(d, "T-M1") == "completada"


def test_C3_una_tarea_NO_elegible_se_rechaza_sin_propuesta_ni_efecto(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "m.py"
    fuente = "def _muerta():\n    return 2\n"
    objetivo.write_text(fuente, encoding="utf-8")
    _habilitar_review(d)
    _planificada_sintetica_viva = pl.registrar_planificada(
        d, {"id": "T-M1", "origen": "t", "accion": "eliminar_codigo_muerto", "fichero": str(objetivo),
            "riesgo": "bajo"})
    assert _planificada_sintetica_viva["seq"]
    with pytest.raises(pl.TareaNoElegible):
        rv.ejecutar_bajo_review(d, _tarea_manual(objetivo), propuesto_por="aura", autoridad="orquestador",
                                verificacion=lambda raiz: True)
    assert objetivo.read_text(encoding="utf-8") == fuente
    assert not [e for e in cp.leer_eventos(d) if e["tipo"] in ("propuesta_registrada", "veredicto_emitido")]


@pytest.mark.parametrize("quitar", ["id", "fichero"])
def test_C3_una_tarea_incompleta_es_un_error_explicito_sin_efecto_parcial(tmp_path, quitar):
    d = pathlib.Path(tmp_path)
    objetivo = d / "m.py"
    objetivo.write_text("def _muerta():\n    return 2\n", encoding="utf-8")
    _habilitar_review(d)
    tarea = _tarea_manual(objetivo)
    del tarea[quitar]
    with pytest.raises((ValueError, KeyError, ac.ZonaProhibida)):
        rv.ejecutar_bajo_review(d, tarea, propuesto_por="aura", autoridad="orquestador",
                                verificacion=lambda raiz: True)
    assert not [e for e in cp.leer_eventos(d) if e["tipo"] in ("tarea_planificada", "propuesta_registrada")]


def test_D1_el_motor_transporta_el_seq_de_la_planificada_a_la_ejecucion(tmp_path):
    import motor_autonomia as motor
    from test_red_motor_autonomia import _con_review, _plano_con_codigo_muerto
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda raiz: True, max_tareas=2)
    assert informe["ejecutadas"] == 2
    planificadas = {e["seq"]: e["datos"]["id"] for e in cp.leer_eventos(tmp_path)
                    if e["tipo"] == "tarea_planificada"}
    cambios = _cambios(tmp_path)
    assert len(cambios) == 2 and len(planificadas) == 2
    for c in cambios:
        assert planificadas[c["intento"]] == c["tarea"], "el intento ES el seq de su tarea_planificada"
    assert len([e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "tarea_planificada"]) == 2, \
        "el motor no registra una segunda planificada por el review"


# ============================================================================== D2 =====


def test_D2_SIGKILL_entre_promover_y_registrar_la_tarea_queda_COMPLETADA_con_verificacion_copiada(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["recuperado"] is True and cambio["promovido"] is True and cambio["revertido"] is False
    assert cambio["efecto_verificado"] is True and cambio["verificacion_sana"] is True
    assert cambio["verificacion_aislada"] is True and cambio["ejecucion_confinada"] is False
    assert (cambio["tarea"], cambio["intento"]) == (TAREA, p["intento"])
    assert pl.estado_de(d, TAREA) == "completada" and pl.intentos_de(d, TAREA) == 1
    assert not _diarios(estado)


def test_D2_C1_los_valores_reales_aislada_y_confinada_se_copian_NO_se_fijan_a_true(mundo, monkeypatch):
    sano_sin_aislar = lambda raiz: ac.ResultadoVerificacion("sano", False, False, "")      # noqa: E731
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch, verificacion=sano_sin_aislar)
    (diario,) = [json.loads(r.read_text(encoding="utf-8")) for r in _diarios(estado)]
    assert diario["verificacion_aislada"] is False and diario["ejecucion_confinada"] is False
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["verificacion_aislada"] is False and cambio["ejecucion_confinada"] is False


def test_D2_C1_CONTROL_con_valores_verdaderos_se_copian_verdaderos(mundo, monkeypatch):
    todo = lambda raiz: ac.ResultadoVerificacion("sano", True, True, "")                   # noqa: E731
    d, *_ = _promovido_y_muerto(mundo, monkeypatch, verificacion=todo)
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["verificacion_aislada"] is True and cambio["ejecucion_confinada"] is True


def _editar_diario(estado, **cambios):
    (ruta,) = _diarios(estado)
    diario = json.loads(ruta.read_text(encoding="utf-8"))
    for k, v in cambios.items():
        if v is _QUITAR:
            diario.pop(k, None)
        else:
            diario[k] = v
    ruta.write_text(json.dumps(diario), encoding="utf-8")


_QUITAR = object()
_CAMPOS_VERIFICACION = ("efecto_verificado", "verificacion_sana", "verificacion_aislada", "ejecucion_confinada")


def test_D2_un_diario_ANTERIOR_sin_verificacion_publica_verificacion_no_registrada_y_queda_AMBIGUO(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    _editar_diario(estado, **{k: _QUITAR for k in _CAMPOS_VERIFICACION})
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["verificacion_no_registrada"] is True and cambio["recuperado"] is True
    assert not ({"efecto_verificado", "verificacion_sana"} & set(cambio)), "no se fabrica verificacion"
    _en_ejecutor_muerto(monkeypatch)
    assert pl.estado_de(d, TAREA) == "resultado_ambiguo" and pl.elegible(d, TAREA) is False


@pytest.mark.parametrize("campo,valor", [("efecto_verificado", 1), ("efecto_verificado", "true"),
                                         ("verificacion_sana", "True"), ("verificacion_sana", False),
                                         ("verificacion_aislada", "si"), ("verificacion_aislada", 1),
                                         ("ejecucion_confinada", None), ("ejecucion_confinada", 0)])
def test_D2_un_campo_presente_pero_mal_tipado_se_trata_como_ausente(mundo, monkeypatch, campo, valor):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    _editar_diario(estado, **{campo: valor})
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert cambio["verificacion_no_registrada"] is True and "efecto_verificado" not in cambio
    assert pl.estado_de(d, TAREA) != "completada"


@pytest.mark.parametrize("tarea,intento", [(TAREA, True), (TAREA, "5"), (None, 5), (TAREA, 0), (3, 5)])
def test_D2_una_correlacion_del_diario_mal_formada_se_trata_como_ausente(mundo, monkeypatch, tarea, intento):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    _editar_diario(estado, tarea=tarea, intento=intento)
    ac.recuperar(d)
    (cambio,) = _cambios(d)
    assert "tarea" not in cambio and "intento" not in cambio


def test_D2_recuperar_tres_veces_deja_un_solo_cambio_y_una_sola_recuperacion(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    for _ in range(3):
        ac.recuperar(d)
    assert len(_cambios(d)) == 1
    assert len([e for e in cp.leer_eventos(d) if e["tipo"] == "recuperacion_al_arranque"]) == 1


def test_D2_I2_si_el_cambio_ya_constaba_por_tarea_e_intento_no_se_duplica(mundo, monkeypatch):
    """Muerte despues de registrar el cambio y antes de cerrar el diario: la clave es `(tarea, intento)`."""
    d, objetivo, estado = mundo
    p = _propuesta(d, objetivo)
    real = ac.shutil.rmtree

    def rmtree_con_muerte(ruta, *a, **k):
        if "aura-autoconstruccion" in str(ruta):
            raise SystemExit(9)
        return real(ruta, *a, **k)

    monkeypatch.setattr(ac.shutil, "rmtree", rmtree_con_muerte)
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    monkeypatch.setattr(ac.shutil, "rmtree", real)
    assert len(_cambios(d)) == 1 and len(_diarios(estado)) == 1
    ac.recuperar(d)
    assert len(_cambios(d)) == 1 and not _diarios(estado)
    assert pl.estado_de(d, TAREA) == "completada"


def test_D2_I2_la_clave_es_la_correlacion_aunque_cambie_el_id_de_propuesta(mundo, monkeypatch):
    """CONTROL de la clave: un cambio del mismo `(tarea, intento)` con OTRO id de propuesta tambien cuenta."""
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    _evento_cambio(d, id="P-999", tarea=TAREA, intento=p["intento"])
    ac.recuperar(d)
    assert len(_cambios(d)) == 1


def test_D2_muerte_DURANTE_la_recuperacion_la_siguiente_termina_sin_duplicar(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    reponer = _morir_al(monkeypatch, "recuperacion_al_arranque")
    with pytest.raises(SystemExit):
        ac.recuperar(d)
    reponer()
    assert len(_cambios(d)) == 1 and len(_diarios(estado)) == 1, "el diario sigue hasta registrar la recuperacion"
    ac.recuperar(d)
    assert len(_cambios(d)) == 1 and not _diarios(estado)
    assert len([e for e in cp.leer_eventos(d) if e["tipo"] == "recuperacion_al_arranque"]) == 1


def test_D2_R3_dos_recuperar_sobre_el_mismo_diario_el_segundo_devuelve_OCUPADO(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    ruta_estado = ac._dir_estado(d)
    with ac._cerrojo(ruta_estado, bloqueante=False) as tomado:       # el primero esta recuperando
        assert tomado
        segundo = ac.recuperar(d)
    assert segundo["ocupado"] is True and segundo["escribio"] is False
    assert not _cambios(d), "el segundo no toco el diario ajeno"
    primero = ac.recuperar(d)
    assert primero["ocupado"] is False and len(_cambios(d)) == 1


# --- los cuatro estados del §13.1 se observan ---


def test_D2_los_cuatro_estados_de_la_seccion_13_se_observan(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    # 1. promocion realizada + verificacion pendiente de registrar: diario `promovido` con verificacion real.
    (diario,) = [json.loads(r.read_text(encoding="utf-8")) for r in _diarios(estado)]
    assert diario["estado"] == "promovido" and all(k in diario for k in _CAMPOS_VERIFICACION)
    # 2. verificacion confirmada: recuperar -> completada.
    ac.recuperar(d)
    assert pl.estado_de(d, TAREA) == "completada"


def test_D2_estado_verificacion_pendiente_diario_PREPARADO_se_restaura_y_es_reintentable(mundo, monkeypatch):
    d, objetivo, estado = mundo
    p = _propuesta(d, objetivo)

    real = ac._escribir_atomico

    def muere(destino, *a, **k):
        if pathlib.Path(destino) == objetivo.resolve():
            raise SystemExit(9)
        return real(destino, *a, **k)

    monkeypatch.setattr(ac, "_escribir_atomico", muere)              # muere al escribir el candidato en el vivo
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    monkeypatch.undo()
    (diario,) = [json.loads(r.read_text(encoding="utf-8")) for r in _diarios(estado)]
    assert diario["estado"] == "preparado" and "efecto_verificado" not in diario
    ac.recuperar(d)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL and not _cambios(d)
    monkeypatch.setattr(pl, "_ejecutor_vivo", lambda ejecutor: False)
    assert pl.estado_de(d, TAREA) == "interrumpida_reintentable"


def test_D2_estado_resultado_ambiguo_un_diario_invalido_BLOQUEA_y_nunca_completa(mundo, monkeypatch):
    d, objetivo, estado, p = _promovido_y_muerto(mundo, monkeypatch)
    _editar_diario(estado, sha_candidato="no-es-un-sha")
    informe = ac.recuperar(d)
    assert informe["bloqueado"] is True and not _cambios(d)
    assert pl.estado_de(d, TAREA) != "completada"


# ============================================================================== D3 =====


def _proponer_en_proceso(directorio, pausa, retraso, cola):
    """Proceso hijo: pausa inyectada ENTRE leer el log y anadir (tras `leer_eventos`)."""
    time.sleep(retraso)
    original = cp.leer_eventos

    def lento(d):
        resultado = original(d)
        time.sleep(pausa)
        return resultado

    cp.leer_eventos = lento
    p = ac.proponer(pathlib.Path(directorio), {"fichero": "f.py", "simbolo": "_s", "motivo": "m"})
    cola.put(p["id"])


def _proponer_SIN_cerrojo_en_proceso(directorio, pausa, retraso, cola):
    """El defecto original (calculo fuera del cerrojo), con la MISMA pausa: el control de R1."""
    time.sleep(retraso)
    directorio = pathlib.Path(directorio)
    existentes = [e for e in cp.leer_eventos(directorio) if e["tipo"] == "propuesta_registrada"]
    time.sleep(pausa)
    identificador = f"P-{len(existentes) + 1:03d}"
    cp.registrar_evento(directorio, "propuesta_registrada", {"id": identificador})
    cola.put(identificador)


def _dos_procesos(objetivo, tmp_path):
    ctx = multiprocessing.get_context("fork")
    cola = ctx.Queue()
    procesos = [ctx.Process(target=objetivo, args=(str(tmp_path / "hist"), 0.8, retraso, cola))
                for retraso in (0.0, 0.25)]
    for p in procesos:
        p.start()
    for p in procesos:
        p.join(60)
        assert p.exitcode == 0
    return sorted(cola.get(timeout=5) for _ in procesos)


def test_D3_R1_dos_proponer_concurrentes_con_pausa_inyectada_obtienen_ids_DISTINTOS(tmp_path):
    ids = _dos_procesos(_proponer_en_proceso, tmp_path)
    assert ids == ["P-001", "P-002"]
    d = tmp_path / "hist"
    assert cp.verificar_integridad_log(d)["integro"] is True
    assert [e["datos"]["id"] for e in cp.leer_eventos(d)] == ["P-001", "P-002"]


def test_D3_R1_CONTROL_con_el_calculo_FUERA_del_cerrojo_colisionan_siempre(tmp_path):
    ids = _dos_procesos(_proponer_SIN_cerrojo_en_proceso, tmp_path)
    assert ids == ["P-001", "P-001"], "el guion discrimina: sin cerrojo el mismo id sale dos veces"


def test_D3_registrar_evento_si_deriva_los_datos_bajo_el_cerrojo_y_solo_si_la_condicion_se_cumple(tmp_path):
    llamadas = []

    def derivar():
        llamadas.append(1)
        return {"n": len(cp.leer_eventos(tmp_path))}

    assert cp.registrar_evento_si(tmp_path, "x", None, lambda: False, derivar=derivar) is None
    assert llamadas == []
    evento = cp.registrar_evento_si(tmp_path, "x", {"ignorado": True}, lambda: True, derivar=derivar)
    assert evento["datos"] == {"n": 0} and llamadas == [1]


def test_D3_registrar_evento_si_con_derivar_NIEGA_los_eventos_gobernados_antes_de_derivar(tmp_path):
    llamadas = []
    with pytest.raises(cp.EventoNoGobernado):
        cp.registrar_evento_si(tmp_path, "estado_de_tarea", None, lambda: True,
                               derivar=lambda: llamadas.append(1) or {})
    assert llamadas == [] and not cp.leer_eventos(tmp_path)


def test_D3_proponer_pasa_por_el_mismo_mecanismo_del_ancla(tmp_path):
    d = tmp_path / "h"
    ac.proponer(d, {"fichero": "f.py", "simbolo": "_s", "motivo": "m"})
    assert cp.verificar_integridad_log(d)["ancla"]["seq"] == 1
