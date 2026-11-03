"""RED · F2 — Kill switch universal. **Decisión del CEO 17.1 = B (2026-08-25).**

El Paso 0 permanece en `PermissionManager.authorize()`; **no se mueve al motor y no se duplica**.
Lo que F2 debe garantizar es lo otro: que **el motor lo atraviesa siempre**, para toda acción que
ejecute, sin ninguna ruta interna que llegue al adaptador sin pasar por permisos.

**Qué prueba este fichero y qué NO.** Prueba la garantía *dentro* del motor, por **efecto real**:
con el kill switch armado, ninguna acción ejecutada por el motor toca el disco. **No** prueba que
`ModeloUsuario.borrar` pase por el motor — eso es **F4 · Migrar rutas** (`DP-D-M-8 §7`), y sus rojos
ya viven en `test_garantias_motor_unico.py`. Mezclarlo aquí daría por cerrado en F2 algo que el
plan aprobado sitúa dos fases más adelante.

**Decisiones aplicadas:** 17.2 — la firma no se amplía, `sujeto` es de F3. · 17.3 — `simular()` queda
**fuera del alcance**: no se modifica ni se le añade comportamiento. · 17.4 — F2 se adelanta a la
auditoría de F0, que sigue `WAITING_FOR_QUOTA`.
"""
from __future__ import annotations

import pathlib

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.permissions import ALTERA_ESTADO, CATALOGO, RED, PermissionManager

#: ARGS ANADIDO 2026-08-25 con F3: tres operaciones del catalogo declaran `sujeto: usuario` y sin
#: `user_id` se deniegan por falta de sujeto. El fixture pasaba `{}`, que ya no describe una peticion
#: valida. **Ningun veredicto de F2 cambia** — las demas acciones ignoran este argumento.
ARGS = {"user_id": "mauricio"}


async def _confirma_siempre(accion, args, trace_id):
    """Aprueba toda lista roja. Así, si algo queda bloqueado, **no puede ser por falta de HITL**."""
    return True


class AdaptadorQueEscribe:
    """Adaptador con **efecto real**: `execute` crea un fichero en disco.

    Comprobar retornos no bastaría — la garantía es que **el dato no se toca**, no que una función
    devuelva `False`."""

    def __init__(self, destino: pathlib.Path) -> None:
        self.destino = destino
        self.ejecutadas: list[str] = []
        self.simuladas: list[str] = []

    def para(self, accion):          # hace de RegistroAdaptadores
        return self

    async def simular(self, accion, args, trace_id):
        self.simuladas.append(accion)
        return {"viable": True, "efecto": f"crearia {self.destino.name}"}

    async def execute(self, accion, args, trace_id, event_id):
        self.ejecutadas.append(accion)
        self.destino.write_text("MUTADO", encoding="utf-8")
        return {"ok": True}


def _motor(tmp_path, armado: bool):
    destino = tmp_path / "efecto.txt"
    kill = KillSwitch(trigger_file=str(tmp_path / "KILL"))
    kill.disengage()
    if armado:
        kill.engage("prueba F2")
    adaptador = AdaptadorQueEscribe(destino)
    return MotorAutomatizacion(adaptador, PermissionManager(_confirma_siempre, kill_switch=kill)), adaptador, destino


# ================================================== META-CONTROL DEL FICHERO --


async def test_meta_el_adaptador_de_prueba_muta_de_verdad(tmp_path):
    """Si `execute` no escribiera, **todas** las pruebas de abajo pasarían en vacío y este fichero
    mentiría diciendo que el sistema está protegido. Es la lección de `test_la_siembra_es_realmente_borrable`."""
    motor, adaptador, destino = _motor(tmp_path, armado=False)
    r = await motor.ejecutar("escribir_archivo", ARGS, "t", "e", "prueba")
    assert r["estado"] == "ejecutada" and destino.exists() and destino.read_text() == "MUTADO"


# ============================================ COBERTURA · TODO ALTERA_ESTADO --


@pytest.mark.parametrize("accion", sorted(ALTERA_ESTADO))
async def test_f2_ninguna_accion_que_altera_estado_muta_con_el_kill_switch_armado(accion, tmp_path):
    """**La garantía, por efecto real y sobre TODO el catálogo aplicable** — `DP-D-M-8 §6` exige
    parametrizar sobre todas las operaciones, no muestrear."""
    motor, adaptador, destino = _motor(tmp_path, armado=True)
    r = await motor.ejecutar(accion, ARGS, "t", "e", "prueba")
    assert not destino.exists(), f"{accion}: hubo mutación con el kill switch armado"
    assert adaptador.ejecutadas == [], f"{accion}: el adaptador ejecutó"
    assert r["estado"] == "detenida", f"{accion}: estado {r['estado']}"
    assert "kill switch" in r["motivo"], f"{accion}: el motivo no menciona el kill switch: {r['motivo']!r}"


@pytest.mark.parametrize("accion", sorted(CATALOGO))
async def test_f2_el_adaptador_nunca_recibe_execute_con_el_kill_switch_armado(accion, tmp_path):
    """`authorize` es inevitable **dentro del motor**: ninguna acción del catálogo —altere o no el
    estado— llega al ejecutor con la parada armada."""
    motor, adaptador, _ = _motor(tmp_path, armado=True)
    await motor.ejecutar(accion, ARGS, "t", "e", "prueba")
    assert adaptador.ejecutadas == []


# =========================================================== CASO DE CONTROL --


@pytest.mark.parametrize("accion", sorted(ALTERA_ESTADO))
async def test_control_desarmado_la_accion_SI_se_ejecuta(accion, tmp_path):
    """Sin él, un motor totalmente roto —que no ejecutase nunca nada— pasaría toda la batería."""
    motor, adaptador, destino = _motor(tmp_path, armado=False)
    r = await motor.ejecutar(accion, ARGS, "t", "e", "prueba")
    assert r["estado"] == "ejecutada", f"{accion}: {r.get('motivo')}"
    assert destino.exists() and adaptador.ejecutadas == [accion]


# ================================================== ORDEN · kill ANTES de HITL --


async def test_f2_el_kill_switch_se_evalua_ANTES_que_la_confirmacion_humana(tmp_path):
    """`I-F2-5`. Con la parada armada, una acción de LISTA ROJA **no debe llegar a preguntar**: si
    preguntara, el orden estaría invertido y el kill switch habría dejado de ser el Paso 0."""
    preguntas: list[str] = []

    async def confirmador_que_registra(accion, args, trace_id):
        preguntas.append(accion)
        return True

    destino = tmp_path / "efecto.txt"
    kill = KillSwitch(trigger_file=str(tmp_path / "KILL"))
    kill.disengage()
    kill.engage("prueba F2")
    adaptador = AdaptadorQueEscribe(destino)
    motor = MotorAutomatizacion(adaptador, PermissionManager(confirmador_que_registra, kill_switch=kill))

    accion_roja = sorted(RED & ALTERA_ESTADO)[0]
    r = await motor.ejecutar(accion_roja, ARGS, "t", "e", "prueba")
    assert preguntas == [], f"se pidió confirmación pese al kill switch armado: {preguntas}"
    assert r["estado"] == "detenida" and not destino.exists()


# =============================================================== AUDITORÍA --


async def test_f2_la_detencion_por_kill_switch_queda_en_el_audit(tmp_path, monkeypatch):
    """`I-F2-3`. Una parada que no deja rastro es indistinguible de una acción que nunca se intentó."""
    from aura_skeleton import observability as obs

    registros: list[tuple] = []
    monkeypatch.setattr(obs, "log", lambda *a, **k: registros.append((a, k)))
    motor, _, _ = _motor(tmp_path, armado=True)
    await motor.ejecutar("escribir_archivo", ARGS, "t", "e", "prueba")
    # CORREGIDA 2026-08-25 tras el superviviente F2-M7. La version anterior aceptaba
    # `"DETENIDA" in texto or "kill" in texto.lower()`: ese `or` la volvia NO discriminante — dos
    # evidencias distintas contadas como si fueran la misma, de modo que borrar el registro del
    # ejecutor seguia pasando gracias al de permisos. La invariante declarada (I-F2-3) es
    # concreta: **existe un registro de AUDITORIA del bloqueo**, y eso es lo que se comprueba.
    de_auditoria = [(a, k) for a, k in registros if k.get("audit") is True]
    assert de_auditoria, f"ningun registro con audit=True: {registros}"
    assert any("kill switch" in " ".join(str(x) for x in a).lower() for a, _ in de_auditoria), (
        f"el audit no identifica el bloqueo por kill switch: {de_auditoria}")


# ============================= 17.3 · simular queda FUERA DE ALCANCE, y se fija --


async def test_f2_no_altera_el_comportamiento_de_simular(tmp_path):
    """**Decisión 17.3: `simular()` fuera del alcance de F2.** No se bloquea ni se permite
    especialmente: se deja como está. Esta prueba **fija** que F2 no le añadió semántica — el motor
    sigue simulando antes de permisos— y a la vez que eso **no rompe la garantía**, porque simular
    no muta.

    Si mañana alguien decide que la parada también detiene la simulación, esta prueba lo hará
    visible en vez de dejar que el cambio entre en silencio."""
    motor, adaptador, destino = _motor(tmp_path, armado=True)
    await motor.ejecutar("escribir_archivo", ARGS, "t", "e", "prueba")
    assert adaptador.simuladas == ["escribir_archivo"], "F2 no debe cambiar el dry-run"
    assert not destino.exists(), "simular no muta: la garantía se mantiene"
