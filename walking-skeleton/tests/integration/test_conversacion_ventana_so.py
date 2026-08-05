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

RECHAZO DE AUDITORÍA INDEPENDIENTE (corregido en esta versión):
  - Defecto 1 (bloqueante): las aserciones eran decorativas (subcadenas genéricas como "1 tarea" o
    "Aprendidas" + longitud), satisfechas por CUALQUIER constante fabricada. Ahora cada prueba
    compara contra el DATO SEMBRADO o contra la fuente real leída de forma independiente en la
    propia prueba (nunca reimportando la función bajo prueba como oráculo de sí misma).
  - Defecto 2 (bloqueante): los detectores nuevos no discriminaban sujeto ("¿qué está pasando con
    mi pedido de Amazon?" volcaba el Centro de Gobierno). Se añaden pruebas NEGATIVAS que exigen
    que esas frases NO activen las superficies nuevas y sigan el flujo previo (ausencia de
    memoria, ADR-0014).
  - Defecto 3 (menor): un `UnicodeDecodeError` al leer el Plan de Formación reventaba el turno.
    Se cubre con un fichero de codificación inválida.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core import orchestrator as orch_mod
from aura_skeleton.core.centro_gobierno import panel as panel_real
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


def _texto_de(secciones, *sufijos: str) -> str:
    """Réplica DELIBERADA, en la prueba, del formato de `Orchestrator._resumen_de`: sirve de
    oráculo independiente construido sobre `centro_gobierno.panel()` -la fuente real-, no sobre la
    respuesta del orquestador. Si el orquestador ignorase el filtro de secciones o fabricase texto,
    dejaría de coincidir con esto."""
    filtradas = [s for s in secciones if any(s.titulo.endswith(suf) for suf in sufijos)]
    return "\n".join(f"• {s.titulo}: {s.contenido}" for s in filtradas)


@pytest.fixture
def sistema(tmp_path):
    """El sistema COMPUESTO real (MA.1): todas las superficies conectadas como en producción."""
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg)


def _sin_estado_operativo():
    """Orchestrator construido a mano SIN estado_operativo ni automatizaciones: el camino que ya
    existía antes de este incremento para cualquier pregunta sin superficie dedicada."""
    return Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([MockProvider("m", 1)], 1200),
        PermissionManager(_deny),
        VoiceAdapterMock(),
        HomeAssistantMock(),
    )


# --------------------------------------------------------------------------------------- capacidades --


@pytest.mark.asyncio
async def test_que_capacidades_tienes_responde_desde_el_registro_real(sistema):
    """ "¿Qué capacidades tienes?" debe leer `registro.capacidades()` -TODAS, no una muestra- y el
    conteo debe ser el REAL. Una lista fabricada de 3 nombres (aunque reales) no basta: aquí se
    exige la lista COMPLETA que el sistema compuesto tiene de verdad, derivada del propio fixture,
    nunca de una constante escrita en la prueba."""
    reales = sistema.registro_adaptadores.capacidades()
    assert len(reales) > 3, "guarda de cordura: si el catálogo se redujera a <=3, esta prueba no discriminaría nada"

    r = await _di(sistema.orquestador, "¿Qué capacidades tienes?")
    assert r["provider"] == "core", "debio responder el nucleo (SO), no el LLM"
    assert f"Tengo {len(reales)} capacidad(es) registradas" in r["say"], (
        f"el conteo declarado no coincide con las {len(reales)} capacidades reales: {r['say']!r}"
    )
    for cap in sorted(reales):
        assert cap in r["say"], f"falta la capacidad real '{cap}' en la respuesta: {r['say']!r}"


@pytest.mark.asyncio
async def test_que_puedes_hacer_es_la_misma_superficie_que_que_capacidades_tienes(sistema):
    reales = sistema.registro_adaptadores.capacidades()
    r = await _di(sistema.orquestador, "¿Qué puedes hacer?")
    assert r["provider"] == "core"
    for cap in sorted(reales):
        assert cap in r["say"]


@pytest.mark.asyncio
async def test_capacidades_no_se_delega_al_llm_ni_con_recuerdos_relacionados(sistema):
    """Guarda contra el defecto "responde bien pero SIGUE hasta el LLM" (falta de `return`): se
    siembra un recuerdo que SI haría `hits` no vacío para esta pregunta -- si el nucleo no
    cortara el turno con `return`, el flujo seguiría hasta `memory.recall`/el LLM y el resultado
    final vendría de ahí, no del registro de capacidades."""
    await sistema.memoria.write(
        "mauricio", "episodica", "hablamos de que capacidades tienes ayer", {"fuente": "conversacion"}
    )
    reales = sistema.registro_adaptadores.capacidades()
    r = await _di(sistema.orquestador, "¿Qué capacidades tienes?")
    assert r["provider"] == "core", "el turno debio cortarse en el nucleo, no seguir hasta el LLM"
    for cap in sorted(reales):
        assert cap in r["say"]


# -------------------------------------------------------------------------------------------- tareas --


@pytest.mark.asyncio
async def test_en_que_estas_trabajando_responde_desde_estado_operativo(sistema):
    """El Estado Operativo (`estado_operativo.py`) es la fuente; nunca se inventa trabajo. Se
    compara contra `panel()` calculado de forma independiente en la prueba (fuente real), no
    contra una subcadena genérica."""
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
    secciones_reales = panel_real(
        estado=sistema.estado_operativo, objetivo=sistema.estado_operativo.objetivos_activos()
    )
    esperado = _texto_de(secciones_reales, "Que esta haciendo", "Que hara despues", "Progreso")

    r = await _di(sistema.orquestador, "¿En qué estás trabajando?")
    assert r["provider"] == "core"
    assert esperado in r["say"], f"la respuesta no refleja el panel REAL: {r['say']!r}"
    assert "escribir el ADR de la ventana del SO" in r["say"]


@pytest.mark.asyncio
async def test_tareas_y_bloqueo_no_devuelven_lo_mismo_el_filtro_de_secciones_se_respeta(sistema):
    """Kill del mutante "el filtro de `_resumen_de` se ignora": con una tarea ABIERTA y otra
    BLOQUEADA en el mismo objetivo, "en qué trabajas" y "por qué bloqueada" deben traer secciones
    DISTINTAS. Si el filtro se ignorase, ambas respuestas incluirían el mismo texto completo del
    panel (tareas Y bloqueos mezclados)."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-abierta",
            descripcion="escribir el ADR de la ventana del SO",
            estado="abierta",
            responsable="programador",
            origen="ceo",
        )
    )
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-bloqueada",
            descripcion="desplegar el incremento",
            estado="bloqueada",
            responsable="qa",
            origen="ceo",
            bloqueos=["veredicto negativo: 2 garantias ya no protegen nada"],
        )
    )

    r_tareas = await _di(sistema.orquestador, "¿En qué estás trabajando?")
    r_bloqueo = await _di(sistema.orquestador, "¿Por qué estás bloqueada?")
    assert r_tareas["provider"] == r_bloqueo["provider"] == "core"
    assert r_tareas["say"] != r_bloqueo["say"], "tareas y bloqueo devolvieron LO MISMO: el filtro no se aplicó"

    # Positivo: cada respuesta trae SU sección propia.
    assert "Que esta haciendo" in r_tareas["say"]
    assert "Que esta bloqueado" in r_bloqueo["say"]
    # Negativo: ninguna respuesta se cuela en el dominio de la otra.
    assert "Riesgos activos" not in r_tareas["say"], "tareas se coló con contenido de bloqueo"
    assert "Recomendaciones derivadas" not in r_tareas["say"], "tareas se coló con contenido de bloqueo"
    assert "Que esta haciendo" not in r_bloqueo["say"], "bloqueo se coló con contenido de tareas"
    assert "Progreso" not in r_bloqueo["say"], "bloqueo se coló con contenido de tareas"


@pytest.mark.asyncio
async def test_sin_objetivos_activos_declara_ausencia_no_fabrica_trabajo(sistema):
    """INV-9: sin ningún objetivo activo, se declara la ausencia EXACTA -- no una aproximación."""
    r = await _di(sistema.orquestador, "¿Qué tareas tienes?")
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningún objetivo activo registrado en el estado operativo ahora mismo."


@pytest.mark.asyncio
async def test_sin_estado_operativo_conectado_la_pregunta_sigue_el_flujo_normal():
    """Si el componente ni siquiera está conectado (Orchestrator construido a mano, como antes de
    este incremento), la pregunta NO debe romper nada: sigue el camino que ya existía (ausencia
    de memoria, ADR-0014), igual que cualquier otra pregunta sin superficie dedicada."""
    orq = _sin_estado_operativo()
    r = await _di(orq, "¿En qué estás trabajando?")
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso."


# ----------------------------------------------------------------------- guarda de dominio: tareas --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    [
        "¿qué estás haciendo con mis archivos?",
        "¿en qué trabajas con mi proyecto?",
    ],
)
async def test_tareas_con_objeto_ajeno_no_se_intercepta(sistema, frase):
    """Regresión de la auditoría independiente: "¿qué estás haciendo con mis archivos?" volcaba el
    Estado Operativo. La frase habla de algo que el USUARIO posee (sus archivos), no del trabajo de
    AURORA: debe seguir el flujo previo (ausencia de memoria), exactamente como ANTES de este
    incremento -- contestar mal es peor que no responder."""
    sistema.estado_operativo.registrar(
        Tarea(objetivo_id="obj-1", tarea_id="t-1", descripcion="tarea interna", estado="abierta", origen="ceo")
    )
    r = await _di(sistema.orquestador, frase)
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso.", (
        f"'{frase}' activó la ventana del SO en vez de seguir el flujo previo: {r['say']!r}"
    )
    assert "tarea interna" not in r["say"]


# ----------------------------------------------------------------------------------- centro de gobierno --


@pytest.mark.asyncio
async def test_por_que_estas_bloqueada_responde_desde_el_centro_de_gobierno(sistema):
    """Reutiliza `centro_gobierno.panel()/render()` sobre el Estado Operativo real: se compara
    contra ese cálculo independiente, no contra subcadenas genéricas como "1 tarea"/"detenidas"
    (que un texto fijo también satisface)."""
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
    secciones_reales = panel_real(
        estado=sistema.estado_operativo, objetivo=sistema.estado_operativo.objetivos_activos()
    )
    esperado = _texto_de(secciones_reales, "Que esta bloqueado", "Riesgos activos", "Recomendaciones derivadas")

    r = await _di(sistema.orquestador, "¿Por qué estás bloqueada?")
    assert r["provider"] == "core"
    assert esperado in r["say"], f"la respuesta no refleja el panel REAL: {r['say']!r}"
    # Derivado especificamente del RESPONSABLE sembrado ('qa'): un texto fijo no podria adivinarlo.
    assert "'qa'" in r["say"], "la recomendacion no refleja el responsable REAL del bloqueo"


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
    secciones_reales = panel_real(
        estado=sistema.estado_operativo, objetivo=sistema.estado_operativo.objetivos_activos()
    )
    esperado = _texto_de(secciones_reales, "Que esta bloqueado", "Riesgos activos", "Recomendaciones derivadas")

    r = await _di(sistema.orquestador, "¿Qué está pasando?")
    assert r["provider"] == "core"
    assert esperado in r["say"]


@pytest.mark.asyncio
async def test_sin_objetivos_activos_el_bloqueo_declara_ausencia_exacta(sistema):
    r = await _di(sistema.orquestador, "¿Por qué estás bloqueada?")
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningún objetivo activo, así que no hay nada bloqueado ahora mismo."


# --------------------------------------------------------------------- guarda de dominio: gobierno --


@pytest.mark.asyncio
async def test_gobierno_con_objeto_ajeno_no_se_intercepta(sistema):
    """Regresión de la auditoría: "¿qué está pasando con mi pedido de Amazon?" volcaba el Centro de
    Gobierno. Habla de un pedido del USUARIO, no del estado de AURORA."""
    sistema.estado_operativo.registrar(
        Tarea(
            objetivo_id="obj-1",
            tarea_id="t-1",
            descripcion="desplegar",
            estado="bloqueada",
            responsable="qa",
            origen="ceo",
            bloqueos=["motivo interno"],
        )
    )
    r = await _di(sistema.orquestador, "¿qué está pasando con mi pedido de Amazon?")
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso.", (
        f"la frase activó el Centro de Gobierno en vez de seguir el flujo previo: {r['say']!r}"
    )
    assert "motivo interno" not in r["say"]


# ------------------------------------------------------------------------------------- plan de formación --


@pytest.mark.asyncio
async def test_que_aprendiste_responde_desde_el_plan_de_formacion_real(sistema):
    """Lee `PLAN-DE-FORMACION-AURORA.md` (raíz del repo) TAL CUAL está escrito: se compara contra
    la sección leída de forma INDEPENDIENTE en la propia prueba (no reimportando la función bajo
    prueba), para que un resumen inventado -aunque contenga la palabra "Aprendidas" y sea largo- no
    pueda pasar."""
    ruta = orch_mod._ruta_plan_formacion()
    contenido_real = ruta.read_text(encoding="utf-8")
    lineas = contenido_real.splitlines()
    inicio = next(i for i, linea in enumerate(lineas) if linea.startswith("## ") and "Aprendidas" in linea)
    fin = next((i for i in range(inicio + 1, len(lineas)) if lineas[i].startswith("## ")), len(lineas))
    seccion_real = "\n".join(lineas[inicio:fin]).strip()
    assert "Coordinar su propio backlog" in seccion_real, (
        "guarda de cordura: el fichero real cambió de forma inesperada"
    )

    r = await _di(sistema.orquestador, "¿Qué aprendiste?")
    assert r["provider"] == "core"
    assert r["say"] == seccion_real, "la respuesta no es la sección REAL del Plan de Formación"


@pytest.mark.asyncio
async def test_formacion_con_fichero_ausente_declara_ausencia_no_fabrica(monkeypatch, tmp_path):
    """Cubre la rama de ausencia de `_resumen_formacion` (fichero inexistente): declara, no inventa
    un resumen plausible de lo que AURORA "debería" haber aprendido."""
    ruta_falsa = tmp_path / "no-existe.md"
    monkeypatch.setattr(orch_mod, "_ruta_plan_formacion", lambda: ruta_falsa)
    assert orch_mod._resumen_formacion() == (
        "No encuentro el Plan de Formación en el repositorio; no puedo declarar qué he aprendido."
    )


@pytest.mark.asyncio
async def test_formacion_sin_seccion_aprendidas_declara_ausencia_no_fabrica(monkeypatch, tmp_path):
    """Cubre la rama de ausencia de `_resumen_formacion` (fichero presente, sin sección "Aprendidas")."""
    ruta = tmp_path / "plan-sin-seccion.md"
    ruta.write_text("# Plan de Formación\n\n## Otra cosa\n\ncontenido irrelevante\n", encoding="utf-8")
    monkeypatch.setattr(orch_mod, "_ruta_plan_formacion", lambda: ruta)
    assert orch_mod._resumen_formacion() == (
        "El Plan de Formación existe pero no tiene una sección de capacidades aprendidas."
    )


@pytest.mark.asyncio
async def test_formacion_con_codificacion_invalida_no_revienta_el_turno(monkeypatch, tmp_path):
    """Defecto menor de la auditoría: `UnicodeDecodeError` (subclase de `ValueError`, no de
    `OSError`) al leer un fichero con bytes que no son UTF-8 válido. Antes de la corrección, esto
    reventaba el turno entero -ni declaraba ausencia ni fabricaba, explotaba-."""
    ruta = tmp_path / "plan-binario.md"
    ruta.write_bytes(b"\xff\xfe\x00\x01 bytes que no son utf-8 valido")
    monkeypatch.setattr(orch_mod, "_ruta_plan_formacion", lambda: ruta)
    assert orch_mod._resumen_formacion() == (
        "No encuentro el Plan de Formación en el repositorio; no puedo declarar qué he aprendido."
    )


@pytest.mark.asyncio
async def test_formacion_con_objeto_ajeno_no_se_intercepta(sistema):
    """Regresión de la auditoría: "¿qué has aprendido de mí?" volcaba el Plan de Formación completo
    -incluidas notas internas sobre APUS-5-. Es una pregunta sobre el USUARIO (Modelo de Usuario),
    no sobre lo que AURORA aprendió del mundo."""
    r = await _di(sistema.orquestador, "¿qué has aprendido de mí?")
    assert r["provider"] == "core"
    assert r["say"] == "No tengo ningun recuerdo registrado sobre eso.", (
        f"la frase activó el Plan de Formación en vez de seguir el flujo previo: {r['say']!r}"
    )
    assert "APUS-5" not in r["say"]


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
