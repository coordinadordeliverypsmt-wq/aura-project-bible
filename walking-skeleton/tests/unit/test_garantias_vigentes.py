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
