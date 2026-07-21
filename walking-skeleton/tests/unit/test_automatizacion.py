"""M2.3 — Motor de automatizacion: dry-run obligatorio y previsualizacion antes de confirmar.

Pruebas adversariales. La evidencia central que exige el CEO es que el dry-run NO produzca ningun
efecto sobre el sistema de archivos: se comprueba comparando una huella completa del directorio
(nombres, tamanos y mtime en nanosegundos) antes y despues.
"""

import os

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.contracts import Event
from aura_skeleton.core.automatizacion import MotorAutomatizacion, Regla
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.permissions import RED, PermissionManager


def _huella(raiz):
    """Huella del arbol: nombre, tamano y mtime en ns. Detecta cualquier efecto, incluso sobrescribir
    un archivo con contenido del mismo tamano."""
    out = {}
    for d, _, ns in os.walk(raiz):
        for n in ns:
            r = os.path.join(d, n)
            st = os.lstat(r)
            out[r] = (st.st_size, st.st_mtime_ns)
    return out


async def _niega(a, ar, t):
    return False


async def _confirma(a, ar, t):
    return True


def _altera(accion):
    return accion in {"borrar_archivo", "mover_archivo", "renombrar_archivo", "escribir_archivo"}


@pytest.fixture
def entorno(tmp_path):
    (tmp_path / "datos.txt").write_text("informacion del usuario")
    (tmp_path / "otro.txt").write_text("mas datos")
    ad = AdaptadorComputador(raices=(str(tmp_path),))
    return tmp_path, ad


def _ev():
    return Event("sensor.disco_lleno", "t1", "mauricio", {})


# ------------------------------------------------------------------ dry-run --


@pytest.mark.parametrize(
    "accion,mk",
    [
        ("borrar_archivo", lambda p: {"ruta": str(p / "datos.txt")}),
        ("escribir_archivo", lambda p: {"ruta": str(p / "datos.txt"), "contenido": "SOBRESCRITO"}),
        ("mover_archivo", lambda p: {"origen": str(p / "datos.txt"), "destino": str(p / "movido.txt")}),
    ],
)
@pytest.mark.asyncio
async def test_dry_run_no_produce_ningun_efecto(accion, mk, entorno):
    """EVIDENCIA CENTRAL: la simulacion deja el arbol byte a byte identico."""
    ruta, ad = entorno
    antes = _huella(ruta)

    plan = await ad.simular(accion, mk(ruta), "t")

    assert plan["viable"] is True and plan["altera_estado"] is True
    assert plan["efecto"], "el plan debe describir que ocurriria"
    assert _huella(ruta) == antes, f"el dry-run de {accion} produjo efectos reales"


@pytest.mark.asyncio
async def test_dry_run_de_operacion_inviable_tampoco_toca_nada(entorno):
    """Un plan NO viable tampoco puede dejar rastro (p. ej. destino ocupado)."""
    ruta, ad = entorno
    antes = _huella(ruta)
    plan = await ad.simular(
        "mover_archivo", {"origen": str(ruta / "datos.txt"), "destino": str(ruta / "otro.txt")}, "t"
    )
    assert plan["viable"] is False and "ya existe" in plan["motivo"]
    assert _huella(ruta) == antes


# ------------------------------------------------------ motor y lista roja ---


@pytest.mark.asyncio
async def test_accion_roja_sin_confirmacion_no_se_ejecuta(entorno):
    """Ninguna accion de lista roja se ejecuta sin confirmacion explicita."""
    ruta, ad = entorno
    antes = _huella(ruta)
    motor = MotorAutomatizacion(ad, PermissionManager(_niega), _altera)
    motor.agregar(Regla("limpieza", "sensor.disco_lleno", "borrar_archivo", {"ruta": str(ruta / "datos.txt")}))

    r = await motor.disparar(motor.reglas[0], _ev())

    assert r["estado"] == "detenida"
    assert _huella(ruta) == antes, "se borro pese a no haber confirmacion"


@pytest.mark.asyncio
async def test_la_confirmacion_recibe_la_previsualizacion(entorno):
    """Confirmar a ciegas no es consentimiento informado: el plan debe llegar a quien confirma."""
    ruta, ad = entorno
    visto = {}

    async def confirma_capturando(accion, args, tid):
        visto.update(args)
        return True

    motor = MotorAutomatizacion(ad, PermissionManager(confirma_capturando), _altera)
    regla = Regla("limpieza", "sensor.disco_lleno", "borrar_archivo", {"ruta": str(ruta / "datos.txt")})
    await motor.disparar(regla, _ev())

    assert "_previsualizacion" in visto, "la confirmacion no recibio el plan"
    assert "se eliminaria" in visto["_previsualizacion"]


@pytest.mark.asyncio
async def test_kill_switch_detiene_el_motor_de_reglas(entorno, tmp_path):
    """RN-3: el kill switch debe alcanzar a las automatizaciones, no solo al turno conversacional."""
    ruta, ad = entorno
    ks = KillSwitch(str(tmp_path / "KILL"))
    ks.engage("emergencia")
    # La huella se toma DESPUES de armar el kill switch: su archivo disparador vive en el mismo
    # directorio y forma parte del montaje de la prueba, no del efecto que se quiere medir.
    antes = _huella(ruta)
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma, kill_switch=ks), _altera)
    regla = Regla("limpieza", "sensor.disco_lleno", "borrar_archivo", {"ruta": str(ruta / "datos.txt")})

    r = await motor.disparar(regla, _ev())

    assert r["estado"] == "detenida"
    assert _huella(ruta) == antes


@pytest.mark.asyncio
async def test_adaptador_sin_dry_run_no_puede_alterar_estado(entorno):
    """Si el adaptador no sabe simular, no se le permite ejecutar acciones que alteren."""
    ruta, _ = entorno

    class SinSimulacion:
        name = "parcial"
        capabilities = ["borrar_archivo"]

        async def execute(self, command, args, trace_id, event_id):
            raise AssertionError("no debio ejecutarse")

    motor = MotorAutomatizacion(SinSimulacion(), PermissionManager(_confirma), _altera)
    regla = Regla("r", "sensor.disco_lleno", "borrar_archivo", {"ruta": str(ruta / "datos.txt")})
    r = await motor.disparar(regla, _ev())
    assert r["estado"] == "detenida" and "dry-run" in r["motivo"]


@pytest.mark.asyncio
async def test_dry_run_inviable_impide_la_ejecucion(entorno):
    """Si el plan no es viable, no se intenta ejecutar aunque el usuario confirmase."""
    ruta, ad = entorno
    antes = _huella(ruta)
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma), _altera)
    regla = Regla(
        "mover",
        "sensor.disco_lleno",
        "mover_archivo",
        {"origen": str(ruta / "datos.txt"), "destino": str(ruta / "otro.txt")},
    )
    r = await motor.disparar(regla, _ev())
    assert r["estado"] == "detenida" and "no viable" in r["motivo"]
    assert _huella(ruta) == antes


# --------------------------------------------------------------- control ----


@pytest.mark.asyncio
async def test_control_la_automatizacion_si_ejecuta_cuando_todo_es_correcto(entorno):
    """CONTROL: sin esto, un motor que rechazara TODO daria PASS en las pruebas anteriores."""
    ruta, ad = entorno
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma), _altera)
    regla = Regla("limpieza", "sensor.disco_lleno", "borrar_archivo", {"ruta": str(ruta / "datos.txt")})

    r = await motor.disparar(regla, _ev())

    assert r["estado"] == "ejecutada"
    assert not (ruta / "datos.txt").exists(), "la accion confirmada deberia haberse ejecutado"
    assert r["plan"]["efecto"].startswith("se eliminaria")


@pytest.mark.asyncio
async def test_regla_solo_dispara_con_su_evento_y_condicion(entorno):
    ruta, ad = entorno
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma), _altera)
    motor.agregar(
        Regla(
            "limpieza",
            "sensor.disco_lleno",
            "borrar_archivo",
            {"ruta": str(ruta / "datos.txt")},
            condicion=lambda ev: ev.payload.get("pct", 0) > 90,
        )
    )
    await motor.on_event(Event("sensor.otra_cosa", "t", "u", {"pct": 99}))
    await motor.on_event(Event("sensor.disco_lleno", "t", "u", {"pct": 50}))
    assert (ruta / "datos.txt").exists(), "disparo sin cumplirse evento/condicion"

    await motor.on_event(Event("sensor.disco_lleno", "t", "u", {"pct": 95}))
    assert not (ruta / "datos.txt").exists()


def test_toda_accion_destructiva_del_catalogo_exige_dry_run():
    """Coherencia estructural: nada de lista roja puede quedar fuera de la exigencia de dry-run."""
    for accion in ("borrar_archivo", "mover_archivo", "renombrar_archivo", "escribir_archivo"):
        assert _altera(accion), f"'{accion}' no exigiria dry-run"
        assert accion in RED, f"'{accion}' deberia ser de lista roja"


@pytest.mark.asyncio
async def test_regla_reincidente_no_rompe_el_turno(entorno):
    """Defecto hallado por la demo de capacidad M2 (DoD 9: cero errores NO recuperados).

    Una regla que dispara dos veces sobre el mismo archivo encontraba el segundo disparo con el
    origen ya movido. `os.lstat` lanzaba FileNotFoundError, que atravesaba el motor y mataba el
    turno completo. El estado del disco es una condicion del entorno, no un error de programa:
    debe degradar a "detenida" y dejar el sistema en pie.
    """
    ruta, ad = entorno
    (ruta / "sub").mkdir(exist_ok=True)
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma), _altera)
    regla = Regla(
        "archivar",
        "sensor.disco",
        "mover_archivo",
        {"origen": str(ruta / "datos.txt"), "destino": str(ruta / "sub" / "datos.txt")},
    )
    motor.agregar(regla)

    await motor.on_event(_ev())
    assert motor.ejecutadas[-1]["estado"] == "ejecutada"

    await motor.on_event(_ev())  # el origen ya no existe
    segundo = motor.ejecutadas[-1]
    assert segundo["estado"] == "detenida", "un disparo sobre un archivo ausente no puede propagar OSError"
    assert "no realizable" in segundo["motivo"] or "no viable" in segundo["motivo"]


@pytest.mark.asyncio
async def test_desaparicion_entre_confirmacion_y_ejecucion_se_recupera(entorno):
    """El disco puede cambiar tras confirmar. El turno debe sobrevivir e informar el fallo."""
    ruta, ad = entorno
    objetivo = ruta / "datos.txt"

    async def confirma_y_borra(accion, args, tid):
        objetivo.unlink()  # un tercero elimina el archivo justo despues de confirmar
        return True

    motor = MotorAutomatizacion(ad, PermissionManager(confirma_y_borra), _altera)
    r = await motor.ejecutar("borrar_archivo", {"ruta": str(objetivo)}, "t", "e1", "conversacion")
    assert r["estado"] == "error" and "sistema de archivos" in r["motivo"]
