"""Órdenes habladas que el Core responde de forma determinista, sin valores libres (CM1, v2).

Con gramática cerrada Vosk FUERZA lo que oye a la frase más cercana (`escucha.py` lo documenta con
«aurora»). Por eso la lista NO puede contener declaraciones con valor libre: «me llamo Pedro» se
convertiría en «me llamo mauricio» y corrompería la memoria. Y cada entrada tiene que ser algo que el
Core responde de verdad, o la gramática prometería una orden que no existe (INV-9).
"""

from __future__ import annotations

import asyncio
import re
import sys
import unicodedata
from pathlib import Path

import pytest

from aura_skeleton.core.ordenes_deterministas import ORDENES_DE_VOZ

sys.path.insert(0, str(Path(__file__).parent))
from test_hecho_declarado_sin_llm import _sistema, _turno  # noqa: E402

from aura_skeleton.modules.memory import SimpleMemory  # noqa: E402


def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def test_hay_ordenes_y_estan_en_minusculas_sin_puntuacion():
    assert len(ORDENES_DE_VOZ) >= 10 and len(set(ORDENES_DE_VOZ)) == len(ORDENES_DE_VOZ)
    for o in ORDENES_DE_VOZ:
        assert o == o.lower().strip() and not re.search(r"[¿?¡!.,;:]", o), o


def test_conserva_las_tildes_que_el_modelo_de_vosk_conoce():
    """La forma hablada lleva tilde («cómo»): sin ella Vosk no tiene la palabra en el vocabulario."""
    assert "cómo me llamo" in ORDENES_DE_VOZ and "cuál es mi color favorito" in ORDENES_DE_VOZ


_DECLARATIVAS = re.compile(r"^(me llamo|mi .+ es\b|mi .+ son\b|soy\b|trabajo\b|vivo\b|tengo\b|prefiero\b|me gusta\b)")


def test_ninguna_entrada_es_una_declaracion_con_valor_libre():
    for o in ORDENES_DE_VOZ:
        assert not _DECLARATIVAS.match(_sin_tildes(o)), f"declaración con valor libre: {o!r}"


def test_el_detector_de_declaraciones_de_la_prueba_atrapa_las_declaraciones():
    """Control de la prueba anterior: si el patrón no reconociera ni «me llamo Pedro», sería decorativa."""
    for d in ("me llamo pedro", "mi color favorito es el azul", "soy ingeniero", "trabajo en una fábrica"):
        assert _DECLARATIVAS.match(d), d


@pytest.mark.parametrize("orden", ORDENES_DE_VOZ)
def test_cada_orden_la_responde_el_Core_sin_llamar_al_modelo_ni_caer_en_la_pared_de_memoria(orden):
    """Si alguna no, no pertenece a la lista: la gramática la ofrecería a Vosk sin que exista."""
    orq, espia = _sistema(SimpleMemory())
    res = asyncio.run(_turno(orq, f"¿{orden}?"))
    assert res.get("provider") == "core", (orden, res)
    assert res.get("dominio") not in ("memoria", "llm", ""), (orden, res.get("dominio"))
    assert espia.llamadas == 0


def test_el_control_de_la_prueba_una_frase_no_soportada_SI_cae_en_la_pared():
    """Sin esto la prueba anterior podría pasar con cualquier frase."""
    orq, _ = _sistema(SimpleMemory())
    res = asyncio.run(_turno(orq, "¿qué hora es?"))
    assert res.get("dominio") == "memoria"
