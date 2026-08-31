"""RED · cuarta auditoría independiente (2026-08-30). Dos GRAVE, y una afirmación mía que era falsa.

**GRAVE 1 · `esperar_por_cuota` no era «la única vía».** Lo escribí en su docstring y lo repetí en el
`CHECKPOINT §10.quindecies`. `transicion()` acepta `WAITING_FOR_QUOTA` con solo autoridad y causa:

```python
cp.transicion(d, "T-Q", "WAITING_FOR_QUOTA", autoridad="entorno", causa="me da la gana")   # aceptado
```

Es **ALERTA-005 con otro estado**. Lo cerré tres veces para `COMPLETED` y lo dejé abierto para el
siguiente en cuanto añadí una regla nueva: la lección de las tres auditorías anteriores era *«la puerta
va en el motor, no en el llamante»*, y yo puse un envoltorio.

**GRAVE 2 · el modelo en memoria persiste un `COMPLETED` fabricado.** `guardar()` y
`actualizar_estado()` aceptan cualquier dict mientras las tareas lleven las claves `autoridad` y
`previo` — se comprueba que **estén**, no lo que dicen:

```python
estado["tareas"] = {"T-FAB": {"estado": "COMPLETED", "autoridad": "cualquiera", "previo": "WORKING"}}
cp.guardar(estado, destino)      # -> persistido, sin criterio y sin humano
```

Y el `CHECKPOINT §10.quindecies` afirma: *«Ninguna ruta pública concede estado sin gobierno — probado,
y es lo que cerraron las tres auditorías»*. **No era cierto.** Peor: `render_handoff()` —del que depende
el Protocolo de Continuidad— lee de ese modelo, así que un relevo podría presentar como terminado un
trabajo fabricado.

La diferencia con `_registrar_sin_lock`, que sí declaré residual, es que **este es cerrable en
proceso**: basta que `validar_tareas()` exija para `COMPLETED` lo mismo que ya exigen
`completar_tarea` y `fijar_estado_tarea`. Declarar como irreducible algo que se puede cerrar es la
forma cómoda del `declarado ≠ real`.

Y tres MEDIO que también son míos: el revisor nombrado a mano no se valida, el barrido sigue ciego a
`functools.partial` y a las clases anidadas, y `MODULOS_DEL_PLANO` es **una tupla escrita a mano** —el
defecto exacto que llevo cuatro auditorías corrigiendo—.
"""

from __future__ import annotations

import functools
import pathlib

import control_plane as cp
import orquestador as orq
import pytest


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _en_curso(d, ident="T-Q"):
    cp.registrar_evento(d, "tarea_registrada", {"id": ident, "accion": "ejecutar_pruebas"})
    cp.transicion(d, ident, "WORKING", autoridad="ceo", causa="empieza")


# ============ GRAVE 1 · WAITING_FOR_QUOTA TAMBIEN TIENE UNA SOLA PUERTA --


def test_transicion_NO_aparca_por_cuota_sin_evidencia_observada(tmp_path):
    """La vía que encontró la cuarta auditoría. `WAITING_FOR_QUOTA` **afirma** que una cuota concreta
    bloqueó y que se renovará; sin evidencia, eso es fabricar una explicación (`§11`)."""
    _en_curso(tmp_path)
    with pytest.raises(cp.VentanaIndeterminada):
        cp.transicion(tmp_path, "T-Q", "WAITING_FOR_QUOTA", autoridad="entorno",
                      causa="me da la gana, sin evidencia real")
    assert cp.estado_de(tmp_path, "T-Q") != "WAITING_FOR_QUOTA"


def test_la_via_gobernada_de_cuota_SI_aparca(tmp_path):
    """Caso de control: se cierra la alternativa, no la función."""
    _en_curso(tmp_path, "T-W")
    cp.esperar_por_cuota(tmp_path, "T-W", ventana="SHORT_4H30", autoridad="orquestador",
                         evidencia="mensaje observado: 5-hour limit reached")
    assert cp.estado_de(tmp_path, "T-W") == "WAITING_FOR_QUOTA"


def test_la_observacion_de_cuota_va_atada_a_SU_tarea(tmp_path):
    """Como el criterio: la evidencia de una tarea no abre la de al lado."""
    _en_curso(tmp_path, "T-A")
    _en_curso(tmp_path, "T-B")
    cp.esperar_por_cuota(tmp_path, "T-A", ventana="WEEKLY", autoridad="orquestador",
                         evidencia="weekly limit reached")
    with pytest.raises(cp.VentanaIndeterminada):
        cp.transicion(tmp_path, "T-B", "WAITING_FOR_QUOTA", autoridad="orquestador",
                      causa="me vale la evidencia de la otra")


# ============ GRAVE 2 · EL MODELO EN MEMORIA NO PERSISTE UN COMPLETED FABRICADO --


def test_guardar_NO_persiste_una_tarea_COMPLETED_sin_autoridad_humana(tmp_path):
    """`validar_tareas` comprobaba que los campos de gobierno **estuvieran**, no lo que decían. Un
    `COMPLETED` con `autoridad="cualquiera"` pasaba."""
    estado = cp.estado_inicial()
    estado["tareas"] = {"T-FAB": {"estado": "COMPLETED", "autoridad": "cualquiera",
                                  "previo": "WORKING"}}
    with pytest.raises(ValueError):
        cp.guardar(estado, tmp_path / "estado.json")
    assert not (tmp_path / "estado.json").exists(), "no puede quedar escrito y luego lanzar"


def test_actualizar_estado_tampoco_deja_fabricar_un_COMPLETED(tmp_path):
    """La otra mitad de la ruta: la misma comprobación tiene que valer para las dos, o gobernar una
    sola deja la otra como puerta trasera — que es `ALERTA-005` literal."""
    destino = tmp_path / "estado.json"
    cp.guardar(cp.estado_inicial(), destino)
    with pytest.raises(ValueError):
        cp.actualizar_estado(destino, lambda e: {**e, "tareas": {"T-BYPASS": {
            "estado": "COMPLETED", "autoridad": "nadie-en-absoluto",
            "previo": "WAITING_FOR_NEXT_TASK"}}})
    assert "T-BYPASS" not in cp.cargar(destino).get("tareas", {})


def test_una_tarea_COMPLETED_con_autoridad_HUMANA_si_se_persiste(tmp_path):
    """Caso de control, y la regla 4 al derecho: lo que no es automatizable lo cierra una persona, y
    el modelo en memoria no tiene log donde comprobar ningún criterio."""
    estado = cp.estado_inicial()
    estado["tareas"] = {"T-OK": {"estado": "COMPLETED", "autoridad": "ceo", "previo": "WORKING"}}
    cp.guardar(estado, tmp_path / "estado.json")
    assert cp.cargar(tmp_path / "estado.json")["tareas"]["T-OK"]["estado"] == "COMPLETED"


def test_los_demas_estados_se_persisten_con_normalidad(tmp_path):
    """La barrera es sobre `COMPLETED`, no sobre guardar. Cerrar de más habría roto el estado entero."""
    estado = cp.estado_inicial()
    estado["tareas"] = {"T-1": {"estado": "WORKING", "autoridad": "orquestador", "previo": "UNKNOWN"},
                        "T-2": {"estado": "FAILED", "autoridad": "orquestador", "previo": "WORKING"}}
    cp.guardar(estado, tmp_path / "estado.json")
    assert cp.cargar(tmp_path / "estado.json")["tareas"]["T-2"]["estado"] == "FAILED"


def test_guardar_y_actualizar_estado_estan_CLASIFICADAS():
    """Estaban fuera de las tres listas, así que el meta-control no las miraba. La clasificación no
    es burocracia: es la única forma de que «no está en ninguna lista» deje de significar «nadie la
    ha mirado»."""
    todas = cp.FUNCIONES_GOBERNADAS | cp.NO_CONCEDEN_ESTADO | cp.ESCRITORES_CRUDOS
    for nombre in ("guardar", "actualizar_estado", "cargar", "validar_tareas"):
        assert nombre in todas, f"{nombre} no está clasificada en ninguna de las tres listas"


# ============ MEDIO · EL REVISOR NOMBRADO A MANO --


def test_un_revisor_NOMBRADO_sin_ficha_se_rechaza(tmp_path):
    """`revisores_capaces()` decidía si la puerta se abría, pero no validaba **quién** revisaba: se
    podía nombrar a un revisor inexistente y emitía veredicto. No es alcanzable desde el ciclo real
    —nunca pasa `revisor=`—, pero un contrato público que acepta un revisor fabricado es un contrato
    que alguien usará mal."""
    import review
    modulo = tmp_path / "modulo.py"
    modulo.write_text("def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n", encoding="utf-8")
    review.habilitar(tmp_path, alcance=("eliminar_codigo_muerto",), por="ceo", acta="DEC-ORCH-2")
    tarea = {"id": "T-R", "accion": "eliminar_codigo_muerto", "simbolo": "_muerta",
             "fichero": str(modulo), "cambia_alcance": False, "respeta_decisiones": True,
             "d21_afirmativas": True, "reversible": True}
    with pytest.raises(review.RevisorNoIndependiente):
        review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura", autoridad="orquestador",
                                    revisor="revisor-fabricado-sin-ficha")
    assert "_muerta" in modulo.read_text(encoding="utf-8"), "no se tocó el fichero"


# ============ MEDIO · EL BARRIDO, SIN LOS DOS HUECOS QUE QUEDABAN --


def test_el_barrido_ve_los_functools_partial():
    """`inspect.isfunction` devuelve `False` para un `partial`, así que una función gobernada
    envuelta y colgada de un módulo era invisible."""
    envuelto = functools.partial(cp.transicion)
    assert cp.es_invocable_vigilable(envuelto), "un partial también ejecuta código"


def test_el_barrido_desciende_a_las_clases_ANIDADAS():
    """Recorría un solo nivel de `vars(clase)`. Una clase dentro de otra escondía sus métodos."""
    class Fuera:
        class Dentro:
            def metodo(self):
                return "COMPLETED"

    hallados = dict(cp.invocables_de(Fuera, "Fuera"))
    assert "Fuera.Dentro.metodo" in hallados, "los métodos de una clase anidada también cuentan"


def test_los_modulos_vigilados_salen_del_DIRECTORIO_no_de_una_tupla():
    """El defecto exacto que llevo cuatro auditorías corrigiendo, cometido una vez más: la lista de
    módulos a vigilar estaba **escrita a mano**. Si mañana alguien añade un módulo al plano y olvida
    la tupla, el barrido no lo mira — y «no está en la lista» volvería a significar «nadie lo ha
    mirado»."""
    nombres = {m.__name__ for m in cp.modulos_vigilados()}
    base = pathlib.Path(cp.__file__).resolve().parent
    en_disco = {f.stem for f in base.glob("*.py")
                if not f.name.startswith(("test_", "conftest")) and "-" not in f.name}
    assert en_disco <= nombres, f"módulos del plano sin vigilar: {sorted(en_disco - nombres)}"


def test_una_observacion_de_cuota_FALSA_no_llega_a_escribirse(tmp_path):
    """La garantía que **solo** cubre `esperar_por_cuota`, y que tres mutantes destaparon al
    sobrevivir por doble cobertura.

    Desde que el motor rechaza `WAITING_FOR_QUOTA` sin observación válida, quitarle las
    comprobaciones al envoltorio no cambia el estado final — la tarea no se aparca igual. Pero sí
    cambia otra cosa: **el log se quedaría con una observación de cuota que nadie observó**. Y este
    proyecto tiene una regla para eso: un dato sin procedencia es indistinguible de uno inventado, y
    el historial es justamente lo que el relevo lee como cierto.

    Un superviviente «cubierto de otra forma» que no se explica es indistinguible de un hueco; este
    se explica, y la prueba que lo cierra mide lo que la otra capa no puede ver."""
    _en_curso(tmp_path, "T-F")
    for ventana, evidencia in (("UNKNOWN", "algo pasó"), ("SHORT_4H30", ""), ("SHORT_4H30", "   ")):
        with pytest.raises((cp.VentanaIndeterminada, ValueError)):
            cp.esperar_por_cuota(tmp_path, "T-F", ventana=ventana, autoridad="orquestador",
                                 evidencia=evidencia)
    assert cp.cuota_observada_de(tmp_path, "T-F") is None, (
        "ninguna observación falsa puede haber quedado escrita en el historial")
    assert "cuota_observada" not in [e["tipo"] for e in cp.leer_eventos(tmp_path)]
