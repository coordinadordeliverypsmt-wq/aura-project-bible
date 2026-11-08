"""T9 — Cableado real de los avisos de NODO-01: la composición inyecta el puerto y el aviso llega al Centro.

Falla si `composicion.py` deja de inyectar el vigía (mutante M5) y si el Core pasa a abrir ficheros o a
importar adaptadores (frontera arquitectónica).
"""

from __future__ import annotations

import ast
import json
import time
import uuid
from pathlib import Path

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core import nodos as modulo_nodos
from aura_skeleton.core.nodos import RegistroNodos, construir_latido, validar_latido

ID_A = "a" * 32
ARR = "1" * 32


def _escribir_red(red, recibido_en, receptor_latido):
    latido = validar_latido(
        construir_latido(ID_A, "NODO-01", 1, ARR, 10.0, {"ram_mb": 986.0, "nucleos": 2.0}, (), "1.0")
    )
    reg = RegistroNodos()
    reg.registrar(latido, recibido_en)
    carpeta = Path(red) / "nodos"
    carpeta.mkdir(parents=True)
    contenido = {"receptor": {"latido": receptor_latido, "pid": 1}, "nodos": reg.a_dict()["nodos"]}
    (carpeta / "registro.json").write_text(json.dumps(contenido), encoding="utf-8")


def _config(tmp_path):
    return Configuracion(datos=str(tmp_path / "datos"), raices_permitidas=(str(tmp_path),), usar_stack_real=False)


def test_t9_la_composicion_entrega_el_aviso_de_caida_al_centro_de_notificaciones(tmp_path, monkeypatch):
    red = tmp_path / "red"
    ahora = time.time()
    caido = ahora - 3600.0
    _escribir_red(red, recibido_en=caido, receptor_latido=ahora)  # receptor vivo, nodo sin latido hace 1 h
    monkeypatch.setenv("AURA_RED", str(red))

    sistema = componer(_config(tmp_path))

    titulos = [n.titulo for n in sistema.notificaciones.listar()]
    esperado = f"Al abrir AURA: NODO-01 sin latido desde las {time.strftime('%H:%M %d-%m', time.localtime(caido))}"
    assert esperado in titulos
    avisos = [n for n in sistema.notificaciones.listar() if n.titulo == esperado]
    assert avisos[0].fuente == "aura" and avisos[0].prioridad == "alta"


def test_t9_una_segunda_evaluacion_del_orquestador_no_repite_el_aviso(tmp_path, monkeypatch):
    red = tmp_path / "red"
    ahora = time.time()
    _escribir_red(red, recibido_en=ahora - 3600.0, receptor_latido=ahora)
    monkeypatch.setenv("AURA_RED", str(red))
    sistema = componer(_config(tmp_path))
    antes = len(sistema.notificaciones.listar())

    sistema.orquestador.evaluar_nodos()

    assert len(sistema.notificaciones.listar()) == antes
    # y la supresión no la hizo el Centro por huella: la función no emitió nada
    assert sistema.notificaciones.suprimidas == 0


def test_t9_sin_red_declarada_no_hay_avisos_de_nodos(tmp_path):
    # conftest fija AURA_RED="" => sin vigía
    sistema = componer(_config(tmp_path))
    assert not [n for n in sistema.notificaciones.listar() if "sin latido" in n.titulo or "receptor" in n.titulo]


def test_t9_el_receptor_caido_se_avisa_en_la_composicion(tmp_path, monkeypatch):
    red = tmp_path / "red"
    ahora = time.time()
    _escribir_red(red, recibido_en=ahora, receptor_latido=ahora - 3600.0)
    monkeypatch.setenv("AURA_RED", str(red))

    sistema = componer(_config(tmp_path))

    titulos = [n.titulo for n in sistema.notificaciones.listar()]
    assert any(
        t.startswith("No se sabe el estado de los nodos: el receptor de HC-1 no está escuchando (detectado a las ")
        for t in titulos
    )


def test_t9_el_core_de_nodos_no_importa_adapters_ni_abre_ficheros():
    arbol = ast.parse(Path(modulo_nodos.__file__).read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            assert "adapters" not in (nodo.module or ""), "core/nodos.py importa un adaptador"
            assert nodo.level <= 1 or "adapters" not in (nodo.module or "")
        if isinstance(nodo, ast.Import):
            assert all("adapters" not in a.name for a in nodo.names)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id != "open", "core/nodos.py abre ficheros"


@pytest.mark.asyncio
async def test_t9_un_turno_real_evalua_los_nodos_y_avisa_de_la_caida_detectada_en_sesion(tmp_path, monkeypatch):
    """Mata M8: el aviso por turno tiene que llegar por el CAMINO DEL TURNO (`handle_utterance` → `on_turn`), no
    por una llamada directa a `evaluar_nodos()`. Al abrir el nodo está ONLINE (sin aviso); a mitad de sesión el
    registro deja de recibir latidos y el siguiente turno debe detectarlo."""
    red = tmp_path / "red"
    ahora = time.time()
    _escribir_red(red, recibido_en=ahora, receptor_latido=ahora)  # al abrir: ONLINE
    monkeypatch.setenv("AURA_RED", str(red))
    sistema = componer(_config(tmp_path))
    assert not [n for n in sistema.notificaciones.listar() if "NODO-01" in n.titulo]

    caido = ahora - 3600.0  # el receptor sigue vivo, pero el último latido del nodo envejece
    (red / "nodos" / "registro.json").unlink()
    (red / "nodos").rmdir()
    _escribir_red(red, recibido_en=caido, receptor_latido=time.time())

    tid = uuid.uuid4().hex[:12]
    await sistema.orquestador.handle_utterance("mauricio", "hola", tid)
    await sistema.orquestador.wait(tid)

    esperado = (
        f"Detectado en esta sesión: NODO-01 sin latido desde las {time.strftime('%H:%M %d-%m', time.localtime(caido))}"
    )
    assert esperado in [n.titulo for n in sistema.notificaciones.listar()]


def test_t9_segunda_caida_del_receptor_en_la_sesion_es_visible_en_el_centro_real(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from aura_skeleton.core import orchestrator as modulo_orq

    sistema = componer(_config(tmp_path))
    reloj = [2_000_000.0]
    estado = {"vivo": False}
    monkeypatch.setattr(modulo_orq, "time", SimpleNamespace(time=lambda: reloj[0]))
    sistema.orquestador.vigia_nodos = lambda ahora: (RegistroNodos(), estado["vivo"])
    sistema.orquestador._estado_nodos = None
    visibles_antes = len(sistema.notificaciones.listar())

    aceptados = [sistema.orquestador.evaluar_nodos()]  # cae
    reloj[0] += 7200.0
    estado["vivo"] = True
    aceptados.append(sistema.orquestador.evaluar_nodos())  # vuelve
    reloj[0] += 7200.0
    estado["vivo"] = False
    aceptados.append(sistema.orquestador.evaluar_nodos())  # cae otra vez

    del_receptor = [n for n in sistema.notificaciones.listar() if "receptor de HC-1" in n.titulo]
    assert len(del_receptor) == 2
    assert len({n.titulo for n in del_receptor}) == 2
    assert len(sistema.notificaciones.listar()) == visibles_antes + 2
    assert sistema.notificaciones.suprimidas == 0
    assert aceptados == [1, 0, 1]
