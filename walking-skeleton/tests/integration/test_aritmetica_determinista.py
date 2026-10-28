"""Integración (CEO, 2026-09-01): `1+1` lo resuelve el núcleo, no el modelo.

    tu>   cuanto es 1+1
    AURA> Entendido.

`«cuanto es 1+1»` no tenía superficie propia, así que recorría la cascada entera y la contestaba el
enrutador con su respuesta enlatada (`router.py:51`). Que en el modo simulado saliera «Entendido.» y
con un modelo real quizá saliera «2» es justamente el problema: **una suma no es una inferencia**.
Es la misma regla que ADR-0014 aplica al resto del sistema, y aquí hay poco margen de duda sobre si
`1+1` es un hecho.

DOS FAMILIAS DE PRUEBAS, Y LA SEGUNDA IMPORTA MÁS.

La primera comprueba que las cuentas salen. La segunda, que **nada más** se cuela por esta puerta: el
texto del usuario llega a un evaluador, y un evaluador que acepte de más ejecuta código ajeno. Por eso
`«__import__('os').system('ls')»` y `«2**10»` tienen su prueba, y por eso `«borra 2 archivos»` —que
lleva un número— tiene que seguir su camino.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core import aritmetica as ar


async def _di(orq, texto, uid="mauricio"):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


@pytest.fixture
def sistema(tmp_path):
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg)


# ============================================================ 1–9 · LAS CUENTAS SALEN --

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("1+1", "2."),
        ("cuánto es 1+1", "2."),               # con acento
        ("cuanto es 1+1", "2."),               # sin acento: la frase LITERAL del CEO
        ("¿Cuánto es 1+1?", "2."),             # con signos
        ("10 + 5", "15."),
        ("20 - 3", "17."),
        ("7 * 8", "56."),
        ("7 por 8", "56."),                    # el operador dicho en castellano
        ("12 / 4", "3."),
        ("2 + 3 * 4", "14."),                  # precedencia: NO es 20
        ("(2 + 3) * 4", "20."),                # y los paréntesis la cambian
        ("100 menos 1", "99."),
        ("10 dividido entre 2", "5."),
        ("-3 + 10", "7."),                     # signo unario
    ],
)
async def test_la_operacion_la_resuelve_EL_NUCLEO_y_es_correcta(sistema, frase, esperado):
    r = await _di(sistema.orquestador, frase)
    assert r["say"] == esperado, f"{frase!r} -> {r['say']!r}"
    assert r["provider"] == "core", f"{frase!r} acabó en {r['provider']!r}: una suma no es una inferencia"


def test_la_PRECEDENCIA_no_es_de_izquierda_a_derecha():
    """El control que hace que la prueba anterior signifique algo: si se evaluara en orden, `2+3*4`
    daría 20 y las dos aserciones de arriba serían compatibles con un evaluador roto."""
    assert ar.resolver("2 + 3 * 4") == "14."
    assert ar.resolver("(2 + 3) * 4") == "20."
    assert ar.resolver("2 + 3 * 4") != ar.resolver("(2 + 3) * 4")


def test_el_resultado_es_EXACTO_y_no_se_finge_precision():
    """Se calcula con `Fraction`, no con `float`. Y al presentar: entero si lo es, decimal si TERMINA,
    y la fracción exacta si no termina — escribir `0.3333` sería inventarle un final a un número que
    no lo tiene."""
    assert ar.resolver("12 / 4") == "3."
    assert ar.resolver("7 / 2") == "3.5"
    assert ar.resolver("1 / 3") == "1/3."
    assert ar.resolver("(1 / 3) * 3") == "1.", "con float esto no sería exacto"


# ============================================================ 10–12 · LO QUE NO SE CONTESTA --

@pytest.mark.asyncio
async def test_la_DIVISION_POR_CERO_se_declara_y_no_se_inventa(sistema):
    """Es aritmética, y su respuesta es que no existe. Dejarla caer al modelo produciría cualquier
    cosa para una operación que no tiene resultado."""
    r = await _di(sistema.orquestador, "cuanto es 1/0")
    assert "no está definida" in r["say"]
    assert r["provider"] == "core"


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["1 + * 2", "cuanto es 5 +", "((2+3)", "cuanto es dos mas dos"])
async def test_una_expresion_INVALIDA_no_inventa_un_numero(sistema, frase):
    """No se contesta «no lo sé»: se deja pasar. Devolver un texto aquí le robaría el turno a las
    superficies siguientes, que es como esta capacidad rompería el resto del sistema."""
    r = await _di(sistema.orquestador, frase)
    assert ar.resolver(frase) is None
    assert not any(c.isdigit() for c in r["say"]) or r["provider"] != "core"


@pytest.mark.parametrize("frase", [
    "hola", "gracias por todo", "borra 2 archivos", "7", "¿qué tal?",
    "en que estas trabajando", "me llamo Mauricio", "tengo 3 hijos y 2 gatos",
])
def test_el_texto_NO_MATEMATICO_no_lo_intercepta(frase):
    """La guarda que sostiene todo lo demás: o la frase empieza por una entradilla declarada, o el
    texto ENTERO es una expresión. «borra 2 archivos» lleva un número y no es una cuenta."""
    assert ar.resolver(frase) is None, f"{frase!r} se interpretó como aritmética"


# ============================================================ 16 · NO EJECUTA CÓDIGO --

@pytest.mark.parametrize("ataque", [
    "__import__('os').system('ls')",
    "cuanto es __import__('os').listdir('/')",
    "open('/etc/passwd').read()",
    "2**10",                                   # potencia: fuera del alcance declarado
    "1 if True else 2",
    "[x for x in range(10)]",
    "cuanto es len('abc')",
    "int('1')+1",
])
def test_NINGUNA_expresion_ejecuta_codigo_arbitrario(ataque):
    """El texto viene del usuario. Un evaluador que acepte de más ejecuta código ajeno, así que la
    postura es la contraria: se acepta una lista de nodos y se rechaza todo lo demás."""
    assert ar.resolver(ataque) is None, f"{ataque!r} atravesó el parser"


def test_el_evaluador_NO_conoce_llamadas_ni_nombres():
    """Comprobado sobre el árbol, no sobre una lista de ataques: los ataques que se me ocurran hoy
    son un subconjunto de los posibles. Lo que vale es qué nodos tienen caso en el evaluador."""
    import ast

    for fuente in ("os.system('ls')", "f(1)", "x + 1", "'a' * 3", "1 if x else 2", "2**3"):
        with pytest.raises((ar.NoEsAritmetica, ar.DivisionPorCero)):
            ar.evaluar(fuente)
    # Se mira el ÁRBOL, no el texto: el docstring del módulo explica por qué no se usa `eval`, así
    # que buscar la cadena «eval(» cazaría la explicación en vez del uso. Prohibir que se nombre al
    # razonarlo premiaría el silencio, no la ausencia.
    texto = __import__("pathlib").Path(ar.__file__).read_text("utf-8")
    arbol = ast.parse(texto)
    llamadas = {n.func.id for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "eval" not in llamadas and "exec" not in llamadas and "compile" not in llamadas


def test_el_filtro_de_CARACTERES_no_es_redundante_con_el_parser():
    """Un mutante que quitaba el filtro sobrevivió: casi todo lo que cuela lo rechaza después el
    parser, así que parecía defensa duplicada. No lo es.

    Python acepta formas numéricas que **el usuario no escribió como aritmética**: `1_0` vale 10,
    `0x10` vale 16, `0b101` vale 5. Sin el filtro, «1_0 + 5» respondería 15 a alguien que no escribió
    ningún diez. El filtro no repite al parser: le acota lo que puede llegar a ver."""
    for exotico in ("1_0 + 5", "0x10 + 1", "0b101 + 1", "0o17 + 1"):
        assert ar.expresion_en(exotico) is None, f"{exotico!r} atravesó el filtro de caracteres"
        assert ar.resolver(exotico) is None
    # Y el control: la forma decimal de siempre sí pasa, o el filtro estaría cortando de más.
    assert ar.resolver("10 + 5") == "15."


def test_las_COTAS_impiden_bloquear_el_turno():
    """Con `*` encadenado se pueden construir enteros de millones de dígitos y multiplicarlos cuelga
    el turno. Un límite visible es preferible a descubrirlo colgado."""
    assert ar.resolver("9" * (ar.MAX_DIGITOS + 1) + " * 2") is None
    assert ar.resolver("1" + "*1" * (ar.MAX_OPERADORES + 1)) is None
    assert ar.resolver("1+1" + " " * ar.MAX_CARACTERES) is None
    # Y el control: justo por debajo del límite sí se resuelve, o la cota estaría cortando de más.
    assert ar.resolver("1" + "*1" * (ar.MAX_OPERADORES - 1)) == "1."


# ============================================================ 13–15 · REGRESIÓN --

@pytest.mark.asyncio
async def test_regresion_el_SALUDO_sigue_igual(sistema):
    r = await _di(sistema.orquestador, "hola")
    assert "hola" in r["say"].lower()
    assert r["provider"] == "core"


@pytest.mark.asyncio
async def test_regresion_la_MEMORIA_sigue_igual(sistema):
    await _di(sistema.orquestador, "me llamo Mauricio")
    r = await _di(sistema.orquestador, "¿cuál es mi nombre?")
    assert "mauricio" in r["say"].lower()


@pytest.mark.asyncio
async def test_regresion_el_ESTADO_AUTONOMO_sigue_respondiendo_desde_su_fuente(sistema, monkeypatch):
    """Y sigue viniendo del estado real, no de memoria ni del modelo: la fuente tiene que haberse
    leído, no acertarse el texto por casualidad."""
    lecturas = []

    class Fuente:
        def instantanea(self):
            lecturas.append(1)
            return {"estado": "DECISION_REQUIRED", "cola": {"OPORTUNIDAD_REAL": 0},
                    "trabajo_bloqueado": 6, "trabajo_elevado": 2, "decisiones_pendientes": [],
                    "proximo_despertar": "2026-09-01T23:00:00", "ultima_tarea": "NO DISPONIBLE"}

    monkeypatch.setattr(sistema.orquestador, "estado_autonomo", Fuente())
    r = await _di(sistema.orquestador, "¿en qué estás trabajando ahora?")
    assert lecturas, "no consultó el estado autónomo"
    assert r["provider"] == "core"
    assert "no tengo ninguna tarea autorizada" in r["say"].lower()


@pytest.mark.asyncio
async def test_la_aritmetica_NO_le_roba_el_turno_a_ninguna_superficie_previa(sistema):
    """El candado de no-interferencia. Cada frase la contesta quien la contestaba antes."""
    casos = [("¿qué capacidades tienes?", "capacidad"),
             ("¿quién eres?", ""),
             ("hola", "hola")]
    for frase, marca in casos:
        r = await _di(sistema.orquestador, frase)
        assert r["provider"] == "core", f"{frase!r} cambió de responsable"
        if marca:
            assert marca in r["say"].lower(), f"{frase!r} -> {r['say']!r}"
