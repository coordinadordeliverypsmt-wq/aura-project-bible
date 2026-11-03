"""RED · F4 tramos 2 y 3 — REGLAS y SEÑALES por el camino único.

`DP-D-M-8 §7` fija el orden del tramo F4: *«soberanía (borrar/refutar/cablear `corregir`) → reglas
(crear/desactivar) → señales»*. Soberanía ya está cerrada; esto es lo que falta.

**El defecto que cierran, medido:** `AlmacenReglas.crear` escribía `reglas.jsonl` **sin motor, sin
permisos y sin kill switch** —es el rojo `test_g2_el_kill_switch_armado_no_detiene_la_creacion_de_reglas`—
y `AlmacenSenales.guardar` escribía conocimiento sobre la persona directamente con `memoria.write`,
que es el hueco que `§4.2` denuncia: *«la captura de señales escribe conocimiento sobre el usuario
sin correspondencia alguna»*.

**Sin motor, ninguna de las dos muta.** Fail-closed, igual que la soberanía: una ruta directa de
reserva sería la segunda vía que `ALERTA-005` prohíbe.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.almacen_senales import AlmacenSenales
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.ejecutor_reglas import EjecutorReglas
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.core.reglas import AlmacenReglas, ReglaUsuario
from aura_skeleton.core.senales import ClaseSenal, Senal
from aura_skeleton.modules.memory import PersistentMemory


async def _confirma(accion, args, trace_id):
    return True


def _regla(rule_id="r1", user_id="mauricio"):
    return ReglaUsuario(rule_id=rule_id, user_id=user_id, evento="archivo_creado",
                        condicion={}, accion="copiar_archivo", args={})


def _sistema(tmp_path, armado: bool):
    """Reglas + señales cableadas al MISMO motor, como en producción."""
    ruta_reglas = tmp_path / "reglas.jsonl"
    mem = PersistentMemory(str(tmp_path / "memoria.json"))
    kill = KillSwitch(trigger_file=str(tmp_path / "KILL"))
    kill.disengage()
    if armado:
        kill.engage("prueba F4")
    permisos = PermissionManager(_confirma, kill_switch=kill)
    registro = RegistroAdaptadores([EjecutorModeloUsuario(mem)])
    motor = MotorAutomatizacion(registro, permisos)
    almacen = AlmacenReglas(str(ruta_reglas), motor=motor)
    registro.registrar(EjecutorReglas(almacen))
    senales = AlmacenSenales(mem, motor=motor)
    return almacen, senales, mem, ruta_reglas


def _lineas(ruta):
    return len(ruta.read_text(encoding="utf-8").splitlines()) if ruta.exists() else 0


# ========================================== META-CONTROL · ejecutar SÍ funciona --


async def test_meta_con_la_parada_DESARMADA_la_regla_se_crea_de_verdad(tmp_path):
    """Sin este control, un almacén que dejara de escribir pasaría toda la batería de bloqueo."""
    almacen, _, _, ruta = _sistema(tmp_path, armado=False)
    await almacen.crear(_regla())
    assert _lineas(ruta) == 1, "la creación debe poder ejecutarse por el camino único"
    assert [r.rule_id for r in almacen.listar("mauricio")] == ["r1"]


async def test_meta_la_senal_se_guarda_de_verdad(tmp_path):
    _, senales, mem, _ = _sistema(tmp_path, armado=False)
    n = await senales.guardar("mauricio", [Senal(clase=ClaseSenal.PREFERENCIA_DECLARADA, contenido="prefiere el te",
                                                 fuente="conversacion", trace_id="t", ts=1.0)])
    assert n == 1
    assert "prefiere el te" in [i["content"] for i in mem._items]


# ================================================== LA GARANTÍA · G-2 en reglas --


async def test_el_kill_switch_armado_impide_CREAR_una_regla(tmp_path):
    """El rojo histórico `test_g2_el_kill_switch_armado_no_detiene_la_creacion_de_reglas`, cerrado
    por efecto real **en disco**."""
    almacen, _, _, ruta = _sistema(tmp_path, armado=True)
    await almacen.crear(_regla())
    assert _lineas(ruta) == 0, "se escribió reglas.jsonl con la parada armada"
    assert almacen.listar("mauricio") == []


async def test_el_kill_switch_armado_impide_DESACTIVAR_una_regla(tmp_path):
    """Desactivar también muta el almacén: anexa una línea. La parada la detiene igual."""
    almacen, _, _, ruta = _sistema(tmp_path, armado=False)
    await almacen.crear(_regla())
    lineas = _lineas(ruta)

    almacen._motor.permisos._kill.engage("armado a mitad")
    assert await almacen.desactivar("mauricio", "r1") is False
    assert _lineas(ruta) == lineas, "el almacén creció con la parada armada"
    assert [r.rule_id for r in almacen.listar("mauricio")] == ["r1"], "la regla quedó desactivada"


async def test_el_kill_switch_armado_impide_guardar_SENALES(tmp_path):
    """§4.2: la captura escribía conocimiento sobre la persona sin pasar por el catálogo."""
    _, senales, mem, _ = _sistema(tmp_path, armado=True)
    n = await senales.guardar("mauricio", [Senal(clase=ClaseSenal.PREFERENCIA_DECLARADA, contenido="prefiere el te",
                                                 fuente="conversacion", trace_id="t", ts=1.0)])
    assert n == 0
    assert mem._items == []


# ============================================================ FAIL-CLOSED --


async def test_sin_motor_las_reglas_no_mutan(tmp_path):
    ruta = tmp_path / "r.jsonl"
    almacen = AlmacenReglas(str(ruta))
    await almacen.crear(_regla())
    assert _lineas(ruta) == 0 and almacen.listar("mauricio") == []


async def test_sin_motor_las_senales_no_se_guardan(tmp_path):
    mem = PersistentMemory(str(tmp_path / "m.json"))
    n = await AlmacenSenales(mem).guardar("mauricio", [Senal(
        clase=ClaseSenal.PREFERENCIA_DECLARADA, contenido="x", fuente="c", trace_id="t", ts=1.0)])
    assert n == 0 and mem._items == []


# =============================================== PERSISTENCIA Y DESACTIVACIÓN --


async def test_desactivar_ANEXA_y_no_reescribe(tmp_path):
    """`§5.2` llama a `AlmacenReglas.desactivar` *«el modelo a imitar»*. Migrarlo al motor no puede
    degradar esa propiedad: sigue anexando, nunca reescribiendo."""
    almacen, _, _, ruta = _sistema(tmp_path, armado=False)
    await almacen.crear(_regla())
    antes = _lineas(ruta)
    assert await almacen.desactivar("mauricio", "r1") is True
    assert _lineas(ruta) == antes + 1, "debe anexar una línea, no reescribir"
    assert almacen.listar("mauricio") == []


async def test_la_regla_sobrevive_al_reinicio(tmp_path):
    """Persistencia real: se relee el fichero desde cero."""
    almacen, _, _, ruta = _sistema(tmp_path, armado=False)
    await almacen.crear(_regla())
    releido = AlmacenReglas(str(ruta))
    assert [r.rule_id for r in releido.listar("mauricio")] == ["r1"]


@pytest.mark.parametrize("armado,esperado", [(False, 1), (True, 0)])
async def test_e2e_regla_extremo_a_extremo(armado, esperado, tmp_path):
    """catálogo → authorize → kill switch → motor → ejecutor → audit → persistencia, releído del disco."""
    almacen, _, _, ruta = _sistema(tmp_path, armado=armado)
    await almacen.crear(_regla())
    releido = AlmacenReglas(str(ruta))
    assert len(releido.listar("mauricio")) == esperado


# ======== CASOS AÑADIDOS 2026-08-25 por mutantes SUPERVIVIENTES (RSN-M3, RSN-M7) --


def test_el_ejecutor_de_reglas_no_atiende_capacidades_ajenas(tmp_path):
    """Lo destapó `RSN-M3`. Un ejecutor que responde a todo se vuelve comodín: resolvería
    `borrar_archivo` con la lógica de las automatizaciones."""
    almacen, _, _, _ = _sistema(tmp_path, armado=False)
    ejecutor = EjecutorReglas(almacen)
    assert ejecutor.para("automatizacion") is ejecutor
    for ajena in ("borrar_archivo", "consulta", "olvidar_informacion_usuario", "lo_que_sea"):
        assert ejecutor.para(ajena) is None, f"atendió una capacidad ajena: {ajena}"


async def test_la_senal_conserva_su_TIPO_de_memoria(tmp_path):
    """Lo destapó `RSN-M7`. `4.1 §1` define tres memorias y la captura reparte entre **semántica** y
    **procedimental**. Si el registro fuerza «semantica», un patrón de uso se guarda como si fuera
    algo que el usuario declaró sobre sí mismo, y la taxonomía se pierde en silencio.

    Mi batería solo guardaba una preferencia declarada —semántica—, así que borrar el reparto no
    rompía nada: el mutante sobrevivía por falta de cobertura, no porque el código lo protegiera.
    """
    _, senales, mem, _ = _sistema(tmp_path, armado=False)
    await senales.guardar("mauricio", [
        Senal(clase=ClaseSenal.PREFERENCIA_DECLARADA, contenido="prefiere el te",
              fuente="conversacion", trace_id="t", ts=1.0),
        Senal(clase=ClaseSenal.PATRON_DE_USO, contenido="borra los viernes",
              fuente="computador", trace_id="t", ts=2.0),
    ])
    por_contenido = {i["content"]: i["kind"] for i in mem._items}
    assert por_contenido["prefiere el te"] == "semantica"
    assert por_contenido["borra los viernes"] == "procedimental", "se perdió el tipo de la señal"
