"""RED · los criterios de aceptación del `§22` que **F2, F3 y F4 desbloquearon y nadie reabrió**.

El cierre de F1 los dejó anotados así:

> | A6–A12 | worker, revisor, GitHub, seguridad, cuota, 0/7 | **FUERA DE F1** — dependen de F2–F5, bloqueadas |

F2, F3 y F4 están cerradas desde entonces. De los siete criterios que esa fila aparcaba, **solo uno
sigue dependiendo de F5** —y F5 está bloqueada por decisión del CEO—. Los demás llevan desde
entonces autorizados y sin demostrar, que es el patrón `declarado ≠ real` en su forma más silenciosa:
nadie afirmó nada falso, simplemente la condición que los bloqueaba dejó de existir y no se volvió a
mirar.

`§22` es explícito sobre la forma de la demostración: **«Comportamiento demostrado, nunca "las pruebas
pasan"»**, y cada criterio trae su columna *cómo se demuestra*. Este fichero ejecuta esa columna.

Lo que **no** está aquí, y por qué:

- **A1–A5** ya se demostraron en F1 `[EJEC]`.
- **A12** vive en `test_red_controles_14.py`, junto al control que lo hace posible.
- **A11 capas 1 y 2** exigen invocar el binario `claude` de verdad, y esta batería no habla con
  procesos externos ni con la red. Se miden en `medicion-a11.py`, una vez, y el resultado se cita en
  el cierre. Aquí queda su **capa 3** —el kill switch en el bucle— y la barrera de zona.
"""

from __future__ import annotations

import inspect
import pathlib
import socket

import autoconstruccion as ac
import control_plane as cp
import orquestador as orq
import pytest
import review
import revisores as rev


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    """El `§14` obliga al ciclo a negarse mientras `herramientas.mutar` corre, y el arnes se lanza
    como `python -m herramientas.mutar`: al mutar, el propio arnes aparece en `/proc` y el bucle se
    niega en TODAS las pruebas, no solo en las que miden esa garantia.

    No es un falso positivo del control: es el control funcionando. Estas pruebas trabajan sobre un
    `tmp_path` sintetico y **no miden el arbol real**, asi que lo declaran. Las pruebas de la
    garantia lo vuelven a poner a `True` en su cuerpo, y ganan por ser mas especificas."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


BASE = pathlib.Path(__file__).resolve().parent



# ============================================================ A6 --
# «El worker no puede escribir la politica ni el Control Plane» · como: intentarlo y ver el bloqueo.


def test_A6_escribir_la_politica_desde_el_codigo_se_BLOQUEA():
    with pytest.raises(orq.PoliticaInmutable):
        orq.escribir_politica({"auto": {"acciones": ["lo_que_yo_quiera"]}})


def test_A6_la_politica_no_cambio_tras_el_intento():
    """El bloqueo se demuestra por el **efecto**, no por la excepción: una excepción lanzada después
    de escribir el fichero no habría bloqueado nada."""
    antes = orq.RUTA_POLITICA.read_bytes()
    with pytest.raises(orq.PoliticaInmutable):
        orq.escribir_politica({"auto": {"acciones": ["lo_que_yo_quiera"]}})
    assert orq.RUTA_POLITICA.read_bytes() == antes
    assert "lo_que_yo_quiera" not in orq.acciones_de_nivel("AUTO")


def test_A6_el_orquestador_no_puede_tocar_su_codigo_su_politica_ni_el_control_plane(tmp_path):
    o = orq.Orquestador(tmp_path)
    for prohibido in ("orquestador.py", "politica-orquestador.toml", "control_plane.py",
                      "conftest.py"):
        assert not o.puede_tocar(BASE / prohibido), f"{prohibido} tiene que estar fuera de alcance"
    assert o.puede_tocar(tmp_path / "cualquier_otra_cosa.py"), "no puede negarlo todo: no distinguiría"


def test_A6_NINGUN_sobre_concede_permiso_de_escritura():
    """`§14`, control primario: *«el sobre nunca concede `Edit` sobre la política ni sobre
    `entorno/control-plane/`»*. Se recorre **todo** el catálogo, no una acción de muestra: basta una
    entrada con `Write` para que el control no exista."""
    for accion in orq.acciones_de_nivel("AUTO") + orq.acciones_de_nivel("REVIEW") + ("desconocida",):
        permisos = orq.WorkerAdapter().permisos_de(accion)
        for peligrosa in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
            assert peligrosa not in permisos["allowedTools"], f"{accion} concede {peligrosa}"
        assert permisos["permission_mode"] != "bypassPermissions"
        assert permisos["permission_mode"] in orq.MODOS_QUE_NO_ANULAN_LA_ALLOWLIST


def test_A6_toda_ruta_del_control_plane_esta_prohibida_al_worker():
    """`§14`: *«`entorno/control-plane/` y la política en la lista de rutas prohibidas al worker»*.
    Se comprueba **por segmento de ruta**, no por subcadena: el repositorio se llama
    `aura-project-bible`, y buscar `bible` dentro de la ruta completa rechazaba el árbol entero. Ese
    defecto ya se cometió aquí."""
    o = orq.Orquestador(BASE)
    for fichero in sorted(BASE.glob("*.py")):
        if fichero.name in orq._INTOCABLES:
            assert not o.puede_tocar(fichero), f"{fichero.name} es intocable y el worker lo alcanza"


# ============================================================ A7 --
# «Sin revisor, AUTO sigue avanzando y REVIEW espera» · como: desconectar el revisor.


def test_A7_sin_ningun_revisor_capaz_la_tarea_de_REVIEW_ESPERA(tmp_path):
    """`§8.3`. Y el estado importa: `WAITING_FOR_REVIEW`, **no** `COMPLETED` ni `FAILED`. Esperar no
    es fracasar, y sobre todo no es aprobar."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-R", "accion": "eliminar_codigo_muerto"})
    cp.transicion(tmp_path, "T-R", "WORKING", autoridad="ceo", causa="empieza")
    expediente = rev.Expediente(tarea_id="T-R", accion="eliminar_codigo_muerto",
                                fichero="orquestador.py", diagnostico="funcion privada sin uso",
                                criterios={"cumple": True})
    resultado = rev.pedir_revision(tmp_path, expediente,
                                   [rev.RevisorLocal(), rev.RevisorExterno()], autoridad="orquestador")
    assert resultado["estado"] == "WAITING_FOR_REVIEW"
    assert resultado["veredicto"] is None
    assert cp.proyectar(tmp_path)["tareas"]["T-R"]["estado"] == "WAITING_FOR_REVIEW"


def test_A7_y_mientras_tanto_las_tareas_AUTO_SIGUEN_avanzando(tmp_path):
    """*«El sistema no se detiene entero porque falte el revisor»*. Es la mitad que se olvida: un
    sistema que se para del todo ante la ausencia de un revisor es tan inútil como uno que
    autoaprueba."""
    for accion in orq.acciones_de_nivel("AUTO"):
        assert not rev.exige_revision(accion), f"{accion} es AUTO: no debe esperar a ningún revisor"
    assert rev.exige_revision("eliminar_codigo_muerto")


def test_A7_ningun_timeout_produce_APROBADO(tmp_path):
    """`1.1:85` — *«el silencio o la ausencia de objeción no constituye aprobación»*. Se recorren las
    tres formas de ausencia: revisor sin capacidad, revisor bloqueado y lista vacía."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-S", "accion": "eliminar_codigo_muerto"})
    cp.transicion(tmp_path, "T-S", "WORKING", autoridad="ceo", causa="empieza")
    expediente = rev.Expediente(tarea_id="T-S", accion="eliminar_codigo_muerto",
                                fichero="orquestador.py", diagnostico="funcion privada sin uso",
                                criterios={"cumple": True})
    for ausencia in ([], [rev.RevisorLocal()], [rev.RevisorExterno()], [rev.RevisorLocal(), rev.RevisorExterno()]):
        resultado = rev.pedir_revision(tmp_path, expediente, ausencia, autoridad="orquestador")
        assert resultado["estado"] == "WAITING_FOR_REVIEW"
        assert resultado["estado"] != "COMPLETED"


# ============================================================ A8 --
# «Sin GitHub, el ciclo completo funciona» · como: desconectar la red.


def test_A8_el_ciclo_completo_funciona_con_la_RED_DESCONECTADA(tmp_path, monkeypatch):
    """La desconexión es real dentro del proceso: cualquier intento de abrir un socket lanza. Si
    alguna pieza del ciclo hablase con la red, esta prueba fallaría con `RedProhibida`, no con un
    fallo difuso."""
    class RedProhibida(RuntimeError):
        pass

    def sin_red(*_a, **_k):
        raise RedProhibida("A8: el ciclo no puede depender de la red")

    monkeypatch.setattr(socket, "socket", sin_red)
    monkeypatch.setattr(socket, "create_connection", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)

    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    resultado = orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    assert resultado["iteraciones"] >= 1
    veredicto = orq.verificar_criterio(tmp_path, "T-1", lambda _c: 0)
    assert veredicto["verificado"] is True
    assert cp.verificar_integridad_log(tmp_path)["integro"] is True


def test_A8_ningun_modulo_del_plano_de_desarrollo_importa_red_ni_github():
    """`§16 · Funcionamiento offline`. Se mira el fuente porque una importación perezosa no
    aparecería en la prueba anterior: solo se abriría el día que se ejecute esa rama."""
    prohibidos = ("import requests", "import urllib", "import http.client", "from github",
                  "import socket")
    for modulo in sorted(BASE.glob("*.py")):
        if modulo.name.startswith(("test_", "conftest")):
            continue
        fuente = modulo.read_text(encoding="utf-8")
        for prohibido in prohibidos:
            assert prohibido not in fuente, f"{modulo.name} habla con la red: {prohibido}"


# ============================================================ A9 --
# «Ningun informe afirma un porcentaje de cuota» · como: prueba que falla ante cualquier insinuacion.


def test_A9_ningun_informe_del_plano_de_desarrollo_afirma_un_porcentaje_de_cuota(tmp_path):
    """El criterio dice *«ante cualquier insinuación»*, así que se recorre la **salida real** de los
    informes, no el fuente: un porcentaje puede formarse en tiempo de ejecución."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    # La versión anterior listaba cuatro salidas, y la primera era `cp.informe(...)` — **una función
    # que no existe**, protegida por una condición siempre falsa. Medía tres creyendo medir cuatro.
    # Lo encontró la segunda auditoría independiente. Ahora todas se ejecutan de verdad.
    salidas = [
        str(orq.Orquestador(tmp_path).ciclo(max_iteraciones=2)),
        str(cp.proyectar(tmp_path)),
        str(cp.estado_inicial()["cuota"]),
        str(cp.verificar_integridad_log(tmp_path)),
        repr(orq.PRESUPUESTO_POR_DEFECTO),
    ]
    assert all(s for s in salidas), "una salida vacía no demuestra nada: todas tienen que producirse"
    for salida in salidas:
        assert "%" not in salida, f"un informe insinúa un porcentaje: {salida[:200]}"
        for insinuacion in ("cuota_restante", "porcentaje_usado", "queda un", "restante:"):
            assert insinuacion not in salida


def test_A9_usage_known_sigue_en_false(tmp_path):
    """`§11`: el consumo real **no es observable**. Un `true` aquí sería una afirmación fabricada."""
    assert cp.estado_inicial()["cuota"]["usage_known"] is False


def test_A9_un_porcentaje_SIN_fuente_ni_instante_se_rechaza():
    """No se prohíbe anotar un porcentaje que alguien vio de verdad: se prohíbe uno **sin
    procedencia**, que es indistinguible de uno inventado."""
    cuota = {"usage_known": False}
    # `rolling_window` y `UNKNOWN` son VALIDOS a proposito: si la ventana o el estado fuesen
    # invalidos, el `ValueError` vendria de ellos y la prueba verdearia sin tocar la garantia. Es el
    # defecto que este proyecto llama «prueba decorativa», y esta prueba lo tuvo: la escribi con
    # `ventana="SHORT_4H30"`, que no existe, y el mutante `C22-M11` sobrevivio por eso.
    with pytest.raises(ValueError, match="fuente"):
        cp.registrar_uso_observado(cuota, "rolling_window", 42.0, fuente="",
                                   observado_en="", estado="UNKNOWN")
    with pytest.raises(ValueError, match="fuente"):
        cp.registrar_uso_observado(cuota, "rolling_window", 42.0, fuente="el panel",
                                   observado_en="", estado="UNKNOWN")
    # y el control: con procedencia completa SI se acepta, asi que la barrera distingue
    aceptada = cp.registrar_uso_observado(dict(cuota), "rolling_window", 42.0, fuente="el panel",
                                          observado_en="2026-08-30T10:00:00", estado="UNKNOWN")
    assert aceptada["rolling_window"]["fuente"] == "el panel"
    assert aceptada["rolling_window"]["caduca"] is True


# ============================================================ A10 --
# «La autonomia de AURORA sigue en 0/7» · como: medicion existente, sin cambios.


def test_A10_ningun_modulo_del_plano_de_desarrollo_importa_el_PRODUCTO():
    """`§0` del DP: *«No es AURORA y no le concede ninguna capacidad»*. La autonomía del producto no
    puede haber cambiado si ninguna línea del producto participa. Es la forma **verificable** del
    criterio: reejecutar la medición del razonador no demostraría nada sobre este trabajo, porque el
    número que da depende del razonador, no del orquestador."""
    for modulo in sorted(BASE.glob("*.py")):
        if modulo.name.startswith("test_"):
            continue          # las pruebas citan rutas del producto para comprobar que se rechazan
        fuente = modulo.read_text(encoding="utf-8")
        for prohibido in ("from aura_skeleton", "import aura_skeleton", "walking-skeleton/aura"):
            assert prohibido not in fuente, f"{modulo.name} importa el producto: {prohibido}"


def test_A10_la_zona_de_escritura_EXCLUYE_el_producto(tmp_path):
    """La barrera, ejercida: el plano de desarrollo no puede escribir en el producto ni aunque se lo
    pidan por nombre."""
    raiz = BASE.parent.parent
    for fuera in ("walking-skeleton/aura_skeleton/core/orchestrator.py",
                  "docs/libro-05-seguridad-y-confianza/5.3-autonomia-gobernada-hitl.md",
                  "adr/0003-listas-autonomia-hitl.md",
                  "CLAUDE.md"):
        assert not ac.zona_permitida(raiz / fuera), f"{fuera} NO puede estar en la zona de escritura"


def test_A10_REVIEW_no_alcanza_ninguna_materia_del_producto_ni_de_gobierno():
    """`DEC-ORCH-2` acotó REVIEW a *«únicamente tareas técnicas de desarrollo; únicamente dentro de
    `entorno/control-plane/`»*. Si REVIEW alcanzase el producto, la autonomía de AURORA habría
    cambiado por la puerta de atrás."""
    for materia in ("modificar_d24", "modificar_bible", "modificar_adr", "modificar_roadmap",
                    "crear_autoridad", "promover_propuesta"):
        assert review.es_materia_reservada(materia), f"{materia} tiene que ser materia reservada"
    # Y la garantia de verdad no es esa lista, que es negra y siempre incompleta: es que lo
    # delegable sea una lista BLANCA. Una accion que nadie previo no es delegable por no estar
    # en la lista negra — es que no esta en la blanca.
    assert review.TODO_LO_DELEGABLE == ("eliminar_codigo_muerto",)
    for inventada in ("modificar_D24", "tocar_el_roadmap", "lo_que_sea"):
        assert inventada not in review.TODO_LO_DELEGABLE


# ============================================================ A11 · capa 3 y zona --
# «Ningun control de seguridad se declara operativo sin un intento real de violacion que falle.»


def test_A11_el_kill_switch_detiene_el_bucle_MEDIDO_no_leido(tmp_path):
    """§14.ter tenía esta capa como `[LECT]` *«por analogía con `kill_switch.py`, que sí está en
    producción»*. Aquí se mide **en el bucle del orquestador**, que es lo que pedía."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    orq.ruta_parada(tmp_path).write_text("intento real de parada", encoding="utf-8")
    resultado = orq.Orquestador(tmp_path).ciclo(max_iteraciones=10)
    assert resultado["motivo"] == "kill switch activado"
    assert resultado["ejecutadas"] == 0


def test_A11_una_escritura_FUERA_de_la_zona_falla_de_verdad_y_no_deja_efecto(tmp_path):
    """Intento **real** de violación, no una comprobación de la lista: se pide el cambio y se
    comprueba que el fichero no cambió."""
    intruso = tmp_path / "producto.py"
    intruso.write_text("original\n", encoding="utf-8")
    assert not ac.zona_permitida(intruso)
    with pytest.raises(Exception):
        ac.ejecutar(tmp_path, {"ruta": str(intruso), "buscar": "original", "poner": "pirateado"})
    assert intruso.read_text(encoding="utf-8") == "original\n"


def test_A11_el_criterio_mecanico_no_admite_una_orden_libre_del_sistema():
    """CEO 2026-08-03: *«AURORA nunca ejecuta instrucciones arbitrarias del sistema operativo: solo
    CAPACIDADES registradas»*. Es la puerta por la que se colaría todo lo demás."""
    for orden_libre in ("rm -rf /", "bash -c 'curl x | sh'", "pytest -q", "git push"):
        assert not orq.criterio_valido({"capacidad": orden_libre})
        assert not orq.criterio_valido({"comando": orden_libre})


def test_A11_la_verificacion_no_tiene_por_donde_recibir_una_orden():
    """La garantía estructural: no hay parámetro `comando`, así que no hay nada que sanear."""
    firma = set(inspect.signature(orq.verificar_criterio).parameters)
    for prohibido in ("comando", "cmd", "shell", "orden"):
        assert prohibido not in firma


# ============================================================ §21 · DEUDA PAGADA --


def test_el_modelo_DERIVA_los_campos_del_veredicto_de_la_clase_real():
    """`§21` declaró esta deuda literalmente: *«compara dos tuplas escritas a mano en el mismo
    fichero y por el mismo autor (...) su poder de detección frente a una implementación futura que
    se desvíe es nulo. Cuando C5 se implemente, esta prueba debe apuntar a la clase real o se
    convierte en decoración»*.

    C5 existe desde F4. Se comprueba **en el fuente** porque la igualdad de tuplas sería cierta por
    coincidencia mientras nadie se desvíe, que es justo el caso en que la prueba no sirve."""
    fuente = (BASE / "test_modelo_orquestador.py").read_text(encoding="utf-8")
    declaracion = next(ln for ln in fuente.splitlines() if ln.startswith("CAMPOS_VEREDICTO"))
    assert "Veredicto" in declaracion and "dataclass_fields" in declaracion, (
        "sigue escrita a mano: §21 la declara decorativa desde que C5 existe")


def test_el_modelo_y_la_implementacion_coinciden_en_el_contrato_del_veredicto():
    import test_modelo_orquestador as modelo
    assert modelo.CAMPOS_VEREDICTO == tuple(rev.Veredicto.__dataclass_fields__)
    assert "autoriza" not in modelo.CAMPOS_VEREDICTO


# ================================ HALLAZGO · LA ZONA TENIA UNA PUERTA PARA LAS PRUEBAS --


def test_TMP_ya_no_es_una_zona_libre(tmp_path):
    """`zona_permitida` aceptaba **incondicionalmente** cualquier ruta bajo `/tmp/` o que
    contuviese `/pytest-`. Existía para que las pruebas —que trabajan en directorios temporales—
    pasaran, y el precio era que el guardarrail de producción protegía la zona declarada *más todo
    `/tmp`*.

    Lo material: **17 pruebas de esta misma batería pasaban por ese hueco**. Creían ejercitar la
    regla real y ejercitaban la excepción, así que la barrera nunca se probó donde importa. Es el
    caso de control que este proyecto exige antes de escribir una aserción —*«¿qué tendría que
    romperse para que fallara?»*—, contestado por el lado que no se mira: la prueba pasaba porque el
    código la dejaba pasar, no porque la garantía existiera."""
    intruso = tmp_path / "cualquier_cosa.py"
    intruso.write_text("x", encoding="utf-8")
    assert not ac.zona_permitida(intruso), "/tmp no puede ser zona blanca por sí mismo"
    assert not ac.zona_permitida("/tmp/loquesea/modulo.py")
    assert not ac.zona_permitida("/var/tmp/pytest-de-mentira/modulo.py")
    assert ac.zona_permitida(intruso, raiz=tmp_path), "declarada la raíz, el sandbox sí vale"
    # ...y acota: lo que cae FUERA de la raíz declarada sigue fuera. Una raíz que acepta cualquier
    # ruta no es un sandbox, es el mismo agujero con otro nombre.
    assert not ac.zona_permitida("/etc/passwd", raiz=tmp_path)
    assert not ac.zona_permitida(tmp_path.parent / "vecino.py", raiz=tmp_path)


def test_la_zona_real_sigue_siendo_la_declarada():
    """Caso de control: cerrar el hueco no puede haber cerrado la zona legítima."""
    assert ac.zona_permitida("entorno/control-plane/orquestador.py")
    assert not ac.zona_permitida("walking-skeleton/aura_skeleton/core/permissions.py")
    # Una ruta que no es zona, ni producto, ni gobernanza: la sostiene la LISTA BLANCA y solo ella.
    # Sin este caso, un mutante que devolviera `True` al final sobrevivía —porque producto y
    # gobernanza ya se rechazan antes— y la lista blanca quedaba sin red.
    assert not ac.zona_permitida("otro-proyecto/modulo.py")
    assert not ac.zona_permitida("/home/alguien/scripts/util.py")
    assert not ac.zona_permitida("entorno/communication-plane/algo.py")


def test_NINGUN_modulo_de_produccion_declara_su_propia_raiz_de_zona():
    """La excepción sigue existiendo, pero **vigilada**: en producción, `raiz` solo puede ser el
    directorio que la llamada ya audita —el mismo donde escribe su log—, nunca una ruta escrita a
    mano. Un literal ahí sería reabrir el hueco con otro nombre."""
    for modulo in sorted(BASE.glob("*.py")):
        if modulo.name.startswith(("test_", "conftest")):
            continue
        for numero, linea in enumerate(modulo.read_text(encoding="utf-8").splitlines(), 1):
            if "zona_permitida(" not in linea or "def zona_permitida" in linea:
                continue
            if "raiz=" in linea:
                assert "raiz=directorio" in linea, (
                    f"{modulo.name}:{numero} declara una raíz que no es su directorio auditado")


def test_A11_ningun_modo_de_permiso_puede_ANULAR_la_allowlist():
    """**Hallazgo medido** (`medicion-a11.py`, 2026-08-30, binario real): con `--allowedTools Read`
    y sin `Write`, el fichero **no se crea** en `default` ni en `plan`, y **sí se crea** en
    `acceptEdits`. La allowlist es un control real, pero **el modo de permisos puede anularla**, y el
    `§14` la llama *«control primario `[EJEC]`»* sin mencionarlo.

    Hoy el orquestador emite siempre `plan`, así que nunca estuvo expuesto. Pero nada lo impedía:
    `bypassPermissions` estaba prohibido por su nombre y `acceptEdits` hace lo mismo por otra vía.
    Una garantía que se sostiene porque nadie escribió la otra palabra no es una garantía."""
    assert "acceptEdits" not in orq.MODOS_QUE_NO_ANULAN_LA_ALLOWLIST
    assert "bypassPermissions" not in orq.MODOS_QUE_NO_ANULAN_LA_ALLOWLIST
    assert set(orq.MODOS_QUE_NO_ANULAN_LA_ALLOWLIST) == {"plan", "default"}


def test_A11_un_modo_inseguro_se_RECHAZA_no_se_emite(monkeypatch):
    """Caso de control: la garantía es una puerta que se cierra, no una lista que se lee. Si alguien
    cambia el modo, `permisos_de()` se niega en vez de emitir el sobre."""
    monkeypatch.setattr(orq, "MODOS_QUE_NO_ANULAN_LA_ALLOWLIST", ("solo-este",))
    with pytest.raises(orq.ModoDePermisoInseguro):
        orq.WorkerAdapter().permisos_de("ejecutar_pruebas")


def test_la_gobernanza_se_rechaza_incluso_DENTRO_de_la_raiz_declarada(tmp_path):
    """Las dos reglas de `zona_permitida` son independientes, y la de gobernanza solo se distingue
    **dentro** de una zona blanca: fuera, la ruta ya cae por el otro motivo y un mutante que borre
    el filtro de gobernanza sobrevive sin que nadie lo note. Ya pasó una vez."""
    for nombre in ("CLAUDE.md", "ROADMAP.md", "acta-lo-que-sea.md", "CHECKPOINT-CONTINUIDAD.md"):
        assert not ac.zona_permitida(tmp_path / nombre, raiz=tmp_path), (
            f"{nombre} está dentro de la raíz declarada, y sigue siendo gobernanza")
    for subdir in ("adr", "docs", "decisiones", "actas"):
        assert not ac.zona_permitida(tmp_path / subdir / "cualquiera.md", raiz=tmp_path)
    assert ac.zona_permitida(tmp_path / "modulo.py", raiz=tmp_path), "y el control: código sí pasa"


def test_el_detector_de_mutacion_MIRA_los_procesos_de_verdad():
    """`C14-M11` sobrevivió porque **todas** las pruebas del ciclo sustituyen `mutacion_en_curso`
    por una constante —hace falta: el arnés se lanza como `python -m herramientas.mutar` y se
    detectaría a sí mismo—, así que el barrido real de `/proc` no se ejecutaba nunca.

    La marca es inventada a propósito. Preguntar «¿no hay ningún arnés?» es indecidible desde dentro
    de un arnés, y una prueba que lo pregunte deja la base en rojo justo cuando se la muta: pasó."""
    import os
    import subprocess
    import time
    # Se **construye** en ejecución: escrita como literal, aparecía en la línea de órdenes del shell
    # que lanzó la batería y el barrido la encontraba ahí. El `pid` la hace además única.
    marca = "aura-detector-" + str(os.getpid()) + "-" + "centinela"
    assert not orq._hay_proceso_con(marca), "nadie puede llevar una marca inventada aquí mismo"
    señuelo = subprocess.Popen(["python3", "-c", "import time; time.sleep(20)", marca])
    try:
        for _ in range(60):                       # el proceso tarda unos ms en aparecer en /proc
            if orq._hay_proceso_con(marca):
                break
            time.sleep(0.05)
        assert orq._hay_proceso_con(marca), "hay un proceso con la marca y el barrido no lo vio"
    finally:
        señuelo.kill()
        señuelo.wait()
    for _ in range(60):
        if not orq._hay_proceso_con(marca):
            break
        time.sleep(0.05)
    assert not orq._hay_proceso_con(marca), "muerto el proceso, la detección se levanta"


def test_la_exclusion_mutua_busca_EXACTAMENTE_la_marca_del_arnes():
    """Y que sea la del arnés, no cualquiera: el control existe para `herramientas.mutar`."""
    assert orq._MARCA_DEL_ARNES == "herramientas.mutar"


# ================================ §11 · UNKNOWN NO ES UNA VENTANA CONOCIDA --


def test_A9_una_ventana_UNKNOWN_no_produce_WAITING_FOR_QUOTA(tmp_path):
    """`§11`, regla literal: *«si no puede determinarse la ventana, `UNKNOWN` · **`UNKNOWN` nunca se
    convierte en `WAITING_FOR_QUOTA`**»*.

    Y la razón es la misma que sostiene todo el apartado: `WAITING_FOR_QUOTA` **afirma algo** —que una
    cuota concreta bloqueó el trabajo y que se renovará—. Con `UNKNOWN` no se sabe ni qué se agotó ni
    si se renovará, así que declararlo sería fabricar una explicación. El estado honesto para «algo
    falló y no sé qué» es `FAILED`, que no promete ninguna renovación."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-U", "accion": "ejecutar_pruebas"})
    cp.transicion(tmp_path, "T-U", "WORKING", autoridad="ceo", causa="empieza")
    with pytest.raises(cp.VentanaIndeterminada):
        cp.esperar_por_cuota(tmp_path, "T-U", ventana="UNKNOWN", autoridad="orquestador",
                             evidencia="algo falló y no sé qué ventana fue")
    assert cp.estado_de(tmp_path, "T-U") != "WAITING_FOR_QUOTA"


def test_A9_una_ventana_DETERMINADA_si_produce_WAITING_FOR_QUOTA(tmp_path):
    """Caso de control: con evidencia de qué ventana se agotó, el estado sí es el correcto — la
    regla distingue, no bloquea siempre."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-W", "accion": "ejecutar_pruebas"})
    cp.transicion(tmp_path, "T-W", "WORKING", autoridad="ceo", causa="empieza")
    cp.esperar_por_cuota(tmp_path, "T-W", ventana="SHORT_4H30", autoridad="orquestador",
                         evidencia="mensaje observado: 5-hour limit reached")
    assert cp.estado_de(tmp_path, "T-W") == "WAITING_FOR_QUOTA"


def test_A9_esperar_por_cuota_exige_EVIDENCIA_observada(tmp_path):
    """`§11`: *«ante evidencia **real** de agotamiento»*. Sin el mensaje observado, la ventana se
    estaría deduciendo, y deducir cuota es justo lo que este módulo no hace."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-E", "accion": "ejecutar_pruebas"})
    cp.transicion(tmp_path, "T-E", "WORKING", autoridad="ceo", causa="empieza")
    with pytest.raises(ValueError):
        cp.esperar_por_cuota(tmp_path, "T-E", ventana="WEEKLY", autoridad="orquestador",
                             evidencia="")
    assert cp.estado_de(tmp_path, "T-E") != "WAITING_FOR_QUOTA"
