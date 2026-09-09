"""RED · segunda barrera — **el detector propone; otra cosa decide si se puede borrar**.

AURA ejecutó tres falsos positivos en producción el 2026-08-31 —`__future__`, `__all__`, `__dunder__`—
e hizo exactamente lo que se le pidió. El fallo estaba en la clasificación, y eso destapó algo más
grande que los tres nombres:

> **La verificación de efecto comprueba que el símbolo desapareció, no que debiera desaparecer.**

Contra un falso positivo del detector, todo el circuito gobernado —el revisor, el acta, la
verificación, la reversión— **no protege**, porque todos dan por buena la premisa. El único punto que
puede refutarla es uno que vuelva a mirar el árbol y pregunte otra cosa.

## Dos preguntas distintas, no la misma dos veces

| Quién | Pregunta |
|---|---|
| el detector | *¿parece que nadie lo usa?* |
| **la barrera** | *¿es esto **eliminable**, mire quien lo mire?* |

Son independientes: la primera es de uso, la segunda es **estructural**. Un `__future__` no se puede
borrar aunque nadie lo «use», porque su efecto no es un uso.

## Una sola regla, aplicada en dos puntos

`es_eliminable()` vive en un sitio y la consultan **el descubridor** —para que un falso positivo no
llegue siquiera a ser oportunidad— y **el ejecutor** —para que nada que llegue por otra vía se borre—.
Escribir la regla dos veces sería el defecto que este proyecto lleva cinco auditorías corrigiendo: la
copia que falta es la ruta abierta.

## Meta-control

Estas pruebas podrían pasar por cuatro motivos falsos: que no haya trabajo, que el motor no ejecute
nunca, que el revisor rechace siempre, o que el ejecutor esté roto. Por eso hay un **caso de control
que sí recorre el circuito entero y borra de verdad**: si ese falla, todo lo demás no demuestra nada.
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
    review.habilitar(directorio, alcance=("eliminar_codigo_muerto",), por="ceo", acta="DEC-ORCH-2")


# ==================================================== LA REGLA, SOLA --


def test_la_barrera_RECHAZA_los_tres_falsos_positivos_reales():
    """Los tres que AURA ejecutó en producción. La barrera los rechaza **y dice por qué**: un rechazo
    sin motivo obliga a quien lo lea a averiguarlo, y averiguar es lo que el Protocolo de Continuidad
    existe para evitar."""
    casos = [
        ("from __future__ import annotations\nimport json\n", "annotations", "import"),
        ('import json\n\n\n__all__ = ["json"]\n', "json", "import"),
        ('__all__ = ["x"]\nx = 1\n', "__all__", "constante"),
    ]
    for fuente, simbolo, forma in casos:
        puede, motivo = ac.es_eliminable(fuente, simbolo, forma)
        assert puede is False, f"{simbolo} ({forma}) no debería poder borrarse"
        assert motivo, f"{simbolo} se rechaza sin decir por qué"


def test_la_barrera_ACEPTA_lo_que_si_es_eliminable():
    """Caso de control de la regla: si rechazara todo, no distinguiría nada y bloquearía la capacidad
    entera en vez de protegerla."""
    for fuente, simbolo, forma in [
        ("import json\n\n\ndef v():\n    return 1\n", "json", "import"),
        ("_SOBRA = 1\n\n\ndef v():\n    return 2\n", "_SOBRA", "constante"),
        ("def _sobra():\n    return 1\n\n\ndef v():\n    return 2\n", "_sobra", "funcion"),
        ("class _Sobra:\n    pass\n\n\ndef v():\n    return 3\n", "_Sobra", "clase"),
    ]:
        puede, motivo = ac.es_eliminable(fuente, simbolo, forma)
        assert puede is True, f"{simbolo} ({forma}) sí es eliminable: {motivo}"


def test_la_barrera_rechaza_lo_que_NO_EXISTE():
    """Fail-closed. Borrar «aproximadamente» es peor que no borrar: deja el árbol en un estado que
    nadie pidió y que la verificación tendría que descubrir después."""
    puede, motivo = ac.es_eliminable("def v():\n    return 1\n", "_no_existe", "funcion")
    assert puede is False and motivo


def test_la_barrera_rechaza_si_el_resultado_NO_COMPILA():
    """La comprobación **estructural** que cubre lo que nadie previó: si quitar el símbolo deja un
    fichero que Python ya no acepta, no se quita. Es la única de las reglas que protege contra errores
    que todavía no se han cometido.

    El caso: una clase cuyo único cuerpo es el método que se pretende borrar. Quitarlo deja
    `class C:` sin cuerpo, que es un `SyntaxError`."""
    fuente = "class C:\n    def _solo(self):\n        return 1\n"
    puede, motivo = ac.es_eliminable(fuente, "C._solo", "metodo")
    assert puede is False
    assert "compil" in motivo.lower() or "sintax" in motivo.lower(), motivo


def test_la_barrera_rechaza_CUALQUIER_dunder_no_solo_los_tres_conocidos():
    """La propiedad, no la lista. Excluir solo `__all__`, `__future__` y `__version__` sería volver a
    una lista escrita a mano — el defecto que este proyecto lleva cinco auditorías corrigiendo."""
    for nombre in ("__version__", "__author__", "__slots__", "__inventado__"):
        fuente = f"{nombre} = 1\n"
        puede, motivo = ac.es_eliminable(fuente, nombre, "constante")
        assert puede is False, f"{nombre} es protocolo del lenguaje, no una constante privada"


# ==================================================== UNA REGLA, DOS PUNTOS --


def test_la_regla_vive_en_UN_SOLO_SITIO():
    """Escribirla dos veces es el defecto del `§0` del CHECKPOINT en su versión cara: la copia que
    falta es la ruta abierta. El descubridor la **consulta**, no la reimplementa."""
    import inspect
    fuente = inspect.getsource(des)
    assert "es_eliminable" in fuente, "el descubridor tiene que consultarla, no reimplementarla"
    # y no puede haberse quedado una copia de las reglas dentro del descubridor
    for regla in ('n.module == "__future__"', 'endswith("__")'):
        assert regla not in fuente, f"el descubridor reimplementa la regla: {regla}"


def test_un_falso_positivo_NO_LLEGA_A_SER_OPORTUNIDAD(tmp_path):
    """Primer punto de aplicación: el descubridor. Lo que la barrera rechaza no llega ni a proponerse,
    así que no consume revisor, ni acta, ni una vuelta del ciclo."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text(
        "from __future__ import annotations\n"
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
    reales = {o.detalle.get("simbolo") for o in des.descubrir(zona, tmp_path)
              if o.estado == des.OPORTUNIDAD_REAL}
    assert reales == set(), f"nada de ese fichero es eliminable, y propuso: {reales}"


def test_el_EJECUTOR_se_niega_aunque_la_tarea_llegue_por_otra_via(tmp_path):
    """Segundo punto, y el que de verdad es una **segunda** barrera: aunque alguien construya la
    propuesta a mano y la autorice, el ejecutor vuelve a preguntar antes de tocar el fichero.

    Es la lección de `ALERTA-005` aplicada aquí: la puerta va donde pasa todo el mundo, y por el
    ejecutor pasa cualquier ruta."""
    zona = _zona(tmp_path)
    fichero = zona / "m.py"
    original = "from __future__ import annotations\n\n\ndef v():\n    return 1\n"
    fichero.write_text(original, encoding="utf-8")

    propuesta = ac.proponer(tmp_path, {"simbolo": "annotations", "fichero": str(fichero),
                                       "forma": "import", "motivo": "por la puerta de atrás"})
    ac.autorizar(tmp_path, propuesta["id"], por="ceo", acta="acta real")
    with pytest.raises(ac.NoEliminable):
        ac.ejecutar(tmp_path, propuesta, autoridad="ceo", verificacion=lambda: True)
    assert fichero.read_text(encoding="utf-8") == original, "no se tocó el fichero"


def test_el_rechazo_del_ejecutor_QUEDA_REGISTRADO(tmp_path):
    """Un rechazo que no consta es indistinguible de una tarea que nadie intentó."""
    import control_plane as cp
    zona = _zona(tmp_path)
    fichero = zona / "m.py"
    fichero.write_text("from __future__ import annotations\n\n\ndef v():\n    return 1\n",
                       encoding="utf-8")
    propuesta = ac.proponer(tmp_path, {"simbolo": "annotations", "fichero": str(fichero),
                                       "forma": "import", "motivo": "x"})
    ac.autorizar(tmp_path, propuesta["id"], por="ceo", acta="acta")
    with pytest.raises(ac.NoEliminable):
        ac.ejecutar(tmp_path, propuesta, autoridad="ceo", verificacion=lambda: True)
    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert "eliminacion_rechazada" in tipos


# ==================================================== EL CASO DE CONTROL --


def test_CONTROL_una_oportunidad_legitima_SI_recorre_el_circuito_entero(tmp_path):
    """**El meta-control.** Sin esto, todas las pruebas de arriba pasarían igual si el motor no
    ejecutara nunca, si el revisor rechazara siempre o si el ejecutor estuviera roto — y no
    demostrarían nada sobre la barrera, solo que el sistema no hace nada.

    Aquí AURA descubre, planifica, revisa, ejecuta y **borra de verdad**."""
    zona = _zona(tmp_path)
    fichero = zona / "m.py"
    fichero.write_text(
        "from __future__ import annotations\n"
        "import json\n"
        "\n"
        "\n"
        "def _sobra():\n"
        "    return 1\n"
        "\n"
        "\n"
        "def v():\n"
        "    return 2\n",
        encoding="utf-8")
    _con_acta(tmp_path)

    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    texto = fichero.read_text(encoding="utf-8")

    assert informe["ejecutadas"] == 2, informe        # json y _sobra: los dos legitimos
    assert informe["actos_humanos_durante_el_ciclo"] == 0
    assert "import json" not in texto and "_sobra" not in texto
    assert "from __future__ import annotations" in texto, "la directiva sobrevive"
    assert "def v():" in texto
    compile(texto, "m.py", "exec")


def test_CONTROL_la_barrera_no_bloquea_la_capacidad_entera(tmp_path):
    """Y el contraste que hace legible al anterior: si la barrera rechazara todo, `ejecutadas` sería
    0 y el circuito parecería sano estando muerto."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text("def _sobra():\n    return 1\n\n\ndef v():\n    return 2\n",
                               encoding="utf-8")
    _con_acta(tmp_path)
    assert motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=3)["ejecutadas"] == 1


# ==================================================== LA IDENTIDAD DE UNA OPORTUNIDAD --


def test_dos_simbolos_DISTINTOS_no_comparten_identidad(tmp_path):
    """**Defecto real, y de los que no se ven.** El id de la oportunidad se derivaba de
    `fichero:línea`. Al borrar un símbolo, el siguiente **ocupa la línea que dejó libre**, obtiene el
    mismo id, y el antiduplicados lo suprime: AURA pierde trabajo real **en silencio**, y el ciclo
    informa «cola agotada» habiendo dejado algo sin hacer.

    Ocurrió de verdad: `import json` en la línea 2, y `_sobra` cayendo a la línea 2 al quitarlo.
    Lo delató una prueba intermitente — que es la forma que tienen estos fallos de avisar.

    La identidad de una oportunidad de código muerto es **(fichero, símbolo, forma)**. La línea es
    dónde estaba, no qué es."""
    zona = _zona(tmp_path)
    (zona / "m.py").write_text("import json\n_SOBRA = 1\n\n\ndef v():\n    return 1\n",
                               encoding="utf-8")
    _con_acta(tmp_path)
    ids = {o.id for o in des.descubrir(zona, tmp_path) if o.estado == des.OPORTUNIDAD_REAL}
    assert len(ids) == 2, "dos símbolos distintos, dos identidades"


def test_la_identidad_NO_cambia_si_el_simbolo_se_MUEVE_de_linea(tmp_path):
    """La otra mitad, y la que sostiene el antiduplicados: si el id cambiara al desplazarse el
    símbolo, cualquier edición por encima haría que la misma oportunidad se viera como nueva — y la
    repetición dejaría de ser detectable, que es justo lo que el id derivado existe para lograr."""
    zona = _zona(tmp_path)
    fichero = zona / "m.py"
    _con_acta(tmp_path)

    fichero.write_text("def _sobra():\n    return 1\n\n\ndef v():\n    return 2\n", encoding="utf-8")
    antes = {o.detalle["simbolo"]: o.id for o in des.descubrir(zona, tmp_path)
             if o.estado == des.OPORTUNIDAD_REAL}

    fichero.write_text("# un comentario nuevo arriba\n# y otro\n"
                       "def _sobra():\n    return 1\n\n\ndef v():\n    return 2\n", encoding="utf-8")
    despues = {o.detalle["simbolo"]: o.id for o in des.descubrir(zona, tmp_path)
               if o.estado == des.OPORTUNIDAD_REAL}

    assert antes["_sobra"] == despues["_sobra"], "es la misma oportunidad, dos líneas más abajo"


def test_AURA_no_pierde_la_segunda_tarea_cuando_ocupa_la_linea_de_la_primera(tmp_path):
    """El caso completo, por el circuito real: el símbolo que queda cae **exactamente** en la línea
    que liberó el que se fue. Antes, la segunda tarea desaparecía y el ciclo decía «cola agotada»."""
    zona = _zona(tmp_path)
    fichero = zona / "m.py"
    fichero.write_text("import json\n\n\ndef _sobra():\n    return 1\n\n\ndef v():\n    return 2\n",
                       encoding="utf-8")
    _con_acta(tmp_path)
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    texto = fichero.read_text(encoding="utf-8")
    assert informe["ejecutadas"] == 2, informe
    assert "import json" not in texto and "_sobra" not in texto
    assert "def v():" in texto


def test_si_el_BORRADO_no_hace_nada_no_se_declara_efecto(tmp_path, monkeypatch):
    """La garantía que sostiene todo el circuito, y que ningún caso ejercitaba desde que existe la
    barrera: **el efecto se comprueba releyendo el fichero**, no se deduce de haber llamado al
    borrador.

    Antes, la barrera garantizaba que el símbolo estaba, así que el borrado siempre surtía efecto y
    la comprobación nunca llegaba a ser falsa — el mutante que la sustituía por `True` sobrevivía sin
    que faltara ninguna prueba, solo un caso.

    Aquí el borrador se rompe a propósito: devuelve el texto tal cual. El ejecutor tiene que notarlo,
    **no declarar éxito**, y revertir."""
    zona = _zona(tmp_path)
    fichero = zona / "m.py"
    original = "def _sobra():\n    return 1\n\n\ndef v():\n    return 2\n"
    fichero.write_text(original, encoding="utf-8")

    monkeypatch.setattr(ac, "quitar_simbolo", lambda texto, simbolo, clase="funcion": texto)
    propuesta = ac.proponer(tmp_path, {"simbolo": "_sobra", "fichero": str(fichero),
                                       "forma": "funcion", "motivo": "muerto"})
    ac.autorizar(tmp_path, propuesta["id"], por="ceo", acta="acta")
    resultado = ac.ejecutar(tmp_path, propuesta, autoridad="ceo", verificacion=lambda: True)

    assert resultado["efecto_verificado"] is False, "el símbolo sigue ahí: no hubo efecto"
    assert resultado["revertido"] is True
    assert fichero.read_text(encoding="utf-8") == original
