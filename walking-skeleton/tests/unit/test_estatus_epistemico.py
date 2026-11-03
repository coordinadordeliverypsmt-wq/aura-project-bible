"""Estatus epistémico por ruta en el cierre del turno (D-FC-1 = A, D-FC-2 = B, D-FC-6, CEO 2026-09-13).

La regla que estas pruebas fijan: **el estatus lo decide la RUTA, en un único punto** —`asignar` dentro
de `_finalizar_turno`—, y una salida de proveedor es PROPUESTA pida lo que pida quien cierra el turno.
El usuario solo ve la marca del Core en una PROPUESTA; `results["estatus"]` lo expone de forma aditiva.

Todas usan proveedores espía deterministas: ninguna toca Ollama.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core import orchestrator as O
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.estatus import MARCA_PROPUESTA, Estatus
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter
from aura_skeleton.observability import Timer

FUENTE_ORQ = pathlib.Path(O.__file__).read_text(encoding="utf-8")


class _Espia:
    """Proveedor que cuenta llamadas y devuelve una respuesta fija. `orq` permite observar
    `turno_en_modelo` DESDE DENTRO de la inferencia."""

    name = "espia"

    def __init__(self, say: str = "RESPUESTA DEL MODELO", action: str = "consulta") -> None:
        self.llamadas = 0
        self.say, self.action = say, action
        self.orq = None
        self.tid = None
        self.en_modelo_durante: list[bool] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        if self.orq is not None and self.tid is not None:
            self.en_modelo_durante.append(self.orq.turno_en_modelo(self.tid))
        return json.dumps({"intent": "x", "action": self.action, "args": {}, "say": self.say})


class _Caido:
    name = "caido"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        raise ConnectionError("ollama no responde")


class _VozEspia(VoiceAdapterMock):
    def __init__(self) -> None:
        super().__init__()
        self.dichos: list[str] = []

    async def tts(self, text, trace_id):
        self.dichos.append(text)
        return text


async def _si(accion, args, trace_id):
    return True


def _orq(proveedores=None, *, modelo_usuario=True, voz=None, kill=None, **kw):
    mem = SimpleMemory()
    proveedores = proveedores if proveedores is not None else [_Espia()]
    perm = PermissionManager(_si, kill_switch=kill)
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), perm)
    orq = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter(proveedores, 1200, enfriamiento_s=3600),
        perm,
        voz or VoiceAdapterMock(),
        HomeAssistantMock(),
        modelo_usuario=ModeloUsuario(mem, motor=motor) if modelo_usuario else None,
        **kw,
    )
    return orq, mem


async def _turno(orq, texto: str, uid: str = "u", tid: str | None = None, timeout: float = 5) -> dict:
    tid = tid or uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid, timeout=timeout)


# =============================================================== 1 · UN SOLO PUNTO DECIDE --


async def test_una_respuesta_del_modelo_es_PROPUESTA_y_lleva_la_marca_del_core():
    espia = _Espia(say="La fotosíntesis convierte luz en energía.")
    orq, _ = _orq([espia])
    r = await _turno(orq, "que es la fotosintesis?")
    assert espia.llamadas == 1, "guarda: el turno debía llegar al modelo"
    assert r["estatus"] == Estatus.PROPUESTA.value
    assert r["say"] == f"{MARCA_PROPUESTA} La fotosíntesis convierte luz en energía."
    assert r["provider"] == "espia" and r["dominio"] == "llm"


async def test_el_LLM_nunca_es_HECHO_aunque_el_cierre_lo_pida():
    """Se llama al cierre con `estatus=HECHO` y proveedor != core: tiene que salir PROPUESTA.
    Caso de control en la misma prueba: con proveedor core, lo pedido se respeta."""
    orq, _ = _orq()
    for prov, esperado in (("espia", Estatus.PROPUESTA), ("core", Estatus.HECHO)):
        tid = uuid.uuid4().hex[:12]
        orq._done[tid] = asyncio.Event()
        await orq._finalizar_turno("u", tid, "x?", "texto", prov, Timer(), dominio="d", estatus=Estatus.HECHO)
        r = await orq.wait(tid)
        assert r["estatus"] == esperado.value, prov
        assert r["say"].startswith(MARCA_PROPUESTA) is (esperado is Estatus.PROPUESTA), prov


@pytest.mark.parametrize("estatus", [Estatus.HECHO, Estatus.AUSENCIA, Estatus.ACLARACION, Estatus.ABSTENCION])
async def test_la_marca_SOLO_aparece_en_una_propuesta(estatus):
    orq, _ = _orq()
    tid = uuid.uuid4().hex[:12]
    orq._done[tid] = asyncio.Event()
    await orq._finalizar_turno("u", tid, "x", "texto del core", "core", Timer(), estatus=estatus)
    r = await orq.wait(tid)
    assert r["say"] == "texto del core"
    assert r["estatus"] == estatus.value


async def test_sin_estatus_declarado_el_core_es_HECHO():
    orq, _ = _orq()
    r = await _turno(orq, "cuanto es 2+2")
    assert r["estatus"] == Estatus.HECHO.value and r["say"] == "4."


# ======================================================================= 2 · CADA RUTA --


async def test_pared_de_memoria_es_AUSENCIA_sin_modelo():
    espia = _Espia()
    orq, _ = _orq([espia], modelo_usuario=False)
    r = await _turno(orq, "como se llama mi hija?")
    assert r["dominio"] == "memoria" and r["estatus"] == Estatus.AUSENCIA.value
    assert espia.llamadas == 0


async def test_ausencia_del_modelo_de_usuario_es_AUSENCIA():
    espia = _Espia()
    orq, _ = _orq([espia])
    r = await _turno(orq, "como me llamo?")
    assert r["say"] == "Todavía no me has dicho cómo te llamas."
    assert r["dominio"] == "modelo_usuario" and r["estatus"] == Estatus.AUSENCIA.value
    assert espia.llamadas == 0


async def test_desambiguar_del_modelo_de_usuario_es_ACLARACION():
    orq, _ = _orq()
    r = await _turno(orq, "Olvida eso.")
    assert r["say"] == O._DESAMBIGUAR and r["estatus"] == Estatus.ACLARACION.value


async def test_ver_modelo_de_usuario_sin_datos_es_AUSENCIA():
    orq, _ = _orq()
    r = await _turno(orq, "que sabes de mi?")
    assert r["dominio"] == "modelo_usuario" and r["estatus"] == Estatus.AUSENCIA.value


async def test_problema_formal_infradeterminado_es_ACLARACION_sin_modelo():
    espia = _Espia()
    orq, _ = _orq([espia])
    r = await _turno(orq, "si tengo 4 manzanas y compro 2 y me como 1, cuantas manzanas me quedan?")
    assert r["dominio"] == "formal" and r["estatus"] == Estatus.ACLARACION.value
    assert espia.llamadas == 0


async def test_dominio_sensible_es_ABSTENCION_sin_modelo():
    espia = _Espia(say="FALSEDAD")
    orq, _ = _orq([espia])
    r = await _turno(orq, "quien es Jesus Cristo?")
    assert r["dominio"] == "sensible" and r["estatus"] == Estatus.ABSTENCION.value
    assert "religión" in r["say"] and "FALSEDAD" not in r["say"]
    assert espia.llamadas == 0


async def test_la_abstencion_sensible_NO_se_aplica_a_una_orden():
    """Control de D-FC-2: «testamento» es léxico de derecho, pero una orden va por el motor."""
    espia = _Espia()
    orq, _ = _orq([espia])
    r = await _turno(orq, "borra el archivo testamento.txt")
    assert espia.llamadas == 1 and r["dominio"] != "sensible"
    assert r["estatus"] == Estatus.PROPUESTA.value


# ================================================================= 3 · SIN PROVEEDOR --


async def test_sin_proveedor_el_turno_TERMINA_en_ABSTENCION():
    caido = _Caido()
    orq, _ = _orq([caido])
    tid = uuid.uuid4().hex[:12]
    r = await _turno(orq, "que es la fotosintesis?", tid=tid, timeout=2)  # expirar sería el defecto
    assert caido.llamadas == 1
    assert r["estatus"] == Estatus.ABSTENCION.value and r["dominio"] == "proveedor_no_disponible"
    assert r["provider"] == "core" and r["say"] == O._ABSTENCION_SIN_PROVEEDOR
    assert orq.turno_en_modelo(tid) is False


async def test_router_sin_ningun_proveedor_tambien_termina():
    orq, _ = _orq([])
    r = await _turno(orq, "que es la fotosintesis?", timeout=2)
    assert r["estatus"] == Estatus.ABSTENCION.value


# ============================================================== 4 · ACUSE (D-FC-6) --


async def test_turno_en_modelo_es_True_solo_mientras_se_espera_al_modelo():
    espia = _Espia()
    orq, _ = _orq([espia])
    espia.orq, espia.tid = orq, "T-MODELO"
    assert orq.turno_en_modelo("T-MODELO") is False
    await _turno(orq, "que es la fotosintesis?", tid="T-MODELO")
    assert espia.en_modelo_durante == [True], "dentro de la inferencia debía verse True"
    assert orq.turno_en_modelo("T-MODELO") is False, "tras cerrar debía volver a False"


async def test_el_acuse_por_voz_precede_a_la_respuesta_del_modelo_y_no_existe_en_el_core():
    voz = _VozEspia()
    orq, _ = _orq(voz=voz)
    await _turno(orq, "que es la fotosintesis?")
    assert voz.dichos[0] == O._ACUSE_CONSULTA_MODELO
    assert voz.dichos[-1].startswith(MARCA_PROPUESTA)
    voz.dichos.clear()
    await _turno(orq, "cuanto es 2+2")
    assert voz.dichos == ["4."], "una respuesta del Core no lleva acuse"


# ==================================================== 5 · AURA SOBRE SÍ MISMA (D-FC-3) --


class _EstadoOperativoVacio:
    def objetivos_activos(self):
        return []


class _Autonomo:
    def __init__(self, inst):
        self.inst = inst

    def instantanea(self):
        return self.inst


async def test_T8_sin_objetivos_es_AUSENCIA_del_core():
    espia = _Espia()
    orq, _ = _orq([espia], estado_operativo=_EstadoOperativoVacio())
    r = await _turno(orq, "que desarrollas en este momento?")
    assert r["dominio"] == "aura" and r["estatus"] == Estatus.AUSENCIA.value
    assert "ningún objetivo activo" in r["say"] and espia.llamadas == 0


async def test_T8_sin_fuente_conectada_sigue_la_pared_del_core():
    """Precedencia documentada: sin estado operativo (orquestador construido a mano) la pregunta sigue
    el camino que ya existia, como fija `test_conversacion_ventana_so`. Sigue siendo Core y 0 LLM."""
    espia = _Espia()
    orq, _ = _orq([espia])
    r = await _turno(orq, "que desarrollas en este momento?")
    assert r["dominio"] == "memoria" and r["estatus"] == Estatus.AUSENCIA.value
    assert espia.llamadas == 0


async def test_T8_con_ciclo_real_es_HECHO_con_el_dato():
    espia = _Espia()
    orq, _ = _orq([espia], estado_autonomo=_Autonomo({"estado": "TRABAJANDO", "ultimo_ciclo": 7}))
    r = await _turno(orq, "que desarrollas en este momento?")
    assert r["dominio"] == "aura" and r["estatus"] == Estatus.HECHO.value
    assert "ciclo autónomo en curso" in r["say"] and "7" in r["say"]
    assert espia.llamadas == 0


async def test_T8_con_la_parada_echada_lo_dice_el_core(tmp_path):
    ks = KillSwitch(str(tmp_path / "KILL"))
    ks.engage("prueba")
    orq, _ = _orq(kill=ks, estado_operativo=_EstadoOperativoVacio())
    r = await _turno(orq, "que desarrollas en este momento?")
    assert "parada de emergencia" in r["say"] and r["estatus"] == Estatus.HECHO.value


# ========================================= 6 · LAS AUSENCIAS DECLARADAS SIGUEN SIENDO REALES --


def test_cada_ausencia_declarada_sigue_existiendo_en_el_codigo_que_la_produce():
    """«declarado != real»: si alguien reescribe un retorno, el literal de `_AUSENCIAS_DEL_CORE`
    quedaria huérfano y esa superficie pasaria a salir HECHO en silencio."""
    from aura_skeleton.core import modelo_usuario

    fuente_mu = pathlib.Path(modelo_usuario.__file__).read_text(encoding="utf-8")
    # Las que se derivan por NOMBRE (la tabla de hechos, las constantes, `describir_conocimiento([])`)
    # no pueden quedar huerfanas: son la misma referencia. Solo se vigilan los literales copiados.
    por_referencia = {a for *_, a in O._CONSULTAS_DE_HECHO} | {
        O._SIN_PENDIENTES,
        modelo_usuario.describir_conocimiento([]),
    }
    literales = O._AUSENCIAS_DEL_CORE - por_referencia
    assert len(literales) >= 10, "guarda: la comprobacion tiene que vigilar algo"
    huerfanos = [a for a in literales if FUENTE_ORQ.count(a) < 2 and a not in fuente_mu]
    assert not huerfanos, huerfanos


async def test_las_superficies_de_estado_vacias_salen_AUSENCIA(monkeypatch, tmp_path):
    orq, _ = _orq(estado_operativo=_EstadoOperativoVacio(), estado_autonomo=_Autonomo({}))
    for texto in (
        orq._describir_tareas(),
        orq._describir_bloqueo(),
        orq._describir_decisiones("x"),
        orq._describir_oportunidades(),
        orq._describir_evolucion("x"),
        orq._describir_ultima_tarea(),
    ):
        assert O._estatus_del_core(texto) is Estatus.AUSENCIA, texto
    monkeypatch.setattr(O, "_ruta_plan_formacion", lambda: tmp_path / "no-existe.md")
    assert O._estatus_del_core(O._resumen_formacion()) is Estatus.AUSENCIA
    (tmp_path / "plan.md").write_text("# Plan\n## Otra\nnada\n", encoding="utf-8")
    monkeypatch.setattr(O, "_ruta_plan_formacion", lambda: tmp_path / "plan.md")
    assert O._estatus_del_core(O._resumen_formacion()) is Estatus.AUSENCIA
    # Control: un texto con dato real no es ausencia.
    assert O._estatus_del_core("Tengo 3 capacidad(es) registradas:") is Estatus.HECHO


async def test_la_ruta_de_estado_propaga_la_ausencia_al_resultado():
    orq, _ = _orq(estado_operativo=_EstadoOperativoVacio())
    r = await _turno(orq, "por que estas bloqueada?")
    assert r["dominio"] == "gobierno" and r["estatus"] == Estatus.AUSENCIA.value


# ================================================ 7 · LA COMPUERTA COGNITIVA, POR SÍ MISMA --


@pytest.mark.parametrize(
    ("texto", "sale"),
    [
        ("si mi hija tiene 7 años, cuantos cumplira el proximo verano?", False),
        ("si mi jefe cobra 2000 al mes, cuanto gana en un año?", False),
        ("por que llueve?", True),  # control: cognición del mundo
        ("si meto la mano en agua caliente que me pasa?", True),  # control: T5
    ],
)
def test_la_compuerta_cognitiva_exige_referente_MUNDO(texto, sale):
    """FC-M13: independiente del orden de la cascada. Los dos posesivos tienen FORMA cognitiva —si esa
    guarda no se cumpliera, la prueba no discriminaría nada— y aun así no salen al modelo."""
    from aura_skeleton.core import intencion as I

    if not sale:
        assert I.es_cognicion_general(texto), "guarda: el caso tiene que tener forma cognitiva"
    assert O._es_turno_cognitivo(texto) is sale, texto
