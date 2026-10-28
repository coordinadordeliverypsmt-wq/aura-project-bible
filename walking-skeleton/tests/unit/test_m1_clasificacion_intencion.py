"""M-1 — matriz de regresion ACTO x CONTENIDO x RUTA (DP-D-M-7, Opcion A aprobada por el CEO).

**Que fija esta bateria.** No que el clasificador acierte mucho: que las cosas que NO pueden pasar
sigan sin pasar. La metrica de acierto vive en `bateria-intencion.json` y se mide aparte; aqui estan
las garantias, que son binarias.

La mas importante de todas, y la razon de que este fichero exista: **M-1 no puede anadir ni una sola
escritura de memoria que antes no ocurriera.** Se prueba por cuantificacion sobre las dos baterias
reales, no con ejemplos escogidos.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from aura_skeleton.core import intencion as I
from aura_skeleton.core.orchestrator import _es_consulta_de_memoria, _es_pregunta

DATOS = pathlib.Path(__file__).resolve().parents[1] / "datos" / "bateria_memoria.json"
INTENCION = (pathlib.Path(__file__).resolve().parents[3]
             / "milestones" / "m3-entry" / "bateria-intencion.json")


def _bateria_memoria() -> dict:
    return json.loads(DATOS.read_text(encoding="utf-8"))


def _negativas() -> list[str]:
    return [c["texto"] for c in _bateria_memoria()["consultas"] if c["esperado"] is None]


# ============================================================ LA GARANTIA QUE NO PUEDE CAER --


def test_las_24_negativas_siguen_protegidas_despues_de_M1():
    """**24/24.** Es la garantia anti-fabricacion, y M-1 no la toca: solo le dio otro domicilio."""
    fallos = [t for t in _negativas() if not _es_consulta_de_memoria(t)]
    assert not fallos, f"{len(fallos)}/24 negativas desprotegidas tras M-1: {fallos}"


def test_la_senal_sintactica_es_identica_a_la_de_antes():
    """`_es_pregunta` delega en `intencion.es_interrogativa`. Delegar no es cambiar.

    Caso de control: si alguien reimplementara `es_interrogativa` con otro criterio, esta prueba
    caeria sobre las 77 consultas reales, no sobre un ejemplo elegido a mano.
    """
    consultas = [c["texto"] for c in _bateria_memoria()["consultas"]]
    distintas = [t for t in consultas if _es_pregunta(t) != I.es_interrogativa(t)]
    assert not distintas, f"la delegacion cambio el comportamiento en: {distintas}"


def test_M1_NO_PUEDE_anadir_escrituras_que_antes_no_ocurrian():
    """**La propiedad estructural del eje 2.** Antes se escribia si `not _es_pregunta(text)`.

    Ahora se exige ademas que el contenido este en la whitelist. Eso solo puede RESTAR. Si algun dia
    alguien relaja `contenido_proposicional`, esta prueba lo atrapa: no mide una lista de ejemplos,
    cuantifica sobre los 249 turnos de las dos baterias.
    """
    turnos = [c["texto"] for c in _bateria_memoria()["consultas"]]
    turnos += [c["texto"] for c in json.loads(INTENCION.read_text(encoding="utf-8"))["casos"]]
    nuevas = [t for t in turnos if I.debe_almacenarse(t) and _es_pregunta(t)]
    assert not nuevas, f"M-1 escribiria {len(nuevas)} turnos que antes no se escribian: {nuevas[:5]}"


@pytest.mark.parametrize("texto", [
    "¿Cuál es el nombre de mi abuela?",
    "¿A qué hora ceno normalmente?",
    "¿Qué marca de teléfono tengo?",
    "¿Cuál es la dirección y el teléfono de la oficina nueva?",
    "¿Dónde dejé las llaves de mi coche nuevo?",
])
def test_una_pregunta_personal_NUNCA_se_convierte_en_memoria(texto):
    """Aunque la pregunta CONTENGA un hecho personal, el acto manda para escribir: no se almacena.

    Es `D-M-2`: almacenarla haria que al repetirla se cubriera a si misma y `ADR-0014` dejara de
    activarse. Los dos ejes son ortogonales, y aqui se ve: el contenido puede ser `HECHO_USUARIO` y
    aun asi no escribirse.
    """
    assert I.acto_de_habla(texto) == I.PREGUNTA
    assert not I.debe_almacenarse(texto)


# ================================================================= EJE 1 · ACTO DE HABLA --


@pytest.mark.parametrize("texto,acto", [
    # PREGUNTA
    ("¿Cómo me llamo?", I.PREGUNTA),
    ("¿Sabes que me mudé a Alcalá el año pasado?", I.PREGUNTA),
    # AFIRMACION -- incluida la negacion sobre uno mismo, que fue el agujero del 56,2 % del DP
    ("Trabajo en logística", I.AFIRMACION),
    ("No soy alérgico a los frutos secos", I.AFIRMACION),
    ("No tengo hermanos", I.AFIRMACION),
    ("No trabajo los viernes", I.AFIRMACION),
    ("Cuando llego a casa siempre me hago un té", I.AFIRMACION),
    ("Mi profesora recomienda leer más", I.AFIRMACION),
    # ORDEN -- afirmativa, negada, y con contenido personal incrustado
    ("Apaga la luz del salón", I.ORDEN),
    ("No borres nada", I.ORDEN),
    ("No enciendas la luz", I.ORDEN),
    ("Anota que el viernes viajo a Lisboa", I.ORDEN),
    ("Si llueve avísame antes de salir", I.ORDEN),
    # CORRECCION
    ("Ya no trabajo en logística", I.CORRECCION),
    ("Mi apellido no es Pérez, es Peres", I.CORRECCION),
    # SOCIAL
    ("gracias", I.SOCIAL),
    ("Hola", I.SOCIAL),
])
def test_eje1_acto_de_habla(texto, acto):
    assert I.acto_de_habla(texto) == acto, f"{texto!r}"


def test_la_precedencia_es_explicita_y_ese_orden_es_la_regla():
    """El DP exige prioridad «explicita y documentada». Si alguien reordena, esto cae."""
    assert I.PRECEDENCIA_ACTO == (I.CORRECCION, I.ORDEN, I.PREGUNTA, I.SOCIAL, I.AFIRMACION)
    # ORDEN gana a PREGUNTA: empieza por interrogativo, pero pide que se haga algo.
    assert I.acto_de_habla("Cuando termine el mes hazme un resumen") == I.ORDEN


# ============================================================ EJE 2 · CONTENIDO Y ESCRITURA --


@pytest.mark.parametrize("texto,contenido,almacena", [
    ("Trabajo en logística", I.HECHO_USUARIO, True),
    ("Mi cumpleaños es el 14 de marzo", I.HECHO_USUARIO, True),
    ("No soy alérgico a los frutos secos", I.HECHO_USUARIO, True),
    ("Para el café uso la italiana", I.CONOCIMIENTO_PROCEDURAL, True),
    ("gracias", I.NADA_PROPOSICIONAL, False),
    ("¿Quién escribió el Quijote?", I.INCIERTO, False),
    ("Si tengo dos caballos y vendo uno, ¿cuántos quedan?", I.HECHO_USUARIO, False),
])
def test_eje2_contenido_y_decision_de_escritura(texto, contenido, almacena):
    assert I.contenido_proposicional(texto) == contenido, f"{texto!r}"
    assert I.debe_almacenarse(texto) is almacena, f"{texto!r}"


def test_ante_la_duda_NO_se_almacena():
    """La regla de seguridad del CEO para el eje 2. `INCIERTO` nunca entra en la whitelist."""
    assert I.INCIERTO not in I.ALMACENABLES
    assert I.NADA_PROPOSICIONAL not in I.ALMACENABLES
    # Una regla condicional tampoco: su sitio es el almacen de reglas, no la memoria.
    assert I.REGLA_CONDICIONAL not in I.ALMACENABLES


def test_conocimiento_general_e_hipotesis_no_son_hechos_del_usuario():
    """Ni el conocimiento del mundo ni una suposicion se convierten en memoria personal."""
    for t in ("¿Qué color es el cielo?", "¿Por qué llueve?", "¿Cuál es la capital de Francia?",
              "Supongamos que el agua fuera roja", "¿Qué pasaría si la gravedad fuera la mitad?"):
        assert not I.debe_almacenarse(t), t


def test_una_afirmacion_legitima_SIGUE_pudiendo_almacenarse():
    """Caso de control del conservadurismo: si el eje 2 se volviera paranoico, AURA dejaria de
    aprender. Esta prueba existe para que endurecerlo tenga un coste visible."""
    assert I.debe_almacenarse("Trabajo en logística")
    assert I.debe_almacenarse("Mi color favorito es el azul")


# ==================================================================== AUTORIDAD Y RUTAS --


def test_una_etiqueta_no_es_una_autorizacion():
    """M-1 clasifica; no ejecuta, no escribe y no concede permisos.

    Garantia ESTRUCTURAL, verificada sobre los imports reales del modulo con `ast` —no sobre el texto
    del fichero, que menciona esas piezas en la prosa para explicar por que NO las usa—. Si alguien
    se trajera el motor, los permisos o la memoria, esta prueba cae antes de que llegue a usarlos.
    """
    import ast
    arbol = ast.parse(pathlib.Path(I.__file__).read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
            modulos.update(a.name for a in nodo.names)
    assert modulos <= {"__future__", "annotations", "re", "unicodedata", "dataclasses", "dataclass"}, (
        f"intencion.py importa algo que no le corresponde: {modulos}")


def test_M1_no_usa_el_modelo_para_clasificar():
    """ADR-0014 §2: la deteccion es determinista, en el nucleo, nunca por clasificacion del LLM.

    Se comprueba sobre el CODIGO ejecutable, no sobre los comentarios: se recorren las llamadas del
    arbol sintactico. Un `provider.infer(...)` aqui seria la reintroduccion de la dependencia que
    ADR-0014 elimina.
    """
    import ast
    arbol = ast.parse(pathlib.Path(I.__file__).read_text(encoding="utf-8"))
    llamadas = {ast.unparse(n.func) for n in ast.walk(arbol) if isinstance(n, ast.Call)}
    prohibidas = [c for c in llamadas
                  if any(p in c.lower() for p in ("infer", "provider", "router", "llm", "model"))]
    assert not prohibidas, f"M-1 no puede llamar al modelo: {prohibidas}"


def test_R7_servir_no_pasa_por_el_clasificador_y_eso_esta_bien():
    """**R7** (`python -m aura_skeleton --servir`) ejecuta sin turno conversacional.

    No se le anade clasificacion de intencion —no hay intencion que clasificar: no hay hablante—.
    Lo que se fija aqui es lo que SI debe protegerla: que siga pasando por el motor unico, y que el
    motor siga comprobando el kill switch. Si alguien cableara `servir` a un adaptador directo,
    saltandose el motor, esto lo detecta.
    """
    from aura_skeleton.core import motor_ciclo
    fuente = pathlib.Path(motor_ciclo.__file__).read_text(encoding="utf-8")
    assert "intencion" not in fuente, "R7 no debe convertirse en una ruta conversacional"
    from aura_skeleton.core import director
    assert "motor" in pathlib.Path(director.__file__).read_text(encoding="utf-8"), (
        "R7 llega al efecto por el Director: si dejara de usar el motor, seria un bypass")


def test_R6_el_bus_de_red_no_esta_cableado():
    """**R6.** Mientras el bus sea in-process, `on_turn` solo recibe lo que publica `handle_utterance`.

    M-1 no introduce bypass por aqui porque no cambia quien publica. Esta prueba fija el hecho que lo
    sostiene: si alguien cableara NATS, la premisa deja de valer y hay que revisar la frontera.
    """
    from aura_skeleton import composicion
    fuente = pathlib.Path(composicion.__file__).read_text(encoding="utf-8")
    assert "InProcessEventBus()" in fuente
    assert "NatsEventBus" not in fuente, "cablear NATS exige revisar R6: es DECISION_REQUIRED"
