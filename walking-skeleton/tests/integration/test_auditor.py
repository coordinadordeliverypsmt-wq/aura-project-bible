"""Integracion: el Auditor detecta garantias declaradas que ya no protegen nada.

Es una forma silenciosa del patron declarado != real: el mutante figura en el TOML, el arnes lo
reporta NO_APLICADO —no como superviviente— y un informe puede decir "todos detectados" mientras la
garantia se quedo sin red. Ocurrio CUATRO veces en la sesion del 2026-08-03/04.
"""

from pathlib import Path

import pytest

from aura_skeleton.adapters.auditor import EjecutorAuditor, auditar_garantias

_RAIZ = str(Path(__file__).resolve().parents[2])


def _repo(tmp_path, buscar, sustituir="X", contenido="alfa\nbeta\n"):
    (tmp_path / "mutaciones").mkdir()
    (tmp_path / "m.py").write_text(contenido, encoding="utf-8")
    (tmp_path / "mutaciones" / "t.toml").write_text(
        f'incremento = "t"\npruebas = []\n\n[[mutante]]\nid = "M1"\ngarantia = "g"\n'
        f'fichero = "m.py"\nbuscar = """{buscar}"""\nsustituir = """{sustituir}"""\n',
        encoding="utf-8",
    )
    return str(tmp_path)


def test_detecta_un_patron_que_ya_no_aparece(tmp_path):
    """El caso que ocurrio cuatro veces: un reformateo invalida el patron."""
    r = auditar_garantias(_repo(tmp_path, "patron que no existe"))
    assert r["ok"] is False and r["rotas"][0]["problema"] == "AUSENTE"


def test_detecta_un_patron_AMBIGUO(tmp_path):
    """Con el patron repetido se mutaria la PRIMERA aparicion, que puede ser un comentario."""
    r = auditar_garantias(_repo(tmp_path, "alfa", contenido="alfa\nalfa\n"))
    assert r["rotas"][0]["problema"] == "AMBIGUO"


def test_detecta_un_mutante_DEGENERADO(tmp_path):
    """`buscar` == `sustituir` no degrada nada: su 'detectado' no informaria de ninguna garantia."""
    r = auditar_garantias(_repo(tmp_path, "alfa", sustituir="alfa"))
    assert r["rotas"][0]["problema"] == "DEGENERADO"


def test_CONTROL_un_mutante_sano_no_se_reporta(tmp_path):
    """Sin este control, todo lo anterior pasaria con un auditor que lo marca todo como roto."""
    r = auditar_garantias(_repo(tmp_path, "alfa"))
    assert r["ok"] is True and r["rotas"] == [] and r["declaradas"] == 1


def test_audita_el_repositorio_real_sin_romperse():
    """Debe funcionar sobre las 100+ garantias reales, no solo sobre un repo de juguete."""
    r = auditar_garantias(_RAIZ)
    assert r["declaradas"] > 50, f"solo encontro {r['declaradas']} garantias declaradas"
    assert isinstance(r["ok"], bool)


@pytest.mark.asyncio
async def test_la_superficie_del_ejecutor_es_cerrada(tmp_path):
    a = EjecutorAuditor(raiz=_repo(tmp_path, "alfa"))
    assert a.capabilities == ["auditar_garantias"]
    with pytest.raises(ValueError):
        await a.execute("ejecutar_comando", {}, "t", "e")
