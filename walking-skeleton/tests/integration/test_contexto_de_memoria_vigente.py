"""El contexto de memoria que se envía al modelo solo lleva lo que AURA da por cierto HOY.

DEUDA `D-M-5` (`milestones/m3-entry/DEUDA-N1-RECUPERADOR.md`), reproducida el 2026-09-15 con datos
aislados: el usuario refuta un hecho («eso ya no es cierto»), `¿qué sabes de mí?` deja de mostrarlo
—la presentación filtra `refutada`—, pero `memory.recall` lo sigue devolviendo y el orquestador lo
une en `[contexto memoria: ...]`. El modelo recibe como recuerdo vigente justo lo que el usuario
acaba de desmentir.

Y la misma fuga, por el otro lado del historial (AMP-AURA etapas 1-2): tras redeclarar un atributo,
la versión anterior queda cerrada con `valid_until`. Pertenece al historial, no al presente —así lo
aplica ya `_responder_hecho`—, pero `recall` también la devuelve y entraba al contexto junto a la
vigente, con dos valores contradictorios y ninguna marca de cuál vale.

POR QUÉ ESTAS PRUEBAS MIRAN EL PROMPT Y NO LA RESPUESTA. La respuesta la escribe el modelo y un
espía no la puede fabricar con sentido; lo que AURA controla —y lo único que esta corrección
cambia— es QUÉ LE ENSEÑA. Así que el espía captura el prompt y se comprueba ahí.

CADA CASO LLEVA SU CONTROL: el mismo recorrido sin refutar / sin redeclarar, en el que el dato SÍ
aparece en el contexto. Sin el control, «el dato no aparece» pasaría también si `recall` no lo
encontrara nunca, que es otra forma de no demostrar nada.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"


class _EspiaDePrompt:
    """Registra cada prompt que llega al modelo. No decide nada."""

    name = "espia"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.prompts.append(prompt)
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "respuesta del modelo"})


@pytest.fixture
def sistema(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    espia = _EspiaDePrompt()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


def _contexto_de_memoria(prompt: str) -> str:
    """Solo el bloque `[contexto memoria: ...]`: el texto del usuario no cuenta como memoria."""
    inicio = prompt.index("[contexto memoria:")
    return prompt[inicio : prompt.index("]\n", inicio)]


def _segmentos(prompt: str) -> list[str]:
    """Cada recuerdo del contexto por separado. Hace falta distinguir la entrada SEMANTICA versionada
    («mi cumpleaños es el 10 de mayo») de su eco EPISODICO («usuario dijo: mi cumpleaños es...»): la
    subcadena de la primera esta dentro de la segunda, y un `in` sobre el bloque entero no las separa."""
    return _contexto_de_memoria(prompt).removeprefix("[contexto memoria: ").split(" | ")


# ------------------------------------------------------------------ REFUTADO --

_HECHO = "suelo pagar las facturas por la app"
_PREGUNTA_FACTURAS = "cuéntame qué sabes sobre las facturas"


@pytest.mark.asyncio
async def test_CONTROL_sin_refutar_el_hecho_SI_llega_al_contexto(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _HECHO)
    await _turno(s.orquestador, _PREGUNTA_FACTURAS)
    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert "facturas por la app" in _contexto_de_memoria(espia.prompts[-1])


@pytest.mark.asyncio
async def test_un_hecho_refutado_NO_llega_al_contexto_del_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _HECHO)
    await _turno(s.orquestador, "¿qué sabes de mí?")  # fija el foco en la entrada
    r = await _turno(s.orquestador, "eso ya no es cierto")
    assert "corrijo" in r["say"], f"la refutación debe haberse aplicado: {r['say']!r}"

    await _turno(s.orquestador, _PREGUNTA_FACTURAS)

    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert "facturas por la app" not in _contexto_de_memoria(espia.prompts[-1])


# ---------------------------------------------------------------- SUPERSEDED --

# «el cumpleaños» y no «cuéntame algo sobre mi cumpleaños»: medido el 2026-09-15, la segunda la atiende
# la puerta de memoria y nunca llega al modelo, y las formulaciones largas no alcanzan la cobertura
# minima de `recall` (60 % de los terminos informativos), de modo que el contexto llegaba vacio y la
# prueba no habria medido nada. Se eligio la frase que SI llega al modelo CON recuerdos.
_PREGUNTA_CUMPLE = "el cumpleaños"
_V1_SEMANTICA = "mi cumpleaños es el 10 de mayo"
_V1_ECO = "usuario dijo: mi cumpleaños es el 10 de mayo"


@pytest.mark.asyncio
async def test_CONTROL_con_una_sola_version_la_entrada_SI_llega_al_contexto(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _V1_SEMANTICA)
    await _turno(s.orquestador, _PREGUNTA_CUMPLE)
    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert _V1_SEMANTICA in _segmentos(espia.prompts[-1])


@pytest.mark.asyncio
async def test_la_entrada_superseded_NO_llega_al_contexto_del_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _V1_SEMANTICA)
    await _turno(s.orquestador, "mi cumpleaños es el 3 de junio")
    await _turno(s.orquestador, _PREGUNTA_CUMPLE)

    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert _V1_SEMANTICA not in _segmentos(espia.prompts[-1]), _segmentos(espia.prompts[-1])


@pytest.mark.asyncio
async def test_MEDIDO_NO_DESEADO_el_eco_episodico_de_la_version_antigua_sigue_llegando(sistema):
    """**Comportamiento medido, no deseado, y fijado a proposito para que nadie lo lea como arreglado.**

    Cada declaracion deja dos entradas: la SEMANTICA versionada y un eco EPISODICO «usuario dijo: ...»
    sin `valid_until` ni `refutada`. El filtro de contexto retira la primera y no puede alcanzar la
    segunda: enlazar el eco con su version exige tocar el modelo de memoria, fuera del perimetro de
    esta correccion. Si algun dia deja de llegar, esta prueba fallara, y ese es el aviso de que hay que
    reescribirla como garantia en vez de borrarla."""
    s, espia = sistema
    await _turno(s.orquestador, _V1_SEMANTICA)
    await _turno(s.orquestador, "mi cumpleaños es el 3 de junio")
    await _turno(s.orquestador, _PREGUNTA_CUMPLE)

    assert _V1_ECO in _segmentos(espia.prompts[-1]), _segmentos(espia.prompts[-1])


# ------------------------------------------------------- LA PUERTA NO SE MUEVE --


@pytest.mark.asyncio
async def test_la_puerta_de_ADR_0014_sigue_decidiendo_con_lo_mismo(sistema):
    """Esta corrección filtra lo que se ENSEÑA al modelo; no lo que decide la puerta de ADR-0014
    (`DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` §10 la declara intocable). Sin ningún recuerdo, una pregunta
    por uno sigue respondiéndose en el Core, sin modelo, exactamente como antes."""
    s, espia = sistema
    r = await _turno(s.orquestador, "¿qué acordamos sobre el presupuesto?")
    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso."
    assert espia.prompts == []


# ------------------------------------------------------------------ TERCEROS --
# D-AMP-2 (`AMP-AURA-DECISIONES.md` §D-AMP-2; aprobación `decisiones/2026-10-11-D-AMP-2-aprobacion-construccion.md`).
# Un hecho sobre un TERCERO no se captura como hecho semantico —`_habla_de_tercero` lo veta en la
# captura (`conectores/conversacion.py`)—, pero su ECO EPISODICO «usuario dijo: ...» se escribe igual
# (`orchestrator.py`, kind=episodica) y reentra por `recall`. El filtro de VIGENCIA (`_da_por_cierto`)
# no lo alcanza: el eco es un registro valido de lo que se dijo. El Context Builder cierra esa fuga en
# la SALIDA hacia el modelo. Igual que arriba, se mira el PROMPT y cada caso lleva su CONTROL.

_TERCERO_HECHO = "mi abuela es enfermera"
_TERCERO_ECO = "usuario dijo: mi abuela es enfermera"
_PREGUNTA_ENFERMERA = "cuéntame qué sabes sobre la enfermera"


@pytest.mark.asyncio
async def test_CONTROL_el_eco_llega_al_contexto_cuando_el_recall_lo_pesca(sistema):
    """Control del filtro de terceros: con un hecho del PROPIO usuario y el MISMO recorrido, el eco SÍ
    aparece en el contexto. Sin este control, «el eco de tercero no aparece» podria pasar tambien si el
    `recall` no lo encontrara nunca — que no demostraria nada."""
    s, espia = sistema
    await _turno(s.orquestador, "suelo pagar las facturas por la app")
    await _turno(s.orquestador, "cuéntame qué sabes sobre las facturas")
    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert "facturas por la app" in _contexto_de_memoria(espia.prompts[-1])


@pytest.mark.asyncio
async def test_el_eco_episodico_de_un_tercero_NO_llega_al_contexto_del_modelo(sistema):
    """El vector medido en D-AMP-2: «mi abuela es enfermera» queda como eco episodico y, al preguntar
    algo que lo pesca, reentra al `[contexto memoria: ...]`. El Builder lo excluye por hablar de un
    tercero, sin tocar el store ni la puerta de ADR-0014."""
    s, espia = sistema
    await _turno(s.orquestador, _TERCERO_HECHO)
    await _turno(s.orquestador, _PREGUNTA_ENFERMERA)
    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    ctx = _contexto_de_memoria(espia.prompts[-1])
    assert _TERCERO_ECO not in _segmentos(espia.prompts[-1]), ctx
    assert "abuela" not in ctx, ctx
