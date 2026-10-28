"""RED · `D-ORCH-3` — catálogo `AUTO` + selección de agente + **failover Claude → OpenCode**.

El circuito completo, no funciones sueltas:

    AUTO → TASK → selección de agente → ejecución → RESULT → **verificación externa** → registro

**El punto crítico:** AURA no cree al agente. El agente **afirma**; AURA **verifica el efecto**. Un
agente que dice «archivo creado» y no lo crea produce `RESULT = NO_VERIFICADO`, nunca `VERIFIED`.
Esto no es teórico: la Línea B ya midió un agente que respondía texto sin producir efecto.

**El failover NO es «si Claude falla, usa OpenCode».** Hay que distinguir *el agente no puede* de *la
tarea está mal*: lo primero justifica un relevo, lo segundo no, y confundirlos oculta el fallo
cambiando de agente indefinidamente.
"""

from __future__ import annotations

import json
import pathlib

import control_plane as cp
import pytest

import agentes as ag
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



# ============================================ CATÁLOGO AUTO — derivado, no inventado --


def test_auto_ya_NO_esta_vacio_y_sale_de_fuentes_aprobadas():
    """`§10.2`: `AUTO` ← *«lista verde (ADR-0003)… tests, lint, formato, análisis, documentación»*.
    `D-ORCH-3` pedía la lista exacta; se **deriva** del catálogo verde ya aprobado en
    `permissions.py`, no se inventa."""
    auto = orq.acciones_de_nivel("AUTO")
    assert auto, "D-ORCH-3 sin resolver dejaba AUTO vacío"
    for accion in auto:
        assert orq.nivel_de(accion) == "AUTO"


def test_toda_entrada_AUTO_declara_el_contrato_completo():
    """El CEO fija los campos obligatorios. Una entrada incompleta es una autorización sin límites."""
    exigidos = ("tipo", "objetivo", "autoridad", "precondiciones", "agentes_permitidos",
                "evidencia_requerida", "criterio_de_exito", "ante_fallo", "permite_fallback",
                "limites_de_modificacion", "origen")
    for accion in orq.acciones_de_nivel("AUTO"):
        ficha = orq.ficha_de(accion)
        faltan = [c for c in exigidos if c not in ficha]
        assert not faltan, f"{accion} no declara {faltan}"
        assert ficha["origen"], f"{accion} no cita la fuente que la autoriza"


def test_ninguna_accion_AUTO_modifica_nada():
    """El plano de desarrollo hereda el criterio de `permissions.py`: solo entran acciones cuyo
    efecto es **lectura**. Una acción `AUTO` que escribiera sería autonomía de escritura concedida
    sin acta."""
    for accion in orq.acciones_de_nivel("AUTO"):
        ficha = orq.ficha_de(accion)
        assert ficha["limites_de_modificacion"] == "ninguna", f"{accion} podría modificar"
        assert ficha["tipo"] == "lectura"


def test_una_accion_ROJA_jamas_puede_colarse_en_AUTO():
    """Control del control: si `AUTO` admitiera una acción de lista roja, ADR-0003 quedaría roto."""
    rojas = ("eliminar_archivo", "pagar", "enviar_mensaje", "modificar_adr", "promover_propuesta")
    for accion in rojas:
        assert accion not in orq.acciones_de_nivel("AUTO")
        assert orq.nivel_de(accion) == "HUMAN"


# ==================================== TAXONOMÍA DE FALLOS — el corazón del failover --


def test_se_distingue_AGENTE_NO_DISPONIBLE_de_TAREA_FALLIDA():
    """La distinción que el CEO exige. Confundirlas produce el peor comportamiento posible: ocultar
    un fallo real cambiando de agente hasta que alguno calle."""
    assert ag.clasificar(exit_code=None, motivo="quota exhausted") == ag.AGENTE_SIN_CUOTA
    assert ag.clasificar(exit_code=127, motivo="command not found") == ag.AGENTE_NO_DISPONIBLE
    assert ag.clasificar(exit_code=1, motivo="assertion failed") == ag.TAREA_FALLIDA
    assert ag.clasificar(exit_code=None, motivo="timeout tras 120s") == ag.TIMEOUT
    assert ag.clasificar(exit_code=0, motivo="", efecto_verificado=False) == ag.SIN_EFECTO
    assert ag.clasificar(exit_code=0, motivo="", efecto_verificado=True) == ag.EXITO


def test_solo_la_indisponibilidad_del_AGENTE_justifica_el_relevo():
    """`TAREA_FALLIDA` y `SIN_EFECTO` **no** son motivo de fallback: la tarea está mal o el agente
    mintió, y en ambos casos cambiar de agente esconde el problema."""
    assert ag.justifica_fallback(ag.AGENTE_SIN_CUOTA) is True
    assert ag.justifica_fallback(ag.AGENTE_NO_DISPONIBLE) is True
    assert ag.justifica_fallback(ag.TAREA_FALLIDA) is False
    assert ag.justifica_fallback(ag.SIN_EFECTO) is False
    assert ag.justifica_fallback(ag.RESULTADO_INVALIDO) is False
    assert ag.justifica_fallback(ag.EXITO) is False


def test_el_fallback_es_FINITO_y_no_repite_agente():
    """Un fallback infinito es un bucle de gasto. La cadena está declarada y se recorre una vez."""
    assert ag.CADENA_DE_AGENTES == ("claude", "opencode")
    assert ag.siguiente_agente("claude") == "opencode"
    assert ag.siguiente_agente("opencode") is None, "no hay tercero: la cadena termina"


def test_un_agente_fuera_de_la_cadena_no_se_usa_jamas():
    """Codex está expresamente excluido por decisión del CEO, y Ollama no participa en este flujo."""
    for prohibido in ("codex", "ollama", "cualquiera"):
        assert prohibido not in ag.CADENA_DE_AGENTES
        with pytest.raises(ag.AgenteNoAutorizado):
            ag.verificar_autorizado(prohibido)


# ================== EL PUNTO CRÍTICO — AURA no cree al agente, verifica el efecto --


def test_un_agente_que_AFIRMA_sin_producir_efecto_no_obtiene_VERIFIED(tmp_path):
    """El caso medido en la Línea B: el agente responde texto plausible y no ocurre nada.

    Si AURA aceptara la afirmación, marcaría `COMPLETED` un trabajo inexistente — el `COMPLETED`
    falso que `interrumpir()` existe para impedir."""
    destino = pathlib.Path(tmp_path) / "prueba.txt"
    evidencia = {"tipo": "fichero_existe", "ruta": str(destino)}
    veredicto = ag.verificar_efecto(evidencia, afirmacion="archivo creado correctamente")
    assert veredicto["verificado"] is False
    assert veredicto["resultado"] == "NO_VERIFICADO"

    destino.write_text("contenido real", encoding="utf-8")
    veredicto = ag.verificar_efecto(evidencia, afirmacion="archivo creado correctamente")
    assert veredicto["verificado"] is True
    assert veredicto["resultado"] == "VERIFIED"


def test_la_verificacion_NO_lee_la_afirmacion_del_agente(tmp_path):
    """Meta-control. Si el veredicto dependiera del texto, un agente elocuente pasaría siempre."""
    destino = pathlib.Path(tmp_path) / "x.txt"
    destino.write_text("existe", encoding="utf-8")
    ev = {"tipo": "fichero_existe", "ruta": str(destino)}
    for afirmacion in ("he fallado", "todo mal", "", "ERROR CATASTRÓFICO", "no pude hacer nada"):
        assert ag.verificar_efecto(ev, afirmacion=afirmacion)["verificado"] is True, (
            "el efecto es real: lo que diga el agente es irrelevante")


def test_una_evidencia_que_no_se_puede_comprobar_NUNCA_da_VERIFIED():
    """*«Efecto no verificable»* es uno de los meta-controles que el CEO pide. Ante la duda, no."""
    veredicto = ag.verificar_efecto({"tipo": "confia_en_mi"}, afirmacion="hecho")
    assert veredicto["verificado"] is False
    assert veredicto["resultado"] == "NO_VERIFICABLE"


# ============================================ TRAZABILIDAD DEL INTENTO --


def test_cada_intento_registra_los_NUEVE_campos_exigidos(tmp_path):
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    intento = ag.Intento(agente="claude", numero=1, motivo="", exit_code=0,
                         resultado="VERIFIED", efecto_verificado=True,
                         duracion_s=1.5, fallback_usado=False, clase=ag.EXITO)
    registro = intento.como_evento()
    for campo in ("agent", "attempt", "reason", "exit_code", "result", "effect_verified",
                  "duration", "fallback_used", "class"):
        assert campo in registro, f"falta {campo}"
    ag.registrar_intento(d, "T-1", intento)
    tipos = [e["tipo"] for e in cp.leer_eventos(d)]
    assert "intento_de_agente" in tipos
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_una_tarea_sin_efecto_verificado_NO_llega_a_COMPLETED(tmp_path):
    """*«TASK marcada COMPLETED sin evidencia»* — meta-control explícito del CEO."""
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    with pytest.raises(ag.SinEvidencia):
        ag.cerrar_tarea(d, "T-1", veredicto={"verificado": False, "resultado": "NO_VERIFICADO"},
                        autoridad="orquestador")
    assert cp.estado_de(d, "T-1") != "COMPLETED"

    # Afirmar el efecto tampoco basta ya: desde la auditoria del 2026-08-30 el motor unico exige
    # ademas que el criterio mecanico conste ejecutado. Este era el hueco — `cerrar_tarea` daba por
    # buena la afirmacion de que el efecto se verifico, sin que nada hubiera corrido.
    with pytest.raises(cp.CriterioNoVerificado):
        ag.cerrar_tarea(d, "T-1", veredicto={"verificado": True, "resultado": "VERIFIED"},
                        autoridad="orquestador")
    assert cp.estado_de(d, "T-1") != "COMPLETED"

    orq.fijar_criterio(d, "T-1", {"capacidad": "ejecutar_pruebas"})
    orq.verificar_criterio(d, "T-1", lambda _c: 0)
    ag.cerrar_tarea(d, "T-1", veredicto={"verificado": True, "resultado": "VERIFIED"},
                    autoridad="orquestador")
    assert cp.estado_de(d, "T-1") == "COMPLETED"


# ============================================ OPENCODE — bajo demanda, y AUSENTE al final --


def test_opencode_es_BAJO_DEMANDA_y_su_ciclo_incluye_la_retirada():
    """Contrato aprobado: `INSTALAR → VERIFICAR → EJECUTAR → MEDIR → RETIRAR → LIMPIAR → VERIFICAR
    AUSENCIA`. Sin los tres últimos pasos, «bajo demanda» se convierte en «instalado»."""
    pasos = ag.PASOS_AGENTE_EXTERNO
    for exigido in ("instalar", "verificar", "ejecutar", "medir", "retirar", "limpiar",
                    "comprobar_residuos"):
        assert exigido in pasos, f"el ciclo no contempla {exigido}"
    assert pasos.index("retirar") > pasos.index("ejecutar")
    assert pasos[-1] == "comprobar_residuos", "lo último es comprobar que no queda nada"


def test_opencode_NO_recibe_secretos_ni_acceso_innecesario():
    sobre = ag.sobre_para_externo({"id": "T-1", "accion": "ejecutar_pruebas", "objetivo": "x"})
    texto = json.dumps(sobre, ensure_ascii=False).lower()
    for prohibido in ("api_key", "token", "password", "secret", "aura_approved", "credential"):
        assert prohibido not in texto
    assert sobre["permisos"]["allowedTools"], "sí recibe permisos, pero declarados"
    assert "no commit" in " ".join(sobre["restricciones"]).lower()


def test_el_agente_externo_no_queda_como_dependencia_permanente():
    """*«No convertir OpenCode en dependencia permanente»*. El módulo no puede asumir que existe."""
    fuente = pathlib.Path(ag.__file__).read_text(encoding="utf-8")
    assert "import opencode" not in fuente
    # `in (True, False)` no comprobaba nada: pasaba con un `return True` constante, y un mutante
    # que hacía justo eso sobrevivió. Se comprueba contra la realidad del sistema.
    assert ag.disponible("agente_que_no_existe_en_ninguna_parte") is False
    import shutil
    assert ag.disponible("opencode") == (shutil.which("opencode") is not None), (
        "disponible() debe reflejar el sistema, no una constante")


# ============================================ CIRCUITO COMPLETO --


def test_circuito_AUTO_a_cierre_con_el_agente_principal(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path)
    marca = pathlib.Path(tmp_path) / "efecto.txt"

    def claude_falso(sobre, **_):
        marca.write_text("hecho", encoding="utf-8")
        return ag.Respuesta(exit_code=0, salida='{"ok": true}', afirmacion="listo")

    monkeypatch.setattr(ag, "_EJECUTORES", {"claude": claude_falso})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-9", "accion": "ejecutar_pruebas"})
    resultado = ag.ejecutar_tarea(
        d, {"id": "T-9", "accion": "ejecutar_pruebas", "objetivo": "x",
            "evidencia_requerida": {"tipo": "fichero_existe", "ruta": str(marca)}},
        autoridad="orquestador")
    assert resultado["resultado"] == "VERIFIED"
    assert resultado["agente"] == "claude"
    assert resultado["fallback_usado"] is False
    assert cp.estado_de(d, "T-9") == "COMPLETED"


def test_circuito_con_FAILOVER_cuando_claude_no_tiene_cuota(tmp_path, monkeypatch):
    """El escenario que motiva el bloque: Claude sin cuota, OpenCode toma el relevo, y el efecto se
    verifica **externamente** antes de cerrar."""
    d = pathlib.Path(tmp_path)
    marca = pathlib.Path(tmp_path) / "efecto.txt"

    def claude_sin_cuota(sobre, **_):
        return ag.Respuesta(exit_code=None, salida="", afirmacion="",
                            motivo="You've hit your monthly spend limit")

    def opencode_falso(sobre, **_):
        marca.write_text("hecho por opencode", encoding="utf-8")
        return ag.Respuesta(exit_code=0, salida='{"ok": true}', afirmacion="listo")

    monkeypatch.setattr(ag, "_EJECUTORES", {"claude": claude_sin_cuota, "opencode": opencode_falso})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-F", "accion": "ejecutar_pruebas"})
    resultado = ag.ejecutar_tarea(
        d, {"id": "T-F", "accion": "ejecutar_pruebas", "objetivo": "x", "permite_fallback": True,
            "evidencia_requerida": {"tipo": "fichero_existe", "ruta": str(marca)}},
        autoridad="orquestador")
    assert resultado["agente"] == "opencode"
    assert resultado["fallback_usado"] is True
    assert resultado["resultado"] == "VERIFIED"

    intentos = [e for e in cp.leer_eventos(d) if e["tipo"] == "intento_de_agente"]
    assert len(intentos) == 2, "los DOS intentos quedan registrados, no solo el que salió bien"
    assert intentos[0]["datos"]["agent"] == "claude"
    assert intentos[0]["datos"]["class"] == ag.AGENTE_SIN_CUOTA


def test_una_TAREA_FALLIDA_no_dispara_failover_y_la_tarea_queda_FAILED(tmp_path, monkeypatch):
    """Lo contrario del caso anterior, y es lo que impide esconder fallos rotando agentes."""
    d = pathlib.Path(tmp_path)

    def claude_falla(sobre, **_):
        return ag.Respuesta(exit_code=1, salida="", afirmacion="", motivo="assertion failed")

    llamado = []
    monkeypatch.setattr(ag, "_EJECUTORES", {
        "claude": claude_falla,
        "opencode": lambda *a, **k: llamado.append(1) or ag.Respuesta(0, "{}", "ok")})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-E", "accion": "ejecutar_pruebas"})
    resultado = ag.ejecutar_tarea(
        d, {"id": "T-E", "accion": "ejecutar_pruebas", "objetivo": "x", "permite_fallback": True,
            "evidencia_requerida": {"tipo": "fichero_existe", "ruta": str(d / "nada.txt")}},
        autoridad="orquestador")
    assert llamado == [], "no se releva a un agente porque la TAREA falle"
    assert resultado["resultado"] != "VERIFIED"
    assert cp.estado_de(d, "T-E") == "FAILED"


def test_una_accion_que_no_esta_en_AUTO_no_se_ejecuta_jamas(tmp_path, monkeypatch):
    d = pathlib.Path(tmp_path)
    monkeypatch.setattr(ag, "_EJECUTORES", {"claude": lambda *a, **k: pytest.fail("no debió llamarse")})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-H", "accion": "modificar_adr"})
    with pytest.raises(ag.AccionNoAutorizada):
        ag.ejecutar_tarea(d, {"id": "T-H", "accion": "modificar_adr", "objetivo": "x"},
                          autoridad="orquestador")


def test_AURA_no_inventa_tareas(tmp_path):
    """*«NO debe inventar tareas nuevas. Solo ejecutar tareas que estén dentro de AUTO»*."""
    d = pathlib.Path(tmp_path)
    o = orq.Orquestador(d)
    assert o.tareas_candidatas() == [], "sin trabajo registrado, no hay trabajo"
    resultado = o.ciclo(max_iteraciones=3)
    assert resultado["ejecutadas"] == 0


# ============================ E2E con EJECUTOR DE PROCESO REAL (no un doble) --


def test_e2e_circuito_completo_con_PROCESO_REAL(tmp_path):
    """El circuito cerrado en verde con un **proceso del sistema de verdad**, no un doble.

    El agente principal está indisponible por cuota —el escenario del bloque— y el secundario es un
    subproceso real que produce un fichero. AURA **no lee lo que el proceso dice**: comprueba el
    fichero. Solo entonces cierra."""
    import subprocess
    import sys as _sys

    d = pathlib.Path(tmp_path)
    informe = d / "informe.txt"

    def sin_cuota(sobre, **_):
        return ag.Respuesta(exit_code=None, motivo="You've hit your monthly spend limit")

    def proceso_real(sobre, **_):
        r = subprocess.run(
            [_sys.executable, "-c",
             f"import platform,pathlib;pathlib.Path(r'{informe}').write_text('estado: '+platform.system())"],
            capture_output=True, text=True, timeout=120)
        return ag.Respuesta(exit_code=r.returncode, salida=r.stdout,
                            afirmacion="informe generado correctamente")

    original = dict(ag._EJECUTORES)
    try:
        ag._EJECUTORES = {"claude": sin_cuota, "opencode": proceso_real}
        cp.registrar_evento(d, "tarea_registrada", {"id": "T-R", "accion": "diagnosticar_estado"})
        resultado = ag.ejecutar_tarea(d, {
            "id": "T-R", "accion": "diagnosticar_estado", "objetivo": "informe",
            "permite_fallback": True,
            "evidencia_requerida": {"tipo": "fichero_existe", "ruta": str(informe)}},
            autoridad="orquestador")
    finally:
        ag._EJECUTORES = original

    assert informe.exists() and informe.read_text(encoding="utf-8"), "el efecto ocurrió de verdad"
    assert resultado["resultado"] == "VERIFIED"
    assert resultado["agente"] == "opencode" and resultado["fallback_usado"] is True
    assert cp.estado_de(d, "T-R") == "COMPLETED"

    intentos = [e["datos"] for e in cp.leer_eventos(d) if e["tipo"] == "intento_de_agente"]
    assert [i["class"] for i in intentos] == [ag.AGENTE_SIN_CUOTA, ag.EXITO]
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_e2e_el_mismo_proceso_SIN_efecto_no_cierra_la_tarea(tmp_path):
    """Caso de control del anterior. Mismo circuito, proceso que **dice** que hizo el trabajo y no lo
    hace. Sin esta prueba, la de arriba no demostraría que la verificación sirve de algo."""
    import subprocess
    import sys as _sys

    d = pathlib.Path(tmp_path)
    informe = d / "informe.txt"

    def mentiroso(sobre, **_):
        r = subprocess.run([_sys.executable, "-c", "print('informe generado correctamente')"],
                           capture_output=True, text=True, timeout=60)
        return ag.Respuesta(exit_code=r.returncode, salida=r.stdout,
                            afirmacion="informe generado correctamente")

    original = dict(ag._EJECUTORES)
    try:
        ag._EJECUTORES = {"claude": mentiroso, "opencode": mentiroso}
        cp.registrar_evento(d, "tarea_registrada", {"id": "T-M", "accion": "diagnosticar_estado"})
        resultado = ag.ejecutar_tarea(d, {
            "id": "T-M", "accion": "diagnosticar_estado", "objetivo": "informe",
            "permite_fallback": True,
            "evidencia_requerida": {"tipo": "fichero_existe", "ruta": str(informe)}},
            autoridad="orquestador")
    finally:
        ag._EJECUTORES = original

    assert not informe.exists()
    assert resultado["resultado"] != "VERIFIED"
    assert cp.estado_de(d, "T-M") == "FAILED", "una afirmación no cierra una tarea"


def test_opencode_como_LLM_esta_bloqueado_por_D24_y_consta():
    """**Bloqueo real, medido `[EJEC]` el 2026-08-26.** `opencode run` responde:

        *«Google Generative AI API key is missing»*

    Es decir: el agente secundario **necesita una clave de terceros para razonar**, y D24 lo prohíbe
    —*«sin claves de terceros»*—. No es una limitación del mecanismo de failover, que funciona: es
    que el ejecutor LLM externo no puede operar sin violar una decisión que no se toca.

    Esta prueba fija el hecho para que nadie lo redescubra ni lo dé por resuelto sin acta."""
    assert "opencode" in ag.CADENA_DE_AGENTES, "sigue autorizado como agente secundario"
    assert ag.BLOQUEO_CONOCIDO["opencode"]["motivo"].startswith("exige clave de proveedor")
    assert "D24" in ag.BLOQUEO_CONOCIDO["opencode"]["decision"]


# ============================================ CONTINUIDAD — el punto prioritario --


def test_continuidad_encadena_tareas_AUTO_sin_intervencion(tmp_path):
    """*«AURA no debe quedar simplemente esperando»*: detecta la indisponibilidad, conserva la TASK,
    registra el motivo, activa el secundario, continúa y pasa a la siguiente."""
    import subprocess
    import sys as _sys

    d = pathlib.Path(tmp_path)
    hechos = []

    def sin_cuota(sobre, **_):
        return ag.Respuesta(exit_code=None, motivo="You've hit your monthly spend limit")

    def secundario(sobre, **_):
        destino = d / f"{sobre['tarea_id']}.txt"
        subprocess.run([_sys.executable, "-c",
                        f"import pathlib;pathlib.Path(r'{destino}').write_text('hecho')"],
                       capture_output=True, timeout=60)
        hechos.append(sobre["tarea_id"])
        return ag.Respuesta(exit_code=0, salida="{}", afirmacion="hecho")

    for i in (1, 2, 3):
        cp.registrar_evento(d, "tarea_registrada",
                            {"id": f"T-{i}", "accion": "diagnosticar_estado",
                             "evidencia_requerida": {"tipo": "fichero_existe",
                                                     "ruta": str(d / f"T-{i}.txt")}})
    original = dict(ag._EJECUTORES)
    try:
        ag._EJECUTORES = {"claude": sin_cuota, "opencode": secundario}
        informe = ag.continuidad(d, autoridad="orquestador", max_tareas=5)
    finally:
        ag._EJECUTORES = original

    assert informe["completadas"] == 3, informe
    assert sorted(hechos) == ["T-1", "T-2", "T-3"]
    assert all(cp.estado_de(d, f"T-{i}") == "COMPLETED" for i in (1, 2, 3))
    assert informe["fallback_usado"] is True


def test_continuidad_NO_inventa_tareas(tmp_path):
    """*«Pero NO debe inventar tareas nuevas»*. Sin trabajo registrado, no hay trabajo."""
    d = pathlib.Path(tmp_path)
    informe = ag.continuidad(d, autoridad="orquestador", max_tareas=5)
    assert informe["completadas"] == 0 and informe["intentadas"] == 0
    assert informe["motivo"] == "sin tareas AUTO pendientes"


def test_continuidad_se_DETIENE_si_ningun_agente_puede_seguir(tmp_path):
    """Si ni el principal ni el secundario pueden, no tiene sentido seguir consumiendo la cola:
    se para y **deja el motivo escrito**, que es lo que permite retomar sin investigar."""
    d = pathlib.Path(tmp_path)
    for i in (1, 2):
        cp.registrar_evento(d, "tarea_registrada", {"id": f"T-{i}", "accion": "diagnosticar_estado"})
    original = dict(ag._EJECUTORES)
    try:
        ag._EJECUTORES = {k: (lambda *a, **kw: ag.Respuesta(exit_code=None, motivo="quota exhausted"))
                          for k in ag.CADENA_DE_AGENTES}
        informe = ag.continuidad(d, autoridad="orquestador", max_tareas=5)
    finally:
        ag._EJECUTORES = original
    assert informe["completadas"] == 0
    assert "agente" in informe["motivo"].lower()
    assert informe["intentadas"] == 1, "se para en la primera, no arrasa la cola entera"


def test_continuidad_es_FINITA(tmp_path):
    d = pathlib.Path(tmp_path)
    for i in range(10):
        cp.registrar_evento(d, "tarea_registrada", {"id": f"T-{i}", "accion": "diagnosticar_estado"})
    original = dict(ag._EJECUTORES)
    try:
        ag._EJECUTORES = {k: (lambda *a, **kw: ag.Respuesta(exit_code=1, motivo="assertion failed"))
                          for k in ag.CADENA_DE_AGENTES}
        informe = ag.continuidad(d, autoridad="orquestador", max_tareas=3)
    finally:
        ag._EJECUTORES = original
    assert informe["intentadas"] <= 3


def test_continuidad_IGNORA_las_tareas_que_no_estan_en_AUTO(tmp_path):
    """Cola mixta: sin este caso el filtro de `AUTO` nunca se ejercitaba y un mutante que lo quitaba
    sobrevivía. Una tarea `HUMAN` en la cola no se toca **ni se marca fallida**: espera al CEO."""
    d = pathlib.Path(tmp_path)
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-AUTO", "accion": "diagnosticar_estado"})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-HUMANA", "accion": "modificar_adr"})
    cp.registrar_evento(d, "tarea_registrada", {"id": "T-RARA", "accion": "accion_inexistente"})

    pendientes = [t["id"] for t in ag.tareas_auto_pendientes(d)]
    assert pendientes == ["T-AUTO"], f"solo AUTO entra en la cola; entraron {pendientes}"

    original = dict(ag._EJECUTORES)
    try:
        ag._EJECUTORES = {k: (lambda *a, **kw: ag.Respuesta(exit_code=1, motivo="assertion failed"))
                          for k in ag.CADENA_DE_AGENTES}
        ag.continuidad(d, autoridad="orquestador", max_tareas=5)
    finally:
        ag._EJECUTORES = original

    assert cp.estado_de(d, "T-HUMANA") == "WAITING_FOR_NEXT_TASK", "intacta, esperando al CEO"
    assert cp.estado_de(d, "T-RARA") == "WAITING_FOR_NEXT_TASK"
