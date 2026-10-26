# ruff: noqa: E702, E741
"""FASE B del PROMPT 03 · aislamiento ESTRICTO de la verificacion por contrato (CEO: restringir la
lectura y denegar la red por defecto, sin excepciones).

Cada prueba de ataque usa SENUELOS FUERA de la copia con sha antes/despues, servidores propios en
127.0.0.1 (TCP, UDP, unix de ruta, unix abstracto) y un `sleep` propio. Se ejercen el proceso
confinado, su HIJO y su NIETO. Las pruebas de FALLO SEGURO (soporte insuficiente) no llevan skip: son
las que garantizan que nunca se degrada en silencio.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import secrets
import signal
import socket
import subprocess
import sys
import time

import aislamiento as ais
import pytest
import review
import verificador as vf

PLANO = pathlib.Path(__file__).resolve().parent
ESTRICTO = hasattr(ais, "estricto_disponible") and ais.estricto_disponible()
necesita_estricto = pytest.mark.skipif(not ESTRICTO, reason="este kernel no ofrece Landlock ABI>=6 + seccomp")

_INTENTOS = r'''
import ctypes, errno, json, os, socket, subprocess, sys
D = json.loads(sys.argv[1]); N = int(sys.argv[2]); R = {}
def t(nombre, f):
    try:
        f(); R[nombre] = "OK"
    except OSError as e:
        R[nombre] = errno.errorcode.get(e.errno, str(e.errno))
    except Exception as e:
        R[nombre] = "EXC:" + repr(e)
def tcp_connect():
    s = socket.socket(); s.settimeout(3); s.connect(("127.0.0.1", D["tcp"]))
def tcp_bind():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(1)
def udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b"x", ("127.0.0.1", D["udp"]))
def unix_ruta():
    s = socket.socket(socket.AF_UNIX); s.connect(D["unix"])
def unix_abstracto():
    s = socket.socket(socket.AF_UNIX); s.connect("\0" + D["abs"])
def inet6():
    socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
def netlink():
    socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 0)
def io_uring():
    libc = ctypes.CDLL(None, use_errno=True); buf = ctypes.create_string_buffer(120)
    if libc.syscall(425, 1, buf) < 0:
        raise OSError(ctypes.get_errno(), "io_uring_setup")
for n, f in (("tcp_connect", tcp_connect), ("tcp_bind", tcp_bind), ("udp", udp), ("unix_ruta", unix_ruta),
             ("unix_abstracto", unix_abstracto), ("inet6", inet6), ("netlink", netlink), ("io_uring", io_uring)):
    t(n, f)
print("NIVEL%d %s" % (N, json.dumps(R)))
if N > 0:
    p = subprocess.run([sys.executable, __file__, sys.argv[1], str(N - 1)], capture_output=True, text=True)
    sys.stdout.write(p.stdout)
'''

_LEE = r'''
import json, sys
R = {}
for ruta in json.loads(sys.argv[1]):
    try:
        open(ruta, "rb").read(16); R[ruta] = "OK"
    except OSError as e:
        R[ruta] = type(e).__name__
print(json.dumps(R))
'''


def _sha(ruta) -> str:
    return hashlib.sha256(pathlib.Path(ruta).read_bytes()).hexdigest()


class Escenario:
    pass


@pytest.fixture
def esc(tmp_path, monkeypatch):
    e = Escenario()
    e.caja = tmp_path / "caja"
    e.caja.mkdir()
    e.fuera = tmp_path / "fuera"
    e.fuera.mkdir()
    e.secreto = e.fuera / "secreto.txt"
    e.secreto.write_text("CLAVE-FUERA", encoding="utf-8")
    e.home = tmp_path / "home"
    (e.home / ".ssh").mkdir(parents=True)
    e.secreto_home = e.home / ".ssh" / "id_falso"
    e.secreto_home.write_text("CLAVE-HOME", encoding="utf-8")
    e.vivo = tmp_path / "vivo"                      # un directorio que SI esta en sys.path del padre
    e.vivo.mkdir()
    (e.vivo / "modvivo.py").write_text("VIVO = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(e.vivo))
    e.entorno = {"PATH": os.environ.get("PATH", ""), "HOME": str(e.home), "PYTHONDONTWRITEBYTECODE": "1"}
    e.senuelos = [e.secreto, e.secreto_home, e.vivo / "modvivo.py", PLANO / "aislamiento.py"]
    e.shas = {str(p): _sha(p) for p in e.senuelos}
    yield e
    for p in e.senuelos:                            # ningun ataque modifico un senuelo
        assert _sha(p) == e.shas[str(p)], f"se modifico {p}"


def correr(esc, argv, *, extra=(), timeout=60):
    confinar = ais.preparar_estricto(esc.caja, extra)
    return subprocess.run([sys.executable, *argv], cwd=esc.caja, env=esc.entorno, preexec_fn=confinar,
                          capture_output=True, text=True, timeout=timeout)


def _escribir(esc, nombre, fuente):
    (esc.caja / nombre).write_text(fuente, encoding="utf-8")
    return str(esc.caja / nombre)


# ============================================================================= LECTURA ==

@necesita_estricto
def test_la_lectura_DENTRO_de_la_copia_esta_permitida(esc):
    (esc.caja / "dato.txt").write_text("hola", encoding="utf-8")
    (esc.caja / "modcopia.py").write_text("X = 7\n", encoding="utf-8")
    script = _escribir(esc, "lee.py", "import modcopia, sys\nprint(open('dato.txt').read(), modcopia.X)\n")
    r = correr(esc, [script])
    assert r.returncode == 0 and r.stdout.split() == ["hola", "7"], r.stderr


def _leidas(esc, rutas):
    script = _escribir(esc, "leer.py", _LEE)
    r = correr(esc, [script, json.dumps([str(x) for x in rutas])])
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@necesita_estricto
@pytest.mark.parametrize("cual", ["plano_real", "dir_en_syspath", "etc_passwd", "proc_environ",
                                   "secreto_home", "ruta_arbitraria"])
def test_la_lectura_FUERA_de_la_copia_esta_DENEGADA(esc, cual):
    ruta = {"plano_real": PLANO / "aislamiento.py", "dir_en_syspath": esc.vivo / "modvivo.py",
            "etc_passwd": pathlib.Path("/etc/passwd"), "proc_environ": pathlib.Path("/proc/self/environ"),
            "secreto_home": esc.secreto_home, "ruta_arbitraria": esc.secreto}[cual]
    ruta.read_bytes()                                           # CONTROL: el padre SI puede leerlo
    assert _leidas(esc, [ruta]) == {str(ruta): "PermissionError"}


@necesita_estricto
def test_enlaces_simbolicos_de_la_copia_hacia_fuera_no_dan_lectura(esc):
    (esc.caja / "enlace").symlink_to(esc.secreto)
    (esc.caja / "enlace_dir").symlink_to(esc.fuera)
    (esc.caja / "propio.txt").write_text("ok", encoding="utf-8")
    r = _leidas(esc, [esc.caja / "enlace", esc.caja / "enlace_dir" / "secreto.txt", esc.caja / "propio.txt"])
    assert r == {str(esc.caja / "enlace"): "PermissionError",
                 str(esc.caja / "enlace_dir" / "secreto.txt"): "PermissionError",
                 str(esc.caja / "propio.txt"): "OK"}


@necesita_estricto
def test_importar_un_modulo_del_vivo_por_ruta_absoluta_falla(esc):
    script = _escribir(esc, "imp.py", (
        "import sys, importlib.util\n"
        f"sys.path.insert(0, {str(esc.vivo)!r})\n"
        "res = []\n"
        "try:\n    import modvivo; res.append('importo')\n"
        "except Exception as e:\n    res.append(type(e).__name__)\n"
        f"s = importlib.util.spec_from_file_location('ais_vivo', {str(PLANO / 'aislamiento.py')!r})\n"
        "try:\n    s.loader.exec_module(importlib.util.module_from_spec(s)); res.append('importo')\n"
        "except Exception as e:\n    res.append(type(e).__name__)\n"
        "print(res)\n"))
    r = correr(esc, [script])
    assert "importo" not in r.stdout and r.stdout.count("Error") == 2, (r.stdout, r.stderr)


# =========================================================================== ESCRITURA ==

@necesita_estricto
def test_la_escritura_fuera_de_la_copia_esta_denegada_y_dentro_permitida(esc):
    script = _escribir(esc, "esc.py", (
        "import os, json\nR = {}\n"
        f"for n, f in (('fuera_nuevo', {str(esc.fuera / 'nuevo.txt')!r}), ('fuera_existente', {str(esc.secreto)!r}),\n"
        f"              ('dentro', {str(esc.caja / 'nuevo.txt')!r}), ('dev_null', '/dev/null')):\n"
        "    try:\n        open(f, 'w').write('X'); R[n] = 'OK'\n    except OSError as e:\n        R[n] = type(e).__name__\n"
        f"try:\n    os.unlink({str(esc.secreto)!r}); R['unlink'] = 'OK'\nexcept OSError as e:\n    R['unlink'] = type(e).__name__\n"
        "print(json.dumps(R))\n"))
    r = correr(esc, [script])
    assert json.loads(r.stdout) == {"fuera_nuevo": "PermissionError", "fuera_existente": "PermissionError",
                                    "dentro": "OK", "dev_null": "OK", "unlink": "PermissionError"}, r.stderr
    assert not (esc.fuera / "nuevo.txt").exists()


# ================================================================================ RED ==

@pytest.fixture
def servidores(tmp_path):
    srv = {}
    tcp = socket.socket(); tcp.bind(("127.0.0.1", 0)); tcp.listen(5); tcp.setblocking(False)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); udp.bind(("127.0.0.1", 0)); udp.setblocking(False)
    ruta = str(tmp_path / "s.sock")
    un = socket.socket(socket.AF_UNIX); un.bind(ruta); un.listen(5); un.setblocking(False)
    nombre = "aura-test-" + secrets.token_hex(6)
    ab = socket.socket(socket.AF_UNIX); ab.bind("\0" + nombre); ab.listen(5); ab.setblocking(False)
    srv.update(tcp=tcp, udp=udp, unix=un, abs=ab)
    srv["datos"] = {"tcp": tcp.getsockname()[1], "udp": udp.getsockname()[1], "unix": ruta, "abs": nombre}
    yield srv
    for k in ("tcp", "udp", "unix", "abs"):
        srv[k].close()


def _recibido(srv) -> dict:
    def hay(f):
        try:
            f(); return True
        except (BlockingIOError, OSError):
            return False
    return {"tcp": hay(srv["tcp"].accept), "udp": hay(lambda: srv["udp"].recvfrom(8)),
            "unix": hay(srv["unix"].accept), "abs": hay(srv["abs"].accept)}


def _niveles(salida: str) -> dict:
    return {int(l[5]): json.loads(l[7:]) for l in salida.splitlines() if l.startswith("NIVEL")}


@necesita_estricto
def test_CONTROL_sin_confinar_los_servidores_de_la_prueba_SI_reciben(esc, servidores):
    script = _escribir(esc, "intentos.py", _INTENTOS)
    r = subprocess.run([sys.executable, script, json.dumps(servidores["datos"]), "0"], cwd=esc.caja,
                       capture_output=True, text=True, timeout=60)
    res = _niveles(r.stdout)[0]
    assert res["tcp_connect"] == res["udp"] == res["unix_ruta"] == res["unix_abstracto"] == "OK", res
    assert all(_recibido(servidores).values())


@necesita_estricto
def test_la_red_esta_denegada_en_el_proceso_su_hijo_y_su_nieto(esc, servidores):
    script = _escribir(esc, "intentos.py", _INTENTOS)
    r = correr(esc, [script, json.dumps(servidores["datos"]), "2"])
    niveles = _niveles(r.stdout)
    assert sorted(niveles) == [0, 1, 2], (r.stdout, r.stderr)           # proceso, hijo, nieto
    for nivel, res in niveles.items():
        for nombre, valor in res.items():
            assert valor in ("EPERM", "EACCES"), f"nivel {nivel} {nombre}: {valor}"
    assert not any(_recibido(servidores).values()), "algun servidor propio recibio trafico del confinado"


# ============================================================================== SENALES ==

@necesita_estricto
def test_el_confinado_no_puede_senalar_un_proceso_externo_pero_el_padre_si_puede_matar_al_hijo(esc):
    externo = subprocess.Popen(["sleep", "300"])                         # lanzado por esta prueba
    try:
        script = _escribir(esc, "sen.py", (
            "import os, signal, sys, json\npid = int(sys.argv[1]); R = {}\n"
            "for n, s in (('sig0', 0), ('term', signal.SIGTERM)):\n"
            "    try:\n        os.kill(pid, s); R[n] = 'OK'\n    except OSError as e:\n        R[n] = type(e).__name__\n"
            "os.kill(os.getpid(), 0); R['propio'] = 'OK'\nprint(json.dumps(R))\n"))
        os.kill(externo.pid, 0)                                          # CONTROL: el padre si puede
        r = correr(esc, [script, str(externo.pid)])
        assert json.loads(r.stdout) == {"sig0": "PermissionError", "term": "PermissionError",
                                        "propio": "OK"}, r.stderr
        assert externo.poll() is None, "el sleep externo murio"
        hijo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"], cwd=esc.caja,
                                env=esc.entorno, preexec_fn=ais.preparar_estricto(esc.caja))
        time.sleep(0.5)
        hijo.terminate()
        assert hijo.wait(timeout=10) == -signal.SIGTERM, "el padre no pudo terminar al hijo confinado"
    finally:
        externo.kill(); externo.wait()


# ================================================================ FALLO SEGURO (sin skip) ==

def test_ABI_menor_que_6_NO_devuelve_confinador(esc, monkeypatch):
    monkeypatch.setattr(ais, "abi_disponible", lambda: 5)
    with pytest.raises(ais.ConfinamientoInsuficiente):
        ais.preparar_estricto(esc.caja)


def test_sin_seccomp_NO_devuelve_confinador(esc, monkeypatch):
    monkeypatch.setattr(ais, "seccomp_disponible", lambda: False)
    with pytest.raises(ais.ConfinamientoInsuficiente):
        ais.preparar_estricto(esc.caja)


def _contrato(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    return real, {"verificacion": {"pruebas_minimas": [str(real / "test_x.py")]}}


@pytest.mark.parametrize("que", ["abi5", "sin_seccomp"])
def test_review_con_soporte_insuficiente_rechaza_sin_ejecutar(tmp_path, monkeypatch, que):
    real, contrato = _contrato(tmp_path)
    if que == "abi5":
        monkeypatch.setattr(ais, "abi_disponible", lambda: 5)
    else:
        monkeypatch.setattr(ais, "seccomp_disponible", lambda: False)
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a))
    r = review._verificador_de_review(contrato, real)(real)
    assert llamadas == [] and r.estado == "sin_confinamiento" and r.confinada is False, r


def test_review_no_acepta_un_confinador_incompleto(tmp_path, monkeypatch):
    real, contrato = _contrato(tmp_path)

    def falso():
        return None
    falso.abi, falso.completo, falso.controles = 6, False, {"seccomp_red": False}
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: falso)
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a))
    r = review._verificador_de_review(contrato, real)(real)
    assert llamadas == [] and r.estado == "sin_confinamiento" and r.confinada is False, r


def test_el_modo_por_defecto_NO_cambia_y_no_es_estricto(tmp_path):
    c = ais.preparar(tmp_path)
    assert not getattr(c, "completo", False) and not hasattr(c, "controles")


# ================================================================================ E2E ==

@necesita_estricto
def test_el_confinador_estricto_declara_TODOS_los_controles(tmp_path):
    c = ais.preparar_estricto(tmp_path)
    assert c.completo is True and c.abi >= 6
    assert set(ais.CONTROLES_ESTRICTOS) <= set(c.controles) and all(c.controles[k] for k in ais.CONTROLES_ESTRICTOS)
    assert c.con_escritura_en(tmp_path / "x").completo is True          # componible sin degradarse


@necesita_estricto
def test_TMPDIR_es_el_temporal_del_informe_y_no_se_crea_pytest_of_en_el_cwd(tmp_path, monkeypatch):
    import orquestador as orq
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    monkeypatch.delenv("TMPDIR", raising=False)
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    (raiz / "test_t.py").write_text(
        "import os\ndef test_t(tmp_path):\n"
        "    assert 'aura-verificador-' in os.environ['TMPDIR']\n"
        "    assert 'aura-verificador-' in str(tmp_path)\n", encoding="utf-8")
    informe = vf.ejecutar_pruebas([str(raiz / "test_t.py")], raiz, confinar=ais.preparar_estricto(raiz))
    assert informe.sano, informe.salida
    assert not list(raiz.glob("pytest-of-*")), "pytest creo su directorio base en el cwd"


def _contrato_en_este_plano(contrato: dict) -> dict:
    """Los contratos reales guardan `pruebas_minimas` ABSOLUTAS al plano vivo. Cuando esta bateria corre en la copia
    aislada del arnes de mutacion (regla 6, 2026-10-25), `PLANO` es la copia: se reubican sobre `PLANO` para medir el
    plano bajo prueba. Sin esto la verificacion devuelve `no_aislable` (y hace bien). En el arbol vivo no cambia nada."""
    marca = "/entorno/control-plane/"
    verificacion = dict(contrato.get("verificacion") or {})
    verificacion["pruebas_minimas"] = [
        str(PLANO.resolve() / str(p).split(marca, 1)[1]) if marca in str(p) else p
        for p in verificacion.get("pruebas_minimas") or []]
    return {**contrato, "verificacion": verificacion}


@necesita_estricto
@pytest.mark.parametrize("ident,modulo", [("sexta-fuente-estancamiento", "estancamiento.py"),
                                          ("etiqueta-observatorio-efecto", "observatorio.py")])
def test_E2E_los_contratos_reales_pasan_confinados_en_estricto(ident, modulo, tmp_path, monkeypatch):
    import autoconstruccion as ac
    import contrato as ct
    import orquestador as orq
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    contrato = _contrato_en_este_plano(ct.contrato_de(ident))
    copia, _, _, _ = ac._crear_copia(PLANO.resolve(), pathlib.PurePath(modulo))
    try:
        r = review._verificador_de_review(contrato, PLANO)(copia)
        assert r.estado == "sano" and r.aislada is True and r.confinada is True, r
        # la copia hereda el `pytest-of-*` preexistente del vivo; la verificacion no debe crear otro
        assert {x.name for x in copia.glob("pytest-of-*")} == {x.name for x in PLANO.glob("pytest-of-*")}
    finally:
        import shutil
        shutil.rmtree(copia, ignore_errors=True)


# ================================================================ RONDA PROMPT 04 (seguridad) ==

import ctypes  # noqa: E402
import inspect  # noqa: E402

_PYC = r'''
import ctypes, errno, json, os, socket, sys
D = json.loads(sys.argv[1]); R = {}
libc = ctypes.CDLL(None, use_errno=True)
def t(n, f):
    try:
        f(); R[n] = "OK"
    except OSError as e:
        R[n] = errno.errorcode.get(e.errno, str(e.errno))
    except Exception as e:
        R[n] = "EXC:" + repr(e)
def vsock(): socket.socket(40, socket.SOCK_STREAM)
def bluetooth(): socket.socket(31, socket.SOCK_STREAM, 3)
def shm():
    libc.shmat.restype = ctypes.c_void_p
    p = libc.shmat(D["shmid"], None, 1)
    if p in (None, ctypes.c_void_p(-1).value): raise OSError(ctypes.get_errno(), "shmat")
def shmget():
    if libc.shmget(0, 4096, 0o1600) < 0: raise OSError(ctypes.get_errno(), "shmget")
def msgget():
    if libc.msgget(0, 0o1600) < 0: raise OSError(ctypes.get_errno(), "msgget")
def semget():
    if libc.semget(0, 1, 0o1600) < 0: raise OSError(ctypes.get_errno(), "semget")
def chmod(): os.chmod(D["ext"], 0o777)
def chmod0(): os.chmod(D["ext"], 0)
def chown(): os.chown(D["ext"], os.getuid(), os.getgid())
def utime(): os.utime(D["ext"], (1, 1))
def utime_ns(): os.utime(D["ext"], ns=(1, 1), follow_symlinks=False)
for n, f in (("vsock", vsock), ("bluetooth", bluetooth), ("shmat", shm), ("shmget", shmget),
             ("msgget", msgget), ("semget", semget), ("chmod", chmod), ("chmod0", chmod0),
             ("chown", chown), ("utime", utime), ("utimens", utime_ns)):
    t(n, f)
print(json.dumps(R))
'''


def _estado(p):
    s = os.stat(p)
    return (s.st_mode, s.st_mtime_ns, s.st_uid)


@pytest.fixture
def shm_propio():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.shmat.restype = ctypes.c_void_p
    sid = libc.shmget(0, 4096, 0o1600)                           # IPC_PRIVATE|IPC_CREAT 0600
    assert sid >= 0
    p = libc.shmat(sid, None, 0)
    ctypes.memmove(p, b"SECRETO-SHM", 11)
    yield sid, libc, p
    libc.shmdt(ctypes.c_void_p(p))
    libc.shmctl(sid, 0, None)                                    # IPC_RMID


@necesita_estricto
def test_H1_H2_H3_vsock_bluetooth_sysv_y_metadatos_denegados(esc, shm_propio):
    sid, libc, p = shm_propio
    assert ctypes.string_at(p, 11) == b"SECRETO-SHM"
    ext = esc.fuera / "meta.txt"
    ext.write_text("m", encoding="utf-8")
    os.utime(ext, (5, 5))
    antes = _estado(ext)
    script = _escribir(esc, "p04.py", _PYC)
    datos = json.dumps({"shmid": sid, "ext": str(ext)})
    r = correr(esc, [script, datos])
    res = json.loads(r.stdout)
    assert res == {k: "EPERM" for k in res} and len(res) == 11, (res, r.stderr)
    assert _estado(ext) == antes, "se alteraron los metadatos del fichero externo"


@necesita_estricto
def test_H1_CONTROL_sin_confinar_los_mismos_intentos_si_funcionan(esc, shm_propio):
    sid, _, _ = shm_propio
    ext = esc.fuera / "meta2.txt"
    ext.write_text("m", encoding="utf-8")
    script = _escribir(esc, "p04.py", _PYC)
    r = subprocess.run([sys.executable, script, json.dumps({"shmid": sid, "ext": str(ext)})], cwd=esc.caja,
                       env=esc.entorno, capture_output=True, text=True, timeout=60)
    res = json.loads(r.stdout)
    assert res["shmat"] == res["shmget"] == res["msgget"] == res["semget"] == "OK", res
    assert res["chmod"] == "OK" and res["utime"] == "OK", res


@necesita_estricto
def test_H1_un_listener_vsock_propio_no_recibe_nada_del_confinado(esc):
    escucha = socket.socket(40, socket.SOCK_STREAM)
    try:
        puerto = 49152 + secrets.randbelow(10000)                # vsock no admite puerto 0 sin privilegios
        escucha.bind((0xFFFFFFFF, puerto))                       # VMADDR_CID_ANY
        escucha.listen(1)
        escucha.setblocking(False)
        cli = socket.socket(40, socket.SOCK_STREAM)
        cli.settimeout(2)
        cli.connect((1, puerto))                                 # CID 1 = loopback local
        cli.close()
    except OSError as exc:
        escucha.close()
        pytest.skip(f"este kernel no ofrece vsock local utilizable: {exc}")
    try:
        escucha.accept()                                         # drena la conexion del CONTROL
        script = _escribir(esc, "vs.py", (
            "import socket, sys\ns = socket.socket(40, socket.SOCK_STREAM)\n"
            f"s.connect((1, {puerto}))\n"))
        r = correr(esc, [script])
        assert r.returncode != 0 and "PermissionError" in r.stderr, r.stderr
        with pytest.raises(BlockingIOError):
            escucha.accept()
    finally:
        escucha.close()


_HEREDADOS = r'''
import json, os, socket, sys
D = json.loads(sys.argv[1]); R = {}
for n, fd in D["fds"].items():
    try:
        os.fstat(fd); R[n] = "ABIERTO"
    except OSError as e:
        R[n] = "EBADF" if e.errno == 9 else str(e.errno)
print(json.dumps(R))
'''


@necesita_estricto
def test_los_fds_heredados_se_cierran_en_el_hijo_estricto(esc, servidores):
    cli = socket.socket(); cli.connect(("127.0.0.1", servidores["datos"]["tcp"]))
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fichero = open(esc.secreto, "rb")
    fds = {"tcp": cli.fileno(), "udp": udp.fileno(), "fichero": fichero.fileno()}
    try:
        script = _escribir(esc, "fds.py", _HEREDADOS)
        argv = [sys.executable, script, json.dumps({"fds": fds})]
        control = subprocess.run(argv, cwd=esc.caja, env=esc.entorno, pass_fds=tuple(fds.values()),
                                 capture_output=True, text=True, timeout=60)
        assert set(json.loads(control.stdout).values()) == {"ABIERTO"}, control.stderr   # CONTROL
        r = subprocess.run(argv, cwd=esc.caja, env=esc.entorno, pass_fds=tuple(fds.values()),
                           preexec_fn=ais.preparar_estricto(esc.caja), capture_output=True, text=True,
                           timeout=60)
        assert json.loads(r.stdout) == {"tcp": "EBADF", "udp": "EBADF", "fichero": "EBADF"}, r.stderr
    finally:
        cli.close(); udp.close(); fichero.close()


def test_ejecutar_pruebas_no_pasa_fds_al_hijo():
    fuente = inspect.getsource(vf.ejecutar_pruebas)
    assert "pass_fds" not in fuente and "close_fds=False" not in fuente.replace(" ", "")


_SOLO_LANDLOCK = r'''
import json, os, socket, sys
D = json.loads(sys.argv[1]); R = {}
def t(n, f):
    try:
        f(); R[n] = "OK"
    except OSError as e:
        R[n] = e.errno
t("connect", lambda: socket.socket(fileno=D["tcp"]).connect(("127.0.0.1", D["puerto"])))
t("bind", lambda: socket.socket(fileno=D["tcp2"]).bind(("127.0.0.1", 0)))
t("udp_sendto", lambda: socket.socket(fileno=D["udp"]).sendto(b"x", ("127.0.0.1", D["pudp"])))
print(json.dumps(R))
'''


@necesita_estricto
def test_Landlock_red_aislado_un_socket_TCP_heredado_no_conecta_ni_hace_bind(esc, servidores):
    """Aisla Landlock-net de seccomp y de `close_range`: el socket lo crea el PADRE (seccomp no ve
    `socket()`) y se hereda con `pass_fds`. TCP => EACCES; UDP heredado: `sendto` PASA (Landlock no cubre
    UDP y seccomp no mira `sendto`): lo cierra `close_range` en el estricto completo (prueba anterior)."""
    import errno
    tcp = socket.socket(); tcp2 = socket.socket()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    d = {"tcp": tcp.fileno(), "tcp2": tcp2.fileno(), "udp": udp.fileno(),
         "puerto": servidores["datos"]["tcp"], "pudp": servidores["datos"]["udp"]}
    script = _escribir(esc, "ll.py", _SOLO_LANDLOCK)
    abi = ais.abi_disponible()
    lect = [*ais.rutas_estrictas(), esc.caja]

    def solo_landlock():
        ais._confinar_ficheros(lect, [esc.caja], abi, estricto=True, dispositivos=("/dev/null",),
                               listado=ais.listados_estrictos())
    try:
        argv = [sys.executable, script, json.dumps(d)]
        ctl = subprocess.run(argv, cwd=esc.caja, env=esc.entorno, pass_fds=tuple(d[k] for k in ("tcp", "tcp2", "udp")),
                             capture_output=True, text=True, timeout=60)
        assert json.loads(ctl.stdout) == {"connect": "OK", "bind": "OK", "udp_sendto": "OK"}, ctl.stderr
        servidores["tcp"].accept()                               # drena el control
        servidores["udp"].recvfrom(8)
        r = subprocess.run(argv, cwd=esc.caja, env=esc.entorno, pass_fds=tuple(d[k] for k in ("tcp", "tcp2", "udp")),
                           preexec_fn=solo_landlock, capture_output=True, text=True, timeout=60)
        res = json.loads(r.stdout)
        assert res["connect"] == errno.EACCES and res["bind"] == errno.EACCES, res
        assert res["udp_sendto"] == "OK", "documentado: Landlock no cubre UDP heredado"
        servidores["udp"].recvfrom(8)                            # el UDP heredado SI llega (limite)
        with pytest.raises(BlockingIOError):
            servidores["tcp"].accept()
    finally:
        tcp.close(); tcp2.close(); udp.close()


# ------------------------------------------------------------------ documentacion y bajo ==

def test_el_ancla_Limites_no_mitigados_existe_y_esta_enlazada():
    import autoconstruccion as ac
    assert "Limites no mitigados" in ais.__doc__
    seccion = ais.__doc__.split("Limites no mitigados", 1)[1]
    for tema in ("stat", "site-packages", "/dev/null", "socketpair", "x86_64", "cacheado", "delegacion"):
        assert tema in seccion, f"falta el limite {tema!r}"
    for modulo in (ac, review):
        assert "Limites no mitigados" in pathlib.Path(modulo.__file__).read_text(encoding="utf-8")


def test_los_controles_declarados_estan_acreditados_por_pruebas_de_ataque():
    """`controles` es DECLARATIVO (constante). Lo que lo acredita son estas pruebas de ataque."""
    acredita = {"landlock_lectura_minima": "test_la_lectura_FUERA_de_la_copia_esta_DENEGADA",
                "landlock_escritura_confinada": "test_la_escritura_fuera_de_la_copia_esta_denegada_y_dentro_permitida",
                "landlock_red_tcp": "test_Landlock_red_aislado_un_socket_TCP_heredado_no_conecta_ni_hace_bind",
                "landlock_scoped_senales": "test_el_confinado_no_puede_senalar_un_proceso_externo_pero_el_padre_si_puede_matar_al_hijo",
                "landlock_scoped_unix_abstracto": "test_la_red_esta_denegada_en_el_proceso_su_hijo_y_su_nieto",
                "seccomp_red": "test_H1_H2_H3_vsock_bluetooth_sysv_y_metadatos_denegados",
                "seccomp_io_uring": "test_la_red_esta_denegada_en_el_proceso_su_hijo_y_su_nieto",
                "seccomp_arquitectura": "test_H1_H2_H3_vsock_bluetooth_sysv_y_metadatos_denegados",
                "no_new_privs": "test_el_confinador_estricto_declara_TODOS_los_controles",
                "rlimits": "test_el_confinador_estricto_declara_TODOS_los_controles"}
    assert set(acredita) == set(ais.CONTROLES_ESTRICTOS)
    for prueba in acredita.values():
        assert prueba in globals(), prueba
    assert "DECLARATIVO" in ais.__doc__


def test_listados_estrictos_compara_rutas_no_prefijos_de_texto():
    assert "is_relative_to" in inspect.getsource(ais.listados_estrictos)
    assert "startswith" not in inspect.getsource(ais.listados_estrictos)


def test_el_sondeo_cacheado_incluye_firma_de_los_directorios_de_paquetes():
    assert "firma" in inspect.signature(ais._sondeo).parameters


# ================================================== SUPERVIVIENTES DE LA MUTACION (2026-10-23) ==
# Cada prueba lleva su CONTROL (sin confinar el intento SI funciona) y mata un mutante concreto.

_MQ = r'''
import ctypes, errno, json
libc = ctypes.CDLL(None, use_errno=True)
nombre = ctypes.c_char_p(__import__("sys").argv[1].encode())
r = libc.syscall(240, nombre, 0o102, 0o600, None)           # mq_open(O_CREAT|O_RDWR)
e = ctypes.get_errno()
if r >= 0:
    libc.syscall(241, nombre)                                # mq_unlink
print(json.dumps({"ret": r, "errno": errno.errorcode.get(e, e) if r < 0 else None}))
'''


@necesita_estricto
def test_mq_open_POSIX_denegada_en_el_estricto_y_permitida_sin_confinar(esc):
    nombre = "aura-mq-" + secrets.token_hex(6)
    script = _escribir(esc, "mq.py", _MQ)
    ctl = subprocess.run([sys.executable, script, nombre], cwd=esc.caja, env=esc.entorno,
                         capture_output=True, text=True, timeout=60)
    if json.loads(ctl.stdout)["ret"] < 0:
        pytest.skip("este kernel no permite mq_open ni sin confinar")
    try:
        r = correr(esc, [script, nombre])
        assert json.loads(r.stdout) == {"ret": -1, "errno": "EPERM"}, (r.stdout, r.stderr)
    finally:
        ctypes.CDLL(None).syscall(241, ctypes.c_char_p(nombre.encode()))


_X32 = r'''
import ctypes
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall(0x40000000 + 39)                                # getpid con el bit x32
print("VIVO")
'''


@necesita_estricto
def test_una_syscall_x32_mata_al_proceso_confinado_y_sin_confinar_no(esc):
    script = _escribir(esc, "x32.py", _X32)
    ctl = subprocess.run([sys.executable, script], cwd=esc.caja, env=esc.entorno,
                         capture_output=True, text=True, timeout=60)
    assert ctl.returncode == 0 and "VIVO" in ctl.stdout, ctl.stderr          # CONTROL
    r = correr(esc, [script])
    assert r.returncode == -signal.SIGSYS and "VIVO" not in r.stdout, (r.returncode, r.stderr)


_INT80 = r'''
import ctypes, mmap
m = mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
m.write(bytes([0xB8, 0x14, 0, 0, 0, 0xCD, 0x80, 0xC3]))      # mov eax,20 (getpid i386); int 0x80; ret
dir_ = ctypes.addressof(ctypes.c_char.from_buffer(m))
ctypes.CFUNCTYPE(ctypes.c_int)(dir_)()
print("VIVO")
'''


@necesita_estricto
def test_una_syscall_de_otra_arquitectura_int80_mata_al_proceso_confinado(esc):
    script = _escribir(esc, "int80.py", _INT80)
    ctl = subprocess.run([sys.executable, script], cwd=esc.caja, env=esc.entorno,
                         capture_output=True, text=True, timeout=60)
    if ctl.returncode != 0 or "VIVO" not in ctl.stdout:
        pytest.skip("este kernel no emula int 0x80 (IA32_EMULATION): no hay arquitectura alterna que probar")
    r = correr(esc, [script])
    assert r.returncode == -signal.SIGSYS and "VIVO" not in r.stdout, (r.returncode, r.stderr)


_ABSTRACTO_HEREDADO = r'''
import json, socket, sys
D = json.loads(sys.argv[1])
try:
    socket.socket(fileno=D["fd"]).connect("\0" + D["abs"]); print("OK")
except OSError as e:
    print(e.errno)
'''


@necesita_estricto
def test_Landlock_scoped_aislado_un_socket_unix_ABSTRACTO_heredado_no_conecta(esc, servidores):
    """Aisla `ABSTRACT_UNIX_SOCKET` de seccomp: el socket AF_UNIX lo crea el PADRE y se hereda; solo se
    aplica Landlock (sin seccomp ni close_range). Control: sin confinar conecta."""
    import errno
    cli = socket.socket(socket.AF_UNIX)
    datos = {"fd": cli.fileno(), "abs": servidores["datos"]["abs"]}
    script = _escribir(esc, "abs.py", _ABSTRACTO_HEREDADO)
    abi = ais.abi_disponible()
    lect = [*ais.rutas_estrictas(), esc.caja]

    def solo_landlock():
        ais._confinar_ficheros(lect, [esc.caja], abi, estricto=True, dispositivos=("/dev/null",),
                               listado=ais.listados_estrictos())
    try:
        argv = [sys.executable, script, json.dumps(datos)]
        ctl = subprocess.run(argv, cwd=esc.caja, env=esc.entorno, pass_fds=(cli.fileno(),),
                             capture_output=True, text=True, timeout=60)
        assert ctl.stdout.strip() == "OK", ctl.stderr                        # CONTROL
        servidores["abs"].accept()
        cli2 = socket.socket(socket.AF_UNIX)
        datos["fd"] = cli2.fileno()
        try:
            r = subprocess.run([sys.executable, script, json.dumps(datos)], cwd=esc.caja, env=esc.entorno,
                               pass_fds=(cli2.fileno(),), preexec_fn=solo_landlock, capture_output=True,
                               text=True, timeout=60)
            assert r.stdout.strip() == str(errno.EPERM), (r.stdout, r.stderr)
            with pytest.raises(BlockingIOError):
                servidores["abs"].accept()
        finally:
            cli2.close()
    finally:
        cli.close()


_LISTA = r'''
import json, os, sys
R = {}
for ruta in json.loads(sys.argv[1]):
    try:
        os.listdir(ruta); R[ruta] = "OK"
    except OSError as e:
        R[ruta] = type(e).__name__
print(json.dumps(R))
'''


@necesita_estricto
def test_el_HOME_real_no_se_puede_listar_en_el_estricto(esc):
    home = os.path.expanduser("~")
    script = _escribir(esc, "ls.py", _LISTA)
    ctl = subprocess.run([sys.executable, script, json.dumps([home])], cwd=esc.caja, env=esc.entorno,
                         capture_output=True, text=True, timeout=60)
    assert json.loads(ctl.stdout) == {home: "OK"}, ctl.stderr                # CONTROL
    r = correr(esc, [script, json.dumps([home])])
    assert json.loads(r.stdout) == {home: "PermissionError"}, r.stderr


def test_un_fallo_al_aplicar_el_confinamiento_en_el_hijo_se_VE_en_el_padre(esc, monkeypatch):
    """Si `close_range` cerrara YA (flags=0) el pipe de error de `subprocess`, un fallo posterior en el
    hijo moriria sin informar y el padre lo leeria como exito."""
    def boom(*a, **k):
        raise OSError(5, "fallo simulado al aplicar Landlock")
    confinar = ais.preparar_estricto(esc.caja)
    monkeypatch.setattr(ais, "_confinar_ficheros", boom)
    with pytest.raises((subprocess.SubprocessError, OSError)):
        subprocess.run([sys.executable, "-c", "print(1)"], cwd=esc.caja, env=esc.entorno,
                       preexec_fn=confinar, capture_output=True, text=True, timeout=60)


def test_review_no_acepta_completo_False_aunque_declare_todos_los_controles(tmp_path, monkeypatch):
    real, contrato = _contrato(tmp_path)

    def falso():
        return None
    falso.abi, falso.completo = 6, False
    falso.controles = {c: True for c in ais.CONTROLES_ESTRICTOS}
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: falso)
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a))
    r = review._verificador_de_review(contrato, real)(real)
    assert llamadas == [] and r.estado == "sin_confinamiento" and r.confinada is False, r


def test_cambiar_la_firma_del_sondeo_provoca_un_re_sondeo_y_sin_cambio_no(tmp_path, monkeypatch):
    import site
    paquetes = tmp_path / "sp"
    paquetes.mkdir()
    monkeypatch.setattr(site, "getsitepackages", lambda: [str(paquetes)])
    monkeypatch.setattr(site, "getusersitepackages", lambda: str(tmp_path / "no-existe"))
    ais._sondeo_cacheado.cache_clear()
    lanzados = []

    class _R:
        stdout = json.dumps({"mapas": [], "paquetes": [], "stdlib": [], "exe": "x"})

    monkeypatch.setattr(ais.subprocess, "run", lambda *a, **k: (lanzados.append(1), _R())[1])
    try:
        ais._sondeo("/ejecutable/falso"); ais._sondeo("/ejecutable/falso")
        assert len(lanzados) == 1, "sin cambios la cache debe servir"
        os.utime(paquetes, ns=(1_000_000_000, 1_000_000_000))                # el directorio cambia
        ais._sondeo("/ejecutable/falso")
        assert len(lanzados) == 2, "un cambio en site-packages debe invalidar el sondeo cacheado"
    finally:
        ais._sondeo_cacheado.cache_clear()


def test_listados_estrictos_no_confunde_lib_con_lib2_por_prefijo(tmp_path, monkeypatch):
    std = tmp_path / "a" / "lib"
    hermano = tmp_path / "a" / "lib2"
    std.mkdir(parents=True); hermano.mkdir(parents=True)
    monkeypatch.setattr(ais, "_sondeo", lambda *_a, **_k: {"stdlib": [str(std)],
                                                           "paquetes": [str(hermano / "pk")]})
    assert ais.listados_estrictos() == (str(hermano),), "lib2 NO es subruta de lib: debe concederse el listado"


def test_review_no_acepta_controles_incompletos_aunque_completo_sea_True(tmp_path, monkeypatch):
    real, contrato = _contrato(tmp_path)

    def falso():
        return None
    falso.abi, falso.completo = 6, True
    falso.controles = {c: (c != "seccomp_red") for c in ais.CONTROLES_ESTRICTOS}
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: falso)
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a))
    r = review._verificador_de_review(contrato, real)(real)
    assert llamadas == [] and r.estado == "sin_confinamiento" and r.confinada is False, r
    assert "seccomp_red" in r.detalle if hasattr(r, "detalle") else True


_RLIM = r'''
import json, resource
print(json.dumps({n: list(resource.getrlimit(getattr(resource, n))) for n in ("RLIMIT_AS", "RLIMIT_FSIZE", "RLIMIT_CPU")}))
'''


@necesita_estricto
def test_el_estricto_aplica_los_rlimits_EXACTOS_blando_y_duro_al_hijo(esc):
    # AE-M26: la version anterior comparaba con `<=` y RLIM_INFINITY es -1 en Python: `-1 <= X` siempre es
    # verdad, asi que quitar los rlimits no rompia nada. Ahora se exige IGUALDAD con las constantes.
    import resource as _r
    constantes = {"RLIMIT_CPU": ais.LIMITE_CPU_S, "RLIMIT_AS": ais.LIMITE_MEMORIA_BYTES,
                  "RLIMIT_FSIZE": ais.LIMITE_FICHERO_BYTES}
    esperado = {}
    for nombre, valor in constantes.items():             # `_limitar_recursos`: min(constante, duro heredado)
        duro = _r.getrlimit(getattr(_r, nombre))[1]
        esperado[nombre] = [valor if duro == _r.RLIM_INFINITY else min(valor, duro)] * 2
    script = _escribir(esc, "rl.py", _RLIM)
    ctl = subprocess.run([sys.executable, script], cwd=esc.caja, env=esc.entorno, capture_output=True,
                         text=True, timeout=60)
    ctl_v = json.loads(ctl.stdout)
    if any(ctl_v[k] == esperado[k] for k in esperado):
        pytest.skip(f"el entorno ya trae limites duros <= las constantes (ulimit -H): el control no discrimina {ctl_v}")
    r = correr(esc, [script])
    assert json.loads(r.stdout) == esperado, (r.stdout, r.stderr)


# ================================================================ RONDA PROMPT 05 (seguridad) ==

_KEYS = r'''
import ctypes, errno, json, sys
D = json.loads(sys.argv[1]); R = {}
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
def sc(*a):
    r = libc.syscall(*a)
    return r, ctypes.get_errno()
def leer():
    buf = ctypes.create_string_buffer(64)
    r, e = sc(250, 11, D["serial"], buf, 64)               # keyctl(KEYCTL_READ)
    return errno.errorcode.get(e, e) if r < 0 else "LEIDO:" + buf.raw[:r].decode()
def anadir():
    r, e = sc(248, b"user", D["intruso"].encode(), b"x", 1, -3)  # add_key
    return errno.errorcode.get(e, e) if r < 0 else "OK"
def pedir():
    r, e = sc(249, b"user", D["intruso"].encode(), None, 0)      # request_key
    return errno.errorcode.get(e, e) if r < 0 else "OK"
print(json.dumps({"keyctl_read": leer(), "add_key": anadir(), "request_key": pedir()}))
'''


@pytest.fixture
def clave_propia():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    desc = b"aura-p05-" + secrets.token_hex(6).encode()
    serial = libc.syscall(248, b"user", desc, b"SECRETO-KEYRING", 15, -3)       # keyring de sesion
    if serial < 0:
        pytest.skip(f"este equipo no ofrece keyring de sesion (errno {ctypes.get_errno()})")
    intruso = "aura-p05-intruso-" + secrets.token_hex(6)
    yield serial, intruso
    libc.syscall(250, 3, serial)                                                 # KEYCTL_REVOKE
    libc.syscall(250, 21, serial, -3)                                            # KEYCTL_UNLINK
    ajeno = libc.syscall(250, 10, -3, b"user", intruso.encode(), 0)              # KEYCTL_SEARCH (por si el control la creo)
    if ajeno > 0:
        libc.syscall(250, 3, ajeno)
        libc.syscall(250, 21, ajeno, -3)


def _correr_keys(esc, clave, confinado):
    serial, intruso = clave
    script = _escribir(esc, "keys.py", _KEYS)
    datos = json.dumps({"serial": serial, "intruso": intruso})
    if confinado:
        return correr(esc, [script, datos])
    return subprocess.run([sys.executable, script, datos], cwd=esc.caja, env=esc.entorno,
                          capture_output=True, text=True, timeout=60)


@necesita_estricto
def test_keyring_el_hijo_estricto_no_lee_ni_anade_claves_y_el_CONTROL_si(esc, clave_propia):
    ctl = json.loads(_correr_keys(esc, clave_propia, False).stdout)
    assert ctl["keyctl_read"] == "LEIDO:SECRETO-KEYRING" and ctl["add_key"] == "OK", ctl   # CONTROL
    r = _correr_keys(esc, clave_propia, True)
    res = json.loads(r.stdout)
    assert res == {"keyctl_read": "EPERM", "add_key": "EPERM", "request_key": "EPERM"}, (res, r.stderr)
    assert "SECRETO" not in r.stdout


_XATTR = r'''
import errno, json, os, sys
D = json.loads(sys.argv[1]); R = {}
def t(n, f):
    try:
        f(); R[n] = "OK"
    except OSError as e:
        R[n] = errno.errorcode.get(e.errno, str(e.errno))
t("setxattr", lambda: os.setxattr(D["a"], "user.aura", b"1"))
t("lsetxattr", lambda: os.setxattr(D["a"], "user.aura", b"1", follow_symlinks=False))
t("fsetxattr", lambda: os.setxattr(0, "user.aura", b"1"))            # fd 0 = fichero externo A (heredado)
t("removexattr", lambda: os.removexattr(D["b1"], "user.aura"))
t("lremovexattr", lambda: os.removexattr(D["b2"], "user.aura", follow_symlinks=False))
t("fremovexattr", lambda: os.removexattr(2, "user.aura"))             # fd 2 = fichero externo B3 (heredado)
print(json.dumps(R))
'''


def _xattr_ficheros(esc, nombre):
    f = {}
    for k in ("a", "b1", "b2", "b3"):
        f[k] = esc.fuera / f"{nombre}-{k}.txt"
        f[k].write_text("x", encoding="utf-8")
    try:
        for k in ("b1", "b2", "b3"):
            os.setxattr(f[k], "user.aura", b"0")
    except OSError:
        pytest.skip("el sistema de ficheros del temporal no admite xattr de usuario")
    return f


def _correr_xattr(esc, f, confinado):
    script = _escribir(esc, "xa.py", _XATTR)
    datos = json.dumps({k: str(v) for k, v in f.items()})
    with open(f["a"], "rb") as fa, open(f["b3"], "rb") as fb:
        kw = dict(cwd=esc.caja, env=esc.entorno, stdin=fa, stdout=subprocess.PIPE, stderr=fb, timeout=60)
        if confinado:
            return subprocess.run([sys.executable, script, datos], preexec_fn=ais.preparar_estricto(esc.caja), **kw)
        return subprocess.run([sys.executable, script, datos], **kw)


@necesita_estricto
def test_xattr_el_hijo_estricto_no_pone_ni_quita_atributos_de_ficheros_externos(esc):
    f = _xattr_ficheros(esc, "e")
    r = _correr_xattr(esc, f, True)
    res = json.loads(r.stdout)
    assert res == {k: "EPERM" for k in res} and len(res) == 6, (res, r.stderr)
    assert os.listxattr(f["a"]) == [], "el hijo estricto puso un atributo en un fichero externo"
    for k in ("b1", "b2", "b3"):
        assert os.getxattr(f[k], "user.aura") == b"0", f"el hijo estricto quito el atributo de {k}"


@necesita_estricto
def test_xattr_CONTROL_sin_confinar_los_mismos_intentos_si_funcionan(esc):
    f = _xattr_ficheros(esc, "c")
    r = _correr_xattr(esc, f, False)
    res = json.loads(r.stdout)
    assert res == {k: "OK" for k in res} and len(res) == 6, (res, r.stderr)
    assert os.getxattr(f["a"], "user.aura") == b"1"
    for k in ("b1", "b2", "b3"):
        assert os.listxattr(f[k]) == [], f"el control no quito el atributo de {k}"


_SHUTIL = r'''
import errno, json, os, pathlib, shutil, sys
caja = pathlib.Path(sys.argv[1]); R = {}
(caja / "origen.txt").write_text("hola")
(caja / "dir").mkdir(exist_ok=True); (caja / "dir" / "f.txt").write_text("f")
def t(n, f):
    try:
        f(); R[n] = "OK"
    except PermissionError:
        R[n] = "PermissionError"
    except shutil.Error as e:                              # copytree agrega los fallos por fichero
        R[n] = "PermissionError" if "Operation not permitted" in repr(e) else "EXC:" + repr(e)
    except Exception as e:
        R[n] = "EXC:" + repr(e)
t("copyfile", lambda: shutil.copyfile(caja / "origen.txt", caja / "d_copyfile.txt"))
t("copy", lambda: shutil.copy(caja / "origen.txt", caja / "d_copy.txt"))
t("copy2", lambda: shutil.copy2(caja / "origen.txt", caja / "d_copy2.txt"))
t("copytree", lambda: shutil.copytree(caja / "dir", caja / "d_tree"))
print(json.dumps(R))
'''


@necesita_estricto
def test_shutil_copy_copy2_copytree_fallan_en_el_estricto_y_copyfile_funciona(esc):
    # FIJA un limite DECLARADO (docstring, «Limites no mitigados»): cerrar chmod/utime rompe copymode/copystat.
    script = _escribir(esc, "sh.py", _SHUTIL)
    ctl = subprocess.run([sys.executable, script, str(esc.caja)], cwd=esc.caja, env=esc.entorno,
                         capture_output=True, text=True, timeout=60)
    assert json.loads(ctl.stdout) == {k: "OK" for k in ("copyfile", "copy", "copy2", "copytree")}, ctl.stdout
    for f in esc.caja.glob("d_*"):                       # limpia el control para el caso confinado
        shutil_rm = __import__("shutil")
        shutil_rm.rmtree(f) if f.is_dir() else f.unlink()
    r = correr(esc, [script, str(esc.caja)])
    assert json.loads(r.stdout) == {"copyfile": "OK", "copy": "PermissionError", "copy2": "PermissionError",
                                    "copytree": "PermissionError"}, (r.stdout, r.stderr)


def test_el_docstring_declara_el_limite_de_shutil_y_el_cierre_de_keyring_y_xattr():
    doc = ais.__doc__
    assert "shutil.copy" in doc and "copytree" in doc and "PermissionError" in doc
    assert "add_key" in doc and "xattr" in doc
    assert "prlimit64" in doc and "inotify" in doc and "sched_setaffinity" in doc and "setpriority" in doc


# ================================================================ RONDA PROMPT 06 (seguridad) ==

_PRLIM = r"""
import ctypes, errno, json, resource, sys
D = json.loads(sys.argv[1]); R = {}
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
class RL(ctypes.Structure):
    _fields_ = [("cur", ctypes.c_ulonglong), ("max", ctypes.c_ulonglong)]
def pr(pid, nuevo=True):
    nl = RL(12345, 12345)
    r = libc.syscall(302, ctypes.c_long(pid), resource.RLIMIT_CORE, ctypes.byref(nl) if nuevo else None,
                     ctypes.byref(RL()))
    return "OK" if r == 0 else errno.errorcode.get(ctypes.get_errno(), ctypes.get_errno())
R["otro_pid_escribir"] = pr(D["victima"])
R["otro_pid_leer"] = pr(D["victima"], False)
R["pid_con_bits_altos"] = pr(1 << 32, False)
R["pid_cero_leer"] = pr(0, False)
try:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); R["setrlimit_propio"] = "OK"
except OSError as e:
    R["setrlimit_propio"] = errno.errorcode.get(e.errno, e.errno)
print(json.dumps(R))
"""


def _victima():
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)   # su propio grupo: PRIO_PGRP no toca al runner


@pytest.fixture
def victima():
    v = _victima()
    time.sleep(0.3)
    yield v
    v.kill()
    v.wait()


def _limite_core(pid):
    for linea in open(f"/proc/{pid}/limits"):
        if linea.startswith("Max core file size"):
            return linea.split()[4:6]


def _lanzar(esc, script, datos, confinado):
    argv = [sys.executable, script, json.dumps(datos)]
    if confinado:
        return correr(esc, argv[1:])
    return subprocess.run(argv, cwd=esc.caja, env=esc.entorno, capture_output=True, text=True, timeout=60)


@necesita_estricto
def test_prlimit64_sobre_OTRO_pid_da_EPERM_y_la_victima_no_cambia_pero_el_propio_funciona(esc, victima):
    script = _escribir(esc, "pr.py", _PRLIM)
    antes = _limite_core(victima.pid)
    r = _lanzar(esc, script, {"victima": victima.pid}, True)
    res = json.loads(r.stdout)
    assert res == {"otro_pid_escribir": "EPERM", "otro_pid_leer": "EPERM", "pid_con_bits_altos": "EPERM",
                   "pid_cero_leer": "OK", "setrlimit_propio": "OK"}, (res, r.stderr)
    assert victima.poll() is None and _limite_core(victima.pid) == antes, "la victima fue alterada"


@necesita_estricto
def test_prlimit64_CONTROL_sin_confinar_si_altera_a_la_victima(esc, victima):
    script = _escribir(esc, "pr.py", _PRLIM)
    res = json.loads(_lanzar(esc, script, {"victima": victima.pid}, False).stdout)
    assert res["otro_pid_escribir"] == res["otro_pid_leer"] == res["pid_con_bits_altos"] == "OK", res
    assert _limite_core(victima.pid) == ["12345", "12345"]


_PLANIF = r"""
import ctypes, errno, json, os, sys
D = json.loads(sys.argv[1]); R = {}
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
def t(n, f):
    try:
        f(); R[n] = "OK"
    except OSError as e:
        R[n] = errno.errorcode.get(e.errno, str(e.errno))
def attr(pid):
    buf = ctypes.create_string_buffer(48); ctypes.c_uint32.from_buffer(buf).value = 48
    ctypes.c_int32.from_buffer(buf, 16).value = 7                    # sched_nice
    if libc.syscall(314, ctypes.c_long(pid), buf, 0) != 0:
        raise OSError(ctypes.get_errno(), "sched_setattr")
V = D["victima"]
for sufijo, pid in (("_ajeno", V), ("_propio", 0)):
    t("setpriority" + sufijo, lambda: os.setpriority(os.PRIO_PROCESS, pid, 7))
    t("sched_setaffinity" + sufijo, lambda: os.sched_setaffinity(pid, {D["cpu"]}))
    t("sched_setscheduler" + sufijo, lambda: os.sched_setscheduler(pid, os.SCHED_BATCH, os.sched_param(0)))
    t("sched_setparam" + sufijo, lambda: os.sched_setparam(pid, os.sched_param(0)))
    t("sched_setattr" + sufijo, lambda: attr(pid))
t("setpriority_grupo_ajeno", lambda: os.setpriority(os.PRIO_PGRP, V, 7))
print(json.dumps(R))
"""

_PLANIF_ESPERADO_CONFINADO = {
    "setpriority_ajeno": "EPERM", "sched_setaffinity_ajeno": "EPERM", "sched_setscheduler_ajeno": "EPERM",
    "sched_setparam_ajeno": "EPERM", "sched_setattr_ajeno": "EPERM",
    "setpriority_propio": "OK", "sched_setaffinity_propio": "OK", "sched_setscheduler_propio": "OK",
    "sched_setparam_propio": "OK", "sched_setattr_propio": "OK",
    "setpriority_grupo_ajeno": "EPERM"}


@necesita_estricto
def test_planificacion_y_prioridad_de_un_proceso_ajeno_dan_EPERM_y_la_del_propio_funciona(esc, victima):
    script = _escribir(esc, "pl.py", _PLANIF)
    prio = os.getpriority(os.PRIO_PROCESS, victima.pid)
    afin = os.sched_getaffinity(victima.pid)
    cpu = sorted(afin)[0]
    r = _lanzar(esc, script, {"victima": victima.pid, "cpu": cpu}, True)
    assert json.loads(r.stdout) == _PLANIF_ESPERADO_CONFINADO, (r.stdout, r.stderr)
    assert os.getpriority(os.PRIO_PROCESS, victima.pid) == prio and os.sched_getaffinity(victima.pid) == afin
    assert os.sched_getscheduler(victima.pid) == os.SCHED_OTHER


@necesita_estricto
def test_planificacion_CONTROL_sin_confinar_si_altera_al_proceso_ajeno(esc, victima):
    script = _escribir(esc, "pl.py", _PLANIF)
    cpu = sorted(os.sched_getaffinity(victima.pid))[0]
    res = json.loads(_lanzar(esc, script, {"victima": victima.pid, "cpu": cpu}, False).stdout)
    assert all(res[k] == "OK" for k in res if k.endswith("_ajeno")), res
    assert os.getpriority(os.PRIO_PROCESS, victima.pid) == 7


_INOTIFY = r"""
import ctypes, errno, json, sys
D = json.loads(sys.argv[1]); R = {}
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
def e():
    return errno.errorcode.get(ctypes.get_errno(), ctypes.get_errno())
fd1 = libc.syscall(294, 0)                                          # inotify_init1
R["inotify_init1"] = "OK" if fd1 >= 0 else e()
fd0 = libc.syscall(253)                                             # inotify_init
R["inotify_init"] = "OK" if fd0 >= 0 else e()
w = libc.syscall(254, fd1 if fd1 >= 0 else 0, D["dir"].encode(), 0x2)  # inotify_add_watch(IN_MODIFY)
R["inotify_add_watch"] = "OK" if w >= 0 else e()
print(json.dumps(R))
"""


@necesita_estricto
def test_inotify_esta_cerrado_en_el_estricto_y_el_CONTROL_sin_confinar_si_vigila(esc):
    script = _escribir(esc, "ino.py", _INOTIFY)
    ctl = json.loads(_lanzar(esc, script, {"dir": str(esc.fuera)}, False).stdout)
    assert ctl == {"inotify_init1": "OK", "inotify_init": "OK", "inotify_add_watch": "OK"}, ctl
    r = _lanzar(esc, script, {"dir": str(esc.fuera)}, True)
    assert json.loads(r.stdout) == {k: "EPERM" for k in ctl}, (r.stdout, r.stderr)
