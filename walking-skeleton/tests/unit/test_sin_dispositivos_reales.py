"""La bateria NUNCA hereda los dispositivos reales del shell que la ejecuta (2026-10-25).

Defecto medido `[EJEC]`: con `AURA_HA_URL`/`AURA_HA_TOKEN` exportados en el shell, una prueba de composicion
(`componer` con `usar_stack_real=False`) abrio 1 conexion a un servidor local que hacia de Home Assistant:
`composicion._hogar` lee el entorno, no `usar_stack_real`. Con el entorno real, la bateria habria hablado con
el hogar de verdad y le habria enviado el token. Lo mismo para las camaras (`AURA_CAMARA_*_RTSP`).

La guardia es la fixture autouse `_sin_dispositivos_reales` de `tests/conftest.py`. Esta prueba la ejercita
en un pytest HIJO con un entorno hostil: sin la fixture, el hijo falla y esta prueba tambien.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

VARIABLES_DE_DISPOSITIVO = ("AURA_HA_URL", "AURA_HA_TOKEN", "AURA_CAMARA_RTSP", "AURA_CAMARA_AUDIO_RTSP")


def test_la_bateria_no_hereda_variables_de_dispositivos_reales():
    heredadas = [v for v in VARIABLES_DE_DISPOSITIVO if v in os.environ]
    assert heredadas == [], f"variables de dispositivo real visibles dentro de la bateria: {heredadas}"


#: El directorio «real» que el shell hostil exporta como AURA_DATOS. Solo el pytest hijo lo recibe.
CENTINELA = "AURA_PRUEBA_DATOS_HEREDADOS"


def test_la_configuracion_por_defecto_no_hereda_ni_datos_ni_stack_reales():
    """`Configuracion()` sin argumentos es la ruta por la que una prueba caeria en los datos y el stack reales.

    Se comprueba ANTES de componer: si la guardia faltara, componer encenderia el stack real (Ollama,
    Whisper) y escribiria en el directorio heredado. Despues se compone de verdad: el efecto (audit log)
    tiene que caer en el directorio temporal de la guardia, nunca en el heredado.
    """
    from aura_skeleton import observability as obs
    from aura_skeleton.composicion import Configuracion, componer

    config = Configuracion()
    heredado = os.environ.get(CENTINELA)
    assert config.usar_stack_real is False, "un AURA_STACK_REAL=1 del shell enciende el stack real en la bateria"
    assert heredado is None or os.path.realpath(config.datos) != os.path.realpath(heredado), config.datos
    assert not os.path.realpath(config.datos).startswith(os.path.realpath(os.path.expanduser("~/.aura"))), config.datos
    try:
        componer(config)
    finally:
        obs.reset_audit()
    assert os.path.exists(os.path.join(config.datos, "audit.jsonl")), "control: componer escribe en `datos`"


def _hijo_con_entorno_hostil(extra: dict[str, str], *pruebas: str) -> subprocess.CompletedProcess:
    raiz = pathlib.Path(__file__).resolve().parents[2]
    yo = pathlib.Path(__file__).resolve()
    return subprocess.run(  # noqa: S603 - argv fijo: el interprete actual y pruebas de este mismo fichero
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *(f"{yo}::{p}" for p in pruebas)],
        cwd=raiz,
        env={**os.environ, **extra},
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_control_con_un_entorno_hostil_la_guardia_las_retira():
    """Control: el hijo arranca CON las variables puestas; solo la fixture puede retirarlas."""
    hijo = _hijo_con_entorno_hostil(
        {
            "AURA_HA_URL": "http://127.0.0.1:1",
            "AURA_HA_TOKEN": "token-ficticio-de-prueba",
            "AURA_CAMARA_RTSP": "rtsp://192.0.2.1/x",
            "AURA_CAMARA_AUDIO_RTSP": "rtsp://192.0.2.1/a",
        },
        "test_la_bateria_no_hereda_variables_de_dispositivos_reales",
    )
    assert hijo.returncode == 0, hijo.stdout[-2000:]


def test_control_un_shell_con_datos_y_stack_reales_no_llega_a_la_bateria(tmp_path):
    """Control: el hijo arranca con AURA_DATOS y AURA_STACK_REAL=1 del «usuario»; el directorio sigue intacto."""
    heredado = tmp_path / "datos-reales-del-shell"
    heredado.mkdir()
    hijo = _hijo_con_entorno_hostil(
        {"AURA_DATOS": str(heredado), "AURA_STACK_REAL": "1", CENTINELA: str(heredado)},
        "test_la_configuracion_por_defecto_no_hereda_ni_datos_ni_stack_reales",
    )
    assert hijo.returncode == 0, hijo.stdout[-2000:]
    assert list(heredado.iterdir()) == [], "la bateria escribio en el AURA_DATOS heredado del shell"
