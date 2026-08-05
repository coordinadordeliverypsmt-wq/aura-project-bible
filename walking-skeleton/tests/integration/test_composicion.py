"""Punto de entrada unico de produccion (MA.1).

Existe para impedir el patron que ya costo ALERTA-004 y ALERTA-005 dos veces: **una capacidad
construida y probada que ningun camino real enciende.**

Hasta MA.1 habia siete scripts cableando el `Orchestrator` por su cuenta, y la auditoria del
2026-07-21 midio que **ninguno activaba la captura de senales de M3.0**. Estas pruebas verifican que
el arranque oficial enciende el sistema COMPLETO, y fallan si alguna pieza queda fuera.

Criterio de diseno de estas pruebas: no comprueban que los objetos existan, sino que el sistema
armado **tiene todas las capacidades declaradas alcanzables**. Una prueba que solo verificara
`assert sistema is not None` habria pasado con el cableado incompleto que la auditoria encontro.
"""

import os

import pytest

from aura_skeleton.composicion import Configuracion, componer


@pytest.fixture
def config(tmp_path):
    return Configuracion(
        datos=str(tmp_path),
        raices_permitidas=(str(tmp_path),),
        usar_stack_real=False,
    )


def test_arranque_registra_todos_los_adaptadores(config):
    """Toda capacidad del catalogo con adaptador disponible debe quedar registrada."""
    sistema = componer(config)

    capacidades = sistema.registro_adaptadores.capacidades()
    assert "listar_directorio" in capacidades, "el adaptador del computador no se encendio"
    assert "borrar_archivo" in capacidades
    assert "encender_dispositivo" in capacidades, "el adaptador del hogar no se encendio"


def test_arranque_enciende_la_captura_de_senales(config):
    """REGRESION DE LA AUDITORIA: ninguno de los siete scripts activaba la captura."""
    sistema = componer(config)

    assert sistema.orquestador.contexto is not None, "la captura de senales quedo apagada"
    fuentes = sistema.registro_contexto.fuentes
    assert set(fuentes) == {"conversacion", "computador", "home_assistant"}, f"faltan fuentes de contexto: {fuentes}"


def test_arranque_configura_el_audit_log_persistente(config, tmp_path):
    """Sin audit log persistente no hay registro forense ni senales implicitas."""
    import os

    sistema = componer(config)
    assert sistema.ruta_audit.startswith(str(tmp_path))

    # El log debe existir tras registrar una accion auditable.
    from aura_skeleton import observability as obs

    obs.log("TEST", "composicion", "accion de prueba", "t", audit=True)
    assert os.path.exists(sistema.ruta_audit), "el audit log no se creo"


def test_arranque_cablea_el_kill_switch(config):
    """El kill switch debe alcanzar al ejecutor, no solo existir."""
    sistema = componer(config)

    assert sistema.kill_switch is not None
    assert sistema.permisos._kill is sistema.kill_switch, "el kill switch no llega a Permisos"
    assert sistema.motor.permisos is sistema.permisos, "el motor usa otros permisos: habria dos politicas"


def test_arranque_usa_memoria_persistente(config, tmp_path):
    """En produccion la memoria NO puede vivir en un directorio temporal que se borra."""
    sistema = componer(config)

    assert sistema.ruta_memoria.startswith(str(tmp_path))
    assert "tmp" not in sistema.ruta_memoria.replace(str(tmp_path), ""), "memoria en directorio volatil"


def test_arranque_enciende_las_automatizaciones_del_usuario(config, tmp_path):
    """MVP capacidad 5: las reglas del usuario deben quedar ENCENDIDAS y persistir junto a su estado.

    Detectada por mutacion: sin esta prueba, quitar `automatizaciones=` del cableado dejaba la
    capacidad construida, probada e INALCANZABLE desde el arranque real — exactamente ALERTA-005.
    Se comprueba tambien que el orquestador use EL MISMO almacen que expone el sistema: dos almacenes
    distintos harian que lo que el usuario crea y lo que el sistema ejecuta diverjan en silencio.
    """
    sistema = componer(config)

    assert sistema.automatizaciones is not None, "las automatizaciones del usuario quedaron apagadas"
    assert sistema.orquestador.automatizaciones is sistema.automatizaciones, "el orquestador usa otro almacen"
    assert sistema.automatizaciones._ruta.startswith(str(tmp_path)), "las reglas no viven con el estado del usuario"


def test_orquestador_y_motor_comparten_el_mismo_registro(config):
    """Un registro distinto en cada uno permitiria dos conjuntos de capacidades divergentes."""
    sistema = componer(config)

    assert sistema.orquestador.motor is sistema.motor
    assert sistema.motor.registro is sistema.registro_adaptadores


@pytest.mark.asyncio
async def test_el_sistema_compuesto_ejecuta_de_extremo_a_extremo(config, tmp_path):
    """La verificacion que de verdad importa: hablarle al sistema compuesto y que ACTUE."""
    (tmp_path / "documentos").mkdir()
    (tmp_path / "documentos" / "factura.txt").write_text("x")

    sistema = componer(config)
    sistema.orquestador.router = _RouterFijo(str(tmp_path / "documentos"))

    await sistema.orquestador.handle_utterance("mauricio", "lista esa carpeta", "T-e2e")
    res = await sistema.orquestador.wait("T-e2e")

    assert "ejecutada" in res["say"], f"el sistema compuesto no ejecuto la accion: {res['say']!r}"


class _RouterFijo:
    """Sustituye solo el modelo: el resto del sistema es el compuesto de verdad."""

    def __init__(self, ruta):
        self._ruta = ruta

    async def route(self, prompt, tid):
        import json

        return "fijo", json.dumps({"action": "listar_directorio", "args": {"ruta": self._ruta}, "say": "Listo."})


# --- Ejecutable de produccion ------------------------------------------------


def test_existe_un_ejecutable_de_produccion():
    """`python -m aura_skeleton` debe ser el mecanismo oficial para ejecutar AURA.

    La auditoria constato que no existia ningun programa que ejecutar: solo scripts de demo.
    """
    import importlib.util

    assert importlib.util.find_spec("aura_skeleton.__main__") is not None, "no existe punto de entrada ejecutable"


def test_el_ejecutable_arranca_y_reporta_el_sistema(tmp_path):
    """Arranque real por subproceso: si el cableado falla, el proceso no llega a reportar."""
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "-m", "aura_skeleton", "--verificar"],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "AURA_DATOS": str(tmp_path), "AURA_STACK_REAL": "0"},
    )
    salida = res.stdout + res.stderr
    assert res.returncode == 0, f"el arranque fallo: {salida[-500:]}"
    assert "capacidades" in salida.lower()
    assert "conversacion" in salida.lower(), "la captura de senales no aparece en el arranque"


def test_el_ejecutable_gobierno_publica_el_estado_operativo_real(tmp_path):
    """`--gobierno` debe pasar por el MISMO `componer()` que el resto (D40/PIEZA 3), leyendo el
    estado operativo REAL -- no un panel vacio. Se siembra una tarea en el log append-only ANTES de
    arrancar el proceso, tal como quedaria tras una sesion anterior de AURORA, para distinguir "el
    cableado lee el estado real" de "el cableado no engancha nada" (el mismo patron de ALERTA-005:
    una capacidad construida y probada en aislamiento que ningun camino real enciende)."""
    import json
    import subprocess
    import sys
    from dataclasses import asdict

    from aura_skeleton.core.estado_operativo import Tarea

    tarea = Tarea(
        objetivo_id="cli-e2e", tarea_id="t-1", descripcion="demo", estado="abierta", responsable="qa", origen="ceo"
    )
    (tmp_path / "estado_operativo.jsonl").write_text(json.dumps(asdict(tarea), ensure_ascii=False) + "\n")

    res = subprocess.run(
        [sys.executable, "-m", "aura_skeleton", "--gobierno"],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "AURA_DATOS": str(tmp_path), "AURA_STACK_REAL": "0"},
    )
    salida = res.stdout + res.stderr
    assert res.returncode == 0, f"--gobierno fallo: {salida[-500:]}"
    assert "CENTRO DE GOBIERNO" in res.stdout
    assert "[AURORA]" in res.stdout, "el panel no uso el estado operativo real: sin el, todo queda INEXISTENTE"
    assert "1 tarea(s) accionables de 1" in res.stdout, "no reflejo la tarea sembrada en el log real"

    publicado = tmp_path / "CENTRO-DE-GOBIERNO.md"
    assert publicado.exists(), "el panel no quedo escrito en disco junto al resto del estado permanente"
    # Lo impreso y lo publicado deben ser la MISMA proyeccion (ADR-0023): dos superficies del mismo
    # dato, no dos fuentes que puedan divergir.
    assert res.stdout == publicado.read_text(encoding="utf-8") + "\n"


def test_gobierno_CUBRE_TODOS_los_objetivos_activos_no_solo_el_PRIMERO(tmp_path):
    """D-3 (auditoria independiente, 2026-08-04): un panel que muestra un objetivo y OCULTA otro sin
    avisar firma como [AURORA] una afirmacion falsa. Se reproduce el caso exacto que encontro el
    auditor: DOS objetivos activos, el alfabeticamente PRIMERO sin riesgos y el segundo con tareas
    bloqueadas -- `activos[0]` mostraria solo el tranquilo. Se llama a `_gobierno()` directamente
    (sin subproceso) porque necesita examinar el resultado con precision y una constante `sistema`
    minima (solo `estado_operativo` y `ruta_memoria`, lo unico que `_gobierno()` usa) basta para
    ejercitar el codigo REAL de `aura_skeleton.__main__`, no una reimplementacion de prueba."""
    from types import SimpleNamespace

    from aura_skeleton.__main__ import _gobierno
    from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea

    alm = AlmacenEstadoOperativo(str(tmp_path / "estado_operativo.jsonl"))
    alm.registrar(
        Tarea(
            objetivo_id="aaa-sin-riesgo",
            tarea_id="t-1",
            descripcion="ok",
            estado="abierta",
            responsable="qa",
            origen="ceo",
        )
    )
    alm.registrar(
        Tarea(
            objetivo_id="zzz-con-riesgo",
            tarea_id="t-1",
            descripcion="detenida",
            estado="bloqueada",
            responsable="programador",
            origen="ceo",
            bloqueos=["detenida: dry-run no viable"],
        )
    )

    sistema = SimpleNamespace(estado_operativo=alm, ruta_memoria=str(tmp_path / "memoria.json"))
    texto = _gobierno(sistema)

    assert "aaa-sin-riesgo" in texto, "el objetivo sin riesgos desaparecio del panel publicado"
    assert "zzz-con-riesgo" in texto, "el objetivo CON bloqueos desaparecio: el CEO no lo veria"
    assert "1 tarea(s) detenidas" in texto, "los riesgos reales del segundo objetivo no llegaron al panel"


def test_el_ejecutable_servir_arranca_el_latido_permanente(tmp_path):
    """PIEZA 1 (CABLEADO, D40): `--servir` debe arrancar `motor_ciclo.servir()` sobre el MISMO
    `componer()` que el resto -- no un bucle propio en el CLI. Se siembra una tarea para que exista un
    objetivo activo (igual que el e2e de `--gobierno`) y se comprueba que el PROCESO SIGUE VIVO
    sirviendolo (no termina solo), que es justo lo que no pasaria si el flag no arrancara el motor
    (ALERTA-005: una capacidad construida y probada que ningun camino real enciende)."""
    import json
    import subprocess
    import sys
    import time
    from dataclasses import asdict

    from aura_skeleton.core.estado_operativo import Tarea

    # `responsable` sin ejecutor registrado a proposito: el latido se despacha, no encuentra dueno y
    # bloquea la tarea (sin romper nada), lo que basta para demostrar que el bucle esta corriendo de
    # verdad sin depender de un adaptador pesado (QA/Programador) dentro del subproceso de la prueba.
    tarea = Tarea(
        objetivo_id="cli-servir",
        tarea_id="t-1",
        descripcion="demo",
        estado="abierta",
        responsable="sin-ejecutor-registrado",
        origen="ceo",
    )
    (tmp_path / "estado_operativo.jsonl").write_text(json.dumps(asdict(tarea), ensure_ascii=False) + "\n")

    proc = subprocess.Popen(
        [sys.executable, "-m", "aura_skeleton", "--servir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "AURA_DATOS": str(tmp_path), "AURA_STACK_REAL": "0"},
    )
    try:
        time.sleep(2)
        assert proc.poll() is None, "el proceso termino solo: --servir no dejo el latido permanente corriendo"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
