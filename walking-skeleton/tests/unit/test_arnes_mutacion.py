"""Meta-pruebas del arnes de mutacion (herramientas/mutar.py).

El arnes de mutacion es la unica linea de defensa contra un peligro concreto: un arnes ad-hoc
anterior declaro "7 mutantes sobreviven" en produccion y la afirmacion era FALSA, porque parseaba
el texto de salida de pytest en vez de mirar el codigo de retorno. Un arnes que miente es peor que
no tener arnes, porque genera confianza donde no la hay.

Estas pruebas verifican el arnes A EL MISMO, con un mini-proyecto de juguete creado en tmp_path
(NUNCA el codigo real de AURA: si usaramos codigo real, un cambio futuro en ese codigo rompería
estas meta-pruebas por razones ajenas al arnes). La mas importante es la que reproduce el fallo
historico: un mutante que la prueba de juguete NO cubre debe reportarse como "SOBREVIVE", nunca
como "detectado". Si esa prueba fallara, el arnes estaria mintiendo otra vez.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

from herramientas import mutar
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


def _crear_proyecto_juguete(tmp_path: Path) -> None:
    """Mini-proyecto: un modulo con dos funciones y una prueba que cubre solo una de ellas.

    sumar() esta cubierta por test_sumar_cubierta -> un mutante ahi debe ser detectado.
    restar() NO tiene ninguna prueba -> un mutante ahi debe sobrevivir.
    """
    modulo = tmp_path / "modulo_juguete.py"
    modulo.write_text(
        textwrap.dedent(
            """\
            def sumar(a, b):
                return a + b


            def restar(a, b):
                return a - b
            """
        ),
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_modulo_juguete.py").write_text(
        textwrap.dedent(
            """\
            from modulo_juguete import sumar


            def test_sumar_cubierta():
                assert sumar(2, 3) == 5
            """
        ),
        encoding="utf-8",
    )


def _escribir_toml(tmp_path: Path, contenido: str) -> Path:
    ruta = tmp_path / "mutaciones.toml"
    ruta.write_text(textwrap.dedent(contenido), encoding="utf-8")
    return ruta


def test_mutante_cubierto_por_la_prueba_es_detectado(tmp_path):
    """sumar() esta cubierta: mutar `+` a `-` DEBE romper la prueba -> estado 'detectado'."""
    _crear_proyecto_juguete(tmp_path)
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: mutante cubierto"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M1"
        garantia = "sumar debe sumar, no restar"
        fichero = "modulo_juguete.py"
        buscar = "return a + b"
        sustituir = "return a - b"
        """,
    )

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert resultado.base_verde is True
    assert resultado.detectados == 1
    assert resultado.supervivientes == 0
    assert resultado.no_aplicados == 0
    assert len(resultado.resultados) == 1
    assert resultado.resultados[0].id == "M1"
    assert resultado.resultados[0].estado == "detectado"
    assert resultado.resultados[0].garantia == "sumar debe sumar, no restar"


def test_mutante_no_cubierto_sobrevive_reproduce_el_fallo_historico(tmp_path):
    """restar() NO tiene ninguna prueba: el mutante DEBE sobrevivir.

    Esta es la meta-prueba mas importante del arnes: si aqui se reportara "detectado", el arnes
    estaria mintiendo exactamente como lo hizo el arnes ad-hoc que fallo en produccion.
    """
    _crear_proyecto_juguete(tmp_path)
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: mutante no cubierto"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M2"
        garantia = "restar debe restar, no sumar"
        fichero = "modulo_juguete.py"
        buscar = "return a - b"
        sustituir = "return a + b"
        """,
    )

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert resultado.base_verde is True
    assert resultado.detectados == 0
    assert resultado.supervivientes == 1
    assert resultado.no_aplicados == 0
    assert resultado.resultados[0].estado == "SOBREVIVE"


def test_base_en_rojo_no_ejecuta_ningun_mutante(tmp_path):
    """Si las pruebas declaradas ya fallan ANTES de mutar, no se informa de ningun mutante."""
    _crear_proyecto_juguete(tmp_path)
    # Rompemos la base: la prueba importa algo que no existe en el modulo.
    (tmp_path / "tests" / "test_modulo_juguete.py").write_text(
        textwrap.dedent(
            """\
            from modulo_juguete import funcion_que_no_existe


            def test_siempre_falla():
                assert funcion_que_no_existe() == 1
            """
        ),
        encoding="utf-8",
    )
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: base en rojo"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M1"
        garantia = "no deberia evaluarse, la base ya esta rota"
        fichero = "modulo_juguete.py"
        buscar = "return a + b"
        sustituir = "return a - b"
        """,
    )

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert resultado.base_verde is False
    assert resultado.resultados == []
    assert resultado.detectados == 0
    assert resultado.supervivientes == 0
    assert resultado.no_aplicados == 0


def test_patron_inexistente_es_no_aplicado_y_no_cuenta_como_detectado(tmp_path):
    """Si `buscar` no aparece en el fichero, el estado es NO_APLICADO, jamas 'detectado'."""
    _crear_proyecto_juguete(tmp_path)
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: patron inexistente"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M3"
        garantia = "patron que no existe en el fichero de juguete"
        fichero = "modulo_juguete.py"
        buscar = "return a * b"
        sustituir = "return a / b"
        """,
    )

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert resultado.base_verde is True
    assert resultado.resultados[0].estado == "NO_APLICADO"
    assert resultado.detectados == 0
    assert resultado.no_aplicados == 1


def test_el_fichero_mutado_se_restaura_byte_a_byte(tmp_path):
    """Tras ejecutar, el fichero mutado debe quedar identico byte a byte al original."""
    _crear_proyecto_juguete(tmp_path)
    fichero = tmp_path / "modulo_juguete.py"
    original = fichero.read_bytes()
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: restauracion"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M1"
        garantia = "sumar debe sumar, no restar"
        fichero = "modulo_juguete.py"
        buscar = "return a + b"
        sustituir = "return a - b"
        """,
    )

    ejecutar(str(toml), raiz=str(tmp_path))

    assert fichero.read_bytes() == original


def test_restauracion_incluso_si_subprocess_lanza_excepcion(tmp_path, monkeypatch):
    """Si el subprocess de pytest lanza una excepcion evaluando el mutante, el fichero se restaura
    igual.

    La restauracion va en un try/finally: la excepcion debe seguir propagandose (el arnes no la
    esconde, porque esconderla seria otra forma de mentir), pero el contenido original queda a
    salvo pase lo que pase.

    Se monkeypatchea `subprocess.Popen` (no `subprocess.run`): desde el timeout por mutante
    (2026-08-04) `_ejecutar_pytest` gestiona el Popen a mano -para poder matar el grupo de procesos
    completo al agotarse el plazo, ver `_matar_arbol_de_procesos`- en vez de usar `subprocess.run`.
    """
    _crear_proyecto_juguete(tmp_path)
    fichero = tmp_path / "modulo_juguete.py"
    original = fichero.read_bytes()
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: excepcion en subprocess"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M1"
        garantia = "sumar debe sumar, no restar"
        fichero = "modulo_juguete.py"
        buscar = "return a + b"
        sustituir = "return a - b"
        """,
    )

    llamadas = {"n": 0}
    original_popen = subprocess.Popen

    def popen_que_explota_en_la_segunda_llamada(*args, **kwargs):
        # 1a llamada: verificacion de base en verde (debe pasar de verdad).
        # 2a llamada: evaluacion del mutante -> aqui simulamos que Popen explota.
        llamadas["n"] += 1
        if llamadas["n"] >= 2:
            raise OSError("fallo simulado de subprocess")
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen_que_explota_en_la_segunda_llamada)

    with pytest.raises(OSError):
        ejecutar(str(toml), raiz=str(tmp_path))

    assert fichero.read_bytes() == original


# --------------------------------------------------------------------------------------------
# Meta-pruebas de la CAPA CLI y de los casos que no permiten concluir.
#
# La auditoria independiente (2026-08-02) encontro que `main()` y su mapeo de codigos de salida no
# estaban cubiertos: mutando `main()` a `return 0` incondicional, las meta-pruebas seguian en verde.
# Era el fallo historico repetido una capa mas arriba, y en la que de verdad se consume como senal:
# un hook o una CI leen el exit code, no el dataclass.
# --------------------------------------------------------------------------------------------


def _toml_de_un_mutante(tmp_path: Path, buscar: str, sustituir: str) -> Path:
    return _escribir_toml(
        tmp_path,
        f"""\
        incremento = "juguete"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M1"
        garantia = "sumar suma"
        fichero = "modulo_juguete.py"
        buscar = '''{buscar}'''
        sustituir = '''{sustituir}'''
        """,
    )


def test_main_devuelve_0_solo_si_todos_los_mutantes_mueren(tmp_path):
    """`exit 0` es la senal de "todo protegido". Si mintiera aqui, un hook o una CI se lo creerian."""
    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a + b", "return 0")
    assert mutar.main([str(toml), "--raiz", str(tmp_path)]) == 0


def test_main_devuelve_2_si_algun_mutante_sobrevive(tmp_path):
    """Un superviviente NUNCA puede reportarse como exito: es una garantia sin red."""
    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a - b", "return 0")  # restar() no tiene prueba
    assert mutar.main([str(toml), "--raiz", str(tmp_path)]) == 2


def test_main_devuelve_1_si_la_base_no_esta_en_verde(tmp_path):
    """Base rota tiene codigo PROPIO: confundirla con un superviviente ocultaria el motivo real."""
    _crear_proyecto_juguete(tmp_path)
    (tmp_path / "modulo_juguete.py").write_text("def sumar(a, b):\n    return 999\n", encoding="utf-8")
    toml = _toml_de_un_mutante(tmp_path, "return 999", "return 0")
    assert mutar.main([str(toml), "--raiz", str(tmp_path)]) == 1


def test_patron_repetido_es_ambiguo_y_no_sobrevive_falsamente(tmp_path):
    """Con el patron repetido se mutaria la PRIMERA aparicion —quiza un comentario— y el resultado
    seria un "SOBREVIVE" que parece un hueco de cobertura y en realidad es una declaracion mal escrita."""
    _crear_proyecto_juguete(tmp_path)
    modulo = tmp_path / "modulo_juguete.py"
    modulo.write_text(modulo.read_text(encoding="utf-8").replace("def sumar", "# return a + b\ndef sumar", 1), "utf-8")
    resultado = ejecutar(str(_toml_de_un_mutante(tmp_path, "return a + b", "return 0")), raiz=str(tmp_path))
    assert resultado.resultados[0].estado == "AMBIGUO", "el patron repetido debe rechazarse, no adivinarse"
    assert resultado.concluyente is False


def test_mutante_que_rompe_la_sintaxis_no_cuenta_como_detectado(tmp_path):
    """pytest falla por ERROR de coleccion, no porque una prueba ejercite la garantia.

    Contarlo como "detectado" daria por protegida una garantia que nadie llego a probar.
    """
    _crear_proyecto_juguete(tmp_path)
    resultado = ejecutar(str(_toml_de_un_mutante(tmp_path, "return a + b", "return =!= b")), raiz=str(tmp_path))
    assert resultado.resultados[0].estado == "AMBIGUO", "un mutante que ni compila no prueba nada"
    assert resultado.detectados == 0


def test_mutante_identico_no_degrada_nada(tmp_path):
    """`buscar == sustituir` no degrada: su "SOBREVIVE" no informaria de ningun hueco real."""
    _crear_proyecto_juguete(tmp_path)
    resultado = ejecutar(str(_toml_de_un_mutante(tmp_path, "return a + b", "return a + b")), raiz=str(tmp_path))
    assert resultado.resultados[0].estado == "AMBIGUO"


def test_la_verificacion_de_restauracion_esta_viva(tmp_path, monkeypatch):
    """Si la restauracion fallara en silencio, el arnes dejaria el repositorio corrupto sin avisar."""
    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a + b", "return 0")
    real = mutar._escribir_atomico

    def sabotea_la_restauracion(ruta, datos):
        # Deja pasar la escritura del mutante (y el diario) pero ignora la restauracion: simula un disco que
        # miente. Desde 2026-10-06 el arnes escribe con `_escribir_atomico` (temporal + os.replace), no con
        # `Path.write_bytes`: el sabotaje va a esa costura para seguir ejercitando la verificacion.
        if b"return 0" in datos or ruta.name == mutar._DIARIO:
            return real(ruta, datos)
        return None

    monkeypatch.setattr(mutar, "_escribir_atomico", sabotea_la_restauracion)
    with pytest.raises(RuntimeError, match="restaurar"):
        ejecutar(str(toml), raiz=str(tmp_path))


# --------------------------------------------------------------------------------------------
# Meta-pruebas del TIMEOUT por mutante (2026-08-04).
#
# Dano ya documentado en mutaciones/motor-ciclo.toml: los mutantes M2 y M3 degradaban la
# condicion de parada de un bucle y el arnes se colgaba EN VEZ de reportar SOBREVIVE, porque
# `_ejecutar_pytest` no imponia ningun limite de tiempo al subprocess de pytest. Un proceso
# huerfano llego a quedar 15+ horas consumiendo CPU en un equipo de 2 nucleos.
#
# El proyecto de juguete de aqui abajo reproduce el bug DE VERDAD: su mutante produce un bucle
# infinito real (`while True: pass`, sin valvula de escape) y ademas lanza un proceso HIJO
# propio, para poder comprobar que el arnes no lo deja huerfano al matar el arbol completo.
# --------------------------------------------------------------------------------------------


def _crear_proyecto_que_cuelga(tmp_path: Path) -> None:
    """Proyecto de juguete cuyo mutante cuelga de verdad (reproduce M2/M3 de motor-ciclo.toml).

    `trabajo()` lanza un proceso hijo propio (un `sleep` en Python, sin dependencias del SO) y dejar
    escrito su PID en un fichero ANTES de decidir si para o no: eso permite que la meta-prueba
    compruebe, despues de que el arnes actue, si ese proceso hijo sigue vivo (huerfano) o no.

    La duracion del sleep (20s) es DELIBERADAMENTE mayor que `timeout_s` (ver `_toml_que_cuelga`):
    si el hijo se autoterminara ANTES de que el arnes lo mate, `test_no_deja_procesos_huerfanos_tras_el_timeout`
    pasaria de forma VACUA -el proceso habria muerto solo, no por el SIGKILL del arnes- y no
    demostraria nada. Con 20s > timeout_s, el hijo sigue vivo cuando el timeout vence, asi que
    matarlo (o no) es lo unico que decide el resultado de la prueba. Sigue siendo acotado: incluso si
    algun mutante de `arnes-timeout.toml` llegase a dejar escapar el proceso, se autolimpia en
    segundos, no minutos ni horas.
    """
    modulo = tmp_path / "modulo_cuelga.py"
    modulo.write_text(
        textwrap.dedent(
            """\
            import subprocess
            import sys
            from pathlib import Path


            def condicion_de_parada():
                return True


            def trabajo():
                proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
                Path(RUTA_PID).write_text(str(proc.pid))
                if condicion_de_parada():
                    return "listo"
                while True:
                    pass  # bucle infinito real: reproduce el bug de motor-ciclo.toml M2/M3
            """
        ).replace("RUTA_PID", repr(str(tmp_path / "pid_hijo.txt"))),  # absoluta: pytest corre en una copia aislada
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_modulo_cuelga.py").write_text(
        textwrap.dedent(
            """\
            from modulo_cuelga import trabajo


            def test_trabajo_termina():
                assert trabajo() == "listo"
            """
        ),
        encoding="utf-8",
    )


def _toml_que_cuelga(tmp_path: Path, timeout_s: float = 8.0) -> Path:
    # 8s (no 2s): el chequeo de "base en verde" tambien pasa por este timeout, y un valor demasiado
    # ajustado convierte una maquina momentaneamente cargada (CI compartida, otras pruebas todavia
    # liberando CPU) en una BASE EN ROJO falsa -medido en esta misma verificacion bajo carga real.
    return _escribir_toml(
        tmp_path,
        f"""\
        incremento = "juguete: mutante que cuelga"
        pruebas = ["tests/test_modulo_cuelga.py"]
        timeout_s = {timeout_s}

        [[mutante]]
        id = "M1"
        garantia = "la condicion de parada deja de parar: bucle infinito"
        fichero = "modulo_cuelga.py"
        buscar = "return True"
        sustituir = "return False"
        """,
    )


def test_mutante_que_cuelga_se_reporta_como_timeout_y_no_bloquea_el_arnes(tmp_path):
    """OBLIGATORIA (a): un mutante cuyas pruebas cuelgan se reporta y NO bloquea el arnes.

    Sin timeout, esta linea nunca devuelve: `ejecutar()` se queda esperando al subprocess de
    pytest para siempre. Con timeout, debe devolver en un tiempo acotado y el mutante debe
    quedar marcado de forma que NUNCA cuente como "detectado" ni como exito del conjunto.
    """
    _crear_proyecto_que_cuelga(tmp_path)
    toml = _toml_que_cuelga(tmp_path)

    inicio = time.monotonic()
    resultado = ejecutar(str(toml), raiz=str(tmp_path))
    duracion = time.monotonic() - inicio

    assert duracion < 40, f"el arnes debio cortar el mutante colgado en ~8s, tardo {duracion:.1f}s"
    assert resultado.base_verde is True
    assert len(resultado.resultados) == 1
    assert resultado.resultados[0].estado != "detectado", "un mutante colgado JAMAS puede contar como detectado"
    assert resultado.resultados[0].estado == "TIMEOUT"
    assert resultado.concluyente is False, "un mutante en TIMEOUT no puede dejar el conjunto como exito"


def test_el_fichero_se_restaura_aunque_el_mutante_cuelgue(tmp_path):
    """OBLIGATORIA (b): tras el timeout el fichero mutado queda RESTAURADO byte a byte."""
    _crear_proyecto_que_cuelga(tmp_path)
    fichero = tmp_path / "modulo_cuelga.py"
    original = fichero.read_bytes()
    toml = _toml_que_cuelga(tmp_path)

    ejecutar(str(toml), raiz=str(tmp_path))

    assert fichero.read_bytes() == original


def test_no_deja_procesos_huerfanos_tras_el_timeout(tmp_path):
    """OBLIGATORIA (c): tras el timeout NO quedan procesos huerfanos.

    El mutante lanza un proceso hijo propio (ver `_crear_proyecto_que_cuelga`). Si el arnes solo
    matara el proceso de pytest directo (y no el ARBOL completo), ese hijo quedaria huerfano y
    seguiria vivo. Se comprueba con `os.kill(pid, 0)`: si el proceso sigue vivo no lanza excepcion.
    """
    _crear_proyecto_que_cuelga(tmp_path)
    toml = _toml_que_cuelga(tmp_path)

    ejecutar(str(toml), raiz=str(tmp_path))

    ruta_pid = tmp_path / "pid_hijo.txt"
    assert ruta_pid.exists(), "el proceso hijo no llego a escribir su PID: la prueba de juguete no es valida"
    pid_hijo = int(ruta_pid.read_text().strip())

    time.sleep(0.5)  # margen breve por si el SO tarda un instante en liberar el PID tras el SIGKILL
    with pytest.raises(ProcessLookupError):
        os.kill(pid_hijo, 0)


def test_main_devuelve_2_si_un_mutante_esta_en_timeout(tmp_path):
    """El TIMEOUT tambien debe reflejarse en el codigo de salida de la CLI, no solo en el dataclass:
    es el codigo el que consume un hook o una CI, no el objeto Python."""
    _crear_proyecto_que_cuelga(tmp_path)
    toml = _toml_que_cuelga(tmp_path)

    assert mutar.main([str(toml), "--raiz", str(tmp_path)]) == 2


def test_timeout_s_del_toml_se_pasa_a_ejecutar_pytest(tmp_path, monkeypatch):
    """El `timeout_s` declarado en el TOML debe llegar de verdad a `_ejecutar_pytest`, no quedarse
    como una clave leida y nunca usada.

    Se verifica CAPTURANDO el argumento (rapido, sin depender del reloj) en vez de comprobar cuanto
    tarda un mutante colgado en cortarse: si esta wiring se rompiera y `ejecutar()` volviera a usar
    siempre `_TIMEOUT_S_POR_DEFECTO`, un timeout corto declarado en un TOML real (como los 10s de
    `mutaciones/motor-ciclo.toml`) se ignoraria en silencio y cualquier mutante que cuelgue tardaria
    el DEFAULT completo en reportarse -exactamente la lentitud que declarar un timeout corto existe
    para evitar.
    """
    _crear_proyecto_juguete(tmp_path)
    toml = _escribir_toml(
        tmp_path,
        """\
        incremento = "juguete: timeout_s personalizado"
        pruebas = ["tests/test_modulo_juguete.py"]
        timeout_s = 12.5

        [[mutante]]
        id = "M1"
        garantia = "sumar debe sumar, no restar"
        fichero = "modulo_juguete.py"
        buscar = "return a + b"
        sustituir = "return a - b"
        """,
    )
    capturados: list[float] = []
    original = mutar._ejecutar_pytest

    def espia(pruebas, raiz, timeout_s):
        capturados.append(timeout_s)
        return original(pruebas, raiz, timeout_s)

    monkeypatch.setattr(mutar, "_ejecutar_pytest", espia)

    ejecutar(str(toml), raiz=str(tmp_path))

    assert capturados, "nunca se llamo a _ejecutar_pytest: la prueba de juguete no es valida"
    assert all(t == 12.5 for t in capturados), f"timeout_s del TOML no llego a _ejecutar_pytest: {capturados}"


# --------------------------------------------------------------------------------------------
# La mutacion NUNCA escribe en el arbol original (2026-10-25).
#
# Medido `[EJEC]`: el servicio `aura-receptor-nodos` (credencial real) carga 67 modulos del worktree, y el
# despertador de AURORA importa el plano de control ANTES de comprobar PARADA. Una bateria muto en el sitio
# `composicion.py` y `ejecutor_modelo_usuario.py`, que el receptor carga: un reinicio en esa ventana habria
# arrancado produccion con un mutante. El arnes trabaja ahora sobre una COPIA aislada fuera del proyecto; el
# arbol original solo se lee.


def _huella(raiz: Path) -> dict[str, tuple[str, int]]:
    """Contenido y mtime de cada fichero: «no se toco» exige las dos cosas (restaurar cambia el mtime)."""
    import hashlib

    return {
        str(p.relative_to(raiz)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        for p in sorted(raiz.rglob("*"))
        if p.is_file() and not ({"__pycache__", ".pytest_cache"} & set(p.parts))
    }


def _espiar_pytest(monkeypatch, original: Path, interrumpir_en: int | None = None) -> list[tuple[str, dict]]:
    """Registra en que raiz corre cada pytest y como esta el arbol ORIGINAL en ese instante."""
    vistas: list[tuple[str, dict]] = []
    real = mutar._ejecutar_pytest

    def espia(pruebas, raiz, timeout_s):
        vistas.append((raiz, _huella(original)))
        if interrumpir_en is not None and len(vistas) == interrumpir_en:
            raise KeyboardInterrupt
        return real(pruebas, raiz, timeout_s)

    monkeypatch.setattr(mutar, "_ejecutar_pytest", espia)
    return vistas


def test_mientras_corre_el_mutante_el_arbol_original_no_cambia_ni_en_contenido_ni_en_mtime(tmp_path, monkeypatch):
    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a + b", "return 0")
    antes = _huella(tmp_path)
    vistas = _espiar_pytest(monkeypatch, tmp_path)

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert resultado.detectados == 1, "control: el mutante se aplico (en algun sitio) y una prueba lo mato"
    assert len(vistas) == 2, vistas  # base + mutante
    assert all(huella == antes for _, huella in vistas), "el arbol original cambio mientras pytest corria"
    assert _huella(tmp_path) == antes, "el arbol original quedo con otro contenido o mtime"


def test_pytest_corre_en_una_copia_fuera_del_proyecto_que_se_borra_al_terminar(tmp_path, monkeypatch):
    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a + b", "return 0")
    vistas = _espiar_pytest(monkeypatch, tmp_path)

    ejecutar(str(toml), raiz=str(tmp_path))

    for raiz, _ in vistas:
        assert not Path(raiz).resolve().is_relative_to(tmp_path.resolve()), f"pytest corrio dentro del proyecto: {raiz}"
        assert Path(raiz).name == tmp_path.name, "la copia conserva el nombre del proyecto (rutas relativas)"
    assert not any(Path(raiz).exists() for raiz, _ in vistas), "la copia aislada no se borro al terminar"


def test_una_interrupcion_durante_el_mutante_no_toca_el_original_y_borra_la_copia(tmp_path, monkeypatch):
    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a + b", "return 0")
    antes = _huella(tmp_path)
    vistas = _espiar_pytest(monkeypatch, tmp_path, interrumpir_en=2)

    with pytest.raises(KeyboardInterrupt):
        ejecutar(str(toml), raiz=str(tmp_path))

    assert len(vistas) == 2, "control: la interrupcion llego con el mutante aplicado"
    assert _huella(tmp_path) == antes
    assert not (tmp_path / mutar._DIARIO).exists(), "el diario de la mutacion no pertenece al arbol original"
    assert not Path(vistas[-1][0]).exists(), "la copia aislada no se borro tras la interrupcion"


def test_en_un_repositorio_se_copia_el_proyecto_entero_sin_git(tmp_path, monkeypatch):
    """Las pruebas reales leen ficheros hermanos (`entorno/`, `milestones/`): se copia la raiz del repositorio."""
    proyecto = tmp_path / "repo"
    sub = proyecto / "sub"
    sub.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proyecto)], check=True)
    (proyecto / "hermano.txt").write_text("dato hermano", encoding="utf-8")
    _crear_proyecto_juguete(sub)
    (sub / "tests" / "test_hermano.py").write_text(
        "from pathlib import Path\n\n\ndef test_ve_al_hermano():\n"
        "    assert (Path.cwd().parent / 'hermano.txt').read_text() == 'dato hermano'\n",
        encoding="utf-8",
    )
    toml = _escribir_toml(
        sub,
        """\
        incremento = "juguete"
        pruebas = ["tests/test_modulo_juguete.py", "tests/test_hermano.py"]

        [[mutante]]
        id = "M1"
        garantia = "sumar suma"
        fichero = "modulo_juguete.py"
        buscar = '''return a + b'''
        sustituir = '''return 0'''
        """,
    )
    vistas: list[str] = []
    real = mutar._ejecutar_pytest

    def espia(pruebas, raiz, timeout_s):
        vistas.append(raiz)
        assert not (Path(raiz).parent / ".git").exists(), "la copia arrastro el .git del repositorio"
        return real(pruebas, raiz, timeout_s)

    monkeypatch.setattr(mutar, "_ejecutar_pytest", espia)
    resultado = ejecutar(str(toml), raiz=str(sub))

    assert resultado.base_verde and resultado.detectados == 1, resultado
    assert vistas and all(Path(r).name == "sub" and Path(r).parent.name == "repo" for r in vistas), vistas


def test_si_la_copia_cayera_dentro_del_proyecto_el_arnes_se_niega_sin_mutar_nada(tmp_path, monkeypatch):
    """TMPDIR apuntando dentro del proyecto haria que la «copia aislada» viviera en el arbol: se rechaza."""
    import tempfile

    _crear_proyecto_juguete(tmp_path)
    toml = _toml_de_un_mutante(tmp_path, "return a + b", "return 0")
    dentro = tmp_path / "tmp-dentro"
    dentro.mkdir()
    antes = _huella(tmp_path)
    real = tempfile.mkdtemp
    monkeypatch.setattr(mutar.tempfile, "mkdtemp", lambda prefix=None: real(prefix=prefix, dir=str(dentro)))

    with pytest.raises(RuntimeError, match="dentro del proyecto"):
        ejecutar(str(toml), raiz=str(tmp_path))
    assert _huella(tmp_path) == antes, "el arnes toco el proyecto aunque rechazo la copia"
    assert list(dentro.iterdir()) == [], "el directorio rechazado no se retiro"


@pytest.mark.parametrize("como", ["absoluto", "relativo_que_sale"])
def test_un_fichero_declarado_fuera_de_la_raiz_no_se_muta_nunca(tmp_path, tmp_path_factory, como):
    """`Path(raiz) / fichero` descarta la raiz si `fichero` es absoluto, y `../` sale de ella: la copia aislada no
    protegeria nada (revision de seguridad 2026-10-25 (w), MEDIO). Se rechaza ANTES de leer o escribir."""
    _crear_proyecto_juguete(tmp_path)
    ajeno = tmp_path_factory.mktemp("fuera") / "ajeno.py"
    ajeno.write_text("def sumar(a, b):\n    return a + b\n", encoding="utf-8")
    huella_ajena = (ajeno.read_bytes(), ajeno.stat().st_mtime_ns)
    fichero = str(ajeno) if como == "absoluto" else str(Path("..") / ajeno.parent.name / ajeno.name)
    toml = _escribir_toml(
        tmp_path,
        f"""\
        incremento = "juguete"
        pruebas = ["tests/test_modulo_juguete.py"]

        [[mutante]]
        id = "M1"
        garantia = "fuera de la raiz"
        fichero = '''{fichero}'''
        buscar = '''return a + b'''
        sustituir = '''return 0'''
        """,
    )

    resultado = ejecutar(str(toml), raiz=str(tmp_path))

    assert [r.estado for r in resultado.resultados] == ["AMBIGUO"], resultado
    assert "fuera de la raiz" in resultado.resultados[0].pruebas_que_fallaron
    assert (ajeno.read_bytes(), ajeno.stat().st_mtime_ns) == huella_ajena, "se escribio un fichero fuera de la raiz"


def test_al_arrancar_se_retiran_las_copias_huerfanas_y_solo_ellas(tmp_path):
    """Un SIGKILL no ejecuta el `finally`: la copia queda. El siguiente arranque retira las copias cuyo arnes dueño
    ya no existe; nunca la de un arnes vivo ni un directorio sin marca de dueño (revision de codigo, MEDIO)."""
    import json
    import tempfile

    temporal = Path(tempfile.gettempdir())
    muerto = subprocess.Popen(["true"])
    muerto.wait()

    def copia(nombre: str, dueno: int | None) -> Path:
        d = temporal / f"{mutar._PREFIJO_COPIA}{nombre}"
        (d / "proyecto").mkdir(parents=True)
        if dueno is not None:
            campos = mutar._estado_proc(dueno)
            inicio = campos[19] if campos and len(campos) > 19 else "0"
            (d / mutar._MARCA_DUENO).write_text(json.dumps({"pid": dueno, "inicio": inicio}), encoding="utf-8")
        return d

    huerfana, viva, sin_marca = copia("huerfana", muerto.pid), copia("viva", os.getpid()), copia("sin-marca", None)
    _crear_proyecto_juguete(tmp_path)

    ejecutar(str(_toml_de_un_mutante(tmp_path, "return a + b", "return 0")), raiz=str(tmp_path))

    assert not huerfana.exists(), "la copia huerfana (dueño muerto) no se retiro"
    assert viva.exists(), "se retiro la copia de un arnes vivo"
    assert sin_marca.exists(), "se retiro un directorio sin marca de dueño"


def test_sin_git_se_copia_la_raiz_pedida_y_el_arnes_sigue(tmp_path, monkeypatch):
    real = mutar.subprocess.run

    def sin_git(argv, *a, **k):
        if argv and argv[0] == "git":
            raise FileNotFoundError("git")
        return real(argv, *a, **k)

    monkeypatch.setattr(mutar.subprocess, "run", sin_git)
    _crear_proyecto_juguete(tmp_path)
    resultado = ejecutar(str(_toml_de_un_mutante(tmp_path, "return a + b", "return 0")), raiz=str(tmp_path))
    assert resultado.base_verde and resultado.detectados == 1, resultado


def test_control_un_fichero_hermano_dentro_del_repositorio_copiado_si_se_muta(tmp_path):
    """Control de la contencion: `../x` es legitimo si sigue DENTRO del repositorio copiado (p. ej. los mutantes de
    `../entorno/scripts/voz-usb.sh` desde walking-skeleton). El limite es la copia, no la raiz pedida."""
    proyecto = tmp_path / "repo"
    sub = proyecto / "sub"
    sub.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proyecto)], check=True)
    (proyecto / "modulo_hermano.py").write_text("def sumar(a, b):\n    return a + b\n", encoding="utf-8")
    (sub / "tests").mkdir()
    (sub / "tests" / "test_hermano.py").write_text(
        "import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path.cwd().parent))\n"
        "from modulo_hermano import sumar\n\n\ndef test_suma():\n    assert sumar(2, 3) == 5\n",
        encoding="utf-8",
    )
    toml = _escribir_toml(
        sub,
        """\
        incremento = "juguete"
        pruebas = ["tests/test_hermano.py"]

        [[mutante]]
        id = "M1"
        garantia = "el hermano suma"
        fichero = '''../modulo_hermano.py'''
        buscar = '''return a + b'''
        sustituir = '''return 0'''
        """,
    )
    original = (proyecto / "modulo_hermano.py").read_bytes()

    resultado = ejecutar(str(toml), raiz=str(sub))

    assert [r.estado for r in resultado.resultados] == ["detectado"], resultado
    assert (proyecto / "modulo_hermano.py").read_bytes() == original
