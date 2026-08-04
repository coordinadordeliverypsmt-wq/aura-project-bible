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


def test_la_superficie_es_cerrada(tmp_path):
    prog, _, _ = _entorno(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(prog.execute("escribir_archivo", {}, "t", "e"))


def test_proponer_cambio_es_lista_ROJA():
    """Altera el arbol: exige confirmacion humana. Reversible no es lo mismo que inocuo."""
    from aura_skeleton.core.permissions import CATALOGO

    assert CATALOGO["proponer_cambio"]["lista"] == "roja"
