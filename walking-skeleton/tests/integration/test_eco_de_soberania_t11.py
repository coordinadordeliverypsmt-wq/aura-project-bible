"""T11 (CONTRATO-OLVIDO-Y-RETENCION.md §2): el eco de un turno de soberania NO se persiste.

Defecto medido [EJEC] 2026-10-07: «olvida que mi ciudad favorita es Valencia» se escribia, DESPUES de la
lapida, como `usuario dijo: olvida que mi ciudad favorita es Valencia` (episodica, vigente para
`_da_por_cierto`). El dato olvidado volvia al contexto del modelo y anulaba la ausencia determinista de
ADR-0014. Guardarlo ademas como `historico` seria otra copia en claro del contenido olvidado (contrato §5).
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"
AUSENCIA = "No tengo ningun recuerdo registrado sobre eso."
DECLARACION = "mi ciudad favorita es Valencia"
PREGUNTA = "¿cuál es mi ciudad favorita?"


class _EspiaDePrompt:
    name = "espia"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.prompts.append(prompt)
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "respuesta del modelo"})


def _componer(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    espia = _EspiaDePrompt()
    s.orquestador.router.providers = [espia]
    return s, espia


@pytest.fixture
def sistema(tmp_path):
    return _componer(tmp_path)


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


def _vigente(i: dict) -> bool:
    """Una entrada que el sistema aun afirma o puede recuperar: ni retirada, ni refutada, ni cerrada."""
    prov = i.get("provenance") or {}
    return not (prov.get("retirada") or prov.get("refutada") or i.get("valid_until") is not None)


def _vigentes_con(s, dato: str) -> list[str]:
    """Medicion sobre el contenido COMPLETO de la memoria (no un corte por indice: el olvido retira una
    entrada y la captura de senales anade otra, y un corte `[antes:]` no veria nada)."""
    return [
        str(i.get("content", ""))
        for i in s.orquestador.memory._items
        if dato in str(i.get("content", "")) and _vigente(i)
    ]


@pytest.mark.asyncio
async def test_CONTROL_sin_orden_de_olvido_la_pregunta_si_trae_valencia(sistema):
    s, espia = sistema
    await _turno(s.orquestador, DECLARACION)
    assert _vigentes_con(s, "Valencia"), "precondicion: la declaracion queda vigente en memoria"
    r = await _turno(s.orquestador, PREGUNTA)
    assert r["say"] != AUSENCIA, r["say"]
    # Respondio el Core con el hecho declarado o el modelo con el contexto: en ambos casos Valencia
    # llega por una via vigente. Asi la prueba mide algo cuando se omite la orden de olvido.
    assert "Valencia" in r["say"] or any("Valencia" in p for p in espia.prompts), (r["say"], espia.prompts)


@pytest.mark.asyncio
async def test_olvida_que_X_da_ausencia_determinista_y_no_filtra_al_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, DECLARACION)
    r = await _turno(s.orquestador, f"olvida que {DECLARACION}")
    assert "Hecho" in r["say"], r["say"]
    assert _vigentes_con(s, "Valencia") == [], "tras la orden queda una copia vigente del dato olvidado"
    espia.prompts.clear()

    r = await _turno(s.orquestador, PREGUNTA)

    assert r["say"] == AUSENCIA, r["say"]
    assert not any("Valencia" in p for p in espia.prompts), "el modelo recibio el dato olvidado"


@pytest.mark.asyncio
async def test_la_ausencia_y_la_falta_de_eco_sobreviven_al_reinicio(sistema, tmp_path):
    s, _ = sistema
    await _turno(s.orquestador, DECLARACION)
    await _turno(s.orquestador, f"olvida que {DECLARACION}")

    otra, espia = _componer(tmp_path)
    r = await _turno(otra.orquestador, PREGUNTA)

    assert r["say"] == AUSENCIA, r["say"]
    assert not any("Valencia" in p for p in espia.prompts)
    assert _vigentes_con(otra, "Valencia") == []
    assert not [i for i in otra.orquestador.memory._items if "olvida que" in str(i.get("content", ""))], (
        "el eco de la orden persistio en disco"
    )


@pytest.mark.asyncio
async def test_olvida_eso_tampoco_deja_eco_de_la_orden(sistema):
    s, _ = sistema
    await _turno(s.orquestador, DECLARACION)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    r = await _turno(s.orquestador, "olvida eso")
    assert "Hecho" in r["say"], r["say"]
    assert not [i for i in s.orquestador.memory._items if "olvida eso" in str(i.get("content", ""))]
    assert _vigentes_con(s, "Valencia") == []


@pytest.mark.asyncio
async def test_refutar_no_deja_copia_vigente_ni_filtra_al_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, DECLARACION)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    r = await _turno(s.orquestador, "eso ya no es cierto")
    assert "corrijo" in r["say"], r["say"]
    assert not [i for i in s.orquestador.memory._items if "ya no es cierto" in str(i.get("content", ""))]
    assert _vigentes_con(s, "Valencia") == []
    espia.prompts.clear()
    r = await _turno(s.orquestador, PREGUNTA)
    assert r["say"] == AUSENCIA, r["say"]
    assert not any("Valencia" in p for p in espia.prompts)


# ---------------------------- A1: la CAPTURA DE SENALES tampoco aporta nada en un turno de soberania --

CUMPLE = "mi cumpleaños es el 3 de junio"
OLVIDALO = f"olvídalo, {CUMPLE}"


@pytest.mark.asyncio
async def test_olvidalo_con_la_declaracion_dentro_no_la_deja_capturada_como_vigente(sistema):
    """Reproducido por ECC: la captura guardaba ('semantica', 'olvídalo, mi cumpleaños es el 3 de junio')
    vigente, y la pregunta la llevaba al LLM dentro de `[contexto memoria: ...]`."""
    s, espia = sistema
    await _turno(s.orquestador, CUMPLE)
    await _turno(s.orquestador, "¿qué sabes de mí?")  # fija el foco
    r = await _turno(s.orquestador, OLVIDALO)
    assert "Hecho" in r["say"], r["say"]
    assert _vigentes_con(s, "3 de junio") == [], "la captura dejo vigente lo que el usuario acaba de olvidar"
    espia.prompts.clear()

    await _turno(s.orquestador, "¿cuándo es mi cumpleaños?")

    assert not any("3 de junio" in p for p in espia.prompts), "el LLM recibio el dato olvidado"


@pytest.mark.asyncio
async def test_CONTROL_la_misma_declaracion_fuera_de_una_orden_de_soberania_si_se_captura(sistema):
    s, _ = sistema
    await _turno(s.orquestador, CUMPLE)
    assert _vigentes_con(s, "3 de junio"), "sin orden de soberania la declaracion SI queda capturada/vigente"
