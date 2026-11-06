import pytest


@pytest.fixture(autouse=True)
def _sin_plano_de_control_real(monkeypatch):
    """La bateria NUNCA lee el ciclo autonomo real del equipo que la ejecuta.

    `componer()` cablea la fuente de estado autonomo cuando encuentra `entorno/control-plane`, que en
    este repositorio SIEMPRE esta. Sin esta fixture, las pruebas de conversacion leerian el
    `eventos.jsonl` de verdad y su resultado cambiaria solo cada media hora, cuando el `cron`
    despierta a AURORA: una prueba cuyo veredicto depende de la hora no prueba nada.

    Quien quiera ejercitar la superficie inyecta su propia fuente, que es ademas la unica forma de
    fijar los seis casos (ejecutando / esperando / sin trabajo / bloqueado / elevado / proximo ciclo)
    sin fabricar un entorno (D34).
    """
    monkeypatch.setenv("AURA_CONTROL_PLANE", "")


@pytest.fixture(autouse=True)
def _sin_red_de_nodos_real(monkeypatch):
    """La bateria NUNCA lee la red de nodos real (`~/.aura-red`) del equipo que la ejecuta.

    `componer()` cablea el vigia de nodos desde `AURA_RED`; sin esto, cada prueba de composicion leeria
    el `registro.json` de verdad y recibiria avisos segun el estado del NODO-01 de hoy. Declarado y vacio
    significa «no hay red de nodos». Quien quiera ejercitar los avisos apunta `AURA_RED` a su `tmp_path`.
    """
    monkeypatch.setenv("AURA_RED", "")


@pytest.fixture(autouse=True)
def _sin_dispositivos_reales(monkeypatch):
    """La bateria NUNCA habla con el hogar ni con las camaras reales del equipo que la ejecuta.

    `componer()` decide Home Assistant real y camaras RTSP por el ENTORNO, no por `usar_stack_real`. Medido
    2026-10-25: con `AURA_HA_URL`/`AURA_HA_TOKEN` exportados en el shell, una prueba de composicion abrio una
    conexion al hogar (y le habria enviado el token). Quien quiera ejercitarlos los fija con `monkeypatch`
    en su prueba, apuntando a 127.0.0.1 o a TEST-NET (`tests/unit/test_sin_dispositivos_reales.py`).
    """
    for variable in ("AURA_HA_URL", "AURA_HA_TOKEN", "AURA_CAMARA_RTSP", "AURA_CAMARA_AUDIO_RTSP"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture(autouse=True)
def _sin_datos_ni_stack_reales(monkeypatch, tmp_path_factory):
    """La bateria NUNCA cae en el directorio de datos real ni enciende el stack real por herencia del shell.

    `Configuracion()` toma `datos` de `AURA_DATOS` y, sin ella, de `~/.aura`; y `usar_stack_real` de
    `AURA_STACK_REAL`. Medido 2026-10-25: en este equipo `Configuracion()` dentro de la bateria valia
    `~/.aura` (los datos REALES), y un `AURA_STACK_REAL=1` exportado encendia Ollama/Whisper. Retirar
    `AURA_DATOS` no basta (el defecto ES el directorio real): se fija a un temporal propio de cada prueba.
    Quien necesite otro directorio u otro stack lo fija con `monkeypatch` en su prueba.
    """
    monkeypatch.setenv("AURA_DATOS", str(tmp_path_factory.mktemp("aura-datos-por-defecto")))
    monkeypatch.setenv("AURA_STACK_REAL", "")


@pytest.fixture(autouse=True)
def _sin_red_real_por_defecto(monkeypatch, tmp_path_factory):
    """El CLI de nodos (`--nodos`, `--receptor-nodos`) NUNCA resuelve el `~/.aura-red` real dentro de la bateria.

    `_sin_red_de_nodos_real` fija `AURA_RED=""`, que significa «sin red» para el vigia y, desde la correccion de
    `__main__._ruta_red` (2026-10-25), tambien para el CLI. Antes el CLI trataba la cadena vacia como ausencia y
    caia en `~/.aura-red`, con la credencial y la PKI REALES del receptor. Esta fixture se conserva como defensa
    en profundidad: desvia el valor por defecto que ve la bateria (AURA_RED ausente) a un temporal por prueba.
    Limite: un SUBPROCESO `python -m aura_skeleton` no hereda este parche; las pruebas que lo lanzan fijan
    `AURA_RED` explicito (`test_cli_nodos.py`, `test_nodo_e2e_nats.py`).
    """
    monkeypatch.setattr("aura_skeleton.__main__._RED_POR_DEFECTO", str(tmp_path_factory.mktemp("aura-red-por-defecto")))


@pytest.fixture(autouse=True)
def _anclas_del_log_en_un_temporal(tmp_path_factory, monkeypatch):
    """D-LOG-1 · Ninguna prueba escribe el ancla externa del log del control-plane en el estado real
    (`~/.local/state/aura/anclas`). El ancla vive fuera del directorio del log."""
    monkeypatch.setenv("AURA_ANCLA_DIR", str(tmp_path_factory.mktemp("anclas") / "anclas"))
