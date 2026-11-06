"""El historial de un hecho redeclarado se puede PREGUNTAR, no solo versionar (AMP-AURA etapas 1-2).

**Lo que faltaba, medido en el plano** (`milestones/m3-entry/AMP-AURA-DECISIONES.md`): AURA ya versiona
un atributo redeclarado -`version`/`supersedes`/`valid_from`/`valid_until`- pero `_responder_hecho`
filtra `valid_until is None`, asi que SOLO responde el presente. No existe ninguna superficie que
responda «¿cual era mi cumpleaños?» con el dato anterior. Esta bateria cierra esa superficie de LECTURA,
determinista, en el Core, sin una sola llamada al LLM (ADR-0014).

Sigue el estilo de `tests/unit/test_historial_y_vigencia.py` (mismos helpers `_sistema`/`_declarar`/
`_turno`) y de `tests/unit/test_es_declaracion_de_hecho_propio.py` (pruebas puras de la gramatica).
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
from aura_skeleton.core.identidad_memoria import atributo_preguntado_en_pasado
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import ClaseSenal, Senal
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter

V1 = "Mi cumpleaños es el 10 de mayo"
V2 = "Mi cumpleaños es el 3 de junio"


class _ProveedorEspia:
    """Cuenta las llamadas. Si el historial pasara por el modelo, esta prueba lo delataria."""

    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"FABRICADO por el LLM"}'


async def _si(accion, args, trace_id):
    return True


def _sistema(mem: SimpleMemory):
    espia = _ProveedorEspia()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    orq = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([espia], 1200),
        PermissionManager(_si),
        VoiceAdapterMock(),
        HomeAssistantMock(),
        modelo_usuario=ModeloUsuario(mem, motor=motor),
    )
    return orq, espia


async def _declarar(mem: SimpleMemory, frase: str, uid: str = "mauricio", ts: float | None = None) -> None:
    """Siembra por la VIA REAL: se clasifica el enunciado y se guarda la señal que salga -el
    versionado vive en el ejecutor del motor unico (G-1), escribir a mano en el almacen lo saltaria."""
    clase = _clasificar(_normalizar(frase))
    assert clase is not None, f"el enunciado no se clasifica: {frase!r}"
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    await AlmacenSenales(mem, motor=motor).guardar(uid, [Senal(clase, frase, "conversacion", "t1", ts=ts)])


async def _turno(orq, texto: str, uid: str = "mauricio") -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


# ---------------------------------------------------- 1 · LA GRAMATICA PURA: QUE ACTIVA Y QUE NO --


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("¿cual era mi cumpleaños?", "cumpleanos"),
        ("¿cual fue mi cumpleaños?", "cumpleanos"),
        ("¿cuales eran mi cumpleaños?", "cumpleanos"),
        ("¿cuales fueron mi cumpleaños?", "cumpleanos"),
        ("¿que me dijiste antes de mi cumpleaños?", "cumpleanos"),
        ("¿que me dijiste antes sobre mi cumpleaños?", "cumpleanos"),
        ("¿que me dijiste de mi cumpleaños?", "cumpleanos"),
        ("¿que me dijiste sobre mi cumpleaños?", "cumpleanos"),
        ("¿cual es mi cumpleaños anterior?", "cumpleanos"),
        ("¿cual era mi color favorito?", "color favorito"),
    ],
)
def test_reconoce_las_formas_de_pregunta_de_historial(texto, esperado):
    assert atributo_preguntado_en_pasado(_normalizar(texto)) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "¿cual es mi cumpleaños?",  # presente, no historial: no lleva "anterior" ni "era/fue"
        "antes de comer me lavo las manos",  # no es ni pregunta ni posesiva
        "que me dijiste",  # sin "mi X": no hay atributo que nombrar
        "¿que me dijiste antes de comer?",  # "antes de" sin "mi X" posesivo
        "mi cumpleaños es el 10 de mayo",  # es una DECLARACION, no una pregunta
        "¿que sabes de mi cumpleaños?",  # pertenece a `_PAT_MODELO_VER`, no al historial
        # Con COLA: sin el anclaje de FINAL (`$`), `match()` seguiria casando el principio y la
        # superficie robaria el turno a la parte de la frase que no vio. La segunda es la que
        # importa de verdad: sin anclaje, se roba el turno a la peticion de olvido.
        "¿cual era mi cumpleaños y apaga la luz?",
        "olvida cual era mi cumpleaños",
    ],
)
def test_no_activa_con_frases_que_no_son_pregunta_de_historial(texto):
    assert atributo_preguntado_en_pasado(_normalizar(texto)) is None


# ------------------------------------------------ 2 · EL CASO OBLIGATORIO, DE EXTREMO A EXTREMO --


@pytest.mark.asyncio
async def test_el_cumpleanos_redeclarado_responde_ambos_valores_con_el_actual_vigente():
    """El caso del plano: "tu cumpleaños es el 3 de junio" y ADEMAS "antes me dijiste el 10 de mayo"."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)

    r = await _turno(orq, "¿Cuál era mi cumpleaños?")

    assert r["say"] == "Ahora tu cumpleaños es 3 de junio. Antes me dijiste: 10 de mayo.", r["say"]
    assert r["provider"] == "core" and r["dominio"] == "modelo_usuario"
    assert espia.llamadas == 0, "el historial lo tiene el Core: el modelo no pinta nada aqui"


@pytest.mark.asyncio
async def test_los_anteriores_se_narran_en_orden_cronologico_ascendente():
    """Caso de control del anterior: con SOLO un valor anterior el orden es invisible (cualquier
    orden produce la misma lista de un elemento). Con TRES versiones, invertir el orden cronologico
    SI cambia el `say` literal: «antes me dijiste» deja de ser una secuencia veraz (HC-M4)."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)  # 10 de mayo
    await _declarar(mem, V2, ts=2000.0)  # 3 de junio
    await _declarar(mem, "Mi cumpleaños es el 7 de agosto", ts=3000.0)

    r = await _turno(orq, "¿Cuál era mi cumpleaños?")

    assert r["say"] == ("Ahora tu cumpleaños es 7 de agosto. Antes me dijiste: 10 de mayo, 3 de junio."), r["say"]
    assert espia.llamadas == 0


# --------------------------------------------------------- 3 · UN SOLO VALOR: NO HAY "ANTES" --


@pytest.mark.asyncio
async def test_un_solo_valor_declarado_lo_dice_asi_y_no_inventa_un_antes():
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)

    r = await _turno(orq, "¿Cuál era mi cumpleaños?")

    assert r["say"] == "Solo me has dicho una cosa sobre tu cumpleaños: 10 de mayo. No me habías dicho otra antes."
    assert espia.llamadas == 0


# ------------------------------------------------- 4 · ATRIBUTO JAMAS DECLARADO: NO ROBA EL TURNO --


def test_un_atributo_jamas_declarado_devuelve_none_y_no_roba_el_turno():
    """INV-9: sin dato que mostrar, la superficie se aparta -no inventa un texto de ausencia propio,
    que le robaria el turno a la puerta de ADR-0014 (mismo criterio que documenta `_responder_hecho`)."""
    assert Orchestrator._responder_historial("¿cual era mi cumpleaños?", []) is None


@pytest.mark.asyncio
async def test_preguntar_el_historial_de_un_atributo_nunca_declarado_no_lo_fabrica():
    """Sin `pares`, la superficie se aparta (`None`) y el turno cae a la puerta REAL de ADR-0014
    -no a un texto inventado por esta superficie-. Se afirma el literal EXACTO de esa puerta, no solo
    la ausencia de "cumpleaños": un texto fabricado que tampoco mencionara el atributo pasaria el
    segundo candado sin ser la ruta correcta (HC-M7)."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Trabajo en logística", ts=1000.0)

    r = await _turno(orq, "¿Cuál era mi cumpleaños?")

    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso.", r["say"]
    assert espia.llamadas == 0


# ------------------------------------------ 5 · EL PRESENTE NO SE ROMPE: REGRESION DE `_responder_hecho` --


@pytest.mark.asyncio
async def test_una_pregunta_de_presente_sigue_respondiendo_solo_el_valor_vigente():
    """Regresion: `_responder_historial` va ANTES de `_responder_hecho` en el cableado. Una pregunta
    de PRESENTE no debe activar el historial ni mezclar el valor anterior en la respuesta."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)

    r = await _turno(orq, "¿Cuál es mi cumpleaños?")

    assert "3 de junio" in r["say"]
    assert "10 de mayo" not in r["say"], "una pregunta de presente no debe mezclar el historial"
    assert espia.llamadas == 0


# ---------------------------------------------------------- 6 · FIDELIDAD ADR-0017: TAL CUAL SE DIJO --


@pytest.mark.asyncio
async def test_el_valor_se_repite_tal_y_como_el_usuario_lo_escribio():
    """ADR-0017: ni se reformula ni se normaliza el valor -mayusculas y tildes incluidas-.

    `atributo_declarado` descarta el articulo ("un"/"el"...) al extraer el valor -es la MISMA gramatica
    que ya usa `_responder_hecho`, no un comportamiento nuevo de esta superficie-, pero conserva
    mayusculas y tildes tal cual el usuario las escribio: eso es lo que esta prueba demuestra."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi coche es un Seat León", ts=1000.0)
    await _declarar(mem, "Mi coche es un Škoda Fabia", ts=2000.0)

    r = await _turno(orq, "¿Cuál era mi coche?")

    assert r["say"] == "Ahora tu coche es Škoda Fabia. Antes me dijiste: Seat León.", r["say"]
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_el_valor_de_UN_SOLO_dato_tambien_se_repite_tal_cual_lo_escribio():
    """Caso de control del anterior: la rama de UN SOLO VALOR es una rama de codigo DISTINTA -no la
    misma que la de "ahora/antes"- y necesita su propia prueba de fidelidad. Con una sola declaracion
    de «10 de mayo», normalizar no cambia nada; aqui el valor SI cambia al normalizarlo (HC-M5)."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi coche es un Seat León", ts=1000.0)

    r = await _turno(orq, "¿Cuál era mi coche?")

    assert r["say"] == "Solo me has dicho una cosa sobre tu coche: Seat León. No me habías dicho otra antes.", r["say"]
    assert espia.llamadas == 0


# --------------------------------------------------- 7 · SOLO HECHOS DECLARADOS ALIMENTAN LA RUTA --


@pytest.mark.asyncio
async def test_una_senal_observada_no_se_mezcla_en_el_historial():
    """La misma guarda que protege `_responder_hecho`: una observacion no es una declaracion del
    usuario y no debe aparecer mezclada en el historial de lo que el usuario SI declaro.

    Se inyecta DIRECTAMENTE -sin pasar por el motor- para aislar esta guarda (clase != HECHO_DECLARADO)
    de otra cuestion distinta: que el versionado de la identidad opera sobre el CONTENIDO, no sobre la
    clase, y una senal observada con la misma identidad tambien cerraria la vigencia de la declarada si
    pasara por el ejecutor. Esa interaccion no es del alcance de esta superficie de lectura.

    `version`/`valid_until` se fijan a mano -2 y no-None- para que, SIN la guarda de clase, la
    observada caeria inequivocamente en `anteriores` y el `say` completo cambiaria (mencionaria «1 de
    enero»). Con un empate de version (ambas en 1, ambas vigentes) el mutante de la guarda sobrevive:
    `max` devolveria la declarada igual y la respuesta no se moveria (HC-M3)."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)  # declaracion real -> HECHO_DECLARADO, version 1, vigente
    await mem.write(
        "mauricio",
        "procedimental",
        "mi cumpleaños es el 1 de enero",
        {
            "trace_id": "t9",
            "fuente": "computador",
            "clase": ClaseSenal.PATRON_DE_USO.value,
            "origen": "observada",
            "ts": 1500.0,
            "version": 2,
            "valid_until": 1600.0,
        },
    )

    r = await _turno(orq, "¿Cuál era mi cumpleaños?")

    assert "1 de enero" not in r["say"]
    assert r["say"] == "Solo me has dicho una cosa sobre tu cumpleaños: 10 de mayo. No me habías dicho otra antes."
    assert espia.llamadas == 0


# ------------------------------------ redeclarar el mismo valor no inventa un estado anterior (2026-09-27)

import pytest as _pytest  # noqa: E402

from aura_skeleton.composicion import Configuracion as _Conf  # noqa: E402
from aura_skeleton.composicion import componer as _componer  # noqa: E402


async def _decir(orq, texto, tid):
    await orq.handle_utterance("u", texto, tid)
    await orq.wait(tid)
    return orq._results[tid]["say"]


@_pytest.mark.asyncio
async def test_una_redeclaracion_identica_no_aparece_dos_veces_en_el_historial(tmp_path):
    orq = _componer(_Conf(datos=str(tmp_path))).orquestador
    for i, t in enumerate(["me llamo Mauricio", "me llamo Mauricio", "me llamo Pedro"]):
        await _decir(orq, t, f"H{i}")

    respuesta = await _decir(orq, "¿cuál era mi nombre?", "H9")

    assert "Pedro" in respuesta
    assert respuesta.count("Mauricio") == 1, respuesta


@_pytest.mark.asyncio
async def test_CONTROL_ir_y_volver_a_un_valor_SI_son_estados_distintos(tmp_path):
    """Sin este control, deduplicar TODO el historial pasaría la prueba anterior y borraría una
    vuelta atrás real: Valencia -> Sevilla -> Valencia son tres estados."""
    orq = _componer(_Conf(datos=str(tmp_path))).orquestador
    for i, t in enumerate(
        ["mi ciudad es Valencia", "mi ciudad es Sevilla", "mi ciudad es Valencia", "mi ciudad es Madrid"]
    ):
        await _decir(orq, t, f"C{i}")

    respuesta = await _decir(orq, "¿cuál era mi ciudad?", "C9")

    assert respuesta.count("Valencia") == 2, respuesta
