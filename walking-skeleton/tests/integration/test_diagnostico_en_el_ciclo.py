"""Integracion: el informe de estado es TRABAJO que el Director despacha, no una funcion suelta.

Y su veredicto vuelve al ciclo: si hay incidencias, la tarea se bloquea y la planificacion genera
trabajo de correccion. Un diagnostico que siempre dijera "ok" seria un informe descartado — el defecto
que corregimos al hacer que el ciclo reaccione al veredicto.
"""

import asyncio
import json
import tempfile

import pytest

from aura_skeleton.adapters.diagnostico import EjecutorDiagnostico
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.planificacion import CEO, oyente_de_transiciones


def _audit(tmp_path, registros):
    p = tmp_path / "audit.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")
    return str(p)


@pytest.mark.asyncio
async def test_el_diagnostico_declara_ok_cuando_no_hay_incidencias(tmp_path):
    e = EjecutorDiagnostico(_audit(tmp_path, [{"kind": "MEM"}] * 5))
    r = await e.execute("diagnosticar_estado", {}, "t", "e")
    assert r["ok"] is True and r["eventos"] == 5


@pytest.mark.asyncio
async def test_el_diagnostico_declara_NO_ok_ante_una_incidencia_dominante(tmp_path):
    e = EjecutorDiagnostico(_audit(tmp_path, [{"kind": "ERROR"}] * 4))
    r = await e.execute("diagnosticar_estado", {}, "t", "e")
    assert r["ok"] is False
    assert r["incidencia_dominante"][0] == "errores de ejecucion"
    assert "4x" in r["resumen"], f"el resumen debe ser accionable: {r['resumen']}"


@pytest.mark.asyncio
async def test_SIN_DATOS_no_es_un_problema_que_corregir(tmp_path):
    """CONTROL: ausencia de evidencia no es una incidencia. Bloquear generaria trabajo sobre nada."""
    e = EjecutorDiagnostico(str(tmp_path / "no-existe.jsonl"))
    r = await e.execute("diagnosticar_estado", {}, "t", "e")
    assert r["ok"] is True and "sin uso registrado" in r["resumen"]


def test_UN_DIAGNOSTICO_CON_INCIDENCIAS_GENERA_TRABAJO(tmp_path):
    """EL CICLO COMPLETO: el informe deja de ser un texto y pasa a producir una tarea."""

    class Motor:
        def __init__(self, ejec):
            self.e = ejec

        async def ejecutar(self, accion, args, tid, eid, origen):
            return {"accion": accion, "estado": "ejecutada", "resultado": await self.e.execute(accion, args, tid, eid)}

    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    alm.observar(oyente_de_transiciones(alm))
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="diagnostico", origen=CEO))
    ejec = EjecutorDiagnostico(_audit(tmp_path, [{"kind": "HITL"}] * 6))
    d = DirectorGeneral(alm, Motor(ejec), RegistroEjecutores({"diagnostico": "diagnosticar_estado"}))

    hecha = asyncio.run(d.ciclo("o"))

    assert hecha.estado == "bloqueada", "un diagnostico con incidencias no puede cerrarse como hecho"
    assert len(alm.tareas("o")) == 2, "debia generar trabajo de correccion"
    assert any("intervenciones humanas" in b for b in hecha.bloqueos), f"motivo real: {hecha.bloqueos}"


def test_esta_cableado_en_el_arranque_real():
    s = componer(Configuracion(datos=tempfile.mkdtemp()))
    assert s.director.ejecutores.para("diagnostico") == "diagnosticar_estado"
    assert "diagnosticar_estado" in s.registro_adaptadores.capacidades()
