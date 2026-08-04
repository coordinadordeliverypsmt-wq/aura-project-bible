"""Integracion: el ciclo completo de auto-mejora sobre el SISTEMA REAL, sin simulacion.

Objetivo -> Director -> ejecutor -> resultado -> (si procede) nueva tarea -> Director -> fin.

Antes de este incremento el bucle estaba construido por sus dos extremos y DESCONECTADO en el medio:
`desde_verificacion` existia y no la invocaba nadie. El Director cerraba o bloqueaba una tarea y ahi
terminaba todo. Un objetivo bloqueado quedaba atascado sin que nadie reaccionara.

LA SEPARACION QUE PIDIO EL CEO: el Director informa el resultado de una transicion, el PROTOCOLO
notifica que ocurrio, y la PLANIFICACION decide si nace trabajo. No hay llamada directa entre ellos.
"""

import asyncio
import tempfile

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estado_operativo import Tarea


def _sistema():
    return componer(Configuracion(datos=tempfile.mkdtemp()))


def test_UN_OBJETIVO_BLOQUEADO_GENERA_SU_PROPIO_TRABAJO_DE_DESBLOQUEO():
    """EL HITO: el ciclo se realimenta solo. Nadie escribio la segunda tarea."""
    s = _sistema()
    s.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj",
            tarea_id="t-01",
            estado="abierta",
            responsable="arquitecto",
            descripcion="revisar el diseño",
        )
    )

    asyncio.run(s.motor_ciclo.correr("obj", max_latidos=1))
    tareas = s.estado_operativo.tareas("obj")

    assert len(tareas) == 2, f"el bloqueo debia generar trabajo de desbloqueo, hay {len(tareas)} tarea(s)"
    nueva = next(t for t in tareas if t.tarea_id != "t-01")
    assert nueva.origen == "derivado" and nueva.prioridad == 1
    assert "desbloquear" in nueva.descripcion
    assert any("ningun ejecutor" in e for e in nueva.evidencias), "debe conservar la causa real"


def test_el_trabajo_derivado_NO_se_realimenta_a_si_mismo():
    """El corte estructural sigue vigente: si no, el ciclo generaria trabajo indefinidamente."""
    s = _sistema()
    s.estado_operativo.registrar(Tarea(objetivo_id="obj", tarea_id="t-01", estado="abierta", responsable="arquitecto"))

    asyncio.run(s.motor_ciclo.correr("obj"))  # corre hasta agotar

    tareas = s.estado_operativo.tareas("obj")
    assert len(tareas) == 2, f"el ciclo debe converger: 1 humana + 1 derivada, hay {len(tareas)}"
    assert s.estado_operativo.abiertas("obj") == [], "el objetivo debe quedar sin trabajo accionable"


def test_el_programador_real_esta_cableado():
    """El marcador de posicion desaparecio: 'programador' despacha la capacidad real."""
    s = _sistema()
    assert s.director.ejecutores.para("programador") == "proponer_cambio"
    assert "proponer_cambio" in s.registro_adaptadores.capacidades()


def test_el_director_NO_conoce_la_planificacion():
    """La separacion es verificable: el Director informa transiciones, no decide que trabajo nace."""
    import inspect

    from aura_skeleton.core import director

    fuente = inspect.getsource(director)
    for termino in ("planificacion", "admitir", "desde_verificacion", "oyente"):
        assert termino not in fuente, f"el Director conoce '{termino}': acoplamiento indebido"


def test_una_tarea_TERMINADA_no_genera_trabajo():
    """CONTROL NEGATIVO: solo el bloqueo realimenta. Sin esto, cada avance crearia trabajo nuevo."""
    s = _sistema()
    s.estado_operativo.registrar(Tarea(objetivo_id="obj", tarea_id="t-01", estado="abierta"))
    s.estado_operativo.transitar("obj", "t-01", "terminada", autoridad="test", causa="ok")

    assert len(s.estado_operativo.tareas("obj")) == 1, "una tarea terminada no necesita correccion"
