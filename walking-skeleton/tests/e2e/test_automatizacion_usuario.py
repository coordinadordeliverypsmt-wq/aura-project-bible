"""Criterio de aceptación del MVP capacidad 5 — automatización definida por el usuario (Bible 6.4).

El CEO fijó el criterio como una CONVERSACIÓN, no como una API:

    Usuario: "Siempre que borres un archivo, guarda antes una copia."
    AURA:    "Entendido. Lo haré a partir de ahora."
    Usuario: "Borra informe.pdf"
    AURA:    "Guardé una copia de informe.pdf y luego lo borré."
    --- reinicio de AURA ---
    Usuario: "Borra notas.txt"
    AURA:    "Guardé una copia de notas.txt y luego lo borré."

El reinicio es REAL: la segunda mitad de la prueba construye un sistema completamente nuevo
(orquestador, memoria, motor y almacén nuevos) que solo comparte con el primero el DISCO. Si la regla
viviera en memoria de proceso —o en el buffer de conversación, o en el prompt del LLM— la segunda
mitad fallaría.

El proveedor de modelo es un guion determinista que solo sabe traducir "borra X" a `borrar_archivo`:
NO sabe nada de reglas ni de copias. Así, todo lo que ocurra con la automatización es obra del núcleo
(ADR-0014), no del LLM.
"""

import json
import os
import uuid

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.core.reglas import AlmacenReglas
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter

USUARIO = "mauricio"


class _GuionBorrado:
    """Doble del proveedor: traduce "borra <archivo>" a `borrar_archivo`. No conoce las reglas."""

    name = "guion"
    healthy = True

    def __init__(self, base: str) -> None:
        self._base = base

    async def infer(self, prompt: str) -> str:
        nombre = prompt.split("Usuario:")[-1].strip().split()[-1]
        decision = {
            "intent": "borrar",
            "action": "borrar_archivo",
            "args": {"ruta": os.path.join(self._base, nombre)},
            "say": "Borro el archivo.",
        }
        return json.dumps(decision)


async def _aprobar(accion, args, trace_id):
    """El usuario confirma el borrado (lista roja). La copia es verde: no pasa por aquí."""
    return True


def _arrancar_aura(archivos, estado):
    """Arranque completo de AURA. Todo es nuevo salvo el disco: esto ES el reinicio."""
    registro = RegistroAdaptadores([AdaptadorComputador(raices=(str(archivos),))])
    permisos = PermissionManager(_aprobar)
    motor = MotorAutomatizacion(registro, permisos)
    return Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([_GuionBorrado(str(archivos))], 1200),
        permisos,
        VoiceAdapterMock(),
        registro,
        motor=motor,
        automatizaciones=AlmacenReglas(str(estado / "reglas.jsonl")),
    )


async def _decir(orq, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(USUARIO, texto, tid)
    return (await orq.wait(tid))["say"]


@pytest.fixture
def entorno(tmp_path):
    archivos = tmp_path / "archivos"
    archivos.mkdir()
    (archivos / "informe.pdf").write_text("informe de julio")
    (archivos / "notas.txt").write_text("notas sueltas")
    estado = tmp_path / "estado"
    return archivos, estado


@pytest.mark.asyncio
async def test_la_automatizacion_del_usuario_sobrevive_al_reinicio(entorno):
    """La conversación completa del criterio de aceptación, incluido el reinicio."""
    archivos, estado = entorno

    aura = _arrancar_aura(archivos, estado)
    assert await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.") == (
        "Entendido. Lo haré a partir de ahora."
    )

    say = await _decir(aura, "Borra informe.pdf")
    assert "Guardé una copia de informe.pdf y luego lo borré." in say
    assert not (archivos / "informe.pdf").exists(), "la acción del usuario debe haberse ejecutado"
    assert (archivos / "informe.pdf.copia").read_text() == "informe de julio", "la copia debe existir en disco"

    # --- reinicio de AURA: proceso nuevo, memoria nueva, conversación nueva; solo persiste el disco ---
    aura = _arrancar_aura(archivos, estado)

    say = await _decir(aura, "Borra notas.txt")
    assert "Guardé una copia de notas.txt y luego lo borré." in say
    assert not (archivos / "notas.txt").exists()
    assert (archivos / "notas.txt.copia").read_text() == "notas sueltas", "la regla siguió activa tras reiniciar"


@pytest.mark.asyncio
async def test_sin_regla_no_hay_copia(entorno):
    """CONTROL imprescindible: sin la automatización, borrar NO deja copia.

    Sin este control, la prueba anterior pasaría igual si el sistema copiara SIEMPRE, y no
    demostraría nada sobre la regla del usuario.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    say = await _decir(aura, "Borra informe.pdf")

    assert not (archivos / "informe.pdf").exists()
    assert not (archivos / "informe.pdf.copia").exists(), "copió sin que el usuario lo pidiera"
    assert "copia" not in say.lower(), "narró una copia que no hizo"


@pytest.mark.asyncio
async def test_el_usuario_puede_inspeccionar_sus_automatizaciones(entorno):
    """ "¿Qué automatizaciones tengo?" debe ser fiel al estado interno, antes y después de crear una."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    assert await _decir(aura, "¿Qué automatizaciones tengo?") == "No tienes ninguna automatización activa."

    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")

    # Tras reiniciar: lo que se inspecciona sale del disco, no de la conversación anterior.
    aura = _arrancar_aura(archivos, estado)
    say = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "1 automatización activa" in say
    assert "copia" in say.lower() and "borrar" in say.lower()
