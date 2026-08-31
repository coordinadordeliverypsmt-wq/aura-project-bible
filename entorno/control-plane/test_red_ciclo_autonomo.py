"""RED · **ciclo autónomo de desarrollo** — `DEC-ORCH-2` aprobada, `REVIEW` encendido.

    observar → diagnosticar → proponer → clasificar → [REVIEW] revisor → 4 criterios D22
    → ejecutar → probar → verificar efecto → registrar → siguiente tarea → repetir

Encadena **sin intervención humana entre tareas**, y se detiene solo por: cola vacía, `HUMAN`,
`DECISION_REQUIRED`, verificación fallida, prueba fallida o límite de seguridad.

**La cola sale del estado real del repositorio.** No se fabrican tareas para aparentar autonomía: si
no hay trabajo, el informe dice que no hay trabajo.
"""

from __future__ import annotations

import pathlib

import control_plane as cp

import ciclo_autonomo as ca
import review as rv


def _preparar(d: pathlib.Path, n: int) -> list[pathlib.Path]:
    ficheros = []
    for i in range(n):
        f = d / f"modulo_{i}.py"
        f.write_text(f"def viva_{i}():\n    return {i}\n\n\ndef _muerta_{i}():\n    return {i}\n",
                     encoding="utf-8")
        ficheros.append(f)
    return ficheros


def _habilitar(d):
    rv.habilitar(d, por="ceo", acta="DEC-ORCH-2 aprobada", alcance=("eliminar_codigo_muerto",))


# ============================================ CLASIFICACIÓN — antes de tocar nada --


def test_cada_propuesta_se_CLASIFICA_antes_de_ejecutarse(tmp_path):
    d = pathlib.Path(tmp_path)
    assert ca.clasificar({"accion": "eliminar_codigo_muerto", "fichero": str(d / "x.py")}, d) == "HUMAN", \
        "sin REVIEW habilitado, incluso lo delegable es HUMAN"
    _habilitar(d)
    assert ca.clasificar({"accion": "eliminar_codigo_muerto", "fichero": str(d / "x.py")}, d) == "REVIEW"
    assert ca.clasificar({"accion": "ejecutar_pruebas", "fichero": str(d / "x.py")}, d) == "AUTO"
    assert ca.clasificar({"accion": "modificar_adr", "fichero": "adr/x.md"}, d) == "HUMAN"
    assert ca.clasificar({"accion": "refactorizar_modulo", "fichero": str(d / "x.py")}, d) == "HUMAN", \
        "fuera del alcance del acta = HUMAN, no REVIEW"


def test_una_tarea_fuera_de_ZONA_se_clasifica_HUMAN_aunque_la_accion_este_en_alcance(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    for fuera in ("CLAUDE.md", "adr/0003.md", "walking-skeleton/aura_skeleton/core/x.py"):
        assert ca.clasificar({"accion": "eliminar_codigo_muerto", "fichero": fuera}, d) == "HUMAN"


# ============================================ ENCADENAMIENTO SIN INTERVENCIÓN --


def test_el_ciclo_encadena_TRES_tareas_sin_intervencion(tmp_path):
    """El requisito central: entre tarea y tarea no hay ningún acto humano."""
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    ficheros = _preparar(d, 3)
    informe = ca.ciclo_autonomo(d, ficheros, verificacion=lambda: True, max_tareas=10)

    assert informe["ejecutadas"] == 3, informe
    assert informe["actos_humanos_durante_el_ciclo"] == 0
    assert informe["motivo_de_parada"] == "cola agotada"
    for i, f in enumerate(ficheros):
        texto = f.read_text(encoding="utf-8")
        assert f"_muerta_{i}" not in texto and f"def viva_{i}" in texto


def test_cada_tarea_deja_su_EVIDENCIA_en_el_log(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    ca.ciclo_autonomo(d, _preparar(d, 2), verificacion=lambda: True, max_tareas=10)
    tipos = [e["tipo"] for e in cp.leer_eventos(d)]
    assert tipos.count("veredicto_emitido") == 2
    assert tipos.count("cambio_aplicado") == 2
    assert "ciclo_autonomo_iniciado" in tipos and "ciclo_autonomo_terminado" in tipos
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_el_revisor_es_INDEPENDIENTE_en_cada_tarea(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    ca.ciclo_autonomo(d, _preparar(d, 2), verificacion=lambda: True, max_tareas=10)
    for e in cp.leer_eventos(d):
        if e["tipo"] == "veredicto_emitido":
            assert e["datos"]["revisor"] != e["datos"]["propuesto_por"]


# ============================================ LAS SEIS CAUSAS DE PARADA --


def test_se_detiene_con_la_COLA_VACIA(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    limpio = d / "limpio.py"
    limpio.write_text("def a():\n    return _b()\n\n\ndef _b():\n    return 1\n", encoding="utf-8")
    informe = ca.ciclo_autonomo(d, [limpio], verificacion=lambda: True)
    assert informe["ejecutadas"] == 0 and informe["motivo_de_parada"] == "cola agotada"
    assert informe["propuestas"] == 0, "no se inventa trabajo donde no lo hay"


def test_una_tarea_HUMAN_DETIENE_el_ciclo_y_queda_registrada(tmp_path):
    """*«Comprobar que una tarea HUMAN detiene correctamente el ciclo»*. Y no se salta en silencio:
    queda escrita, que es lo que permite retomarla."""
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    # **Tres**, no dos: con la HUMAN en la última posición, `break` y `continue` dan el mismo
    # resultado y la prueba no distingue. Hace falta trabajo DESPUÉS de la parada para comprobar
    # que de verdad se paró.
    ficheros = _preparar(d, 3)
    informe = ca.ciclo_autonomo(d, ficheros, verificacion=lambda: True, max_tareas=10,
                                inyectar_human=True)
    assert informe["motivo_de_parada"] == "tarea HUMAN"
    assert informe["detenida_en"] is not None
    assert any(e["tipo"] == "decision_requerida" for e in cp.leer_eventos(d))
    # Y **se detuvo de verdad**: solo la primera se ejecutó. Sin esto, cambiar el `break` por un
    # `continue` dejaba los campos del informe idénticos mientras el ciclo seguía trabajando —el
    # motivo de parada decía una cosa y el comportamiento hacía otra.
    assert informe["ejecutadas"] == 1, "la HUMAN detiene: ni ella ni la siguiente se ejecutan"
    assert "def _muerta_1(" in ficheros[1].read_text(encoding="utf-8"), "la HUMAN quedó intacta"
    assert "def _muerta_2(" in ficheros[2].read_text(encoding="utf-8"), (
        "la tarea POSTERIOR a la HUMAN tampoco se ejecutó: el ciclo se detuvo de verdad")


def test_una_tarea_FUERA_DE_ZONA_nunca_se_ejecuta(tmp_path):
    """*«Comprobar que una tarea fuera de zona nunca se ejecuta»*."""
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    prohibido = d / "CLAUDE.md"
    prohibido.write_text("# gobernanza\n", encoding="utf-8")
    antes = prohibido.read_bytes()
    informe = ca.ciclo_autonomo(d, [prohibido], verificacion=lambda: True)
    assert informe["ejecutadas"] == 0
    assert prohibido.read_bytes() == antes


def test_una_VERIFICACION_fallida_detiene_el_ciclo_y_revierte(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    ficheros = _preparar(d, 3)
    originales = [f.read_bytes() for f in ficheros]
    informe = ca.ciclo_autonomo(d, ficheros, verificacion=lambda: False, max_tareas=10)
    assert informe["ejecutadas"] == 0
    assert informe["motivo_de_parada"] == "verificacion fallida"
    assert ficheros[0].read_bytes() == originales[0], "revertido"
    assert ficheros[2].read_bytes() == originales[2], "y no se siguió con las demás"


def test_el_LIMITE_DE_SEGURIDAD_acota_el_ciclo(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    informe = ca.ciclo_autonomo(d, _preparar(d, 8), verificacion=lambda: True, max_tareas=2)
    assert informe["ejecutadas"] == 2
    assert informe["motivo_de_parada"] == "limite de seguridad"


def test_sin_REVIEW_habilitado_el_ciclo_no_ejecuta_nada(tmp_path):
    d = pathlib.Path(tmp_path)
    ficheros = _preparar(d, 2)
    originales = [f.read_bytes() for f in ficheros]
    informe = ca.ciclo_autonomo(d, ficheros, verificacion=lambda: True)
    assert informe["ejecutadas"] == 0
    assert informe["motivo_de_parada"] == "tarea HUMAN"
    assert [f.read_bytes() for f in ficheros] == originales


# ============================================ RESILIENCIA · sin inventar éxito --


def test_un_EJECUTOR_NO_DISPONIBLE_no_produce_exito_fingido(tmp_path):
    """*«NO inventar éxito»*. Y sin recurrir a OpenCode, Codex ni Ollama: la tarea queda pendiente
    para que otro ejecutor autorizado la retome leyendo el Control Plane."""
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    ficheros = _preparar(d, 2)
    originales = [f.read_bytes() for f in ficheros]

    def revienta():
        raise RuntimeError("You've hit your monthly spend limit")

    informe = ca.ciclo_autonomo(d, ficheros, verificacion=revienta, max_tareas=10)
    assert informe["ejecutadas"] == 0
    assert informe["motivo_de_parada"] == "agente no disponible"
    assert informe["clase"] in ("AGENTE_SIN_CUOTA", "AGENTE_NO_DISPONIBLE")
    assert [f.read_bytes() for f in ficheros] == originales, "nada a medias"
    assert any(e["tipo"] == "agente_no_disponible" for e in cp.leer_eventos(d))


def test_el_ciclo_NO_recurre_a_agentes_externos():
    fuente = pathlib.Path(ca.__file__).read_text(encoding="utf-8")
    for prohibido in ("opencode", "codex", "ollama"):
        assert prohibido not in fuente.lower()


# ============================================ CONTINUIDAD — qué queda escrito --


def test_al_terminar_queda_escrito_el_SIGUIENTE_TRABAJO(tmp_path):
    """*«`siguiente_auto()` debe representar el trabajo real disponible»*."""
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    ficheros = _preparar(d, 3)
    informe = ca.ciclo_autonomo(d, ficheros, verificacion=lambda: True, max_tareas=1)
    assert informe["siguiente"] is not None, "quedaban 2: el siguiente trabajo debe constar"
    assert informe["pendientes"] == 2

    informe2 = ca.ciclo_autonomo(d, ficheros, verificacion=lambda: True, max_tareas=10)
    assert informe2["siguiente"] is None and informe2["pendientes"] == 0


def test_el_informe_no_declara_trabajo_que_no_existe(tmp_path):
    d = pathlib.Path(tmp_path)
    _habilitar(d)
    informe = ca.ciclo_autonomo(d, [], verificacion=lambda: True)
    assert informe["propuestas"] == 0 and informe["siguiente"] is None
    assert informe["pendientes"] == 0
