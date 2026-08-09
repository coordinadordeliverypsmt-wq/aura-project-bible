"""Conversación General v1 — contrato cerrado por el CEO (`DP-CONVERSACION-GENERAL-V1.md`, 06f53f3).

EVIDENCIA DE USO REAL QUE LO MOTIVA. El CEO ejecutó AURORA y obtuvo:

    tu> ¿Quién eres?
    AURA> No tengo ningun recuerdo registrado sobre eso.
    tu> ¿Cómo puedo ayudarte?
    AURA> No tengo ningun recuerdo registrado sobre eso.
    tu> Buenos días Aurora, ¿qué tienes pendiente para hoy?
    AURA> No tengo ningun recuerdo registrado sobre eso.

CAUSA (verificada en `orchestrator.py`): `_es_consulta_de_memoria` termina en `or _es_pregunta(texto)`,
de modo que CUALQUIER interrogativa que nadie haya reclamado antes cae en la ausencia de memoria.

QUÉ NO SE TOCA (condición del CEO): ni `_es_consulta_de_memoria` ni la puerta de ADR-0014. Este
incremento sólo RECLAMA ANTES un conjunto cerrado de intenciones. Lo que no está en la lista sigue
exactamente el camino de hoy, bit a bit -- por eso las 24 negativas de la batería oficial siguen
protegidas (`test_las_24_negativas_de_adr0014_siguen_atendidas_por_el_nucleo`).

LA UNIDAD DE RECONOCIMIENTO ES UNA SECUENCIA DE INTENCIONES, no una frase (ajuste del CEO):
  - MODIFICADORAS (saludo, cortesía, despedida) NO consumen el turno: sólo anteponen su respuesta.
  - PRINCIPALES deciden quién responde.
  - MULTIPLICIDAD != AMBIGÜEDAD: dos principales distintas y resolubles se responden AMBAS, en el
    orden formulado, sin preguntar; sólo una frase que pertenece a dos dominios donde responder uno
    implica ignorar el otro pide aclaración.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estado_operativo import Tarea
from aura_skeleton.core.orchestrator import (
    _ACLARACION_APRENDIDO_DE_MI,
    _SIN_PENDIENTES,
    _TABLA_INTENCIONES,
    _VAR_SALUDO,
    _es_consulta_de_capacidades,
    _es_consulta_de_formacion,
    _es_consulta_de_gobierno,
    _es_consulta_de_tareas,
    _normalizar,
    _secuencia_de_intenciones,
)
from aura_skeleton.modules.router import ModelRouter

_RUTA_BATERIA_MEMORIA = Path(__file__).parent.parent / "datos" / "bateria_memoria.json"
_RUTA_BATERIA_INTENCION = Path(__file__).resolve().parents[3] / "milestones" / "m3-entry" / "bateria-intencion.json"


class _ProveedorEspia:
    """Registra si el orquestador llegó a consultar al modelo. Copiado a propósito del patrón de
    `tests/unit/test_grounding_core.py`: la garantía que vigila es la misma (ADR-0014)."""

    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str) -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"respuesta fabricada por el LLM"}'


async def _di(orq, texto, uid="mauricio"):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


@pytest.fixture
def sistema(tmp_path):
    """El sistema COMPUESTO real: mismas superficies que en producción (MA.1)."""
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg)


@pytest.fixture
def espia(sistema):
    """Sustituye el proveedor del router del sistema compuesto por un espía. Permite afirmar
    "el LLM NO se consultó" sobre el sistema real, no sobre un doble escrito para cumplirlo."""
    sonda = _ProveedorEspia()
    sistema.orquestador.router = ModelRouter([sonda], 1200)
    return sonda


def _ausencia(r) -> bool:
    return r["say"] == "No tengo ningun recuerdo registrado sobre eso."


# ------------------------------------------------------ LA BATERÍA DEL CEO (prueba funcional base) --
#
# El CEO: "Considero esta batería de preguntas como la prueba funcional base de Conversación General
# v1. A partir de ahora, cualquier implementación del router deberá superar esta batería antes de
# integrarse." Cada frase es literal, tal como la escribió en la terminal.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    [
        "Hola",
        "Buenos días Aurora",
        "Hola Aurora, ¿qué puedes hacer?",
        "¿Quién eres?",
        "¿Cómo puedo ayudarte?",
        "Buenos días Aurora, ¿qué tienes pendiente para hoy?",
        "¿En qué estás trabajando?",
    ],
)
async def test_bateria_del_ceo_ninguna_cae_en_la_ausencia_de_memoria(sistema, espia, frase):
    """Ninguna de estas frases es una consulta de memoria: ninguna puede recibir la respuesta de
    ausencia, y ninguna puede acabar en el LLM (son hechos del sistema o cortesía, ADR-0014 §2)."""
    r = await _di(sistema.orquestador, frase)
    assert not _ausencia(r), f"{frase!r} sigue cayendo en la ausencia de memoria: {r['say']!r}"
    assert r["provider"] == "core", f"{frase!r} debió responderla el núcleo, no {r['provider']!r}"
    assert espia.llamadas == 0, f"{frase!r} llegó al LLM"
    assert r["say"].strip(), f"{frase!r} respondió con texto vacío"


@pytest.mark.asyncio
async def test_que_recuerdas_de_mi_sigue_siendo_consulta_de_memoria_sin_llm(sistema, espia):
    """La otra mitad de la batería del CEO: esta SÍ es una consulta de memoria. Sin recuerdos debe
    seguir respondiendo el núcleo con la ausencia y SIN consultar al LLM. Si este incremento la
    hubiera reclamado, habría roto ADR-0014 arreglando la experiencia."""
    r = await _di(sistema.orquestador, "¿Qué recuerdas de mí?")
    assert r["provider"] == "core"
    assert _ausencia(r), f"dejó de declarar la ausencia: {r['say']!r}"
    assert espia.llamadas == 0


# ------------------------------------------------------------------------ identidad y propósito --


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["¿Quién eres?", "¿Qué eres?", "¿Sabes quién eres?"])
async def test_quien_eres_se_presenta_sin_fabricar(sistema, frase):
    """Se presenta con su nombre real y su papel. INV-9: no afirma capacidades concretas aquí --
    para eso está la superficie de capacidades, que lee el registro."""
    r = await _di(sistema.orquestador, frase)
    assert r["provider"] == "core"
    assert "AURORA" in r["say"], f"no se presenta por su nombre: {r['say']!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["¿Cómo puedo ayudarte?", "¿En qué puedo ayudarte?"])
async def test_como_puedo_ayudarte_es_una_intencion_distinta_de_capacidades(sistema, frase):
    """El usuario ofrece ayuda: no está preguntando qué sabe hacer AURORA. Responder aquí el
    catálogo de capacidades sería contestar a otra pregunta."""
    r = await _di(sistema.orquestador, frase)
    assert r["provider"] == "core"
    assert "capacidad(es) registradas" not in r["say"], (
        f"contestó el catálogo de capacidades a una oferta de ayuda: {r['say']!r}"
    )
    assert not _ausencia(r)


# ---------------------------------------------------- saludo + principal: la secuencia del CEO --


@pytest.mark.asyncio
async def test_el_saludo_no_consume_el_turno_capacidades(sistema):
    """Frase exacta exigida por el contrato. El saludo es MODIFICADORA: antepone su respuesta pero
    la intención principal (capacidades) sigue decidiendo quién responde."""
    reales = sistema.registro_adaptadores.capacidades()
    assert len(reales) > 3, "guarda de cordura: con <=3 capacidades esta prueba no discriminaría"

    r = await _di(sistema.orquestador, "Hola Aurora, ¿qué puedes hacer?")
    assert r["provider"] == "core"
    assert r["say"].startswith("Hola"), f"el saludo no se antepuso: {r['say']!r}"
    for cap in sorted(reales):
        assert cap in r["say"], f"el saludo hizo perder la intención principal (falta {cap!r})"


@pytest.mark.asyncio
async def test_el_saludo_no_consume_el_turno_pendientes(sistema):
    """La frase LITERAL que el CEO escribió en la terminal y que motivó todo el incremento."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="escribir el ADR de la ventana del SO",
            estado="abierta",
            responsable="programador",
            origen="ceo",
        )
    )
    r = await _di(sistema.orquestador, "Buenos días Aurora, ¿qué tienes pendiente para hoy?")
    assert r["provider"] == "core"
    assert r["say"].startswith("Buenos días"), f"el saludo no se antepuso: {r['say']!r}"
    assert "escribir el ADR de la ventana del SO" in r["say"], (
        f"el saludo hizo perder la consulta de pendientes: {r['say']!r}"
    )


@pytest.mark.asyncio
async def test_control_sin_saludo_el_destino_es_el_mismo(sistema):
    """CONTROL exigido por el contrato: quitar el saludo no puede cambiar el destino. El cuerpo de
    la respuesta debe ser IDÉNTICO; lo único que desaparece es la línea del saludo.

    Sin este control, la prueba anterior pasaría aunque el saludo estuviera decidiendo el destino.
    """
    con_saludo = await _di(sistema.orquestador, "Hola Aurora, ¿qué puedes hacer?")
    sin_saludo = await _di(sistema.orquestador, "¿Qué puedes hacer?")
    assert con_saludo["provider"] == sin_saludo["provider"] == "core"
    assert con_saludo["say"].endswith(sin_saludo["say"]), (
        f"el cuerpo cambió al quitar el saludo:\ncon:  {con_saludo['say']!r}\nsin: {sin_saludo['say']!r}"
    )
    assert con_saludo["say"] != sin_saludo["say"], "el saludo no añadió nada"


@pytest.mark.asyncio
async def test_el_vocativo_no_impide_reconocer_el_saludo_solo(sistema):
    r_con = await _di(sistema.orquestador, "Buenos días Aurora")
    r_sin = await _di(sistema.orquestador, "Buenos días")
    assert r_con["provider"] == r_sin["provider"] == "core"
    assert r_con["say"] == r_sin["say"], "el vocativo 'Aurora' cambió la respuesta al saludo"


@pytest.mark.asyncio
async def test_un_saludo_solo_ofrece_ayuda_no_deja_el_turno_mudo(sistema):
    r = await _di(sistema.orquestador, "Hola")
    assert r["provider"] == "core"
    assert "?" in r["say"], f"un saludo suelto debe devolver la conversación al usuario: {r['say']!r}"


# --------------------------------------------------------- MULTIPLICIDAD: dos principales, ambas --


@pytest.mark.asyncio
async def test_dos_intenciones_principales_se_responden_ambas_en_orden(sistema):
    """Decisión del CEO que cerró el contrato: si las dos pueden resolverse, se responden AMBAS,
    en el orden formulado. NUNCA se pide aclaración por multiplicidad."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="escribir el ADR de la ventana del SO",
            estado="abierta",
            responsable="programador",
            origen="ceo",
        )
    )
    reales = sistema.registro_adaptadores.capacidades()

    r = await _di(sistema.orquestador, "Hola Aurora, ¿qué puedes hacer y qué tienes pendiente?")
    assert r["provider"] == "core"
    say = r["say"]

    pos_capacidades = say.find("capacidad(es) registradas")
    pos_pendientes = say.find("escribir el ADR de la ventana del SO")
    assert pos_capacidades >= 0, f"falta la PRIMERA intención (capacidades): {say!r}"
    assert pos_pendientes >= 0, f"falta la SEGUNDA intención (pendientes): {say!r}"
    assert pos_capacidades < pos_pendientes, f"el orden de las intenciones se invirtió: {say!r}"
    for cap in sorted(reales):
        assert cap in say
    assert _ACLARACION_APRENDIDO_DE_MI not in say, "pidió aclaración ante MULTIPLICIDAD; el contrato lo prohíbe"


@pytest.mark.asyncio
async def test_multiplicidad_invertida_respeta_el_orden_formulado(sistema):
    """Kill del mutante "el orden lo fija la tabla, no el turno": con las mismas dos intenciones en
    orden inverso, la respuesta debe invertirse también."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="escribir el ADR de la ventana del SO",
            estado="abierta",
            responsable="programador",
            origen="ceo",
        )
    )
    r = await _di(sistema.orquestador, "Hola Aurora, ¿qué tienes pendiente y qué puedes hacer?")
    say = r["say"]
    pos_pendientes = say.find("escribir el ADR de la ventana del SO")
    pos_capacidades = say.find("capacidad(es) registradas")
    assert pos_pendientes >= 0 and pos_capacidades >= 0, f"falta alguna de las dos intenciones: {say!r}"
    assert pos_pendientes < pos_capacidades, f"no se respetó el orden formulado: {say!r}"


# --------------------------------------------------------------- AMBIGÜEDAD REAL: pide aclaración --


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["¿Qué has aprendido de mí?", "¿qué aprendiste de mí?"])
async def test_ambiguedad_real_pide_aclaracion(sistema, frase):
    """UNA frase, DOS dominios (lo que sé de ti / lo que he aprendido yo trabajando), y responder
    uno implica ignorar el otro. El contrato exige preguntar.

    CAMBIO DE COMPORTAMIENTO DECLARADO: antes de este incremento caía en la ausencia de memoria.
    La garantía que protegía aquella prueba -no volcar el Plan de Formación con notas internas
    sobre APUS-5- se mantiene y se sigue verificando aquí.
    """
    r = await _di(sistema.orquestador, frase)
    assert r["provider"] == "core"
    assert r["say"].rstrip().endswith("?"), f"no pidió aclaración: {r['say']!r}"
    assert not _ausencia(r)
    assert "APUS-5" not in r["say"], "volcó el Plan de Formación en vez de preguntar"
    assert "Coordinar su propio backlog" not in r["say"]


@pytest.mark.asyncio
async def test_que_has_aprendido_sin_objeto_ajeno_sigue_siendo_el_plan_de_formacion(sistema):
    """Control de la anterior: sin "de mí" NO hay ambigüedad, y la superficie de formación que ya
    existía debe seguir respondiendo exactamente igual."""
    r = await _di(sistema.orquestador, "¿Qué has aprendido?")
    assert r["provider"] == "core"
    assert "Coordinar su propio backlog" in r["say"], f"la superficie de formación cambió: {r['say']!r}"


# ------------------------------------------------------------------------------- INV-9: el nombre --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "declarado",
    [
        "me llamo Mauricio",
        "Prefiero el té. No me llamo Pedro, me llamo Mauricio.",
        "Mi nombre es de dominio publico.",
        "El perro se llama Toby. Me llamo Mauricio.",
    ],
)
async def test_el_saludo_nunca_lleva_nombre_propio(sistema, declarado):
    """INV-9, endurecido tras el rechazo de la auditoría independiente.

    La primera versión leía "me llamo X" del texto libre de cualquier entrada semántica y saludaba
    con la PRIMERA coincidencia. Medido `[EJEC]`: con "No me llamo Pedro, me llamo Mauricio" saludaba
    "Buenos días, Pedro" -la negación explícita del usuario perdía-, y con "Mi nombre es de dominio
    publico" saludaba "Buenos días, de".

    Y el fondo era peor: decir "me llamo Mauricio" NO alimenta el Modelo de Usuario (0 entradas,
    medido). La rama "con nombre" sólo era alcanzable fabricando. Saludar por el nombre exige antes
    una capacidad que no existe -que AURORA aprenda cómo te llamas- y ésa necesita su propio
    Decision Package.

    Estas cuatro entradas son las que rompían la versión anterior; ninguna puede colarse ahora.
    """
    await sistema.memoria.write("mauricio", "semantica", declarado, {"origen": "declarada", "fuente": "usuario"})
    r = await _di(sistema.orquestador, "Buenos días")
    assert r["provider"] == "core"
    assert r["say"].split("\n")[0] == "Buenos días.", f"el saludo llevaba nombre: {r['say']!r}"
    for fabricado in ("Mauricio", "Pedro", "Toby", "dominio"):
        assert fabricado not in r["say"], f"coló {fabricado!r} en el saludo: {r['say']!r}"


# ------------------------------------------------------- ADR-0014: la garantía irrenunciable --


def _negativas_de_la_bateria() -> list[str]:
    """Las consultas SIN `esperado` de la batería oficial: aquellas para las que NO existe ningún
    recuerdo correcto. Son las que la garantía de no-fabricación existe para proteger."""
    bateria = json.loads(_RUTA_BATERIA_MEMORIA.read_text(encoding="utf-8"))
    return [c["texto"] for c in bateria["consultas"] if c.get("esperado") is None]


@pytest.mark.asyncio
async def test_las_24_negativas_de_adr0014_siguen_atendidas_por_el_nucleo(sistema, espia):
    """LA PRUEBA IRRENUNCIABLE. Con memoria vacía, las 24 consultas negativas de la batería oficial
    deben seguir respondidas por el NÚCLEO y sin UNA SOLA llamada al LLM.

    Es la medida que hundió la tabla de enrutamiento: su regla de admisión llevaba esta garantía de
    24/24 a 0/24 y ninguna prueba existente lo habría notado.
    """
    negativas = _negativas_de_la_bateria()
    assert len(negativas) == 24, f"la batería oficial cambió de tamaño: {len(negativas)} negativas"

    fallos = []
    for frase in negativas:
        r = await _di(sistema.orquestador, frase)
        if r["provider"] != "core" or not _ausencia(r):
            fallos.append((frase, r["provider"], r["say"]))
    assert not fallos, f"{len(fallos)}/24 negativas dejaron de estar protegidas: {fallos[:3]}"
    assert espia.llamadas == 0, f"el LLM fue consultado {espia.llamadas} veces sobre las negativas"


# --------------------------------------- DEFECTOS ENCONTRADOS POR LA AUDITORÍA INDEPENDIENTE --
#
# Cada prueba de este bloque nació de un mutante que SOBREVIVÍA o de una conducta medida como
# defectuosa. Ninguna es preventiva: todas cubren algo que estaba roto.


@pytest.mark.asyncio
async def test_el_saludo_pegado_a_la_consulta_sin_coma_se_reconoce(sistema):
    """DEFECTO MEDIDO: "buenos días Aurora qué tienes pendiente para hoy" -sin la coma- respondía
    "Entendido." desde el LLM. Es la frase insignia del contrato, y la entrada llega por
    transcripción de voz, donde la puntuación es lo primero que se pierde."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="escribir el ADR de la ventana del SO",
            estado="abierta",
            responsable="programador",
            origen="ceo",
        )
    )
    r = await _di(sistema.orquestador, "buenos días Aurora qué tienes pendiente para hoy")
    assert r["provider"] == "core", f"acabó en el LLM: {r['say']!r}"
    assert r["say"].startswith("Buenos días."), f"no reconoció el saludo pegado: {r['say']!r}"
    assert "escribir el ADR de la ventana del SO" in r["say"], f"perdió la consulta: {r['say']!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("buenas noches qué tienes pendiente", "Buenas noches."),
        ("buenas tardes Aurora qué tienes pendiente", "Buenas tardes."),
        ("qué tal estás qué tienes pendiente", "Hola."),
    ],
)
async def test_el_saludo_pegado_reconoce_la_variante_mas_larga(sistema, frase, esperado):
    """MUTANTE VIVO (2ª auditoría): recorrer las variantes de saludo de MENOR a mayor longitud.

    "buenas" es prefijo de "buenas noches" y "buenas tardes"; "que tal" lo es de "que tal estas". Con
    el orden ascendente, "buenas noches qué tienes pendiente" se parte como "buenas" + "noches qué
    tienes pendiente", el resto no casa y la frase acaba en el LLM: el defecto insignia del contrato
    reintroducido para las tardes y las noches. El docstring afirmaba que el orden lo impedía y nada
    lo comprobaba.
    """
    r = await _di(sistema.orquestador, frase)
    assert r["provider"] == "core", f"{frase!r} acabó en el LLM: {r['say']!r}"
    assert r["say"].startswith(esperado), f"no eligió la variante más larga: {r['say']!r}"
    assert _SIN_PENDIENTES in r["say"], f"perdió la consulta: {r['say']!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["heyque tienes pendiente", "holaque puedes hacer"])
async def test_el_saludo_pegado_exige_limite_de_palabra(sistema, frase):
    """MUTANTE VIVO (2ª auditoría): `startswith(variante)` en vez de `startswith(variante + " ")`.

    Sin el espacio, la coincidencia pasa a ser por prefijo de CARACTERES y "heyque…" se lee como
    "hey" + "que…". Es la misma disciplina de límite de palabra que `_RE_OBJETO_AJENO` ya aplica con
    `\\b` en este fichero, por la misma razón: "de mi" no debe reconocer "de miedo".
    """
    r = await _di(sistema.orquestador, frase)
    assert not r["say"].startswith("Hola."), f"reclamó por prefijo de caracteres: {r['say']!r}"


@pytest.mark.asyncio
async def test_la_deduplicacion_conserva_el_primer_saludo(sistema):
    """MUTANTE VIVO (2ª auditoría): deduplicar conservando la ÚLTIMA aparición en vez de la primera.

    "buenos días, hola, qué tal" pasaba a responder "Hola." en vez de "Buenos días.": AURORA
    contestaría con un saludo que el usuario escribió de pasada, no con el que abrió la conversación.
    El docstring exige "conservando su primera posición" y nada lo comprobaba.
    """
    r = await _di(sistema.orquestador, "buenos días, hola, qué tal")
    assert r["provider"] == "core"
    assert r["say"].startswith("Buenos días."), f"no conservó el primer saludo: {r['say']!r}"


@pytest.mark.asyncio
async def test_para_que_sirves_no_responde_lo_mismo_que_quien_eres(sistema):
    """MUTANTE VIVO (2ª auditoría): la rama `proposito` devolvía el texto de `identidad` y ninguna
    prueba lo notaba -- `_RESPUESTA_PROPOSITO` no tenía red alguna. Son dos preguntas distintas:
    quién eres y para qué estás."""
    r_proposito = await _di(sistema.orquestador, "¿Para qué sirves?")
    r_identidad = await _di(sistema.orquestador, "¿Quién eres?")
    assert r_proposito["provider"] == r_identidad["provider"] == "core"
    assert r_proposito["say"] != r_identidad["say"], "propósito e identidad devuelven el mismo texto"
    assert not _ausencia(r_proposito)


@pytest.mark.asyncio
async def test_el_saludo_pegado_no_reintroduce_la_coincidencia_por_subcadena(sistema):
    """CONTROL de la anterior. Separar un saludo inicial NO puede convertirse en "empieza por hola,
    luego reclamo": el resto tiene que casar ENTERO con otra variante."""
    r = await _di(sistema.orquestador, "hola qué tal la fiesta de ayer")
    assert not r["say"].startswith("Hola."), f"reclamó por prefijo: {r['say']!r}"


@pytest.mark.asyncio
async def test_una_intencion_repetida_se_responde_una_sola_vez(sistema):
    """DEFECTO MEDIDO: "hola, Aurora, qué tal" respondía "Hola.\\nHola." y "¿Qué puedes hacer? ¿Qué
    puedes hacer?" volcaba el catálogo de 17 capacidades DOS veces."""
    r_saludo = await _di(sistema.orquestador, "hola, Aurora, qué tal")
    assert r_saludo["say"].count("Hola.") == 1, f"saludo duplicado: {r_saludo['say']!r}"

    r_caps = await _di(sistema.orquestador, "¿Qué puedes hacer? ¿Qué puedes hacer?")
    assert r_caps["say"].count("capacidad(es) registradas") == 1, f"catálogo duplicado: {r_caps['say']!r}"


@pytest.mark.asyncio
async def test_una_ambigua_no_anula_una_principal_resoluble(sistema):
    """REGRESIÓN MEDIDA por la auditoría: "¿qué puedes hacer y qué has aprendido de mí?" respondía
    las capacidades ANTES del incremento y pasó a sólo preguntar.

    Contradice el criterio literal del CEO: "si las dos intenciones pueden resolverse, prefiero una
    respuesta más larga antes que interrumpir la conversación". La ambigua ocupa su posición en la
    secuencia; no se traga las demás.
    """
    reales = sistema.registro_adaptadores.capacidades()
    r = await _di(sistema.orquestador, "¿qué puedes hacer y qué has aprendido de mí?")
    assert r["provider"] == "core"
    for cap in sorted(reales):
        assert cap in r["say"], f"la ambigua se tragó la intención resoluble: {r['say']!r}"
    assert _ACLARACION_APRENDIDO_DE_MI in r["say"], f"perdió la aclaración: {r['say']!r}"
    assert r["say"].find("capacidad(es) registradas") < r["say"].find(_ACLARACION_APRENDIDO_DE_MI), (
        "no respetó el orden formulado"
    )


@pytest.mark.asyncio
async def test_una_parte_desconocida_dentro_de_la_conjuncion_anula_el_turno(sistema):
    """MUTANTE A5, que sobrevivía: en la pasada de la conjunción "y", descartar en silencio los
    trozos no reconocidos, contestando el que sí se reconoce y TIRANDO la pregunta del usuario.
    El mutante declarado M12 sólo cubría la otra rama (`len(trozos) < 2`).

    OJO CON LA FRASE ELEGIDA. Con "¿qué puedes hacer y cuál es la capital de Francia?" esta prueba
    mediría otra cosa: ahí Conversación General SÍ devuelve el turno, pero lo recoge después
    `_es_consulta_de_capacidades`, que casa por SUBCADENA y contesta el catálogo tirando la pregunta.
    Ese defecto es PREEXISTENTE y ajeno a este incremento (verificado `[EJEC]`: el detector antiguo
    reconoce la frase entera). Se usa "qué tienes pendiente", que ninguna superficie posterior
    reclama, para que lo que falle aquí sea sólo lo de este incremento.
    """
    r = await _di(sistema.orquestador, "Hola, ¿qué tienes pendiente y cuál es la capital de Francia?")
    assert r["provider"] == "core"
    assert _ausencia(r), f"descartó la parte desconocida y respondió igual: {r['say']!r}"


@pytest.mark.asyncio
async def test_el_vocativo_inicial_tambien_se_quita(sistema):
    """MUTANTE A3, que sobrevivía: quitar sólo el vocativo FINAL. "Aurora buenos días" acababa en
    el LLM. El bucle del principio no tenía ninguna prueba que dependiera de él."""
    r = await _di(sistema.orquestador, "Aurora, buenos días")
    assert r["provider"] == "core", f"acabó en el LLM: {r['say']!r}"
    assert r["say"].startswith("Buenos días."), f"no quitó el vocativo inicial: {r['say']!r}"


@pytest.mark.asyncio
async def test_cada_modificadora_aporta_su_propia_linea(sistema):
    """MUTANTES A15 y A2, que sobrevivían: que la despedida dejara de aportar su línea, y que las
    líneas se unieran con un espacio en vez de con un salto. "Gracias, adiós" debe dar las dos
    líneas, en su orden."""
    r = await _di(sistema.orquestador, "Gracias, adiós")
    assert r["provider"] == "core"
    assert r["say"] == "De nada.\nHasta luego.", f"las modificadoras no se compusieron bien: {r['say']!r}"


@pytest.mark.asyncio
async def test_pendientes_distingue_tener_objetivos_de_no_tenerlos(sistema):
    """MUTANTE A14, que sobrevivía: que el texto de "sin objetivos" dejara de distinguirse. Se fija
    el texto EXACTO de la ausencia y se comprueba que con una tarea real deja de aparecer."""
    r_vacio = await _di(sistema.orquestador, "¿Qué tienes pendiente?")
    assert r_vacio["say"] == _SIN_PENDIENTES, f"el texto de ausencia cambió: {r_vacio['say']!r}"

    sistema.estado_operativo.registrar(
        Tarea(objetivo_id="obj-1", tarea_id="t-1", descripcion="tarea real sembrada", estado="abierta", origen="ceo")
    )
    r_con = await _di(sistema.orquestador, "¿Qué tienes pendiente?")
    assert r_con["say"] != _SIN_PENDIENTES, "siguió declarando ausencia con una tarea real registrada"
    assert "tarea real sembrada" in r_con["say"], f"no leyó el Estado Operativo real: {r_con['say']!r}"


# ------------------------------------------- LO QUE NO ESTÁ EN LA LISTA SIGUE EL CAMINO DE HOY --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    [
        "¿qué tienes pendiente en la lista de la compra que te di?",
        "hola qué tal la fiesta de ayer",
    ],
)
async def test_contener_una_variante_no_basta_hace_falta_ser_el_segmento_entero(sistema, frase):
    """Kill del mutante "coincidencia por subcadena". Estas frases CONTIENEN una variante ("qué
    tienes pendiente", "hola", "qué tal") pero no la SON: hablan de otra cosa. `any(patrón in texto)`
    es la construcción que produjo el defecto original y aquí lo recrearía en el otro sentido --
    robarle el turno a lo que sí sabe responder."""
    r = await _di(sistema.orquestador, frase)
    assert not r["say"].startswith("Hola"), f"la reclamó por subcadena: {r['say']!r}"
    assert "capacidad(es) registradas" not in r["say"]
    assert "pendiente registrado" not in r["say"]


@pytest.mark.asyncio
async def test_saludo_mas_pregunta_desconocida_sigue_el_flujo_previo(sistema):
    """Kill del mutante "las partes no reconocidas se ignoran". Si el saludo se respondiera y la
    pregunta se descartara en silencio, el usuario recibiría "Hola." a una pregunta real: peor que
    la ausencia de memoria, porque parece una respuesta."""
    r = await _di(sistema.orquestador, "Hola, ¿cuál es la capital de Francia?")
    assert r["provider"] == "core"
    assert _ausencia(r), f"perdió la pregunta y respondió sólo al saludo: {r['say']!r}"


@pytest.mark.asyncio
async def test_pendientes_sin_estado_operativo_conectado_no_fabrica_la_ausencia(tmp_path):
    """INV-9 sobre el CABLEADO, no sobre la lógica. Sin Estado Operativo conectado, AURORA no puede
    afirmar "no tengo nada pendiente": no lo sabe. Debe seguir el camino previo.

    Es el mutante que ALERTA-005 enseñó a buscar: la composición deja de encender una fuente y el
    sistema responde igual de convincente con datos que nadie le dio.
    """
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock
    from aura_skeleton.adapters.voice import VoiceAdapterMock
    from aura_skeleton.bus import InProcessEventBus
    from aura_skeleton.core.orchestrator import Orchestrator
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.modules.memory import SimpleMemory
    from aura_skeleton.modules.router import MockProvider

    async def _deny(a, args, tid):
        return False

    orq = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([MockProvider("m", 1)], 1200),
        PermissionManager(_deny),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    r = await _di(orq, "¿Qué tienes pendiente?")
    assert r["provider"] == "core"
    assert _ausencia(r), f"afirmó no tener pendientes sin Estado Operativo conectado: {r['say']!r}"

    # MUTANTE VIVO (2ª auditoría): `continue` en vez de `return None` cuando una principal no es
    # resoluble. CON SALUDO DELANTE el efecto es peor y la frase sola no lo detecta: el turno se
    # queda con el saludo, responde "Hola. ¿En qué puedo ayudarte hoy?" y DESCARTA la pregunta. El
    # usuario recibe algo que PARECE una respuesta, que es peor que declarar la ausencia.
    r_con_saludo = await _di(orq, "Hola, ¿qué tienes pendiente para hoy?")
    assert r_con_saludo["provider"] == "core"
    assert _ausencia(r_con_saludo), f"el saludo se comió una pregunta que no podía resolver: {r_con_saludo['say']!r}"


# ------------------------------------------------------------------- PRUEBA DE EQUIVALENCIA (DP §4) --
#
# `bateria-intencion.json` (172 casos) existía en `milestones/m3-entry/` y NINGUNA prueba lo leía.
# Se estrena aquí, que es para lo que se grabó.

# Medido `[EJEC]` grabando la respuesta del sistema COMPUESTO a los 172 casos con el código anterior
# (06f53f3) y con el nuevo: cambian 5 y sólo 5. Los 167 restantes son idénticos byte a byte, provider
# incluido. Los 5 pasan de `mock` a `core`: este incremento QUITA llamadas al LLM, no las añade.
_CAMBIOS_ESPERADOS_EN_LA_BATERIA = ("Adiós", "Buenos días", "Gracias", "Hasta luego", "Hola")

# ÚNICAS variantes autorizadas a cambiar lo que respondía la cascada, declaradas por adelantado.
# `_tiene_objeto_ajeno` cubre "de mi" pero NO "sobre mi", así que estas dos frases volcaban el Plan
# de Formación entero -con las notas internas sobre APUS-5- que la auditoría anterior declaró
# bloqueante para su hermana "de mí". Aquí pasan a pedir aclaración, que es la misma corrección.
# Lo señaló la auditoría independiente como cambio de conducta no declarado; queda declarado.
_VARIANTES_QUE_CAMBIAN_A_PROPOSITO = frozenset({"que has aprendido sobre mi", "que aprendiste sobre mi"})


def test_equivalencia_solo_cambian_los_casos_declarados_por_adelantado():
    """La lista es POSITIVA y CERRADA: sólo puede desviar lo que nombra. Esta prueba lo convierte en
    una obligación permanente -- ampliar las variantes sin declarar el cambio rompe aquí, no en
    producción, que es donde se enteró el CEO la última vez.
    """
    casos = json.loads(_RUTA_BATERIA_INTENCION.read_text(encoding="utf-8"))["casos"]
    assert len(casos) == 172, f"la batería de intención cambió de tamaño: {len(casos)}"

    reclamados = sorted({c["texto"] for c in casos if _secuencia_de_intenciones(c["texto"]) is not None})
    assert reclamados == sorted(_CAMBIOS_ESPERADOS_EN_LA_BATERIA), (
        f"el conjunto de casos desviados dejó de ser el declarado: {reclamados}"
    )


# INVENTARIO CONGELADO de la lista cerrada. Es la lista POSITIVA completa, copiada aquí a propósito:
# ampliar una intención en el código sin declararlo aquí rompe la prueba.
#
# POR QUÉ HACE FALTA, además del candado de abajo (rechazo de la segunda auditoría independiente):
# aquel bucle empieza por `if not reconoce(variante): continue`, así que sólo vigila las variantes que
# YA reconocía alguna de las 4 superficies posteriores. Una variante que NADIE reconocía no se
# comparaba con nada -- y sin embargo cambia la producción. El auditor lo demostró con tres mutantes
# que sobrevivían a las 730 pruebas: añadir "que me gusta" a las de pendientes, "cuentame algo" a las
# de capacidades o "que hora es" a los saludos hace que esas frases dejen de llegar a la puerta de
# ADR-0014, que es exactamente lo que este incremento prometió no tocar fuera de la lista declarada.
#
# La batería de intención tampoco las atrapaba: ninguna de las tres aparece entre sus 172 casos.
_INVENTARIO_DECLARADO = {
    "saludo": (
        "buen dia",
        "buenas",
        "buenas noches",
        "buenas tardes",
        "buenos dias",
        "como estas",
        "como te va",
        "hey",
        "hola",
        "que tal",
        "que tal estas",
    ),
    "cortesia": ("gracias", "mil gracias", "muchas gracias", "te lo agradezco"),
    "despedida": ("adios", "chao", "chau", "hasta luego", "hasta manana", "nos vemos"),
    "identidad": ("como te llamas", "que eres", "quien eres", "quien sos", "sabes quien eres"),
    "proposito": ("cual es tu proposito", "para que estas", "para que existes", "para que sirves"),
    "ofrecimiento": (
        "como puedo ayudarte",
        "como te puedo ayudar",
        "en que puedo ayudarte",
        "en que te puedo ayudar",
        "que necesitas",
        "que necesitas de mi",
    ),
    "capacidades": (
        "como puedes ayudarme",
        "con que me puedes ayudar",
        "cuales son tus capacidades",
        "en que me puedes ayudar",
        "que capacidades tienes",
        "que podes hacer",
        "que puedes hacer",
        "que sabes hacer",
    ),
    "pendientes": (
        "como va todo",
        "que hay de nuevo",
        "que hay pendiente",
        "que tal vas",
        "que tienes para hoy",
        "que tienes pendiente",
        "que tienes pendiente hoy",
        "que tienes pendiente para hoy",
    ),
    "aprendido_de_mi": (
        "que aprendiste de mi",
        "que aprendiste sobre mi",
        "que has aprendido de mi",
        "que has aprendido sobre mi",
    ),
}


# La CLASE de cada intención, congelada aparte: decide si consume el turno o sólo lo modifica.
# El inventario de arriba sólo fija QUÉ frases se reclaman; cambiar `pendientes` de `principal` a
# `ambigua` no lo veía (lo señaló el auditor).
_CLASES_DECLARADAS = {
    "saludo": "modificadora",
    "cortesia": "modificadora",
    "despedida": "modificadora",
    "identidad": "principal",
    "proposito": "principal",
    "ofrecimiento": "principal",
    "capacidades": "principal",
    "pendientes": "principal",
    "aprendido_de_mi": "ambigua",
}

# La REDACCIÓN de cada saludo, congelada literalmente y NO derivada del código.
#
# MUTANTE VIVO que cierra (auditoría, 2026-08-09): el inventario congelaba las CLAVES y nunca los
# VALORES, así que cambiar `"buen dia": "Buenos días"` por `"Buenas noches"` dejaba a AURORA
# contestando "Buenas noches" a un "buen día" con las 749 pruebas en verde. `"buen dia"` y `"hey"`
# sólo aparecían en la declaración del inventario y su redacción no se afirmaba en ninguna parte.
#
# Derivar el esperado de `_VAR_SALUDO` no serviría: el mutante cambiaría los dos lados a la vez.
_REDACCIONES_DECLARADAS = {
    "hola": "Hola",
    "hey": "Hola",
    "buenas": "Hola",
    "que tal": "Hola",
    "que tal estas": "Hola",
    "como estas": "Hola",
    "como te va": "Hola",
    "buenos dias": "Buenos días",
    "buen dia": "Buenos días",
    "buenas tardes": "Buenas tardes",
    "buenas noches": "Buenas noches",
}


def test_el_inventario_de_variantes_esta_congelado():
    """Ninguna frase entra en la lista cerrada sin declararse aquí, ni cambia de clase, ni cambia lo
    que AURORA contesta.

    El riesgo que cubre no es hipotético: la lista existe para CRECER con el uso real del CEO, y cada
    frase que se le añada deja de llegar donde llegaba antes. Esta prueba obliga a que ese cambio sea
    explícito y revisable, en vez de descubrirse en producción -que es donde se descubrió el defecto
    que originó todo el incremento-.
    """
    actual = {nombre: tuple(sorted(variantes)) for _clase, nombre, variantes in _TABLA_INTENCIONES}
    assert actual == _INVENTARIO_DECLARADO, "la lista cerrada cambió sin declararse"

    clases = {nombre: clase for clase, nombre, _variantes in _TABLA_INTENCIONES}
    assert clases == _CLASES_DECLARADAS, "una intención cambió de clase sin declararse"

    assert _VAR_SALUDO == _REDACCIONES_DECLARADAS, "la redacción de un saludo cambió sin declararse"


@pytest.mark.asyncio
@pytest.mark.parametrize("variante", sorted(_REDACCIONES_DECLARADAS))
async def test_cada_saludo_responde_con_su_propia_redaccion(sistema, variante):
    """La otra mitad del mutante anterior, medida sobre el producto y no sobre la tabla: un "buen
    día" no puede contestarse "Buenas noches". La redacción sale de la variante reconocida, nunca del
    reloj -deducir la franja horaria sería afirmar algo que el usuario no ha dicho-."""
    r = await _di(sistema.orquestador, variante)
    assert r["provider"] == "core"
    assert r["say"].startswith(f"{_REDACCIONES_DECLARADAS[variante]}."), (
        f"{variante!r} se contestó con otra redacción: {r['say']!r}"
    )


def test_ninguna_variante_colisiona_con_la_bateria_protegida_de_adr0014():
    """LO QUE EL INVENTARIO POR SÍ SOLO NO GARANTIZA (segundo apunte del auditor).

    Congelar la lista obliga a DECLARAR una ampliación, pero no impide que la ampliación declarada
    rompa algo: quien añada una variante y actualice el inventario pasa el gate igual.

    Aquí está el límite que NO se puede cruzar declarándolo: ninguna variante puede coincidir con una
    de las 24 consultas negativas de la batería oficial. Ésas son las frases que ADR-0014 existe para
    proteger, y desviarlas no es una decisión de producto -- es romper la garantía. Con el inventario
    delante, esto convierte "no robar a ADR-0014" en algo comprobable antes de llegar a producción.
    """
    negativas = {_normalizar(t) for t in _negativas_de_la_bateria()}
    colisiones = [
        (nombre, variante)
        for _clase, nombre, variantes in _TABLA_INTENCIONES
        for variante in variantes
        if variante in negativas
    ]
    assert not colisiones, f"variantes que desvían una negativa protegida por ADR-0014: {colisiones}"


@pytest.mark.asyncio
async def test_ninguna_variante_le_roba_la_respuesta_a_una_superficie_posterior(sistema):
    """EL CANDADO QUE FALTABA (rechazo de auditoría independiente).

    `test_equivalencia_...` sólo ejercita 5 de las 56 variantes, porque la batería de intención no
    contiene las demás. El auditor lo falsó con un mutante: añadir "que estas haciendo" a
    `_VAR_PENDIENTES` CAMBIA la respuesta en producción y las 730 pruebas seguían en verde.

    Esta prueba cierra el hueco por construcción y para las 56: si una variante también la reconoce
    una de las 4 superficies posteriores, Conversación General debe devolver EXACTAMENTE su mismo
    texto. Puede adelantarse a ellas -hace falta para componer el saludo-, pero no puede cambiar lo
    que responden. Añadir una variante solapada sin igualar la respuesta rompe aquí.
    """
    posteriores = (
        (_es_consulta_de_capacidades, sistema.orquestador._describir_capacidades),
        (_es_consulta_de_tareas, sistema.orquestador._describir_tareas),
        (_es_consulta_de_gobierno, sistema.orquestador._describir_bloqueo),
        (_es_consulta_de_formacion, lambda: None),
    )
    discrepancias = []
    for _clase, _nombre, variantes in _TABLA_INTENCIONES:
        for variante in variantes:
            if variante in _VARIANTES_QUE_CAMBIAN_A_PROPOSITO:
                continue
            for reconoce, responder in posteriores:
                if not reconoce(variante):
                    continue
                r = await _di(sistema.orquestador, variante)
                esperado = responder()
                if esperado is None or r["say"] != esperado:
                    discrepancias.append((variante, r["say"], esperado))
                # FORMA COMPUESTA (segundo apunte del auditor): el candado sólo probaba variantes
                # DESNUDAS, así que fijaba casos y no la propiedad. Con un saludo delante, el cuerpo
                # tiene que seguir siendo EXACTAMENTE el de la superficie: lo único que puede añadir
                # este incremento es la línea del saludo.
                compuesta = await _di(sistema.orquestador, f"hola, {variante}")
                if esperado is None or compuesta["say"] != f"Hola.\n{esperado}":
                    discrepancias.append((f"hola, {variante}", compuesta["say"], f"Hola.\n{esperado}"))
    assert not discrepancias, f"variantes que cambian lo que respondía la cascada: {discrepancias}"


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", sorted(_VARIANTES_QUE_CAMBIAN_A_PROPOSITO))
async def test_las_excepciones_declaradas_dejan_de_volcar_el_plan_de_formacion(sistema, frase):
    """La excepción de arriba no puede ser una puerta trasera: aquí se verifica que cada frase
    exceptuada cambia EN LA DIRECCIÓN declarada -pedir aclaración- y no en cualquier otra."""
    r = await _di(sistema.orquestador, frase)
    assert r["provider"] == "core"
    assert r["say"] == _ACLARACION_APRENDIDO_DE_MI, f"{frase!r} no pidió aclaración: {r['say']!r}"
    assert "APUS-5" not in r["say"]


def test_las_variantes_son_disjuntas_entre_intenciones():
    """Si una variante estuviera en dos intenciones, el orden de `_TABLA_INTENCIONES` pasaría a fijar
    precedencia -- exactamente la precedencia accidental que este proyecto ya ha pagado cuatro veces
    en la cascada de detectores. Aquí se prohíbe por construcción."""
    duenos: dict[str, str] = {}
    for _clase, nombre, variantes in _TABLA_INTENCIONES:
        for variante in variantes:
            assert variante not in duenos, f"{variante!r} está en {duenos[variante]!r} y en {nombre!r}"
            duenos[variante] = nombre


def test_todas_las_variantes_estan_normalizadas():
    """El texto del turno se compara YA normalizado (minúsculas, sin tildes). Una variante escrita
    con tilde o mayúscula no casaría NUNCA y el defecto sería invisible: la frase seguiría cayendo
    donde caía, sin error ni aviso."""
    for _clase, nombre, variantes in _TABLA_INTENCIONES:
        for variante in variantes:
            assert variante == _normalizar(variante), f"variante sin normalizar en {nombre!r}: {variante!r}"
