"""Integracion: AURORA se apaga, arranca de nuevo y continua donde estaba. SIN intervencion humana.

CRITERIO DEL CEO (2026-08-03): no basta con "guardar informacion". La capacidad solo esta terminada si
AURORA puede **detenerse, apagarse, volver a arrancar y continuar exactamente donde estaba** sin
depender de Claude, del contexto de una conversacion ni de un checkpoint escrito a mano.

Por eso la prueba central NO reconstruye el almacen en el mismo proceso —eso probaria muy poco, porque
el objeto podria estar sobreviviendo en memoria—: **mata el proceso de verdad** con `subprocess` y
arranca otro intérprete que solo conoce la ruta del fichero. Si el proceso nuevo no sabe por donde
seguir, la capacidad no existe.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea

_RAIZ = Path(__file__).resolve().parents[2]


def _en_proceso_nuevo(codigo: str, ruta: str) -> str:
    """Ejecuta `codigo` en un INTERPRETE DISTINTO. El proceso anterior ya no existe."""
    completo = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(_RAIZ)!r})
        from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
        alm = AlmacenEstadoOperativo({ruta!r})
        {codigo}
    """)
    r = subprocess.run(
        [sys.executable, "-c", completo],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    assert r.returncode == 0, f"el proceso nuevo fallo: {r.stderr}"
    return r.stdout.strip()


def _sembrar(ruta: str) -> None:
    alm = AlmacenEstadoOperativo(ruta)
    alm.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-01",
            objetivo="Construir la Persistencia Operativa",
            plan="Extraer el patron de AlmacenReglas",
            descripcion="Escribir el almacen",
            estado="terminada",
            responsable="programador",
            evidencias=["commit:abc123"],
        )
    )
    alm.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-02",
            objetivo="Construir la Persistencia Operativa",
            plan="Extraer el patron de AlmacenReglas",
            descripcion="Probar el reinicio real",
            estado="abierta",
            responsable="qa",
            proxima_accion="ejecutar la prueba de reinicio por subproceso",
            punto_reanudacion="tests/integration/test_estado_operativo_reinicio.py",
        )
    )
    alm.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-03",
            objetivo="Construir la Persistencia Operativa",
            plan="Extraer el patron de AlmacenReglas",
            descripcion="Auditoria independiente",
            estado="bloqueada",
            responsable="auditor",
            bloqueos=["requiere que t-02 termine"],
        )
    )


def test_tras_matar_el_proceso_aurora_sabe_por_donde_seguir(tmp_path):
    """LA PRUEBA QUE DEFINE LA CAPACIDAD: otro proceso, sin contexto, continua solo."""
    ruta = str(tmp_path / "estado.jsonl")
    _sembrar(ruta)

    # El proceso que sembro el estado TERMINA aqui. Lo que sigue corre en otro interprete.
    salida = _en_proceso_nuevo(
        "t = alm.reanudar('obj-1'); print(t.tarea_id, '|', t.proxima_accion, '|', t.punto_reanudacion)",
        ruta,
    )

    assert salida.startswith("t-02"), f"el proceso nuevo no retomo la tarea correcta: {salida!r}"
    assert "ejecutar la prueba de reinicio" in salida, "no recupero la proxima accion"
    assert "test_estado_operativo_reinicio.py" in salida, "no recupero el punto exacto de reanudacion"


def test_el_proceso_nuevo_no_elige_una_tarea_bloqueada(tmp_path):
    """CONTROL: una tarea bloqueada no es trabajo accionable, aunque no este terminada.

    Sin esta distincion, reanudar despues de un reinicio elegiria trabajo imposible y AURORA se
    quedaria atascada creyendo que avanza.
    """
    ruta = str(tmp_path / "estado.jsonl")
    _sembrar(ruta)
    AlmacenEstadoOperativo(ruta).actualizar("obj-1", "t-02", estado="terminada")

    salida = _en_proceso_nuevo("print(alm.reanudar('obj-1'))", ruta)

    assert salida == "None", f"t-03 esta bloqueada: no puede proponerse como siguiente accion ({salida!r})"


def test_el_estado_vigente_es_el_ultimo_no_el_primero(tmp_path):
    """El log es append-only y la proyeccion decide: la ultima linea de una clave gana.

    Es la trampa que `AlmacenReglas._proyectar` documenta haber pagado: si la proyeccion no reemplaza,
    la busqueda encuentra la version vieja para siempre.
    """
    ruta = str(tmp_path / "estado.jsonl")
    _sembrar(ruta)
    alm = AlmacenEstadoOperativo(ruta)
    alm.actualizar("obj-1", "t-02", estado="en_curso", responsable="programador")
    alm.actualizar("obj-1", "t-02", estado="terminada", evidencias=["commit:def456"])

    salida = _en_proceso_nuevo("t = alm.tarea('obj-1','t-02'); print(t.estado, t.responsable, t.evidencias)", ruta)

    assert salida.startswith("terminada"), f"gano una version antigua: {salida!r}"
    assert "def456" in salida, "no conservo la evidencia de la ultima version"
    # Y el historial completo sigue en disco: append-only, nada se reescribio.
    lineas = [x for x in Path(ruta).read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lineas) == 5, f"debe haber 3 siembras + 2 actualizaciones, sin reescritura: {len(lineas)}"


def test_una_linea_corrupta_no_impide_arrancar(tmp_path):
    """Disponibilidad: un caracter dañado no puede dejar a AURORA sin poder reanudar.

    Es la leccion de D-A-11 (una linea corrupta en reglas.jsonl tumbaba TODO el arranque).
    """
    ruta = str(tmp_path / "estado.jsonl")
    _sembrar(ruta)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write("{esto no es json valido\n")

    salida = _en_proceso_nuevo("t = alm.reanudar('obj-1'); print(t.tarea_id if t else 'None')", ruta)

    assert salida == "t-02", f"la linea corrupta impidio reanudar: {salida!r}"


def test_la_reanudacion_es_determinista_entre_procesos(tmp_path):
    """Dos arranques del mismo estado eligen SIEMPRE la misma tarea.

    Sin esto, reanudar seria una decision distinta en cada reinicio y nada seria auditable.
    """
    ruta = str(tmp_path / "estado.jsonl")
    _sembrar(ruta)
    alm = AlmacenEstadoOperativo(ruta)
    for i in range(4, 9):  # varias tareas abiertas a la vez
        alm.registrar(Tarea(objetivo_id="obj-1", tarea_id=f"t-{i:02d}", estado="abierta"))

    huellas = {_en_proceso_nuevo("print(alm.reanudar('obj-1').tarea_id)", ruta) for _ in range(5)}

    assert huellas == {"t-02"}, f"la reanudacion no es determinista entre procesos: {huellas}"


def test_objetivos_activos_sobrevive_al_reinicio(tmp_path):
    """AURORA debe saber, al arrancar, QUE objetivo tenia activo sin que nadie se lo diga."""
    ruta = str(tmp_path / "estado.jsonl")
    _sembrar(ruta)

    salida = _en_proceso_nuevo("print(json.dumps(alm.objetivos_activos()))".replace("json", "__import__('json')"), ruta)

    assert "obj-1" in salida, f"no recupero el objetivo activo tras el reinicio: {salida!r}"


def test_control_sin_estado_persistido_no_hay_nada_que_reanudar(tmp_path):
    """CONTROL NEGATIVO: sin fichero, el almacen no inventa trabajo.

    Sin este control, las pruebas anteriores pasarian con una implementacion que devolviera algo
    siempre. Ademas verifica que arrancar en frio no revienta.
    """
    ruta = str(tmp_path / "no-existe.jsonl")

    salida = _en_proceso_nuevo("print(alm.reanudar('obj-1'), alm.objetivos_activos())", ruta)

    assert salida == "None []", f"sin estado persistido no puede haber reanudacion: {salida!r}"
    assert not Path(ruta).exists(), "leer no puede crear el fichero"


def test_el_estado_vigente_es_correcto_SIN_reiniciar(tmp_path):
    """CONTROL EN LA MISMA SESION: la proyeccion en memoria debe reemplazar, no acumular.

    Lo detecto la mutacion: todas las demas pruebas consultan tras reiniciar, y al recargar del disco
    `_cargar` reconstruye la proyeccion con un dict —que reemplaza por clave por definicion—, de modo
    que un fallo de `_proyectar` quedaba invisible. El defecto solo se manifiesta EN LA MISMA SESION,
    que es precisamente la trampa que `AlmacenReglas._proyectar` documenta haber pagado: crear ->
    desactivar -> crear dejaba dos entradas de la misma clave y la busqueda encontraba la vieja.
    """
    ruta = str(tmp_path / "estado.jsonl")
    alm = AlmacenEstadoOperativo(ruta)
    alm.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="qa"))
    alm.actualizar("o", "t-01", estado="terminada", responsable="programador")

    # SIN reiniciar: se consulta el mismo objeto que hizo las escrituras.
    assert len(alm.tareas("o")) == 1, "la proyeccion acumulo dos entradas para la misma clave"
    vigente = alm.tarea("o", "t-01")
    assert vigente.estado == "terminada", f"gano la version antigua en memoria: {vigente.estado}"
    assert alm.abiertas("o") == [], "una tarea terminada no puede seguir contando como abierta"
    assert alm.reanudar("o") is None, "no queda trabajo accionable, pero reanudar propuso uno"
