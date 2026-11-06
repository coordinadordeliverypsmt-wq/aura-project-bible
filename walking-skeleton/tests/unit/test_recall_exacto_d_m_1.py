"""D-M-1 A′: la recuperación léxica N1 es EXACTA respecto al barrido completo, también en el régimen
ubicuo (>256 posteos) que antes producía falsos negativos.

Oráculo = fuerza bruta (alternativa B del DP): recorre TODOS los recuerdos del usuario y puntúa por el
MISMO criterio de cobertura que `recall`. Toda prueba compara `recall` contra ese oráculo.

Aprobación: `decisiones/2026-10-12-D-M-1-aprobacion-construccion.md`. DP:
`milestones/m3-entry/DP-D-M-1-RECUPERACION-EXACTA.md`.
"""

from __future__ import annotations

import os
import random

import pytest

from aura_skeleton.contracts import es_recuperable
from aura_skeleton.modules.memory import _COBERTURA_MINIMA, PersistentMemory, _terminos


def _fuerza_bruta(items: list[dict], user_id: str, query: str, k: int = 3) -> list[dict]:
    """Oráculo: mismo criterio de cobertura que recall, pero mirando TODOS los recuerdos del usuario."""
    consulta = _terminos(query)
    if not consulta:
        return []
    minimo = _COBERTURA_MINIMA * len(consulta)
    puntuados = [
        (idx, len(consulta & _terminos(it["content"])))
        for idx, it in enumerate(items)
        if it["user_id"] == user_id and es_recuperable(it)
    ]
    mejores = sorted(((i, n) for i, n in puntuados if n >= minimo), key=lambda p: (-p[1], p[0]))[:k]
    return [items[i] for i, _ in mejores]


def _contenidos(hits: list[dict]) -> list[str]:
    return [h["content"] for h in hits]


async def _mem(tmp_path, nombre="m.jsonl") -> PersistentMemory:
    return PersistentMemory(os.path.join(tmp_path, nombre))


# --------------------------------------------- EL DEFECTO D-M-1 (régimen ubicuo) --


@pytest.mark.asyncio
async def test_D_M_1_regimen_ubicuo_NO_produce_falso_negativo(tmp_path):
    """Contraejemplo del DP §1: con >256 recuerdos que comparten un término de contenido, el recuerdo
    cuyo único solape son esos términos ubicuos SÍ se recupera (antes: `recall` devolvía [])."""
    mem = await _mem(tmp_path)
    for i in range(300):
        await mem.write("u", "semantica", f"trabajo nota numero {i}", {"origen": "declarada"})
    for i in range(300):
        await mem.write("u", "semantica", f"reunion apunte numero {i}", {"origen": "declarada"})
    await mem.write("u", "semantica", "mi trabajo tiene una reunion importante", {"origen": "declarada"})
    await mem.write("u", "semantica", "nota xyzterm sin relacion alguna", {"origen": "declarada"})

    q = "trabajo reunion xyzterm"
    hits = await mem.recall("u", q, k=3)
    oraculo = _fuerza_bruta(mem._items, "u", q, k=3)
    assert _contenidos(hits) == _contenidos(oraculo), "recall debe coincidir con la fuerza bruta"
    assert any("mi trabajo tiene una reunion importante" in c for c in _contenidos(hits)), (
        "el recuerdo objetivo (cobertura 2/3) no puede perderse por términos ubicuos"
    )


@pytest.mark.asyncio
async def test_cota_activada_todos_los_terminos_ubicuos_sigue_exacto(tmp_path):
    """Peor caso de A (todos los términos de la consulta ubicuos): la cota α=1 dispara el barrido
    completo y el resultado sigue coincidiendo con la fuerza bruta."""
    mem = await _mem(tmp_path)
    for i in range(300):
        await mem.write("u", "semantica", f"alfa beta relleno {i}", {"origen": "declarada"})
    await mem.write("u", "semantica", "alfa beta son mis dos palabras clave", {"origen": "declarada"})
    q = "alfa beta"  # ambos en >256 recuerdos → ubicuos; prefijo visitaría > N → barrido completo
    hits = await mem.recall("u", q, k=3)
    oraculo = _fuerza_bruta(mem._items, "u", q, k=3)
    assert _contenidos(hits) == _contenidos(oraculo)


# --------------------------------------------------- DIFERENCIAL vs FUERZA BRUTA --


@pytest.mark.asyncio
async def test_diferencial_aleatorio_cero_discrepancias_vs_fuerza_bruta(tmp_path):
    """Muchos corpus/consultas aleatorios con semilla fija: `recall` == fuerza bruta en todos."""
    rng = random.Random(20260803)
    vocab = [f"t{i}" for i in range(40)]
    # algunos términos ubicuos a propósito, para ejercitar ambas ramas
    for corpus_id in range(6):
        mem = await _mem(tmp_path, f"c{corpus_id}.jsonl")
        n_rec = rng.choice([50, 300, 400])
        for _ in range(n_rec):
            k = rng.randint(1, 5)
            pal = " ".join(rng.choice(vocab) for _ in range(k))
            # sesgo hacia t0/t1 para crear posteos ubicuos cuando n_rec>256
            if rng.random() < 0.7:
                pal = "t0 " + pal if rng.random() < 0.5 else "t1 " + pal
            await mem.write("u", "semantica", pal, {"origen": "declarada"})
        for _ in range(40):
            nq = rng.randint(1, 4)
            q = " ".join(rng.choice(vocab) for _ in range(nq))
            hits = await mem.recall("u", q, k=3)
            oraculo = _fuerza_bruta(mem._items, "u", q, k=3)
            assert _contenidos(hits) == _contenidos(oraculo), f"discrepancia en corpus {corpus_id}, q={q!r}"


# --------------------------------------------------------------- AISLAMIENTO / LÍMITES --


@pytest.mark.asyncio
async def test_aislamiento_por_usuario_con_barrido_activo(tmp_path):
    """El barrido completo (rama de la cota) itera SOLO los recuerdos del `user_id`. La consulta de 3
    términos con dos ubicuos fuerza esa rama (prefijo de 2 listas, Σ>N); un segundo usuario con un
    recuerdo que cualifica NO debe aparecer."""
    mem = await _mem(tmp_path)
    for i in range(300):
        await mem.write("u1", "semantica", f"alfa beta relleno {i}", {"origen": "declarada"})
    await mem.write("u1", "semantica", "alfa beta gamma objetivo de u1", {"origen": "declarada"})
    await mem.write("u2", "semantica", "alfa beta gamma secreto de u2", {"origen": "declarada"})
    q = "alfa beta gamma"  # alfa/beta en >256 (ubicuos) + gamma selectivo → prefijo 2 listas, Σ>N → barrido
    hits = await mem.recall("u1", q, k=5)
    assert all("u2" not in c for c in _contenidos(hits)), "el barrido no puede filtrar recuerdos de otro usuario"
    assert _contenidos(hits) == _contenidos(_fuerza_bruta(mem._items, "u1", q, k=5))


@pytest.mark.asyncio
async def test_limites_sin_terminos_y_sin_cobertura(tmp_path):
    mem = await _mem(tmp_path)
    await mem.write("u", "semantica", "el gato duerme en el sofa", {"origen": "declarada"})
    assert await mem.recall("u", "", k=3) == []  # sin términos informativos
    # una consulta sin solape suficiente no devuelve nada (coincide con fuerza bruta)
    assert await mem.recall("u", "elefante avion montaña", k=3) == _fuerza_bruta(
        mem._items, "u", "elefante avion montaña", k=3
    )


@pytest.mark.asyncio
async def test_determinismo_entre_llamadas(tmp_path):
    mem = await _mem(tmp_path)
    for i in range(300):
        await mem.write("u", "semantica", f"alfa relleno {i}", {"origen": "declarada"})
    await mem.write("u", "semantica", "alfa beta gamma", {"origen": "declarada"})
    r1 = _contenidos(await mem.recall("u", "alfa beta gamma", k=3))
    r2 = _contenidos(await mem.recall("u", "alfa beta gamma", k=3))
    assert r1 == r2
