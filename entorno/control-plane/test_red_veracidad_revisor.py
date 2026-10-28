"""`DR-F-3d-2` — que el revisor determinista **compruebe lo que dice comprobar**.

`DR-F-3d` auditó el mecanismo y encontró tres cosas, todas medidas:

* **H1** `planificador.a_tarea` escribe los cuatro criterios de `D22` como **constantes literales**
  (`cambia_alcance: False`, `respeta_decisiones: True`, `d21_afirmativas: True`), y
  `aplicar_criterios` las consume. Sobre cualquier tarea real devolvía `cumple: True` salvo materia
  reservada. Deuda de veracidad: el revisor no comprobaba, transcribía.
* **H2** `RevisorSubagente` firma con el nombre de un agente al que **nunca invoca**.
* **H3** citaba `fichero:0` —una línea que no existe en ningún fichero— y `cuenta()` la aceptaba
  porque solo miraba que la tupla no estuviese vacía.

La reparación no inventa criterios: **usa las fuentes de verdad que ya existen** —`TODO_LO_DELEGABLE`,
`zona_permitida`, `_MATERIA_RESERVADA`, `en_alcance`— y **declara explícitamente lo que no puede
verificar**. `D21` son cinco preguntas cualitativas («¿escala durante 10 años?»); no hay función que
las responda, así que no se finge que se comprueban: se marcan como declaradas.
"""

from __future__ import annotations

import pathlib

import review as rv
import revisores as rev

BASE = pathlib.Path(__file__).resolve().parent
RAIZ = BASE.parents[1]
#: Un fichero que existe de verdad, para no repetir el defecto que se está reparando.
REAL = "entorno/control-plane/review.py"
#: El texto real de la primera linea, para no repetir el defecto de citar lo que no pone.
LINEA_1 = '"""Nivel `REVIEW` — `D-ORCH-2`. **Construido y apagado.**'

def _tarea(**kw):
    base = {"accion": "eliminar_codigo_muerto", "fichero": REAL, "cambia_alcance": False,
            "respeta_decisiones": True, "d21_afirmativas": True, "materia_reservada": False}
    base.update(kw)
    return base

# ---------------------------------------------- H1 · los criterios se comprueban de verdad --

def test_una_accion_fuera_de_lo_delegable_cambia_el_alcance_aunque_declare_que_no():
    """El corazón de H1: la bandera del proponente ya no puede conceder lo que la comprobación
    niega. `TODO_LO_DELEGABLE` es la fuente de verdad, no el dict de la tarea."""
    juicio = rv.aplicar_criterios(_tarea(accion="refactorizar_nucleo", cambia_alcance=False))
    assert juicio["cumple"] is False
    assert "alcance" in juicio["fallos"]

def test_consistencia_se_declara_porque_no_tiene_fuente_de_verdad_completa():
    """*«Respeta todas las decisiones previas (actas, ADRs, principios)»* es un universo abierto.
    `zona_permitida` cubre una parte pero no es utilizable aquí —sin `raiz` rechaza cualquier
    sandbox, y `raiz` está reservado a las pruebas—. El acta de `DR-F-3d-2` ordena **no fabricar** la
    comprobación: se declara y se dice que se declara. `DECISION_REQUIRED DR-F-3d-2-A`."""
    juicio = rv.aplicar_criterios(_tarea())
    assert "consistencia" in juicio["declarados"]
    assert "consistencia" not in juicio["verificados"]

def test_el_revisor_sigue_rechazando_el_plano_producto_por_su_propia_via():
    """La zona no queda sin vigilar: `RevisorSubagente` la comprueba donde sí tiene el fichero, y el
    motor la vuelve a comprobar antes de escribir."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto",
                       "walking-skeleton/aura_skeleton/composicion.py", "x", {}))
    assert v is not None and v.veredicto == "fuera_de_alcance"

def test_la_materia_reservada_falla_aunque_la_bandera_diga_que_no():
    """Ya era fail-closed antes (el `or`), y debe seguir siéndolo."""
    juicio = rv.aplicar_criterios(_tarea(accion="modificar_adr", materia_reservada=False))
    assert juicio["cumple"] is False
    assert "materia_reservada" in juicio["fallos"]

def test_el_juicio_distingue_lo_verificado_de_lo_declarado():
    """La reparación de veracidad: el resultado dice **qué comprobó** y qué aceptó por declaración.
    Antes los mezclaba en un `cumple` que no distinguía una cosa de la otra."""
    juicio = rv.aplicar_criterios(_tarea())
    assert set(juicio["verificados"]) == {"alcance", "materia_reservada"}
    #: `DR-F-3d-4` (`B2`, aprobada por el CEO): a una tarea tecnica acotada ya no se le exige el
    #: gate de las cinco preguntas, asi que `D21` sale de «declarado» y pasa a «no aplica».
    assert set(juicio["declarados"]) == {"consistencia"}
    assert set(juicio["no_aplica"]) == {"cinco_preguntas_d21"}
    assert "cinco_preguntas_d21" not in juicio["verificados"]
    assert set(juicio["verificados"]) & set(juicio["declarados"]) == set()

def test_d21_nunca_se_declara_verificado():
    """`D21` son cinco preguntas cualitativas de largo plazo. Ninguna función puede responderlas, y
    fingir que se comprueban sería exactamente el defecto que se está reparando."""
    for tarea in (_tarea(), _tarea(d21_afirmativas=False), _tarea(accion="modificar_bible")):
        assert "cinco_preguntas_d21" not in rv.aplicar_criterios(tarea)["verificados"]
    #: Y donde sigue aplicando, se declara: nunca se finge comprobado.
    assert "cinco_preguntas_d21" in rv.aplicar_criterios(
        _tarea(accion="modificar_bible"))["declarados"]

def test_una_tarea_legitima_sigue_cumpliendo():
    """Regresión: reparar la veracidad no puede detener el trabajo que sí es legítimo."""
    juicio = rv.aplicar_criterios(_tarea())
    assert juicio["cumple"] is True and juicio["fallos"] == ()

def test_el_alcance_se_mide_contra_el_acta_cuando_hay_acta(tmp_path):
    """Con directorio, la fuente de verdad es el acta registrada, no una constante."""
    rv.habilitar(tmp_path, por="ceo", acta="DEC-ORCH-2", alcance=rv.TODO_LO_DELEGABLE)
    assert rv.aplicar_criterios(_tarea(), directorio=tmp_path)["cumple"] is True
    fuera = rv.aplicar_criterios(_tarea(accion="desplegar_a_produccion"), directorio=tmp_path)
    assert "alcance" in fuera["fallos"]

def test_las_banderas_solo_pueden_anadir_fallos_nunca_quitarlos():
    """La propiedad que hace la reparación fail-closed: una declaración pesimista se respeta, una
    optimista no puede sobreescribir una comprobación objetiva."""
    assert "alcance" in rv.aplicar_criterios(_tarea(cambia_alcance=True))["fallos"]
    assert "consistencia" in rv.aplicar_criterios(_tarea(respeta_decisiones=False))["fallos"]
    #: `D21` solo se exige donde sigue aplicando (`B2`): una decision estrategica, no una tarea
    #: tecnica acotada. La propiedad que se comprueba es la misma: la bandera puede hacer fallar.
    assert "cinco_preguntas_d21" in rv.aplicar_criterios(
        _tarea(accion="seleccionar_tecnologia", d21_afirmativas=False))["fallos"]

# ---------------------------------------------------------- H3 · la evidencia es verificable --

def test_el_revisor_no_emite_la_linea_cero():
    """H3 literal: `fichero:0` no existe en ningún fichero del mundo."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto", REAL, "codigo muerto",
                       {"cambia_alcance": False, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False},
                       evidencia=({"fichero": REAL, "linea": 1, "texto": LINEA_1,
                                   "verificada": True},)))
    assert v is not None
    for cita in v.evidencia_citada:
        assert not cita.endswith(":0"), f"cita imposible: {cita}"

def test_un_fichero_inexistente_no_produce_veredicto():
    """`(F)`: sin evidencia verificable no hay veredicto. Antes salía «conforme» citando la nada."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto", "entorno/control-plane/no_existe.py",
                       "codigo muerto", {"cambia_alcance": False, "respeta_decisiones": True,
                                         "d21_afirmativas": True, "materia_reservada": False}))
    assert v is None

def test_una_linea_inexistente_no_produce_veredicto():
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto", REAL, "x",
                       {"cambia_alcance": False, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False},
                       evidencia=({"fichero": REAL, "linea": 999999, "texto": "x",
                                   "verificada": True},)))
    assert v is None

def test_una_cita_cuyo_contenido_no_coincide_no_produce_veredicto():
    """El caso que separa «la línea existe» de «la línea dice lo que se afirma»."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto", REAL, "x",
                       {"cambia_alcance": False, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False},
                       evidencia=({"fichero": REAL, "linea": 1,
                                   "texto": "esto no es lo que pone", "verificada": True},)))
    assert v is None

def test_toda_cita_emitida_existe_de_verdad_en_el_disco():
    """La garantía general: cada cita del veredicto se puede abrir y leer."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto", REAL, "codigo muerto",
                       {"cambia_alcance": False, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False},
                       evidencia=({"fichero": REAL, "linea": 63,
                                   "texto": '''CRITERIOS_D22 = ("alcance", "consistencia", "cinco_preguntas_d21", "materia_reservada")''',
                                   "verificada": True},)))
    assert v is not None and v.evidencia_citada
    for cita in v.evidencia_citada:
        ruta, _, numero = cita.rpartition(":")
        destino = RAIZ / ruta
        assert destino.is_file(), f"{ruta} no existe"
        assert 1 <= int(numero) <= len(destino.read_text(encoding="utf-8").splitlines())

def test_la_materia_reservada_sigue_saliendo_fuera_de_alcance_con_cita_verificable():
    """Regresión: el camino de rechazo también debe citar algo que exista."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "modificar_adr", REAL, "x", {}))
    assert v is not None and v.veredicto == "fuera_de_alcance"
    for cita in v.evidencia_citada:
        assert not cita.endswith(":0")

# ------------------------------------------------------------------- H2 · la firma --

def test_el_revisor_no_declara_haber_invocado_a_quien_no_invoca():
    """H2. `§275` decide **reutilizar** los agentes existentes en vez de crear un revisor nuevo; no
    dice que este camino los invoque. Invocarlos sería ejecutar, que el revisor tiene prohibido.
    Lo que no puede seguir ocurriendo es que el docstring afirme una invocación que no existe."""
    import inspect
    fuente = inspect.getsource(rev.RevisorSubagente)
    assert "no invoca" in fuente.lower() or "sin invocar" in fuente.lower(), (
        "el contrato del revisor debe decir explicitamente que no invoca al agente")

def test_el_veredicto_dice_sobre_que_criterios_se_pronuncia():
    """Trazabilidad: quien lea el veredicto debe poder saber qué se comprobó."""
    v = rev.RevisorSubagente(raiz=RAIZ).revisar(
        rev.Expediente("T-1", "eliminar_codigo_muerto", REAL, "codigo muerto",
                       {"cambia_alcance": False, "respeta_decisiones": True,
                        "d21_afirmativas": True, "materia_reservada": False},
                       evidencia=({"fichero": REAL, "linea": 1, "texto": LINEA_1,
                                   "verificada": True},)))
    assert v is not None
    assert any("verificados" in m for m in v.motivos)
    assert any("declarados" in m for m in v.motivos)
    for cita in v.evidencia_citada:
        assert ":" in cita and cita.rpartition(":")[2].isdigit(), (
            f"la evidencia solo lleva citas verificables: {cita}")

# ------------------------------------------------------------ autoridad, intacta --

def test_la_reparacion_no_toca_la_autoridad():
    assert rv.REVIEW_HABILITADO is False
    assert rv.TODO_LO_DELEGABLE == ("eliminar_codigo_muerto", "implementar_incremento_especificado")
    assert len(rv._MATERIA_RESERVADA) == 10
    assert rev.autoriza(rev.Veredicto("conforme", (), ("f.py:1",), "x", "y")) is False
    assert "autoriza" not in rev.Veredicto.__dataclass_fields__
    assert rev.RevisorLocal().disponible() is False

def test_el_revisor_sigue_sin_ejecutar_nada():
    import ast
    arbol = ast.parse((BASE / "revisores.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                assert alias.name.split(".")[0] not in {"subprocess", "os", "socket", "urllib"}
        elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in {"eval", "exec", "compile"}
