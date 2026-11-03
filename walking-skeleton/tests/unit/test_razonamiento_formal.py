"""`resolver_formal` — razonamiento formal en lenguaje natural (D-FC-4 = A, CEO 2026-09-13).

## El defecto que esta capacidad cierra

    tu>   si tengo 4 manzanas y me como una, cuantas manzanas me quedan?
    AURA> [248 s, qwen2.5:0.5b] 0

No hay superficie que reconozca la frase como un problema aritmético expresado en lenguaje
natural, así que cae en el LLM, que tarda 248 s y contesta mal (3 es la respuesta correcta). La
decisión del CEO es tajante: el razonamiento formal pertenece al Core cuando se extrae con
CERTEZA; si está infradeterminado, el Core pregunta — nunca el LLM como calculadora.

## Qué cubre cada bloque de pruebas

1. Expresiones puras: idéntico resultado que `resolver` (requisito 1).
2. Problemas verbales pequeños, con caso de control por cada garantía (requisito 2).
3. ACLARACIÓN cuando la forma es cuantitativa pero infradeterminada (requisito 3).
4. Sin colisiones con las 24 negativas de memoria personal, ni con órdenes con número, ni con
   preguntas personales sin premisa (requisito 4).
5. Límites heredados de `aritmetica` (requisito 5): MAX_CARACTERES, MAX_DIGITOS.

Cada aserción trae su caso de control: qué tendría que romperse para que la prueba fallara si la
garantía dejara de cumplirse.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from aura_skeleton.core import aritmetica as ar
from aura_skeleton.core.aritmetica import resolver_formal
from aura_skeleton.core.estatus import Estatus

DATOS_MEMORIA = pathlib.Path(__file__).resolve().parents[1] / "datos" / "bateria_memoria.json"


# ============================================================ 1 · EXPRESIONES PURAS --


@pytest.mark.parametrize(
    "frase",
    [
        "cuanto es 1+1",
        "1+1",
        "100 - 200",
        "20 - 3",
        "7 * 8",
        "12 / 4",
        "cuanto es 1/0",
    ],
)
def test_una_expresion_PURA_da_la_MISMA_respuesta_que_resolver(frase):
    """Requisito 1, literal: `resolver_formal` no puede divergir un solo carácter de `resolver`.

    Caso de control: si `resolver_formal` recalculara por su cuenta en vez de delegar, un cambio
    futuro en `resolver` (p. ej. el formato de la división por cero) dejaría a las dos funciones
    en desacuerdo sin que ninguna prueba de este fichero lo notara — por eso se compara contra la
    llamada real, no contra un texto fijado a mano.
    """
    esperado = ar.resolver(frase)
    assert esperado is not None, f"{frase!r} debería resolverla `resolver`: revisa el caso de prueba"
    assert resolver_formal(frase) == (Estatus.HECHO.value, esperado)


def test_100_menos_200_da_negativo():
    """El ejemplo literal de la especificación: la resta puede dar un entero negativo y sigue
    siendo un HECHO — no hay «consumo» que lo prohíba, eso solo aplica a los problemas verbales."""
    assert resolver_formal("100 - 200") == (Estatus.HECHO.value, "-100.")


def test_CONTROL_una_expresion_invalida_no_pasa_por_esta_via():
    """Caso de control del bloque 1: una expresión que `resolver` rechaza no puede colarse como
    HECHO por esta vía — si lo hiciera, `resolver_formal` estaría inventando un resultado."""
    assert ar.resolver("cuanto es 5 +") is None
    assert resolver_formal("cuanto es 5 +") is None


# ================================================== 2 · PROBLEMAS VERBALES → HECHO --


@pytest.mark.parametrize(
    ("frase", "resultado"),
    [
        ("si tengo 4 manzanas y me como una, cuantas manzanas me quedan?", 3),
        ("tengo 4 manzanas y como una, cuantas manzanas me quedan?", 3),
        ("tengo 3 galletas y pierdo 1, cuantas galletas me quedan?", 2),
        ("tengo 10 caramelos y regalo 2, cuantos caramelos me quedan?", 8),
        ("tengo 5 euros y doy 2, cuantos euros me quedan?", 3),
        ("tengo 20 euros y gasto 5, cuantos euros me quedan?", 15),
        ("Si tengo 1 caballo y vendo 1, ¿cuántos me quedan?", 0),
        ("tengo 4 boligrafos y uso 1, cuantos boligrafos me quedan?", 3),
        ("tengo 6 platos y rompo 2, cuantos platos me quedan?", 4),
        ("tengo 2 manzanas y compro 3, cuantas manzanas me quedan?", 5),
        ("tengo 1 manzana y me dan 2, cuantas manzanas me quedan?", 3),
        ("tengo 1 manzana y me regalan 4, cuantas manzanas me quedan?", 5),
        ("tengo 2 monedas y encuentro 3, cuantas monedas me quedan?", 5),
        ("tengo 3 partidas y gano 2, cuantas partidas me quedan?", 5),
        ("tengo 1 carta y recibo 2, cuantas cartas me quedan?", 3),
        ("tengo 2 puntos y consigo 3, cuantos puntos me quedan?", 5),
        # numerales en palabras, no solo cifras
        ("tengo dos manzanas y como una, cuantas manzanas me quedan?", 1),
        ("tengo una manzana y me dan tres, cuantas manzanas me quedan?", 4),
        ("Si tengo un caballo y vendo uno, ¿cuántos me quedan?", 0),
    ],
)
def test_un_problema_verbal_ESTRUCTURADO_se_resuelve_con_certeza(frase, resultado):
    estatus, respuesta = resolver_formal(frase)
    assert estatus == Estatus.HECHO.value, frase
    assert respuesta.startswith(f"Te quedan {resultado} "), f"{frase!r} -> {respuesta!r}"


def test_el_sustantivo_se_conserva_TAL_COMO_lo_escribio_el_usuario():
    """ADR-0017: no se normaliza el objeto. Caso de control: si `resolver_formal` devolviera el
    sustantivo en minúsculas o sin tilde, esta prueba lo detectaría — el texto de entrada lleva
    mayúscula y la comprobación exige que sobreviva intacta."""
    estatus, respuesta = resolver_formal("tengo 2 Manzanas y como 1, cuantas manzanas me quedan?")
    assert estatus == Estatus.HECHO.value
    assert "Manzanas" in respuesta, respuesta


def test_CONTROL_sin_la_clausula_de_operacion_no_hay_HECHO_verbal():
    """Caso de control del bloque 2: quitar la operación dejando premisa y pregunta de cantidad
    intactas no puede seguir dando HECHO -si lo hiciera, la prueba de arriba no estaría probando
    la clausula de operación, sino solo la premisa-."""
    estatus, _ = resolver_formal("tengo 4 manzanas, cuantas manzanas tengo?")
    assert estatus == Estatus.ACLARACION.value


# ============================================== 3 · ACLARACIÓN, NUNCA ADIVINAR --


def test_MAS_DE_UNA_operacion_pide_aclaracion():
    estatus, pregunta = resolver_formal("tengo 5 manzanas y me como una y compro dos, cuantas manzanas me quedan?")
    assert estatus == Estatus.ACLARACION.value
    assert "manzana" not in pregunta.lower(), "la aclaracion no debe afirmar datos del turno"


def test_CONTROL_la_MISMA_frase_con_UNA_sola_operacion_SI_resuelve():
    """Caso de control del anterior: quitar la segunda operación basta para volver a HECHO — si
    la prueba de arriba fallara por otro motivo (verbo mal reconocido, por ejemplo), esta lo
    revelaría, porque entonces tampoco resolvería con una sola operación."""
    estatus, _ = resolver_formal("tengo 5 manzanas y me como una, cuantas manzanas me quedan?")
    assert estatus == Estatus.HECHO.value


def test_un_VERBO_DESCONOCIDO_pide_aclaracion():
    estatus, _ = resolver_formal("tengo 5 manzanas y presto una, cuantas manzanas me quedan?")
    assert estatus == Estatus.ACLARACION.value


def test_CONTROL_el_mismo_verbo_SUSTITUIDO_por_uno_conocido_SI_resuelve():
    """Caso de control: `presto` no es el problema de la frase en sí -la premisa y la pregunta
    están bien formadas-, es específicamente que el verbo no está en la lista cerrada."""
    estatus, _ = resolver_formal("tengo 5 manzanas y regalo una, cuantas manzanas me quedan?")
    assert estatus == Estatus.HECHO.value


def test_PRECIO_AMBIGUO_pide_aclaracion():
    """El ejemplo literal de la especificación: precio unitario vs total, indistinguible."""
    estatus, pregunta = resolver_formal("tengo 100 y compro 2 peras que cuestan 200 cuanto me queda")
    assert estatus == Estatus.ACLARACION.value
    assert "100" not in pregunta and "200" not in pregunta, "no debe repetir las cifras del turno"


def test_CONTROL_la_misma_frase_SIN_precio_SI_resuelve():
    """Caso de control: lo que dispara la aclaración es la palabra de precio, no la estructura
    general de la frase con `compro`."""
    estatus, _ = resolver_formal("tengo 100 manzanas y compro 2, cuantas manzanas me quedan?")
    assert estatus == Estatus.HECHO.value


def test_RESULTADO_NEGATIVO_en_un_consumo_pide_aclaracion():
    estatus, _ = resolver_formal("tengo 2 manzanas y me como 5, cuantas manzanas me quedan?")
    assert estatus == Estatus.ACLARACION.value


def test_CONTROL_una_cantidad_suficiente_SI_resuelve():
    """Caso de control: el problema no es el verbo `como`, es que 5 > 2. Con una cantidad que
    alcanza, la misma frase resuelve."""
    estatus, respuesta = resolver_formal("tengo 5 manzanas y como 2, cuantas manzanas me quedan?")
    assert estatus == Estatus.HECHO.value
    assert "3" in respuesta


def test_la_aclaracion_SUGIERE_reformular_como_operacion():
    _, pregunta = resolver_formal("tengo 100 y compro 2 peras que cuestan 200 cuanto me queda")
    assert "operación" in pregunta.lower()
    assert "4 - 1" in pregunta or "operación" in pregunta.lower()


# ------------------------------- la rama numérica de `intencion` queda cubierta --
#
# HUECO MEDIDO por el arquitecto tras la integración (2026-09-13): la primera versión exigía que
# la pregunta de cantidad terminara en «quedan/queda/tengo/tendre/hay». La rama numérica de
# `es_cognicion_general` no exige eso — solo que «cuanto/cuantos/cuantas/cuanta» aparezca en
# CUALQUIER posición junto a una suposición y un dígito —, así que frases como «si un coche cuesta
# 2000 euros al mes, cuanto cuesta en un año?» activaban esa rama pero `resolver_formal` daba
# `None`: el LLM seguía de calculadora. Esta sección fija la propiedad — no una lista de ejemplos
# sueltos — para que un hueco equivalente no vuelva a colarse sin que ninguna prueba lo note.


@pytest.mark.parametrize(
    "frase",
    [
        "si tengo 1 caballo y vendo 1, ¿cuántos me quedan?",
        "Si tengo 2 caballos y vendo uno, ¿cuántos me quedan?",
    ],
)
def test_lo_que_ANTES_caia_en_la_rama_numerica_del_LLM_ahora_nunca_da_None(frase):
    """`intencion.es_cognicion_general` deja pasar al LLM «suposición + cifra + pide cantidad».
    Como `resolver_formal` se evalúa ANTES en la cascada, todo lo que esa rama acepta tiene que
    salir de aquí como HECHO o ACLARACIÓN — nunca `None`, o el LLM seguiría de calculadora.

    Ancla de mutación `FC-M11`: se conserva por nombre exacto aunque la propiedad general — para
    TODA la rama numérica, no solo estos dos casos — vive ahora en
    `test_TODO_lo_que_activa_la_rama_numerica_nunca_da_None`, más abajo.
    """
    from aura_skeleton.core.intencion import es_cognicion_general

    assert es_cognicion_general(frase), f"{frase!r} ya no activa la rama numérica: revisa el caso"
    assert resolver_formal(frase) is not None, f"{frase!r} volvería a caer en el LLM"


def _activa_rama_numerica(texto: str) -> bool:
    """Réplica LITERAL de la condición de `intencion.es_cognicion_general` para su rama numérica,
    construida con las MISMAS constantes que usa `resolver_formal` (importadas, no copiadas a
    mano) — así la réplica no puede divergir en silencio de lo que de verdad decide esa rama."""
    from aura_skeleton.core.intencion import _SUPOSICION_COGNITIVA as _S
    from aura_skeleton.core.intencion import normalizar

    n = normalizar(texto)
    return (
        any(p in n for p in _S)
        and any(ch.isdigit() for ch in texto)
        and any(q in n for q in ar._PIDE_CANTIDAD_COGNITIVA)
    )


#: Batería amplia: los cuatro huecos reportados por el arquitecto, los dos posesivos exigidos, los
#: casos ya cubiertos antes de esta ronda, y ≥15 variaciones nuevas — verbos reconocidos y
#: desconocidos, con y sin premisa `tengo`, con y sin precio, cifra en dígitos y en palabras.
_BATERIA_RAMA_NUMERICA = [
    # los cuatro huecos reportados, literales
    "si un coche cuesta 2000 euros al mes, cuanto cuesta en un año?",
    "si un tren va a 80 km por hora, cuantos km recorre en 3 horas?",
    "si compro 3 panes a 2 euros cada uno, cuanto pago?",
    "si todos los alumnos son 30 y faltan 4, cuantos vinieron?",
    # ya daba aclaración antes de esta ronda: no puede regresar a None
    "si cada caja tiene 12 huevos, cuantos huevos hay en 5 cajas?",
    # casos ya cubiertos, se conservan como regresión
    "si tengo 1 caballo y vendo 1, ¿cuántos me quedan?",
    "Si tengo 2 caballos y vendo uno, ¿cuántos me quedan?",
    # ≥15 variaciones nuevas
    "si tengo 5 hijos y adopto 2, cuantos hijos tengo?",
    "supongamos que tengo 10 libros y regalo 3, cuantos libros me quedan?",
    "imagina que tengo 8 peces y se mueren 2, cuantos peces me quedan?",
    "si fuera cierto que tengo 6 gatos y regalo 1, cuantos gatos tendria?",
    "si un litro de leche cuesta 3 euros, cuantos litros puedo comprar con 300 euros?",
    "si tengo 2 perros y compro 1 mas, cuantos perros tengo ahora?",
    "supongamos que tengo 4 naranjas y como 2, cuantas naranjas me quedan?",
    "si tengo 9 lapices y pierdo 3, cuantos lapices me quedan?",
    "si todos mis ahorros son 500 y gasto 100, cuanto me queda?",
    "si tengo 7 canicas y gano 3 mas, cuantas canicas tengo?",
    "si tengo 3 pasteles y vendo 5, cuantos pasteles me quedan?",
    "supon que tengo 2 sillas y rompo 1, cuantas sillas me quedan?",
    "si tengo 100 manzanas y compro 20, cuantas manzanas tengo en total?",
    "si cada trabajador cobra 1500, cuanto cobran 4 trabajadores?",
    "si tengo 1 gato y encuentro 2 mas, cuantos gatos tengo?",
    # posesivos: exigidos explícitamente, nunca pueden fabricar el dato personal
    "si mi hija tiene 7 años, cuantos cumplira el proximo verano?",
    "si mi jefe cobra 2000 al mes, cuanto gana en un año?",
]


def test_CONTROL_la_bateria_SI_activa_la_rama_numerica_de_verdad():
    """Caso de control de toda la sección: si `_activa_rama_numerica` o la propia
    `es_cognicion_general` no reconociera ninguna frase de la batería, la prueba de propiedad de
    abajo pasaría trivialmente sin comprobar nada real."""
    from aura_skeleton.core.intencion import es_cognicion_general

    for frase in _BATERIA_RAMA_NUMERICA:
        assert _activa_rama_numerica(frase), f"la réplica no activa la rama numérica: {frase!r}"
        assert es_cognicion_general(frase), f"{frase!r} ya no activa la rama numérica real: revisa"


@pytest.mark.parametrize("frase", _BATERIA_RAMA_NUMERICA)
def test_TODO_lo_que_activa_la_rama_numerica_nunca_da_None(frase):
    """La propiedad exigida: para toda frase que activa la rama numérica de
    `es_cognicion_general`, `resolver_formal` nunca es `None` — sale como HECHO o ACLARACIÓN, y en
    ningún caso el turno vuelve a caer en el LLM como calculadora."""
    assert resolver_formal(frase) is not None, f"{frase!r} volvería a caer en el LLM"


def test_CONTROL_una_pregunta_cognitiva_NO_numerica_sigue_dando_None():
    """Caso de control exigido explícitamente: una pregunta cognitiva que NO pasa por la rama
    numérica (no hay dígito) no la reclama `resolver_formal` — sigue su camino de siempre."""
    from aura_skeleton.core.intencion import es_cognicion_general

    frase = "por que llueve?"
    assert es_cognicion_general(frase), "sigue siendo cognición general, solo que no numérica"
    assert not _activa_rama_numerica(frase), "no debe activar la rama numérica: no hay dígito"
    assert resolver_formal(frase) is None


def test_CONTROL_una_suposicion_SIN_cifra_no_la_reclama_esta_capacidad():
    """Caso de control: `resolver_formal` no reclama TODA suposición, solo las que tienen forma
    cuantitativa. «si todos los A son B» sigue su camino de siempre (cognición general)."""
    frase = "si todos los A son B y X es A, que podemos concluir?"
    assert resolver_formal(frase) is None


@pytest.mark.parametrize(
    "frase",
    [
        "si mi hija tiene 7 años, cuantos cumplira el proximo verano?",
        "si mi jefe cobra 2000 al mes, cuanto gana en un año?",
    ],
)
def test_un_posesivo_con_cifra_pide_aclaracion_y_NUNCA_afirma_el_dato_personal(frase):
    """Requisito explícito: una suposición con posesivo sobre un tercero (hija, jefe) no puede
    resolverse con certeza — no hay `tengo N objeto` del que partir — y la pregunta de aclaración
    no puede repetir ni insinuar ningún dato personal del turno."""
    estatus, pregunta = resolver_formal(frase)
    assert estatus == Estatus.ACLARACION.value
    for dato in ("hija", "jefe", "7", "2000", "año"):
        assert dato not in pregunta.lower(), f"la aclaración afirma un dato del turno: {dato!r}"


# ===================================== 4 · SIN COLISIONES CON MEMORIA PERSONAL --


def _negativas_de_memoria() -> list[str]:
    datos = json.loads(DATOS_MEMORIA.read_text(encoding="utf-8"))
    negativas = [c["texto"] for c in datos["consultas"] if c["esperado"] is None]
    assert len(negativas) == 24, "la batería cambió: vuelve a medir antes de decidir"
    return negativas


def test_las_24_NEGATIVAS_de_memoria_personal_no_las_reclama_el_razonamiento_formal():
    """Ninguna de las 24 consultas protegidas de `tests/datos/bateria_memoria.json` (importadas,
    no reescritas a mano) puede convertirse en HECHO o ACLARACIÓN aquí: `resolver_formal` no
    conoce hechos personales, así que reclamar una de estas sería fabricar autoridad sobre datos
    que no tiene."""
    negativas = _negativas_de_memoria()
    colisiones = [(t, resolver_formal(t)) for t in negativas if resolver_formal(t) is not None]
    assert not colisiones, f"colisión con memoria personal: {colisiones}"


def test_CONTROL_la_bateria_SI_contiene_casos_con_tengo_y_con_cifras():
    """Caso de control del anterior: si la batería no tuviera ningún caso parecido a la forma que
    reconoce `resolver_formal`, la prueba de arriba pasaría trivialmente sin probar nada. Confirma
    que al menos una negativa lleva un verbo en primera persona parecido a `tengo` o una cifra,
    para que «0 colisiones» sea una medición real y no una ausencia de solapamiento."""
    negativas = _negativas_de_memoria()
    assert any("tengo" in t.lower() for t in negativas) or any(any(ch.isdigit() for ch in t) for t in negativas), (
        "la bateria no ejercita ningun solapamiento real con la gramatica de resolver_formal"
    )


@pytest.mark.parametrize(
    "frase",
    [
        "borra 2 archivos",
        "elimina 3 archivos temporales",
        "abre los 2 archivos que descargue",
    ],
)
def test_ordenes_con_NUMERO_no_las_reclama_el_razonamiento_formal(frase):
    """Una orden con cifra («borra 2 archivos») no es un problema de razonamiento: no hay premisa
    de posesión, y una orden no pide una cantidad."""
    assert resolver_formal(frase) is None


def test_pregunta_de_cantidad_SIN_premisa_no_la_reclama_el_razonamiento_formal():
    """`cuantos hijos tengo?` lleva el verbo `tengo` pero SIN una cifra que lo acompañe: no hay
    dato del que partir, así que no es un problema de razonamiento formal — es memoria personal."""
    assert resolver_formal("cuantos hijos tengo?") is None


@pytest.mark.parametrize(
    "frase",
    [
        "¿Cuántos años tiene mi gato?",
        "¿Cuál es mi altura en centímetros?",
        "¿A qué hora ceno normalmente?",
    ],
)
def test_preguntas_personales_de_cantidad_SIN_cifra_no_las_reclama(frase):
    """Preguntan una cantidad y hablan del usuario, pero no traen ninguna cifra de la que partir:
    sin cifra no hay problema formal que resolver, así que siguen su camino de memoria."""
    assert resolver_formal(frase) is None


# ============================================================ 5 · LÍMITES HEREDADOS --


def test_MAX_CARACTERES_se_respeta_en_la_via_verbal():
    """Caso de control: justo por debajo del límite sí se evalúa -devuelve `None` porque el
    relleno no es una frase reconocible-, así que el límite no está cortando de más."""
    frase_larga = "tengo 4 manzanas y como una, cuantas manzanas me quedan? " + "x" * (ar.MAX_CARACTERES + 1)
    assert resolver_formal(frase_larga) is None
    assert len(frase_larga) > ar.MAX_CARACTERES


def test_MAX_DIGITOS_se_respeta_en_la_cifra_de_la_premisa():
    """Una cifra que excede `MAX_DIGITOS` no se convierte con confianza: pide aclaración en vez
    de intentar aritmética sobre un número que la propia herramienta declara fuera de sus cotas."""
    cifra_larga = "9" * (ar.MAX_DIGITOS + 1)
    estatus, _ = resolver_formal(f"tengo {cifra_larga} manzanas y como 1, cuantas manzanas me quedan?")
    assert estatus == Estatus.ACLARACION.value


def test_CONTROL_una_cifra_justo_por_debajo_del_limite_SI_resuelve():
    cifra_al_limite = "9" * ar.MAX_DIGITOS
    estatus, respuesta = resolver_formal(f"tengo {cifra_al_limite} manzanas y como 1, cuantas manzanas me quedan?")
    assert estatus == Estatus.HECHO.value
    assert str(int(cifra_al_limite) - 1) in respuesta


# ==================================================== ENTRADA VACÍA O TRIVIAL --


@pytest.mark.parametrize("frase", ["", "hola", "gracias por todo", "¿qué tal?"])
def test_texto_no_cuantitativo_no_lo_reclama_el_razonamiento_formal(frase):
    assert resolver_formal(frase) is None


def test_los_literales_de_estatus_coinciden_con_el_contrato_del_arquitecto():
    """`resolver_formal` no inventa sus propios literales: usa `Estatus.HECHO.value` y
    `Estatus.ACLARACION.value` del contrato de `core.estatus`, que este fichero no modifica."""
    hecho, _ = resolver_formal("1+1")
    assert hecho == "hecho" == Estatus.HECHO.value
    aclaracion, _ = resolver_formal("tengo 5 manzanas y presto una, cuantas manzanas me quedan?")
    assert aclaracion == "aclaracion" == Estatus.ACLARACION.value
