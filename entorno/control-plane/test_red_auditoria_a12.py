"""RED · lo que encontró la auditoría independiente sobre A12 (2026-08-30).

Yo declaré A12 cerrado. **No lo estaba**, y las dos razones son las dos que este proyecto ya tiene
escritas en la pared:

**GRAVE 1 · `transicion()` es una ruta alternativa.** La puerta del criterio mecánico vivía **solo**
en `agentes.cerrar_tarea`. `control_plane.transicion()` es la primitiva que usa toda la base —incluida
`agentes.py`— y no la consultaba. Reproducido por la auditoría `[EJEC]`:

```python
ag.cerrar_tarea(d, "T-1", falsa, autoridad="orquestador")     # -> SinEvidencia  (correcto)
cp.transicion(d, "T-1", "COMPLETED", autoridad="ceo", causa="afirmo que esta hecho")
cp.estado_de(d, "T-1")                                        # -> "COMPLETED"   (se cerró igual)
```

Es **ALERTA-005** literal: *«toda ejecución pasa por el motor único… ninguna ruta alternativa»*. Y mis
34 pruebas nuevas no la veían porque **todas** entraban por `cerrar_tarea`: probé la puerta que había
puesto, no el edificio.

**GRAVE 2 · el aparato no estaba enchufado.** `grep` sobre los módulos de producción: nadie llama a
`fijar_criterio()` antes de invocar a un worker. Para toda tarea real `criterio_registrado()` devuelve
`None`, la rama de protección de `cerrar_tarea` queda **inerte**, y el cierre seguía dependiendo de
`verificar_efecto()` con la evidencia que elige el worker — la vulnerabilidad exacta que A12 decía
haber cerrado.

Es el defecto que el propio `CLAUDE.md` pone como ejemplo: *«el mutante "la composición no enciende
las automatizaciones" sobrevivió con 426 pruebas en verde, y era ALERTA-005 otra vez»*. **El mecanismo
existía, tenía pruebas propias en verde, y no estaba conectado al bucle.**

La regla que sale de aquí: **una garantía probada sobre su propia función no es una garantía del
sistema.** Hay que probarla desde la primitiva que cualquiera usaría.
"""

from __future__ import annotations

import agentes as ag
import control_plane as cp
import orquestador as orq
import pytest


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _tarea_en_curso(d, ident="T-1", accion="ejecutar_pruebas"):
    cp.registrar_evento(d, "tarea_registrada", {"id": ident, "accion": accion})
    cp.transicion(d, ident, "WORKING", autoridad="orquestador", causa="empieza")


# ============================ GRAVE 1 · NINGUNA RUTA ALTERNATIVA --


def test_transicion_NO_cierra_una_tarea_con_criterio_sin_haberlo_verificado(tmp_path):
    """La ruta que encontró la auditoría, cerrada. Da igual la autoridad que se declare: si la tarea
    tiene criterio mecánico fijado, `COMPLETED` exige que ese criterio se haya **ejecutado**."""
    _tarea_en_curso(tmp_path)
    orq.fijar_criterio(tmp_path, "T-1", {"capacidad": "ejecutar_pruebas"})
    with pytest.raises(cp.CriterioNoVerificado):
        cp.transicion(tmp_path, "T-1", "COMPLETED", autoridad="ceo", causa="afirmo que está hecho")
    assert cp.estado_de(tmp_path, "T-1") != "COMPLETED"


def test_ninguna_autoridad_NO_HUMANA_cierra_a_COMPLETED_sin_criterio_verificado(tmp_path):
    """La otra mitad de la ruta: sin criterio fijado, un cierre automático tampoco vale. `§14.bis`
    regla 4 dice que una tarea sin criterio mecánico **no es `AUTO`**, luego solo puede cerrarla un
    acto humano. Si bastara con declararse `orquestador`, la regla 4 no existiría."""
    _tarea_en_curso(tmp_path, "T-2")
    with pytest.raises(cp.CriterioNoVerificado):
        cp.transicion(tmp_path, "T-2", "COMPLETED", autoridad="orquestador", causa="ya está")
    assert cp.estado_de(tmp_path, "T-2") != "COMPLETED"


def test_un_acto_HUMANO_si_puede_cerrar_una_tarea_sin_criterio_mecanico(tmp_path):
    """Caso de control, y además la regla 4 al derecho: lo que no es automatizable lo cierra una
    persona. Sin esto, el arreglo habría bloqueado el trabajo que **debe** juzgar un humano."""
    _tarea_en_curso(tmp_path, "T-3")
    cp.transicion(tmp_path, "T-3", "COMPLETED", autoridad="ceo", causa="revisado a mano")
    assert cp.estado_de(tmp_path, "T-3") == "COMPLETED"


def test_el_criterio_VERIFICADO_si_deja_cerrar_por_la_via_automatica(tmp_path):
    """Caso de control de la vía automática: el mecanismo distingue, no bloquea siempre."""
    _tarea_en_curso(tmp_path, "T-4")
    orq.fijar_criterio(tmp_path, "T-4", {"capacidad": "ejecutar_pruebas"})
    orq.verificar_criterio(tmp_path, "T-4", lambda _c: 0)
    cp.transicion(tmp_path, "T-4", "COMPLETED", autoridad="orquestador", causa="criterio en verde")
    assert cp.estado_de(tmp_path, "T-4") == "COMPLETED"


def test_un_criterio_verificado_que_FALLO_no_deja_cerrar(tmp_path):
    """Haberlo ejecutado no basta: tiene que haber salido bien. Si valiera la mera ejecución,
    bastaría lanzarlo y despreciar el resultado."""
    _tarea_en_curso(tmp_path, "T-5")
    orq.fijar_criterio(tmp_path, "T-5", {"capacidad": "ejecutar_pruebas"})
    orq.verificar_criterio(tmp_path, "T-5", lambda _c: 1)
    with pytest.raises(cp.CriterioNoVerificado):
        cp.transicion(tmp_path, "T-5", "COMPLETED", autoridad="orquestador", causa="da igual")


def test_la_verificacion_de_OTRA_tarea_no_abre_esta(tmp_path):
    """La atadura sigue siendo por tarea y por huella, también en la primitiva."""
    _tarea_en_curso(tmp_path, "T-6")
    _tarea_en_curso(tmp_path, "T-7")
    orq.fijar_criterio(tmp_path, "T-6", {"capacidad": "ejecutar_pruebas"})
    orq.fijar_criterio(tmp_path, "T-7", {"capacidad": "verificar_calidad"})
    orq.verificar_criterio(tmp_path, "T-6", lambda _c: 0)
    with pytest.raises(cp.CriterioNoVerificado):
        cp.transicion(tmp_path, "T-7", "COMPLETED", autoridad="orquestador", causa="me vale la de al lado")


def test_la_verificacion_queda_REGISTRADA_en_el_log(tmp_path):
    """Sin evento, la primitiva no tendría con qué decidir: el estado del criterio vive en el
    historial, no en la memoria de quien lo ejecutó."""
    _tarea_en_curso(tmp_path, "T-8")
    orq.fijar_criterio(tmp_path, "T-8", {"capacidad": "ejecutar_pruebas"})
    orq.verificar_criterio(tmp_path, "T-8", lambda _c: 0)
    assert "criterio_verificado" in [e["tipo"] for e in cp.leer_eventos(tmp_path)]


def test_TODAS_las_vias_publicas_a_COMPLETED_respetan_el_criterio(tmp_path):
    """El barrido que faltaba. `ALERTA-005` no se cierra probando una puerta: se cierra recorriendo
    **todas** las funciones públicas que podrían llevar a `COMPLETED` y comprobando que ninguna lo
    hace. Mi error fue probar la que yo había puesto."""
    _tarea_en_curso(tmp_path, "T-9")
    orq.fijar_criterio(tmp_path, "T-9", {"capacidad": "ejecutar_pruebas"})
    falsa = ag.verificar_efecto({"tipo": "salida_contiene", "patron": "OK", "salida": "OK"})

    vias = [
        ("agentes.cerrar_tarea", lambda: ag.cerrar_tarea(tmp_path, "T-9", falsa, autoridad="orquestador")),
        ("control_plane.transicion", lambda: cp.transicion(tmp_path, "T-9", "COMPLETED",
                                                           autoridad="ceo", causa="x")),
        ("registrar_evento crudo", lambda: cp.registrar_evento(tmp_path, "estado_de_tarea",
                                                               {"id": "T-9", "estado": "COMPLETED"})),
    ]
    abiertas = []
    for nombre, via in vias:
        try:
            via()
        except Exception:
            continue
        if cp.estado_de(tmp_path, "T-9") == "COMPLETED":
            abiertas.append(nombre)
    assert abiertas == [], f"rutas que cierran sin criterio verificado: {abiertas}"


# ============================ GRAVE 2 · EL APARATO, ENCHUFADO --


def test_una_tarea_SIN_criterio_mecanico_no_es_AUTO(tmp_path):
    """`§14.bis` regla 4, aplicada donde se decide de verdad. Si el bucle acepta una tarea sin
    criterio, todo el aparato queda inerte: es lo que la auditoría encontró."""
    o = orq.Orquestador(tmp_path)
    assert not o.es_ejecutable({"id": "T-1", "accion": "ejecutar_pruebas"})
    assert o.es_ejecutable({"id": "T-1", "accion": "ejecutar_pruebas",
                            "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}})


def test_el_bucle_FIJA_el_criterio_en_el_log_ANTES_de_invocar(tmp_path):
    """`§14.bis` regla 1: *«se escribe en el event log **antes** de invocar al Worker»*. Se comprueba
    por **orden de eventos**, no por su presencia: fijarlo después sería exactamente el vector que la
    regla prohíbe —ejecutar cualquier cosa y escribir luego el criterio que esa cosa cumple—."""
    tarea = {"id": "T-1", "accion": "ejecutar_pruebas",
             "criterio_de_finalizacion": {"capacidad": "ejecutar_pruebas"}}
    cp.registrar_evento(tmp_path, "tarea_registrada", tarea)
    o = orq.Orquestador(tmp_path)
    momentos = {}

    def invocar(_t):
        momentos["invocacion"] = len(cp.leer_eventos(tmp_path))

    o.worker.invocar = invocar
    o.ciclo(max_iteraciones=2)

    tipos = [e["tipo"] for e in cp.leer_eventos(tmp_path)]
    assert "criterio_fijado" in tipos, "el bucle tiene que fijarlo: si no, el aparato está inerte"
    assert tipos.index("criterio_fijado") < momentos["invocacion"], "lo fijó DESPUÉS de invocar"


def test_el_bucle_no_invoca_una_tarea_cuyo_criterio_no_es_mecanico(tmp_path):
    """La regla 4 en el bucle: prosa por criterio significa que no se automatiza, no que se ejecute
    igual y ya se verá."""
    cp.registrar_evento(tmp_path, "tarea_registrada",
                        {"id": "T-P", "accion": "ejecutar_pruebas",
                         "criterio_de_finalizacion": {"prosa": "que quede bien"}})
    o = orq.Orquestador(tmp_path)
    invocadas = []
    o.worker.invocar = lambda t: invocadas.append(t["id"])
    o.ciclo(max_iteraciones=3)
    assert invocadas == []


# ============================ MEDIO · LA ZONA CON `raiz` CONCEDÍA EL PRODUCTO --


def test_la_raiz_declarada_NO_puede_conceder_el_producto(tmp_path):
    """Hallazgo MEDIO de la auditoría: con `raiz` dado, `zona_permitida` dejaba de mirar la zona y
    solo comprobaba la pertenencia. Con `raiz=<raíz del repo>` concedía `walking-skeleton/`.

    *«El producto queda fuera, siempre»* tiene que sostenerlo **la función**, no una convención de
    nombres vigilada por `grep`. `raiz` solo puede **estrechar**, nunca ampliar."""
    import autoconstruccion as ac
    raiz_repo = pathlib_parent()
    producto = raiz_repo / "walking-skeleton" / "aura_skeleton" / "composicion.py"
    assert not ac.zona_permitida(producto, raiz=raiz_repo)
    assert not ac.zona_permitida(producto, raiz=raiz_repo / "walking-skeleton")
    assert not ac.zona_permitida(tmp_path / "aura_skeleton" / "x.py", raiz=tmp_path)


def pathlib_parent():
    import pathlib
    return pathlib.Path(__file__).resolve().parents[2]


# ============================ MEDIO · MENSAJES FALSOS --


def test_ningun_mensaje_del_orquestador_afirma_que_el_catalogo_AUTO_esta_vacio():
    """Hallazgo MEDIO: el catálogo dejó de estar vacío con `D-ORCH-3` (2026-08-26) y el módulo seguía
    diciendo lo contrario en su docstring y en sus excepciones. `INV-9` va en las dos direcciones: no
    fingir capacidad que no existe, y no negar la que sí.

    Un mensaje falso en una excepción es peor que un comentario desfasado: es lo que alguien lee
    justo cuando está depurando y menos margen tiene para dudar."""
    import pathlib
    fuente = (pathlib.Path(__file__).resolve().parent / "orquestador.py").read_text(encoding="utf-8")
    assert orq.acciones_de_nivel("AUTO"), "el catálogo NO está vacío desde D-ORCH-3"
    for falsedad in ("catalogo AUTO esta vacio", "catálogo AUTO está vacío",
                     "El catalogo `AUTO` esta **vacio**"):
        assert falsedad not in fuente, f"el módulo sigue afirmando: {falsedad!r}"


def test_una_verificacion_con_huella_QUE_NO_ES_LA_SUYA_no_cuenta(tmp_path):
    """El mutante `AUD-M4` sobrevivió a la primera pasada: quitar la comparación de huella no rompía
    nada, porque todas mis pruebas distinguían ya por `id`. Faltaba el caso que la huella protege de
    verdad — una verificación **de esta misma tarea** que no corresponde al criterio que rige.

    Ocurre si el criterio se refija: `criterio_fijado_de` devuelve el **primero**, así que una
    verificación de otro no puede abrir la puerta. Y es también el caso adversario: `criterio_fijado`
    y `criterio_verificado` no son eventos bloqueados en crudo, de modo que quien pueda escribir en
    el log puede fabricar uno. **Eso no es una vulnerabilidad del worker** —A6 demuestra que no tiene
    permiso de escritura sobre `entorno/control-plane/`— pero sí la razón por la que la huella tiene
    que atar: sin ella, cualquier `criterio_verificado` suelto valdría para cualquier criterio."""
    _tarea_en_curso(tmp_path, "T-F")
    orq.fijar_criterio(tmp_path, "T-F", {"capacidad": "ejecutar_pruebas"})
    # Por la **puerta gobernada**, que es la única que queda: registrar el evento en crudo se
    # bloquea desde la segunda auditoría. La puerta acepta la huella que se le pase, y ahí está el
    # caso: una verificación de esta misma tarea que no corresponde al criterio que rige.
    cp.registrar_criterio_verificado(tmp_path, "T-F", "0" * 64, True,
                                     "una verificación que no es de este criterio")
    assert cp.criterio_superado(tmp_path, "T-F") is False
    with pytest.raises(cp.CriterioNoVerificado):
        cp.transicion(tmp_path, "T-F", "COMPLETED", autoridad="orquestador", causa="me vale esa")
    assert cp.estado_de(tmp_path, "T-F") != "COMPLETED"
