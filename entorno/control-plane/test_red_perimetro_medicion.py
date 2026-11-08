"""Ampliacion quirurgica del perimetro (acta del CEO 2026-09-07) — y la garantia que faltaba.

El acta autoriza aplicar `eliminar_codigo_muerto` sobre **un** fichero mas:
`milestones/m3-entry/medicion-razonador/heuristicas_deterministas.py`. Al comprobar el fichero, como
el acta ordena, las 17 oportunidades que el detector proponia resultaron **no ser codigo muerto**:
las 17 llevan `@_regla(...)`, un decorador que las inscribe en el registro `REGLAS` por efecto
lateral. Su nombre no aparece llamado en ninguna parte y sin embargo estan vivas.

`es_eliminable()` —la unica fuente de verdad sobre lo eliminable— no miraba los decoradores, asi que
sus cinco comprobaciones las daban por buenas y el ejecutor las habria borrado verificando el efecto
correcto: el simbolo desaparece. Es literalmente el fallo que su propio docstring describe —*«la
verificacion de efecto comprueba que el simbolo DESAPARECIO, no que DEBIERA desaparecer»*—, con un
disfraz nuevo.

La proteccion se declara por **propiedad**, no por lista de decoradores conocidos: cualquier simbolo
decorado queda fuera. Un decorador es codigo que se ejecuta sobre la definicion, y lo que hace con
ella no se deduce de su nombre. Fail-closed, ADR-0003: ante la duda, roja. Solo puede REDUCIR lo que
AURA borra, nunca ampliarlo.
"""

import ast
import pathlib

import pytest

import autoconstruccion as ac
import ciclo_autonomo as ca
import descubrimiento as des

RAIZ = pathlib.Path(__file__).resolve().parents[2]
OBJETIVO = RAIZ / "milestones/m3-entry/medicion-razonador/heuristicas_deterministas.py"

#: **Dos funciones decoradas seguidas, como en el fichero real.** Importa que sean dos: al quitar la
#: primera, su decorador queda huerfano y se **apila sobre la segunda**, asi que el fichero SIGUE
#: COMPILANDO. La comprobacion estructural que ya existia no puede ver esto, y el resultado seria un
#: fichero valido en el que una regla desaparecio y otra quedo registrada dos veces. Con una sola
#: funcion la prueba pasaria por el motivo equivocado.
_DECORADA = """
REGLAS = []


def _registro(fn):
    REGLAS.append(fn)
    return fn


@_registro
def _r_uno(c):
    return 1


@_registro
def _r_dos(c):
    return 2
"""

_SIN_DECORAR = """
REGLAS = []


def _registro(fn):
    REGLAS.append(fn)
    return fn


def _r_uno(c):
    return 1


def _r_dos(c):
    return 2
"""


# ---------------------------------------------------------------- la garantia que faltaba --

def test_una_funcion_decorada_no_es_eliminable():
    puede, motivo = ac.es_eliminable(_DECORADA, "_r_uno", "funcion")
    assert puede is False
    assert "decor" in motivo.lower(), f"el rechazo debe decir por que: {motivo!r}"


def test_control_positivo_la_misma_funcion_sin_decorador_si_es_eliminable():
    """Sin este control la prueba anterior seria decorativa: hay que demostrar que lo que la hace
    fallar es **el decorador** y no cualquier otra cosa del fragmento."""
    puede, motivo = ac.es_eliminable(_SIN_DECORAR, "_r_uno", "funcion")
    assert puede is True, motivo


def test_la_proteccion_es_una_propiedad_no_una_lista_de_nombres_conocidos():
    """Un decorador inventado, que ninguna lista podria contener, protege igual."""
    fuente = _DECORADA.replace("_registro", "_decorador_que_nadie_ha_visto_nunca")
    puede, _ = ac.es_eliminable(fuente, "_r_uno", "funcion")
    assert puede is False


def test_una_clase_decorada_tampoco_es_eliminable():
    fuente = "def _d(c):\n    return c\n\n\n@_d\nclass _C:\n    pass\n"
    puede, _ = ac.es_eliminable(fuente, "_C", "clase")
    assert puede is False


def test_el_detector_no_propone_lo_decorado():
    """La regla vive en un sitio: el detector la **consulta**, no la reimplementa."""
    fichero = pathlib.Path(__file__).parent / "_muestra_decorada.py"
    fichero.write_text(_DECORADA, encoding="utf-8")
    try:
        assert [s for s, _, _ in des._muertos_en(fichero) if s == "_r_uno"] == []
    finally:
        fichero.unlink()


def test_quitar_una_decorada_deja_un_fichero_que_compila_y_esta_corrompido():
    """**El control que demuestra que la comprobacion de compilacion NO basta aqui.**

    Quitar `_r_uno` deja su `@_registro` huerfano apilado sobre `_r_dos`: Python lo acepta. El
    fichero compila, la verificacion de efecto confirma que el simbolo desaparecio, y sin embargo
    el modulo quedo registrando `_r_dos` dos veces. Ninguna barrera anterior podia verlo."""
    quedo = ac.quitar_simbolo(_DECORADA, "_r_uno", "funcion")
    ast.parse(quedo)                                   # compila: no salta la barrera estructural
    assert quedo.count("@_registro") == 2 and "def _r_uno" not in quedo
    assert quedo.count("def _r_dos") == 1, "el decorador huerfano se apilo sobre la siguiente"


def test_el_ejecutor_rechaza_lo_decorado_aunque_llegue_por_otra_via(tmp_path):
    """La segunda barrera va donde pasa todo el mundo (ALERTA-005)."""
    objetivo = tmp_path / "entorno" / "control-plane" / "modulo.py"
    objetivo.parent.mkdir(parents=True)
    objetivo.write_text(_DECORADA, encoding="utf-8")
    puede, motivo = ac.es_eliminable(objetivo.read_text(encoding="utf-8"), "_r_uno", "funcion")
    assert puede is False and "decor" in motivo.lower()


def test_las_17_del_fichero_autorizado_no_son_eliminables():
    """El caso real que motiva todo esto, medido contra el fichero de verdad."""
    fuente = OBJETIVO.read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    decoradas = [n.name for n in arbol.body
                 if isinstance(n, ast.FunctionDef) and n.decorator_list
                 and n.name.startswith("_r_")]
    assert len(decoradas) >= 17, "el fichero cambio: vuelve a comprobarlo antes de tocar nada"
    for nombre in decoradas:
        puede, motivo = ac.es_eliminable(fuente, nombre, "funcion")
        assert puede is False, f"{nombre} se habria borrado estando viva: {motivo}"


def test_el_detector_no_encuentra_nada_que_borrar_en_el_fichero_autorizado():
    assert des._muertos_en(OBJETIVO) == []


# -------------------------------------------------------------------------- el perimetro --

def test_el_fichero_autorizado_esta_en_zona():
    assert ac.zona_permitida(OBJETIVO) is True


def test_el_fichero_autorizado_sigue_en_zona_con_la_raiz_que_usa_el_ciclo():
    """El ciclo llama `zona_permitida(f, raiz=<control-plane>)` y el fichero no cuelga de ahi."""
    assert ac.zona_permitida(OBJETIVO, raiz=pathlib.Path(__file__).parent) is True


def test_la_autorizacion_no_alcanza_a_los_vecinos_del_mismo_directorio():
    vecino = OBJETIVO.parent / "lanzar.py"
    assert vecino.exists(), "el vecino tiene que existir para que la prueba valga algo"
    assert ac.zona_permitida(vecino) is False


def test_la_autorizacion_no_alcanza_al_resto_de_milestones():
    assert ac.zona_permitida(RAIZ / "milestones/m3-entry/A2-metricas-basicas.md") is False


def test_la_autorizacion_no_abre_el_producto_ni_la_gobernanza():
    assert ac.zona_permitida(RAIZ / "walking-skeleton/demo_capacidad_m1.py") is False
    assert ac.zona_permitida(RAIZ / "adr/0003-x.md") is False
    assert ac.zona_permitida(RAIZ / "docs/bible.md") is False


def test_el_perimetro_anadido_es_exactamente_un_fichero():
    """Que no crezca por descuido: el acta nombra uno, y uno es lo que hay."""
    assert len(ac._FICHEROS_AUTORIZADOS) == 1
    assert ac.ficheros_autorizados() == (OBJETIVO,)


def test_la_zona_declarada_original_no_cambio():
    assert ac._ZONA_PERMITIDA == "entorno/control-plane/"
    assert ac.zona_permitida(RAIZ / "entorno/control-plane/review.py") is True


def test_el_descubrimiento_barre_el_fichero_autorizado_con_la_raiz_de_produccion():
    """Ampliar la zona sin ampliar el barrido dejaria la autorizacion sin efecto."""
    assert OBJETIVO in ac.ficheros_autorizados()


def test_una_tarea_sobre_el_fichero_autorizado_se_clasifica_review(tmp_path):
    """Autoridad real, ejecutada — no supuesta.

    **El verbo se pregunta al historial, no se asume.** Lo que esta prueba mide es que el fichero
    ampliado por acta cae en zona y por tanto llega a `REVIEW` en vez de a `HUMAN`. El verbo es el
    vehiculo, no el objeto: fijarlo a `eliminar_codigo_muerto` puso esta prueba en rojo el
    2026-09-16 —cuando `DR-E` reemplazo a `DR-D`, ese verbo salio del alcance— sin que nadie hubiera
    tocado ni la zona ni el perimetro que aqui se comprueban.
    """
    import review as rv

    plano = pathlib.Path(__file__).parent
    en_alcance = rv._alcance(plano)
    assert en_alcance, "sin acta vigente esta prueba no mide nada: no hay verbo que clasificar"

    assert ca.clasificar({"accion": en_alcance[0], "fichero": str(OBJETIVO)}, plano) == "REVIEW"


def test_una_tarea_sobre_un_vecino_sigue_siendo_human():
    plano = pathlib.Path(__file__).parent
    assert ca.clasificar({"accion": "eliminar_codigo_muerto",
                          "fichero": str(OBJETIVO.parent / "lanzar.py")}, plano) == "HUMAN"


@pytest.mark.parametrize("constante,esperado", [
    ("TODO_LO_DELEGABLE", ("eliminar_codigo_muerto", "implementar_incremento_especificado")),
])
def test_la_autoridad_no_se_amplio(constante, esperado):
    import review as rv
    assert getattr(rv, constante) == esperado
    assert len(rv._MATERIA_RESERVADA) == 10
    assert rv.REVIEW_HABILITADO is False


# ================================ EL PERIMETRO DEL ACTA NO ESCAPA DEL REPOSITORIO --


def test_el_fichero_autorizado_NO_se_concede_con_una_raiz_AJENA_al_repositorio(tmp_path):
    """INCIDENTE REAL del 2026-09-20, reproducido.

    Una medición del motor montada en un sandbox temporal —`raiz` en `/tmp`— **borró código del
    fichero real del repositorio**: 49 líneas, dos funciones decoradas. Se restauró con
    `git checkout`, pero la causa no era el sandbox: era que el atajo del acta concede el fichero
    ANTES de comprobar `raiz`, y `ficheros_autorizados()` devuelve rutas **absolutas reales**. Montar
    un sandbox no protegía nada, porque la ruta concedida apuntaba fuera de él.

    El acta amplió el perímetro para trabajar **sobre este repositorio**, no «desde cualquier raíz».
    Con una raíz ajena al repositorio, el acta no tiene nada que decir.

    Esto **restringe**: el camino de producción —`raiz=<control-plane>` del repo real— no cambia, y
    lo fija la prueba de control de abajo.
    """
    autorizado = OBJETIVO

    assert ac.zona_permitida(autorizado, raiz=tmp_path) is False, (
        "el fichero del acta se concedio con una raiz ajena: un sandbox puede escribir el repo real")


def test_CONTROL_con_la_raiz_REAL_del_plano_el_acta_sigue_concediendo(tmp_path):
    """La otra mitad, o el arreglo sería una parálisis: en producción el acta tiene que seguir valiendo."""
    plano = pathlib.Path(__file__).resolve().parent

    assert ac.zona_permitida(OBJETIVO, raiz=plano) is True, (
        "se rompio el perimetro que el acta del CEO concedio para el trabajo real")
    assert ac.zona_permitida(OBJETIVO) is True, "sin raiz, el acta tambien vale"


def test_CONTROL_un_vecino_del_autorizado_sigue_fuera_con_cualquier_raiz(tmp_path):
    """La barrera de identidad no se relaja por ninguno de los dos caminos."""
    vecino = OBJETIVO.parent / "lanzar.py"
    plano = pathlib.Path(__file__).resolve().parent

    assert ac.zona_permitida(vecino, raiz=plano) is False
    assert ac.zona_permitida(vecino, raiz=tmp_path) is False


def test_un_fichero_autorizado_que_NO_EXISTE_no_se_devuelve(monkeypatch):
    """El acta nombra ficheros; `ficheros_autorizados()` devuelve solo los que están de verdad.

    Sin esta comprobación, un acta con una ruta mal escrita —o un fichero movido— metería en el
    barrido una ruta fantasma, y el descubridor intentaría parsear algo que no existe. El mutante
    PM-M6 la degrada, y hasta hoy lo detectaba de rebote una prueba que ejercía el barrido sobre un
    sandbox; al acotar el perímetro del acta a este repositorio esa vía dejó de alcanzarla, así que
    la garantía se queda **sin red** salvo que se ejerza aquí directamente.
    """
    fantasma = "milestones/m3-entry/medicion-razonador/no_existe_este_fichero.py"
    monkeypatch.setattr(ac, "_FICHEROS_AUTORIZADOS", frozenset({fantasma}))

    assert ac.ficheros_autorizados() == (), "se devolvio una ruta que no existe"


def test_el_barrido_de_descubrimiento_INCLUYE_el_fichero_autorizado(tmp_path, monkeypatch):
    """Ampliar la zona sin ampliar el barrido dejaría la autorización sin efecto.

    `zona_permitida` dice QUÉ se puede tocar; `raiz` dice DÓNDE se mira. Son dos cosas distintas y
    el acta necesita las dos: por eso `codigo_muerto()` une los ficheros del acta a los de la raíz.

    **Se ejerce el caso para el que la unión existe**: el fichero autorizado NO cuelga de `raiz`, y
    el trabajo está dentro de él. Sin la unión, el descubridor nunca lo mira y la ampliación de
    perímetro que el CEO firmó no produce una sola oportunidad. Con ella, aparece.

    Hasta el 2026-09-20 este mutante (PM-M7) lo mataba de rebote una prueba que barría un sandbox
    contando con alcanzar el fichero REAL del repositorio. Esa vía se cerró a propósito —un sandbox
    no debe tocar el árbol real—, así que la garantía necesitaba un detector propio.
    """
    import descubrimiento as des

    raiz = tmp_path / "raiz"
    raiz.mkdir()
    (raiz / "otro.py").write_text("def vive():\n    return 1\n", encoding="utf-8")

    fuera_de_la_raiz = tmp_path / "del_acta"
    fuera_de_la_raiz.mkdir()
    autorizado = fuera_de_la_raiz / "autorizado.py"
    autorizado.write_text(
        "def _muerta_del_acta():\n    return 1\n\n\ndef viva():\n    return 2\n",
        encoding="utf-8")

    monkeypatch.setattr(ac, "ficheros_autorizados", lambda: (autorizado,))
    con_union = des.codigo_muerto(raiz, raiz)

    monkeypatch.setattr(ac, "ficheros_autorizados", lambda: ())
    sin_union = des.codigo_muerto(raiz, raiz)

    assert [o.detalle.get("simbolo") for o in con_union] == ["_muerta_del_acta"], (
        "el barrido no llego al fichero que el acta autorizo: la ampliacion queda sin efecto")
    assert sin_union == [], "el montaje no aisla la union: sin ella tampoco deberia aparecer nada"
