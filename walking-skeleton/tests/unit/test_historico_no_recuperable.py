"""HISTÓRICO NO RECUPERABLE — la tercera opción que faltaba (CEO, 2026-09-09).

**El problema que resuelve.** `DP-D-M-7` §3 clasifica la orden pura como «histórico no recuperable»,
pero `MemoryStore` solo tenía dos salidas: escribir —y entonces `recall` la devolvía, que es el
auto-eco de `D-M-2`— o no escribir, y perder la traza. Ninguna servía.

**Lo que NO significa «no recuperable»:** ni borrado, ni oculto, ni sin auditoría. Significa
exactamente una cosa: *no forma parte del espacio semántico de la memoria personal recuperable*.
Por eso las pruebas de aquí comprueban las dos mitades — que se persiste **y** que no vuelve—: si solo
comprobaran la segunda, borrar el histórico las pasaría todas.
"""

from __future__ import annotations

import pytest

from aura_skeleton.contracts import HISTORICO, KINDS_NO_RECUPERABLES, es_recuperable
from aura_skeleton.core import intencion as I
from aura_skeleton.modules.memory import PersistentMemory, SimpleMemory

ORDEN_DEL_E2E = "Enciende la luz de la sala en modo tenue"


# ------------------------------------------------------------------- EL CONTRATO --


def test_el_contrato_declara_el_nivel_y_su_regla():
    assert HISTORICO == "historico"
    assert HISTORICO in KINDS_NO_RECUPERABLES
    # Fail-closed por omisión: lo que no está marcado sigue siendo recuperable. Al revés haría
    # desaparecer memoria legítima ante un fallo de escritura.
    assert es_recuperable({}) is True
    assert es_recuperable({"kind": "episodica"}) is True
    assert es_recuperable({"kind": HISTORICO}) is False


# --------------------------------------------------- M-1 DECIDE EL DESTINO (eje 1 x eje 2) --


@pytest.mark.parametrize("texto,destino", [
    # ORDEN pura -> histórico. Es el caso que dejaba rojo el e2e.
    (ORDEN_DEL_E2E, I.HISTORICO_NO_RECUPERABLE),
    ("Apaga la luz del salón", I.HISTORICO_NO_RECUPERABLE),
    ("No borres nada", I.HISTORICO_NO_RECUPERABLE),
    # HECHO_USUARIO -> memoria recuperable
    ("Trabajo en logística", I.RECUPERABLE),
    ("Mi cumpleaños es el 14 de marzo", I.RECUPERABLE),
    ("No soy alérgico a los frutos secos", I.RECUPERABLE),
    # Nada de esto se almacena en ningún sitio
    ("¿Cómo me llamo?", None),
    ("¿Cuál es el nombre de mi abuela?", None),
    ("gracias", None),
    ("¿Quién escribió el Quijote?", None),
])
def test_M1_decide_el_destino(texto, destino):
    assert I.destino_de_memoria(texto) == destino, f"{texto!r}"


def test_una_regla_condicional_no_se_cuela_en_memoria_personal():
    """`DP-D-M-7` §3: su sitio es el almacén de reglas. Ni recuperable, ni histórico."""
    texto = "Cuando llegue a casa enciende la luz"
    assert I.contenido_proposicional(texto) == I.REGLA_CONDICIONAL
    assert not I.debe_almacenarse(texto)


def test_INCIERTO_nunca_es_memoria_recuperable():
    for t in ("¿Por qué llueve?", "Supongamos que el agua fuera roja", "Sobre gustos no hay nada escrito"):
        assert I.destino_de_memoria(t) != I.RECUPERABLE, t


# ------------------------------------------------- LAS DOS MITADES: PERSISTE Y NO VUELVE --


@pytest.mark.asyncio
async def test_el_historico_se_persiste_de_verdad(tmp_path):
    """Primera mitad. Si esto fallara, «no recuperable» habría degenerado en «borrado»."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await mem.write("u", HISTORICO, f"usuario dijo: {ORDEN_DEL_E2E}", {"trace_id": "t"})
    guardados = [i for i in mem._items if i["kind"] == HISTORICO]
    assert len(guardados) == 1
    assert "tenue" in guardados[0]["content"], "la traza tiene que conservar el contenido íntegro"


@pytest.mark.asyncio
async def test_el_historico_NO_vuelve_en_recall(tmp_path):
    """Segunda mitad, y la que da nombre al nivel."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await mem.write("u", HISTORICO, f"usuario dijo: {ORDEN_DEL_E2E}", {"trace_id": "t"})
    assert await mem.recall("u", "tenue") == []
    assert await mem.recall("u", "luz de la sala") == []


@pytest.mark.asyncio
async def test_ambos_niveles_coexisten_y_solo_vuelve_uno(tmp_path):
    """El caso que importa: los dos en el mismo almacén, compitiendo por la misma consulta."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await mem.write("u", HISTORICO, "usuario dijo: enciende la luz tenue de la sala", {"trace_id": "1"})
    await mem.write("u", "episodica", "usuario dijo: prefiero la luz tenue por la noche", {"trace_id": "2"})
    hits = await mem.recall("u", "luz tenue")
    assert len(hits) == 1, f"el histórico compitió por el hueco: {hits}"
    assert "prefiero" in hits[0]["content"]
    assert all(h["kind"] != HISTORICO for h in hits)


@pytest.mark.asyncio
async def test_sobrevive_al_reinicio_y_sigue_sin_volver(tmp_path):
    """Persistencia + reload. Un filtro que solo viviera en el índice en memoria se caería aquí."""
    ruta = str(tmp_path / "m.json")
    mem = PersistentMemory(ruta)
    await mem.write("u", HISTORICO, "usuario dijo: enciende la luz tenue", {"trace_id": "1"})
    await mem.write("u", "episodica", "prefiero el té sin azúcar", {"trace_id": "2"})

    otra = PersistentMemory(ruta)  # instancia nueva: carga del disco y reconstruye el índice
    assert any(i["kind"] == HISTORICO for i in otra._items), "el histórico no sobrevivió al reinicio"
    assert await otra.recall("u", "luz tenue") == []
    assert await otra.recall("u", "té sin azúcar"), "la memoria recuperable sí tiene que volver"


@pytest.mark.asyncio
async def test_la_exclusion_vale_para_las_dos_implementaciones(tmp_path):
    """`SimpleMemory` y `PersistentMemory` comparten la garantía, no la implementación.

    Caso de control: si alguien arreglara solo una, esta prueba cae por la otra.
    """
    for mem in (SimpleMemory(), PersistentMemory(str(tmp_path / "s.json"))):
        await mem.write("u", HISTORICO, "usuario dijo: enciende la luz tenue", {"trace_id": "1"})
        assert await mem.recall("u", "luz tenue") == [], type(mem).__name__


# --------------------------------------------------------- NO SE AMPLÍA NINGUNA AUTORIDAD --


def test_el_historico_no_concede_autoridad_de_ejecucion():
    """Clasificar un turno como histórico no lo ejecuta ni le da permisos: es un `kind` de almacén.

    Garantía estructural sobre los imports reales: si `intencion` se trajera el motor o los permisos
    para «decidir mejor», esto cae antes de que llegue a usarlos.
    """
    import ast
    import pathlib
    arbol = ast.parse(pathlib.Path(I.__file__).read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
            modulos.update(a.name for a in nodo.names)
    assert modulos <= {"__future__", "annotations", "re", "unicodedata", "dataclasses", "dataclass"}


def test_no_existe_una_puerta_trasera_que_devuelva_el_historico():
    """`recall` es el único camino a la memoria personal, y filtra. No puede haber un segundo.

    Se comprueba que ninguna implementación exponga un `recall` alternativo sin filtro: todas las
    funciones que devuelven items del almacén tienen que pasar por `es_recuperable`.
    """
    import pathlib

    from aura_skeleton.modules import memory, memory_semantic
    for mod in (memory, memory_semantic):
        fuente = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        for bloque in fuente.split("async def recall")[1:]:
            cuerpo = bloque.split("\n    async def ")[0].split("\n    def ")[0]
            assert "es_recuperable" in cuerpo, f"{mod.__name__}: un recall sin filtro de histórico"


# ------------------------------------------- EL CABLEADO: que el orquestador use el kind correcto --
#
# Estas dos existen porque el arnes de mutacion encontro el hueco: `H-M6` —cambiar el `kind` a
# "episodica" al escribir— SOBREVIVIA. Las pruebas de arriba comprueban el clasificador y el almacen
# por separado, y ninguna miraba el punto donde se unen. Un mutante que sobrevive es una garantia sin
# red, y esta era justo la que da nombre al incremento.


async def _turno(orq, texto):
    import uuid
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return await orq.wait(tid)


def _orquestador(mem):
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock
    from aura_skeleton.adapters.voice import VoiceAdapterMock
    from aura_skeleton.bus import InProcessEventBus
    from aura_skeleton.core.kill_switch import KillSwitch
    from aura_skeleton.core.orchestrator import Orchestrator
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.modules.router import MockProvider, ModelRouter

    async def _permite(action, args, tid):
        return True

    return Orchestrator(
        InProcessEventBus(), mem,
        ModelRouter([MockProvider("m", 3, healthy=True)], 1200),
        PermissionManager(_permite, kill_switch=KillSwitch("/tmp/aura-test-kill-inexistente")),
        VoiceAdapterMock(), HomeAssistantMock(),
    )


@pytest.mark.asyncio
async def test_el_orquestador_escribe_la_orden_CON_EL_KIND_DEL_HISTORICO(tmp_path):
    """El turno completo, no el clasificador aislado: una orden real termina en el histórico."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await _turno(_orquestador(mem), ORDEN_DEL_E2E)

    escritos = [i for i in mem._items if "tenue" in i["content"]]
    assert escritos, "la orden tiene que dejar traza: 'no recuperable' no es 'borrado'"
    assert all(i["kind"] == HISTORICO for i in escritos), (
        f"la orden se escribió como memoria recuperable: {[i['kind'] for i in escritos]}")


@pytest.mark.asyncio
async def test_el_orquestador_escribe_la_afirmacion_como_memoria_recuperable(tmp_path):
    """Caso de control del anterior. Si el orquestador mandara TODO al histórico, AURA dejaría de
    recordar y la prueba de arriba seguiría verde: por eso hacen falta las dos."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await _turno(_orquestador(mem), "Prefiero la luz tenue por la noche")

    escritos = [i for i in mem._items if "tenue" in i["content"]]
    assert escritos, "una afirmación del usuario tiene que almacenarse"
    assert all(i["kind"] != HISTORICO for i in escritos)
    assert await mem.recall("mauricio", "luz tenue"), "y tiene que poder recuperarse"
