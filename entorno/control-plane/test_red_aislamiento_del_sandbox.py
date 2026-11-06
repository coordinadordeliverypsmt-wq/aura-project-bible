"""Un sandbox no puede tocar el árbol real (CEO, 2026-09-20).

EL INCIDENTE. Una medición del motor montada en un directorio temporal **borró 49 líneas y dos
funciones del fichero real** `milestones/m3-entry/medicion-razonador/heuristicas_deterministas.py`.
Se restauró con `git checkout`, pero la causa no era el sandbox: `ac.ficheros_autorizados()` devuelve
**rutas absolutas del repositorio**, y el atajo del acta concedía ese fichero con cualquier `raiz`.
Montar un sandbox no protegía nada, porque la ruta concedida apuntaba fuera de él.

POR QUÉ ESTE FICHERO Y NO SOLO EL ARREGLO. La barrera ya está puesta
(`autoconstruccion._la_raiz_es_de_este_repositorio`), y una barrera sin prueba es una promesa. Esto
la convierte en una garantía que se ejerce en cada batería: **el día que alguien vuelva a abrir esa
vía —por un refactor, por un atajo nuevo, por otra lista de rutas absolutas— falla aquí**, y no en
el árbol de un compañero.

CÓMO SE MIDE, Y POR QUÉ ASÍ. No se comprueba leyendo el código: se ejecuta el motor entero en un
sandbox y se compara el **hash** de los ficheros reales que estuvieron en riesgo, antes y después.
La lección de este proyecto es que la lectura basta para conjeturar y solo la ejecución acredita.

ESTE FICHERO NO ESCRIBE EN EL ÁRBOL REAL. Todo lo que crea vive en `tmp_path`. Lo único que hace con
el repositorio es **leerlo para comprobar que no cambió**.
"""

from __future__ import annotations

import hashlib
import pathlib

import autoconstruccion as ac
import orquestador as orq
import pytest

PLANO = pathlib.Path(__file__).resolve().parent
RAIZ_REPO = PLANO.parents[1]

#: Los ficheros reales que estuvieron —o podrían estar— al alcance de una ejecución en sandbox.
#: El primero es el que el incidente borró; los otros dos son el objetivo del incremento autorizado
#: y la puerta de escritura, que es la que decide.
EN_RIESGO = (
    RAIZ_REPO / "milestones" / "m3-entry" / "medicion-razonador" / "heuristicas_deterministas.py",
    PLANO / "observatorio.py",
    PLANO / "autoconstruccion.py",
)


def _huellas() -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in EN_RIESGO if p.is_file()}


@pytest.fixture(autouse=True)
def _el_arnes_no_esta_corriendo(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


# ============================================================ LA BARRERA, EJERCIDA --


def test_ninguna_ruta_del_repositorio_se_concede_desde_una_raiz_AJENA(tmp_path):
    """El acta amplía el perímetro para trabajar SOBRE este repositorio, no «desde cualquier raíz»."""
    for real in EN_RIESGO:
        assert ac.zona_permitida(real, raiz=tmp_path) is False, (
            f"{real.name} se concedio con una raiz ajena al repositorio")


def test_un_SYMLINK_del_sandbox_al_arbol_real_no_se_concede(tmp_path):
    """La comparación es sobre la ruta RESUELTA: un nombre inocente no cambia a dónde apunta."""
    objetivo = PLANO / "observatorio.py"
    enlace = tmp_path / "inocente.py"
    try:
        enlace.symlink_to(objetivo)
    except (OSError, NotImplementedError):
        pytest.skip("el sistema de ficheros no permite enlaces simbolicos")

    assert ac.zona_permitida(enlace, raiz=tmp_path) is False, (
        "se alcanzo el arbol real a traves de un enlace con nombre inocente")
    assert objetivo.read_text(encoding="utf-8"), "la prueba no debe alterar el fichero real"


def test_una_ruta_con_PUNTOS_desde_el_sandbox_no_escapa(tmp_path):
    """`..` no es un atajo: se resuelve antes de juzgar."""
    escape = tmp_path / ".." / ".." / "entorno" / "control-plane" / "observatorio.py"

    assert ac.zona_permitida(escape, raiz=tmp_path) is False


# ============================================================ EL MOTOR ENTERO, MEDIDO --


def test_un_ciclo_COMPLETO_en_sandbox_deja_el_arbol_real_byte_a_byte_igual(tmp_path):
    """La garantía por el efecto, que es la única que este proyecto acepta.

    Se ejecuta el motor de verdad —descubrir, planificar, revisar, ejecutar, verificar— sobre un
    árbol temporal con su propio PARADA desarmado y su propio historial, y se comprueba que los
    ficheros reales que estuvieron en riesgo no cambiaron ni un byte. Es exactamente la medición que
    faltaba el día del incidente.
    """
    import motor_autonomia as motor
    import review

    zona = tmp_path / "entorno" / "control-plane"
    zona.mkdir(parents=True)
    (zona / "modulo.py").write_text(
        "def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n", encoding="utf-8")
    review.habilitar(zona, alcance=("eliminar_codigo_muerto",), por="ceo",
                     acta="DEC-ORCH-2 del CEO")

    antes = _huellas()
    motor.trabajar(zona, zona, verificacion=lambda raiz: True, max_tareas=3)
    despues = _huellas()

    assert despues == antes, (
        "un ciclo ejecutado en sandbox altero el arbol REAL: "
        f"{[n for n in antes if antes[n] != despues.get(n)]}")
    assert "_muerta" not in (zona / "modulo.py").read_text(encoding="utf-8"), (
        "la prueba no ejercito el motor: no hizo trabajo en su propio sandbox")


def test_el_motor_en_sandbox_no_toca_el_PARADA_real(tmp_path):
    """El kill switch real no se arma ni se desarma por ejecutar algo en otro sitio."""
    import motor_autonomia as motor

    real = orq.ruta_parada(PLANO)
    existia = real.exists()

    zona = tmp_path / "entorno" / "control-plane"
    zona.mkdir(parents=True)
    motor.trabajar(zona, zona, verificacion=lambda raiz: True, max_tareas=1)

    assert real.exists() is existia, "el PARADA real cambio por una ejecucion en sandbox"


def test_el_motor_en_sandbox_no_escribe_en_el_historial_real(tmp_path):
    """Cada árbol lleva su propio log. Mezclarlos haría del historial real una ficción."""
    import motor_autonomia as motor
    import control_plane as cp

    eventos_reales = PLANO / "eventos.jsonl"
    antes = eventos_reales.read_bytes() if eventos_reales.is_file() else b""

    zona = tmp_path / "entorno" / "control-plane"
    zona.mkdir(parents=True)
    motor.trabajar(zona, zona, verificacion=lambda raiz: True, max_tareas=1)

    despues = eventos_reales.read_bytes() if eventos_reales.is_file() else b""
    assert despues == antes, "el motor en sandbox escribio en el historial REAL"
    assert cp.leer_eventos(zona), "la prueba no midio nada: el sandbox no registro ningun evento"


# ============================================================ EL CONTROL --


def test_CONTROL_con_la_raiz_REAL_el_perimetro_del_acta_SIGUE_concediendo(tmp_path):
    """Sin esto, el aislamiento sería indistinguible de una parálisis: en producción tiene que valer."""
    autorizado = EN_RIESGO[0]
    if not autorizado.is_file():
        pytest.skip("el fichero que el acta autoriza no esta en el arbol")

    assert ac.zona_permitida(autorizado, raiz=PLANO) is True, (
        "se rompio el perimetro que el acta del CEO concedio para el trabajo real")
