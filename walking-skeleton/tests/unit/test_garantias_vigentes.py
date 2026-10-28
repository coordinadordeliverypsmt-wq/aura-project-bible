"""Anti-regresion: TODA garantia declarada debe seguir aplicandose.

Un mutante cuyo patron ya no coincide figura declarado en el TOML y no protege nada. El arnes lo
reporta NO_APLICADO y NO lo cuenta como superviviente, asi que un informe puede decir "todos
detectados" mientras la garantia se quedo sin red. Ocurrio SEIS veces en la sesion del 2026-08-03/04,
siempre tras un reformateo o un cambio de firma.

Por eso esto es una PRUEBA y no un comando opcional: si una garantia existe, debe comprobarse siempre,
no depender de que alguien recuerde ejecutar el auditor. Mismo criterio que el manifiesto de
arquitectura (D41) y que el verificador del modelo de datos (ADR-0023).
"""

from pathlib import Path

from aura_skeleton.adapters.auditor import auditar_garantias

_RAIZ = str(Path(__file__).resolve().parents[2])


def test_todas_las_garantias_declaradas_siguen_vigentes():
    r = auditar_garantias(_RAIZ)

    assert r["ok"], (
        f"{len(r['rotas'])} de {r['declaradas']} garantias declaradas ya NO protegen nada:\n"
        + "\n".join(f"  · {x['mutante']}: {x['problema']} — {x['detalle']}" for x in r["rotas"])
        + "\n\nAmplia el patron `buscar` hasta que vuelva a coincidir y sea unico."
    )


def test_el_repositorio_declara_un_numero_significativo_de_garantias():
    """CONTROL: la prueba anterior pasaria trivialmente si no hubiera garantias que comprobar."""
    r = auditar_garantias(_RAIZ)
    assert r["declaradas"] >= 100, f"solo {r['declaradas']} garantias declaradas: ¿se perdio algun TOML?"


# ------------------------------------- LA RAIZ DEL CATALOGO (defecto corregido el 2026-09-09) --


def test_el_auditor_resuelve_cada_catalogo_contra_SU_raiz(tmp_path):
    """**583 de 588 «garantías que no protegen nada» eran este defecto, no garantías rotas.**

    Un mutante no vive necesariamente en el plano del producto: el arnés ya lo sabía —acepta
    `--raiz`— pero el auditor resolvía SIEMPRE contra la raíz del producto y daba `AUSENTE` a todo
    lo que viviera en el plano de control, de comunicación o del agente externo. El auditor cuyo
    oficio es cazar «declarado ≠ real» lo estaba cometiendo.

    Esta prueba lo fija por los dos lados, que es lo único que demuestra que la raíz se usa: con
    `raiz` declarada el patrón se encuentra; sin ella, el mismo catálogo da `AUSENTE`.
    """
    otro_plano = tmp_path / "otro-plano"
    otro_plano.mkdir()
    (otro_plano / "modulo.py").write_text("def f():\n    return 'patron vigente'\n", encoding="utf-8")

    raiz = tmp_path / "plano-producto"
    (raiz / "mutaciones").mkdir(parents=True)
    cuerpo = (
        'incremento = "prueba"\n{raiz}'
        'pruebas = ["x"]\n\n'
        '[[mutante]]\nid = "X1"\ngarantia = "g"\nfichero = "modulo.py"\n'
        "buscar = '''    return 'patron vigente''''\n"
        "sustituir = '''    return 'degradado''''\n"
    )
    catalogo = raiz / "mutaciones" / "c.toml"

    catalogo.write_text(cuerpo.format(raiz='raiz = "../otro-plano"\n'), encoding="utf-8")
    con = auditar_garantias(str(raiz))
    assert con["ok"], f"con `raiz` declarada el patrón debía encontrarse: {con['rotas']}"

    catalogo.write_text(cuerpo.format(raiz=""), encoding="utf-8")
    sin = auditar_garantias(str(raiz))
    assert not sin["ok"] and sin["rotas"][0]["problema"] == "AUSENTE", (
        "sin `raiz`, el catálogo debe resolverse contra el producto y dar AUSENTE: "
        "si no, la raíz no se está usando y la prueba de arriba pasaría por casualidad")

    # Y el tercer caso, que el arnés exigió: sin `raiz`, el plano por defecto es EL DEL PRODUCTO.
    # Sin esto, invertir el defecto —hacer que la raíz por defecto fuera otra— sobrevivía: las dos
    # comprobaciones de arriba seguían pasando mientras los 394 mutantes del producto dejaban de
    # resolverse. Un defecto no se corrige cambiando de sitio el mismo error.
    (raiz / "modulo.py").write_text("def f():\n    return 'patron vigente'\n", encoding="utf-8")
    por_defecto = auditar_garantias(str(raiz))
    assert por_defecto["ok"], (
        f"sin `raiz`, el fichero del propio plano del producto tiene que encontrarse: {por_defecto['rotas']}")


def test_todo_catalogo_de_otro_plano_DECLARA_su_raiz():
    """Caso de control del arreglo: la raíz se declara, **no se adivina**.

    Probar raíces hasta que una encaje acertaría casi siempre y mentiría el resto —un homónimo entre
    planos resolvería al fichero equivocado sin avisar—. Así que ningún mutante puede quedar con su
    fichero irresoluble: o vive en el producto, o su catálogo dice dónde vive.
    """
    import tomllib

    sin_raiz = []
    for toml in sorted((Path(_RAIZ) / "mutaciones").glob("*.toml")):
        datos = tomllib.loads(toml.read_text(encoding="utf-8"))
        base = Path(_RAIZ) / str(datos.get("raiz", ""))
        for m in datos.get("mutante", []):
            destino = base / str(m.get("fichero", ""))
            if not destino.is_file():
                sin_raiz.append(f"{toml.name}:{m.get('id')} -> {m.get('fichero')}")
    # Los 5 de `validador.py` son deuda preexistente: el fichero no existe en NINGÚN plano, así que
    # no es un problema de raíz. Se nombran para que este límite sea explícito y no un silencio.
    assert all("validador.py" in x for x in sin_raiz), (
        f"hay catálogos que no declaran su raíz: {[x for x in sin_raiz if 'validador' not in x]}")
