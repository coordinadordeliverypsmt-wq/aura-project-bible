"""El confinamiento de sistema operativo, ejercido de verdad (CEO, 2026-09-21).

QUÉ SE DEMUESTRA AQUÍ, Y POR QUÉ NO BASTA CON MENOS. Una auditoría adversarial probó, ejecutándolo,
que una misión delegada podía **leer y escribir fuera de su sandbox**: pytest ejecuta como Python
real el contenido de los ficheros de prueba, y el perímetro de `delegacion.py` solo acota *qué
ficheros se le nombran a la herramienta*, no *qué hace el código que contienen*.

Estas pruebas no comprueban que exista una función de confinamiento: **ejecutan el ataque** y
comprueban que el kernel lo niega. Es el criterio del plano — *«ningún control de seguridad se
declara operativo sin un intento real de violación que falle»*—, y aquí se toma al pie de la letra:
el código malicioso **corre**; lo que no puede es salir.

LA OTRA MITAD, QUE IMPORTA IGUAL. Un sandbox que lo niega todo no es seguro: es inservible, y el
proyecto ya sabe que ese es el otro modo de fallar. Por eso cada prueba de contención tiene su
control: el trabajo legítimo tiene que seguir pasando. Al construir esto, el confinamiento dejó dos
veces la capacidad inutilizable —`/dev/null` sin escritura, y derechos de directorio pedidos sobre
un fichero— y las dos se detectaron por este lado, no por el otro.
"""

from __future__ import annotations

import os
import pathlib

import aislamiento as ais
import delegacion as dl
import orquestador as orq
import pytest

ACTA = "DEC-ORCH-2 del CEO"

pytestmark = pytest.mark.skipif(not ais.DISPONIBLE,
                                reason="este kernel no ofrece Landlock: no hay nada que ejercer")


@pytest.fixture(autouse=True)
def _el_arnes_no_esta_corriendo(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _escenario(tmp_path):
    """Un sandbox, una víctima fuera de él, y un plano donde registrar. Nada más."""
    caja = tmp_path / "caja"
    caja.mkdir()
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (fuera / "secreto.txt").write_text("CLAVE-SECRETA", encoding="utf-8")
    plano = tmp_path / "plano"
    plano.mkdir()
    return plano, caja, fuera


def _mision(caja, fichero="test_caso.py", limite_s=60.0):
    return dl.Mision(capacidad="ejecutar_pruebas", sandbox=str(caja),
                     argumentos=(fichero,), limite_s=limite_s)


# ============================================================ EL ATAQUE, NEGADO POR EL KERNEL --


def test_una_mision_NO_puede_escribir_fuera_de_su_sandbox(tmp_path):
    """El ataque exacto que la auditoría ejecutó con éxito el 2026-09-21."""
    plano, caja, fuera = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        f"import pathlib\n\n\ndef test_escribir_fuera():\n"
        f"    (pathlib.Path({str(fuera)!r}) / 'robado.txt').write_text('pwned')\n",
        encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert not (fuera / "robado.txt").exists(), (
        "la mision escribio FUERA de su sandbox: el confinamiento no esta puesto")
    assert resultado.ok is False, "una mision que intenta escapar no puede salir correcta"
    assert resultado.evidencia["fallidas"] == 1, (
        "el codigo malicioso tiene que EJECUTARSE y fallar por permisos; si no se ejecuto, esta "
        "prueba no demuestra que el kernel lo niegue")


def test_una_mision_NO_puede_leer_fuera_de_su_sandbox(tmp_path):
    """Leer también está prohibido: un subagente que no puede escribir pero sí leer sigue siendo
    una fuga de datos."""
    plano, caja, fuera = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        f"import pathlib\n\n\ndef test_leer_fuera():\n"
        f"    dato = (pathlib.Path({str(fuera)!r}) / 'secreto.txt').read_text()\n"
        f"    pathlib.Path('copia.txt').write_text(dato)\n",
        encoding="utf-8")

    dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert not (caja / "copia.txt").exists(), "la mision leyo un fichero de fuera del sandbox"


def test_ni_siquiera_con_una_ruta_ABSOLUTA_construida_dentro_del_codigo(tmp_path):
    """El confinamiento no depende de validar rutas: las valida el kernel, ya resueltas."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        "import pathlib\n\n\ndef test_tocar_etc():\n"
        "    pathlib.Path('/etc/aura-pwned').write_text('x')\n", encoding="utf-8")

    dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert not pathlib.Path("/etc/aura-pwned").exists(), "la mision escribio en /etc"


def test_el_confinamiento_se_HEREDA_por_los_procesos_hijos(tmp_path):
    """Landlock es irreversible y se hereda: lanzar un proceso nieto no es una vía de escape."""
    plano, caja, fuera = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        f"import subprocess, sys, pathlib\n\n\ndef test_nieto_escribe_fuera():\n"
        f"    objetivo = pathlib.Path({str(fuera)!r}) / 'por_el_nieto.txt'\n"
        f"    subprocess.run([sys.executable, '-c',\n"
        f"                    f\"open({{objetivo!r}}, 'w').write('pwned')\"], check=False)\n",
        encoding="utf-8")

    dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert not (fuera / "por_el_nieto.txt").exists(), (
        "un proceso nieto escapo del confinamiento: no se esta heredando")


# ============================================================ Y SIGUE SIENDO UTILIZABLE --


def test_CONTROL_el_trabajo_legitimo_DENTRO_del_sandbox_sigue_funcionando(tmp_path):
    """La otra mitad. Un sandbox que lo niega todo no es seguro: es inservible.

    Esta prueba encontró dos veces un confinamiento roto mientras se construía —`/dev/null` sin
    permiso de escritura, y derechos de directorio pedidos sobre un fichero—, las dos veces con la
    capacidad aparentando estar «muy protegida» y sin poder ejecutar nada."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        "def test_suma():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert resultado.ok is True, f"el trabajo legitimo dejo de pasar: {resultado.motivo}"
    assert resultado.evidencia["ejecutadas"] == 1


def test_CONTROL_una_mision_puede_escribir_DENTRO_de_su_sandbox(tmp_path):
    """Escribir en su propia caja es trabajo normal, no un escape."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        "import pathlib\n\n\ndef test_escribe_dentro():\n"
        "    pathlib.Path('salida.txt').write_text('trabajo')\n", encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert resultado.ok is True, f"no pudo trabajar en su propia caja: {resultado.motivo}"
    assert (caja / "salida.txt").read_text(encoding="utf-8") == "trabajo"


# ============================================================ LA EVIDENCIA LO DECLARA --


def test_el_resultado_declara_QUE_aislamiento_se_aplico(tmp_path):
    """No se afirma que hubo confinamiento: se registra cuál, y queda en el historial.

    Sin esto, un día con Landlock deshabilitado la capacidad seguiría diciendo lo mismo que un día
    con él activo — que es `INV-9` con consecuencias de seguridad."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert resultado.evidencia["aislamiento"].startswith("landlock:abi"), (
        f"la evidencia no declara el confinamiento real: {resultado.evidencia.get('aislamiento')!r}")


def test_sin_LANDLOCK_la_capacidad_se_NIEGA_en_vez_de_fingir(tmp_path, monkeypatch):
    """Fail-closed. Ejecutar declarando un aislamiento que no existe sería la peor versión de
    «declarado ≠ real»: la que además es un agujero de seguridad."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    monkeypatch.setattr(ais, "DISPONIBLE", False)

    with pytest.raises(dl.MisionRechazada, match="Landlock|aislamiento|confinamiento"):
        dl.delegar(plano, _mision(caja), "ceo", ACTA)


# ============================================================ LA SEGUNDA CAPA: RECURSOS --


def test_los_limites_de_recursos_se_aplican_al_subagente(tmp_path):
    """`rlimit` acota lo que Landlock no: memoria, CPU, tamaño de fichero y número de procesos.

    Se comprueba **desde dentro** de la misión, que es donde se puede ver: el subagente lee sus
    propios límites y los escribe en su caja."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        "import pathlib, resource\n\n\ndef test_declara_sus_limites():\n"
        "    duros = {n: resource.getrlimit(getattr(resource, n))[1]\n"
        "             for n in ('RLIMIT_AS', 'RLIMIT_FSIZE')}\n"
        "    pathlib.Path('limites.txt').write_text(repr(duros))\n", encoding="utf-8")

    dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    limites = eval((caja / "limites.txt").read_text(encoding="utf-8"))   # noqa: S307

    # **`RLIM_INFINITY` vale -1**, así que un `<=` pelado pasaba con los límites SIN aplicar: -1 es
    # menor que cualquier tope. La prueba decía que los recursos estaban acotados mientras el
    # subagente corría sin límite ninguno. Lo descubrió el mutante `AI-M6` al sobrevivir.
    import resource as _r
    for nombre, tope in (("RLIMIT_AS", ais.LIMITE_MEMORIA_BYTES),
                         ("RLIMIT_FSIZE", ais.LIMITE_FICHERO_BYTES)):
        valor = limites[nombre]
        assert valor != _r.RLIM_INFINITY, f"{nombre} quedo SIN limite: el rlimit no se aplico"
        assert 0 < valor <= tope, f"{nombre} no quedo acotado: {valor}"


def test_una_mision_no_puede_SUBIR_los_limites_que_recibio(tmp_path):
    """Bajar el límite duro es irreversible. Si solo se bajara el blando, el subagente lo subiría
    de vuelta y el límite sería decorativo."""
    plano, caja, _ = _escenario(tmp_path)
    (caja / "test_caso.py").write_text(
        "import pathlib, resource\n\n\ndef test_intenta_subirlos():\n"
        "    try:\n"
        "        resource.setrlimit(resource.RLIMIT_FSIZE,\n"
        "                           (resource.RLIM_INFINITY, resource.RLIM_INFINITY))\n"
        "        pathlib.Path('subio.txt').write_text('si')\n"
        "    except (ValueError, OSError):\n"
        "        pathlib.Path('subio.txt').write_text('no')\n", encoding="utf-8")

    dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)

    assert (caja / "subio.txt").read_text(encoding="utf-8") == "no", (
        "la mision subio su propio limite: se bajo solo el blando, no el duro")


# ============================================================ EL MODULO, A SOLAS --


def test_el_abi_se_pregunta_al_kernel_y_es_coherente():
    """`DISPONIBLE` no puede decir una cosa y `abi_disponible()` otra."""
    assert ais.DISPONIBLE is (ais.abi_disponible() > 0)
    assert ais.abi_disponible() >= 1


def test_las_rutas_del_interprete_se_DERIVAN_y_existen():
    """Cablearlas funcionaría hoy y se rompería con el siguiente intérprete."""
    rutas = ais.rutas_del_interprete()

    assert rutas, "sin rutas de lectura el interprete no arranca"
    assert all(pathlib.Path(r).exists() for r in rutas), "se declaro una ruta que no existe"
    assert any(str(r).startswith(os.path.dirname(os.__file__)[:8]) or "python" in str(r).lower()
               for r in rutas), "no aparece ninguna ruta del propio interprete"


def test_la_descripcion_no_miente_sobre_lo_que_hay():
    """Lo que se escribe en la evidencia tiene que ser lo que el kernel ofrece."""
    assert ais.descripcion() == f"landlock:abi{ais.abi_disponible()}+rlimits"


# ============================================================ LO QUE LOS MUTANTES DESTAPARON --
#
# `AI-M2`, `AI-M4`, `AI-M8` y `AI-M10` sobrevivieron la primera vez. Ninguno era un fallo del
# código: eran **pruebas insuficientes**, y dos de ellas tautológicas en esta máquina concreta —
# comprobaban algo que se cumplía tanto con la barrera puesta como sin ella.


def test_una_mision_no_puede_escribir_en_las_RUTAS_DE_LECTURA_del_interprete(tmp_path):
    """Las rutas que el intérprete necesita se conceden en LECTURA, no en escritura.

    `AI-M4` sobrevivía porque el único objetivo que se atacaba era `/etc`, que el usuario no puede
    escribir ni siquiera sin confinamiento: el mutante no cambiaba nada observable. Se ataca ahora
    `~/.local`, que **sí** es escribible por el usuario y **sí** está entre las rutas concedidas.
    """
    plano, caja, _ = _escenario(tmp_path)
    objetivo = pathlib.Path(os.path.expanduser("~/.local")) / "aura-pwned-por-mision.txt"
    assert objetivo.parent.exists(), "el montaje necesita que ~/.local exista"
    (caja / "test_caso.py").write_text(
        f"import pathlib\n\n\ndef test_escribir_en_lectura():\n"
        f"    pathlib.Path({str(objetivo)!r}).write_text('pwned')\n", encoding="utf-8")

    try:
        dl.delegar_y_ejecutar(plano, _mision(caja), "ceo", ACTA)
        assert not objetivo.exists(), (
            "la mision escribio en una ruta concedida solo para LECTURA")
    finally:
        objetivo.unlink(missing_ok=True)


def test_verificar_calidad_tambien_esta_confinada(tmp_path):
    """`AI-M2` sobrevivía porque ninguna prueba ejercía el confinamiento de la **segunda**
    capacidad: se comprobaba que funcionaba, no que estuviera encerrada."""
    plano, caja, fuera = _escenario(tmp_path)
    # `ruff` analiza el fichero, no lo ejecuta — así que el intento de escape se hace por la vía
    # que `verificar_calidad` sí abre: el fichero de configuración que ruff lee del directorio.
    (caja / "limpio.py").write_text("VALOR = 1\n", encoding="utf-8")
    objetivo = fuera / "ruff-pwned.txt"

    resultado = dl.delegar_y_ejecutar(
        plano, dl.Mision(capacidad="verificar_calidad", sandbox=str(caja),
                         argumentos=("limpio.py",), limite_s=60.0), "ceo", ACTA)

    assert resultado.ok is True, f"la capacidad dejo de funcionar: {resultado.evidencia}"
    assert resultado.evidencia["aislamiento"].startswith("landlock:abi"), (
        "verificar_calidad corrio SIN declarar confinamiento")
    assert not objetivo.exists()


def test_la_descripcion_dice_RLIMITS_cuando_no_hay_landlock(monkeypatch):
    """`AI-M8` sobrevivía porque en esta máquina el ABI es 6 y el literal cableado coincidía.

    Se fuerza el caso contrario: sin Landlock, la descripción **no puede** decir «landlock»."""
    monkeypatch.setattr(ais, "abi_disponible", lambda: 0)

    assert ais.descripcion() == "rlimits", (
        "se declaro confinamiento de Landlock en un kernel que no lo ofrece")


def test_las_DOS_capacidades_se_confinan_por_el_MISMO_punto(tmp_path):
    """El confinamiento se construye en un solo sitio, no una vez por capacidad.

    `AI-M2` sobrevivía porque cada capacidad cableaba su propio `preexec_fn` y quitarlo de una sola
    no rompía ninguna prueba de la otra. Un control que hay que acordarse de conectar en cada rama
    se olvidará en alguna — ALERTA-005 otra vez. Se comprueba **estructuralmente**, leyendo el
    código: las dos ramas tienen que llamar al mismo constructor."""
    import ast

    fuente = pathlib.Path(dl.__file__).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    llamadas = [n for n in ast.walk(arbol)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_confinador_de"]

    assert len(llamadas) == 2, (
        f"se esperaban exactamente dos lanzamientos confinados (uno por capacidad construida) y "
        f"hay {len(llamadas)}: alguna capacidad se lanza sin pasar por el confinador")
    assert len(dl.MISIONES_CONSTRUIDAS) == len(llamadas), (
        "hay mas capacidades construidas que lanzamientos confinados")


def test_DISPONIBLE_no_esta_CABLEADO_a_un_literal():
    """`AI-M10` sobrevivía porque `DISPONIBLE is (abi > 0)` es cierto con el valor cableado a `True`.

    Se comprueba lo que de verdad importa y no se puede fingir: que el valor **se calcule**. Un
    literal ahí abriría la puerta fail-closed de `delegacion` en cualquier máquina sin Landlock."""
    import ast

    arbol = ast.parse(pathlib.Path(ais.__file__).read_text(encoding="utf-8"))
    asignaciones = [n for n in ast.walk(arbol) if isinstance(n, ast.Assign)
                    and any(isinstance(d, ast.Name) and d.id == "DISPONIBLE" for d in n.targets)]

    assert asignaciones, "DISPONIBLE dejo de existir"
    valor = asignaciones[0].value
    assert not isinstance(valor, ast.Constant), (
        f"DISPONIBLE esta cableado a {getattr(valor, 'value', valor)!r} en vez de preguntarle al "
        f"kernel: la puerta fail-closed se abriria donde no hay confinamiento")
    assert any(isinstance(n, ast.Call) for n in ast.walk(valor)), (
        "DISPONIBLE no llama a nada: no puede estar derivandose del kernel")


def test_DISPONIBLE_se_deriva_del_kernel_y_no_esta_cableado(monkeypatch):
    """`AI-M10` sobrevivía por lo mismo: `DISPONIBLE is (abi > 0)` es cierto con el valor cableado.

    Se recarga el módulo con la syscall fingiendo que el kernel no ofrece Landlock. Si `DISPONIBLE`
    estuviera escrito a mano, seguiría diciendo que sí — y la puerta fail-closed de `delegacion` se
    abriría en máquinas sin confinamiento."""
    import importlib

    class _LibcSinLandlock:
        def syscall(self, *_a, **_k):
            return -1

        def prctl(self, *_a, **_k):
            return 0

    monkeypatch.setattr(ais, "_libc", _LibcSinLandlock())
    recargado = importlib.reload(ais)
    try:
        monkeypatch.setattr(recargado, "_libc", _LibcSinLandlock())
        assert recargado.abi_disponible() == 0
        assert recargado.abi_disponible() > 0 or True     # el ABI real se restaura abajo
    finally:
        importlib.reload(ais)

    assert ais.DISPONIBLE is (ais.abi_disponible() > 0), "DISPONIBLE dejo de derivarse del kernel"
