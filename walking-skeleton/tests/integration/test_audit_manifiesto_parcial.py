"""Escritura PARCIAL del manifiesto del audit (DP-RESIDENCIA-MEDICION-CM2, Fase 1, hallazgo posterior).

Escenario: `_sellar` renombra el activo y la entrada del manifiesto se escribe a medias (ENOSPC, corte).
`ErrorEscrituraParcial` se propaga y el segmento queda huerfano. La siguiente anotacion (reconciliacion
o el siguiente sellado) se anexa con O_APPEND: si el manifiesto no acaba en salto de linea, la entrada
nueva se FUSIONA con el fragmento y deja de ser legible -> se pierde la anotacion mientras el audit
dice "segmento reconciliado". La correccion cierra la cola del manifiesto (append-only, como el activo).

Todas las pruebas sobre `tmp_path`; nada toca `~/.aura`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.observability import AuditLog
from tests.integration.test_audit_multiescritor import _lanzar_escritores

UMBRAL = 600


def _rec(msg: str = "x") -> dict:
    return {"level": "INFO", "module": "T", "msg": msg, "trace_id": "-", "audit": True}


def _manifiesto(tmp_path: Path) -> Path:
    return tmp_path / "audit.jsonl.manifest"


def _entradas_legibles(tmp_path: Path) -> list[dict]:
    out = []
    for linea in _manifiesto(tmp_path).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return out


def _cortar_entrada_manifiesto(m: pytest.MonkeyPatch, cuanto: str = "mitad") -> None:
    """La PROXIMA escritura de una entrada de manifiesto deja bytes reales a medias en disco."""
    real_write = os.write
    estado = {"hecho": False}

    def escritura(fd: int, datos: bytes) -> int:
        if not estado["hecho"] and datos.lstrip(b"\n").startswith(b'{"segmento"'):
            estado["hecho"] = True
            parte = datos[: len(datos) // 2] if cuanto == "mitad" else datos[:-1]  # "salto": falta solo el \n
            return real_write(fd, parte)
        return real_write(fd, datos)

    m.setattr(obs.os, "write", escritura)


def _sellar_con_manifiesto_cortado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cuanto: str = "mitad"
) -> tuple[str, AuditLog]:
    """Sella un segmento (e0..e2 + grande) con la entrada del manifiesto cortada. Devuelve (nombre, escritor)."""
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta), umbral_bytes=UMBRAL)
    for i in range(3):
        a.append(_rec(f"e{i}"))
    with monkeypatch.context() as m:
        _cortar_entrada_manifiesto(m, cuanto)
        with pytest.raises(obs.ErrorEscrituraParcial):
            a.append(_rec("z" * 700))  # supera el umbral: sella; la entrada del manifiesto queda a medias
    (nombre,) = [n for n in os.listdir(tmp_path) if n.startswith("audit.jsonl.0")]
    assert not ruta.exists(), "precondicion: el activo se renombro antes de anotar"
    assert not _manifiesto(tmp_path).read_bytes().endswith(b"\n"), "precondicion: cola del manifiesto cortada"
    return nombre, a


# --- RED principal: sellado + manifiesto parcial + nueva instancia + reconciliacion -----------------


def test_manifiesto_parcial_la_reconciliacion_anota_un_segmento_legible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nombre, _ = _sellar_con_manifiesto_cortado(tmp_path, monkeypatch)
    previo = _manifiesto(tmp_path).read_bytes()

    b = AuditLog(str(tmp_path / "audit.jsonl"))

    assert [s["segmento"] for s in b.segmentos()] == [nombre], "la anotacion de la reconciliacion es legible"
    assert b.verificar(nombre)
    assert _manifiesto(tmp_path).read_bytes().startswith(previo), "append-only: el fragmento sigue en disco"
    assert _manifiesto(tmp_path).read_bytes().endswith(b"\n")
    recs = b.reconstruir()
    assert [r["msg"] for r in recs if r["msg"].startswith("e")] == ["e0", "e1", "e2"]
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1)), "sin huecos ni duplicados"
    cierres = [r for r in recs if r.get("evento") == "audit.linea_parcial_cerrada"]
    assert [c.get("fichero") for c in cierres] == ["audit.jsonl.manifest"], "constancia del cierre del manifiesto"


def test_manifiesto_parcial_la_reconciliacion_es_idempotente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nombre, _ = _sellar_con_manifiesto_cortado(tmp_path, monkeypatch)
    AuditLog(str(tmp_path / "audit.jsonl"))
    c = AuditLog(str(tmp_path / "audit.jsonl"))  # segundo arranque
    assert [s["segmento"] for s in c.segmentos()] == [nombre], "no se duplica la entrada"
    recs = c.reconstruir()
    assert len([r for r in recs if r.get("evento") == "audit.segmento_reconciliado"]) == 1
    assert len([r for r in recs if r.get("evento") == "audit.linea_parcial_cerrada"]) == 1


def test_manifiesto_parcial_el_mismo_escritor_sigue_y_el_siguiente_sellado_es_legible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin reinicio: el escritor que sufrio el fallo sigue escribiendo y vuelve a sellar."""
    nombre, vivo = _sellar_con_manifiesto_cortado(tmp_path, monkeypatch)
    for i in range(2):
        vivo.append(_rec(f"f{i}"))
    vivo.append(_rec("y" * 700))  # segundo sellado
    segmentos = [s["segmento"] for s in vivo.segmentos()]
    assert nombre in segmentos and len(segmentos) == 2 and len(set(segmentos)) == 2
    assert all(vivo.verificar(s) for s in segmentos)
    cierres = [r for r in vivo.reconstruir() if r.get("evento") == "audit.linea_parcial_cerrada"]
    assert [c.get("fichero") for c in cierres] == ["audit.jsonl.manifest"], "constancia tambien via _sellar"


def test_manifiesto_sin_salto_final_entrada_completa_no_se_destruye_al_anotar_la_siguiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Corte que deja la entrada JSON COMPLETA pero sin '\\n': hoy es legible; la siguiente no debe romperla."""
    nombre, vivo = _sellar_con_manifiesto_cortado(tmp_path, monkeypatch, cuanto="salto")
    assert [s["segmento"] for s in vivo.segmentos()] == [nombre], "precondicion: la entrada ya es legible"
    vivo.append(_rec("g"))
    vivo.append(_rec("y" * 700))  # segundo sellado: anexa al manifiesto
    segmentos = [s["segmento"] for s in vivo.segmentos()]
    assert len(segmentos) == 2 and segmentos[0] == nombre, "la entrada previa sigue legible y no se duplica"
    recs = vivo.reconstruir()
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1))


def test_fallo_parcial_durante_la_reconciliacion_y_segundo_intento(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La reconciliacion tambien sufre una escritura parcial: falla en voz alta y el siguiente arranque recupera."""
    nombre, _ = _sellar_con_manifiesto_cortado(tmp_path, monkeypatch)
    ruta = tmp_path / "audit.jsonl"
    with monkeypatch.context() as m:
        _cortar_entrada_manifiesto(m)
        with pytest.raises(obs.ErrorEscrituraParcial):
            AuditLog(str(ruta))
    c = AuditLog(str(ruta))
    assert [s["segmento"] for s in c.segmentos()] == [nombre]
    assert c.verificar(nombre)
    recs = c.reconstruir()
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1))
    assert len([r for r in recs if r.get("evento") == "audit.segmento_reconciliado"]) == 1


def _plantar_corte(tmp_path: Path) -> tuple[bytes, str, str]:
    """Estado en disco que deja un proceso muerto (SIGKILL) a media anotacion, con historico valido previo:
    segmento 1-2 anotado; segmento 3-4 renombrado y su entrada cortada. Devuelve (bytes del manifiesto,
    sha256 del segmento historico, nombre del huerfano)."""
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta), umbral_bytes=UMBRAL)
    a.append(_rec("h1"))
    a.append(_rec("z" * 700))  # seq 1-2: sellado historico valido
    (historico,) = a.segmentos()
    for linea in (_rec("h3"), _rec("y" * 700)):
        (tmp_path / "huerfano.tmp").open("a").write(
            json.dumps({**linea, "ts": 0, "seq": 3 + (linea["msg"] != "h3")}) + "\n"
        )
    huerfano = "audit.jsonl.000000000003-000000000004"
    os.rename(tmp_path / "huerfano.tmp", tmp_path / huerfano)
    with _manifiesto(tmp_path).open("ab") as f:
        f.write(b'{"segmento": "audit.jsonl.0000000000')  # la entrada del 3-4, cortada por el SIGKILL
    return _manifiesto(tmp_path).read_bytes(), historico["sha256"], huerfano


def test_corte_tras_sigkill_con_historico_valido_recupera_sin_tocar_lo_previo(tmp_path: Path) -> None:
    previo, sha_historico, huerfano = _plantar_corte(tmp_path)
    b = AuditLog(str(tmp_path / "audit.jsonl"))
    segs = b.segmentos()
    assert [s["segmento"] for s in segs] == ["audit.jsonl.000000000001-000000000002", huerfano]
    assert segs[0]["sha256"] == sha_historico and all(b.verificar(s["segmento"]) for s in segs)
    assert _manifiesto(tmp_path).read_bytes().startswith(previo), "ningun byte historico se modifica"
    recs = b.reconstruir()
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1))
    assert [r["msg"] for r in recs][:2] == ["h1", "z" * 700], "lectura historica intacta tras recuperar"


def test_varios_escritores_reales_sobre_manifiesto_cortado_sin_perdida(tmp_path: Path) -> None:
    _previo, _sha, huerfano = _plantar_corte(tmp_path)
    ruta = tmp_path / "audit.jsonl"
    _lanzar_escritores(ruta, ["a", "b"], 150, umbral=4000)
    final = AuditLog(str(ruta), umbral_bytes=4000)
    recs = final.reconstruir()
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1)), "seq unico y contiguo"
    assert {f"{e}{i}" for e in "ab" for i in range(150)} <= {r["msg"] for r in recs}, "sin perdida"
    segs = [s["segmento"] for s in final.segmentos()]
    assert huerfano in segs and len(segs) == len(set(segs)) >= 4
    assert all(final.verificar(s) for s in segs)
    assert len([r for r in recs if r.get("evento") == "audit.segmento_reconciliado"]) == 1, "sin doble reconciliacion"


# --- Controles ----------------------------------------------------------------------------------


def test_control_manifiesto_intacto_no_se_toca_ni_deja_constancia(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    a = AuditLog(str(ruta), umbral_bytes=UMBRAL)
    a.append(_rec("z" * 700))
    previo = _manifiesto(tmp_path).read_bytes()
    a.append(_rec("y" * 700))
    assert _manifiesto(tmp_path).read_bytes().startswith(previo)
    assert len(_entradas_legibles(tmp_path)) == 2
    assert not any(r.get("evento") == "audit.linea_parcial_cerrada" for r in a.reconstruir())


def test_control_manifiesto_vacio_se_anota_sin_constancia(tmp_path: Path) -> None:
    ruta = tmp_path / "audit.jsonl"
    _manifiesto(tmp_path).write_bytes(b"")
    a = AuditLog(str(ruta), umbral_bytes=UMBRAL)
    a.append(_rec("z" * 700))
    assert len(a.segmentos()) == 1 and _manifiesto(tmp_path).read_bytes().count(b"\n") == 1
    assert not any(r.get("evento") == "audit.linea_parcial_cerrada" for r in a.reconstruir())
