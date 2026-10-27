"""N1 — anti-replay persistente del nodo (§12.6 N1, N5). Cada rechazo tiene control positivo."""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

import pytest

from aura_skeleton.adapters.almacen_consumidas import NOMBRE, AlmacenConsumidas
from aura_skeleton.core.delegacion import Motivo, RechazoOrden, validar_orden
from tests.delegacion_apoyo import T0, campos_validos, firmante_orden, mundo


def _validar(m, sobre, almacen, **kw):  # type: ignore[no-untyped-def]
    return validar_orden(sobre, politica=m.politica(**kw), verificar=m.verificador_hc1(), almacen=almacen)


def _motivo(m, sobre, almacen, **kw) -> Motivo:  # type: ignore[no-untyped-def]
    with pytest.raises(RechazoOrden) as e:
        _validar(m, sobre, almacen, **kw)
    return e.value.motivo


def test_control_una_orden_fresca_se_acepta_una_sola_vez(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    sobre = firmante_orden(m.hc1, campos_validos())
    assert _validar(m, sobre, alm)
    assert _motivo(m, sobre, alm) is Motivo.ORDEN_REPETIDA


def test_tras_reiniciar_el_nodo_la_misma_orden_se_rechaza(tmp_path: Path) -> None:
    m = mundo()
    sobre = firmante_orden(m.hc1, campos_validos())
    assert _validar(m, sobre, AlmacenConsumidas(tmp_path / "nodo"))
    # "reinicio": instancia NUEVA del almacén y política nueva, mismo directorio
    assert _motivo(m, sobre, AlmacenConsumidas(tmp_path / "nodo")) is Motivo.ORDEN_REPETIDA


def test_el_consumo_es_durable_y_el_directorio_es_privado(tmp_path: Path) -> None:
    alm = AlmacenConsumidas(tmp_path / "nodo")
    alm.consumir("x" * 36, 3)
    assert (tmp_path / "nodo" / NOMBRE).read_text().count("\n") == 1
    assert (tmp_path / "nodo").stat().st_mode & 0o777 == 0o700
    assert alm.ruta.stat().st_mode & 0o077 == 0


def test_retransmision_de_la_misma_orden_otras_veces_siempre_rechazada(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    sobre = firmante_orden(m.hc1, campos_validos())
    _validar(m, sobre, alm)
    for _ in range(3):
        assert _motivo(m, sobre, alm) is Motivo.ORDEN_REPETIDA


def test_una_orden_rechazada_por_otra_causa_no_se_quema(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    c = campos_validos()
    malo = firmante_orden(m.hc1, {**c, "destinatario": "c" * 32})
    assert _motivo(m, malo, alm) is Motivo.DESTINATARIO_AJENO
    assert _validar(m, firmante_orden(m.hc1, c), alm)  # mismo id_ejecucion, ahora válida: no se había consumido


def test_orden_caducada_se_rechaza_y_en_el_limite_exacto_tambien(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    m.reloj.t = T0 + 59.9
    assert _validar(m, firmante_orden(m.hc1, campos_validos()), alm)  # control: aún viva
    m.reloj.t = T0 + 60
    assert _motivo(m, firmante_orden(m.hc1, campos_validos()), alm) is Motivo.ORDEN_CADUCADA


def test_caducidad_excesiva_o_invertida_se_rechaza(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    assert _motivo(m, firmante_orden(m.hc1, campos_validos(caduca_en=T0 + 301)), alm) is Motivo.CADUCIDAD_EXCESIVA
    assert _validar(m, firmante_orden(m.hc1, campos_validos(caduca_en=T0 + 300)), alm)
    assert _motivo(m, firmante_orden(m.hc1, campos_validos(caduca_en=T0 - 1)), alm) in (
        Motivo.ORDEN_CADUCADA,
        Motivo.CADUCIDAD_EXCESIVA,
    )


def test_emitida_antes_del_arranque_del_nodo_se_rechaza(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    viejo = firmante_orden(m.hc1, campos_validos(emitida_en=T0 - 20, caduca_en=T0 + 60))
    assert _motivo(m, viejo, alm, arranque=T0 - 10) is Motivo.EMITIDA_ANTES_DEL_ARRANQUE
    assert _validar(m, viejo, alm, arranque=T0 - 20)  # control: con el arranque anterior sí es aceptable


def test_emitida_en_el_futuro_lejano_se_rechaza(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    f = firmante_orden(m.hc1, campos_validos(emitida_en=T0 + 30, caduca_en=T0 + 90))
    assert _motivo(m, f, alm) is Motivo.EMITIDA_EN_EL_FUTURO
    ok = firmante_orden(m.hc1, campos_validos(emitida_en=T0 + 5, caduca_en=T0 + 90))
    assert _validar(m, ok, alm)


def test_epoch_antiguo_se_rechaza_tambien_tras_reiniciar(tmp_path: Path) -> None:
    m = mundo()
    nodo = tmp_path / "nodo"
    assert _validar(m, firmante_orden(m.hc1, campos_validos(epoch_hc1=5)), AlmacenConsumidas(nodo))
    alm2 = AlmacenConsumidas(nodo)  # reinicio
    assert _motivo(m, firmante_orden(m.hc1, campos_validos(epoch_hc1=4)), alm2) is Motivo.EPOCH_ANTIGUO
    assert _validar(m, firmante_orden(m.hc1, campos_validos(epoch_hc1=5)), alm2)  # epoch igual: permitido
    assert _validar(m, firmante_orden(m.hc1, campos_validos(epoch_hc1=6)), alm2)


def test_reloj_no_sincronizado_rechaza_todo_incluso_una_orden_perfecta(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    sobre = firmante_orden(m.hc1, campos_validos())
    m.reloj.poner_sincronizado(False)
    assert _motivo(m, sobre, alm) is Motivo.RELOJ_NO_SINCRONIZADO
    assert _motivo(m, b"basura", alm) is Motivo.RELOJ_NO_SINCRONIZADO  # ni mira el contenido
    m.reloj.poner_sincronizado(True)  # control: al sincronizar, la misma orden (no quemada) pasa
    assert _validar(m, sobre, alm)


def test_tras_una_desconexion_las_ordenes_ya_consumidas_siguen_rechazadas(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "nodo")
    sobre = firmante_orden(m.hc1, campos_validos())
    _validar(m, sobre, alm)
    del alm  # el proceso del nodo "cae" y se reconecta más tarde
    m.reloj.t = T0 + 30
    assert _motivo(m, sobre, AlmacenConsumidas(tmp_path / "nodo")) is Motivo.ORDEN_REPETIDA


def test_almacen_corrupto_o_truncado_falla_cerrado(tmp_path: Path) -> None:
    m = mundo()
    nodo = tmp_path / "nodo"
    alm = AlmacenConsumidas(nodo)
    _validar(m, firmante_orden(m.hc1, campos_validos()), alm)
    # (una línea FINAL truncada por caída ya no es corrupción: se recupera, ver test_delegacion_nodo_estados.py)
    (nodo / NOMBRE).write_bytes(b"basura\n")
    assert _motivo(m, firmante_orden(m.hc1, campos_validos()), AlmacenConsumidas(nodo)) is Motivo.ALMACEN_ILEGIBLE


def _consumir_en_proceso(ruta: str, ident: str, salida: multiprocessing.Queue[str]) -> None:
    try:
        AlmacenConsumidas(Path(ruta)).consumir(ident, 1)
        salida.put("ok")
    except RechazoOrden as e:
        salida.put(e.motivo.value)


def test_dos_procesos_compitiendo_por_la_misma_orden_solo_uno_la_consume(tmp_path: Path) -> None:
    ctx = multiprocessing.get_context("fork")
    cola = ctx.Queue()
    ps = [ctx.Process(target=_consumir_en_proceso, args=(str(tmp_path / "nodo"), "u" * 36, cola)) for _ in range(6)]
    for p in ps:
        p.start()
    for p in ps:
        p.join(30)
        assert p.exitcode == 0
    resultados = sorted(cola.get(timeout=5) for _ in ps)
    assert resultados.count("ok") == 1
    assert resultados.count(Motivo.ORDEN_REPETIDA.value) == 5


def test_el_almacen_no_pierde_consumos_ante_muchas_ordenes(tmp_path: Path) -> None:
    alm = AlmacenConsumidas(tmp_path / "nodo")
    for i in range(50):
        alm.consumir(f"id-{i}", i)
    otro = AlmacenConsumidas(tmp_path / "nodo")
    with pytest.raises(RechazoOrden):
        otro.consumir("id-49", 49)
    assert os.stat(alm.ruta).st_size > 0
