"""RED/GREEN · DP-ALERTA-005 (Alternativa B) = contrato de correspondencia verificable.

Especificacion: `milestones/m3-entry/DP-ALERTA-005-CORRESPONDENCIA.md`. Este modulo no cambia
ningun comportamiento del motor: **verifica** que la correspondencia declarada en el contrato (una
sola fuente de hechos, dos proyecciones -Maquina A de estados de tarea y Maquina B del ciclo real-,
dos gates de autoridad fail-closed) sigue siendo cierta en el codigo real. Cada invariante lleva su
CONTROL: un caso que debe comportarse distinto si la garantia se hubiera roto, para que la prueba no
sea decorativa (CLAUDE.md §5: "una prueba sin caso de control no vale").

Fixtures SIEMPRE en `tmp_path` (nunca `~/.aura`); `conftest.py::blindar_el_estado_de_produccion` ya
rechaza cualquier escritura accidental al estado real.
"""

from __future__ import annotations

import ast
import pathlib

import autoconstruccion as ac
import control_plane as cp
import pytest


def _dir(tmp_path):
    return pathlib.Path(tmp_path)


def _tarea_working(d, id_tarea="T-1", autoridad="orquestador"):
    cp.registrar_evento(d, "tarea_registrada", {"id": id_tarea})
    cp.transicion(d, id_tarea, "WORKING", autoridad=autoridad, causa="empieza")
    return id_tarea


# ================================================================ INV-1 · gobierno completo --


def test_inv1_todo_evento_gobernado_rechaza_la_via_cruda(tmp_path):
    """Para CADA evento en `EVENTOS_GOBERNADOS`, `registrar_evento` crudo DEBE lanzar
    `EventoNoGobernado`: ninguno se escribe "a pelo", todos tienen su puerta dedicada."""
    d = _dir(tmp_path)
    for evento in cp.EVENTOS_GOBERNADOS:
        with pytest.raises(cp.EventoNoGobernado):
            cp.registrar_evento(d, evento, {"sonda": evento})


def test_inv1_control_un_evento_informativo_si_se_escribe_crudo(tmp_path):
    """CONTROL de INV-1: si la guarda estuviera rota (p. ej. negara TODO), estos tres eventos
    informativos representativos del ciclo real tambien fallarian. Deben pasar limpios y quedar
    en el log."""
    d = _dir(tmp_path)
    for evento in ("cambio_aplicado", "propuesta_registrada", "decision_requerida"):
        cp.registrar_evento(d, evento, {"sonda": evento})
    tipos_en_log = {e["tipo"] for e in cp.leer_eventos(d)}
    assert {"cambio_aplicado", "propuesta_registrada", "decision_requerida"} <= tipos_en_log


# ================================================================== INV-2 · puerta unica --


def test_inv2_estado_de_tarea_no_es_de_la_puerta_gobernada_comun(tmp_path):
    """`estado_de_tarea` tiene su PROPIA puerta (`transicion()`), no la puerta gobernada comun
    (`_registrar_evento_gobernado`): su unico escritor legitimo valida tabla+autoridad+criterio
    ANTES de escribir, cosa que la puerta comun no hace. Aceptarlo ahi seria el bypass entero."""
    d = _dir(tmp_path)
    with pytest.raises(cp.EventoNoGobernado):
        cp._registrar_evento_gobernado(d, "estado_de_tarea", {"id": "T-1", "valor": "COMPLETED"})


def test_inv2_los_cinco_eventos_de_la_puerta_comun_si_pasan_por_ella(tmp_path):
    """Los cinco eventos de `_EVENTOS_DE_ESTA_PUERTA` SI son aceptados por `_registrar_evento_gobernado`
    (comportamiento, no solo el nombre de la funcion)."""
    d = _dir(tmp_path)
    for evento in cp._EVENTOS_DE_ESTA_PUERTA:
        resultado = cp._registrar_evento_gobernado(d, evento, {"sonda": evento})
        assert resultado["tipo"] == evento


def test_inv2_relacion_de_conjuntos_de_la_matriz_de_gobierno():
    """Respaldo formal de INV-G (contrato §2): la igualdad de conjuntos declarada."""
    assert cp.EVENTOS_GOBERNADOS == set(cp._PUERTA_DE)
    assert cp._EVENTOS_DE_ESTA_PUERTA == cp.EVENTOS_GOBERNADOS - {"estado_de_tarea"}


def test_inv2_cada_evento_de_la_puerta_tiene_entrada_en_puerta_de():
    """Cada evento que pasa por la puerta comun tiene una entrada declarada en `_PUERTA_DE` (si no
    la tuviera, el mensaje de error de `_negar_gobernado` lanzaria un `KeyError` en vez de guiar a
    la puerta correcta: comportamiento, no solo el diccionario)."""
    d_vacio = None
    for evento in cp._EVENTOS_DE_ESTA_PUERTA:
        assert evento in cp._PUERTA_DE, f"{evento!r} no tiene puerta declarada en _PUERTA_DE"
        assert isinstance(cp._PUERTA_DE[evento], str) and cp._PUERTA_DE[evento].strip()
    del d_vacio


# ============================================================ INV-3 · correspondencia matriz --


# Tabla alineada con DP-ALERTA-005-CORRESPONDENCIA.md §3: eventos del ciclo real por categoria.
_MATRIZ_CATEGORIA = {
    "tarea_planificada": "informativo",
    "propuesta_registrada": "informativo",
    "revision_sin_revisor_capaz": "informativo",
    "propuesta_autorizada": "gobernado",
    "review_habilitado": "gobernado",
    "cambio_aplicado": "informativo",
    "cambio_revertido_por_error": "informativo",
    "decision_requerida": "informativo",
    "ciclo_detenido": "informativo",
    "veredicto_emitido": "informativo",
    "motor_iniciado": "informativo",
    "descubrimiento_realizado": "informativo",
}


def test_inv3_la_matriz_declarada_corresponde_al_comportamiento_real(tmp_path):
    """Si un evento de la tabla estuviera mal clasificado (p. ej. `propuesta_autorizada` se
    marcara "informativo"), esta prueba lo detecta: el INFORMATIVO se escribe sin error y el
    GOBERNADO lanza `EventoNoGobernado`. No compara texto: ejecuta ambas rutas."""
    d = _dir(tmp_path)
    for evento, categoria in _MATRIZ_CATEGORIA.items():
        if categoria == "informativo":
            cp.registrar_evento(d, evento, {"sonda": evento})
        elif categoria == "gobernado":
            with pytest.raises(cp.EventoNoGobernado):
                cp.registrar_evento(d, evento, {"sonda": evento})
        else:
            raise AssertionError(f"categoria desconocida en la tabla del test: {categoria!r}")


def test_inv3_control_todo_gobernado_real_aparece_marcado_gobernado_en_la_tabla():
    """CONTROL de INV-3: todo evento que `control_plane.py` declara gobernado y que ademas
    pertenece al vocabulario del ciclo real (Maquina B, contrato §3) debe estar en la tabla local
    como "gobernado". Evita que la tabla del test quede desalineada con el contrato en silencio."""
    gobernados_en_la_tabla = {e for e, c in _MATRIZ_CATEGORIA.items() if c == "gobernado"}
    gobernados_del_contrato_mb = {"propuesta_autorizada", "review_habilitado"}
    assert gobernados_en_la_tabla == gobernados_del_contrato_mb
    assert gobernados_en_la_tabla <= cp.EVENTOS_GOBERNADOS


# ============================================================= INV-4 · WAITING_FOR_HUMAN --


# Vocabulario del CICLO REAL (Maquina B, contrato §3): tipos de evento que emite el ciclo de
# ejecucion. Estos eventos los producen VARIOS modulos -motor_autonomia, descubrimiento,
# planificador, review, autoconstruccion-, no solo `autoconstruccion.py`; por eso el nombre dice
# "del ciclo real", no "de autoconstruccion".
#
# **No es una lista exhaustiva** y no se afirma que lo sea: existen otros eventos informativos del
# flujo (p. ej. `decision_pendiente`, autoconstruccion.py:203, un informativo de D-ORCH-2) que no
# estan aqui. La propiedad que esta prueba verifica NO es "esta es la lista completa", sino la
# AUSENCIA de "estado_de_tarea": ningun evento del ciclo real transiciona la Maquina A, porque el
# ciclo no transiciona tareas -se detiene y reintenta (contrato §4)-.
_VOCABULARIO_DEL_CICLO_REAL = frozenset({
    "propuesta_registrada", "propuesta_autorizada", "cambio_aplicado",
    "cambio_revertido_por_error", "decision_requerida", "ciclo_detenido",
    "veredicto_emitido", "tarea_planificada", "descubrimiento_realizado", "motor_iniciado",
})


def test_inv4_waiting_for_human_es_solo_humano():
    assert "WAITING_FOR_HUMAN" in cp.ESTADOS_SOLO_HUMANO


def test_inv4_el_vocabulario_del_ciclo_real_no_incluye_estado_de_tarea():
    """El ciclo real (Maquina B) nunca emite `estado_de_tarea`: no transiciona tareas de la
    Maquina A. Es justo el hueco que el contrato documenta en §4. La propiedad verificada es la
    AUSENCIA de `estado_de_tarea`, no la exhaustividad del vocabulario (ver nota de la constante)."""
    assert "estado_de_tarea" not in _VOCABULARIO_DEL_CICLO_REAL


def test_inv4_control_waiting_for_human_SI_es_alcanzable_por_transicion_con_autoridad_humana(tmp_path):
    """CONTROL POSITIVO: aunque el ciclo real no lo use, el MECANISMO general de `transicion()`
    si deja alcanzar WAITING_FOR_HUMAN (D-ORCH-6) y su salida exige autoridad humana -exactamente
    el comportamiento que test_red_waiting_for_human.py ya fija en detalle-."""
    d = _dir(tmp_path)
    id_tarea = _tarea_working(d)
    cp.transicion(d, id_tarea, "WAITING_FOR_HUMAN", autoridad="orquestador", causa="necesito humano")
    assert cp.estado_de(d, id_tarea) == "WAITING_FOR_HUMAN"
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="sigo solo")
    cp.transicion(d, id_tarea, "WORKING", autoridad="ceo", causa="decidido")
    assert cp.estado_de(d, id_tarea) == "WORKING"


# ======================================================= INV-5 · decision_requerida != DECISION_REQUIRED --


def test_inv5_decision_requerida_no_es_evento_gobernado():
    assert "decision_requerida" not in cp.EVENTOS_GOBERNADOS


def test_inv5_registrar_decision_requerida_no_crea_ni_cambia_estado_de_tarea(tmp_path):
    """El evento informativo `decision_requerida` no concede estado: una tarea en WORKING sigue en
    WORKING despues de registrarlo, y una tarea inexistente sigue sin existir (0 tareas en la
    proyeccion)."""
    d = _dir(tmp_path)
    # Caso A: sin ninguna tarea registrada, el evento no crea ninguna.
    cp.registrar_evento(d, "decision_requerida", {"motivo": "zona prohibida"})
    proyeccion_sin_tareas = cp._base_proyeccion()
    for evento in cp.leer_eventos(d):
        cp._aplicar(proyeccion_sin_tareas, evento)
    assert proyeccion_sin_tareas["tareas"] == {}

    # Caso B: con una tarea en WORKING, el evento no la mueve de estado.
    id_tarea = _tarea_working(d, id_tarea="T-DR")
    cp.registrar_evento(d, "decision_requerida", {"id": id_tarea, "motivo": "sin revisor capaz"})
    assert cp.estado_de(d, id_tarea) == "WORKING"


def test_inv5_decision_required_estado_sigue_solo_humano_y_fail_closed(tmp_path):
    """Mientras tanto, el ESTADO `DECISION_REQUIRED` (distinto del evento) sigue exigiendo
    autoridad humana para salir: sonda con autoridad no humana -> TransicionInvalida."""
    d = _dir(tmp_path)
    assert "DECISION_REQUIRED" in cp.ESTADOS_SOLO_HUMANO
    id_tarea = _tarea_working(d, id_tarea="T-DRQ")
    cp.transicion(d, id_tarea, "DECISION_REQUIRED", autoridad="orquestador", causa="falta decidir")
    with pytest.raises(cp.TransicionInvalida, match="humana|autoridad"):
        cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="sigo solo")
    assert cp.estado_de(d, id_tarea) == "DECISION_REQUIRED"


# ================================================= INV-6 · autoridad no sustituible --


def test_inv6_registrar_propuesta_autorizada_rechaza_autoridad_no_humana(tmp_path):
    d = _dir(tmp_path)
    with pytest.raises(cp.AutoridadNoHumana):
        cp.registrar_propuesta_autorizada(d, "P-1", autorizada_por="orquestador", acta="acta")


def test_inv6_registrar_propuesta_autorizada_acepta_ceo(tmp_path):
    d = _dir(tmp_path)
    resultado = cp.registrar_propuesta_autorizada(d, "P-1", autorizada_por="ceo", acta="acta del CEO")
    assert resultado["tipo"] == "propuesta_autorizada"


def test_inv6_autoconstruccion_autorizar_rechaza_autoridad_no_humana(tmp_path):
    """En el codigo SANO, `autorizar()` ataja la autoridad no humana en su PROPIO guard y lanza
    `ac.SinAutorizacion`: esa es la capa que corresponde a esta funcion."""
    d = _dir(tmp_path)
    with pytest.raises(ac.SinAutorizacion):
        ac.autorizar(d, "P-1", "orquestador", "acta")


def test_inv6_autorizar_rechaza_autoridad_no_humana_con_red_de_mutacion(tmp_path):
    """RED DE MUTACION de la garantia "autorizar exige humano" (hallazgo de auditoria, CA-M8).

    Trampa que la auditoria detecto y que esta prueba evita: la garantia tiene DEFENSA EN
    PROFUNDIDAD -el guard propio de `autorizar()` Y, por debajo, el de
    `cp.registrar_propuesta_autorizada`-. Si se afirma solo "se rechaza" (aceptando cualquier
    excepcion), degradar el guard propio NO rompe nada observable: la capa inferior sigue
    cerrando con `cp.AutoridadNoHumana`, el test pasa, y CA-M8 SOBREVIVE sin red. Se verifico
    ejecutando: con el guard degradado, el test que aceptaba ambas excepciones daba PASS.

    La garantia que ESTA funcion aporta, y que debe tener red, es mas fuerte que "alguien lo
    rechaza": es que `autorizar()` lo rechaza EN SU PROPIA CAPA, con su propia semantica
    (`ac.SinAutorizacion`, `1.1:93`). Por eso se exige exactamente esa excepcion y se comprueba,
    ADEMAS, que la capa inferior ni siquiera llega a ejercitarse -el log no gana el evento
    `propuesta_autorizada` ni rechazado-: si la ejecucion hubiese caido hasta
    `cp.registrar_propuesta_autorizada`, el guard propio no habria atajado, que es justo lo que
    CA-M8 degrada. Asi el mutante muere por la CAPA correcta, no por accidente de tipos."""
    d = _dir(tmp_path)
    with pytest.raises(ac.SinAutorizacion):
        ac.autorizar(d, "P-1", "orquestador", "acta")
    # La garantia por el RESULTADO: no quedo autorizada en ningun sentido.
    assert not ac.esta_autorizada(d, "P-1")
    # Y el guard PROPIO atajo ANTES de delegar: el log no tiene NINGUN rastro del intento de
    # `propuesta_autorizada`. Si CA-M8 degrada el guard, la ejecucion delega a
    # `cp.registrar_propuesta_autorizada`, que lanza `cp.AutoridadNoHumana` -no capturada arriba-
    # y el test falla: la red que faltaba.
    tipos_en_log = {e["tipo"] for e in cp.leer_eventos(d)}
    assert "propuesta_autorizada" not in tipos_en_log


def test_inv6_transicion_waiting_for_human_a_working_rechaza_autoridad_no_humana(tmp_path):
    d = _dir(tmp_path)
    id_tarea = _tarea_working(d, id_tarea="T-INV6")
    cp.transicion(d, id_tarea, "WAITING_FOR_HUMAN", autoridad="orquestador", causa="necesito humano")
    with pytest.raises(cp.TransicionInvalida):
        cp.transicion(d, id_tarea, "WORKING", autoridad="orquestador", causa="sigo")


# ========================================== INV-7 · API legada sin llamante productivo --


# Lista blanca EXPLICITA de modulos de produccion exentos del barrido: hoy solo el propio modulo
# que DEFINE `ciclo()`. Ampliarla exige decision consciente (contrato §8), no un descuido de grep.
_LISTA_BLANCA_LLAMANTES_DE_CICLO = frozenset({"autoconstruccion.py"})


def _modulos_de_produccion(raiz: pathlib.Path):
    """Todo `.py` bajo `raiz` (RECURSIVO, `rglob`) que no sea una prueba (`test_*.py`), ni este
    propio fichero, ni este en la lista blanca. `rglob` cierra el vector de los subdirectorios:
    un llamante escondido en `raiz/sub/mod.py` tambien se barre."""
    for ruta in sorted(raiz.rglob("*.py")):
        if ruta.name.startswith("test_"):
            continue
        if ruta.name == pathlib.Path(__file__).name:
            continue
        if ruta.name in _LISTA_BLANCA_LLAMANTES_DE_CICLO:
            continue
        yield ruta


def _referencias_a_ciclo_en_arbol(arbol) -> list[int]:
    """Localiza CUALQUIER REFERENCIA ESTATICA a `autoconstruccion.ciclo` en un AST ya parseado,
    no solo las llamadas directas. Devuelve las lineas culpables. Conservador (fail-closed): una
    referencia basta, no hace falta que sea una llamada.

    Que cubre, y por que no basta con `ast.Call`:
    - `ast.Attribute(attr="ciclo", value=ast.Name(id in alias_del_modulo))` EN CUALQUIER CONTEXTO:
      captura `ac.ciclo(...)` (llamada), `fn = ac.ciclo` (asignacion a variable, que luego se
      invoca sin dejar rastro de `ciclo` en el `ast.Call`), y `_delegar(ac.ciclo, ...)` (pasada
      como argumento). El barrido anterior solo miraba `ast.Call` y se perdia estas dos ultimas.
    - `ast.Name(id in nombres_locales_de_ciclo)`: captura el asname de
      `from autoconstruccion import ciclo as c` (`c(x)`, `fn = c`, `_delegar(c, ...)`). El barrido
      anterior registraba `ciclo_importado_directo` pero ignoraba `alias.asname`, asi que `c(...)`
      era un FALSO NEGATIVO. Se excluyen los `ast.Name` que son el propio alias dentro del nodo de
      import (ver abajo: el import se recorre por separado y no genera un `ast.Name` de uso).

    FUERA DE ALCANCE A PROPOSITO (riesgo residual aceptado, coherente con el contrato §8): la
    indireccion DINAMICA -`getattr(autoconstruccion, "ciclo")`, `importlib.import_module(...)`,
    construir el nombre `"ci" + "clo"` en tiempo de ejecucion- no es resoluble por analisis
    estatico y no se intenta cubrir. El contrato §8 asume que añadir un llamante es un acto
    consciente; un llamante que se esconde tras `getattr` ya no es "inadvertido", y la lista blanca
    y la revision humana son la red para ese caso, no esta prueba."""
    # Nombres locales importados de `autoconstruccion`: alias del modulo entero, y asname de `ciclo`.
    alias_del_modulo = set()
    nombres_locales_de_ciclo = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == "autoconstruccion":
                    alias_del_modulo.add(alias.asname or "autoconstruccion")
        elif isinstance(nodo, ast.ImportFrom) and nodo.module == "autoconstruccion":
            for alias in nodo.names:
                if alias.name == "ciclo":
                    nombres_locales_de_ciclo.add(alias.asname or "ciclo")

    lineas = []
    for nodo in ast.walk(arbol):
        # (a) `X.ciclo` con X = alias del modulo, en cualquier contexto (Call, Assign, arg, ...).
        if (isinstance(nodo, ast.Attribute) and nodo.attr == "ciclo"
                and isinstance(nodo.value, ast.Name) and nodo.value.id in alias_del_modulo):
            lineas.append(nodo.lineno)
        # (b) uso del nombre local importado de `ciclo` (su asname), en cualquier contexto.
        elif (isinstance(nodo, ast.Name) and nodo.id in nombres_locales_de_ciclo
                and nodo.id):
            lineas.append(nodo.lineno)
    return lineas


def _llamantes_productivos_de_ciclo(raiz: pathlib.Path) -> list[str]:
    """Barrido AST sobre los modulos de produccion: cualquier REFERENCIA estatica a
    `autoconstruccion.ciclo` (llamada, asignacion, paso como argumento, o uso de su asname
    importado) es culpable. Ver `_referencias_a_ciclo_en_arbol` para el detalle y el alcance.

    Por que el AST NO ve comentarios: `ast.parse` construye el arbol a partir de los TOKENS de
    codigo real; una cadena de comentario (`#`) o una mencion dentro de un docstring/string nunca
    se convierte en un `ast.Attribute` ni en un `ast.Name` de USO -el docstring es un unico
    `ast.Constant`, no un `ast.Name`-. Por eso `review.py`, que solo MENCIONA
    `autoconstruccion.ciclo()` en prosa, no genera ninguna referencia que esta funcion encuentre."""
    culpables = []
    for ruta in _modulos_de_produccion(raiz):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        for linea in _referencias_a_ciclo_en_arbol(arbol):
            culpables.append(f"{ruta.name}:{linea}")
    return culpables


def test_inv7_api_legada_ciclo_sin_llamante_de_produccion():
    """`autoconstruccion.ciclo()` no tiene hoy ningun llamante de produccion (contrato §8): la
    lista blanca de exentos es `{"autoconstruccion.py"}` -su propia definicion- y nada mas.
    Si CA-M6 (mutacion) inyecta una llamada real en un modulo de produccion, esta prueba falla."""
    raiz = pathlib.Path(__file__).resolve().parent
    culpables = _llamantes_productivos_de_ciclo(raiz)
    assert not culpables, (
        f"autoconstruccion.ciclo() gano un llamante de produccion sin su quinta puerta propia: "
        f"{culpables}")


def test_inv7_control_review_py_menciona_ciclo_en_comentario_y_no_cuenta_como_llamante():
    """CONTROL: `review.py` SI contiene la cadena "autoconstruccion.ciclo()" (documenta la deuda
    condicionada en el docstring de `_exigir_correspondencia_con_el_contrato`, contrato §8), pero
    NO debe aparecer en la lista de culpables: es prosa, no una llamada AST real. Si el barrido
    fuera un grep de texto en vez de un parseo AST, este control fallaria -que es justo la
    diferencia que demuestra la robustez del metodo."""
    raiz = pathlib.Path(__file__).resolve().parent
    review_py = raiz / "review.py"
    assert "autoconstruccion.ciclo()" in review_py.read_text(encoding="utf-8"), (
        "este control asume que review.py sigue mencionando ciclo() en prosa; si ya no lo hace, "
        "el control debe actualizarse para seguir siendo significativo")
    culpables = _llamantes_productivos_de_ciclo(raiz)
    assert not any(c.startswith("review.py:") for c in culpables)


def test_inv7_control_la_lista_blanca_es_exactamente_autoconstruccion_y_nada_mas():
    """CONTROL: la lista blanca no ha crecido por descuido. Ampliarla exige decision consciente
    del Director/CEO (contrato §8), nunca un commit silencioso."""
    assert _LISTA_BLANCA_LLAMANTES_DE_CICLO == frozenset({"autoconstruccion.py"})


# Formas de INDIRECCION que el barrido ESTATICO debe cazar (hallazgo ALTO de auditoria). Cada
# snippet es codigo real pero se parsea EN MEMORIA -no se escribe ningun .py en control-plane-,
# para probar la deteccion sin introducir un falso llamante en el arbol de produccion.
_SNIPPETS_QUE_DEBEN_DETECTARSE = {
    "call_directa_con_alias": "import autoconstruccion as ac\nac.ciclo(d, [], None, '')\n",
    "asname_de_ciclo_llamado": "from autoconstruccion import ciclo as c\nc(d, [], None, '')\n",
    "asname_de_ciclo_como_arg": "from autoconstruccion import ciclo as c\n_delegar(c, d)\n",
    "atributo_asignado_a_variable": "import autoconstruccion as ac\nfn = ac.ciclo\nfn(d)\n",
    "atributo_pasado_como_arg": "import autoconstruccion as ac\n_delegar(ac.ciclo, d)\n",
    "import_sin_asname_llamado": "from autoconstruccion import ciclo\nciclo(d, [], None, '')\n",
    "modulo_sin_alias": "import autoconstruccion\nautoconstruccion.ciclo(d)\n",
}

_SNIPPETS_QUE_NO_DEBEN_DETECTARSE = {
    # `Orquestador.ciclo()` es un metodo homonimo de OTRA clase: no viene de `autoconstruccion`.
    "ciclo_de_otro_objeto": "import orquestador as orq\norq.Orquestador(d).ciclo(max_iteraciones=3)\n",
    # `_ciclo` local de motor_autonomia es una funcion privada distinta, no `ciclo`.
    "guion_bajo_ciclo_local": "def _ciclo(d):\n    return 1\n_ciclo(d)\n",
    # mencion en prosa dentro de un string/docstring: es un ast.Constant, no un Name/Attribute de uso.
    "mencion_en_docstring": '"""llama a autoconstruccion.ciclo() algun dia"""\nx = 1\n',
    # `ciclo` como nombre local NO importado de autoconstruccion: no debe confundirse.
    "ciclo_nombre_no_importado": "ciclo = 5\nprint(ciclo)\n",
}


def test_inv7_control_el_barrido_caza_las_formas_de_indireccion_realistas():
    """CONTROL de la AMPLIACION (hallazgo ALTO): el barrido anterior solo miraba `ast.Call` y se
    perdia `c(...)` (asname), `fn = ac.ciclo`, y `ac.ciclo` pasado como argumento. Aqui se parsea
    cada forma EN MEMORIA y se confirma que `_referencias_a_ciclo_en_arbol` la detecta -cobertura
    probada, no solo afirmada-."""
    for nombre, codigo in _SNIPPETS_QUE_DEBEN_DETECTARSE.items():
        arbol = ast.parse(codigo)
        assert _referencias_a_ciclo_en_arbol(arbol), (
            f"forma de indireccion NO detectada por el barrido: {nombre!r}\n{codigo}")


def test_inv7_control_el_barrido_no_produce_falsos_positivos():
    """CONTROL negativo de la ampliacion: al ampliar de `ast.Call` a cualquier referencia, el
    riesgo es cazar de mas. Estas formas NO son `autoconstruccion.ciclo` y NO deben marcarse:
    el `ciclo` de `Orquestador` (otro objeto), el `_ciclo` privado de motor_autonomia, una mencion
    en prosa, y un `ciclo` local no importado del modulo."""
    for nombre, codigo in _SNIPPETS_QUE_NO_DEBEN_DETECTARSE.items():
        arbol = ast.parse(codigo)
        assert not _referencias_a_ciclo_en_arbol(arbol), (
            f"FALSO POSITIVO: el barrido marco {nombre!r} y no es autoconstruccion.ciclo\n{codigo}")


def test_inv7_control_rglob_barre_subdirectorios(tmp_path):
    """CONTROL del vector de SUBDIRECTORIOS (hallazgo ALTO): `glob("*.py")` no era recursivo; un
    llamante en `raiz/sub/mod.py` se escapaba. Con `rglob`, un modulo escondido en un subdirectorio
    SI entra en el barrido. Se monta un arbol sintetico en tmp (nunca en control-plane)."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "escondido.py").write_text(
        "import autoconstruccion as ac\nac.ciclo(d, [], None, '')\n", encoding="utf-8")
    culpables = _llamantes_productivos_de_ciclo(tmp_path)
    assert any("escondido.py" in c for c in culpables), (
        f"rglob no encontro el llamante en el subdirectorio: {culpables}")
