"""Unit: metricas basicas de observabilidad (contrato P-ARQ-7 / Bible 7.4, Plan de Calidad §3).

A2 cablea el subsistema de metricas —que existia sin llamadores (D42)— en sus puntos de emision
REALES: el bus (eventos publicados) y el gestor de permisos (acciones autorizadas/denegadas). Las
metricas son observabilidad interna, local y en memoria (ADR-0001/D24), NO una API publica ni un
contrato para consumidores externos.

Comportamiento observable, medido por DELTA para ser robusto al estado global del modulo (no depende
del orden de ejecucion de la suite). Validado por mutacion: si un punto de emision deja de
incrementar, la asercion del delta correspondiente falla.
"""

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.contracts import Event
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.permissions import PermissionManager


async def _confirm_yes(a, args, t):
    return True


async def _confirm_no(a, args, t):
    return False


@pytest.mark.asyncio
async def test_publish_incrementa_eventos_publicados():
    """Cada evento que sale por el bus (E1, ADR-0018) cuenta como eventos.publicados."""
    bus = InProcessEventBus()
    antes = obs.metrics().get("eventos.publicados", 0.0)
    await bus.publish(Event("perception.turn_end", "T1", "u", {}))
    await bus.publish(Event("perception.turn_end", "T2", "u", {}))
    despues = obs.metrics().get("eventos.publicados", 0.0)
    assert despues - antes == 2.0


@pytest.mark.asyncio
async def test_lista_verde_incrementa_autorizadas():
    pm = PermissionManager(_confirm_no)
    antes = obs.metrics().get("acciones.autorizadas", 0.0)
    ok, _ = await pm.authorize("consulta", {}, "t")  # verde -> auto-ejecucion
    despues = obs.metrics().get("acciones.autorizadas", 0.0)
    assert ok is True and despues - antes == 1.0


@pytest.mark.asyncio
async def test_lista_roja_confirmada_incrementa_autorizadas():
    pm = PermissionManager(_confirm_yes)  # el usuario confirma
    antes = obs.metrics().get("acciones.autorizadas", 0.0)
    ok, _ = await pm.authorize("pago", {}, "t")  # roja confirmada -> autorizada
    despues = obs.metrics().get("acciones.autorizadas", 0.0)
    assert ok is True and despues - antes == 1.0


@pytest.mark.asyncio
async def test_lista_roja_denegada_incrementa_denegadas():
    pm = PermissionManager(_confirm_no)  # el usuario deniega
    antes = obs.metrics().get("acciones.denegadas", 0.0)
    ok, _ = await pm.authorize("borrar_archivo", {}, "t")  # roja denegada
    despues = obs.metrics().get("acciones.denegadas", 0.0)
    assert ok is False and despues - antes == 1.0


@pytest.mark.asyncio
async def test_accion_desconocida_incrementa_denegadas():
    pm = PermissionManager(_confirm_yes)
    antes = obs.metrics().get("acciones.denegadas", 0.0)
    ok, _ = await pm.authorize("accion_inexistente", {}, "t")  # deny por defecto
    despues = obs.metrics().get("acciones.denegadas", 0.0)
    assert ok is False and despues - antes == 1.0


@pytest.mark.asyncio
async def test_kill_switch_incrementa_denegadas(tmp_path):
    ks = KillSwitch(trigger_file=str(tmp_path / "KILL"))
    ks.engage("prueba")
    pm = PermissionManager(_confirm_yes, kill_switch=ks)
    antes = obs.metrics().get("acciones.denegadas", 0.0)
    ok, _ = await pm.authorize("consulta", {}, "t")  # bloqueada por kill switch
    despues = obs.metrics().get("acciones.denegadas", 0.0)
    assert ok is False and despues - antes == 1.0


def test_evolucion_aditiva_por_nombre():
    """Condicion CEO: incorporar una metrica nueva no altera las existentes."""
    a = obs.metrics().get("eventos.publicados", 0.0)
    b = obs.metrics().get("acciones.denegadas", 0.0)
    obs.metric_inc("metrica.futura.hipotetica")  # una metrica nueva cualquiera
    assert obs.metrics().get("eventos.publicados", 0.0) == a
    assert obs.metrics().get("acciones.denegadas", 0.0) == b
