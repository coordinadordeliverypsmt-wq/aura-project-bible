"""Integracion: AURORA se coordina de forma CONTINUA por si misma, sin que nadie pida cada vuelta.

Hasta este incremento, `DirectorGeneral.ciclo()` no lo invocaba nadie en el paquete: cada vuelta
existia porque un modelo externo la pedia. Estas pruebas demuestran que el latido ya es propio.
"""

import asyncio

import pytest

from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.motor_ciclo import MotorDelCiclo


class MotorOK:
    def __init__(self):
        self.ejecutadas = []

    async def ejecutar(self, accion, args, trace_id, event_id, origen):
        self.ejecutadas.append(accion)
        return {"accion": accion, "estado": "ejecutada"}


class KillSwitchFalso:
    def __init__(self, armado=False):
        self.armado = armado

    def is_engaged(self):
        return self.armado


def _sistema(tmp_path, n=3, kill=None):
    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    for i in range(1, n + 1):
        alm.registrar(Tarea(objetivo_id="obj", tarea_id=f"t-{i:02d}", estado="abierta", responsable="qa"))
    motor = MotorOK()
    d = DirectorGeneral(alm, motor, RegistroEjecutores({"qa": "verificar_calidad"}))
    return MotorDelCiclo(d, kill_switch=kill, espera_s=0, dormir=_no_dormir), alm, motor


async def _no_dormir(_s):
    return None


def test_aurora_atiende_TODO_su_backlog_sin_que_nadie_pida_cada_vuelta(tmp_path):
    """LA CAPACIDAD: una sola llamada y el sistema trabaja hasta agotar el trabajo."""
    ciclo, alm, motor = _sistema(tmp_path, n=3)

    atendidas = asyncio.run(ciclo.correr("obj"))

    assert atendidas == 3, f"debia atender las 3 tareas del backlog, atendio {atendidas}"
    assert len(motor.ejecutadas) == 3, "cada tarea debe haberse despachado por el motor"
    assert alm.abiertas("obj") == [], "no puede quedar trabajo accionable"


def test_se_detiene_solo_cuando_no_queda_trabajo(tmp_path):
    """CONTROL: no gira en vacio. Un bucle que no sabe parar consume la maquina."""
    ciclo, _, motor = _sistema(tmp_path, n=1)

    asyncio.run(ciclo.correr("obj"))
    otra = asyncio.run(ciclo.correr("obj"))

    assert otra == 0, "sin trabajo pendiente no puede atender nada"
    assert len(motor.ejecutadas) == 1, "no puede reejecutar trabajo ya terminado"


def test_EL_KILL_SWITCH_ARMADO_IMPIDE_LATIR(tmp_path):
    """Bible 5.3 §5 / RN-3: con la parada de emergencia echada, AURORA no arranca trabajo.

    Se comprueba ANTES de latir, no solo dentro del motor de ejecucion: un latido que arranca trabajo
    con el switch armado seria una ruta que lo esquiva — el defecto que ALERTA-006 encontro.
    """
    kill = KillSwitchFalso(armado=True)
    ciclo, alm, motor = _sistema(tmp_path, n=3, kill=kill)

    atendidas = asyncio.run(ciclo.correr("obj"))

    assert atendidas == 0, "con el kill switch armado no puede atenderse ninguna tarea"
    assert motor.ejecutadas == [], "no puede despacharse NADA con la parada de emergencia echada"
    assert len(alm.abiertas("obj")) == 3, "el backlog debe quedar intacto"


def test_al_desarmar_el_kill_switch_el_ciclo_se_reanuda(tmp_path):
    """CONTROL NEGATIVO del anterior: sin este, la prueba pasaria con un sistema que nunca trabaja."""
    kill = KillSwitchFalso(armado=True)
    ciclo, _, motor = _sistema(tmp_path, n=2, kill=kill)

    assert asyncio.run(ciclo.correr("obj")) == 0
    kill.armado = False
    assert asyncio.run(ciclo.correr("obj")) == 2, "al desarmar, el trabajo pendiente debe atenderse"


def test_un_latido_aislado_respeta_el_kill_switch(tmp_path):
    ciclo, _, motor = _sistema(tmp_path, n=1, kill=KillSwitchFalso(armado=True))
    assert asyncio.run(ciclo.latir("obj")) is None
    assert motor.ejecutadas == []


def test_max_latidos_acota_la_corrida(tmp_path):
    """Red frente a un objetivo que se realimente: la corrida puede acotarse."""
    ciclo, alm, _ = _sistema(tmp_path, n=5)

    assert asyncio.run(ciclo.correr("obj", max_latidos=2)) == 2
    assert len(alm.abiertas("obj")) == 3, "solo debian atenderse dos tareas"


def test_servir_espera_en_vez_de_girar_en_vacio(tmp_path):
    """Sin trabajo, el bucle permanente DUERME. Un bucle que no espera quema la maquina."""
    esperas = []

    async def contar(s):
        esperas.append(s)
        if len(esperas) >= 3:
            raise asyncio.CancelledError  # se corta para poder observarlo

    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    d = DirectorGeneral(alm, MotorOK(), RegistroEjecutores({}))
    ciclo = MotorDelCiclo(d, espera_s=7, dormir=contar)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ciclo.servir("obj"))

    assert esperas == [7, 7, 7], f"debe esperar el intervalo configurado entre sondeos: {esperas}"


def test_el_motor_del_ciclo_no_conoce_las_tareas(tmp_path):
    """DESACOPLAMIENTO: su unica responsabilidad es el latido; la logica vive en el Director."""
    import inspect

    from aura_skeleton.core import motor_ciclo

    fuente = inspect.getsource(motor_ciclo)
    for concepto in ("Tarea", "responsable", "evidencia", "prioridad", "AlmacenEstadoOperativo"):
        assert concepto not in fuente, f"el Motor del Ciclo conoce '{concepto}': logica en el sitio equivocado"
