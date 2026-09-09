"""Unit: MVP Modelo de Usuario — inspeccionar, entender, corregir y OLVIDAR DE FORMA PERSISTENTE.

Objetivo del CEO (2026-07-28): el usuario puede inspeccionar, entender, corregir y **olvidar de forma
persistente** lo que AURA sabe sobre él. El criterio definitivo es que un "olvida eso" **sobreviva a un
reinicio**: si el dato reaparece, el incremento no está terminado aunque las pruebas estén en verde.

Precisión del CEO: la interfaz es **fiel al modelo interno**. El sistema hoy distingue conocimiento
`declarado` (el usuario lo dijo) de `observado` (patrón visto en conversaciones); NO infiere. Por eso la
presentación usa "me lo dijiste" / "lo he observado" y NUNCA inventa grados de certeza ("creo") que no
correspondan a algo verificable en la procedencia.
"""

import os

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory


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



async def _sembrar(mem):
    await mem.write("u", "semantica", "prefiere la luz tenue de noche", {"origen": "declarada", "fuente": "usuario"})
    await mem.write(
        "u", "semantica", "suele pagar las facturas por la app", {"origen": "observada", "fuente": "conversacion"}
    )


@pytest.mark.asyncio
async def test_olvidar_persiste_tras_reiniciar(tmp_path):
    """EL CRITERIO DEL CEO: lo olvidado NO reaparece tras reconstruir la memoria desde disco."""
    ruta = os.path.join(tmp_path, "m.jsonl")
    mem = PersistentMemory(ruta)
    mu = _mu(mem)
    await _sembrar(mem)

    n = await mu.borrar("u", contiene="facturas")
    assert n == 1

    # Reinicio: nueva instancia que lee del disco.
    mu2 = _mu(PersistentMemory(ruta))
    contenidos = [e["contenido"] for e in await mu2.ver("u")]
    assert any("luz tenue" in c for c in contenidos), "lo no borrado debe seguir"
    assert not any("facturas" in c for c in contenidos), "lo OLVIDADO no puede reaparecer tras reiniciar"


@pytest.mark.asyncio
async def test_olvidar_no_corrompe_el_recall(tmp_path):
    """Tras olvidar un elemento INTERMEDIO, la memoria sigue consultable: el índice (posiciones) se reconstruye.

    Con 3 entradas, borrar la del medio deja el índice apuntando a una posición inexistente si NO se
    reconstruye; un recall del último elemento lanzaría IndexError.
    """
    ruta = os.path.join(tmp_path, "m.jsonl")
    mem = PersistentMemory(ruta)
    await mem.write("u", "semantica", "alfa primero", {"origen": "declarada"})
    await mem.write("u", "semantica", "beta facturas medio", {"origen": "observada"})
    await mem.write("u", "semantica", "gamma ultimo", {"origen": "declarada"})
    await _mu(mem).borrar("u", contiene="facturas")  # borra el del medio (posición 1)
    hits = await mem.recall("u", "gamma ultimo")  # gamma estaba en posición 2; sin reindexar -> IndexError
    assert any("gamma" in h["content"] for h in hits)


@pytest.mark.asyncio
async def test_ver_no_devuelve_lo_ya_olvidado(tmp_path):
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    mu = _mu(mem)
    await mu.borrar("u", contiene="facturas")
    assert not any("facturas" in e["contenido"] for e in await mu.ver("u"))


@pytest.mark.asyncio
async def test_refutar_persiste_tras_reiniciar(tmp_path):
    """ "Eso ya no es cierto" marca `refutada` de forma que sobrevive al reinicio."""
    ruta = os.path.join(tmp_path, "m.jsonl")
    mem = PersistentMemory(ruta)
    await _sembrar(mem)
    await _mu(mem).refutar("u", contiene="facturas")
    tras = await _mu(PersistentMemory(ruta)).ver("u")
    facturas = next(e for e in tras if "facturas" in e["contenido"])
    assert facturas["refutada"] is True


def test_presentacion_es_fiel_al_modelo_no_inventa_certeza():
    """Precisión del CEO: 'declarada'->'me lo dijiste', 'observada'->'lo he observado'. Nunca 'creo'."""
    from aura_skeleton.core.modelo_usuario import describir_conocimiento

    texto = describir_conocimiento(
        [
            {"contenido": "prefiere luz tenue", "origen": "declarada", "refutada": False},
            {"contenido": "paga por la app", "origen": "observada", "refutada": False},
        ]
    )
    assert "prefiere luz tenue (me lo dijiste)" in texto
    assert "paga por la app (lo he observado)" in texto
    assert "creo" not in texto.lower()


def test_describir_excluye_lo_refutado():
    from aura_skeleton.core.modelo_usuario import describir_conocimiento

    texto = describir_conocimiento(
        [
            {"contenido": "vigente", "origen": "declarada", "refutada": False},
            {"contenido": "refutado", "origen": "observada", "refutada": True},
        ]
    )
    assert "vigente" in texto and "refutado" not in texto
