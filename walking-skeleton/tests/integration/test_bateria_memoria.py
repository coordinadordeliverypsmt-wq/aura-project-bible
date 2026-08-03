"""Integracion M3: bateria oficial de memoria (decision del CEO).

Carga `tests/datos/bateria_memoria.json` (65 recuerdos, 77 consultas etiquetadas) y ejercita
`PersistentMemory.recall(...)` tal como la usa el orquestador real. Cuatro garantias, cada una en
su propia prueba, para que un fallo senale con precision cual se rompio:

  1. Cero falsos positivos "puros" (ADR-0014): una consulta sin ningun recuerdo relacionado no
     puede devolver nada. Es la garantia mas basica de no-fabricacion (Bible 4.1).
  2. Cero falsos positivos "criticos": un recuerdo de OTRA entidad que comparte un atributo
     generico (marca, color, numero, anos) induciria al LLM a responder un dato CONCRETO pero
     EQUIVOCADO sobre la entidad incorrecta. Mas grave que un FP puro: ahi el LLM no sabe, aqui
     el LLM cree saber y se equivoca con seguridad.
  3. recall@3 no baja del minimo acordado por el CEO para la variante elegida (RECALL_MINIMO).
  4. Determinismo: el mismo input produce el mismo output, siempre. Sin esto ninguna de las tres
     garantias anteriores se puede auditar de forma reproducible: una corrida en verde no
     demostraria nada si la siguiente pudiera variar.

Esta prueba se escribe ANTES de que exista el recuperador nuevo (TDD, fase RED): se espera que
varias garantias fallen contra la implementacion actual de `PersistentMemory.recall`, que puntua
por simple solapamiento de terminos y no distingue "hablar del mismo tema" de "compartir un
atributo generico de otra entidad distinta".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton.modules.memory import PersistentMemory

# Umbral de recall@3 acordado por el CEO para la variante de recuperador elegida (decision M3, ver
# cierre de la bateria). No es un numero redondo elegido a ojo: nace de medir la variante candidata
# contra ESTA MISMA bateria (53 de las 77 consultas tienen `esperado`) y fijar el piso que no debe
# volver a bajar -- asi una futura optimizacion (p.ej. de velocidad) no puede sacrificar calidad de
# recuperacion sin que esta prueba lo note.
# Falsos positivos criticos ACEPTADOS en los casos adversariales. No es un objetivo, es la frontera
# medida de N1: en esos 2 casos el discriminante es un poseedor ("de mi vecino", "de mi hermano") que
# la consulta menciona y el recuerdo no. Estan clasificados como "corregible" en la bateria: admiten
# una mejora lexica futura (deteccion del patron "de mi <X>"), no requieren semantica.
_ADVERSARIALES_CONOCIDOS = 2

_RAIZ = Path(__file__).resolve().parents[2]

RECALL_MINIMO = 0.63

_RUTA_BATERIA = Path(__file__).parent.parent / "datos" / "bateria_memoria.json"


def _cargar_bateria() -> dict[str, Any]:
    """Ruta relativa al fichero de prueba (no absoluta): la bateria se localiza sola sin importar
    desde donde se invoque pytest."""
    with open(_RUTA_BATERIA, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _contenido_a_id(corpus: list[dict[str, Any]]) -> dict[str, int]:
    """Mapa contenido -> id para traducir un resultado de recall() a su recuerdo original.

    Se traduce por CONTENIDO y no por `provenance`/trace_id a proposito: el contenido es lo unico
    que el contrato MemoryStore (aura_skeleton/contracts.py) garantiza que recall() devuelve
    intacto; un recuperador nuevo (embeddings, reranking, etc.) podria reconstruir provenance de
    otra forma sin romper el contrato.
    """
    mapa = {r["content"]: r["id"] for r in corpus}
    assert len(mapa) == len(corpus), "hay contenidos duplicados en el corpus de la bateria"
    return mapa


async def _memoria_con_corpus(tmp_path: Path, corpus: list[dict[str, Any]]) -> PersistentMemory:
    """Escribe el corpus completo en una PersistentMemory nueva sobre tmp_path (nunca disco real)."""
    mem = PersistentMemory(str(tmp_path / "mem.json"))
    for recuerdo in corpus:
        await mem.write(recuerdo["user_id"], "semantica", recuerdo["content"], {"trace_id": str(recuerdo["id"])})
    return mem


async def _medir_consultas(
    mem: PersistentMemory, consultas: list[dict[str, Any]], contenido_a_id: dict[str, int]
) -> list[dict[str, Any]]:
    """Ejecuta recall(user_id, texto, k=3) para cada consulta y devuelve, por consulta, todo lo
    que las garantias necesitan: categoria, gravedad, esperado, ids hallados y si acerto."""
    evaluacion = []
    for consulta in consultas:
        hits = await mem.recall("u1", consulta["texto"], k=3)
        ids = [contenido_a_id[h["content"]] for h in hits]
        esperado = consulta["esperado"]
        evaluacion.append(
            {
                "texto": consulta["texto"],
                "categoria": consulta["categoria"],
                "gravedad": consulta.get("gravedad"),
                "esperado": esperado,
                "ids": ids,
                "acerto": esperado is not None and esperado in ids,
            }
        )
    return evaluacion


async def _ejecutar_bateria(tmp_path: Path, bateria: dict[str, Any]) -> list[dict[str, Any]]:
    """Construye la memoria UNA vez y mide todas las consultas. Corpus y bateria son pequenos
    (65 recuerdos, 77 consultas): no hay necesidad de nada mas elaborado para que sea rapida."""
    mem = await _memoria_con_corpus(tmp_path, bateria["corpus"])
    contenido_a_id = _contenido_a_id(bateria["corpus"])
    return await _medir_consultas(mem, bateria["consultas"], contenido_a_id)


@pytest.fixture(scope="module")
def bateria() -> dict[str, Any]:
    return _cargar_bateria()


@pytest.mark.asyncio
async def test_ningun_falso_positivo_puro(tmp_path: Path, bateria: dict[str, Any]) -> None:
    """ADR-0014: sin ningun recuerdo relacionado, la respuesta correcta es no encontrar nada.

    Un FP aqui significa que el recuperador le entrega al LLM un recuerdo IRRELEVANTE como si
    fuera la respuesta a una pregunta que la bateria disenio para que NADA calzara (p.ej. "el
    nombre de mi abuela", que no existe en el corpus). El LLM puede entonces fabricar una
    contestacion en vez de admitir que no lo sabe. Es la garantia mas basica de no-fabricacion.
    """
    evaluacion = await _ejecutar_bateria(tmp_path, bateria)
    fallos = [e for e in evaluacion if e["gravedad"] == "puro" and e["ids"]]
    assert not fallos, (
        f"{len(fallos)} consulta(s) sin recuerdo relacionado devolvieron resultado (FP puro), "
        f"violando ADR-0014 (no-fabricacion): {[f['texto'] for f in fallos]}"
    )


@pytest.mark.asyncio
async def test_ningun_falso_positivo_critico(tmp_path: Path, bateria: dict[str, Any]) -> None:
    """Un FP critico es un recuerdo de OTRA entidad que comparte un atributo generico (marca,
    color, numero, anos): p.ej. devolver "mi coche es electrico" como respuesta a una pregunta
    sobre el color de los ojos induciria al LLM a inventar un color a partir de un dato sin
    relacion real. Es MAS grave que un FP puro: ahi el LLM no sabe, aqui el LLM cree saber y
    responde con seguridad un dato CONCRETO pero equivocado sobre la persona.
    """
    evaluacion = await _ejecutar_bateria(tmp_path, bateria)
    por_categoria = {e["texto"]: e for e in evaluacion}
    consultas = {c["texto"]: c for c in bateria["consultas"]}

    # (1) GARANTIA ESTRICTA sobre la bateria de referencia: cero. Es lo que restaura ADR-0014.
    de_referencia = [
        e
        for e in evaluacion
        if e["gravedad"] == "critico" and e["ids"] and consultas[e["texto"]].get("categoria") != "adversarial"
    ]
    assert not de_referencia, (
        f"{len(de_referencia)} consulta(s) critica(s) de la bateria de referencia devolvieron un "
        f"recuerdo de otra entidad: {[f['texto'] for f in de_referencia]}"
    )

    # (2) TECHO DOCUMENTADO sobre los casos adversariales. No es cero, y el CEO lo acepto de forma
    # explicita: son la frontera real de N1 (2 de 6, los que comparten un poseedor no mencionado en el
    # recuerdo). Se fija el numero ACTUAL como maximo para que ninguna variante futura empeore: la
    # descartada V7 —"cobertura o solape>=2"— fallaba 6 de 6 y esta asercion la habria rechazado.
    adversariales = [
        e
        for e in evaluacion
        if e["gravedad"] == "critico" and e["ids"] and consultas[e["texto"]].get("categoria") == "adversarial"
    ]
    assert len(adversariales) <= _ADVERSARIALES_CONOCIDOS, (
        f"{len(adversariales)} falsos positivos criticos en casos adversariales, por encima del techo "
        f"documentado ({_ADVERSARIALES_CONOCIDOS}). Una variante nueva ha empeorado la frontera de N1: "
        f"{[f['texto'] for f in adversariales]}"
    )
    assert por_categoria  # el informe se apoya en esta evaluacion


@pytest.mark.asyncio
async def test_el_recall_no_baja_del_minimo_aceptado(tmp_path: Path, bateria: dict[str, Any]) -> None:
    """recall@3 sobre las consultas con recuerdo correcto conocido (`esperado` != null) no puede
    bajar del piso acordado por el CEO (ver RECALL_MINIMO): por debajo de ese piso, el usuario
    percibe que AURA "olvida" cosas que si le conto.
    """
    evaluacion = await _ejecutar_bateria(tmp_path, bateria)
    con_esperado = [e for e in evaluacion if e["esperado"] is not None]
    aciertos = sum(1 for e in con_esperado if e["acerto"])
    recall = aciertos / len(con_esperado)
    fallos = [e["texto"] for e in con_esperado if not e["acerto"]]
    assert recall >= RECALL_MINIMO, (
        f"recall@3 = {aciertos}/{len(con_esperado)} = {recall:.4f}, por debajo del minimo "
        f"acordado {RECALL_MINIMO}. No encontraron su recuerdo esperado: {fallos}"
    )


@pytest.mark.asyncio
async def test_el_recuperador_es_determinista(tmp_path: Path, bateria: dict[str, Any]) -> None:
    """Sin esto, ninguna de las tres garantias anteriores se puede auditar: una corrida en verde
    no demostraria nada si la siguiente pudiera devolver otro resultado para la misma consulta.

    Se construye la memoria UNA sola vez y se mide la bateria DOS veces sobre la misma instancia,
    dentro del mismo proceso, comparando ids y orden consulta por consulta.
    """
    mem = await _memoria_con_corpus(tmp_path, bateria["corpus"])
    contenido_a_id = _contenido_a_id(bateria["corpus"])

    primera = await _medir_consultas(mem, bateria["consultas"], contenido_a_id)
    segunda = await _medir_consultas(mem, bateria["consultas"], contenido_a_id)

    diferencias = [
        (p["texto"], p["ids"], s["ids"]) for p, s in zip(primera, segunda, strict=True) if p["ids"] != s["ids"]
    ]
    assert not diferencias, (
        f"el recuperador no es determinista en {len(diferencias)} consulta(s) (se esperaban los "
        f"mismos ids en el mismo orden en dos ejecuciones): {diferencias}"
    )


@pytest.mark.asyncio
async def test_informe_de_la_bateria(tmp_path: Path, bateria: dict[str, Any]) -> None:
    """Informe legible de la bateria completa (correr con -s para verlo). NUNCA falla: no es una
    garantia, es evidencia auditable de donde esta cada categoria hoy, mas alla del veredicto
    binario de las pruebas anteriores.
    """
    evaluacion = await _ejecutar_bateria(tmp_path, bateria)

    print("\n=== Informe de la bateria de memoria ===")
    print(f"corpus: {len(bateria['corpus'])} recuerdos | consultas: {len(evaluacion)}")

    for categoria in sorted({e["categoria"] for e in evaluacion}):
        del_grupo = [e for e in evaluacion if e["categoria"] == categoria]
        con_esperado = [e for e in del_grupo if e["esperado"] is not None]
        if con_esperado:
            aciertos = sum(1 for e in con_esperado if e["acerto"])
            print(f"  {categoria:20s} {aciertos}/{len(con_esperado)} aciertos (recall@3)")
        else:
            con_resultado = sum(1 for e in del_grupo if e["ids"])
            print(f"  {categoria:20s} {con_resultado}/{len(del_grupo)} con resultado (FP)")

    con_esperado_total = [e for e in evaluacion if e["esperado"] is not None]
    aciertos_total = sum(1 for e in con_esperado_total if e["acerto"])
    recall = aciertos_total / len(con_esperado_total)

    def _fp_por_gravedad(gravedad: str) -> tuple[int, int]:
        del_grupo = [e for e in evaluacion if e["gravedad"] == gravedad]
        return sum(1 for e in del_grupo if e["ids"]), len(del_grupo)

    fp_puro, total_puro = _fp_por_gravedad("puro")
    fp_critico, total_critico = _fp_por_gravedad("critico")
    fp_aceptable, total_aceptable = _fp_por_gravedad("aceptable")

    print(
        f"  ---\n  recall@3 global: {aciertos_total}/{len(con_esperado_total)} = {recall:.4f}"
        f" (minimo acordado {RECALL_MINIMO})"
    )
    print(
        f"  FP puros: {fp_puro}/{total_puro} | FP criticos: {fp_critico}/{total_critico} | "
        f"FP aceptables (solo informa): {fp_aceptable}/{total_aceptable}"
    )
    print("=========================================")


def test_el_determinismo_se_mantiene_ENTRE_PROCESOS() -> None:
    """El determinismo real solo se ve entre procesos distintos, no dentro de uno.

    Comparar dos llamadas en el MISMO proceso no prueba nada: `PYTHONHASHSEED` es el mismo y el orden
    de iteracion de los `set` no cambia. El no-determinismo original se manifestaba entre ARRANQUES
    —la misma consulta devolvia recuerdos distintos segun el seed—, asi que hay que lanzar varios
    interpretes con seeds diferentes y comprobar que la salida es identica.
    """
    guion = textwrap.dedent(
        """
        import asyncio, json, hashlib, sys, tempfile, os
        sys.path.insert(0, %r)
        from aura_skeleton.modules.memory import PersistentMemory

        bateria = json.load(open(%r, encoding="utf-8"))
        memoria = PersistentMemory(os.path.join(tempfile.mkdtemp(), "m.json"))

        async def main():
            for recuerdo in bateria["corpus"]:
                await memoria.write(recuerdo["user_id"], "x", recuerdo["content"], {})
            salida = []
            for consulta in bateria["consultas"]:
                hits = await memoria.recall("u1", consulta["texto"])
                salida.append([h["content"] for h in hits])
            print(hashlib.sha256(json.dumps(salida, ensure_ascii=False).encode()).hexdigest())

        asyncio.run(main())
        """
    ) % (str(_RAIZ), str(_RUTA_BATERIA))

    huellas = set()
    for seed in ("0", "1", "2", "3", "4"):
        entorno = {**os.environ, "PYTHONHASHSEED": seed}
        proceso = subprocess.run([sys.executable, "-c", guion], capture_output=True, text=True, env=entorno)
        assert proceso.returncode == 0, f"el subproceso fallo con seed={seed}: {proceso.stderr[-400:]}"
        huellas.add(proceso.stdout.strip())

    assert len(huellas) == 1, (
        f"el recuperador NO es determinista entre procesos: {len(huellas)} resultados distintos con "
        f"5 semillas de hash. Los empates deben resolverse por un criterio estable, no por el orden "
        f"de iteracion de un set."
    )


@pytest.mark.asyncio
async def test_una_consulta_sin_terminos_informativos_no_devuelve_nada(tmp_path: Path) -> None:
    """ "¿Y eso?" o "¿que?" no pueden recuperar recuerdos: no hay nada que discriminar.

    Si se devolviera algo, seria por emparejar palabras vacias — exactamente el defecto que vaciaba
    de contenido la garantia de ADR-0014.
    """
    memoria = PersistentMemory(str(tmp_path / "m.json"))
    await memoria.write("u1", "episodica", "Mi color favorito es el azul marino.", {})

    for consulta in ("¿Y eso?", "¿Que?", "es que...", "lo de la de los"):
        assert await memoria.recall("u1", consulta) == [], f"{consulta!r} devolvio recuerdos sin nada que discriminar"
