"""`DR-F-3f` — `descubrir()` **no es read-only**, y eso es parte del contrato.

Lo aprendí equivocándome: en `DR-F-3d-5` traté una llamada directa a `descubrimiento.descubrir()`
como si fuera una consulta inocua, y escribió eventos en el log del plano.

Investigado, resulta que el registro **no es un efecto secundario**: es la fuente de datos de dos
consumidores. `observatorio._resumir_ciclo` (`observatorio.py:240`) saca de ahí las cifras que enseña
`aura.py estado`, y la sexta fuente —estancamiento— mira esos mismos eventos para saber si el sistema
lleva vueltas sin avanzar. Si `descubrir()` dejase de registrar, AURA se quedaría **ciega en
silencio**: seguiría descubriendo, y nadie podría verlo.

Y no había red. Las pruebas de `observatorio` y de `estancamiento` **fabrican** el evento a mano para
montar sus escenarios, así que ninguna se enteraría de que el productor real dejó de emitirlo. Es el
mismo patrón que el mutante «la composición no enciende las automatizaciones», que sobrevivió con 426
pruebas en verde.

Esta prueba no cambia comportamiento: fija el que ya hay, y deja escrito por qué importa.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import descubrimiento as des


def _sin_fuentes(monkeypatch):
    """El contrato que se comprueba es **el registro**, no lo que se encuentre. Con las fuentes
    vacías la prueba no depende del contenido del árbol y sigue siendo determinista."""
    monkeypatch.setattr(des, "FUENTES", {})


def test_descubrir_registra_su_evento(tmp_path, monkeypatch):
    """Sin este evento, `aura.py estado` no tendría de dónde sacar sus cifras."""
    _sin_fuentes(monkeypatch)
    antes = len(cp.leer_eventos(tmp_path))
    des.descubrir(tmp_path, tmp_path)
    eventos = cp.leer_eventos(tmp_path)
    assert len(eventos) == antes + 1, "descubrir() escribe: no es una consulta"
    assert eventos[-1]["tipo"] == "descubrimiento_realizado"


def test_el_evento_lleva_lo_que_el_observatorio_necesita(tmp_path, monkeypatch):
    """`observatorio._resumir_ciclo` lee `encontradas` y `por_clase`; `estancamiento` mira el mismo
    evento. Los nombres de esos campos son contrato entre productor y consumidores."""
    _sin_fuentes(monkeypatch)
    des.descubrir(tmp_path, tmp_path)
    datos = cp.leer_eventos(tmp_path)[-1]["datos"]
    assert datos["encontradas"] == 0
    assert set(datos["por_clase"]) == set(des.CLASES)
    assert "raiz" in datos, "sin la raiz no se puede saber sobre qué ámbito se descubrió"


def test_la_raiz_registrada_es_la_que_se_uso(tmp_path, monkeypatch):
    """El campo que explicó `FINDING-1`: 9 y 30 eran el mismo código sobre ámbitos distintos, y solo
    se pudo demostrar porque la raíz viaja en el evento."""
    _sin_fuentes(monkeypatch)
    otra = tmp_path / "otro_ambito"
    otra.mkdir()
    des.descubrir(otra, tmp_path)
    assert cp.leer_eventos(tmp_path)[-1]["datos"]["raiz"] == str(otra)


def test_una_fuente_rota_no_impide_el_registro(tmp_path, monkeypatch):
    """Un descubrimiento parcial **también** se registra, y dice qué fuente falló: quedarse sin
    evento por una fuente rota sería perder la única señal de que algo va mal."""
    def _explota(_raiz, _directorio):
        raise RuntimeError("fuente defectuosa")

    monkeypatch.setattr(des, "FUENTES", {"rota": _explota})
    des.descubrir(tmp_path, tmp_path)
    datos = cp.leer_eventos(tmp_path)[-1]["datos"]
    assert datos["fuentes_con_error"], "una fuente rota debe quedar registrada"
    assert datos["fuentes_con_error"][0]["fuente"] == "rota"


def test_el_modulo_declara_que_escribe(tmp_path, monkeypatch):
    """Una advertencia en prosa se borra sin que nadie se entere; esta no. El día que alguien vuelva
    a tratar `descubrir()` como una consulta, esta prueba es la que se lo dirá."""
    fuente = (pathlib.Path(__file__).parent / "descubrimiento.py").read_text(encoding="utf-8")
    assert "registrar_evento" in fuente, (
        "descubrir() registra su acto en el log; si deja de hacerlo, el observatorio y la fuente de "
        "estancamiento se quedan sin datos y nadie lo nota")
