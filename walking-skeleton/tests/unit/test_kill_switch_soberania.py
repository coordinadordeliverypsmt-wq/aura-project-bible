"""Unit: la parada de emergencia alcanza TAMBIEN a la soberania del modelo de usuario.

ALERTA-006: el kill switch solo se comprobaba dentro de `PermissionManager.authorize`, y la cascada de
soberania no pasa por ahi. Con la parada ECHADA, AURA seguia borrando datos del usuario. Bible 5.3 §5
y RN-3 no admiten excepciones: cuando esta activado, NINGUNA accion se ejecuta.
"""

import os

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


def _mu(mem, kill=None):
    """`ModeloUsuario` cableado al MOTOR UNICO (F4, 2026-08-25).

    La ruta de soberania dejo de mutar el almacen directamente. **Sin motor no muta**, asi que un
    fixture que construya `ModeloUsuario(mem)` a secas haria pasar la prueba en vacio. El veredicto
    que cada prueba mide no cambia: se completa el cableado que la migracion hizo obligatorio.
    """
    return ModeloUsuario(mem, motor=MotorAutomatizacion(
        EjecutorModeloUsuario(mem), PermissionManager(_confirmar_mu, kill_switch=kill)))


async def _confirmar_mu(accion, args, trace_id):
    return True



async def _si(a, args, tid):
    return True


def _orq(tmp_path, armado):
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    ks = KillSwitch(os.path.join(tmp_path, "KILL"))
    if armado:
        ks.engage()
    return (
        Orchestrator(
            InProcessEventBus(),
            mem,
            ModelRouter([MockProvider("m", 1)], 1200),
            PermissionManager(_si, kill_switch=ks),
            VoiceAdapterMock(),
            HomeAssistantMock(),
            modelo_usuario=_mu(mem, locals().get("kill")),
        ),
        mem,
        ks,
    )


async def _sembrar(mem):
    await mem.write("u", "semantica", "tiene alergia a la penicilina", {"origen": "declarada"})


@pytest.mark.asyncio
async def test_con_la_parada_ARMADA_no_se_borra_nada(tmp_path):
    orq, mem, _ = _orq(str(tmp_path), armado=True)
    await _sembrar(mem)

    resp = await orq._atender_modelo_usuario("u", "Olvida lo de la penicilina.")

    assert "detenido" in (resp or "").lower(), f"debe declarar que esta detenido: {resp!r}"
    quedan = [e["contenido"] for e in await _mu(mem).ver("u")]
    assert any("penicilina" in c for c in quedan), "con la parada echada NO puede borrarse un dato"


@pytest.mark.asyncio
async def test_con_la_parada_ARMADA_no_se_refuta_nada(tmp_path):
    orq, mem, _ = _orq(str(tmp_path), armado=True)
    await _sembrar(mem)

    await orq._atender_modelo_usuario("u", "Lo de la penicilina ya no es cierto.")

    assert not any(e.get("refutada") for e in await _mu(mem).ver("u")), "refutar tambien muta"


@pytest.mark.asyncio
async def test_INSPECCIONAR_sigue_permitido_con_la_parada_armada(tmp_path):
    """CONTROL: leer no muta. La parada impide MODIFICAR, no consultar."""
    orq, mem, _ = _orq(str(tmp_path), armado=True)
    await _sembrar(mem)

    resp = await orq._atender_modelo_usuario("u", "Que sabes de mi?")

    assert "penicilina" in (resp or ""), f"consultar debe seguir funcionando: {resp!r}"


@pytest.mark.asyncio
async def test_CONTROL_al_desarmar_el_olvido_vuelve_a_funcionar(tmp_path):
    """Sin este control, todo lo anterior pasaria con un sistema que nunca borra."""
    orq, mem, ks = _orq(str(tmp_path), armado=True)
    await _sembrar(mem)
    ks.disengage()

    resp = await orq._atender_modelo_usuario("u", "Olvida lo de la penicilina.")

    assert "hecho" in (resp or "").lower(), f"al desarmar debe volver a funcionar: {resp!r}"
    assert not [e for e in await _mu(mem).ver("u")], "el olvido debe surtir efecto"
