"""Integracion: AURORA toma trabajo de su propio backlog, lo ejecuta y prepara lo siguiente.

CAPACIDAD QUE DEMUESTRA (CEO, 2026-08-03): leer el backlog persistido, seleccionar la siguiente tarea,
ejecutarla por el Motor Unico, validar el resultado, actualizar el Estado Operativo y dejar preparada
la siguiente accion — **incluso despues de reiniciar el proceso**.

El Director NO ejecuta: despacha por el motor. Estas pruebas usan un motor espia para comprobar
exactamente eso, y una prueba final mata el proceso para verificar que el ciclo sobrevive.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores, ResponsableDuplicado
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea

_RAIZ = Path(__file__).resolve().parents[2]


class MotorEspia:
    """Doble del Motor Unico: registra como fue llamado y devuelve el estado que se le indique."""

    def __init__(self, estado="ejecutada", motivo=""):
        self._estado, self._motivo, self.llamadas = estado, motivo, []

    async def ejecutar(self, accion, args, trace_id, event_id, origen):
        self.llamadas.append({"accion": accion, "args": args, "origen": origen})
        return {"accion": accion, "estado": self._estado, "motivo": self._motivo}


def _backlog(ruta):
    alm = AlmacenEstadoOperativo(ruta)
    alm.registrar(
        Tarea(
            objetivo_id="obj",
            tarea_id="t-01",
            descripcion="copiar el informe",
            estado="abierta",
            responsable="programador",
            args={"ruta": "/tmp/informe.txt"},
        )
    )
    alm.registrar(
        Tarea(
            objetivo_id="obj",
            tarea_id="t-02",
            descripcion="auditar el resultado",
            estado="abierta",
            responsable="auditor",
        )
    )
    return alm


@pytest.mark.asyncio
async def test_aurora_toma_una_tarea_de_su_backlog_y_la_despacha_por_el_motor(tmp_path):
    """LA CAPACIDAD: nadie le dice que hacer; lo deduce de su estado persistido."""
    ruta = str(tmp_path / "estado.jsonl")
    alm, motor = _backlog(ruta), MotorEspia()
    d = DirectorGeneral(alm, motor, RegistroEjecutores({"programador": "copiar_archivo"}))

    hecha = await d.ciclo("obj")

    assert len(motor.llamadas) == 1, "debe despachar exactamente una tarea por vuelta"
    assert motor.llamadas[0]["accion"] == "copiar_archivo", "no resolvio el ejecutor del responsable"
    assert motor.llamadas[0]["args"] == {"ruta": "/tmp/informe.txt"}, "no propago los argumentos"
    assert motor.llamadas[0]["origen"] == "director:programador", "el origen debe identificar al responsable"
    assert hecha.estado == "terminada"
    assert "motor:copiar_archivo:ejecutada" in hecha.evidencias, "debe registrar evidencia del resultado real"


@pytest.mark.asyncio
async def test_deja_preparada_la_siguiente_accion_antes_de_terminar(tmp_path):
    ruta = str(tmp_path / "estado.jsonl")
    d = DirectorGeneral(_backlog(ruta), MotorEspia(), RegistroEjecutores({"programador": "copiar_archivo"}))

    hecha = await d.ciclo("obj")

    assert "t-02" in hecha.proxima_accion, f"no dejo preparada la siguiente tarea: {hecha.proxima_accion!r}"
    assert "auditar" in hecha.proxima_accion


@pytest.mark.asyncio
async def test_una_accion_detenida_por_el_gobierno_NO_cierra_la_tarea(tmp_path):
    """INV-9 / ALERTA-005 punto 4: solo "ejecutada" cierra. "detenida" es el gobierno funcionando."""
    ruta = str(tmp_path / "estado.jsonl")
    motor = MotorEspia(estado="detenida", motivo="permisos: kill switch activo")
    d = DirectorGeneral(_backlog(ruta), motor, RegistroEjecutores({"programador": "copiar_archivo"}))

    hecha = await d.ciclo("obj")

    assert hecha.estado == "bloqueada", "una accion detenida no puede dar la tarea por terminada"
    assert any("kill switch" in b for b in hecha.bloqueos), "debe conservar el motivo real del bloqueo"


@pytest.mark.asyncio
async def test_sin_ejecutor_la_tarea_se_bloquea_y_se_declara(tmp_path):
    """Sin dueno no hay ejecucion Y EL HECHO SE DECLARA (regla de RegistroAdaptadores, ALERTA-005)."""
    ruta = str(tmp_path / "estado.jsonl")
    motor = MotorEspia()
    d = DirectorGeneral(_backlog(ruta), motor, RegistroEjecutores({}))  # nadie atiende

    hecha = await d.ciclo("obj")

    assert motor.llamadas == [], "no puede despacharse una tarea sin ejecutor conocido"
    assert hecha.estado == "bloqueada"
    assert any("ningun ejecutor" in b for b in hecha.bloqueos), "el hecho debe quedar declarado"


def test_un_responsable_no_puede_tener_dos_ejecutores():
    """Un responsable, un dueno: la ambiguedad se rechaza al registrar, no en ejecucion."""
    r = RegistroEjecutores({"qa": "validar"})
    with pytest.raises(ResponsableDuplicado):
        r.registrar("qa", "otra_accion")


@pytest.mark.asyncio
async def test_control_sin_backlog_no_inventa_trabajo(tmp_path):
    """CONTROL NEGATIVO: sin tareas accionables el Director no despacha nada."""
    ruta = str(tmp_path / "vacio.jsonl")
    motor = MotorEspia()
    d = DirectorGeneral(AlmacenEstadoOperativo(ruta), motor, RegistroEjecutores({"programador": "copiar_archivo"}))

    assert await d.ciclo("obj") is None, "sin backlog no puede haber trabajo que hacer"
    assert motor.llamadas == [], "no puede despacharse nada cuando no hay tareas"


def test_el_ciclo_continua_tras_MATAR_el_proceso(tmp_path):
    """LA PRUEBA QUE DEFINE EL INCREMENTO: el proceso muere y otro sigue el ciclo donde quedo.

    El primer proceso ejecuta una vuelta y termina. El segundo —interprete distinto, sin contexto
    alguno— lee el estado del disco, ve que t-01 quedo terminada y despacha t-02 por su cuenta.
    """
    ruta = str(tmp_path / "estado.jsonl")
    _backlog(ruta)

    guion = textwrap.dedent(f"""
        import asyncio, sys
        sys.path.insert(0, {str(_RAIZ)!r})
        from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
        from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo

        class Motor:
            async def ejecutar(self, accion, args, tid, eid, origen):
                print("DESPACHA", accion, origen)
                return {{"accion": accion, "estado": "ejecutada"}}

        alm = AlmacenEstadoOperativo({ruta!r})
        d = DirectorGeneral(alm, Motor(), RegistroEjecutores(
            {{"programador": "copiar_archivo", "auditor": "consultar"}}))
        t = asyncio.run(d.ciclo("obj"))
        print("TAREA", t.tarea_id if t else "None", t.estado if t else "-")
    """)

    def arrancar():
        r = subprocess.run(
            [sys.executable, "-c", guion],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
        assert r.returncode == 0, r.stderr
        return r.stdout

    primera = arrancar()  # proceso 1: hace t-01 y MUERE
    segunda = arrancar()  # proceso 2: arranca de cero y continua solo

    assert "TAREA t-01 terminada" in primera, f"el primer proceso no cerro t-01: {primera!r}"
    assert "TAREA t-02 terminada" in segunda, f"el segundo proceso no continuo por t-02: {segunda!r}"
    assert "DESPACHA consultar director:auditor" in segunda, "no resolvio el ejecutor del segundo responsable"

    tercera = arrancar()  # proceso 3: ya no queda trabajo
    assert "TAREA None" in tercera, f"deberia no quedar trabajo accionable: {tercera!r}"
