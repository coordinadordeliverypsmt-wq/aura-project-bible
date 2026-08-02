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

import subprocess
import textwrap
from pathlib import Path

import pytest

from herramientas import mutar
from herramientas.mutar import ejecutar


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
    """Si subprocess.run lanza una excepcion evaluando el mutante, el fichero se restaura igual.

    La restauracion va en un try/finally: la excepcion debe seguir propagandose (el arnes no la
    esconde, porque esconderla seria otra forma de mentir), pero el contenido original queda a
    salvo pase lo que pase.
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
    original_run = subprocess.run

    def run_que_explota_en_la_segunda_llamada(*args, **kwargs):
        # 1a llamada: verificacion de base en verde (debe pasar de verdad).
        # 2a llamada: evaluacion del mutante -> aqui simulamos que subprocess explota.
        llamadas["n"] += 1
        if llamadas["n"] >= 2:
            raise OSError("fallo simulado de subprocess")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run_que_explota_en_la_segunda_llamada)

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
    real = Path.write_bytes

    def sabotea_la_restauracion(self, datos):
        # Deja pasar la escritura del mutante pero ignora la restauracion: simula un disco que miente.
        if b"return 0" in datos:
            return real(self, datos)
        return len(datos)

    monkeypatch.setattr(Path, "write_bytes", sabotea_la_restauracion)
    with pytest.raises(RuntimeError, match="restaurar"):
        ejecutar(str(toml), raiz=str(tmp_path))
