"""RED CONTRACTUAL del transporte Claude Code <-> Codex CLI.

Complementa `test_red_communication_plane.py` (35 pruebas) con lo que anade el diseno de
`DISENO-CP-TRANSPORTE-CLAUDE-CODEX.md`. **Todas fallan a proposito**: `communication_plane` no
existe y su construccion NO esta autorizada (D-CP-2 sigue pendiente).

**Son contractuales, no de integracion.** Ninguna lanza Codex, ninguna lanza `claude`, ninguna
consume cuota. Fijan la FORMA del contrato para que, cuando el CEO autorice GREEN, no haya margen
para reinterpretarlo.

**Dos hechos medidos el 2026-08-17 que estas pruebas convierten en contrato:**

1. `claude -p --output-format json` devolvio **`is_error: true` junto a `subtype: "success"`**, con
   codigo de retorno 1. Fiarse de `subtype` daria por buena una ejecucion fallida.
2. `codex` **no esta instalado** en esta maquina. Sus capacidades son `UNKNOWN`, y el canal debe
   decirlo en vez de suponerlas.
"""

from __future__ import annotations

import importlib

import pytest


def _canal():
    """Importa el modulo bajo prueba. Falla en RED, y ese es el punto."""
    return importlib.import_module("communication_plane")


# ======================================================== SOBRE Y CONCURRENCIA --


def test_el_mensaje_declara_que_version_del_estado_leyo_su_emisor():
    """«¿Que version del estado leyo?» — pregunta 4 del encargo del CEO. Sin este campo, dos agentes
    pueden actuar sobre estados distintos creyendo que comparten uno."""
    m = _canal().nuevo_mensaje(tipo="ENCARGO", de="claude-code", para="codex", cuerpo={})
    assert "estado_leido" in m, "el sobre no declara sobre que estado se emitio"


def test_un_resultado_calculado_sobre_un_estado_viejo_se_rechaza():
    """Control de concurrencia optimista (caso 7 de recuperacion). Si el estado cambio entre que el
    agente lo leyo y que entrega el resultado, aplicarlo pisaria trabajo ajeno."""
    canal = _canal()
    assert canal.aplicable(mensaje={"estado_leido": "hash-viejo"}, estado_actual="hash-nuevo") is False
    assert canal.aplicable(mensaje={"estado_leido": "hash-x"}, estado_actual="hash-x") is True
    # CASO ANADIDO 2026-08-24 por un mutante SUPERVIVIENTE. Los dos casos anteriores NO distinguen
    # la igualdad de la pertenencia: con `in` en lugar de `==`, ambos dan el mismo resultado. Un
    # estado que es PREFIJO de otro los separa, y sin este caso la comparacion podia degradarse a
    # tolerante sin que ninguna prueba lo notara. Es la leccion de CLAUDE.md: si un mutante
    # sobrevive, falta una prueba.
    assert canal.aplicable(mensaje={"estado_leido": "hash-x"}, estado_actual="hash-x-extendido") is False


def test_un_hueco_en_la_secuencia_se_detecta_y_no_se_rellena():
    """Caso 5 · fuera de orden. Un `seq` que salta significa que falta un mensaje: inventarlo o
    ignorarlo en silencio haria que el canal mintiese sobre su propia historia."""
    canal = _canal()
    huecos = canal.huecos_de_secuencia([1, 2, 4, 5])
    assert huecos == [3]


def test_una_respuesta_a_un_mensaje_inexistente_se_rechaza():
    canal = _canal()
    with pytest.raises(ValueError, match="in_reply_to"):
        canal.validar_respuesta({"in_reply_to": "id-que-no-existe"}, ids_conocidos=set())


# ==================================================== IDENTIDAD · D-CP-3 · N-2 --


def test_la_identidad_atestiguada_exige_algo_mas_que_el_campo_de():
    """N-2 (§5.2 del diseno): `de` es declarativo y no prueba nada. La linea base propuesta anade el
    identificador de sesion REAL del agente y el estado que leyo."""
    canal = _canal()
    for campo in ("de", "sesion_id", "estado_leido"):
        assert campo in canal.CAMPOS_DE_IDENTIDAD, f"falta {campo} en la identidad atestiguada"


def test_el_canal_no_afirma_autenticar_a_nadie():
    """INV-9 · **N-2 es trazabilidad, no autenticacion.** Quien tenga acceso de escritura al disco
    puede falsificar un mensaje, y el canal debe declararlo en vez de sugerir lo contrario."""
    canal = _canal()
    limite = canal.limites_de_identidad()
    assert limite["autentica"] is False
    assert "escritura" in limite["por_que"].lower()


def test_la_identidad_de_codex_esta_declarada_como_desconocida():
    """No se inventan capacidades. `codex` no esta instalado en esta maquina: su identificador de
    agente es UNKNOWN hasta que alguien lo mida."""
    canal = _canal()
    assert canal.identidad_de_agente("codex") == "UNKNOWN"


# ============================================== CONTRATO DEL TRANSPORTE (ADAPTADOR) --


def test_el_transporte_expone_exactamente_entregar_y_recoger():
    """El canal no habla con Codex: habla con un adaptador. Nueve incognitas quedan encerradas
    detras de dos metodos."""
    canal = _canal()
    for metodo in ("entregar", "recoger"):
        assert hasattr(canal.TransporteAdapter, metodo)


def test_el_canal_declara_que_transportes_estan_disponibles_hoy_y_cuales_no():
    """`TransporteFichero` es construible en esta maquina; `TransporteCodex` no, y decir lo
    contrario seria fingir capacidad (INV-9)."""
    canal = _canal()
    disponibles = canal.transportes_disponibles()
    assert disponibles["fichero"] == "DISPONIBLE"
    assert disponibles["codex"] == "UNKNOWN"


# ================================ SOBRE DE CLAUDE CODE · trampa medida 2026-08-17 --


def test_el_exito_se_decide_por_is_error_nunca_por_subtype():
    """MEDIDO: `claude -p --output-format json` devolvio `is_error: true` **con**
    `subtype: "success"` y codigo de retorno 1. Un lector que use `subtype` da por buena una
    ejecucion fallida. Esta prueba impide que ese error entre en el canal."""
    canal = _canal()
    sobre = {"is_error": True, "subtype": "success", "terminal_reason": "api_error"}
    assert canal.ejecucion_correcta(sobre) is False


def test_un_sobre_sin_is_error_no_se_interpreta_como_exito():
    """Ausencia de dato no es dato. Si el campo falta, el resultado es desconocido, no bueno."""
    canal = _canal()
    with pytest.raises(ValueError, match="is_error"):
        canal.ejecucion_correcta({"subtype": "success"})


def test_el_coste_de_la_invocacion_se_registra_sin_estimar_cuota_restante():
    """El sobre publica `total_cost_usd` y `usage` [EJEC], pero NO cuanta cuota queda. El canal
    puede acumular coste; no puede derivar margen."""
    canal = _canal()
    registro = canal.registrar_coste({"total_cost_usd": 0.42, "usage": {"output_tokens": 10}})
    assert registro["coste_usd"] == 0.42
    assert registro["cuota_restante"] == "UNKNOWN"


# ========================================== FINALIZACION · el ejecutor no se certifica --


def test_una_tarea_sin_orden_verificable_no_es_automatizable():
    """Heredado de `DP-ORCH §14.bis`: el criterio de finalizacion lo fija quien crea la tarea y sin el
    el ejecutor se autocertifica.

    **Actualizada el 2026-08-23 por decision del CEO (`D-CP-4` = C).** La regla 2 de §14.bis exigia
    antes *«un comando verificable de terceros»*, y esta prueba lo codificaba aceptando una orden de
    shell. La regla cambio —el criterio referencia una CAPACIDAD REGISTRADA, nunca una orden libre
    del SO— y la prueba la sigue. **La cobertura no se retira: se invierte el veredicto del caso de
    shell**, que pasa de esperado-valido a esperado-rechazado."""
    canal = _canal()
    assert canal.es_automatizable({"criterio": None}) is False
    assert canal.es_automatizable({"criterio": "ejecutar_pruebas"}) is True
    assert canal.es_automatizable({"criterio": "python3 -m pytest tests/unit -q"}) is False


# ===========================================================================
# FRONTERA -- el canal comunica; el cierre es del motor unico
#
# `cerrar_tarea` vivio en este plano hasta el 2026-09-02. La sustituye esta bateria, que ya no
# comprueba COMO cerraba, sino que NO PUEDE cerrar. Es una garantia distinta y mas fuerte: la
# anterior protegia el comportamiento de una funcion; esta protege la ausencia de la capacidad.
# ===========================================================================

#: Vocabulario de cierre y certificacion. No es una lista de nombres prohibidos: es la categoria.
#: Ninguno de los 40 simbolos que el canal expone hoy contiene ninguno de estos fragmentos.
_VOCABULARIO_DE_CIERRE = ("cerrar", "cierre", "completar", "completad", "certificar",
                          "finalizar", "efecto")


def _simbolos_del_canal(modulo):
    """Funciones de modulo Y metodos de `Canal`. Mirar solo las primeras dejaria fuera la mitad
    de la superficie: `aprobar` y `marcar_procesado` son metodos, no funciones."""
    import ast
    import inspect
    arbol = ast.parse(inspect.getsource(modulo))
    nombres = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nombres.append(nodo.name)
    return nombres


def test_el_canal_no_puede_cerrar_una_tarea():
    """FASE 4.1 y 4.2 -- decision del CEO del 2026-09-02, opcion 3.

    El canal no fija el criterio antes de invocar (§14.bis regla 1), no puede ejecutarlo contra el
    arbol resultante (regla 3) y **no sabe quien le habla**: su propio `limites_de_identidad()`
    declara `autentica: False`. Sin identidad no puede distinguir al Orchestrator del Worker que se
    autocertifica, que es justo lo que la regla 3 existe para impedir.

    Se comprueba la CATEGORIA, no el nombre retirado. Devolver la capacidad llamandola
    `completar_tarea` seria la misma segunda via con otra etiqueta.
    """
    canal = _canal()
    assert not hasattr(canal, "cerrar_tarea"), (
        "`cerrar_tarea` ha vuelto al Communication Plane: es la segunda ruta hacia COMPLETED que la "
        "decision del CEO del 2026-09-02 retiro")
    culpables = [n for n in _simbolos_del_canal(canal)
                 if any(f in n.lower() for f in _VOCABULARIO_DE_CIERRE)]
    assert culpables == [], (
        f"el canal expone capacidad de cierre o de certificacion de efecto: {culpables}. "
        "Comunicar no es certificar: el cierre vive solo en el motor unico")


def test_el_canal_no_nombra_el_estado_terminal():
    """FASE 4.1 -- quien no nombra `COMPLETED` no puede producirlo.

    Se mira el **AST**, no el texto: un comentario que explique por que el cierre no vive aqui es
    exactamente lo que debe poder escribirse. Lo que no puede existir es el literal en codigo que
    se ejecuta.
    """
    import ast
    import inspect
    canal = _canal()
    arbol = ast.parse(inspect.getsource(canal))

    docs = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = getattr(nodo, "body", None)
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant):
                docs.add(id(cuerpo[0].value))

    literales = [n.value for n in ast.walk(arbol)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
    terminales = [v for v in literales if "COMPLETED" in v or "COMPLETADA" in v]
    assert terminales == [], (
        f"el canal nombra el estado terminal en codigo ejecutable: {terminales}. "
        "El unico que produce COMPLETED es el motor unico")


def test_el_canal_no_importa_autoridad_del_control_plane():
    """FASE 4.3 -- la decision prohibe **importar autoridad** hacia el Communication Plane.

    El canal declara de donde viene la autoridad; no la ejerce ni la trae. Si un dia importara el
    Control Plane, la direccion de la dependencia se invertiria y `SOLO_LECTURA` dejaria de ser
    verificable estructuralmente para pasar a ser una promesa.
    """
    import ast
    import inspect
    canal = _canal()

    assert canal.permisos_sobre_el_control_plane() == "SOLO_LECTURA"
    assert canal.fuentes_de_autoridad() == ("control_plane",), (
        "el canal no es fuente de autoridad: solo declara cual lo es")

    arbol = ast.parse(inspect.getsource(canal))
    importados = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.append(nodo.module)
    prohibidos = [m for m in importados if "control_plane" in m or m.startswith("agentes")]
    assert prohibidos == [], (
        f"el canal importa el motor unico: {prohibidos}. Eso es traer autoridad a un plano que no "
        "la tiene, y abre la ruta que la opcion 3 cerro")


def test_el_unico_cierre_valido_sigue_en_el_motor_unico():
    """FASE 4.4 y 4.5 -- retirar una puerta solo es correcto si la buena sigue en pie.

    Sin esta comprobacion, borrar `cerrar_tarea` de los dos planos dejaria las tres pruebas
    anteriores en verde y **el sistema sin ninguna forma de cerrar una tarea**. Se lee por ruta, no
    se importa: comprobar la frontera no puede consistir en cruzarla.
    """
    import pathlib
    motor = pathlib.Path(__file__).resolve().parent.parent / "control-plane"

    agentes = (motor / "agentes.py").read_text()
    assert "def cerrar_tarea(" in agentes, (
        "el cierre ha desaparecido tambien del motor unico: no queda ninguna autoridad capaz de "
        "producir COMPLETED")
    assert "SinEvidencia" in agentes, "el motor ya no exige efecto verificado (A12)"

    cp = (motor / "control_plane.py").read_text()
    assert 'AUTORIDADES_HUMANAS = ("ceo", "humano")' in cp
    assert 'valor == "COMPLETED" and autoridad not in AUTORIDADES_HUMANAS' in cp, (
        "el motor unico ya no exige autoridad humana para COMPLETED: §14.bis quedaria sin puerta "
        "justo despues de haber retirado la del canal")
