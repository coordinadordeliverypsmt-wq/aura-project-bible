"""Integración (CEO, 2026-09-01): la conversación registra la autorización; el motor la ejecuta.

## Lo que hay que demostrar, y lo que hay que demostrar que NO pasa

    TU>   Autorizo <decisión>
    AURA> Autorización registrada. No ejecuto desde la conversación.
    ...el ciclo autónomo despierta solo...
    AURA> ...y la ejecutó.

La mitad interesante es la negativa: **`chat → autorización` no puede equivaler a `chat → ejecución`**.
Por eso casi todas las pruebas de abajo comprueban que algo NO ocurrió — que el fichero no existe
todavía, que la tarea sigue bloqueada, que el turno terminó sin efecto.

## No se construye ningún modelo nuevo

El circuito ya estaba entero: `hitl_diferido` deniega y anexa la solicitud al buzón, `aprobar()` la
marca, `reabrir_aprobadas()` devuelve la tarea al backlog al despertar, y el motor **vuelve a
preguntar** recalculando la huella sobre lo que va a ejecutar de verdad. Faltaba la superficie. El
propio `aprobar()` lo anticipaba: *«…y para una futura interfaz»*.

Que la puerta siga estando en el motor es lo que hace que esto sea seguro, y no una promesa: aunque
alguien marcara un fichero a mano, la huella se recalcula y una aprobación obsoleta no vale.

## Reconocer una autorización es decir que NO casi siempre

Un falso positivo abre una acción de lista roja que nadie pidió. La asimetría del daño manda, así que
la batería de frases que NO deben autorizar es más larga que la de las que sí.
"""

from __future__ import annotations

import ast
import json
import pathlib
import uuid

import pytest

import aura_skeleton.observability as obs
from aura_skeleton.adapters.hitl_diferido import crear_confirmador_diferido
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core import autorizacion as autz
from aura_skeleton.core.decisiones import AlmacenDecisiones, reabrir_aprobadas
from aura_skeleton.core.estado_operativo import Tarea


async def _di(orq, texto, uid="mauricio"):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


@pytest.fixture
def sistema(tmp_path):
    """El sistema COMPUESTO con el confirmador diferido: el mismo cableado que `--servir`, que es
    donde las solicitudes se escriben de verdad."""
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg, confirmador=crear_confirmador_diferido(str(tmp_path / "decisiones")))


class _EscritorDeObra:
    """Un ejecutor mínimo de una acción de LISTA ROJA real (`escribir_archivo`), con su `dry-run`.

    Por qué no se usa `AdaptadorComputador`, que es el de producción: al bloquearse una tarea, el
    Director le adjunta su contexto de corrección en `args[_veredicto]` (`director.py:154`), y en el
    siguiente despacho `operaciones.py` lo rechaza como *«argumentos no declarados»*. Es decir, una
    tarea del ciclo cuya acción valide ese catálogo **no puede completarse tras su primer bloqueo,
    ni siquiera con la aprobación del CEO**. Lo encontró este E2E.

    Hoy es latente —`_EJECUTORES` no mapea ninguna acción del computador— y arreglarlo tocaría un
    control de seguridad deliberado, así que se reporta como `DECISION_REQUIRED` en vez de decidirlo
    aquí. Este ejecutor tolera la metadata igual que hacen los del ciclo en producción, y el efecto
    que produce es real: escribe el fichero, y la prueba lo lee del disco.
    """

    capabilities = ["escribir_archivo"]

    async def simular(self, command: str, args: dict, trace_id: str) -> dict:
        ruta = args.get("ruta")
        if not ruta:
            return {"viable": False, "motivo": "hace falta una ruta"}
        return {"viable": True, "efecto": f"crear {ruta} con {len(str(args.get('contenido', '')))} caracteres"}

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        destino = pathlib.Path(args["ruta"])
        destino.write_text(str(args.get("contenido", "")), encoding="utf-8")
        return {"ok": True, "ruta": str(destino)}


def _ciclo_autonomo(tmp_path):
    """El ciclo autónomo REAL, montado sobre el mismo buzón que usa la conversación.

    Todo lo de dentro es de producción: el `PermissionManager`, el confirmador diferido, el motor
    único, el `DirectorGeneral` y el latido de `MotorDelCiclo` con su `al_despertar` -el mismo
    `reabrir_aprobadas` que cuelga `componer()`-.

    Lo único que la prueba elige es **qué acción roja** ejecuta el ciclo: `escribir_archivo` sobre
    `tmp_path`, en vez del `proponer_cambio` de producción. El motivo no es comodidad: el
    `EjecutorProgramador` real tiene por raíz el propio árbol de trabajo y verifica ejecutando la
    suite entera, así que un E2E que lo usara **reescribiría el repositorio**. Las dos acciones son
    de lista roja y recorren exactamente la misma puerta, que es lo que aquí se prueba.

    Que el buzón se comparta por el sistema de ficheros no es un atajo: es el arreglo real. En
    producción `--servir` corre en una terminal y la conversación en otra — dos procesos, un
    directorio.
    """
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
    from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo
    from aura_skeleton.core.motor_ciclo import MotorDelCiclo
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.core.registro import RegistroAdaptadores

    dir_dec = str(tmp_path / "decisiones")
    estado = AlmacenEstadoOperativo(str(tmp_path / "estado_ciclo.jsonl"))
    motor = MotorAutomatizacion(
        RegistroAdaptadores([_EscritorDeObra()]),
        PermissionManager(crear_confirmador_diferido(dir_dec)))
    director = DirectorGeneral(estado, motor, RegistroEjecutores({"escritor": "escribir_archivo"}))
    buzon = AlmacenDecisiones(dir_dec)
    return estado, MotorDelCiclo(director, al_despertar=lambda: reabrir_aprobadas(buzon, estado)), buzon


async def _sembrar_solicitud_real(sistema, tmp_path) -> dict:
    """Deja UNA solicitud pendiente **haciéndola producir al ciclo**, no escribiéndola a mano.

    Escribir el fichero del buzón directamente sería fabricar el escenario (D34) y probaría el
    formato en vez del circuito: lo que interesa es que la solicitud exista porque una acción de
    lista roja se topó con la puerta de permisos de verdad."""
    estado, ciclo, buzon = _ciclo_autonomo(tmp_path)
    sistema._ciclo = (estado, ciclo, buzon)
    sistema._destino = tmp_path / "obra.txt"
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-cambio", descripcion="escribir la obra",
                           responsable="escritor",
                           args={"ruta": str(sistema._destino), "contenido": "hola"}))
    await ciclo.correr("obj", max_latidos=3)
    pendientes = buzon.pendientes()
    assert pendientes, "el ciclo no llegó a pedir permiso: el escenario no es real"
    assert not sistema._destino.exists(), "INV-9: el efecto ocurrió sin permiso"
    return pendientes[0]


# ============================================================ 5 y 6 · RECONOCER --

@pytest.mark.parametrize("frase", ["Autorizo D-ORCH-6", "Apruebo D-ORCH-6", "Puedes ejecutar D-ORCH-6",
                                   "Adelante con D-ORCH-6", "Tienes mi permiso para D-ORCH-6"])
def test_una_autorizacion_INEQUIVOCA_se_reconoce(frase):
    assert autz.es_autorizacion(frase) == "D-ORCH-6", frase


@pytest.mark.parametrize("frase", [
    "¿Qué es D-ORCH-6?",
    "¿Qué opinas de D-ORCH-6?",
    "¿Puedes ejecutar D-ORCH-6?",          # la misma frase que SÍ autoriza, con signos
    "Trabaja en D-ORCH-6",                 # una orden de trabajo no es un permiso
    "Creo que podrías hacerlo",
    "haz lo que consideres",
    "Quizá deberías autorizar D-ORCH-6",   # matizado: quien duda no ha decidido
    "Si te parece, apruebo D-ORCH-6",
    "autorizo",                            # sin objeto no hay autorización
])
def test_el_lenguaje_AMBIGUO_no_autoriza_nunca(frase):
    """Un falso positivo aquí abre una acción de lista roja que nadie pidió. La asimetría del daño
    manda: ante la duda, no autoriza."""
    assert autz.es_autorizacion(frase) is None, f"{frase!r} se interpretó como autorización"


def test_la_diferencia_entre_permiso_y_pregunta_es_EL_SIGNO():
    """El control que fija la propiedad: la misma frase decide distinto según sea afirmación o
    pregunta. Sin este par, la guarda podría estar mirando otra cosa."""
    assert autz.es_autorizacion("Puedes ejecutar D-ORCH-6") == "D-ORCH-6"
    assert autz.es_autorizacion("¿Puedes ejecutar D-ORCH-6?") is None


def test_el_mecanismo_NO_esta_atado_a_D_ORCH_6_ni_a_D_INT_1():
    """El CEO lo pidió explícitamente. Se comprueba sobre identificadores que no aparecen en el
    código: si alguien los hubiera puesto a mano, esto fallaría."""
    for ident in ("X-9", "PROY-2026-11", "AB-CD-EF"):
        assert autz.es_autorizacion(f"Autorizo {ident}") == ident
    # Se mira el CÓDIGO, no la documentación: el docstring cita `D-ORCH-6` como ejemplo, y prohibir
    # que se nombre al explicarlo sería premiar el silencio en vez de la ausencia de acoplamiento.
    arbol = ast.parse(pathlib.Path(autz.__file__).read_text(encoding="utf-8"))
    literales = {n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    literales -= {ast.get_docstring(arbol) or ""}
    assert not [x for x in literales if "D-ORCH" in x or "D-INT" in x], literales


# ============================================================ 1, 2, 8, 10 · REGISTRAR --

@pytest.mark.asyncio
async def test_una_autorizacion_VALIDA_se_registra_y_PERSISTE(sistema, tmp_path):
    """Persiste en el mismo fichero del buzón que el motor consulta: no hay un segundo sitio donde
    mirar, ni un estado derivado que pudiera divergir."""
    solicitud = await _sembrar_solicitud_real(sistema, tmp_path)
    corta = solicitud["huella"][:8]

    r = await _di(sistema.orquestador, f"Autorizo {corta}")
    assert "Autorización registrada" in r["say"]
    assert r["provider"] == "core", "conceder un permiso es un hecho, no una inferencia (ADR-0014)"

    fichero = tmp_path / "decisiones" / f"{solicitud['huella']}.json"
    guardado = json.loads(fichero.read_text(encoding="utf-8"))
    assert guardado["estado"] == "aprobada"
    assert guardado["estado_anterior"] == "pendiente", "el estado previo tiene que constar"
    assert guardado["respondida_por"] == "mauricio"
    assert guardado["origen_respuesta"] == "conversacion"
    assert corta in guardado["evidencia"], "el mensaje original es la prueba de la intención"
    assert guardado["ts_respuesta"] > 0


@pytest.mark.asyncio
async def test_la_autorizacion_deja_rastro_en_la_AUDITORIA(sistema, tmp_path):
    """Prueba forense (H2): quién abrió una acción de lista roja tiene que poder auditarse sin
    creerle a nadie."""
    solicitud = await _sembrar_solicitud_real(sistema, tmp_path)
    antes = len(obs.audit_records())
    await _di(sistema.orquestador, f"Autorizo {solicitud['huella'][:8]}")
    nuevos = obs.audit_records()[antes:]
    assert any(r["module"] == "autorizacion" and "mauricio" in r["msg"] for r in nuevos), nuevos


# ============================================================ 3, 4, 11 · LOS CASOS QUE NO --

@pytest.mark.asyncio
async def test_una_decision_INEXISTENTE_no_registra_nada(sistema, tmp_path):
    r = await _di(sistema.orquestador, "Autorizo ZZ-404")
    assert "No encuentro una decisión llamada ZZ-404" in r["say"]
    assert "No registré ninguna autorización" in r["say"]
    assert not AlmacenDecisiones(str(tmp_path / "decisiones")).aprobadas()


@pytest.mark.asyncio
async def test_una_decision_YA_AUTORIZADA_no_se_autoriza_dos_veces(sistema, tmp_path):
    """No duplicar importa por algo concreto: una segunda marca reescribiría `estado_anterior` y
    `evidencia`, y perdería quién y con qué palabras se autorizó la primera vez."""
    solicitud = await _sembrar_solicitud_real(sistema, tmp_path)
    corta = solicitud["huella"][:8]
    await _di(sistema.orquestador, f"Autorizo {corta}")
    fichero = tmp_path / "decisiones" / f"{solicitud['huella']}.json"
    primera = json.loads(fichero.read_text(encoding="utf-8"))

    r = await _di(sistema.orquestador, f"Autorizo {corta}")
    assert "ya estaba autorizada" in r["say"]
    assert "No registré una segunda autorización" in r["say"]
    assert json.loads(fichero.read_text(encoding="utf-8")) == primera, "se reescribió el registro"


@pytest.mark.asyncio
async def test_un_identificador_AMBIGUO_no_elige_por_el_usuario(sistema, tmp_path, monkeypatch):
    """Dos solicitudes que empiezan igual. Adivinar cuál quería sería autorizar una acción de lista
    roja por cuenta propia."""
    buzon = AlmacenDecisiones(str(tmp_path / "decisiones"))
    monkeypatch.setattr(sistema.orquestador, "decisiones", buzon)
    falsas = [{"huella": "abc123aa", "accion": "escribir_archivo", "estado": "pendiente", "tarea": "t1"},
              {"huella": "abc123bb", "accion": "borrar_archivo", "estado": "pendiente", "tarea": "t2"}]
    monkeypatch.setattr(buzon, "pendientes", lambda: falsas)
    monkeypatch.setattr(buzon, "aprobadas", lambda: [])
    r = await _di(sistema.orquestador, "Autorizo abc123")
    assert "más de una decisión" in r["say"]
    assert "No registré" in r["say"]


@pytest.mark.asyncio
async def test_lo_que_requiere_OTRA_AUTORIDAD_se_declara_y_no_se_registra(sistema, monkeypatch):
    """Una decisión de gobernanza elevada al CEO no se resuelve con un permiso: tiene opciones, y
    ninguna se elige sola. Decir «registrada» afirmaría que algo queda desbloqueado cuando no lo
    queda — y ésa es exactamente la clase de frase tranquilizadora que este proyecto persigue."""
    class FuenteFalsa:
        def instantanea(self):
            return {"decisiones_pendientes": [
                {"id": "D-ORCH-6", "titulo": "algo", "opciones": ["(a) una", "(b) otra"]}]}
    monkeypatch.setattr(sistema.orquestador, "estado_autonomo", FuenteFalsa())
    r = await _di(sistema.orquestador, "Autorizo D-ORCH-6")
    assert "No puedo registrar esa autorización con la autoridad disponible" in r["say"]
    assert "(a) una" in r["say"] and "(b) otra" in r["say"], "las opciones salen del estado real"
    assert "registrada" not in r["say"].lower()


# ============================================================ 7 · EL CHAT NO EJECUTA --

@pytest.mark.asyncio
async def test_autorizar_NO_ejecuta_la_tarea_en_el_turno(sistema, tmp_path):
    """La garantía central, comprobada por el EFECTO y no por el texto: tras autorizar, la tarea
    sigue bloqueada y no ha ocurrido nada en el mundo."""
    await _sembrar_solicitud_real(sistema, tmp_path)
    solicitud = AlmacenDecisiones(str(tmp_path / "decisiones")).pendientes()[0]
    estado, _ciclo, _buzon = sistema._ciclo
    antes = {t.tarea_id: t.estado for t in estado.tareas("obj")}

    r = await _di(sistema.orquestador, f"Autorizo {solicitud['huella'][:8]}")

    assert "No ejecuto la tarea desde la conversación" in r["say"]
    despues = {t.tarea_id: t.estado for t in estado.tareas("obj")}
    assert despues == antes, f"el turno movió el trabajo: {antes} -> {despues}"
    assert despues["t-cambio"] == "bloqueada"
    assert not sistema._destino.exists(), "el efecto ocurrió en el turno de la conversación"


def test_la_superficie_de_autorizacion_NO_PUEDE_ejecutar_ni_despertar():
    """Comprobado en el código: si la conversación pudiera arrancar el ciclo, la autorización y la
    ejecución habrían vuelto a ser el mismo acto."""
    arbol = ast.parse(pathlib.Path(autz.__file__).read_text(encoding="utf-8"))
    nombres = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    nombres |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for prohibido in ("ejecutar", "correr", "servir", "despertar", "authorize", "aprobar",
                      "write_text", "registrar"):
        assert prohibido not in nombres, f"la superficie de reconocimiento no {prohibido}"


def test_la_autorizacion_NO_amplia_permisos():
    """No toca el gestor de permisos ni el acta: lo único que puede cambiar es el estado de UNA
    solicitud que ya estaba en el buzón."""
    fuente = pathlib.Path(autz.__file__).read_text(encoding="utf-8")
    import re as _re
    for prohibido in ("PermissionManager", "lista_roja", "alcance_actual", "kill_switch",
                      "habilitado"):
        assert not _re.search(rf"\b{prohibido}\b", fuente), f"la superficie no debe conocer {prohibido}"


# ============================================================ 9 y 14 · EL MOTOR LA VE --

@pytest.mark.asyncio
async def test_la_autorizacion_es_VISIBLE_para_el_siguiente_ciclo(sistema, tmp_path):
    """`reabrir_aprobadas` es el paso que convierte «aprobado» en «trabajo reanudado». Se ejercita el
    mismo callable que `componer` cuelga de `al_despertar`, no una copia."""
    solicitud = await _sembrar_solicitud_real(sistema, tmp_path)
    estado, _ciclo, buzon = sistema._ciclo
    assert reabrir_aprobadas(buzon, estado) == 0, "sin aprobar no se reabre nada"

    await _di(sistema.orquestador, f"Autorizo {solicitud['huella'][:8]}")

    assert reabrir_aprobadas(buzon, estado) == 1, (
        "el motor no vio la autorización registrada desde la conversación")
    tarea = {t.tarea_id: t for t in estado.tareas("obj")}["t-cambio"]
    assert tarea.estado != "bloqueada", "la tarea no volvió al trabajo"


# ============================================================ 12, 13, 16 · AISLAMIENTO Y REGRESIÓN --

def test_las_pruebas_estan_AISLADAS_del_plano_de_control_real(sistema):
    """La fixture global declara `AURA_CONTROL_PLANE=""`. Sin eso, esta batería leería el ciclo
    autónomo del equipo que la ejecuta y su veredicto cambiaría solo cada media hora."""
    assert sistema.orquestador.estado_autonomo is None


@pytest.mark.asyncio
async def test_la_conversacion_NORMAL_no_cambia(sistema):
    """La superficie nueva no puede robarle frases a las anteriores."""
    await _di(sistema.orquestador, "me llamo Mauricio")
    r = await _di(sistema.orquestador, "¿cuál es mi nombre?")
    assert "mauricio" in r["say"].lower()
    saludo = await _di(sistema.orquestador, "hola")
    assert "hola" in saludo["say"].lower()


@pytest.mark.asyncio
async def test_una_frase_con_un_identificador_pero_SIN_permiso_sigue_su_camino(sistema, tmp_path):
    """El control de no-interferencia por el otro lado: nombrar una decisión no basta para activar
    esta superficie, o le robaría el turno a cualquier pregunta que la mencione."""
    await _sembrar_solicitud_real(sistema, tmp_path)
    solicitud = AlmacenDecisiones(str(tmp_path / "decisiones")).pendientes()[0]
    r = await _di(sistema.orquestador, f"¿qué es {solicitud['huella'][:8]}?")
    assert "Autorización registrada" not in r["say"]
    assert AlmacenDecisiones(str(tmp_path / "decisiones")).pendientes(), "se autorizó una pregunta"


def test_el_buzon_de_la_conversacion_es_EL_MISMO_que_el_del_motor(tmp_path):
    """Sin esto podría haber dos buzones: el CEO autorizaría en uno y el motor leería el otro — dos
    fuentes de verdad, que es el defecto recurrente de este proyecto."""
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(cfg, confirmador=crear_confirmador_diferido(str(tmp_path / "decisiones")))
    assert s.orquestador.decisiones is not None
    huella = s.orquestador.decisiones.solicitar("escribir_archivo", {"ruta": "x"}, "efecto", "t-x")
    assert AlmacenDecisiones(str(tmp_path / "decisiones")).veredicto(huella) == "pendiente"


# ============================================================ 7 (FASE 7) · E2E COMPLETO --

@pytest.mark.asyncio
async def test_E2E_autorizo_por_chat_y_el_CICLO_AUTONOMO_lo_ejecuta(sistema, tmp_path):
    """La cadena entera, sin mocks y **sin que nadie llame al ejecutor a mano**.

        el ciclo pide permiso  →  queda bloqueada + solicitud pendiente
        el humano autoriza POR CONVERSACIÓN
        el turno termina SIN efecto
        el ciclo vuelve a despertar POR SÍ MISMO
        el motor revalida la huella y ejecuta
        el efecto queda verificado y registrado

    El paso 4 es el que da sentido a todo lo demás: si el efecto apareciera en el turno de la
    conversación, `chat → autorización` habría sido `chat → ejecución`.
    """
    solicitud = await _sembrar_solicitud_real(sistema, tmp_path)
    estado, ciclo, _buzon = sistema._ciclo
    bloqueada = {t.tarea_id: t for t in estado.tareas("obj")}["t-cambio"]
    assert bloqueada.estado == "bloqueada", "el escenario de partida no es un bloqueo real"

    # (2) y (3): el humano autoriza desde la conversación, y queda registrado.
    r = await _di(sistema.orquestador, f"Autorizo {solicitud['huella'][:8]}")
    assert "Autorización registrada" in r["say"]

    # (4) el turno termina sin ejecutar: la tarea sigue bloqueada AQUÍ.
    sigue = {t.tarea_id: t for t in estado.tareas("obj")}["t-cambio"]
    assert sigue.estado == "bloqueada", "la conversación ejecutó la tarea"
    assert not sistema._destino.exists(), "el efecto ocurrió sin que el ciclo despertara"

    # (5)…(9): el ciclo despierta por su cuenta. `correr` es el mismo latido que usa `--servir` y que
    # el cron dispara; nadie llama aquí a `motor.ejecutar`.
    await ciclo.correr("obj", max_latidos=6)

    final = {t.tarea_id: t for t in estado.tareas("obj")}["t-cambio"]
    assert final.estado == "terminada", (
        f"el ciclo autónomo no completó la tarea autorizada: {final.estado} · {final.bloqueos}")
    # (8) EL EFECTO REAL, que es lo único que no se puede fingir.
    assert sistema._destino.read_text(encoding="utf-8") == "hola"

    # (10) y una consulta posterior puede decir exactamente qué pasó.
    guardado = json.loads((tmp_path / "decisiones" / f"{solicitud['huella']}.json").read_text("utf-8"))
    assert guardado["estado"] == "aprobada"
    assert guardado["origen_respuesta"] == "conversacion"
    assert guardado["respondida_por"] == "mauricio"


@pytest.mark.asyncio
async def test_SIN_BUZON_conectado_no_se_finge_haber_registrado_nada(sistema):
    """El despliegue sin buzón —o uno donde el cableado se rompiera— no puede responder «registrada».

    Lo destapó un mutante: la fixture compone siempre el buzón, así que ninguna prueba llegaba a esta
    rama y podía devolver cualquier cosa. Decir «registrada» sin haber escrito nada es exactamente
    fingir una capacidad que no está (INV-9), y además la peor variante: el humano se queda creyendo
    que autorizó algo."""
    sistema.orquestador.decisiones = None
    r = await _di(sistema.orquestador, "Autorizo D-CUALQUIERA-1")
    assert "no puedo registrar ninguna autorización" in r["say"].lower()
    assert "registrada" not in r["say"].lower()
