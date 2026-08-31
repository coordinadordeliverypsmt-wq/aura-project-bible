"""RED · `DP-DEVELOPMENT-ORCHESTRATOR` **F2 + F3** — C3, C4, C6, C7.

`§20`: **F2** = *«C3 + C4: Orchestrator (bucle finito) + WorkerAdapter, solo tareas AUTO»*, depende
de **F1** (hecha). **F3** = *«C6 + C7: política versionada + presupuestos»*, depende de F2. Se
construyen como un solo bloque vertical porque F3 gobierna lo que F2 ejecuta: separarlas dejaría a
F2 decidiendo su propia política, que es justo lo que `§5` le prohíbe.

**F4 y F5 quedan fuera y no se tocan:** F4 exige `§25.2` —crear el nivel `REVIEW`, que *«no existe
hoy»* en ADR-0003 y *«solo el CEO puede conceder»*— y F5 exige *«enmienda de D24»*. Ninguna consta
aprobada `[EJEC]`.

**Lo que el contrato ya determina y no decido yo:** `§25.3` — *«La matriz de §10.2 es una propuesta.
La lista exacta la fija el CEO. **Sin lista aprobada, todo es `HUMAN`**»*. Así que el catálogo `AUTO`
nace **vacío**, y el orquestador arranca sin nada que ejecutar. Eso no es un fallo: es la política
existente aplicada, *«ante la duda, roja»*.
"""

from __future__ import annotations

import json
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



def _dir(tmp_path):
    return pathlib.Path(tmp_path)


# ============================================================ C6 · POLÍTICA (F3) --


def test_c6_la_politica_vive_en_un_FICHERO_versionado():
    """`§10.2`: *«La política vive en un fichero versionado que ningún componente del orquestador
    puede escribir»*. Si viviera en código, cambiarla sería un `commit` de lógica y no un acto de
    gobierno registrable."""
    assert orq.RUTA_POLITICA.exists(), "la política debe ser un artefacto, no una constante"
    assert orq.RUTA_POLITICA.suffix == ".toml"


def test_c6_sin_regla_la_accion_es_HUMAN():
    """*«Si no hay regla para una acción, la acción es HUMAN»* — aplicación literal de «ante la duda,
    roja» (ADR-0003)."""
    assert orq.nivel_de("una_accion_que_nadie_ha_declarado_jamas") == "HUMAN"


def test_c6_el_catalogo_AUTO_sale_de_fuentes_aprobadas_y_REVIEW_sigue_vacio():
    """**Premisa superada por `D-ORCH-3` (2026-08-26).** Esta prueba medía que `AUTO` estaba vacío
    *«mientras el CEO no fije la lista»*. La lista ya está fijada — **derivada** del catálogo verde
    de `permissions.py` y de `DP §10.2`, no inventada—, así que exigir que siga vacía sería pedirle
    al código que no haga lo que se le encargó.

    Lo que **no** ha cambiado y sigue protegido: `REVIEW` continúa vacío, porque ese nivel *«no
    existe hoy»* en ADR-0003 y crearlo es `D-ORCH-2`, del CEO."""
    auto = orq.acciones_de_nivel("AUTO")
    assert auto, "D-ORCH-3 fija la lista; vacía significaría que no se aplicó"
    for accion in auto:
        ficha = orq.ficha_de(accion)
        assert ficha.get("origen"), f"{accion} debe citar la fuente aprobada que la autoriza"
        assert ficha.get("limites_de_modificacion") == "ninguna", "AUTO no concede escritura"
    assert orq.acciones_de_nivel("REVIEW") == (), "REVIEW no existe hasta D-ORCH-2"


def test_c6_ningun_componente_del_orquestador_puede_ESCRIBIR_la_politica():
    """`§5`: C6 *«NUNCA: ser escrito por C3, C4 o C5»*. Es la separación que impide que el ejecutor
    se conceda permisos a sí mismo."""
    with pytest.raises(orq.PoliticaInmutable):
        orq.escribir_politica({"accion": "AUTO"})
    for modulo in (orq.Orquestador, orq.WorkerAdapter):
        fuente = pathlib.Path(orq.__file__).read_text(encoding="utf-8")
        assert "RUTA_POLITICA.write_text" not in fuente


def test_c6_la_politica_declara_su_version():
    """Una política sin versión no es auditable: no se puede decir bajo qué reglas se ejecutó algo."""
    assert isinstance(orq.version_de_politica(), str) and orq.version_de_politica()


# ========================================================= C7 · PRESUPUESTO (F3) --


def test_c7_hay_tope_por_TAREA_y_por_CICLO():
    """`§5`: C7 = *«Topes por tarea y por ciclo»*."""
    p = orq.Presupuesto(por_tarea_usd=0.50, por_ciclo_usd=2.00)
    assert p.permite(gastado_en_ciclo=0.0, coste_previsto=0.50)
    assert not p.permite(gastado_en_ciclo=0.0, coste_previsto=0.51), "supera el tope por tarea"
    assert not p.permite(gastado_en_ciclo=1.90, coste_previsto=0.20), "supera el tope por ciclo"


def test_c7_el_presupuesto_NO_inventa_cuota():
    """`§5`: C7 *«NUNCA: inventar cuota»*, y la regla del CEO de 2026-08-04 sobre techos no
    derivables. El presupuesto es un **límite que el operador fija**, no una medición de lo que
    queda: el Control Plane ya documenta que el consumo **no es observable**."""
    fuente = pathlib.Path(orq.__file__).read_text(encoding="utf-8")
    for prohibido in ("cuota_restante", "porcentaje_usado", "usage_known = True"):
        assert prohibido not in fuente
    p = orq.Presupuesto(por_tarea_usd=0.50, por_ciclo_usd=2.00)
    assert not hasattr(p, "restante_real"), "no se afirma lo que no se puede medir"


def test_c7_un_presupuesto_agotado_DETIENE_el_ciclo(tmp_path):
    d = _dir(tmp_path)
    o = orq.Orquestador(d, presupuesto=orq.Presupuesto(por_tarea_usd=0.10, por_ciclo_usd=0.10))
    assert o.puede_gastar(0.05) is True
    o.registrar_gasto(0.10)
    assert o.puede_gastar(0.01) is False


# ====================================================== C3 · ORCHESTRATOR (F2) --


def test_c3_el_bucle_es_FINITO(tmp_path):
    """`§5`: C3 es un *«bucle finito»*. Un bucle sin cota es un demonio, y el DP no autoriza ninguno.

    Se comprueba el **tope calculado**, no las iteraciones observadas: hoy el ciclo se rompe siempre
    en la primera vuelta (no hay tareas AUTO), así que contar vueltas no distingue un tope sano de
    uno roto — un mutante que cambiaba `min` por `max` sobrevivía por eso. El tope viaja en el
    evento `ciclo_iniciado`, que es donde queda auditable."""
    d = _dir(tmp_path)
    o = orq.Orquestador(d)
    resultado = o.ciclo(max_iteraciones=3)
    assert resultado["iteraciones"] <= 3

    inicio = next(e for e in cp.leer_eventos(d) if e["tipo"] == "ciclo_iniciado")
    assert inicio["datos"]["tope"] == 3, "pedir 3 no puede acabar en un tope mayor"

    d2 = _dir(tmp_path) / "otro"
    o2 = orq.Orquestador(d2)
    o2.ciclo(max_iteraciones=10_000)
    tope = next(e for e in cp.leer_eventos(d2) if e["tipo"] == "ciclo_iniciado")["datos"]["tope"]
    assert tope <= orq.Orquestador.MAX_ITERACIONES, "ni pidiendo 10.000 se supera el tope duro"


def test_c3_sin_tareas_AUTO_el_ciclo_no_ejecuta_NADA(tmp_path):
    """La consecuencia directa de `§25.3`. El orquestador arranca **sin trabajo**, y decirlo es más
    honesto que fabricar una lista para que parezca que funciona (INV-9)."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "refactor_grande"})
    o = orq.Orquestador(d)
    resultado = o.ciclo(max_iteraciones=5)
    assert resultado["ejecutadas"] == 0
    assert resultado["motivo"] in ("sin tareas ejecutables", "sin trabajo")
    assert cp.estado_de(d, "T-1") == "WAITING_FOR_NEXT_TASK", "no se tocó"


def test_c3_una_tarea_HUMAN_NUNCA_la_ejecuta_el_orquestador(tmp_path):
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-H", "accion": "modificar_adr"})
    o = orq.Orquestador(d)
    assert orq.nivel_de("modificar_adr") == "HUMAN"
    assert o.es_ejecutable({"id": "T-H", "accion": "modificar_adr"}) is False


def test_c3_el_orquestador_NO_decide_politica():
    """`§5`: C3 *«NUNCA: decidir política, editarse a sí mismo»*."""
    import inspect

    metodos = inspect.getsource(orq.Orquestador)
    assert "escribir_politica" not in metodos, "el ejecutor no toca la política"
    assert "NIVELES = " not in metodos, "la clasificación no vive en el ejecutor"
    assert "def nivel_de" not in metodos, "clasificar es de C6, no de C3"
    # y clasifica delegando, no reimplementando
    assert "nivel_de(" in inspect.getsource(orq.Orquestador.es_ejecutable)


def test_c3_el_orquestador_NO_puede_editarse_a_si_mismo(tmp_path):
    """La otra prohibición de `§5`. Un ejecutor que puede reescribir su propio código puede
    concederse cualquier cosa en la siguiente iteración."""
    d = _dir(tmp_path)
    o = orq.Orquestador(d)
    for prohibido in (pathlib.Path(orq.__file__), orq.RUTA_POLITICA, pathlib.Path(cp.__file__)):
        assert o.puede_tocar(prohibido) is False, f"{prohibido.name} debe ser intocable"
    assert o.puede_tocar(pathlib.Path("milestones/m3-entry/algo.md")) is True


def test_c3_cada_iteracion_queda_REGISTRADA_en_el_log(tmp_path):
    """`§5`: C3 = *«leer estado → elegir tarea ejecutable → invocar → **registrar**»*. Un ciclo que
    no deja rastro no es auditable, y F1 existe precisamente para que lo deje."""
    d = _dir(tmp_path)
    o = orq.Orquestador(d)
    o.ciclo(max_iteraciones=2)
    tipos = [e["tipo"] for e in cp.leer_eventos(d)]
    assert "ciclo_iniciado" in tipos and "ciclo_terminado" in tipos
    assert cp.verificar_integridad_log(d)["integro"] is True


# ======================================================== C4 · WORKERADAPTER (F2) --


def test_c4_el_sobre_lleva_PUNTEROS_no_la_historia_del_proyecto(tmp_path):
    """`§7.1`: *«El sobre no lleva la historia del proyecto. Lleva punteros»*, porque inyectarla *«por
    si acaso»* **es** el consumo de contexto que este DP quiere reducir."""
    w = orq.WorkerAdapter()
    sobre = w.sobre({"id": "T-042", "objetivo": "que X sea cierto", "accion": "ejecutar_pruebas"})
    for clave in ("tarea_id", "objetivo", "restricciones", "permisos", "presupuesto", "stop",
                  "criterio_de_finalizacion"):
        assert clave in sobre, f"falta {clave} del contrato de §7.1"
    texto = json.dumps(sobre, ensure_ascii=False)
    assert "CHECKPOINT-CONTINUIDAD" not in texto or len(texto) < 4000
    assert len(texto) < 4000, "el sobre debe ser mínimo suficiente, no un volcado"


def test_c4_el_sobre_incluye_las_restricciones_permanentes_del_CEO():
    w = orq.WorkerAdapter()
    sobre = w.sobre({"id": "T-1", "objetivo": "x", "accion": "ejecutar_pruebas"})
    restricciones = " ".join(sobre["restricciones"]).lower()
    for exigida in ("commit", "push"):
        assert exigida in restricciones, f"el sobre debe prohibir {exigida}"


def test_c4_NO_ejecuta_sin_permisos_declarados():
    """`§5`: C4 *«NUNCA: ejecutar sin permisos declarados»*. Con el catálogo `AUTO` vacío no hay
    ninguna acción con permisos, así que **no hay nada que el worker pueda ejecutar hoy**. Fail-closed."""
    w = orq.WorkerAdapter()
    # `match` preciso: hay DOS puertas que lanzan la misma excepción, y sin distinguirlas un
    # mutante que abría la primera sobrevivía porque la segunda seguía cerrando.
    with pytest.raises(orq.SinPermisosDeclarados, match="catalogo AUTO esta vacio|no tiene permisos"):
        w.invocar({"id": "T-1", "objetivo": "x", "accion": "accion_sin_politica"})


def test_c4_una_accion_NO_AUTO_no_recibe_permiso_alguno():
    """Los permisos salen de la política, no de la tarea. Si `permisos_de` los concediera sin mirar
    el nivel, quien redacta la tarea se estaría concediendo los suyos."""
    w = orq.WorkerAdapter()
    for accion in ("modificar_adr", "accion_desconocida", "cambiar_arquitectura"):
        permisos = w.permisos_de(accion)
        assert permisos["allowedTools"] == [], f"{accion} es {orq.nivel_de(accion)} y no lleva permisos"
        assert permisos["permission_mode"] == "plan"
        sobre = w.sobre({"id": "T", "objetivo": "x", "accion": accion})
        assert sobre["permisos"]["allowedTools"] == []


def test_c4_la_invocacion_se_CONSTRUYE_pero_no_se_lanza_sola():
    """**INV-9 aplicado al adaptador.** `§7.2` fija la orden exacta; construirla es el trabajo de C4.
    Lanzarla gasta dinero real y ejecuta un agente: eso exige una puerta explícita, no un efecto
    lateral de traducir una tarea."""
    w = orq.WorkerAdapter()
    orden = w.orden_de_invocacion({"id": "T-1", "objetivo": "x", "accion": "ejecutar_pruebas"},
                                  presupuesto_usd=0.50)
    assert orden[0] == "claude"
    unida = " ".join(orden)
    for flag in ("--output-format", "--session-id", "--max-budget-usd", "--permission-mode"):
        assert flag in unida, f"falta {flag} de §7.2"
    assert w.ejecuciones_reales == 0, "construir una orden no puede lanzarla"


def test_c4_el_session_id_se_DERIVA_de_la_tarea_y_es_estable():
    """`§7.2`: *«El `--session-id` derivado de la tarea es lo que hace la ejecución idempotente»*.

    **Reapuntada el 2026-08-30.** Pasaba el `id` como cadena y así fijaba lo *implementado* en vez de
    lo *acordado*: el `§13` dice `uuid5(namespace, tarea_id + sha256(sobre))`, y el sobre no
    participaba. Con esta prueba en verde, dos ejecuciones de la misma tarea con permisos o criterio
    distintos compartían identificador. La cobertura de esa mitad está en
    `test_red_idempotencia_13.py`."""
    w = orq.WorkerAdapter()
    tarea = {"id": "T-042", "accion": "ejecutar_pruebas"}
    uno = w.session_id(tarea)
    otro = orq.WorkerAdapter().session_id(tarea)
    assert uno == otro, "dos orquestadores deben derivar el mismo id para la misma tarea"
    assert uno != w.session_id({"id": "T-043", "accion": "ejecutar_pruebas"})


def test_c4_recoge_evidencia_ESTRUCTURADA_no_prosa():
    """C4 = *«recoger evidencia»*. Si el resultado fuese prosa, alguien tendría que interpretarla —y
    `INV-7` prohíbe reinterpretar: el plan se interpreta en un solo punto."""
    w = orq.WorkerAdapter()
    ev = w.leer_evidencia('{"ok": true, "tests": 12}')
    assert ev == {"ok": True, "tests": 12}
    with pytest.raises(orq.EvidenciaNoEstructurada):
        w.leer_evidencia("he terminado, todo bien")


# ================================================= LÍMITES DEL ALCANCE (F4 · F5) --


def test_F4_y_F5_NO_estan_construidas_y_el_modulo_no_finge_que_lo_esten():
    """**INV-9.** F4 exige `§25.2` (nivel `REVIEW`, que *«no existe hoy»* en ADR-0003) y F5 exige
    *«enmienda de D24»*. Ninguna consta aprobada, así que no hay revisor ni externo ni interno."""
    assert not hasattr(orq, "RevisorSubagente")
    assert not hasattr(orq, "RevisorExterno")
    assert orq.acciones_de_nivel("REVIEW") == ()


def test_el_orquestador_no_concede_ninguna_capacidad_a_AURORA():
    """`§0`: *«No es AURORA y no le concede ninguna capacidad»*.

    Se comprueba sobre los **imports reales**, no sobre el texto: el orquestador tiene que poder
    escribir «no tocar walking-skeleton/» en las restricciones que manda al worker, y prohibirle
    nombrar aquello que debe prohibir sería absurdo. Lo que no puede es **importarlo**, que es lo
    que crearía el acoplamiento."""
    import ast

    arbol = ast.parse(pathlib.Path(orq.__file__).read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    del arbol
    contaminados = [m for m in modulos if "aura" in m.lower() or "skeleton" in m.lower()]
    assert contaminados == [], f"el orquestador importa producto: {contaminados}"
    assert "control_plane" in modulos, "y sí depende del Control Plane, que es su autoridad (§9)"

    # y el producto tampoco aparece como destino de escritura en ninguna parte
    fuente = pathlib.Path(orq.__file__).read_text(encoding="utf-8")
    assert "walking-skeleton" not in fuente.replace('"no tocar walking-skeleton/"', "")
