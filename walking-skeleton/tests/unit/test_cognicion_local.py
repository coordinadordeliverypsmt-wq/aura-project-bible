"""Frontera cognitiva — qué recuerda, qué piensa, qué conversa, qué actúa y qué no sabe (M3, 2026-09-09).

**El defecto que cierra.** `_es_consulta_de_memoria` termina en `or _es_pregunta(texto)`, así que TODA
interrogativa que nadie reclamara antes caía en la ausencia de memoria. El CEO lo vio en producción:
*«¿quién es Jesús Cristo?»* y *«si tengo 1 caballo y lo vendo, ¿cuántos me quedan?»* respondían
«No tengo ningún recuerdo registrado sobre eso».

**La vía que NO se toma.** Estrechar `_es_consulta_de_memoria` se midió: `24/24 → 17/24`. Cerrada. Esto
es lo contrario — una superficie positiva y cerrada delante de la puerta— y por eso estas pruebas fijan
las dos mitades: que la cognición llega al modelo **y** que la memoria personal sigue protegida.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from aura_skeleton.core import intencion as I
from aura_skeleton.core.orchestrator import (
    _es_consulta_de_memoria,
    _pide_accion,
)

DATOS = pathlib.Path(__file__).resolve().parents[1] / "datos" / "bateria_memoria.json"


def _consultas() -> list[dict]:
    return json.loads(DATOS.read_text(encoding="utf-8"))["consultas"]


def _puerta_activa(texto: str) -> bool:
    """La condición EFECTIVA del orquestador tras la superficie cognitiva."""
    return _es_consulta_de_memoria(texto) and not I.es_cognicion_general(texto)


# ============================================== LA GARANTÍA, POR LOS DOS LADOS --


def test_las_24_negativas_siguen_protegidas():
    """**24/24.** Es la condición que no se negocia, y se mide sobre la puerta EFECTIVA, no sobre
    `_es_consulta_de_memoria` aislada: lo que importa es qué llega a contestar el núcleo."""
    negativas = [c["texto"] for c in _consultas() if c["esperado"] is None]
    fallos = [t for t in negativas if not _puerta_activa(t)]
    assert not fallos, f"{len(fallos)}/24 negativas desprotegidas: {fallos}"


def test_el_detector_de_memoria_NO_se_ha_tocado():
    """Caso de control de la vía: la garantía se conserva **sin estrechar el clasificador**.

    Si alguien «arreglara» la cognición relajando `_es_consulta_de_memoria`, esto caería — y ésa es
    exactamente la vía que midió `24/24 → 17/24`.
    """
    negativas = [c["texto"] for c in _consultas() if c["esperado"] is None]
    assert all(_es_consulta_de_memoria(t) for t in negativas), (
        "`_es_consulta_de_memoria` dejó de reconocer alguna negativa: la puerta se estrechó")


def test_ninguna_consulta_de_la_bateria_se_desvia_a_cognicion():
    """Disyunción completa: ni las 24 negativas ni las 53 positivas pueden irse por la vía cognitiva."""
    desviadas = [c["texto"] for c in _consultas() if I.es_cognicion_general(c["texto"])]
    assert not desviadas, f"la superficie cognitiva robó turnos a memoria: {desviadas}"


# ==================================================== LAS SEIS CATEGORÍAS --


@pytest.mark.parametrize("texto", [
    "¿Cómo me llamo?", "¿A qué me dedico?", "¿Cómo se llama mi hija?",
    "¿Cuál es el nombre de mi abuela?", "¿Qué marca de teléfono tengo?",
])
def test_MEMORIA_PERSONAL_sigue_yendo_al_nucleo(texto):
    assert _puerta_activa(texto), texto
    assert not I.es_cognicion_general(texto), texto


@pytest.mark.parametrize("texto", [
    "¿Quién es Jesús Cristo?", "¿Qué es la fotosíntesis?", "¿Por qué llueve?",
    "¿Cuál es la capital de Francia?", "¿Quién escribió el Quijote?",
])
def test_CONOCIMIENTO_GENERAL_llega_al_modelo(texto):
    assert I.es_cognicion_general(texto), texto
    assert not _puerta_activa(texto), texto


def test_MATEMATICA_la_resuelve_el_nucleo_sin_modelo():
    """Una suma no es una inferencia: la contesta el Core, y ni siquiera llega a la cognición."""
    from aura_skeleton.core.aritmetica import resolver
    assert resolver("cuanto es 2+2") is not None


@pytest.mark.parametrize("texto", [
    "si tengo 1 caballo y vendo 1, ¿cuántos me quedan?",
    "si todos los A son B y X es A, ¿qué podemos concluir?",
])
def test_RAZONAMIENTO_llega_al_modelo(texto):
    """El caso que el CEO vio fallar. «tengo» es aquí una PREMISA, no un hecho recordado."""
    assert I.es_cognicion_general(texto), texto


@pytest.mark.parametrize("texto", [
    "supongamos que mañana desaparece Internet, ¿qué consecuencias podría tener?",
    "¿qué pasaría si la gravedad fuera la mitad?",
])
def test_HIPOTESIS_llega_al_modelo_y_no_se_vuelve_un_hecho(texto):
    assert I.es_cognicion_general(texto), texto
    assert I.destino_de_memoria(texto) is None, "una hipótesis no puede almacenarse como hecho"


def test_CONVERSACION_no_queda_atrapada_por_la_memoria():
    assert not _puerta_activa("hoy tuve un día difícil")


def test_ACCION_sigue_su_ruta_y_no_la_roba_la_cognicion():
    texto = "enciende la luz del salón"
    assert _pide_accion(texto)
    assert not I.es_cognicion_general(texto)
    assert I.acto_de_habla(texto) == I.ORDEN


# ====================================== LA SUPOSICIÓN NO ES UN SALVOCONDUCTO --


@pytest.mark.parametrize("texto", [
    "Si hoy es martes, ¿a qué hora ceno?",
    "Supongamos que olvidé el dato, ¿qué idioma hablo?",
    "Si me lo preguntan, ¿qué postre preparo en Navidad?",
    "Si necesito llamar, ¿cuál es el teléfono de la oficina nueva?",
    "Supongamos que voy al taller, ¿cuál es el número de la factura?",
    "Si tengo 2 hijos, ¿cómo se llaman?",
    "Supongamos 3 cosas, ¿cuál es mi altura?",
    "¿Qué es lo que te conté ayer sobre el presupuesto?",
    "¿Qué es mi comida favorita?",
    "¿Quién es mi jefa?",
])
def test_una_pregunta_personal_DISFRAZADA_no_pasa(texto):
    """Los diez ataques con los que se acotó la regla, y que explican por qué es tan estrecha.

    «Si tengo 2 hijos, ¿cómo se llaman?» lleva cifra y es una suposición — y pide un NOMBRE. Una
    premisa numérica puede responder «cuántos quedan»; no puede responder «cómo se llaman». Por eso la
    suposición exige **cifra Y pregunta por cantidad**, no una de las dos.
    """
    assert not I.es_cognicion_general(texto), texto
    assert _puerta_activa(texto), texto


# ============================================= COSTE: EL CATÁLOGO NO VIAJA --


@pytest.mark.parametrize("texto", [
    "¿Quién es Jesús Cristo?", "¿Qué es la fotosíntesis?",
    "si tengo 1 caballo y vendo 1, ¿cuántos me quedan?",
    "¿qué opinas de esta idea?",
])
def test_una_consulta_COGNITIVA_no_carga_el_catalogo(texto):
    """Requisito de coste: el catálogo de acciones era el 71 % del tiempo de ingesta del turno.

    Se comprueba la condición exacta que el orquestador evalúa. `_pide_accion` es deliberadamente
    generoso —ante la duda manda el catálogo—, así que sin esta condición una pregunta cognitiva que
    contuviera un verbo de acción pagaría el catálogo entero sin necesitarlo.
    """
    assert I.es_cognicion_general(texto)
    modo = "accion" if (_pide_accion(texto) and not I.es_cognicion_general(texto)) else "cognitivo"
    assert modo == "cognitivo", texto


def test_una_ACCION_si_carga_el_catalogo():
    """Caso de control del anterior: si el catálogo dejara de viajar nunca, AURA no podría actuar."""
    texto = "enciende la luz del salón"
    modo = "accion" if (_pide_accion(texto) and not I.es_cognicion_general(texto)) else "cognitivo"
    assert modo == "accion"


def test_el_prompt_cognitivo_sigue_separado_del_de_accion():
    """La separación ya construida no se sustituye por una mega-prompt."""
    from aura_skeleton.modules.providers_real import _SYSTEM, _SYSTEM_COGNITIVO
    assert _SYSTEM_COGNITIVO != _SYSTEM
    assert len(_SYSTEM_COGNITIVO) < len(_SYSTEM), (
        "el prompt cognitivo dejó de ser el pequeño: ahí estaba la mejora de 441,2 s a 237,0 s")
    assert "NUNCA afirmes recordar" in _SYSTEM_COGNITIVO


# ================================================== AUTORIDAD Y NO AUTO-MEMORIA --


def test_la_respuesta_del_modelo_NO_se_convierte_en_memoria():
    """`_finalizar_turno` almacena lo que dijo el USUARIO, nunca lo que contestó el modelo."""
    import inspect

    from aura_skeleton.core.orchestrator import Orchestrator
    fuente = inspect.getsource(Orchestrator._finalizar_turno)
    escritura = fuente.split("memory.write")[1][:220]
    assert "say" not in escritura, "la respuesta del modelo no puede entrar en memoria"


def test_la_cognicion_no_concede_autoridad_de_ejecucion():
    """Clasificar un turno como cognitivo no lo ejecuta: `intencion` no conoce motor ni permisos."""
    import ast

    arbol = ast.parse(pathlib.Path(I.__file__).read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
            modulos.update(a.name for a in nodo.names)
    assert modulos <= {"__future__", "annotations", "re", "unicodedata", "dataclasses", "dataclass"}


def test_los_marcadores_de_evocacion_tienen_UN_solo_hogar():
    """No hay dos copias: el orquestador aliasa la lista de M-1. Dos copias divergen en una."""
    from aura_skeleton.core.orchestrator import _PATRONES_CONSULTA_MEMORIA
    assert _PATRONES_CONSULTA_MEMORIA is I.MARCADORES_DE_EVOCACION


def test_los_marcos_cognitivos_son_una_lista_CERRADA():
    """Fail-closed: lo que no está declarado sigue el camino de hoy, no el cognitivo."""
    assert not I.es_cognicion_general("¿Cuál es el código de mi alarma?")
    assert not I.es_cognicion_general("¿Dónde guardé las escrituras de la casa?")


def test_solo_una_PREGUNTA_entra_por_la_via_cognitiva():
    """El arnés exigió esta prueba: `COG-M5` sobrevivía sin ella.

    Sin el filtro del acto, una AFIRMACIÓN que contuviera un marco conceptual se iría al modelo por la
    ruta cognitiva. «Por qué llueve me interesa mucho» no es una pregunta: es una afirmación, y su
    sitio es el camino de hoy.
    """
    # El caso tiene que DISCRIMINAR: una afirmacion con marco conceptual Y contenido `INCIERTO`.
    # «Por que llueve me interesa» no sirve -el «me» la hace `HECHO_USUARIO`, asi que el eje 2 ya la
    # rechaza y el filtro del acto quedaria sin probar-. Esta pasa las dos condiciones menos el acto.
    afirmacion = "Te cuento que es la fotosintesis"
    c = I.clasificar(afirmacion)
    assert c.acto == I.AFIRMACION and c.contenido == I.INCIERTO, f"guarda de cordura: {c}"
    assert not I.es_cognicion_general(afirmacion), "una afirmacion no entra por la via cognitiva"


def test_el_orquestador_exime_del_catalogo_a_la_consulta_cognitiva():
    """`COG-M6` sobrevivía porque la prueba de coste recalculaba el modo por su cuenta.

    La condición tiene que comprobarse **donde vive**, en el orquestador: si alguien la revierte, la
    consulta cognitiva vuelve a pagar los ~398 tokens del catálogo y ninguna aserción sobre una copia
    local de la fórmula lo notaría.
    """
    import inspect

    from aura_skeleton.core.orchestrator import Orchestrator
    fuente = inspect.getsource(Orchestrator.on_turn)
    assert 'modo = "accion" if (_pide_accion(text) and not cognicion_general) else "cognitivo"' in fuente, (
        "el orquestador dejó de eximir del catálogo a la consulta cognitiva")
