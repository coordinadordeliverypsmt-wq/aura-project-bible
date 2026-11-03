"""RED · F4 — migración de la ruta de SOBERANÍA al camino único · + integración E2E.

`DP-D-M-8 §7` ordena F4 así, literalmente: *«Soberanía (borrar/refutar/cablear `corregir`) → reglas
(crear/desactivar) → señales. De más peligrosa a menos.»* Este fichero cubre **el primer tramo**.

El defecto que cierra es el de `ALERTA-006`: `ModeloUsuario.borrar` llamaba a `memoria.olvidar`
**directamente**, sin motor, sin permisos y sin kill switch. Con la parada armada, el dato se
destruía igual.

**Flujo que se exige demostrar de extremo a extremo:**
`operación → catálogo → sujeto → authorize → kill switch → motor → ejecutor → audit → persistencia`.

**Fail-closed:** un `ModeloUsuario` sin motor **no muta**. No hay ruta directa de reserva — sería la
segunda vía que `ALERTA-005` prohíbe.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory


async def _nunca_confirma(accion, args, trace_id):
    raise AssertionError(f"la soberanía del usuario no debe pasar por HITL: {accion}")


def _sistema(tmp_path, armado: bool):
    """Sistema real cableado como en producción: memoria → ejecutor → motor → modelo."""
    ruta = tmp_path / "memoria.json"
    mem = PersistentMemory(str(ruta))
    mem._items = [
        {"user_id": "mauricio", "kind": "semantica", "content": "tiene alergia a la penicilina",
         "provenance": {"origen": "declarada"}},
        {"user_id": "mauricio", "kind": "semantica", "content": "prefiere el te",
         "provenance": {"origen": "declarada"}},
    ]
    mem._persist()
    kill = KillSwitch(trigger_file=str(tmp_path / "KILL"))
    kill.disengage()
    if armado:
        kill.engage("prueba F4")
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_nunca_confirma, kill_switch=kill))
    return ModeloUsuario(mem, motor=motor), mem, ruta


def _lineas(ruta):
    return len(ruta.read_text(encoding="utf-8").splitlines())


# ============================================== META-CONTROL · ejecutar SÍ funciona --


async def test_meta_con_la_parada_DESARMADA_el_borrado_ocurre_de_verdad(tmp_path):
    """**El control que impide el falso GREEN.** Si el borrado no funcionara por el camino nuevo,
    todas las pruebas de bloqueo pasarían «porque nada hace nada» y este fichero mentiría."""
    modelo, mem, _ = _sistema(tmp_path, armado=False)
    n = await modelo.borrar("mauricio", "penicilina")
    assert n == 1, "el camino único debe poder EJECUTAR, no solo bloquear"
    assert "tiene alergia a la penicilina" not in [i["content"] for i in mem._items]


async def test_meta_la_refutacion_ocurre_de_verdad(tmp_path):
    modelo, mem, _ = _sistema(tmp_path, armado=False)
    n = await modelo.refutar("mauricio", "penicilina")
    assert n == 1
    assert any(i["provenance"].get("refutada") for i in mem._items)


# ==================================================== LA GARANTÍA · G-2 y G-3 #4 --


async def test_f4_el_kill_switch_armado_DETIENE_el_borrado(tmp_path):
    """G-2, por efecto real y **sobre el disco**, no sobre la lista en memoria."""
    modelo, mem, ruta = _sistema(tmp_path, armado=True)
    antes = ruta.read_text(encoding="utf-8")
    n = await modelo.borrar("mauricio", "penicilina")
    assert n == 0
    assert "tiene alergia a la penicilina" in [i["content"] for i in mem._items]
    assert ruta.read_text(encoding="utf-8") == antes, "el almacén cambió con la parada armada"


async def test_f4_el_kill_switch_armado_DETIENE_la_refutacion(tmp_path):
    modelo, mem, _ = _sistema(tmp_path, armado=True)
    n = await modelo.refutar("mauricio", "penicilina")
    assert n == 0
    assert not any(i["provenance"].get("refutada") for i in mem._items)


async def test_f4_la_operacion_esta_catalogada_y_por_eso_puede_ejecutarse(tmp_path):
    """G-3 #4: antes se ejecutaba **sin estar catalogada**. Ahora existe en el catálogo y por eso
    `authorize` la deja pasar — no por casualidad de que nadie la mirase."""
    from aura_skeleton.core.permissions import CATALOGO
    assert "olvidar_informacion_usuario" in CATALOGO
    modelo, _, _ = _sistema(tmp_path, armado=False)
    assert await modelo.borrar("mauricio", "penicilina") == 1


# =========================================================== FAIL-CLOSED · sin motor --


async def test_f4_sin_motor_NO_hay_ruta_directa(tmp_path):
    """Si quedara una ruta directa de reserva, la migración sería decorativa: bastaría construir el
    modelo sin motor para volver a mutar sin control."""
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    mem._items = [{"user_id": "mauricio", "kind": "semantica", "content": "dato", "provenance": {}}]
    mem._persist()
    modelo = ModeloUsuario(mem)          # sin motor: fuera del sistema
    assert await modelo.borrar("mauricio", "dato") == 0
    assert [i["content"] for i in mem._items] == ["dato"], "mutó sin pasar por el motor"


# ========================================================== SUJETO · F3 en la cadena --


async def test_f4_sin_sujeto_la_cadena_se_detiene_en_authorize(tmp_path):
    """El par `(operacion, sujeto)` de §4.2, ejercido de extremo a extremo."""
    modelo, mem, _ = _sistema(tmp_path, armado=False)
    assert await modelo.borrar("", "penicilina") == 0
    assert len(mem._items) == 2


# =============================================================== AUDIT · G-6 (§5.1) --


async def test_f4_el_audit_registra_QUE_se_borro_y_SOBRE_QUIEN(tmp_path, monkeypatch):
    """`§5.1`: *«a partir del audit log debe poder responderse ¿qué había antes y qué hay ahora?»*.
    Sin contenido ni sujeto, el registro existe pero no permite reconstruir lo perdido."""
    from aura_skeleton import observability as obs
    registros: list[tuple] = []
    monkeypatch.setattr(obs, "log", lambda *a, **k: registros.append((a, k)))
    modelo, _, _ = _sistema(tmp_path, armado=False)
    await modelo.borrar("mauricio", "penicilina")
    de_auditoria = " ".join(" ".join(str(x) for x in a) for a, k in registros if k.get("audit") is True)
    assert "tiene alergia a la penicilina" in de_auditoria, "el audit no dice QUÉ se borró"
    assert "mauricio" in de_auditoria, "el audit no dice SOBRE QUIÉN recayó"


async def test_f4_el_bloqueo_por_kill_switch_tambien_queda_auditado(tmp_path, monkeypatch):
    from aura_skeleton import observability as obs
    registros: list[tuple] = []
    monkeypatch.setattr(obs, "log", lambda *a, **k: registros.append((a, k)))
    modelo, _, _ = _sistema(tmp_path, armado=True)
    await modelo.borrar("mauricio", "penicilina")
    de_auditoria = [(a, k) for a, k in registros if k.get("audit") is True]
    assert any("kill switch" in " ".join(str(x) for x in a).lower() for a, _ in de_auditoria)


# ======================================================================== E2E --


@pytest.mark.parametrize("armado,esperado", [(False, 1), (True, 0)])
async def test_e2e_flujo_completo_de_soberania(armado, esperado, tmp_path):
    """**La prueba de la sesión.** Recorre `operación → catálogo → sujeto → authorize → kill switch
    → motor → ejecutor → audit → persistencia` y comprueba el resultado **en disco**, releyendo el
    almacén desde cero: si el olvido no persistiera, el dato reaparecería al reiniciar."""
    modelo, _, ruta = _sistema(tmp_path, armado=armado)
    n = await modelo.borrar("mauricio", "penicilina")
    assert n == esperado
    releida = PersistentMemory(str(ruta))
    vivos = [i["content"] for i in releida._items]
    assert ("tiene alergia a la penicilina" in vivos) is bool(armado), (
        f"persistencia incoherente con armado={armado}: {vivos}")
    assert "prefiere el te" in vivos, "el olvido selectivo se llevó por delante otra entrada"


# =========== CASOS AÑADIDOS 2026-08-25 por mutantes SUPERVIVIENTES de la batería del bloque --


async def test_refutar_lo_YA_refutado_no_narra_efecto(tmp_path):
    """Lo destapó `BLQ-M8`. Refutar dos veces lo mismo no tiene efecto la segunda vez, y decir que
    sí lo tuvo es INV-9 —«no se finge capacidad»— y el punto 4 de ALERTA-005.

    Mi batería probaba la refutación **una** vez, así que borrar el filtro de «solo vivas» no rompía
    nada aquí: el mutante sobrevivía por falta de cobertura, no porque el código estuviera protegido.
    """
    modelo, _, _ = _sistema(tmp_path, armado=False)
    assert await modelo.refutar("mauricio", "penicilina") == 1
    assert await modelo.refutar("mauricio", "penicilina") == 0, (
        "la segunda refutación no puede contar como efecto")


def test_el_ejecutor_no_atiende_acciones_ajenas(tmp_path):
    """Lo destapó `BLQ-M9`. Un ejecutor que responde a todo se convierte en comodín: resolvería
    `borrar_archivo` con la lógica de olvidar información del usuario."""
    from aura_skeleton.core.ejecutor_modelo_usuario import ACCIONES, EjecutorModeloUsuario
    ejecutor = EjecutorModeloUsuario(PersistentMemory(str(tmp_path / "m.json")))
    for accion in ACCIONES:
        assert ejecutor.para(accion) is ejecutor
    for ajena in ("borrar_archivo", "consulta", "accion_financiera", "lo_que_sea"):
        assert ejecutor.para(ajena) is None, f"atendió una acción ajena: {ajena}"


# ============== `corregir` — el tercer verbo del tramo soberanía (§7: «cablear `corregir`») --


async def test_corregir_marca_y_registra_POR_EL_MOTOR(tmp_path):
    """`§7` incluye `corregir` en el tramo de soberanía, y era la última ruta huérfana del grupo:
    mutaba `provenance` sobre `_items` **en RAM y sin pasar por el motor**, y solo la escritura de la
    corrección usaba `write`.

    Corregir son dos operaciones del catálogo, no una: **refutar** lo anterior y **registrar** la
    versión del usuario. Ambas ya existen y ambas deben atravesar el camino único.
    """
    modelo, mem, _ = _sistema(tmp_path, armado=False)
    await modelo.corregir("mauricio", "prefiere el te", "prefiere el cafe")

    contenidos = [i["content"] for i in mem._items]
    assert "prefiere el cafe" in contenidos, "la corrección del usuario no se registró"
    anterior = next(i for i in mem._items if i["content"] == "prefiere el te")
    assert anterior["provenance"].get("refutada") is True, "lo corregido debe quedar marcado"


async def test_corregir_NO_ocurre_con_el_kill_switch_armado(tmp_path):
    """Ni la marca ni el registro: la parada detiene **las dos** operaciones."""
    modelo, mem, ruta = _sistema(tmp_path, armado=True)
    antes = ruta.read_text(encoding="utf-8")
    await modelo.corregir("mauricio", "prefiere el te", "prefiere el cafe")

    contenidos = [i["content"] for i in mem._items]
    assert "prefiere el cafe" not in contenidos, "se registró la corrección con la parada armada"
    anterior = next(i for i in mem._items if i["content"] == "prefiere el te")
    assert not anterior["provenance"].get("refutada"), "se marcó como refutada con la parada armada"
    assert ruta.read_text(encoding="utf-8") == antes, "el almacén cambió en disco"


async def test_corregir_sin_motor_no_muta(tmp_path):
    """Fail-closed, igual que `borrar` y `refutar`: sin motor no hay ruta directa de reserva."""
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    mem._items = [{"user_id": "mauricio", "kind": "semantica", "content": "prefiere el te",
                   "provenance": {"origen": "declarada"}}]
    mem._persist()
    await ModeloUsuario(mem).corregir("mauricio", "prefiere el te", "prefiere el cafe")
    assert [i["content"] for i in mem._items] == ["prefiere el te"]
