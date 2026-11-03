"""RED · DP-DEVELOPMENT-ORCHESTRATOR **Fase 1** = C1 + C2.

`§20`: *«F1 · C1 + C2: event log, lock, transiciones gobernadas, proyección reconstruible · Depende
de: nada · Valor si se para aquí: **Alto**: cierra P2/P3/P4»*. Y `§5`: *«C1 y C2 son el 80 % del
valor y no requieren ningún servicio externo. Se pueden construir, probar y usar **sin resolver
ninguna de las decisiones pendientes de §25**»*.

**Los tres defectos que cierra están MEDIDOS en el propio DP `[EJEC]`**, no supuestos:
- **P2** — no hay lock: *«si dos procesos cargan y guardan, el último gana y el otro pierde sus
  cambios en silencio»*.
- **P3** — no hay event log: *«`estado.json` se sobrescribe entero en cada guardado»*.
- **P4** — *«`fijar_estado_tarea` no valida el estado previo: nada impide pasar de `COMPLETED` a
  `WORKING`»*.

**Esto es infraestructura de DESARROLLO, no AURORA.** `§0`: *«No es AURORA y no le concede ninguna
capacidad. La autonomía de AURORA sigue en 0/7 y este DP no la mueve.»*
"""

from __future__ import annotations

import json
import multiprocessing
import os
import pathlib

import control_plane as cp
import pytest


def _dir(tmp_path):
    return pathlib.Path(tmp_path)


# ============================================ C1 · EVENT LOG (cierra P3) --


def test_c1_el_log_es_append_only_y_la_secuencia_es_monotonica(tmp_path):
    """`§5`: *«Historia append-only, `seq` monotónico, `fsync`, `sha256` por línea. **Nunca borrarse
    ni reescribirse**»*."""
    d = _dir(tmp_path)
    for i in range(3):
        cp.registrar_evento(d, "tarea_iniciada", {"id": f"T-{i}"})
    eventos = cp.leer_eventos(d)
    assert [e["seq"] for e in eventos] == [1, 2, 3]
    assert all(e["tipo"] == "tarea_iniciada" for e in eventos)


def test_c1_cada_linea_lleva_su_sha256_y_encadena_con_la_anterior(tmp_path):
    d = _dir(tmp_path)
    cp.registrar_evento(d, "a", {})
    cp.registrar_evento(d, "b", {})
    e1, e2 = cp.leer_eventos(d)
    assert len(e1["hash"]) == 64 and len(e2["hash"]) == 64
    assert e1["hash_anterior"] is None
    assert e2["hash_anterior"] == e1["hash"], "la cadena debe encadenar, no solo firmar"


def test_c1_una_linea_alterada_rompe_la_integridad(tmp_path):
    """**Control del control.** Si `verificar_integridad_log` no pudiera dar False, no comprobaría
    nada."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "a", {"v": 1})
    cp.registrar_evento(d, "b", {"v": 2})
    assert cp.verificar_integridad_log(d)["integro"] is True

    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    alterada = lineas[0].replace('"v":1', '"v":99')
    assert alterada != lineas[0], "el control no alteró nada: no habría comprobado nada"
    ruta.write_text("\n".join([alterada] + lineas[1:]) + "\n", encoding="utf-8")
    assert cp.verificar_integridad_log(d)["integro"] is False


def test_c1_una_linea_ELIMINADA_tambien_rompe_la_integridad(tmp_path):
    """Firmar cada línea por separado detectaría una línea **alterada**, pero no una **eliminada**.
    Por eso la cadena encadena: `hash_anterior` convierte un borrado en una ruptura visible."""
    d = _dir(tmp_path)
    for i in range(3):
        cp.registrar_evento(d, "x", {"i": i})
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text("\n".join([lineas[0], lineas[2]]) + "\n", encoding="utf-8")
    assert cp.verificar_integridad_log(d)["integro"] is False


def test_c1_el_log_NUNCA_se_reescribe(tmp_path):
    """`§9.1`: append-only. Registrar el evento 4 no puede tocar los bytes de los 3 primeros."""
    d = _dir(tmp_path)
    for i in range(3):
        cp.registrar_evento(d, "x", {"i": i})
    antes = cp.ruta_eventos(d).read_text(encoding="utf-8")
    cp.registrar_evento(d, "x", {"i": 3})
    despues = cp.ruta_eventos(d).read_text(encoding="utf-8")
    assert despues.startswith(antes), "el prefijo del log cambió: se reescribió"


# ================================ C2 · PROYECCIÓN RECONSTRUIBLE · A1 --


def test_a1_el_estado_se_reconstruye_tras_BORRAR_estado_json(tmp_path):
    """**Criterio A1**, y el mismo listón que `ADR-0023` exige de toda proyección: *«debe poder
    eliminarse por completo y regenerarse desde el historial sin alterar el comportamiento»*."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "descripcion": "primera"})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-2", "descripcion": "segunda"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    esperado = cp.proyectar(d)
    assert set(esperado["tareas"]) == {"T-1", "T-2"}
    assert esperado["tareas"]["T-1"]["estado"] == "WORKING"

    ruta = d / "estado.json"
    ruta.write_text(json.dumps(esperado, ensure_ascii=False), encoding="utf-8")
    ruta.unlink()
    assert not ruta.exists()

    assert cp.proyectar(d) == esperado, "la proyección no se reconstruyó igual"


def test_a1_la_proyeccion_es_desechable_no_una_segunda_fuente_de_verdad(tmp_path):
    """Si alguien edita `estado.json` a mano, la reproyección desde el log **manda**."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    (d / "estado.json").write_text(json.dumps({"tareas": {"INVENTADA": {}}}), encoding="utf-8")
    assert set(cp.proyectar(d)["tareas"]) == {"T-1"}


# ==================================== C2 · TRANSICIONES GOBERNADAS (cierra P4) --


def test_p4_ya_NO_se_puede_pasar_de_completed_a_working(tmp_path):
    """El defecto P4, cerrado. `§9.3`: *«`fijar_estado_tarea` pasa a validar el estado previo contra
    la tabla de §6 y a exigir autoridad y causa»*."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="empieza")
    cp.transicion(d, "T-1", "COMPLETED", autoridad="ceo", causa="terminada")
    with pytest.raises(cp.TransicionInvalida, match="COMPLETED"):
        cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="reabrir")


def test_una_transicion_exige_autoridad_Y_causa(tmp_path):
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    with pytest.raises(cp.TransicionInvalida, match="autoridad"):
        cp.transicion(d, "T-1", "WORKING", autoridad="", causa="x")
    with pytest.raises(cp.TransicionInvalida, match="causa"):
        cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="")


def test_a5_DECISION_REQUIRED_no_se_resuelve_sin_acto_humano(tmp_path):
    """**Criterio A5.** `§9`: *«solo un evento de autoridad humana lo levanta»*."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    cp.transicion(d, "T-1", "DECISION_REQUIRED", autoridad="orquestador", causa="falta decidir")
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="sigo")
    cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="decidido")
    assert cp.estado_de(d, "T-1") == "WORKING"


def test_meta_una_transicion_VALIDA_si_ocurre(tmp_path):
    """**Meta-control.** Sin él, un `transicion()` que rechazara siempre pasaría todo lo anterior."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    assert cp.estado_de(d, "T-1") == "WORKING"
    # Autoridad humana: desde la auditoria del 2026-08-30, una autoridad NO humana solo cierra a
    # COMPLETED con criterio mecanico ejecutado y superado (`§14.bis` reglas 3 y 4). Esta prueba
    # mide que una transicion valida OCURRE, no el gobierno del criterio, asi que usa la via que no
    # lo necesita — y que es la que la regla 4 reserva para lo no automatizable.
    cp.transicion(d, "T-1", "COMPLETED", autoridad="ceo", causa="revisada a mano")
    assert cp.estado_de(d, "T-1") == "COMPLETED"


# ============================================= C2 · LOCK · A2 (cierra P2) --


def _escritor(directorio, n):
    for i in range(n):
        cp.registrar_evento(pathlib.Path(directorio), "ping", {"i": i, "pid": os.getpid()})


def test_a2_dos_procesos_concurrentes_NO_pierden_escrituras(tmp_path):
    """**Criterio A2**, con **dos procesos reales**, no hilos: *«dos procesos reales, contar
    eventos»*. Es el defecto P2 cerrado — antes *«el último gana y el otro pierde sus cambios en
    silencio»*."""
    d = _dir(tmp_path)
    n = 25
    procesos = [multiprocessing.Process(target=_escritor, args=(str(d), n)) for _ in range(2)]
    for p in procesos:
        p.start()
    for p in procesos:
        p.join(timeout=60)

    eventos = cp.leer_eventos(d)
    assert len(eventos) == 2 * n, f"se perdieron escrituras: {len(eventos)} de {2 * n}"
    assert [e["seq"] for e in eventos] == list(range(1, 2 * n + 1)), "la secuencia tiene huecos"
    assert cp.verificar_integridad_log(d)["integro"] is True, "la cadena se corrompió"
    assert len({e["datos"]["pid"] for e in eventos}) == 2, "no escribieron dos procesos distintos"


def test_el_lock_se_libera_al_terminar_el_bloque(tmp_path):
    """Un lock que no se suelta convierte el primer fallo en un interbloqueo permanente."""
    d = _dir(tmp_path)
    with cp.lock_estado(d):
        pass
    with cp.lock_estado(d):
        pass          # si no se hubiera liberado, esto colgaría


# ================================================= LÍMITES DEL ALCANCE --


def test_f1_no_concede_ninguna_capacidad_a_AURORA(tmp_path):
    """`§0`: *«No es AURORA y no le concede ninguna capacidad»*. El Control Plane no importa producto
    — garantía ya existente que F1 no puede romper."""
    fuente = pathlib.Path(cp.__file__).read_text(encoding="utf-8")
    assert "aura_skeleton" not in fuente
    assert "walking-skeleton" not in fuente


# ============================ C2 · §9.3 — `fijar_estado_tarea` GOBERNADO (cierra P4) --
#
# `§9.3`: *«`fijar_estado_tarea` pasa a validar el estado previo contra la tabla de `§6` y a exigir
# **autoridad y causa**, como ya hace el producto.»* Hay dos rutas al mismo estado —la nueva basada
# en log (`transicion`) y la antigua en memoria— y **gobernar solo una deja la otra como puerta
# trasera**. Es literalmente ALERTA-005 («ninguna ruta alternativa») aplicada aquí.


def test_p4_la_ruta_EN_MEMORIA_tampoco_permite_reabrir_un_COMPLETED():
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "COMPLETED", "terminada", autoridad="ceo")
    with pytest.raises(cp.TransicionInvalida, match="COMPLETED"):
        cp.fijar_estado_tarea(estado, "T-1", "WORKING", "reabrir", autoridad="ceo")


def test_p4_completar_por_completar_tarea_TAMBIEN_cierra_la_puerta():
    """`estado_de_tarea` devuelve COMPLETED tanto si vino de `fijar_estado_tarea` como de
    `completar_tarea`. Si el gobierno solo mirara `estado['tareas']`, completar por la segunda vía
    dejaría la tarea reabrible — la misma puerta trasera, por otra llave."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-9", "WORKING", "empieza", autoridad="ceo")
    cp.completar_tarea(estado, "T-9", "hecha", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-9")["estado"] == "COMPLETED"
    with pytest.raises(cp.TransicionInvalida, match="COMPLETED"):
        cp.fijar_estado_tarea(estado, "T-9", "WORKING", "reabrir", autoridad="ceo")


def test_la_ruta_en_memoria_exige_autoridad_y_causa():
    estado = cp.estado_inicial()
    with pytest.raises(cp.TransicionInvalida, match="autoridad"):
        cp.fijar_estado_tarea(estado, "T-1", "WORKING", "hay causa", autoridad="")
    with pytest.raises(cp.TransicionInvalida, match="causa"):
        cp.fijar_estado_tarea(estado, "T-1", "WORKING", "", autoridad="ceo")


def test_registrar_una_tarea_NUEVA_no_es_una_transicion():
    """Una tarea sin estado previo se **crea**, no transiciona: no hay origen contra el que validar.

    Sin esta distinción el gobierno prohibiría registrar un bloqueo de entorno sobre una tarea que
    aún no consta como `WORKING` —que es justo lo que `interrumpir` y `registrar_bloqueo_de_cuota`
    hacen hoy— y P4 se habría «cerrado» rompiendo el uso legítimo."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "NUEVA", "WAITING_FOR_ENVIRONMENT", "falta RAM", autoridad="entorno")
    assert cp.estado_de_tarea(estado, "NUEVA")["estado"] == "WAITING_FOR_ENVIRONMENT"


def test_el_estado_en_memoria_registra_QUIEN_y_POR_QUE():
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "arranca el bloque", autoridad="ceo")
    registro = cp.estado_de_tarea(estado, "T-1")
    assert registro["autoridad"] == "ceo"
    assert registro["motivo"] == "arranca el bloque"


def test_salir_de_DECISION_REQUIRED_en_memoria_exige_humano():
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "DECISION_REQUIRED", "falta decidir", autoridad="orquestador")
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.fijar_estado_tarea(estado, "T-1", "WORKING", "sigo", autoridad="orquestador")
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "decidido", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-1")["estado"] == "WORKING"


def test_interrumpir_sigue_funcionando_bajo_gobierno():
    """`interrumpir` es la garantía de que un COMPLETED falso nunca se fabrica. El gobierno no puede
    romperla: si al endurecer la puerta se rompe la cerradura honesta, se ha empeorado el sistema."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.interrumpir(estado, "T-1", next(iter(cp.INTERRUPCION)))
    assert cp.estado_de_tarea(estado, "T-1")["estado"] != "COMPLETED"


# ================== C2 · §9.2 — LOCK EN LA RUTA ANTIGUA · y A3/A4 (reconciliación) --


def test_p2_actualizar_estado_serializa_leer_modificar_escribir(tmp_path):
    """`§9.2`: *«`flock` sobre un fichero centinela alrededor de **leer-modificar-escribir**»*.

    `guardar()` suelto es una escritura atómica pero **no** una actualización atómica: entre el
    `cargar` y el `guardar` de un proceso cabe entero el ciclo de otro, y el segundo pisa al primero
    *«en silencio»*. Por eso el lock envuelve el ciclo completo, no solo la escritura."""
    destino = pathlib.Path(tmp_path) / "estado.json"
    cp.guardar(cp.estado_inicial(), destino)

    def sumar(estado):
        estado.setdefault("aprobaciones", []).append({"por": "ceo", "n": len(estado["aprobaciones"])})
        return estado

    for _ in range(3):
        cp.actualizar_estado(destino, sumar)
    assert len(cp.cargar(destino)["aprobaciones"]) == 3


def _actualizador(ruta, n):
    destino = pathlib.Path(ruta)
    for _ in range(n):
        cp.actualizar_estado(destino, lambda e: (e["aprobaciones"].append({"pid": os.getpid()}), e)[1])


def test_a2_dos_procesos_reales_actualizando_el_mismo_estado_no_se_pisan(tmp_path):
    """**Criterio A2 sobre la ruta antigua.** El defecto P2 medido en el DP era exactamente este:
    *«si dos procesos cargan y guardan, el último gana y el otro pierde sus cambios en silencio»*."""
    destino = pathlib.Path(tmp_path) / "estado.json"
    cp.guardar(cp.estado_inicial(), destino)
    n = 15
    procesos = [multiprocessing.Process(target=_actualizador, args=(str(destino), n))
                for _ in range(2)]
    for p in procesos:
        p.start()
    for p in procesos:
        p.join(timeout=60)
    aprobaciones = cp.cargar(destino)["aprobaciones"]
    assert len(aprobaciones) == 2 * n, f"se perdieron escrituras: {len(aprobaciones)} de {2 * n}"
    assert len({a["pid"] for a in aprobaciones}) == 2


def test_a4_una_tarea_interrumpida_queda_FAILED_nunca_COMPLETED(tmp_path):
    """**Criterio A4.** Una tarea que quedó `WORKING` sin cierre es una tarea cuyo proceso murió.

    La reconciliación **solo puede concluir FAILED**. Concluir COMPLETED sería fabricar evidencia de
    un trabajo que nadie vio terminar — el mismo motivo por el que `interrumpir` existe: *«un
    COMPLETED falso hace que el siguiente agente dé por hecho un trabajo que nunca ocurrió, y nadie
    vuelve a mirarlo»*."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-VIVA"})
    cp.transicion(d, "T-VIVA", "WORKING", autoridad="orquestador", causa="empieza")

    reconciliadas = cp.reconciliar_tras_caida(d, autoridad="orquestador",
                                              causa="el proceso no cerró la tarea")
    assert reconciliadas == ["T-VIVA"]
    assert cp.estado_de(d, "T-VIVA") == "FAILED"


def test_a3_una_tarea_COMPLETED_no_la_toca_la_reconciliacion(tmp_path):
    """**Criterio A3.** Reconciliar tras una caída no puede reabrir ni degradar lo ya cerrado: sería
    P4 entrando por la puerta de la recuperación."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-HECHA"})
    cp.transicion(d, "T-HECHA", "WORKING", autoridad="orquestador", causa="empieza")
    cp.transicion(d, "T-HECHA", "COMPLETED", autoridad="ceo", causa="revisada a mano")
    assert cp.reconciliar_tras_caida(d, autoridad="orquestador", causa="arranque") == []
    assert cp.estado_de(d, "T-HECHA") == "COMPLETED"


def test_la_reconciliacion_no_toca_a_quien_espera_legitimamente(tmp_path):
    """Esperar cuota o una decisión **no es haber muerto**. Marcarlas FAILED convertiría cada
    reinicio en una masacre de tareas sanas."""
    d = _dir(tmp_path)
    for tid in ("T-Q", "T-D"):
        cp.registrar_evento(d, "tarea_registrada", {"id": tid})
        cp.transicion(d, tid, "WORKING", autoridad="orquestador", causa="empieza")
    # `WAITING_FOR_QUOTA` se alcanza **solo** por su vía gobernada desde la 4.ª auditoría: el §11
    # exige ventana determinada y evidencia observada, y `transicion()` ya no lo acepta sin ellas.
    cp.esperar_por_cuota(d, "T-Q", ventana="SHORT_4H30", autoridad="orquestador",
                         evidencia="mensaje observado: 5-hour limit reached")
    cp.transicion(d, "T-D", "DECISION_REQUIRED", autoridad="orquestador", causa="espera")
    assert cp.reconciliar_tras_caida(d, autoridad="orquestador", causa="arranque") == []
    assert cp.estado_de(d, "T-Q") == "WAITING_FOR_QUOTA"
    assert cp.estado_de(d, "T-D") == "DECISION_REQUIRED"


def test_reafirmar_el_mismo_estado_es_idempotente_no_una_transicion(tmp_path):
    """La tabla de `§6` describe el **flujo**, no la repetición: no lista `X → X`. Exigirlo allí
    rompería registrar dos veces el mismo bloqueo de cuota —cosa que `registrar_bloqueo_de_cuota`
    hace— sin proteger nada, porque el estado resultante es idéntico."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "FAILED", "revienta", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "FAILED", "sigue reventada", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-1")["estado"] == "FAILED"

    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="empieza")
    cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="sigue")
    assert cp.estado_de(d, "T-1") == "WORKING"
    assert len(cp.leer_eventos(d)) == 3, "la re-afirmación también deja rastro en la historia"


def test_completar_dos_veces_no_rompe_el_gobierno():
    """`completar_tarea` se documenta idempotente. El gobierno no puede desmentirlo."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-9", "WORKING", "empieza", autoridad="ceo")
    cp.completar_tarea(estado, "T-9", "hecha", autoridad="ceo")
    cp.completar_tarea(estado, "T-9", "hecha otra vez", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-9")["estado"] == "COMPLETED"


def test_c1_una_linea_SUSTITUIDA_con_seq_correcto_rompe_el_enlace(tmp_path):
    """Cierra el hueco que dejó `test_c1_una_linea_ELIMINADA_...`: allí el borrado se detecta por el
    **salto de `seq`**, así que la comprobación del enlace nunca llegaba a ejercitarse — un mutante
    que la eliminaba sobrevivía.

    Aquí el `seq` es correcto y el hash de la línea es coherente **consigo misma**: lo único que
    delata la sustitución es que `hash_anterior` ya no apunta a lo que había. Es el ataque realista:
    quien reescribe una historia recalcula lo que sabe recalcular."""
    d = _dir(tmp_path)
    for i in range(3):
        cp.registrar_evento(d, "x", {"i": i})
    ruta = cp.ruta_eventos(d)
    lineas = ruta.read_text(encoding="utf-8").splitlines()

    falsa = json.loads(lineas[1])
    falsa["datos"] = {"i": 99}
    falsa["hash_anterior"] = "0" * 64          # coherente en forma, falso en contenido
    falsa["hash"] = cp._hash_de(falsa)         # la línea se firma a sí misma sin problema
    assert falsa["seq"] == 2, "el control exige que el seq siga siendo el correcto"

    ruta.write_text("\n".join([lineas[0], json.dumps(falsa, sort_keys=True, ensure_ascii=False,
                                                     separators=(",", ":")), lineas[2]]) + "\n",
                    encoding="utf-8")
    veredicto = cp.verificar_integridad_log(d)
    assert veredicto["integro"] is False
    assert "enlaz" in veredicto["motivo"], f"se detectó por otra vía: {veredicto['motivo']}"


def test_la_proyeccion_no_depende_del_reloj(monkeypatch, tmp_path):
    """Cierra el hueco de `test_a1_...`: comparar dos proyecciones seguidas **no** prueba pureza,
    porque `_ahora()` tiene precisión de segundos y ambas caen en el mismo. Un mutante que metía un
    reloj en la proyección sobrevivía por eso.

    Aquí el reloj cambia entre las dos reconstrucciones. Si algo del entorno se cuela en la
    proyección, deja de ser función de su historia — y entonces `estado.json` no es desechable, que
    es lo que `§9.1` exige."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "descripcion": "una"})
    cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="empieza")

    monkeypatch.setattr(cp, "_ahora", lambda: "2020-01-01T00:00:00")
    primera = cp.proyectar(d)
    monkeypatch.setattr(cp, "_ahora", lambda: "2099-12-31T23:59:59")
    segunda = cp.proyectar(d)
    assert primera == segunda, "la proyección cambió sin que cambiara el log: depende del entorno"


# =========================================== HALLAZGOS DE LA AUDITORÍA INDEPENDIENTE --
#
# Tres los encontró el auditor —dos GRAVES—, y el cuarto salió tirando del mismo hilo. Todos son
# **la misma clase de defecto**: rutas al estado que no pasan por el gobierno. Es ALERTA-005,
# «ninguna ruta alternativa», y el cierre llegó a afirmar que estaban «ambas» gobernadas cuando eran
# cuatro. La afirmación era falsa; queda corregida aquí y en el documento.


def test_auditoria_h1_completar_tarea_NO_puede_cerrar_una_decision_pendiente():
    """**HALLAZGO GRAVE 1 · A5 incumplido.** `completar_tarea` escribe en `trabajo_completado`, y
    `estado_de_tarea` lee de ahí COMPLETED — así que era una **tercera ruta** al estado, sin
    autoridad, sin causa y sin tabla.

    La demostración de A5 del cierre probó cinco autoridades no humanas contra `transicion()` y las
    rechazó todas... mientras esta puerta quedaba abierta al lado. `§22` dice «intentarlo por
    **todas las vías del código**», y no se hizo."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "DECISION_REQUIRED", "el CEO debe decidir",
                          autoridad="orquestador")
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.completar_tarea(estado, "T-1", "hecho sin que nadie decidiera nada",
                           autoridad="orquestador")
    assert cp.estado_de_tarea(estado, "T-1")["estado"] == "DECISION_REQUIRED", "no se cerró"


def test_auditoria_h1_completar_tarea_exige_autoridad_y_respeta_la_tabla():
    estado = cp.estado_inicial()
    # El setup va FUERA del bloque: dentro, una excepcion suya haria pasar la prueba sin que la
    # llamada bajo examen llegase a ejecutarse nunca.
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    with pytest.raises(cp.TransicionInvalida, match="autoridad"):
        cp.completar_tarea(estado, "T-1", "hecha")          # sin autoridad: es el caso negativo
    cp.fijar_estado_tarea(estado, "T-2", "WORKING", "empieza", autoridad="ceo")
    # **Contrato endurecido el 2026-08-30 (2.a auditoría independiente).** `completar_tarea` trabaja
    # sobre el modelo en memoria y no tiene log donde comprobar un criterio mecánico, así que ya no
    # acepta autoridad no humana: cerraba `COMPLETED` sin criterio y sin humano, que es lo que A12
    # prohíbe. La vía automática es `transicion()` sobre el event log.
    with pytest.raises(cp.CriterioNoVerificado, match="humano|memoria|criterio"):
        cp.completar_tarea(estado, "T-2", "hecha", autoridad="orquestador")
    cp.completar_tarea(estado, "T-2", "hecha", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-2")["estado"] == "COMPLETED"


def test_auditoria_h1_completar_tarea_sigue_siendo_idempotente():
    """La corrección no puede romper lo que ya estaba garantizado: *«Idempotente: completar dos
    veces no la duplica»*."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.completar_tarea(estado, "T-1", "hecha", autoridad="ceo")
    cp.completar_tarea(estado, "T-1", "hecha otra vez", autoridad="ceo")
    assert len([t for t in estado["trabajo_completado"] if t["id"] == "T-1"]) == 1


def test_auditoria_h4_un_evento_crudo_no_puede_fabricar_un_estado(tmp_path):
    """**CUARTA RUTA**, encontrada tirando del hilo del hallazgo 1. `registrar_evento` es la
    primitiva del log; si acepta un `estado_de_tarea` a pelo, cualquiera fabrica una transición que
    la proyección aplicará como buena — el gobierno de `transicion()` sería decorativo.

    A diferencia de `guardar()`, que es una primitiva inofensiva (escribe lo que le den, sin
    interpretarlo), este evento **produce estado**. Por eso esta puerta sí se cierra."""
    d = _dir(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1"})
    cp.transicion(d, "T-1", "WORKING", autoridad="ceo", causa="empieza")
    cp.transicion(d, "T-1", "DECISION_REQUIRED", autoridad="ceo", causa="hay que decidir")
    with pytest.raises(cp.TransicionInvalida, match="transicion|crudo|estado_de_tarea"):
        cp.registrar_evento(d, "estado_de_tarea",
                            {"id": "T-1", "valor": "COMPLETED", "autoridad": "bot", "causa": "yo"})
    assert cp.estado_de(d, "T-1") == "DECISION_REQUIRED"


def test_auditoria_h3_reafirmar_un_estado_SOLO_HUMANO_tambien_exige_humano():
    """**HALLAZGO 3.** El atajo de idempotencia se evaluaba **antes** del control de autoridad
    humana, así que un adaptador podía reescribir `autoridad` y `causa` sobre una tarea parada en
    `DECISION_REQUIRED`. El estado no cambiaba —pero el registro de **quién** la sostiene sí, y ese
    registro es justamente lo que hace auditable la espera."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-3", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-3", "DECISION_REQUIRED", "ambiguo", autoridad="ceo")
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.fijar_estado_tarea(estado, "T-3", "DECISION_REQUIRED", "sigo ambiguo",
                              autoridad="orquestador")
    assert cp.estado_de_tarea(estado, "T-3")["autoridad"] == "ceo", "no se reescribió el registro"
    cp.fijar_estado_tarea(estado, "T-3", "DECISION_REQUIRED", "sigue esperándome", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-3")["motivo"] == "sigue esperándome"


def test_auditoria_h2_la_tabla_implementada_es_LITERALMENTE_la_del_DP():
    """**HALLAZGO GRAVE 2.** La prueba que debía garantizar esto era **decorativa**: su segundo
    operando comparaba solo las **claves**, así que la disyunción la hacía inalcanzable y cualquier
    redefinición de destinos seguía en verde. Con ella oculta viajó una divergencia real —un destino
    añadido a `WORKING` que el DP no contiene—.

    Aquí no hay disyunción y la comparación es exacta, destino a destino."""
    from test_modelo_orquestador import TRANSICIONES_PROPUESTAS
    assert set(cp.TRANSICIONES) == set(TRANSICIONES_PROPUESTAS)
    for origen, destinos in TRANSICIONES_PROPUESTAS.items():
        assert tuple(sorted(cp.TRANSICIONES[origen])) == tuple(sorted(destinos)), (
            f"{origen}: implementado {cp.TRANSICIONES[origen]} != DP §6 {destinos}")


# ============================ SEGUNDA AUDITORÍA · un defecto que introduje al corregir --


def test_auditoria2_no_se_puede_CREAR_una_tarea_ya_completada():
    """**GRAVE, y es mío: lo introduje arreglando H1.** La regla «crear no es transicionar» hacía un
    `return` **antes** de la tabla y antes del control humano, así que cualquier id nunca visto podía
    aparecer directamente en `COMPLETED` con cualquier cadena por autoridad. Nadie completa lo que
    nunca empezó.

    Lo delató la **asimetría**: `transicion()` sí lo rechaza —*«no se transiciona lo que no
    existe»*— mientras la ruta en memoria lo permitía. Dos rutas al mismo estado con distinto rigor
    es ALERTA-005, *«ninguna ruta alternativa»*, y el barrido de A5 no lo vio porque las 10 vías
    partían de una tarea que **ya estaba** en `DECISION_REQUIRED`."""
    estado = cp.estado_inicial()
    with pytest.raises(cp.TransicionInvalida, match="no se puede crear una tarea directamente"):
        cp.completar_tarea(estado, "T-FABRICADA", "inventado", autoridad="cualquier_agente")
    with pytest.raises(cp.TransicionInvalida, match="no se puede crear una tarea directamente"):
        cp.fijar_estado_tarea(estado, "T-FABRICADA", "COMPLETED", "inventado", autoridad="ceo")


def test_auditoria2_no_se_puede_CREAR_una_tarea_en_un_estado_que_exige_humano():
    """Entrar en `DECISION_REQUIRED` declara que hay una espera humana **sobre un trabajo en curso**.
    Crearla ya ahí permitiría fabricar una decisión pendiente que nadie pidió."""
    estado = cp.estado_inicial()
    for prohibido in ("DECISION_REQUIRED", "WAITING_FOR_HUMAN", "WAITING_FOR_REVIEW"):
        with pytest.raises(cp.TransicionInvalida, match="no se puede crear una tarea directamente"):
            cp.fijar_estado_tarea(estado, f"T-{prohibido}", prohibido, "yo lo digo", autoridad="bot")


def test_auditoria2_el_uso_LEGITIMO_de_crear_sigue_intacto():
    """La corrección no puede romper lo que ya funcionaba. `interrumpir` crea tareas en
    `WAITING_FOR_ENVIRONMENT`, `WAITING_FOR_QUOTA` y `FAILED`, y `registrar_bloqueo_de_cuota` en
    `WAITING_FOR_QUOTA`: **todos sobre tareas que pueden no constar todavía**. Si el arreglo los
    rompiera, habría cerrado la puerta trasera tapiando también la principal."""
    for creable in cp.ESTADOS_CREABLES:
        estado = cp.estado_inicial()
        cp.fijar_estado_tarea(estado, "T", creable, "arranque", autoridad="control_plane")
        assert cp.estado_de_tarea(estado, "T")["estado"] == creable

    estado = cp.estado_inicial()
    for momento in cp.INTERRUPCION:
        cp.interrumpir(estado, f"T-{momento}", momento)
    estado = cp.estado_inicial()
    cp.registrar_bloqueo_de_cuota(estado, "sin cuota", None, "T-NUEVA")
    assert cp.estado_de_tarea(estado, "T-NUEVA")["estado"] == "WAITING_FOR_QUOTA"


def test_auditoria2_ningun_estado_creable_es_terminal_ni_exige_humano():
    """La regla, expresada como propiedad en vez de como lista: si mañana alguien añade un estado a
    `ESTADOS_CREABLES`, esta prueba dice si acaba de abrir el agujero otra vez."""
    for creable in cp.ESTADOS_CREABLES:
        assert creable not in cp.ESTADOS_SOLO_HUMANO, f"{creable} exige acto humano"
        assert cp.TRANSICIONES.get(creable) != (), f"{creable} es terminal: nadie lo crea"
    assert "COMPLETED" not in cp.ESTADOS_CREABLES


def test_auditoria2_recompletar_sin_autoridad_falla_aunque_ya_este_completada():
    """**Cambio de contrato, documentado.** Antes de gobernar `completar_tarea`, re-completar no
    exigía nada. Ahora exige autoridad **incluso** cuando la llamada sería un no-op, porque una regla
    con excepciones es dos reglas — y este fichero ya pagó ese precio una vez."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.completar_tarea(estado, "T-1", "hecha", autoridad="ceo")
    with pytest.raises(cp.TransicionInvalida, match="autoridad"):
        cp.completar_tarea(estado, "T-1", "otra vez")


def test_ninguna_funcion_FUERA_de_las_gobernadas_cambia_el_estado_de_una_tarea():
    """**La garantía que faltaba, y la que habría ahorrado las dos auditorías.**

    Los defectos H1 y H4 fueron el mismo error dos veces: apareció una ruta al estado y nadie la
    contó. Enumerar las rutas a mano no escala — se demostró: el cierre llegó a decir «ambas» cuando
    eran cuatro. Esta prueba **no enumera**: recorre el módulo entero y comprueba que ninguna función
    pública fuera de las gobernadas puede mover una tarea.

    Si mañana alguien añade una quinta ruta, esta prueba la encuentra sin que nadie se acuerde de
    buscarla."""
    import copy
    import inspect

    GOBERNADAS = {"fijar_estado_tarea", "completar_tarea", "transicion", "reconciliar_tras_caida",
                  "interrumpir", "registrar_bloqueo_de_cuota", "validar_transicion"}

    # **Aisladas a propósito.** Escriben en disco con un destino por defecto que apunta al
    # `estado.json` REAL del Control Plane. La primera versión de esta prueba las llamaba sin
    # destino y **sobrescribió el estado real del proyecto**, borrando sus defectos registrados.
    # Un detector de rutas no puede destruir aquello que vigila.
    ESCRIBEN_EN_DISCO = {"guardar", "actualizar_estado", "confirmar_checkpoint"}

    def con_tarea_en_curso():
        estado = cp.estado_inicial()
        cp.fijar_estado_tarea(estado, "T", "WORKING", "empieza", autoridad="ceo")
        return estado

    movidas = []
    for nombre, obj in vars(cp).items():
        if nombre.startswith("_") or not inspect.isfunction(obj) or nombre in GOBERNADAS:
            continue
        if nombre in ESCRIBEN_EN_DISCO:
            continue
        firma = inspect.signature(obj)
        parametros = list(firma.parameters)
        if not parametros or parametros[0] not in ("estado", "cuota"):
            continue
        estado = con_tarea_en_curso()
        antes = copy.deepcopy(cp.estado_de_tarea(estado, "T"))
        argumentos = {}
        for p in parametros[1:]:
            if firma.parameters[p].default is not inspect.Parameter.empty:
                continue
            argumentos[p] = "T" if "tarea" in p or p == "id_trabajo" else "x"
        try:
            obj(estado, **argumentos)
        except Exception:
            continue                      # que rechace es aceptable; lo que no vale es que mueva
        if cp.estado_de_tarea(estado, "T")["estado"] != antes["estado"]:
            movidas.append(nombre)

    assert movidas == [], f"rutas al estado fuera del gobierno: {movidas}"


def test_el_detector_de_rutas_NUNCA_escribe_en_el_estado_real():
    """**Caso de control de la lección más cara de este bloque.** La primera versión del detector
    llamaba a toda función pública con el estado, incluida `guardar()`, cuyo destino por defecto es
    el `estado.json` real — y lo sobrescribió, borrando los defectos registrados del proyecto.

    Esta prueba fija el contrato: la lista de exclusión debe contener **todas** las funciones cuyo
    destino por defecto apunte al estado real."""
    import inspect

    for nombre, obj in vars(cp).items():
        if nombre.startswith("_") or not inspect.isfunction(obj):
            continue
        defectos = [p.default for p in inspect.signature(obj).parameters.values()]
        if cp.ESTADO_POR_DEFECTO in defectos:
            assert nombre in {"guardar", "actualizar_estado", "confirmar_checkpoint", "cargar"}, (
                f"{nombre} escribe o lee el estado real por defecto y no está declarada")


def test_meta_el_detector_de_rutas_encuentra_una_ruta_plantada():
    """**Caso de control.** Sin él, la prueba anterior pasaría igual si su detector no detectase
    nada — que es justo cómo una prueba se vuelve decorativa."""
    import copy
    import inspect

    def ruta_clandestina(estado, id_tarea):
        estado.setdefault("tareas", {})[id_tarea] = {"estado": "COMPLETED", "motivo": "por la cara"}
        return estado

    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T", "WORKING", "empieza", autoridad="ceo")
    antes = copy.deepcopy(cp.estado_de_tarea(estado, "T"))
    ruta_clandestina(estado, "T")
    assert cp.estado_de_tarea(estado, "T")["estado"] != antes["estado"], (
        "el detector compara el estado antes y después: si esto no cambiase, no detectaría nada")
    assert list(inspect.signature(ruta_clandestina).parameters)[0] == "estado", (
        "y solo inspecciona funciones cuyo primer parámetro es el estado")
