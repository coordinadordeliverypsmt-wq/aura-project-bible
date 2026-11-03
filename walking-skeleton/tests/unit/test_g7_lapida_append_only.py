"""RED · G-7 — append-only en la memoria: LÁPIDA en vez de reescritura.

`DP-D-M-8 §5.2` no lo propone, lo **ordena**: *«`memoria.json · olvidar`: reescribe todo, destruye
historia → **lápida: anexar baja lógica**»*, *«`marcar`: reescribe todo → anexar marca»*, y cierra
con *«**La memoria debe adoptar el patrón que las reglas ya usan**, no inventar otro»*.

El patrón existe y está en verde: `AlmacenReglas.desactivar` anexa una línea `inactiva` y la lectura
proyecta quedándose con la última. Aquí se aplica el mismo modelo:

    historial físico completo  +  última línea por clave  =  estado lógico

**La purga física queda FUERA.** `§5.2` la deja abierta con un «No lo decido aquí» explícito, y esta
batería no la implementa ni la presupone.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory


async def _si(accion, args, trace_id):
    return True


def _sistema(tmp_path, armado=False):
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
        kill.engage("prueba G-7")
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si, kill_switch=kill))
    return ModeloUsuario(mem, motor=motor), mem, ruta


def _lineas(ruta):
    return len(ruta.read_text(encoding="utf-8").splitlines())


# ============================================================ META-CONTROL --


async def test_meta_el_olvido_ocurre_de_verdad(tmp_path):
    """Sin esto, una memoria que dejara de olvidar pasaría toda la batería append-only."""
    modelo, mem, _ = _sistema(tmp_path)
    assert await modelo.borrar("mauricio", "penicilina") == 1
    assert "tiene alergia a la penicilina" not in [i["content"] for i in mem._items]


# ================================================== LA GARANTÍA · append-only --


async def test_g7_olvidar_NO_reduce_las_lineas_del_almacen(tmp_path):
    """La garantía literal de G-7."""
    modelo, _, ruta = _sistema(tmp_path)
    antes = _lineas(ruta)
    await modelo.borrar("mauricio", "penicilina")
    assert _lineas(ruta) >= antes, f"el almacén perdió líneas ({antes} -> {_lineas(ruta)})"


async def test_g7_el_olvido_ANEXA_una_lapida(tmp_path):
    """No basta con no perder líneas: debe quedar **constancia** de la baja."""
    modelo, _, ruta = _sistema(tmp_path)
    antes = _lineas(ruta)
    await modelo.borrar("mauricio", "penicilina")
    assert _lineas(ruta) == antes + 1, "debe anexar exactamente una lápida"
    ultima = ruta.read_text(encoding="utf-8").splitlines()[-1]
    assert "penicilina" in ultima, "la lápida no identifica qué se dio de baja"


async def test_g7_el_historial_FISICO_permanece(tmp_path):
    """*«reescribe todo, destruye historia»* era el defecto. La línea original sigue en disco."""
    modelo, _, ruta = _sistema(tmp_path)
    await modelo.borrar("mauricio", "penicilina")
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    originales = [ln for ln in lineas if "penicilina" in ln and '"_olvidada": true' not in ln.lower()]
    assert originales, "la entrada original desapareció del historial"


async def test_g7_la_proyeccion_al_RELEER_del_disco_excluye_lo_olvidado(tmp_path):
    """El eslabón que hace útil la lápida: si al reiniciar el dato volviera, el olvido sería falso."""
    modelo, _, ruta = _sistema(tmp_path)
    await modelo.borrar("mauricio", "penicilina")
    releida = PersistentMemory(str(ruta))
    contenidos = [i["content"] for i in releida._items]
    assert "tiene alergia a la penicilina" not in contenidos, "lo olvidado reapareció al reiniciar"
    assert "prefiere el te" in contenidos, "el olvido selectivo se llevó otra entrada"


async def test_g7_marcar_tambien_anexa_en_vez_de_reescribir(tmp_path):
    """`§5.2` lo pide en la misma tabla: `marcar` → «anexar marca»."""
    modelo, _, ruta = _sistema(tmp_path)
    antes = _lineas(ruta)
    assert await modelo.refutar("mauricio", "penicilina") == 1
    assert _lineas(ruta) > antes, "la refutación reescribió en vez de anexar"
    releida = PersistentMemory(str(ruta))
    refutadas = [i for i in releida._items if i["provenance"].get("refutada")]
    assert len(refutadas) == 1, "la marca no sobrevivió al reinicio proyectada"


# ================================================ EL CAMINO ÚNICO SE MANTIENE --


async def test_g7_con_la_parada_ARMADA_no_se_anexa_nada(tmp_path):
    modelo, mem, ruta = _sistema(tmp_path, armado=True)
    antes = ruta.read_text(encoding="utf-8")
    await modelo.borrar("mauricio", "penicilina")
    assert ruta.read_text(encoding="utf-8") == antes, "el almacén cambió con la parada armada"
    assert "tiene alergia a la penicilina" in [i["content"] for i in mem._items]


async def test_g7_el_audit_sigue_identificando_QUE_y_SOBRE_QUIEN(tmp_path, monkeypatch):
    """G-6 no se degrada para conseguir G-7."""
    from aura_skeleton import observability as obs
    registros: list[tuple] = []
    monkeypatch.setattr(obs, "log", lambda *a, **k: registros.append((a, k)))
    modelo, _, _ = _sistema(tmp_path)
    await modelo.borrar("mauricio", "penicilina")
    auditoria = " ".join(" ".join(str(x) for x in a) for a, k in registros if k.get("audit") is True)
    assert "tiene alergia a la penicilina" in auditoria and "mauricio" in auditoria


@pytest.mark.parametrize("armado,vivos", [(False, 1), (True, 2)])
async def test_e2e_olvido_con_lapida_extremo_a_extremo(armado, vivos, tmp_path):
    """catálogo → sujeto → authorize → kill switch → motor → ejecutor → audit → **lápida** →
    proyección → estado lógico, releído del disco."""
    modelo, _, ruta = _sistema(tmp_path, armado=armado)
    await modelo.borrar("mauricio", "penicilina")
    releida = PersistentMemory(str(ruta))
    assert len(releida._items) == vivos


# ============= CASO AÑADIDO 2026-08-25 por el mutante SUPERVIVIENTE G7-M7 --


async def test_g7_la_lapida_de_un_usuario_no_alcanza_a_otro(tmp_path):
    """Lo destapó `G7-M7`. La clave de proyección incluye `user_id`, y debe: dos personas pueden
    haber declarado **exactamente lo mismo**, y el olvido de una no puede llevarse el recuerdo de la
    otra. Es el aislamiento por usuario de `P-ARQ-5` aplicado a la proyección.

    Mi batería usaba un solo usuario, así que quitar `user_id` de la clave no rompía nada: el mutante
    sobrevivía por falta de cobertura, no porque el código estuviera protegido.
    """
    ruta = tmp_path / "memoria.json"
    mem = PersistentMemory(str(ruta))
    mem._items = [
        {"user_id": "mauricio", "kind": "semantica", "content": "prefiere el te", "provenance": {}},
        {"user_id": "otra", "kind": "semantica", "content": "prefiere el te", "provenance": {}},
    ]
    mem._persist()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    assert await ModeloUsuario(mem, motor=motor).borrar("mauricio", "prefiere el te") == 1

    releida = PersistentMemory(str(ruta))
    dueños = [i["user_id"] for i in releida._items]
    assert dueños == ["otra"], f"la lápida cruzó de usuario: {dueños}"
