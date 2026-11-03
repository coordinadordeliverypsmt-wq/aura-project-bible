"""RED · **Blindaje del estado de produccion** (CEO, 2026-08-26).

Una prueba de F1 recorrio las funciones publicas del modulo y termino escribiendo sobre el
`estado.json` **real** del Control Plane, destruyendo informacion historica que solo se ha podido
restaurar en parte. La orden del CEO es que eso no pueda repetirse:

> *«Agregar un meta-control permanente que impida que una prueba de auditoria escriba accidentalmente
> sobre estado.json REAL. La prueba debe fallar si detecta que su destino coincide con el estado de
> produccion.»*

El control vive en `conftest.py` y se aplica a **toda** la bateria, no solo a las pruebas de F1: una
proteccion que hay que acordarse de invocar no protege de un descuido, y el incidente **fue** un
descuido.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import control_plane as cp
import pytest


def _huella() -> str | None:
    ruta = cp.ESTADO_POR_DEFECTO
    if not ruta.exists():
        return None
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_el_blindaje_existe_y_esta_activo_en_toda_la_bateria():
    """El control es una fixture `autouse` del `conftest.py`: nadie tiene que acordarse de pedirlo."""
    conftest = pathlib.Path(__file__).parent / "conftest.py"
    assert conftest.exists(), "sin conftest.py no hay proteccion global"
    fuente = conftest.read_text(encoding="utf-8")
    assert "autouse=True" in fuente, "el blindaje debe aplicarse solo, no bajo peticion"
    assert "ESTADO_POR_DEFECTO" in fuente


def test_escribir_en_el_estado_REAL_hace_fallar_la_prueba_en_el_acto():
    """**El caso de control del blindaje.** Si esto no lanzara, el `conftest` no estaria protegiendo
    nada — que es justamente como el incidente paso inadvertido hasta la regresion."""
    with pytest.raises(cp.EscrituraDeProduccionProhibida, match="estado de produccion|produccion"):
        cp.guardar(cp.estado_inicial())          # sin destino: apunta al estado REAL


def test_el_blindaje_no_estorba_a_quien_escribe_donde_debe(tmp_path):
    destino = pathlib.Path(tmp_path) / "estado.json"
    cp.guardar(cp.estado_inicial(), destino)
    assert cp.cargar(destino) is not None
    cp.actualizar_estado(destino, lambda e: e)


def test_el_estado_real_sigue_siendo_LEGIBLE_bajo_pruebas():
    """Blindar la escritura no puede impedir la lectura: hay pruebas de regresion del CEO que leen
    el registro real a proposito (`test_red_6_DEF_CUERPO_LIBRE...`)."""
    assert cp.cargar(cp.ESTADO_POR_DEFECTO) is not None
    real = json.loads(cp.ESTADO_POR_DEFECTO.read_text(encoding="utf-8"))
    assert any(d.get("id") == "DEF-CUERPO-LIBRE" for d in real.get("defectos", []))


def test_la_huella_del_estado_real_no_cambia_al_ejecutar_esta_bateria():
    """Red de seguridad por si alguien escribe por una via que la intercepcion no cubre —un `open()`
    directo, por ejemplo—. La fixture compara la huella antes y despues de **cada** prueba."""
    assert _huella() is not None, "el estado real debe existir para poder vigilarlo"


# ================== TERCERA AUDITORÍA INDEPENDIENTE · tres hallazgos GRAVES --


def test_auditoria3_g1_guardar_RECHAZA_una_tarea_fabricada_a_mano(tmp_path):
    """**GRAVE 1.** `validar()` solo miraba `status` y `cuota`, nunca `tareas`. Así que escribir
    directamente en el diccionario y llamar a `guardar()` persistía cualquier estado inventado —la
    misma creación en `COMPLETED` que `ESTADOS_CREABLES` decía haber cerrado, entrando por debajo.

    El detector de rutas de F1 no podía verlo: enumera **funciones**, y esto no pasa por ninguna.

    Lo que se puede garantizar de verdad: el **borde de persistencia**. Una entrada de tarea sin los
    campos que solo pone el gobierno (`autoridad`, `previo`) no se escribe."""
    destino = pathlib.Path(tmp_path) / "estado.json"
    e = cp.estado_inicial()
    e.setdefault("tareas", {})["T-CLANDESTINA"] = {"estado": "COMPLETED", "autoridad": "nadie"}
    with pytest.raises(ValueError, match="gobierno|procedencia|previo"):
        cp.guardar(e, destino)
    assert not destino.exists(), "no se persiste un estado que no se pudo validar"


def test_auditoria3_g1_el_estado_gobernado_SI_se_persiste(tmp_path):
    """Caso de control: la validación nueva no puede romper el camino honesto."""
    destino = pathlib.Path(tmp_path) / "estado.json"
    e = cp.estado_inicial()
    cp.fijar_estado_tarea(e, "T-1", "WORKING", "empieza", autoridad="ceo")
    cp.guardar(e, destino)
    assert cp.cargar(destino)["tareas"]["T-1"]["estado"] == "WORKING"


def test_auditoria3_g2_una_tarea_creada_de_la_nada_queda_MARCADA():
    """**GRAVE 2.** Crear en `FAILED` → `WORKING` → `COMPLETED` con autoridad no humana produce una
    tarea que nunca existió, dada por terminada, en tres llamadas.

    **PREMISA SUPERADA — el rodeo está CERRADO desde el 2026-08-30.** Esta prueba decía:

    > *«No se puede cerrar aquí… el control que lo cierra de verdad es el criterio **A12**, que
    > pertenece a **F4/F5**, hoy bloqueadas.»*

    F4 se cerró, `DEC-ORCH-2` la desbloqueó y A12 se implementó. La segunda auditoría independiente
    encontró que `completar_tarea` seguía aceptando autoridad no humana, y ahora se niega: trabaja
    sobre el modelo en memoria, no tiene log donde comprobar un criterio mecánico, y `§14.bis`
    regla 4 reserva a un acto humano lo que no es automatizable.

    Se conservan **las dos** garantías, porque son distintas: el tercer paso ya no lo puede dar un
    adaptador, y la marca de origen sigue viajando por la vía humana, que sí queda abierta."""
    e = cp.estado_inicial()
    cp.fijar_estado_tarea(e, "T-FANTASMA", "FAILED", "de la nada", autoridad="adaptador")
    assert cp.estado_de_tarea(e, "T-FANTASMA")["creada_sin_origen"] is True

    cp.fijar_estado_tarea(e, "T-FANTASMA", "WORKING", "reintento", autoridad="adaptador")
    # El tercer paso del rodeo, hoy cerrado: sin humano y sin criterio no hay COMPLETED.
    with pytest.raises(cp.CriterioNoVerificado):
        cp.completar_tarea(e, "T-FANTASMA", "resultado inventado", autoridad="adaptador")
    assert cp.estado_de_tarea(e, "T-FANTASMA")["estado"] == "WORKING"

    # Y por la vía humana, que sigue abierta a propósito, la marca sobrevive a la cadena entera:
    # el CEO puede cerrarla, pero el registro dice que apareció sin origen.
    cp.completar_tarea(e, "T-FANTASMA", "resultado revisado a mano", autoridad="ceo")
    hecha = next(t for t in e["trabajo_completado"] if t["id"] == "T-FANTASMA")
    assert hecha["creada_sin_origen"] is True, "la marca sobrevive a la cadena entera"

    # Caso de control: registrarla como pendiente y luego avanzarla NO la marca. Sin este
    # contraste la marca no distinguiría nada, porque toda tarea nueva carece de estado previo.
    limpia = cp.estado_inicial()
    cp.fijar_estado_tarea(limpia, "T-REAL", "WAITING_FOR_NEXT_TASK", "se registra", autoridad="ceo")
    cp.fijar_estado_tarea(limpia, "T-REAL", "WORKING", "empieza", autoridad="ceo")
    assert cp.estado_de_tarea(limpia, "T-REAL")["creada_sin_origen"] is False


def test_auditoria3_g3_el_destino_por_defecto_se_resuelve_al_LLAMAR_no_al_importar(tmp_path,
                                                                                  monkeypatch):
    """**GRAVE 3.** `destino: Path = ESTADO_POR_DEFECTO` se evalúa **una vez, al importar**. Quien
    aislara una prueba con `monkeypatch.setattr(cp, "ESTADO_POR_DEFECTO", tmp)` creía estar a salvo
    y seguía escribiendo el fichero real, porque el valor por defecto quedó horneado en la firma.

    Es una trampa especialmente cruel: el patrón que la gente usa **para protegerse** era el que
    fallaba."""
    import inspect

    assert inspect.signature(cp.guardar).parameters["destino"].default is None, (
        "el default no puede ser el Path: debe resolverse en tiempo de llamada")
    falso = pathlib.Path(tmp_path) / "falso.json"
    monkeypatch.setattr(cp, "ESTADO_POR_DEFECTO", falso)
    cp.guardar(cp.estado_inicial())
    assert falso.exists(), "guardar() debe honrar la reasignación de ESTADO_POR_DEFECTO"


def test_auditoria3_g3_el_blindaje_RESTAURA_el_fichero_no_solo_lo_denuncia():
    """El blindaje era **detectivo**: denunciaba después del hecho, con el fichero ya corrompido en
    disco. Ahora el `conftest` guarda una copia antes de cada prueba y **la repone** si detecta
    cambio, así que el daño no se consolida aunque alguien desactive la intercepción."""
    conftest = pathlib.Path(__file__).parent / "conftest.py"
    fuente = conftest.read_text(encoding="utf-8")
    assert "write_bytes" in fuente or "restaur" in fuente.lower(), (
        "el blindaje debe reponer el fichero, no limitarse a fallar")
