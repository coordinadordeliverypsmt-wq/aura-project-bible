"""Integracion: el Director delega TRABAJO REAL en el ejecutor QA y actualiza su estado.

CADENA QUE DEMUESTRA (CEO, 2026-08-03):
  Director -> asigna tarea al ejecutor QA -> el ejecutor verifica -> devuelve resultado estructurado
  -> el Director actualiza el Estado Operativo -> queda preparada la siguiente tarea.

Si esa cadena funciona, AURORA deja de coordinar tareas vacias y empieza a coordinar trabajo real.

Las pruebas ejecutan el ejecutor sobre un ARBOL TEMPORAL MINIMO, no sobre el repositorio: verificar el
repositorio desde dentro de su propia bateria de pruebas seria recursivo.
"""

import asyncio
import textwrap

import pytest

from aura_skeleton.adapters.qa import EjecutorQA
from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea


def _repo_minimo(tmp_path, aprueban=True):
    """Arbol de trabajo con una prueba que pasa o falla, segun se pida."""
    (tmp_path / "test_ejemplo.py").write_text(
        textwrap.dedent(f"def test_x():\n    assert {aprueban}\n"), encoding="utf-8"
    )
    (tmp_path / "quality-gate.sh").write_text(
        "#!/usr/bin/env bash\npython3 -m pytest -q --no-header\n", encoding="utf-8"
    )
    return EjecutorQA(raiz=str(tmp_path))


def test_el_ejecutor_devuelve_un_resultado_estructurado(tmp_path):
    """No texto libre: un dict que el Director pueda interpretar sin parsear prosa."""
    qa = _repo_minimo(tmp_path)

    res = asyncio.run(qa.execute("ejecutar_pruebas", {}, "t", "e"))

    assert res["capacidad"] == "ejecutar_pruebas"
    assert res["ok"] is True, f"las pruebas del arbol minimo deberian pasar: {res}"
    assert res["codigo_salida"] == 0
    assert res["resumen"], "el resultado debe traer un resumen accionable"


def test_el_ejecutor_reporta_el_fallo_sin_disfrazarlo(tmp_path):
    """INV-9: una verificacion que falla NO puede devolver ok=True."""
    qa = _repo_minimo(tmp_path, aprueban=False)

    res = asyncio.run(qa.execute("ejecutar_pruebas", {}, "t", "e"))

    assert res["ok"] is False, "una bateria en rojo no puede reportarse como correcta"
    assert res["codigo_salida"] != 0


def test_verificar_calidad_es_una_capacidad_distinta(tmp_path):
    qa = _repo_minimo(tmp_path)
    res = asyncio.run(qa.execute("verificar_calidad", {}, "t", "e"))
    assert res["capacidad"] == "verificar_calidad" and res["ok"] is True


def test_la_superficie_ejecutable_es_CERRADA(tmp_path):
    """Lo que no esta declarado no se ejecuta: no hay puerta al shell.

    Es la garantia que separa "ejecutar capacidades" de "ejecutar comandos".
    """
    qa = _repo_minimo(tmp_path)

    for intento in ("ejecutar_comando", "rm", "bash", "ejecutar_mutacion"):
        with pytest.raises(ValueError):
            asyncio.run(qa.execute(intento, {"cmd": "rm -rf /"}, "t", "e"))


def test_los_argumentos_NO_pueden_alterar_lo_que_se_ejecuta(tmp_path):
    """`args` no participa en construir el comando: un llamador no puede redirigir la verificacion."""
    qa = _repo_minimo(tmp_path)

    limpio = asyncio.run(qa.execute("ejecutar_pruebas", {}, "t", "e"))
    hostil = asyncio.run(qa.execute("ejecutar_pruebas", {"cmd": "echo hola", "cwd": "/", "args": ";rm"}, "t", "e"))

    assert limpio["ok"] == hostil["ok"] == True  # noqa: E712
    assert limpio["codigo_salida"] == hostil["codigo_salida"], "los argumentos alteraron la ejecucion"


def test_la_mutacion_NO_esta_autorizada_todavia(tmp_path):
    """Decision explicita del CEO: ante la duda, roja. La mutacion altera el arbol de trabajo."""
    qa = _repo_minimo(tmp_path)
    assert "ejecutar_mutacion" not in qa.capabilities, "capacidad no autorizada por el CEO"


def test_CADENA_COMPLETA_el_director_delega_trabajo_real_y_actualiza_su_estado(tmp_path):
    """LA EVIDENCIA QUE PIDIO EL CEO: coordinacion de trabajo real, de punta a punta."""
    repo = tmp_path / "repo"
    repo.mkdir()
    qa = _repo_minimo(repo)

    class MotorQA:
        """Motor minimo que despacha al adaptador, como hace el Motor Unico."""

        def __init__(self, adaptador):
            self.adaptador = adaptador

        async def ejecutar(self, accion, args, trace_id, event_id, origen):
            res = await self.adaptador.execute(accion, args, trace_id, event_id)
            return {
                "accion": accion,
                "estado": "ejecutada" if res["ok"] else "error",
                "motivo": res["resumen"],
                "resultado": res,
            }

    alm = AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl"))
    alm.registrar(
        Tarea(
            objetivo_id="obj", tarea_id="t-01", descripcion="verificar la calidad", estado="abierta", responsable="qa"
        )
    )
    alm.registrar(
        Tarea(
            objetivo_id="obj",
            tarea_id="t-02",
            descripcion="documentar el resultado",
            estado="abierta",
            responsable="documentacion",
        )
    )

    d = DirectorGeneral(alm, MotorQA(qa), RegistroEjecutores({"qa": "verificar_calidad"}))
    hecha = asyncio.run(d.ciclo("obj", trace_id="t"))

    # 1. el Director asigno la tarea al ejecutor QA y 2. el ejecutor verifico de verdad
    assert hecha.estado == "terminada", f"la verificacion real no cerro la tarea: {hecha.bloqueos}"
    # 3. resultado estructurado convertido en evidencia persistida
    assert any("verificar_calidad" in e for e in hecha.evidencias), "no registro evidencia del trabajo real"
    # 4. el Estado Operativo quedo actualizado en disco
    assert AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl")).tarea("obj", "t-01").estado == "terminada"
    # 5. la siguiente tarea quedo preparada
    assert "t-02" in hecha.proxima_accion, f"no preparo la siguiente: {hecha.proxima_accion!r}"


def test_el_director_no_sabe_como_se_verifica(tmp_path):
    """DESACOPLAMIENTO: el Director solo conoce responsables y capacidades, nunca herramientas."""
    import inspect

    from aura_skeleton.core import director

    fuente = inspect.getsource(director)
    for herramienta in ("pytest", "quality-gate", "subprocess", "bash", "EjecutorQA"):
        assert herramienta not in fuente, f"el Director conoce la herramienta {herramienta!r}"
