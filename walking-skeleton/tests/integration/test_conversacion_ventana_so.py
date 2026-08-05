"""Integración (M3 entry): la conversación debe ser la VENTANA del Sistema Operativo de AURORA.

PROBLEMA QUE RESUELVE. Antes de este incremento, preguntas como "¿qué capacidades tienes?" o
"¿en qué estás trabajando?" caían en la ausencia de memoria (ADR-0014) y AURA respondía "No tengo
ningún recuerdo registrado sobre eso" aunque la respuesta EXISTIERA en el propio sistema: el
registro de capacidades, el Estado Operativo, el Centro de Gobierno y el Plan de Formación. Eso
viola el principio de producto: si la respuesta existe en el SO, no hay que llamar al LLM ni
fingir que no hay nada que decir.

NO SE CREA NINGUNA CAPACIDAD NUEVA: se conectan cuatro fuentes que YA EXISTEN
(`registro.capacidades()`, `estado_operativo.py`, `centro_gobierno.panel()/render()`,
`PLAN-DE-FORMACION-AURORA.md`) al mismo cauce determinista que ya usan modelo de usuario,
notificaciones y reglas (ADR-0014: detección por patrones en el núcleo, nunca con el LLM).

LA TRAMPA (CHECKLIST-CONTINUIDAD.md #4.6): ya existían 8 grupos de superficies deterministas en
cascada, con precedencia por orden de escritura, y 4 defectos de interferencia verificados entre
ellas. `test_no_interferencia_las_8_superficies_previas_siguen_intactas` prueba que las 4
superficies nuevas no le roban ninguna frase a las 8 anteriores: se ejercitan una por una sobre el
MISMO orquestador, completamente conectado, con las aserciones que ya usan sus propias pruebas de
flujo (`test_modelo_usuario_flujo.py`, `test_notificaciones_flujo.py`).
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estado_operativo import Tarea
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


async def _di(orq, texto, uid="mauricio"):
    """Un turno de conversación; devuelve el resultado completo (say, provider, ...)."""
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


async def _deny(a, args, tid):
    return False


@pytest.fixture
def sistema(tmp_path):
    """El sistema COMPUESTO real (MA.1): todas las superficies conectadas como en producción."""
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg)


# --------------------------------------------------------------------------------------- capacidades --


@pytest.mark.asyncio
async def test_que_capacidades_tienes_responde_desde_el_registro_real(sistema):
    """ "¿Qué capacidades tienes?" debe leer `registro.capacidades()`, la misma fuente que
    `--verificar` imprime al arrancar -- no una lista inventada ni una llamada al LLM."""
    r = await _di(sistema.orquestador, "¿Qué capacidades tienes?")
    assert r["provider"] == "core", "debio responder el nucleo (SO), no el LLM"
    for cap in ("listar_directorio", "borrar_archivo", "encender_dispositivo"):
        assert cap in r["say"], f"falta la capacidad real '{cap}' en la respuesta: {r['say']!r}"


@pytest.mark.asyncio
async def test_que_puedes_hacer_es_la_misma_superficie_que_que_capacidades_tienes(sistema):
    r = await _di(sistema.orquestador, "¿Qué puedes hacer?")
    assert r["provider"] == "core"
    assert "listar_directorio" in r["say"]


@pytest.mark.asyncio
async def test_capacidades_no_se_delega_al_llm_ni_con_recuerdos_relacionados(sistema):
    """Guarda contra el defecto "responde bien pero SIGUE hasta el LLM" (falta de `return`): se
    siembra un recuerdo que SI haría `hits` no vacío para esta pregunta -- si el nucleo no
    cortara el turno con `return`, el flujo seguiría hasta `memory.recall`/el LLM y el resultado
    final vendría de ahí, no del registro de capacidades."""
    await sistema.memoria.write(
        "mauricio", "episodica", "hablamos de que capacidades tienes ayer", {"fuente": "conversacion"}
    )
    r = await _di(sistema.orquestador, "¿Qué capacidades tienes?")
    assert r["provider"] == "core", "el turno debio cortarse en el nucleo, no seguir hasta el LLM"
    assert "listar_directorio" in r["say"]


# -------------------------------------------------------------------------------------------- tareas --


@pytest.mark.asyncio
async def test_en_que_estas_trabajando_responde_desde_estado_operativo(sistema):
    """El Estado Operativo (`estado_operativo.py`) es la fuente; nunca se inventa trabajo."""
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
    r = await _di(sistema.orquestador, "¿En qué estás trabajando?")
    assert r["provider"] == "core"
    assert "escribir el ADR de la ventana del SO" in r["say"]


@pytest.mark.asyncio
async def test_sin_objetivos_activos_declara_ausencia_no_fabrica_trabajo(sistema):
    """INV-9: sin ningún objetivo activo, se declara la ausencia -- no se simula estar trabajando."""
    r = await _di(sistema.orquestador, "¿Qué tareas tienes?")
    assert r["provider"] == "core"
    assert "ningún objetivo activo" in r["say"] or "ningun objetivo activo" in r["say"].lower()


@pytest.mark.asyncio
async def test_sin_estado_operativo_conectado_la_pregunta_sigue_el_flujo_normal():
    """Si el componente ni siquiera está conectado (Orchestrator construido a mano, como antes de
    este incremento), la pregunta NO debe romper nada: sigue el camino que ya existía (ausencia
    de memoria, ADR-0014), igual que cualquier otra pregunta sin superficie dedicada."""
    orq = Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([MockProvider("m", 1)], 1200),
        PermissionManager(_deny),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )
    r = await _di(orq, "¿En qué estás trabajando?")
    assert r["provider"] == "core"
    assert "recuerdo" in r["say"].lower()


# ----------------------------------------------------------------------------------- centro de gobierno --


@pytest.mark.asyncio
async def test_por_que_estas_bloqueada_responde_desde_el_centro_de_gobierno(sistema):
    """Reutiliza `centro_gobierno.panel()/render()` sobre el Estado Operativo real: no se duplica
    el cálculo de bloqueos en el orquestador."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="desplegar el incremento",
            estado="bloqueada",
            responsable="qa",
            origen="ceo",
            bloqueos=["veredicto negativo: 2 garantias ya no protegen nada"],
        )
    )
    r = await _di(sistema.orquestador, "¿Por qué estás bloqueada?")
    assert r["provider"] == "core"
    assert "1 tarea" in r["say"] and "detenidas" in r["say"]


@pytest.mark.asyncio
async def test_que_esta_pasando_es_la_misma_superficie_que_por_que_estas_bloqueada(sistema):
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="desplegar el incremento",
            estado="bloqueada",
            responsable="qa",
            origen="ceo",
            bloqueos=["veredicto negativo: 2 garantias ya no protegen nada"],
        )
    )
    r = await _di(sistema.orquestador, "¿Qué está pasando?")
    assert r["provider"] == "core"
    assert "detenidas" in r["say"]


# ------------------------------------------------------------------------------------- plan de formación --


@pytest.mark.asyncio
async def test_que_aprendiste_responde_desde_el_plan_de_formacion_real(sistema):
    """Lee `PLAN-DE-FORMACION-AURORA.md` (raíz del repo) tal cual está escrito: no se resume con
    el LLM ni se inventa contenido (INV-9)."""
    r = await _di(sistema.orquestador, "¿Qué aprendiste?")
    assert r["provider"] == "core"
    assert "Aprendidas" in r["say"]
    assert len(r["say"]) > 80, "la respuesta parece vacia o truncada"


# --------------------------------------------------------------------------- prueba de NO INTERFERENCIA --


@pytest.mark.asyncio
async def test_no_interferencia_las_8_superficies_previas_siguen_intactas(sistema):
    """Las 8 superficies deterministas previas (CHECKLIST-CONTINUIDAD.md #4.6: modelo de usuario
    ver/porqué/refuta/olvida, notificaciones, y reglas ver/crear/cancelar) más la ausencia de
    memoria (ADR-0014) deben responder EXACTAMENTE igual con las 4 superficies nuevas conectadas
    en el MISMO orquestador. Si una frase nueva le hubiera robado un patrón a una vieja, alguna de
    estas aserciones fallaría.

    ORDEN DELIBERADO: el bloque de Modelo de Usuario se ejercita ANTES que "deja de guardar copia
    cuando borre un archivo" (reglas: cancelación): esa frase contiene "deja de", que la captura de
    señales de M3.0 (`conectores/conversacion.py`) clasifica como `FEEDBACK_DIRECTO` y escribe en
    memoria semántica -- comportamiento real y correcto del sistema, pero ajeno a esta prueba. Si
    corriera antes, contaminaría "¿qué sabes de mí?" con una entrada que esta prueba no sembró.
    """
    orq = sistema.orquestador

    # --- Notificaciones: sin actividad, no se fabrica ningún aviso -------------------------
    r = await _di(orq, "¿qué ha pasado mientras no estaba?")
    assert r["provider"] == "core"
    assert r["say"] == "No ha pasado nada relevante mientras no estabas."

    # --- Modelo de usuario: ver (sin nada declarado aún) ----------------------------------------
    r = await _di(orq, "¿qué sabes de mí?")
    assert r["provider"] == "core"
    assert r["say"] == "Todavía no sé nada sobre ti."

    # --- Modelo de usuario: sembrar y volver a ver ----------------------------------------------
    await sistema.memoria.write(
        "mauricio", "semantica", "prefiere trabajar de noche", {"origen": "declarada", "fuente": "usuario"}
    )
    await sistema.memoria.write(
        "mauricio", "semantica", "suele posponer los correos", {"origen": "observada", "fuente": "conversacion"}
    )
    r = await _di(orq, "¿qué sabes de mí?")
    assert r["provider"] == "core"
    assert "prefiere trabajar de noche (me lo dijiste)" in r["say"]
    assert "suele posponer los correos (lo he observado)" in r["say"]

    # --- Modelo de usuario: por qué (el foco es lo observado) -----------------------------------
    r = await _di(orq, "¿Por qué dices eso?")
    assert r["provider"] == "core"
    assert "observado" in r["say"].lower() and "correos" in r["say"].lower()

    # --- Modelo de usuario: refutar ---------------------------------------------------------------
    r = await _di(orq, "Eso ya no es cierto.")
    assert r["provider"] == "core"
    assert "corrijo" in r["say"].lower()

    # --- Modelo de usuario: olvidar ----------------------------------------------------------------
    r = await _di(orq, "Olvida eso.")
    assert r["provider"] == "core"
    assert "hecho" in r["say"].lower()

    # --- Reglas: consulta -------------------------------------------------------------------
    r = await _di(orq, "¿qué automatizaciones tengo?")
    assert r["provider"] == "core"
    assert r["say"] == "No tienes ninguna automatización activa."

    # --- Reglas: creación ---------------------------------------------------------------------
    r = await _di(orq, "cada vez que borres un archivo guarda una copia")
    assert r["provider"] == "core"
    assert r["say"] == "Entendido. Lo haré a partir de ahora."

    # --- Reglas: cancelación ------------------------------------------------------------------
    r = await _di(orq, "deja de guardar copia cuando borre un archivo")
    assert r["provider"] == "core"
    assert "desactivado" in r["say"].lower()

    # --- Ausencia de memoria (ADR-0014): una pregunta genérica sin relación con nada de arriba ----
    r = await _di(orq, "¿Cuál es la capital de Francia?")
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso."
