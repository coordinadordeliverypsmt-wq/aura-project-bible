"""N2 — custodia de la clave de firma de HC-1: firmador como proceso aparte con política (§12.6 N2).

Incluye la LIMITACIÓN DEMOSTRADA: con el mismo uid otro proceso lee la clave. Esas pruebas no esconden el límite: lo
fijan como hecho medido, para que nadie documente «custodia» donde solo hay separación de procesos.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from aura_skeleton.adapters.firma_delegacion import (
    ErrorClave,
    Firmante,
    cargar_clave_privada,
    generar_firmante,
    guardar_clave_privada,
    verificador_de,
)
from aura_skeleton.adapters.firmador_hc1 import (
    Firmador,
    PoliticaFirmador,
    credenciales_del_par,
    pedir_firma,
    uid_autorizado,
)
from aura_skeleton.core.delegacion import DOMINIO_ORDEN, Motivo, RechazoOrden, abrir_sobre, verificar_y_leer
from tests.delegacion_apoyo import NODO, OTRO_NODO

_WS = Path(__file__).resolve().parents[2]
PET = {"tarea": "t-1", "intento": 1, "destinatario": NODO, "capacidad": "calcular_resumen_sha256",
       "argumentos": {"texto": "hola"}, "vida_s": 60}  # fmt: skip


def _politica(**kw: object) -> PoliticaFirmador:
    base = {"emisor": "hc1", "kid": "hc1-k1", "destinatarios": frozenset({NODO}),
            "capacidades": frozenset({"calcular_resumen_sha256"}), "epoch": 7}  # fmt: skip
    base.update(kw)
    return PoliticaFirmador(**base)  # type: ignore[arg-type]


@pytest.fixture
def firmador(tmp_path: Path) -> tuple[Firmador, Firmante, Path]:
    f = generar_firmante("hc1-k1")
    log = tmp_path / "firmador.log.jsonl"
    return Firmador(f, _politica(), log, ahora=lambda: 5000.0), f, log


def test_peticion_valida_firma_una_orden_que_el_nodo_verifica(firmador: tuple[Firmador, Firmante, Path]) -> None:
    fm, f, _ = firmador
    sobre, ident = fm.firmar(PET)
    _, c = verificar_y_leer(sobre, DOMINIO_ORDEN, verificador_de({"hc1-k1": f.publica()}))
    assert c["id_ejecucion"] == ident and c["epoch_hc1"] == 7 and c["emisor"] == "hc1"
    assert c["emitida_en"] == 5000.0 and c["caduca_en"] == 5060.0  # el firmador pone la hora, no el cliente


def test_el_cliente_no_puede_fijar_emisor_epoch_ni_tiempos(firmador: tuple[Firmador, Firmante, Path]) -> None:
    fm, _, _ = firmador
    for extra in ("emisor", "epoch_hc1", "emitida_en", "caduca_en", "kid", "id_ejecucion", "v"):
        with pytest.raises(RechazoOrden) as e:
            fm.firmar({**PET, extra: 1})
        assert e.value.motivo is Motivo.CAMPOS_DESCONOCIDOS


def test_payload_arbitrario_no_se_firma(firmador: tuple[Firmador, Firmante, Path]) -> None:
    fm, _, log = firmador
    for basura in ({"bytes": "aGVsbG8="}, {}, "hola", ["x"], None, 5):
        with pytest.raises(RechazoOrden):
            fm.firmar(basura)  # type: ignore[arg-type]
    assert "firma" not in {json.loads(x)["tipo"] for x in log.read_text().splitlines()}


def test_capacidad_no_registrada_o_no_permitida_se_rechaza(firmador: tuple[Firmador, Firmante, Path]) -> None:
    fm, f, log = firmador
    with pytest.raises(RechazoOrden) as e:
        fm.firmar({**PET, "capacidad": "ejecutar_comando"})
    assert e.value.motivo is Motivo.CAPACIDAD_NO_REGISTRADA
    restringido = Firmador(f, _politica(capacidades=frozenset()), log, ahora=lambda: 1.0)
    with pytest.raises(RechazoOrden) as e2:
        restringido.firmar(PET)  # registrada globalmente pero NO permitida a este firmador
    assert e2.value.motivo is Motivo.CAPACIDAD_NO_REGISTRADA


def test_argumentos_invalidos_y_destinatario_desconocido_se_rechazan(firmador: tuple[Firmador, Firmante, Path]) -> None:
    fm, _, _ = firmador
    with pytest.raises(RechazoOrden) as e:
        fm.firmar({**PET, "argumentos": {"comando": "id"}})
    assert e.value.motivo is Motivo.ARGUMENTOS_INVALIDOS
    with pytest.raises(RechazoOrden) as e2:
        fm.firmar({**PET, "destinatario": OTRO_NODO})
    assert e2.value.motivo is Motivo.DESTINATARIO_AJENO


@pytest.mark.parametrize("vida", [301, 1e9, 0, -5, True, "60", None])
def test_caducidad_excesiva_o_invalida_se_rechaza(firmador: tuple[Firmador, Firmante, Path], vida: object) -> None:
    fm, _, _ = firmador
    with pytest.raises(RechazoOrden):
        fm.firmar({**PET, "vida_s": vida})
    assert fm.firmar({**PET, "vida_s": 300})  # control: el tope exacto se firma


def test_cada_firma_y_cada_rechazo_quedan_en_el_log_append_only_con_hash_y_momento(
    firmador: tuple[Firmador, Firmante, Path],
) -> None:
    fm, _, log = firmador
    sobre, ident = fm.firmar(PET)
    with pytest.raises(RechazoOrden):
        fm.firmar({**PET, "capacidad": "x"})
    sobre2, _ = fm.firmar({**PET, "tarea": "t-2"})
    lineas = [json.loads(x) for x in log.read_text().splitlines()]
    assert [x["tipo"] for x in lineas] == ["firma", "rechazo", "firma"]
    import hashlib

    assert lineas[0]["hash"] == hashlib.sha256(abrir_sobre(sobre).payload).hexdigest()
    assert lineas[0]["id_ejecucion"] == ident and lineas[0]["momento"] == 5000.0
    assert lineas[1]["motivo"] == Motivo.CAPACIDAD_NO_REGISTRADA.value
    assert log.stat().st_mode & 0o077 == 0
    assert sobre != sobre2


def test_la_clave_privada_no_aparece_en_logs_repr_ni_excepciones(
    firmador: tuple[Firmador, Firmante, Path], tmp_path: Path
) -> None:
    fm, f, log = firmador
    ruta = tmp_path / "k.pem"
    ruta.parent.chmod(0o700)
    from cryptography.hazmat.primitives import serialization

    clave = f._Firmante__clave  # type: ignore[attr-defined]
    guardar_clave_privada(ruta, clave)
    pem = ruta.read_bytes()
    raw = clave.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    fm.firmar(PET)
    with pytest.raises(RechazoOrden) as e:
        fm.firmar({**PET, "capacidad": "no"})
    textos = log.read_bytes() + repr(f).encode() + str(e.value).encode()
    assert raw.hex().encode() not in textos and raw not in textos and b"PRIVATE KEY" not in textos
    assert pem.startswith(b"-----BEGIN PRIVATE KEY")  # control: el detector de arriba sí vería un PEM


def test_clave_con_permisos_abiertos_o_directorio_abierto_falla_cerrado(tmp_path: Path) -> None:
    d = tmp_path / "k"
    d.mkdir(mode=0o700)
    ruta = d / "clave.pem"
    guardar_clave_privada(ruta, generar_firmante("k")._Firmante__clave)  # type: ignore[attr-defined]
    assert cargar_clave_privada(ruta)  # control
    ruta.chmod(0o640)
    with pytest.raises(ErrorClave):
        cargar_clave_privada(ruta)
    ruta.chmod(0o600)
    d.chmod(0o755)
    with pytest.raises(ErrorClave):
        cargar_clave_privada(ruta)
    d.chmod(0o700)
    with pytest.raises(ErrorClave):
        guardar_clave_privada(ruta, generar_firmante("k")._Firmante__clave)  # type: ignore[attr-defined]


def test_so_peercred_solo_acepta_uid_permitido() -> None:
    assert uid_autorizado(1000, frozenset({1000})) is True
    assert uid_autorizado(1001, frozenset({1000})) is False
    assert uid_autorizado(0, frozenset()) is False
    a, b = socket.socketpair()
    try:
        pid, uid, _ = credenciales_del_par(a)
        assert uid == os.getuid() and pid == os.getpid()
    finally:
        a.close()
        b.close()


# --- proceso real por socket Unix ------------------------------------------------------------------------------


class _Servicio:
    def __init__(self, raiz: Path, uids: list[int] | None = None) -> None:
        self.dir = raiz / "firmador"
        self.dir.mkdir(mode=0o700)
        self.firmante = generar_firmante("hc1-k1")
        self.clave = self.dir / "clave.pem"
        guardar_clave_privada(self.clave, self.firmante._Firmante__clave)  # type: ignore[attr-defined]
        self.sock = self.dir / "firmador.sock"
        self.log = self.dir / "log.jsonl"
        conf = {"kid": "hc1-k1", "emisor": "hc1", "destinatarios": [NODO], "capacidades": ["calcular_resumen_sha256"],
                "epoch": 3, "clave": str(self.clave), "socket": str(self.sock), "log": str(self.log)}  # fmt: skip
        if uids is not None:
            conf["uids"] = uids
        (self.dir / "config.json").write_text(json.dumps(conf))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "aura_skeleton.adapters.firmador_hc1", str(self.dir / "config.json")],
            cwd=_WS, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )  # fmt: skip
        assert self.proc.stdout is not None
        assert self.proc.stdout.readline().strip() == "listo", self.proc.stderr.read() if self.proc.stderr else ""

    def parar(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)


@pytest.fixture
def servicio(tmp_path: Path) -> Iterator[_Servicio]:
    s = _Servicio(tmp_path)
    try:
        yield s
    finally:
        s.parar()


def test_proceso_aparte_el_socket_es_0600_en_directorio_0700_y_firma_una_peticion_valida(servicio: _Servicio) -> None:
    assert servicio.sock.stat().st_mode & 0o777 == 0o600
    assert servicio.dir.stat().st_mode & 0o777 == 0o700
    r = pedir_firma(servicio.sock, PET)
    assert r["ok"] is True
    _, c = verificar_y_leer(r["sobre"], DOMINIO_ORDEN, verificador_de({"hc1-k1": servicio.firmante.publica()}))
    assert c["epoch_hc1"] == 3 and c["id_ejecucion"] == r["id_ejecucion"]
    assert set(r) == {"ok", "sobre", "id_ejecucion"}  # el cliente no recibe la clave ni nada más


def test_por_el_socket_el_payload_arbitrario_la_capacidad_y_la_caducidad_se_rechazan(servicio: _Servicio) -> None:
    for malo, motivo in (
        ({"capacidad": "bash"}, Motivo.CAPACIDAD_NO_REGISTRADA),
        ({"vida_s": 100000}, Motivo.CADUCIDAD_EXCESIVA),
    ):
        r = pedir_firma(servicio.sock, {**PET, **malo})
        assert r == {"ok": False, "motivo": motivo.value}
    assert pedir_firma(servicio.sock, {"payload": "aGVsbG8="})["ok"] is False
    r_basura = subprocess.run(
        [sys.executable, "-c",
         f"import socket;s=socket.socket(socket.AF_UNIX);s.connect({str(servicio.sock)!r});s.sendall(b'no json\\n');print(s.recv(999))"],
        capture_output=True, text=True, timeout=10,
    )  # fmt: skip
    assert "sobre_malformado" in r_basura.stdout


def test_el_respuesta_y_stderr_del_servicio_no_contienen_la_clave(servicio: _Servicio) -> None:
    from cryptography.hazmat.primitives import serialization

    raw = servicio.firmante._Firmante__clave.private_bytes(  # type: ignore[attr-defined]
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    r = pedir_firma(servicio.sock, PET)
    pedir_firma(servicio.sock, {**PET, "capacidad": "x"})
    servicio.parar()
    assert servicio.proc.stderr is not None and servicio.proc.stdout is not None
    visible = servicio.proc.stderr.read().encode() + servicio.proc.stdout.read().encode() + servicio.log.read_bytes()
    assert raw not in visible and raw.hex().encode() not in visible and r["sobre"].find(raw) == -1


def test_el_servicio_se_niega_a_arrancar_con_la_clave_abierta(tmp_path: Path) -> None:
    d = tmp_path / "f"
    d.mkdir(mode=0o700)
    ruta = d / "clave.pem"
    guardar_clave_privada(ruta, generar_firmante("hc1-k1")._Firmante__clave)  # type: ignore[attr-defined]
    ruta.chmod(0o644)
    conf = {"kid": "hc1-k1", "emisor": "hc1", "destinatarios": [NODO], "capacidades": [], "epoch": 1,
            "clave": str(ruta), "socket": str(d / "s.sock"), "log": str(d / "l")}  # fmt: skip
    (d / "c.json").write_text(json.dumps(conf))
    r = subprocess.run(
        [sys.executable, "-m", "aura_skeleton.adapters.firmador_hc1", str(d / "c.json")],
        cwd=_WS, capture_output=True, text=True, timeout=20,
    )  # fmt: skip
    assert r.returncode == 3 and "permisos inseguros" in r.stderr


def test_par_con_uid_no_permitido_es_rechazado_por_el_servicio(tmp_path: Path) -> None:
    s = _Servicio(tmp_path, uids=[os.getuid() + 1])  # nadie, ni nosotros, está permitido
    try:
        assert pedir_firma(s.sock, PET) == {"ok": False, "motivo": "par_no_autorizado"}
        assert not s.log.exists() or "firma" not in s.log.read_text()
    finally:
        s.parar()


def test_el_directorio_del_socket_abierto_hace_fallar_cerrado_el_arranque(tmp_path: Path) -> None:
    from aura_skeleton.adapters.firmador_hc1 import crear_servidor

    d = tmp_path / "abierto"
    d.mkdir()
    d.chmod(0o755)
    with pytest.raises(ErrorClave):
        crear_servidor(Firmador(generar_firmante("hc1-k1"), _politica(), tmp_path / "l"), d / "s", frozenset({0}))


# --- LIMITACIÓN DEMOSTRADA -------------------------------------------------------------------------------------


def test_limitacion_con_el_mismo_uid_otro_proceso_lee_la_clave_y_firma_lo_que_quiera(servicio: _Servicio) -> None:
    """Este test PASA porque el límite es real: la separación de procesos NO es custodia frente al mismo uid.

    Un proceso cualquiera del mismo usuario (aquí un `python -c` ajeno al firmador) lee el PEM y fabrica una orden
    que el nodo aceptaría, saltándose la política del firmador (capacidad, destinatario, caducidad)."""
    codigo = (
        "import sys;from cryptography.hazmat.primitives import serialization as s;"
        "k=s.load_pem_private_key(open(sys.argv[1],'rb').read(),None);"
        "sys.stdout.buffer.write(k.sign(b'aura.delegacion.orden/1\\n'+b'{\"cualquier\":\"cosa\"}'))"
    )
    r = subprocess.run(
        [sys.executable, "-c", codigo, str(servicio.clave)], capture_output=True, timeout=20, check=False
    )
    assert r.returncode == 0, r.stderr
    firma_falsa = r.stdout
    assert len(firma_falsa) == 64
    ok = verificador_de({"hc1-k1": servicio.firmante.publica()})(
        "hc1-k1", b'aura.delegacion.orden/1\n{"cualquier":"cosa"}', firma_falsa
    )
    assert ok is True, "el atacante del mismo uid firmó un payload que el firmador jamás habría firmado"
    # El permiso 0600 solo excluye a OTROS usuarios; no al propio. Custodia real: usuario de sistema distinto
    # (crear usuarios exige root) o HSM/TPM.
    assert servicio.clave.stat().st_uid == os.getuid()
    time.sleep(0)
