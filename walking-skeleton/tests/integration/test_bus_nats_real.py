"""NatsEventBus contra un `nats-server` REAL (sin mocks): round-trip, autenticación y permisos por subject.

Arranca el servidor en un puerto libre de 127.0.0.1 con un fichero de configuración temporal. Si el binario no
existe (ni en el PATH ni en ~/.local/bin) se omite con motivo. El servidor se termina SIEMPRE en el teardown
(Popen + terminate + wait; sin pkill).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path

import nats
import nats.errors
import pytest

from aura_skeleton.adapters.receptor_nodos import ReceptorNodos, leer_registro
from aura_skeleton.bus_nats import NatsEventBus
from aura_skeleton.contracts import Event
from aura_skeleton.core.nodos import construir_latido, subject_de

_CLAVE_PUB = "clave-pub-AAA"
_CLAVE_SUB = "clave-sub"
_ID_A = "a" * 32
_ID_B = "b" * 32
_ESPERA_S = 2.0  # margen para que llegue (o NO llegue) un mensaje en localhost


def _binario() -> str | None:
    return shutil.which("nats-server") or next(
        (str(p) for p in [Path.home() / ".local" / "bin" / "nats-server"] if p.is_file()), None
    )


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _esperar_puerto(puerto: int, proc: subprocess.Popen) -> None:
    limite = time.monotonic() + 10
    while time.monotonic() < limite:
        if proc.poll() is not None:
            raise RuntimeError(f"nats-server terminó al arrancar (código {proc.returncode})")
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("nats-server no abrió el puerto a tiempo")


@pytest.fixture(scope="module")
def servidor(tmp_path_factory):
    binario = _binario()
    if binario is None:
        pytest.skip("nats-server no está en el PATH ni en ~/.local/bin")
    puerto = _puerto_libre()
    conf = tmp_path_factory.mktemp("nats") / "nats.conf"
    conf.write_text(
        f"""
listen: 127.0.0.1:{puerto}
authorization {{
  users = [
    {{ user: "pub_aaa", password: "{_CLAVE_PUB}",
       permissions: {{ publish: {{ allow: ["nodo.latido.AAA"] }}, subscribe: {{ deny: [">"] }} }} }}
    {{ user: "pub_a32", password: "{_CLAVE_PUB}",
       permissions: {{ publish: {{ allow: ["nodo.latido.{_ID_A}"] }}, subscribe: {{ deny: [">"] }} }} }}
    {{ user: "receptor", password: "{_CLAVE_SUB}",
       permissions: {{ publish: {{ deny: [">"] }}, subscribe: {{ allow: ["nodo.>"] }} }} }}
  ]
}}
"""
    )
    proc = subprocess.Popen([binario, "-c", str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _esperar_puerto(puerto, proc)
        yield f"nats://127.0.0.1:{puerto}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _evento(tipo: str) -> Event:
    return Event(
        type=tipo,
        trace_id="traza-1",
        user_id="usuario-1",
        payload={"a": 1, "b": ["x", {"c": None}], "ñ": "tildé ✓"},
        event_id="evento-1",
        causation_id="causa-1",
        schema_version="2.3.4",
        ts=1234.5,
    )


async def _con_suscriptor(url: str, tipo: str):
    """Abre un suscriptor (usuario `receptor`) y devuelve (bus, cola de eventos recibidos)."""
    recibidos: asyncio.Queue[Event] = asyncio.Queue()

    async def manejador(ev: Event) -> None:
        await recibidos.put(ev)

    bus = await NatsEventBus.connect(url, user="receptor", password=_CLAVE_SUB)
    bus.subscribe(tipo, manejador)
    await bus.start()
    return bus, recibidos


async def test_publish_subscribe_round_trip_con_todos_los_campos(servidor):
    sub, recibidos = await _con_suscriptor(servidor, "nodo.latido.AAA")
    pub = await NatsEventBus.connect(servidor, user="pub_aaa", password=_CLAVE_PUB)
    try:
        enviado = _evento("nodo.latido.AAA")
        await pub.publish(enviado)
        recibido = await asyncio.wait_for(recibidos.get(), _ESPERA_S)
        assert recibido == enviado  # los 8 campos, incluido el payload anidado y Unicode
    finally:
        await pub.close()
        await sub.close()


async def test_connect_con_url_posicional_y_sin_credenciales_es_rechazado(servidor):
    # `connect(url)` (como run_demo_nats.py) sigue aceptando la URL posicional; el servidor exige credenciales, sin ellas
    # debe FALLAR (control: si ignorara la autenticación, conectaría).
    with pytest.raises((nats.errors.Error, OSError)):
        await NatsEventBus.connect(servidor, allow_reconnect=False, connect_timeout=1)


async def test_autenticacion_correcta_conecta(servidor):
    bus = await NatsEventBus.connect(servidor, user="pub_aaa", password=_CLAVE_PUB)
    try:
        assert bus.conectado is True
    finally:
        await bus.close()


async def test_contrasena_erronea_falla(servidor):
    with pytest.raises((nats.errors.Error, OSError)):
        await NatsEventBus.connect(
            servidor, user="pub_aaa", password="incorrecta", allow_reconnect=False, connect_timeout=1
        )


async def test_acepta_lista_de_servidores_y_salta_al_que_responde(servidor):
    muerto = f"nats://127.0.0.1:{_puerto_libre()}"  # nadie escucha: el primero falla, el segundo responde
    bus = await NatsEventBus.connect([muerto, servidor], user="pub_aaa", password=_CLAVE_PUB, connect_timeout=1)
    try:
        assert bus.conectado is True
    finally:
        await bus.close()


async def test_permiso_de_publicacion_impide_suplantar_otro_subject(servidor):
    sub, recibidos = await _con_suscriptor(servidor, "nodo.latido.>")
    errores: list[Exception] = []

    async def error_cb(e: Exception) -> None:
        errores.append(e)

    pub = await NatsEventBus.connect(servidor, user="pub_aaa", password=_CLAVE_PUB, error_cb=error_cb)
    try:
        await pub.publish(_evento("nodo.latido.BBB"))  # NO permitido para pub_aaa
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(recibidos.get(), _ESPERA_S)
        assert any("ermission" in str(e) for e in errores)  # el servidor lo rechazó explícitamente
        # Control: el subject permitido SÍ llega por el mismo camino, así que la ausencia anterior es el permiso.
        await pub.publish(_evento("nodo.latido.AAA"))
        permitido = await asyncio.wait_for(recibidos.get(), _ESPERA_S)
        assert permitido.type == "nodo.latido.AAA"
        assert recibidos.empty()
    finally:
        await pub.close()
        await sub.close()


async def test_conectado_es_false_tras_cerrar(servidor):
    bus = await NatsEventBus.connect(servidor, user="pub_aaa", password=_CLAVE_PUB)
    assert bus.conectado is True
    await bus.close()
    assert bus.conectado is False


def _cuerpo_de_b() -> bytes:
    """Cuerpo JSON que un nodo A malicioso construye diciendo ser B (type y nodo_id de B)."""
    payload = construir_latido(_ID_B, "falso", 0, "1" * 32, 10.0, {"ram_mb": 1.0, "nucleos": 1.0}, [], "1.0")
    return json.dumps(
        {"type": subject_de(_ID_B), "trace_id": "t", "user_id": "nodo", "payload": payload, "event_id": "e-1"}
    ).encode()


async def _publicar_crudo(url: str, subject: str, cuerpo: bytes) -> None:
    nc = await nats.connect(url, user="pub_a32", password=_CLAVE_PUB)
    try:
        await nc.publish(subject, cuerpo)
        await nc.flush()
    finally:
        await nc.close()


async def test_el_type_recibido_es_el_subject_y_no_el_del_cuerpo(servidor):
    sub, recibidos = await _con_suscriptor(servidor, "nodo.latido.>")
    try:
        await _publicar_crudo(servidor, subject_de(_ID_A), _cuerpo_de_b())
        ev = await asyncio.wait_for(recibidos.get(), _ESPERA_S)
        assert ev.type == subject_de(_ID_A)  # la autoridad es el subject (ACL), no el cuerpo
    finally:
        await sub.close()


async def test_suplantacion_por_cuerpo_termina_rechazada_y_b_no_se_registra(servidor, tmp_path):
    receptor = ReceptorNodos(str(tmp_path))
    resultados: list[str] = []

    async def manejador(ev: Event) -> None:
        resultados.append(await receptor.manejar(ev))

    sub = await NatsEventBus.connect(servidor, user="receptor", password=_CLAVE_SUB)
    sub.subscribe("nodo.latido.>", manejador)
    await sub.start()
    try:
        await _publicar_crudo(servidor, subject_de(_ID_A), _cuerpo_de_b())
        limite = time.monotonic() + _ESPERA_S
        while not resultados and time.monotonic() < limite:
            await asyncio.sleep(0.05)
        assert resultados == ["rechazado"]
        assert _ID_B not in leer_registro(str(tmp_path))["nodos"]
        assert receptor.registro.obtener(_ID_B) is None
    finally:
        await sub.close()
