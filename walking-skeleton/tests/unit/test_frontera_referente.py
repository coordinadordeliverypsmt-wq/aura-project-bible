"""Frontera cognitiva · referente, dominios sensibles e hipótesis de consecuencia (D-FC, 2026-09-13).

Tres casos medidos en producción la motivan:

- **T5** «si meto la mano en agua caliente que me pasa?» caía en la pared de `ADR-0014`.
- **T7** «quien es Jesus Cristo?» llegaba al modelo, y el modelo fabricó una falsedad grave.
- **T8** «que desarrollas en este momento?» caía en la pared: interroga a AURA, no a la memoria.

La garantía que NO se degrada es 24/24: ninguna consulta personal sin recuerdo puede salir hacia el
modelo. Por eso la batería de medición de T5 vive aquí como prueba: negativas, ataques existentes,
ataques nuevos contra la forma nueva y positivas. 0 colisiones y 0 fugas, o la ampliación no se activa.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from aura_skeleton.core import intencion as I
from aura_skeleton.core.orchestrator import (
    _PAT_MODELO_OLVIDA,
    _PAT_MODELO_PORQUE,
    _PAT_MODELO_REFUTA,
    _PAT_MODELO_VER,
    _es_consulta_de_memoria,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]
BATERIA_MEMORIA = RAIZ / "datos" / "bateria_memoria.json"
BATERIA_INTENCION = RAIZ.parents[1] / "milestones" / "m3-entry" / "bateria-intencion.json"

T5 = "si meto la mano en agua caliente que me pasa?"
T7 = "quien es Jesus Cristo?"
T8 = "que desarrollas en este momento?"


def _memoria() -> list[dict]:
    return json.loads(BATERIA_MEMORIA.read_text(encoding="utf-8"))["consultas"]


def _negativas() -> list[str]:
    textos = [c["texto"] for c in _memoria() if c["esperado"] is None]
    assert len(textos) == 24, "la bateria cambio: vuelve a medir antes de decidir"
    return textos


def _puerta_activa(texto: str) -> bool:
    """La condición EFECTIVA del orquestador: pared si es consulta de memoria y no es cognición."""
    return _es_consulta_de_memoria(texto) and not I.es_cognicion_general(texto)


# ============================================================ BATERÍA DE MEDICIÓN T5 --

#: Ataques YA escritos en `test_cognicion_local.py` y `test_conversacion_natural_local.py`, copiados
#: literalmente: la forma nueva no puede abrir ninguno.
ATAQUES_EXISTENTES = [
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
    "¿Qué me recomendaste ayer?",
    "¿Qué te conté sobre mi abuela?",
    "¿Qué me dijiste la semana pasada?",
    "¿Crees que mi hermana vive en Madrid?",
    "¿Crees que mis gatos están bien?",
    "¿Qué me recomiendas para el regalo de mi madre?",
    "¿Qué puedo hacer con lo que te conté?",
    "¿Cómo puedo recordar lo que me dijiste?",
    "¿Qué me recomiendas sobre lo que hablamos de mi trabajo?",
    "¿Cuál es el código de mi alarma?",
    "¿Dónde guardé las escrituras de la casa?",
    "¿Cómo me llamo?",
    "¿A qué me dedico?",
    "¿Cómo se llama mi hija?",
]

#: Ataques NUEVOS escritos contra la forma «suposición + consecuencia sin cifra»: fugas personales
#: disfrazadas de hipótesis. Cada uno debe chocar con al menos un freno.
ATAQUES_NUEVOS = [
    "si me llamo pedro que me pasa?",  # sin verbo físico
    "si mi hija sale tarde que pasa?",  # posesivo
    "si te dije ayer mi clave que pasa?",  # deixis + posesivo
    "si hoy es martes que me pasa?",  # deixis, sin verbo físico
    "si cumplo años mañana que me pasa?",  # deixis, sin verbo físico
    "si meto la llave que te di que pasa?",  # «te di» + interrogativo
    "si meto la mano en mi bolsillo que me pasa?",  # posesivo
    "¿qué pasa si pongo la contraseña que te conté?",  # evocación
    "si meto la mano en agua caliente que me pasa y a qué hora ceno?",  # algo cuelga detrás
    "¿qué me pasa si pongo el coche que compré en el garaje?",  # verbo del usuario
    "si tengo cita el lunes que me pasa?",  # verbo del usuario + deixis
    "si caigo enfermo como el año pasado que me pasa?",  # «como» interrogativo/yo
    "si pongo la alarma con el código de mi casa que pasa?",  # posesivo
    "si meto la mano donde guardé las escrituras que me pasa?",  # interrogativo en la premisa
    "si mezclo lo que acordamos que pasa?",  # evocación
    "si soy alérgico y toca algo que me pasa?",  # verbo del usuario
    "¿qué pasa si vivo en Madrid?",  # verbo del usuario
    "si pongo la fecha de nuestro aniversario que pasa?",  # posesivo plural + deixis
    "si pedro mete la mano como mi jefe que le pasa?",  # posesivo
    "si trabajo en logística y meto horas que me pasa?",  # verbo del usuario
]

#: Hipótesis y explicaciones del mundo SIN cifra que la ampliación debe liberar. T5 literal incluida.
POSITIVAS_T5 = [
    T5,
    "si miro el sol directamente, ¿qué me pasa?",
    "¿Qué pasa si mezclo agua y aceite?",
    "si pongo un metal en el microondas, ¿qué pasa?",
    "si caigo desde un segundo piso, ¿qué me pasaría?",
    "si el hielo se derrite, ¿qué ocurre?",
    "¿Qué sucede si la luna desapareciera?",
    "si tocas un cable pelado, ¿qué te pasa?",
    "supongamos que caliento agua sin parar, ¿qué ocurre?",
    "imagina que salto en la luna, ¿qué me pasa?",
    "si congelo agua en una botella cerrada, ¿qué pasa?",
    "si dos coches chocan de frente, ¿qué ocurre?",
]


def test_T5_literal_llega_a_la_cognicion():
    assert I.es_cognicion_general(T5)
    assert not _puerta_activa(T5), "T5 seguiria cayendo en la pared"
    assert I.referente(T5) == I.REFERENTE_MUNDO


@pytest.mark.parametrize("texto", POSITIVAS_T5)
def test_hipotesis_de_consecuencia_sin_cifra_es_cognicion(texto):
    assert I.es_cognicion_general(texto), texto
    assert I.referente(texto) == I.REFERENTE_MUNDO, texto
    assert I.destino_de_memoria(texto) is None, "una hipotesis no se almacena"


def test_la_hipotesis_de_consecuencia_exige_PREGUNTA():
    """Caso de control del filtro de acto: la misma forma sin signo ni interrogativo inicial es
    AFIRMACION y no entra por la cognicion. Sin este control, el acto podria dejar de filtrar."""
    sin_signo = "si meto la mano en agua caliente que me pasa"
    assert I._es_hipotesis_de_consecuencia(sin_signo), "guarda de cordura: la forma casa"
    assert I.acto_de_habla(sin_signo) != I.PREGUNTA
    assert not I.es_cognicion_general(sin_signo)


@pytest.mark.parametrize("texto", _negativas())
def test_MEDICION_ninguna_de_las_24_colisiona(texto):
    assert not I._es_hipotesis_de_consecuencia(texto), texto
    assert not I.es_cognicion_general(texto), texto
    assert _puerta_activa(texto), texto
    assert I.referente(texto) != I.REFERENTE_MUNDO, texto


def test_MEDICION_ninguna_consulta_de_las_dos_baterias_casa_la_forma_nueva():
    """Disyunción ampliada: las 77 de memoria y los 172 casos de intención."""
    textos = [c["texto"] for c in _memoria()]
    textos += [c["texto"] for c in json.loads(BATERIA_INTENCION.read_text(encoding="utf-8"))["casos"]]
    assert len(textos) == 77 + 172, "las baterias cambiaron: vuelve a medir"
    casan = [t for t in textos if I._es_hipotesis_de_consecuencia(t)]
    assert not casan, casan


@pytest.mark.parametrize("texto", ATAQUES_EXISTENTES + ATAQUES_NUEVOS)
def test_MEDICION_ningun_ataque_fuga_a_la_cognicion(texto):
    assert not I._es_hipotesis_de_consecuencia(texto), texto
    assert not I.es_cognicion_general(texto), texto
    assert I.referente(texto) != I.REFERENTE_MUNDO, texto


def test_MEDICION_tamano_de_la_bateria():
    """El Decision Package pide ≥12 ataques nuevos y ≥10 positivas. Si alguien recorta la batería,
    la medición deja de valer lo que dice."""
    assert len(ATAQUES_NUEVOS) >= 12
    assert len(POSITIVAS_T5) >= 10
    assert len(set(ATAQUES_NUEVOS) & set(POSITIVAS_T5)) == 0


@pytest.mark.parametrize(
    "texto,freno",
    [
        ("si meto la mano en agua caliente que me pasa y a que hora ceno?", "cola"),
        ("si meto la mano en mi agua caliente que me pasa?", "posesivo"),
        ("si hoy meto la mano en agua caliente que me pasa?", "deixis"),
        ("si trabajo y meto la mano en agua caliente que me pasa?", "verbo_yo"),
        ("si meto la mano donde hay agua caliente que me pasa?", "interrogativo"),
        ("si llevo la mano a agua caliente que me pasa?", "sin_verbo_fisico"),
    ],
)
def test_cada_freno_de_la_hipotesis_tiene_su_prueba(texto, freno):
    """Una variación mínima de T5 por freno: si se desarma uno solo, su caso cae."""
    assert I._es_hipotesis_de_consecuencia(T5), "control: la base casa"
    assert not I._es_hipotesis_de_consecuencia(texto), freno


# ============================================================ T8 · CONSULTA SOBRE AURA --


@pytest.mark.parametrize(
    "texto",
    [
        T8,
        "¿Qué estás haciendo?",
        "¿En qué estás trabajando?",
        "¿en que estas trabajado ahora?",
        "¿Por qué estás detenida?",
        "¿Por qué estás parada?",
        "¿Qué capacidades tienes?",
        "¿Qué puedes hacer?",
        "¿A qué te dedicas?",
        "¿Qué haces ahora?",
    ],
)
def test_T8_una_pregunta_a_AURA_sobre_si_misma(texto):
    assert I.es_consulta_sobre_aura(texto), texto
    assert I.referente(texto) == I.REFERENTE_AURA, texto


@pytest.mark.parametrize(
    "texto",
    [
        "¿A qué me dedico?",
        "¿Qué hago si llueve?",
        "¿Cómo me llamo?",
        "¿Qué sabes de mí?",
        "¿Qué estás haciendo con mis archivos?",
        "¿En qué trabajo?",
        "¿Qué desarrollé ayer?",
        "¿Qué me dijiste que estabas haciendo?",
    ],
)
def test_una_pregunta_del_usuario_sobre_si_mismo_NO_es_sobre_aura(texto):
    assert not I.es_consulta_sobre_aura(texto), texto


def test_consulta_sobre_aura_es_disjunta_de_la_soberania_del_modelo_de_usuario():
    """Los patrones de soberanía van antes en la cascada: ninguno puede casar aquí."""
    for pat in _PAT_MODELO_VER + _PAT_MODELO_PORQUE + _PAT_MODELO_REFUTA + _PAT_MODELO_OLVIDA:
        assert not I.es_consulta_sobre_aura(f"¿{pat}?"), pat
    for marco in I._MARCOS_SOBRE_AURA:
        for pat in _PAT_MODELO_VER:
            assert pat not in marco and marco not in pat, (marco, pat)


def test_ninguna_consulta_de_la_bateria_de_memoria_es_sobre_aura():
    casan = [c["texto"] for c in _memoria() if I.es_consulta_sobre_aura(c["texto"])]
    assert not casan, casan


# ================================================================= T7 · DOMINIO SENSIBLE --


def test_T7_quien_es_Jesus_Cristo_es_sensible():
    assert I.dominio_sensible(T7) is not None
    assert I.dominio_sensible("¿Quién es Jesús Cristo?") is not None


@pytest.mark.parametrize(
    "texto,dominio",
    [
        ("¿Qué dosis de paracetamol puedo tomar?", "salud"),
        ("¿Cuáles son los síntomas del cáncer?", "salud"),
        ("¿Puedo tomar ibuprofeno si estoy embarazada?", "salud"),
        ("¿Cómo pongo una demanda a mi casero?", "derecho"),
        ("¿Qué dice la ley sobre la herencia?", "derecho"),
        ("¿Necesito un abogado para un divorcio?", "derecho"),
        ("¿Conviene invertir en bitcoin?", "finanzas"),
        ("¿Cómo funciona una hipoteca?", "finanzas"),
        ("¿Qué es la bolsa de valores?", "finanzas"),
        ("¿Existe Dios?", "religion"),
        ("¿Qué dice la Biblia sobre el perdón?", "religion"),
        ("¿Quién fue Mahoma?", "religion"),
        ("¿Quién fue Napoleón?", "personas_reales"),
        ("quien invento la bombilla?", "personas_reales"),
        ("QUIEN ESCRIBIO EL QUIJOTE?", "personas_reales"),
        ("¿Quién descubrió América?", "personas_reales"),
        ("¿Quién era Marie Curie?", "personas_reales"),
    ],
)
def test_dominio_sensible_por_dominio(texto, dominio):
    assert I.dominio_sensible(texto) == dominio, texto


@pytest.mark.parametrize(
    "texto",
    [
        "¿Qué es la fotosíntesis?",
        "¿Por qué llueve?",
        "Adiós",  # «dios» dentro de «adios»: palabra completa
        "¿Cómo hago una papa al horno?",  # «papa» se evita a proposito
        "¿Qué receta de tortilla me recomiendas?",
        "¿Cuál es la capital de Francia?",
        "Hola",
        T5,
        T8,
        "¿Alguien es capaz de explicarme la gravedad?",  # «quien es» no puede casar dentro de otra palabra
    ],
)
def test_dominio_sensible_control_negativo(texto):
    assert I.dominio_sensible(texto) is None, texto


# ======================================================================== REFERENTE --


@pytest.mark.parametrize(
    "texto,esperado",
    [
        (T5, I.REFERENTE_MUNDO),
        (T7, I.REFERENTE_MUNDO),
        (T8, I.REFERENTE_AURA),
        ("¿Qué es la fotosíntesis?", I.REFERENTE_MUNDO),
        ("¿Qué me recomiendas para dormir mejor?", I.REFERENTE_MUNDO),
        ("si tengo 1 caballo y vendo 1, ¿cuántos me quedan?", I.REFERENTE_MUNDO),
        ("¿Cómo me llamo?", I.REFERENTE_USUARIO),
        ("¿Quién es mi jefa?", I.REFERENTE_USUARIO),
        ("¿Qué te conté sobre el presupuesto?", I.REFERENTE_USUARIO),
        ("Trabajo en logística", I.REFERENTE_USUARIO),
        ("Hola", I.REFERENTE_CONVERSACION),
        ("gracias", I.REFERENTE_CONVERSACION),
        ("¿Dónde guardé las escrituras de la casa?", I.REFERENTE_INCIERTO),
    ],
)
def test_referente(texto, esperado):
    assert I.referente(texto) == esperado, texto


def test_el_posesivo_gana_al_mundo():
    """Control del orden: esta suposición con cifra ES cognición general, pero nombra «mi». El freno
    del posesivo va antes que el mundo, así que sale USUARIO."""
    texto = "si mi hermano tiene 3 coches y vende 1, ¿cuántos le quedan?"
    assert I.es_cognicion_general(texto), "guarda de cordura: la superficie cognitiva la acepta"
    assert I.referente(texto) == I.REFERENTE_USUARIO


def test_referente_solo_devuelve_las_cinco_etiquetas():
    etiquetas = {
        I.REFERENTE_USUARIO,
        I.REFERENTE_AURA,
        I.REFERENTE_MUNDO,
        I.REFERENTE_CONVERSACION,
        I.REFERENTE_INCIERTO,
    }
    assert etiquetas == {"usuario", "aura", "mundo", "conversacion", "incierto"}
    textos = [c["texto"] for c in _memoria()] + ATAQUES_NUEVOS + POSITIVAS_T5
    assert {I.referente(t) for t in textos} <= etiquetas


def test_ninguna_consulta_de_la_bateria_de_memoria_sale_MUNDO():
    """Las 77 (24 negativas + 53 positivas) interrogan la memoria personal: ninguna es MUNDO."""
    mundo = [c["texto"] for c in _memoria() if I.referente(c["texto"]) == I.REFERENTE_MUNDO]
    assert not mundo, mundo
