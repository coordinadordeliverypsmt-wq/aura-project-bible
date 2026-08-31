"""RED · el **despertador**: lo único que falta para que AURA trabaje sin Claude.

El motor ya sabe descubrir, decidir, ejecutar y parar. Lo que no tiene es quién lo llame. Y ahí está
la trampa que este fichero existe para evitar: **es facilísimo que el que despierta acabe decidiendo**.

Un despertador que consulta la cola para saber si merece la pena arrancar, o que reintenta cuando no
hubo trabajo, o que decide cuántas tareas tocan hoy, ha dejado de ser un despertador: es un planificador
externo, y la autonomía se habría mudado fuera de AURA sin que nadie lo declarase.

La regla, entonces, es negativa y se prueba como tal:

| El despertador… | |
|---|---|
| **no** decide qué trabajo | no importa `descubrimiento` ni `planificador` |
| **no** crea tareas | no registra `tarea_planificada` |
| **no** tiene autoridad | no llama a `transicion`, `guardar` ni `actualizar_estado` |
| **no** se repite solo | ni bucles, ni esperas, ni reprogramación (`§23`) |
| **sí** deja rastro | cada despertar consta, con su resultado |

Y dos comprobaciones **antes** de despertar, que no son decisiones sobre el trabajo sino sobre si es
seguro tocar el árbol: el kill switch, y que no haya un arnés de mutación corriendo — porque mientras
`herramientas.mutar` corre, el árbol **no contiene el código real**.
"""

from __future__ import annotations

import pathlib

import despertador
import orquestador as orq
import pytest


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


# ==================================================== NO DECIDE --


def test_el_despertador_NO_sabe_nada_del_trabajo():
    """La garantía central, comprobada en el **código**: si importara el descubridor o el
    planificador, podría mirar la cola antes de arrancar — y mirar la cola para decidir si arranca ya
    es decidir."""
    import ast
    arbol = ast.parse(pathlib.Path(despertador.__file__).read_text(encoding="utf-8"))
    importados = {a.name.split(".")[0] for n in ast.walk(arbol)
                  if isinstance(n, ast.Import) for a in n.names}
    importados |= {n.module.split(".")[0] for n in ast.walk(arbol)
                   if isinstance(n, ast.ImportFrom) and n.module}
    for prohibido in ("descubrimiento", "planificador", "review", "agentes", "autoconstruccion"):
        assert prohibido not in importados, (
            f"un despertador que conoce {prohibido} puede decidir, y entonces la autonomía se muda "
            f"fuera de AURA sin que nadie lo declare")


def test_el_despertador_NO_crea_tareas_ni_toca_el_estado():
    """No tiene autoridad sobre el repositorio: no transiciona, no guarda, no escribe ficheros."""
    import ast
    arbol = ast.parse(pathlib.Path(despertador.__file__).read_text(encoding="utf-8"))
    llamadas = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    for prohibido in ("transicion", "guardar", "actualizar_estado", "completar_tarea",
                      "fijar_estado_tarea", "write_text", "write_bytes", "unlink"):
        assert prohibido not in llamadas, f"el despertador no tiene autoridad: {prohibido}"


def test_el_despertador_NO_se_repite_solo():
    """`§23` del DP: *«Ningún daemon ni watcher permanente»*. Un despertador que se reprograma es un
    demonio con otro nombre — y a un demonio hay que ir a matarlo, que es justo lo que el kill switch
    existe para no tener que hacer."""
    import ast
    fuente = pathlib.Path(despertador.__file__).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    assert not [n for n in ast.walk(arbol) if isinstance(n, (ast.While, ast.AsyncFor))]
    llamadas = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    llamadas |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for prohibido in ("sleep", "Thread", "Timer", "fork", "crontab", "schedule"):
        assert prohibido not in llamadas, f"el despertador despierta una vez y termina: {prohibido}"


# ==================================================== SÍ DESPIERTA --


def test_despertar_INVOCA_el_ciclo_de_AURA(tmp_path, monkeypatch):
    """Lo único que hace: llamar. Y el resultado que devuelve es el de AURA, sin interpretarlo — un
    despertador que reinterpretara el informe estaría opinando sobre el trabajo."""
    llamadas = []
    monkeypatch.setattr(despertador, "_ciclo_de_aura",
                        lambda tope: llamadas.append(tope) or {"motivo_de_parada": "cola agotada",
                                                               "ejecutadas": 0})
    resultado = despertador.despertar(tmp_path, max_tareas=3)
    assert llamadas == [3], "pasa el tope tal cual: no decide cuántas tareas tocan"
    assert resultado["despertado"] is True
    assert resultado["informe"]["motivo_de_parada"] == "cola agotada"


def test_cada_despertar_deja_RASTRO(tmp_path, monkeypatch):
    """Un despertar que no consta es indistinguible de uno que no ocurrió, y el siguiente lector no
    sabría si el ciclo lleva parado una hora o una semana."""
    monkeypatch.setattr(despertador, "_ciclo_de_aura",
                        lambda tope: {"motivo_de_parada": "cola agotada", "ejecutadas": 0})
    despertador.despertar(tmp_path, max_tareas=1)
    import control_plane as cp
    eventos = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "aura_despertada"]
    assert eventos, "el despertar tiene que constar"
    assert eventos[-1]["datos"]["resultado"] == "cola agotada"


# ==================================================== NO DESPIERTA SI NO ES SEGURO --


def test_el_kill_switch_impide_despertar(tmp_path, monkeypatch):
    """Fuera de banda y **antes** de arrancar: si el sistema está comprometido, lo último que hace
    falta es despertarlo."""
    monkeypatch.setattr(despertador, "_ciclo_de_aura",
                        lambda tope: pytest.fail("no debería haber llegado a llamar a AURA"))
    orq.ruta_parada(tmp_path).write_text("parada", encoding="utf-8")
    resultado = despertador.despertar(tmp_path, max_tareas=1)
    assert resultado["despertado"] is False
    assert resultado["motivo"] == "kill switch activado"


def test_NO_despierta_mientras_corre_el_ARNES_de_mutacion(tmp_path, monkeypatch):
    """Regla del CEO (2026-08-09): mientras `herramientas.mutar` corre, el árbol **no contiene el
    código real**. Despertar a AURA entonces la pondría a trabajar sobre mutantes, y a registrar como
    hecho un trabajo hecho sobre código que no existe.

    No es una decisión sobre el trabajo: es sobre si es seguro tocar el árbol. Por eso sí le
    corresponde al despertador."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: True)
    monkeypatch.setattr(despertador, "_ciclo_de_aura",
                        lambda tope: pytest.fail("no debería haber llegado a llamar a AURA"))
    resultado = despertador.despertar(tmp_path, max_tareas=1)
    assert resultado["despertado"] is False
    assert resultado["motivo"] == "arnés de mutación en curso"


def test_una_negativa_a_despertar_tambien_deja_RASTRO(tmp_path, monkeypatch):
    """Y con su motivo: «no desperté» sin decir por qué obliga al siguiente a averiguarlo."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: True)
    despertador.despertar(tmp_path, max_tareas=1)
    import control_plane as cp
    eventos = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "despertar_rechazado"]
    assert eventos and eventos[-1]["datos"]["motivo"] == "arnés de mutación en curso"


# ==================================================== EL TOPE ES DEL QUE DESPIERTA, ACOTADO --


def test_el_tope_esta_ACOTADO_aunque_lo_pidan_enorme(tmp_path, monkeypatch):
    """`§14`: ningún bucle sin cota. Que el tope venga de fuera no significa que valga cualquiera —
    un despertador mal configurado no puede convertirse en el demonio que el `§23` prohíbe."""
    visto = []
    monkeypatch.setattr(despertador, "_ciclo_de_aura",
                        lambda tope: visto.append(tope) or {"motivo_de_parada": "cola agotada",
                                                            "ejecutadas": 0})
    despertador.despertar(tmp_path, max_tareas=10_000)
    assert visto == [despertador.TOPE_MAXIMO]


def test_un_tope_absurdo_no_pasa_de_largo(tmp_path, monkeypatch):
    monkeypatch.setattr(despertador, "_ciclo_de_aura",
                        lambda tope: {"motivo_de_parada": "cola agotada", "ejecutadas": 0})
    for absurdo in (0, -1):
        with pytest.raises(ValueError):
            despertador.despertar(tmp_path, max_tareas=absurdo)
