"""Un hecho declarado lo responde el Core, con su valor exacto y sin pasar por el modelo.

**El defecto que cierra esta prueba, medido a través del producto** (2026-09-10). El usuario declaró
«Mi color favorito es el azul» y, al preguntar «¿Cuál es mi color favorito?», AURA respondió tras
**129,02 s**: «Mis preferencias personales incluyen la agradable amarilla, la apacible llena y la
hermosa amarillo.» El hecho correcto estaba en el `recall` y viajó en el prompt: **el modelo lo deformó
al redactarlo**. La autoridad era del Core; la redacción, del modelo — y un modelo de 0,5 B no conserva
el dato.

**La reparación tiene dos mitades y ninguna sirve sola:**

1. `conectores/conversacion.py` — el enunciado no se clasificaba: `_HECHO` es una tupla cerrada de seis
   patrones y «mi color favorito es …» no estaba en ella, así que la declaración se guardaba SIN clase
   y `_responder_hecho`, que solo admite `HECHO_DECLARADO`, no podía verla.
2. `core/orchestrator.py` — `_CONSULTAS_DE_HECHO` no tenía la fila con la que responder.

**Lo que NO cambia:** un marcador de gusto suelto («me gusta el azul») sigue siendo
`PREFERENCIA_DECLARADA`. La distinción hecho/preferencia del acta del CEO (2026-08-09) se conserva: aquí
solo entra la **construcción declarativa completa**, que es verdadera o falsa respecto de lo que el
usuario dijo, no un gusto expresado de pasada.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import _clasificar, _normalizar
from aura_skeleton.core.almacen_senales import AlmacenSenales
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import ClaseSenal, Senal
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _ProveedorProhibido:
    """Un proveedor que NO debe llegar a usarse. Cuenta las llamadas y delata la que sobre."""

    name = "prohibido"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"AMARILLO (el modelo redactando)"}'


async def _si(accion, args, trace_id):
    return True


def _sistema(mem: SimpleMemory):
    espia = _ProveedorProhibido()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    orq = Orchestrator(
        InProcessEventBus(), mem, ModelRouter([espia], 1200), PermissionManager(_si),
        VoiceAdapterMock(), HomeAssistantMock(), modelo_usuario=ModeloUsuario(mem, motor=motor),
    )
    return orq, espia


async def _declarar(mem: SimpleMemory, frase: str, uid: str = "mauricio") -> None:
    """Siembra por la vía real: se clasifica el enunciado y se guarda la señal que salga."""
    clase = _clasificar(_normalizar(frase))
    assert clase is not None, f"el enunciado no se clasifica: {frase!r}"
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    await AlmacenSenales(mem, motor=motor).guardar(uid, [Senal(clase, frase, "conversacion", "t1")])


async def _turno(orq, texto: str, uid: str = "mauricio") -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


# ------------------------------------------------- 1 · LA DECLARACIÓN SE RECONOCE COMO HECHO --


@pytest.mark.parametrize("frase", [
    "Mi color favorito es el azul",
    "Mi color preferido es el verde",
])
def test_declarar_un_color_es_un_hecho_declarado(frase):
    """Sin esto, la declaración se guarda sin clase y la ruta del Core no puede leerla."""
    assert _clasificar(_normalizar(frase)) == ClaseSenal.HECHO_DECLARADO


@pytest.mark.parametrize("frase", [
    "Me gusta el azul",
    "Prefiero el azul",
])
def test_un_gusto_suelto_sigue_siendo_preferencia(frase):
    """Caso de control del acta del CEO (2026-08-09): la preferencia gana con marcador suelto."""
    assert _clasificar(_normalizar(frase)) == ClaseSenal.PREFERENCIA_DECLARADA


def test_preguntar_no_declara():
    """Preguntar no es declarar, para ninguna clase."""
    assert _clasificar(_normalizar("¿Cuál es mi color favorito?")) is None


# --------------------------------------------- 2 · EL CASO OBLIGATORIO: 0 LLAMADAS AL MODELO --


@pytest.mark.asyncio
async def test_el_color_declarado_lo_responde_el_core_sin_llamar_al_modelo():
    """El caso que el CEO exige demostrado: declarar azul, preguntar, y que responda el Core."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi color favorito es el azul")

    res = await _turno(orq, "¿Cuál es mi color favorito?")

    assert "azul" in res["say"], res["say"]
    assert res["say"] == "Tu color favorito es azul."
    assert espia.llamadas == 0, "el hecho lo tiene el Core: el modelo no pinta nada aquí"
    assert res.get("provider") == "core"


@pytest.mark.asyncio
async def test_el_valor_es_EXACTAMENTE_el_declarado_y_no_lo_redacta_el_modelo():
    """El doble devuelve «AMARILLO» si se le llama. Si aparece, es que el modelo redactó el hecho."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi color favorito es el azul")

    res = await _turno(orq, "¿Cuál es mi color favorito?")

    assert "AMARILLO" not in res["say"]
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_la_ultima_declaracion_gana():
    """Redeclarar es cómo uno se corrige; devolver la primera dejaría el dato viejo para siempre."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi color favorito es el azul")
    await _declarar(mem, "Mi color favorito es el verde")

    res = await _turno(orq, "¿Cuál es mi color favorito?")

    assert res["say"] == "Tu color favorito es verde."
    assert espia.llamadas == 0


# ------------------------------------------------------------ 3 · AUSENCIA: NO SE INVENTA --


@pytest.mark.asyncio
async def test_sin_declaracion_no_se_inventa_nada():
    """INV-9: si el usuario no lo dijo, se dice — no se infiere ni se deja caer al recall."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)

    res = await _turno(orq, "¿Cuál es mi color favorito?")

    assert res["say"] == "Todavía no me has dicho cuál es tu color favorito."
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_una_entrada_refutada_no_alimenta_la_ruta():
    """Solo entradas VIVAS: un hecho refutado dejó de darse por cierto."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi color favorito es el azul")
    await ModeloUsuario(mem, motor=MotorAutomatizacion(
        EjecutorModeloUsuario(mem), PermissionManager(_si))).refutar("mauricio", "azul")

    res = await _turno(orq, "¿Cuál es mi color favorito?")

    assert "azul" not in res["say"]
    assert res["say"] == "Todavía no me has dicho cuál es tu color favorito."
    assert espia.llamadas == 0


# ------------------------------------------------- 4 · NO ROBA TURNOS QUE NO LE CORRESPONDEN --


@pytest.mark.asyncio
@pytest.mark.parametrize("pregunta", [
    "¿Cuál es la capital de Francia?",
    "¿Qué me recomiendas para concentrarme mejor?",
    "¿Por qué crees que dormir poco afecta al ánimo?",
])
async def test_una_pregunta_que_no_es_el_atributo_no_la_roba_esta_ruta(pregunta):
    """La tabla es cerrada: lo que no nombra, no lo desvía. Estas van al modelo, como deben."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi color favorito es el azul")

    res = await _turno(orq, pregunta)

    assert "color favorito" not in (res.get("say") or "")
    assert espia.llamadas == 1, "estas preguntas SÍ son del modelo"


@pytest.mark.asyncio
async def test_el_nombre_y_el_trabajo_siguen_respondiendose_igual():
    """Caso de control: la ampliación no puede desplazar a los atributos que ya existían."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Me llamo Mauricio")
    await _declarar(mem, "Trabajo en logistica")

    assert (await _turno(orq, "¿Cómo me llamo?"))["say"] == "Te llamas Mauricio."
    assert (await _turno(orq, "¿A qué me dedico?"))["say"] == "Trabajas en logistica."
    assert espia.llamadas == 0


# ------------------------------------- 5 · SOLO HECHOS DECLARADOS ALIMENTAN ESTA RUTA --
#
# Lo destapó la verificación de mutación: `HD-M6` —sustituir el filtro de clase por «todas las
# entradas vivas»— sobrevivía porque ninguna prueba lo cubría. Es justo la regla que la autorización
# del CEO manda preservar, así que necesita su propia red.


@pytest.mark.asyncio
async def test_una_senal_OBSERVADA_no_se_presenta_como_hecho_del_usuario():
    """Una observación del sistema no es una declaración del usuario, aunque lo diga con sus palabras.

    El sistema observa patrones y los guarda con OTRA clase. Si el filtro de `HECHO_DECLARADO` cayera,
    una observación se le repetiría al usuario como si él la hubiera declarado — que es exactamente la
    confusión declarado/observado que `ADR-0017` y el acta del CEO (2026-08-09) existen para impedir.
    """
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    await AlmacenSenales(mem, motor=motor).guardar("mauricio", [
        Senal(ClaseSenal.PATRON_DE_USO, "mi color favorito es el rojo", "computador", "t9"),
    ])

    # Caso de control: la entrada EXISTE y está viva. Sin esto la prueba sería decorativa.
    entradas = await ModeloUsuario(mem, motor=motor).ver("mauricio")
    vivas = [e for e in entradas if not e.get("refutada")]
    assert any("rojo" in e["contenido"] for e in vivas), "la prueba mediría una memoria vacía"

    res = await _turno(orq, "¿Cuál es mi color favorito?")

    assert "rojo" not in res["say"], "una observación no puede devolverse como hecho declarado"
    assert res["say"] == "Todavía no me has dicho cuál es tu color favorito."
    assert espia.llamadas == 0
