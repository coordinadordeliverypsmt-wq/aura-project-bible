"""La ventana de diálogo: cuánto recuerda AURA de la conversación y cuánto le cuesta — DR-4 (2026-09-15).

MEDIDO en HC-1 con Ollama real (`milestones/m3-entry/evidencia-cognicion-local/`): la ventana de 6 turnos
deslizaba turno a turno; al descartar el más antiguo cambiaba el PRINCIPIO del buffer y la caché de
prefijo del modelo se invalidaba entera. Turno 8: 144,8 s de ingesta y 187,8 s de turno.

Estas pruebas no miden latencia —eso lo hace la campaña, con el modelo real—. Fijan, sin modelo y de
forma determinista, las tres propiedades de las que depende todo lo demás:

1. **El suelo de memoria.** Una vez alcanzados, AURA nunca ve MENOS de `_DIALOG_N` turnos previos. DR-4
   exige no sacrificar en silencio la memoria conversacional: descartar por bloques no puede significar
   recordar menos.
2. **Qué se recorta.** Solo lo que dijo AURA, y solo en el prompt. Lo que dijo el usuario reentra íntegro,
   y el buffer no se modifica.
3. **La propiedad de caché.** Entre dos turnos seguidos sin descarte, el buffer del segundo EMPIEZA por el
   del primero. Es lo que permite al modelo reutilizar lo ya evaluado.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"
_SAY_LARGO = "La respuesta del modelo es deliberadamente larga para que el recorte tenga algo que cortar. " * 4
_PREGUNTAS = [f"que es un volcan numero {i}?" for i in range(1, 15)]


class _Espia:
    name = "espia"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.prompts.append(prompt)
        return json.dumps({"action": "consulta", "say": _SAY_LARGO})


def _sistema(tmp_path, *, n: int, maximo: int, recorte: int | None):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    espia = _Espia()
    s.orquestador.router.providers = [espia]
    s.orquestador._DIALOG_N, s.orquestador._DIALOG_MAX, s.orquestador._RECORTE_AURA = n, maximo, recorte
    return s, espia


async def _conversar(s, turnos: int) -> None:
    for pregunta in _PREGUNTAS[:turnos]:
        tid = uuid.uuid4().hex[:12]
        await s.orquestador.handle_utterance(UID, pregunta, tid)
        await s.orquestador.wait(tid)


def _buffer(prompt: str) -> str:
    return prompt.split("[conversacion reciente:\n", 1)[1].split("]\nUsuario:", 1)[0]


def _previos(prompt: str) -> int:
    return _buffer(prompt).count("(previo)")


@pytest.mark.asyncio
async def test_LA_POLITICA_VIGENTE_es_la_que_la_medicion_sostiene(tmp_path):
    """Los valores por defecto no se eligen: salen de la campaña 4 (DR-4).

    Turnos 8-12 de cuatro conversaciones reales de 12 turnos en HC-1: deslizante 6 → 5 de 5 turnos por
    encima de 180 s; solo recorte → 2 de 5; solo bloques → 0 de 5; ambas → 0 de 5 y la mediana del turno
    más baja (75,9 s). Si alguien cambia estos números, esta prueba obliga a volver a medir.
    """
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    orq = componer(config).orquestador
    assert (orq._DIALOG_N, orq._DIALOG_MAX, orq._RECORTE_AURA) == (6, 9, 160)


@pytest.mark.asyncio
async def test_la_politica_vigente_recuerda_al_menos_tanto_como_la_anterior(tmp_path):
    """DR-4 prohíbe sacrificar memoria conversacional en silencio: con la política vigente AURA nunca ve
    menos turnos previos que con la ventana deslizante de 6 que había antes."""
    s, espia = _sistema(tmp_path, n=6, maximo=9, recorte=160)
    await _conversar(s, 12)
    vigente = [_previos(p) for p in espia.prompts]
    s2, espia2 = _sistema(tmp_path / "antes", n=6, maximo=6, recorte=None)
    await _conversar(s2, 12)
    anterior = [_previos(p) for p in espia2.prompts]
    assert all(v >= a for v, a in zip(vigente, anterior, strict=True)), (vigente, anterior)


@pytest.mark.asyncio
async def test_todas_las_preguntas_de_la_prueba_llegan_al_modelo(tmp_path):
    """Precondicion de todo el fichero: si alguna la atendiera otra superficie, no se mediria la ventana."""
    s, espia = _sistema(tmp_path, n=6, maximo=6, recorte=None)
    await _conversar(s, 12)
    assert len(espia.prompts) == 12


# -------------------------------------------------------------- 1 · EL SUELO --


@pytest.mark.asyncio
async def test_la_ventana_deslizante_ve_siempre_los_ultimos_N_turnos(tmp_path):
    s, espia = _sistema(tmp_path, n=6, maximo=6, recorte=None)
    await _conversar(s, 12)
    assert [_previos(p) for p in espia.prompts] == [0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6]


@pytest.mark.asyncio
async def test_el_descarte_por_bloques_nunca_recuerda_menos_que_la_ventana_deslizante(tmp_path):
    """El suelo de DR-4: descartar por bloques NO puede significar recordar menos."""
    s, espia = _sistema(tmp_path, n=6, maximo=9, recorte=None)
    await _conversar(s, 14)
    previos = [_previos(p) for p in espia.prompts]
    assert previos == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 6, 7, 8, 9], previos
    assert all(p >= min(i, 6) for i, p in enumerate(previos)), "nunca menos turnos que la ventana deslizante"


# ------------------------------------------------------------ 2 · EL RECORTE --


@pytest.mark.asyncio
async def test_el_recorte_solo_afecta_a_lo_que_dijo_AURA_y_lo_marca(tmp_path):
    s, espia = _sistema(tmp_path, n=6, maximo=6, recorte=40)
    await _conversar(s, 3)
    lineas = _buffer(espia.prompts[-1]).splitlines()
    assert len(lineas) == 2
    for linea, pregunta in zip(lineas, _PREGUNTAS, strict=False):
        assert f"tu: {pregunta} |" in linea, "lo que dijo el usuario reentra integro"
        assert linea.endswith(" [...]"), "el extracto de AURA se marca como extracto"
        assert _SAY_LARGO not in linea


@pytest.mark.asyncio
async def test_el_recorte_no_modifica_el_buffer_guardado(tmp_path):
    s, _ = _sistema(tmp_path, n=6, maximo=6, recorte=40)
    await _conversar(s, 2)
    assert all(t.aura == _SAY_LARGO for t in s.orquestador._dialogue[UID])


@pytest.mark.asyncio
async def test_CONTROL_sin_recorte_la_respuesta_previa_reentra_integra(tmp_path):
    s, espia = _sistema(tmp_path, n=6, maximo=6, recorte=None)
    await _conversar(s, 2)
    assert _SAY_LARGO in _buffer(espia.prompts[-1])


# --------------------------------------------------- 3 · LA PROPIEDAD DE CACHE --


def _turnos_con_prefijo_estable(prompts: list[str]) -> list[bool]:
    buffers = [_buffer(p) for p in prompts]
    # El primero lleva «(inicio de la conversacion)» y no es prefijo de nada: se compara desde el segundo.
    return [buffers[i].startswith(buffers[i - 1]) for i in range(2, len(buffers))]


@pytest.mark.asyncio
async def test_MEDIDO_la_ventana_deslizante_rompe_el_prefijo_en_cada_turno_desde_el_octavo(tmp_path):
    """El defecto medido, fijado como propiedad: a partir del turno 8 ningun buffer empieza por el anterior."""
    s, espia = _sistema(tmp_path, n=6, maximo=6, recorte=None)
    await _conversar(s, 12)
    estables = _turnos_con_prefijo_estable(espia.prompts)  # turnos 3..12
    assert estables == [True, True, True, True, True, False, False, False, False, False], estables


@pytest.mark.asyncio
async def test_el_descarte_por_bloques_solo_rompe_el_prefijo_en_el_turno_del_descarte(tmp_path):
    s, espia = _sistema(tmp_path, n=6, maximo=9, recorte=None)
    await _conversar(s, 14)
    estables = _turnos_con_prefijo_estable(espia.prompts)  # turnos 3..14
    rotos = [i + 3 for i, ok in enumerate(estables) if not ok]
    assert rotos == [11], f"el prefijo solo puede romperse al descartar el bloque: turnos {rotos}"


@pytest.mark.asyncio
async def test_el_recorte_conserva_la_propiedad_de_cache(tmp_path):
    """Recortar tiene que ser DETERMINISTA: el mismo turno previo produce el mismo extracto en cada prompt.
    Si el recorte dependiera de la posicion o del turno actual, rompería el prefijo en cada turno."""
    s, espia = _sistema(tmp_path, n=6, maximo=9, recorte=40)
    await _conversar(s, 10)
    assert all(_turnos_con_prefijo_estable(espia.prompts))
