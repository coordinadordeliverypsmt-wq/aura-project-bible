"""Emparejamiento gramatical simétrico: «mi X es V» ↔ «¿cuál es mi X?» (CEO, 2026-09-10).

**Por qué existe.** La tabla `_CONSULTAS_DE_HECHO` no escala: cada atributo costaba dos ediciones de
producto. Y la barrera de verdad no era la tabla sino `_HECHO`, una lista cerrada de construcciones: «mi
cumpleaños es el 10 de mayo» **no se guardaba**, así que no había nada que responder y la pregunta caía
al modelo, que ya demostró deformar un hecho («azul» → «amarillo»).

**La arquitectura autorizada (C).** La declaración «mi X es V» y la pregunta «¿cuál es mi X?» comparten
el sujeto posesivo. Se deriva X de ambas y se resuelve por **igualdad exacta**, sobre la frase literal
que la memoria ya guarda: sin metadata nueva, sin migración, sin tocar contratos.

**La contrapartida, y por eso va en el mismo incremento:** abrir `_HECHO` a la construcción posesiva
genérica haría que «mi abuela es enfermera» se guardara como hecho del usuario. `_TERCERO` no cubría
abuela, primo ni tío. Se refuerza aquí.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import _clasificar, _habla_de_tercero, _normalizar
from aura_skeleton.core.almacen_senales import AlmacenSenales
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import ClaseSenal, Senal, SenalDeTercero
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter


class _ProveedorProhibido:
    name = "prohibido"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"VALOR INVENTADO POR EL MODELO"}'


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


async def _declarar(mem: SimpleMemory, frase: str, uid: str = "mauricio") -> ClaseSenal | None:
    """Siembra por la vía REAL: clasifica, comprueba terceros y guarda lo que sobreviva."""
    norm = _normalizar(frase)
    clase = _clasificar(norm)
    if clase is None:
        return None
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    try:
        senal = Senal(clase, frase, "conversacion", "t1", sobre_tercero=_habla_de_tercero(norm))
    except SenalDeTercero:
        return None  # la restricción funcionando: no se captura
    await AlmacenSenales(mem, motor=motor).guardar(uid, [senal])
    return clase


async def _turno(orq, texto: str, uid: str = "mauricio") -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


# ============================================ 1-2 · EL CASO YA CUBIERTO SIGUE CUBIERTO --


@pytest.mark.asyncio
async def test_color_favorito_y_la_ultima_declaracion_gana():
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi color favorito es el azul")
    assert (await _turno(orq, "¿Cuál es mi color favorito?"))["say"] == "Tu color favorito es azul."
    await _declarar(mem, "Mi color favorito es el verde")
    assert (await _turno(orq, "¿Cuál es mi color favorito?"))["say"] == "Tu color favorito es verde."
    assert espia.llamadas == 0


# ===================================== 3-4 · HECHOS QUE ANTES NO ENTRABAN SIQUIERA --


HECHOS_NUEVOS = [
    ("Mi cumpleaños es el 10 de mayo", "¿Cuál es mi cumpleaños?", "Tu cumpleaños es 10 de mayo."),
    ("Mi teléfono es 600123456", "¿Cuál es mi teléfono?", "Tu teléfono es 600123456."),
    ("Mi coche es un Seat León", "¿Cuál es mi coche?", "Tu coche es Seat León."),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("declaracion", "pregunta", "esperado"), HECHOS_NUEVOS)
async def test_un_hecho_posesivo_nuevo_entra_y_se_responde_desde_el_core(declaracion, pregunta, esperado):
    """Ninguno de estos estaba en `_HECHO` ni en `_CONSULTAS_DE_HECHO`: antes no se guardaban."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    assert await _declarar(mem, declaracion) == ClaseSenal.HECHO_DECLARADO

    res = await _turno(orq, pregunta)

    assert res["say"] == esperado, res["say"]
    assert res.get("provider") == "core"
    assert espia.llamadas == 0
    assert "INVENTADO" not in res["say"]


# ================================================================ 5-6 · TERCEROS --


TERCEROS_NUEVOS = ["Mi abuela es enfermera", "Mi abuelo es jubilado", "Mi primo es piloto",
                   "Mi prima es arquitecta", "Mi tío es abogado", "Mi tía es profesora"]
TERCEROS_YA_PROTEGIDOS = ["Mi hermana es médico", "Mi jefe es exigente", "Mi vecino es un pesado",
                          "Mi madre es jardinera", "Mi padre es cocinero", "Mi hijo es estudiante",
                          "Mi esposa es ingeniera", "Mi pareja es dentista", "Mi amigo es músico"]


@pytest.mark.parametrize("frase", TERCEROS_NUEVOS + TERCEROS_YA_PROTEGIDOS)
def test_un_hecho_sobre_un_tercero_no_se_captura(frase):
    """Restricción 3 / ALERTA-002: la señal versa sobre otra persona. Abrir `_HECHO` sin esto
    convertiría a AURA en un registro sobre la familia del usuario."""
    assert _habla_de_tercero(_normalizar(frase)), f"«{frase}» quedaría guardada como hecho personal"


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", TERCEROS_NUEVOS)
async def test_un_tercero_no_llega_a_la_memoria_ni_se_responde(frase):
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    assert await _declarar(mem, frase) is None, "no debe guardarse"

    res = await _turno(orq, "¿Cuál es mi abuela?")

    assert "enfermera" not in (res.get("say") or "")
    assert res.get("provider") == "core", "sin hecho, responde la ruta segura del Core"


# ========================================================== 7 · PREFERENCIAS --


@pytest.mark.parametrize("frase", ["Me gusta el azul", "Prefiero el azul", "No me gusta madrugar"])
def test_una_preferencia_sigue_siendo_preferencia(frase):
    """El acta del CEO (2026-08-09) separa gusto de identidad. Abrir `_HECHO` no puede borrar eso."""
    assert _clasificar(_normalizar(frase)) == ClaseSenal.PREFERENCIA_DECLARADA


# ============================================= 8-10 · NO ROBAR, NO INVENTAR, NO OBSERVAR --


@pytest.mark.asyncio
@pytest.mark.parametrize("pregunta", [
    "¿Cuál es la capital de Francia?",
    "¿Qué me recomiendas para dormir mejor?",
    "¿Por qué crees que dormir poco afecta al ánimo?",
])
async def test_una_pregunta_que_no_es_un_atributo_no_la_roba_esta_ruta(pregunta):
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi cumpleaños es el 10 de mayo")

    await _turno(orq, pregunta)

    assert espia.llamadas == 1, "estas preguntas SÍ son del modelo"


@pytest.mark.asyncio
async def test_sin_declaracion_no_se_inventa():
    mem = SimpleMemory()
    orq, espia = _sistema(mem)

    res = await _turno(orq, "¿Cuál es mi cumpleaños?")

    assert "mayo" not in res["say"]
    assert res.get("provider") == "core"
    assert espia.llamadas == 0, "no se llama al modelo para fabricar un hecho"


@pytest.mark.asyncio
async def test_una_senal_OBSERVADA_no_se_devuelve_como_declaracion():
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    await AlmacenSenales(mem, motor=motor).guardar("mauricio", [
        Senal(ClaseSenal.PATRON_DE_USO, "mi cumpleanos es el 1 de enero", "computador", "t9")])

    res = await _turno(orq, "¿Cuál es mi cumpleaños?")

    # La ruta del Core NO debe atenderla: sin hecho declarado, el turno sigue el recorrido normal (y
    # con un recuerdo en memoria acaba en el modelo, que es la regla vigente). Lo que no puede pasar
    # es que una observación se devuelva con la autoridad del Core.
    assert res["say"] != "Tu cumpleanos es 1 de enero."
    assert res.get("provider") != "core", "el Core no puede firmar una observación como declaración"


@pytest.mark.asyncio
async def test_una_entrada_refutada_no_alimenta_la_ruta():
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi cumpleaños es el 10 de mayo")
    await ModeloUsuario(mem, motor=MotorAutomatizacion(
        EjecutorModeloUsuario(mem), PermissionManager(_si))).refutar("mauricio", "cumplea")

    res = await _turno(orq, "¿Cuál es mi cumpleaños?")

    # Refutado = dejó de darse por cierto: el Core no lo responde. El turno sigue la ruta vigente.
    assert res["say"] != "Tu cumpleanos es 10 de mayo."
    assert res.get("provider") != "core"


# ===================================================== 11 · LOS 24 PROTEGIDOS --


def test_ninguna_de_las_24_deriva_un_atributo_posesivo():
    """La garantía que no se negocia: si una de las 24 entrara por esta ruta, la memoria vacía
    dejaría de protegerla. Medido: las 24 preguntan por un dato de otra forma gramatical."""
    import json
    from pathlib import Path

    from aura_skeleton.core.orchestrator import _atributo_preguntado

    datos = json.loads((Path(__file__).parent.parent / "datos" / "bateria_memoria.json")
                       .read_text(encoding="utf-8"))
    protegidas = [c["texto"] for c in datos["consultas"] if c["esperado"] is None]
    assert len(protegidas) == 24
    escapadas = [t for t in protegidas if _atributo_preguntado(_normalizar(t))]
    assert escapadas == [], f"{len(escapadas)} de 24 entrarían por la ruta posesiva: {escapadas}"


# ========================= 12 · LAS CUATRO GARANTÍAS QUE DESTAPÓ LA MUTACIÓN --
#
# `HP-M2`, `HP-M5`, `HP-M6` y `HP-M9` sobrevivieron a la primera pasada. Cada uno señalaba una garantía
# real sin prueba, no un mutante mal elegido.


@pytest.mark.parametrize("frase", ["Mi abuela es enfermera", "Mi tío es abogado", "Mi hermana es médico"])
def test_un_tercero_NO_SE_CLASIFICA_como_hecho_declarado(frase):
    """Mata `HP-M2`. La protección tiene que estar en la CLASIFICACIÓN, no solo en la captura.

    Antes, el único filtro vivo era el de `capturar`, que descarta la señal al construirla. Con la
    construcción posesiva abierta eso deja la clase mal puesta un paso antes: cualquier otro camino que
    clasifique un enunciado —hoy o mañana— obtendría `HECHO_DECLARADO` para un hecho sobre un tercero.
    """
    assert _clasificar(_normalizar(frase)) != ClaseSenal.HECHO_DECLARADO
    assert _clasificar(_normalizar(frase)) is None


@pytest.mark.asyncio
async def test_con_VARIOS_atributos_responde_el_que_se_pregunta():
    """Mata `HP-M5`. Con una sola declaración, «la primera que casa» acierta por suerte."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi cumpleaños es el 10 de mayo")
    await _declarar(mem, "Mi teléfono es 600123456")

    assert (await _turno(orq, "¿Cuál es mi teléfono?"))["say"] == "Tu teléfono es 600123456."
    assert (await _turno(orq, "¿Cuál es mi cumpleaños?"))["say"] == "Tu cumpleaños es 10 de mayo."
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_la_ultima_declaracion_gana_tambien_en_la_ruta_nueva():
    """Mata `HP-M6`. El caso del color favorito lo atiende la TABLA, que se evalúa antes: no probaba
    esta ruta. Con un atributo que solo cubre el emparejamiento simétrico, sí."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi cumpleaños es el 10 de mayo")
    await _declarar(mem, "Mi cumpleaños es el 3 de junio")

    assert (await _turno(orq, "¿Cuál es mi cumpleaños?"))["say"] == "Tu cumpleaños es 3 de junio."
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_el_valor_se_corta_en_el_primer_conector():
    """Mata `HP-M9`. «mi coche es rojo y muy viejo» declara el coche; la coletilla no es el valor."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi coche es rojo y muy viejo")

    res = await _turno(orq, "¿Cuál es mi coche?")

    assert res["say"] == "Tu coche es rojo."
    assert "viejo" not in res["say"]
    assert espia.llamadas == 0


# ============== 13 · LA CONVERSACIÓN NO INTERROGATIVA SIGUE SIENDO DEL MODELO --
#
# Única garantía de la lista de la misión M3 que no tenía prueba propia: las demás —conocimiento,
# razonamiento, consejo, ausencia, terceros, valor literal, redeclaración— ya están cubiertas arriba o
# en `test_hecho_declarado_sin_llm.py`.


@pytest.mark.asyncio
async def test_una_afirmacion_conversacional_va_al_modelo_no_a_la_ruta_de_hechos():
    """«Hoy tuve un día difícil» no pregunta por un atributo: no la puede atender la ruta directa.

    Medido a través del producto: `provider=ollama`, una llamada. La ruta de hechos solo responde
    interrogativas posesivas sobre algo declarado; todo lo demás sigue su camino.
    """
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi cumpleaños es el 10 de mayo")

    res = await _turno(orq, "Hoy tuve un día difícil.")

    assert "cumpleaños" not in (res.get("say") or ""), "la ruta de hechos no puede atender esto"
    assert espia.llamadas == 1, "la conversación es del modelo"


@pytest.mark.asyncio
async def test_una_suposicion_sin_cifra_NO_la_atiende_la_ruta_de_hechos():
    """Comportamiento PREEXISTENTE, medido y declarado aquí para que quede fijado lo que esta misión
    sí garantiza: «Si tengo un caballo y vendo uno, ¿cuántos me quedan?» **no** la absorbe la respuesta
    directa de memoria.

    Lo que hace hoy es caer en la guarda de ausencia de `ADR-0014` —`dominio=memoria`, 0 llamadas—
    porque `es_cognicion_general` exige una cifra y «uno» no es un dígito. Eso NO lo introdujo esta
    ruta y no se toca aquí: la garantía que esta prueba fija es que el dominio no es `modelo_usuario`.
    """
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, "Mi cumpleaños es el 10 de mayo")

    res = await _turno(orq, "Si tengo un caballo y vendo uno, ¿cuántos me quedan?")

    assert res.get("dominio") != "modelo_usuario", "la ruta de hechos no puede absorber un razonamiento"
    assert "cumpleaños" not in (res.get("say") or "")
