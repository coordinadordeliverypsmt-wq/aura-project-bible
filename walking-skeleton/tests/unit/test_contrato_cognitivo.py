"""El contrato de salida del modo cognitivo — decodificado restringido por esquema (2026-09-09).

**El defecto, medido en HC-1.** `format: "json"` obliga a que la salida sea JSON **válido**; no obliga a
que tenga las claves pedidas. `qwen2.5:0.5b` devolvía
`{"intent":"consulta","action":"consultar","args":{"nombre":"Jesús","tipo":1}}` — JSON impecable, **sin
`say`**, y con una **acción inventada y argumentos fabricados**. El usuario recibía el fallback.

**La reparación.** Un JSON Schema en `format` restringe el decodificado por gramática. Medido sobre el
mismo prompt: `say` presente **1/4 → 7/7**, acciones inventadas **1/4 → 0/7**.

Estas pruebas no llaman a Ollama: interceptan la petición y comprueban **qué se le pide**. Lo que el
modelo contesta depende del modelo; lo que AURA exige, no, y es lo único que se puede fijar.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from aura_skeleton.modules.providers_real import (
    _ESQUEMA_COGNITIVO,
    _SYSTEM,
    _SYSTEM_COGNITIVO,
    OllamaProvider,
)


class _Respuesta:
    """Doble de la respuesta de `urlopen`: solo lo que `_infer_sync` usa."""

    def __init__(self, payload: dict) -> None:
        self._cuerpo = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def _espia(monkeypatch, *, fallar_con_esquema: bool = False) -> list[dict]:
    """Captura los cuerpos de las peticiones. Devuelve la lista, en orden."""
    vistos: list[dict] = []

    def _falso_urlopen(req, timeout=None):  # noqa: ARG001
        cuerpo = json.loads(req.data.decode())
        vistos.append(cuerpo)
        if fallar_con_esquema and cuerpo.get("format") != "json":
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
        return _Respuesta({"response": json.dumps(
            {"say": "respuesta", "intent": "consulta", "action": "consulta", "args": {}})})

    monkeypatch.setattr(urllib.request, "urlopen", _falso_urlopen)
    return vistos


# ==================================================== EL ESQUEMA, COMO CONTRATO --


def test_el_esquema_exige_say_y_no_solo_la_clave():
    """`required` es la diferencia entre «el modelo puede omitir `say`» y «no puede».

    Y `minLength: 1` es la diferencia entre «la clave está» y «la clave dice algo»: sin él, la gramática
    aceptaría `{"say": ""}` y el usuario volvería a recibir el fallback con el contrato cumplido.
    """
    assert "say" in _ESQUEMA_COGNITIVO["required"]
    assert _ESQUEMA_COGNITIVO["properties"]["say"]["minLength"] == 1


def test_en_modo_cognitivo_el_modelo_NO_PUEDE_nombrar_una_accion():
    """La parte que importa para la seguridad.

    `action` es una CONSTANTE, no un string libre: en modo cognitivo el modelo no puede inventar una
    acción **ni siquiera al decodificar**. Medido antes de esto: inventó `"action":"consultar"` con
    `args` fabricados. No sustituye al catálogo, a los permisos ni al HITL — es una barrera más, aguas
    arriba, donde el problema todavía no existe.
    """
    accion = _ESQUEMA_COGNITIVO["properties"]["action"]
    assert accion.get("enum") == ["consulta"], accion
    assert "action" in _ESQUEMA_COGNITIVO["required"]


# ============================================== QUÉ SE LE PIDE EN CADA MODO --


def test_el_modo_COGNITIVO_pide_el_esquema(monkeypatch):
    vistos = _espia(monkeypatch)
    OllamaProvider("ollama", "m")._infer_sync("hola", "cognitivo")
    assert len(vistos) == 1
    assert vistos[0]["format"] == _ESQUEMA_COGNITIVO
    assert vistos[0]["system"] == _SYSTEM_COGNITIVO


def test_el_modo_ACCION_conserva_format_json(monkeypatch):
    """Caso de control, y es deliberado: en modo acción la elección la gobierna el catálogo.

    Constreñir `action` también aquí duplicaría esa autoridad en un segundo sitio, que es el error que
    `D-M-8` diagnostica en el propio sistema. Si alguien lo cambiara sin decidirlo, esto lo dice.
    """
    vistos = _espia(monkeypatch)
    OllamaProvider("ollama", "m")._infer_sync("enciende la luz", "accion")
    assert vistos[0]["format"] == "json"
    assert vistos[0]["system"] == _SYSTEM


# ======================================================= DEGRADACIÓN SEGURA --


def test_si_el_runtime_rechaza_el_esquema_se_degrada_UNA_vez(monkeypatch):
    """El esquema necesita Ollama >= 0.5. Con un runtime más antiguo el turno no se queda sin respuesta:
    se reintenta con el contrato previo. Se pierde la garantía de `say`, no la conversación."""
    vistos = _espia(monkeypatch, fallar_con_esquema=True)
    salida = OllamaProvider("ollama", "m")._infer_sync("hola", "cognitivo")
    assert json.loads(salida)["say"] == "respuesta"
    assert len(vistos) == 2, "debe reintentar exactamente una vez"
    assert vistos[0]["format"] == _ESQUEMA_COGNITIVO
    assert vistos[1]["format"] == "json"


def test_un_fallo_en_modo_ACCION_no_reintenta(monkeypatch):
    """El reintento es para la degradación del esquema, no un reintento general: duplicar toda
    inferencia fallida doblaría la latencia del peor caso en un hardware que ya tarda ~100 s."""
    vistos: list[dict] = []

    def _siempre_falla(req, timeout=None):  # noqa: ARG001
        vistos.append(json.loads(req.data.decode()))
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", _siempre_falla)
    with pytest.raises(urllib.error.HTTPError):
        OllamaProvider("ollama", "m")._infer_sync("enciende la luz", "accion")
    assert len(vistos) == 1


# ================================================ LO QUE NO HA CAMBIADO --


def test_la_separacion_de_prompts_sigue_intacta():
    """La mejora de 441,2 s a 237,0 s vino de separar los prompts. El esquema no la sustituye."""
    assert _SYSTEM_COGNITIVO != _SYSTEM
    assert len(_SYSTEM_COGNITIVO) < len(_SYSTEM)
    assert "NUNCA afirmes recordar" in _SYSTEM_COGNITIVO


def test_el_esquema_no_concede_autoridad_de_ejecucion():
    """Un esquema de salida no ejecuta nada. `action: "consulta"` es precisamente el valor que el
    orquestador trata como «no hay acción»: el motor, los permisos y el HITL siguen siendo la autoridad.
    """
    from aura_skeleton.core.permissions import CATALOGO

    # CORRECCIÓN DE UNA SUPOSICIÓN MÍA: creí que `consulta` no estaba en el catálogo. Sí está, y la
    # garantía real es mejor que mi conjetura: está declarada **verde y sin efecto** —«responder sin
    # actuar»—. Así que el único valor que el esquema permite es, por declaración del propio catálogo,
    # incapaz de mutar nada.
    assert CATALOGO["consulta"]["lista"] == "verde"
    assert CATALOGO["consulta"]["efecto"] == "ninguno"

    # Y es además el valor que el orquestador trata como «no hay acción»: con él no se llama al motor.
    import inspect

    from aura_skeleton.core.orchestrator import Orchestrator
    assert 'if action != "consulta":' in inspect.getsource(Orchestrator.on_turn)
