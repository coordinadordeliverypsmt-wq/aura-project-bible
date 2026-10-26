"""Ciclo de vida del arnés de mutación: interrupciones, timeouts y descendientes (2026-10-06).

Defecto observado `[EJEC]`: el arnés recibió SIGTERM de un `timeout` externo y murió sin ejecutar su
`finally`. Un fichero de código quedó MUTADO y el pytest del mutante —en su propia sesión, así que la señal no
le llegaba— siguió 48 min huérfano (ppid 1). Además, un descendiente que abría SU PROPIA sesión sobrevivía
también al `killpg` del timeout. Mientras tanto, `orquestador.mutacion_en_curso()` veía «no hay arnés» porque
el huérfano no lleva la marca `herramientas.mutar` en su línea de órdenes.

Mini-proyecto de juguete en `tmp_path`, como en `test_arnes_mutacion.py`. Cada proceso auxiliar lleva una
duración ÚNICA en su orden (marca) y se comprueba por PID + marca —nunca por patrón—. Toda prueba mata al final
lo que haya quedado vivo: si una garantía falla, la prueba falla sin dejar procesos.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from herramientas.mutar import ejecutar


@pytest.fixture(autouse=True)
def _copias_aisladas_en_el_tmp_de_pytest(tmp_path_factory, monkeypatch):
    """Las copias aisladas del arnés (regla 6) caen en el tmp de pytest, que pytest retira, y no en el /tmp del
    sistema. Medido 2026-10-25: al mutar el propio arnés, los mutantes que desactivan su limpieza (A3, AL-M8)
    dejaban ~30 copias de juguete en /tmp por ejecución. Directorio HERMANO del proyecto de juguete, nunca hijo
    (la guarda «copia dentro del proyecto» lo rechazaría). TMPDIR también para el arnés lanzado en subproceso."""
    import tempfile

    destino = tmp_path_factory.mktemp("copias-del-arnes")
    monkeypatch.setenv("TMPDIR", str(destino))
    monkeypatch.setattr(tempfile, "tempdir", str(destino))


_MARCA_HIJO = "time.sleep(41.25)"  # hijo en la sesión de pytest
_MARCA_NIETO = "time.sleep(41.75)"  # nieto que abre SU PROPIA sesión: escapa a killpg


def _crear_proyecto(tmp_path: Path) -> Path:
    """El mutante cuelga para siempre tras lanzar un hijo y un nieto en sesión propia y anotar sus PID.

    La ejecución base (sin mutar) NO lanza nada: así `pids.txt` solo existe cuando corre el mutante y la prueba
    interrumpe en el momento justo, no en la ejecución base (versión anterior: prueba vacua). La ruta es ABSOLUTA: el
    arnés ejecuta pytest en una copia aislada (2026-10-25), y una ruta relativa caería dentro de la copia."""
    modulo = tmp_path / "modulo_vida.py"
    modulo.write_text(
        textwrap.dedent(
            f"""\
            import subprocess
            import sys
            from pathlib import Path


            def condicion_de_parada():
                return True


            def trabajo():
                if condicion_de_parada():
                    return "listo"
                # Solo el MUTANTE llega aquí: la ejecución base no lanza nada ni anota PID.
                hijo = subprocess.Popen([sys.executable, "-c", "import time; {_MARCA_HIJO}"])
                nieto = subprocess.Popen([sys.executable, "-c", "import time; {_MARCA_NIETO}"], start_new_session=True)
                Path({str(tmp_path / "pids.txt")!r}).write_text(f"{{hijo.pid}} {{nieto.pid}}")
                while True:
                    pass
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_modulo_vida.py").write_text(
        "from modulo_vida import trabajo\n\n\ndef test_trabajo_termina():\n    assert trabajo() == 'listo'\n",
        encoding="utf-8",
    )
    return modulo


def _toml(tmp_path: Path, timeout_s: float) -> Path:
    ruta = tmp_path / "mutaciones.toml"
    ruta.write_text(
        textwrap.dedent(
            f"""\
            incremento = "juguete: ciclo de vida del arnes"
            pruebas = ["tests/test_modulo_vida.py"]
            timeout_s = {timeout_s}

            [[mutante]]
            id = "V1"
            garantia = "la condicion de parada deja de parar"
            fichero = "modulo_vida.py"
            buscar = "return True"
            sustituir = "return False"
            """
        ),
        encoding="utf-8",
    )
    return ruta


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


def _vivo(pid: int, marca: str) -> bool:
    """Vivo y SIGUE siendo el mismo proceso (la marca descarta un PID reutilizado). Un zombi no cuenta."""
    try:
        estado = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return estado != "Z" and marca in _cmdline(pid)


def _matar_si_vivo(pid: int, marca: str) -> None:
    if _vivo(pid, marca):
        os.kill(pid, signal.SIGKILL)


def _esperar_pids(tmp_path: Path, limite_s: float = 20) -> tuple[int, int]:
    fichero = tmp_path / "pids.txt"
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite_s:
        if fichero.exists() and fichero.read_text().strip():
            a, b = fichero.read_text().split()
            return int(a), int(b)
        time.sleep(0.05)
    raise AssertionError("el mutante no llegó a arrancar sus procesos")


def _esperar_muerte(pid: int, marca: str, limite_s: float = 5) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite_s:
        if not _vivo(pid, marca):
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def senuelo():
    """Proceso AJENO al arnés, con su propia marca: la limpieza no puede tocarlo."""
    marca = "time.sleep(43.5)"
    proceso = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    yield proceso.pid, marca
    proceso.kill()
    proceso.wait()


# ----------------------------------------------------------------------- timeout --


def test_el_timeout_mata_tambien_al_descendiente_que_abrio_su_propia_sesion(tmp_path, senuelo):
    _crear_proyecto(tmp_path)
    toml = _toml(tmp_path, timeout_s=8)
    hijo = nieto = None
    try:
        resultado = ejecutar(str(toml), raiz=str(tmp_path))
        hijo, nieto = _esperar_pids(tmp_path, limite_s=1)

        assert resultado.timeouts == 1
        assert _esperar_muerte(hijo, _MARCA_HIJO), "el hijo de pytest sobrevivió al timeout"
        assert _esperar_muerte(nieto, _MARCA_NIETO), "el nieto en sesión propia sobrevivió al timeout"
        assert _vivo(*senuelo), "la limpieza mató un proceso ajeno al arnés"
    finally:
        if hijo:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)


# ------------------------------------------------- interrupción en la biblioteca --


def test_una_interrupcion_restaura_el_fichero_y_no_deja_descendientes(tmp_path, senuelo):
    modulo = _crear_proyecto(tmp_path)
    original = modulo.read_bytes()
    toml = _toml(tmp_path, timeout_s=60)
    pids: list[tuple[int, int]] = []
    pytests: list[tuple[int, str]] = []

    def _interrumpir_cuando_arranque():
        try:
            pids.append(_esperar_pids(tmp_path))
            # El pytest del mutante es hijo de ESTE proceso: se anota para comprobarlo y, si falla, limpiarlo.
            pytests.extend((p, _cmdline(p)) for p in _descendientes(os.getpid()) if "test_modulo_vida" in _cmdline(p))
            os.kill(os.getpid(), signal.SIGUSR1)
        except AssertionError:
            pass

    anterior = signal.signal(signal.SIGUSR1, lambda *_a: (_ for _ in ()).throw(KeyboardInterrupt()))
    threading.Thread(target=_interrumpir_cuando_arranque, daemon=True).start()
    try:
        t0 = time.monotonic()
        with pytest.raises(KeyboardInterrupt):
            ejecutar(str(toml), raiz=str(tmp_path))
        assert time.monotonic() - t0 < 30
        assert pids, "el mutante no arrancó"
        hijo, nieto = pids[0]

        assert modulo.read_bytes() == original, "el fichero quedó mutado tras la interrupción"
        assert pytests, "no se encontró el pytest del mutante"
        assert all(_esperar_muerte(p, linea) for p, linea in pytests), "el pytest del mutante quedó huérfano"
        assert _esperar_muerte(hijo, _MARCA_HIJO), "el hijo de pytest siguió vivo tras interrumpir el arnés"
        assert _esperar_muerte(nieto, _MARCA_NIETO), "el nieto en sesión propia siguió vivo"
        assert _vivo(*senuelo), "la limpieza mató un proceso ajeno al arnés"
    finally:
        signal.signal(signal.SIGUSR1, anterior)
        for p, linea in pytests:
            _matar_si_vivo(p, linea)
        for hijo, nieto in pids:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)


# ------------------------------------------------------- SIGTERM al proceso CLI --


def _descendientes(pid: int) -> list[int]:
    hijos: dict[int, list[int]] = {}
    for entrada in os.listdir("/proc"):
        if entrada.isdigit():
            try:
                ppid = int(Path(f"/proc/{entrada}/stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                continue
            hijos.setdefault(ppid, []).append(int(entrada))
    todos, pendientes = [], [pid]
    while pendientes:
        for h in hijos.get(pendientes.pop(), []):
            todos.append(h)
            pendientes.append(h)
    return todos


def test_sigterm_al_arnes_restaura_el_fichero_y_termina_todo_su_arbol(tmp_path, senuelo):
    """El caso real: `timeout` o un operador mandan SIGTERM al proceso `python -m herramientas.mutar`."""
    modulo = _crear_proyecto(tmp_path)
    original = modulo.read_bytes()
    toml = _toml(tmp_path, timeout_s=60)
    raiz_repo = Path(__file__).resolve().parents[2]
    arnes = subprocess.Popen(
        [sys.executable, "-m", "herramientas.mutar", str(toml), "--raiz", str(tmp_path)],
        cwd=raiz_repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    hijo = nieto = None
    arbol: list[tuple[int, str]] = []
    try:
        hijo, nieto = _esperar_pids(tmp_path)
        arbol = [(p, _cmdline(p)) for p in _descendientes(arnes.pid)]
        arnes.send_signal(signal.SIGTERM)
        time.sleep(0.05)
        arnes.send_signal(signal.SIGTERM)  # una segunda señal no puede cortar la restauración
        codigo = arnes.wait(timeout=20)

        assert codigo == 130, codigo
        assert modulo.read_bytes() == original, "el fichero quedó mutado tras SIGTERM"
        assert _esperar_muerte(hijo, _MARCA_HIJO), "el hijo siguió vivo tras SIGTERM al arnés"
        assert _esperar_muerte(nieto, _MARCA_NIETO), "el nieto en sesión propia siguió vivo"
        vivos = [p for p, linea in arbol if linea and _vivo(p, linea)]
        assert vivos == [], f"procesos del arnés supervivientes: {vivos}"
        assert _vivo(*senuelo), "la limpieza mató un proceso ajeno al arnés"
    finally:
        if arnes.poll() is None:
            arnes.kill()
            arnes.wait()
        for p, linea in arbol:
            if linea:
                _matar_si_vivo(p, linea)
        if hijo:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)


# ------------------------------------------------- SIGKILL: diario de restauración --


def test_tras_un_sigkill_el_proyecto_real_sigue_intacto_y_pytest_no_queda_huerfano(tmp_path, senuelo):
    """SIGKILL no ejecuta ningún `finally` (`timeout -k`, OOM, corte).

    Hasta 2026-10-25 el fichero del proyecto quedaba MUTADO y se recuperaba del diario al siguiente arranque.
    Desde la regla 6 el arnés muta una COPIA aislada: el proyecto real no llega a contener el mutante, no hay
    diario en su raíz, y el pytest del mutante muere con el arnés (PDEATHSIG). La copia queda en el temporal
    del sistema, reconocible por su prefijo; esta prueba la retira."""
    import shutil
    import tempfile

    from herramientas import mutar

    modulo = _crear_proyecto(tmp_path)
    original = modulo.read_bytes()
    toml = _toml(tmp_path, timeout_s=60)
    raiz_repo = Path(__file__).resolve().parents[2]
    temporal = Path(tempfile.gettempdir())
    copias_previas = set(temporal.glob(f"{mutar._PREFIJO_COPIA}*"))
    arnes = subprocess.Popen(
        [sys.executable, "-m", "herramientas.mutar", str(toml), "--raiz", str(tmp_path)],
        cwd=raiz_repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    hijo = nieto = None
    pytests: list[tuple[int, str]] = []
    copias: set[Path] = set()
    try:
        hijo, nieto = _esperar_pids(tmp_path)
        pytests = [(p, _cmdline(p)) for p in _descendientes(arnes.pid) if "pytest" in _cmdline(p)]
        assert pytests, "no se encontró el pytest del mutante"
        copias = set(temporal.glob(f"{mutar._PREFIJO_COPIA}*")) - copias_previas
        assert len(copias) == 1, f"control: debe existir la copia aislada del arnés vivo: {copias}"
        en_la_copia = next(iter(copias)) / tmp_path.name / modulo.name
        assert en_la_copia.read_bytes() != original, "control: el mutante está aplicado (en la copia)"
        assert modulo.read_bytes() == original, "el proyecto real contiene el mutante mientras el arnés vive"

        arnes.kill()
        arnes.wait(timeout=10)

        assert modulo.read_bytes() == original, "tras el SIGKILL el proyecto real contiene el mutante"
        assert not (tmp_path / ".mutar-en-curso.json").exists(), "el diario no pertenece a la raíz del proyecto"
        assert all(_esperar_muerte(p, linea) for p, linea in pytests), "el pytest del mutante quedó huérfano"
        assert mutar.recuperar_mutacion_interrumpida(str(tmp_path)) == []
        assert _vivo(*senuelo)
    finally:
        if arnes.poll() is None:
            arnes.kill()
            arnes.wait()
        for p, linea in pytests:
            _matar_si_vivo(p, linea)
        if hijo:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)
        for copia in copias:
            shutil.rmtree(copia, ignore_errors=True)


def test_una_ejecucion_normal_no_deja_diario(tmp_path):
    _crear_proyecto(tmp_path)
    (tmp_path / "modulo_vida.py").write_text("def trabajo():\n    return 'listo'\n", encoding="utf-8")
    toml = tmp_path / "mutaciones.toml"
    toml.write_text(
        'incremento = "juguete"\npruebas = ["tests/test_modulo_vida.py"]\ntimeout_s = 30\n\n'
        '[[mutante]]\nid = "N1"\ngarantia = "x"\nfichero = "modulo_vida.py"\n'
        "buscar = \"return 'listo'\"\nsustituir = \"return 'otro'\"\n",
        encoding="utf-8",
    )

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert resultado.detectados == 1
    assert not (tmp_path / ".mutar-en-curso.json").exists()


# ------------------------------------------------- escritura atómica y diario --


def test_ejecutar_restaura_primero_lo_que_dejo_mutado_una_ejecucion_anterior(tmp_path):
    from herramientas import mutar

    _crear_proyecto(tmp_path)
    modulo = tmp_path / "modulo_vida.py"
    original = modulo.read_bytes()
    mutado = original.replace(b"return True", b"return False")
    mutar._anotar_diario(str(tmp_path), "modulo_vida.py", original, mutado, pid=_pid_muerto())
    modulo.write_bytes(mutado)  # lo que dejó el SIGKILL

    ejecutar(str(_toml(tmp_path, timeout_s=0.001)), raiz=str(tmp_path))  # aunque la base no llegue a verde

    assert modulo.read_bytes() == original
    assert not (tmp_path / ".mutar-en-curso.json").exists()


def test_la_escritura_atomica_no_deja_el_fichero_a_medias_si_falla(tmp_path, monkeypatch):
    from herramientas import mutar

    fichero = tmp_path / "fuente.py"
    fichero.write_bytes(b"contenido original\n")

    def _falla(_fd):
        raise OSError("disco lleno a mitad de escritura")

    monkeypatch.setattr(mutar.os, "fsync", _falla)
    with pytest.raises(OSError):
        mutar._escribir_atomico(fichero, b"contenido nuevo que no llega a completarse\n")

    assert fichero.read_bytes() == b"contenido original\n", "el fuente quedó truncado o a medias"


def test_la_restauracion_corre_con_las_senales_de_parada_bloqueadas(tmp_path, monkeypatch):
    """Una segunda señal no puede cortar la restauración: durante ella, SIGTERM/SIGINT/SIGHUP están bloqueadas."""
    from herramientas import mutar

    _crear_proyecto(tmp_path)
    (tmp_path / "modulo_vida.py").write_text("def trabajo():\n    return 'listo'\n", encoding="utf-8")
    toml = tmp_path / "m.toml"
    toml.write_text(
        'incremento = "j"\npruebas = ["tests/test_modulo_vida.py"]\ntimeout_s = 30\n\n'
        '[[mutante]]\nid = "B1"\ngarantia = "x"\nfichero = "modulo_vida.py"\n'
        "buscar = \"return 'listo'\"\nsustituir = \"return 'otro'\"\n",
        encoding="utf-8",
    )
    original = (tmp_path / "modulo_vida.py").read_bytes()
    real = mutar._escribir_atomico
    mascaras = []

    def _espia(ruta, datos):
        if ruta.name == "modulo_vida.py" and datos == original:
            mascaras.append(signal.pthread_sigmask(signal.SIG_BLOCK, []))
        return real(ruta, datos)

    monkeypatch.setattr(mutar, "_escribir_atomico", _espia)
    ejecutar(str(toml), raiz=str(tmp_path))

    assert mascaras, "no hubo restauración"
    assert {signal.SIGTERM, signal.SIGINT, signal.SIGHUP} <= set(mascaras[0])
    assert signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, []), "las señales quedaron bloqueadas"


# ------------------------------------------------- segunda señal y doble fork --


def test_tras_la_primera_senal_las_siguientes_se_ignoran():
    """La limpieza (matar el árbol, restaurar) no puede cortarse por una segunda señal."""
    from herramientas import mutar

    interrumpido = False
    segunda_interrumpio = False
    with pytest.raises(KeyboardInterrupt):
        with mutar._parada_limpia():
            try:
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(1)
            except KeyboardInterrupt:
                interrumpido = True
                try:
                    os.kill(os.getpid(), signal.SIGTERM)  # llega en plena limpieza: no debe interrumpirla
                    time.sleep(0.2)
                except KeyboardInterrupt:
                    segunda_interrumpio = True
                raise
    assert interrumpido
    assert not segunda_interrumpio, "una segunda señal cortó la limpieza"
    assert signal.getsignal(signal.SIGTERM) is not signal.SIG_IGN, "los manejadores no se restauraron"


_MARCA_HUERFANO = "time.sleep(44.25)"


def test_el_timeout_mata_tambien_al_proceso_del_grupo_que_ya_cuelga_de_init(tmp_path):
    """Doble fork: el durmiente ya no es descendiente (ppid 1) pero sigue en el grupo de pytest. La foto de
    descendientes no lo ve; solo `killpg` lo alcanza. Protege que el arnés mate el GRUPO, no solo el árbol."""
    (tmp_path / "modulo_vida.py").write_text(
        textwrap.dedent(
            f"""\
            import subprocess
            import sys
            import time
            from pathlib import Path


            def condicion_de_parada():
                return True


            def trabajo():
                if condicion_de_parada():
                    return "listo"
                intermedio = (
                    "import subprocess, sys; "
                    "p = subprocess.Popen([sys.executable, '-c', 'import time; {_MARCA_HUERFANO}']); "
                    "open({str(tmp_path / "pid_huerfano.txt")!r}, 'w').write(str(p.pid))"
                )
                subprocess.run([sys.executable, "-c", intermedio])  # el intermedio sale: el durmiente cuelga de init
                while True:
                    time.sleep(0.05)
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_modulo_vida.py").write_text(
        "from modulo_vida import trabajo\n\n\ndef test_trabajo_termina():\n    assert trabajo() == 'listo'\n",
        encoding="utf-8",
    )
    huerfano = None
    try:
        resultado = ejecutar(str(_toml(tmp_path, timeout_s=8)), raiz=str(tmp_path))
        huerfano = int((tmp_path / "pid_huerfano.txt").read_text())

        assert resultado.timeouts == 1
        assert _esperar_muerte(huerfano, _MARCA_HUERFANO), "el proceso del grupo que colgaba de init sobrevivió"
    finally:
        if huerfano:
            _matar_si_vivo(huerfano, _MARCA_HUERFANO)


# ------------------------------------------- recuperación prudente (revisión ECC del código) --


def _pid_muerto() -> int:
    """PID de un proceso que ya terminó: el «dueño» de un diario abandonado."""
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _diario_de(tmp_path: Path, original: bytes, mutado: bytes, pid: int) -> Path:
    from herramientas import mutar

    (tmp_path / "fuente.py").write_bytes(mutado)
    mutar._anotar_diario(str(tmp_path), "fuente.py", original, mutado, pid=pid)
    return tmp_path / "fuente.py"


def test_la_recuperacion_no_pisa_un_fichero_que_ya_no_es_el_mutado(tmp_path, capsys):
    """Tras el SIGKILL la persona hizo `git checkout` o editó el fichero: el diario está obsoleto y no se toca nada."""
    from herramientas import mutar

    fuente = _diario_de(tmp_path, b"original\n", b"mutado\n", pid=_pid_muerto())
    fuente.write_bytes(b"trabajo nuevo de la persona\n")

    assert mutar.recuperar_mutacion_interrumpida(str(tmp_path)) == []
    assert fuente.read_bytes() == b"trabajo nuevo de la persona\n"
    assert not (tmp_path / ".mutar-en-curso.json").exists()
    assert "obsoleto" in capsys.readouterr().err


def test_la_recuperacion_se_niega_si_el_arnes_dueno_sigue_vivo(tmp_path):
    """Dos arneses sobre la misma raíz: el segundo no puede «recuperar» la mutación en curso del primero."""
    from herramientas import mutar

    fuente = _diario_de(tmp_path, b"original\n", b"mutado\n", pid=os.getpid())  # dueño vivo: este proceso

    with pytest.raises(RuntimeError, match="(?i)otro arnés"):
        mutar.recuperar_mutacion_interrumpida(str(tmp_path))
    assert fuente.read_bytes() == b"mutado\n"
    assert (tmp_path / ".mutar-en-curso.json").exists()


def test_un_diario_corrupto_da_un_error_claro(tmp_path):
    from herramientas import mutar

    (tmp_path / ".mutar-en-curso.json").write_text("{no es json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="diario"):
        mutar.recuperar_mutacion_interrumpida(str(tmp_path))


def test_la_escritura_atomica_no_deja_temporales_y_respeta_los_enlaces(tmp_path, monkeypatch):
    from herramientas import mutar

    real = tmp_path / "real.py"
    real.write_bytes(b"uno\n")
    enlace = tmp_path / "enlace.py"
    enlace.symlink_to(real)

    mutar._escribir_atomico(enlace, b"dos\n")
    assert enlace.is_symlink() and real.read_bytes() == b"dos\n", "el enlace se convirtió en fichero regular"

    monkeypatch.setattr(mutar.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("fallo")))
    with pytest.raises(OSError):
        mutar._escribir_atomico(real, b"tres\n")
    assert [n.name for n in tmp_path.iterdir() if "mutar-tmp" in n.name] == [], "quedó un temporal"


def test_si_pidfd_no_esta_disponible_se_mata_igualmente_y_solo_al_mismo_proceso(monkeypatch):
    from herramientas import mutar

    marca = "time.sleep(45.5)"
    p = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    try:
        (pid, inicio), *_ = [d for d in mutar._descendientes(os.getpid()) if d[0] == p.pid]
        monkeypatch.setattr(mutar.os, "pidfd_open", lambda _pid: (_ for _ in ()).throw(OSError(38, "ENOSYS")))

        mutar._matar_si_es_el_mismo(pid, "otro-starttime")  # PID reutilizado por otro: no se toca
        time.sleep(0.3)  # SIGKILL es asíncrono: sin esperar, `poll()` podría no ver aún la muerte (prueba vacua)
        assert p.poll() is None
        mutar._matar_si_es_el_mismo(pid, inicio)
        assert p.wait(timeout=5) == -signal.SIGKILL
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_no_se_sobrescribe_una_senal_que_el_llamador_ignoraba():
    """`nohup` ignora SIGHUP: el arnés no puede volverse interrumpible por esa señal."""
    from herramientas import mutar

    anterior = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        try:
            with mutar._parada_limpia():
                os.kill(os.getpid(), signal.SIGHUP)
                time.sleep(0.2)  # si la hubiera tomado como parada, aquí saltaría la interrupción
        except KeyboardInterrupt:
            pytest.fail("el arnés tomó como parada un SIGHUP que el llamador ignoraba (nohup)")
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGHUP, anterior)


def test_bloquear_y_desbloquear_restaura_la_mascara_del_llamador():
    from herramientas import mutar

    # El llamador ya tenía bloqueada SIGTERM —una de las señales de parada— y SIGUSR1: al terminar, siguen así.
    previa = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1, signal.SIGTERM})
    try:
        estado = mutar._bloquear_senales()
        mutar._desbloquear_senales(estado)
        mascara = signal.pthread_sigmask(signal.SIG_BLOCK, [])
        assert signal.SIGUSR1 in mascara, "se perdió una señal que el llamador tenía bloqueada"
        assert signal.SIGTERM in mascara, "se desbloqueó una señal de parada que el llamador tenía bloqueada"
        assert signal.SIGHUP not in mascara, "una señal que el llamador no bloqueaba quedó bloqueada"
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previa)


def test_con_pidfd_real_un_pid_cuyo_starttime_no_coincide_no_se_mata():
    """La rama de pidfd también exige identidad: si el PID se reutilizó, no se toca (la otra prueba fuerza ENOSYS)."""
    from herramientas import mutar

    marca = "time.sleep(49.25)"
    p = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    try:
        (pid, inicio), *_ = [d for d in mutar._descendientes(os.getpid()) if d[0] == p.pid]

        mutar._matar_si_es_el_mismo(pid, "otro-starttime")
        time.sleep(0.3)
        assert p.poll() is None, "se mató un proceso cuyo starttime no coincidía"
        mutar._matar_si_es_el_mismo(pid, inicio)
        assert p.wait(timeout=5) == -signal.SIGKILL
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
