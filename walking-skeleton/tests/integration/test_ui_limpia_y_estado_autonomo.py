"""Integración (CEO, 2026-09-01): la conversación se lee, y «¿en qué estás trabajando?» se contesta.

DOS DEFECTOS OBSERVADOS EN PRODUCCIÓN, con causas raíz distintas.

**1 · La telemetría sepultaba la conversación.** Cada turno imprimía `[VOICE]`, `[EVENT]`, `[MEM]`,
`[LLM]`, `[AUDIT]`, `[AUTO]`, `[CTX]` y `[LAT]` antes de la respuesta. La separación por flujo ya
existía —telemetría a `stderr`, conversación a `stdout`— pero en una terminal los dos caen en el
mismo sitio, así que no separaba nada. `observability.log` hacía un `print` incondicional.

Lo que se corrige es **dónde se imprime**, no si se registra: `_records` y el audit log se escriben
ANTES de decidir si se pinta. Por eso estas pruebas exigen las dos mitades a la vez — pantalla
limpia **y** auditoría intacta—: apagar la pantalla borrando registros sería «arreglarlo» destruyendo
justo la evidencia.

**2 · Una pregunta sobre AURA se contestó desde la memoria del usuario.**

    tu> ¿en qué estás trabajado ahora?
    AURA> No tengo ningun recuerdo registrado sobre eso.

La superficie existía, pero su lista de frases era literal: bastó escribir «trabajado» en vez de
«trabajando» para que la frase llegara al final del recorrido, donde una memoria vacía produce la
ausencia de recuerdos. **Una pregunta sobre uno mismo que no se reconoce no se queda sin responder:
se responde mal**, porque el último recurso pertenece a otro dominio. Y aun reconociéndola, se leía
el tablero de objetivos del producto, que no sabe nada del ciclo autónomo.

NINGUNA PRUEBA DE AQUÍ LEE EL PLANO REAL. La fuente se inyecta, que es además la única forma de
fijar los seis casos sin fabricar un entorno (D34) y sin que el veredicto dependa de la hora a la
que se ejecute la suite.
"""

from __future__ import annotations

import pathlib
import time
import uuid

import pytest

import aura_skeleton.observability as obs
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estado_autonomo import redactar_actividad, redactar_ultima_tarea

ND = "NO DISPONIBLE"


async def _di(orq, texto, uid="mauricio"):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


def _ausencia(r) -> bool:
    return "no tengo ningun recuerdo" in r["say"].lower().replace("ú", "u")


class FuenteFalsa:
    """Una `FuenteEstadoAutonomo` de laboratorio: devuelve lo que se le siembre y cuenta lecturas."""

    def __init__(self, instantanea: dict):
        self._inst = instantanea
        self.lecturas = 0

    def instantanea(self) -> dict:
        self.lecturas += 1
        return self._inst


#: Lo que el observatorio devuelve hoy en el plano real: cola agotada, seis bloqueadas y dos
#: elevadas. Copiado de una salida REAL de `aura.py estado --json`, no inventado.
COLA_AGOTADA = {
    "estado": "DECISION_REQUIRED",
    "ultimo_ciclo": 73,
    "hora_ultimo_ciclo": "2026-09-01T07:30:01",
    "cola": {"OPORTUNIDAD_REAL": 0, "BLOQUEADA": 6, "DECISION_REQUIRED": 2, "FALSO_HUECO": 0},
    "trabajo_bloqueado": 6,
    "trabajo_elevado": 2,
    "decisiones_pendientes": [{"id": "D-ORCH-6", "titulo": "..."}, {"id": "D-INT-1", "titulo": "..."}],
    "proximo_despertar": "2026-09-01T08:00:00",
    "ultima_tarea": {
        "id": "P-016", "simbolo": "_quitar_funcion", "fichero": "/x/autoconstruccion.py",
        "resultado": "efecto verificado", "autorizada_por": "REVIEW:auditor-consistencia",
        "momento": "2026-08-31T21:44:43",
    },
    "sospecha": "",
}

EJECUTANDO = {
    "estado": "TRABAJANDO",
    "ultimo_ciclo": 74,
    "hora_ultimo_ciclo": "2026-09-01T08:00:02",
    "cola": {"OPORTUNIDAD_REAL": 1, "BLOQUEADA": 6, "DECISION_REQUIRED": 0, "FALSO_HUECO": 0},
    "trabajo_bloqueado": 6, "trabajo_elevado": 0, "decisiones_pendientes": [],
    "proximo_despertar": "2026-09-01T08:30:00", "ultima_tarea": ND, "sospecha": "",
}


@pytest.fixture
def sistema(tmp_path):
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg)


def _con_fuente(sistema, instantanea) -> FuenteFalsa:
    fuente = FuenteFalsa(instantanea)
    sistema.orquestador.estado_autonomo = fuente
    return fuente


# =================================================================== 1 · UI LIMPIA --


@pytest.mark.asyncio
async def test_hola_produce_UNICAMENTE_la_respuesta_conversacional_visible(sistema, capsys):
    """Con la pantalla de telemetría apagada, un turno no imprime ni una etiqueta interna."""
    anterior = obs.salida_actual()
    obs.configurar_salida(None)
    try:
        capsys.readouterr()
        r = await _di(sistema.orquestador, "hola")
        print(f"AURA> {r['say']}")          # lo que hace `__main__._conversar`
        salida = capsys.readouterr()
    finally:
        obs.configurar_salida(anterior)

    visible = salida.out + salida.err
    for etiqueta in ("[VOICE", "[EVENT", "[MEM", "[LLM", "[AUDIT", "[AUTO", "[CTX", "[LAT", "[CORE"):
        assert etiqueta not in visible, f"{etiqueta}] sigue apareciendo en la interfaz: {visible!r}"
    assert r["say"] in visible, "la respuesta sí tiene que verse"


@pytest.mark.asyncio
async def test_los_eventos_internos_SIGUEN_existiendo_aunque_no_se_vean(sistema):
    """La mitad que impide «arreglarlo» destruyendo la evidencia: con la pantalla apagada, el turno
    tiene que producir EXACTAMENTE los mismos registros que con la pantalla encendida."""
    anterior = obs.salida_actual()
    try:
        obs.configurar_salida(None)
        antes = len(obs._records)
        r = await _di(sistema.orquestador, "hola")
        apagada = [x["module"] for x in obs._records[antes:]]

        obs.configurar_salida(anterior)
        antes = len(obs._records)
        await _di(sistema.orquestador, "hola")
        encendida = [x["module"] for x in obs._records[antes:]]
    finally:
        obs.configurar_salida(anterior)

    assert apagada, "un turno tiene que dejar telemetría"
    assert apagada == encendida, (
        f"apagar la pantalla cambió lo que se registra: {apagada} != {encendida}")
    assert r["say"].strip()


@pytest.mark.asyncio
async def test_la_separacion_NO_rompe_la_AUDITORIA(sistema, tmp_path):
    """`audit=True` es prueba forense (H2), no observabilidad: se PERSISTE en disco.

    La primera versión de esta prueba miraba `obs.audit_records()`, que lee la lista en memoria — el
    camino que el mutante ni siquiera tocaba. Un mutante que salta `_audit.append()` cuando la
    pantalla está apagada sobrevivió, y tenía razón: la prueba no vigilaba el fichero, que es donde
    la auditoría de verdad vive."""
    ruta = str(tmp_path / "audit-prueba.jsonl")
    anterior_salida, anterior_audit = obs.salida_actual(), obs._audit
    obs.configure_audit(ruta)
    obs.configurar_salida(None)
    try:
        antes = len(obs.audit_records())
        obs.log("PRUEBA", "forense", "accion con efecto", "t9", audit=True)
        await _di(sistema.orquestador, "recuerda que mi color favorito es el verde")
    finally:
        obs.configurar_salida(anterior_salida)
        obs._audit = anterior_audit
    assert len(obs.audit_records()) > antes, "la auditoría en memoria dejó de registrar"
    persistido = pathlib.Path(ruta).read_text(encoding="utf-8")
    assert "accion con efecto" in persistido, (
        "con la pantalla apagada el registro forense dejó de llegar al DISCO")


def test_la_pantalla_apagada_es_un_SUMIDERO_y_no_un_filtro(capsys):
    """El registro ocurre ANTES de decidir si se pinta. Si algún día se invirtiera el orden, esto
    fallaría — y sería el defecto grave: observabilidad perdida para ganar legibilidad."""
    anterior = obs.salida_actual()
    try:
        obs.configurar_salida(None)
        antes = len(obs._records)
        obs.log("PRUEBA", "sumidero", "no debe verse", "t1", audit=True)
        assert len(obs._records) == antes + 1, "el registro se perdió al apagar la pantalla"
        assert "no debe verse" not in capsys.readouterr().err
    finally:
        obs.configurar_salida(anterior)


@pytest.mark.asyncio
async def test_la_CONVERSACION_INTERACTIVA_apaga_la_pantalla_ella_sola(sistema, monkeypatch):
    """La prueba anterior apagaba la salida a mano, así que nunca ejercitaba la línea que de verdad
    lo decide. Un mutante que invertía la condición de `--telemetria` sobrevivió por eso.

    Aquí se ejecuta `_conversar` de verdad, con una entrada que termina de inmediato."""
    from aura_skeleton import __main__ as principal

    anterior = obs.salida_actual()
    try:
        monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError()))
        obs.configurar_salida(anterior)
        await principal._conversar(sistema)
        assert obs.salida_actual() is None, "la conversación no apagó la telemetría de pantalla"

        obs.configurar_salida(anterior)
        await principal._conversar(sistema, telemetria=True)
        assert obs.salida_actual() is anterior, "--telemetria debe DEJARLA en pantalla"
    finally:
        obs.configurar_salida(anterior)


# =================================================================== 2 · GROUNDING DEL CICLO --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    [
        "¿en qué estás trabajando ahora?",
        "¿en qué estás trabajado ahora?",     # el typo LITERAL del CEO, que fue el defecto
        "¿qué estás haciendo?",
        "¿en qué andas?",
        "¿cuál es tu estado?",
        "¿qué tarea estás ejecutando?",
        "¿qué vas a hacer después?",
    ],
)
async def test_preguntar_por_su_ACTIVIDAD_consulta_el_ciclo_y_NO_la_memoria(sistema, frase):
    """La garantía central. Ninguna de estas frases puede caer en la ausencia de memoria, y todas
    tienen que haber leído el estado autónomo — no haberlo leído y acertar el texto por casualidad
    sería el mismo defecto con otra cara."""
    fuente = _con_fuente(sistema, COLA_AGOTADA)
    r = await _di(sistema.orquestador, frase)
    assert not _ausencia(r), f"{frase!r} volvió a contestarse desde la memoria: {r['say']!r}"
    assert r["provider"] == "core", f"{frase!r} no debe ir al LLM: fue a {r['provider']!r}"
    assert fuente.lecturas >= 1, f"{frase!r} respondió SIN consultar el estado autónomo"


@pytest.mark.asyncio
async def test_con_la_COLA_AGOTADA_declara_que_no_hay_trabajo_autorizado(sistema):
    """(C) Es la respuesta correcta cuando no hay trabajo: una cola vacía NO es «no puedo hacer
    nada». El texto se compara contra el redactor aplicado a la MISMA instantánea, nunca contra una
    constante escrita aquí."""
    _con_fuente(sistema, COLA_AGOTADA)
    r = await _di(sistema.orquestador, "¿en qué estás trabajando?")
    assert redactar_actividad(COLA_AGOTADA) in r["say"]
    assert "no tengo ninguna tarea autorizada disponible para ejecutar" in r["say"].lower()


@pytest.mark.asyncio
async def test_con_DECISIONES_PENDIENTES_dice_que_requieren_a_un_humano(sistema):
    """(E) Y las nombra: una decisión sin identificador no se puede ir a firmar."""
    _con_fuente(sistema, COLA_AGOTADA)
    r = await _di(sistema.orquestador, "¿cuál es tu estado?")
    assert "decisión humana" in r["say"] or "decision humana" in r["say"]
    assert "D-ORCH-6" in r["say"] and "D-INT-1" in r["say"]
    assert "necesitan una decisión tuya" in r["say"], (
        "«aprobación» era impreciso: estas decisiones tienen opciones y no se resuelven con un "
        "permiso — la otra superficie lo dice, y las dos tienen que decir lo mismo")


@pytest.mark.asyncio
async def test_con_trabajo_BLOQUEADO_lo_declara_y_no_lo_confunde_con_hecho(sistema):
    """(D) Seis bloqueadas es trabajo que NO se pudo hacer. Contarlo como hecho sería una
    felicitación; callarlo escondería que existe una autorización capaz de desbloquearlo."""
    _con_fuente(sistema, COLA_AGOTADA)
    r = await _di(sistema.orquestador, "¿qué estás haciendo?")
    assert "6 oportunidades bloqueadas" in r["say"]
    # Lo bloqueado NO puede presentarse como hecho: con cero trabajo ejecutable, la frase de cabecera
    # tiene que seguir siendo la de ausencia de trabajo autorizado.
    assert "no tengo ninguna tarea autorizada disponible" in r["say"].lower()
    assert "6 tarea(s) autorizada(s)" not in r["say"]


@pytest.mark.asyncio
async def test_con_un_CICLO_EN_CURSO_refleja_la_tarea_real(sistema):
    """(A) Con un ciclo abierto, la respuesta cambia y trae su número y su hora reales — no un
    texto genérico de «estoy trabajando» que valdría para cualquier estado."""
    _con_fuente(sistema, EJECUTANDO)
    r = await _di(sistema.orquestador, "¿en qué estás trabajando?")
    assert "ciclo autónomo en curso" in r["say"]
    assert "74" in r["say"] and "2026-09-01T08:00:02" in r["say"]
    # Y discrimina de verdad: la MISMA pregunta sobre el otro estado da otra respuesta. Sin esto, un
    # texto genérico de «estoy trabajando» que valiera para todo pasaría la prueba.
    assert redactar_actividad(EJECUTANDO) != redactar_actividad(COLA_AGOTADA)
    assert "no tengo ninguna tarea autorizada" not in r["say"]


@pytest.mark.asyncio
async def test_la_ULTIMA_TAREA_sale_del_historial_y_no_de_la_conversacion(sistema):
    """«¿Qué hiciste?» no se contesta con lo que se dijo hace dos turnos: se contesta con lo que
    consta que ocurrió, con su identidad y su fichero, para que se pueda comprobar."""
    _con_fuente(sistema, COLA_AGOTADA)
    await _di(sistema.orquestador, "acabo de pintar la casa de azul")
    r = await _di(sistema.orquestador, "¿cuál fue tu última tarea?")
    assert redactar_ultima_tarea(COLA_AGOTADA) == r["say"]
    assert "P-016" in r["say"] and "_quitar_funcion" in r["say"]
    assert "azul" not in r["say"], "contestó con la conversación en vez de con el historial"


# =================================================================== NO FABRICAR --


@pytest.mark.asyncio
async def test_sin_datos_NO_se_fabrica_ninguna_tarea_ni_progreso(sistema):
    """Una instantánea con todo en `NO DISPONIBLE` no puede producir un informe optimista. Es el
    control que impide que el redactor rellene huecos con ceros «razonables»."""
    vacia = {"estado": ND, "cola": ND, "trabajo_bloqueado": ND, "trabajo_elevado": ND,
             "decisiones_pendientes": ND, "proximo_despertar": ND, "ultima_tarea": ND}
    _con_fuente(sistema, vacia)
    r = await _di(sistema.orquestador, "¿en qué estás trabajando?")
    dicho = r["say"].lower()
    assert "no me consta qué tengo en cola" in dicho
    for inventado in ("0 oportunidades", "0 elevadas", "progreso", "%"):
        assert inventado not in dicho, f"apareció un dato fabricado: {inventado!r} en {r['say']!r}"
    # Y el hueco no puede IMPRIMIRSE como si fuera un dato: "previsto para las NO DISPONIBLE" es peor
    # que no decir la hora, porque parece una medición. Lo destapó un mutante que hacía que `_hay`
    # aceptara el centinela.
    assert ND not in r["say"], f"el centinela de hueco se filtró a la respuesta: {r['say']!r}"
    r2 = await _di(sistema.orquestador, "¿qué hiciste?")
    assert "no me consta ninguna tarea ejecutada" in r2["say"].lower()


def test_el_redactor_NO_inventa_cuando_no_hay_fuente():
    """Sin fuente devuelve `None`, y el orquestador cae al camino de siempre. Devolver un texto
    plausible aquí sería fingir capacidad no construida (INV-9)."""
    assert redactar_actividad({}) is None
    assert redactar_ultima_tarea({}) is None


@pytest.mark.asyncio
async def test_SIN_plano_de_control_la_conversacion_se_comporta_como_antes(sistema):
    """El producto tiene que poder instalarse sin el plano de desarrollo. Sin fuente, la pregunta
    sigue el camino que ya existía: el tablero de objetivos, nunca un invento."""
    sistema.orquestador.estado_autonomo = None
    r = await _di(sistema.orquestador, "¿en qué estás trabajando?")
    assert r["provider"] == "core"
    # Oráculo INDEPENDIENTE: el estado operativo real del sistema compuesto. Comparar contra
    # `_describir_tareas()` sería preguntarle a la función bajo prueba si acertó — y un mutante que
    # devolvía "Estoy trabajando en varias cosas." sobrevivía, porque las dos ramas mentían igual.
    activos = sistema.estado_operativo.objetivos_activos()
    if not activos:
        assert r["say"] == "No tengo ningún objetivo activo registrado en el estado operativo ahora mismo."
    else:
        assert "Esto es en lo que estoy trabajando:" in r["say"]
    assert "ciclo autónomo" not in r["say"]
    assert "varias cosas" not in r["say"], "sin fuente no se improvisa una respuesta genérica"


# =================================================================== NO ROBAR TURNOS --


@pytest.mark.asyncio
async def test_las_preguntas_de_MEMORIA_siguen_funcionando_igual(sistema):
    """La superficie nueva no puede robarle frases a las anteriores."""
    _con_fuente(sistema, COLA_AGOTADA)
    await _di(sistema.orquestador, "me llamo Mauricio")
    r = await _di(sistema.orquestador, "¿cuál es mi nombre?")
    assert "mauricio" in r["say"].lower(), f"la memoria dejó de funcionar: {r['say']!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    ["¿qué hiciste con mis archivos?", "¿en qué estado está mi pedido?", "¿qué estás haciendo con mi carpeta?"],
)
async def test_una_pregunta_sobre_algo_AJENO_no_la_intercepta_el_ciclo(sistema, frase):
    """La guarda de dominio, en el sentido contrario. Robarle «¿qué hiciste con mis archivos?» al
    usuario para contestar con el historial del ciclo sería este mismo defecto con los dominios
    cambiados de sitio."""
    fuente = _con_fuente(sistema, COLA_AGOTADA)
    await _di(sistema.orquestador, frase)
    assert fuente.lecturas == 0, f"{frase!r} activó el estado autónomo y es una pregunta del usuario"


# =================================================================== LATENCIA --


@pytest.mark.asyncio
async def test_el_estado_autonomo_se_lee_UNA_SOLA_VEZ_por_turno(sistema):
    """La garantía determinista contra la regresión de latencia: leer el plano cuesta ~76 ms sobre
    un historial real, así que leerlo dos veces por turno lo duplicaría sin que ninguna prueba de
    reloj lo notara de forma fiable."""
    fuente = _con_fuente(sistema, COLA_AGOTADA)
    await _di(sistema.orquestador, "¿en qué estás trabajando?")
    assert fuente.lecturas == 1, f"se leyó {fuente.lecturas} veces"


@pytest.mark.asyncio
async def test_la_pregunta_de_estado_no_encarece_el_turno_por_si_misma(sistema):
    """Con una fuente instantánea, el turno de estado no puede costar mucho más que uno normal: lo
    que cueste de más ha de venir de LEER el plano, no del cableado añadido."""
    _con_fuente(sistema, COLA_AGOTADA)
    t0 = time.perf_counter()
    await _di(sistema.orquestador, "hola")
    normal = time.perf_counter() - t0
    t0 = time.perf_counter()
    await _di(sistema.orquestador, "¿en qué estás trabajando?")
    estado = time.perf_counter() - t0
    assert estado < max(normal * 6, 0.5), f"turno normal {normal * 1000:.1f} ms, de estado {estado * 1000:.1f} ms"
