"""PARADA · Opción B — qué es una escritura pasiva (CEO, 2026-09-09, D-A006-2).

`PARADA` bloquea las acciones del Motor Único y **no** bloquea la conversación. El riesgo de esa
lectura es que «conversación» no es un criterio mecánico: sin uno, cada escritura futura la resolvería
quien la escribiera, y así nacen las rutas alternativas que `ALERTA-005` prohíbe.

Por eso la definición es una **whitelist de `kind`** y estas pruebas la fijan por sus dos lados: que lo
pasivo SIGUE funcionando con la parada armada, y que lo que no está declarado pasivo NO pasa. Una
prueba que solo comprobara el segundo lado se pasaría dejando a AURA muda.
"""

from __future__ import annotations

import pytest

from aura_skeleton.contracts import HISTORICO, KINDS_PASIVOS, es_escritura_pasiva
from aura_skeleton.modules.memory import PersistentMemory

TIPOS_DEL_MODELO = ("semantica", "procedimental")


# ------------------------------------------------------------------ LA DEFINICIÓN --


def test_la_whitelist_declara_exactamente_lo_conversacional():
    assert KINDS_PASIVOS == frozenset({"episodica", HISTORICO})
    assert es_escritura_pasiva("episodica") is True
    assert es_escritura_pasiva(HISTORICO) is True


@pytest.mark.parametrize("kind", [*TIPOS_DEL_MODELO, "configuracion", "regla", "", "un_kind_futuro"])
def test_lo_que_no_esta_declarado_pasivo_NO_es_pasivo(kind):
    """**Fail-closed.** Es lo que exigió el CEO: *«Todo lo que no pueda demostrarse como pasivo debe
    tratarse como NO PASIVO»*. Un `kind` inventado hoy queda fuera sin que nadie lo prohíba."""
    assert es_escritura_pasiva(kind) is False


def test_la_definicion_es_whitelist_y_no_blacklist():
    """Caso de control estructural: si alguien la invirtiera, un `kind` desconocido pasaría a ser
    pasivo y el olvido concedería. Se comprueba con un nombre que nadie va a declarar nunca."""
    assert es_escritura_pasiva("kind_que_nadie_declaro_" + "x" * 12) is False


# ------------------------------------------------- EL COMPORTAMIENTO CON PARADA ARMADA --


async def _turno(orq, texto):
    import uuid
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return await orq.wait(tid)


def _sistema(tmp_path, *, parada: bool):
    """Orquestador con modelo de usuario y captura de señales cableados: sin ellos, la mitad
    NO pasiva de estas pruebas no tendría nada que bloquear y pasarían por vacuidad."""
    from aura_skeleton.adapters.home_assistant import HomeAssistantMock
    from aura_skeleton.adapters.voice import VoiceAdapterMock
    from aura_skeleton.bus import InProcessEventBus
    from aura_skeleton.conectores.conversacion import ConectorConversacion
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.contexto import RegistroContexto
    from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
    from aura_skeleton.core.kill_switch import KillSwitch
    from aura_skeleton.core.orchestrator import Orchestrator
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.core.registro import RegistroAdaptadores
    from aura_skeleton.modules.router import MockProvider, ModelRouter

    async def _permite(action, args, tid):
        return True

    ks = KillSwitch(str(tmp_path / "KILL"))
    if parada:
        ks.engage("prueba")
    mem = PersistentMemory(str(tmp_path / "mem.json"))
    perm = PermissionManager(_permite, kill_switch=ks)
    registro = RegistroAdaptadores()
    registro.registrar(EjecutorModeloUsuario(mem))  # atiende `registrar_informacion_usuario`
    motor = MotorAutomatizacion(registro, perm)
    contexto = RegistroContexto([ConectorConversacion()])
    orq = Orchestrator(
        InProcessEventBus(), mem,
        ModelRouter([MockProvider("m", 3, healthy=True)], 1200),
        perm, VoiceAdapterMock(), HomeAssistantMock(),
        motor=motor, contexto=contexto,  # el orquestador construye el AlmacenSenales
    )
    return orq, mem, ks


@pytest.mark.asyncio
async def test_con_PARADA_armada_la_escritura_pasiva_SIGUE_funcionando(tmp_path):
    """Opción B, primer lado. Si esto fallara, PARADA habría dejado de ser una parada de la ejecución
    para convertirse en un apagado del producto — que es justo la Opción A que el CEO no eligió."""
    orq, mem, _ = _sistema(tmp_path, parada=True)
    await _turno(orq, "Trabajo en logística")

    pasivas = [i for i in mem._items if es_escritura_pasiva(i["kind"])]
    assert pasivas, "con PARADA armada, la conversación tiene que seguir registrándose"
    assert any("logística" in i["content"] for i in pasivas)


@pytest.mark.asyncio
async def test_con_PARADA_armada_NINGUNA_escritura_no_pasiva_ocurre(tmp_path):
    """Opción B, segundo lado y el que importa: el modelo del usuario no se toca con la parada echada.

    `semantica` y `procedimental` viajan por `AlmacenSenales` → Motor Único, así que el kill switch
    las detiene ahí. Esta prueba comprueba el RESULTADO, no el mecanismo: si mañana alguien abriera
    una segunda vía hacia el modelo, caería igual."""
    orq, mem, _ = _sistema(tmp_path, parada=True)
    await _turno(orq, "Prefiero el té sin azúcar")
    await _turno(orq, "Suelo cenar temprano")

    no_pasivas = [i for i in mem._items if not es_escritura_pasiva(i["kind"])]
    assert not no_pasivas, f"PARADA armada y aun así se escribió: {[i['kind'] for i in no_pasivas]}"


@pytest.mark.asyncio
async def test_sin_PARADA_lo_no_pasivo_SI_puede_escribirse(tmp_path):
    """Caso de control de la anterior. Sin él, un sistema que nunca escribiera el modelo del usuario
    pasaría la prueba de arriba sin proteger nada."""
    orq, mem, _ = _sistema(tmp_path, parada=False)
    await _turno(orq, "Prefiero el té sin azúcar")

    assert [i for i in mem._items if i["kind"] in TIPOS_DEL_MODELO], (
        "sin PARADA, la captura de señales tiene que poder escribir el modelo del usuario")


@pytest.mark.asyncio
async def test_con_PARADA_armada_una_ACCION_del_motor_queda_bloqueada(tmp_path):
    """Lo que PARADA sí bloquea, y sigue bloqueando: `Bible 5.3 §5` — ninguna acción se ejecuta."""
    orq, _, _ = _sistema(tmp_path, parada=True)
    r = await _turno(orq, "Enciende la luz de la sala")
    assert "kill switch" in r["say"].lower(), r["say"]


# ------------------------------------------- D-A006-4 · LA EXCLUSIÓN NO ES UNA AMNISTÍA --


def test_las_cuatro_exclusiones_son_POR_OPERACION_no_por_modulo():
    """El CEO lo exigió: *«No conviertas una exclusión en autorización genérica»*."""
    from tests.unit import verificador_g1 as v

    por_op = v._excluidos_por_operacion()
    completos = v._excluidos()
    esperado = {
        "aura_skeleton/adapters/computador.py": {"unlink", "rename"},
        "aura_skeleton/adapters/programador.py": {"write_bytes"},
        "aura_skeleton/conectores/auditoria.py": {"open", "replace"},
        "aura_skeleton/core/decisiones.py": {"open", "replace"},
    }
    for modulo, ops in esperado.items():
        assert por_op.get(modulo) == ops, modulo
        assert modulo not in completos, f"{modulo} quedó excluido ENTERO: eso es una amnistía"


def test_una_escritura_NUEVA_no_declarada_se_sigue_detectando(tmp_path):
    """La condición que el CEO puso al aprobar D-A006-4.

    Se comprueba por los dos extremos: un módulo sin exclusión declarada se acusa (el caso por
    defecto), y en los módulos exentos la exención cubre **solo** lo nombrado — `write_text` no está
    en ninguna de las cuatro listas, así que aparecer allí sería una violación.
    """
    from tests.unit import verificador_g1 as v

    intruso = tmp_path / "modulo_nuevo.py"
    intruso.write_text("import pathlib\n\n\ndef f(p):\n    pathlib.Path(p).write_text('x')\n",
                       encoding="utf-8")
    hallazgos = v.analizar_fichero(intruso, autorizado_para=frozenset())
    assert [h for h in hallazgos if h.regla == "R-B"], "una escritura nueva sin declarar debe acusarse"

    for modulo, ops in v._excluidos_por_operacion().items():
        assert "write_text" not in ops, f"{modulo} eximió una operación que nadie declaró"


def test_el_manifiesto_declara_motivo_y_fecha_en_cada_exclusion():
    """*«con motivo y fecha»*. Una exclusión sin motivo es silenciosa, y el CEO prohibió eso en
    D-G1-2: *«quedan escritas aquí, con motivo, para que cualquiera pueda discutirlas»*."""
    from tests.unit import verificador_g1 as v

    for x in v._mutaciones().get("excluido", []):
        assert x.get("motivo", "").strip(), f"{x['modulo']} sin motivo"
        assert x.get("desde", "").strip(), f"{x['modulo']} sin fecha"
        assert len(x["motivo"]) > 60, f"{x['modulo']}: el motivo no explica nada"


def test_la_guarda_de_PARADA_esta_en_el_cierre_de_turno():
    """**Barrera para el futuro, y por eso hace falta esta prueba.**

    Hoy `_finalizar_turno` solo escribe `kind` que ya son pasivos, así que la guarda no cambia ningún
    comportamiento observable: es una segunda barrera para el día que alguien añada un `kind` nuevo.
    Una garantía que no cambia comportamiento no puede fijarse midiendo comportamiento — se fija
    comprobando que la guarda existe y consulta las dos cosas que debe consultar.

    Sin esto, retirarla no rompería ninguna prueba, y sería una garantía sin red.
    """
    import inspect

    from aura_skeleton.core.orchestrator import Orchestrator
    fuente = inspect.getsource(Orchestrator._finalizar_turno)
    assert "_sistema_detenido()" in fuente, "el cierre de turno dejó de mirar PARADA"
    assert "es_escritura_pasiva(kind)" in fuente, "el cierre de turno dejó de exigir que sea pasiva"
    guarda = fuente.split("_sistema_detenido()")[1][:120]
    assert "not es_escritura_pasiva" in guarda, (
        "la guarda ya no bloquea lo NO pasivo: comprobar PARADA sin actuar no protege nada")


def test_la_exencion_por_operacion_NO_exime_las_demas_operaciones(tmp_path, monkeypatch):
    """El mutante `P-M5` sobrevivía sin esta prueba, y era el mutante que importaba.

    Las cuatro entradas reales solo contienen las operaciones que declaran, así que una exención que
    cubriera el módulo ENTERO se comportaría igual y ninguna prueba lo notaría. Aquí se fabrica el caso
    que el repositorio no tiene: un módulo exento para `unlink` que además escribe con `write_text`.
    Lo primero debe eximirse; lo segundo, acusarse.
    """
    from tests.unit import verificador_g1 as v

    modulo = tmp_path / "con_dos_escrituras.py"
    modulo.write_text(
        "import os\nimport pathlib\n\n\n"
        "def f(p, fd):\n"
        "    os.unlink(p, dir_fd=fd)\n"
        "    pathlib.Path(p).write_text('x')\n",
        encoding="utf-8")
    monkeypatch.setattr(v, "_excluidos_por_operacion", lambda: {v._rel(modulo): {"unlink"}})

    ops = {h.operacion for h in v.analizar_fichero(modulo, autorizado_para=frozenset())
           if h.regla == "R-B"}
    assert "unlink" not in ops, "la operación declarada debía quedar exenta"
    assert "write_text" in ops, "la exención se comió una operación que nadie declaró: es una amnistía"
