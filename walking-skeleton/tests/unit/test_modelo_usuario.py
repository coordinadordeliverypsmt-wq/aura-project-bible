"""Soberanía del modelo del usuario (M3.2a, ADR-0017 / Bible 4.4 §2, 4.1 §5).

Las cuatro capacidades son DETERMINISTAS: su corrección no depende de la calidad de ninguna
inferencia, solo de que el mecanismo funcione. Por eso se construyen ANTES de que AURA infiera nada
—si se hicieran despues, existiria una ventana en la que el sistema acumula conclusiones sobre una
persona que esa persona no puede rectificar (D34 y ADR-0017).
"""

import json

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import ClaseSenal, Senal
from aura_skeleton.modules.memory import SimpleMemory


def _mu(mem, kill=None):
    """`ModeloUsuario` cableado al MOTOR UNICO (F4, 2026-08-25).

    La ruta de soberania dejo de mutar el almacen directamente. **Sin motor no muta**, asi que un
    fixture que construya `ModeloUsuario(mem)` a secas haria pasar la prueba en vacio. El veredicto
    que cada prueba mide no cambia: se completa el cableado que la migracion hizo obligatorio.
    """
    return ModeloUsuario(mem, motor=MotorAutomatizacion(
        EjecutorModeloUsuario(mem), PermissionManager(_confirmar_mu, kill_switch=kill)))


async def _confirmar_mu(accion, args, trace_id):
    return True



async def _sembrar(mem, uid="mauricio"):
    """Siembra por la via real: el almacen de senales de M3.0."""
    from aura_skeleton.core.almacen_senales import AlmacenSenales

    # motor ANADIDO (F4 tramo 3): la captura de senales pasa por el camino unico y sin motor no
    # guarda nada; sembrar en vacio habria dejado estas pruebas midiendo una memoria vacia.
    await AlmacenSenales(mem, motor=MotorAutomatizacion(
        EjecutorModeloUsuario(mem), PermissionManager(_confirmar_mu))).guardar(
        uid,
        [
            Senal(ClaseSenal.PREFERENCIA_DECLARADA, "prefiere la luz tenue", "conversacion", "t1"),
            Senal(ClaseSenal.PATRON_DE_USO, "borrar_archivo", "computador", "t2"),
        ],
    )


@pytest.mark.asyncio
async def test_ver_lo_que_aura_cree_saber():
    mem = SimpleMemory()
    await _sembrar(mem)

    entradas = await _mu(mem).ver("mauricio")

    assert len(entradas) == 2
    assert {e["origen"] for e in entradas} == {"declarada", "observada"}
    assert all(e["fuente"] for e in entradas), "sin procedencia no es auditable (ADR-0017 §3)"


@pytest.mark.asyncio
async def test_una_correccion_prevalece_sobre_lo_inferido():
    """ADR-0017 §2: el usuario gana siempre, sin ponderacion."""
    mem = SimpleMemory()
    modelo = _mu(mem)
    await mem.write(
        "mauricio",
        "semantica",
        "prefiere la luz brillante",
        {"trace_id": "t", "fuente": "inferencia", "clase": "preferencia_declarada", "origen": "inferida"},
    )

    await modelo.corregir("mauricio", "prefiere la luz brillante", "prefiere la luz tenue")
    entradas = await modelo.ver("mauricio")

    vigentes = [e for e in entradas if not e.get("refutada")]
    assert len(vigentes) == 1
    assert vigentes[0]["contenido"] == "prefiere la luz tenue"
    assert vigentes[0]["origen"] == "declarada", "una correccion del usuario es declarada, no inferida"

    refutadas = [e for e in entradas if e.get("refutada")]
    assert len(refutadas) == 1, "la inferencia refutada se conserva marcada, no se borra en silencio"


@pytest.mark.asyncio
async def test_exportar_es_legible_sin_aura():
    """4.1 §5: exportable. Un formato que solo AURA sabe leer no es soberania."""
    mem = SimpleMemory()
    await _sembrar(mem)

    volcado = await _mu(mem).exportar("mauricio")
    datos = json.loads(volcado)

    assert datos["usuario"] == "mauricio"
    assert len(datos["entradas"]) == 2
    assert "prefiere la luz tenue" in volcado


@pytest.mark.asyncio
async def test_borrado_selectivo_no_toca_el_resto():
    mem = SimpleMemory()
    await _sembrar(mem)
    modelo = _mu(mem)

    borradas = await modelo.borrar("mauricio", contiene="luz")

    assert borradas == 1
    restantes = await modelo.ver("mauricio")
    assert len(restantes) == 1
    assert "luz" not in restantes[0]["contenido"]


@pytest.mark.asyncio
async def test_borrado_total_no_degrada_la_memoria_episodica():
    """Borrar lo que AURA cree saber no puede borrar la conversacion del usuario."""
    mem = SimpleMemory()
    await _sembrar(mem)
    await mem.write("mauricio", "episodica", "usuario dijo: hola", {"trace_id": "t"})

    await _mu(mem).borrar("mauricio")

    assert await _mu(mem).ver("mauricio") == []
    episodicas = [i for i in mem._items if i["kind"] == "episodica"]
    assert len(episodicas) == 1, "el borrado del modelo no puede tocar el historial episodico"


@pytest.mark.asyncio
async def test_el_modelo_esta_aislado_por_usuario():
    """P-ARQ-5: multiusuario. Nadie ve ni corrige el modelo de otro."""
    mem = SimpleMemory()
    await _sembrar(mem, "mauricio")
    await _sembrar(mem, "otra_persona")
    modelo = _mu(mem)

    await modelo.borrar("otra_persona")

    assert len(await modelo.ver("mauricio")) == 2, "el borrado de un usuario afecto a otro"
