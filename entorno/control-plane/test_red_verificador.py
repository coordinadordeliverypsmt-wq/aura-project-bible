"""El verificador cuenta, no se fía del código de salida (CEO, 2026-09-20).

POR QUÉ EXISTE. Sin verificador, `autoconstruccion.ejecutar` recibe `verificacion=None`, trata «no
se sabe» como fallo y **revierte todo cambio**. Medido: una tarea impecable —oportunidad real,
acta, contrato, correspondencia, zona, PARADA desarmada— se aplicaba y se deshacía. Ninguna tarea
podía completarse jamás.

LOS TRES FALSOS POSITIVOS QUE ESTE FICHERO CIERRA, todos reproducidos antes de escribirlo:

    PYTEST_ADDOPTS=--collect-only heredado  -> pytest sale 0 sin ejecutar una sola prueba
    conftest.py que hace skip de todo       -> pytest sale 0 con la batería entera omitida
    ningún fichero que recoger              -> pytest sale 5, que no es un fallo de prueba

Los tres dan `returncode == 0` o parecido y **ninguno significa «la batería pasó»**. Por eso el
veredicto sale del informe `--junitxml`: salida estructurada, no prosa. La ficha de la capacidad
`ejecutar_pruebas` ya lo exigía desde antes de que existiera el ejecutor —`evidencia_requerida =
"informe de pytest con conteo"`—; esto solo lo cumple.

LA PRUEBA QUE MÁS IMPORTA es `test_un_conftest_hostil...`: es el vector que el red team usó para
obtener «árbol sano» con la batería sin ejecutar. Si alguna vez vuelve a pasar, falla aquí.
"""

from __future__ import annotations

import pathlib

import orquestador as orq
import pytest
import verificador as vf

PRUEBA_VERDE = "def test_pasa():\n    assert True\n"
PRUEBA_ROJA = "def test_falla():\n    assert False, 'rota a proposito'\n"


@pytest.fixture(autouse=True)
def _el_arnes_no_esta_corriendo(monkeypatch):
    """Las pruebas no pueden depender de si hay un arnés de mutación vivo en la máquina."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _bateria(raiz: pathlib.Path, contenido: str, nombre: str = "test_x.py") -> pathlib.Path:
    fichero = raiz / nombre
    fichero.write_text(contenido, encoding="utf-8")
    return fichero


# ============================================================ EL CAMINO SANO --


def test_una_bateria_en_verde_declara_el_arbol_SANO(tmp_path):
    f = _bateria(tmp_path, PRUEBA_VERDE)

    informe = vf.ejecutar_pruebas([str(f)], tmp_path)

    assert informe.sano is True
    assert informe.ejecutadas == 1 and informe.fallidas == 0


def test_una_bateria_en_ROJO_declara_el_arbol_enfermo(tmp_path):
    f = _bateria(tmp_path, PRUEBA_ROJA)

    informe = vf.ejecutar_pruebas([str(f)], tmp_path)

    assert informe.sano is False
    assert informe.ejecutadas == 1 and informe.fallidas == 1


# ============================================================ LOS FALSOS POSITIVOS --


def test_PYTEST_ADDOPTS_heredado_NO_puede_declarar_sano_un_arbol_roto(tmp_path, monkeypatch):
    """El vector: `--collect-only` hace salir a pytest con 0 sin ejecutar nada.

    El verificador construye su entorno en vez de heredarlo, así que la variable ni llega al hijo.
    """
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    f = _bateria(tmp_path, PRUEBA_ROJA)

    informe = vf.ejecutar_pruebas([str(f)], tmp_path)

    assert informe.sano is False, "una bateria rota se declaro sana por una variable de entorno"
    assert informe.ejecutadas == 1, "la prueba ni siquiera se ejecuto"


def test_un_conftest_hostil_que_omite_TODO_no_declara_sano_el_arbol(tmp_path):
    """El vector del red team: todo omitido, `returncode == 0`, y nada comprobado.

    Es el caso que separa «contar» de «mirar el código de salida». Con solo el `returncode`, este
    árbol sale sano; contando, se ve que no se ejercitó ninguna garantía.
    """
    _bateria(tmp_path, PRUEBA_ROJA)
    (tmp_path / "conftest.py").write_text(
        "import pytest\n\n\ndef pytest_collection_modifyitems(items):\n"
        "    for i in items:\n        i.add_marker(pytest.mark.skip(reason='hostil'))\n",
        encoding="utf-8")

    informe = vf.ejecutar_pruebas([str(tmp_path / "test_x.py")], tmp_path)

    assert informe.codigo == 0, "el vector exige que pytest salga con 0; si no, no prueba nada"
    assert informe.sano is False, "todo omitido se declaro sano"
    assert informe.omitidas == 1


def test_una_bateria_que_no_recoge_NADA_no_es_un_arbol_sano(tmp_path):
    """«No hay pruebas» no es «las pruebas pasan». Sin esto, borrar la batería daría verde."""
    f = _bateria(tmp_path, "# sin ninguna prueba dentro\n")

    informe = vf.ejecutar_pruebas([str(f)], tmp_path)

    assert informe.sano is False and informe.ejecutadas == 0


def test_un_contrato_SIN_pruebas_minimas_no_declara_nada_sano(tmp_path):
    """Un contrato sin batería no produce un verificador permisivo: produce uno que dice `False`."""
    assert vf.ejecutar_pruebas([], tmp_path).sano is False
    assert vf.ejecutar_pruebas(None, tmp_path).sano is False


def test_un_fichero_de_pruebas_INEXISTENTE_no_declara_sano_el_arbol(tmp_path):
    """pytest sale con 4 —error de uso— y eso no es un fallo de prueba: hay que contarlo igual."""
    informe = vf.ejecutar_pruebas([str(tmp_path / "no_existe.py")], tmp_path)

    assert informe.sano is False


# ============================================================ COTAS Y PRECONDICIONES --


def test_una_bateria_que_NO_TERMINA_a_tiempo_no_se_declara_sana(tmp_path):
    """Agotar el plazo no es «pasó»: es que nadie llegó a decidir. Y el proceso se mata."""
    f = _bateria(tmp_path, "import time\n\n\ndef test_cuelga():\n    time.sleep(30)\n")

    informe = vf.ejecutar_pruebas([str(f)], tmp_path, limite_s=3)

    assert informe.agotado is True
    assert informe.codigo is None
    assert informe.sano is False


def test_con_el_ARNES_DE_MUTACION_corriendo_el_verificador_se_niega(tmp_path, monkeypatch):
    """Precondición declarada en la ficha de la capacidad, ejercida.

    Mientras el arnés muta ficheros en el sitio, el árbol NO contiene el código real: medir
    entonces es medir un mutante y reportarlo como si fuera el producto. Pasó de verdad el
    2026-08-09 y estuvo a un paso de declarar rota una garantía sana.
    """
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: True)
    f = _bateria(tmp_path, PRUEBA_VERDE)

    with pytest.raises(vf.ArnesEnCurso):
        vf.ejecutar_pruebas([str(f)], tmp_path)

    assert vf.arbol_sano([str(f)], tmp_path) is False, "el fallo del verificador tiene que ser rojo"


# ============================================================ NO ESCRIBE NADA --


def test_el_verificador_no_deja_NADA_escrito_en_el_arbol(tmp_path):
    """Capacidad de `tipo = "lectura"` con `limites_de_modificacion = "ninguna"`, comprobado."""
    f = _bateria(tmp_path, PRUEBA_VERDE)
    antes = sorted(p.name for p in tmp_path.iterdir())

    vf.ejecutar_pruebas([str(f)], tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == antes, "el verificador dejo ficheros"


def test_el_modulo_no_escribe_en_el_arbol_ni_habla_con_la_red(tmp_path):
    """Propiedad de diseño, comprobada sobre el árbol sintáctico y no sobre la prosa.

    Se mira el CÓDIGO y no el texto del fichero: la primera versión de un control así en este
    repositorio se encontró a sí misma en un docstring que explicaba precisamente la regla.
    """
    import ast

    arbol = ast.parse(pathlib.Path(vf.__file__).read_text(encoding="utf-8"))
    importados = {n.names[0].name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import)}
    importados |= {n.module.split(".")[0] for n in ast.walk(arbol)
                   if isinstance(n, ast.ImportFrom) and n.module}

    for prohibido in ("socket", "urllib", "requests", "http", "ftplib"):
        assert prohibido not in importados, f"el verificador no habla con la red: {prohibido}"
    llamadas = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    assert "write_text" not in llamadas and "write_bytes" not in llamadas


def test_el_verificador_no_importa_el_PRODUCTO(tmp_path):
    """La frontera plano/producto se respeta: el verificador es del plano y no alcanza el producto.

    Existía la tentación de importar el ejecutor de pytest que ya vive bajo `walking-skeleton/` y
    está probado. Que el plano alcance ese árbol es un acoplamiento nuevo, y eso no lo decide un
    módulo: lo decide el CEO. Aquí se porta la lección, no el código.

    **Se mira el ÁRBOL SINTÁCTICO, no el texto.** La primera versión de esta prueba escaneaba el
    fuente en crudo y falló contra su propio objetivo: el docstring del verificador *nombra* el
    módulo que promete no importar, y un detector que confunde hablar de algo con hacerlo produce
    falsos positivos — que en un control de seguridad se acaban desactivando, y eso es peor que no
    tenerlo. Un `import` es además la única forma real de alcanzar el producto.
    """
    import ast

    arbol = ast.parse(pathlib.Path(vf.__file__).read_text(encoding="utf-8"))
    importados = {a.name.split(".")[0] for n in ast.walk(arbol)
                  if isinstance(n, ast.Import) for a in n.names}
    importados |= {n.module.split(".")[0] for n in ast.walk(arbol)
                   if isinstance(n, ast.ImportFrom) and n.module}

    for prohibido in ("aura_skeleton", "herramientas", "walking_skeleton"):
        assert prohibido not in importados, f"el verificador alcanza el producto: {prohibido}"


# ============================================================ ATADO AL CONTRATO --


def test_el_liston_lo_pone_el_CONTRATO_y_no_el_ejecutor(tmp_path):
    """Quien decide qué hay que comprobar es quien autorizó el cambio."""
    verde = _bateria(tmp_path, PRUEBA_VERDE, "test_verde.py")
    _bateria(tmp_path, PRUEBA_ROJA, "test_rojo.py")

    contrato = {"verificacion": {"pruebas_minimas": [str(verde)]}}
    assert vf.verificador_de(contrato, tmp_path)() is True

    contrato_estricto = {"verificacion": {"pruebas_minimas": [str(tmp_path / "test_rojo.py")]}}
    assert vf.verificador_de(contrato_estricto, tmp_path)() is False


def test_un_contrato_sin_seccion_de_verificacion_no_pasa(tmp_path):
    assert vf.verificador_de({}, tmp_path)() is False
    assert vf.verificador_de(None, tmp_path)() is False


# ============================================================ EL CABLEADO, EJERCIDO --


def _montaje_real(tmp_path, monkeypatch, bateria: str):
    """Un circuito REVIEW completo cuyo contrato declara `bateria` como prueba mínima."""
    import contrato as ct
    import review

    objetivo = tmp_path / "observable.py"
    objetivo.write_text('E = "ORIGEN"\n', encoding="utf-8")
    prueba = tmp_path / "test_bateria.py"
    prueba.write_text(bateria, encoding="utf-8")

    caps = tmp_path / "caps"
    caps.mkdir()
    (caps / "cap.toml").write_text(f'''
id = "cap"
nombre = "c"
version = "1"
estado = "AUTORIZADA"
intencion = "i"
regla_de_transformacion = {{ operacion = "sustituir_texto", buscar = """"ORIGEN"""", sustituir = """"DESTINO"""" }}
[[entradas]]
nombre = "f"
fuente = "{objetivo}"
formato = "py"
[[salidas]]
resultado = "r"
destino = "{objetivo}"
[fuentes_de_verdad]
autoridad = ["{objetivo}"]
referencia = []
[perimetro]
modificables = ["{objetivo}"]
fuera_de_alcance = []
[autoridad]
nivel = "REVIEW"
acta = "DR-E"
parte_de_aura = "a"
parte_del_ceo = "b"
[ejecutor]
verbo = "implementar_incremento_especificado"
[efectos]
permitidos = ["x"]
prohibidos = []
reversible = true
[verificacion]
invariantes = ["INV-9"]
pruebas_minimas = ["{prueba}"]
criterio_de_aceptacion = "c"
evidencia = "e"
[trazabilidad]
especificacion = "f"
autorizacion = "DR-E"
''', encoding="utf-8")
    monkeypatch.setattr(ct, "CONTRATOS", caps)
    review.habilitar(tmp_path, por="ceo", acta="DR-E",
                     alcance=("implementar_incremento_especificado",))
    tarea = {"id": "T", "accion": "implementar_incremento_especificado", "simbolo": "",
             "forma": "funcion", "fichero": str(objetivo), "operacion": "sustituir_texto",
             "buscar": '"ORIGEN"', "sustituir": '"DESTINO"', "contrato": "cap"}
    return objetivo, tarea


def test_EL_CABLEADO_sin_verificador_explicito_se_deriva_del_contrato(tmp_path, monkeypatch):
    """El mutante VF-M1 sobrevivió a la primera versión de este fichero, y con razón.

    Todas las pruebas anteriores pasaban un verificador explícito o llamaban a `verificador_de()`
    directamente: ninguna ejercitaba el enchufe. Borrar el enchufe dejaba el verificador entero
    intacto —construido, probado y documentado— sin que protegiera nada, que es exactamente el
    patrón «declarado ≠ real». Esta prueba pasa `verificacion=None`, que es lo que pasa el punto de
    entrada empaquetado, y comprueba que **la batería del contrato decide**.
    """
    import review

    objetivo, tarea = _montaje_real(tmp_path, monkeypatch, PRUEBA_VERDE)

    r = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                    autoridad="orquestador", verificacion=None)

    assert r["ejecutado"] is True, "con la bateria del contrato en verde la tarea debe completarse"
    assert r["revertido"] is False
    assert objetivo.read_text(encoding="utf-8") == 'E = "DESTINO"\n'


def test_EL_CABLEADO_con_la_bateria_del_contrato_en_ROJO_revierte(tmp_path, monkeypatch):
    """La otra mitad: el enchufe tiene que poder decir que NO, o no es una barrera."""
    import review

    objetivo, tarea = _montaje_real(tmp_path, monkeypatch, PRUEBA_ROJA)
    antes = objetivo.read_text(encoding="utf-8")

    r = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                    autoridad="orquestador", verificacion=None)

    assert r["ejecutado"] is False and r["revertido"] is True
    assert objetivo.read_text(encoding="utf-8") == antes, "no se revirtio byte a byte"


# ============================================================ EL VEREDICTO, AISLADO --


def test_agotar_el_PLAZO_no_es_pasar_aunque_los_conteos_parezcan_sanos():
    """El mutante VF-M6 sobrevivía porque dos guardias se tapaban.

    Al agotar el plazo el proceso muere y el informe queda incompleto, así que el conteo ya salía a
    cero y `sano` era `False` por otra vía. La garantía «agotado ⟹ no sano» solo se puede ejercer
    aislándola: un informe con conteos impecables y `agotado=True` no es un árbol sano, porque nadie
    llegó a decidir.
    """
    assert vf.Informe(ejecutadas=9, fallidas=0, errores=0, omitidas=0,
                      agotado=True, codigo=None, salida="").sano is False
    assert vf.Informe(ejecutadas=9, fallidas=0, errores=0, omitidas=0,
                      agotado=False, codigo=0, salida="").sano is True


def test_un_informe_ILEGIBLE_cuenta_como_CERO_ejecutadas(tmp_path):
    """El mutante VF-M9 sobrevivía por lo mismo: la rama de error no se alcanzaba desde fuera.

    Si el informe no se puede leer —fichero ausente, XML corrupto—, no se puede afirmar que la
    batería pasó. Devolver cualquier otra cosa convertiría un fallo de medición en un veredicto.
    """
    assert vf._contar(tmp_path / "no_existe.xml") == (0, 0, 0, 0)
    corrupto = tmp_path / "corrupto.xml"
    corrupto.write_text("<testsuite esto no es xml", encoding="utf-8")
    assert vf._contar(corrupto) == (0, 0, 0, 0)
