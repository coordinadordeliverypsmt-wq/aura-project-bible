"""RED · D-CP-1 — el ciclo `instalar -> ejecutar -> retirar`, según el contrato aprobado.

`CONTRATO-AGENTE-EXTERNO-BAJO-DEMANDA.md` describe el procedimiento en su **§4** y lo declara
*«conceptual — no implementado, no ejecutado»*. Esto lo implementa **sin ampliarlo**: cada garantía
de aquí cita la cláusula que la exige.

**Las dos barreras que ninguna prisa levanta:**
- **§2** — se invita a un externo *«solo cuando `AGENTE_EXTERNO_REQUIRED` esté explícitamente
  determinado y justificado»*, y *«un fallo del agente principal NO es, por sí solo, motivo
  suficiente»*.
- **§3** — *«ningún externo recibe código confidencial de AURA»* mientras `AURA_APPROVED` esté
  vacío: **solo fixtures sintéticos**.

**El ciclo se prueba con un ejecutor de comandos INYECTADO.** No es un mock decorativo: es la costura
que permite comprobar el fallo de instalación, el de ejecución y el de retirada —tres caminos que no
se pueden provocar a voluntad contra un instalador real— sin renunciar a un E2E real, que vive
aparte.
"""

from __future__ import annotations

import pytest
from ciclo_bajo_demanda import (
    CicloBloqueado,
    Ejecucion,
    esta_instalado,
    necesidad_determinada,
    politica_de_datos_permite,
    resultado_del_ciclo,
)


class EjecutorFalso:
    """Doble del ejecutor de comandos. Registra lo que se le pide y simula el estado del sistema."""

    def __init__(self, instalado=False, falla_en=(), instalado_tras_retirar=False, residuos=False):
        self.ordenes: list[tuple] = []
        self._instalado = instalado
        self._falla_en = set(falla_en)
        self._instalado_tras_retirar = instalado_tras_retirar
        # `comprobar_residuos` devuelve 0 CUANDO HAY residuos (es un `grep -qv "^0$"`), asi que el
        # doble por defecto simula que no queda ninguno.
        self._residuos = residuos

    def __call__(self, paso: str, orden: tuple[str, ...]) -> Ejecucion:
        self.ordenes.append((paso, orden))
        if paso in self._falla_en:
            return Ejecucion(paso=paso, orden=orden, codigo=1, salida="fallo simulado")
        if paso == "instalar":
            self._instalado = True
        if paso == "retirar":
            self._instalado = self._instalado_tras_retirar
        if paso == "comprobar":
            return Ejecucion(paso=paso, orden=orden, codigo=0 if self._instalado else 1, salida="")
        if paso == "comprobar_residuos":
            return Ejecucion(paso=paso, orden=orden, codigo=0 if self._residuos else 1, salida="")
        if paso == "limpiar":
            self._residuos = False
        return Ejecucion(paso=paso, orden=orden, codigo=0, salida="ok")


ESTADO_CON_NECESIDAD = {
    "AGENTE_EXTERNO_REQUIRED": {
        "motivo": "segunda opinion independiente: el que implementa nunca audita su propio trabajo",
        "justificado_por": "CONTRATO §2",
    }
}


def _ciclo(**kw):
    from ciclo_bajo_demanda import ciclo
    return ciclo(**kw)


# ============================================== §2 · CUÁNDO PROCEDE INVITAR --


def test_sin_necesidad_declarada_el_ciclo_NO_arranca():
    """**Fail-closed.** Sin `AGENTE_EXTERNO_REQUIRED`, invitar a un externo no está autorizado."""
    procede, motivo = necesidad_determinada({})
    assert procede is False and "AGENTE_EXTERNO_REQUIRED" in motivo


def test_una_necesidad_SIN_justificar_no_basta():
    """§2: debe estar *«explícitamente determinado Y justificado»*. Las dos cosas."""
    procede, _ = necesidad_determinada({"AGENTE_EXTERNO_REQUIRED": {"motivo": ""}})
    assert procede is False


def test_un_fallo_del_agente_principal_NO_es_motivo_suficiente():
    """§2 lo dice con todas las letras. Es la trampa que el contrato quiso cerrar de antemano:
    *«casi siempre significa que hay que corregir el trabajo, no cambiar de trabajador»*."""
    procede, motivo = necesidad_determinada(
        {"AGENTE_EXTERNO_REQUIRED": {"motivo": "el agente principal fallo al implementar la tarea"}})
    assert procede is False and "no es motivo suficiente" in motivo.lower()


def test_una_necesidad_del_catalogo_del_parrafo_2_SI_procede():
    """**Meta-control.** Sin este caso, un `necesidad_determinada` que dijera «no» siempre pasaría
    todas las pruebas anteriores y el ciclo estaría muerto sin que nadie lo notara."""
    procede, _ = necesidad_determinada(ESTADO_CON_NECESIDAD)
    assert procede is True


# ================================================== §3 · POLÍTICA DE DATOS --


def test_no_se_envia_codigo_de_AURA_mientras_AURA_APPROVED_este_vacio():
    assert politica_de_datos_permite({"tipo": "codigo_de_aura"}, aprobados=[]) is False


def test_un_fixture_sintetico_SI_se_puede_enviar():
    assert politica_de_datos_permite({"tipo": "fixture_sintetico"}, aprobados=[]) is True


def test_una_carga_sin_tipo_declarado_se_rechaza():
    """Fail-closed: lo que no se sabe qué es, no sale de la máquina."""
    assert politica_de_datos_permite({}, aprobados=[]) is False


def test_el_ciclo_se_detiene_si_la_carga_no_cumple_la_politica():
    ejecutor = EjecutorFalso()
    with pytest.raises(CicloBloqueado, match="politica de datos"):
        _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "codigo_de_aura"},
               aprobados=[], ejecutor=ejecutor)
    assert ejecutor.ordenes == [], "no debe tocarse el sistema si la carga no está autorizada"


# ======================================================== EL CICLO COMPLETO --


def test_el_ciclo_recorre_instalar_ejecutar_retirar_y_verificar():
    ejecutor = EjecutorFalso()
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico", "tarea": "sumar"},
               aprobados=[], ejecutor=ejecutor)
    pasos = [paso for paso, _ in ejecutor.ordenes]
    assert pasos.index("instalar") < pasos.index("ejecutar") < pasos.index("retirar")
    assert pasos[-1] == "comprobar_residuos", "la última palabra la tiene la verificación de ausencia"
    assert resultado_del_ciclo(r) == "COMPLETED"
    assert r["retirado"] is True and r["residuo"] is False


def test_la_ejecucion_queda_trazada():
    """§4 · `capturar evidencia` y `registrar resultado`. Un ciclo sin rastro no es auditable."""
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico", "tarea": "sumar"},
               aprobados=[], ejecutor=EjecutorFalso())
    assert [e.paso for e in r["evidencia"]] == [
        "instalar", "ejecutar", "retirar", "limpiar", "comprobar", "comprobar_residuos"]
    assert r["motivo"], "debe quedar registrado POR QUÉ se invitó al externo"


# ================================================================ FALLOS --


def test_si_la_instalacion_FALLA_no_se_ejecuta_nada():
    ejecutor = EjecutorFalso(falla_en={"instalar"})
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
               aprobados=[], ejecutor=ejecutor)
    assert resultado_del_ciclo(r) == "FALLO_INSTALACION"
    assert "ejecutar" not in [p for p, _ in ejecutor.ordenes]


def test_si_la_EJECUCION_falla_igualmente_se_retira():
    """El externo no se queda instalado porque su tarea saliera mal."""
    ejecutor = EjecutorFalso(falla_en={"ejecutar"})
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
               aprobados=[], ejecutor=ejecutor)
    assert resultado_del_ciclo(r) == "FALLO_EJECUCION"
    assert "retirar" in [p for p, _ in ejecutor.ordenes], "un fallo no justifica dejarlo instalado"
    assert r["retirado"] is True


def test_si_la_RETIRADA_falla_NO_se_declara_COMPLETED():
    """La garantía 13 del encargo, y la más fácil de falsear: declarar el ciclo cerrado mientras el
    agente sigue en la máquina."""
    ejecutor = EjecutorFalso(falla_en={"retirar"}, instalado_tras_retirar=True)
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
               aprobados=[], ejecutor=ejecutor)
    assert resultado_del_ciclo(r) != "COMPLETED"
    assert resultado_del_ciclo(r) == "RESIDUO"
    assert r["residuo"] is True, "debe quedar EVIDENCIA de que el agente sigue instalado"


def test_residuo_detectado_aunque_la_retirada_diga_que_fue_bien():
    """No basta con que `desinstalar` devuelva 0: se **comprueba**. Es la diferencia entre creer y
    verificar, y este proyecto ya sabe lo que cuesta confundirlas."""
    ejecutor = EjecutorFalso(instalado_tras_retirar=True)
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
               aprobados=[], ejecutor=ejecutor)
    assert r["residuo"] is True and resultado_del_ciclo(r) != "COMPLETED"


# ===================================================== LO QUE NO PUEDE HACER --


def test_el_ciclo_no_toca_tareas_AUTO_ni_promueve():
    """§5 y §6 del contrato: el externo no modifica `tareas_AUTO` ni aprueba nada, y **el ciclo
    tampoco lo hace en su nombre**."""
    estado = dict(ESTADO_CON_NECESIDAD, tareas_AUTO=[{"id": "T-1"}], propuestas=[{"id": "P-1"}])
    antes = (list(estado["tareas_AUTO"]), list(estado["propuestas"]))
    _ciclo(estado=estado, carga={"tipo": "fixture_sintetico"}, aprobados=[], ejecutor=EjecutorFalso())
    assert (estado["tareas_AUTO"], estado["propuestas"]) == antes


def test_el_ciclo_no_marca_AURA_APPROVED():
    estado = dict(ESTADO_CON_NECESIDAD, modelos_AURA_APPROVED=[])
    _ciclo(estado=estado, carga={"tipo": "fixture_sintetico"}, aprobados=[], ejecutor=EjecutorFalso())
    assert estado["modelos_AURA_APPROVED"] == [], "aprobar un modelo es decisión del CEO (§3)"


def test_esta_instalado_pregunta_al_sistema_y_no_a_una_variable():
    """Si la detección se fiara de un estado propio, un residuo real sería invisible."""
    ejecutor = EjecutorFalso(instalado=True)
    assert esta_instalado("opencode", ejecutor) is True
    assert [p for p, _ in ejecutor.ordenes] == ["comprobar"]


# ===== §4 · `limpiar residuos` — paso AÑADIDO 2026-08-25 tras medirlo en el E2E real --
#
# El primer ciclo real termino con `command -v opencode` en AUSENTE y aun asi dejo TRES directorios
# en HOME: `npm uninstall` retira el paquete, no el rastro. El §4 pide `desinstalar` y **luego**
# `limpiar residuos`; mi implementacion tenia el primero y no el segundo, y la comprobacion de
# ausencia miraba solo al ejecutable, de modo que habria declarado COMPLETED con residuo en disco.


def test_el_ciclo_limpia_los_residuos_ademas_de_desinstalar():
    ejecutor = EjecutorFalso()
    _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
           aprobados=[], ejecutor=ejecutor)
    pasos = [paso for paso, _ in ejecutor.ordenes]
    assert "limpiar" in pasos, "§4 pide limpiar residuos, no solo desinstalar"
    assert pasos.index("retirar") < pasos.index("limpiar")


def test_un_residuo_en_disco_impide_declarar_COMPLETED():
    """Aunque el ejecutable ya no responda. Es el caso exacto que el E2E real destapo."""
    class ConResiduo(EjecutorFalso):
        def __call__(self, paso, orden):
            eje = super().__call__(paso, orden)
            if paso == "comprobar_residuos":
                return Ejecucion(paso=paso, orden=orden, codigo=0, salida="3")  # 0 = HAY residuos
            return eje

    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
               aprobados=[], ejecutor=ConResiduo())
    assert r["residuo"] is True and resultado_del_ciclo(r) == "RESIDUO"


def test_sin_residuos_y_sin_ejecutable_el_ciclo_SI_es_COMPLETED():
    """Meta-control del paso nuevo: si `comprobar_residuos` bloqueara siempre, el ciclo no podria
    cerrarse nunca y las dos pruebas anteriores pasarian igual."""
    r = _ciclo(estado=ESTADO_CON_NECESIDAD, carga={"tipo": "fixture_sintetico"},
               aprobados=[], ejecutor=EjecutorFalso())
    assert resultado_del_ciclo(r) == "COMPLETED" and r["residuo"] is False
