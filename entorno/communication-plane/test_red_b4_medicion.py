"""RED de B4 · «medir rutas de ejecución» != «declarar que no existen».

Autorizada por el CEO el 2026-08-23 junto con `D-CP-8` **(c)**, con un objetivo concreto: matar al
superviviente **M9** que la auditoría independiente dejó documentado.

**El hueco que cierra.** `rutas_de_ejecucion_desde_el_cuerpo()` debe devolver `()` *porque lo ha
comprobado*, no porque esté escrito. Ninguna de las 79 RED distinguía ambas cosas: sustituir el
cuerpo entero de la función por `return ()` dejaba la suite en verde. Una garantía sin red.

**Por qué esta prueba no es decorativa.** `CLAUDE.md §5` exige preguntarse qué tendría que romperse
para que fallara. La respuesta es exacta y está medida: **el mutante M9**. Y funciona en pareja con
`test_v3_no_existe_ninguna_ruta_del_cuerpo_a_un_ejecutor`, que fija el otro extremo:

- si la función mintiera devolviendo `()` siempre → **falla esta**;
- si mintiera devolviendo algo no vacío siempre → **falla la otra**.

Solo una función que *mide de verdad* satisface ambas a la vez.

**Alcance.** No cablea nada (`D-CP-8` = (c)), no toca `D-CP-4` ni `D-CP-5`, y no modifica el módulo:
trabaja sobre una **copia** en `tmp_path`.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

# Una ruta de ejecución real y directa, del tipo exacto que la función dice detectar.
RUTA_INYECTADA = """

import subprocess


def _ejecutar_desde_el_cuerpo(cuerpo):
    subprocess.run(cuerpo["cmd"], check=False)
"""


def _cargar(ruta: Path):
    """Importa un módulo desde una ruta concreta, aislado del que ya está en `sys.modules`."""
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_la_medicion_detecta_una_ruta_de_ejecucion_inyectada(tmp_path):
    """**Si la función midiera de mentira, este es el caso que no podría superar.**

    Se copia el módulo, se le añade un `subprocess.run` que consume el cuerpo, y se le pregunta.
    Una función que mide lo encuentra; una que declara `()` de memoria sigue diciendo que no hay
    nada mientras la ruta está delante.
    """
    original = importlib.import_module("communication_plane")
    copia = tmp_path / "canal_con_ruta.py"
    copia.write_text(Path(original.__file__).read_text(encoding="utf-8") + RUTA_INYECTADA,
                     encoding="utf-8")

    rutas = _cargar(copia).rutas_de_ejecucion_desde_el_cuerpo()

    assert rutas != (), (
        "la funcion devolvio () con un subprocess.run delante: no esta midiendo, esta declarando")
    assert any(r.startswith("run:") for r in rutas), f"no identifico la ruta inyectada: {rutas}"


def test_caso_de_control_la_misma_medicion_sobre_el_modulo_intacto_da_vacio(tmp_path):
    """El otro extremo de la pinza: sobre una copia **sin tocar**, la respuesta debe ser `()`.

    Sin este control, la prueba anterior se satisfaría con una función que devolviera siempre algo.
    """
    original = importlib.import_module("communication_plane")
    copia = tmp_path / "canal_intacto.py"
    copia.write_text(Path(original.__file__).read_text(encoding="utf-8"), encoding="utf-8")

    assert _cargar(copia).rutas_de_ejecucion_desde_el_cuerpo() == ()


def test_el_limite_declarado_se_DERIVA_de_la_medicion_y_no_se_afirma(monkeypatch):
    """**ANADIDA 2026-08-25 por un mutante SUPERVIVIENTE.** `limites_frente_a_inyeccion()` afirma
    que el canal impide que la persuasion produzca efecto. Hoy ese valor sale de MEDIR que no hay
    rutas de ejecucion — pero sustituirlo por un `True` fijo da exactamente el mismo resultado
    observable, y ninguna prueba lo notaba.

    La diferencia importa: un valor fijo seguiria afirmando la garantia **el dia que exista una
    ruta**, que es justo cuando dejaria de ser cierta. `INV-9` lo prohibe —no se finge capacidad no
    construida— y `CLAUDE.md` lo dice sin rodeos: nunca se publica como propiedad un valor que no
    pueda derivarse.

    Se comprueba inyectando una ruta: si el limite se DERIVA, pasa a False. Si esta afirmado, no.
    """
    canal = importlib.import_module("communication_plane")
    monkeypatch.setattr(canal, "rutas_de_ejecucion_desde_el_cuerpo", lambda: ("ruta_inyectada",))
    limite = canal.limites_frente_a_inyeccion()
    assert limite["impide_que_la_persuasion_produzca_efecto"] is False, (
        "con una ruta de ejecucion presente el canal sigue afirmando que impide el efecto: "
        "el limite esta AFIRMADO, no medido")
