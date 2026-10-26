"""Ciclo de vida de los procesos del verificador (`ejecutar_pruebas`), 2026-10-06.

El verificador lanza pytest en su PROPIA sesión (`start_new_session=True`) para poder matar su grupo. Pero:

  · solo lo mataba en `TimeoutExpired`: ante Ctrl-C o cualquier excepción, pytest quedaba HUÉRFANO;
  · `killpg` no alcanza a un descendiente que abre SU propia sesión;
  · si el proceso que llama muere (SIGTERM con la acción por defecto, SIGKILL), ningún `finally` corre y pytest
    sigue vivo sin nadie que le aplique el plazo;
  · la precondición «el arnés de mutación no está corriendo» solo se miraba AL EMPEZAR: si el arnés arranca a
    mitad, se mide un mutante y se informa como si fuera el producto.

Lotes de prueba en `tmp_path`, con procesos reales: cada uno lleva una duración ÚNICA en su orden (marca) y se
comprueba por PID + marca, nunca contando por patrón. Toda prueba mata lo que haya quedado vivo.
"""

from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time

import orquestador as orq
import pytest
import verificador as vf

_MARCA_HIJO = "time.sleep(46.25)"
_MARCA_NIETO = "time.sleep(46.75)"  # abre SU PROPIA sesión: escapa a killpg


@pytest.fixture(autouse=True)
def _el_arnes_no_esta_corriendo(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _bateria_que_cuelga(raiz: pathlib.Path, sin_marca: bool = False) -> pathlib.Path:
    """Una prueba que lanza un hijo y un nieto en sesión propia, anota sus PID y cuelga.

    `sin_marca`: los lanza con un entorno CONSTRUIDO, sin la marca de la ejecución. Entonces el barrido final no los
    ve y solo `_matar_arbol` (foto por ppid + grupo) puede alcanzarlos: las dos capas se prueban por separado."""
    entorno = ", env={'PATH': '/usr/bin:/bin'}" if sin_marca else ""
    f = raiz / "test_cuelga.py"
    f.write_text(
        textwrap.dedent(
            f"""\
            import subprocess
            import sys
            import time
            from pathlib import Path


            def test_cuelga():
                hijo = subprocess.Popen([sys.executable, "-c", "import time; {_MARCA_HIJO}"]{entorno})
                nieto = subprocess.Popen([sys.executable, "-c", "import time; {_MARCA_NIETO}"], start_new_session=True{entorno})
                Path({str(raiz / "pids.txt")!r}).write_text(f"{{hijo.pid}} {{nieto.pid}}")
                while True:
                    time.sleep(0.05)
            """
        ),
        encoding="utf-8",
    )
    return f


def _cmdline(pid: int) -> str:
    try:
        return pathlib.Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


def _vivo(pid: int, marca: str) -> bool:
    try:
        estado = pathlib.Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return estado != "Z" and marca in _cmdline(pid)


def _matar_si_vivo(pid: int, marca: str) -> None:
    if _vivo(pid, marca):
        os.kill(pid, signal.SIGKILL)


def _esperar_muerte(pid: int, marca: str, limite_s: float = 5) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite_s:
        if not _vivo(pid, marca):
            return True
        time.sleep(0.05)
    return False


def _esperar_pids(raiz: pathlib.Path, limite_s: float = 30) -> tuple[int, int]:
    fichero = raiz / "pids.txt"
    t0 = time.monotonic()
    while time.monotonic() - t0 < limite_s:
        if fichero.exists() and fichero.read_text().strip():
            a, b = fichero.read_text().split()
            return int(a), int(b)
        time.sleep(0.05)
    raise AssertionError("la batería no llegó a arrancar sus procesos")


def _descendientes(pid: int) -> list[int]:
    hijos: dict[int, list[int]] = {}
    for entrada in os.listdir("/proc"):
        if entrada.isdigit():
            try:
                ppid = int(pathlib.Path(f"/proc/{entrada}/stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                continue
            hijos.setdefault(ppid, []).append(int(entrada))
    todos, pendientes = [], [pid]
    while pendientes:
        for h in hijos.get(pendientes.pop(), []):
            todos.append(h)
            pendientes.append(h)
    return todos


def _temporales_del_verificador() -> set[str]:
    return {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("aura-verificador-")}


@pytest.fixture
def senuelo():
    """Proceso AJENO al verificador: la limpieza no puede tocarlo."""
    marca = "time.sleep(47.5)"
    proceso = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    yield proceso.pid, marca
    proceso.kill()
    proceso.wait()


# ------------------------------------------------------------------ plazo agotado --


@pytest.mark.parametrize("sin_marca", [False, True], ids=["con_marca", "entorno_construido"])
def test_al_agotar_el_plazo_muere_tambien_el_descendiente_que_abrio_su_propia_sesion(tmp_path, senuelo, sin_marca):
    f = _bateria_que_cuelga(tmp_path, sin_marca)
    hijo = nieto = None
    try:
        informe = vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=6)
        hijo, nieto = _esperar_pids(tmp_path, limite_s=1)

        assert informe.agotado is True and informe.sano is False
        assert _esperar_muerte(hijo, _MARCA_HIJO), "el hijo de pytest sobrevivió al plazo"
        assert _esperar_muerte(nieto, _MARCA_NIETO), "el nieto en sesión propia sobrevivió al plazo"
        assert _vivo(*senuelo), "la limpieza mató un proceso ajeno"
    finally:
        if hijo:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)


# ------------------------------------------------------------- interrupción --


@pytest.mark.parametrize("sin_marca", [False, True], ids=["con_marca", "entorno_construido"])
def test_una_interrupcion_mata_a_pytest_y_a_sus_descendientes_y_borra_el_temporal(tmp_path, senuelo, sin_marca):
    f = _bateria_que_cuelga(tmp_path, sin_marca)
    antes = _temporales_del_verificador()
    pids: list[tuple[int, int]] = []
    pytests: list[tuple[int, str]] = []

    def _interrumpir_cuando_arranque():
        try:
            pids.append(_esperar_pids(tmp_path))
            pytests.extend((p, _cmdline(p)) for p in _descendientes(os.getpid()) if "test_cuelga" in _cmdline(p))
            os.kill(os.getpid(), signal.SIGUSR1)
        except AssertionError:
            pass

    anterior = signal.signal(signal.SIGUSR1, lambda *_a: (_ for _ in ()).throw(KeyboardInterrupt()))
    threading.Thread(target=_interrumpir_cuando_arranque, daemon=True).start()
    try:
        with pytest.raises(KeyboardInterrupt):
            vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=120)
        assert pids and pytests, "la batería no arrancó"
        hijo, nieto = pids[0]

        assert all(_esperar_muerte(p, linea) for p, linea in pytests), "pytest quedó huérfano tras la interrupción"
        assert _esperar_muerte(hijo, _MARCA_HIJO), "el hijo de pytest siguió vivo"
        assert _esperar_muerte(nieto, _MARCA_NIETO), "el nieto en sesión propia siguió vivo"
        assert _temporales_del_verificador() <= antes, "quedó el temporal del informe"
        assert _vivo(*senuelo), "la limpieza mató un proceso ajeno"
    finally:
        signal.signal(signal.SIGUSR1, anterior)
        for p, linea in pytests:
            _matar_si_vivo(p, linea)
        for hijo, nieto in pids:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)


# ------------------------------------------------ muerte del proceso que llama --


_LLAMANTE = textwrap.dedent(
    """\
    import sys
    sys.path.insert(0, {plano!r})
    import orquestador
    orquestador.mutacion_en_curso = lambda: False
    import verificador
    verificador.ejecutar_pruebas([{prueba!r}], {raiz!r}, limite_s=120)
    """
)


@pytest.mark.parametrize("senal", [signal.SIGTERM, signal.SIGKILL])
def test_si_muere_el_proceso_que_llama_pytest_no_queda_huerfano(tmp_path, senal):
    """El ciclo desatendido muere por SIGTERM (acción por defecto) o SIGKILL: ningún `finally` corre. pytest debe
    morir con él (PR_SET_PDEATHSIG). Límite declarado: los DESCENDIENTES de pytest no heredan esa señal."""
    f = _bateria_que_cuelga(tmp_path)
    plano = str(pathlib.Path(vf.__file__).resolve().parent)
    llamante = subprocess.Popen(
        [sys.executable, "-c", _LLAMANTE.format(plano=plano, prueba=str(f), raiz=str(tmp_path))],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    hijo = nieto = None
    pytests: list[tuple[int, str]] = []
    antes = _temporales_del_verificador()
    try:
        hijo, nieto = _esperar_pids(tmp_path)
        pytests = [(p, _cmdline(p)) for p in _descendientes(llamante.pid) if "test_cuelga" in _cmdline(p)]
        assert pytests, "no se encontró el pytest del verificador"
        llamante.send_signal(senal)
        llamante.wait(timeout=10)

        assert all(_esperar_muerte(p, linea) for p, linea in pytests), "pytest quedó huérfano al morir quien lo lanzó"
    finally:
        if llamante.poll() is None:
            llamante.kill()
            llamante.wait()
        for p, linea in pytests:
            _matar_si_vivo(p, linea)
        if hijo:
            _matar_si_vivo(hijo, _MARCA_HIJO)
            _matar_si_vivo(nieto, _MARCA_NIETO)
        # Sin `finally` en el llamante, su temporal queda (riesgo residual declarado): la prueba lo retira.
        import shutil

        for nombre in _temporales_del_verificador() - antes:
            shutil.rmtree(pathlib.Path(tempfile.gettempdir()) / nombre, ignore_errors=True)


def test_el_confinamiento_se_sigue_aplicando_junto_a_la_muerte_con_el_padre(tmp_path):
    """`preexec_fn` compone: la red de PDEATHSIG no puede sustituir al confinador de `aislamiento`."""
    marca = tmp_path / "confinado.txt"

    def confinar():  # corre en el hijo, entre fork y exec
        marca.write_text("si")

    f = tmp_path / "test_v.py"
    f.write_text("def test_pasa():\n    assert True\n", encoding="utf-8")

    informe = vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=60, confinar=confinar)

    assert informe.sano
    assert marca.read_text() == "si", "el confinador no llegó a ejecutarse"


# -------------------------------------------------- arnés que arranca a mitad --


def test_si_el_arnes_de_mutacion_arranca_a_mitad_la_medicion_no_vale(tmp_path, monkeypatch):
    """Precondición vigente también AL TERMINAR: medir mientras el arnés muta es medir un mutante."""
    respuestas = iter([False, True])
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: next(respuestas))
    f = tmp_path / "test_v.py"
    f.write_text("def test_pasa():\n    assert True\n", encoding="utf-8")

    with pytest.raises(vf.ArnesEnCurso):
        vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=60)


def test_el_veredicto_booleano_de_esa_medicion_es_rojo(tmp_path, monkeypatch):
    respuestas = iter([False, True])
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: next(respuestas))
    f = tmp_path / "test_v.py"
    f.write_text("def test_pasa():\n    assert True\n", encoding="utf-8")

    assert vf.arbol_sano([str(f)], tmp_path, limite_s=60) is False


# ----------------------------------------------------- identidad del proceso --


def test_solo_se_mata_un_descendiente_si_sigue_siendo_el_mismo_proceso():
    """Si el PID se reutiliza entre la foto y la señal, el starttime ya no coincide y no se toca a nadie."""
    marca = "time.sleep(48.25)"
    p = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    try:
        (pid, inicio), *_ = [d for d in vf._descendientes(os.getpid()) if d[0] == p.pid]

        vf._matar_si_es_el_mismo(pid, "otro-starttime")
        time.sleep(0.3)  # SIGKILL es asíncrono: sin esperar, `poll()` podría no ver aún la muerte (prueba vacua)
        assert p.poll() is None, "se mató un proceso cuyo starttime no coincidía"
        vf._matar_si_es_el_mismo(pid, inicio)
        assert p.wait(timeout=5) == -signal.SIGKILL
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_sin_pidfd_disponible_se_mata_igualmente_con_la_misma_comprobacion(monkeypatch):
    marca = "time.sleep(48.75)"
    p = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    try:
        (pid, inicio), *_ = [d for d in vf._descendientes(os.getpid()) if d[0] == p.pid]
        monkeypatch.setattr(vf.os, "pidfd_open", lambda _pid: (_ for _ in ()).throw(OSError(38, "ENOSYS")))

        vf._matar_si_es_el_mismo(pid, "otro-starttime")
        time.sleep(0.3)  # SIGKILL es asíncrono: sin esperar, `poll()` podría no ver aún la muerte (prueba vacua)
        assert p.poll() is None
        vf._matar_si_es_el_mismo(pid, inicio)
        assert p.wait(timeout=5) == -signal.SIGKILL
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_si_el_arnes_arranca_y_termina_durante_la_bateria_se_detecta_igualmente(tmp_path, monkeypatch):
    """El arnés muta y restaura en segundos; la batería dura hasta 600 s. Mirar solo al principio y al final no
    lo ve: hay que vigilar DURANTE la ejecución, y entonces se para la batería y se declara inválida."""
    inicio = time.monotonic()

    def _arnes_entre_1_y_2_segundos():
        return 1.0 <= time.monotonic() - inicio <= 2.0

    monkeypatch.setattr(orq, "mutacion_en_curso", _arnes_entre_1_y_2_segundos)
    f = tmp_path / "test_lento.py"
    f.write_text("import time\n\n\ndef test_lento():\n    time.sleep(4)\n", encoding="utf-8")

    t0 = time.monotonic()
    with pytest.raises(vf.ArnesEnCurso):
        vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=60)
    assert time.monotonic() - t0 < 3.5, "no se paró la batería al detectar el arnés"


def test_con_el_arnes_corriendo_al_empezar_no_se_lanza_ni_un_proceso(tmp_path, monkeypatch):
    """La comprobación de ENTRADA no es redundante con las demás: se niega ANTES de lanzar pytest."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: True)

    def _prohibido(*_a, **_k):
        raise AssertionError("se lanzó pytest con el arnés de mutación corriendo")

    monkeypatch.setattr(vf.subprocess, "Popen", _prohibido)
    f = tmp_path / "test_v.py"
    f.write_text("def test_pasa():\n    assert True\n", encoding="utf-8")

    with pytest.raises(vf.ArnesEnCurso):
        vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=60)


def test_la_comprobacion_final_cubre_lo_que_la_vigilancia_no_llega_a_ver(tmp_path, monkeypatch):
    """Con la vigilancia más lenta que la batería, solo la comprobación AL TERMINAR puede ver el arnés."""
    monkeypatch.setattr(vf, "_VIGILANCIA_S", 600.0)
    respuestas = iter([False, True])
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: next(respuestas))
    f = tmp_path / "test_v.py"
    f.write_text("def test_pasa():\n    assert True\n", encoding="utf-8")

    with pytest.raises(vf.ArnesEnCurso):
        vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=60)


def test_si_falla_la_foto_el_arbol_congelado_se_mata_igual_y_no_queda_parado(monkeypatch):
    """Entre SIGSTOP y SIGKILL cualquier excepción (un segundo Ctrl-C, un OSError) dejaba el grupo PARADO para
    siempre. La muerte va en un `finally`: pase lo que pase en la foto, el árbol congelado se mata."""
    marca = "time.sleep(49.75)"
    proceso = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"], start_new_session=True)

    def _foto_que_revienta(_pid):
        raise KeyboardInterrupt  # el segundo Ctrl-C llega justo durante la foto

    monkeypatch.setattr(vf, "_descendientes", _foto_que_revienta)
    try:
        with pytest.raises(KeyboardInterrupt):
            vf._matar_arbol(proceso)
        assert proceso.wait(timeout=5) == -signal.SIGKILL, "el grupo quedó congelado sin matar"
    finally:
        if proceso.poll() is None:
            os.killpg(proceso.pid, signal.SIGKILL)
            proceso.wait()


def test_un_error_inesperado_al_senalar_no_sale_de_la_funcion(monkeypatch):
    """`pidfd_send_signal` puede fallar con otros OSError (EINVAL…): no puede cortar el bucle de muerte."""
    marca = "time.sleep(51.25)"
    p = subprocess.Popen([sys.executable, "-c", f"import time; {marca}"])
    try:
        (pid, inicio), *_ = [d for d in vf._descendientes(os.getpid()) if d[0] == p.pid]
        monkeypatch.setattr(vf.signal, "pidfd_send_signal", lambda *_a: (_ for _ in ()).throw(OSError(22, "EINVAL")))

        vf._senal_si_es_el_mismo(pid, inicio, signal.SIGKILL)  # no debe lanzar
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


# ------------------------------------------------------- descendientes desvinculados (2026-10-06, 2.ª fase) --

_MARCA_FUGADO = "time.sleep(52.25)"


def _bateria_con_fugado(raiz: pathlib.Path, colgar: bool) -> None:
    """Doble fork: el intermedio sale enseguida y el nieto (sesión propia) queda colgando de init, FUERA de la
    foto de descendientes de pytest y fuera de su grupo. `[EJEC]` 2026-10-06: sobrevivía al verificador."""
    (raiz / "test_fuga.py").write_text(
        textwrap.dedent(
            f"""\
            import subprocess
            import sys
            import time
            from pathlib import Path


            def test_fuga():
                intermedio = subprocess.run(
                    [sys.executable, "-c",
                     "import subprocess, sys; "
                     "p = subprocess.Popen([sys.executable, '-c', 'import time; {_MARCA_FUGADO}'], "
                     "start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print(p.pid)"],
                    capture_output=True, text=True, check=True)
                Path({str(raiz / "pids.txt")!r}).write_text(intermedio.stdout.strip() + " 0")
                while {colgar!r}:
                    time.sleep(0.05)
            """
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("colgar", [False, True], ids=["bateria_termina", "plazo_agotado"])
def test_un_descendiente_desvinculado_por_doble_fork_no_sobrevive_al_verificador(tmp_path, senuelo, colgar):
    _bateria_con_fugado(tmp_path, colgar)
    fugado = None
    try:
        informe = vf.ejecutar_pruebas(["test_fuga.py"], tmp_path, limite_s=8 if colgar else 60)
        fugado, _ = _esperar_pids(tmp_path, limite_s=1)
        assert informe.agotado is colgar
        assert _esperar_muerte(fugado, _MARCA_FUGADO), "el nieto desvinculado sigue vivo tras el verificador"
        assert _vivo(senuelo[0], senuelo[1]), "la limpieza tocó un proceso ajeno al verificador"
    finally:
        if fugado:
            _matar_si_vivo(fugado, _MARCA_FUGADO)


def test_la_marca_de_la_ejecucion_no_se_filtra_al_proceso_que_llama(tmp_path):
    """La marca va solo en el entorno del HIJO: si se filtrara al plano, sus siguientes hijos la heredarían. Se
    compara antes y después (no «ausente»): esta batería puede correr ella misma bajo el verificador (ECC)."""
    (tmp_path / "test_vacia.py").write_text("def test_nada():\n    pass\n", encoding="utf-8")
    antes = os.environ.get(vf._VARIABLE_MARCA)
    vf.ejecutar_pruebas(["test_vacia.py"], tmp_path, limite_s=60)
    assert os.environ.get(vf._VARIABLE_MARCA) == antes
