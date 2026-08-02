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
