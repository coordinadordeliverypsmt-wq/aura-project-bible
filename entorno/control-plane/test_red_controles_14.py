"""RED · los controles que el `§14` del DP declara y el bucle **todavía no ejerce**.

`§14` se titula *«los controles son estructurales, no confianza»*. Cuatro de sus filas describen un
control que hoy **no existe en el código del orquestador**, medido `[EJEC]` con `grep` sobre
`entorno/control-plane/*.py`:

| Fila del `§14` | Estado medido antes de este fichero |
|---|---|
| **Kill switch** — *«fichero centinela consultado en cada iteración»* | `ruta_centinela()` existe, pero es el centinela del **`flock`**, no un kill switch. `Orquestador.ciclo` no consulta ninguno |
| **Tarea repetitiva** — *«detección de tarea equivalente repetida (misma huella)»* | no hay ninguna huella de tarea. `huella` solo aparece en `conftest.py`, y es la del `estado.json` |
| **Medir mientras el árbol está mutado** — *«un lock que impide toda otra tarea»* | sin rastro. Es la trampa que el proyecto **ya pagó**: una auditoría midió el producto mientras `herramientas.mutar` tenía el árbol mutado y estuvo a un paso de reportar como rota la garantía `INV-9`, que estaba sana |
| **A12** — *«`COMPLETED` solo tras ejecutar el criterio mecánico, no tras la afirmación del Worker»* | `cerrar_tarea()` exige un veredicto verificado, pero **ese veredicto se calcula sobre la evidencia que el propio Worker enmarca**. Nada lo ata al `criterio_de_finalizacion` registrado antes de invocarlo |

La última es la grave, y es exactamente el hueco que el `§14.bis` dice haber cerrado por diseño:

> 1. El `criterio_de_finalizacion` lo fija quien crea la tarea, **nunca quien la ejecuta**, y se
>    escribe en el event log **antes** de invocar al Worker. Un criterio añadido o alterado después
>    es inválido.
> 2. El criterio debe referenciar una **CAPACIDAD REGISTRADA del catálogo**.
> 3. **Lo ejecuta el Orchestrator, no el Worker.** `COMPLETED` exige que ese comando pase; la
>    afirmación del Worker no basta **y no se consulta**.
> 4. Si el criterio no es expresable como comando, la tarea **no es `AUTO`**.

Diseñado en el `§14.bis`, declarado cumplido en el cierre de F2/F3, y **no implementado**. Es el
patrón `declarado ≠ real` en el sitio donde más caro sale: el control que impide la
auto-certificación del ejecutor.
"""

from __future__ import annotations


import agentes as ag
import control_plane as cp
import orquestador as orq
import pytest


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    """El `§14` obliga al ciclo a negarse mientras `herramientas.mutar` corre, y el arnes se lanza
    como `python -m herramientas.mutar`: al mutar, el propio arnes aparece en `/proc` y el bucle se
    niega en TODAS las pruebas, no solo en las que miden esa garantia.

    No es un falso positivo del control: es el control funcionando. Estas pruebas trabajan sobre un
    `tmp_path` sintetico y **no miden el arbol real**, asi que lo declaran. Las pruebas de la
    garantia lo vuelven a poner a `True` en su cuerpo, y ganan por ser mas especificas."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)



# `criterio_de_finalizacion` por defecto: desde que el bucle exige criterio mecanico para considerar
# ejecutable una tarea (`§14.bis` regla 4, cableada tras la auditoria del 2026-08-30), una tarea sin
# el no es AUTO. Antes lo era, y ese era el defecto: el aparato entero quedaba inerte.
def _tarea(directorio, ident="T-1", accion="ejecutar_pruebas", **extra):
    datos = {"id": ident, "accion": accion,
             "criterio_de_finalizacion": {"capacidad": accion}, **extra}
    cp.registrar_evento(directorio, "tarea_registrada", datos)
    return datos


# El cierre lo puede rechazar `agentes` —no hay efecto verificado— o el **motor unico** —hay criterio
# fijado y no consta superado—. Las dos son la misma garantia vista desde dos capas, y desde la
# auditoria del 2026-08-30 la regla vive solo en el motor: `cerrar_tarea` ya no la escribe por su
# cuenta. Lo que ninguna de las dos permite es que la tarea acabe en `COMPLETED`.
RECHAZOS = (ag.SinEvidencia, cp.CriterioNoVerificado, cp.TransicionInvalida)


# ==================================================== §14 · KILL SWITCH --
# «Fichero centinela consultado en CADA iteración. Replica el patron ya aprobado y en produccion
# (kill_switch.py:29-31), "mecanismo fuera de banda" segun Bible 5.3.»


def test_el_kill_switch_es_la_PRESENCIA_de_un_fichero_fuera_de_banda(tmp_path):
    """`kill_switch.py:31`: *«fuera de banda: el archivo tambien activa»*. Sin fichero, no hay
    parada; con fichero, la hay. No hace falta ninguna llamada al sistema ni ningún proceso vivo:
    ese es justamente el punto de un mecanismo fuera de banda."""
    assert not orq.parada_solicitada(tmp_path)
    orq.ruta_parada(tmp_path).write_text("porque lo digo yo", encoding="utf-8")
    assert orq.parada_solicitada(tmp_path)


def test_el_bucle_consulta_el_kill_switch_en_CADA_iteracion_no_solo_al_entrar(tmp_path):
    """`§14` dice *«en cada iteración»*, y la diferencia importa: un kill switch consultado solo al
    arrancar no detiene un ciclo que ya empezó, que es precisamente cuando hace falta detenerlo.

    Se activa **después** de que el ciclo haya arrancado, contando iteraciones."""
    _tarea(tmp_path, "T-1", objetivo="a")
    _tarea(tmp_path, "T-2", objetivo="b")
    o = orq.Orquestador(tmp_path)
    o.es_ejecutable = lambda _t: True
    o.worker.invocar = lambda _t: None
    iteraciones = {"n": 0}
    original = o.tareas_candidatas

    def espia():
        iteraciones["n"] += 1
        if iteraciones["n"] == 1:                       # ya dentro del bucle, no antes
            orq.ruta_parada(tmp_path).write_text("parada en caliente", encoding="utf-8")
        return original()

    o.tareas_candidatas = espia
    resultado = o.ciclo(max_iteraciones=5)
    assert iteraciones["n"] >= 1, "el ciclo tiene que haber entrado antes de que se pidiera parar"
    assert resultado["motivo"] == "kill switch activado"
    assert resultado["iteraciones"] < 5, "no puede haber agotado el tope: se le pidió parar"


def test_el_kill_switch_deja_rastro_en_el_log(tmp_path):
    """Bible 5.3 exige que la parada de emergencia sea **auditable**. Una parada que no se registra
    es indistinguible de un ciclo que no encontró trabajo."""
    orq.ruta_parada(tmp_path).write_text("emergencia", encoding="utf-8")
    orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert "parada_de_emergencia" in tipos


def test_el_kill_switch_es_REVERSIBLE(tmp_path):
    """*«parada de emergencia reversible»* (Bible 5.3 §5). Retirado el fichero, el ciclo vuelve a
    correr. Un interruptor que no se puede desactivar no es un interruptor: es una avería."""
    orq.ruta_parada(tmp_path).write_text("x", encoding="utf-8")
    assert orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)["motivo"] == "kill switch activado"
    orq.ruta_parada(tmp_path).unlink()
    assert orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)["motivo"] != "kill switch activado"


# ============================================ §14 · TAREA EQUIVALENTE REPETIDA --
# «Tarea repetitiva -> debe_ejecutar + idempotencia + deteccion de tarea equivalente repetida
# (misma huella).»


def test_dos_tareas_con_distinto_id_pero_mismo_trabajo_tienen_la_MISMA_huella():
    """La amenaza es *«tarea repetitiva»*, no *«id repetido»*. Si la huella incluyera el `id`, dos
    altas del mismo trabajo con ids distintos serían indistinguibles de trabajo nuevo — y volver a
    ejecutarlas es exactamente el bucle que el `§14` quiere impedir."""
    a = {"id": "T-1", "accion": "ejecutar_pruebas", "objetivo": "batería en verde",
         "ficheros_relevantes": ["a.py", "b.py"]}
    b = {**a, "id": "T-2"}
    assert orq.huella_de_tarea(a) == orq.huella_de_tarea(b)


def test_la_huella_cambia_si_cambia_el_trabajo():
    """Caso de control. Sin él, una huella constante pasaría la prueba anterior y no detectaría
    nada."""
    a = {"id": "T-1", "accion": "ejecutar_pruebas", "objetivo": "x", "ficheros_relevantes": ["a.py"]}
    assert orq.huella_de_tarea(a) != orq.huella_de_tarea({**a, "accion": "verificar_calidad"})
    assert orq.huella_de_tarea(a) != orq.huella_de_tarea({**a, "objetivo": "y"})
    assert orq.huella_de_tarea(a) != orq.huella_de_tarea({**a, "ficheros_relevantes": ["b.py"]})


def test_el_orden_de_los_ficheros_no_cambia_la_huella():
    """Dos altas de la misma tarea que listan los mismos ficheros en otro orden **son la misma
    tarea**. Si el orden contase, bastaría barajar la lista para reejecutar indefinidamente."""
    a = {"accion": "ejecutar_pruebas", "objetivo": "x", "ficheros_relevantes": ["a.py", "b.py"]}
    assert orq.huella_de_tarea(a) == orq.huella_de_tarea({**a, "ficheros_relevantes": ["b.py", "a.py"]})


def test_el_bucle_no_ejecuta_dos_veces_la_misma_huella_en_el_mismo_ciclo(tmp_path):
    """El control, ejercido: dos tareas equivalentes, un solo ciclo, **una sola ejecución**."""
    invocadas = []
    o = orq.Orquestador(tmp_path)
    o.worker.invocar = lambda tarea: invocadas.append(tarea["id"])
    o.es_ejecutable = lambda _tarea: True
    _tarea(tmp_path, "T-1", objetivo="lo mismo")
    _tarea(tmp_path, "T-2", objetivo="lo mismo")
    o.ciclo(max_iteraciones=5)
    assert len(invocadas) == 1, f"ejecutó trabajo equivalente dos veces: {invocadas}"


# ================================ §14 · EXCLUSION MUTUA CON EL ARNES DE MUTACION --
# «Para el orquestador NO es una preferencia: es un lock que impide toda otra tarea.»


def test_el_ciclo_se_NIEGA_a_correr_mientras_el_arbol_esta_mutado(tmp_path, monkeypatch):
    """La regla del CEO (2026-08-09): *«mientras corra el arnés, ni pruebas, ni demos, ni otro
    arnés»*. El árbol mutado **no contiene el código real**, así que cualquier medición hecha
    entonces mide un mutante y lo reporta como si fuera el producto. Ya ocurrió."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: True)
    resultado = orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    assert resultado["motivo"] == "arnés de mutación en curso"
    assert resultado["ejecutadas"] == 0


def test_sin_arnes_en_curso_el_ciclo_corre_con_normalidad(tmp_path, monkeypatch):
    """Caso de control: la exclusión mutua debe distinguir, no bloquear siempre."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    assert orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)["motivo"] != "arnés de mutación en curso"


def test_la_exclusion_mutua_deja_rastro(tmp_path, monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: True)
    orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    assert "medicion_rechazada_por_mutacion" in [e["tipo"] for e in cp.leer_eventos(tmp_path)]


# ============================================ A12 · EL CRITERIO ES MECANICO --
# «COMPLETED solo tras ejecutar el criterio mecanico, no tras la afirmacion del Worker.»


def test_un_criterio_que_no_nombra_una_CAPACIDAD_REGISTRADA_es_invalido():
    """`§14.bis` regla 2. Y las capacidades salen del **catálogo de la política**, no de una lista
    escrita aquí: si viviesen en el código del orquestador, ampliarlas no exigiría acta."""
    assert orq.criterio_valido({"capacidad": "ejecutar_pruebas"})
    assert not orq.criterio_valido({"capacidad": "rm -rf /"})
    assert not orq.criterio_valido({"capacidad": "pytest"}), "se nombra por el resultado, no por la herramienta"
    assert not orq.criterio_valido({"prosa": "que quede bonito"})
    assert not orq.criterio_valido("ejecutar_pruebas")


def test_las_capacidades_verificables_SALEN_de_la_politica_no_del_codigo():
    """Caso de control de la regla anterior: si alguien añade una capacidad a mano en el módulo, esta
    prueba lo detecta."""
    assert orq.capacidades_verificables() == orq.acciones_de_nivel("AUTO")


def test_una_tarea_cuyo_criterio_no_es_mecanico_NO_puede_ser_AUTO():
    """`§14.bis` regla 4: *«Una tarea cuyo éxito solo puede juzgarse leyendo prosa no es
    automatizable, y pretender lo contrario es fabricar la apariencia de verificación»*."""
    assert not orq.admite_nivel_auto({"accion": "ejecutar_pruebas",
                                      "criterio_de_finalizacion": {"prosa": "que quede bien"}})
    assert orq.admite_nivel_auto({"accion": "ejecutar_pruebas",
                                  "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}})


def test_el_criterio_se_fija_ANTES_y_queda_en_el_log(tmp_path):
    """`§14.bis` regla 1: *«se escribe en el event log antes de invocar al Worker»*."""
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    fijados = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "criterio_fijado"]
    assert len(fijados) == 1
    assert fijados[0]["datos"]["criterio"]["capacidad"] == "ejecutar_pruebas"


def test_un_criterio_ALTERADO_despues_invalida_la_tarea(tmp_path):
    """`§14.bis` regla 1: *«Un criterio añadido o alterado después es inválido»*. Es el vector
    obvio: ejecutar cualquier cosa y después escribir el criterio que esa cosa cumple."""
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "verificar_calidad"})
    with pytest.raises(orq.CriterioAlterado):
        orq.criterio_de(tmp_path, "T-1")


def test_refijar_el_MISMO_criterio_no_lo_invalida(tmp_path):
    """Idempotencia: reintentar el alta de una tarea no puede invalidarla. Lo prohibido es
    **cambiarlo**, no repetirlo."""
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    assert orq.criterio_de(tmp_path, "T-1")["criterio"]["capacidad"] == "ejecutar_pruebas"


def test_la_verificacion_del_criterio_NO_RECIBE_la_afirmacion_del_worker(tmp_path):
    """`§14.bis` regla 3: *«la afirmación del Worker no basta **y no se consulta**»*.

    La garantía no es de comportamiento: es que **el parámetro no existe**. Un argumento que no se
    puede pasar no se puede ponderar mal más adelante — la misma forma de garantía que el `Veredicto`
    sin campo `autoriza`."""
    import inspect
    firma = set(inspect.signature(orq.verificar_criterio).parameters)
    for prohibido in ("evidencia", "afirmacion", "salida_del_worker", "resultado_del_worker"):
        assert prohibido not in firma, f"el Worker no puede influir: sobra el parámetro {prohibido!r}"


def test_el_criterio_lo_ejecuta_el_ORQUESTADOR_contra_el_arbol(tmp_path):
    """`§14.bis` regla 3: *«Lo ejecuta el Orchestrator, no el Worker, tras la invocación y contra el
    árbol resultante»*."""
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    ejecutadas = []

    def ejecutor(criterio):
        ejecutadas.append(criterio["capacidad"])
        return 0

    veredicto = orq.verificar_criterio(tmp_path, "T-1", ejecutor)
    assert ejecutadas == ["ejecutar_pruebas"], "el orquestador debe ejecutar la capacidad él mismo"
    assert veredicto["verificado"] is True
    assert veredicto["origen"] == "criterio_mecanico"


def test_si_la_capacidad_falla_el_veredicto_es_NO_VERIFICADO(tmp_path):
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    veredicto = orq.verificar_criterio(tmp_path, "T-1", lambda _c: 1)
    assert veredicto["verificado"] is False
    assert veredicto["resultado"] == "NO_VERIFICADO"


# ------------------------------------ A12, el criterio literal: FALSEAR LA EVIDENCIA --


def test_A12_falsear_la_evidencia_del_worker_NO_completa_la_tarea(tmp_path):
    """**El criterio A12, literal**: *«falsear la evidencia del Worker y comprobar que la tarea NO se
    completa»*.

    El Worker devuelve una evidencia que él mismo enmarca y que se comprueba sola —el patrón
    `salida_contiene` con el patrón dentro de la salida—. `verificar_efecto` la da por buena, y es
    correcto: comprueba lo que le dan. Lo que **no** puede pasar es que eso cierre la tarea, porque
    la tarea tiene un criterio mecánico fijado antes y ese veredicto no procede de él."""
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})

    falsa = ag.verificar_efecto({"tipo": "salida_contiene", "patron": "TODO OK", "salida": "TODO OK"},
                                afirmacion="he terminado, todo pasa")
    assert falsa["verificado"] is True, "la evidencia autofabricada se comprueba a sí misma..."

    with pytest.raises(RECHAZOS):                       # ...y aun así no cierra nada
        ag.cerrar_tarea(tmp_path, "T-1", falsa, autoridad="orquestador")
    assert cp.proyectar(tmp_path)["tareas"]["T-1"]["estado"] != "COMPLETED"


def test_solo_el_veredicto_del_criterio_FIJADO_cierra_la_tarea(tmp_path):
    """Caso de control de A12: el mecanismo distingue, no rechaza siempre.

    La tarea pasa por `WORKING` porque la tabla gobernada de F1 no admite saltar de
    `WAITING_FOR_NEXT_TASK` a `COMPLETED`. Son dos controles distintos y ambos siguen puestos."""
    _tarea(tmp_path, "T-1")
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    veredicto = orq.verificar_criterio(tmp_path, "T-1", lambda _c: 0)
    assert ag.cerrar_tarea(tmp_path, "T-1", veredicto, autoridad="orquestador") == "COMPLETED"


def test_un_veredicto_de_OTRA_tarea_no_sirve_para_cerrar_esta(tmp_path):
    """El veredicto mecánico va atado a **su** criterio. Sin esa atadura bastaría con verificar la
    tarea más fácil del ciclo y reutilizar su veredicto para todas."""
    _tarea(tmp_path, "T-1")
    _tarea(tmp_path, "T-2")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    orq.fijar_criterio(tmp_path, "T-2", {"capacidad": "verificar_calidad"})
    ajeno = orq.verificar_criterio(tmp_path, "T-1", lambda _c: 0)
    with pytest.raises(RECHAZOS):
        ag.cerrar_tarea(tmp_path, "T-2", ajeno, autoridad="orquestador")


def test_una_tarea_SIN_criterio_fijado_no_se_cierra_por_la_via_mecanica(tmp_path):
    """*«Si el criterio no es expresable como comando, la tarea no es AUTO»* (regla 4). Sin criterio
    no hay cierre automático posible: sube a `REVIEW` o a `HUMAN`, y esa vía exige un revisor o un
    acto humano. Lo que no puede es cerrarse sola."""
    _tarea(tmp_path, "T-SIN")
    inventado = {"verificado": True, "resultado": "VERIFIED", "origen": "criterio_mecanico",
                 "huella_criterio": "0" * 64}
    with pytest.raises(RECHAZOS):
        ag.cerrar_tarea(tmp_path, "T-SIN", inventado, autoridad="orquestador")


def test_la_huella_del_criterio_no_se_puede_falsificar_a_ojo(tmp_path):
    """Si la atadura fuese el nombre de la capacidad, copiarla sería trivial. Es un `sha256` del
    criterio canonicalizado, y el criterio vive en un log encadenado."""
    _tarea(tmp_path, "T-1")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    huella = orq.criterio_de(tmp_path, "T-1")["huella"]
    assert len(huella) == 64 and huella != "ejecutar_pruebas"
    esperada = orq.huella_de_criterio({"capacidad": "ejecutar_pruebas"})
    assert huella == esperada
    assert huella != orq.huella_de_criterio({"capacidad": "verificar_calidad"})
    # y el veredicto la lleva: sin esto, el veredicto no queda atado a SU criterio
    veredicto = orq.verificar_criterio(tmp_path, "T-1", lambda _c: 0)
    assert veredicto["huella_criterio"] == huella


def test_un_veredicto_FABRICADO_A_MANO_no_cierra_aunque_lleve_la_huella_buena(tmp_path):
    """**Reescrita el 2026-08-30: la versión anterior era decorativa.** Se llamaba
    `..._pero_otro_origen_no_cierra` y afirmaba que el campo `origen` del veredicto protegía algo.
    **No protege nada: ningún código lo lee.** Lo encontró la segunda auditoría independiente con un
    `grep` — se escribe en `orquestador.py` y no se consulta en ninguna parte.

    El rechazo que la prueba observaba venía enteramente de otro sitio, y ese sí es la garantía: el
    motor no mira el diccionario que le pasan, mira **el log**. Un veredicto fabricado a mano no
    cierra porque **no existe ningún evento `criterio_verificado`**, lleve la huella que lleve. Eso
    es lo que ahora se comprueba, y el `origen` se deja como dato de auditoría, sin fingir que
    autoriza.

    El caso importa: el criterio vive en un log legible, así que copiar su huella está al alcance de
    quien pueda leerlo."""
    _tarea(tmp_path, "T-1")
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    huella_buena = orq.criterio_de(tmp_path, "T-1")["huella"]

    for disfraz in ("criterio_mecanico", "worker", "ceo"):
        fabricado = {"verificado": True, "resultado": "VERIFIED", "origen": disfraz,
                     "huella_criterio": huella_buena}
        with pytest.raises(RECHAZOS):
            ag.cerrar_tarea(tmp_path, "T-1", fabricado, autoridad="orquestador")
        assert cp.proyectar(tmp_path)["tareas"]["T-1"]["estado"] != "COMPLETED"

    assert cp.criterio_superado(tmp_path, "T-1") is False, (
        "ningún veredicto fabricado deja rastro en el log, que es lo único que el motor consulta")


def test_refijar_el_mismo_criterio_deja_entradas_IDENTICAS(tmp_path):
    """Demostración por ejecución de que `fijados[0]` y `fijados[-1]` son intercambiables **cuando
    `criterio_de` no lanza**: si las huellas difieren, salta `CriterioAlterado` antes; y si no
    difieren, los registros son iguales campo a campo. Es la prueba que sostiene que el mutante
    `C14-M16` (`return fijados[-1]`) es EQUIVALENTE, en vez de darlo por supuesto."""
    _tarea(tmp_path, "T-1")
    for _ in range(3):
        orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    fijados = [e["datos"] for e in cp.leer_eventos(tmp_path)
               if e["tipo"] == "criterio_fijado" and e["datos"]["id"] == "T-1"]
    assert len(fijados) == 3
    assert fijados[0] == fijados[-1], "mismo criterio ⇒ registros indistinguibles"
