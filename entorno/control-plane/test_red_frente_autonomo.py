"""El frente autónomo — **lo ya decidido no vuelve a la bandeja de excepciones**.

`bloqueos_registrados` reencuentra en cada vuelta lo que `estado.json` declara fuera de alcance, y
eso es deliberado: *«que siga apareciendo en cada vuelta es lo que impide que un bloqueo se convierta
en un olvido»*. Pero una entrada cuyo propio registro dice **`quien_desbloquea: "nadie: esta cerrada
como deuda aceptada"`** no es un bloqueo esperando decision: es una cuestion **ya resuelta**.

Contarla como `BLOQUEADA` convierte una decision tomada en una pendiente, que es exactamente lo que
un canal de excepciones no debe hacer. Su clase correcta ya existe y no hay que inventarla:
`FALSO_HUECO` —*«parece un hueco y no lo es; se descarta con su motivo»*—.

**El criterio se lee del dato, no se deduce.** Solo se reclasifica lo que el propio registro declara
sin desbloqueador; cualquier entrada con un desbloqueador nombrado sigue siendo `BLOQUEADA`.
"""

import pathlib

import control_plane as cp
import descubrimiento as des

PLANO = pathlib.Path(__file__).parent


def _estado_con(tmp_path, bloqueadas):
    (tmp_path / "estado.json").write_text(
        cp.json.dumps({"version": 1, "oportunidades_bloqueadas": bloqueadas})
        if hasattr(cp, "json") else __import__("json").dumps(
            {"version": 1, "oportunidades_bloqueadas": bloqueadas}), encoding="utf-8")


def test_una_deuda_cerrada_no_es_un_bloqueo_pendiente(tmp_path):
    _estado_con(tmp_path, [{"id": "OB-X", "que": "deuda aceptada", "por_que": "cerrada",
                            "quien_desbloquea": "nadie: esta cerrada como deuda aceptada"}])
    op = des.bloqueos_registrados(tmp_path, tmp_path)[0]
    assert op.estado == des.FALSO_HUECO
    assert "cerrada" in op.justificacion.lower()


def test_un_bloqueo_con_desbloqueador_NOMBRADO_sigue_bloqueado(tmp_path):
    _estado_con(tmp_path, [{"id": "OB-Y", "que": "algo real", "por_que": "exige acta",
                            "quien_desbloquea": "CEO"}])
    assert des.bloqueos_registrados(tmp_path, tmp_path)[0].estado == des.BLOQUEADA


def test_sin_desbloqueador_declarado_sigue_bloqueado(tmp_path):
    """**Fail-closed**: la ausencia del campo no es una declaracion de cierre."""
    _estado_con(tmp_path, [{"id": "OB-Z", "que": "algo", "por_que": "vete a saber"}])
    assert des.bloqueos_registrados(tmp_path, tmp_path)[0].estado == des.BLOQUEADA


def test_en_el_plano_real_OB3_deja_de_contarse_como_bloqueo():
    """`OB-3` es la deuda `G-1`, cerrada por `DEC-G1-MANIFIESTO-TRAS-F4 = C`. Su propio registro lo
    dice; contarla como pendiente era convertir una decision tomada en una por tomar."""
    ops = {o.detalle.get("id") or o.alcance: o for o in des.bloqueos_registrados(PLANO, PLANO)}
    por_estado = {}
    for o in des.bloqueos_registrados(PLANO, PLANO):
        por_estado.setdefault(o.estado, []).append(o)
    assert len(por_estado.get(des.BLOQUEADA, [])) == 5, "quedan cinco bloqueos reales"
    assert len(por_estado.get(des.FALSO_HUECO, [])) == 1, "OB-3 pasa a falso hueco"
    del ops


def test_el_frente_autonomo_no_lo_bloquea_una_decision_pendiente():
    """Las decisiones elevadas conviven con el trabajo: son bandeja de excepciones, no cola de
    autorizacion. Con 12 elevadas, el ciclo sigue pudiendo ejecutar lo que este en territorio."""
    ops = des.descubrir(PLANO, PLANO)
    elevadas = [o for o in ops if o.estado == des.DECISION_REQUIRED]
    assert len(elevadas) >= 10, "hay decisiones pendientes"
    import motor_autonomia as motor
    import inspect
    fuente = inspect.getsource(motor.trabajar)
    assert "cola agotada" in fuente
    assert "return" not in fuente.split("elevadas")[1].split("\n")[0], (
        "las elevadas no detienen el ciclo por si mismas")
