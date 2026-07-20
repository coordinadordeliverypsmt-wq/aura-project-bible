"""M2.2 — Evidencias de las dos condiciones de arquitectura del CEO.

C1: el adaptador no puede ejecutar nada sin pasar por `operaciones.validar()`.
C2: proteccion TOCTOU en operaciones destructivas.
"""

import os

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.core.operaciones import ErrorDeValidacion

CASOS = [
    ("listar_directorio", lambda p: {"ruta": str(p)}),
    ("leer_archivo", lambda p: {"ruta": str(p / "a.txt")}),
    ("buscar_archivo", lambda p: {"patron": "*.txt", "raiz": str(p)}),
    ("escribir_archivo", lambda p: {"ruta": str(p / "nuevo.txt"), "contenido": "x"}),
    ("borrar_archivo", lambda p: {"ruta": str(p / "a.txt")}),
    ("mover_archivo", lambda p: {"origen": str(p / "a.txt"), "destino": str(p / "b.txt")}),
]


@pytest.fixture
def entorno(tmp_path):
    (tmp_path / "a.txt").write_text("contenido original")
    return tmp_path, AdaptadorComputador(raices=(str(tmp_path),))


# ---------------------------------------------------------------- C1 --------


@pytest.mark.parametrize("accion,mk", CASOS)
@pytest.mark.asyncio
async def test_ninguna_operacion_se_ejecuta_si_validar_falla(accion, mk, entorno, monkeypatch):
    """C1: si la validacion rechaza, NADA alcanza el sistema de archivos.

    Se sustituye `validar` por una version que siempre lanza. Si existiera cualquier ruta
    alternativa dentro del adaptador, alguna de estas operaciones dejaria rastro y el estado
    del directorio cambiaria. Se comprueba que no cambia.
    """
    ruta, ad = entorno
    antes = sorted(os.listdir(ruta)), (ruta / "a.txt").read_text()

    def rechaza(*_a, **_k):
        raise ErrorDeValidacion("rechazo forzado por la prueba")

    monkeypatch.setattr("aura_skeleton.adapters.computador.validar", rechaza)
    with pytest.raises(ErrorDeValidacion):
        await ad.execute(accion, mk(ruta), "t", f"e-{accion}")

    assert (sorted(os.listdir(ruta)), (ruta / "a.txt").read_text()) == antes, "hubo efecto pese al rechazo"


@pytest.mark.asyncio
async def test_operacion_fuera_del_catalogo_no_llega_al_disco(entorno):
    """C1: el adaptador no expone ninguna via para ejecucion arbitraria (RN-2)."""
    ruta, ad = entorno
    with pytest.raises(ErrorDeValidacion, match="fuera del catalogo"):
        await ad.execute("ejecutar_comando", {"cmd": "rm -rf ~"}, "t", "e1")


# ---------------------------------------------------------------- C2 --------


@pytest.mark.asyncio
async def test_toctou_enlace_creado_justo_despues_de_validar(tmp_path, monkeypatch):
    """C2: el caso real de TOCTOU, hecho determinista.

    El saboteador actua EXACTAMENTE entre la comprobacion y el uso: se envuelve `validar` para
    que, tras validar correctamente, sustituya el objetivo por un enlace a un archivo externo.
    Sin proteccion, el borrado seguiria el enlace y destruiria el archivo de fuera.
    """
    from aura_skeleton.core import operaciones

    raiz = tmp_path / "ambito"
    raiz.mkdir()
    victima = raiz / "objetivo.txt"
    victima.write_text("datos")
    externo = tmp_path / "IMPORTANTE.txt"
    externo.write_text("no debe borrarse")

    original = operaciones.validar

    def validar_y_sabotear(accion, args, raices=None):
        seguros = original(accion, args, raices)
        victima.unlink()
        os.symlink(externo, victima)  # <-- la carrera
        return seguros

    monkeypatch.setattr("aura_skeleton.adapters.computador.validar", validar_y_sabotear)
    ad = AdaptadorComputador(raices=(str(raiz),))

    with pytest.raises(ErrorDeValidacion, match="enlace simbolico"):
        await ad.execute("borrar_archivo", {"ruta": str(victima)}, "t", "e1")

    assert externo.exists(), "TOCTOU: se borro el archivo externo siguiendo el enlace"
    assert externo.read_text() == "no debe borrarse"


@pytest.mark.asyncio
async def test_toctou_escritura_no_sigue_enlace(tmp_path, monkeypatch):
    """C2: escribir tampoco puede desviarse a un enlace creado tras la validacion."""
    from aura_skeleton.core import operaciones

    raiz = tmp_path / "ambito"
    raiz.mkdir()
    destino = raiz / "salida.txt"
    externo = tmp_path / "IMPORTANTE.txt"
    externo.write_text("intacto")

    original = operaciones.validar

    def validar_y_sabotear(accion, args, raices=None):
        seguros = original(accion, args, raices)
        os.symlink(externo, destino)
        return seguros

    monkeypatch.setattr("aura_skeleton.adapters.computador.validar", validar_y_sabotear)
    ad = AdaptadorComputador(raices=(str(raiz),))

    with pytest.raises(ErrorDeValidacion, match="enlace simbolico"):
        await ad.execute("escribir_archivo", {"ruta": str(destino), "contenido": "SOBRESCRITO"}, "t", "e1")

    assert externo.read_text() == "intacto"


@pytest.mark.asyncio
async def test_enlace_hacia_fuera_lo_rechaza_la_validacion(tmp_path):
    """Defensa en profundidad, capa 1: un enlace que apunta FUERA lo para `validar` por ambito."""
    raiz = tmp_path / "ambito"
    raiz.mkdir()
    externo = tmp_path / "externo.txt"
    externo.write_text("dato")
    enlace = raiz / "enlace.txt"
    os.symlink(externo, enlace)

    ad = AdaptadorComputador(raices=(str(raiz),))
    with pytest.raises(ErrorDeValidacion, match="fuera del ambito"):
        await ad.execute("borrar_archivo", {"ruta": str(enlace)}, "t", "e1")
    assert externo.exists()


@pytest.mark.asyncio
async def test_enlace_hacia_dentro_lo_rechaza_el_adaptador(tmp_path):
    """Capa 2: un enlace que apunta DENTRO del ambito pasa la validacion de ruta —su destino es
    legitimo— y debe pararlo el adaptador. Sin `_exigir_no_enlace`, borrar el enlace destruiria
    el archivo real al que apunta."""
    raiz = tmp_path / "ambito"
    raiz.mkdir()
    real = raiz / "real.txt"
    real.write_text("dato importante")
    enlace = raiz / "enlace.txt"
    os.symlink(real, enlace)

    ad = AdaptadorComputador(raices=(str(raiz),))
    with pytest.raises(ErrorDeValidacion, match="enlace simbolico"):
        await ad.execute("borrar_archivo", {"ruta": str(enlace)}, "t", "e1")
    assert real.exists() and real.read_text() == "dato importante"


@pytest.mark.asyncio
async def test_mover_no_sobrescribe_destino_existente(entorno):
    """Sobrescribir en un 'mover' perderia el destino en silencio (D32, maxima seguridad)."""
    ruta, ad = entorno
    (ruta / "b.txt").write_text("no perder")
    with pytest.raises(ErrorDeValidacion, match="ya existe"):
        await ad.execute("mover_archivo", {"origen": str(ruta / "a.txt"), "destino": str(ruta / "b.txt")}, "t", "e1")
    assert (ruta / "b.txt").read_text() == "no perder"


# ------------------------------------------------------- CONTROL ------------


@pytest.mark.asyncio
async def test_operaciones_legitimas_si_funcionan(entorno):
    """CONTROL imprescindible: sin esto, un adaptador que rechazara TODO daria PASS arriba."""
    ruta, ad = entorno

    r = await ad.execute("leer_archivo", {"ruta": str(ruta / "a.txt")}, "t", "e1")
    assert r["contenido"] == "contenido original"

    r = await ad.execute("escribir_archivo", {"ruta": str(ruta / "n.txt"), "contenido": "hola"}, "t", "e2")
    assert (ruta / "n.txt").read_text() == "hola"

    r = await ad.execute("mover_archivo", {"origen": str(ruta / "n.txt"), "destino": str(ruta / "m.txt")}, "t", "e3")
    assert (ruta / "m.txt").exists() and not (ruta / "n.txt").exists()

    r = await ad.execute("borrar_archivo", {"ruta": str(ruta / "m.txt")}, "t", "e4")
    assert not (ruta / "m.txt").exists()


@pytest.mark.asyncio
async def test_idempotencia_mismo_evento_no_borra_dos_veces(entorno):
    """Un evento reentregado no puede producir dos efectos reales (3.3 §3)."""
    ruta, ad = entorno
    await ad.execute("borrar_archivo", {"ruta": str(ruta / "a.txt")}, "t", "MISMO")
    (ruta / "a.txt").write_text("recreado por el usuario")
    r = await ad.execute("borrar_archivo", {"ruta": str(ruta / "a.txt")}, "t", "MISMO")
    assert r["status"] == "duplicate"
    assert (ruta / "a.txt").exists(), "el reintento borro un archivo que el usuario habia recreado"
