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

import pytest

import control_plane as cp
import descubrimiento as des

PLANO = pathlib.Path(__file__).parent
LOG_REAL = (PLANO / cp.NOMBRE_EVENTOS).resolve()


class EscrituraEnElLogReal(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _el_log_real_no_se_toca(monkeypatch):
    """**Ninguna prueba de este fichero escribe en el `eventos.jsonl` de produccion** (2026-10-23).

    `descubrir()` registra `descubrimiento_realizado` en el `directorio` que recibe, y una prueba le
    pasaba el plano real: cada ejecucion de la bateria anadia un evento al historial append-only (6 el
    2026-10-22; 31 el 2026-09-20). El guardian de `conftest.py` solo cubre `estado.json`.

    Se intercepta `cp.registrar_evento` —el unico escritor del log (`control_plane.py`)— y se compara la
    ruta RESUELTA del destino: un guardian por ruta es determinista; uno por hash fallaria cada vez que
    el cron `despertar` anade su linea mientras corre la bateria."""
    original = cp.registrar_evento

    def guardado(directorio, *args, **kwargs):
        if (pathlib.Path(directorio) / cp.NOMBRE_EVENTOS).resolve() == LOG_REAL:
            raise EscrituraEnElLogReal(f"una prueba intento escribir en el log de produccion {LOG_REAL}")
        return original(directorio, *args, **kwargs)

    monkeypatch.setattr(cp, "registrar_evento", guardado)


def _copia_del_plano(tmp_path) -> pathlib.Path:
    """El plano real copiado a `tmp_path`: las fuentes LEEN lo mismo (`estado.json`, eventos,
    politica) y todo lo que el descubrimiento escribe cae en la copia."""
    import shutil

    copia = tmp_path / "plano"
    shutil.copytree(PLANO, copia, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", "mutaciones", ".control-plane.lock"))
    return copia


def test_el_guardian_impide_escribir_en_el_log_real(monkeypatch):
    """Control del guardian. El escritor original se sustituye ANTES por un registro inocuo: si el
    guardian fallara, esta prueba tampoco escribiria en produccion."""
    llamadas = []
    monkeypatch.setattr(cp, "registrar_evento", lambda d, *a, **k: llamadas.append(d))
    _el_log_real_no_se_toca.__wrapped__(monkeypatch)
    with pytest.raises(EscrituraEnElLogReal):
        cp.registrar_evento(PLANO, "prueba", {})
    assert llamadas == []


def test_un_directorio_que_no_es_el_plano_si_puede_registrar(tmp_path):
    cp.registrar_evento(tmp_path, "prueba", {"x": 1})
    assert (tmp_path / cp.NOMBRE_EVENTOS).exists()


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


def test_en_el_plano_real_OB3_Y_OB2_dejan_de_contarse_como_bloqueos():
    """`OB-3` es la deuda `G-1`, cerrada por `DEC-G1-MANIFIESTO-TRAS-F4 = C`. Su propio registro lo
    dice; contarla como pendiente era convertir una decision tomada en una por tomar.

    **`OB-2` se le unio el 2026-09-21**, y conviene contar por que: declaraba bloqueante un defecto
    del auditor de garantias —«no resuelve rutas bajo `entorno/`»— que se habia corregido el
    2026-09-09. Medido de nuevo: `auditar_garantias('entorno/control-plane')` devuelve 41 declaradas
    y 0 rotas. Al corregir el registro, su `quien_desbloquea` paso a «nadie: corregida» y la regla
    de `bloqueos_registrados` lo reclasifico sola a `FALSO_HUECO`. **Eso es el mecanismo
    funcionando**, no un efecto colateral que haya que revertir: una cuestion resuelta deja de pedir
    decision.

    Los numeros siguen siendo literales a proposito. Derivarlos del propio `estado.json` haria que
    la prueba se calculase a si misma y dejara de controlar nada: es el caso de control, y tiene que
    romperse cuando el recuento cambie — como acaba de romperse."""
    ops = {o.detalle.get("id") or o.alcance: o for o in des.bloqueos_registrados(PLANO, PLANO)}
    por_estado = {}
    for o in des.bloqueos_registrados(PLANO, PLANO):
        por_estado.setdefault(o.estado, []).append(o)
    assert len(por_estado.get(des.BLOQUEADA, [])) == 4, "quedan cuatro bloqueos reales"
    assert len(por_estado.get(des.FALSO_HUECO, [])) == 2, "OB-3 y OB-2 pasan a falso hueco"
    del ops


def test_el_frente_autonomo_no_lo_bloquea_una_decision_pendiente(tmp_path):
    """Las decisiones elevadas conviven con el trabajo: son bandeja de excepciones, no cola de
    autorizacion. Con 12 elevadas, el ciclo sigue pudiendo ejecutar lo que este en territorio.

    Se descubre sobre el plano real (`raiz`, solo lectura) con el `directorio` en una COPIA: antes se
    pasaba `PLANO` y cada ejecucion anadia `descubrimiento_realizado` al log de produccion."""
    directorio = _copia_del_plano(tmp_path)
    antes = len(cp.leer_eventos(directorio))
    ops = des.descubrir(PLANO, directorio)
    tras = cp.leer_eventos(directorio)
    assert len(tras) == antes + 1 and tras[-1].get("tipo") == "descubrimiento_realizado", (
        "el evento del descubrimiento cae en la copia, no en el log de produccion")
    elevadas = [o for o in ops if o.estado == des.DECISION_REQUIRED]
    assert len(elevadas) >= 10, "hay decisiones pendientes"
    import motor_autonomia as motor
    import inspect
    fuente = inspect.getsource(motor.trabajar)
    assert "cola agotada" in fuente
    assert "return" not in fuente.split("elevadas")[1].split("\n")[0], (
        "las elevadas no detienen el ciclo por si mismas")
