"""Alcanzabilidad de capacidades (M2.5, ALERTA-005). Prueba PERMANENTE del Quality Gate.

Que existe para impedir. ALERTA-004 y ALERTA-005 fueron el mismo fallo con un dia de diferencia:
algo declarado en un documento de arquitectura, ausente del codigo, invisible porque todas las
pruebas verificaban la pieza en aislamiento. M2 llego a tener 218 pruebas en verde con sus tres
componentes principales inalcanzables desde la conversacion.

Lo que verifica: que una peticion CONVERSACIONAL llega realmente al adaptador. No que las clases
existan, no que los contratos encajen: que el camino completo esta unido.

Diseno anti-falso-PASS:
  - Se recorre `registro.capacidades()`, no una lista escrita a mano. Registrar un adaptador nuevo
    sin cablearlo —o sin declarar como ejercitarlo— hace fallar el gate.
  - El espia DELEGA en el adaptador real, y para las operaciones con efecto se comprueba ademas el
    efecto en el sistema de archivos. Un espia roto que no delegara suspenderia esas dos pruebas.
  - Caso de control explicito: una accion sin adaptador NO puede reportarse como exito.
"""

import json
import uuid

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _ProveedorFijo:
    """Emite SIEMPRE la misma accion: aisla el cableado de la variabilidad del modelo."""

    def __init__(self, accion, args):
        self.name = "fijo"
        self._a, self._args = accion, args

    async def infer(self, prompt):
        return json.dumps({"intent": "x", "action": self._a, "args": self._args, "say": "hecho"})


async def _confirma(a, args, t):
    return True


def _args_para(accion, raiz):
    """Argumentos validos por capacidad. Un KeyError aqui = capacidad nueva sin cobertura."""
    d = raiz / "sub"
    return {
        "buscar_archivo": {"raiz": str(raiz), "patron": "*.txt"},
        "listar_directorio": {"ruta": str(raiz)},
        "leer_archivo": {"ruta": str(raiz / "datos.txt")},
        "abrir_archivo": {"ruta": str(raiz / "datos.txt")},
        "consultar_estado_sistema": {},
        "escribir_archivo": {"ruta": str(raiz / "nuevo.txt"), "contenido": "hola"},
        "borrar_archivo": {"ruta": str(raiz / "sobrante.txt")},
        # `copiar_archivo` recibe SOLO el origen: el destino (`<ruta>.copia`) lo deriva el adaptador.
        "copiar_archivo": {"ruta": str(raiz / "datos.txt")},
        "mover_archivo": {"origen": str(raiz / "mover.txt"), "destino": str(d / "mover.txt")},
        "renombrar_archivo": {"origen": str(raiz / "viejo.txt"), "destino": str(raiz / "nuevo2.txt")},
        "encender_dispositivo": {"device": "lampara"},
        "apagar_dispositivo": {"device": "lampara"},
    }[accion]


def _montar(tmp_path, accion, args):
    (tmp_path / "sub").mkdir(exist_ok=True)
    for nombre in ("datos.txt", "sobrante.txt", "mover.txt", "viejo.txt"):
        (tmp_path / nombre).write_text("contenido")

    computador = AdaptadorComputador(raices=(str(tmp_path),))
    registro = RegistroAdaptadores([computador, HomeAssistantMock()])

    llamadas = []
    for adaptador in registro.adaptadores:
        original = adaptador.execute

        def espia(cmd, a, tid, eid, _orig=original):
            llamadas.append(cmd)
            return _orig(cmd, a, tid, eid)  # DELEGA: el efecto real ocurre

        adaptador.execute = espia

    orch = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([_ProveedorFijo(accion, args)], 1200),
        PermissionManager(_confirma),
        VoiceAdapterMock(),
        registro,
    )
    return orch, llamadas, registro


def _capacidades():
    return sorted(RegistroAdaptadores([AdaptadorComputador(), HomeAssistantMock()]).capacidades())


@pytest.mark.asyncio
@pytest.mark.parametrize("accion", _capacidades())
async def test_toda_capacidad_es_alcanzable_desde_la_conversacion(accion, tmp_path):
    """Cada capacidad declarada debe poder ejercitarse hablando con AURA."""
    args = _args_para(accion, tmp_path)
    orch, llamadas, _ = _montar(tmp_path, accion, args)

    tid = uuid.uuid4().hex[:12]
    await orch.handle_utterance("u", "haz algo", tid)
    res = await orch.wait(tid)

    assert accion in llamadas, (
        f"la capacidad '{accion}' esta declarada pero NO es alcanzable desde la conversacion "
        f"(el adaptador nunca fue invocado). Respuesta: {res['say']!r}"
    )
    assert "ejecutada" in res["say"], f"se ejecuto pero no se informo como ejecutada: {res['say']!r}"


@pytest.mark.asyncio
async def test_efecto_real_de_una_operacion_destructiva(tmp_path):
    """Control del espia: no basta con que se llame, el efecto debe existir."""
    args = _args_para("borrar_archivo", tmp_path)
    orch, llamadas, _ = _montar(tmp_path, "borrar_archivo", args)
    objetivo = tmp_path / "sobrante.txt"
    assert objetivo.exists()

    await orch.handle_utterance("u", "borra eso", "T1")
    await orch.wait("T1")

    assert "borrar_archivo" in llamadas
    assert not objetivo.exists(), "el adaptador fue invocado pero el archivo sigue ahi"


@pytest.mark.asyncio
async def test_accion_sin_adaptador_no_se_reporta_como_exito(tmp_path):
    """CASO DE CONTROL (ALERTA-005 punto 4).

    `recordatorio` es lista verde y esta en el catalogo, pero ningun adaptador la atiende todavia.
    Antes de M2.5 el orquestador respondia con la frase del LLM y AURA afirmaba haberlo hecho.
    """
    orch, llamadas, _ = _montar(tmp_path, "recordatorio", {"texto": "comprar pan"})

    await orch.handle_utterance("u", "recuerdame comprar pan", "T2")
    res = await orch.wait("T2")

    assert llamadas == [], "ningun adaptador deberia haber sido invocado"
    assert "No pude ejecutar" in res["say"], f"exito sin evidencia de ejecucion: {res['say']!r}"
    assert "ejecutada" not in res["say"]
    assert "hecho" not in res["say"], "la frase de exito del modelo sobrevivio sin ejecucion real"


@pytest.mark.asyncio
async def test_capacidad_duplicada_se_rechaza_al_registrar(tmp_path):
    """Dos adaptadores con la misma capacidad: ambiguedad no resoluble en tiempo de ejecucion."""
    from aura_skeleton.core.registro import CapacidadDuplicada

    with pytest.raises(CapacidadDuplicada):
        RegistroAdaptadores([HomeAssistantMock(), HomeAssistantMock()])
