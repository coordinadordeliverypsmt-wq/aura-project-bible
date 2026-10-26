"""La tarea se comprueba contra SU contrato antes de escribir (CEO, 2026-09-20).

QUÉ FALTABA. `contrato.corresponde_tarea_a_contrato()` existía, era pura y estaba probada; y desde
este mismo día la tarea transporta `tarea["contrato"]`. Pero **nadie las juntaba**. La puerta real
—`review.ejecutar_bajo_review`— comprobaba cuatro cosas antes de tocar nada: materia reservada,
ejecutor construido, REVIEW habilitado y alcance del acta. Ninguna de las cuatro mira el contrato.
Resultado medido: una tarea que declaraba venir de un contrato y **no se correspondía con él**
—otro fichero, otra operación, otros textos— llegaba a la escritura sin que nada lo notara.

POR QUÉ LA PUERTA ES ESA Y NO OTRA. `review.ejecutar_bajo_review` es donde convergen las dos vías de
producción (`motor_autonomia` y `ciclo_autonomo`) y el único llamante externo de producción de
`autoconstruccion.ejecutar`; `autoconstruccion.ciclo` no tiene llamante. Es «la puerta por donde pasa
todo el mundo» (ALERTA-005). Y es el último punto donde la TAREA todavía existe: dos líneas después
`ac.proponer()` la convierte en una `propuesta` que ya **no lleva** el identificador del contrato.

LAS DOS BARRERAS SON INDEPENDIENTES. El contrato responde «¿esta escritura es la que se autorizó?».
`PARADA` responde «¿se puede escribir algo ahora mismo?». Una tarea impecablemente atada a su
contrato sigue sin escribir con el kill switch armado, y este fichero lo demuestra en vez de
suponerlo.

QUÉ NO SE TOCA AQUÍ: `review_habilitado`, `propuesta_autorizada`, `EVENTOS_GOBERNADOS`,
`_INTOCABLES`, el alcance ni la autoridad. La barrera nueva **restringe**; no concede nada.
"""

from __future__ import annotations

import pathlib

import autoconstruccion as ac
import contrato as ct
import orquestador as orq
import pytest
import review

ORIGEN = '"Trabajo ejecutado (total)"'
DESTINO = '"Trabajo ejecutado con efecto acreditado (total)"'
IDENTIFICADOR = "capacidad-de-prueba"


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _contrato_toml(objetivo: pathlib.Path, *, operacion="sustituir_texto",
                   buscar=ORIGEN, sustituir=DESTINO, fuera=()) -> str:
    return f'''
id = "{IDENTIFICADOR}"
nombre = "capacidad de prueba"
version = "1"
estado = "AUTORIZADA"
intencion = "ejercitar la correspondencia tarea-contrato"
regla_de_transformacion = {{ operacion = "{operacion}", buscar = """{buscar}""", sustituir = """{sustituir}""" }}

[[entradas]]
nombre = "fichero"
fuente = "{objetivo}"
formato = "py"

[[salidas]]
resultado = "etiqueta cambiada"
destino = "{objetivo}"

[fuentes_de_verdad]
autoridad = ["{objetivo}"]
referencia = []

[perimetro]
modificables = ["{objetivo}"]
fuera_de_alcance = [{", ".join(f'"{f}"' for f in fuera)}]

[autoridad]
nivel = "REVIEW"
acta = "DR-E"
parte_de_aura = "aplicar"
parte_del_ceo = "autorizar"

[ejecutor]
verbo = "implementar_incremento_especificado"

[efectos]
permitidos = ["sustituir una cadena"]
prohibidos = []
reversible = true

[verificacion]
invariantes = ["INV-9"]
pruebas_minimas = ["{objetivo}"]
criterio_de_aceptacion = "la cadena cambio"
evidencia = "cambio_aplicado"

[trazabilidad]
especificacion = "fixture"
autorizacion = "DR-E"
'''


def _montaje(tmp_path, monkeypatch, *, fuera=(), operacion="sustituir_texto"):
    """REVIEW habilitado para el verbo de evolución, un fichero real y un contrato que lo autoriza."""
    objetivo = tmp_path / "observable.py"
    objetivo.write_text(f"ETIQUETA = {ORIGEN}\n", encoding="utf-8")

    capacidades = tmp_path / "capacidades"
    capacidades.mkdir()
    (capacidades / f"{IDENTIFICADOR}.toml").write_text(
        _contrato_toml(objetivo, fuera=fuera, operacion=operacion), encoding="utf-8")
    monkeypatch.setattr(ct, "CONTRATOS", capacidades)

    review.habilitar(tmp_path, alcance=("implementar_incremento_especificado",), por="ceo",
                     acta="DR-E del CEO")
    return objetivo


def _tarea(objetivo, **cambios) -> dict:
    base = {"id": "T-C1", "accion": "implementar_incremento_especificado", "simbolo": "",
            "forma": "funcion", "fichero": str(objetivo), "operacion": "sustituir_texto",
            "buscar": ORIGEN, "sustituir": DESTINO, "contrato": IDENTIFICADOR}
    base.update(cambios)
    return base


def _ejecutar(tmp_path, tarea):
    return review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                       autoridad="orquestador", verificacion=lambda raiz: True)


# ============================================================ EL CONTROL, PRIMERO --


def test_CONTROL_tarea_correcta_y_contrato_correcto_SIGUE_ejecutandose(tmp_path, monkeypatch):
    """El camino legítimo no puede romperse: una barrera que bloquea todo no distingue nada."""
    objetivo = _montaje(tmp_path, monkeypatch)

    r = _ejecutar(tmp_path, _tarea(objetivo))

    assert r["ejecutado"] is True, "la barrera bloqueo el camino autorizado"
    assert objetivo.read_text(encoding="utf-8") == f"ETIQUETA = {DESTINO}\n"


# ============================================================ LO QUE DEBE BLOQUEARSE --


def test_una_tarea_que_NO_corresponde_a_su_contrato_no_llega_a_escribir(tmp_path, monkeypatch):
    """RED el 2026-09-20: los textos de la tarea se alteraban y el contrato no los desmentía."""
    objetivo = _montaje(tmp_path, monkeypatch)
    antes = objetivo.read_text(encoding="utf-8")

    with pytest.raises(Exception) as exc:  # noqa: B017 — el tipo lo fija la implementacion
        _ejecutar(tmp_path, _tarea(objetivo, sustituir='"otra cosa completamente distinta"'))

    assert "contrato" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert objetivo.read_text(encoding="utf-8") == antes, "escribio algo que el contrato no autorizo"


def test_una_tarea_sobre_OTRO_fichero_no_llega_a_escribir(tmp_path, monkeypatch):
    """El contrato acota el fichero. Cambiarlo es salirse del perímetro que el CEO autorizó."""
    objetivo = _montaje(tmp_path, monkeypatch)
    intruso = tmp_path / "otro.py"
    intruso.write_text(f"ETIQUETA = {ORIGEN}\n", encoding="utf-8")

    with pytest.raises(Exception) as exc:  # noqa: B017
        _ejecutar(tmp_path, _tarea(objetivo, fichero=str(intruso)))

    assert "contrato" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert intruso.read_text(encoding="utf-8") == f"ETIQUETA = {ORIGEN}\n"


def test_una_OPERACION_distinta_de_la_que_el_contrato_declara_no_pasa(tmp_path, monkeypatch):
    objetivo = _montaje(tmp_path, monkeypatch)
    antes = objetivo.read_text(encoding="utf-8")

    with pytest.raises(Exception) as exc:  # noqa: B017
        _ejecutar(tmp_path, _tarea(objetivo, operacion="eliminar_codigo_muerto", simbolo="ETIQUETA"))

    assert "contrato" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert objetivo.read_text(encoding="utf-8") == antes


def test_un_contrato_que_NO_EXISTE_no_autoriza_nada(tmp_path, monkeypatch):
    """Citar un contrato inexistente no puede ser más permisivo que no citar ninguno.

    Si la ausencia de fichero se tratara como «no hay nada que comprobar», inventarse un nombre
    sería la forma más barata de saltarse la barrera entera.

    **Afirma POR QUÉ se detuvo, no solo que se detuvo.** Con la comprobación de existencia anulada,
    un contrato ausente llega a `corresponde_tarea_a_contrato()` como diccionario vacío, esa función
    devuelve `False` y la puerta siguiente bloquea igual: el resultado es seguro y la garantía queda
    **sin verificar**. Lo descubrió el mutante TC-M3, que sobrevivió con la versión anterior de esta
    prueba. Dos guardias tapándose es justo lo que la mutación existe para encontrar.
    """
    objetivo = _montaje(tmp_path, monkeypatch)
    antes = objetivo.read_text(encoding="utf-8")

    with pytest.raises(Exception) as exc:  # noqa: B017
        _ejecutar(tmp_path, _tarea(objetivo, contrato="contrato-que-nadie-escribio"))

    mensaje = str(exc.value).lower()
    assert "no consta" in mensaje, (
        f"se detuvo, pero NO por la comprobacion de existencia del contrato: {exc.value}"
    )
    assert "contrato-que-nadie-escribio" in mensaje, "no dice cual es el contrato que falta"
    assert objetivo.read_text(encoding="utf-8") == antes


def test_el_verbo_de_evolucion_SIN_contrato_no_pasa(tmp_path, monkeypatch):
    """`implementar_incremento_especificado` solo nace de un contrato (`formacion.py`).

    Una tarea con ese verbo y sin contrato no es «una tarea sin contrato»: es una que perdió —o
    nunca tuvo— la autorización que la justifica.
    """
    objetivo = _montaje(tmp_path, monkeypatch)
    antes = objetivo.read_text(encoding="utf-8")

    with pytest.raises(Exception) as exc:  # noqa: B017
        _ejecutar(tmp_path, _tarea(objetivo, contrato=""))

    assert "contrato" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert objetivo.read_text(encoding="utf-8") == antes


def test_un_fichero_declarado_FUERA_DE_ALCANCE_no_pasa_aunque_este_en_modificables(tmp_path, monkeypatch):
    """El candado de `fuera_de_alcance` sigue siendo obligatorio también por esta vía."""
    objetivo = _montaje(tmp_path, monkeypatch)
    # El mismo fichero, declarado a la vez modificable y fuera de alcance: contradictorio.
    capacidades = tmp_path / "capacidades"
    (capacidades / f"{IDENTIFICADOR}.toml").write_text(
        _contrato_toml(objetivo, fuera=(str(objetivo),)), encoding="utf-8")
    antes = objetivo.read_text(encoding="utf-8")

    with pytest.raises(Exception) as exc:  # noqa: B017
        _ejecutar(tmp_path, _tarea(objetivo))

    assert "contrato" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert objetivo.read_text(encoding="utf-8") == antes


# ============================================================ LO LEGITIMO SIN CONTRATO --


def test_CONTROL_el_codigo_muerto_sigue_sin_necesitar_contrato(tmp_path, monkeypatch):
    """No todo trabajo nace de un contrato. Exigirlo siempre habría roto la capacidad anterior."""
    modulo = tmp_path / "modulo.py"
    modulo.write_text("def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n",
                      encoding="utf-8")
    review.habilitar(tmp_path, alcance=("eliminar_codigo_muerto",), por="ceo",
                     acta="DEC-ORCH-2 del CEO")

    r = _ejecutar(tmp_path, {"id": "T-CM", "accion": "eliminar_codigo_muerto", "simbolo": "_muerta",
                             "forma": "funcion", "fichero": str(modulo), "contrato": ""})

    assert r["ejecutado"] is True, "una tarea legitima sin contrato quedo bloqueada"
    assert "_muerta" not in modulo.read_text(encoding="utf-8")


# ============================================================ LAS DOS BARRERAS SON INDEPENDIENTES --


def test_con_PARADA_armada_ni_siquiera_una_tarea_PERFECTA_escribe(tmp_path, monkeypatch):
    """Contrato correcto + tarea correcta + autorización válida + PARADA armada = BLOQUEO.

    Es la prueba de que contrato y kill switch no son la misma barrera vestida de dos maneras: la
    primera dice *«esta escritura no es la autorizada»*, la segunda *«ahora no se escribe nada»*.
    """
    objetivo = _montaje(tmp_path, monkeypatch)
    (tmp_path / "PARADA").write_text("", encoding="utf-8")
    antes = objetivo.read_text(encoding="utf-8")

    with pytest.raises(ac.ParadaActiva):
        _ejecutar(tmp_path, _tarea(objetivo))

    assert objetivo.read_text(encoding="utf-8") == antes
