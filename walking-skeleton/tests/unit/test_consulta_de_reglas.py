"""La consulta de automatizaciones no se queda con frases que no hablan de automatizaciones.

DEFECTO DE USO REAL QUE LO MOTIVA (§4.6 del CHECKLIST, abierto desde 2026-08-02 y vuelto a medir el
2026-09-15 ejecutando AURA con proveedor mock):

    Usuario: mis reglas de casa son otras
    AURA:    No tienes ninguna automatización activa.

`_PAT_REGLAS_VER` casa por SUBCADENA y contiene «mis reglas». Pero «regla» es una palabra corriente
del español que casi nunca habla de automatizaciones, y esa frase no pregunta nada: afirma.

LO QUE ESTAS PRUEBAS EXISTEN PARA MATAR. Una prueba que solo comprobara las formas correctas
(«¿que automatizaciones tengo?») pasaria hoy y pasaria tambien con el defecto dentro: no demostraria
nada. Por eso hay las dos mitades —lo que NO debe activar y lo que SI debe seguir activando—, y por eso
el caso de la declaracion se comprueba ademas de extremo a extremo: que `_es_consulta_de_reglas`
devuelva False no sirve de nada si otra superficie acaba respondiendo lo mismo.

Esta superficie NO tenia ninguna prueba de activacion antes de este fichero (verificado por busqueda en
`tests/`): la red se anade con el arreglo.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.orchestrator import _es_consulta_de_reglas

_SIN_AUTOMATIZACIONES = "No tienes ninguna automatización activa."


class _ProveedorEspia:
    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return '{"action":"consulta","say":"respuesta del modelo"}'


@pytest.fixture
def sistema(tmp_path):
    """La COMPOSICION REAL, no un orquestador armado a mano.

    Armarlo a mano deja la automatizacion sin cablear, y entonces la rama de consulta de reglas no se
    alcanza siquiera: el caso de control «pasaba» por el motivo equivocado. Es la misma clase de error
    que estas pruebas persiguen, cometida en la propia prueba.
    """
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    espia = _ProveedorEspia()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return await orq.wait(tid)


# ------------------------------------------------------- LO QUE YA NO DEBE ACTIVAR LA SUPERFICIE --


@pytest.mark.parametrize(
    "texto",
    [
        "mis reglas de casa son otras",  # el defecto medido de §4.6
        "mis reglas son otras",
        "mi regla es no trabajar los domingos",
        "mis reglas del juego eran distintas",
        "mis reglas de convivencia fueron siempre las mismas",
    ],
)
def test_una_declaracion_sobre_las_propias_reglas_no_es_una_consulta(texto):
    assert _es_consulta_de_reglas(texto) is False


# ----------------------------------------------------------- LO QUE DEBE SEGUIR ACTIVANDOLA --


@pytest.mark.parametrize(
    "texto",
    [
        "que automatizaciones tengo",
        "¿Qué automatizaciones tengo?",
        "mis automatizaciones",
        "que reglas tengo",
        "mis reglas",
        "¿cuales son mis reglas?",  # el verbo va DELANTE: es una pregunta, no una declaracion
        "enseñame mis reglas",
    ],
)
def test_las_consultas_de_verdad_siguen_activando_la_superficie(texto):
    assert _es_consulta_de_reglas(texto) is True


# --------------------------------------------------------------- Y DE EXTREMO A EXTREMO --


@pytest.mark.asyncio
async def test_la_declaracion_ya_no_recibe_la_respuesta_de_automatizaciones(sistema):
    """Lo que importa para el usuario: que AURA deje de contestar sobre automatizaciones a una frase
    que no las menciona. Que la superficie se aparte no basta si otra acaba diciendo lo mismo."""
    s, _ = sistema
    r = await _turno(s.orquestador, "mis reglas de casa son otras")
    assert _SIN_AUTOMATIZACIONES not in r["say"], r["say"]


@pytest.mark.asyncio
async def test_CONTROL_la_consulta_real_si_recibe_la_respuesta_de_automatizaciones(sistema):
    """Caso de control. Sin esto, la prueba de arriba pasaria aunque la superficie estuviera muerta
    entera —que es otra forma de romperla, no de arreglarla—."""
    s, _ = sistema
    r = await _turno(s.orquestador, "¿qué automatizaciones tengo?")
    assert r["say"] == _SIN_AUTOMATIZACIONES, r["say"]
