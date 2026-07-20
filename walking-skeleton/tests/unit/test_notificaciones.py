"""M2.4 — Centro unico de notificaciones.

La prueba mas importante del bloque es que el centro NO sea una puerta trasera: una accion lanzada
desde una notificacion debe recorrer el mismo camino de Permisos y dry-run que cualquier otra.
"""

import os

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.notificaciones import (
    CentroNotificaciones,
    FuenteNoPermitida,
    Notificacion,
)
from aura_skeleton.core.permissions import PermissionManager


async def _niega(a, ar, t):
    return False


async def _confirma(a, ar, t):
    return True


def _altera(accion):
    return accion in {"borrar_archivo", "mover_archivo", "renombrar_archivo", "escribir_archivo"}


def _huella_arbol(raiz):
    out = {}
    for d, _, ns in os.walk(raiz):
        for n in ns:
            r = os.path.join(d, n)
            st = os.lstat(r)
            out[r] = (st.st_size, st.st_mtime_ns)
    return out


@pytest.fixture
def centro(tmp_path):
    (tmp_path / "datos.txt").write_text("informacion del usuario")
    ad = AdaptadorComputador(raices=(str(tmp_path),))
    return tmp_path, ad


# ------------------------------------------------- frontera de fuentes ------


@pytest.mark.parametrize("fuente", ["android", "nas", "docker", "telegram", ""])
def test_fuente_fuera_del_mvp_se_rechaza(fuente):
    """2.2 §4.4: Android/NAS quedan fuera hasta R2. Un centro que acepta cualquier origen es un
    canal de entrada sin control."""
    with pytest.raises(FuenteNoPermitida):
        Notificacion(fuente, "titulo")


@pytest.mark.parametrize("fuente", ["computador", "home_assistant", "aura"])
def test_fuentes_del_mvp_se_aceptan(fuente):
    assert Notificacion(fuente, "titulo").fuente == fuente


# ------------------------------------------------------ reduccion de ruido --


def test_duplicadas_se_suprimen():
    c = CentroNotificaciones()
    assert c.recibir(Notificacion("computador", "Disco al 95%")) is True
    assert c.recibir(Notificacion("computador", "Disco al 95%")) is False
    assert c.recibir(Notificacion("computador", "Disco al 95%")) is False
    assert len(c.listar()) == 1 and c.suprimidas == 2


def test_misma_notificacion_de_fuentes_distintas_no_se_confunde():
    c = CentroNotificaciones()
    c.recibir(Notificacion("computador", "Sin espacio"))
    c.recibir(Notificacion("home_assistant", "Sin espacio"))
    assert len(c.listar()) == 2


def test_prioriza_criticas_y_luego_recientes():
    c = CentroNotificaciones()
    c.recibir(Notificacion("aura", "vieja normal", prioridad="normal", ts=100))
    c.recibir(Notificacion("aura", "nueva normal", prioridad="normal", ts=200))
    c.recibir(Notificacion("computador", "critica", prioridad="critica", ts=50))
    assert [n.titulo for n in c.listar()] == ["critica", "nueva normal", "vieja normal"]


# ------------------------------------------- privacidad (ALERTA-002) --------


def test_contenido_de_terceros_se_purga_al_cerrar_sesion():
    """El contenido de terceros es contextual a la sesion, no historial persistente."""
    c = CentroNotificaciones()
    n = Notificacion("computador", "Mensaje recibido", cuerpo="Juan: te espero a las 5", contiene_terceros=True)
    propia = Notificacion("aura", "Recordatorio propio", cuerpo="comprar pan")
    c.recibir(n)
    c.recibir(propia)

    assert c.cerrar_sesion() == 1
    assert n.cuerpo == "", "el contenido del tercero debio purgarse"
    assert n.titulo and n.fuente, "el HECHO de la notificacion se conserva"
    assert propia.cuerpo == "comprar pan", "el contenido propio del usuario no se toca"


def test_purga_es_idempotente():
    c = CentroNotificaciones()
    c.recibir(Notificacion("computador", "M", cuerpo="dato", contiene_terceros=True))
    assert c.cerrar_sesion() == 1
    assert c.cerrar_sesion() == 0


# ------------------------ el centro NO es una puerta trasera (RN-5) ---------


@pytest.mark.asyncio
async def test_actuar_sin_motor_es_imposible(centro):
    """No existe ejecucion directa desde el centro."""
    ruta, ad = centro
    c = CentroNotificaciones(adaptador=ad, permisos=PermissionManager(_confirma))
    n = Notificacion("computador", "Disco lleno")
    with pytest.raises(RuntimeError, match="ejecucion directa"):
        await c.actuar(n, "borrar_archivo", {"ruta": str(ruta / "datos.txt")}, "t")


@pytest.mark.asyncio
async def test_accion_roja_desde_notificacion_exige_confirmacion(centro):
    """EVIDENCIA CENTRAL: llegar por notificacion no evita el HITL."""
    ruta, ad = centro
    antes = _huella_arbol(ruta)
    motor = MotorAutomatizacion(ad, PermissionManager(_niega), _altera)
    c = CentroNotificaciones(adaptador=ad, permisos=PermissionManager(_niega), motor=motor)

    r = await c.actuar(
        Notificacion("computador", "Disco lleno"), "borrar_archivo", {"ruta": str(ruta / "datos.txt")}, "t"
    )

    assert r["estado"] == "detenida"
    assert _huella_arbol(ruta) == antes, "se ejecuto una accion roja sin confirmacion via notificacion"


@pytest.mark.asyncio
async def test_accion_desde_notificacion_pasa_por_dry_run(centro):
    """El dry-run obligatorio tampoco se evita entrando por el centro."""
    ruta, ad = centro
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma), _altera)
    c = CentroNotificaciones(adaptador=ad, permisos=PermissionManager(_confirma), motor=motor)

    r = await c.actuar(Notificacion("computador", "Limpieza"), "borrar_archivo", {"ruta": str(ruta / "datos.txt")}, "t")

    assert r["estado"] == "ejecutada"
    assert r["plan"] is not None and r["plan"]["efecto"].startswith("se eliminaria")


@pytest.mark.asyncio
async def test_kill_switch_alcanza_a_las_acciones_del_centro(centro, tmp_path):
    ruta, ad = centro
    ks = KillSwitch(str(tmp_path / "KILL"))
    ks.engage("emergencia")
    antes = _huella_arbol(ruta)
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma, kill_switch=ks), _altera)
    c = CentroNotificaciones(adaptador=ad, permisos=None, motor=motor)

    r = await c.actuar(Notificacion("aura", "x"), "borrar_archivo", {"ruta": str(ruta / "datos.txt")}, "t")

    assert r["estado"] == "detenida"
    assert _huella_arbol(ruta) == antes


@pytest.mark.asyncio
async def test_operacion_fuera_del_catalogo_desde_notificacion(centro):
    """RN-2 tambien aplica al centro: no hay via para ejecucion arbitraria."""
    ruta, ad = centro
    motor = MotorAutomatizacion(ad, PermissionManager(_confirma), _altera)
    c = CentroNotificaciones(adaptador=ad, permisos=None, motor=motor)
    r = await c.actuar(Notificacion("aura", "x"), "ejecutar_comando", {"cmd": "rm -rf ~"}, "t")
    assert r["estado"] == "detenida"
