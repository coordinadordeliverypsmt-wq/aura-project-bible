"""RED · el **motor de autonomía**: descubrir el trabajo en vez de recibirlo.

`ciclo_autonomo(directorio, ficheros, ...)` recibe la lista de ficheros **desde fuera**. Ese
parámetro es el traspaso manual: alguien —hasta hoy, la asistencia externa— decide dónde mirar. El
ciclo sabe encadenar tareas, pero no sabe **de dónde salen**.

Lo que falta es el tramo de arriba:

    DESCUBRIR → CLASIFICAR → VALIDAR AUTORIDAD → DESCOMPONER → CREAR TAREA
              → [el circuito gobernado que YA existe] → REGISTRAR → SELECCIONAR SIGUIENTE

**No se construye un segundo motor de ejecución.** La ejecución sigue pasando por
`review.ejecutar_bajo_review` y por `control_plane.transicion`, con sus mismas puertas. Lo que se
añade es de dónde vienen las tareas.

## La regla que hace esto seguro

Descubrir trabajo **no es** concederse autoridad. El descubrimiento mira **todas** las fuentes; la
autoridad se decide después y por separado, con el mecanismo que ya existe. De ahí las cuatro
clases:

| Clase | Qué es | Qué se hace |
|---|---|---|
| `OPORTUNIDAD_REAL` | dentro del perímetro autorizado | se convierte en tarea y se ejecuta |
| `BLOQUEADA` | real, pero exige acta del CEO | se registra y **no se ejecuta** |
| `DECISION_REQUIRED` | no está determinada por ninguna fuente aprobada | se eleva |
| `FALSO_HUECO` | parece un hueco y no lo es | se descarta **con su motivo** |

## El meta-control, que es la mitad del valor

Un descubridor que puede inventar trabajo es peor que no tener ninguno: produce actividad que parece
progreso. Por eso **toda oportunidad debe traer las ocho piezas** —fuente, justificación, alcance,
autoridad, criterio de finalización, evidencia requerida, riesgo y estado— y la fuente tiene que
**apuntar a algo que se pueda ir a mirar**. Una oportunidad sin procedencia se rechaza igual que un
porcentaje de cuota sin procedencia: son indistinguibles de las inventadas.

Y una cola vacía deja de significar *«no puedo hacer nada»* para significar *«no hay trabajo
autorizado ahora mismo»* — que es una afirmación con evidencia detrás, no una rendición.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import descubrimiento as des
import motor_autonomia as motor
import orquestador as orq
import planificador as plan
import pytest
import review


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _plano_con_codigo_muerto(base, cuantos=3):
    """Un plano de desarrollo **real** en miniatura: ficheros de verdad, con código muerto de verdad.

    No se fabrican tareas: se fabrica el **árbol** que el descubridor va a leer, que es lo que hace
    cualquier prueba. Las oportunidades las encuentra él parseando."""
    zona = base / "entorno" / "control-plane"
    zona.mkdir(parents=True, exist_ok=True)
    for i in range(cuantos):
        (zona / f"modulo_{i}.py").write_text(
            f"def _muerta_{i}():\n"
            f"    return {i}\n"
            f"\n"
            f"\n"
            f"def viva_{i}():\n"
            f"    return {i} * 2\n",
            encoding="utf-8")
    return zona


def _con_review(directorio):
    review.habilitar(directorio, alcance=("eliminar_codigo_muerto",), por="ceo",
                     acta="DEC-ORCH-2 del CEO")


# ==================================================== FASE 1 · DESCUBRIMIENTO --


def test_toda_oportunidad_trae_LAS_OCHO_PIEZAS(tmp_path):
    """El meta-control. Sin las ocho, una oportunidad no es accionable ni auditable: quien la lea
    mañana no sabría de dónde salió ni cuándo estaría terminada."""
    zona = _plano_con_codigo_muerto(tmp_path)
    encontradas = des.descubrir(zona, directorio=tmp_path)
    assert encontradas, "hay código muerto real en el árbol: tiene que encontrarlo"
    for o in encontradas:
        for pieza in des.PIEZAS_OBLIGATORIAS:
            assert getattr(o, pieza, None) not in (None, "", {}), f"{o.id} no trae {pieza}"


def test_una_oportunidad_SIN_FUENTE_se_rechaza():
    """La garantía contra inventar trabajo, y es estructural: la fuente tiene que **apuntar a algo**.
    Una oportunidad sin procedencia es indistinguible de una inventada, exactamente como un
    porcentaje de cuota sin procedencia."""
    with pytest.raises(des.OportunidadSinProcedencia):
        des.Oportunidad(id="INVENTADA", fuente="", justificacion="me apetecía",
                        alcance="x.py", accion="eliminar_codigo_muerto", autoridad="AUTO",
                        criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
                        evidencia_requerida={"tipo": "fichero_existe", "ruta": "x.py"},
                        riesgo="bajo", estado=des.OPORTUNIDAD_REAL)


def test_la_fuente_APUNTA_a_algo_que_se_puede_ir_a_mirar(tmp_path):
    """**Reescrita: la versión anterior era decorativa.** No habilitaba `REVIEW`, así que
    `descubrir()` no devolvía ninguna `OPORTUNIDAD_REAL`, el `continue` se disparaba siempre y el
    `assert` no se ejecutaba **nunca**. La auditoría lo demostró sustituyendo la fuente por
    `"GARBAGE_NO_APUNTA_A_NADA"` en una copia: la prueba seguía en verde.

    Era justo la prueba que debía sostener el meta-control contra inventar trabajo. Séptima
    decorativa de esta serie, y la que más caro salía."""
    zona = _plano_con_codigo_muerto(tmp_path)
    _con_review(tmp_path)                          # <- lo que faltaba: sin esto no hay nada que mirar
    reales = [o for o in des.descubrir(zona, directorio=tmp_path)
              if o.estado == des.OPORTUNIDAD_REAL]
    assert reales, "con el acta habilitada tiene que haber oportunidades reales que comprobar"
    for o in reales:
        assert des.fuente_verificable(o.fuente), f"la fuente {o.fuente!r} no lleva a ninguna parte"
        assert pathlib.Path(o.fuente.rsplit(":", 1)[0]).exists()


def test_una_fuente_INVENTADA_no_construye_oportunidad():
    """El GRAVE que encontró la auditoría: el constructor solo comprobaba que la cadena no estuviera
    en blanco, así que `fuente="de la nada"` producía una oportunidad **ejecutable**.

    El docstring decía *«apunta a algo que se puede ir a mirar»* y no lo comprobaba. La barrera real
    estaba en la disciplina de las cinco fuentes incluidas, no en la clase — y una barrera que depende
    de que nadie escriba una sexta fuente con un fallo no es una barrera."""
    for basura in ("de la nada", ".", "porque sí", "/no/existe/x.py:1", "algo:1"):
        with pytest.raises(des.OportunidadSinProcedencia):
            des.Oportunidad(id="FAKE", fuente=basura, justificacion="me lo invento",
                            alcance="no_existe.py", accion="eliminar_codigo_muerto",
                            autoridad="AUTO",
                            criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
                            evidencia_requerida={"tipo": "fichero_existe", "ruta": "x.py"},
                            riesgo="bajo", estado=des.OPORTUNIDAD_REAL)


def test_una_fuente_que_nombra_un_MECANISMO_declarado_si_vale():
    """Caso de control: no todas las fuentes son ficheros. Las que nombran un mecanismo —el
    `estado.json`, el log, una función del Control Plane— valen **si el mecanismo está declarado**,
    no si suena bien."""
    assert des.fuente_verificable("control_plane.invocables_sin_clasificar() -> guardar")
    assert des.fuente_verificable("estado.json:oportunidades_bloqueadas:OB-1")
    assert des.fuente_verificable("eventos.jsonl:seq=42")
    assert not des.fuente_verificable("estado_inventado.json:algo")
    assert not des.fuente_verificable("control_plane.funcion_que_no_existe()")


def test_el_descubridor_recorre_VARIAS_fuentes_no_solo_el_codigo_muerto(tmp_path):
    """El contrato reconoce varias fuentes de trabajo. Un descubridor de una sola fuente vuelve a ser
    una lista escrita a mano, solo que más corta."""
    assert len(des.FUENTES) >= 4
    for nombre, funcion in des.FUENTES.items():
        assert callable(funcion), f"{nombre} no es una fuente ejecutable"


def test_las_CUATRO_clases_se_distinguen(tmp_path):
    """Descubrir no es autorizarse. Una oportunidad real y una bloqueada se encuentran igual; lo que
    cambia es qué se hace con ellas."""
    zona = _plano_con_codigo_muerto(tmp_path)
    _con_review(tmp_path)
    cp.registrar_evento(tmp_path, "decision_pendiente", {"id": "D-X", "pregunta": "¿y esto?"})
    clases = {o.estado for o in des.descubrir(zona, directorio=tmp_path)}
    assert des.OPORTUNIDAD_REAL in clases
    assert des.DECISION_REQUIRED in clases
    assert clases <= set(des.CLASES)


def test_una_decision_pendiente_se_eleva_y_NO_se_ejecuta(tmp_path):
    """`DECISION_REQUIRED` no es trabajo: es una pregunta. Convertirla en tarea sería resolverla por
    cuenta propia, que es exactamente lo que `ADR-0003:33` prohíbe."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=0)
    cp.registrar_evento(tmp_path, "decision_pendiente", {"id": "D-Y", "pregunta": "¿quién decide?"})
    elevadas = [o for o in des.descubrir(zona, directorio=tmp_path)
                if o.estado == des.DECISION_REQUIRED]
    assert elevadas
    for o in elevadas:
        assert plan.a_tarea(o) is None, "una decisión no se convierte en tarea"


def test_un_FALSO_HUECO_se_descarta_CON_SU_MOTIVO(tmp_path):
    """Una privada que sí se usa **desde otro módulo** parece muerta en su fichero y no lo está.
    Descartarla en silencio dejaría a quien lea el informe sin saber que se miró."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=0)
    (zona / "define.py").write_text("def _compartida():\n    return 1\n", encoding="utf-8")
    (zona / "usa.py").write_text("import define\n\n\ndef viva():\n    return define._compartida()\n",
                                 encoding="utf-8")
    falsos = [o for o in des.descubrir(zona, directorio=tmp_path) if o.estado == des.FALSO_HUECO]
    assert falsos, "_compartida se usa desde otro módulo: no es código muerto"
    assert all(o.justificacion for o in falsos), "un descarte sin motivo no es auditable"


def test_lo_que_exige_ACTA_se_marca_BLOQUEADA_y_no_se_ejecuta(tmp_path):
    """El perímetro **no se amplía descubriendo**. Una oportunidad real fuera del alcance del acta se
    registra y se queda ahí."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=0)
    (zona / "sucio.py").write_text("def _muerta():\n    return 1\n", encoding="utf-8")
    sin_acta = des.descubrir(zona, directorio=tmp_path)   # REVIEW no habilitado
    reales = [o for o in sin_acta if o.estado == des.OPORTUNIDAD_REAL]
    assert not reales, "sin acta que habilite REVIEW, nada es ejecutable"
    assert any(o.estado == des.BLOQUEADA for o in sin_acta)


# ==================================================== FASE 2 · PLANIFICACION --


def test_una_oportunidad_autorizada_se_convierte_en_TAREA_ejecutable(tmp_path):
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    o = next(x for x in des.descubrir(zona, directorio=tmp_path) if x.estado == des.OPORTUNIDAD_REAL)
    tarea = plan.a_tarea(o)
    assert tarea["accion"] == "eliminar_codigo_muerto"
    assert tarea["criterio_de_finalizacion"] == o.criterio_de_finalizacion
    assert tarea["origen"] == o.id, "la tarea sabe de qué oportunidad viene: trazabilidad"


def test_el_id_de_la_tarea_es_DERIVADO_de_la_oportunidad(tmp_path):
    """Derivado y no correlativo: dos descubrimientos de la misma oportunidad producen la misma
    tarea, así que el duplicado **se reconoce solo**. Es la misma razón que el `--session-id`."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    uno = next(x for x in des.descubrir(zona, directorio=tmp_path) if x.estado == des.OPORTUNIDAD_REAL)
    otro = next(x for x in des.descubrir(zona, directorio=tmp_path) if x.estado == des.OPORTUNIDAD_REAL)
    assert plan.a_tarea(uno)["id"] == plan.a_tarea(otro)["id"]


def test_no_se_planifica_DOS_VECES_la_misma_tarea(tmp_path):
    """Sin esto, cada vuelta del ciclo redescubriría lo mismo y el bucle no terminaría nunca."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    oportunidades = des.descubrir(zona, directorio=tmp_path)
    primera = plan.siguiente(tmp_path, oportunidades)
    plan.registrar_planificada(tmp_path, primera)
    segunda = plan.siguiente(tmp_path, oportunidades)
    assert segunda is not None and segunda["id"] != primera["id"]


def test_sin_oportunidades_autorizadas_NO_se_inventa_ninguna(tmp_path):
    """*«si no hay tareas → inventar una»* no existe. `siguiente()` devuelve `None`, y eso es una
    respuesta completa."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=0)
    assert plan.siguiente(tmp_path, des.descubrir(zona, directorio=tmp_path)) is None


def test_el_plan_ordena_por_RIESGO_y_deja_lo_bloqueado_fuera(tmp_path):
    """Lo reversible primero: si algo va a fallar, que falle donde se puede deshacer."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    oportunidades = des.descubrir(zona, directorio=tmp_path)
    cola = plan.cola(tmp_path, oportunidades)
    assert cola, "hay oportunidades reales: la cola no puede estar vacía"
    assert all(t["accion"] in review.TODO_LO_DELEGABLE for t in cola)

    # **El orden, medido.** La versión anterior solo comprobaba pertenencia: invertir `_peso` la
    # dejaba en verde, y el nombre prometía «ordena por riesgo». Lo demostró la auditoría.
    riesgos = [plan._ORDEN_DE_RIESGO.get(t["riesgo"].split(":")[0].strip().lower(), 9) for t in cola]
    assert riesgos == sorted(riesgos), f"la cola no está ordenada por riesgo: {riesgos}"

    mezcladas = list(reversed(oportunidades))
    assert [t["id"] for t in plan.cola(tmp_path, mezcladas)] == [t["id"] for t in cola], (
        "el orden lo pone el planificador, no el orden en que llegaron")


# ==================================================== FASE 4 · ENCADENADO --


def test_TRES_tareas_encadenadas_sin_UN_SOLO_acto_humano(tmp_path):
    """**La prueba que importa.** Tres oportunidades **descubiertas**, no entregadas; ejecutadas por
    el circuito gobernado que ya existía; verificadas por efecto; y la cola termina agotada.

    `actos_humanos_durante_el_ciclo = 0` no es una declaración: se cuenta."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=3)
    _con_review(tmp_path)
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)

    assert informe["ejecutadas"] == 3, informe
    assert informe["actos_humanos_durante_el_ciclo"] == 0
    assert informe["motivo_de_parada"] == "cola agotada"
    for i in range(3):
        assert f"_muerta_{i}" not in (zona / f"modulo_{i}.py").read_text(encoding="utf-8")
        assert f"viva_{i}" in (zona / f"modulo_{i}.py").read_text(encoding="utf-8")


def test_cada_tarea_del_encadenado_deja_su_RASTRO(tmp_path):
    """Trazabilidad de punta a punta: de la oportunidad a la tarea, de la tarea al efecto."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    for esperado in ("descubrimiento_realizado", "tarea_planificada", "veredicto_emitido"):
        assert esperado in tipos, f"falta el rastro {esperado}"


def test_la_segunda_vuelta_encuentra_la_cola_AGOTADA(tmp_path):
    """Y agotada **por evidencia**: se volvió a descubrir y no había nada, no es que dejara de
    mirar."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    segunda = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    assert segunda["ejecutadas"] == 0
    assert segunda["motivo_de_parada"] == "cola agotada"
    # `>= 0` era trivialmente cierto para cualquier entero: no verificaba nada. Lo que sí demuestra
    # que volvió a mirar es que quede un **segundo** evento de descubrimiento en el log.
    descubrimientos = [e for e in cp.leer_eventos(tmp_path)
                       if e["tipo"] == "descubrimiento_realizado"]
    assert len(descubrimientos) >= 3, "cada vuelta redescubre: el árbol cambia con cada tarea"


# ==================================================== FASE 5 · PARADA SEGURA --


def test_una_DECISION_REQUIRED_detiene_su_frente_y_NO_el_ciclo(tmp_path):
    """`PARADA ≠ fallo`, y una decisión pendiente **no bloquea el trabajo independiente**. Detener
    todo por una pregunta abierta sería convertir cada duda en una parada general."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    cp.registrar_evento(tmp_path, "decision_pendiente", {"id": "D-Z", "pregunta": "¿?"})
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    assert informe["ejecutadas"] == 2, "el trabajo autorizado siguió"
    assert informe["elevadas"] >= 1
    assert informe["motivo_de_parada"] == "cola agotada"


def test_el_trabajo_BLOQUEADO_se_registra_y_el_ciclo_continua(tmp_path):
    """Un bloqueo es información, no un muro. Se anota y se sigue con lo demás."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    (zona.parent.parent / "walking-skeleton").mkdir(parents=True, exist_ok=True)
    fuera = zona.parent.parent / "walking-skeleton" / "producto.py"
    fuera.write_text("def _muerta_prod():\n    return 1\n", encoding="utf-8")
    informe = motor.trabajar(tmp_path, zona.parent.parent, verificacion=lambda: True, max_tareas=5)
    assert informe["bloqueadas"] >= 1, "el producto está fuera del perímetro: bloqueada, no ejecutada"
    assert "producto.py" not in str(informe.get("ejecutadas_ids", ""))
    assert "_muerta_prod" in fuera.read_text(encoding="utf-8"), "no se tocó el producto"


def test_una_VERIFICACION_fallida_detiene_y_revierte(tmp_path):
    """El árbol roto es peor que no haber hecho nada, y seguir tras un fallo de verificación es
    apostar a que el siguiente cambio arregle el anterior."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    original = (zona / "modulo_0.py").read_text(encoding="utf-8")
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: False, max_tareas=5)
    assert informe["ejecutadas"] == 0
    assert informe["motivo_de_parada"] == "verificacion fallida"
    assert (zona / "modulo_0.py").read_text(encoding="utf-8") == original


def test_la_parada_deja_escrito_el_MOTIVO_EXACTO(tmp_path):
    """Una parada sin motivo obliga al siguiente a reconstruir por qué se paró — y reconstruir es
    justamente lo que el Protocolo de Continuidad existe para evitar."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    motor.trabajar(tmp_path, zona, verificacion=lambda: False, max_tareas=5)
    paradas = [e["datos"] for e in cp.leer_eventos(tmp_path) if e["tipo"] == "ciclo_detenido"]
    assert paradas and paradas[-1].get("motivo") == "verificacion fallida"
    assert paradas[-1].get("detenida_en")


def test_el_limite_de_seguridad_acota_el_ciclo(tmp_path):
    """`§14`: ningún bucle sin cota. La autonomía no es correr sin freno."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=4)
    _con_review(tmp_path)
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=2)
    assert informe["ejecutadas"] == 2
    assert informe["motivo_de_parada"] == "limite de seguridad"


def test_el_kill_switch_detiene_el_motor(tmp_path):
    """Fuera de banda, como en el bucle del orquestador: si el sistema está comprometido, su
    colaboración no vale nada."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    orq.ruta_parada(tmp_path).write_text("parada", encoding="utf-8")
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    assert informe["ejecutadas"] == 0
    assert informe["motivo_de_parada"] == "kill switch activado"


# ==================================================== NO HAY SEGUNDO MOTOR --


def test_el_motor_NO_ejecuta_por_su_cuenta(tmp_path):
    """`§5` y la orden explícita: *«no crear un segundo motor de ejecución»*. El motor descubre,
    planifica y encadena; **ejecutar lo hace el circuito gobernado que ya existía**.

    Se comprueba en el fuente porque es una propiedad de diseño, no de comportamiento: el día que
    alguien escriba aquí un `write_text`, esta prueba lo verá antes que una auditoría."""
    import ast
    fuente = (pathlib.Path(__file__).resolve().parent / "motor_autonomia.py").read_text(
        encoding="utf-8")
    arbol = ast.parse(fuente)

    # Se mira el **código**, no la prosa: la primera versión buscaba las palabras en el fuente entero
    # y se encontró a sí misma en un docstring que explicaba precisamente esta regla. Un detector que
    # confunde hablar de algo con hacerlo produce falsos positivos, y un falso positivo en un control
    # de seguridad se acaba desactivando — que es peor que no tenerlo.
    llamadas = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    llamadas |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    importados = {a.name.split(".")[0] for n in ast.walk(arbol)
                  if isinstance(n, ast.Import) for a in n.names}
    importados |= {n.module.split(".")[0] for n in ast.walk(arbol)
                   if isinstance(n, ast.ImportFrom) and n.module}

    for prohibido in ("write_text", "write_bytes", "unlink", "remove", "rmtree", "mkdir"):
        assert prohibido not in llamadas, f"el motor no escribe nada por su cuenta: {prohibido}"
    for modulo in ("shutil", "subprocess", "os"):
        assert modulo not in importados, f"el motor no necesita {modulo}: no toca el sistema"
    assert "ejecutar_bajo_review" in llamadas, "la ejecución pasa por el circuito gobernado"


def test_una_fuente_EN_BLANCO_tambien_se_rechaza():
    """`MOT-M1` sobrevivió porque las dos comprobaciones del constructor se tapaban entre sí: quitar
    la del `fuente` dejaba la del bucle, y al revés. Solo se distinguen en un caso, y es este —una
    fuente hecha de espacios—: el bucle la ve como presente (una cadena con espacios es *truthy*) y
    solo la comprobación específica, que hace `strip()`, la rechaza.

    No es un caso rebuscado: `fuente=" "` es exactamente lo que sale de rellenar el campo por
    obligación, que es la forma educada de inventar trabajo."""
    with pytest.raises(des.OportunidadSinProcedencia):
        des.Oportunidad(id="EN-BLANCO", fuente="   ", justificacion="algo",
                        alcance="x.py", accion="eliminar_codigo_muerto", autoridad="AUTO",
                        criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
                        evidencia_requerida={"tipo": "fichero_existe", "ruta": "x.py"},
                        riesgo="bajo", estado=des.OPORTUNIDAD_REAL)


def test_falta_una_pieza_QUE_NO_ES_LA_FUENTE_y_tambien_se_rechaza():
    """La otra mitad de la pareja: `MOT-M2` quitaba el bucle de las ocho piezas y sobrevivía porque
    todas mis pruebas dejaban vacía justo la que la otra comprobación cubre. Aquí falta el criterio
    de finalización, que solo mira el bucle.

    Y la garantía importa por sí misma: una oportunidad sin criterio de finalización no se puede
    cerrar nunca — `§14.bis` regla 4 —, así que aceptarla sería crear trabajo que no termina."""
    real = str(pathlib.Path(__file__).resolve())
    for pieza, vacio in (("justificacion", ""), ("criterio_de_finalizacion", {}),
                         ("evidencia_requerida", {}), ("riesgo", "")):
        campos = dict(id="SIN-PIEZA", fuente=f"{real}:1", justificacion="algo", alcance="x.py",
                      accion="eliminar_codigo_muerto", autoridad="AUTO",
                      criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
                      evidencia_requerida={"tipo": "fichero_existe", "ruta": "x.py"},
                      riesgo="bajo", estado=des.OPORTUNIDAD_REAL)
        campos[pieza] = vacio
        with pytest.raises(des.OportunidadSinProcedencia):
            des.Oportunidad(**campos)


def test_NINGUNA_clase_distinta_de_OPORTUNIDAD_REAL_produce_tarea(tmp_path):
    """Demostración por ejecución de que el filtro de `cola()` y la puerta de `a_tarea()` dicen lo
    mismo — que es lo que sostiene que `MOT-M6` sea **equivalente** y no un superviviente aceptado.

    Se recorren las tres clases no ejecutables y se comprueba que ninguna llega a tarea. Si algún
    día una de ellas la produjera, el filtro dejaría de ser redundante y esta prueba lo vería."""
    real = str(pathlib.Path(__file__).resolve())      # una fuente que existe de verdad
    for clase in (des.BLOQUEADA, des.DECISION_REQUIRED, des.FALSO_HUECO):
        oportunidad = des.Oportunidad(
            id=f"OP-{clase}", fuente=f"{real}:1", justificacion="da igual", alcance="x.py",
            accion="eliminar_codigo_muerto", autoridad="CEO",
            criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
            evidencia_requerida={"tipo": "fichero_existe", "ruta": "x.py"},
            riesgo="bajo", estado=clase)
        assert plan.a_tarea(oportunidad) is None
        assert plan.cola(tmp_path, [oportunidad]) == []


def test_SIN_REVISOR_CAPAZ_el_motor_espera_y_no_toca_nada(tmp_path, monkeypatch):
    """`MOT-M18` sobrevivió por un hueco real de cobertura **mío**: ninguna prueba del motor corría
    sin revisor capaz, así que la rama del `§8.3` no se ejercitaba nunca.

    Es la garantía que más caro sale perder: *«no se autoaprueba jamás»*. Un motor que, ante la
    ausencia de revisor, siguiera adelante convertiría la falta de supervisión en permiso."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=2)
    _con_review(tmp_path)
    original = (zona / "modulo_0.py").read_text(encoding="utf-8")
    monkeypatch.setattr(review, "revisores_capaces", lambda: ())
    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    assert informe["ejecutadas"] == 0
    assert informe["motivo_de_parada"] == "sin revisor capaz"
    assert (zona / "modulo_0.py").read_text(encoding="utf-8") == original


# ==================================================== FASE 14 · SIN CLAUDE --


def test_el_punto_de_entrada_NO_es_un_demonio():
    """`§23` del DP aprobado: *«**Ningún daemon ni watcher permanente.** El Orchestrator se invoca y
    termina»*. No es una preferencia de estilo: un proceso que no muere es uno al que hay que ir a
    matar, y un sistema al que hay que ir a matar no está gobernado.

    Se comprueba en el **código**, no en la prosa, por la misma razón que en el motor."""
    import ast
    import aura
    arbol = ast.parse(pathlib.Path(aura.__file__).read_text(encoding="utf-8"))
    llamadas = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    llamadas |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for prohibido in ("sleep", "Thread", "Timer", "fork", "Popen", "daemon", "schedule"):
        assert prohibido not in llamadas, f"un punto de entrada no espera ni se reprograma: {prohibido}"
    assert not [n for n in ast.walk(arbol) if isinstance(n, ast.While)], (
        "ningún bucle sin cota: la única iteración acotada vive en el motor")


def test_la_cola_agotada_SALE_CON_CERO():
    """No haber encontrado trabajo autorizado **no es un fallo**. Si saliera con error, quien lo
    automatice acabaría fabricando trabajo para que «pase» — que es exactamente lo que no debe
    ocurrir."""
    import aura
    assert aura.codigo_de_salida({"motivo_de_parada": "cola agotada"}) == aura.SALIDA_OK
    assert aura.codigo_de_salida({"motivo_de_parada": "limite de seguridad"}) == aura.SALIDA_OK


def test_una_parada_que_alguien_debe_MIRAR_no_sale_con_cero():
    """Y la otra mitad: quien encadene esto necesita distinguir «no había trabajo» de «me tuve que
    parar» sin leer prosa."""
    import aura
    for motivo in ("kill switch activado", "verificacion fallida", "zona prohibida",
                   "sin revisor capaz", "objeciones del revisor"):
        assert aura.codigo_de_salida({"motivo_de_parada": motivo}) == aura.SALIDA_PARADA


def test_la_zona_de_trabajo_NO_la_elige_quien_invoca():
    """La base se deriva del propio fichero. Aceptarla por parámetro invitaría a apuntarla a otro
    sitio, y dónde puede escribir AURA no es una decisión de quien la despierta."""
    import inspect

    import aura
    assert not inspect.signature(aura._base).parameters
    assert "--base" not in pathlib.Path(aura.__file__).read_text(encoding="utf-8")


def test_los_actos_humanos_se_CUENTAN_no_se_declaran(tmp_path):
    """La auditoría encontró que `actos_humanos_durante_el_ciclo` se inicializaba a `0` y **no se
    incrementaba nunca**: era una constante que las pruebas leían como si fuera una medición. Y es
    justo la cifra que decide si esto es autonomía o teatro.

    Ahora se cuenta de verdad: cualquier evento con autoridad humana registrado mientras el ciclo
    corría entra en la cuenta. Se comprueba metiendo uno a propósito."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    limpio = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    assert limpio["actos_humanos_durante_el_ciclo"] == 0

    zona2 = _plano_con_codigo_muerto(tmp_path / "otro", cuantos=1)
    review.habilitar(tmp_path / "otro", alcance=("eliminar_codigo_muerto",), por="ceo", acta="acta")
    cp.registrar_evento(tmp_path / "otro", "tarea_registrada",
                        {"id": "T-H", "accion": "ejecutar_pruebas"})

    def con_intervencion():
        cp.transicion(tmp_path / "otro", "T-H", "WORKING", autoridad="ceo", causa="el CEO interviene")
        return True

    sucio = motor.trabajar(tmp_path / "otro", zona2, verificacion=con_intervencion, max_tareas=5)
    assert sucio["actos_humanos_durante_el_ciclo"] >= 1, (
        "hubo un acto humano dentro del ciclo y la cuenta tiene que verlo")


def test_la_raiz_declarada_no_concede_planos_VECINOS(tmp_path):
    """El tercer GRAVE de la auditoría del motor: `zona_permitida(x, raiz=<raíz del repo>)` concedía
    `entorno/agente-externo/`. El docstring decía *«`raiz` solo puede ESTRECHAR, nunca ampliar»* y era
    falso para cualquier directorio que no fuese gobernanza ni producto.

    Es el mismo patrón que el propio código dice haber corregido una vez, en otro sitio: una garantía
    documentada que no la sostiene el código sino la convención de que hoy solo hay un llamador."""
    import autoconstruccion as ac
    repo = tmp_path
    (repo / "entorno" / "control-plane").mkdir(parents=True)
    (repo / "entorno" / "agente-externo").mkdir(parents=True)
    propio = repo / "entorno" / "control-plane" / "modulo.py"
    vecino = repo / "entorno" / "agente-externo" / "otro.py"
    for f in (propio, vecino):
        f.write_text("x = 1\n", encoding="utf-8")

    assert not ac.zona_permitida(vecino, raiz=repo), "un plano vecino no es la zona declarada"
    assert ac.zona_permitida(propio, raiz=repo), "y el plano propio sí, o se habría cerrado de más"


def test_los_actos_humanos_ANTERIORES_al_ciclo_no_cuentan(tmp_path):
    """`MOT-M29` sobrevivió porque en mis pruebas no había ningún acto humano **antes** del ciclo, así
    que contar el historial entero daba lo mismo que contar desde el arranque.

    El caso real es justo ese: el acta la firma el CEO **antes** de que el motor arranque. Si contara
    todo el historial, cada ciclo reportaría ≥1 acto humano y la métrica que decide si esto es
    autonomía dejaría de significar nada."""
    zona = _plano_con_codigo_muerto(tmp_path, cuantos=1)
    _con_review(tmp_path)
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-PREVIA", "accion": "ejecutar_pruebas"})
    cp.transicion(tmp_path, "T-PREVIA", "WORKING", autoridad="ceo",
                  causa="el CEO hizo algo ANTES de que el motor arrancara")

    informe = motor.trabajar(tmp_path, zona, verificacion=lambda: True, max_tareas=5)
    assert informe["ejecutadas"] == 1
    assert informe["actos_humanos_durante_el_ciclo"] == 0, (
        "el acto humano es anterior al ciclo: contarlo haría que ningún ciclo pudiera dar 0")


def test_la_cola_ordena_riesgos_DISTINTOS(tmp_path):
    """`MOT-M31` sobrevivió porque todas las oportunidades de código muerto traen el **mismo** riesgo,
    así que invertir el orden daba la misma secuencia. Ordenar solo se puede comprobar con cosas
    distintas.

    Y la regla importa: lo reversible primero, para que si algo falla, falle donde se puede deshacer."""
    real = str(pathlib.Path(__file__).resolve())

    def _op(ident, riesgo):
        return des.Oportunidad(
            id=ident, fuente=f"{real}:1", justificacion="da igual", alcance=f"{ident}.py",
            accion="eliminar_codigo_muerto", autoridad="REVIEW",
            criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
            evidencia_requerida={"tipo": "fichero_existe", "ruta": "x.py"},
            riesgo=riesgo, estado=des.OPORTUNIDAD_REAL)

    revueltas = [_op("OP-alto", "alto: toca gobierno"), _op("OP-ninguno", "ninguno"),
                 _op("OP-medio", "medio: varios ficheros"), _op("OP-bajo", "bajo: reversible")]
    orden = [t["origen"] for t in plan.cola(tmp_path, revueltas)]
    assert orden == ["OP-ninguno", "OP-bajo", "OP-medio", "OP-alto"], orden
