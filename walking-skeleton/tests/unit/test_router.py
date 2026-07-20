"""Unit: Model Router — fallback y prioridad de seguridad (Bible 4.2 / 5.2)."""

import json

import pytest

from aura_skeleton.modules.router import MockProvider, ModelRouter


@pytest.mark.asyncio
async def test_fallback_a_proveedor_sano():
    r = ModelRouter([MockProvider("a", 5, healthy=False), MockProvider("b", 5, healthy=True)], 1200)
    prov, out = await r.route("Usuario: hola", "t")
    assert prov == "b"


@pytest.mark.asyncio
async def test_fixture_mockprovider_clasifica_sobre_la_peticion():
    """AUTOPRUEBA DEL FIXTURE, no garantia del sistema (auditoria T1).

    En produccion quien clasifica la intencion es el LLM, no este doble. Esta prueba solo
    fija el comportamiento de MockProvider para que el resto de pruebas que lo usan como
    ENTRADA sean deterministas. No debe leerse como evidencia de ninguna propiedad de AURA.
    """
    # el contexto de memoria contiene 'luz' pero la peticion es borrar -> gana la lista roja (5.2)
    r = ModelRouter([MockProvider("b", 5, healthy=True)], 1200)
    _, out = await r.route("[contexto memoria: luz de la sala]\nUsuario: elimina el archivo", "t")
    assert json.loads(out)["action"] == "eliminar_informacion"


@pytest.mark.asyncio
async def test_sin_proveedores_lanza():
    r = ModelRouter([MockProvider("a", 5, healthy=False)], 1200)
    with pytest.raises(RuntimeError):
        await r.route("Usuario: hola", "t")
