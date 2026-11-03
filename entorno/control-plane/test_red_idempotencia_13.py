"""RED · `§13 · Idempotencia`, mecanismo 2 — el `--session-id` no deriva de lo que el DP dice.

El `§13` enumera cuatro mecanismos en capas. El segundo está escrito así, literalmente:

> 2. **`--session-id` derivado** — `uuid5(namespace, tarea_id + sha256(sobre))`. La misma tarea **con
>    el mismo sobre** produce el mismo identificador: la doble ejecución es **detectable**, no una
>    cuestión de disciplina.

Y el modelo conceptual, escrito **antes** de que existiera una línea del orquestador, lo modela igual:

```python
def id_de_sesion(tarea_id: str, huella_sobre: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"aura-orch/{tarea_id}/{huella_sobre}"))
```

La implementación deriva **solo del `tarea_id`** `[EJEC]`:

```python
semilla = hashlib.sha256(f"aura-orq:{tarea_id}".encode("utf-8")).digest()[:16]
return str(uuid.UUID(bytes=semilla))
```

**Consecuencia medible:** dos ejecuciones de la misma tarea con **sobres distintos** —otros permisos,
otro presupuesto, otro criterio de finalización, otra versión de la política— reciben el **mismo**
identificador de sesión. El orquestador las tomaría por la misma ejecución. Justo lo contrario de lo
que el mecanismo existe para conseguir: la frase del DP no dice *«la misma tarea»*, dice *«la misma
tarea **con el mismo sobre**»*, y esas cuatro palabras son el mecanismo entero.

Es la misma forma que la deuda del `§21`: modelo e implementación divergen y ninguna prueba lo veía,
porque las que había fijaban el comportamiento implementado en vez del contrato.
"""

from __future__ import annotations

import uuid

import orquestador as orq
import pytest


TAREA = {"id": "T-1", "accion": "ejecutar_pruebas", "objetivo": "batería en verde"}


def test_el_session_id_DEPENDE_del_sobre_no_solo_del_id():
    """El defecto, en una línea: dos sobres distintos de la misma tarea deben dar ids distintos."""
    w = orq.WorkerAdapter()
    barato = orq.Presupuesto(por_tarea_usd=0.10, por_ciclo_usd=1.00)
    caro = orq.Presupuesto(por_tarea_usd=5.00, por_ciclo_usd=10.00)
    assert w.session_id(TAREA, presupuesto=barato) != w.session_id(TAREA, presupuesto=caro), (
        "§13: «la misma tarea CON EL MISMO SOBRE produce el mismo identificador». Sobres distintos, "
        "no")


def test_el_session_id_es_ESTABLE_para_el_mismo_sobre():
    """La otra mitad, y sin ella la anterior se satisface con un id aleatorio. Dos adaptadores
    distintos que reciban la misma tarea deben coincidir, o el reintento abriría sesión nueva."""
    uno = orq.WorkerAdapter().session_id(TAREA)
    otro = orq.WorkerAdapter().session_id(TAREA)
    assert uno == otro
    assert uno == orq.WorkerAdapter().session_id(dict(TAREA))


def test_el_session_id_cambia_si_cambia_el_CRITERIO_de_finalizacion():
    """El criterio viaja en el sobre (`§7.1`). Reejecutar la misma tarea con otro criterio es otra
    ejecución: darle el mismo id la haría indistinguible de un reintento."""
    w = orq.WorkerAdapter()
    con_uno = {**TAREA, "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}}
    con_otro = {**TAREA, "criterio_de_finalizacion": {"capacidad": "verificar_calidad"}}
    assert w.session_id(con_uno) != w.session_id(con_otro)
    assert w.session_id(con_uno) != w.session_id(TAREA)


def test_el_session_id_cambia_si_cambian_los_FICHEROS_o_el_objetivo():
    w = orq.WorkerAdapter()
    assert w.session_id(TAREA) != w.session_id({**TAREA, "objetivo": "otra cosa"})
    assert w.session_id(TAREA) != w.session_id({**TAREA, "ficheros_relevantes": ["a.py"]})


def test_tareas_DISTINTAS_no_comparten_session_id():
    w = orq.WorkerAdapter()
    assert w.session_id(TAREA) != w.session_id({**TAREA, "id": "T-2"})


def test_el_session_id_es_un_uuid5_como_dice_el_contrato():
    """`§13` nombra `uuid5`, no un troceado de `sha256` reinterpretado como UUID. La diferencia
    importa: un `uuid5` es un identificador con versión y espacio de nombres declarados, y cualquiera
    puede recalcularlo desde el contrato sin leer esta implementación."""
    identificador = uuid.UUID(orq.WorkerAdapter().session_id(TAREA))
    assert identificador.version == 5


def test_el_session_id_coincide_con_el_MODELO_conceptual():
    """El modelo se escribió antes que el orquestador para fijar el contrato. Que diverjan es la
    deuda del `§21` otra vez: una prueba que fija lo implementado en vez de lo acordado."""
    import test_modelo_orquestador as modelo
    w = orq.WorkerAdapter()
    esperado = modelo.id_de_sesion(TAREA["id"], w.huella_de_sobre(TAREA))
    assert w.session_id(TAREA) == esperado


def test_la_orden_de_invocacion_lleva_el_id_derivado_del_sobre_que_manda():
    """Cerrar el círculo: el id que viaja en la orden tiene que ser el del sobre que se envía. Si se
    calculara con otro sobre, el identificador no describiría la ejecución que ocurre."""
    w = orq.WorkerAdapter()
    orden = w.orden_de_invocacion(TAREA)
    assert w.session_id(TAREA) in orden
    assert "--session-id" in orden


def test_no_se_puede_pedir_un_session_id_sin_el_sobre():
    """La garantía, estructural: pasar solo el id ya no es posible. Si siguiera aceptándose una
    cadena, el defecto volvería en la primera llamada que se escribiera de memoria."""
    with pytest.raises((TypeError, AttributeError, KeyError)):
        orq.WorkerAdapter().session_id("T-1")
