"""Integración e2e (MVP Centro de Notificaciones): AURA registra lo que hace y se lo cuenta al usuario.

Demuestra el flujo de producto: el usuario pide acciones, AURA las ejecuta (o no), y más tarde puede
preguntar "¿qué ha pasado mientras no estaba?" y recibir un resumen EN LENGUAJE NATURAL de lo ocurrido.
"""

import json
import uuid

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.notificaciones import CentroNotificaciones
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _ProviderDemo:
    """Doble del proveedor: traduce la intención del usuario a una decisión (el LLM real no es el objeto)."""

    name = "demo"
    healthy = True

    def __init__(self, mapa: dict) -> None:
        self._mapa = mapa

    async def infer(self, prompt: str) -> str:
        u = prompt.split("Usuario:")[-1].lower()
        for clave, decision in self._mapa.items():
            if clave in u:
                return json.dumps(decision)
        return json.dumps({"action": "consulta", "args": {}, "say": "Entendido."})


def _sistema(tmp_path, mapa, confirmador):
    raices = (str(tmp_path),)
    registro = RegistroAdaptadores([AdaptadorComputador(raices=raices)])
    permisos = PermissionManager(confirmador)
    motor = MotorAutomatizacion(registro, permisos)
    centro = CentroNotificaciones(permisos=permisos, motor=motor)
    orq = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([_ProviderDemo(mapa)], 1200),
        permisos,
        VoiceAdapterMock(),
        registro,
        motor=motor,
        notificaciones=centro,
    )
    return orq, centro


async def _run(orq, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return await orq.wait(tid)


async def _aprobar(a, args, tid):
    return True


@pytest.mark.asyncio
async def test_aura_registra_una_accion_y_luego_la_cuenta(tmp_path):
    """Producto demostrable: acción ejecutada -> notificación en lenguaje natural -> el usuario la consulta."""
    (tmp_path / "informe.pdf").write_text("contenido")
    (tmp_path / "Descargas").mkdir()
    mapa = {
        "mueve": {
            "action": "mover_archivo",
            "args": {
                "origen": str(tmp_path / "informe.pdf"),
                "destino": str(tmp_path / "Descargas" / "informe.pdf"),  # ruta final que el motor requiere
            },
            "say": "Muevo el archivo.",
        }
    }
    orq, _ = _sistema(tmp_path, mapa, _aprobar)

    await _run(orq, "mueve informe.pdf a Descargas")  # AURA ejecuta y registra la notificación

    resp = await _run(orq, "¿que ha pasado mientras no estaba?")
    assert "Desde la última vez:" in resp["say"]
    assert "Moví informe.pdf a Descargas." in resp["say"]


@pytest.mark.asyncio
async def test_accion_detenida_por_confirmacion_se_comunica(tmp_path):
    """Una acción de lista roja que el usuario no confirma queda como notificación comunicable."""

    async def _rechazar(a, args, tid):
        return False

    mapa = {"borra": {"action": "borrar_archivo", "args": {"ruta": str(tmp_path / "x.txt")}, "say": "Voy a borrarlo."}}
    (tmp_path / "x.txt").write_text("x")
    orq, _ = _sistema(tmp_path, mapa, _rechazar)

    await _run(orq, "borra x.txt")
    resp = await _run(orq, "¿tengo algun aviso?")
    assert "No ejecuté una solicitud porque requería tu confirmación." in resp["say"]


@pytest.mark.asyncio
async def test_sin_actividad_no_inventa_avisos(tmp_path):
    """Si AURA no ha hecho nada, no fabrica notificaciones."""
    orq, _ = _sistema(tmp_path, {}, _aprobar)
    resp = await _run(orq, "¿que ha pasado?")
    assert "No ha pasado nada" in resp["say"]
