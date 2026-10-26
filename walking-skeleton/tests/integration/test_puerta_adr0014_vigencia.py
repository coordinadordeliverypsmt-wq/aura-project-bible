"""La puerta de ADR-0014 decide con lo VIGENTE, no con `hits` crudos (CEO, 2026-10-06).

`memory.recall` devuelve tambien entradas que el Core ya no afirma: el eco episodico retirado por
olvido/refutacion (`provenance.retirada`), las refutadas y las superseded (`valid_until`). Si TODOS los
hits son no vigentes, la ausencia es un HECHO: responde el nucleo con la ausencia determinista y el
modelo NO es llamado. Ver `milestones/m3-entry/RESOLUCION-S3-CM2-ORDEN-CEO-2026-10-06.md` §1 y §2.

La correccion vive en la puerta, no en `recall`: la prueba (e) fija que `recall` sigue devolviendo el
eco retirado.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"
AUSENCIA = "No tengo ningun recuerdo registrado sobre eso."
_HECHO = "mi cumpleaños es el 10 de mayo"
_PREGUNTA = "¿mi cumpleaños?"


class _EspiaDePrompt:
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


@pytest.mark.asyncio
async def test_CONTROL_con_un_recuerdo_vigente_no_hay_ausencia_y_llega_al_contexto(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _HECHO)
    r = await _turno(s.orquestador, _PREGUNTA)
    assert r["say"] != AUSENCIA, r["say"]
    assert espia.prompts, "con memoria vigente el turno debe llegar al modelo"
    assert "10 de mayo" in espia.prompts[-1]


@pytest.mark.asyncio
async def test_tras_olvidar_el_hecho_la_consulta_da_la_ausencia_determinista_sin_llamar_al_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _HECHO)
    await _turno(s.orquestador, "¿qué sabes de mí?")  # fija el foco
    r = await _turno(s.orquestador, "olvida eso")
    assert "Hecho" in r["say"], r["say"]
    espia.prompts.clear()

    r = await _turno(s.orquestador, _PREGUNTA)

    assert r["say"] == AUSENCIA, r["say"]
    assert espia.prompts == [], "la ausencia es un hecho del Core: el modelo no debe ser llamado"


@pytest.mark.asyncio
async def test_tras_refutar_el_hecho_la_consulta_da_la_ausencia_determinista_sin_llamar_al_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, _HECHO)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    r = await _turno(s.orquestador, "eso ya no es cierto")
    assert "corrijo" in r["say"], r["say"]
    espia.prompts.clear()

    r = await _turno(s.orquestador, _PREGUNTA)

    assert r["say"] == AUSENCIA, r["say"]
    assert espia.prompts == [], "la ausencia es un hecho del Core: el modelo no debe ser llamado"


@pytest.mark.asyncio
async def test_superseded_con_version_vigente_no_da_ausencia(sistema):
    s, espia = sistema
    await _turno(s.orquestador, "mi cumpleaños es el 10 de mayo")
    await _turno(s.orquestador, "mi cumpleaños es el 3 de junio")
    r = await _turno(s.orquestador, "el cumpleaños")
    assert r["say"] != AUSENCIA, r["say"]
    assert espia.prompts, "hay una version vigente: el turno debe llegar al modelo"
    assert "3 de junio" in espia.prompts[-1]


@pytest.mark.asyncio
async def test_recall_sigue_devolviendo_el_eco_retirado_la_correccion_esta_en_la_puerta(sistema):
    s, _ = sistema
    await _turno(s.orquestador, _HECHO)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    await _turno(s.orquestador, "olvida eso")

    hits = await s.orquestador.memory.recall(UID, _PREGUNTA)

    retirados = [h for h in hits if (h.get("provenance") or {}).get("retirada")]
    assert retirados, f"recall debe seguir devolviendo el eco retirado (contrato intacto): {hits}"


# ------------------------------------------------ K TRUNCADO: la vigente no puede quedar fuera --

_CUMPLES = (
    "mi cumpleaños es el 10 de mayo",
    "mi cumpleaños es el 3 de junio",
    "mi cumpleaños es el 4 de julio",
    "mi cumpleaños es el 5 de agosto",
)
_PREGUNTA_CUMPLE = "¿mi cumpleaños?"


async def _cuatro_versiones_con_ecos_antiguos_retirados(s) -> list[dict]:
    """4 versiones; los ecos de v1..v3 retirados con la misma operacion que usa el olvido (`marcar`).

    Con k=3 y desempate por antiguedad, `recall` devuelve [eco v1 retirado, v1 superseded, eco v2
    retirado]: TODO no vigente, y la v4 vigente queda fuera del recorte.
    """
    for c in _CUMPLES:
        await _turno(s.orquestador, c)
    antiguos = tuple(f"usuario dijo: {c}" for c in _CUMPLES[:3])
    n = s.orquestador.memory.marcar(lambda i: i["content"] in antiguos, {"retirada": True})
    assert n == 3, "precondicion: tres ecos retirados"
    return await s.orquestador.memory.recall(UID, _PREGUNTA_CUMPLE)


@pytest.mark.asyncio
async def test_con_cuatro_versiones_la_vigente_desplazada_por_k_no_da_falsa_ausencia(sistema):
    s, espia = sistema
    hits = await _cuatro_versiones_con_ecos_antiguos_retirados(s)
    assert hits and all("5 de agosto" not in h["content"] for h in hits), f"precondicion: v4 fuera de k=3: {hits}"
    espia.prompts.clear()

    r = await _turno(s.orquestador, _PREGUNTA_CUMPLE)

    assert r["say"] != AUSENCIA, "falsa ausencia: hay una version vigente que recall(k=3) no devolvio"
    assert espia.prompts, "con una version vigente el turno debe llegar al modelo"
    assert "5 de agosto" in espia.prompts[-1]


@pytest.mark.asyncio
async def test_la_consulta_amplia_no_ensancha_el_contexto_mas_alla_de_los_hits_originales(sistema):
    s, espia = sistema
    hits = await _cuatro_versiones_con_ecos_antiguos_retirados(s)
    espia.prompts.clear()

    await _turno(s.orquestador, _PREGUNTA_CUMPLE)

    inicio = espia.prompts[-1].index("[contexto memoria: ") + len("[contexto memoria: ")
    segmentos = espia.prompts[-1][inicio : espia.prompts[-1].index("]\n", inicio)].split(" | ")
    assert 1 <= len(segmentos) <= len(hits), segmentos
    assert all("5 de agosto" in x for x in segmentos), "solo lo vigente entra al contexto"
