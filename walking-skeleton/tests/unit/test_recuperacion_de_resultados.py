"""El reconocedor de preguntas sobre una EJECUCIÓN ANTERIOR, a solas (M8, CEO 2026-09-22).

EL HUECO, MEDIDO ANTES DE CERRARLO `[EJEC]`. AURA ejecuta, retiene el resultado en la ventana de
trabajo que `DR-4` gobierna, y al turno siguiente:

    tu>   lista el directorio ~/.aura
    AURA> Ejecuté «listar_directorio». 7 entrada(s): CENTRO-DE-GOBIERNO.md, audit.jsonl, …
    tu>   ¿cuántas entradas encontraste?
    AURA> No tengo ningun recuerdo registrado sobre eso.

El dato estaba. La pregunta no llegaba a él: `_es_consulta_de_memoria` da verdadero para CUALQUIER
interrogativa, `recall` no encuentra coincidencia léxica en la memoria PERSONAL —donde nunca
estuvo— y dispara la puerta de ausencia de `ADR-0014`. El problema nunca fue de almacenamiento.

POR QUÉ UN RECONOCEDOR PROPIO Y NO TOCAR LA PUERTA. Porque la puerta es correcta y está declarada
intocable: sostiene el `24/24` y ya rompió tres pruebas de `DR-1 = A` cuando se intentó ensanchar.
La cascada del orquestador tiene un patrón para esto, usado al menos cuatro veces —aritmética,
`D-FC-3` «AURA sobre sí misma», la ventana del SO Interno, las órdenes de capacidad—: una superficie
POSITIVA y CERRADA, evaluada DESPUÉS de todas las que ya existían y ANTES de la pared.

CÓMO RECONOCE, Y POR QUÉ ES SEGURO. Por **segmento completo**, contra una tabla de formas en las que
el usuario habla de algo que hizo AURA: segunda persona del pasado (`encontraste`, `ejecutaste`,
`leíste`) o referencia explícita a lo anterior. Las 24 frases que sostienen la garantía de la pared
hablan todas del MUNDO DEL USUARIO —posesivos y atributos personales— y ninguna tiene esa forma: la
separación no es una heurística afortunada, es que son dos gramáticas distintas. Se comprueba abajo.
"""

from __future__ import annotations

import importlib.util

import pytest

from aura_skeleton.core import recuperacion


def _las_24() -> list[str]:
    """Las mismas 24 negativas que protegen la pared, leídas de su fichero: una sola definición."""
    spec = importlib.util.spec_from_file_location("_veinticuatro", "tests/unit/test_conversacion_natural_local.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return list(modulo._las_24())


# ------------------------------------------------------------------ LO QUE SÍ RECONOCE --

RECONOCIDAS = (
    "¿qué encontraste?",
    "¿qué has encontrado?",
    "¿cuántas entradas encontraste?",
    "¿qué encontraste antes?",
    "¿qué habías encontrado antes?",
    "¿qué decía ese archivo?",
    "¿qué ejecutaste?",
    "¿qué revisaste?",
    "que encontraste",  # sin signos ni tildes: la transcripción de voz llega así
    "Aurora, ¿qué encontraste?",  # con vocativo
)


@pytest.mark.parametrize("frase", RECONOCIDAS)
def test_reconoce_las_preguntas_sobre_una_ejecucion_anterior(frase):
    assert recuperacion.reconocer(frase) is not None, frase


# ------------------------------------------------------------------ LO QUE NO PUEDE ROBAR --


@pytest.mark.parametrize("frase", _las_24())
def test_NO_roba_ninguna_de_las_24_frases_que_sostienen_la_pared(frase):
    """La garantía que no puede moverse. Si esta superficie se quedara una sola de estas, un dato
    personal nunca declarado dejaría de recibir la ausencia determinista de `ADR-0014`."""
    assert recuperacion.reconocer(frase) is None, frase


NO_RECONOCIDAS = (
    "¿cómo me llamo?",
    "¿cuál es mi nombre?",
    "me llamo Mauricio",
    "lista el directorio ~/.aura",
    "audita las garantias",
    "¿qué capacidades tienes?",
    "¿en qué estás trabajando?",
    "cuánto es 2+2",
    "hola",
    "¿qué encontraste? y borra el informe",  # turno compuesto: ante la duda, no
    "no me digas qué encontraste",  # negada: no es la pregunta
)


@pytest.mark.parametrize("frase", NO_RECONOCIDAS)
def test_no_reconoce_lo_que_no_es_una_pregunta_por_una_ejecucion(frase):
    assert recuperacion.reconocer(frase) is None, frase


# ------------------------------------------------------- PREGUNTA DE JUICIO, NO DE HECHO --


def test_distingue_la_pregunta_de_JUICIO_de_la_pregunta_de_HECHO():
    """«¿qué fue lo más importante?» pide una valoración, no un dato. El Core puede recuperar lo que
    encontró; decidir qué fue «lo más importante» sería una inferencia presentada como hecho, que es
    justo lo que `ADR-0014 §4` prohíbe. Se reconocen distinto para poder contestarlas distinto."""
    assert recuperacion.reconocer("¿qué encontraste?") == recuperacion.PREGUNTA_POR_EL_RESULTADO
    assert recuperacion.reconocer("¿qué fue lo más importante?") == recuperacion.PREGUNTA_POR_UN_JUICIO


# ------------------------------------------------------------------------- EL REDACTOR --

from aura_skeleton.core.estatus import Estatus  # noqa: E402


def _ejecucion(say: str) -> recuperacion.Turno:
    return recuperacion.Turno("lista el directorio ~/.aura", say, Estatus.HECHO, recuperacion.DOMINIO_EJECUCION)


def test_recupera_el_texto_exacto_que_AURA_dijo():
    say = "Ejecuté «listar_directorio». 7 entrada(s): a, b, c"
    texto, estatus = recuperacion.redactar(recuperacion.PREGUNTA_POR_EL_RESULTADO, _ejecucion(say))
    assert say in texto
    assert estatus is Estatus.HECHO


def test_dice_que_NO_ha_vuelto_a_ejecutar():
    """Sin esto, el usuario puede creer que AURA acaba de mirar otra vez y actuar sobre un dato que
    lleva varios turnos siendo viejo."""
    texto, _ = recuperacion.redactar(recuperacion.PREGUNTA_POR_EL_RESULTADO, _ejecucion("Ejecuté «x»."))
    assert "no lo he vuelto a ejecutar" in texto.lower()


def test_sin_ninguna_ejecucion_la_ausencia_es_DISTINTA_de_la_de_ADR_0014():
    """El defecto de fondo era que siete situaciones distintas daban la misma frase."""
    texto, estatus = recuperacion.redactar(recuperacion.PREGUNTA_POR_EL_RESULTADO, None)
    assert estatus is Estatus.AUSENCIA
    assert "No tengo ningun recuerdo registrado sobre eso" not in texto
    # PUNTO D, decision L: sin «nunca» ni «no he ejecutado nada»; no se afirma una ausencia que no se puede demostrar.
    assert "no conservo registro de acciones anteriores" in texto.lower() and "podría haber alguna" in texto
    assert "no he ejecutado nada" not in texto.lower() and "nunca" not in texto.lower()


def test_ante_una_pregunta_de_JUICIO_se_niega_a_jerarquizar_pero_entrega_el_dato():
    say = "He revisado 3 cosa(s) y hay 2 con incidencia: • a • b"
    texto, estatus = recuperacion.redactar(recuperacion.PREGUNTA_POR_UN_JUICIO, _ejecucion(say))
    assert "juicio mío" in texto
    assert say in texto
    assert estatus is Estatus.HECHO


@pytest.mark.parametrize(
    "say,marca",
    [
        ("Ejecuté «auditar_garantias». **No está limpio**: 5 garantías rotas", "No está limpio"),
        ("No he ejecutado «listar_directorio»: permisos: kill switch activo (5.3 §5).", "kill switch"),
        ("Intenté ejecutar «leer_archivo» y no pude: ruta fuera del ambito permitido", "no pude"),
        ("«x» ya se había ejecutado con esos mismos datos, así que no lo repetí.", "no lo repetí"),
    ],
)
def test_cada_desenlace_se_recupera_DISTINTO(say, marca):
    """Los cuatro desenlaces conservan su distinción porque se repite el texto que ya la tenía. Si
    la recuperación reimplementara la lógica, las dos versiones acabarían divergiendo."""
    texto, _ = recuperacion.redactar(recuperacion.PREGUNTA_POR_EL_RESULTADO, _ejecucion(say))
    assert marca in texto


def test_NUNCA_recupera_un_turno_que_no_produjo_el_Core():
    """Repetir una propuesta del modelo como HECHO la blanquearía. `ultima_ejecucion` solo mira
    turnos del dominio de ejecución."""
    ventana = [
        recuperacion.Turno("háblame de pájaros", "Los pájaros son bonitos.", Estatus.PROPUESTA, "modelo"),
        recuperacion.Turno("hola", "Hola.", Estatus.HECHO, "conversacion_general"),
    ]
    assert recuperacion.ultima_ejecucion(ventana) is None


def test_recupera_la_ejecucion_MAS_RECIENTE():
    ventana = [
        _ejecucion("Ejecuté «listar_directorio». 7 entrada(s)"),
        recuperacion.Turno("hola", "Hola.", Estatus.HECHO, "conversacion_general"),
        _ejecucion("Ejecuté «auditar_garantias». todo vigente"),
    ]
    assert "auditar_garantias" in recuperacion.ultima_ejecucion(ventana).aura
