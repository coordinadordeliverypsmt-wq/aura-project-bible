"""RED · completar `eliminar_codigo_muerto` — la capacidad autorizada, entera.

El acta de `DEC-ORCH-2` autoriza **`eliminar_codigo_muerto`** dentro de `entorno/control-plane/`.
Medido `[EJEC]` antes de escribir esto, AURA solo sabe ver y borrar **una** de las formas que toma:

| Forma de código muerto | ¿La ve? | ¿La sabe borrar? |
|---|---|---|
| función privada sin uso | **sí** | **sí** (`_quitar_funcion`) |
| import sin usar | no | no |
| constante privada de módulo sin uso | no | no |
| clase privada sin uso | no | no |
| método privado sin uso en su clase | no | no |

**Esto no amplía el perímetro.** La acción es la misma —`eliminar_codigo_muerto`— y la zona es la
misma. Lo que cambia es que AURA deja de estar autorizada a algo que solo sabía hacer en un tercio.
Ampliar el perímetro exige un acta; completar una capacidad ya autorizada, no.

## Lo que deliberadamente NO se detecta

**Ficheros huérfanos.** Hay exactamente uno en el plano —`medicion-a11.py`— y **no es código
muerto**: es el artefacto que mide el criterio `A11` contra el binario real, y por eso nadie lo
importa. Detectarlos habría puesto a AURA a borrar la evidencia de una medición.

Añadir un detector cuya única instancia real sería un error es peor que no tenerlo: convierte una
capacidad en un riesgo. Se declara aquí para que quien lo eche en falta sepa que se miró y se
descartó, no que se olvidó.

## El borrado se hace con `ast`, no con expresiones regulares

`_quitar_funcion` usa una regex que busca hasta el siguiente `def` o `class`. Para una función suelta
funciona; para un método dentro de una clase, o para un import en medio de un bloque, no hay patrón
fiable. Se localiza el nodo y se borra **su rango de líneas**: lo que el parser dice que ocupa, ni una
más.
"""

from __future__ import annotations


import autoconstruccion as ac
import descubrimiento as des
import motor_autonomia as motor
import orquestador as orq
import pytest
import review


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _zona(base):
    z = base / "entorno" / "control-plane"
    z.mkdir(parents=True, exist_ok=True)
    return z


def _con_acta(directorio):
    review.habilitar(directorio, alcance=("eliminar_codigo_muerto",), por="ceo",
                     acta="DEC-ORCH-2 del CEO")


# ==================================================== LAS FORMAS QUE FALTABAN --


def test_un_IMPORT_sin_usar_es_codigo_muerto(tmp_path):
    """Un import que nadie usa carga un módulo entero por nada y engaña a quien lee sobre de qué
    depende el fichero."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text("import json\nimport os\n\n\ndef viva():\n    return os.getpid()\n",
                               encoding="utf-8")
    simbolos = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)}
    assert "json" in simbolos, "json no se usa: es código muerto"
    assert "os" not in simbolos, "os sí se usa: tocarlo rompería el fichero"


def test_una_CONSTANTE_privada_sin_uso_es_codigo_muerto(tmp_path):
    zona = _zona(tmp_path)
    (zona / "m.py").write_text("_SOBRA = 1\n_SE_USA = 2\n\n\ndef viva():\n    return _SE_USA\n",
                               encoding="utf-8")
    simbolos = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)}
    assert "_SOBRA" in simbolos and "_SE_USA" not in simbolos


def test_una_CLASE_privada_sin_uso_es_codigo_muerto(tmp_path):
    zona = _zona(tmp_path)
    (zona / "m.py").write_text(
        "class _Sobra:\n    pass\n\n\nclass _SeUsa:\n    pass\n\n\ndef viva():\n    return _SeUsa()\n",
        encoding="utf-8")
    simbolos = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)}
    assert "_Sobra" in simbolos and "_SeUsa" not in simbolos


def test_un_METODO_privado_sin_uso_en_su_clase_es_codigo_muerto(tmp_path):
    zona = _zona(tmp_path)
    (zona / "m.py").write_text(
        "class C:\n"
        "    def publico(self):\n"
        "        return self._ayuda()\n"
        "\n"
        "    def _ayuda(self):\n"
        "        return 1\n"
        "\n"
        "    def _sobra(self):\n"
        "        return 2\n",
        encoding="utf-8")
    simbolos = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)}
    assert "C._sobra" in simbolos, "nadie llama a _sobra"
    assert "C._ayuda" not in simbolos, "_ayuda sí se llama"


def test_lo_PUBLICO_no_se_toca_nunca(tmp_path):
    """Una función pública sin uso **en su fichero** puede usarse desde fuera del árbol. Borrarla
    sería romper una interfaz sin saberlo, y el acta habla de código muerto, no de código que hoy no
    veo llamar."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text("MAX = 10\n\n\ndef publica():\n    return 1\n\n\nclass Publica:\n    pass\n",
                               encoding="utf-8")
    # **Con el acta habilitada**: sin ella nada llega a ser `OPORTUNIDAD_REAL` y la prueba verdearía
    # por el motivo equivocado — lo destapó el mutante `CMC-M5`, que sobrevivía por eso.
    _con_acta(tmp_path)
    encontradas = des.descubrir(zona, tmp_path)
    assert [o for o in encontradas if o.estado == des.OPORTUNIDAD_REAL] == []
    assert not any(o.detalle.get("simbolo") in ("publica", "MAX", "Publica") for o in encontradas)


def test_lo_que_se_usa_DESDE_OTRO_FICHERO_es_FALSO_HUECO(tmp_path):
    """La regla que ya existía, extendida a las formas nuevas: parece muerto en su fichero y no lo
    está."""
    zona = _zona(tmp_path)
    (zona / "define.py").write_text("_COMPARTIDA = 42\n", encoding="utf-8")
    (zona / "usa.py").write_text("import define\n\n\ndef viva():\n    return define._COMPARTIDA\n",
                                 encoding="utf-8")
    falsos = [o for o in des.descubrir(zona, tmp_path) if o.estado == des.FALSO_HUECO]
    assert any(o.detalle.get("simbolo") == "_COMPARTIDA" for o in falsos)


def test_los_ficheros_HUERFANOS_no_se_proponen_NUNCA(tmp_path):
    """Decisión declarada: no se detectan. En el plano real hay exactamente uno —`medicion-a11.py`—
    y **no es código muerto**: es el artefacto que mide `A11` contra el binario real, y por eso nadie
    lo importa.

    Un detector cuya única instancia real sería un error convierte una capacidad en un riesgo."""
    zona = _zona(tmp_path)
    (zona / "huerfano.py").write_text('"""Nadie me importa, y es a propósito."""\n\n\nX = 1\n',
                                      encoding="utf-8")
    alcances = {o.alcance for o in des.descubrir(zona, tmp_path)}
    assert not any("huerfano.py" in a for a in alcances)
    assert des.FICHEROS_NO_SE_PROPONEN_COMO_MUERTOS is True


# ==================================================== EL BORRADO, POR `ast` --


@pytest.mark.parametrize("clase,fuente,simbolo,debe_irse,debe_quedar", [
    ("import", "import json\nimport os\n\n\ndef v():\n    return os.getpid()\n", "json",
     "import json", "import os"),
    ("constante", "_SOBRA = 1\n_QUEDA = 2\n\n\ndef v():\n    return _QUEDA\n", "_SOBRA",
     "_SOBRA", "_QUEDA"),
    ("clase", "class _Sobra:\n    pass\n\n\ndef v():\n    return 1\n", "_Sobra",
     "_Sobra", "def v"),
    ("funcion", "def _sobra():\n    return 1\n\n\ndef v():\n    return 2\n", "_sobra",
     "_sobra", "def v"),
])
def test_se_borra_EXACTAMENTE_el_simbolo_y_nada_mas(tmp_path, clase, fuente, simbolo,
                                                    debe_irse, debe_quedar):
    """Lo que el parser dice que ocupa, ni una línea más. Una regex que busca «hasta el siguiente
    `def`» se lleva por delante lo que haya en medio."""
    fichero = tmp_path / "m.py"
    fichero.write_text(fuente, encoding="utf-8")
    nuevo = ac.quitar_simbolo(fuente, simbolo, clase)
    assert debe_irse not in nuevo
    assert debe_quedar in nuevo
    compile(nuevo, "m.py", "exec")          # y el fichero sigue siendo Python valido


def test_borrar_un_METODO_no_se_lleva_la_clase(tmp_path):
    """El caso que ninguna regex resuelve: un método en medio de una clase."""
    fuente = ("class C:\n"
              "    def a(self):\n"
              "        return 1\n"
              "\n"
              "    def _sobra(self):\n"
              "        return 2\n"
              "\n"
              "    def b(self):\n"
              "        return 3\n")
    nuevo = ac.quitar_simbolo(fuente, "C._sobra", "metodo")
    assert "_sobra" not in nuevo
    for queda in ("class C:", "def a(self):", "def b(self):"):
        assert queda in nuevo
    compile(nuevo, "m.py", "exec")


def test_quitar_un_simbolo_que_no_esta_no_cambia_nada():
    """Fail-closed: si no se encuentra, no se toca. Un borrado «aproximado» es peor que ninguno."""
    fuente = "def v():\n    return 1\n"
    assert ac.quitar_simbolo(fuente, "_no_existe", "funcion") == fuente


# ==================================================== LA CADENA ENTERA, POR EL MECANISMO REAL --


def test_AURA_ejecuta_las_CUATRO_formas_encadenadas(tmp_path):
    """El E2E que importa: cuatro ficheros con cuatro formas distintas de código muerto, descubiertas
    por AURA, ejecutadas por su circuito gobernado, con efecto observable en disco y **0 actos
    humanos**."""
    zona = _zona(tmp_path)
    (zona / "a.py").write_text("import json\n\n\ndef v():\n    return 1\n", encoding="utf-8")
    (zona / "b.py").write_text("_SOBRA = 1\n\n\ndef v():\n    return 2\n", encoding="utf-8")
    (zona / "c.py").write_text("class _Sobra:\n    pass\n\n\ndef v():\n    return 3\n", encoding="utf-8")
    (zona / "d.py").write_text("def _sobra():\n    return 1\n\n\ndef v():\n    return 4\n",
                               encoding="utf-8")
    _con_acta(tmp_path)

    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=6)

    assert informe["ejecutadas"] == 4, informe
    assert informe["actos_humanos_durante_el_ciclo"] == 0
    assert informe["motivo_de_parada"] == "cola agotada"
    for nombre, muerto in (("a.py", "import json"), ("b.py", "_SOBRA"),
                           ("c.py", "_Sobra"), ("d.py", "_sobra")):
        texto = (zona / nombre).read_text(encoding="utf-8")
        assert muerto not in texto, f"{nombre} sigue con {muerto}"
        assert "def v():" in texto, f"{nombre} perdió lo vivo"
        compile(texto, nombre, "exec")


def test_si_la_verificacion_falla_se_REVIERTE_cualquiera_de_las_formas(tmp_path):
    """La reversibilidad no puede depender de qué forma tenía el código muerto."""
    zona = _zona(tmp_path)
    (zona / "a.py").write_text("_SOBRA = 1\n\n\ndef v():\n    return 1\n", encoding="utf-8")
    _con_acta(tmp_path)
    original = (zona / "a.py").read_text(encoding="utf-8")
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: False, max_tareas=3)
    assert informe["ejecutadas"] == 0
    assert (zona / "a.py").read_text(encoding="utf-8") == original


def test_un_IMPORT_no_es_FALSO_HUECO_porque_otro_MODULO_lo_use(tmp_path):
    """`CMC-M6` sobrevivía porque en mis pruebas ningún otro fichero mencionaba el import sobrante.

    El caso real es el más común de todos: **dos módulos importan `json`**. Si el nombre visto en
    otro fichero contara como uso, ningún import sobrante se limpiaría jamás — cada módulo tiene los
    suyos, y que el vecino use `json` no dice nada sobre este."""
    zona = _zona(tmp_path)
    (zona / "sobra.py").write_text("import json\n\n\ndef v():\n    return 1\n", encoding="utf-8")
    (zona / "usa.py").write_text("import json\n\n\ndef w():\n    return json.dumps({})\n",
                                 encoding="utf-8")
    _con_acta(tmp_path)
    encontradas = des.descubrir(zona, tmp_path)
    reales = [o for o in encontradas if o.estado == des.OPORTUNIDAD_REAL]
    assert len(reales) == 1, [o.alcance for o in reales]
    assert reales[0].alcance.endswith("sobra.py"), "el que sobra es el de sobra.py, no el de usa.py"


def test_un_IMPORT_MULTIPLE_pierde_solo_el_que_sobra(tmp_path):
    """`CMC-M10` sobrevivía porque todas mis pruebas usaban imports de un solo nombre. Con
    `import json, os` y solo `os` en uso, borrar la línea entera se llevaría por delante el que sí
    hace falta — y el fichero dejaría de compilar."""
    fuente = "import json, os\n\n\ndef v():\n    return os.getpid()\n"
    nuevo = ac.quitar_simbolo(fuente, "json", "import")
    assert "json" not in nuevo
    assert "import os" in nuevo
    compile(nuevo, "m.py", "exec")

    desde = "from pathlib import Path, PurePath\n\n\ndef v():\n    return Path('.')\n"
    limpio = ac.quitar_simbolo(desde, "PurePath", "import")
    assert "PurePath" not in limpio and "Path" in limpio
    compile(limpio, "m.py", "exec")


def test_un_import_de___future___NUNCA_es_codigo_muerto(tmp_path):
    """**Defecto encontrado por AURA en producción, y era mío.**

    `from __future__ import annotations` es una **directiva del compilador**, no un import normal: su
    efecto ocurre al parsear y su nombre no aparece jamás como `Name` en el árbol. Mi detector lo veía
    como import muerto, y AURA —haciendo exactamente lo que se le pidió— lo borró de tres ficheros del
    plano real el 2026-08-31.

    No rompió nada hoy: la batería siguió en verde y `ruff` también. Pero cambia cómo se evalúan las
    anotaciones (`PEP 563`), así que es un fallo latente, no una cuestión de estilo. Y la lección es
    la del proyecto: **la verificación de efecto comprueba que el símbolo desapareció, no que debiera
    desaparecer**. Contra un falso positivo del detector, la verificación no protege.

    Lo mismo vale para cualquier otro `__future__`: se declaran todos fuera, no solo el que falló."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text(
        "from __future__ import annotations\n"
        "import json\n"
        "\n"
        "\n"
        "def v() -> int:\n"
        "    return 1\n",
        encoding="utf-8")
    _con_acta(tmp_path)
    simbolos = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)}
    assert "annotations" not in simbolos, "__future__ es una directiva del compilador, no un import"
    assert "json" in simbolos, "y el import de verdad muerto se sigue viendo"


def test_ningun_import_de___future___se_propone_aunque_se_pida(tmp_path):
    """Caso de control por el otro lado: aunque alguien construya la tarea a mano, la directiva no se
    borra.

    **Reapuntada el 2026-08-31.** Antes medía el guardia dentro de `quitar_simbolo`, que era una
    **copia** de la regla: cada guardia tapaba al otro y un mutante sobrevivía porque quitar uno no
    cambiaba nada. La regla vive ahora solo en `es_eliminable()`; `quitar_simbolo` sabe *cómo* borrar,
    no *si* se debe."""
    fuente = "from __future__ import annotations\nimport json\n\n\ndef v():\n    return 1\n"
    puede, motivo = ac.es_eliminable(fuente, "annotations", "import")
    assert puede is False and "__future__" in motivo
    assert ac.es_eliminable(fuente, "json", "import")[0] is True


def test_lo_que_esta_en___all___NO_es_codigo_muerto(tmp_path):
    """**Segundo falso positivo de la misma clase, y más silencioso que el primero.**

    Un nombre listado en `__all__` está **exportado**: `from modulo import *` lo entrega. Pero en el
    árbol es una cadena dentro de una lista, no un `Name`, así que un detector que busque usos lo ve
    muerto.

    Y lo que lo hace peor que el caso de `__future__`: borrar el import dejaría `__all__` nombrando
    algo que ya no existe, y `import *` fallaría con `AttributeError`. La batería no lo vería —nadie
    hace `import *`— así que la verificación de efecto daría el cambio por bueno. **Un fallo latente
    que ninguna prueba existente detectaría.**"""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text(
        "import json\n"
        "import os\n"
        "\n"
        "\n"
        "def v():\n"
        "    return os.getpid()\n"
        "\n"
        "\n"
        '__all__ = ["v", "json"]\n',
        encoding="utf-8")
    _con_acta(tmp_path)
    simbolos = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)
                if o.estado == des.OPORTUNIDAD_REAL}
    assert "json" not in simbolos, "json está exportado en __all__: se usa"
    assert simbolos == set(), "y no queda nada más muerto en ese fichero"


def test_una_constante_exportada_en___all___tampoco_se_toca(tmp_path):
    """La regla vale para todas las formas, no solo para los imports."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text('_SECRETO = 1\n\n\n__all__ = ["_SECRETO"]\n', encoding="utf-8")
    _con_acta(tmp_path)
    reales = [o for o in des.descubrir(zona, tmp_path) if o.estado == des.OPORTUNIDAD_REAL]
    assert reales == [], "está exportado: no es código muerto"
