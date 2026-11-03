"""Unit: circuit breaker RECUPERABLE del `ModelRouter` (D-FC-7).

## El defecto medido

`self._open` anadia un proveedor al primer fallo y nunca lo retiraba: un unico timeout de Ollama
dejaba la sesion entera sin LLM hasta reiniciar el proceso. Esta bateria prueba, sin Ollama y sin
dormir de verdad (reloj falso inyectado via `reloj=`), el ciclo completo que lo repara:

    CERRADO --[fallo]--> ABIERTO --[protegido, NO llama]--> (enfriamiento) --> SEMIABIERTO
    SEMIABIERTO --[UNA llamada de prueba]--> CERRADO (exito) o ABIERTO de nuevo (fallo)

Cada asercion de "no llamado" cuenta invocaciones reales al proveedor (`.llamadas`), no solo lee el
resultado: un contador es la unica forma de demostrar "nunca dos llamadas al mismo proveedor en un
mismo `route()`" y "nunca reintentos en bucle".
"""

import pytest

from aura_skeleton.modules.router import ModelRouter, ProveedoresNoDisponibles


class _RelojFalso:
    """Reloj inyectable: el tiempo solo avanza cuando la prueba lo pide, nunca por si mismo."""

    def __init__(self, inicio: float = 0.0) -> None:
        self._ahora = inicio

    def avanzar(self, segundos: float) -> None:
        self._ahora += segundos

    def __call__(self) -> float:
        return self._ahora


class _ProveedorControlado:
    """Responde segun una cola de resultados fijada de antemano; cuenta llamadas REALES."""

    def __init__(self, name: str, resultados) -> None:
        self.name = name
        self._resultados = list(resultados)
        self.llamadas = 0

    async def infer(self, prompt, modo: str = "accion"):
        self.llamadas += 1
        resultado = self._resultados.pop(0)
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado


def test_proveedores_no_disponibles_es_runtimeerror():
    """Compatibilidad: quien ya capturaba `RuntimeError` generico (p.ej. `__main__._conversar`)
    sigue funcionando sin cambios."""
    assert issubclass(ProveedoresNoDisponibles, RuntimeError)


@pytest.mark.asyncio
async def test_fallo_abre_el_circuito_y_la_siguiente_llamada_queda_protegida():
    reloj = _RelojFalso()
    prov = _ProveedorControlado("p", [RuntimeError("cae"), "no deberia usarse"])
    router = ModelRouter([prov], 1200, enfriamiento_s=60.0, reloj=reloj)

    with pytest.raises(ProveedoresNoDisponibles):
        await router.route("hola", "t1")
    assert prov.llamadas == 1
    assert router.estado_circuitos()["p"] == "ABIERTO"

    # Mismo instante (nada de tiempo transcurrido): el circuito sigue ABIERTO y debe saltarse la
    # llamada, no reintentarla.
    with pytest.raises(ProveedoresNoDisponibles):
        await router.route("hola de nuevo", "t2")
    assert prov.llamadas == 1, "el proveedor NO debe llamarse mientras el circuito esta ABIERTO"


@pytest.mark.asyncio
async def test_tras_enfriar_el_circuito_pasa_a_semiabierto():
    reloj = _RelojFalso()
    prov = _ProveedorControlado("p", [RuntimeError("cae")])
    router = ModelRouter([prov], 1200, enfriamiento_s=10.0, reloj=reloj)

    with pytest.raises(ProveedoresNoDisponibles):
        await router.route("hola", "t1")
    assert router.estado_circuitos()["p"] == "ABIERTO"

    reloj.avanzar(9.999)
    assert router.estado_circuitos()["p"] == "ABIERTO", "todavia no paso el enfriamiento completo"

    reloj.avanzar(0.001)
    assert router.estado_circuitos()["p"] == "SEMIABIERTO"


@pytest.mark.asyncio
async def test_semiabierto_hace_una_llamada_de_prueba_y_cierra_si_acierta():
    reloj = _RelojFalso()
    prov = _ProveedorControlado("p", [RuntimeError("cae"), '{"say": "ok"}'])
    router = ModelRouter([prov], 1200, enfriamiento_s=10.0, reloj=reloj)

    with pytest.raises(ProveedoresNoDisponibles):
        await router.route("hola", "t1")
    reloj.avanzar(10.0)
    assert router.estado_circuitos()["p"] == "SEMIABIERTO"

    nombre, salida = await router.route("hola otra vez", "t2")

    assert (nombre, salida) == ("p", '{"say": "ok"}')
    assert prov.llamadas == 2, "SEMIABIERTO permite EXACTAMENTE una llamada de prueba"
    assert router.estado_circuitos()["p"] == "CERRADO"

    # El circuito CERRADO ya no protege nada: una tercera llamada SI debe volver a invocar al
    # proveedor con normalidad.
    prov._resultados.append('{"say": "sigue vivo"}')
    nombre2, _ = await router.route("una mas", "t3")
    assert nombre2 == "p"
    assert prov.llamadas == 3


@pytest.mark.asyncio
async def test_fallo_en_semiabierto_reabre_el_circuito_con_marca_nueva():
    reloj = _RelojFalso()
    prov = _ProveedorControlado("p", [RuntimeError("cae"), RuntimeError("cae de nuevo")])
    router = ModelRouter([prov], 1200, enfriamiento_s=5.0, reloj=reloj)

    with pytest.raises(ProveedoresNoDisponibles):
        await router.route("hola", "t1")
    reloj.avanzar(5.0)
    assert router.estado_circuitos()["p"] == "SEMIABIERTO"

    with pytest.raises(ProveedoresNoDisponibles):
        await router.route("hola de nuevo", "t2")
    assert prov.llamadas == 2, "la prueba semiabierta es UNA llamada, nunca dos en el mismo route()"
    assert router.estado_circuitos()["p"] == "ABIERTO"

    # La marca de tiempo se renovo: el enfriamiento vuelve a contar desde AHORA (5.0), no desde 0.
    # Margenes amplios (no al filo del segundo) para no depender de precision de punto flotante.
    reloj.avanzar(4.9)
    assert router.estado_circuitos()["p"] == "ABIERTO"
    reloj.avanzar(0.2)
    assert router.estado_circuitos()["p"] == "SEMIABIERTO"


@pytest.mark.asyncio
async def test_fallback_entre_proveedores_sigue_funcionando_con_el_circuito_nuevo():
    reloj = _RelojFalso()
    malo = _ProveedorControlado("malo", [RuntimeError("cae")])
    bueno = _ProveedorControlado("bueno", ['{"say": "hola"}'])
    router = ModelRouter([malo, bueno], 1200, enfriamiento_s=60.0, reloj=reloj)

    nombre, salida = await router.route("hola", "t1")

    assert nombre == "bueno"
    assert salida == '{"say": "hola"}'
    assert malo.llamadas == 1
    assert bueno.llamadas == 1
    assert router.estado_circuitos() == {"malo": "ABIERTO", "bueno": "CERRADO"}


@pytest.mark.asyncio
async def test_sin_ningun_proveedor_utilizable_el_mensaje_incluye_el_estado():
    reloj = _RelojFalso()
    prov = _ProveedorControlado("p", [RuntimeError("cae")])
    router = ModelRouter([prov], 1200, enfriamiento_s=60.0, reloj=reloj)

    with pytest.raises(ProveedoresNoDisponibles) as exc:
        await router.route("hola", "t1")
    assert "p" in str(exc.value)
    assert "ABIERTO" in str(exc.value)
