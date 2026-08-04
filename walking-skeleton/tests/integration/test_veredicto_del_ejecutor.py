"""Integracion: el ciclo reacciona al RESULTADO de una verificacion, no solo a que se ejecutara.

Antes, un ejecutor podia devolver `ok: False` y la tarea se cerraba como "terminada" con evidencia
`motor:auditar_garantias:ejecutada` —literalmente cierta y completamente engañosa—. AURORA podia
auditar y verificar, y descartaba lo que descubria: cada ejecutor nuevo aportaba informacion que el
ciclo ignoraba.

VALIDACION EN DOS NIVELES: el motor dice si la accion PUDO ejecutarse; el ejecutor dice si el
resultado es BUENO. Hacen falta ambos.
"""

import asyncio

import pytest

from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea


class MotorConVeredicto:
    """Motor que ejecuta bien y devuelve el veredicto del ejecutor, como hace el Motor Unico real."""

    def __init__(self, ok):
        self.ok = ok

    async def ejecutar(self, accion, args, trace_id, event_id, origen):
        return {
            "accion": accion,
            "estado": "ejecutada",  # la accion SI pudo ejecutarse
            "resultado": {
                "capacidad": accion,
                "ok": self.ok,
                "resumen": "3 garantias rotas" if not self.ok else "todo bien",
            },
        }


def _director(tmp_path, ok):
    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="auditor"))
    return DirectorGeneral(alm, MotorConVeredicto(ok), RegistroEjecutores({"auditor": "auditar_garantias"})), alm


def test_un_veredicto_NEGATIVO_no_cierra_la_tarea(tmp_path):
    """EL DEFECTO QUE CIERRA: ejecutarse bien no es lo mismo que dar un resultado bueno."""
    d, _ = _director(tmp_path, ok=False)

    t = asyncio.run(d.ciclo("o"))

    assert t.estado == "bloqueada", f"un veredicto negativo no puede darse por terminado: {t.estado}"
    assert any("3 garantias rotas" in b for b in t.bloqueos), f"debe conservar el motivo REAL: {t.bloqueos}"


def test_un_veredicto_POSITIVO_si_cierra_la_tarea(tmp_path):
    """CONTROL: sin esto, la prueba anterior pasaria con un sistema que nunca cierra nada."""
    d, _ = _director(tmp_path, ok=True)

    t = asyncio.run(d.ciclo("o"))

    assert t.estado == "terminada", f"un veredicto positivo debe cerrar la tarea: {t.estado}"


def test_un_ejecutor_sin_veredicto_sigue_funcionando(tmp_path):
    """Compatibilidad: los ejecutores que no declaran `ok` (copiar_archivo) no se rompen."""

    class MotorSinVeredicto:
        async def ejecutar(self, accion, args, trace_id, event_id, origen):
            return {"accion": accion, "estado": "ejecutada"}

    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="programador"))
    d = DirectorGeneral(alm, MotorSinVeredicto(), RegistroEjecutores({"programador": "copiar_archivo"}))

    assert asyncio.run(d.ciclo("o")).estado == "terminada"


@pytest.mark.asyncio
async def test_el_bloqueo_por_veredicto_GENERA_trabajo_de_correccion(tmp_path):
    """El ciclo completo: un mal resultado se convierte en trabajo, no en un informe descartado."""
    from aura_skeleton.core.planificacion import CEO, oyente_de_transiciones

    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    alm.observar(oyente_de_transiciones(alm))
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="auditor", origen=CEO))
    d = DirectorGeneral(alm, MotorConVeredicto(ok=False), RegistroEjecutores({"auditor": "auditar_garantias"}))

    await d.ciclo("o")

    tareas = alm.tareas("o")
    assert len(tareas) == 2, f"el veredicto negativo debia generar trabajo de correccion: {len(tareas)}"
    assert any(t.origen == "derivado" for t in tareas)
