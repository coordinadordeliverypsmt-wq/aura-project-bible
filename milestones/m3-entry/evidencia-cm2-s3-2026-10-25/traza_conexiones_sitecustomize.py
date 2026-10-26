"""Diagnostico: registra connect() a puertos de servicios REALES del equipo, con la prueba que lo hizo."""
import json, os, socket

_PUERTOS = {int(p) for p in os.environ.get("VIGIA_PUERTOS", "").split(",") if p}
_SALIDA = os.environ.get("VIGIA_CONEXIONES")
_orig_connect, _orig_connect_ex = socket.socket.connect, socket.socket.connect_ex


def _anotar(sock, addr):
    try:
        if _SALIDA and sock.family in (socket.AF_INET, socket.AF_INET6) and int(addr[1]) in _PUERTOS:
            with open(_SALIDA, "a") as f:
                f.write(json.dumps({"prueba": os.environ.get("PYTEST_CURRENT_TEST", "?"), "pid": os.getpid(),
                                    "destino": [str(addr[0]), int(addr[1])]}) + "\n")
    except Exception:
        pass


def _connect(self, addr):
    _anotar(self, addr)
    return _orig_connect(self, addr)


def _connect_ex(self, addr):
    _anotar(self, addr)
    return _orig_connect_ex(self, addr)


if _PUERTOS and _SALIDA:
    socket.socket.connect, socket.socket.connect_ex = _connect, _connect_ex
