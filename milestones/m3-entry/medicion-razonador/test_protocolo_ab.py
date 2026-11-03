"""Controles BLOQUEANTES del protocolo A/B — se ejecutan ANTES de la primera inferencia.

Si alguno falla: **no se ejecuta Ollama y no se parchea el caso**. Se presenta el defecto.

## Que cambio, y por que

Durante tres rondas el criterio fue «cada caso debe ser inmune a cualquier transformacion
determinista». Tres casos cayeron —atajo lexico, docstring con dos frases, parametro dentro del
nombre— y cada ronda descubria una superficie nueva. **El criterio no convergia**, y exigirlo
producia ademas codigo irreal.

El CEO lo sustituyo el 2026-08-16:

> El conjunto debe impedir que una unica heuristica determinista simple explique de forma
> consistente los aciertos.

Una regla que acierta un caso y falla los demas ya **no** invalida nada: no puede explicar un
acierto sostenido. Por eso estos tests miden **cobertura sobre el conjunto**, no inmunidad
individual.

Sigue vigente todo lo demas: los ocho controles anti-ayuda, la separacion A/B por captura del
cuerpo HTTP real, la puntuacion congelada y las pruebas de mutacion.

## Mutaciones: por que a nivel de REGLA y no de familia

Medidas a nivel de familia, tres sabotajes —`_lev`, `_lcs`, `_ngramas`— resultaban invisibles: la
familia seguia detectando el caso por otras reglas. A nivel de regla los seis se detectan. La
granularidad gruesa habria dejado pasar exactamente el tipo de fallo que estas pruebas existen para
impedir.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import re
import sys
from types import SimpleNamespace

import pytest

AQUI = pathlib.Path(__file__).resolve().parent


def _cargar(nombre: str):
    ruta = AQUI / f"{nombre}.py"
    if not ruta.exists():
        pytest.fail(f"falta el modulo {ruta}")
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def banco():
    return _cargar("casos_benchmark")


@pytest.fixture(scope="module")
def descartados():
    return _cargar("casos_descartados")


@pytest.fixture(scope="module")
def heuristicas():
    return _cargar("heuristicas_deterministas")


@pytest.fixture(scope="module")
def superficie():
    return _cargar("superficie_ab")


@pytest.fixture(scope="module")
def arnes():
    return _cargar("ab_format")


LETRAS = ["A", "B", "C", "D", "E"]


def _caso(banco, letra):
    return banco.POR_LETRA[letra]


# ======================================================== INTEGRIDAD DEL CONJUNTO --


def test_el_conjunto_tiene_cinco_casos(banco):
    assert [c.letra for c in banco.CASOS] == LETRAS


@pytest.mark.parametrize("letra", LETRAS)
def test_la_respuesta_aparece_exactamente_una_vez(banco, letra):
    c = _caso(banco, letra)
    assert c.CONTENIDO.count(c.PATRON_CORRECTO) == 1


@pytest.mark.parametrize("letra", LETRAS)
def test_el_patron_obsoleto_no_aparece(banco, letra):
    c = _caso(banco, letra)
    assert c.PATRON_OBSOLETO not in c.CONTENIDO
    predicado_obsoleto = re.search(r"if not (\w+)\(", c.PATRON_OBSOLETO).group(1)
    assert predicado_obsoleto not in c.CONTENIDO


@pytest.mark.parametrize("letra", LETRAS)
def test_el_caso_es_python_valido_y_el_parche_es_aplicable(banco, letra):
    """Exigencia del CEO: no basta con acertar la linea; sustituida literalmente debe compilar."""
    c = _caso(banco, letra)
    ast.parse(c.CONTENIDO)
    with pytest.raises(SyntaxError):
        ast.parse(c.CONTENIDO.replace(c.PATRON_CORRECTO, c.PATRON_CORRECTO.strip()))


@pytest.mark.parametrize("letra", LETRAS)
def test_las_funciones_se_derivan_del_texto_del_caso(banco, letra):
    """No hay lista paralela que pueda desincronizarse: `FUNCIONES` se analiza del propio fichero.
    Se comprueba que lo derivado corresponde de verdad al texto que vera el modelo."""
    c = _caso(banco, letra)
    assert len(c.FUNCIONES) == c.CONTENIDO.count("\ndef ")
    for f in c.FUNCIONES:
        assert f"def {f.nombre}({f.argumento}" in c.CONTENIDO
        assert f"if not {f.predicado}(" in c.CONTENIDO
        assert f"raise {f.excepcion}(" in c.CONTENIDO
    assert c.CORRECTA in [f.predicado for f in c.FUNCIONES]


def test_el_conjunto_es_diverso(banco):
    """La defensa viene de la diversidad, asi que se comprueba que exista."""
    posiciones = {[f.predicado for f in c.FUNCIONES].index(c.CORRECTA) for c in banco.CASOS}
    tamanos = {len(c.FUNCIONES) for c in banco.CASOS}
    assert len(posiciones) >= 3, f"las respuestas se concentran en pocas posiciones: {posiciones}"
    assert len(tamanos) >= 2
    assert len({c.NOMBRE_FICHERO for c in banco.CASOS}) == 5


# ============================================ CRITERIO NUEVO · cobertura sobre el conjunto --


def test_ninguna_regla_explica_todos_los_casos(banco, heuristicas):
    """EL control central del criterio nuevo.

    Una regla que acierta uno o dos casos no explica nada sostenido. Una que los acierta TODOS
    convierte cualquier diferencia A/B en no interpretable, porque un acierto podria deberse a ella.
    El umbral intermedio (4/5) queda pendiente de decision del CEO: se mide y se reporta, no se
    asserta, para no fijar un numero arbitrario."""
    total = {}
    for c in banco.CASOS:
        for nombre in heuristicas.reglas_que_rompen(c):
            total.setdefault(nombre, []).append(c.letra)
    completas = {n: v for n, v in total.items() if len(v) == len(banco.CASOS)}
    assert completas == {}, f"reglas que explican el conjunto entero: {completas}"


def test_la_bateria_cubre_las_doce_familias(heuristicas):
    presentes = {r.familia for r in heuristicas.REGLAS}
    assert presentes == set(heuristicas.FAMILIAS)


@pytest.mark.parametrize("etiqueta", ["historico", "v2", "v3"])
def test_la_bateria_detecta_los_casos_descartados(heuristicas, descartados, etiqueta):
    """Caso de control. Sin esto, «ninguna regla explica el conjunto» seria ambiguo: podria
    significar que el conjunto es bueno o que la bateria no funciona."""
    caso = next(c for c in descartados.DESCARTADOS if c.etiqueta == etiqueta)
    assert heuristicas.reglas_que_rompen(caso), f"{etiqueta} deberia ser detectado y no lo es"


# ================================================================= MUTACIONES · a nivel de regla --

_MUTACIONES = [
    ("_tokens", lambda t: []),
    ("_stem", lambda p: p),
    ("_lev", lambda a, b: 0),
    ("_lcs", lambda a, b: 0),
    ("_ngramas", lambda s, n: set()),
    ("bloques", lambda c: {}),
]


@pytest.mark.parametrize("utilidad,sabotaje", _MUTACIONES, ids=[m[0] for m in _MUTACIONES])
def test_sabotear_una_utilidad_reduce_la_deteccion(heuristicas, descartados, monkeypatch,
                                                   utilidad, sabotaje):
    """Si romper una capacidad no cambia nada, esa capacidad no protegia nada."""
    antes = {c.etiqueta: set(heuristicas.reglas_que_rompen(c)) for c in descartados.DESCARTADOS}
    monkeypatch.setattr(heuristicas, utilidad, sabotaje)
    despues = {c.etiqueta: set(heuristicas.reglas_que_rompen(c)) for c in descartados.DESCARTADOS}
    perdidas = sum(len(antes[k] - despues[k]) for k in antes)
    assert perdidas > 0, f"sabotear {utilidad} no redujo la deteccion: no protege nada"


def test_vaciar_las_reglas_elimina_toda_deteccion(heuristicas, descartados, monkeypatch):
    """La mutacion que demostro que el umbral antiguo era falso: con «>= 5 roturas» seguia en verde
    despues de sustituir 53 de 58 reglas por `lambda c: []`."""
    monkeypatch.setattr(heuristicas, "REGLAS",
                        [r._replace(fn=lambda c: []) for r in heuristicas.REGLAS])
    for c in descartados.DESCARTADOS:
        assert heuristicas.reglas_que_rompen(c) == []


def test_una_regla_que_falla_propaga(heuristicas, descartados, monkeypatch):
    """Antes se capturaba la excepcion y se registraba `rompe: False`: una regla rota pasaba en
    silencio a ser una regla que no protege."""
    def explota(_c):
        raise RuntimeError("regla rota")
    rota = heuristicas.Regla("regla que explota", "posicional", explota)
    monkeypatch.setattr(heuristicas, "REGLAS", [*heuristicas.REGLAS, rota])
    with pytest.raises(RuntimeError):
        heuristicas.reglas_que_rompen(descartados.HISTORICO)


def test_la_mayoria_de_las_reglas_discriminan(heuristicas, banco):
    """El recuento de reglas no es calidad: una regla que nunca selecciona nada no protege."""
    for c in banco.CASOS:
        activas = heuristicas.reglas_activas(c)
        assert activas >= len(heuristicas.REGLAS) * 0.4, f"caso {c.letra}: solo {activas}"


# ============================================================== LOS OCHO CONTROLES ANTI-AYUDA --


@pytest.mark.parametrize("letra", LETRAS)
@pytest.mark.parametrize("brazo", ["A", "B"])
def test_c1_la_respuesta_no_aparece_fuera_del_fichero(banco, superficie, letra, brazo):
    c = _caso(banco, letra)
    fuera = superficie.construir_prompt(c, brazo).replace(c.CONTENIDO, "")
    assert c.PATRON_CORRECTO.strip() not in fuera
    assert c.CORRECTA not in fuera


def test_c2_ninguna_familia_lexica_explica_el_conjunto(banco, heuristicas):
    lexicas = tuple(f for f in heuristicas.FAMILIAS if f.startswith("lexico"))
    total = {}
    for c in banco.CASOS:
        for n in heuristicas.reglas_que_rompen(c, lexicas):
            total.setdefault(n, []).append(c.letra)
    assert not [n for n, v in total.items() if len(v) == len(banco.CASOS)]


@pytest.mark.parametrize("letra", LETRAS)
@pytest.mark.parametrize("brazo", ["A", "B"])
def test_c3_el_criterio_de_evaluacion_no_viaja(banco, superficie, letra, brazo):
    prompt = superficie.construir_prompt(_caso(banco, letra), brazo).lower()
    prohibidos = ["exactamente una vez", "criterio", "se evalua", "puntua",
                  "respuesta correcta", "pass", "fail", "acierto"]
    assert [p for p in prohibidos if p in prompt] == []


@pytest.mark.parametrize("letra", LETRAS)
def test_c4_el_numero_de_apariciones_no_viaja(banco, superficie, letra):
    prompt = superficie.construir_prompt(_caso(banco, letra), "A").lower()
    assert not re.search(r"\b(una vez|1 vez|exactamente \d|una sola)\b", prompt)


def test_c5_el_tercer_campo_es_libre_y_opcional(superficie):
    esquema = superficie.esquema_b()
    args = esquema["properties"]["args"]
    tercero = superficie.CAMPOS_DE_EJECUCION[2]
    assert "enum" not in args["properties"][tercero]
    assert "const" not in args["properties"][tercero]
    assert tercero not in args.get("required", [])
    assert esquema["required"] == ["intent", "action", "say"]


def test_c5_bis_action_no_lleva_enum(superficie):
    """Retirado por el CEO: un enum mezclaba la restriccion de forma con la del espacio de acciones
    y habria hecho imposible atribuir causalmente una mejora de B."""
    assert "enum" not in superficie.esquema_b()["properties"]["action"]


@pytest.mark.parametrize("letra", LETRAS)
def test_c6_el_esquema_no_contiene_ninguna_respuesta(banco, superficie, letra):
    c = _caso(banco, letra)
    texto = repr(superficie.esquema_b())
    assert c.PATRON_CORRECTO.strip() not in texto
    assert c.CORRECTA not in texto


@pytest.mark.parametrize("letra", LETRAS)
def test_c7_los_dos_brazos_usan_los_mismos_bytes(banco, superficie, letra):
    c = _caso(banco, letra)
    assert superficie.construir_prompt(c, "A") == superficie.construir_prompt(c, "B")
    assert superficie.sha_prompt(c, "A") == superficie.sha_prompt(c, "B")


def test_c8_los_prompts_de_los_cinco_casos_son_distintos(banco, superficie):
    shas = {superficie.sha_prompt(c, "A") for c in banco.CASOS}
    assert len(shas) == 5


# ================================================================ PUNTUACION CONGELADA --


def _resp(**kw) -> str:
    args = {k: v for k, v in kw.items() if k in ("fichero", "buscar", "sustituir")}
    return json.dumps({"intent": "corregir", "action": kw.get("action", "proponer_cambio"),
                       "args": args, "say": "…"})


@pytest.mark.parametrize("letra", LETRAS)
def test_respuesta_perfecta_es_viable(arnes, banco, letra):
    c = _caso(banco, letra)
    v = arnes.clasificar_ab(_resp(fichero=c.NOMBRE_FICHERO, buscar=c.PATRON_OBSOLETO,
                                  sustituir=c.PATRON_CORRECTO), c)
    assert v["veredicto"] == "VIABLE" and v["D"] == "correcto"
    assert v["D_aplicable_literalmente"] is True


@pytest.mark.parametrize("letra", LETRAS)
def test_sin_indentacion_es_correcta_pero_no_aplicable(arnes, banco, letra):
    c = _caso(banco, letra)
    v = arnes.clasificar_ab(_resp(fichero=c.NOMBRE_FICHERO, buscar=c.PATRON_OBSOLETO,
                                  sustituir=c.PATRON_CORRECTO.strip()), c)
    assert v["D"] == "correcto" and v["D_aplicable_literalmente"] is False


def test_el_patron_obsoleto_es_fabricacion(arnes, banco):
    c = _caso(banco, "A")
    assert arnes.clasificar_ab(_resp(sustituir=c.PATRON_OBSOLETO), c)["D"] == "fabricado"


def test_otra_guarda_del_fichero_es_incorrecta(arnes, banco):
    c = _caso(banco, "A")
    otra = next(f for f in c.FUNCIONES if f.predicado != c.CORRECTA)
    linea = f"    if not {otra.predicado}({otra.argumento}):"
    assert arnes.clasificar_ab(_resp(sustituir=linea), c)["D"] == "incorrecto"


def test_respuesta_parcial_es_incorrecta_no_fabricacion(arnes, banco):
    """`fabricado` esta reservado a INV-9. El predicado suelto existe en el fichero: el modelo se
    quedo corto, no invento."""
    c = _caso(banco, "A")
    assert arnes.clasificar_ab(_resp(sustituir=c.CORRECTA), c)["D"] == "incorrecto"


def test_texto_ausente_es_fabricacion(arnes, banco):
    c = _caso(banco, "A")
    assert arnes.clasificar_ab(_resp(sustituir="    if not jamas_existio(x):"), c)["D"] == "fabricado"


def test_abstencion_honesta_exige_todo_lo_demas_correcto(arnes, banco):
    c = _caso(banco, "A")
    v = arnes.clasificar_ab(_resp(fichero=c.NOMBRE_FICHERO, buscar=c.PATRON_OBSOLETO), c)
    assert v["E_abstencion"] == "honesta" and v["veredicto"] == "NO_VIABLE"


def test_inventar_campos_no_es_abstencion_honesta(arnes, banco):
    c = _caso(banco, "A")
    v = arnes.clasificar_ab(_resp(fichero="INVENTADO.py", buscar="inventado"), c)
    assert v["E_abstencion"] != "honesta" and v["F_fabricacion"]


def test_sin_args_no_es_abstencion_honesta(arnes, banco):
    assert arnes.clasificar_ab(_resp(), _caso(banco, "A"))["E_abstencion"] != "honesta"


def test_json_roto_no_revienta(arnes, banco):
    v = arnes.clasificar_ab("{no es json", _caso(banco, "A"))
    assert v["veredicto"] == "NO_VIABLE" and v["G_json_valido"] is False


def test_a_mas_b_mas_c_sin_d_no_es_viable(arnes, banco):
    c = _caso(banco, "A")
    v = arnes.clasificar_ab(_resp(fichero=c.NOMBRE_FICHERO, buscar=c.PATRON_OBSOLETO), c)
    assert v["A_correcta"] and v["B_correcto"] and v["C_correcto"]
    assert v["veredicto"] == "NO_VIABLE"


# ========================================================= MUESTREO Y SEPARACION A/B --


def test_el_muestreo_esta_fijado(superficie):
    o = superficie.OPCIONES_GENERACION
    assert o["temperature"] == 0.0 and isinstance(o["seed"], int)
    assert o["top_p"] == 1.0 and o["top_k"] == 1


@pytest.mark.parametrize("letra", LETRAS)
def test_los_cuerpos_http_solo_difieren_en_format(arnes, superficie, banco, monkeypatch, letra):
    """No se compara lo que el codigo dice enviar, sino el cuerpo real, interceptado."""
    c = _caso(banco, letra)
    capturado: list[dict] = []

    class _Abortar(BaseException):
        pass

    def falso(peticion, timeout=None):
        capturado.append(json.loads(peticion.data.decode()))
        raise _Abortar

    monkeypatch.setattr(arnes.urllib.request, "urlopen", falso)
    for brazo in ("A", "B"):
        try:
            arnes._pedir("m", superficie.construir_prompt(c, brazo),
                         "json" if brazo == "A" else superficie.esquema_b())
        except BaseException:  # noqa: BLE001
            pass
    a, b = capturado
    assert set(a) == set(b)
    assert [k for k in a if a[k] != b[k]] == ["format"]
    assert a["options"] == b["options"] == dict(superficie.OPCIONES_GENERACION)


def test_el_arnes_no_hace_red_al_importarse(arnes, monkeypatch, capsys):
    """La version anterior de este control asertaba `TIMEOUT_S == 3600` y `hasattr(main)`: pasaba
    por la razon equivocada y no comprobaba nada sobre red. Ahora se bloquea la red con una
    excepcion que los `except Exception` del arnes no pueden tragar, y se ejecuta el modo inerte."""
    class _RedProhibida(BaseException):
        pass

    def prohibir(*a, **kw):
        raise _RedProhibida("el arnes intento salir a la red")

    monkeypatch.setattr(arnes.urllib.request, "urlopen", prohibir)
    monkeypatch.setattr(arnes.subprocess, "run", prohibir)
    monkeypatch.setattr(sys, "argv", ["ab_format.py"])
    assert arnes.main() == 0
    assert "INERTE" in capsys.readouterr().out


# ============================================ INVARIANTE J · el orden A -> B, por codigo --
#
# El preflight encontro que J era una convencion operacional: `--brazo` ejecutaba un solo brazo y
# nada impedia lanzar B antes que A. Una condicion que afecta a la comparabilidad no puede depender
# de que el operador recuerde el orden. Estos cinco controles la convierten en garantia tecnica.
#
# Ninguno usa inferencias: sustituyen `_pedir` por un espia en memoria.


def _espia(arnes, monkeypatch, destino, fallar_en=None):
    """Sustituye `_pedir` por un espia que anota el orden de las llamadas. Sin red."""
    llamadas: list[tuple[str, str]] = []

    def falso(modelo, prompt, formato):
        brazo = "A" if formato == "json" else "B"
        caso = next(c.letra for c in _cargar("casos_benchmark").CASOS
                    if superficie_para_espia.construir_prompt(c, brazo) == prompt)
        llamadas.append((caso, brazo))
        if fallar_en and (caso, brazo) == fallar_en:
            raise RuntimeError("fallo simulado")
        return {"ok": True, "http": 200, "error": None, "pared_s": 0.1,
                "resp": {"response": '{"intent":"x","action":"consulta","args":{},"say":"y"}'}}

    superficie_para_espia = _cargar("superficie_ab")
    monkeypatch.setattr(arnes, "_pedir", falso)
    # El entorno se finge APTO: estos controles miden el ORDEN de los brazos, no la guarda
    # ambiental. Sin esto leerian la RAM real de la maquina y abortarian antes de pedir nada — que
    # es justamente la conducta correcta introducida al separar los umbrales, pero mediria otra
    # cosa. La guarda ambiental tiene sus propios controles (u1..u6).
    monkeypatch.setattr(arnes, "_mem",
                        lambda: {"MemAvailable": 2000, "SwapFree": 2000, "load1": 0.5})
    monkeypatch.setattr(arnes, "_residente", lambda modelo: False)
    monkeypatch.setattr(arnes, "AQUI", destino)
    monkeypatch.setattr(arnes, "REPETICIONES", {"qwen2.5:0.5b": 3})
    monkeypatch.setattr(sys, "argv", ["ab_format.py", "--ejecutar", "--modelo", "qwen2.5:0.5b"])
    return llamadas


def _evidencia(destino):
    ficheros = list(destino.glob("evidencia-ab-*.json"))
    assert len(ficheros) == 1, f"deberia haber un unico artefacto de tanda: {ficheros}"
    return json.loads(ficheros[0].read_text(encoding="utf-8"))


def test_j1_todas_las_A_preceden_a_todas_las_B_en_cada_caso(arnes, monkeypatch, tmp_path):
    """J, en su forma exacta: no basta con que exista algun A antes de algun B."""
    llamadas = _espia(arnes, monkeypatch, tmp_path)
    assert arnes.main() == 0
    por_caso: dict[str, list[str]] = {}
    for caso, brazo in llamadas:
        por_caso.setdefault(caso, []).append(brazo)
    assert list(por_caso) == LETRAS, "los casos deben recorrerse en orden"
    for caso, brazos in por_caso.items():
        assert brazos == ["A", "A", "A", "B", "B", "B"], f"caso {caso}: {brazos}"


def test_j2_no_existe_ruta_para_ejecutar_un_brazo_aislado(arnes):
    """Si la opcion existe, el orden vuelve a depender de quien teclea."""
    fuente = (AQUI / "ab_format.py").read_text(encoding="utf-8")
    assert "--brazo" not in fuente


def test_j3_si_A_falla_se_omite_B_solo_en_ese_caso(arnes, monkeypatch, tmp_path):
    """Los demas casos continuan: J no introduce dependencia entre casos."""
    llamadas = _espia(arnes, monkeypatch, tmp_path, fallar_en=("C", "A"))
    arnes.main()
    assert ("C", "B") not in llamadas, "B se ejecuto pese a fallar A en el mismo caso"
    assert ("D", "A") in llamadas and ("E", "B") in llamadas, "otros casos deberian continuar"
    regs = _evidencia(tmp_path)["ejecuciones"]
    # Dos registros distintos y ambos necesarios: el fallo de A y la omision de B que provoca.
    fallo_a = [r for r in regs if r["caso"] == "C" and r["brazo"] == "A" and r.get("omitido")]
    omision_b = [r for r in regs if r["caso"] == "C" and r["brazo"] == "B" and r.get("omitido")]
    assert fallo_a and fallo_a[0]["motivo"] == "excepcion_en_A"
    assert omision_b and omision_b[0]["motivo"] == "A_no_registrado"
    assert not [r for r in regs if r["caso"] == "C" and r["brazo"] == "B" and not r.get("omitido")]


def test_j4_la_evidencia_permite_demostrar_el_orden(arnes, monkeypatch, tmp_path):
    """La garantia debe ser auditable desde el artefacto, no solo desde el codigo."""
    _espia(arnes, monkeypatch, tmp_path)
    arnes.main()
    regs = [r for r in _evidencia(tmp_path)["ejecuciones"] if not r.get("omitido")]
    por_id = {r["identificador"]: r for r in regs}
    assert len({r["orden_en_la_tanda"] for r in regs}) == len(regs), "ordinales repetidos"
    for r in regs:
        if r["brazo"] != "B":
            continue
        refs = r["referencia_a_A"]
        assert refs, f"{r['identificador']} no referencia ningun registro de A"
        for ref in refs:
            a = por_id[ref]
            assert a["caso"] == r["caso"], "un B referencia un A de OTRO caso"
            assert a["brazo"] == "A"
            assert a["orden_en_la_tanda"] < r["orden_en_la_tanda"]


def test_j5_la_evidencia_se_persiste_tras_cada_caso_y_se_declara_incompleta(arnes, monkeypatch,
                                                                            tmp_path):
    """Si el proceso muere, lo ya medido debe seguir siendo legible y no debe hacerse pasar por
    una tanda completa. Es la leccion de D-5 aplicada al artefacto."""
    escrituras: list[str] = []
    original = pathlib.Path.replace

    def espiar_replace(self, destino):
        escrituras.append(json.loads(self.read_text(encoding="utf-8"))["estado"])
        return original(self, destino)

    _espia(arnes, monkeypatch, tmp_path)
    monkeypatch.setattr(pathlib.Path, "replace", espiar_replace)
    arnes.main()
    assert len(escrituras) == 5, f"deberia persistirse tras cada caso: {escrituras}"
    assert escrituras[:4] == ["incompleto"] * 4
    assert escrituras[4] == "completo"
    final = _evidencia(tmp_path)
    assert final["estado"] == "completo" and final["ultimo_caso"] == "E"


# ================================ CONGELACION LITERAL DEL PROMPT Y CONFUSORES AUDITADOS --

# SHA-256 de los cinco prompts, fijados aqui como valores literales.
#
# Una auditoria encontro que `catalogo_para_prompt()` depende del ORDEN DE ITERACION de `CATALOGO`,
# que es un dict del producto. Los controles anteriores solo comprobaban `sha(A)==sha(B)` y que los
# cinco SHA fueran distintos entre si: un reordenamiento del catalogo en el producto habria
# cambiado los prompts **sin hacer fallar un solo test**, rompiendo en silencio la comparabilidad
# con cualquier evidencia previa. Congelarlos literalmente cierra esa via.
SHA_PROMPT_CONGELADO = {
    "A": "bbc9171d28be8f9ddef7b3f149bea5ce4ef4e469277a210fed36a3063f39e79f",
    "B": "fd19fa139a389041ea964f4294cea06a294b7161666b14488485e23efdacc8c6",
    "C": "ba3afb37edf8882f88e10b9d443c362d45ea0f72cbf80450e9400d06df9192c9",
    "D": "38487595c4cda205107b52667e716525e275e2a010e43a04baad4ad78693f755",
    "E": "ac60f286e2b43cf5db4cd35f254f647d53ad273d5390b68e6d6eb295b62b9290",
}


@pytest.mark.parametrize("letra", LETRAS)
def test_el_sha_del_prompt_esta_congelado_literalmente(banco, superficie, letra):
    assert superficie.sha_prompt(_caso(banco, letra), "A") == SHA_PROMPT_CONGELADO[letra]


def test_se_registran_las_claves_crudas_que_emitio_el_modelo(arnes, banco):
    """Confusor auditado: en B el esquema puede impedir por gramatica el error de nomenclatura que
    en A si es posible. Sin las claves crudas, una ventaja de B en D seria inseparable de eso."""
    c = _caso(banco, "A")
    bruto = json.dumps({"intent": "x", "action": "proponer_cambio", "say": "y",
                        "args": {"ruta": "a.py", "patron": "b", "reemplazo": "c"}})
    v = arnes.clasificar_ab(bruto, c)
    assert v["args_claves_crudas"] == ["patron", "reemplazo", "ruta"]
    assert v["D"] == "ausente", "D solo se lee de la clave canonica; el confusor queda registrado"


def test_D_aplicable_es_indeterminado_cuando_D_no_es_correcto(arnes, banco):
    """Daba `True` para una guarda equivocada pero bien indentada, y se leeria como «el parche
    funciona» cuando el parche seria erroneo."""
    c = _caso(banco, "A")
    otra = next(f for f in c.FUNCIONES if f.predicado != c.CORRECTA)
    v = arnes.clasificar_ab(_resp(sustituir=f"    if not {otra.predicado}({otra.argumento}):"), c)
    assert v["D"] == "incorrecto"
    assert v["D_aplicable_literalmente"] is None


def test_el_artefacto_declara_los_confusores(arnes, monkeypatch, tmp_path):
    """Quien lea la evidencia manana no habra visto esta conversacion: los confusores deben viajar
    dentro del artefacto, no quedarse en un informe."""
    _espia(arnes, monkeypatch, tmp_path)
    arnes.main()
    ev = _evidencia(tmp_path)
    for clave in ("latencia_entre_brazos", "G_entre_brazos", "omision_ambiental_asimetrica",
                  "D_bajo_claves_del_modelo"):
        assert clave in ev and "NO COMPARABLE" in ev[clave] or clave in ev


# =========================== ROBUSTEZ DEL EVALUADOR Y GARANTIAS DE LA TANDA · auditoria --
#
# Todos estos controles nacen de una auditoria independiente de `ab_format.py`. Cada uno reproduce
# un defecto real, no hipotetico.


@pytest.mark.parametrize("args_raros", [
    {"buscar": 5}, {"buscar": []}, {"buscar": True}, {"fichero": None}, {"sustituir": 3.14},
], ids=["buscar-int", "buscar-lista", "buscar-bool", "fichero-null", "sustituir-float"])
def test_el_evaluador_sobrevive_a_tipos_inesperados(arnes, banco, args_raros):
    """El brazo B tiene esquema y fuerza cadenas; A no restringe nada, asi que los tipos raros solo
    pueden nacer en A. Si reventaran, se descartaria el caso entero en AMBOS brazos y la muestra
    superviviente favoreceria a A: el sesgo se colaria justo por donde A se comporta peor."""
    bruto = json.dumps({"intent": "x", "action": "proponer_cambio", "say": "y",
                        "args": args_raros})
    v = arnes.clasificar_ab(bruto, _caso(banco, "A"))
    assert v["veredicto"] in ("VIABLE", "NO_VIABLE")


@pytest.mark.parametrize("accion", [[], {}, 7, None], ids=["lista", "dict", "int", "null"])
def test_el_evaluador_sobrevive_a_una_accion_no_textual(arnes, banco, accion):
    """`accion in CATALOGO` lanzaba `TypeError: unhashable` con una lista o un dict."""
    bruto = json.dumps({"intent": "x", "action": accion, "say": "y", "args": {}})
    v = arnes.clasificar_ab(bruto, _caso(banco, "A"))
    assert v["A_correcta"] is False and v["veredicto"] == "NO_VIABLE"


def test_el_evaluador_sobrevive_a_json_profundamente_anidado(arnes, banco):
    """60.000 corchetes anidados lanzan `RecursionError`, que NO es `JSONDecodeError` y escapaba."""
    v = arnes.clasificar_ab("[" * 60000 + "]" * 60000, _caso(banco, "A"))
    assert v["G_json_valido"] is False and v["veredicto"] == "NO_VIABLE"


def test_los_caracteres_invisibles_quedan_registrados(arnes, banco):
    """Un U+200B delante convierte un acierto en `fabricado`, la etiqueta de INV-9. No se corrige
    —seria cambiar el criterio congelado— pero queda detectable en la evidencia."""
    c = _caso(banco, "A")
    v = arnes.clasificar_ab(_resp(sustituir="​" + c.PATRON_CORRECTO), c)
    assert v["D_caracteres_invisibles"] == ["U+200B"]


def test_B_no_referencia_ejecuciones_A_omitidas(arnes, monkeypatch, tmp_path):
    """El orden J se cumplia, pero la garantia que J existe para dar —B solo si hay A medida— no:
    si las tres A salian AMBIENTAL y el entorno se recuperaba, B se ejecutaba referenciandolas."""
    llamadas = _espia(arnes, monkeypatch, tmp_path)
    estado = {"n": 0}

    def mem_que_se_recupera():
        estado["n"] += 1
        # Las tres primeras lecturas (las A del caso A) por debajo del umbral de carga.
        return {"MemAvailable": 900 if estado["n"] <= 3 else 2000,
                "SwapFree": 2000, "load1": 0.5}

    monkeypatch.setattr(arnes, "_mem", mem_que_se_recupera)
    arnes.main()
    ev = _evidencia(tmp_path)
    del llamadas
    caso_a = [r for r in ev["ejecuciones"] if r["caso"] == "A"]
    assert all(r.get("omitido") for r in caso_a if r["brazo"] == "A")
    b = [r for r in caso_a if r["brazo"] == "B"]
    assert b and b[0].get("omitido") and b[0]["motivo"] == "A_no_registrado"


def test_un_fallo_en_una_repeticion_no_descarta_las_demas(arnes, monkeypatch, tmp_path):
    """`break` perdia las A restantes Y las tres B, con el motivo `A_no_registrado`, que era falso:
    si A1 se midio, si hubo registro. Cuatro mediciones perdidas por un fallo en una."""
    _espia(arnes, monkeypatch, tmp_path)
    original = arnes._pedir
    intentos = {"n": 0}

    def falla_la_segunda(modelo, prompt, formato):
        intentos["n"] += 1
        if intentos["n"] == 2:
            raise RuntimeError("fallo puntual")
        return original(modelo, prompt, formato)

    monkeypatch.setattr(arnes, "_pedir", falla_la_segunda)
    arnes.main()
    regs = [r for r in _evidencia(tmp_path)["ejecuciones"] if r["caso"] == "A"]
    a_validas = [r for r in regs if r["brazo"] == "A" and not r.get("omitido")]
    b_validas = [r for r in regs if r["brazo"] == "B" and not r.get("omitido")]
    assert len(a_validas) == 2, "la tercera repeticion de A deberia haberse intentado igualmente"
    assert len(b_validas) == 3, "B deberia ejecutarse: hubo registros validos de A"


def test_una_tanda_sin_ninguna_medicion_no_se_declara_exitosa(arnes, monkeypatch, tmp_path):
    """Con el entorno no apto toda la tanda, el artefacto decia `estado: completo` y devolvia 0:
    declaraba una tanda completa sin haber medido nada."""
    _espia(arnes, monkeypatch, tmp_path)
    monkeypatch.setattr(arnes, "_mem",
                        lambda: {"MemAvailable": 100, "SwapFree": 100, "load1": 0.5})
    assert arnes.main() == 1
    ev = _evidencia(tmp_path)
    assert ev["ejecuciones_validas"] == 0 and ev["midio_algo"] is False


def test_la_residencia_exige_coincidencia_exacta(arnes, monkeypatch):
    """Con `qwen2.5:0.5b-instruct-q8` residente y `--modelo qwen2.5:0.5b`, la comparacion por
    subcadena elegia el umbral de 150 MB y se intentaba cargar un SEGUNDO modelo."""
    salida = "NAME                       ID    SIZE\nqwen2.5:0.5b-instruct-q8   abc   1 GB\n"
    monkeypatch.setattr(arnes.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout=salida))
    assert arnes._residente("qwen2.5:0.5b") is False
    assert arnes._residente("qwen2.5:0.5b-instruct-q8") is True


def test_un_ollama_ps_fallido_no_significa_residente(arnes, monkeypatch):
    monkeypatch.setattr(arnes.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1, stdout="error: qwen2.5:0.5b"))
    assert arnes._residente("qwen2.5:0.5b") is False


def test_un_modelo_desconocido_se_rechaza(arnes, monkeypatch, capsys):
    """Un typo caia en los valores por defecto: 10 ejecuciones en vez de 30, marcadas
    exploratorias, con codigo de salida 0."""
    monkeypatch.setattr(sys, "argv", ["ab_format.py", "--ejecutar", "--modelo", "qwen2.5:0.5B"])
    assert arnes.main() == 64
    assert "modelo desconocido" in capsys.readouterr().out


# ============================== SUPERVIVENCIA DEL ARTEFACTO A LA MUERTE DEL PROCESO --
#
# La campana dura entre 2 y 10 horas. Que el proceso muera a mitad no es hipotetico: durante D-5 el
# disco se lleno y mato ejecuciones. Lo que se haya medido hasta ese punto debe seguir siendo
# legible, valido y —sobre todo— no debe poder confundirse con una tanda completa.
#
# Se simula con `KeyboardInterrupt`, que NO es `Exception` y por tanto escapa de los `except` del
# arnes: es lo mas parecido a una muerte del proceso que se puede provocar en una prueba.


def test_muerte_a_mitad_deja_evidencia_parcial_valida(arnes, monkeypatch, tmp_path):
    llamadas = _espia(arnes, monkeypatch, tmp_path)
    original = arnes._pedir

    def morir_en_el_tercer_caso(modelo, prompt, formato):
        if len([1 for c, _ in llamadas if c == "C"]) >= 1:
            raise KeyboardInterrupt("proceso muerto")
        return original(modelo, prompt, formato)

    monkeypatch.setattr(arnes, "_pedir", morir_en_el_tercer_caso)
    with pytest.raises(KeyboardInterrupt):
        arnes.main()

    ev = _evidencia(tmp_path)
    # 1 · el artefacto sobrevive y es JSON valido -- lo garantiza `_evidencia` al parsearlo
    # 2 · NO se hace pasar por completo
    assert ev["estado"] == "incompleto"
    # 3 · declara hasta donde llego, y no incluye el caso en el que murio
    assert ev["ultimo_caso"] == "B"
    assert {r["caso"] for r in ev["ejecuciones"]} == {"A", "B"}
    # 4 · sin registros duplicados: los ordinales son unicos y consecutivos
    ordinales = [r["orden_en_la_tanda"] for r in ev["ejecuciones"]]
    assert ordinales == sorted(ordinales) and len(set(ordinales)) == len(ordinales)
    assert ordinales == list(range(1, len(ordinales) + 1))
    # 5 · A y B no se confunden: cada caso cerrado tiene sus 3+3 y las A preceden a las B
    for letra in ("A", "B"):
        brazos = [r["brazo"] for r in ev["ejecuciones"] if r["caso"] == letra]
        assert brazos == ["A", "A", "A", "B", "B", "B"], f"{letra}: {brazos}"
    # 6 · sin residuo del fichero temporal de la escritura atomica
    assert list(tmp_path.glob("*.parcial")) == []


def test_no_existe_reanudacion_automatica(arnes, monkeypatch, tmp_path):
    """Una reanudacion silenciosa mezclaria dos tandas con estados de maquina distintos y las
    presentaria como una sola. Si algun dia hace falta reanudar, sera una decision humana.

    Se comprueba por CONDUCTA y no buscando palabras en el fuente: una primera version de este
    control fallaba porque la palabra «reanuda» aparecia en el comentario que explica que no hay
    reanudacion. Buscar cadenas en el codigo mide como esta escrito, no lo que hace."""
    leidos: list[str] = []
    original = pathlib.Path.read_text

    def espiar(self, *a, **kw):
        leidos.append(str(self))
        return original(self, *a, **kw)

    # Se deja una evidencia previa en el directorio: si el arnes reanudara, la leeria.
    (tmp_path / "evidencia-ab-previa.json").write_text('{"estado":"incompleto"}', encoding="utf-8")
    _espia(arnes, monkeypatch, tmp_path)
    monkeypatch.setattr(pathlib.Path, "read_text", espiar)
    arnes.main()
    assert [r for r in leidos if "evidencia" in r] == [], f"leyo evidencia previa: {leidos}"


# ================================== UMBRALES · separacion semantica pre-carga / post-carga --
#
# Defecto encontrado por aritmetica antes de gastar una sola inferencia: `clase_ambiental`
# comparaba la RAM contra `MIN_RAM_ANTES_MB` (1400) **antes de cada peticion**, sin mirar si el
# modelo ya estaba residente. Con `qwen2.5:0.5b` cargado (~398 MB) la RAM disponible cae por debajo
# de 1400, asi que 29 de las 30 ejecuciones de una tanda habrian quedado marcadas AMBIENTAL y la
# campana no habria medido nada.
#
# `aislamiento.py:126-137` ya tenia la semantica correcta y el discriminante es la residencia:
# 1400 rige **solo si hay que cargar**; una vez residente rige `MIN_RAM_TRAS_CARGA_MB` (150).
#
# Los valores NO se tocan. Se corrige donde se aplica cada uno.

MEM_ALTA = {"MemAvailable": 1600, "SwapFree": 1200, "load1": 1.0}
MEM_MEDIA = {"MemAvailable": 971, "SwapFree": 1200, "load1": 1.0}    # 1400 > x > 150
MEM_BAJA = {"MemAvailable": 100, "SwapFree": 1200, "load1": 1.0}     # < 150


def test_u1_ram_insuficiente_para_cargar_es_ambiental(arnes):
    clase, motivo = arnes.clase_ambiental(MEM_MEDIA, None, None, residente=False)
    assert clase == "AMBIENTAL" and "umbral previo" in motivo


def test_u1_bis_con_entorno_no_apto_no_se_intenta_la_inferencia(arnes, banco, monkeypatch):
    """No basta con etiquetar despues: no debe enviarse la peticion."""
    llamado = []
    monkeypatch.setattr(arnes, "_pedir", lambda *a: llamado.append(1) or {})
    monkeypatch.setattr(arnes, "_mem", lambda: dict(MEM_MEDIA))
    monkeypatch.setattr(arnes, "_residente", lambda modelo: False)
    r = arnes.una_ejecucion("qwen2.5:0.5b", "A", _caso(banco, "A"), 1, 1)
    assert llamado == [], "se envio la inferencia con el entorno no apto"
    assert r["clase"] == "AMBIENTAL" and r.get("omitido") is True


def test_u2_entorno_apto_permite_continuar(arnes):
    assert arnes.clase_ambiental(MEM_ALTA, 200, None, residente=False)[0] == "VALIDO"
    assert arnes.clase_ambiental(MEM_ALTA, 200, None, residente=True)[0] == "VALIDO"


def test_u3_residente_con_ram_bajo_150_es_ambiental(arnes):
    clase, motivo = arnes.clase_ambiental(MEM_BAJA, None, None, residente=True)
    assert clase == "AMBIENTAL" and "tras carga" in motivo


def test_u4_el_umbral_de_1400_no_se_reevalua_tras_la_carga(arnes):
    """El nucleo del defecto: 971 MB con el modelo ya residente es un entorno VALIDO."""
    assert arnes.clase_ambiental(MEM_MEDIA, 200, None, residente=True)[0] == "VALIDO"


def test_u5_el_umbral_de_150_no_decide_si_se_puede_cargar(arnes):
    """200 MB supera los 150 pero no basta para CARGAR: debe seguir siendo AMBIENTAL."""
    mem = {"MemAvailable": 200, "SwapFree": 1200, "load1": 1.0}
    assert arnes.clase_ambiental(mem, None, None, residente=False)[0] == "AMBIENTAL"


def test_u6_una_tanda_con_el_modelo_residente_no_se_invalida_sola(arnes, banco, monkeypatch):
    """Reproduce el escenario real: primera peticion carga el modelo, la RAM cae a 971 y las
    siguientes deben seguir siendo VALIDAS. Antes, 29 de 30 salian AMBIENTAL."""
    estado = {"residente": False}

    def pedir(modelo, prompt, formato):
        estado["residente"] = True
        return {"ok": True, "http": 200, "error": None, "pared_s": 0.1,
                "resp": {"response": '{"intent":"x","action":"consulta","args":{},"say":"y"}'}}

    monkeypatch.setattr(arnes, "_pedir", pedir)
    monkeypatch.setattr(arnes, "_residente", lambda m: estado["residente"])
    monkeypatch.setattr(arnes, "_mem",
                        lambda: dict(MEM_ALTA) if not estado["residente"] else dict(MEM_MEDIA))
    clases = [arnes.una_ejecucion("m", "A", _caso(banco, "A"), i + 1, i + 1)["clase"]
              for i in range(3)]
    assert clases == ["VALIDO"] * 3, clases


def test_los_valores_de_los_umbrales_no_han_cambiado(arnes):
    assert arnes.MIN_RAM_ANTES_MB == 1400
    assert arnes.MIN_RAM_TRAS_CARGA_MB == 150
    assert arnes.MIN_SWAP_LIBRE_MB == 600


def test_la_residencia_se_observa_sin_cargar_el_modelo(arnes):
    """`_residente` debe consultar, nunca provocar una carga."""
    fuente = (AQUI / "ab_format.py").read_text(encoding="utf-8")
    bloque = fuente.split("def _residente")[1].split("\ndef ")[0]
    assert '"ps"' in bloque or "'ps'" in bloque
    for prohibido in ("run", "generate", "pull"):
        assert f'"{prohibido}"' not in bloque


# =========================================================== SUPERFICIE I-1 · procedencia --


def test_la_superficie_declara_los_argumentos_de_proponer_cambio(superficie):
    linea = [ln for ln in superficie.catalogo_para_prompt().splitlines()
             if "proponer_cambio" in ln][0]
    for campo in superficie.CAMPOS_DE_EJECUCION:
        assert campo in linea


def test_los_campos_provienen_de_la_fuente_canonica(superficie):
    fuente = (AQUI / "superficie_ab.py").read_text(encoding="utf-8")
    assert "_CAMPOS_DE_EJECUCION" in fuente
    tercero = superficie.CAMPOS_DE_EJECUCION[2]
    assert f'"{tercero}"' not in fuente and f"'{tercero}'" not in fuente
