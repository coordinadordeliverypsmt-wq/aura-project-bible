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
async def test_intencion_sobre_peticion_no_contexto():
    # el contexto de memoria contiene 'luz' pero la peticion es borrar -> gana la lista roja (5.2)
    r = ModelRouter([MockProvider("b", 5, healthy=True)], 1200)
    _, out = await r.route("[contexto memoria: luz de la sala]\nUsuario: elimina el archivo", "t")
    assert json.loads(out)["action"] == "eliminar_informacion"


@pytest.mark.asyncio
async def test_sin_proveedores_lanza():
    r = ModelRouter([MockProvider("a", 5, healthy=False)], 1200)
    with pytest.raises(RuntimeError):
        await r.route("Usuario: hola", "t")
