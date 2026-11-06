"""Agente de nodo (DP-NODO-01 §4-§5): bucle de servicio, estado local y CLI. Sin red: todo se inyecta."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.contracts import Event
from aura_skeleton.core.capacidades import PerfilHardware
from aura_skeleton.core.nodos import subject_de, validar_latido
from aura_skeleton.nodo_agente import AgenteNodo, ConfigAgente, ErrorConfiguracion, cargar_config

NODO_ID = "ab" * 16
CLAVE = "contraseña-SECRETA-123"
_RAIZ = Path(__file__).resolve().parents[2]


# --- dobles ------------------------------------------------------------------------------------------------


class PublicadorFalso:
    def __init__(self, fallos: list[Exception | None] | None = None) -> None:
        self.eventos: list[Event] = []
        self.conectado = True
        self.cerrado = False
        self._fallos = list(fallos or [])

    async def publish(self, event: Event) -> None:
        if self._fallos:
            fallo = self._fallos.pop(0)
            if fallo is not None:
                raise fallo
        self.eventos.append(event)

    async def close(self) -> None:
        self.cerrado = True
        self.conectado = False


class DetectorFalso:
    def detectar_con_omisiones(self) -> tuple[PerfilHardware, tuple[str, ...]]:
        return PerfilHardware(recursos={"ram_mb": 986.0, "nucleos": 1.0}), ()


class Reloj:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def _config(datos: Path, **cambios: Any) -> ConfigAgente:
    base: dict[str, Any] = {
        "datos": str(datos),
        "nodo_id": NODO_ID,
        "servidores": ["tls://hc-1.local:4222"],
        "usuario": f"nodo-{NODO_ID}",
        "nombre": "nodo-prueba",
        "intervalo_s": 10.0,
    }
    base.update(cambios)
    return ConfigAgente(**base)


def _correr(
    datos: Path,
    ciclos: int,
    publicadores: list[PublicadorFalso | Exception] | None = None,
    **cfg: Any,
) -> tuple[AgenteNodo, list[float], list[PublicadorFalso]]:
    """Ejecuta el agente `ciclos` esperas y lo detiene. Devuelve (agente, esperas, publicadores creados)."""
    guion = list(publicadores) if publicadores is not None else [PublicadorFalso()]
    creados: list[PublicadorFalso] = []
    esperas: list[float] = []

    async def fabrica() -> PublicadorFalso:
        item = guion.pop(0) if len(guion) > 1 or isinstance(guion[0], Exception) else guion[0]
        if isinstance(item, Exception):
            raise item
        if item not in creados:
            creados.append(item)
        return item

    holder: list[AgenteNodo] = []

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if len(esperas) >= ciclos:
            holder[0].detener()

    agente = AgenteNodo(_config(datos, **cfg), fabrica, DetectorFalso(), Reloj(), dormir)
    holder.append(agente)
    asyncio.run(agente.ejecutar())
    return agente, esperas, creados


def _estado(datos: Path) -> dict[str, Any]:
    return json.loads((datos / "estado_local.json").read_text())


# --- conexión inicial acotada ------------------------------------------------------------------------------


async def _fabrica_colgada() -> PublicadorFalso:
    await asyncio.Event().wait()
    raise AssertionError("inalcanzable")


def test_conexion_inicial_colgada_vuelve_con_none_tras_el_tope_y_cuenta_como_fallo(tmp_path: Path) -> None:
    agente = AgenteNodo(_config(tmp_path), _fabrica_colgada, DetectorFalso(), Reloj(), tope_conexion_s=0.05)

    async def prueba() -> Any:
        return await asyncio.wait_for(agente._conectar(), timeout=2)

    assert asyncio.run(prueba()) is None
    agente._escribir_estado()
    estado = _estado(tmp_path)
    assert estado["conectado"] is False
    assert estado["ultimo_error"] == "TimeoutError"


def test_la_parada_interrumpe_una_conexion_inicial_colgada(tmp_path: Path) -> None:
    agente = AgenteNodo(_config(tmp_path), _fabrica_colgada, DetectorFalso(), Reloj(), tope_conexion_s=60)

    async def prueba() -> float:
        asyncio.get_running_loop().call_later(0.1, agente.detener)
        t0 = time.monotonic()
        await asyncio.wait_for(agente.ejecutar(), timeout=5)
        return time.monotonic() - t0

    assert asyncio.run(prueba()) < 1.0
    assert _estado(tmp_path)["ultimo_error"] is None, "una parada no es un error de conexión"


def test_la_parada_durante_la_conexion_devuelve_none_sin_registrar_error(tmp_path: Path) -> None:
    agente = AgenteNodo(_config(tmp_path), _fabrica_colgada, DetectorFalso(), Reloj(), tope_conexion_s=60)

    async def prueba() -> Any:
        agente.detener()
        return await asyncio.wait_for(agente._conectar(), timeout=2)

    assert asyncio.run(prueba()) is None
    assert agente._ultimo_error is None


# --- latidos -----------------------------------------------------------------------------------------------


def test_la_secuencia_es_estrictamente_monotona_desde_cero(tmp_path: Path) -> None:
    _, _, pubs = _correr(tmp_path, ciclos=4)
    secuencias = [e.payload["secuencia"] for e in pubs[0].eventos]
    assert secuencias == [0, 1, 2, 3]


def test_el_arranque_es_unico_por_instancia_y_estable_dentro_de_ella(tmp_path: Path) -> None:
    _, _, pubs_a = _correr(tmp_path, ciclos=2)
    _, _, pubs_b = _correr(tmp_path, ciclos=2, publicadores=[PublicadorFalso()])
    arranques_a = {e.payload["arranque"] for e in pubs_a[0].eventos}
    arranques_b = {e.payload["arranque"] for e in pubs_b[0].eventos}
    assert len(arranques_a) == 1 and len(arranques_b) == 1
    assert arranques_a != arranques_b
    assert re.fullmatch(r"[0-9a-f]{32}", next(iter(arranques_a)))


def test_el_latido_es_valido_y_viaja_por_el_subject_del_nodo(tmp_path: Path) -> None:
    _, _, pubs = _correr(tmp_path, ciclos=1, intervalo_s=5.0)
    evento = pubs[0].eventos[0]
    latido = validar_latido(evento.payload)
    assert evento.type == subject_de(NODO_ID)
    assert evento.user_id == "sistema"
    assert evento.trace_id
    assert latido.nodo_id == NODO_ID
    assert latido.nombre == "nodo-prueba"
    assert latido.intervalo_s == 5.0
    assert latido.recursos["ram_mb"] == 986.0


def test_espera_el_intervalo_configurado_entre_latidos(tmp_path: Path) -> None:
    _, esperas, _ = _correr(tmp_path, ciclos=3, intervalo_s=7.0)
    assert esperas == [7.0, 7.0, 7.0]


# --- conexión ----------------------------------------------------------------------------------------------


def test_conexion_inicial_fallida_reintenta_con_espera_creciente_acotada(tmp_path: Path) -> None:
    fallos: list[Any] = [ConnectionRefusedError("rechazada")] * 7
    _, esperas, _ = _correr(tmp_path, ciclos=7, publicadores=fallos)
    assert esperas == [2, 4, 8, 16, 30, 30, 30]


def test_sin_hc1_sigue_vivo_y_escribe_estado_desconectado(tmp_path: Path) -> None:
    fallos: list[Any] = [ConnectionRefusedError("rechazada")] * 2
    agente, _, _ = _correr(tmp_path, ciclos=2, publicadores=fallos)
    estado = _estado(tmp_path)
    assert estado["conectado"] is False
    assert estado["ultimo_error"] == "ConnectionRefusedError"
    assert estado["ultimo_envio_ok"] is None
    assert estado["nodo_id"] == NODO_ID
    assert agente.secuencia is None


def test_al_conectar_tras_fallos_publica_y_reinicia_la_espera(tmp_path: Path) -> None:
    pub = PublicadorFalso()
    guion: list[Any] = [OSError("no"), OSError("no"), pub]
    _, esperas, _ = _correr(tmp_path, ciclos=4, publicadores=guion, intervalo_s=10.0)
    assert esperas == [2, 4, 10.0, 10.0]
    assert [e.payload["secuencia"] for e in pub.eventos] == [0, 1]
    estado = _estado(tmp_path)  # tras el cierre limpio conectado=false; lo que persiste es el éxito del envío
    assert estado["ultimo_envio_ok"] is not None and estado["ultimo_error"] is None


def test_si_el_bus_esta_reconectando_no_publica_ni_consume_secuencia(tmp_path: Path) -> None:
    pub = PublicadorFalso()
    pub.conectado = False
    _correr(tmp_path, ciclos=2, publicadores=[pub])
    assert pub.eventos == []
    estado = _estado(tmp_path)
    assert estado["conectado"] is False
    assert estado["ultimo_error"] == "SinConexion"


# --- fallos de publicación ---------------------------------------------------------------------------------


def test_un_publish_que_falla_no_mata_al_agente_y_no_filtra_la_contrasena(tmp_path: Path) -> None:
    pub = PublicadorFalso([RuntimeError(f"fallo con {CLAVE}"), None])
    agente, _, _ = _correr(tmp_path, ciclos=2, publicadores=[pub])
    contenido = (tmp_path / "estado_local.json").read_text()
    assert CLAVE not in contenido
    # El segundo ciclo sí publicó: el agente siguió vivo y el error se limpió.
    assert [e.payload["secuencia"] for e in pub.eventos] == [1]
    assert agente.secuencia == 1


def test_el_error_de_publicacion_queda_registrado_por_tipo(tmp_path: Path) -> None:
    pub = PublicadorFalso([TimeoutError(f"detalle {CLAVE}")] * 5)
    _correr(tmp_path, ciclos=1, publicadores=[pub])
    estado = _estado(tmp_path)
    assert estado["ultimo_error"] == "TimeoutError"
    assert estado["ultimo_envio_ok"] is None
    assert CLAVE not in json.dumps(estado)


def test_ultimo_envio_ok_se_anota_con_el_reloj_inyectado(tmp_path: Path) -> None:
    _correr(tmp_path, ciclos=1)
    estado = _estado(tmp_path)
    assert isinstance(estado["ultimo_envio_ok"], float)
    assert estado["ultimo_error"] is None
    assert estado["ultimo_envio_ok"] <= estado["actualizado"]


# --- cierre y estado ---------------------------------------------------------------------------------------


def test_cierre_limpio_cierra_el_bus_y_marca_desconectado(tmp_path: Path) -> None:
    _, _, pubs = _correr(tmp_path, ciclos=2)
    assert pubs[0].cerrado is True
    assert _estado(tmp_path)["conectado"] is False


def test_estado_local_tiene_los_campos_del_contrato_y_permisos_0600(tmp_path: Path) -> None:
    _correr(tmp_path, ciclos=1)
    ruta = tmp_path / "estado_local.json"
    assert set(_estado(tmp_path)) == {
        "nodo_id",
        "nombre",
        "arranque",
        "secuencia",
        "conectado",
        "ultimo_envio_ok",
        "ultimo_error",
        "actualizado",
    }
    assert ruta.stat().st_mode & 0o777 == 0o600
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_la_memoria_de_observabilidad_no_crece_sin_limite(tmp_path: Path) -> None:
    obs._records.clear()
    _correr(tmp_path, ciclos=600)
    assert len(obs._records) <= 600  # sin acotar crecería con cada latido (log EVENT del bus + del agente)


# --- configuración -----------------------------------------------------------------------------------------


def _escribir_datos(datos: Path, modo: int = 0o600, **conf: Any) -> None:
    datos.mkdir(parents=True, exist_ok=True)
    cuerpo = {"servidores": ["tls://127.0.0.1:4222"], "usuario": "u", "nombre": "n1", "intervalo_s": 2}
    cuerpo.update(conf)
    (datos / "nodo.conf").write_text(json.dumps(cuerpo))
    cred = datos / "credencial"
    cred.write_text(CLAVE + "\n")
    cred.chmod(modo)
    (datos / "ca.crt").write_text("CA")


def test_cargar_config_valida_devuelve_los_campos(tmp_path: Path) -> None:
    _escribir_datos(tmp_path)
    cfg, password = cargar_config(str(tmp_path))
    assert cfg.servidores == ["tls://127.0.0.1:4222"]
    assert cfg.usuario == "u" and cfg.nombre == "n1" and cfg.intervalo_s == 2.0
    assert re.fullmatch(r"[0-9a-f]{32}", cfg.nodo_id)
    assert password == CLAVE
    assert CLAVE not in repr(cfg)


@pytest.mark.parametrize("modo", [0o644, 0o640, 0o604, 0o660])
def test_credencial_con_permisos_abiertos_se_rechaza(tmp_path: Path, modo: int) -> None:
    _escribir_datos(tmp_path, modo=modo)
    with pytest.raises(ErrorConfiguracion, match="permisos"):
        cargar_config(str(tmp_path))


def test_credencial_vacia_se_rechaza(tmp_path: Path) -> None:
    _escribir_datos(tmp_path)
    (tmp_path / "credencial").write_text("  \n")
    with pytest.raises(ErrorConfiguracion, match="vacía"):
        cargar_config(str(tmp_path))


@pytest.mark.parametrize("fichero", ["nodo.conf", "credencial", "ca.crt"])
def test_falta_de_ficheros_se_rechaza(tmp_path: Path, fichero: str) -> None:
    _escribir_datos(tmp_path)
    (tmp_path / fichero).unlink()
    with pytest.raises(ErrorConfiguracion, match=fichero):
        cargar_config(str(tmp_path))


@pytest.mark.parametrize(
    "conf",
    [
        {"servidores": []},
        {"servidores": "tls://x:1"},
        {"servidores": [1]},
        {"usuario": ""},
        {"nombre": ""},
        {"nombre": "x" * 65},
        {"intervalo_s": 0.5},
        {"intervalo_s": 4000},
        {"intervalo_s": True},
        {"intervalo_s": "10"},
    ],
)
def test_nodo_conf_con_valores_invalidos_se_rechaza(tmp_path: Path, conf: dict[str, Any]) -> None:
    _escribir_datos(tmp_path, **conf)
    with pytest.raises(ErrorConfiguracion):
        cargar_config(str(tmp_path))


def test_nodo_conf_json_invalido_se_rechaza(tmp_path: Path) -> None:
    _escribir_datos(tmp_path)
    (tmp_path / "nodo.conf").write_text("{no es json")
    with pytest.raises(ErrorConfiguracion, match="JSON"):
        cargar_config(str(tmp_path))


# --- CLI (subprocess real) ---------------------------------------------------------------------------------


def _cli(datos: Path, *args: str, espera: str = "0") -> subprocess.CompletedProcess[str]:
    entorno = {**os.environ, "AURA_NODO_DATOS": str(datos), "AURA_NODO_ESPERA_ERROR_S": espera}
    return subprocess.run(
        [sys.executable, "-m", "aura_skeleton.nodo_agente", *args],
        cwd=_RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_identidad_imprime_solo_el_id_y_es_estable(tmp_path: Path) -> None:
    primera = _cli(tmp_path, "--identidad")
    segunda = _cli(tmp_path, "--identidad")
    assert primera.returncode == 0 and segunda.returncode == 0
    assert re.fullmatch(r"[0-9a-f]{32}\n", primera.stdout)
    assert primera.stdout == segunda.stdout


def test_informe_produce_un_latido_valido_sin_nodo_conf(tmp_path: Path) -> None:
    r = _cli(tmp_path, "--informe")
    assert r.returncode == 0, r.stderr
    latido = validar_latido(json.loads(r.stdout))
    assert latido.nombre == "sin-configurar"
    assert "ram_mb" in latido.recursos


def test_informe_usa_el_nombre_de_nodo_conf(tmp_path: Path) -> None:
    _escribir_datos(tmp_path, nombre="cocina")
    r = _cli(tmp_path, "--informe")
    assert r.returncode == 0, r.stderr
    assert validar_latido(json.loads(r.stdout)).nombre == "cocina"


def test_estado_imprime_el_fichero_de_estado_local(tmp_path: Path) -> None:
    _correr(tmp_path, ciclos=1)
    r = _cli(tmp_path, "--estado")
    assert r.returncode == 0
    assert json.loads(r.stdout) == _estado(tmp_path)


def test_estado_sin_fichero_falla_con_mensaje(tmp_path: Path) -> None:
    r = _cli(tmp_path, "--estado")
    assert r.returncode == 1
    assert "Traceback" not in r.stderr


def test_servicio_con_credencial_abierta_sale_con_2_sin_traza_ni_secreto(tmp_path: Path) -> None:
    _escribir_datos(tmp_path, modo=0o644)
    r = _cli(tmp_path)
    assert r.returncode == 2
    assert "Traceback" not in r.stderr
    assert "permisos" in r.stderr
    assert CLAVE not in r.stdout + r.stderr


def test_servicio_sin_nodo_conf_sale_con_2(tmp_path: Path) -> None:
    r = _cli(tmp_path)
    assert r.returncode == 2
    assert "nodo.conf" in r.stderr
    assert "Traceback" not in r.stderr


def test_el_servicio_espera_antes_de_salir_con_error(tmp_path: Path) -> None:
    import time

    inicio = time.monotonic()
    r = _cli(tmp_path, espera="1.5")
    assert r.returncode == 2
    assert time.monotonic() - inicio >= 1.5


def test_sigterm_cierra_limpio_con_codigo_0_aunque_hc1_no_exista(tmp_path: Path) -> None:
    import signal
    import socket
    import time

    with socket.socket() as s:  # puerto cerrado en 127.0.0.1: la conexión inicial falla
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    _escribir_datos(tmp_path, servidores=[f"tls://127.0.0.1:{puerto}"], intervalo_s=1)
    entorno = {**os.environ, "AURA_NODO_DATOS": str(tmp_path)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "aura_skeleton.nodo_agente"],
        cwd=_RAIZ,
        env=entorno,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        limite = time.monotonic() + 20
        while time.monotonic() < limite and not (tmp_path / "estado_local.json").exists():
            time.sleep(0.1)
        assert (tmp_path / "estado_local.json").exists(), "el agente debe escribir estado aunque no haya HC-1"
        assert proc.poll() is None, "el agente no debe morir sin HC-1"
        proc.send_signal(signal.SIGTERM)
        salida, error = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
    assert proc.returncode == 0, error
    assert _estado(tmp_path)["conectado"] is False
    assert CLAVE not in salida + error


def test_la_fabrica_nats_exige_certificado_contra_la_ca_privada_y_pasa_credenciales(tmp_path, monkeypatch):
    """TLS del agente: CERT_REQUIRED con la CA privada del nodo (la IP de HC-1 cambia: sin hostname, no sin cert)."""
    import shutil
    import ssl

    from aura_skeleton import nodo_agente
    from aura_skeleton.bus_nats import NatsEventBus

    if shutil.which("openssl") is None:
        pytest.skip("openssl no disponible (CA de la prueba)")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
         "-keyout", str(tmp_path / "ca.key"), "-out", str(tmp_path / "ca.crt"), "-days", "1", "-subj", "/CN=ca-agente"],
        check=True, capture_output=True,
    )  # fmt: skip
    capturado: dict[str, Any] = {}

    async def falso_connect(url: Any, **opciones: Any) -> str:
        capturado["url"] = url
        capturado.update(opciones)
        return "bus"

    monkeypatch.setattr(NatsEventBus, "connect", falso_connect)
    fabrica = nodo_agente._fabrica_nats(_config(tmp_path), CLAVE, resolutor=lambda _: None)
    assert asyncio.run(fabrica()) == "bus"
    assert capturado["user"] == f"nodo-{NODO_ID}" and capturado["password"] == CLAVE
    ctx = capturado["tls"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.verify_flags & ssl.VERIFY_X509_STRICT, "HC-1 (3.12) y el nodo (3.13) deben verificar igual de estricto"
    assert [c["subject"][0][0][1] for c in ctx.get_ca_certs()] == ["ca-agente"]


def test_la_fabrica_nats_acota_el_ruido_de_nats_py_con_un_error_cb_que_solo_registra_el_tipo(tmp_path, monkeypatch):
    from aura_skeleton import nodo_agente
    from aura_skeleton.bus_nats import NatsEventBus

    capturado: dict[str, Any] = {}

    async def falso_connect(url: Any, **opciones: Any) -> str:
        capturado.update(opciones)
        return "bus"

    monkeypatch.setattr(NatsEventBus, "connect", falso_connect)
    (tmp_path / "ca.crt").write_text("")
    import ssl

    monkeypatch.setattr(ssl, "create_default_context", lambda **_: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    asyncio.run(nodo_agente._fabrica_nats(_config(tmp_path), CLAVE, resolutor=lambda _: None)())
    assert capturado["allow_reconnect"] is True and capturado["max_reconnect_attempts"] == -1
    registros: list[tuple[str, str]] = []
    monkeypatch.setattr(obs, "log", lambda nivel, modulo, msg, *a, **k: registros.append((nivel, msg)))
    asyncio.run(capturado["error_cb"](ConnectionRefusedError(f"secreto {CLAVE}")))
    assert registros == [("WARN", "nats: ConnectionRefusedError")]


def test_acotar_registros_recorta_el_log_global_y_conserva_los_ultimos() -> None:
    from aura_skeleton import nodo_agente

    original = list(obs._records)
    try:
        obs._records[:] = list(range(nodo_agente._REGISTROS_MAX + 50))
        nodo_agente._acotar_registros()
        assert len(obs._records) == nodo_agente._REGISTROS_TRAS_RECORTE
        assert obs._records[-1] == nodo_agente._REGISTROS_MAX + 49
        obs._records[:] = list(range(nodo_agente._REGISTROS_MAX))  # en el tope exacto no se toca
        nodo_agente._acotar_registros()
        assert len(obs._records) == nodo_agente._REGISTROS_MAX
    finally:
        obs._records[:] = original


# --- mDNS: la IP es configuración, nunca identidad (DP §4.5) ------------------------------------------------


def _urls_que_recibe_la_fabrica(tmp_path, monkeypatch, servidores, resolutor):
    from aura_skeleton import nodo_agente
    from aura_skeleton.bus_nats import NatsEventBus

    capturado: list[Any] = []

    async def falso_connect(url: Any, **opciones: Any) -> str:
        capturado.append(url)
        return "bus"

    monkeypatch.setattr(NatsEventBus, "connect", falso_connect)
    (tmp_path / "ca.crt").write_text("")
    import ssl

    monkeypatch.setattr(ssl, "create_default_context", lambda **_: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    config = _config(tmp_path, servidores=servidores)
    fabrica = nodo_agente._fabrica_nats(config, CLAVE, resolutor=resolutor)
    asyncio.run(fabrica())
    return capturado[0]


def test_la_fabrica_recibe_la_url_con_la_ip_resuelta_por_mdns(tmp_path, monkeypatch):
    llamados: list[str] = []

    def resolutor(nombre: str) -> str | None:
        llamados.append(nombre)
        return "192.168.20.202"

    url = _urls_que_recibe_la_fabrica(
        tmp_path, monkeypatch, ["tls://hc-1.local:4222", "tls://192.168.20.38:4222"], resolutor
    )
    assert url == ["tls://192.168.20.202:4222", "tls://192.168.20.38:4222"]
    assert llamados == ["hc-1.local"]


def test_si_mdns_no_resuelve_la_fabrica_recibe_la_url_original(tmp_path, monkeypatch):
    url = _urls_que_recibe_la_fabrica(
        tmp_path, monkeypatch, ["tls://hc-1.local:4222", "tls://192.168.20.38:4222"], lambda nombre: None
    )
    assert url == ["tls://hc-1.local:4222", "tls://192.168.20.38:4222"]


def test_un_servidor_que_no_es_local_no_se_toca_ni_se_consulta(tmp_path, monkeypatch):
    llamados: list[str] = []
    url = _urls_que_recibe_la_fabrica(
        tmp_path,
        monkeypatch,
        ["tls://nats.example.com:4222", "tls://10.0.0.5:4222"],
        lambda nombre: llamados.append(nombre) or "1.2.3.4",
    )
    assert url == ["tls://nats.example.com:4222", "tls://10.0.0.5:4222"]
    assert llamados == []


def test_la_traduccion_registra_la_ip_resuelta_en_info(tmp_path, monkeypatch):
    registros: list[tuple[str, str]] = []
    monkeypatch.setattr(obs, "log", lambda nivel, modulo, msg, *a, **k: registros.append((nivel, msg)))
    _urls_que_recibe_la_fabrica(tmp_path, monkeypatch, ["tls://hc-1.local:4222"], lambda nombre: "192.168.20.202")
    assert any(n == "INFO" and "192.168.20.202" in m for n, m in registros)


def test_un_resolutor_que_lanza_no_impide_conectar_con_la_url_original(tmp_path, monkeypatch):
    def roto(nombre: str) -> str | None:
        raise OSError("sin red")

    url = _urls_que_recibe_la_fabrica(tmp_path, monkeypatch, ["tls://hc-1.local:4222"], roto)
    assert url == ["tls://hc-1.local:4222"]
