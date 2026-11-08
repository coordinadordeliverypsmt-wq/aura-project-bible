"""E2E REAL del nodo (DP-NODO-01 §6): PKI + nats-server + receptor + agente, todo como procesos, sin mocks.

Demuestra: alta y registro, ONLINE, OFFLINE al matar el agente, reinicio con la MISMA identidad (`reinicios` >= 1)
y reconexión del agente (que NO se reinicia) tras parar y relanzar nats-server en el mismo puerto.

Todo en 127.0.0.1 y puerto libre; HOME apunta a un directorio temporal (nunca se tocan ~/.aura*). Los procesos
se terminan SIEMPRE en el teardown (Popen + terminate + wait; sin pkill).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import site
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_WS = Path(__file__).resolve().parents[2]
_RED_HC1 = _WS.parent / "entorno" / "nodos" / "red_hc1.py"
_INTERVALO_S = 1
_ESPERA_MAX_S = 45.0


def _binario() -> str | None:
    return shutil.which("nats-server") or next(
        (str(p) for p in [Path.home() / ".local" / "bin" / "nats-server"] if p.is_file()), None
    )


pytestmark = [
    pytest.mark.skipif(_binario() is None, reason="nats-server no está en el PATH ni en ~/.local/bin"),
    pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible (PKI de la prueba)"),
]


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Escenario:
    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.red = raiz / "red"
        self.datos = raiz / "nodo"
        self.puerto = _puerto_libre()
        self.entorno = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(raiz / "home"),
            "PYTHONUSERBASE": site.getuserbase(),  # HOME temporal no debe ocultar nats-py instalado en el usuario
            "AURA_RED": str(self.red),
            "AURA_RED_PUERTO": str(self.puerto),
            "AURA_RED_URL": f"tls://127.0.0.1:{self.puerto}",
            "AURA_NODO_DATOS": str(self.datos),
        }
        (raiz / "home").mkdir()
        self.procesos: list[subprocess.Popen[bytes]] = []
        self._ficheros: list[object] = []

    def ejecutar(self, *args: str) -> str:
        r = subprocess.run(
            [sys.executable, *args], cwd=_WS, env=self.entorno, capture_output=True, text=True, timeout=60, check=False
        )
        assert r.returncode == 0, f"{args}: {r.stderr}"
        return r.stdout

    def lanzar(self, nombre: str, *cmd: str) -> subprocess.Popen[bytes]:
        log = open(self.raiz / f"{nombre}.log", "ab")  # noqa: SIM115 - se cierra en `terminar`
        self._ficheros.append(log)
        proc = subprocess.Popen(cmd, cwd=_WS, env=self.entorno, stdout=log, stderr=subprocess.STDOUT)
        self.procesos.append(proc)
        return proc

    def lanzar_nats(self) -> subprocess.Popen[bytes]:
        binario = _binario()
        assert binario is not None
        proc = self.lanzar("nats", binario, "-c", str(self.red / "nats" / "nats.conf"))
        self._esperar_puerto(proc)
        return proc

    def lanzar_agente(self) -> subprocess.Popen[bytes]:
        return self.lanzar("agente", sys.executable, "-m", "aura_skeleton.nodo_agente")

    def _esperar_puerto(self, proc: subprocess.Popen[bytes]) -> None:
        limite = time.monotonic() + 15
        while time.monotonic() < limite:
            assert proc.poll() is None, "nats-server terminó al arrancar"
            try:
                with socket.create_connection(("127.0.0.1", self.puerto), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise AssertionError("nats-server no abrió el puerto")

    def informe(self) -> str:
        return self.ejecutar("-m", "aura_skeleton", "--nodos")

    def esperar(self, condicion: Callable[[str], bool], motivo: str) -> str:
        limite = time.monotonic() + _ESPERA_MAX_S
        ultimo = ""
        while time.monotonic() < limite:
            ultimo = self.informe()
            if condicion(ultimo):
                return ultimo
            time.sleep(0.5)
        raise AssertionError(f"no se cumplió: {motivo}\n--- último informe ---\n{ultimo}")

    def terminar(self) -> None:
        for proc in reversed(self.procesos):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        for f in self._ficheros:
            f.close()  # type: ignore[attr-defined]


def _reinicios(informe: str) -> int:
    m = re.search(r"reinicios: (\d+)", informe)
    assert m, informe
    return int(m.group(1))


def _linea_estado(informe: str, estado: str) -> bool:
    return re.search(rf"\[[0-9a-f]{{8}}…\]\s+{estado}\s", informe) is not None


@pytest.fixture
def escenario(tmp_path: Path) -> Iterator[Escenario]:
    esc = Escenario(tmp_path)
    try:
        esc.ejecutar(str(_RED_HC1), "preparar")
        nodo_id = esc.ejecutar("-m", "aura_skeleton.nodo_agente", "--identidad").strip()
        credencial = json.loads(esc.ejecutar(str(_RED_HC1), "alta", nodo_id))
        # Solo en la prueba: el nats.conf de producción escucha en 0.0.0.0; aquí NUNCA fuera de loopback.
        conf = esc.red / "nats" / "nats.conf"
        conf.write_text(conf.read_text().replace("0.0.0.0", "127.0.0.1"))
        esc.datos.mkdir(exist_ok=True)
        (esc.datos / "nodo.conf").write_text(
            json.dumps(
                {
                    "servidores": [f"tls://127.0.0.1:{esc.puerto}"],
                    "usuario": credencial["usuario"],
                    "nombre": "nodo-e2e",
                    "intervalo_s": _INTERVALO_S,
                }
            )
        )
        cred = esc.datos / "credencial"
        cred.write_text(credencial["password"])
        cred.chmod(0o600)
        shutil.copyfile(esc.red / "pki" / "ca.crt", esc.datos / "ca.crt")
        esc.nodo_id = nodo_id  # type: ignore[attr-defined]
        yield esc
    finally:
        esc.terminar()


def test_ciclo_de_vida_del_nodo_online_offline_reinicio_y_reconexion(escenario: Escenario) -> None:
    esc = escenario
    nodo_id: str = esc.nodo_id  # type: ignore[attr-defined]
    servidor = esc.lanzar_nats()
    esc.lanzar("receptor", sys.executable, "-m", "aura_skeleton", "--receptor-nodos")
    agente = esc.lanzar_agente()

    # 1) El nodo se registra y aparece ONLINE.
    informe = esc.esperar(lambda t: _linea_estado(t, "ONLINE"), "el nodo aparece ONLINE")
    assert "nodo-e2e" in informe and nodo_id[:8] in informe
    assert _reinicios(informe) == 0

    # 2) Se mata el agente: tras >3 intervalos el estado es OFFLINE.
    agente.terminate()
    assert agente.wait(timeout=15) == 0, "SIGTERM debe cerrar limpio con código 0"
    esc.esperar(lambda t: _linea_estado(t, "OFFLINE"), "el nodo pasa a OFFLINE")

    # 3) Se relanza: vuelve ONLINE con la MISMA identidad y reinicios >= 1.
    agente = esc.lanzar_agente()
    informe = esc.esperar(lambda t: _linea_estado(t, "ONLINE") and _reinicios(t) >= 1, "ONLINE tras reinicio")
    assert nodo_id[:8] in informe
    assert esc.ejecutar("-m", "aura_skeleton.nodo_agente", "--identidad").strip() == nodo_id
    reinicios_antes = _reinicios(informe)

    # 4) HC-1 (nats-server) se cae y vuelve en el mismo puerto: el agente NO se reinicia y se reconecta.
    servidor.terminate()
    servidor.wait(timeout=15)
    esc.esperar(lambda t: _linea_estado(t, "OFFLINE"), "el nodo pasa a OFFLINE al caer nats-server")
    assert agente.poll() is None, "el agente no debe morir sin HC-1"
    estado = json.loads((esc.datos / "estado_local.json").read_text())
    assert estado["nodo_id"] == nodo_id
    esc.lanzar_nats()
    informe = esc.esperar(lambda t: _linea_estado(t, "ONLINE"), "el nodo vuelve ONLINE tras la reconexión")
    assert agente.poll() is None
    assert _reinicios(informe) == reinicios_antes, "no hubo reinicio del agente: solo reconexión"
    assert json.loads((esc.datos / "estado_local.json").read_text())["conectado"] is True


def _leer_estado(esc: Escenario) -> dict | None:
    try:
        return json.loads((esc.datos / "estado_local.json").read_text())  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None


def _esperar_estado(esc: Escenario, condicion: Callable[[dict], bool], motivo: str, maximo: float) -> dict:
    limite = time.monotonic() + maximo
    while time.monotonic() < limite:
        estado = _leer_estado(esc)
        if estado is not None and condicion(estado):
            return estado
        time.sleep(0.2)
    raise AssertionError(f"no se cumplió: {motivo}; último estado: {_leer_estado(esc)}")


def test_agente_sin_nats_server_escribe_estado_sale_limpio_con_sigterm_y_conecta_cuando_aparece(
    escenario: Escenario,
) -> None:
    """Defecto 2: con nats-server ausente, nats-py reintentaba la conexión inicial SIN devolver nunca."""
    esc = escenario
    agente = esc.lanzar_agente()  # puerto cerrado: nadie escucha

    # 1) En pocos segundos hay estado local desconectado (antes: jamás aparecía).
    estado = _esperar_estado(esc, lambda e: e["conectado"] is False, "estado_local.json desconectado", 8)
    assert estado["secuencia"] is None
    assert agente.poll() is None

    # 2) SIGTERM interrumpe la conexión pendiente: sale con 0 en < 10 s (antes: «got TERM» > 100 s).
    agente.terminate()
    t0 = time.monotonic()
    assert agente.wait(timeout=10) == 0
    assert time.monotonic() - t0 < 10
    assert _leer_estado(esc)["conectado"] is False  # type: ignore[index]

    # 3) Relanzado sin servidor y luego con servidor: acaba conectando y publicando.
    agente = esc.lanzar_agente()
    _esperar_estado(esc, lambda e: e["conectado"] is False, "arranque desconectado", 8)
    esc.lanzar_nats()
    estado = _esperar_estado(esc, lambda e: e["conectado"] is True and e["secuencia"] is not None, "conecta", 40)
    assert estado["ultimo_error"] is None
    assert agente.poll() is None
