"""MA.4 — Habilitacion y transparencia de conectores externos (ADR-0019, D37).

Se valida el comportamiento OBSERVABLE del mecanismo generico (no detalles internos), usando un
DOBLE de conector externo que solo demuestra el mecanismo: sin comportamiento de ningun proveedor
real, sin red ni credenciales.
"""

import pytest

from aura_skeleton.core.conectores_externos import DeclaracionTransparencia, habilitar
from aura_skeleton.core.contexto import RegistroContexto
from aura_skeleton.core.senales import ClaseSenal, Senal


class _Local:
    """Conector local: no declara `externo` (por defecto local). Siempre activo."""

    def __init__(self, nombre="local"):
        self.nombre = nombre

    async def recoger(self, trace_id):
        return [Senal(ClaseSenal.PATRON_DE_USO, "uso local", self.nombre, trace_id)]


class _ExternoDoble:
    """Doble GENERICO de conector externo. Solo demuestra el mecanismo; sin logica de proveedor."""

    externo = True

    def __init__(self, nombre="externo", transparencia=None, falla=False):
        self.nombre = nombre
        self.transparencia = transparencia
        self._falla = falla

    async def recoger(self, trace_id):
        if self._falla:
            raise RuntimeError("fuente externa no disponible")
        return [Senal(ClaseSenal.PATRON_DE_USO, "uso externo", self.nombre, trace_id)]


def _decl():
    return DeclaracionTransparencia(
        destino="nube-fabricante",
        proposito="enriquecer contexto",
        datos_locales=("resumen",),
        datos_que_salen=("consulta",),
    )


# --- D37.1: opt-in explicito -----------------------------------------------------
def test_un_conector_externo_no_se_activa_por_defecto():
    h = habilitar([_Local(), _ExternoDoble("wearable-x", _decl())], habilitados=frozenset())
    assert "wearable-x" not in [p.nombre for p in h.activos], "un externo NO puede activarse sin opt-in (D37.1)"
    assert "wearable-x" in h.rechazados


def test_un_conector_externo_se_activa_solo_con_opt_in():
    h = habilitar([_Local(), _ExternoDoble("wearable-x", _decl())], habilitados=frozenset({"wearable-x"}))
    assert "wearable-x" in [p.nombre for p in h.activos]


# --- D37.2: transparencia obligatoria + observable + determinista ----------------
def test_un_conector_externo_sin_transparencia_no_se_habilita():
    h = habilitar([_ExternoDoble("sin-decl", transparencia=None)], habilitados=frozenset({"sin-decl"}))
    assert "sin-decl" not in [p.nombre for p in h.activos], "sin declaracion de transparencia no se habilita (D37.2)"
    assert "sin-decl" in h.rechazados


def test_el_informe_declara_el_recorrido_del_dato():
    h = habilitar([_Local(), _ExternoDoble("wearable-x", _decl())], habilitados=frozenset({"wearable-x"}))
    assert "nube-fabricante" in h.informe and "consulta" in h.informe and "resumen" in h.informe


def test_el_informe_es_determinista_independiente_del_orden():
    a, b = _ExternoDoble("a", _decl()), _ExternoDoble("b", _decl())
    hab = frozenset({"a", "b"})
    assert habilitar([a, b], hab).informe == habilitar([b, a], hab).informe, "mismo config -> mismo informe"


def test_la_declaracion_de_transparencia_es_un_contrato_versionado():
    d = DeclaracionTransparencia(destino="x", proposito="y")  # campos minimos, el resto por defecto
    assert d.version_esquema >= 1, "la declaracion debe llevar version de esquema (ampliable sin romper)"
    assert d.datos_locales == () and d.datos_que_salen == ()


# --- D37.3: ninguno-requisito (deshabilitado Y fallando) -------------------------
@pytest.mark.asyncio
async def test_un_externo_deshabilitado_no_impide_operar():
    h = habilitar([_Local("pc"), _ExternoDoble("wearable-x", _decl())], habilitados=frozenset())
    reg = RegistroContexto(h.activos)
    senales = await reg.recoger_todas("t")
    assert any(s.fuente == "pc" for s in senales), "los locales siguen capturando con el externo apagado"
    assert "wearable-x" not in reg.fuentes


@pytest.mark.asyncio
async def test_un_externo_habilitado_que_falla_degrada_limpio():
    ext = _ExternoDoble("wearable-x", _decl(), falla=True)
    h = habilitar([_Local("pc"), ext], habilitados=frozenset({"wearable-x"}))
    reg = RegistroContexto(h.activos)
    senales = await reg.recoger_todas("t")  # no debe lanzar
    assert any(s.fuente == "pc" for s in senales), "un externo caido no puede dejar ciego al sistema (D37.3)"
    assert "wearable-x" in reg.fuentes_con_error


# --- Locales intactos ------------------------------------------------------------
def test_los_conectores_locales_no_dependen_del_opt_in():
    h = habilitar([_Local("conversacion"), _Local("pc")], habilitados=frozenset())
    assert {p.nombre for p in h.activos} == {"conversacion", "pc"}, "los locales estan siempre activos, sin opt-in"
