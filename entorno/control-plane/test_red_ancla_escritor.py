"""RED · el ESCRITOR no se bloquea por el ancla (decision del orquestador, 2026-10-26).

Antes, `_registrar_sin_lock` lanzaba `AnclaInconsistente` si el ancla faltaba o no concordaba: al desplegar
D-LOG-1 el cron de produccion (`despertar_rechazado` cada 30 min) habria empezado a fallar y se habria perdido
evidencia. Contrato nuevo, los 7 casos:

  1 log nuevo y vacio            -> ancla genesis ANTES del primer evento; integro/demostrada
  2 log heredado sin ancla       -> evento escrito, ancla NO creada;       no integro / no_demostrable
  3 cadena interna rota          -> evento escrito, ancla intacta;         no integro / no_demostrable
  4 ancla perdida o corrupta     -> evento escrito, ancla NO sobrescrita;  no integro / no_demostrable
  5 truncamiento / alteracion    -> evento escrito, ancla NO adelantada;   no integro / truncada_o_alterada
  6 integro y ancla valida       -> evento escrito y ancla adelantada;     integro / demostrada
  7 caida durante la inicializacion -> cubierto por 1 (genesis atomica antes del primer evento)

Todo en `tmp_path` con historiales SINTETICOS (`AURA_ANCLA_DIR` lo fija el conftest). Cada prueba lleva control.
"""

from __future__ import annotations

import json
import pathlib

import aura
import control_plane as cp
import motor_autonomia as motor
import orquestador as orq
import pytest
from test_red_motor_autonomia import _con_review, _plano_con_codigo_muerto

NO_DEMOSTRABLE, TRUNCADA, DEMOSTRADA = "no_demostrable", "truncada_o_alterada", "demostrada"


def _log(tmp_path, n=4, nombre="hist"):
    d = pathlib.Path(tmp_path) / nombre
    for i in range(n):
        cp.registrar_evento(d, "hecho", {"i": i})
    return d


def _ancla(d):
    return json.loads(cp.ruta_ancla(d).read_text(encoding="utf-8"))


def _heredado(tmp_path, n=3):
    """Log con eventos y SIN ancla (lo que hay en produccion al desplegar)."""
    d = _log(tmp_path, n, "heredado")
    cp.ruta_ancla(d).unlink()
    return d


def _quitar_ultimos(d, k):
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    ruta.write_text("".join(lineas[:-k]), encoding="utf-8")


def _estado(d):
    r = cp.verificar_integridad_log(d)
    return r["integro"], r["completitud"]


# ----------------------------------------------------------------------- caso 1 y 7


def test_caso1_log_nuevo_escribe_el_ancla_genesis_ANTES_del_primer_evento(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path) / "nuevo"
    vistos = {}
    real = cp._hash_de

    def espiar(evento):                       # se llama tras el plan de ancla y antes de escribir el evento
        vistos["ancla_existia"] = cp.ruta_ancla(d).exists()
        vistos["log_existia"] = cp.ruta_eventos(d).exists()
        return real(evento)

    monkeypatch.setattr(cp, "_hash_de", espiar)
    cp.registrar_evento(d, "hecho", {})
    assert vistos == {"ancla_existia": True, "log_existia": False}, "la genesis precede al primer evento"
    assert _ancla(d)["seq"] == 1 and _estado(d) == (True, DEMOSTRADA)
    assert cp.verificar_integridad_log(d)["completitud_desde"] == 1


def test_caso7_caida_ENTRE_la_ancla_genesis_y_el_primer_evento_deja_ancla_atrasada_recuperable(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path) / "cae"
    real = cp._hash_de
    monkeypatch.setattr(cp, "_hash_de", lambda e: (_ for _ in ()).throw(RuntimeError("caida")))
    with pytest.raises(RuntimeError):
        cp.registrar_evento(d, "hecho", {})
    monkeypatch.setattr(cp, "_hash_de", real)
    assert cp.ruta_ancla(d).exists() and _ancla(d)["seq"] == 0 and not cp.leer_eventos(d)
    assert _estado(d) == (True, DEMOSTRADA), "genesis sin eventos es un log vacio sano, no 'log sin ancla'"
    cp.registrar_evento(d, "hecho", {"i": 1})                       # reanuda: el siguiente evento se ancla
    assert _ancla(d)["seq"] == 1 and _estado(d) == (True, DEMOSTRADA)


def test_caso7_caida_tras_el_primer_evento_antes_de_adelantar_es_ancla_ATRASADA_y_reparable(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path) / "cae2"
    real = cp._escribir_ancla
    estado = {"n": 0}

    def cae_en_el_segundo(*a, **k):                                    # 1.o genesis, 2.o adelantar
        estado["n"] += 1
        if estado["n"] == 2:
            raise RuntimeError("caida")
        return real(*a, **k)

    monkeypatch.setattr(cp, "_escribir_ancla", cae_en_el_segundo)
    with pytest.raises(RuntimeError):
        cp.registrar_evento(d, "hecho", {})
    monkeypatch.setattr(cp, "_escribir_ancla", real)
    r = cp.verificar_integridad_log(d)
    assert len(cp.leer_eventos(d)) == 1 and _ancla(d)["seq"] == 0
    assert r["integro"] is True and r["ancla"]["atrasada"] is True
    assert cp.reparar_ancla(d)["reparada"] is True and _ancla(d)["seq"] == 1


def test_caso7_CONTROL_la_genesis_con_cola_inexplicable_no_es_integra(tmp_path):
    """Una genesis (seq 0) solo se explica con UN evento sin anclar; con mas, alguien tocó el ancla."""
    d = _log(tmp_path, 4)
    contenido = _ancla(d)
    contenido.update(seq=0, hash=None)
    contenido["historial"]["genesis"] = None
    cp.ruta_ancla(d).write_text(json.dumps(contenido), encoding="utf-8")
    r = cp.verificar_integridad_log(d)
    assert (r["integro"], r["completitud"]) == (False, TRUNCADA)


# ----------------------------------------------------------------------- caso 2


def test_caso2_log_heredado_sin_ancla_el_escritor_ESCRIBE_y_NO_crea_el_ancla(tmp_path):
    d = _heredado(tmp_path, 3)
    cp.registrar_evento(d, "hecho", {"i": 99})
    assert len(cp.leer_eventos(d)) == 4 and not cp.ruta_ancla(d).exists(), "nunca en silencio"
    assert _estado(d) == (False, NO_DEMOSTRABLE)
    assert cp.verificar_integridad_log(d)["completitud_desde"] is None


def test_caso2_cron_simulado_tres_despertar_rechazado_no_fallan_y_la_completitud_sigue_no_demostrable(tmp_path):
    d = _heredado(tmp_path, 5)
    for i in range(3):
        cp.registrar_evento(d, "despertar_rechazado", {"motivo": "prueba", "vuelta": i})
    tipos = [e["tipo"] for e in cp.leer_eventos(d)]
    assert tipos[-3:] == ["despertar_rechazado"] * 3 and len(tipos) == 8
    assert not cp.ruta_ancla(d).exists()
    assert _estado(d) == (False, NO_DEMOSTRABLE)
    assert cp.verificar_integridad_log(d)["integridad_eventos"] is True


def test_caso2_CONTROL_el_mismo_guion_con_ancla_adelanta_y_es_demostrada(tmp_path):
    d = _log(tmp_path, 5)
    for i in range(3):
        cp.registrar_evento(d, "despertar_rechazado", {"vuelta": i})
    assert _ancla(d)["seq"] == 8 and _estado(d) == (True, DEMOSTRADA)


# ----------------------------------------------------------------------- caso 3


def test_caso3_cadena_rota_el_escritor_escribe_y_no_toca_el_ancla(tmp_path):
    d = _log(tmp_path, 4)
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ev = json.loads(lineas[1])
    ev["datos"]["i"] = 31337
    lineas[1] = json.dumps(ev)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    antes = cp.ruta_ancla(d).read_bytes()
    cp.registrar_evento(d, "hecho", {"i": 5})
    assert len(cp.leer_eventos(d)) == 5 and cp.ruta_ancla(d).read_bytes() == antes
    assert _estado(d) == (False, NO_DEMOSTRABLE)
    assert cp.verificar_integridad_log(d)["motivo_codigo"] == "cadena_rota"


# ----------------------------------------------------------------------- caso 4


@pytest.mark.parametrize("contenido", ["{no es json", json.dumps({"version": 99}), "[]"])
def test_caso4_ancla_corrupta_o_incompatible_NO_se_sobrescribe(tmp_path, contenido):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).write_text(contenido, encoding="utf-8")
    cp.registrar_evento(d, "hecho", {"i": 7})
    assert len(cp.leer_eventos(d)) == 4
    assert cp.ruta_ancla(d).read_text(encoding="utf-8") == contenido, "una ancla corrupta es evidencia"
    assert _estado(d) == (False, NO_DEMOSTRABLE)


def test_caso4_ancla_perdida_en_un_log_con_eventos_no_se_recrea(tmp_path):
    d = _log(tmp_path, 3)
    cp.ruta_ancla(d).unlink()
    cp.registrar_evento(d, "hecho", {"i": 7})
    assert not cp.ruta_ancla(d).exists() and _estado(d) == (False, NO_DEMOSTRABLE)


# ----------------------------------------------------------------------- caso 5


def test_caso5_truncamiento_el_escritor_escribe_pero_NO_adelanta_el_ancla_y_la_deteccion_es_permanente(tmp_path):
    d = _log(tmp_path, 6)
    _quitar_ultimos(d, 3)
    ancla = cp.ruta_ancla(d).read_bytes()
    deteccion = []
    for i in range(8):                                     # incluso superando el seq anclado
        cp.registrar_evento(d, "hecho", {"i": 100 + i})
        deteccion.append(_estado(d))
    assert deteccion == [(False, TRUNCADA)] * 8
    assert cp.ruta_ancla(d).read_bytes() == ancla
    assert len(cp.leer_eventos(d)) == 11


def test_caso5_alteracion_del_ultimo_evento_con_hash_valido_el_escritor_no_la_blanquea(tmp_path):
    d = _log(tmp_path, 4)
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ev = json.loads(lineas[-1])
    ev["datos"]["i"] = 555
    ev["hash"] = cp._hash_de(ev)
    lineas[-1] = cp._canonico(ev)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    cp.registrar_evento(d, "hecho", {})
    assert _estado(d) == (False, TRUNCADA) and _ancla(d)["seq"] == 4


def test_caso5_ancla_de_otro_historial_no_se_adelanta(tmp_path):
    d = _log(tmp_path, 3)
    otro = _log(tmp_path, 3, "otro")
    cp.ruta_ancla(d).write_bytes(cp.ruta_ancla(otro).read_bytes())
    cp.registrar_evento(d, "hecho", {})
    assert _estado(d) == (False, TRUNCADA)
    assert _ancla(d)["historial"]["ruta"] == str(otro.resolve())


# ----------------------------------------------------------------------- caso 6


def test_caso6_integro_el_escritor_adelanta_y_conserva_completitud_desde(tmp_path):
    d = _log(tmp_path, 3)
    cp.registrar_evento(d, "hecho", {})
    assert _ancla(d)["seq"] == 4 and _estado(d) == (True, DEMOSTRADA)


# ----------------------------------------------------------------------- adoptar_ancla


@pytest.mark.parametrize("por,motivo", [("", "x"), ("CEO", ""), (" ", "x"), ("CEO", "  "), (None, "x")])
def test_adoptar_exige_por_y_motivo_y_no_cambia_nada(tmp_path, por, motivo):
    d = _heredado(tmp_path, 3)
    with pytest.raises(ValueError):
        cp.adoptar_ancla(d, por=por, motivo=motivo)
    assert len(cp.leer_eventos(d)) == 3 and not cp.ruta_ancla(d).exists()


def test_adoptar_registra_el_evento_y_la_completitud_se_demuestra_DESDE_la_adopcion(tmp_path):
    d = _heredado(tmp_path, 3)
    cp.registrar_evento(d, "despertar_rechazado", {})
    r = cp.adoptar_ancla(d, por="Mauricio", motivo="despliegue de D-LOG-1")
    ev = cp.leer_eventos(d)[-1]
    assert r["adoptada"] is True and ev["tipo"] == "ancla_adoptada"
    assert ev["datos"]["por"] == "Mauricio" and ev["datos"]["motivo"] == "despliegue de D-LOG-1"
    assert ev["datos"]["seq_adoptado"] == ev["seq"] == 5
    assert ev["datos"]["completitud_previa"] == NO_DEMOSTRABLE
    v = cp.verificar_integridad_log(d)
    assert v["integro"] is True and v["completitud"] == DEMOSTRADA and v["completitud_desde"] == 5
    cp.registrar_evento(d, "hecho", {})                                  # y el escritor conserva el 'desde'
    assert cp.verificar_integridad_log(d)["completitud_desde"] == 5


def test_adoptar_con_reemplazar_CONSERVA_el_ancla_anterior_como_evidencia(tmp_path):
    d = _log(tmp_path, 4)
    _quitar_ultimos(d, 2)
    anterior = cp.ruta_ancla(d).read_bytes()
    with pytest.raises(cp.AnclaInconsistente):                           # control: sin reemplazar no pisa
        cp.adoptar_ancla(d, por="Mauricio", motivo="x")
    assert cp.ruta_ancla(d).read_bytes() == anterior
    r = cp.adoptar_ancla(d, por="Mauricio", motivo="se acepta la perdida de 2 eventos", reemplazar=True)
    conservada = cp.ruta_ancla(d).with_name(r["ancla_conservada_como"])
    assert ".reemplazada-" in conservada.name and conservada.read_bytes() == anterior
    assert cp.leer_eventos(d)[-1]["datos"]["completitud_previa"] == TRUNCADA
    assert _estado(d) == (True, DEMOSTRADA)


def test_adoptar_no_se_hace_sobre_una_cadena_rota(tmp_path):
    d = _heredado(tmp_path, 3)
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ev = json.loads(lineas[1])
    ev["datos"]["i"] = 1234
    lineas[1] = json.dumps(ev)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    with pytest.raises(cp.AnclaInconsistente):
        cp.adoptar_ancla(d, por="Mauricio", motivo="x")
    assert not cp.ruta_ancla(d).exists()


def test_reparar_ancla_no_adopta_ni_tapa_truncamientos(tmp_path):
    h = _heredado(tmp_path, 3)
    assert cp.reparar_ancla(h)["reparada"] is False and not cp.ruta_ancla(h).exists()
    t = _log(tmp_path, 5, "trunc")
    _quitar_ultimos(t, 2)
    antes = cp.ruta_ancla(t).read_bytes()
    assert cp.reparar_ancla(t)["reparada"] is False and cp.ruta_ancla(t).read_bytes() == antes
    # control: una atrasada SI se repara
    a = _log(tmp_path, 3, "atrasada")
    ancla = cp.ruta_ancla(a).read_bytes()
    cp.registrar_evento(a, "hecho", {})
    cp.ruta_ancla(a).write_bytes(ancla)
    assert cp.reparar_ancla(a)["reparada"] is True


def test_reparar_ancla_conserva_completitud_desde_de_una_adopcion(tmp_path, monkeypatch):
    d = _heredado(tmp_path, 3)
    cp.adoptar_ancla(d, por="Mauricio", motivo="despliegue")
    desde = cp.verificar_integridad_log(d)["completitud_desde"]
    ancla = cp.ruta_ancla(d).read_bytes()
    cp.registrar_evento(d, "hecho", {})
    cp.ruta_ancla(d).write_bytes(ancla)                                   # ancla atrasada tras la adopcion
    assert cp.reparar_ancla(d)["reparada"] is True
    assert cp.verificar_integridad_log(d)["completitud_desde"] == desde == 4


# ----------------------------------------------------------------------- el motor


def _motor(tmp_path, cuantos=2):
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=cuantos)
    _con_review(tmp_path)
    return zona


@pytest.fixture(autouse=True)
def _sin_medir_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def test_el_motor_SE_NIEGA_con_historial_no_verificable_y_sale_con_codigo_2(tmp_path):
    zona = _motor(tmp_path)
    cp.ruta_ancla(tmp_path).unlink()                                      # log heredado: no_demostrable
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda raiz: True, max_tareas=2)
    assert informe["motivo_de_parada"].startswith("historial no verificable: ancla_ausente")
    assert informe["ejecutadas"] == 0
    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert "tarea_planificada" not in tipos and "cambio_aplicado" not in tipos
    assert tipos[-1] == "ciclo_detenido", "la parada queda registrada, visible"
    assert aura.codigo_de_salida(informe) == 2
    assert "def _muerta_0" in (zona / "modulo_0.py").read_text(encoding="utf-8"), "no se toco el arbol"


def test_el_motor_se_niega_tambien_con_el_historial_truncado(tmp_path):
    zona = _motor(tmp_path)
    for i in range(4):
        cp.registrar_evento(tmp_path, "hecho", {"i": i})
    _quitar_ultimos(tmp_path, 2)
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda raiz: True, max_tareas=2)
    assert informe["motivo_de_parada"].startswith("historial no verificable: cola_mas_corta_que_el_ancla")
    assert informe["ejecutadas"] == 0 and aura.codigo_de_salida(informe) == 2


def test_CONTROL_el_motor_con_historial_integro_SI_trabaja(tmp_path):
    zona = _motor(tmp_path)
    assert cp.verificar_integridad_log(tmp_path)["integro"] is True
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda raiz: True, max_tareas=2)
    assert informe["ejecutadas"] == 2 and aura.codigo_de_salida(informe) == 0
    assert not informe["motivo_de_parada"].startswith("historial no verificable")


def test_tras_adoptar_el_motor_vuelve_a_trabajar(tmp_path):
    zona = _motor(tmp_path)
    cp.ruta_ancla(tmp_path).unlink()
    assert motor.trabajar(tmp_path, zona, verificacion=lambda r: True)["ejecutadas"] == 0
    cp.adoptar_ancla(tmp_path, por="Mauricio", motivo="el historial es el de produccion verificado a mano")
    assert motor.trabajar(tmp_path, zona, verificacion=lambda r: True, max_tareas=2)["ejecutadas"] == 2
