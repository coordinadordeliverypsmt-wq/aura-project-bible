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

ALCANCE CONFIRMADO POR EL CEO (2026-08-15), tras medirlo:

    DETECTAR -> CONSERVAR EVIDENCIA -> DERIVAR -> TRANSPORTAR CONTEXTO -> EJECUTOR / BLOQUEO / ESCALADA

**No es requisito de este incremento que AURORA se corrija sin LLM.** La medición dice 0 de 7 casos
completables sin modelo, y esa cifra es correcta y se conserva: los tres tipos que el auditor detecta
exigen decidir un texto nuevo, y decidirlo es razonar. El propósito era eliminar la pérdida de
contexto que impedía **incluso que el siguiente componente pudiera razonar sobre el problema**.

Por eso se retiró del criterio de aceptación la condición «un caso mecánicamente resoluble ya no
muere por `args={}`»: no existe tal caso en este dominio, y forzarlo habría exigido fabricar un valor
o ejecutar un cambio incompleto — y lo segundo se demostró DESTRUCTIVO (ver
`test_un_contexto_de_ejecucion_incompleto_no_llega_como_ejecutable`).

**`fichero + buscar` sin `sustituir` NO es contexto ejecutable.** Esa separación es estricta y la
protección todo-o-nada permanece.
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


# LA FORMA QUE EL AUDITOR REAL PRODUCE: sin `sustituir`, porque el patron nuevo hay que DECIDIRLO.
# La version anterior de esta fixture lo traia, y la prueba «EL DEFECTO QUE CIERRA EL INCREMENTO»
# quedaba verde sobre una entrada que produccion no puede generar -- misma familia que el defecto D1
# que la auditoria destapo. Ahora la fixture refleja lo que el adaptador emite de verdad.
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
            "objetivo": "aura_skeleton/__main__.py",
        }
    ],
}

# Veredicto HIPOTETICO de un ejecutor futuro que si supiera el patron nuevo. Ningun adaptador de hoy
# lo produce; existe para verificar el contrato generico de `contexto_de_correccion`, que no es solo
# del auditor. Se marca como hipotetico para que nadie lo lea como comportamiento actual.
_VEREDICTO_HIPOTETICO_COMPLETO = {
    "capacidad": "auditar_garantias",
    "ok": False,
    "resumen": "1 rota",
    "rotas": [
        {
            "mutante": "x.toml:M1",
            "problema": "AUSENTE",
            "fichero": "mutaciones/x.toml",
            "buscar": "patron viejo",
            "sustituir": "patron nuevo",
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
    # EL ARTEFACTO A CORREGIR ES EL TOML. Cuando una garantía deja de aplicar, el código objetivo
    # suele estar bien: lo obsoleto es el patrón DECLARADO. La primera versión publicaba el objetivo
    # y enviaba al ejecutor a tocar el fichero equivocado -- lo destapó la auditoría, y esta misma
    # prueba y la fixture de abajo codificaban diseños contradictorios.
    assert rota["fichero"] == "mutaciones/x.toml", f"no apunta al artefacto a corregir: {rota}"
    assert rota["buscar"] == "patron que ya no existe", f"no publica el patrón declarado: {rota}"
    assert rota["objetivo"] == "objetivo.py", "el fichero objetivo se conserva como dato informativo"
    assert "sustituir" not in rota, (
        "el `sustituir` del mutante NO es la corrección: publicarlo lo haría pasar por un patrón "
        "nuevo que nadie ha decidido"
    )


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
    assert contexto["fichero_declarado"] == "mutaciones/gobierno-cli.toml"
    assert contexto["buscar_declarado"] == "    secciones = panel(estado=x)"
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
    # Con lo que el auditor produce DE VERDAD -sin `sustituir`- el contexto llega DECLARADO, no
    # ejecutable. Es el resultado correcto: falta el patrón nuevo, y decidirlo es razonar.
    assert d.args.get("fichero_declarado") == "mutaciones/gobierno-cli.toml", f"sin fichero: {d.args}"
    assert d.args.get("buscar_declarado") == "    secciones = panel(estado=x)", f"sin patrón: {d.args}"
    assert "fichero" not in d.args, "un contexto sin `sustituir` no puede llegar como ejecutable"


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
    # Viaja como DECLARADO, no como ejecutable: la corrección de arriba explica por qué. Lo que aquí
    # importa es que el texto de sustitución NO se inventa bajo ninguna forma.
    assert d.args.get("fichero_declarado") == "a.toml"
    assert d.args.get("buscar_declarado") == "p"
    assert "sustituir" not in d.args and "sustituir_declarado" not in d.args, (
        f"inventó el texto de sustitución: {d.args}"
    )


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
    assert d.args.get("fichero_declarado") == "primero.py", f"no tomó la primera garantía rota: {d.args}"
    assert "segundo.py" not in str(d.args), f"mezcló dos correcciones en una tarea: {d.args}"


# --------------------------- DEFECTOS ENCONTRADOS DESPUÉS DE LA PRIMERA AUDITORÍA --


@pytest.mark.asyncio
async def test_un_contexto_de_ejecucion_incompleto_no_llega_como_ejecutable(estado):
    """EL DEFECTO MÁS GRAVE DE ESTE INCREMENTO, y no lo vio la auditoría.

    Medido sobre el dry-run REAL del Programador: con `fichero` y `buscar` pero SIN `sustituir`, el
    plan sale `{'viable': True, 'efecto': 'sustituir 1 aparicion...'}` — es decir, **BORRAR el
    patrón**. Y como borrar un `buscar` de un TOML no rompe ninguna prueba, el QA lo respaldaría y el
    cambio se conservaría: AURORA habría DESTRUIDO la garantía en vez de repararla.

    Un cambio incompleto no es medio cambio: es otro cambio. O van los tres campos, o ninguno viaja
    como ejecutable.
    """
    parcial = {
        "capacidad": "auditar_garantias",
        "ok": False,
        "resumen": "1 rota",
        "rotas": [{"mutante": "x:M1", "problema": "AUSENTE", "fichero": "a.toml", "buscar": "patron"}],
    }
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(estado, _MotorFalso(parcial), RegistroEjecutores({"auditor": "auditar_garantias"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert "fichero" not in d.args, f"un contexto incompleto llegó como ejecutable: {d.args}"
    assert "buscar" not in d.args
    assert d.args.get("fichero_declarado") == "a.toml", "pero el dato SÍ debe viajar, para el CEO"
    assert d.args.get("buscar_declarado") == "patron"


@pytest.mark.asyncio
async def test_el_veredicto_no_puede_inyectar_claves_arbitrarias(estado):
    """MUTANTE VIVO X4 de la auditoría. La lista blanca `_CAMPOS_DE_EJECUCION` es lo único que impide
    que un veredicto meta claves cualesquiera en la ruta de ejecución, y no la protegía ninguna
    prueba. Un adaptador comprometido o defectuoso no puede colar argumentos al Motor Único."""
    malicioso = {
        "capacidad": "auditar_garantias",
        "ok": False,
        "resumen": "1 rota",
        "rotas": [{"mutante": "x:M1", "comando": "rm -rf /", "ruta": "/etc", "contenido": "x"}],
    }
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(estado, _MotorFalso(malicioso), RegistroEjecutores({"auditor": "auditar_garantias"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    for clave in ("comando", "ruta", "contenido"):
        assert clave not in d.args, f"el veredicto inyectó la clave {clave!r} en la ejecución: {d.args}"


@pytest.mark.asyncio
async def test_una_tarea_sin_ejecutor_tambien_deriva_con_su_motivo(estado):
    """DEFECTO D2 de la auditoría. Es la ÚNICA derivada que aparece en el log de producción real del
    CEO, y nacía sin nada. No hay veredicto —no se llegó a ejecutar—, pero el motivo es justo lo que
    hace falta para saber que la corrección no es de código sino de CABLEADO."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-huerfana", descripcion="x", responsable="inexistente"))
    director = DirectorGeneral(estado, _MotorFalso({}), RegistroEjecutores({"auditor": "auditar_garantias"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert "inexistente" in str(d.args.get("motivo", "")), f"la derivada nació sin motivo: {d.args}"


@pytest.mark.asyncio
async def test_una_denegacion_del_ceo_no_se_re_presenta_con_presupuesto_nuevo(estado):
    """REGRESIÓN DE GOBIERNO, la más grave de la segunda auditoría — y la introduje yo al corregir.

    Añadí que la corrección heredara los argumentos de ejecución de su causa. Medido, hacía esto: un
    cambio de lista roja **denegado por el CEO** engendraba una derivada que heredaba el triple
    completo, pasaba el dry-run y **volvía a pedir la misma autorización con `intentos=0`** — un
    presupuesto de reintentos nuevo, saltándose el umbral que la capacidad 017 introdujo justo para
    dejar de insistir. Re-presentar lo denegado no es autonomía: erosiona una decisión del CEO.

    Y ni siquiera aportaba: en el caso legítimo -verificación en rojo- la derivada re-aplicaba el
    triple idéntico, obtenía el mismo rojo y revertía. Repetir lo que ya falló, gastando dos
    verificaciones. La herencia se retiró entera.
    """
    estado.registrar(
        Tarea(
            objetivo_id="obj",
            tarea_id="t-rojo",
            descripcion="cambio de lista roja",
            responsable="programador",
            args={"fichero": "a.py", "buscar": "viejo", "sustituir": "nuevo"},
        )
    )
    denegado = {"capacidad": "proponer_cambio", "ok": False, "resumen": "permisos: denegada por el usuario"}
    director = DirectorGeneral(estado, _MotorFalso(denegado), RegistroEjecutores({"programador": "proponer_cambio"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    for campo in ("fichero", "buscar", "sustituir"):
        assert campo not in d.args, f"la derivada re-pide lo que el CEO denegó: {d.args}"
    assert d.args.get("motivo"), "el motivo sí debe viajar: es lo que el CEO necesita para decidir"


@pytest.mark.asyncio
@pytest.mark.parametrize("en_blanco", ["   ", "", "\n", "\t"])
async def test_un_campo_en_blanco_no_cuenta_como_campo(estado, en_blanco):
    """MUTANTES VIVOS X6 y E-1. La guarda usaba veracidad, así que `sustituir = "   "` era un valor
    PRESENTE y VERDADERO: pasaba el todo-o-nada, llegaba como ejecutable, y el dry-run daba `viable`
    con el efecto de sustituir el patrón **por espacios**. Destruir la garantía, con el QA
    respaldándolo porque eso no rompe ninguna prueba."""
    veredicto = {
        "capacidad": "auditar_garantias",
        "ok": False,
        "resumen": "1 rota",
        "rotas": [{"mutante": "x:M1", "fichero": "a.toml", "buscar": "p", "sustituir": en_blanco}],
    }
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(estado, _MotorFalso(veredicto), RegistroEjecutores({"auditor": "auditar_garantias"}))
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert "fichero" not in d.args, f"un campo en blanco pasó por completo: {d.args}"
    assert d.args.get("fichero_declarado") == "a.toml"


@pytest.mark.parametrize("en_blanco", ["   ", "", "\n"])
def test_el_traductor_por_si_solo_rechaza_los_campos_en_blanco(en_blanco):
    """LAS DOS CAPAS SE PRUEBAN POR SEPARADO, y hace falta.

    La prueba de arriba pasa por el ciclo completo, donde `solo_ejecutable_completo` filtra en el
    punto de paso — y eso ENMASCARA un fallo en `contexto_de_correccion`: el mutante que devuelve la
    guarda a la veracidad sobrevivía porque la segunda capa lo atrapaba. La defensa en profundidad
    protege el sistema, pero deja sin red a cada capa por separado.

    `contexto_de_correccion` es contrato público del módulo: cualquiera puede llamarlo sin pasar por
    el oyente, y entonces la única guarda es la suya.
    """
    from aura_skeleton.core.estado_operativo import contexto_de_correccion

    ctx = contexto_de_correccion(
        {"ok": False, "rotas": [{"fichero": "a.toml", "buscar": "p", "sustituir": en_blanco}]}, "m"
    )
    assert "fichero" not in ctx, f"el traductor dejó pasar un campo en blanco como ejecutable: {ctx}"
    assert ctx.get("fichero_declarado") == "a.toml"


@pytest.mark.asyncio
async def test_la_proteccion_se_aplica_en_el_punto_de_paso_no_en_el_llamador(estado):
    """MUTANTE VIVO E-2. La guarda vivía sólo en `contexto_de_correccion`, que llama el Director,
    mientras el oyente copiaba `args[_veredicto]` VERBATIM: la protección era propiedad de UN
    llamador, no del sistema. Cualquier ruta que adjuntase un contexto a mano la esquivaba y reabría
    el camino destructivo. Aquí se adjunta sin pasar por el Director."""
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-x", descripcion="x", responsable="programador"))
    estado.transitar(
        "obj",
        "t-x",
        "bloqueada",
        autoridad="director",
        causa="fallo",
        bloqueos=["fallo"],
        args={CLAVE_CONTEXTO: {"motivo": "m", "fichero": "a.toml", "buscar": "p"}},
    )

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert "fichero" not in d.args, f"el contexto incompleto esquivó la protección: {d.args}"
    assert d.args.get("fichero_declarado") == "a.toml", "pero el dato debe seguir viajando"


@pytest.mark.asyncio
async def test_un_veredicto_completo_si_llega_como_ejecutable(estado):
    """CONTROL de todo lo anterior. Sin él, «no dejar pasar lo incompleto» se cumpliría trivialmente
    no dejando pasar nada, y el transporte quedaría inservible.

    Usa el veredicto HIPOTÉTICO: ningún adaptador de hoy lo produce, y por eso esta prueba verifica
    el contrato genérico de `contexto_de_correccion` — no un comportamiento actual.
    """
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-audit", descripcion="auditar", responsable="auditor"))
    director = DirectorGeneral(
        estado, _MotorFalso(_VEREDICTO_HIPOTETICO_COMPLETO), RegistroEjecutores({"auditor": "auditar_garantias"})
    )
    await director.ciclo("obj")

    d = [t for t in estado.tareas("obj") if t.origen == "derivado"][0]
    assert d.args.get("fichero") == "mutaciones/x.toml", f"un contexto completo no llegó ejecutable: {d.args}"
    assert d.args.get("buscar") == "patron viejo"
    assert d.args.get("sustituir") == "patron nuevo"
