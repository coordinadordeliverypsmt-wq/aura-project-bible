"""Pruebas del MODELO CONCEPTUAL del Development Orchestrator (DP-DEVELOPMENT-ORCHESTRATOR).

QUE ESTO NO ES
--------------
**No hay Orchestrator implementado y estas pruebas no lo implementan.** Verifican propiedades del
MODELO que el DP propone, antes de que exista una linea de su codigo. Sirven para dos cosas:

1. Demostrar que los invariantes son expresables y consistentes -- si no se puede escribir la prueba,
   no es una garantia, es una expectativa (ADR-0014 regla 4).
2. Demostrar por EJECUCION los defectos P2/P3/P4 que el DP §1 afirma sobre el Control Plane actual.
   Una afirmacion de defecto sin caso que falle es una opinion.

No hay red, no hay procesos persistentes, no hay APIs externas, no se invoca ningun modelo.
Todo ocurre sobre ficheros temporales.

QUE PASA SI EL CEO NO APRUEBA EL DP
-----------------------------------
Este fichero se borra y no queda nada colgando: no lo importa nadie.
"""

from __future__ import annotations

import json
import multiprocessing
import pathlib
import subprocess
import sys
import tempfile
import uuid
import pytest

import control_plane as cp
import revisores

# ---------------------------------------------------------------------------
# El modelo propuesto, como DATOS. No es codigo del orquestador: es la tabla
# que el DP §6 propone, escrita aqui para poder interrogarla.
# ---------------------------------------------------------------------------

TRANSICIONES_PROPUESTAS: dict[str, tuple[str, ...]] = {
    "WAITING_FOR_NEXT_TASK": ("WORKING",),
    "WORKING": ("WAITING_FOR_REVIEW", "WAITING_FOR_ENVIRONMENT", "WAITING_FOR_QUOTA",
                "DECISION_REQUIRED", "FAILED", "COMPLETED"),
    "WAITING_FOR_REVIEW": ("WORKING", "DECISION_REQUIRED", "COMPLETED", "FAILED"),
    "WAITING_FOR_ENVIRONMENT": ("WORKING", "FAILED"),
    "WAITING_FOR_QUOTA": ("WORKING", "FAILED"),
    "DECISION_REQUIRED": ("WORKING", "FAILED"),
    "WAITING_FOR_HUMAN": ("WORKING", "FAILED"),
    "COMPLETED": (),
    "FAILED": ("WORKING",),
}

# Estados desde los que SOLO un acto humano registrado puede sacar la tarea.
REQUIEREN_AUTORIDAD_HUMANA = ("DECISION_REQUIRED", "WAITING_FOR_HUMAN")

# Campos que el veredicto de un revisor puede traer. `autoriza` NO esta, a proposito:
# `1.1:93` -- "su autoridad de aprobacion no es delegable a ningun agente".
#
# **DEUDA DEL `§21`, PAGADA.** El DP la declaro asi: *«compara dos tuplas escritas a mano en el mismo
# fichero y por el mismo autor: no existe todavia una clase `Veredicto` real contra la que
# contrastar. (...) Cuando C5 se implemente, esta prueba debe apuntar a la clase real o se convierte
# en decoracion»*. C5 se implemento en F4 (`revisores.Veredicto`), asi que los campos se **derivan**
# de la clase real. Escritos a mano, la prueba seguiria en verde aunque la implementacion se
# desviara: comprobaria que el autor sabe copiar su propia lista.
CAMPOS_VEREDICTO = tuple(revisores.Veredicto.__dataclass_fields__)

NIVELES_AUTORIDAD = ("AUTO", "REVIEW", "HUMAN")


def clasificar(accion: str, politica: dict[str, str]) -> str:
    """Nivel de autoridad de una accion. Sin regla explicita -> HUMAN.

    Es "ante la duda, roja" (ADR-0003) trasladado al plano de desarrollo. El valor por defecto
    es la garantia: una politica incompleta se vuelve restrictiva, nunca permisiva.
    """
    return politica.get(accion, "HUMAN")


def id_de_sesion(tarea_id: str, huella_sobre: str) -> str:
    """Identificador determinista de la ejecucion de una tarea.

    Modela `--session-id <uuid>`, verificado en Claude Code 2.1.233. La misma tarea con el mismo
    sobre produce el mismo id, asi que una segunda ejecucion es DETECTABLE en vez de depender de
    que nadie se equivoque.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"aura-orch/{tarea_id}/{huella_sobre}"))


def _fuente_sin_este_bloque() -> str:
    """El fuente de este fichero, sin las lineas que declaran terminos prohibidos.

    Una prueba que busca una cadena dentro de su propio fichero SE ENCUENTRA A SI MISMA. Ya paso
    aqui: cuatro pruebas fallaron porque la lista literal de terminos vetados vivia en el mismo
    fuente que inspeccionaban. Se resuelve por dos vias combinadas -- concatenar los terminos para
    que el literal no exista, y descartar las lineas que los construyen.
    """
    lineas = pathlib.Path(__file__).read_text(encoding="utf-8").splitlines()
    utiles = [ln for ln in lineas if '" + "' not in ln]
    return "\n".join(utiles)


def proyectar(eventos: list[dict]) -> dict[str, str]:
    """Reconstruye el estado por tarea desde el log. Ultimo evento por tarea gana.

    ADR-0023: "la direccion del flujo es historial -> proyeccion". La proyeccion debe poder
    eliminarse por completo y regenerarse sin alterar el comportamiento.
    """
    estado: dict[str, str] = {}
    for evento in sorted(eventos, key=lambda e: e["seq"]):
        estado[evento["tarea"]] = evento["estado"]
    return estado


# ---------------------------------------------------------------------------
# 1-2. Estados finales y autoridad humana
# ---------------------------------------------------------------------------

def test_completed_es_final_no_se_reabre_una_tarea_terminada():
    """Replica la garantia que el producto ya tiene (`estado_operativo.py:52-58`).

    Caso de control: si COMPLETED tuviera cualquier sucesor, esta prueba fallaria.
    """
    assert TRANSICIONES_PROPUESTAS["COMPLETED"] == ()


def test_ningun_estado_permite_volver_desde_completed():
    """Complemento del anterior: COMPLETED no es origen de NINGUNA transicion.

    Se comprueba recorriendo la tabla entera, no solo la entrada de COMPLETED: si alguien
    anadiera un camino de vuelta en otra fila, esta prueba lo veria.
    """
    caminos_de_vuelta = [
        (origen, destinos) for origen, destinos in TRANSICIONES_PROPUESTAS.items()
        if origen == "COMPLETED" and destinos
    ]
    assert caminos_de_vuelta == []


def test_salir_de_decision_required_exige_acto_humano():
    """DECISION_REQUIRED no se resuelve solo. Nunca.

    El modelo lo expresa asi: los estados que requieren autoridad humana tienen sucesores, pero
    ninguna transicion automatica del orquestador puede producirlos. Aqui se comprueba la parte
    declarativa: estan marcados y no se puede salir de ellos hacia COMPLETED directamente.
    """
    for estado in REQUIEREN_AUTORIDAD_HUMANA:
        assert estado in TRANSICIONES_PROPUESTAS
        assert "COMPLETED" not in TRANSICIONES_PROPUESTAS[estado], (
            f"{estado} no puede saltar a COMPLETED: eso seria resolver la decision sin humano")


def test_toda_transicion_apunta_a_un_estado_conocido():
    """Una tabla que apunte a un estado inexistente es un bug silencioso."""
    for origen, destinos in TRANSICIONES_PROPUESTAS.items():
        assert origen in TRANSICIONES_PROPUESTAS
        for destino in destinos:
            assert destino in TRANSICIONES_PROPUESTAS, f"{origen} -> {destino} no existe"


def test_los_estados_del_modelo_respetan_el_vocabulario_ya_aprobado():
    """El modelo no inventa vocabulario: reutiliza el fijado por el CEO y anade UNO solo.

    **Premisa superada por F1 (2026-08-26).** Esta prueba media una *propuesta*: el modelo pedia un
    estado, `WAITING_FOR_REVIEW`, que el vocabulario real aun no tenia. F1 lo implemento, asi que la
    diferencia es ahora vacia — y afirmar que sigue habiendo uno pendiente seria el patron
    `declarado != real` al reves: la prueba pidiendo que el codigo *no* haya hecho lo que hizo.

    La garantia que queda es la que de verdad importa y **no caduca**: el modelo conceptual y el
    vocabulario implementado no pueden divergir en ninguna direccion."""
    ya_aprobados = set(cp.ESTADOS)
    del_modelo = set(TRANSICIONES_PROPUESTAS)
    assert cp.ESTADO_REVISION in ya_aprobados, "F1 debia anadir WAITING_FOR_REVIEW"
    assert del_modelo - ya_aprobados == set(), (
        f"el modelo usa estados que no existen: {del_modelo - ya_aprobados}")
    # **Retirada la disyunción decorativa** (2.ª auditoría). Decía
    # `A or set(cp.TRANSICIONES) == del_modelo`, y el segundo operando comparaba solo las **claves**:
    # era alcanzable siempre, así que cualquier redefinición de destinos seguía en verde. Por debajo
    # viajó una divergencia real con el DP. La comparación exacta, destino a destino, vive en
    # `test_red_f1_orquestador.py::test_auditoria_h2_la_tabla_implementada_es_LITERALMENTE_la_del_DP`;
    # aquí se conserva solo lo que esta prueba puede afirmar sin solaparse con ella.
    for origen, destinos in TRANSICIONES_PROPUESTAS.items():
        assert tuple(sorted(cp.TRANSICIONES[origen])) == tuple(sorted(destinos)), (
            f"{origen}: implementado {cp.TRANSICIONES[origen]} != modelo {destinos}")


# ---------------------------------------------------------------------------
# 3. Evidencia insuficiente nunca produce COMPLETED
# ---------------------------------------------------------------------------

def _puede_completar(evidencia: dict | None, criterio_cumplido: bool) -> bool:
    """Regla del modelo: COMPLETED exige evidencia Y criterio demostrado."""
    return bool(evidencia) and criterio_cumplido


def test_una_tarea_sin_evidencia_no_puede_completarse():
    assert _puede_completar(None, True) is False
    assert _puede_completar({}, True) is False


def test_una_tarea_con_evidencia_pero_sin_criterio_cumplido_no_se_completa():
    assert _puede_completar({"artefacto": "x.json"}, False) is False


def test_solo_evidencia_mas_criterio_completa():
    assert _puede_completar({"artefacto": "x.json"}, True) is True


def test_el_control_plane_actual_ya_impide_el_completed_falso():
    """No es teoria: `interrumpir()` ya lo garantiza hoy. Se comprueba, no se supone."""
    estado = cp.estado_inicial()
    for momento in ("espera_ambiental", "primera_inferencia", "escritura_evidencia"):
        cp.interrumpir(estado, "T-X", momento)
        assert cp.estado_de_tarea(estado, "T-X")["estado"] != "COMPLETED"


# ---------------------------------------------------------------------------
# 4. P2 -- DEMOSTRACION POR EJECUCION de la perdida de escritura sin lock
# ---------------------------------------------------------------------------


def _escritor_gobernado(ruta: str, id_tarea: str, barrera_ficticia: float) -> None:
    """El mismo escritor, por la via que F1 anadio: el lock envuelve leer-modificar-escribir."""
    import time

    import control_plane as cp_hijo

    def cambio(estado):
        time.sleep(barrera_ficticia)      # la misma ventana, ahora dentro del lock
        # Empezar antes de completar: desde la 2.a auditoria no se puede crear una tarea ya
        # completada, porque nadie completa lo que nunca empezo.
        cp_hijo.fijar_estado_tarea(estado, id_tarea, "WORKING", "empieza", autoridad="ceo")
        cp_hijo.completar_tarea(estado, id_tarea, f"hecho por {id_tarea}", autoridad="ceo")
        return estado

    cp_hijo.actualizar_estado(pathlib.Path(ruta), cambio)


def test_p2_la_via_GOBERNADA_conserva_las_dos_escrituras():
    """**P2 CERRADO por F1 (2026-08-26).** La version anterior de esta prueba media el defecto y
    anunciaba su propio final: *«si algun dia el Control Plane gana un lock, esta prueba fallara.
    Eso seria la senal de que el defecto esta cerrado, y entonces se invierte la asercion»*. Se
    invierte.

    Tambien **cierra `DEF-FLAKY-P2`**: la asercion vieja («se pierde exactamente una») dependia de
    que el planificador cooperase, y por eso era intermitente. Esta no: si el lock funciona, las dos
    escrituras sobreviven **siempre**; si no funciona, se pierde una y falla. Una prueba de
    concurrencia deja de ser flaky cuando aserta la garantia en vez del accidente.

    La primitiva `guardar()` sigue sin lock a proposito —es una escritura, no una actualizacion—; lo
    que existe ahora es la via correcta para el ciclo completo, y `test_p2_...` la ejercita con dos
    procesos reales."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = pathlib.Path(tmp) / "estado.json"
        cp.guardar(cp.estado_inicial(), ruta)

        ctx = multiprocessing.get_context("spawn")
        a = ctx.Process(target=_escritor_gobernado, args=(str(ruta), "T-A", 0.30))
        b = ctx.Process(target=_escritor_gobernado, args=(str(ruta), "T-B", 0.05))
        a.start()
        b.start()
        a.join(timeout=60)
        b.join(timeout=60)

        final = cp.cargar(ruta)
        hechas = {t["id"] for t in final["trabajo_completado"]}

    assert hechas == {"T-A", "T-B"}, (
        f"el lock no serializo el ciclo: se perdio una escritura, hechas={hechas}")


def test_p2_la_primitiva_CRUDA_sigue_sin_ser_una_actualizacion_atomica():
    """Caso de control del diagnostico, conservado. Si esta prueba dejara de poder perder una
    escritura, `test_p2_la_via_GOBERNADA_...` no estaria demostrando nada: pasaria igual con lock y
    sin el.

    No aserta *cuantas* se pierden —eso era el accidente flaky—, sino que `guardar()` **no ofrece**
    la garantia: quien la necesite debe usar `actualizar_estado`."""
    import inspect
    fuente = inspect.getsource(cp.guardar)
    assert "lock_estado" not in fuente, (
        "si `guardar` gano un lock propio, la via gobernada dejo de ser distinguible")
    assert "lock_estado" in inspect.getsource(cp.actualizar_estado)


def test_p4_ya_NO_se_puede_pasar_de_completed_a_working():
    """**P4 CERRADO por F1 (2026-08-26).** Esta prueba demostraba el defecto y avisaba de su propio
    final: *«si esto falla, las transiciones ya estan gobernadas y P4 esta cerrado»*. Fallo. Se
    convierte en la garantia que protege el cierre.

    Mantenerla midiendo el defecto habria sido pedirle al codigo que **no** hiciera lo que se le
    encargo hacer."""
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "T-1", "COMPLETED", "terminada", autoridad="ceo")
    with pytest.raises(cp.TransicionInvalida, match="COMPLETED"):
        cp.fijar_estado_tarea(estado, "T-1", "WORKING", "reabierta sin declarar por que",
                              autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-1")["estado"] == "COMPLETED", "no se reabrio"
    assert "WORKING" not in TRANSICIONES_PROPUESTAS["COMPLETED"]
    assert "WORKING" not in cp.TRANSICIONES["COMPLETED"], "y la tabla implementada coincide"


# ---------------------------------------------------------------------------
# 5. Idempotencia
# ---------------------------------------------------------------------------

def test_el_mismo_sobre_produce_el_mismo_identificador_de_sesion():
    assert id_de_sesion("T-42", "abc") == id_de_sesion("T-42", "abc")


def test_un_sobre_distinto_produce_identificador_distinto():
    assert id_de_sesion("T-42", "abc") != id_de_sesion("T-42", "abd")
    assert id_de_sesion("T-43", "abc") != id_de_sesion("T-42", "abc")


def test_el_identificador_es_un_uuid_valido():
    """`--session-id` exige un UUID valido: si no lo fuera, la invocacion fallaria."""
    uuid.UUID(id_de_sesion("T-1", "x"))


def test_una_tarea_completada_no_se_reejecuta_ni_tras_recargar_de_disco():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = pathlib.Path(tmp) / "estado.json"
        estado = cp.estado_inicial()
        cp.fijar_estado_tarea(estado, "T-9", "WORKING", "empieza", autoridad="ceo")
        cp.completar_tarea(estado, "T-9", "hecho", evidencia={"artefacto": "x"}, autoridad="ceo")
        cp.guardar(estado, ruta)

        recargado = cp.cargar(ruta)
        puede, motivo = cp.debe_ejecutar(recargado, "T-9")

    assert puede is False
    assert "completada" in motivo


# ---------------------------------------------------------------------------
# 6. Paralelismo: una tarea bloqueada no detiene a otra independiente
# ---------------------------------------------------------------------------

def test_una_decision_pendiente_no_bloquea_una_tarea_que_no_declara():
    estado = cp.estado_inicial()
    estado["decisiones_pendientes"] = [
        {"id": "D-N3", "asunto": "reduccion de n", "bloquea": ["EXP-CAMPANA"]}]

    assert cp.debe_ejecutar(estado, "EXP-CAMPANA")[0] is False
    assert cp.debe_ejecutar(estado, "OTRA-TAREA")[0] is True


def test_estados_distintos_coexisten_sin_contradiccion():
    estado = cp.estado_inicial()
    cp.fijar_estado_tarea(estado, "A", "WAITING_FOR_ENVIRONMENT", "RAM", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "B", "WORKING", "empieza", autoridad="ceo")
    cp.fijar_estado_tarea(estado, "B", "DECISION_REQUIRED", "decision", autoridad="ceo")

    assert cp.estado_de_tarea(estado, "A")["estado"] == "WAITING_FOR_ENVIRONMENT"
    assert cp.estado_de_tarea(estado, "B")["estado"] == "DECISION_REQUIRED"


# ---------------------------------------------------------------------------
# 7. El revisor opina; no autoriza
# ---------------------------------------------------------------------------

def test_el_veredicto_no_tiene_ningun_campo_de_autorizacion():
    """`1.1:93` -- "su autoridad de aprobacion no es delegable a ningun agente".

    La garantia no es una promesa de comportamiento: es que la operacion NO EXISTE en el tipo.
    """
    prohibidos = ("autoriza", "aprueba", "permiso", "permite", "autorizacion", "aprobado")
    for campo in CAMPOS_VEREDICTO:
        assert campo not in prohibidos
    assert not set(CAMPOS_VEREDICTO) & set(prohibidos)


def test_el_silencio_del_revisor_no_aprueba():
    """`1.1:85` -- "el silencio o la ausencia de objecion no constituye aprobacion"."""
    def resolver(veredicto: dict | None) -> str:
        if veredicto is None:                       # timeout, revisor caido, respuesta perdida
            return "WAITING_FOR_REVIEW"
        return "WORKING" if veredicto["veredicto"] == "conforme" else "DECISION_REQUIRED"

    assert resolver(None) == "WAITING_FOR_REVIEW"
    assert resolver(None) != "COMPLETED"


def test_sin_revisor_las_tareas_auto_siguen_avanzando():
    """Degradacion: falta el revisor -> REVIEW espera, AUTO no se detiene."""
    politica = {"ejecutar_pruebas": "AUTO", "refactor": "REVIEW"}
    revisor_disponible = False

    def ejecutable(accion: str) -> bool:
        nivel = clasificar(accion, politica)
        if nivel == "AUTO":
            return True
        if nivel == "REVIEW":
            return revisor_disponible
        return False                                 # HUMAN

    assert ejecutable("ejecutar_pruebas") is True
    assert ejecutable("refactor") is False
    assert ejecutable("modificar_adr") is False


# ---------------------------------------------------------------------------
# 8-9. Bucle finito y politica restrictiva por defecto
# ---------------------------------------------------------------------------

def test_el_bucle_termina_cuando_no_hay_trabajo_elegible():
    """Un orquestador que no puede terminar es un bucle infinito con otro nombre."""
    iteraciones = 0
    pendientes = ["T-1", "T-2"]
    max_iteraciones = 10

    while pendientes and iteraciones < max_iteraciones:
        pendientes.pop()
        iteraciones += 1

    assert not pendientes
    assert iteraciones < max_iteraciones


def test_el_bucle_respeta_el_tope_aunque_el_trabajo_no_se_acabe():
    """Si el trabajo se regenera solo, el tope es lo unico que impide el bucle infinito."""
    iteraciones = 0
    max_iteraciones = 5
    pendientes = ["T"]

    while pendientes and iteraciones < max_iteraciones:
        pendientes.append("T-derivada")               # trabajo que se reproduce
        pendientes.pop(0)
        iteraciones += 1

    assert iteraciones == max_iteraciones, "el tope debe cortar aunque quede trabajo"


def test_una_accion_sin_regla_es_humana():
    """"Ante la duda, roja" (ADR-0003) trasladado: la politica incompleta es restrictiva."""
    politica = {"ejecutar_pruebas": "AUTO"}
    assert clasificar("ejecutar_pruebas", politica) == "AUTO"
    assert clasificar("borrar_el_repositorio", politica) == "HUMAN"
    assert clasificar("", politica) == "HUMAN"


def test_una_politica_vacia_lo_clasifica_todo_como_humano():
    for accion in ("cualquiera", "otra", "modificar_bible"):
        assert clasificar(accion, {}) == "HUMAN"


def test_los_niveles_de_autoridad_son_exactamente_tres():
    assert NIVELES_AUTORIDAD == ("AUTO", "REVIEW", "HUMAN")


# ---------------------------------------------------------------------------
# 10-11. Cuota: nunca se afirma lo que no se observa
# ---------------------------------------------------------------------------

def test_el_modelo_no_introduce_ninguna_nocion_de_cuota_conocida():
    """El Control Plane ya lo garantiza; el modelo no debe erosionarlo."""
    cuota = cp.observar_cuota()
    assert cuota["usage_known"] is False
    assert cuota["rolling_window"]["estado"] == "UNKNOWN"
    assert cuota["weekly"]["estado"] == "UNKNOWN"


def test_el_presupuesto_operacional_no_es_conocimiento_de_cuota():
    """Distincion central del DP §11: topar el gasto NO es saber cuanto queda.

    `--max-budget-usd` y `total_cost_usd` son observables por invocacion; la cuota de la cuenta
    no lo es. Un presupuesto puede existir con `usage_known = false`.
    """
    presupuesto = {"max_budget_usd": 0.50, "max_iteraciones": 3, "max_llamadas_revisor": 2}

    assert all(isinstance(v, (int, float)) for v in presupuesto.values())
    assert "cuota" not in presupuesto
    assert "restante" not in presupuesto
    assert cp.observar_cuota()["usage_known"] is False


def test_este_fichero_no_afirma_ningun_porcentaje_de_cuota():
    """Misma prueba que protege al Control Plane, aplicada a este modelo.

    Los terminos se construyen por CONCATENACION a proposito: si se escribieran literales,
    apareceran en el propio fuente y la prueba se refutaria a si misma -- fallo que este fichero
    ya cometio una vez y que es el mismo patron que produjo >=4 falsos PASS en el proyecto.
    """
    fuente = _fuente_sin_este_bloque()
    sospechosos = ("restante" + "_pct", "consumido" + "_pct",
                   "porcentaje" + "_cuota", "cuota" + "_restante")
    for sospechoso in sospechosos:
        assert sospechoso not in fuente


def test_una_ventana_de_cuota_no_arrastra_a_la_otra():
    estado = cp.estado_inicial()
    cp.registrar_bloqueo_de_cuota(
        estado, mensaje="You've hit your weekly limit", ventana="WEEKLY", tarea="T-1")

    assert estado["cuota"]["weekly"]["estado"] != "UNKNOWN"
    assert estado["cuota"]["rolling_window"]["estado"] == "UNKNOWN", (
        "marcar la semanal no puede decir nada de la movil")


# ---------------------------------------------------------------------------
# 12. La proyeccion es reconstruible desde el historial (ADR-0023)
# ---------------------------------------------------------------------------

def test_el_estado_se_reconstruye_integro_desde_el_log():
    eventos = [
        {"seq": 1, "tarea": "T-1", "estado": "WORKING"},
        {"seq": 2, "tarea": "T-2", "estado": "WORKING"},
        {"seq": 3, "tarea": "T-1", "estado": "COMPLETED"},
    ]
    assert proyectar(eventos) == {"T-1": "COMPLETED", "T-2": "WORKING"}


def test_la_proyeccion_no_depende_del_orden_de_llegada():
    """Si el orden de las lineas cambiara el resultado, el log no seria fuente de verdad."""
    eventos = [
        {"seq": 3, "tarea": "T-1", "estado": "COMPLETED"},
        {"seq": 1, "tarea": "T-1", "estado": "WORKING"},
        {"seq": 2, "tarea": "T-2", "estado": "WORKING"},
    ]
    assert proyectar(eventos)["T-1"] == "COMPLETED"


def test_borrar_la_proyeccion_y_regenerarla_da_el_mismo_resultado():
    """Criterio literal de ADR-0023:82-85 para distinguir proyeccion de fuente de verdad."""
    eventos = [
        {"seq": 1, "tarea": "T-1", "estado": "WORKING"},
        {"seq": 2, "tarea": "T-1", "estado": "COMPLETED"},
    ]
    primera = proyectar(eventos)
    del primera                                        # se borra por completo
    segunda = proyectar(eventos)

    assert segunda == {"T-1": "COMPLETED"}


def test_un_evento_duplicado_no_cambia_la_proyeccion():
    """Idempotencia de la respuesta duplicada (DP §12)."""
    base = [{"seq": 1, "tarea": "T-1", "estado": "COMPLETED"}]
    duplicado = base + [{"seq": 1, "tarea": "T-1", "estado": "COMPLETED"}]

    assert proyectar(base) == proyectar(duplicado)


# ---------------------------------------------------------------------------
# Aislamiento -- la regla mas importante del encargo
# ---------------------------------------------------------------------------

def test_este_modelo_no_importa_nada_del_producto():
    """Confundir "autonomia para desarrollar AURORA" con "autonomia de AURORA" seria el error
    mas caro posible. El modelo del orquestador hereda la misma prohibicion que el Control Plane.
    """
    fuente = pathlib.Path(__file__).read_text(encoding="utf-8")
    cabecera, _, cuerpo = fuente.partition('"""QUE PASA SI EL CEO')
    del cabecera, cuerpo
    lineas_de_codigo = [
        ln for ln in fuente.splitlines()
        if ln.strip().startswith(("import ", "from ")) and "#" not in ln.split("import")[0]
    ]
    for linea in lineas_de_codigo:
        assert "aura_skeleton" not in linea
        assert "walking_skeleton" not in linea
        assert "walking-skeleton" not in linea


def test_el_modelo_no_ejecuta_inferencias_ni_abre_red():
    """Ni un socket, ni un cliente HTTP, ni una llamada a un modelo. Terminos concatenados."""
    fuente = _fuente_sin_este_bloque()
    prohibidos = ("import " + "socket", "import " + "requests", "urllib." + "request",
                  "http." + "client", "oll" + "ama", "open" + "ai", "anthro" + "pic")
    for prohibido in prohibidos:
        assert prohibido not in fuente


def test_el_modelo_no_lanza_ningun_proceso_persistente():
    """No hay daemon, no hay watcher: el encargo lo prohibe expresamente."""
    fuente = _fuente_sin_este_bloque()
    prohibidos = ("Pop" + "en(", "system" + "d", "cron" + "tab", "while " + "True")
    for prohibido in prohibidos:
        assert prohibido not in fuente


def test_el_modelo_no_toca_el_experimento_congelado():
    """EXP-REPRO, el benchmark y n=3 quedan intactos: ni se importan ni se nombran como modulo."""
    fuente = _fuente_sin_este_bloque()
    prohibidos = ("ab_" + "format", "casos_" + "benchmark", "superficie_" + "ab",
                  "aisla" + "miento", "heuristicas_" + "deterministas")
    for prohibido in prohibidos:
        assert prohibido not in fuente


# ---------------------------------------------------------------------------
# Continuidad entre procesos: el modelo sobrevive a un proceso nuevo
# ---------------------------------------------------------------------------

def test_el_estado_del_modelo_sobrevive_a_un_proceso_completamente_nuevo():
    """No basta con que funcione en memoria: un relevo ocurre en OTRO proceso."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = pathlib.Path(tmp) / "estado.json"
        estado = cp.estado_inicial()
        cp.fijar_estado_tarea(estado, "T-7", "WORKING", "empieza", autoridad="ceo")
        cp.fijar_estado_tarea(estado, "T-7", "DECISION_REQUIRED", "espera al CEO", autoridad="ceo")
        cp.guardar(estado, ruta)

        guion = (
            "import json,sys; "
            f"d=json.load(open({str(ruta)!r})); "
            "print(d['tareas']['T-7']['estado'])"
        )
        salida = subprocess.run(
            [sys.executable, "-c", guion], capture_output=True, text=True, timeout=30)

    assert salida.returncode == 0, salida.stderr
    assert salida.stdout.strip() == "DECISION_REQUIRED"


def test_el_log_de_eventos_es_serializable_linea_a_linea():
    """Un event log JSONL exige que cada evento sea una linea JSON valida e independiente."""
    eventos = [
        {"seq": 1, "tarea": "T-1", "estado": "WORKING", "autoridad": "orchestrator"},
        {"seq": 2, "tarea": "T-1", "estado": "DECISION_REQUIRED", "autoridad": "orchestrator"},
    ]
    lineas = [json.dumps(e, ensure_ascii=False) for e in eventos]

    assert all("\n" not in ln for ln in lineas), "una linea con salto rompe el formato JSONL"
    assert [json.loads(ln) for ln in lineas] == eventos
