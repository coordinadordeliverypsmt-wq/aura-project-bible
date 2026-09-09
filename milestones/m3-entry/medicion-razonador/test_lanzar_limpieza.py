"""D-5 · El laboratorio no puede sobrevivir a la ejecución que lo creó.

Estas pruebas NO pertenecen al Quality Gate del producto y no deben presentarse como tales.
`walking-skeleton/pyproject.toml` declara `testpaths = ["tests"]` y el gate corre desde
`walking-skeleton/`, así que este fichero queda fuera de su alcance por construcción. Se ejecuta
aparte, a mano:

    PYTHONDONTWRITEBYTECODE=1 python3 -m pytest milestones/m3-entry/medicion-razonador/test_lanzar_limpieza.py -v

La variable de entorno NO es opcional: no hay `.gitignore` para `__pycache__` en ningun nivel del
repositorio, y sin ella la carga dinamica de `lanzar.py` deja bytecode sin rastrear en este mismo
directorio.

PERIMETRO DE LO QUE SE PRUEBA, y de lo que no. Se cubre: camino feliz, excepciones de Python,
`TimeoutExpired` y `KeyboardInterrupt`/SIGINT -que Python ya convierte en excepcion, asi que el
`finally` la atrapa sin escribir una linea sobre senales-. **NO se cubre SIGTERM, SIGHUP, SIGQUIT ni
SIGKILL/OOM**: sin manejador registrado, Python termina el proceso sin desenrollar la pila y ningun
`finally` corre. Eso queda declarado como perimetro residual de D-5, no como garantia.

NADA AQUI EJECUTA EL EXPERIMENTO. `git archive`, `tar` y el subproceso del arnes estan simulados; no
se invoca Ollama ni se toca el `/tmp` real: los directorios temporales se crean bajo el `tmp_path` de
pytest.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

AQUI_TEST = pathlib.Path(__file__).resolve().parent


# ------------------------------------------------------------------ CARGA DEL MODULO --
#
# `lanzar.py` no es importable como paquete: `m3-entry` y `medicion-razonador` llevan guiones. Se
# carga por ruta y sin registrarlo en `sys.modules`, para que cada prueba reciba un modulo limpio.


def _cargar():
    ruta = AQUI_TEST / "lanzar.py"
    spec = importlib.util.spec_from_file_location("lanzar_bajo_prueba", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Escenario:
    """Monta un `main()` aislado: sin disco real, sin git, sin tar, sin Ollama.

    Guarda las rutas que `mkdtemp` fue devolviendo para poder aseverar sobre ellas despues, que es
    la unica forma de comprobar si la limpieza ocurrio.
    """

    def __init__(self, mod, tmp_path, monkeypatch, modo="denegacion"):
        self.mod = mod
        self.creados: list[pathlib.Path] = []
        self.rmtree_recibio: list[pathlib.Path] = []
        self.falla_en: str | None = None
        self.excepcion: BaseException | None = None

        monkeypatch.setattr(sys, "argv", ["lanzar.py", modo])
        # `AQUI` se lee dinamicamente dentro de `main()`, asi que reasignarla surte efecto: evita
        # escribir evidencia real en el directorio del arnes, que contiene artefactos versionados.
        monkeypatch.setattr(mod, "AQUI", tmp_path)
        (tmp_path / mod.ARNESES[modo]).write_text("# arnes simulado\n", encoding="utf-8")

        real_mkdtemp = mod.tempfile.mkdtemp

        def mkdtemp(prefix=None, dir=None):  # noqa: A002 — firma de la stdlib
            p = pathlib.Path(real_mkdtemp(prefix=prefix, dir=str(tmp_path)))
            self.creados.append(p)
            return str(p)

        monkeypatch.setattr(mod.tempfile, "mkdtemp", mkdtemp)
        monkeypatch.setattr(mod.subprocess, "run", self._run)

        real_rmtree = mod.shutil.rmtree
        # La limpieza del propio arnes de pruebas usa el `rmtree` REAL: con el parcheado, la trampa
        # de abajo se dispararia contra nuestro propio desmontaje. Lo detecto ejecutando: 7 errores
        # en teardown la primera vez. La trampa funciona; lo que estaba mal era el arnes.
        self._rmtree_real = real_rmtree

        def rmtree(ruta, *a, **kw):
            p = pathlib.Path(ruta)
            self.rmtree_recibio.append(p)
            # TRAMPA DELIBERADA. `datos` se conserva por decision del CEO. Sin esto, la prueba de
            # que "no se borra" seria un verde vacio: hoy nada lo borra, asi que pasaria por
            # omision. Aqui revienta en el acto si una implementacion futura lo mete en el bucle de
            # limpieza junto a `lab` -el error de tratar dos cosas distintas como si fueran una-.
            if len(self.creados) > 1 and p == self.creados[1]:
                raise AssertionError(f"shutil.rmtree recibio `datos` ({p}): no debe borrarse")
            return real_rmtree(ruta, *a, **kw)

        monkeypatch.setattr(mod.shutil, "rmtree", rmtree)

    def _run(self, cmd, **kw):
        quien = "git" if cmd[0] == "git" else "tar" if cmd[0] == "tar" else "arnes"
        if self.falla_en == quien:
            raise self.excepcion
        if quien == "git":
            pathlib.Path(cmd[cmd.index("--output") + 1]).touch()
        elif quien == "tar":
            destino = pathlib.Path(cmd[cmd.index("-C") + 1])
            (destino / "walking-skeleton" / "mutaciones").mkdir(parents=True, exist_ok=True)
        else:
            return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def falla(self, quien, excepcion):
        self.falla_en, self.excepcion = quien, excepcion

    @property
    def lab(self) -> pathlib.Path:
        return self.creados[0]

    @property
    def datos(self) -> pathlib.Path:
        return self.creados[1]

    @property
    def tar(self) -> pathlib.Path:
        return self.lab.parent / f"{self.lab.name}.tar"

    def limpiar(self):
        """Limpieza del PROPIO arnes de pruebas, no la que se esta probando."""
        for p in self.creados:
            self._rmtree_real(p, ignore_errors=True)
        if self.creados:
            self.tar.unlink(missing_ok=True)


@pytest.fixture
def escenario(tmp_path, monkeypatch):
    esc = _Escenario(_cargar(), tmp_path, monkeypatch)
    yield esc
    esc.limpiar()


# ============================================================ RED · lo que hoy falla --


def test_el_laboratorio_no_sobrevive_a_un_timeout(escenario):
    """RED. El timeout de la medicion es el aborto mas probable: el arnes espera hasta 1500 s a un
    modelo local que puede colgarse. Hoy la limpieza esta en linea recta al final de `main()`, asi
    que la excepcion se la salta y deja ~9 MB de copia del repositorio en el disco."""
    escenario.falla("arnes", subprocess.TimeoutExpired(cmd=["x"], timeout=1))

    with pytest.raises(subprocess.TimeoutExpired):
        escenario.mod.main()

    assert not escenario.lab.exists(), "el laboratorio sobrevivio al timeout"


def test_el_tar_no_sobrevive_a_un_fallo_de_extraccion(escenario):
    """RED. `git archive` ya escribio los 8,6 MB del tar y `tar -xf` falla: hoy no se borra ninguno
    de los dos, porque `tar.unlink()` esta DESPUES del comando que revento."""
    escenario.falla("tar", subprocess.CalledProcessError(1, ["tar"]))

    with pytest.raises(subprocess.CalledProcessError):
        escenario.mod.main()

    assert not escenario.tar.exists(), "el tar sobrevivio al fallo de extraccion"
    assert not escenario.lab.exists(), "el laboratorio sobrevivio al fallo de extraccion"


def test_un_fallo_antes_de_crear_el_tar_no_sustituye_la_excepcion_original(escenario):
    """RED, y ademas la guarda del defecto mas probable de la propia correccion.

    Si `git archive` falla, el tar NUNCA llega a existir. Un `finally` escrito como
    `tar.unlink()` sin `missing_ok` lanzaria `FileNotFoundError` DENTRO del finally, que sustituiria
    al `CalledProcessError` original y ademas impediria el `rmtree` posterior: el remedio causaria
    el dano. Esta prueba exige la excepcion original, por identidad, no solo por tipo."""
    original = subprocess.CalledProcessError(128, ["git", "archive"])
    escenario.falla("git", original)

    with pytest.raises(subprocess.CalledProcessError) as info:
        escenario.mod.main()

    assert info.value is original, "el finally sustituyo la excepcion original"
    assert not escenario.lab.exists(), "el laboratorio sobrevivio al fallo de git archive"


def test_el_laboratorio_no_sobrevive_a_un_fallo_al_escribir_la_evidencia(escenario, monkeypatch):
    """RED. El disco lleno es el escenario que origino D-5, y golpea justo al escribir la evidencia
    -linea 192-, que hoy esta ANTES de la limpieza. La medicion se pierde y encima quedan los 9 MB."""
    real_write = pathlib.Path.write_text

    def write_text(self, *a, **kw):
        if self.name.startswith("evidencia-"):
            raise OSError(28, "No space left on device")
        return real_write(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "write_text", write_text)

    with pytest.raises(OSError):
        escenario.mod.main()

    assert not escenario.lab.exists(), "el laboratorio sobrevivio al fallo de escritura"


def test_ctrl_c_limpia_el_laboratorio(escenario):
    """La afirmacion del docstring de este fichero, ahora con prueba detras.

    Se decia que SIGINT queda cubierto "gratis" porque Python ya instala `default_int_handler` y
    `KeyboardInterrupt` es una excepcion, asi que el `finally` la atrapa sin escribir una linea sobre
    senales. Era cierto -lo verifico una auditoria independiente- pero **no habia test que lo
    demostrara**: una afirmacion sin prueba dentro de un fichero de pruebas es la forma leve del
    patron que este proyecto persigue.

    Importa porque Ctrl-C es el aborto humano mas probable en una campana larga, y es la unica de
    las cuatro senales que el alcance de D-5 SI cubre. Las otras tres -SIGTERM, SIGHUP, SIGQUIT- y
    SIGKILL quedan fuera por decision del CEO, y no se prueban porque no se garantizan.
    """
    escenario.falla("arnes", KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        escenario.mod.main()

    assert not escenario.lab.exists(), "el laboratorio sobrevivio a Ctrl-C"
    assert not escenario.tar.exists(), "el tar sobrevivio a Ctrl-C"


# =================================================== CONTROLES · lo que ya funciona --
#
# Sin estos, "limpiar siempre" se cumpliria borrandolo todo, evidencia incluida. No son RED: se
# declaran como controles de regresion, no como deuda pendiente.


def test_el_camino_feliz_limpia_el_laboratorio_y_el_tar(escenario):
    """CONTROL. Ya pasa hoy. Existe para que la correccion no rompa lo que funcionaba."""
    assert escenario.mod.main() == 0
    assert not escenario.lab.exists()
    assert not escenario.tar.exists()


def test_el_camino_feliz_conserva_la_evidencia(escenario, tmp_path):
    """CONTROL. La evidencia vive FUERA del laboratorio y la limpieza no puede alcanzarla. Sin esta
    prueba, un `rmtree` mal dirigido podria llevarsela sin que nada fallara."""
    escenario.mod.main()

    evidencias = list(tmp_path.glob("evidencia-*.json"))
    assert len(evidencias) == 1, f"la evidencia no se conservo: {evidencias}"
    assert evidencias[0].stat().st_size > 0


def test_datos_nunca_se_pasa_a_rmtree(escenario):
    """CONTROL REFORZADO. `datos` se conserva por decision del CEO: contiene `audit.jsonl`,
    `memoria.json` y `estado_operativo.jsonl`, y tras esta correccion es el UNICO rastro post-mortem
    que sobrevive a un aborto -el laboratorio ya no queda para inspeccionarlo-.

    La asercion no es "existe" -eso pasaria por omision, porque hoy nada lo borra- sino que el
    espia de `rmtree` no lo recibio nunca. La trampa del escenario revienta en el acto si ocurre."""
    escenario.mod.main()

    assert escenario.datos not in escenario.rmtree_recibio, "`datos` se paso a rmtree"
    assert escenario.datos.exists(), "`datos` fue borrado"
