"""Integracion: AURORA cambia su propio codigo CON RED, no a ciegas.

Un cambio solo se conserva si la verificacion lo respalda; si falla, el fichero vuelve byte a byte.
"""

import asyncio

import pytest

from aura_skeleton.adapters.programador import EjecutorProgramador


class Verificador:
    def __init__(self, ok=True):
        self.ok, self.veces = ok, 0

    async def execute(self, cap, args, tid, eid):
        self.veces += 1
        return {"capacidad": cap, "ok": self.ok, "resumen": "1 passed" if self.ok else "1 failed"}


def _entorno(tmp_path, ok=True):
    (tmp_path / "m.py").write_text("VALOR = 1\n", encoding="utf-8")
    v = Verificador(ok)
    return EjecutorProgramador(str(tmp_path), v), v, tmp_path / "m.py"


def test_un_cambio_VERIFICADO_se_conserva(tmp_path):
    prog, v, f = _entorno(tmp_path, ok=True)
    r = asyncio.run(
        prog.execute("proponer_cambio", {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = 2"}, "t", "e")
    )
    assert r["aplicado"] is True and r["verificado"] is True
    assert f.read_text(encoding="utf-8") == "VALOR = 2\n", "el cambio verificado debe conservarse"
    assert v.veces == 1, "debe verificarse exactamente una vez"


def test_un_cambio_NO_VERIFICADO_se_revierte_byte_a_byte(tmp_path):
    """LA GARANTIA: la verificacion en rojo deshace el cambio. Sin esto seria escribir a ciegas."""
    prog, _, f = _entorno(tmp_path, ok=False)
    original = f.read_bytes()

    r = asyncio.run(
        prog.execute(
            "proponer_cambio", {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = ROTO"}, "t", "e"
        )
    )

    assert r["aplicado"] is False and "revertido" in r["motivo"]
    assert f.read_bytes() == original, "el fichero debe volver EXACTAMENTE a su estado anterior"


def test_un_patron_ambiguo_se_RECHAZA_en_vez_de_adivinar(tmp_path):
    """Misma regla que el arnes de mutacion: con el patron repetido se cambiaria la primera aparicion."""
    (tmp_path / "m.py").write_text("x = 1\ny = 1\n", encoding="utf-8")
    prog = EjecutorProgramador(str(tmp_path), Verificador())

    r = asyncio.run(prog.execute("proponer_cambio", {"fichero": "m.py", "buscar": "1", "sustituir": "9"}, "t", "e"))

    assert r["aplicado"] is False and "veces" in r["motivo"]
    assert (tmp_path / "m.py").read_text(encoding="utf-8") == "x = 1\ny = 1\n", "no puede haberse tocado"


def test_no_se_puede_escapar_del_arbol_de_trabajo(tmp_path):
    """Contencion de ruta: un cambio no puede alcanzar ficheros fuera del arbol declarado.

    El fichero de fuera EXISTE a proposito: si no existiera, la peticion se rechazaria por "no
    existe" y la prueba pasaria sin ejercitar la contencion. Lo detecto la mutacion (M3 sobrevivia).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "m.py").write_text("VALOR = 1\n", encoding="utf-8")
    fuera = tmp_path / "fuera.py"
    fuera.write_text("SECRETO = 1\n", encoding="utf-8")
    prog = EjecutorProgramador(str(repo), Verificador())

    r = asyncio.run(
        prog.execute(
            "proponer_cambio", {"fichero": "../fuera.py", "buscar": "SECRETO = 1", "sustituir": "SECRETO = 2"}, "t", "e"
        )
    )

    assert r["aplicado"] is False, "un cambio no puede alcanzar ficheros fuera del arbol"
    assert fuera.read_text(encoding="utf-8") == "SECRETO = 1\n", "el fichero de fuera fue modificado"


def test_se_rechaza_un_cambio_degenerado(tmp_path):
    prog, v, _ = _entorno(tmp_path)
    r = asyncio.run(prog.execute("proponer_cambio", {"fichero": "m.py", "buscar": "x", "sustituir": "x"}, "t", "e"))
    assert r["aplicado"] is False and "degenerado" in r["motivo"]
    assert v.veces == 0, "un cambio que no cambia nada no debe consumir una verificacion"


# ------------------------------------------- UN CAMBIO SIN SUSTITUTO NO ES UN CAMBIO: ES UN BORRADO --
#
# La tercera auditoria independiente lo midio sobre el sistema real: `fichero` + `buscar` SIN
# `sustituir` daba `viable: True` con efecto "sustituir 1 aparicion ... y verificar", y lo que hacia
# era BORRAR el patron del disco. El QA daba verde -quitar una guarda no rompe pruebas- y el cambio se
# CONSERVABA.
#
# Dos garantias distintas caen ahi, y por eso van dos pruebas:
#   1. El efecto: se destruye codigo que nadie pidio destruir.
#   2. El CONSENTIMIENTO (ADR-0003): al CEO se le enseñaba "sustituir" y se ejecutaba un borrado. Una
#      confirmacion humana sobre una previsualizacion falsa no es una confirmacion.
#
# La regla ya existia un piso mas arriba -el todo-o-nada del contexto derivado-, pero vivia solo en el
# carril derivado: cualquier otra ruta hacia el ejecutor la esquivaba. Aqui se aplica donde de verdad
# se toca el disco.


@pytest.mark.parametrize("sustituir", [None, "", "   ", "\n\t "])
def test_un_cambio_sin_sustituto_real_se_RECHAZA_en_vez_de_borrar(tmp_path, sustituir):
    """Los blancos van aparte de la ausencia: `sustituir = "   "` es un valor PRESENTE y VERDADERO, y
    una guarda escrita con veracidad a secas lo dejaria pasar. Ya ocurrio un piso mas arriba."""
    prog, v, f = _entorno(tmp_path)
    original = f.read_bytes()
    args = {"fichero": "m.py", "buscar": "VALOR = 1"}
    if sustituir is not None:
        args["sustituir"] = sustituir

    previo = asyncio.run(prog.simular("proponer_cambio", args, "t"))
    r = asyncio.run(prog.execute("proponer_cambio", args, "t", "e"))

    assert previo["viable"] is False, f"el dry-run avalo un borrado encubierto: {previo}"
    assert r["aplicado"] is False, "se aplico un cambio sin sustituto: eso es un borrado"
    assert f.read_bytes() == original, "el patron fue BORRADO del disco"
    assert v.veces == 0, "un cambio inadmisible no debe consumir una verificacion"


@pytest.mark.parametrize(
    "sustituto",
    [
        pytest.param(["x"], id="lista"),
        pytest.param(3, id="numero"),
        pytest.param({"a": 1}, id="dict"),
        pytest.param(True, id="bool"),
        # UNA POR CATEGORÍA UNICODE, no tres del mismo tipo. La versión anterior de esta lista traía
        # ZWSP, guion blando y ZWJ — los tres `Cf` — disfrazados de tres casos distintos, y por eso
        # la quinta auditoría encontró cinco puntos de código más que pasaban. Cada `pytest.param`
        # nombra su categoría para que ampliar la regla obligue a ampliar esta lista.
        pytest.param("​", id="Cf-ZWSP"),
        pytest.param("\x00", id="Cc-NUL"),
        pytest.param("️", id="Mn-variation-selector"),
        pytest.param("́", id="Mn-combinante"),
        pytest.param("\U000e0000", id="Cn-no-asignado"),
        pytest.param("\ud800", id="Cs-surrogate"),
        pytest.param(" ", id="Zs-espacio-fino"),
    ],
)
def test_un_sustituto_inservible_se_RECHAZA_aunque_parezca_texto(tmp_path, sustituto):
    """LA CUARTA AUDITORÍA, dos huecos que la corrección anterior dejó abiertos por aplicar aquí la
    lección del caso BLANCO y no la del caso TIPO.

    - Un valor no textual pasaba porque `_campos` hacía `str()` ANTES de validar: `str(["x"])` es un
      texto perfectamente válido. Medido: el fichero quedaba con `['x']` dentro, con el QA en verde.
    - `.strip()` sólo quita lo que `isspace()` reconoce. Un ZWSP o un guion blando lo atraviesan, y
      sustituir una guarda por un carácter de anchura cero es INDISTINGUIBLE de borrarla — en el
      fichero y en el diff — con la misma previsualización de siempre.
    """
    prog, v, f = _entorno(tmp_path)
    original = f.read_bytes()
    args = {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": sustituto}

    previo = asyncio.run(prog.simular("proponer_cambio", args, "t"))
    r = asyncio.run(prog.execute("proponer_cambio", args, "t", "e"))

    assert previo["viable"] is False, f"el dry-run avaló un sustituto inservible: {previo}"
    assert r["aplicado"] is False
    assert f.read_bytes() == original, f"el fichero fue alterado con {sustituto!r}"
    assert v.veces == 0


def test_un_patron_o_fichero_que_no_son_texto_se_RECHAZAN(tmp_path):
    """Mismo hueco por los otros dos argumentos. Sin la comprobación de tipo, `str()` los convertía y
    el ejecutor buscaba el `repr` de una lista dentro del fichero."""
    prog, _, f = _entorno(tmp_path)
    original = f.read_bytes()

    for args in (
        {"fichero": ["m.py"], "buscar": "VALOR = 1", "sustituir": "VALOR = 2"},
        {"fichero": "m.py", "buscar": ["VALOR = 1"], "sustituir": "VALOR = 2"},
    ):
        r = asyncio.run(prog.execute("proponer_cambio", args, "t", "e"))
        assert r["aplicado"] is False, f"un argumento no textual fue aceptado: {args}"

    assert f.read_bytes() == original


def test_la_contencion_de_ruta_no_depende_del_nombre_del_directorio_vecino(tmp_path):
    """LA CUARTA AUDITORÍA, hallazgo preexistente. `startswith` sobre la ruta desnuda comparaba
    prefijos de TEXTO: con la raíz en `.../x`, un `../xyz/secreto.py` resolvía a `.../xyz/secreto.py`,
    que empieza por `.../x` y pasaba la contención. Medido: el cambio se aplicó y se CONSERVÓ fuera
    del árbol declarado.

    `test_no_se_puede_escapar_del_arbol_de_trabajo` no lo cubría porque usa `tmp_path.parent`, cuyo
    nombre no comparte prefijo con la raíz. El caso hay que construirlo a propósito.
    """
    raiz = tmp_path / "x"
    raiz.mkdir()
    (raiz / "m.py").write_text("VALOR = 1\n", encoding="utf-8")
    vecino = tmp_path / "xyz"
    vecino.mkdir()
    secreto = vecino / "secreto.py"
    secreto.write_text("CLAVE = 'intacta'\n", encoding="utf-8")
    prog = EjecutorProgramador(str(raiz), Verificador())

    args = {"fichero": "../xyz/secreto.py", "buscar": "intacta", "sustituir": "TOCADO"}
    previo = asyncio.run(prog.simular("proponer_cambio", args, "t"))
    r = asyncio.run(prog.execute("proponer_cambio", args, "t", "e"))

    assert previo["viable"] is False, "el dry-run avaló un cambio fuera del árbol"
    assert r["aplicado"] is False
    assert secreto.read_text(encoding="utf-8") == "CLAVE = 'intacta'\n", "se escribió fuera del árbol declarado"


@pytest.mark.parametrize("invisible", ["ㅤ", "⠀"])
def test_lo_que_la_regla_no_puede_ver_lo_ve_EL_HUMANO_en_la_previsualizacion(tmp_path, invisible):
    """LA GARANTÍA QUE SOSTIENE A LAS DEMÁS, y la razón de que la guarda pueda ser incompleta.

    `texto_utilizable` rechaza las categorías que nunca se ven solas, pero **no detecta «invisible»**:
    U+3164 (relleno hangul, `Lo`) y U+2800 (braille en blanco, `So`) son signos legítimos en
    categorías ordinarias que se pintan VACÍOS. Ninguna regla categórica los separa de una letra, y
    cada auditoría encontraba dos o tres puntos de código más que la anterior: ampliar la lista es una
    carrera que se pierde.

    Lo que sí es completo y enunciable: **en la previsualización no cabe nada que no se vea.** Con
    `ascii()`, el invisible aparece delante de quien autoriza como `'\\u3164'`, y la decisión es suya
    e informada — que es lo que ADR-0003 pide de verdad.

    `repr()` NO sirve aquí, y se probó: Python sólo escapa lo que considera no imprimible, y U+3164
    lo es. La previsualización mostraba el invisible... invisible.
    """
    prog, _, _ = _entorno(tmp_path)
    args = {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": invisible}

    efecto = asyncio.run(prog.simular("proponer_cambio", args, "t"))["efecto"]

    assert invisible not in efecto, f"el carácter invisible se coló crudo en la previsualización: {efecto!r}"
    assert f"\\u{ord(invisible):04x}" in efecto, f"la previsualización no lo delata: {efecto!r}"


def test_la_previsualizacion_dice_QUE_se_sustituye_y_POR_QUE(tmp_path):
    """Decía sólo «sustituir 1 aparicion en m.py»: cierto y sin informar de nada. Con ese texto
    delante, en cuatro auditorías seguidas se aprobaron borrados encubiertos y sustituciones por
    caracteres invisibles, todos indistinguibles entre sí y de un cambio legítimo."""
    prog, _, _ = _entorno(tmp_path)
    args = {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = 2"}

    efecto = asyncio.run(prog.simular("proponer_cambio", args, "t"))["efecto"]

    assert "VALOR = 1" in efecto and "VALOR = 2" in efecto, f"no dice qué se sustituye ni por qué: {efecto!r}"
    assert "m.py" in efecto


def test_la_previsualizacion_es_ascii_pura(tmp_path):
    """La regla completa, enunciada como aserción: si algo no es ASCII imprimible, va escapado. Sin
    esto, «se ve» depende de la fuente del terminal de quien confirma."""
    prog, _, _ = _entorno(tmp_path)
    args = {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "contraseña válida ㅤ"}

    efecto = asyncio.run(prog.simular("proponer_cambio", args, "t"))["efecto"]

    assert efecto.isascii(), f"la previsualización trae caracteres que pueden no verse: {efecto!r}"


def test_un_arbol_alcanzado_por_un_enlace_simbolico_sigue_siendo_el_arbol(tmp_path):
    """MUTANTE VIVO C31, y es la mitad que faltaba de la contención: endurecerla no puede convertir un
    árbol legítimo en inalcanzable.

    La raíz llega como cadena y nadie garantiza que venga resuelta — un `~/proyecto` que es enlace, o
    `/tmp` en macOS. Sin resolverla antes de comparar, el fichero resuelto (`.../real/m.py`) no es
    relativo a la raíz sin resolver (`.../enlace`) y TODO cambio legítimo se rechaza por «fuera del
    árbol». Falla cerrado, pero deja la capacidad muerta sin que nada lo diga.
    """
    real = tmp_path / "real"
    real.mkdir()
    (real / "m.py").write_text("VALOR = 1\n", encoding="utf-8")
    enlace = tmp_path / "enlace"
    enlace.symlink_to(real, target_is_directory=True)
    prog = EjecutorProgramador(str(enlace), Verificador())

    args = {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = 2"}
    previo = asyncio.run(prog.simular("proponer_cambio", args, "t"))
    r = asyncio.run(prog.execute("proponer_cambio", args, "t", "e"))

    assert previo["viable"] is True, f"un árbol alcanzado por enlace quedó inalcanzable: {previo}"
    assert r["aplicado"] is True
    assert (real / "m.py").read_text(encoding="utf-8") == "VALOR = 2\n"


def test_la_previsualizacion_no_puede_prometer_algo_distinto_de_lo_que_ocurre(tmp_path):
    """CONTROL del par anterior. Sin esto, "rechazar sin sustituto" se cumpliria rechazandolo todo, y
    la capacidad de cambiar codigo -que es el incremento entero- quedaria anulada en silencio.

    Ademas fija lo que exige ADR-0003: lo que se le enseña al humano describe lo que va a pasar.
    """
    prog, v, f = _entorno(tmp_path)
    args = {"fichero": "m.py", "buscar": "VALOR = 1", "sustituir": "VALOR = 2"}

    previo = asyncio.run(prog.simular("proponer_cambio", args, "t"))
    asyncio.run(prog.execute("proponer_cambio", args, "t", "e"))

    assert previo["viable"] is True, "un cambio completo y legitimo debe seguir siendo viable"
    assert f.read_text(encoding="utf-8") == "VALOR = 2\n"
    assert v.veces == 1


def test_la_superficie_es_cerrada(tmp_path):
    prog, _, _ = _entorno(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(prog.execute("escribir_archivo", {}, "t", "e"))


def test_proponer_cambio_es_lista_ROJA():
    """Altera el arbol: exige confirmacion humana. Reversible no es lo mismo que inocuo."""
    from aura_skeleton.core.permissions import CATALOGO

    assert CATALOGO["proponer_cambio"]["lista"] == "roja"
