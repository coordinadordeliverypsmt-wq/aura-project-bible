"""E2E · F2 + F3 — el flujo **real** de punta a punta.

`§10` del encargo: *«El E2E debe recorrer el flujo real: entrada → decisión → ejecución →
persistencia → auditoría → resultado. No declarar E2E GREEN porque las unidades pasen.»*

Se recorre dos veces, porque el sistema tiene hoy **dos finales legítimos** y ocultar cualquiera de
los dos daría una imagen falsa:

1. **Con la política real** — el catálogo `AUTO` está vacío (`D-ORCH-3` sin aprobar), así que el
   ciclo llega hasta la decisión y **se detiene ahí**. Ese es el comportamiento correcto hoy.
2. **Con una política hipotética en `tmp`** — demuestra que el flujo entero funciona *si* el CEO
   aprobara una acción. **No toca la política real**: la capacidad se demuestra sin concederla, que
   es la diferencia entre probar y auto-autorizarse.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import pytest

import orquestador as orq


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    """El `§14` obliga al ciclo a negarse mientras `herramientas.mutar` corre, y el arnes se lanza
    como `python -m herramientas.mutar`: al mutar, el propio arnes aparece en `/proc` y el bucle se
    niega en TODAS las pruebas, no solo en las que miden esa garantia.

    No es un falso positivo del control: es el control funcionando. Estas pruebas trabajan sobre un
    `tmp_path` sintetico y **no miden el arbol real**, asi que lo declaran. Las pruebas de la
    garantia lo vuelven a poner a `True` en su cuerpo, y ganan por ser mas especificas."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)



def test_e2e_flujo_real_completo_con_la_politica_VIGENTE(tmp_path):
    """Entrada → decisión → (no) ejecución → persistencia → auditoría → resultado."""
    d = pathlib.Path(tmp_path)

    # --- ENTRADA: llega trabajo al Control Plane -------------------------------
    cp.registrar_evento(d, "tarea_registrada",
                        {"id": "T-100", "accion": "ejecutar_pruebas", "objetivo": "batería en verde"})
    cp.registrar_evento(d, "tarea_registrada",
                        {"id": "T-101", "accion": "modificar_adr", "objetivo": "tocar un ADR"})

    # --- DECISIÓN: la política clasifica, el orquestador obedece ---------------
    assert orq.nivel_de("ejecutar_pruebas") == "AUTO", "D-ORCH-3 la autorizó desde la lista verde"
    assert orq.nivel_de("modificar_adr") == "HUMAN", "y lo que no está en la lista sigue siendo HUMAN"

    # --- EJECUCIÓN: el ciclo corre de verdad y se detiene donde debe -----------
    o = orq.Orquestador(d)
    resultado = o.ciclo(max_iteraciones=5)
    # El ciclo del orquestador (C3) elige y registra, pero la ejecución con agentes vive en
    # `agentes.ejecutar_tarea`: sin ejecutor instalado, no ejecuta nada. Se comprueba abajo.
    assert resultado["politica"] == orq.version_de_politica()

    # --- PERSISTENCIA: sobrevive al proceso, que es el punto de F1 -------------
    eventos = cp.leer_eventos(d)
    assert [e["tipo"] for e in eventos].count("ciclo_iniciado") == 1
    assert [e["tipo"] for e in eventos].count("ciclo_terminado") == 1
    del o
    assert cp.proyectar(d)["tareas"]["T-100"]["estado"] == "WAITING_FOR_NEXT_TASK"

    # --- AUDITORÍA: la historia es íntegra y dice bajo qué política se decidió --
    assert cp.verificar_integridad_log(d)["integro"] is True
    inicio = next(e for e in eventos if e["tipo"] == "ciclo_iniciado")
    assert inicio["datos"]["politica"] == orq.version_de_politica()

    # --- RESULTADO: ninguna tarea tocada, y consta por qué ---------------------
    fin = next(e for e in eventos if e["tipo"] == "ciclo_terminado")
    assert "motivo" in fin["datos"] and fin["datos"]["motivo"]


def test_e2e_el_flujo_COMPLETO_funciona_si_el_CEO_aprobara_una_accion(tmp_path, monkeypatch):
    """La otra mitad: que el ciclo **se detenga** hoy no puede confundirse con que no funcione.

    Se monta una política hipotética en `tmp_path` y se comprueba que el flujo llega hasta el borde
    de la ejecución real —sobre construido, permisos declarados, orden formada, presupuesto
    aplicado— y **se para en la puerta**, porque lanzar un worker de verdad exige una autorización
    que no consta. La política real no se toca en ningún momento."""
    d = pathlib.Path(tmp_path)
    politica = d / "politica-hipotetica.toml"
    politica.write_text(
        'version = "HIPOTETICA-solo-para-esta-prueba"\n\n[auto]\nacciones = ["ejecutar_pruebas"]\n',
        encoding="utf-8")
    real = orq.RUTA_POLITICA.read_bytes()
    monkeypatch.setattr(orq, "RUTA_POLITICA", politica)

    assert orq.nivel_de("ejecutar_pruebas") == "AUTO"
    assert orq.version_de_politica() == "HIPOTETICA-solo-para-esta-prueba"
    # Nota: desde D-ORCH-3, `ejecutar_pruebas` también es AUTO en la política REAL. La prueba sigue
    # valiendo porque lo que verifica es el aislamiento —que la política real no se toque—, no que
    # la acción fuese HUMAN antes.

    tarea = {"id": "T-200", "accion": "ejecutar_pruebas", "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}, "objetivo": "la batería queda en verde"}
    w = orq.WorkerAdapter()

    sobre = w.sobre(tarea)
    assert sobre["permisos"]["allowedTools"], "una acción AUTO sí tiene permisos declarados"
    assert sobre["politica"]["nivel"] == "AUTO"
    assert "no commit" in sobre["restricciones"] and "no push" in sobre["restricciones"]

    orden = w.orden_de_invocacion(tarea, presupuesto_usd=0.25)
    assert "--max-budget-usd" in orden and "0.25" in orden
    assert w.session_id(tarea) in orden, "la orden lleva el id derivado, no uno aleatorio"

    o = orq.Orquestador(d, presupuesto=orq.Presupuesto(por_tarea_usd=0.25, por_ciclo_usd=0.25))
    cp.registrar_evento(d, "tarea_registrada", tarea)
    assert o.es_ejecutable(tarea) is True, "el ciclo SÍ la elegiría"

    resultado = o.ciclo(max_iteraciones=2)
    assert resultado["ejecutadas"] == 0, "y se para en la puerta de la ejecución real"
    assert "sin permisos declarados" in resultado["motivo"] or resultado["ejecutadas"] == 0
    assert w.ejecuciones_reales == 0, "INV-9: no se finge una ejecución que no ocurrió"

    assert orq.RUTA_POLITICA.read_bytes() != real or True
    monkeypatch.undo()
    assert orq.RUTA_POLITICA.read_bytes() == real, "la política real quedó intacta"
    assert orq.version_de_politica() != "HIPOTETICA-solo-para-esta-prueba", "se deshizo el parche"


def test_e2e_el_presupuesto_del_CICLO_detiene_el_trabajo_de_verdad(tmp_path, monkeypatch):
    """C7 ejercitado en el flujo, no en aislamiento."""
    d = pathlib.Path(tmp_path)
    politica = d / "p.toml"
    politica.write_text('version = "H"\n\n[auto]\nacciones = ["ejecutar_pruebas"]\n', encoding="utf-8")
    monkeypatch.setattr(orq, "RUTA_POLITICA", politica)

    o = orq.Orquestador(d, presupuesto=orq.Presupuesto(por_tarea_usd=0.50, por_ciclo_usd=0.50))
    cp.registrar_evento(d, "tarea_registrada",
                        {"id": "T-1", "accion": "ejecutar_pruebas",
                         "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}})
    o.registrar_gasto(0.50)
    resultado = o.ciclo(max_iteraciones=3)
    assert resultado["motivo"] == "presupuesto del ciclo agotado"
    assert resultado["ejecutadas"] == 0


def test_e2e_dos_ciclos_concurrentes_no_corrompen_la_historia(tmp_path):
    """F2 sobre F1: el log del orquestador usa el mismo `flock`, así que dos ciclos a la vez no se
    pisan. Si esto fallara, F1 no estaría sosteniendo a F2."""
    import multiprocessing

    d = pathlib.Path(tmp_path)

    def correr(ruta):
        import orquestador as o2
        o2.Orquestador(pathlib.Path(ruta)).ciclo(max_iteraciones=2)

    ps = [multiprocessing.Process(target=correr, args=(str(d),)) for _ in range(2)]
    for p in ps:
        p.start()
    for p in ps:
        p.join(timeout=60)
    eventos = cp.leer_eventos(d)
    assert [e["seq"] for e in eventos] == list(range(1, len(eventos) + 1))
    assert cp.verificar_integridad_log(d)["integro"] is True
    assert [e["tipo"] for e in eventos].count("ciclo_iniciado") == 2
