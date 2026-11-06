"""FORGET opera sobre la entrada concreta y retira sus ecos — DR-2 = A (CEO, 2026-09-15).

LO QUE LA DECISION EXIGE, y lo que estas pruebas fijan:

1. **Por entrada, no por texto.** `olvidar_informacion_usuario` localizaba por subcadena. Medido: con
   «mi ciudad favorita es Valencia» declarada como v1, cambiada a Sevilla y vuelta a Valencia (v3),
   «olvida eso» borraba v3 Y la v1 histórica, que nadie había nombrado.
2. **Se retiran los ecos.** Cada declaración deja un eco episódico «usuario dijo: ...» sin marcas. Tras
   olvidar, ese eco seguía entrando al contexto del modelo: el dato olvidado podía volver por su boca.
3. **Se conserva el historial.** Olvidar la versión vigente no destruye las anteriores, y el eco no se
   borra —es el registro de lo que el usuario dijo—: se retira de la recuperación normal.
4. **Nunca «Hecho» y después seguir afirmándolo** por ninguna vía: ni el Core, ni el contexto del modelo.

Los casos de ambigüedad y de subcadena del punto 6 y 7 de la misión viven en
`tests/integration/test_foco_sin_ambiguedad.py`; aquí se cubre lo que depende del contrato de la operación.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"


class _Espia:
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
    espia = _Espia()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno(orq, texto: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid)


async def _semanticas(s, contenido: str) -> list[dict]:
    return [e for e in await s.modelo_usuario.ver(UID) if e["contenido"] == contenido]


def _ecos(s, contenido: str) -> list[dict]:
    return [
        i
        for i in s.orquestador.memory._items
        if i["kind"] == "episodica" and i["content"] == f"usuario dijo: {contenido}"
    ]


def _segmentos_del_contexto(prompt: str) -> list[str]:
    inicio = prompt.index("[contexto memoria: ") + len("[contexto memoria: ")
    return prompt[inicio : prompt.index("]\n", inicio)].split(" | ")


# ------------------------------------------------------- 1 · V1 → V2 → olvidar V2 --

V1 = "mi cumpleaños es el 10 de mayo"
V2 = "mi cumpleaños es el 3 de junio"


@pytest.mark.asyncio
async def test_V1_V2_olvidar_la_vigente_la_retira_y_conserva_V1_como_historial(sistema):
    s, _ = sistema
    await _turno(s.orquestador, V1)
    await _turno(s.orquestador, V2)
    r = await _turno(s.orquestador, "olvida mi cumpleaños")
    assert "Hecho" in r["say"], r["say"]

    assert await _semanticas(s, V2) == [], "la vigente debia olvidarse"
    v1 = await _semanticas(s, V1)
    assert len(v1) == 1 and v1[0]["valid_until"] is not None, "el historial debia conservarse intacto"
    historial = await _turno(s.orquestador, "¿cuál era mi cumpleaños?")
    assert "10 de mayo" in historial["say"] and "3 de junio" not in historial["say"], historial["say"]


@pytest.mark.asyncio
async def test_tras_Hecho_ninguna_superficie_del_Core_sigue_afirmando_lo_olvidado(sistema):
    s, _ = sistema
    await _turno(s.orquestador, V1)
    await _turno(s.orquestador, V2)
    await _turno(s.orquestador, "olvida mi cumpleaños")
    for pregunta in ("¿cuál es mi cumpleaños?", "¿qué sabes de mí?"):
        r = await _turno(s.orquestador, pregunta)
        assert "3 de junio" not in r["say"], f"{pregunta!r} sigue afirmando lo olvidado: {r['say']!r}"


# ------------------------------------------------------- 2 · V1 → V2 → olvidar V1 --


@pytest.mark.asyncio
async def test_V1_V2_olvidar_la_antigua_por_su_nombre_no_toca_la_vigente(sistema):
    s, _ = sistema
    await _turno(s.orquestador, "mi destino favorito es Bangkok")
    await _turno(s.orquestador, "mi destino favorito es Barcelona")
    r = await _turno(s.orquestador, "olvida lo de Bangkok")
    assert "Hecho" in r["say"], r["say"]
    assert await _semanticas(s, "mi destino favorito es Bangkok") == []
    vigente = await _semanticas(s, "mi destino favorito es Barcelona")
    assert len(vigente) == 1 and vigente[0]["valid_until"] is None


# -------------------------------------------- 4 · 5 · TEXTO IDENTICO Y «OLVIDA ESO» --

VALENCIA = "mi ciudad favorita es Valencia"


@pytest.mark.asyncio
async def test_con_texto_identico_olvida_eso_retira_solo_la_version_señalada(sistema):
    """El caso medido: antes se iban v1 y v3 a la vez, porque la operacion localizaba por texto."""
    s, _ = sistema
    await _turno(s.orquestador, VALENCIA)
    await _turno(s.orquestador, "mi ciudad favorita es Sevilla")
    await _turno(s.orquestador, VALENCIA)
    assert len(await _semanticas(s, VALENCIA)) == 2, "precondicion: dos versiones de texto identico"

    await _turno(s.orquestador, "¿qué sabes de mí?")  # el foco queda en la vigente (v3)
    r = await _turno(s.orquestador, "olvida eso")
    assert "Hecho" in r["say"], r["say"]

    quedan = await _semanticas(s, VALENCIA)
    assert len(quedan) == 1, f"debia olvidarse SOLO la vigente, no tambien la historica identica: {quedan}"
    assert quedan[0]["valid_until"] is not None, "la que queda debe ser la version historica (v1)"


@pytest.mark.asyncio
async def test_con_texto_identico_el_eco_del_OTRO_turno_no_se_retira(sistema):
    """El eco se enlaza por su turno, no por su texto: el de v1 sigue siendo el registro de v1."""
    s, _ = sistema
    await _turno(s.orquestador, VALENCIA)
    await _turno(s.orquestador, "mi ciudad favorita es Sevilla")
    await _turno(s.orquestador, VALENCIA)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    await _turno(s.orquestador, "olvida eso")

    ecos = _ecos(s, VALENCIA)
    assert len(ecos) == 2, "los ecos no se borran: se retiran"
    retirados = [e for e in ecos if e["provenance"].get("retirada")]
    assert len(retirados) == 1, f"solo el eco del turno olvidado debia retirarse: {ecos}"


# ---------------------------------------------------- 8 · 9 · ECOS Y AUDITORIA --

COLOR = "mi color favorito es el verde"


@pytest.mark.asyncio
async def test_CONTROL_sin_olvidar_el_eco_SI_llega_al_contexto_del_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, "color favorito")
    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert f"usuario dijo: {COLOR}" in _segmentos_del_contexto(espia.prompts[-1])


@pytest.mark.asyncio
async def test_tras_olvidar_el_eco_no_vuelve_a_contaminar_el_contexto_del_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, COLOR)
    r = await _turno(s.orquestador, "olvida mi color favorito")
    assert "Hecho" in r["say"], r["say"]
    await _turno(s.orquestador, "color favorito")
    assert espia.prompts, "el turno debe llegar al modelo para que la prueba mida algo"
    assert f"usuario dijo: {COLOR}" not in _segmentos_del_contexto(espia.prompts[-1])


@pytest.mark.asyncio
async def test_tras_refutar_el_eco_tampoco_llega_al_contexto_del_modelo(sistema):
    s, espia = sistema
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, "¿qué sabes de mí?")
    r = await _turno(s.orquestador, "eso ya no es cierto")
    assert "corrijo" in r["say"], r["say"]
    await _turno(s.orquestador, "color favorito")
    assert f"usuario dijo: {COLOR}" not in _segmentos_del_contexto(espia.prompts[-1])


@pytest.mark.asyncio
async def test_el_eco_retirado_se_conserva_para_auditoria_con_su_motivo(sistema):
    s, _ = sistema
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, "olvida mi color favorito")
    ecos = _ecos(s, COLOR)
    assert len(ecos) == 1, "el eco no se borra: es el registro de lo que el usuario dijo"
    prov = ecos[0]["provenance"]
    assert prov.get("retirada") is True and prov.get("retirada_por") == "olvido", prov


@pytest.mark.asyncio
async def test_el_olvido_por_entrada_sobrevive_al_reinicio(sistema, tmp_path):
    """Trazabilidad persistente: lo olvidado sigue olvidado y lo historico sigue ahi tras recomponer."""
    s, _ = sistema
    await _turno(s.orquestador, V1)
    await _turno(s.orquestador, V2)
    await _turno(s.orquestador, "olvida mi cumpleaños")

    otra = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False))
    contenidos = {e["contenido"]: e for e in await otra.modelo_usuario.ver(UID)}
    assert V2 not in contenidos, "el olvido debe persistir"
    assert V1 in contenidos and contenidos[V1]["valid_until"] is not None, "y el historial tambien"


# ----------------------------------------------------------- EL CONTRATO DEL MOTOR --


@pytest.mark.asyncio
async def test_el_dry_run_nombra_tambien_los_ecos_que_retirara(sistema):
    """Quien aprueba un plan tiene que ver TODO su efecto (el mismo criterio que ya aplica el registro)."""
    s, _ = sistema
    await _turno(s.orquestador, COLOR)
    entrada = (await _semanticas(s, COLOR))[0]
    ejecutor = s.registro_adaptadores.para("olvidar_informacion_usuario")
    plan = await ejecutor.simular(
        "olvidar_informacion_usuario",
        {"user_id": UID, "entrada": {"contenido": entrada["contenido"], "ts": entrada["ts"]}},
        "t-plan",
    )
    assert plan["viable"] is True
    assert "1 entrada" in plan["efecto"] and "eco" in plan["efecto"], plan


@pytest.mark.asyncio
async def test_CONTROL_olvidarlo_todo_sigue_funcionando_sin_nombrar_entrada(sistema):
    s, _ = sistema
    await _turno(s.orquestador, COLOR)
    await _turno(s.orquestador, V1)
    n = await s.modelo_usuario.borrar(UID)
    assert n >= 2 and await s.modelo_usuario.ver(UID) == []
