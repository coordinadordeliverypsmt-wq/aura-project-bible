"""Declaración de hecho propio sin LLM: «me llamo Mauricio» lo acusa el Core (2026-09-13).

Defecto medido: una declaración no era pregunta ni orden, recorría la cascada entera y llegaba al
modelo (263 s con Ollama real) para devolver un «Entendido.». El hecho lo registraba —y lo sigue
registrando— la captura de señales, que corre DESPUÉS de decidir la respuesta.

Se compone AURA de producción (`componer`, stack mock) y se sustituyen los proveedores por un espía
que CUENTA llamadas: «0 LLM» es un contador que tendría que moverse, no una lectura del código.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estatus import MARCA_PROPUESTA, Estatus
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.senales import ClaseSenal

UID = "mauricio"


class _Espia:
    name = "espia"

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, str]] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas.append((prompt, modo))
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "MARCA-MODELO"})


@pytest.fixture
def sistema(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    espia = _Espia()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


async def _hechos(sistema_) -> list[dict]:
    return [e for e in await sistema_.modelo_usuario.ver(UID) if e["clase"] == ClaseSenal.HECHO_DECLARADO.value]


def _es_acuse_de_declaracion(r: dict) -> bool:
    return (
        r["provider"] == "core"
        and r["dominio"] == "declaracion"
        and r["say"] == "Entendido."
        and r["estatus"] == Estatus.HECHO.value
    )


# ---------------------------------------------------------------- A · B --


async def test_A_me_llamo_se_acusa_en_el_core_sin_modelo_y_el_hecho_se_captura(sistema):
    s, espia = sistema
    r = await _turno(s.orquestador, "me llamo Mauricio")
    assert espia.llamadas == [], "una declaración de hecho propio no puede llegar al modelo"
    assert _es_acuse_de_declaracion(r), r
    assert not r["say"].startswith(MARCA_PROPUESTA)
    # La captura sigue ocurriendo: el acuse no la sustituye.
    assert any(h["contenido"] == "me llamo Mauricio" for h in await _hechos(s)), await s.modelo_usuario.ver(UID)


async def test_B_despues_como_me_llamo_es_HECHO_sin_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, "me llamo Mauricio")
    r = await _turno(s.orquestador, "¿cómo me llamo?")
    assert espia.llamadas == []
    assert r["say"] == "Te llamas Mauricio." and r["estatus"] == Estatus.HECHO.value, r


async def test_B_control_sin_declaracion_como_me_llamo_no_inventa_el_nombre(sistema):
    """Control de B: si la respuesta no viniera del hecho capturado, sin declararlo saldría igual."""
    s, _ = sistema
    r = await _turno(s.orquestador, "¿cómo me llamo?")
    assert "Mauricio" not in r["say"], r


# ---------------------------------------------------------------- C · AMP --


async def test_C_cumpleanos_se_acusa_sin_modelo_se_responde_y_se_versiona(sistema):
    s, espia = sistema
    r = await _turno(s.orquestador, "mi cumpleaños es el 10 de mayo")
    assert _es_acuse_de_declaracion(r), r
    v1 = [h for h in await _hechos(s) if h["contenido"] == "mi cumpleaños es el 10 de mayo"]
    assert len(v1) == 1 and v1[0]["version"] == 1 and v1[0]["supersedes"] is None, v1

    # Forma soportada por la ruta existente (hechos posesivos generales): «¿Cuál es mi cumpleaños?».
    r = await _turno(s.orquestador, "¿Cuál es mi cumpleaños?")
    assert r["provider"] == "core" and r["estatus"] == Estatus.HECHO.value, r
    assert "10 de mayo" in r["say"], r

    r = await _turno(s.orquestador, "mi cumpleaños es el 3 de junio")
    assert _es_acuse_de_declaracion(r), r
    v2 = [h for h in await _hechos(s) if h["contenido"] == "mi cumpleaños es el 3 de junio"]
    assert len(v2) == 1 and v2[0]["version"] == 2 and v2[0]["supersedes"] == 1, v2
    assert espia.llamadas == [], "ni declarar, ni preguntar, ni redeclarar pasa por el modelo"


# ---------------------------------------------------------------- D · E --


async def test_D_hecho_de_un_tercero_no_se_captura_y_conserva_el_camino_del_modelo(sistema):
    s, espia = sistema
    r = await _turno(s.orquestador, "mi abuela es enfermera")
    assert not any("abuela" in h["contenido"] for h in await _hechos(s))
    assert len(espia.llamadas) == 1, "un hecho de un tercero no es declaración propia: camino anterior"
    assert r["dominio"] != "declaracion" and r["estatus"] == Estatus.PROPUESTA.value, r


@pytest.mark.parametrize("texto", ["Hoy tuve un día difícil", "me gusta el jazz"])
async def test_E_lo_que_no_es_hecho_propio_conserva_su_camino(sistema, texto):
    """Medido: ambas llegan al modelo (1 llamada) — `me gusta` es PREFERENCIA, no HECHO_DECLARADO."""
    s, espia = sistema
    r = await _turno(s.orquestador, texto)
    assert len(espia.llamadas) == 1, r
    assert r["dominio"] != "declaracion", r


async def test_E_declaracion_que_ademas_pide_una_accion_llega_al_router(sistema):
    s, espia = sistema
    r = await _turno(s.orquestador, "me llamo Mauricio y enciende la luz")
    assert len(espia.llamadas) == 1, "la compuerta de acción no puede tragarse una orden"
    assert espia.llamadas[0][1] == "accion"
    assert r["dominio"] != "declaracion", r


# ---------------------------------------------------------------- F · cableado --


async def test_F_sin_el_reconocedor_inyectado_la_declaracion_vuelve_al_modelo(sistema):
    """Lo que activa la garantía es el cableado de `composicion`, no un efecto lateral de la cascada."""
    s, espia = sistema
    assert s.orquestador.reconocer_declaracion is not None
    s.orquestador.reconocer_declaracion = None
    r = await _turno(s.orquestador, "me llamo Mauricio")
    assert len(espia.llamadas) == 1 and r["dominio"] != "declaracion", r


def test_F_el_parametro_es_opcional_y_por_defecto_no_cambia_nada():
    import inspect

    assert inspect.signature(Orchestrator.__init__).parameters["reconocer_declaracion"].default is None


# ---------------------------------------------------------------- G · ADR-0017 --


async def test_G_color_favorito_se_acusa_sin_modelo_y_se_responde_literal(sistema):
    s, espia = sistema
    r = await _turno(s.orquestador, "mi color favorito es el azul")
    assert _es_acuse_de_declaracion(r), r
    r = await _turno(s.orquestador, "¿Cuál es mi color favorito?")
    assert "azul" in r["say"] and r["estatus"] == Estatus.HECHO.value, r
    assert espia.llamadas == []
