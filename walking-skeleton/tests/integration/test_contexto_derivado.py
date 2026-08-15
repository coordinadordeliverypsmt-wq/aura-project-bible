"""El contexto del fallo viaja hasta el ejecutor (acta del CEO, 2026-08-15).

EL DEFECTO, MEDIDO. AURORA detecta un fallo, deriva su propia tarea de corrección... y esa tarea
nace con `args={}`. Muere en el mismo dry-run que mató a la original:

    t-ceo              origen=ceo       bloqueada  args=False | dry-run no viable: un cambio
                                                                 necesita fichero y patron
    auto-a8bbecfb8a4e  origen=derivado  bloqueada  args=False | dry-run no viable: un cambio
                                                                 necesita fichero y patron

Y el auditor SÍ tiene lo accionable: dentro de su bucle conoce `fichero`, `buscar` y `sustituir` de
cada mutante, pero sólo publica `{mutante, problema, detalle}`. **AURORA pierde información que ya
posee** entre la detección y la derivación.

LA VÍA ES LA YA CABLEADA (opción A del CEO). `desde_verificacion` NO se toca ni se cablea: sigue
siendo capacidad existente pendiente de decisión futura. El flujo es

    auditor -> veredicto estructurado -> director -> Tarea.args -> oyente -> admitir() -> Programador

y el contexto viaja por `args`, NUNCA de contrabando en `evidencias`, que es una lista de texto para
humanos.

NO SE FINGE AUTONOMÍA. Cuando un dato no existe, se queda ausente: el ejecutor no puede actuar, la
tarea se bloquea y escala con TODO el contexto delante. Eso es un resultado correcto, no un fallo.
"""

from __future__ import annotations

import pytest

from aura_skeleton.core.director import DirectorGeneral, RegistroEjecutores
from aura_skeleton.core.estado_operativo import CLAVE_CONTEXTO, AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.planificacion import oyente_de_transiciones


@pytest.fixture
def estado(tmp_path):
    est = AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl"))
    est.observar(oyente_de_transiciones(est))
    return est


class _MotorFalso:
    """Motor que devuelve un veredicto fijo. Permite ejercitar al director sin adaptadores reales."""

    def __init__(self, resultado):
        self._resultado = resultado
        self.recibidos: list[tuple[str, dict]] = []

    async def ejecutar(self, accion, args, trace_id, event_id, origen):
        self.recibidos.append((accion, dict(args)))
        return {"accion": accion, "estado": "ejecutada", "resultado": self._resultado, "origen": origen}


_VEREDICTO_CON_CONTEXTO = {
    "capacidad": "auditar_garantias",
    "ok": False,
    "resumen": "1 garantia(s) no protegen nada: gobierno-cli.toml:M1 (AUSENTE)",
    "rotas": [
        {
            "mutante": "gobierno-cli.toml:M1",
            "problema": "AUSENTE",
            "detalle": "el patron ya no aparece",
            "fichero": "mutaciones/gobierno-cli.toml",
            "buscar": "    secciones = panel(estado=x)",
            "sustituir": "    secciones = panel()",
        }
    ],
}


# ------------------------------------------- 1 · EL AUDITOR PUBLICA LO QUE YA SABE --


def test_el_auditor_publica_el_contexto_accionable_de_cada_garantia_rota(tmp_path):
    """Hoy el auditor conoce `fichero`, `buscar` y `sustituir` dentro de su bucle y sólo publica el
    identificador y un detalle en prosa. Publicar lo que ya tiene es el primer eslabón: sin esto no
    hay nada que transportar."""
    from aura_skeleton.adapters.auditor import auditar_garantias

    raiz = tmp_path / "proyecto"
    (raiz / "mutaciones").mkdir(parents=True)
    (raiz / "objetivo.py").write_text("valor = 1\n", encoding="utf-8")
    (raiz / "mutaciones" / "x.toml").write_text(
        'incremento = "x"\npruebas = ["t"]\n\n[[mutante]]\nid = "M1"\n'
        'garantia = "g"\nfichero = "objetivo.py"\n'
        "buscar = '''patron que ya no existe'''\nsustituir = '''otra cosa'''\n",
        encoding="utf-8",
    )

    resultado = auditar_garantias(str(raiz), "t")
    assert resultado["ok"] is False, "guarda: la garantía sembrada debe salir rota"

    rota = resultado["rotas"][0]
    assert rota["fichero"] == "objetivo.py", f"no publica el fichero afectado: {rota}"
    assert rota["buscar"] == "patron que ya no existe", f"no publica el patrón: {rota}"
    assert rota["sustituir"] == "otra cosa"


# ------------------------------------- 2 · EL DIRECTOR ADJUNTA EL CONTEXTO A LA TAREA --


@pytest.mark.asyncio
async def test_el_director_adjunta_el_veredicto_estructurado_en_args(estado):
    """El veredicto viaja por `args`, bajo una clave declarada. NO por `evidencias`, que es texto
    para que lo lea una persona."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(
        estado, _MotorFalso(_VEREDICTO_CON_CONTEXTO), RegistroEjecutores({"auditor": "auditar_garantias"})
    )

    await director.ciclo("obj")

    causa = [t for t in estado.tareas("obj") if t.tarea_id == "t-audit"][-1]
    assert causa.estado == "bloqueada"
    contexto = causa.args.get(CLAVE_CONTEXTO)
    assert contexto is not None, f"el veredicto no se adjuntó a la tarea: {causa.args}"
    assert contexto["fichero"] == "mutaciones/gobierno-cli.toml"
    assert contexto["buscar"] == "    secciones = panel(estado=x)"
    assert "AUSENTE" in str(contexto.get("motivo", "")) or "AUSENTE" in str(contexto)


@pytest.mark.asyncio
async def test_el_veredicto_no_se_cuela_en_evidencias(estado):
    """Criterio 8 del acta, literal: nada de contrabando. `evidencias` sigue siendo prosa."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(
        estado, _MotorFalso(_VEREDICTO_CON_CONTEXTO), RegistroEjecutores({"auditor": "auditar_garantias"})
    )
    await director.ciclo("obj")

    for t in estado.tareas("obj"):
        for ev in t.evidencias:
            assert "buscar" not in ev and "mutaciones/gobierno-cli.toml" not in ev, (
                f"el contexto estructurado se coló en evidencias: {ev!r}"
            )


# ------------------------------------------- 3 · LA TAREA DERIVADA LO CONSERVA --


@pytest.mark.asyncio
async def test_la_tarea_derivada_llega_con_los_argumentos_del_ejecutor(estado):
    """EL DEFECTO QUE CIERRA EL INCREMENTO. Hoy la derivada nace con `args={}` y muere en el dry-run
    con «un cambio necesita fichero y patron a sustituir». Ahora debe llegar con lo que el
    `EjecutorProgramador` lee: `fichero`, `buscar` y `sustituir`."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(
        estado, _MotorFalso(_VEREDICTO_CON_CONTEXTO), RegistroEjecutores({"auditor": "auditar_garantias"})
    )
    await director.ciclo("obj")

    derivadas = [t for t in estado.tareas("obj") if t.origen == "derivado"]
    assert len(derivadas) == 1, f"se esperaba UNA tarea derivada, hay {len(derivadas)}"

    d = derivadas[0]
    assert d.responsable == "programador"
    assert d.args.get("fichero") == "mutaciones/gobierno-cli.toml", f"sin fichero: {d.args}"
    assert d.args.get("buscar") == "    secciones = panel(estado=x)", f"sin patrón: {d.args}"
    assert d.args.get("sustituir") == "    secciones = panel()"


@pytest.mark.asyncio
async def test_la_tarea_derivada_conserva_causa_motivo_y_procedencia(estado):
    """Los seis campos que el acta exige «cuando existan». La causa y la procedencia ya viajaban;
    el motivo y el contexto del fichero son lo que se añade."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(
        estado, _MotorFalso(_VEREDICTO_CON_CONTEXTO), RegistroEjecutores({"auditor": "auditar_garantias"})
    )
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert d.origen == "derivado", "procedencia"
    assert any("t-audit" in ev for ev in d.evidencias), "no conserva la tarea causa"
    assert d.args.get("motivo"), f"no conserva el motivo del fallo: {d.args}"


# --------------------------------- 4 · NO SE FINGE: LO AUSENTE SIGUE AUSENTE --


@pytest.mark.asyncio
async def test_sin_contexto_accionable_la_derivada_sigue_naciendo_sin_argumentos(estado):
    """Criterio 5 del acta. Un veredicto sin datos accionables -el QA sólo da un resumen- no puede
    inventarlos. La tarea nace sin `args` de ejecución y se bloqueará: es el comportamiento correcto,
    no un fallo. Sin esta prueba, «transportar contexto» podría cumplirse fabricándolo."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-qa", descripcion="verificar", responsable="qa"))
    veredicto_sin_contexto = {"capacidad": "ejecutar_pruebas", "ok": False, "resumen": "3 pruebas fallaron"}
    director = DirectorGeneral(
        estado, _MotorFalso(veredicto_sin_contexto), RegistroEjecutores({"qa": "verificar_calidad"})
    )
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert "fichero" not in d.args, f"se inventó un fichero que nadie declaró: {d.args}"
    assert "buscar" not in d.args
    assert d.args.get("motivo"), "aun sin datos accionables, el motivo debe viajar"


@pytest.mark.asyncio
async def test_un_contexto_incompleto_no_se_rellena_a_medias(estado):
    """Si el veredicto trae fichero pero no `sustituir`, se transporta lo que hay y NO se inventa el
    resto. El ejecutor rechazará por falta de patrón, con el fichero real delante — que es mucho más
    útil que el «necesita fichero y patron» genérico de hoy."""
    parcial = {
        "capacidad": "auditar_garantias",
        "ok": False,
        "resumen": "1 garantia rota",
        "rotas": [{"mutante": "x:M1", "problema": "AUSENTE", "detalle": "d", "fichero": "a.toml", "buscar": "p"}],
    }
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(estado, _MotorFalso(parcial), RegistroEjecutores({"auditor": "auditar_garantias"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert d.args.get("fichero") == "a.toml"
    assert d.args.get("buscar") == "p"
    assert "sustituir" not in d.args, f"inventó el texto de sustitución: {d.args}"


# --------------------------------------------- 5 · SIN DUPLICADOS, SIN SEGUNDA VÍA --


@pytest.mark.asyncio
async def test_el_mismo_fallo_repetido_no_duplica_la_tarea_derivada(estado):
    """Criterio 6. La deduplicación es una propiedad del identificador -`id_desde_evidencia`- y debe
    seguir funcionando con el contexto viajando: si el contexto entrara en la evidencia, cada matiz
    del veredicto generaría una tarea nueva."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(
        estado, _MotorFalso(_VEREDICTO_CON_CONTEXTO), RegistroEjecutores({"auditor": "auditar_garantias"})
    )

    await director.ciclo("obj")
    for _ in range(3):
        # Se reabre SÓLO si sigue bloqueada: tras el primer ciclo el director atiende la derivada
        # (prioridad 1) antes que la causa (prioridad 5), así que `t-audit` puede ya estar abierta y
        # `abierta -> abierta` no es una transición válida.
        if [t for t in estado.tareas("obj") if t.tarea_id == "t-audit"][-1].estado == "bloqueada":
            estado.transitar("obj", "t-audit", "abierta", autoridad="ceo", causa="reintento")
        await director.ciclo("obj")

    derivadas = [t.tarea_id for t in estado.tareas("obj") if t.origen == "derivado"]
    assert len(set(derivadas)) == 1, f"el mismo fallo generó {len(set(derivadas))} tareas: {set(derivadas)}"


def test_desde_verificacion_sigue_sin_cablearse_en_produccion():
    """Decisión EXPLÍCITA del CEO: `desde_verificacion` conserva su contrato y sus pruebas, pero NO
    entra en producción en este incremento. Esta prueba lo fija para que no se cuele por descuido en
    un incremento futuro sin decisión."""
    import pathlib

    paquete = pathlib.Path(__file__).resolve().parents[2] / "aura_skeleton"
    llamadas = [
        f"{py.relative_to(paquete)}"
        for py in paquete.rglob("*.py")
        if py.name != "planificacion.py" and "desde_verificacion" in py.read_text(encoding="utf-8")
    ]
    assert llamadas == [], f"`desde_verificacion` se cableó sin decisión del CEO: {llamadas}"


@pytest.mark.asyncio
async def test_con_varias_garantias_rotas_solo_se_transporta_la_primera(estado):
    """MUTANTE VIVO C8. Con varias garantías rotas, mezclarlas todas en una sola tarea derivada haría
    que una irresoluble arrastre a las demás: el ciclo ya no podría escalarlas por separado. Una
    tarea derivada es UNA unidad de trabajo."""
    varias = {
        "capacidad": "auditar_garantias",
        "ok": False,
        "resumen": "2 garantias rotas",
        "rotas": [
            {"mutante": "a.toml:M1", "problema": "AUSENTE", "fichero": "primero.py", "buscar": "p1"},
            {"mutante": "b.toml:M2", "problema": "AUSENTE", "fichero": "segundo.py", "buscar": "p2"},
        ],
    }
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(estado, _MotorFalso(varias), RegistroEjecutores({"auditor": "auditar_garantias"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert d.args.get("fichero") == "primero.py", f"no tomó la primera garantía rota: {d.args}"
    assert d.args.get("buscar") == "p1"
    assert "segundo.py" not in str(d.args), f"mezcló dos correcciones en una tarea: {d.args}"
