"""Integracion: el estado del ciclo tambien esta gobernado (D-M-8, ultima excepcion estructural).

Era la unica mutacion persistente que escapaba al control: el Director transitaba tareas sin que el
kill switch las alcanzara, de modo que el sistema con el que AURORA evoluciona era el unico fuera de
su propio gobierno. Bible 5.3 §5 y RN-3 no admiten excepciones.
"""

import asyncio
import tempfile

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea, TransicionInvalida
from aura_skeleton.core.kill_switch import KillSwitch


def _almacen(tmp_path, armado):
    ks = KillSwitch(str(tmp_path / "KILL"))
    if armado:
        ks.engage()
    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"), kill_switch=ks)
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta"))
    return alm, ks


def test_con_la_parada_ARMADA_no_se_muta_el_estado_del_trabajo(tmp_path):
    alm, _ = _almacen(tmp_path, armado=True)
    with pytest.raises(TransicionInvalida, match="kill switch"):
        alm.transitar("o", "t-01", "terminada", autoridad="director", causa="x")
    assert alm.tarea("o", "t-01").estado == "abierta", "la tarea no puede haber cambiado"


def test_CONTROL_al_desarmar_las_transiciones_vuelven_a_funcionar(tmp_path):
    """Sin este control, lo anterior pasaria con un sistema que nunca transita."""
    alm, ks = _almacen(tmp_path, armado=True)
    ks.disengage()
    assert alm.transitar("o", "t-01", "terminada", autoridad="director", causa="ok").estado == "terminada"


def test_el_DIRECTOR_tampoco_puede_avanzar_con_la_parada_armada(tmp_path):
    """El gobierno alcanza al ciclo completo, no solo a una llamada directa."""
    from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores

    class Motor:
        async def ejecutar(self, *a, **k):
            return {"estado": "ejecutada"}

    alm, _ = _almacen(tmp_path, armado=True)
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-02", estado="abierta", responsable="qa"))
    d = DirectorGeneral(alm, Motor(), RegistroEjecutores({"qa": "verificar_calidad"}))

    with pytest.raises(TransicionInvalida):
        asyncio.run(d.ciclo("o"))


def test_el_arranque_real_cablea_el_kill_switch_al_estado():
    """La garantia debe existir en produccion, no solo en las pruebas."""
    s = componer(Configuracion(datos=tempfile.mkdtemp()))
    assert s.estado_operativo._kill is s.kill_switch, "el estado del ciclo debe compartir la parada del sistema"
