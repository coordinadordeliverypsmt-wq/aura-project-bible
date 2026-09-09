"""Integración (CEO, 2026-09-01): una pregunta llega al dominio que puede responderla.

## La causa raíz, que no era ninguna de las frases

    tu> ¿Qué son D-ORCH-6 y D-INT-1?          AURA> Entendido.
    tu> ¿Qué oportunidades tengo bloqueadas?  AURA> No tengo ningun recuerdo registrado sobre eso.

Dos respuestas distintas, un solo defecto: **no existía un dominio por defecto para «no sé a qué
dominio pertenece esto»**. La cascada terminaba en

    hits = memory.recall(text)
    if not hits and _es_consulta_de_memoria(text):  → "no tengo ningún recuerdo"
    else                                           → proveedor  → "Entendido."

y `_es_consulta_de_memoria` acaba en `or _es_pregunta(texto)`. De modo que **toda interrogativa que
nadie hubiera reclamado antes caía en la memoria del usuario**, y todo lo demás en el proveedor. No
faltaban los datos: `estado.json` tenía las dos decisiones con sus opciones y las seis oportunidades
bloqueadas con su motivo. Faltaba la puerta que llevara hasta ellos.

## Qué prueba este fichero

La **matriz de enrutamiento**: para cada entrada, qué fuente respondió. Y se comprueba por el campo
`dominio` del turno, no por el texto de la respuesta: acertar el texto por casualidad es exactamente
como un enrutamiento roto pasa desapercibido.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer


async def _di(orq, texto, uid="mauricio"):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


#: Una instantánea con la FORMA de la real (copiada de una salida de `aura.py estado --json`), para
#: que la batería no dependa del ciclo autónomo del equipo que la ejecuta.
INSTANTANEA = {
    "estado": "DECISION_REQUIRED",
    "ultimo_ciclo": 101, "hora_ultimo_ciclo": "2026-09-01T22:00:01",
    "cola": {"OPORTUNIDAD_REAL": 0, "BLOQUEADA": 6, "DECISION_REQUIRED": 2, "FALSO_HUECO": 0},
    "trabajo_bloqueado": 6, "trabajo_elevado": 2, "proximo_despertar": "2026-09-01T23:00:00",
    "decisiones_pendientes": [
        {"id": "D-ORCH-6", "titulo": "WAITING_FOR_HUMAN es inalcanzable",
         "por_que_no_la_resuelvo": "modificar la tabla de estados es decidir sobre el gobierno",
         "opciones": ["(a) anadirlo como destino de WORKING", "(b) retirarlo del vocabulario"],
         "impacto_hoy": "NINGUNO"},
        {"id": "D-INT-1", "titulo": "Integrar la rama arrastra 17 commits ajenos", "opciones": ["(a) integrar"]},
    ],
    "oportunidades_bloqueadas": [
        {"id": "OB-1", "que": "F5 · RevisorExterno", "por_que": "el §20 del DP la marca Bloqueada",
         "quien_desbloquea": "CEO", "ejecutable_hoy": False},
        {"id": "OB-2", "que": "defecto del auditor de garantias", "por_que": "vive fuera del perimetro",
         "quien_desbloquea": "CEO", "ejecutable_hoy": False},
    ],
    "trabajos_recientes": [
        {"id": "P-015", "simbolo": "_privadas_sin_uso", "fichero": "/x/descubrimiento.py",
         "resultado": "efecto verificado", "momento": "2026-08-31T21:38:40"},
        {"id": "P-016", "simbolo": "_quitar_funcion", "fichero": "/x/autoconstruccion.py",
         "resultado": "efecto verificado", "momento": "2026-08-31T21:44:43"},
    ],
    "ultima_tarea": {"id": "P-016", "simbolo": "_quitar_funcion", "fichero": "/x/autoconstruccion.py",
                     "resultado": "efecto verificado", "autorizada_por": "REVIEW:auditor",
                     "momento": "2026-08-31T21:44:43"},
    "sospecha": "",
}


class FuenteFalsa:
    def __init__(self, inst=None):
        self._inst = INSTANTANEA if inst is None else inst
        self.lecturas = 0

    def instantanea(self):
        self.lecturas += 1
        return self._inst


@pytest.fixture
def sistema(tmp_path):
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(cfg)
    s.orquestador.estado_autonomo = FuenteFalsa()
    return s


# ============================================================ LA MATRIZ --

MATRIZ = [
    # aritmética
    ("cuanto es 1+1", "aritmetica"),
    ("cuanto es 10+10", "aritmetica"),
    # estado autónomo
    ("¿en qué estás trabajando?", "estado_autonomo"),
    ("¿cuál es tu estado?", "estado_autonomo"),
    # historial / evolución
    ("¿cuál fue tu última tarea?", "historial"),
    ("¿qué hiciste?", "historial"),
    ("¿qué hiciste hoy?", "evolucion"),
    ("¿qué mejoraste?", "evolucion"),
    ("¿qué hiciste para evolucionar?", "evolucion"),
    # decisiones
    ("¿qué es D-ORCH-6?", "decisiones"),
    ("¿qué opciones tiene D-ORCH-6?", "decisiones"),
    ("¿qué son D-ORCH-6 y D-INT-1?", "decisiones"),
    ("¿qué decisiones necesitan de mí?", "decisiones"),
    # oportunidades
    ("¿qué oportunidades están bloqueadas?", "oportunidades"),
    ("¿por qué están bloqueadas?", "oportunidades"),
    ("¿qué trabajo tienes disponible?", "oportunidades"),
    # capacidades y cortesía
    ("hola", "conversacion_general"),
    ("¿qué capacidades tienes?", "conversacion_general"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("entrada", "dominio"), MATRIZ)
async def test_cada_entrada_llega_a_SU_dominio(sistema, entrada, dominio):
    """Se comprueba por el `dominio` del turno, no por el texto: acertar el texto por casualidad es
    como un enrutamiento roto pasa desapercibido."""
    r = await _di(sistema.orquestador, entrada)
    assert r["dominio"] == dominio, f"{entrada!r} fue a {r['dominio']!r}, se esperaba {dominio!r}"
    assert r["provider"] == "core", f"{entrada!r} acabó en el modelo"


@pytest.mark.asyncio
@pytest.mark.parametrize("entrada", [e for e, d in MATRIZ if d not in ("aritmetica", "conversacion_general")])
async def test_NINGUNA_de_esas_preguntas_cae_en_MEMORIA(sistema, entrada):
    """El defecto original, dicho como propiedad: ninguna de estas pertenece al dominio «buscar
    recuerdos», y ninguna puede volver a aterrizar ahí."""
    r = await _di(sistema.orquestador, entrada)
    assert r["dominio"] != "memoria", f"{entrada!r} volvió a caer en la memoria del usuario"
    assert "no tengo ningun recuerdo" not in r["say"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("entrada", ["¿qué es D-ORCH-6?", "¿qué oportunidades están bloqueadas?",
                                     "¿qué hiciste hoy?", "¿en qué estás trabajando?"])
async def test_esas_respuestas_LEEN_la_fuente_real(sistema, entrada):
    """No basta con no caer en memoria: hay que haber leído el estado autónomo. Una respuesta que
    acertara sin consultarlo sería el mismo defecto con mejor suerte."""
    sistema.orquestador.estado_autonomo.lecturas = 0
    await _di(sistema.orquestador, entrada)
    assert sistema.orquestador.estado_autonomo.lecturas >= 1, f"{entrada!r} respondió sin leer la fuente"


# ============================================================ EL CONTENIDO ES REAL --

@pytest.mark.asyncio
async def test_una_DECISION_se_describe_con_sus_opciones_reales(sistema):
    r = await _di(sistema.orquestador, "¿qué opciones tiene D-ORCH-6?")
    assert "D-ORCH-6" in r["say"]
    assert "(a) anadirlo como destino de WORKING" in r["say"]
    assert "(b) retirarlo del vocabulario" in r["say"]
    assert "modificar la tabla de estados" in r["say"], "también por qué no la resuelve sola"


@pytest.mark.asyncio
async def test_una_decision_INEXISTENTE_no_se_inventa(sistema):
    r = await _di(sistema.orquestador, "¿qué es D-NO-EXISTE-9?")
    assert "No encuentro una decisión llamada D-NO-EXISTE-9" in r["say"]


@pytest.mark.asyncio
async def test_las_OPORTUNIDADES_se_describen_con_su_motivo_y_quien_desbloquea(sistema):
    """«6 bloqueadas» sin decir cuáles ni por qué es medio informe: el dato que sirve para
    desbloquearlas es quién puede hacerlo."""
    r = await _di(sistema.orquestador, "¿qué oportunidades están bloqueadas?")
    assert "OB-1" in r["say"] and "OB-2" in r["say"]
    assert "el §20 del DP la marca Bloqueada" in r["say"]
    assert "CEO" in r["say"]
    assert "no tengo ninguna oportunidad ejecutable" in r["say"].lower()


@pytest.mark.asyncio
async def test_la_EVOLUCION_sale_del_historial_y_no_de_la_conversacion(sistema):
    await _di(sistema.orquestador, "acabo de pintar la casa de azul")
    r = await _di(sistema.orquestador, "¿qué mejoraste?")
    assert "_quitar_funcion" in r["say"] and "autoconstruccion.py" in r["say"]
    assert "azul" not in r["say"]


@pytest.mark.asyncio
async def test_sin_datos_NINGUNA_superficie_fabrica_nada(sistema):
    """Con una instantánea vacía, las tres declaran la ausencia. Ninguna rellena el hueco."""
    sistema.orquestador.estado_autonomo = FuenteFalsa({"estado": "NO DISPONIBLE"})
    for entrada, marca in [("¿qué decisiones necesitan de mí?", "no me consta"),
                           ("¿qué hiciste hoy?", "no me consta"),
                           ("¿qué oportunidades están bloqueadas?", "no me consta")]:
        r = await _di(sistema.orquestador, entrada)
        assert marca in r["say"].lower(), f"{entrada!r} -> {r['say']!r}"


@pytest.mark.asyncio
async def test_el_tablero_del_producto_NO_se_mezcla_con_el_motor(sistema):
    """Son dos planos. Sumarlos daría un total que no existe en ninguno de los dos."""
    r = await _di(sistema.orquestador, "¿qué oportunidades están bloqueadas?")
    assert "tablero de objetivos" not in r["say"]


# ============================================================ AUTORIZACIÓN: SIGUE SIENDO ESTRICTA --

@pytest.mark.asyncio
@pytest.mark.parametrize(("entrada", "dominio"), [
    ("Autorizo D-ORCH-6", "autorizacion"),          # inequívoca -> su dominio
    ("¿Puedes ejecutar D-ORCH-6?", "decisiones"),   # una pregunta NO autoriza: es una consulta
    ("Autorizo D-ORCH-6 si te parece bien", "decisiones"),   # condicionada: no autoriza
    ("Haz D-ORCH-6", "decisiones"),                 # una orden no es un permiso
])
async def test_solo_la_autorizacion_INEQUIVOCA_autoriza(sistema, entrada, dominio):
    """Y las demás, en vez de caer en memoria como antes, aterrizan en el dominio de decisiones —
    que es donde de verdad pertenecen."""
    r = await _di(sistema.orquestador, entrada)
    assert r["dominio"] == dominio, f"{entrada!r} fue a {r['dominio']!r}"


# ============================================================ CONOCIMIENTO GENERAL Y FALLBACK --

@pytest.mark.asyncio
async def test_el_conocimiento_general_y_la_puerta_de_ADR_0014(sistema):
    """QUÉ VERIFICA ESTA PRUEBA, explícitamente: el ENRUTAMIENTO, no la calidad de la respuesta.

    Dos mitades, y las dos son medidas, no deseadas:

    1. **Cuando el recall acierta**, la pregunta llega al proveedor — que es donde el diseño actual
       pone el conocimiento general. Que el `MockProvider` conteste «Entendido.» es comportamiento
       del mock, NO una capacidad del sistema; con un proveedor real la respuesta sería otra, y este
       test no la simula.

    2. **Cuando el recall no acierta** —el caso de «¿de qué color es el cielo?»— la pregunta NO llega
       al proveedor: la intercepta la puerta de ADR-0014, que trata toda interrogativa sin dueño como
       una consulta de memoria. Eso es un enrutamiento a un dominio incorrecto, y está reportado como
       **DECISION_REQUIRED**: estrechar esa puerta baja la garantía declarada de 70/77 a 67/77
       (medido sobre `tests/datos/bateria_memoria.json`) y además clasifica «¿quién escribió el
       Quijote?» como personal. No hay discriminador determinista barato, y elegir entre «AURA nunca
       inventa sobre ti» y «AURA responde del mundo» no es una decisión que me corresponda.
    """
    await _di(sistema.orquestador, "mi color favorito es el azul")
    con_recall = await _di(sistema.orquestador, "¿cuál es mi color favorito?")
    assert con_recall["dominio"] == "llm", "con recuerdos, la pregunta llega al proveedor"
    assert con_recall["provider"] != "core"

    sin_recall = await _di(sistema.orquestador, "¿de qué color es el cielo?")
    assert sin_recall["dominio"] == "memoria", (
        "comportamiento MEDIDO hoy, no deseado: sin recall la puerta de ADR-0014 la intercepta")
    assert "no tengo ningun recuerdo" in sin_recall["say"].lower()


def test_un_say_VACIO_del_proveedor_no_se_convierte_en_una_confirmacion():
    """`«Entendido.»` afirma que se atendió algo. Cuando el modelo no dice nada, el usuario no tiene
    forma de distinguir esa confirmación de una respuesta real."""
    from aura_skeleton.core.orchestrator import _parse_decision

    _accion, _args, say = _parse_decision('{"action":"consulta","args":{},"say":""}', "t1")
    assert say != "Entendido."
    assert "no he sabido" in say.lower()


# ============================================================ REGRESIÓN --

@pytest.mark.asyncio
async def test_regresion_la_MEMORIA_sigue_siendo_de_la_memoria(sistema):
    """Lo que SÍ es una consulta de memoria tiene que seguir siéndolo: el arreglo no puede
    vaciar el dominio que funcionaba."""
    await _di(sistema.orquestador, "me llamo Mauricio")
    r = await _di(sistema.orquestador, "¿cuál es mi nombre?")
    assert "mauricio" in r["say"].lower()
    r2 = await _di(sistema.orquestador, "¿qué acordamos sobre el presupuesto?")
    assert r2["dominio"] in ("memoria", "llm"), f"salió del dominio de memoria: {r2['dominio']!r}"


@pytest.mark.asyncio
async def test_regresion_SIN_estado_autonomo_las_tres_superficies_no_se_activan(sistema):
    """El producto se instala sin plano de desarrollo. Sin fuente, estas preguntas siguen el camino
    que tenían antes de este bloque — no se responde con un hueco."""
    sistema.orquestador.estado_autonomo = None
    for entrada in ("¿qué es D-ORCH-6?", "¿qué oportunidades están bloqueadas?", "¿qué hiciste hoy?"):
        r = await _di(sistema.orquestador, entrada)
        assert r["dominio"] not in ("decisiones", "oportunidades", "evolucion"), entrada
