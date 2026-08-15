"""El buzón de decisiones, visible en el Centro de Gobierno (acta del CEO, 2026-08-10).

EL DEFECTO QUE CIERRA, medido. Pieza 2 hace que AURORA pida permiso por escrito en vez de
autodenegárselo, y 017 hace que escale una tarea cuando deja de insistir. Pero **el Centro de
Gobierno —la interfaz oficial entre el CEO y AURORA— no muestra ninguna de las dos cosas**:
`centro_gobierno.py` no conocía el buzón, así que el CEO tenía que acordarse de mirar ficheros JSON
sueltos en `~/.aura/decisiones/`.

AURORA pedía permiso por un canal que el CEO no mira. El lazo de gobierno estaba abierto por el lado
de la notificación: no es que faltara autonomía, es que la ya construida no llegaba a usarse.

LO QUE ESTE INCREMENTO NO TOCA: permisos, motor de ejecución, `admitir()`, ADR-0003 y la
confirmación del CEO. Es LECTURA sobre dos fuentes que ya existen.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.centro_gobierno import AURORA, panel, render
from aura_skeleton.core.decisiones import AlmacenDecisiones, huella_de, reabrir_aprobadas
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea


@pytest.fixture
def estado(tmp_path):
    return AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl"))


@pytest.fixture
def almacen(tmp_path):
    return AlmacenDecisiones(str(tmp_path / "decisiones"))


def _seccion(secciones, sufijo: str):
    halladas = [s for s in secciones if s.titulo.endswith(sufijo)]
    return halladas[0] if halladas else None


# ------------------------------------------------- LA DECISIÓN PENDIENTE SE VE --


def test_una_decision_pendiente_aparece_en_el_panel(estado, almacen):
    """LA PRUEBA QUE JUSTIFICA EL INCREMENTO. Sin esto, AURORA pide permiso por un canal que el CEO
    no mira."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="cambio", estado="abierta"))
    almacen.solicitar("proponer_cambio", {"fichero": "a.py"}, "sustituir 1 aparicion en a.py", "tr:t-1")

    seccion = _seccion(panel(estado=estado, objetivo="obj", decisiones=almacen), "Decisiones pendientes")
    assert seccion is not None, "el panel no tiene sección de decisiones pendientes"
    assert seccion.origen == AURORA, "la solicitud la produce AURORA: el origen debe declararlo"
    assert "proponer_cambio" in seccion.contenido, "no dice QUÉ se pide autorizar"
    assert "sustituir 1 aparicion en a.py" in seccion.contenido, (
        "no muestra el efecto previsto: aprobar sin verlo sería confirmar a ciegas (ADR-0003)"
    )
    assert "t-1" in seccion.contenido, "no dice a qué tarea pertenece la decisión"


def test_sin_decisiones_pendientes_se_declara_la_ausencia(estado, almacen):
    """CONTROL. Sin él, «mostrar las pendientes» se cumpliría con una sección que siempre dice algo.
    Y una ausencia declarada es información: significa que AURORA no espera nada de ti."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="x", estado="abierta"))
    seccion = _seccion(panel(estado=estado, objetivo="obj", decisiones=almacen), "Decisiones pendientes")
    assert seccion is not None
    assert "proponer_cambio" not in seccion.contenido
    assert seccion.contenido.strip(), "una sección vacía rompería el contrato de Seccion"


def test_una_decision_ya_resuelta_no_sigue_pidiendo_atencion(estado, almacen):
    """Lo aprobado o rechazado deja de reclamar al CEO: si no, el panel acumularía ruido y dejaría de
    servir para decidir."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="x", estado="abierta"))
    almacen.solicitar("proponer_cambio", {"f": "a.py"}, "efecto", "tr:t-1")
    almacen.aprobar(huella_de("proponer_cambio", {"f": "a.py"}, "efecto"))

    seccion = _seccion(panel(estado=estado, objetivo="obj", decisiones=almacen), "Decisiones pendientes")
    assert "proponer_cambio" not in seccion.contenido, "una decisión ya resuelta seguía pidiendo atención"


# ------------------------------------------------------- LA ESCALADA DEJA DE SER SILENCIOSA --


def test_una_tarea_escalada_se_ve_en_el_panel(estado, almacen):
    """017 hace que AURORA deje de insistir. Si esa escalada no llega al panel, AURORA se para y el
    CEO no se entera: pararse en silencio es peor que girar."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="cambio", estado="abierta"))
    estado.transitar("obj", "t-1", "bloqueada", autoridad="director", causa="permisos: pendiente")
    almacen.solicitar("proponer_cambio", {"t": "t-1"}, "efecto", "tr:t-1")
    almacen.aprobar(huella_de("proponer_cambio", {"t": "t-1"}, "efecto"))
    for _ in range(6):
        if reabrir_aprobadas(almacen, estado):
            t = [x for x in estado.tareas("obj") if x.tarea_id == "t-1"][-1]
            if t.estado == "abierta":
                estado.transitar(
                    "obj", "t-1", "bloqueada", autoridad="director", causa="fallo", bloqueos=[*t.bloqueos, "fallo"]
                )

    seccion = _seccion(panel(estado=estado, objetivo="obj", decisiones=almacen), "Escaladas al CEO")
    assert seccion is not None, "el panel no distingue una tarea escalada de una bloqueada cualquiera"
    assert "t-1" in seccion.contenido
    assert "intentos" in seccion.contenido.lower(), "no dice cuántas veces se intentó: el CEO no puede juzgar"


def test_una_tarea_bloqueada_normal_no_figura_como_escalada(estado, almacen):
    """CONTROL. Una tarea bloqueada esperando aprobación NO está escalada: aún se va a reintentar.
    Confundirlas haría que el CEO creyera que AURORA se rindió cuando sigue trabajando."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="x", estado="abierta"))
    # Con `bloqueos`, como hace el director: `causa` sola no lo conserva, y una tarea bloqueada sin
    # motivo registrado deja vacía la sección "Que esta bloqueado" y `Seccion` la rechaza. En
    # producción no ocurre -el director siempre pasa el motivo-, pero conviene saber que el panel es
    # frágil ante una tarea bloqueada sin motivo. Anotado como observación, fuera de este alcance.
    estado.transitar(
        "obj",
        "t-1",
        "bloqueada",
        autoridad="director",
        causa="permisos: pendiente de aprobacion",
        bloqueos=["permisos: pendiente de aprobacion"],
    )

    seccion = _seccion(panel(estado=estado, objetivo="obj", decisiones=almacen), "Escaladas al CEO")
    assert "t-1" not in seccion.contenido, "una tarea que aún se reintentará figura como escalada"


# ----------------------------------------------------------------- NO SE ROMPE NADA --


def test_sin_buzon_el_panel_sigue_funcionando_igual(estado):
    """El buzón es OPCIONAL: el orquestador llama a `panel()` sin él para responder «¿en qué estás
    trabajando?». Exigirlo rompería esa superficie."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="x", estado="abierta"))
    secciones = panel(estado=estado, objetivo="obj")
    assert _seccion(secciones, "Que esta haciendo") is not None
    assert _seccion(secciones, "Decisiones pendientes") is None, "sin buzón no debe inventarse la sección"


def test_las_secciones_del_estado_operativo_no_cambian(estado, almacen):
    """Regresión: añadir secciones no puede alterar las que el orquestador ya usa para responder al
    usuario (`_resumen_de` filtra por sufijo de título)."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="x", estado="abierta"))
    sin_buzon = [s.titulo for s in panel(estado=estado, objetivo="obj")]
    con_buzon = [s.titulo for s in panel(estado=estado, objetivo="obj", decisiones=almacen)]
    assert set(sin_buzon).issubset(set(con_buzon)), "el buzón hizo desaparecer secciones existentes"
    assert [t for t in con_buzon if t in sin_buzon] == sin_buzon, "cambió el orden de las secciones existentes"


def test_el_panel_renderizado_sigue_siendo_legible(estado, almacen):
    """El CEO lee este panel por `--gobierno`. Se comprueba sobre `render()`, que es lo que ve de
    verdad, no sobre la lista de secciones."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="cambio", estado="abierta"))
    almacen.solicitar("proponer_cambio", {"f": "a.py"}, "sustituir en a.py", "tr:t-1")

    texto = render(panel(estado=estado, objetivo="obj", decisiones=almacen))
    assert "Decisiones pendientes" in texto
    assert "sustituir en a.py" in texto


# ------------------------------------------------------- E2E: EL CEO PUEDE ACTUAR --


@pytest.mark.asyncio
async def test_e2e_el_ceo_ve_la_solicitud_en_el_panel_y_puede_actuar(tmp_path):
    """LA CADENA COMPLETA que exige el acta: AURORA genera la solicitud → el Centro de Gobierno la
    muestra → el CEO la identifica y actúa → la tarea se reanuda.

    Sobre el sistema COMPUESTO y el motor único: sin eso no se demostraría que la huella que el CEO
    aprueba desde el panel es la misma que autoriza la ejecución.
    """
    from aura_skeleton.adapters.computador import AdaptadorComputador
    from aura_skeleton.adapters.hitl_diferido import crear_confirmador_diferido
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.core.registro import RegistroAdaptadores

    dir_dec = str(tmp_path / "decisiones")
    destino = tmp_path / "obra.txt"
    almacen = AlmacenDecisiones(dir_dec)
    motor = MotorAutomatizacion(
        RegistroAdaptadores([AdaptadorComputador(raices=(str(tmp_path),))]),
        PermissionManager(crear_confirmador_diferido(dir_dec)),
    )
    est = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    est.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="escribir", estado="abierta"))
    args = {"ruta": str(destino), "contenido": "hola"}

    # 1 · AURORA lo intenta sin el CEO delante: no se ejecuta, y la solicitud queda escrita.
    assert (await motor.ejecutar("escribir_archivo", dict(args), "tr", "tr:t-1", origen="d"))["estado"] == "detenida"
    assert not destino.exists()

    # 2 · El CEO abre el Centro de Gobierno y LA VE, con el efecto previsto delante.
    texto = render(panel(estado=est, objetivo="obj", decisiones=almacen))
    assert "escribir_archivo" in texto, f"el CEO no puede ver la solicitud en su interfaz oficial:\n{texto}"
    assert "t-1" in texto

    # 3 · Actúa sobre ella: la huella que ve en el panel es la que aprueba.
    pendiente = almacen.pendientes()[0]
    assert pendiente["huella"][:12] in texto, "el panel no identifica la decisión de forma accionable"
    almacen.aprobar(pendiente["huella"])

    # 4 · Y ahora sí se ejecuta.
    assert (await motor.ejecutar("escribir_archivo", dict(args), "tr2", "tr2:t-1", origen="d"))["estado"] == "ejecutada"
    assert destino.read_text(encoding="utf-8") == "hola"

    # 5 · Resuelta, deja de reclamar atención en el panel.
    assert "escribir_archivo" not in render(panel(estado=est, objetivo="obj", decisiones=almacen))
