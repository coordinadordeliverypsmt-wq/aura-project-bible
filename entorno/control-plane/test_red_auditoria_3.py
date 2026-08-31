"""RED · tercera auditoría independiente (2026-08-30). Dos GRAVE, y los dos son míos.

**GRAVE 1 · la puerta tenía la cerradura un piso más arriba.** Cerré `registrar_evento` para los tres
tipos que conceden estado, y puse debajo `_registrar_evento_gobernado(directorio, tipo, datos)` como
implementación de las puertas legítimas. **Acepta cualquier `tipo`.** Reproducido `[EJEC]`:

```python
cp._registrar_evento_gobernado(d, "estado_de_tarea", {
    "id": "T-BYPASS", "valor": "COMPLETED", "previo": "UNKNOWN",
    "autoridad": "nadie", "causa": "bypass total sin criterio"})
cp.proyectar(d)["tareas"]["T-BYPASS"]["estado"]   # -> "COMPLETED"
cp.verificar_integridad_log(d)["integro"]          # -> True
```

Tercera vez que la misma pregunta —*«¿queda alguna ruta a `COMPLETED`?»*— encuentra algo, y cada vez
**un nivel más abajo de donde miré**. Y mi meta-control no podía verlo: es ciego por tres motivos a la
vez —descarta lo que empieza por `_`, descarta lo que no sea función suelta (clases y métodos), y
**solo mira dentro de `control_plane.py`**—. Una función hostil en otro módulo, con el estado en una
constante en vez de un literal, le resulta invisible.

**GRAVE 2 · marcaba la sesión antes de saber si había ocurrido.** El bucle escribía
`sesion_ejecutada` **antes** de `worker.invocar()`. Y `invocar()` hoy se niega **siempre** —no hay
autorización para ejecutar de verdad—, así que en el estado actual del sistema **toda tarea `AUTO`
quedaba marcada «ya ejecutada» en su primer intento sin haberse ejecutado nunca**, y sin forma de
volver atrás salvo cambiando el sobre. El propio docstring decía *«deja en el log que esta ejecución
concreta **ocurrió**»*: no ocurrió, se intentó y fue denegada.

Es el falso positivo que la auditoría pidió buscar, y lo introduje yo doce horas antes escribiendo la
fila del `§12` que promete lo contrario: *«detectada; la segunda no se registra»* habla de la
**segunda ejecución**, no del segundo intento.
"""

from __future__ import annotations

import control_plane as cp
import orquestador as orq
import pytest


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


TAREA = {"id": "T-1", "accion": "ejecutar_pruebas", "objetivo": "batería",
         "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}}


# ============ GRAVE 1 · LA PUERTA INTERNA TAMBIEN TIENE CERRADURA --


def test_la_puerta_interna_NO_escribe_un_estado_de_tarea(tmp_path):
    """La vía que encontró la auditoría, cerrada. `estado_de_tarea` tiene **un solo** escritor
    legítimo —`transicion()`, dentro del lock y tras validar—, y esta puerta no es él."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-B", "accion": "ejecutar_pruebas"})
    with pytest.raises(cp.EventoNoGobernado):
        cp._registrar_evento_gobernado(tmp_path, "estado_de_tarea", {
            "id": "T-B", "valor": "COMPLETED", "previo": "UNKNOWN",
            "autoridad": "nadie", "causa": "bypass total"})
    assert cp.estado_de(tmp_path, "T-B") != "COMPLETED"


def test_la_puerta_interna_solo_admite_los_eventos_de_SU_puerta(tmp_path):
    """Una puerta que abre para cualquier cosa no es una puerta. Solo pasan los dos eventos del
    criterio, que son los que tienen aquí su única vía."""
    for tipo in ("estado_de_tarea", "tarea_registrada", "lo_que_sea"):
        with pytest.raises(cp.EventoNoGobernado):
            cp._registrar_evento_gobernado(tmp_path, tipo, {"id": "T-B"})


def test_las_puertas_legitimas_siguen_funcionando(tmp_path):
    """Caso de control: se acota la puerta, no se tapia."""
    criterio = {"capacidad": "ejecutar_pruebas"}
    cp.registrar_criterio_fijado(tmp_path, "T-C", criterio)
    cp.registrar_criterio_verificado(tmp_path, "T-C", cp.huella_de_criterio(criterio), True, "ok")
    assert cp.criterio_superado(tmp_path, "T-C") is True


def test_el_metacontrol_MIRA_todos_los_modulos_no_solo_el_suyo():
    """Hueco 3 del meta-control: solo recorría `control_plane`. Una función que conceda estado desde
    otro módulo del plano de desarrollo era invisible."""
    revisados = cp.modulos_vigilados()
    nombres = {m.__name__ for m in revisados}
    assert {"control_plane", "orquestador", "agentes", "revisores",
            "autoconstruccion", "ciclo_autonomo"} <= nombres


def test_el_metacontrol_MIRA_las_privadas_y_los_metodos():
    """Huecos 1 y 2: descartaba lo que empieza por `_` y lo que no fuese `inspect.isfunction`. Las
    dos exclusiones eran comodidad mía, y la vía que abrió la tercera auditoría era **exactamente**
    una función privada."""
    vigiladas = cp.invocables_vigilados()
    nombres = {n for n, _ in vigiladas}
    assert "_registrar_evento_gobernado" in nombres, "una privada tiene que estar vigilada"
    assert "_registrar_sin_lock" in nombres
    assert any("." in n for n in nombres), "los métodos de clase también cuentan"


def test_NINGUN_invocable_del_plano_concede_COMPLETED_sin_estar_clasificado():
    """El barrido, ahora completo: **todos los módulos, incluidas privadas y métodos**, y buscando
    el estado tanto como literal como a través de la constante.

    La tercera auditoría lo dijo sin rodeos: la vía seguía abierta *«un nivel más abajo de donde
    miraron las dos auditorías anteriores»*. Ampliar el barrido a mano una cuarta vez sería repetir
    el error; lo que cambia es **de dónde sale la lista de sitios donde mirar**."""
    fuera = cp.invocables_sin_clasificar()
    assert fuera == [], (
        f"conceden o nombran COMPLETED sin estar clasificados: {fuera}. Decláralos gobernados si "
        "conceden estado, o en NO_CONCEDEN_ESTADO si solo lo leen o lo rechazan")


# ============ GRAVE 2 · LA SESION SE MARCA CUANDO OCURRE, NO CUANDO SE INTENTA --


def test_una_invocacion_DENEGADA_no_marca_la_sesion_como_ejecutada(tmp_path):
    """El defecto, en su forma exacta: hoy `invocar()` se niega **siempre** —no hay autorización para
    ejecutar de verdad—, así que marcar antes de invocar dejaba **toda** tarea `AUTO` quemada en su
    primer intento."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    o = orq.Orquestador(tmp_path)
    o.ciclo(max_iteraciones=3)
    assert not orq.sesion_ya_ejecutada(tmp_path, o.worker.session_id(TAREA)), (
        "no se ejecutó nada: se intentó y el propio orquestador lo denegó")


def test_tras_una_invocacion_DENEGADA_la_tarea_SE_PUEDE_REINTENTAR(tmp_path):
    """La consecuencia que importa, medida por el comportamiento: un fallo no puede inhabilitar la
    tarea para siempre. Sin esto, el primer intento de cada tarea era también el último."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    primero = orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    segundo = orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    assert segundo["motivo"] != "sesión ya ejecutada", (
        f"la denegación del primer ciclo ({primero['motivo']}) inhabilitó la tarea")


def test_una_invocacion_que_SI_ocurre_marca_la_sesion(tmp_path):
    """Caso de control, y la garantía original del `§12` intacta: cuando la ejecución **sí** ocurre,
    la segunda no se registra."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    invocadas = []
    o = orq.Orquestador(tmp_path)
    o.worker.invocar = lambda t: invocadas.append(t["id"])
    o.ciclo(max_iteraciones=3)
    assert orq.sesion_ya_ejecutada(tmp_path, o.worker.session_id(TAREA))

    dos = orq.Orquestador(tmp_path)
    dos.worker.invocar = lambda t: invocadas.append(t["id"])
    assert dos.ciclo(max_iteraciones=3)["motivo"] == "sesión ya ejecutada"
    assert invocadas == ["T-1"]


def test_el_criterio_fijado_ANTES_sobrevive_a_la_denegacion(tmp_path):
    """El criterio sí se fija antes de invocar —`§14.bis` regla 1 lo exige— y eso no cambia. La
    diferencia entre los dos registros es lo que afirman: el criterio dice *«así se juzgará esto»*,
    la sesión dice *«esto ocurrió»*. Solo el segundo puede mentir si se escribe demasiado pronto."""
    cp.registrar_evento(tmp_path, "tarea_registrada", TAREA)
    orq.Orquestador(tmp_path).ciclo(max_iteraciones=3)
    assert cp.criterio_fijado_de(tmp_path, "T-1") is not None
    assert cp.criterio_superado(tmp_path, "T-1") is False


def test_el_barrido_reconoce_el_estado_ESCONDIDO_EN_UNA_CONSTANTE():
    """La auditoría construyó el caso: una función hostil que escribe `ESTADO_FINAL = "COMPLETED"` y
    llama a la puerta interna. Buscar solo el literal no la ve, y el mutante que reducía las señales
    a `("COMPLETED",)` sobrevivía porque hoy ninguna función real usa la constante — sobrevivía por
    el estado del código, no porque la garantía existiera."""
    hostil = (
        'def cerrar_silenciosamente(d, ident):\n'
        '    ESTADO_FINAL = "COMPLE" + "TED"\n'
        '    return _registrar_evento_gobernado(d, "estado_de_tarea", {"valor": ESTADO_FINAL})\n')
    assert cp.parece_conceder_estado(hostil), "una constante no puede esconder la concesión"
    assert cp.parece_conceder_estado('    return _registrar_sin_lock(d, tipo, datos)\n')
    assert not cp.parece_conceder_estado('def sumar(a, b):\n    return a + b\n')


def test_un_revisor_SIN_ficha_no_es_capaz(tmp_path, monkeypatch):
    """`§8.1`: la capacidad se **mide**. El mutante que devolvía la lista entera sobrevivía porque
    hoy los dos revisores tienen ficha: medido y declarado coincidían por casualidad, que es
    exactamente cuando una garantía no está probada."""
    import review
    monkeypatch.setattr(cp, "AUTORIDADES_HUMANAS", cp.AUTORIDADES_HUMANAS)   # no-op explícito
    import autoconstruccion as ac
    monkeypatch.setattr(ac, "RAIZ_AGENTES", tmp_path / "sin-fichas")
    assert review.revisores_capaces() == (), "sin ficha no hay revisor, por mucho que esté en la lista"
