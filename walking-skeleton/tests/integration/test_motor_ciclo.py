"""Integracion: AURORA se coordina de forma CONTINUA por si misma, sin que nadie pida cada vuelta.

Hasta este incremento, `DirectorGeneral.ciclo()` no lo invocaba nadie en el paquete: cada vuelta
existia porque un modelo externo la pedia. Estas pruebas demuestran que el latido ya es propio.
"""

import asyncio

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.motor_ciclo import _MAX_FALLOS_CONSECUTIVOS, FallosConsecutivosExcedidos, MotorDelCiclo


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


# --- Servicio permanente: una excepcion en un latido no puede matar el demonio en silencio --------


class DirectorInestable:
    """Test double: falla en los latidos indicados por numero de llamada (1-indexado).

    `tras_agotar` es una VALVULA DE SEGURIDAD para las pruebas: si la llamada indicada se alcanza sin
    que el servicio se haya detenido antes por su cuenta, se lanza `CancelledError` para cortar el
    bucle. Sin ella, una implementacion que NO detenga el servicio como debería (el defecto que un
    mutante degrada a proposito) dejaria el `while True` de `servir` girando para siempre con
    `espera_s=0`: la prueba colgaria en vez de fallar. Con la valvula, una implementacion incorrecta
    sigue terminando -en desacuerdo con lo que la prueba espera- en vez de no terminar nunca.
    """

    def __init__(self, fallos_en: set[int], tras_agotar: int) -> None:
        self.llamada = 0
        self.fallos_en = set(fallos_en)
        self.tras_agotar = tras_agotar

    async def ciclo(self, objetivo_id: str, trace_id: str = "-"):
        self.llamada += 1
        if self.llamada in self.fallos_en:
            raise RuntimeError(f"fallo simulado en el latido {self.llamada}")
        if self.llamada >= self.tras_agotar:
            raise asyncio.CancelledError  # valvula de seguridad: corta para poder observar el resultado
        return None


def test_un_latido_con_excepcion_no_mata_el_servicio_y_queda_registrado():
    """DEFECTO CORREGIDO: antes, una excepcion en `director.ciclo` mataba `servir` EN SILENCIO (nadie
    lo invocaba fuera de las pruebas, asi que daba igual). Con proceso propio, un demonio que muere
    callado ante su primer error es peor que no tener demonio. Ahora debe quedar registrado en el
    audit log y el servicio debe seguir con el siguiente latido."""
    director = DirectorInestable(fallos_en={2}, tras_agotar=4)
    ciclo = MotorDelCiclo(director, espera_s=0, dormir=_no_dormir)
    registros_previos = len(obs._records)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ciclo.servir("obj"))

    assert director.llamada == 4, "el fallo del latido 2 debio dejar seguir latiendo hasta la valvula de seguridad"
    nuevos = obs._records[registros_previos:]
    assert any(
        r.get("audit") and r.get("level") == "ERROR" and "fallido" in r.get("msg", "").lower() for r in nuevos
    ), "la excepcion del latido debe quedar en el registro de auditoria, no perderse en silencio"


def test_N_fallos_consecutivos_detienen_el_servicio():
    """Un demonio no puede girar en vacio para siempre sobre un fallo estructural quemando CPU: tras
    `_MAX_FALLOS_CONSECUTIVOS` latidos seguidos en error, el servicio debe detenerse (con ruido, no en
    silencio)."""
    director = DirectorInestable(
        fallos_en=set(range(1, _MAX_FALLOS_CONSECUTIVOS + 1)), tras_agotar=_MAX_FALLOS_CONSECUTIVOS + 5
    )
    ciclo = MotorDelCiclo(director, espera_s=0, dormir=_no_dormir)

    with pytest.raises(FallosConsecutivosExcedidos):
        asyncio.run(ciclo.servir("obj"))

    assert director.llamada == _MAX_FALLOS_CONSECUTIVOS, (
        f"debio detenerse justo al {_MAX_FALLOS_CONSECUTIVOS}-esimo fallo consecutivo, "
        f"pero siguio hasta la llamada {director.llamada} (la valvula de seguridad no debio alcanzarse)"
    )


def test_un_latido_exitoso_reinicia_el_contador_de_fallos_consecutivos():
    """CONTROL del anterior: sin el reinicio, una racha de fallos NUNCA consecutivos (intercalados con
    exitos) tumbaria igual el servicio en cuanto la CUENTA TOTAL de fallos alcanzara el umbral -- que
    es exactamente lo que un contador que no se reinicia haria pasar la prueba anterior por la razon
    equivocada. Aqui se intercalan mas fallos que el umbral, ninguno en racha, y el servicio NO debe
    detenerse por eso."""
    total_llamadas = _MAX_FALLOS_CONSECUTIVOS * 4  # el doble de fallos que el umbral, todos aislados
    fallos_en = {n for n in range(1, total_llamadas + 1) if n % 2 == 1}
    director = DirectorInestable(fallos_en=fallos_en, tras_agotar=total_llamadas)
    ciclo = MotorDelCiclo(director, espera_s=0, dormir=_no_dormir)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ciclo.servir("obj"))

    assert director.llamada == total_llamadas, (
        "una racha de fallos aislados (nunca dos seguidos) no debe detener el servicio: si el contador "
        f"no se reiniciara tras cada exito, se habria detenido mucho antes de la llamada {total_llamadas}"
    )
