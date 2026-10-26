"""Receptor de latidos de HC-1 (DP-NODO-01 §4.4-§4.5): suplantación, validación y persistencia."""

from __future__ import annotations

import asyncio
import json
import os
import stat

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.adapters.receptor_nodos import TOLERANCIA_RECEPTOR_S, ReceptorNodos, leer_registro
from aura_skeleton.contracts import Event
from aura_skeleton.core.nodos import construir_latido, subject_de

ID_A = "a" * 32
ID_B = "b" * 32
ARR1 = "1" * 32
ARR2 = "2" * 32


def _latido(nodo_id=ID_A, secuencia=0, arranque=ARR1, **extra):
    datos = construir_latido(
        nodo_id, "nodo-01", secuencia, arranque, 10.0, {"ram_mb": 986.0, "nucleos": 2.0}, [], "1.0"
    )
    datos.update(extra)
    return datos


def _evento(payload, subject=None):
    return Event(
        type=subject or subject_de(payload.get("nodo_id", ID_A)), trace_id="t", user_id="nodo", payload=payload
    )


def _leer(ruta):
    with open(os.path.join(ruta, "nodos", "registro.json"), encoding="utf-8") as f:
        return json.load(f)


def _manejar(receptor, evento):
    return asyncio.run(receptor.manejar(evento))


def test_tolerancia_es_tres_intervalos_de_diez_segundos():
    assert TOLERANCIA_RECEPTOR_S == 30.0


def test_suplantacion_rechazada_y_no_registrada(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 100.0)
    resultado = _manejar(receptor, _evento(_latido(ID_A), subject=subject_de(ID_B)))
    assert resultado == "rechazado"
    assert not os.path.exists(tmp_path / "nodos" / "registro.json") or _leer(tmp_path)["nodos"] == {}
    assert any("suplantación" in r["msg"] and r["level"] == "WARN" for r in obs.audit_records())


def test_subject_sin_forma_de_latido_rechazado(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 100.0)
    assert _manejar(receptor, _evento(_latido(), subject="otra.cosa")) == "rechazado"


def test_payload_invalido_rechazado_sin_volcar_el_valor(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 100.0)
    malo = _latido(nombre="SECRETO-NO-LOGUEAR\x00")
    n = len(obs._records)
    assert _manejar(receptor, _evento(malo)) == "rechazado"
    nuevos = obs._records[n:]
    assert any(r["level"] == "WARN" and r.get("audit") for r in nuevos)
    assert "SECRETO-NO-LOGUEAR" not in json.dumps(nuevos)
    assert receptor.registro.nodos() == ()


def test_nuevo_latido_y_reinicio_se_persisten(tmp_path):
    t = [100.0]
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: t[0])
    assert _manejar(receptor, _evento(_latido(secuencia=0))) == "nuevo"
    assert _leer(tmp_path)["nodos"][ID_A]["recibido_en"] == 100.0
    t[0] = 110.0
    assert _manejar(receptor, _evento(_latido(secuencia=1))) == "latido"
    assert _leer(tmp_path)["nodos"][ID_A]["recibido_en"] == 110.0
    t[0] = 120.0
    assert _manejar(receptor, _evento(_latido(secuencia=0, arranque=ARR2))) == "reinicio"
    entrada = _leer(tmp_path)["nodos"][ID_A]
    assert entrada["reinicios"] == 1
    assert entrada["primer_contacto"] == 100.0


def test_nuevo_y_reinicio_se_auditan_con_nombre_e_id_corto(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 1.0)
    n = len(obs._records)
    _manejar(receptor, _evento(_latido(secuencia=0)))
    _manejar(receptor, _evento(_latido(secuencia=0, arranque=ARR2)))
    info = [r for r in obs._records[n:] if r["level"] == "INFO" and r.get("audit")]
    assert len(info) == 2
    assert all("nodo-01" in r["msg"] and ID_A[:8] in r["msg"] for r in info)


def test_permisos_0700_y_0600(tmp_path):
    receptor = ReceptorNodos(str(tmp_path / "red"), reloj=lambda: 1.0)
    _manejar(receptor, _evento(_latido()))
    assert stat.S_IMODE(os.stat(tmp_path / "red" / "nodos").st_mode) == 0o700
    assert stat.S_IMODE(os.stat(tmp_path / "red" / "nodos" / "registro.json").st_mode) == 0o600


def test_registro_corrupto_se_aparta_y_empieza_vacio(tmp_path):
    carpeta = tmp_path / "nodos"
    carpeta.mkdir()
    (carpeta / "registro.json").write_text("{esto no es json", encoding="utf-8")
    n = len(obs._records)
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 1234.0)
    assert receptor.registro.nodos() == ()
    apartados = [p.name for p in carpeta.iterdir() if p.name.startswith("registro.json.corrupto-")]
    assert len(apartados) == 1
    assert (carpeta / apartados[0]).read_text(encoding="utf-8") == "{esto no es json"
    assert not (carpeta / "registro.json").exists()
    assert any(r["level"] == "WARN" and r.get("audit") for r in obs._records[n:])


def test_registro_con_esquema_incoherente_tambien_se_aparta(tmp_path):
    carpeta = tmp_path / "nodos"
    carpeta.mkdir()
    (carpeta / "registro.json").write_text(json.dumps({"nodos": {"x": 1}}), encoding="utf-8")
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 1.0)
    assert receptor.registro.nodos() == ()
    assert any(p.name.startswith("registro.json.corrupto-") for p in carpeta.iterdir())


def test_recarga_tras_reinicio_del_receptor(tmp_path):
    _manejar(ReceptorNodos(str(tmp_path), reloj=lambda: 50.0), _evento(_latido()))
    nuevo = ReceptorNodos(str(tmp_path), reloj=lambda: 60.0)
    previo = nuevo.registro.obtener(ID_A)
    assert previo is not None and previo.recibido_en == 50.0
    # y un latido siguiente del mismo arranque no es "nuevo"
    assert _manejar(nuevo, _evento(_latido(secuencia=1))) == "latido"


def test_latir_escribe_latido_del_receptor_y_conserva_los_nodos(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 77.0)
    _manejar(receptor, _evento(_latido()))
    receptor.latir()
    datos = _leer(tmp_path)
    assert datos["receptor"] == {"latido": 77.0, "pid": os.getpid()}
    assert ID_A in datos["nodos"]


def test_leer_registro_sin_fichero_devuelve_vacio_y_no_crea_nada(tmp_path):
    assert leer_registro(str(tmp_path / "red")) == {"receptor": None, "nodos": {}}
    assert not (tmp_path / "red").exists()


def test_leer_registro_devuelve_lo_persistido(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 5.0)
    _manejar(receptor, _evento(_latido()))
    receptor.latir()
    assert ID_A in leer_registro(str(tmp_path))["nodos"]
    assert leer_registro(str(tmp_path))["receptor"]["latido"] == 5.0


def test_leer_registro_corrupto_lanza_valueerror(tmp_path):
    (tmp_path / "nodos").mkdir()
    (tmp_path / "nodos" / "registro.json").write_text("basura", encoding="utf-8")
    with pytest.raises(ValueError):
        leer_registro(str(tmp_path))


class _ConexionCapturada(Exception):
    pass


def _ca_de_prueba(directorio) -> str:
    import shutil
    import subprocess

    if shutil.which("openssl") is None:
        pytest.skip("openssl no disponible (CA de la prueba)")
    clave, ca = str(directorio / "ca.key"), str(directorio / "ca.crt")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
         "-keyout", clave, "-out", ca, "-days", "1", "-subj", "/CN=ca-prueba"],
        check=True, capture_output=True,
    )  # fmt: skip
    return ca


async def test_ejecutar_conecta_con_tls_verificado_y_credenciales(tmp_path, monkeypatch):
    """El receptor exige certificado y nombre contra la CA privada: sin esto, cualquiera suplantaría a HC-1."""
    import ssl

    from aura_skeleton.bus_nats import NatsEventBus

    capturado: dict = {}

    async def falso_connect(url, **opciones):
        capturado["url"] = url
        capturado.update(opciones)
        raise _ConexionCapturada

    monkeypatch.setattr(NatsEventBus, "connect", falso_connect)
    ca = _ca_de_prueba(tmp_path)
    receptor = ReceptorNodos(str(tmp_path / "red"), reloj=lambda: 1.0)
    with pytest.raises(_ConexionCapturada):
        await receptor.ejecutar(["tls://127.0.0.1:4222"], "receptor", "clave-x", ca)
    assert capturado["url"] == ["tls://127.0.0.1:4222"]
    assert capturado["user"] == "receptor" and capturado["password"] == "clave-x"
    ctx = capturado["tls"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert ctx.verify_flags & ssl.VERIFY_X509_STRICT
    assert any("ca-prueba" in str(c) for c in ctx.get_ca_certs()[0]["subject"])


# --- paso de vida: solo late si el bus está conectado (M-2) ----------------------------------------------


class _BusFalso:
    def __init__(self, conectado: bool) -> None:
        self.conectado = conectado


def test_paso_de_vida_con_bus_conectado_late(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 500.0)
    receptor._paso_de_vida(_BusFalso(True))
    assert _leer(str(tmp_path))["receptor"]["latido"] == 500.0


def test_paso_de_vida_con_bus_desconectado_no_late(tmp_path):
    receptor = ReceptorNodos(str(tmp_path), reloj=lambda: 500.0)
    receptor._paso_de_vida(_BusFalso(False))
    assert not os.path.exists(os.path.join(str(tmp_path), "nodos", "registro.json"))
    assert leer_registro(str(tmp_path))["receptor"] is None
