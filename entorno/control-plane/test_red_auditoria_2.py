"""RED · segunda auditoría independiente (2026-08-30) — **cometí el mismo error dos veces**.

La primera auditoría encontró que la puerta de A12 vivía en el llamante y no en el motor. La corregí,
y escribí una prueba llamada `test_TODAS_las_vias_publicas_a_COMPLETED_respetan_el_criterio` con esta
justificación:

> *«`ALERTA-005` no se cierra probando una puerta: se cierra recorriendo **todas** las funciones
> públicas que podrían llevar a `COMPLETED`. Mi error fue probar la que yo había puesto.»*

**Y enumeré tres rutas a mano.** `completar_tarea` y `fijar_estado_tarea` —listadas como `GOBERNADAS`
desde F1, al mismo nivel que `transicion()`— quedaron fuera. La segunda auditoría las cerró en un
intento:

```python
estado = cp.estado_inicial()
estado["tareas"]["T-1"] = {"estado": "WORKING", ...}
cp.completar_tarea(estado, "T-1", "lo terminé yo mismo, sin criterio", autoridad="worker-no-humano")
# -> {"estado": "COMPLETED", ...}   sin criterio, con autoridad NO humana
```

**Una lista escrita a mano no es un barrido.** Es la misma frase, otra vez: probé las puertas que yo
había puesto. Por eso la corrección de fondo no es añadir dos rutas más a la lista —eso solo aplaza la
tercera vez—, sino **derivar la lista del código** y hacer que una función gobernada nueva sin
cobertura **rompa la prueba**.

Los otros hallazgos, también reproducidos por la auditoría `[EJEC]`:

- **Forjar el log cierra la puerta.** `registrar_evento` solo bloquea `estado_de_tarea`; registrando
  `criterio_fijado` y `criterio_verificado` a mano, `transicion()` acepta el cierre. La defensa que
  di —A6 demuestra que el worker no puede escribir— es **cierta pero estrecha**: A6 habla del sobre
  del worker, no de cualquier otro proceso con acceso al sistema de ficheros.
- **`zona_permitida` sin `raiz` no resuelve enlaces simbólicos.** Un symlink dentro de la zona que
  apunte al producto se acepta. La puerta de escritura real usa `raiz` y sí resuelve, pero el
  veredicto asesor de `RevisorSubagente` queda corrompido.
"""

from __future__ import annotations

import pathlib

import agentes as ag
import autoconstruccion as ac
import control_plane as cp
import orquestador as orq
import pytest


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


# ============== EL BARRIDO, DERIVADO DEL CODIGO Y NO ESCRITO A MANO --


def test_la_lista_de_funciones_gobernadas_vive_en_UN_SOLO_SITIO():
    """La causa raíz de haber fallado dos veces: la lista de funciones que cambian el estado de una
    tarea estaba escrita a mano en una prueba, y mi barrido escribió **otra** lista, más corta. Dos
    listas del mismo hecho es el defecto que el `§0` del CHECKPOINT ya documenta.

    Ahora la declara el módulo, y las pruebas la consultan."""
    assert isinstance(cp.FUNCIONES_GOBERNADAS, frozenset)
    # Se resuelve **en todos los módulos vigilados**, no solo en `control_plane`: desde la 3.ª
    # auditoría la lista cruza módulos, porque `agentes.cerrar_tarea` concede estado igual que
    # `transicion()` y mirar solo un fichero era el tercer hueco del meta-control.
    disponibles = {n.split(".")[-1] for n, _ in cp.invocables_vigilados()}
    for nombre in cp.FUNCIONES_GOBERNADAS:
        assert nombre in disponibles, f"{nombre} está declarada gobernada y no existe en el plano"
    # **Disjuntas.** Sin esto, meter una gobernada también en `NO_CONCEDEN_ESTADO` la sacaba del
    # barrido sin que nada fallara: el meta-control se quedaba ciego por una clasificación doble en
    # vez de por una ausencia. Lo destapó el mutante `AUD2-M4`, no yo. Una función concede estado o
    # no lo concede; estar en las dos listas es decir las dos cosas.
    solapan = cp.FUNCIONES_GOBERNADAS & cp.NO_CONCEDEN_ESTADO
    assert solapan == frozenset(), (
        f"clasificadas dos veces: {sorted(solapan)}. Una función concede estado o no lo concede")


def test_la_lista_gobernada_incluye_TODA_funcion_publica_que_menciona_COMPLETED():
    """El meta-control que impide la tercera vez. Si alguien añade una función que sepa llevar una
    tarea a `COMPLETED` y no la declara, esta prueba falla — sin que nadie tenga que acordarse de
    actualizar una lista.

    **Delega en `cp.invocables_sin_clasificar()`.** La primera versión reimplementaba el barrido aquí
    con sus propios filtros, y la tercera auditoría demostró que esos filtros tenían tres huecos
    —privadas, métodos y otros módulos—. Tener el barrido escrito dos veces era el mismo defecto que
    llevo cuatro auditorías corrigiendo: dos listas del mismo hecho, y la copia peor es la que
    manda."""
    fuera = cp.invocables_sin_clasificar()
    assert fuera == [], (
        f"invocables que nombran el estado final y no están clasificados: {fuera}. "
        "Decláralos gobernados si conceden estado, o en NO_CONCEDEN_ESTADO si solo lo leen, lo "
        "rechazan o lo vigilan — pero decláralos: sin lista, el próximo se cuela como los anteriores")


def test_NINGUNA_funcion_gobernada_cierra_a_COMPLETED_sin_autoridad_humana_ni_criterio(tmp_path):
    """El barrido de verdad: **una entrada por cada nombre de `FUNCIONES_GOBERNADAS`**, y una
    aserción que exige que la tabla las cubra todas. Añadir una gobernada sin cubrirla rompe aquí, no
    en la próxima auditoría."""
    def _estado_dict():
        estado = cp.estado_inicial()
        estado.setdefault("tareas", {})["T-1"] = {
            "estado": "WORKING", "autoridad": "orquestador", "previo": "WAITING_FOR_NEXT_TASK"}
        return estado

    def _log():
        d = tmp_path / "log"
        cp.registrar_evento(d, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
        cp.transicion(d, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
        return d

    def _con_criterio():
        d = _log()
        orq.fijar_criterio(d, "T-1", {"capacidad": "ejecutar_pruebas"})
        return d

    intentos = {
        "_registrar_evento_gobernado": lambda: cp._registrar_evento_gobernado(
            _log(), "estado_de_tarea", {"id": "T-1", "valor": "COMPLETED", "previo": "WORKING",
                                        "autoridad": "nadie", "causa": "bypass"}),
        "registrar_criterio_fijado": lambda: cp.registrar_criterio_fijado(
            _log(), "T-1", {"capacidad": "ejecutar_pruebas"}),
        "registrar_criterio_verificado": lambda: cp.registrar_criterio_verificado(
            _con_criterio(), "T-1", "b" * 64, True, "huella que no es la suya"),
        "cerrar_tarea": lambda: ag.cerrar_tarea(
            _con_criterio(), "T-1", {"verificado": True, "resultado": "VERIFIED"},
            autoridad="orquestador"),
        "ejecutar_tarea": lambda: ag.ejecutar_tarea(
            _con_criterio(), {"id": "T-1", "accion": "ejecutar_pruebas"}, autoridad="orquestador"),
        "completar_tarea": lambda: cp.completar_tarea(
            _estado_dict(), "T-1", "lo terminé yo", autoridad="worker-no-humano"),
        "fijar_estado_tarea": lambda: cp.fijar_estado_tarea(
            _estado_dict(), "T-1", "COMPLETED", "ya está", autoridad="worker-no-humano"),
        "transicion": lambda: cp.transicion(
            _log(), "T-1", "COMPLETED", autoridad="orquestador", causa="ya está"),
        "validar_transicion": lambda: cp.validar_transicion(
            "WORKING", "COMPLETED", "worker-no-humano", "ya está"),
        "reconciliar_tras_caida": lambda: cp.reconciliar_tras_caida(
            _log(), autoridad="orquestador", causa="reconcilio"),
        "interrumpir": lambda: cp.interrumpir(_estado_dict(), "T-1", "2026-08-30T00:00:00"),
        # Llamada **bien formada**: la primera versión desordenaba los argumentos, así que la
        # función se negaba por firma inválida y no por la garantía. Una prueba que verdea por el
        # motivo equivocado es decorativa, y este barrido existe precisamente para no serlo.
        "registrar_bloqueo_de_cuota": lambda: cp.registrar_bloqueo_de_cuota(
            _estado_dict(), mensaje="5-hour limit reached", ventana="SHORT_4H30", tarea="T-1"),
    }
    assert set(intentos) == cp.FUNCIONES_GOBERNADAS, (
        "la tabla de intentos y la lista de gobernadas han divergido: "
        f"sin cubrir {sorted(cp.FUNCIONES_GOBERNADAS - set(intentos))}, "
        f"de más {sorted(set(intentos) - cp.FUNCIONES_GOBERNADAS)}")

    abiertas = []
    for nombre, intento in intentos.items():
        try:
            resultado = intento()
        except Exception:
            continue                                   # se negó: correcto
        # Se mira el **efecto**, no lo que devuelve: una función puede no lanzar y aun así haber
        # dejado la tarea cerrada, y al revés. El estado real vive en el log y en el dict.
        if isinstance(resultado, dict):
            if resultado.get("estado") == "COMPLETED":
                abiertas.append(nombre)
            elif resultado.get("tareas", {}).get("T-1", {}).get("estado") == "COMPLETED":
                abiertas.append(nombre)
    for sufijo in ("log",):
        d = tmp_path / sufijo
        if (d / "eventos.jsonl").exists() and cp.estado_de(d, "T-1") == "COMPLETED":
            abiertas.append(f"efecto sobre el log tras {sufijo}")
    assert abiertas == [], f"cierran a COMPLETED sin humano ni criterio: {abiertas}"


def test_completar_tarea_SI_deja_cerrar_a_una_autoridad_humana(tmp_path):
    """Caso de control. Estas funciones trabajan sobre el modelo en memoria y **no tienen log que
    consultar**, así que no pueden comprobar ningún criterio mecánico. Lo honesto no es inventarles
    una verificación: es exigir el acto humano que la regla 4 reserva para lo no automatizable."""
    estado = cp.estado_inicial()
    estado.setdefault("tareas", {})["T-1"] = {
        "estado": "WORKING", "autoridad": "ceo", "previo": "WAITING_FOR_NEXT_TASK"}
    cp.completar_tarea(estado, "T-1", "revisada a mano", autoridad="ceo")
    assert cp.estado_de_tarea(estado, "T-1")["estado"] == "COMPLETED"


# ============== FORJAR EL LOG YA NO ABRE LA PUERTA --


def test_no_se_puede_forjar_un_criterio_con_registrar_evento_en_crudo(tmp_path):
    """La auditoría cerró la tarea registrando los dos eventos a mano. `registrar_evento` bloqueaba
    `estado_de_tarea` y solo eso; los eventos del criterio son ahora **igual de gobernados**, porque
    conceden exactamente lo mismo: un `COMPLETED`."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    for tipo in ("criterio_fijado", "criterio_verificado"):
        with pytest.raises(cp.EventoNoGobernado):
            cp.registrar_evento(tmp_path, tipo, {"id": "T-1", "huella": "0" * 64, "verificado": True})
    assert cp.estado_de(tmp_path, "T-1") != "COMPLETED"


def test_la_via_gobernada_del_criterio_SI_funciona(tmp_path):
    """Caso de control: se bloquea la vía cruda, no el mecanismo."""
    cp.registrar_evento(tmp_path, "tarea_registrada", {"id": "T-1", "accion": "ejecutar_pruebas"})
    cp.transicion(tmp_path, "T-1", "WORKING", autoridad="orquestador", causa="empieza")
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    orq.verificar_criterio(tmp_path, "T-1", lambda _c: 0)
    cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="orquestador", causa="criterio en verde")
    assert cp.estado_de(tmp_path, "T-1") == "COMPLETED"


# ============== LOS ENLACES SIMBOLICOS --


def test_zona_permitida_SIN_raiz_resuelve_los_enlaces_simbolicos(tmp_path):
    """Un symlink dentro de la zona que apunte al producto se aceptaba: la comparación era de texto.
    La puerta de escritura usa `raiz` y sí resolvía, pero el veredicto de `RevisorSubagente` —que usa
    la forma por defecto— quedaba corrompido, y un revisor que opina sobre el fichero equivocado es
    peor que no tener revisor."""
    zona = tmp_path / "entorno" / "control-plane"
    zona.mkdir(parents=True)
    producto = tmp_path / "walking-skeleton" / "aura_skeleton"
    producto.mkdir(parents=True)
    destino = producto / "composicion.py"
    destino.write_text("x", encoding="utf-8")
    enlace = zona / "inocente.py"
    enlace.symlink_to(destino)
    assert not ac.zona_permitida(enlace), "el enlace apunta al producto: sigue siendo el producto"


def test_un_fichero_REAL_de_la_zona_sigue_pasando(tmp_path):
    """Caso de control: resolver enlaces no puede cerrar la zona legítima."""
    assert ac.zona_permitida("entorno/control-plane/orquestador.py")
    assert ac.zona_permitida(pathlib.Path(__file__).resolve())
