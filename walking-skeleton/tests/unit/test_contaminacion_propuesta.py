"""Una propuesta del modelo no contamina nada (D-FC-8 = B, CEO 2026-09-13). PRUEBA CRÍTICA.

El riesgo que cierra: el modelo local dice una falsedad en el turno 1. Si esa frase entrara en la
memoria, en el modelo de usuario o en las señales, o reentrara desnuda en el prompt del turno 2, AURA
acabaría tratándola como algo que ella misma afirmó —y la reforzaría turno a turno—.

Lo que se demuestra, por ejecución y con proveedor espía:

1. turno 1 sale PROPUESTA y con la marca del Core;
2. la falsedad NO está en el almacén, ni en `modelo_usuario.ver`, ni la vio la captura de señales;
3. en el prompt del turno 2 aparece SOLO en una línea `[PROPUESTA_NO_VERIFICADA]`, nunca en
   `[contexto memoria]`;
4. una consulta posterior sobre el usuario sigue en AUSENCIA con 0 llamadas.
"""

from __future__ import annotations

import json
import uuid

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import ConectorConversacion
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.contexto import RegistroContexto
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.estatus import ETIQUETA_CONTEXTO, MARCA_PROPUESTA, Estatus
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import ModelRouter

FALSEDAD = "LA INFORMACIÓN FALSA XYZ"
MARCADOR = "XYZ"


class _Espia:
    name = "espia"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.prompts.append(prompt)
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": FALSEDAD})


class _ContextoEspia(RegistroContexto):
    """La captura de señales REAL, con registro de lo que se le da a observar."""

    def __init__(self, fuentes) -> None:
        super().__init__(fuentes)
        self.observado: list[str] = []

    def observar(self, texto):
        self.observado.append(texto)
        return super().observar(texto)


async def _si(accion, args, trace_id):
    return True


def _sistema(tmp_path):
    # Almacen de PRODUCCION, persistido en disco: la contaminacion que importa es la que sobrevive.
    mem = PersistentMemory(str(tmp_path / "memoria.json"))
    perm = PermissionManager(_si)
    registro = RegistroAdaptadores()
    registro.registrar(EjecutorModeloUsuario(mem))
    motor = MotorAutomatizacion(registro, perm)
    espia = _Espia()
    contexto = _ContextoEspia([ConectorConversacion()])
    orq = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([espia], 1200),
        perm,
        VoiceAdapterMock(),
        HomeAssistantMock(),
        motor=motor,
        contexto=contexto,
        modelo_usuario=ModeloUsuario(mem, motor=motor),
    )
    return orq, mem, espia, contexto


async def _turno(orq, texto: str, uid: str = "u") -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


def _en_memoria(mem: PersistentMemory, fragmento: str) -> list:
    """En RAM y en el fichero persistido."""
    en_ram = [i for i in mem._items if fragmento in json.dumps(i, ensure_ascii=False)]
    try:
        with open(mem._path, encoding="utf-8") as f:
            en_disco = [linea for linea in f if fragmento in linea]
    except FileNotFoundError:
        en_disco = []
    return en_ram + en_disco


async def test_una_propuesta_falsa_no_contamina_memoria_senales_ni_contexto(tmp_path):
    orq, mem, espia, contexto = _sistema(tmp_path)

    # --- control de cableado: la captura de señales y la memoria ESTÁN vivas. Sin esto, «XYZ no está
    #     en memoria» pasaría por vacuidad con un almacén que nunca escribe nada.
    await _turno(orq, "Mi color favorito es el azul")
    assert _en_memoria(mem, "azul"), "guarda: la vía real de memoria debía escribir la declaración"
    assert any("azul" in e["contenido"] for e in await orq.modelo_usuario.ver("u")), (
        "guarda: la captura de señales debía llevar la declaración al modelo de usuario"
    )
    llamadas_previas = len(espia.prompts)

    # --- turno 1: pregunta factual del mundo, no sensible -> el modelo devuelve la falsedad.
    r1 = await _turno(orq, "que es la fotosintesis?")
    assert len(espia.prompts) == llamadas_previas + 1, "guarda: el turno 1 debía llegar al modelo"
    assert r1["estatus"] == Estatus.PROPUESTA.value
    assert r1["say"] == f"{MARCA_PROPUESTA} {FALSEDAD}"

    # --- 2 · ningún almacén la contiene.
    assert not _en_memoria(mem, MARCADOR), "el say del modelo entró en memoria"
    assert not [e for e in await orq.modelo_usuario.ver("u") if MARCADOR in json.dumps(e, ensure_ascii=False)]
    assert not [t for t in contexto.observado if MARCADOR in t], "la captura de señales vio el say del modelo"
    assert any("fotosintesis" in t for t in contexto.observado), "control: la captura sí ve al USUARIO"

    # --- turno 2: pregunta relacionada -> vuelve al modelo con la conversación reciente.
    r2 = await _turno(orq, "y para que sirve la fotosintesis?")
    assert r2["estatus"] == Estatus.PROPUESTA.value
    prompt2 = espia.prompts[-1]
    assert MARCADOR in prompt2, "control: la propuesta SÍ reentra como contexto (D-FC-8 = B)"

    lineas_con_marcador = [linea for linea in prompt2.splitlines() if MARCADOR in linea]
    etiqueta = f"AURA [{ETIQUETA_CONTEXTO[Estatus.PROPUESTA]}]: {FALSEDAD}"
    assert lineas_con_marcador and all(etiqueta in linea for linea in lineas_con_marcador), lineas_con_marcador
    assert "AURA: " not in prompt2, "ningún turno previo puede reentrar sin etiqueta"
    contexto_memoria = prompt2.split("[conversacion reciente:")[0]
    assert "[contexto memoria:" in contexto_memoria and MARCADOR not in contexto_memoria
    # La marca visible NO se duplica en el contexto: se guarda el say sin marca y se etiqueta aparte.
    assert MARCA_PROPUESTA not in prompt2

    # --- 4 · la memoria personal sigue intacta: ausencia, 0 llamadas.
    antes = len(espia.prompts)
    r3 = await _turno(orq, "como me llamo?")
    assert r3["estatus"] == Estatus.AUSENCIA.value and len(espia.prompts) == antes
    r4 = await _turno(orq, "como se llama mi hija?")  # pared de ADR-0014 con memoria NO vacia
    assert r4["estatus"] == Estatus.AUSENCIA.value and len(espia.prompts) == antes
    assert not _en_memoria(mem, MARCADOR)
