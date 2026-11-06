"""Reloj de CM2 — funciones puras: poblacion, calendario, sonda, tasa e informe.

Resolucion S3 §2.1 (CEO, 2026-10-06). Sin disco: los eventos se construyen a mano con el mismo
formato que deja `obs.log(..., audit=True)` (campos estructurados + `seq`).
"""

from __future__ import annotations

import random

import pytest

from aura_skeleton.core import reloj_cm2 as r
from aura_skeleton.core.orchestrator import Orchestrator

DIA = 86400.0
T0 = 1_700_000_000.0
H = "a" * 32
H2 = "b" * 32


def reg(seq, hid=H, version=1, vf=T0):
    return {"seq": seq, "evento": "cm2.hecho_registrado", "hecho_id": hid, "version": version, "valid_from": vf}


def ini(ts=T0, seq=0):
    """El evento `cm2.inicio` tal como lo deja `obs.log(..., audit=True)` (con `ts` y `seq`)."""
    return {"seq": seq, "evento": "cm2.inicio", "ts": ts}


def ret(seq, hid=H, causa="olvido"):
    return {"seq": seq, "evento": "cm2.hecho_retirado", "hecho_id": hid, "causa": causa}


def sonda(seq, hid=H, dia=28, resultado="vigente", estado="ninguna", edad=None, vedad=None):
    return {
        "seq": seq,
        "evento": "cm2.sonda",
        "hecho_id": hid,
        "dia": dia,
        "edad_dias": float(dia) if edad is None else edad,
        "version_edad_dias": float(dia) if vedad is None else vedad,
        "estado_retirada": estado,
        "resultado": resultado,
        "n_entradas_memoria": 3,
    }


def entrada(contenido, hid=H, version=1, valid_until=None, refutada=False, user="u", clase="hecho_declarado"):
    return {
        "user_id": user,
        "hecho_id": hid,
        "contenido": contenido,
        "clase": clase,
        "version": version,
        "valid_until": valid_until,
        "refutada": refutada,
    }


# ============================================================ poblacion ==


def test_la_poblacion_se_ordena_por_seq_aunque_lleguen_desordenados():
    evs = [reg(5, version=2, vf=T0 + 10 * DIA), reg(1, version=1, vf=T0), ret(3), reg(2, hid=H2, vf=T0 + DIA)]
    random.Random(7).shuffle(evs)
    pob = r.reconstruir_poblacion(evs)
    assert set(pob) == {H, H2}
    assert pob[H].origen == T0 and pob[H].version == 2 and pob[H].valid_from_actual == T0 + 10 * DIA
    # la retirada (seq 3) es ANTERIOR a la ultima declaracion (seq 5): el hecho esta de nuevo en pie
    assert pob[H].causa_retirada is None


def test_la_retirada_posterior_a_la_ultima_declaracion_marca_la_causa():
    pob = r.reconstruir_poblacion([reg(1), ret(2, causa="refutacion")])
    assert pob[H].causa_retirada == "refutacion"


def test_eventos_duplicados_no_duplican():
    evs = [reg(1), reg(1), reg(2, version=1, vf=T0), ret(3), ret(3)]
    pob = r.reconstruir_poblacion(evs)
    assert len(pob) == 1 and pob[H].version == 1


@pytest.mark.parametrize(
    "malo",
    [
        {"seq": 1, "evento": "cm2.hecho_registrado", "version": 1, "valid_from": T0},  # sin hecho_id
        {"seq": 1, "evento": "cm2.hecho_registrado", "hecho_id": H, "version": 1},  # sin valid_from
        {"seq": 1, "evento": "cm2.hecho_registrado", "hecho_id": H, "version": 1, "valid_from": "ayer"},
        {"seq": 1, "evento": "cm2.hecho_registrado", "hecho_id": "", "version": 1, "valid_from": T0},
        {"evento": "cm2.hecho_registrado", "hecho_id": H, "version": 1, "valid_from": T0},  # sin seq
        {"seq": 1, "evento": "cm2.hecho_retirado", "hecho_id": H},  # retirada sin causa
        {"seq": 1, "msg": "otra cosa"},
    ],
)
def test_eventos_incompletos_se_ignoran_sin_reventar(malo):
    assert r.reconstruir_poblacion([malo]) == {}
    assert r.sondas_pendientes([ini(), malo], T0 + 100 * DIA) == []


# =========================================================== calendario ==


@pytest.mark.parametrize(
    "dias,esperado",
    [(6.99, []), (7.0, [7]), (13.9, [7]), (14.0, [7, 14]), (27.99, [7, 14]), (28.0, [7, 14, 28]), (400, [7, 14, 28])],
)
def test_calendario_7_14_28_desde_valid_from_de_la_primera_version(dias, esperado):
    pend = r.sondas_pendientes([ini(), reg(1)], T0 + dias * DIA)
    assert [d for _h, d in pend] == esperado


def test_redeclarar_no_reinicia_la_fecha_de_origen():
    # v2 declarada el dia 20: a los 28 dias del ORIGEN (no de la v2) toca la sonda de 28.
    evs = [ini(), reg(1), reg(2, version=2, vf=T0 + 20 * DIA)]
    assert [d for _h, d in r.sondas_pendientes(evs, T0 + 28 * DIA)] == [7, 14, 28]
    # y `version_edad_dias` si refleja la version vigente
    (hecho, _), *_ = r.sondas_pendientes(evs, T0 + 28 * DIA)
    ev = r.evento_sonda(
        hecho, 28, T0 + 28 * DIA, {"resultado": "vigente", "estado_retirada": "ninguna", "n_entradas_memoria": 2}
    )
    assert ev["edad_dias"] == 28.0 and ev["version_edad_dias"] == 8.0


def test_la_version_1_gana_como_origen_aunque_su_evento_llegue_despues():
    evs = [reg(1, version=2, vf=T0 + 5 * DIA), reg(2, version=1, vf=T0)]
    assert r.reconstruir_poblacion(evs)[H].origen == T0


# ========================================================== idempotencia ==


def test_una_sonda_ya_hecha_no_se_repite_y_las_duplicadas_tampoco():
    evs = [ini(), reg(1), sonda(2, dia=7), sonda(3, dia=7), sonda(4, dia=14)]
    assert [d for _h, d in r.sondas_pendientes(evs, T0 + 30 * DIA)] == [28]
    # releer dos veces el mismo historial da lo mismo
    assert r.sondas_pendientes(evs, T0 + 30 * DIA) == r.sondas_pendientes(list(evs), T0 + 30 * DIA)


def test_las_sondas_hechas_de_otro_hecho_no_cuentan():
    evs = [ini(), reg(1), reg(2, hid=H2), sonda(3, hid=H2, dia=7)]
    pend = [(h.hecho_id, d) for h, d in r.sondas_pendientes(evs, T0 + 8 * DIA)]
    assert pend == [(H, 7)]


# ================================================= el tiempo anterior al inicio no cuenta ==


def test_sin_inicio_no_hay_calendario_aunque_el_hecho_tenga_400_dias():
    assert r.sondas_pendientes([reg(1)], T0 + 400 * DIA) == []


@pytest.mark.parametrize("dias,esperado", [(6.99, []), (7.0, [7]), (13.9, [7]), (14.0, [7, 14]), (28.0, [7, 14, 28])])
def test_hecho_anterior_al_inicio_se_sondea_a_7_14_28_dias_DESPUES_del_inicio(dias, esperado):
    # declarado 60 dias antes del inicio: el primer dia NO se sondea «a 28 dias».
    evs = [reg(1, vf=T0 - 60 * DIA), ini(ts=T0, seq=2)]
    assert [d for _h, d in r.sondas_pendientes(evs, T0 + dias * DIA)] == esperado
    assert r.sondas_pendientes(evs, T0) == []


def test_hecho_posterior_al_inicio_cuenta_desde_su_valid_from():
    evs = [ini(), reg(1, vf=T0 + 3 * DIA)]
    assert r.sondas_pendientes(evs, T0 + 9.99 * DIA) == []  # 6.99 dias de edad
    assert [d for _h, d in r.sondas_pendientes(evs, T0 + 10 * DIA)] == [7]


def test_control_dos_hechos_uno_anterior_y_otro_posterior_al_inicio():
    evs = [ini(), reg(1, hid=H, vf=T0 - 60 * DIA), reg(2, hid=H2, vf=T0 + 5 * DIA)]
    pend = [(h.hecho_id, d) for h, d in r.sondas_pendientes(evs, T0 + 7 * DIA)]
    assert pend == [(H, 7)]  # H: 7 dias tras el inicio; H2 solo lleva 2 dias
    pend = [(h.hecho_id, d) for h, d in r.sondas_pendientes(evs, T0 + 12 * DIA)]
    assert pend == [(H, 7), (H2, 7)]


def test_el_origen_efectivo_es_el_maximo_entre_valid_from_e_inicio_y_no_mira_el_orden_de_llegada():
    # el inicio llega con seq mayor que el hecho (orden de lectura distinto al de seq): igual manda.
    evs = [reg(1, vf=T0 - 60 * DIA), ini(ts=T0, seq=9)]
    assert r.reconstruir_poblacion(evs)[H].origen == T0
    assert r.reconstruir_poblacion([reg(1, vf=T0 + DIA), ini()])[H].origen == T0 + DIA


def test_se_usa_el_primer_inicio_por_seq_y_un_segundo_no_mueve_el_origen():
    evs = [ini(ts=T0 + 50 * DIA, seq=7), ini(ts=T0, seq=2), reg(1, vf=T0 - 9 * DIA)]
    assert r.reconstruir_poblacion(evs)[H].origen == T0


def test_version_edad_dias_no_cuenta_tiempo_previo_al_inicio():
    # v2 declarada 10 dias antes del inicio; a los 28 dias del inicio la version lleva 28, no 38.
    evs = [ini(), reg(1, vf=T0 - 60 * DIA), reg(2, version=2, vf=T0 - 10 * DIA)]
    (hecho, _), *_ = r.sondas_pendientes(evs, T0 + 28 * DIA)
    ev = r.evento_sonda(
        hecho, 28, T0 + 28 * DIA, {"resultado": "vigente", "estado_retirada": "ninguna", "n_entradas_memoria": 2}
    )
    assert ev["edad_dias"] == 28.0 and ev["version_edad_dias"] == 28.0


def test_el_informe_muestra_la_fecha_hora_de_inicio_y_su_seq():
    txt = r.informe([ini(ts=1_700_000_000.0, seq=42)])
    assert "2023-11-14T22:13:20" in txt and "seq 42" in txt


def test_el_informe_sin_inicio_lo_dice():
    assert "inicio: no registrado" in r.informe([reg(1)])


# ======================================================== evaluar sonda ==


def test_vigente_cuando_el_core_responde_con_el_valor_actual():
    e = r.evaluar_sonda(H, [entrada("mi coche es rojo")])
    assert e["resultado"] == "vigente" and e["estado_retirada"] == "ninguna" and e["n_entradas_memoria"] == 1


def test_nombre_por_me_llamo_se_pregunta_como_nombre():
    assert r.evaluar_sonda(H, [entrada("me llamo Mauricio")])["resultado"] == "vigente"


def test_con_version_superseded_responde_la_vigente():
    ents = [entrada("mi coche es rojo", valid_until=T0 + DIA), entrada("mi coche es azul", version=2)]
    assert r.evaluar_sonda(H, ents)["resultado"] == "vigente"


def test_sin_entradas_del_hecho_es_sin_consulta_y_la_causa_viene_del_evento():
    e = r.evaluar_sonda(H, [entrada("mi coche es rojo", hid=H2)], causa_retirada="olvido")
    assert (e["resultado"], e["estado_retirada"]) == ("sin_consulta", "olvido")
    assert r.evaluar_sonda(H, [])["estado_retirada"] == "ninguna"


def test_refutada_sin_vigente_da_nada_con_su_causa():
    e = r.evaluar_sonda(H, [entrada("mi coche es rojo", refutada=True)], causa_retirada="refutacion")
    assert (e["resultado"], e["estado_retirada"]) == ("nada", "refutacion")


def test_valor_retirado_cuando_la_respuesta_da_un_valor_no_vigente():
    ents = [entrada("mi coche es rojo", valid_until=T0 + DIA), entrada("mi coche es azul", version=2, refutada=True)]
    rota = lambda t, vivas: "Tu coche es rojo."  # noqa: E731  (un Core con el filtro de vigencia roto)
    e = r.evaluar_sonda(H, ents, causa_retirada="refutacion", responder=rota)
    assert e["resultado"] == "valor_retirado"
    # control: con el Core real el mismo escenario NO recupera el valor retirado
    assert r.evaluar_sonda(H, ents, causa_retirada="refutacion")["resultado"] == "nada"


def test_estado_retirada_no_anula_el_resultado_si_el_hecho_sigue_vigente():
    # v1 olvidada despues de registrar v2: el evento existe, pero el hecho esta vigente y se recupera.
    e = r.evaluar_sonda(H, [entrada("mi coche es azul", version=2)], causa_retirada="olvido")
    assert (e["resultado"], e["estado_retirada"]) == ("vigente", "ninguna")


def test_otro_usuario_no_contamina_la_respuesta():
    ents = [entrada("mi coche es rojo", user="u"), entrada("mi coche es verde", hid=H2, user="otro")]
    assert r.evaluar_sonda(H, ents, responder=Orchestrator._responder_hecho)["resultado"] == "vigente"


def test_respuesta_distinta_de_cualquier_valor_conocido_es_nada():
    e = r.evaluar_sonda(H, [entrada("mi coche es rojo")], responder=lambda t, v: "Tu coche es fucsia.")
    assert e["resultado"] == "nada"


# ================================================================== tasa ==


def _d28(n_vig, n_perd, n_user=0):
    evs, seq = [], 1
    for i in range(n_vig):
        evs.append(sonda(seq, hid=f"v{i}"))
        seq += 1  # noqa: E702
    for i in range(n_perd):
        evs.append(sonda(seq, hid=f"p{i}", resultado="sin_consulta"))
        seq += 1  # noqa: E702
    for i in range(n_user):
        evs.append(sonda(seq, hid=f"u{i}", resultado="sin_consulta", estado="olvido"))
        seq += 1  # noqa: E702
    return evs


def test_sin_sondas_a_28_dias_no_hay_datos():
    t = r.tasa_dia28([reg(1), sonda(2, dia=7), sonda(3, dia=14)], minimo=1)
    assert t.valor is None and t.veredicto == r.SIN_DATOS


def test_bajo_el_minimo_no_hay_datos_y_en_el_minimo_exacto_si():
    assert r.tasa_dia28(_d28(2, 0), minimo=3).veredicto == r.SIN_DATOS
    t = r.tasa_dia28(_d28(3, 0), minimo=3)
    assert t.veredicto == r.MEDIDA and t.valor == 1.0


def test_el_minimo_por_defecto_es_la_constante_con_nombre():
    assert r.MINIMO_SONDAS_DIA28 >= 1
    n = r.MINIMO_SONDAS_DIA28
    assert r.tasa_dia28(_d28(n - 1, 0)).veredicto == r.SIN_DATOS
    assert r.tasa_dia28(_d28(n, 0)).veredicto == r.MEDIDA


def test_solo_cuentan_las_sondas_de_dia_28():
    evs = _d28(3, 0) + [sonda(100 + i, hid=f"x{i}", dia=14, resultado="nada") for i in range(5)]
    t = r.tasa_dia28(evs, minimo=3)
    assert (t.valor, t.denominador) == (1.0, 3)


def test_politica_por_defecto_excluye_solo_retiradas_del_usuario_y_el_resto_es_no_recuperado():
    t = r.tasa_dia28(_d28(2, 1, 4), minimo=1)
    assert (t.recuperados, t.denominador, t.excluidos) == (2, 3, 4)
    assert t.valor == pytest.approx(2 / 3)


def test_dos_politicas_dan_tasas_distintas_sobre_los_mismos_eventos():
    evs = _d28(2, 1, 4)
    a = r.tasa_dia28(evs, politica=r.EXCLUIR_RETIRADAS_USUARIO, minimo=1)
    b = r.tasa_dia28(evs, politica=r.CONTAR_TODAS, minimo=1)
    assert a.valor == pytest.approx(2 / 3) and b.valor == pytest.approx(2 / 7)
    assert b.excluidos == 0


def test_politica_desconocida_falla_en_voz_alta():
    with pytest.raises(ValueError):
        r.tasa_dia28(_d28(1, 0), politica="inventada")


def test_valor_retirado_nunca_cuenta_como_recuperado():
    evs = [sonda(1, resultado="valor_retirado")]
    t = r.tasa_dia28(evs, minimo=1)
    assert t.valor == 0.0 and t.valor_retirado == 1


def test_sondas_duplicadas_cuentan_una_vez():
    evs = [sonda(1), sonda(2)]
    assert r.tasa_dia28(evs, minimo=1).denominador == 1


# ============================================================== informe ==


def test_el_informe_nunca_afirma_cero_fabricacion():
    for evs in ([], _d28(30, 0), [sonda(1, resultado="valor_retirado")], _d28(0, 5)):
        txt = r.informe(evs, minimo=1).lower()
        assert "cero fabricaci" not in txt and "0 fabricaci" not in txt
        assert "no evidenciada" in txt


def test_el_informe_dice_sin_datos_suficientes_en_vez_de_un_porcentaje():
    txt = r.informe(_d28(1, 0))
    assert "sin datos suficientes" in txt and "%" not in txt


def test_el_informe_muestra_la_tasa_con_su_politica_cuando_hay_datos():
    txt = r.informe(_d28(3, 1), minimo=2)
    assert "75" in txt and r.EXCLUIR_RETIRADAS_USUARIO in txt


# ===================================================== sondas tardias y version reciente (tasa) ==


TOL = r.TOLERANCIA_SONDA_DIAS


def test_la_tolerancia_es_una_constante_con_nombre_positiva():
    assert TOL > 0


def test_sonda_tardia_se_excluye_de_la_tasa_y_la_de_control_dentro_de_tolerancia_cuenta():
    evs = [sonda(1, hid="en", edad=28 + TOL / 2), sonda(2, hid="tarde", edad=40.0, vedad=40.0, resultado="nada")]
    t = r.tasa_dia28(evs, minimo=1)
    assert (t.denominador, t.recuperados, t.fuera_de_ventana, t.valor) == (1, 1, 1, 1.0)


def test_sondas_tardias_a_200_dias_no_dan_tasa():
    evs = [sonda(i, hid=f"h{i}", edad=200.0, vedad=200.0) for i in range(1, 6)]
    t = r.tasa_dia28(evs, minimo=1)
    assert t.veredicto == r.SIN_DATOS and t.fuera_de_ventana == 5 and t.edad_min is None


def test_redeclaracion_el_dia_27_no_es_retencion_a_28_dias():
    evs = [sonda(1, hid="a", edad=28.0, vedad=1.0), sonda(2, hid="b", edad=28.0, vedad=28.0)]
    t = r.tasa_dia28(evs, minimo=1)
    assert (t.denominador, t.version_reciente, t.fuera_de_ventana) == (1, 1, 0)


@pytest.mark.parametrize(
    "edad,vedad,cuenta",
    [
        (27.99, 27.99, False),
        (28.0, 28.0, True),
        (28.0 + TOL, 28.0, True),
        (28.0 + TOL + 0.01, 28.0, False),
        (28.0, 27.99, False),
        (28.0 + TOL, 28.0 + TOL, True),
    ],
)
def test_fronteras_exactas_de_la_ventana_y_de_la_version(edad, vedad, cuenta):
    t = r.tasa_dia28([sonda(1, edad=edad, vedad=vedad)], minimo=1)
    assert (t.denominador == 1) is cuenta


def test_el_informe_muestra_excluidas_por_motivo_y_edades_de_las_contadas():
    evs = [
        sonda(1, hid="a", edad=29.0),
        sonda(2, hid="b", edad=31.0),
        sonda(3, hid="c", edad=90.0, vedad=90.0),
        sonda(4, hid="d", edad=28.0, vedad=3.0),
    ]
    txt = r.informe(evs, minimo=1)
    assert "1 tardia(s)" in txt and "1 con version de menos de 28" in txt
    assert "min 29.0" in txt and "max 31.0" in txt


# =============================================== colision de seq entre procesos (dedupe completo) ==


def test_dos_eventos_cm2_distintos_con_el_mismo_seq_se_conservan_ambos():
    a = {**reg(5, hid=H), "ts": 1.0}
    b = {**reg(5, hid=H2), "ts": 2.0}
    assert set(r.reconstruir_poblacion([a, b])) == {H, H2}


def test_dos_eventos_identicos_cuentan_una_vez():
    a = {**sonda(5, dia=28), "ts": 1.0}
    assert r._ordenados([a, dict(a)], (r.EV_SONDA,)) == [a]
    assert len(r._ordenados([a, {**a, "ts": 2.0}], (r.EV_SONDA,))) == 2


# ============================== `_iniciado` y `inicio_del_reloj` son UNA sola nocion de «iniciado» ==


def test_un_inicio_sin_ts_numerico_no_cuenta_como_inicio(tmp_path):
    """`medir` y `iniciar` usan `inicio_del_reloj`: un `cm2.inicio` sin `ts` numerico no inicia el reloj."""
    import json

    (tmp_path / "audit.jsonl").write_text(json.dumps({"seq": 1, "evento": "cm2.inicio", "ts": "ayer"}) + "\n")
    assert "NO iniciado" in r.medir(str(tmp_path), ahora=T0)
    assert "ya iniciado" not in r.iniciar(str(tmp_path), confirmo=False)
    # CONTROL: con ts numerico SI cuenta.
    (tmp_path / "audit.jsonl").write_text(json.dumps({"seq": 1, "evento": "cm2.inicio", "ts": T0}) + "\n")
    assert "reloj de CM2: iniciado" in r.medir(str(tmp_path), ahora=T0)
