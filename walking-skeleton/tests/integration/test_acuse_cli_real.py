"""Integration: D-FC-6 con el ORQUESTADOR y el BUS REALES (no un doble).

## El defecto que este fichero demuestra que ya no ocurre [medido, arquitecto, 2026-09-13]

`InProcessEventBus.publish` hace `await h(event)`, asi que `Orchestrator.handle_utterance` NO vuelve
hasta que el turno ENTERO termina (medido con Ollama real: 251-263 s por turno). Con el flujo
anterior, `_conversar` hacia `await handle_utterance(...)` y SOLO DESPUES llamaba a
`_esperar_con_acuse`: el turno ya estaba resuelto cuando se le preguntaba, y el acuse de espera nunca
llegaba a imprimirse en produccion -- las pruebas unitarias existentes pasaban igual porque usaban un
doble (`_OrquestadorLento`) cuyo `wait()` expiraba por su cuenta, sin reproducir el bus sincrono real.
Es el mismo patron "declarado != real" que este proyecto ya penalizo 8 veces, esta vez del lado de
las PRUEBAS.

Este fichero compone AURA de verdad (`componer()`, stack MOCK para no depender de Ollama ni de red),
sustituye SOLO la lista de proveedores del router por un espia que duerme (simula la latencia real
sin red ni modelo), y ejercita `__main__._turno` -- la funcion que ahora lanza `handle_utterance`
como tarea del mismo bucle en vez de esperarla en linea. NO se toca `orchestrator.py` ni `bus.py`.
"""

import asyncio

import pytest

from aura_skeleton import __main__ as cli
from aura_skeleton.composicion import Configuracion, componer


class _ProveedorEspiaLento:
    """Simula la latencia de un modelo real SIN red: duerme antes de responder. El nombre no importa
    -- `ModelRouter._circuitos` crea la entrada del circuito de forma perezosa (`setdefault`) la
    primera vez que ve un proveedor, asi que sustituir la lista tras `componer()` es seguro."""

    def __init__(self, salida: str, demora: float = 0.3) -> None:
        self.name = "ollama-espia"
        self._salida = salida
        self._demora = demora
        self.llamadas = 0

    async def infer(self, prompt, modo: str = "accion") -> str:
        self.llamadas += 1
        await asyncio.sleep(self._demora)
        return self._salida


@pytest.fixture
def sistema(tmp_path):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(config)


@pytest.mark.asyncio
async def test_el_acuse_aparece_cuando_el_turno_llega_de_verdad_al_modelo(sistema, monkeypatch, capsys):
    """Pregunta MUNDO ("por que llueve?" -> `_MARCOS_COGNITIVOS` + referente MUNDO, D-FC-5): sin
    recuerdo que la conteste, el Core la enruta al LLM en modo cognitivo. Con el espia tardando mas
    que el primer tramo, el acuse DEBE imprimirse -- lo contrario del defecto medido."""
    espia = _ProveedorEspiaLento(
        '{"intent": "charla", "action": "consulta", "args": {}, '
        '"say": "Llueve porque el vapor de agua se condensa en las nubes."}',
        demora=0.3,
    )
    sistema.orquestador.router.providers = [espia]
    monkeypatch.setattr(cli, "_ACUSE_TRAMO_S", 0.05)

    resultado = await asyncio.wait_for(cli._turno(sistema.orquestador, "por que llueve?", "t-mundo"), timeout=10)

    assert espia.llamadas == 1
    assert "condensa" in resultado["say"]
    salida = capsys.readouterr().out
    assert "consultando mi modelo local" in salida


@pytest.mark.asyncio
async def test_una_pregunta_del_core_no_imprime_acuse_ni_llama_al_modelo(sistema, monkeypatch, capsys):
    """Caso de CONTROL: "como me llamo?" con memoria vacia la resuelve el Core solo (ADR-0014,
    ausencia de memoria = hecho, no inferencia): 0 llamadas al router, 0 acuse. Sin este control la
    prueba anterior no demostraria nada sobre CUANDO debe aparecer el acuse, solo que puede
    aparecer."""
    espia = _ProveedorEspiaLento('{"action": "consulta", "args": {}, "say": "no deberia llamarse"}')
    sistema.orquestador.router.providers = [espia]
    monkeypatch.setattr(cli, "_ACUSE_TRAMO_S", 0.05)

    resultado = await asyncio.wait_for(cli._turno(sistema.orquestador, "como me llamo?", "t-core"), timeout=10)

    assert espia.llamadas == 0, "una pregunta de memoria vacia la responde el Core, sin LLM (ADR-0014)"
    # El Core responde con su superficie especifica de nombre ("todavia no me has dicho como te
    # llamas"), no con el generico "no tengo ningun recuerdo" -- lo que importa para esta prueba es
    # que la respondio el Core (0 llamadas al modelo), no el texto exacto de esa superficie.
    assert "no" in resultado["say"].lower() and "llam" in resultado["say"].lower()
    salida = capsys.readouterr().out
    assert "consultando mi modelo local" not in salida
    assert "sigo trabajando" not in salida


@pytest.mark.asyncio
async def test_el_turno_no_se_cuelga_si_el_router_se_queda_sin_proveedores(sistema, monkeypatch):
    """Control: sin ningun proveedor utilizable, `ModelRouter.route` lanza `ProveedoresNoDisponibles`
    (subclase de `RuntimeError`); `orchestrator.py` YA la captura por esa base y finaliza el turno con
    ABSTENCION (comentario propio: "sin esto el turno moria sin `_done` y `wait` expiraba"). El turno
    debe TERMINAR -- ni colgarse, ni agotar el timeout total -- porque el fallo se resuelve dentro del
    propio Core, no como una excepcion que se escape de `_turno`."""
    sistema.orquestador.router.providers = []
    monkeypatch.setattr(cli, "_ACUSE_TRAMO_S", 0.05)

    resultado = await asyncio.wait_for(
        cli._turno(sistema.orquestador, "por que llueve?", "t-sin-proveedor"), timeout=10
    )

    assert resultado is not None
    assert "say" in resultado
