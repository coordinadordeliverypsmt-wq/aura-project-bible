"""Pieza 2 — Aprobación diferida de acciones de lista roja (acta del CEO, 2026-08-10).

EL BLOQUEO QUE CIERRA, medido. De los cuatro ejecutores del ciclo de AURORA, tres son de lista
verde (`verificar_calidad`, `auditar_garantias`, `diagnosticar_estado`: lectura) y **el único que
produce trabajo nuevo, `proponer_cambio`, es de lista ROJA**. Desatendida, `hitl_consola.py` hace
`input()`, recibe `EOFError` y deniega. Es decir: hoy AURORA no puede completar NINGÚN trabajo que
altere nada sin que el CEO esté delante en ese instante.

QUÉ CAMBIA. La autorización no se presume ni se sustituye: lo que cambia es que la SOLICITUD
sobrevive a la ausencia del CEO. La acción sigue sin ejecutarse, la tarea queda bloqueada y el ciclo
continúa con lo demás. Cuando el CEO aprueba, el siguiente latido reabre la tarea y el motor rehace
el dry-run: si el efecto previsto cambió, la huella no coincide y **se vuelve a pedir permiso**.

LO QUE NO SE HACE (reglas 6 y 7 del acta): no hay aprobación automática, ni timeout, ni «fail open»,
ni conversión de silencio en permiso. La ausencia de respuesta no es aprobación NI rechazo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura_skeleton.adapters.hitl_diferido import crear_confirmador_diferido
from aura_skeleton.core.decisiones import AlmacenDecisiones, huella_de, reabrir_aprobadas
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.permissions import PermissionManager


@pytest.fixture
def almacen(tmp_path):
    return AlmacenDecisiones(str(tmp_path / "decisiones"))


@pytest.fixture
def confirmador(tmp_path):
    return crear_confirmador_diferido(str(tmp_path / "decisiones"))


def _args(**extra):
    base = {"ruta": "/tmp/x.txt", "_previsualizacion": "crear /tmp/x.txt", "_tarea": "t-1"}
    base.update(extra)
    return base


# ------------------------------------------------------------------ LA HUELLA ES EL CONTRATO --


def test_la_huella_ignora_los_metadatos_pero_no_los_argumentos():
    """La huella debe ser ESTABLE entre latidos y SENSIBLE al efecto.

    Estable: el `trace_id` y el identificador de tarea cambian en cada vuelta; si entraran en la
    huella, una aprobación no coincidiría nunca y el mecanismo sería inútil.
    Sensible: si cambian los argumentos o el efecto previsto, la huella DEBE cambiar — es lo único
    que impide ejecutar con una aprobación obsoleta (regla 5 del acta).
    """
    base = huella_de("escribir_archivo", {"ruta": "/tmp/x"}, "crear /tmp/x")
    assert base == huella_de("escribir_archivo", {"ruta": "/tmp/x", "_tarea": "otra"}, "crear /tmp/x")
    assert base == huella_de("escribir_archivo", {"ruta": "/tmp/x", "_previsualizacion": "ignorado"}, "crear /tmp/x")

    assert base != huella_de("escribir_archivo", {"ruta": "/tmp/OTRO"}, "crear /tmp/x"), "args cambiados"
    assert base != huella_de("escribir_archivo", {"ruta": "/tmp/x"}, "SOBRESCRIBIR /tmp/x"), "efecto cambiado"
    assert base != huella_de("borrar_archivo", {"ruta": "/tmp/x"}, "crear /tmp/x"), "accion cambiada"
    assert len(base) == 64, "SHA-256 en hexadecimal"


# ------------------------------------------------- SIN APROBACIÓN: PENDIENTE, NUNCA EJECUTADA --


@pytest.mark.asyncio
async def test_sin_aprobacion_la_accion_no_se_autoriza_y_queda_pendiente(confirmador, almacen, tmp_path):
    """Regla 1. El comportamiento seguro NO cambia: sigue devolviendo False."""
    assert await confirmador("escribir_archivo", _args(), "trace-1") is False

    pendientes = almacen.pendientes()
    assert len(pendientes) == 1, f"la solicitud no se persistió: {pendientes}"
    assert pendientes[0]["estado"] == "pendiente"


@pytest.mark.asyncio
async def test_la_solicitud_persiste_los_siete_campos_exigidos(confirmador, almacen):
    """Regla 2 del acta, campo por campo. Sin la previsualización, aprobar sería confirmar a ciegas
    y ADR-0003 no se satisfaría."""
    await confirmador("escribir_archivo", _args(), "trace-1")
    d = almacen.pendientes()[0]

    assert d["accion"] == "escribir_archivo"
    assert d["argumentos"] == {"ruta": "/tmp/x.txt"}, "los metadatos internos no son argumentos del usuario"
    assert d["previsualizacion"] == "crear /tmp/x.txt"
    assert d["huella"] == huella_de("escribir_archivo", {"ruta": "/tmp/x.txt"}, "crear /tmp/x.txt")
    assert d["estado"] == "pendiente"
    assert d["ts"] > 0
    assert d["tarea"] == "t-1"


@pytest.mark.asyncio
async def test_pedir_dos_veces_lo_mismo_no_duplica_la_solicitud(confirmador, almacen):
    """El ciclo reintenta; si cada latido creara una solicitud nueva, el buzón del CEO se llenaría
    de copias de la misma decisión y sería inservible."""
    for _ in range(3):
        await confirmador("escribir_archivo", _args(), "trace-x")
    assert len(almacen.pendientes()) == 1


@pytest.mark.asyncio
async def test_la_ausencia_de_respuesta_no_aprueba_ni_rechaza_nunca(confirmador, almacen):
    """Reglas 6 y 7: no hay timeout ni «fail open». Por muchas vueltas que dé el ciclo, sin
    respuesta del CEO la acción sigue sin autorizarse."""
    for _ in range(10):
        assert await confirmador("escribir_archivo", _args(), "t") is False
    assert almacen.pendientes()[0]["estado"] == "pendiente"


# ---------------------------------------------------------- CON APROBACIÓN: SÓLO SI COINCIDE --


@pytest.mark.asyncio
async def test_con_aprobacion_de_la_huella_exacta_se_autoriza(confirmador, almacen):
    """Regla 4. Es el caso que desbloquea el trabajo de AURORA."""
    await confirmador("escribir_archivo", _args(), "trace-1")
    almacen.aprobar(almacen.pendientes()[0]["huella"])

    assert await confirmador("escribir_archivo", _args(), "trace-2") is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cambio", "por_que"),
    [
        ({"ruta": "/tmp/OTRO.txt"}, "los argumentos cambiaron"),
        ({"_previsualizacion": "BORRAR /tmp/x.txt"}, "el efecto previsto cambió"),
    ],
)
async def test_una_aprobacion_obsoleta_no_autoriza_y_vuelve_a_pedir_permiso(confirmador, almacen, cambio, por_que):
    """REGLA 5, la garantía que hace esto MÁS fuerte que el HITL síncrono. Hoy el CEO confirma y se
    ejecuta lo que el adaptador haga; aquí se verifica que el efecto no cambió entre la aprobación y
    la ejecución. Si cambió, la aprobación caduca y se emite una solicitud NUEVA."""
    await confirmador("escribir_archivo", _args(), "trace-1")
    almacen.aprobar(almacen.pendientes()[0]["huella"])

    assert await confirmador("escribir_archivo", _args(**cambio), "trace-2") is False, por_que
    assert len(almacen.pendientes()) == 1, "no se pidió permiso para el efecto nuevo"


@pytest.mark.asyncio
async def test_una_decision_rechazada_no_autoriza(confirmador, almacen):
    """El CEO puede decir que no, y ese «no» también persiste."""
    await confirmador("escribir_archivo", _args(), "trace-1")
    almacen.rechazar(almacen.pendientes()[0]["huella"])
    assert await confirmador("escribir_archivo", _args(), "trace-2") is False


@pytest.mark.asyncio
async def test_un_fichero_manipulado_con_huella_ajena_no_autoriza(confirmador, almacen, tmp_path):
    """Control de integridad. Aprobar una solicitud cambiándole el contenido pero no la huella -o al
    revés- no puede autorizar: la huella se RECALCULA sobre lo que se va a ejecutar, no se lee del
    fichero."""
    await confirmador("escribir_archivo", _args(), "trace-1")
    fichero = next(Path(tmp_path / "decisiones").glob("*.json"))
    d = json.loads(fichero.read_text(encoding="utf-8"))
    d["estado"] = "aprobada"
    d["argumentos"] = {"ruta": "/tmp/OTRA_COSA.txt"}  # aprobada para OTRA cosa
    fichero.write_text(json.dumps(d), encoding="utf-8")

    assert await confirmador("escribir_archivo", _args(ruta="/tmp/OTRA_COSA.txt"), "t") is False


# ------------------------------------------------- NO SE TOCA LO QUE YA FUNCIONABA (reglas 8-9) --


@pytest.mark.asyncio
async def test_las_acciones_verdes_no_pasan_por_aprobacion(confirmador, almacen):
    """Regla 8. `PermissionManager` sólo llama al confirmador para lista roja; se verifica sobre el
    gestor real, no sobre el confirmador aislado."""
    permisos = PermissionManager(confirmador)
    ok, motivo = await permisos.authorize("verificar_calidad", {}, "t")
    assert ok is True and "verde" in motivo
    assert almacen.pendientes() == [], "una acción verde generó una solicitud de aprobación"


@pytest.mark.asyncio
async def test_el_kill_switch_sigue_bloqueando_por_delante(confirmador, almacen, tmp_path):
    """Regla 9. La parada de emergencia se comprueba ANTES del HITL: con ella echada no debe
    emitirse ni siquiera la solicitud."""
    from aura_skeleton.core.kill_switch import KillSwitch

    kill = KillSwitch(str(tmp_path / "STOP"))
    kill.engage()
    permisos = PermissionManager(confirmador, kill_switch=kill)

    ok, motivo = await permisos.authorize("escribir_archivo", _args(), "t")
    assert ok is False and "kill switch" in motivo
    assert almacen.pendientes() == [], "con el kill switch echado se emitió una solicitud"


# ------------------------------------------- REANUDACIÓN: LA TAREA VUELVE AL TRABAJO SOLA --


def _estado(tmp_path) -> AlmacenEstadoOperativo:
    return AlmacenEstadoOperativo(str(tmp_path / "estado.jsonl"))


def test_reabrir_aprobadas_devuelve_la_tarea_al_trabajo(tmp_path, almacen):
    """El paso que convierte «aprobado» en «trabajo reanudado». Sin él, la aprobación del CEO se
    quedaría en el disco y la tarea seguiría bloqueada para siempre."""
    estado = _estado(tmp_path)
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="proponer", estado="abierta"))
    estado.transitar("obj", "t-1", "bloqueada", autoridad="director", causa="permisos: pendiente de aprobacion")
    assert estado.abiertas("obj") == [], "guarda: la tarea debe estar fuera del trabajo accionable"

    almacen.solicitar("proponer_cambio", {"x": 1}, "efecto", "t-1")
    almacen.aprobar(almacen.pendientes()[0]["huella"])

    assert reabrir_aprobadas(almacen, estado) == 1
    assert [t.tarea_id for t in estado.abiertas("obj")] == ["t-1"]


def test_reabrir_no_toca_tareas_cuya_decision_sigue_pendiente(tmp_path, almacen):
    """CONTROL. Sin esto, «reabrir» podría estar reabriendo todo indiscriminadamente y la prueba
    anterior pasaría igual."""
    estado = _estado(tmp_path)
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="proponer", estado="abierta"))
    estado.transitar("obj", "t-1", "bloqueada", autoridad="director", causa="permisos: pendiente")
    almacen.solicitar("proponer_cambio", {"x": 1}, "efecto", "t-1")

    assert reabrir_aprobadas(almacen, estado) == 0
    assert estado.abiertas("obj") == []


# ------------------------------------------------------ EL CICLO NO SE DETIENE (métrica del CEO) --


@pytest.mark.asyncio
async def test_una_tarea_bloqueada_no_detiene_el_trabajo_independiente(tmp_path, almacen, confirmador):
    """LA MÉTRICA PRINCIPAL: «AURORA puede continuar trabajando sin que yo esté presente».

    Con una tarea esperando aprobación, el resto del backlog sigue siendo accionable. Se comprueba
    sobre el Estado Operativo real, que es quien decide qué trabajo queda.
    """
    estado = _estado(tmp_path)
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-roja", descripcion="cambio", estado="abierta"))
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-verde", descripcion="auditar", estado="abierta"))

    await confirmador("proponer_cambio", _args(_tarea="t-roja"), "trace")
    estado.transitar("obj", "t-roja", "bloqueada", autoridad="director", causa="permisos: pendiente de aprobacion")

    accionables = [t.tarea_id for t in estado.abiertas("obj")]
    assert accionables == ["t-verde"], f"el ciclo se quedó sin trabajo por una decisión pendiente: {accionables}"
    assert len(almacen.pendientes()) == 1


# --------------------------------------------------- END-TO-END POR EL MOTOR ÚNICO --


@pytest.mark.asyncio
async def test_end_to_end_pendiente_aprobacion_ejecucion(tmp_path):
    """La cadena completa POR EL MOTOR ÚNICO, que es el único camino de ejecución del sistema:

        acción roja desatendida → detenida + solicitud pendiente → el CEO aprueba → se ejecuta.

    Sin pasar por el motor, esta prueba no demostraría que el dry-run se rehace ni que la
    previsualización que se aprueba es la que se ejecuta.
    """
    from aura_skeleton.adapters.computador import AdaptadorComputador
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.registro import RegistroAdaptadores

    destino = tmp_path / "obra.txt"
    dir_dec = str(tmp_path / "decisiones")
    confirmador = crear_confirmador_diferido(dir_dec)
    almacen = AlmacenDecisiones(dir_dec)
    registro = RegistroAdaptadores([AdaptadorComputador(raices=(str(tmp_path),))])
    motor = MotorAutomatizacion(registro, PermissionManager(confirmador))
    args = {"ruta": str(destino), "contenido": "hola"}

    r1 = await motor.ejecutar("escribir_archivo", dict(args), "t1", "e1", origen="director:programador")
    assert r1["estado"] == "detenida", f"se ejecutó sin aprobación: {r1}"
    assert not destino.exists(), "INV-9: el efecto ocurrió sin permiso"
    assert len(almacen.pendientes()) == 1

    almacen.aprobar(almacen.pendientes()[0]["huella"])

    r2 = await motor.ejecutar("escribir_archivo", dict(args), "t2", "e2", origen="director:programador")
    assert r2["estado"] == "ejecutada", f"la aprobación del CEO no desbloqueó la acción: {r2}"
    assert destino.read_text(encoding="utf-8") == "hola"


@pytest.mark.asyncio
async def test_end_to_end_la_aprobacion_caduca_si_cambia_el_efecto(tmp_path):
    """El control negativo del anterior, y la razón por la que esto es más fuerte que confirmar en
    vivo: entre la aprobación y la ejecución el mundo pudo cambiar. Se aprueba CREAR un fichero; si
    para cuando se ejecuta el fichero ya existe, el efecto pasa a ser SOBRESCRIBIR y la aprobación
    deja de valer."""
    from aura_skeleton.adapters.computador import AdaptadorComputador
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.registro import RegistroAdaptadores

    destino = tmp_path / "obra.txt"
    dir_dec = str(tmp_path / "decisiones")
    confirmador = crear_confirmador_diferido(dir_dec)
    almacen = AlmacenDecisiones(dir_dec)
    registro = RegistroAdaptadores([AdaptadorComputador(raices=(str(tmp_path),))])
    motor = MotorAutomatizacion(registro, PermissionManager(confirmador))
    args = {"ruta": str(destino), "contenido": "hola"}

    await motor.ejecutar("escribir_archivo", dict(args), "t1", "e1", origen="d")
    almacen.aprobar(almacen.pendientes()[0]["huella"])

    destino.write_text("alguien lo creó mientras tanto", encoding="utf-8")

    r = await motor.ejecutar("escribir_archivo", dict(args), "t2", "e2", origen="d")
    assert r["estado"] == "detenida", "ejecutó con una aprobación obsoleta"
    assert destino.read_text(encoding="utf-8") == "alguien lo creó mientras tanto", "sobrescribió sin permiso"
    assert len(almacen.pendientes()) == 1, "no volvió a pedir permiso para el efecto nuevo"


@pytest.mark.asyncio
async def test_el_identificador_de_tarea_viaja_hasta_el_fichero(tmp_path):
    """MUTANTE VIVO D16. La primera versión de esta prueba inspeccionaba el CÓDIGO FUENTE buscando la
    cadena `_tarea`: con el mutante `contexto["_tarea"] = ""` la cadena seguía ahí y la prueba
    pasaba. Era decorativa. Ahora se comprueba el VALOR que llega al buzón, que es lo que permite a
    la reapertura encontrar la tarea (regla 2 del acta)."""
    from aura_skeleton.adapters.computador import AdaptadorComputador
    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.registro import RegistroAdaptadores

    dir_dec = str(tmp_path / "decisiones")
    motor = MotorAutomatizacion(
        RegistroAdaptadores([AdaptadorComputador(raices=(str(tmp_path),))]),
        PermissionManager(crear_confirmador_diferido(dir_dec)),
    )
    await motor.ejecutar(
        "escribir_archivo", {"ruta": str(tmp_path / "a.txt"), "contenido": "x"}, "tr", "tr:t-42", origen="d"
    )
    assert AlmacenDecisiones(dir_dec).pendientes()[0]["tarea"] == "tr:t-42"


@pytest.mark.asyncio
async def test_el_fichero_de_la_solicitud_se_nombra_por_su_huella(confirmador, tmp_path):
    """MUTANTE VIVO D8. La prueba de «no duplicar» contaba solicitudes pendientes y no discriminaba:
    la deduplicación real no la da el `if os.path.exists`, la da que el fichero se NOMBRE por la
    huella. Si el nombre llevara un timestamp, cada latido crearía una copia y el buzón del CEO se
    volvería inservible."""
    await confirmador("escribir_archivo", _args(), "t1")
    await confirmador("escribir_archivo", _args(), "t2")

    ficheros = sorted(p.name for p in (tmp_path / "decisiones").glob("*.json"))
    esperado = huella_de("escribir_archivo", {"ruta": "/tmp/x.txt"}, "crear /tmp/x.txt")
    assert ficheros == [f"{esperado}.json"], f"el nombre no es la huella: {ficheros}"


def test_solicitar_de_nuevo_no_pisa_la_respuesta_del_ceo(almacen):
    """MUTANTE VIVO D8, segunda mitad. El confirmador sólo llama a `solicitar` cuando no hay decisión
    previa, así que la guarda de idempotencia no se ejercitaba por ese camino. Pero `solicitar` es API
    pública del almacén: si se la llama con una decisión ya respondida y reescribe el fichero, el
    «aprobada» del CEO se degrada a «pendiente» y su respuesta se pierde en silencio."""
    huella = almacen.solicitar("proponer_cambio", {"x": 1}, "efecto", "t-1")
    almacen.aprobar(huella)

    almacen.solicitar("proponer_cambio", {"x": 1}, "efecto", "t-1")
    assert almacen.veredicto(huella) == "aprobada", "reescribir la solicitud borró la respuesta del CEO"


def test_reabrir_entiende_el_identificador_que_emite_el_motor(tmp_path, almacen):
    """DEFECTO QUE DESTAPÓ LA DEMOSTRACIÓN END-TO-END, no las pruebas de unidad.

    El motor identifica la unidad de trabajo con el `event_id`, que es `"<trace>:<tarea_id>"`. Las
    pruebas pasaban el identificador ya limpio (`"t-1"`), así que la reapertura parecía funcionar;
    en el sistema real la solicitud se guardaba como `"-:t-cambio"`, la comparación no coincidía
    NUNCA y el trabajo aprobado no se reanudaba jamás. La aprobación del CEO no producía efecto.
    """
    estado = _estado(tmp_path)
    estado.registrar(Tarea(objetivo_id="obj", tarea_id="t-cambio", descripcion="x", estado="abierta"))
    estado.transitar("obj", "t-cambio", "bloqueada", autoridad="director", causa="permisos: pendiente")

    almacen.solicitar("proponer_cambio", {"x": 1}, "efecto", "trace-abc:t-cambio")
    almacen.aprobar(huella_de("proponer_cambio", {"x": 1}, "efecto"))

    assert reabrir_aprobadas(almacen, estado) == 1, "no reconoció el identificador que emite el motor"
    assert [t.tarea_id for t in estado.abiertas("obj")] == ["t-cambio"]


def test_reabrir_distingue_aprobadas_de_pendientes_en_el_mismo_objetivo(tmp_path, almacen):
    """MUTANTE VIVO D14. El control anterior no discriminaba: sin NINGUNA decisión aprobada,
    `reabrir_aprobadas` cortaba antes de mirar las tareas y el mutante sobrevivía. Hace falta que
    convivan una aprobada y una pendiente: sólo la primera vuelve al trabajo."""
    estado = _estado(tmp_path)
    for tid in ("t-si", "t-no"):
        estado.registrar(Tarea(objetivo_id="obj", tarea_id=tid, descripcion="x", estado="abierta"))
        estado.transitar("obj", tid, "bloqueada", autoridad="director", causa="permisos: pendiente")

    almacen.solicitar("proponer_cambio", {"a": 1}, "efecto A", "t-si")
    almacen.solicitar("proponer_cambio", {"b": 2}, "efecto B", "t-no")
    almacen.aprobar(huella_de("proponer_cambio", {"a": 1}, "efecto A"))

    assert reabrir_aprobadas(almacen, estado) == 1
    assert [t.tarea_id for t in estado.abiertas("obj")] == ["t-si"], "reabrió una tarea sin aprobación"


def test_la_composicion_cablea_la_reapertura_en_el_latido(tmp_path):
    """MUTANTE VIVO D15, y es ALERTA-005 aplicada a la autonomía: el buzón funcionaría en las pruebas
    y NO en el sistema real. Se verifica sobre el sistema COMPUESTO, que es lo que arranca de verdad:
    se aprueba una decisión, se despierta el latido, y la tarea vuelve al trabajo sola."""
    from aura_skeleton.composicion import Configuracion, componer

    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    sistema = componer(cfg)

    sistema.estado_operativo.registrar(
        Tarea(objetivo_id="obj", tarea_id="t-1", descripcion="cambio", estado="abierta", responsable="programador")
    )
    sistema.estado_operativo.transitar("obj", "t-1", "bloqueada", autoridad="director", causa="permisos: pendiente")

    buzon = AlmacenDecisiones(str(tmp_path / "decisiones"))
    buzon.solicitar("proponer_cambio", {"x": 1}, "efecto", "t-1")
    buzon.aprobar(buzon.pendientes()[0]["huella"])

    # Se mira SÓLO t-1: bloquear una tarea dispara el oyente de transiciones, que crea una tarea de
    # corrección abierta. Comparar contra `[]` mediría ese comportamiento ajeno, no éste.
    def accionables():
        return [t.tarea_id for t in sistema.estado_operativo.abiertas("obj")]

    assert "t-1" not in accionables(), "guarda: la tarea debe partir bloqueada"
    sistema.motor_ciclo._despertar("t")
    assert "t-1" in accionables(), "el latido del sistema real no aplica las decisiones del buzón"


@pytest.mark.asyncio
async def test_la_solicitud_es_legible_por_un_humano(tmp_path, confirmador):
    """El CEO aprueba leyendo estos ficheros a mano. Si no son JSON legible con acentos correctos,
    el canal no sirve para lo que existe."""
    await confirmador("escribir_archivo", _args(), "t")
    fichero = next(Path(tmp_path / "decisiones").glob("*.json"))
    crudo = fichero.read_text(encoding="utf-8")
    assert "\\u" not in crudo, "los acentos salieron escapados: ilegible para un humano"
    assert json.loads(crudo)["estado"] == "pendiente"
