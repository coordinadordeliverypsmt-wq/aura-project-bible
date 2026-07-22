"""MA.3 — Rotacion por archivo del audit log (D9: traza forense INMUTABLE, sin borrado).

La rotacion controla el crecimiento del almacenamiento SIN reducir la evidencia: el fichero activo
se sella en segmentos verificables; nada se elimina. Los conectores de senales resumen por un `seq`
persistente, no por el numero de lineas en memoria.

Invariantes (ver milestones/m3-entry/MA.3-diseno-rotacion-audit-log.md):
  I1 fichero activo acotado · I2 sin borrado · I3 integridad por segmento ·
  I4 reconstruccion completa sin huecos ni duplicados · I5 cursor robusto a rotacion y reinicio.
"""

import os

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.conectores.computador import ConectorComputador

_UMBRAL = 8 * 1024  # 8 KB: umbral pequeno para forzar varias rotaciones en la prueba


def _log(tmp_path, umbral=_UMBRAL):
    return obs.AuditLog(str(tmp_path / "audit.jsonl"), umbral_bytes=umbral)


def _accion(i):
    # module=computador + prefijo EJECUTA: lo que el ConectorComputador reconoce como patron de uso.
    return {"level": "ACT", "module": "computador", "msg": f"EJECUTA borrar_archivo_{i} " + "x" * 40, "audit": True}


# --- I1: el fichero activo no supera el umbral -----------------------------------
def test_el_fichero_activo_no_supera_el_umbral(tmp_path):
    log = _log(tmp_path)
    for i in range(2000):
        log.append(_accion(i))
    activo = os.path.getsize(str(tmp_path / "audit.jsonl"))
    assert activo <= _UMBRAL, f"el fichero activo ({activo} B) supera el umbral ({_UMBRAL} B): no hubo rotacion (I1)"


# --- I2: la rotacion no elimina ningun registro ----------------------------------
def test_la_rotacion_no_elimina_ningun_registro(tmp_path):
    log = _log(tmp_path)
    n = 2000
    for i in range(n):
        log.append(_accion(i))
    assert len(log.reconstruir()) == n, "la rotacion perdio registros: la traza forense debe seguir completa (D9/I2)"


# --- I3: integridad verificable por segmento -------------------------------------
def test_cada_segmento_tiene_integridad_verificable(tmp_path):
    log = _log(tmp_path)
    for i in range(2000):
        log.append(_accion(i))
    segmentos = log.segmentos()
    assert segmentos, "no se sello ningun segmento pese a superar el umbral (I3)"
    for s in segmentos:
        assert log.verificar(s["segmento"]) is True, f"segmento integro reportado como invalido: {s['segmento']}"
    # Alterar un byte de un segmento debe hacerlo detectable.
    ruta_seg = str(tmp_path / segmentos[0]["segmento"])
    with open(ruta_seg, "a", encoding="utf-8") as f:
        f.write("X")
    assert log.verificar(segmentos[0]["segmento"]) is False, "un segmento alterado debe fallar la verificacion (I3)"


# --- I4: reconstruccion completa sin huecos ni duplicados ------------------------
def test_reconstruccion_completa_sin_huecos_ni_duplicados(tmp_path):
    log = _log(tmp_path)
    n = 2000
    for i in range(n):
        log.append(_accion(i))
    registros = log.reconstruir()
    seqs = [r["seq"] for r in registros]
    assert len(registros) == n, "faltan o sobran registros al reconstruir (I4)"
    assert seqs == list(range(seqs[0], seqs[0] + n)), "los seq deben ser contiguos: sin huecos ni duplicados (I4)"


# --- I5a: el cursor no pierde ni duplica tras una rotacion -----------------------
@pytest.mark.asyncio
async def test_el_cursor_no_pierde_ni_duplica_tras_rotacion(tmp_path):
    log = _log(tmp_path, umbral=4 * 1024)
    for i in range(10):
        log.append(_accion(i))
    conector = ConectorComputador(str(tmp_path / "audit.jsonl"))
    primeras = await conector.recoger("t")
    assert len(primeras) == 10

    for i in range(200):  # fuerza al menos una rotacion mientras hay eventos sin procesar
        log.append(_accion(1000 + i))
    nuevas = await conector.recoger("t")
    assert len(nuevas) == 200, (
        "tras rotar, el conector debe ver EXACTAMENTE los nuevos eventos, ni perder ni duplicar (I5a). "
        "El cursor de lineas en memoria fallaria aqui."
    )


# --- I5b: el cursor sobrevive al reinicio ----------------------------------------
@pytest.mark.asyncio
async def test_el_cursor_sobrevive_al_reinicio(tmp_path):
    log = _log(tmp_path)
    for i in range(5):
        log.append(_accion(i))
    ruta = str(tmp_path / "audit.jsonl")

    primeras = await ConectorComputador(ruta).recoger("t")
    assert len(primeras) == 5

    tras_reinicio = await ConectorComputador(ruta).recoger("t")  # instancia nueva = reinicio del proceso
    assert tras_reinicio == [], "el cursor debe sobrevivir al reinicio: no reprocesar lo ya visto (I5b)"
