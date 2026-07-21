"""Proveedores de contexto (M3.0, decision de arquitectura del CEO 2026-07-21).

M3 solo instrumenta conversacion, computador y Home Assistant. La arquitectura debe admitir
camaras, wearables y sensores biometricos **sin modificar el nucleo**.

La prueba central de este modulo es exactamente esa propiedad: se define aqui un proveedor que no
existe en el sistema —una camara— y debe funcionar sin que ningun fichero del nucleo lo mencione.
"""

import pytest

from aura_skeleton.core.contexto import FuenteDuplicada, RegistroContexto
from aura_skeleton.core.senales import ClaseSenal, Senal


class _CamaraFutura:
    """Proveedor que NO existe en el sistema. Simula una fuente de R2+ (camara/wearable).

    Si incorporarlo exigiera tocar el nucleo, esta prueba no compilaria sin editar `core/`.
    """

    nombre = "camara_salon"

    async def recoger(self, trace_id):
        return [Senal(ClaseSenal.PATRON_DE_USO, "presencia detectada en el salon", self.nombre, trace_id)]


class _Vacio:
    nombre = "sin_senales"

    async def recoger(self, trace_id):
        return []


@pytest.mark.asyncio
async def test_proveedor_no_previsto_se_incorpora_sin_tocar_el_nucleo():
    """La propiedad que pidio el CEO: extensibilidad sin modificar el Core."""
    registro = RegistroContexto([_CamaraFutura()])
    senales = await registro.recoger_todas("t-1")

    assert len(senales) == 1
    assert senales[0].fuente == "camara_salon"


@pytest.mark.asyncio
async def test_registro_agrega_senales_de_varias_fuentes():
    registro = RegistroContexto([_CamaraFutura(), _Vacio()])
    senales = await registro.recoger_todas("t-2")
    assert [s.fuente for s in senales] == ["camara_salon"]


def test_fuente_duplicada_se_rechaza():
    """Dos proveedores con el mismo nombre harian ambigua la procedencia de una senal."""
    with pytest.raises(FuenteDuplicada):
        RegistroContexto([_CamaraFutura(), _CamaraFutura()])


@pytest.mark.asyncio
async def test_un_proveedor_que_falla_no_derriba_la_captura():
    """Un sensor puede desconectarse. La captura degrada, no cae.

    Leccion de M2: un OSError propagado desde un adaptador derribaba el turno completo.
    """

    class _Averiado:
        nombre = "sensor_averiado"

        async def recoger(self, trace_id):
            raise OSError("dispositivo desconectado")

    registro = RegistroContexto([_Averiado(), _CamaraFutura()])
    senales = await registro.recoger_todas("t-3")

    assert [s.fuente for s in senales] == ["camara_salon"], "el proveedor sano debe seguir aportando"
    assert registro.fuentes_con_error == ["sensor_averiado"]
