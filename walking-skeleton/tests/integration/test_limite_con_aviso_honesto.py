"""Límite con aviso honesto — DR-3 (CEO, 2026-09-15).

DEFECTO. Un timeout del proveedor llegaba al orquestador como cualquier fallo, y AURA respondía «Mi
modelo local no está disponible ahora mismo» —falso: estaba disponible, solo tardó—. Además el router
abría el circuito, así que el turno siguiente fallaba igual SIN llamar al modelo. Y una respuesta cortada
por el tope de generación dejaba JSON inválido y AURA decía «No entendí bien», también falso.

LO QUE LA DECISIÓN EXIGE: detener la espera, no inventar resultado, no presentar una respuesta parcial
como completa, y decir con claridad que no se pudo completar dentro del límite. Sin subir el timeout.

Se prueba a TRES alturas, porque cada una puede romper la garantía por su cuenta: el proveedor real
(que convierte el timeout y el corte en un límite declarado), el router (que no debe abrir el circuito ni
reintentar) y el orquestador (que debe decirlo con honestidad).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estatus import Estatus
from aura_skeleton.modules.providers_real import LIMITE_GENERACION_COGNITIVA, OllamaProvider
from aura_skeleton.modules.router import LimiteDelProveedor, ModelRouter

UID = "mauricio"
PREGUNTA = "¿por qué el cielo es azul?"  # cognitiva, referente mundo: llega al modelo
_NO_DISPONIBLE = "Mi modelo local no está disponible ahora mismo; inténtalo de nuevo en unos minutos."


class _Respuesta:
    def __init__(self, payload: dict) -> None:
        self._cuerpo = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def _ollama_falso(monkeypatch, comportamientos: list):
    """`urlopen` falso que consume una respuesta o una excepcion por llamada. Devuelve los cuerpos vistos."""
    vistos: list[dict] = []

    def _urlopen(req, timeout=None):  # noqa: ARG001
        vistos.append(json.loads(req.data.decode()))
        siguiente = comportamientos.pop(0)
        if isinstance(siguiente, BaseException):
            raise siguiente
        return _Respuesta(siguiente)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    return vistos


_OK = {"response": json.dumps({"action": "consulta", "say": "Por la dispersión de la luz."}), "done_reason": "stop"}


@pytest.fixture
def sistema_real(tmp_path):
    """Composicion real con el PROVEEDOR REAL de Ollama delante de un `urlopen` falso."""
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    s.orquestador.router.providers = [OllamaProvider("ollama", "qwen2.5:0.5b", timeout_s=5)]
    s.orquestador.router._circuitos = {}
    return s


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


# ================================================================ EXTREMO A EXTREMO --


@pytest.mark.asyncio
async def test_un_timeout_se_dice_como_limite_y_no_como_modelo_no_disponible(sistema_real, monkeypatch):
    _ollama_falso(monkeypatch, [TimeoutError("timed out")])
    r = await _turno(sistema_real.orquestador, PREGUNTA)
    assert r["say"] != _NO_DISPONIBLE, "un timeout no es un modelo caido"
    assert "tiempo límite" in r["say"] and "a medias" in r["say"], r["say"]
    assert r["estatus"] == Estatus.ABSTENCION.value and r["provider"] == "core", r


@pytest.mark.asyncio
async def test_un_timeout_envuelto_en_URLError_tambien_es_un_limite(sistema_real, monkeypatch):
    _ollama_falso(monkeypatch, [urllib.error.URLError(TimeoutError("timed out"))])
    r = await _turno(sistema_real.orquestador, PREGUNTA)
    assert "tiempo límite" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_una_respuesta_cortada_por_el_tope_no_se_entrega_a_medias(sistema_real, monkeypatch):
    cortada = {
        "response": '{"action": "consulta", "say": "La luz del sol se dispersa en la atmos',
        "done_reason": "length",
    }
    _ollama_falso(monkeypatch, [cortada])
    r = await _turno(sistema_real.orquestador, PREGUNTA)
    assert "incompleta" in r["say"] and "a medias" in r["say"], r["say"]
    assert "atmos" not in r["say"], "el fragmento generado no se presenta como respuesta"
    assert "No entendi bien" not in r["say"], "el modelo entendio: se extendio"


@pytest.mark.asyncio
async def test_CONTROL_una_respuesta_dentro_del_limite_se_entrega_normal(sistema_real, monkeypatch):
    _ollama_falso(monkeypatch, [_OK])
    r = await _turno(sistema_real.orquestador, PREGUNTA)
    assert "dispersión de la luz" in r["say"], r["say"]
    assert r["estatus"] == Estatus.PROPUESTA.value, r


@pytest.mark.asyncio
async def test_tras_un_timeout_el_turno_siguiente_vuelve_a_llamar_y_responde(sistema_real, monkeypatch):
    """Recuperacion: el timeout no abre el circuito, asi que el siguiente turno llama y contesta."""
    vistos = _ollama_falso(monkeypatch, [TimeoutError("timed out"), _OK])
    await _turno(sistema_real.orquestador, PREGUNTA)
    r = await _turno(sistema_real.orquestador, PREGUNTA)
    assert "dispersión de la luz" in r["say"], r["say"]
    assert len(vistos) == 2, "exactamente una llamada por turno"


@pytest.mark.asyncio
async def test_un_timeout_no_duplica_la_llamada(sistema_real, monkeypatch):
    vistos = _ollama_falso(monkeypatch, [TimeoutError("timed out"), _OK, _OK])
    await _turno(sistema_real.orquestador, PREGUNTA)
    assert len(vistos) == 1, f"un limite alcanzado no se reintenta: {len(vistos)} llamadas"


# ======================================================================= PROVEEDOR --


def test_el_modo_cognitivo_pide_el_tope_de_generacion(monkeypatch):
    vistos = _ollama_falso(monkeypatch, [_OK])
    OllamaProvider("ollama", "m")._infer_sync("hola", "cognitivo")
    assert vistos[0]["options"] == {"num_predict": LIMITE_GENERACION_COGNITIVA}


def test_el_modo_accion_no_lleva_tope(monkeypatch):
    vistos = _ollama_falso(monkeypatch, [{"response": "{}", "done_reason": "stop"}])
    OllamaProvider("ollama", "m")._infer_sync("enciende la luz", "accion")
    assert "options" not in vistos[0]


def test_la_degradacion_del_esquema_conserva_el_tope(monkeypatch):
    vistos = _ollama_falso(monkeypatch, [urllib.error.HTTPError("u", 400, "Bad", {}, None), _OK])
    OllamaProvider("ollama", "m")._infer_sync("hola", "cognitivo")
    assert len(vistos) == 2 and vistos[1]["format"] == "json"
    assert vistos[1]["options"] == {"num_predict": LIMITE_GENERACION_COGNITIVA}


def test_un_error_http_que_no_es_timeout_no_se_disfraza_de_limite(monkeypatch):
    _ollama_falso(monkeypatch, [urllib.error.URLError("connection refused")])
    with pytest.raises(urllib.error.URLError) as exc:
        OllamaProvider("ollama", "m")._infer_sync("hola", "cognitivo")
    assert not isinstance(exc.value, LimiteDelProveedor)


# ========================================================================== ROUTER --


class _Proveedor:
    def __init__(self, name: str, error: BaseException | None = None) -> None:
        self.name = name
        self.error = error
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        if self.error is not None:
            raise self.error
        return json.dumps({"action": "consulta", "say": "ok"})


@pytest.mark.asyncio
async def test_el_router_no_abre_el_circuito_ni_prueba_otro_proveedor_ante_un_limite():
    lento = _Proveedor("lento", LimiteDelProveedor("tiempo"))
    respaldo = _Proveedor("respaldo")
    router = ModelRouter([lento, respaldo], 1000)
    with pytest.raises(LimiteDelProveedor):
        await router.route("hola", "t-1", "cognitivo")
    assert router.estado_circuitos()["lento"] == "CERRADO", "un limite no es un proveedor caido"
    assert respaldo.llamadas == 0, "repetir la inferencia doblaria la espera del peor caso"


@pytest.mark.asyncio
async def test_CONTROL_un_fallo_real_sigue_abriendo_el_circuito():
    roto = _Proveedor("roto", RuntimeError("connection refused"))
    respaldo = _Proveedor("respaldo")
    router = ModelRouter([roto, respaldo], 1000)
    nombre, _ = await router.route("hola", "t-1", "cognitivo")
    assert nombre == "respaldo" and router.estado_circuitos()["roto"] == "ABIERTO"
