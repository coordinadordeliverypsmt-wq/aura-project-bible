"""Un hecho redeclarado produce HISTORIAL y VIGENCIA, no dos verdades simultáneas.

*AMP-AURA etapas 1-2 · `D-AMP-1 = B` aprobada por el CEO (2026-09-10).*

**El defecto que cierra esta batería, medido antes de tocar código.** Se declaró «Mi cumpleaños es el
10 de mayo» y después «Mi cumpleaños es el 3 de junio». En el almacén quedaron **dos entradas
indistinguibles y las dos igual de vivas**: ninguna decía cuál era la actual, ni que la segunda
sustituía a la primera, ni desde cuándo. La consulta acertaba —respondía «3 de junio»— pero por un
`reversed()` en la lectura: acertaba **por el orden de llegada**, no porque el sistema supiera cuál
estaba vigente. Un inspector que leyera el almacén no podía decir cuál era el cumpleaños del usuario.

**Lo que se añade son cuatro campos y ni uno más** —`version`, `supersedes`, `valid_from`,
`valid_until`—, exactamente los autorizados. «Superseded» no es un quinto campo: es `valid_until is not
None`, derivado, porque un booleano aparte podría contradecir a la fecha.

**Lo que NO se añade, por decisión del CEO:** ni `PROPOSE`, ni alias de identidad (`D-AMP-5`), ni
búsqueda semántica, ni `confidence`. El historial no lo decide el modelo: la identidad del hecho sale
de la gramática de la propia frase del usuario, sin una sola llamada al LLM (ADR-0014).
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import _clasificar, _normalizar
from aura_skeleton.core.almacen_senales import AlmacenSenales
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.identidad_memoria import identidad_de
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.senales import ClaseSenal, Senal
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter

V1 = "Mi cumpleaños es el 10 de mayo"
V2 = "Mi cumpleaños es el 3 de junio"


class _ProveedorProhibido:
    """Un proveedor que NO debe llegar a usarse. Cuenta las llamadas y delata la que sobre."""

    name = "prohibido"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"el modelo inventando una fecha"}'


async def _si(accion, args, trace_id):
    return True


def _sistema(mem: SimpleMemory):
    espia = _ProveedorProhibido()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    orq = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([espia], 1200),
        PermissionManager(_si),
        VoiceAdapterMock(),
        HomeAssistantMock(),
        modelo_usuario=ModeloUsuario(mem, motor=motor),
    )
    return orq, espia


async def _declarar(mem: SimpleMemory, frase: str, uid: str = "mauricio", ts: float | None = None) -> None:
    """Siembra por la VÍA REAL: se clasifica el enunciado y se guarda la señal que salga.

    Escribir a mano en el almacén probaría el almacén, no el sistema: el versionado vive en el ejecutor
    del motor único y solo se ejerce si la escritura pasa por ahí (G-1).
    """
    clase = _clasificar(_normalizar(frase))
    assert clase is not None, f"el enunciado no se clasifica: {frase!r}"
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    await AlmacenSenales(mem, motor=motor).guardar(uid, [Senal(clase, frase, "conversacion", "t1", ts=ts)])


async def _turno(orq, texto: str, uid: str = "mauricio") -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


def _entradas(mem: SimpleMemory, uid: str = "mauricio") -> list[dict]:
    return [i for i in mem._items if i["user_id"] == uid]


def _prov(mem: SimpleMemory, contenido: str) -> dict:
    """La procedencia de la entrada cuyo contenido es exactamente `contenido`."""
    iguales = [i for i in mem._items if i["content"] == contenido]
    assert len(iguales) == 1, f"se esperaba una sola entrada con {contenido!r}, hay {len(iguales)}"
    return iguales[0].get("provenance", {})


# ------------------------------------------------------- A · LA PRIMERA DECLARACIÓN ES LA V1 --


@pytest.mark.asyncio
async def test_la_primera_declaracion_nace_como_version_1_vigente():
    """Sin `version` en la primera, la segunda no tendría sobre qué contar."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    p = _prov(mem, V1)
    assert p["version"] == 1
    assert p["supersedes"] is None, "la primera no sustituye a nada: inventarlo sería fabricar historial"
    assert p["valid_from"] == 1000.0, "la vigencia empieza cuando el usuario lo dijo, no cuando se escribió"
    assert p["valid_until"] is None, "nada la ha superseded todavía"


@pytest.mark.asyncio
async def test_valid_from_es_el_ts_de_la_senal_y_no_un_segundo_reloj():
    """Caso de control: dos relojes para el mismo hecho son dos historias del mismo hecho."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    p = _prov(mem, V1)
    assert p["valid_from"] == p["ts"] == 1000.0


# ------------------------------------------------------ B · LA REDECLARACIÓN ES LA V2 Y CITA --


@pytest.mark.asyncio
async def test_la_redeclaracion_es_la_version_2_y_declara_a_quien_sustituye():
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    p2 = _prov(mem, V2)
    assert p2["version"] == 2
    assert p2["supersedes"] == 1, "sin esto el historial es una lista, no una cadena"
    assert p2["valid_from"] == 2000.0
    assert p2["valid_until"] is None


@pytest.mark.asyncio
async def test_la_cadena_sigue_contando_en_la_tercera_declaracion():
    """Caso de control del contador: si se reiniciase, dos entradas compartirían `version` y
    `supersedes` dejaría de señalar a una sola."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    await _declarar(mem, "Mi cumpleaños es el 7 de julio", ts=3000.0)
    p3 = _prov(mem, "Mi cumpleaños es el 7 de julio")
    assert (p3["version"], p3["supersedes"]) == (3, 2)
    assert [_prov(mem, c)["version"] for c in (V1, V2)] == [1, 2]
    # Y la historia NO se reescribe: la V1 se cerró cuando llegó la V2 y sigue cerrada ahí. Si cada
    # declaración nueva recerrase las antiguas, todas las versiones parecerían haber caducado a la vez
    # y el «desde cuándo hasta cuándo» de cada una se perdería.
    assert _prov(mem, V1)["valid_until"] == 2000.0
    assert _prov(mem, V2)["valid_until"] == 3000.0


# ------------------------------------------------------------- C y D · SUPERSESSION Y CIERRE --


@pytest.mark.asyncio
async def test_la_version_1_queda_superseded_con_su_vigencia_cerrada():
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    p1 = _prov(mem, V1)
    assert p1["valid_until"] == 2000.0, "se cierra en el instante en que el usuario declaró la nueva"
    assert p1["valid_until"] == _prov(mem, V2)["valid_from"], "sin hueco ni solape entre versiones"


@pytest.mark.asyncio
async def test_superseded_se_deriva_de_valid_until_y_no_es_un_quinto_campo():
    """El perímetro autorizado son CUATRO campos. Un booleano `superseded` podría contradecir a la
    fecha, y entonces habría que decidir cuál manda."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    nuevos = {"version", "supersedes", "valid_from", "valid_until"}
    for contenido in (V1, V2):
        sobrantes = set(_prov(mem, contenido)) - nuevos - {"trace_id", "fuente", "clase", "origen", "ts"}
        assert not sobrantes, f"campos fuera de la autorización en {contenido!r}: {sobrantes}"
    assert (_prov(mem, V1)["valid_until"] is not None) and (_prov(mem, V2)["valid_until"] is None)


# ----------------------------------------------------------- E · EXACTAMENTE UNA V I G E N T E --


@pytest.mark.asyncio
async def test_de_la_misma_identidad_solo_queda_una_vigente():
    """El defecto medido era justo este: dos entradas igual de vivas y ninguna marcada como actual."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    vigentes = [
        i["content"]
        for i in _entradas(mem)
        if identidad_de(i["content"]) == "cumpleanos" and i["provenance"].get("valid_until") is None
    ]
    assert vigentes == [V2]


@pytest.mark.asyncio
async def test_redeclarar_OTRO_atributo_no_cierra_la_vigencia_del_primero():
    """Caso de control: si el cierre no discriminase la identidad, declarar el coche borraría el
    cumpleaños del presente."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, "Mi coche es un Seat Leon", ts=2000.0)
    assert _prov(mem, V1)["valid_until"] is None
    assert _prov(mem, V1)["version"] == 1
    assert _prov(mem, "Mi coche es un Seat Leon")["version"] == 1, "otra identidad, otro contador"


@pytest.mark.asyncio
async def test_lo_que_declara_OTRO_usuario_no_toca_mi_historial():
    """P-ARQ-5. Sin el aislamiento, el cumpleaños de otra persona supersedería el mío."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, uid="otra-persona", ts=2000.0)
    assert _prov(mem, V1)["valid_until"] is None
    assert _prov(mem, V2)["version"] == 1, "es su primera declaración, no mi segunda"


# --------------------------------------------- F y G · LA CONSULTA, SIN UNA LLAMADA AL MODELO --


@pytest.mark.asyncio
async def test_la_consulta_devuelve_la_version_vigente_sin_llamar_al_modelo():
    """**El caso obligatorio del CEO, de extremo a extremo.**"""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    r = await _turno(orq, "¿Cuál es mi cumpleaños?")
    assert "3 de junio" in r["say"], r["say"]
    assert "10 de mayo" not in r["say"], "lo superseded no se afirma en el presente"
    assert espia.llamadas == 0, "la autoridad sobre los hechos es del Core (ADR-0014)"
    assert r["provider"] == "core" and r["dominio"] == "modelo_usuario"


@pytest.mark.asyncio
async def test_la_respuesta_NO_depende_del_orden_en_que_el_almacen_devuelva_las_entradas():
    """**La prueba que separa «acierta» de «lo sabe».** Antes, la respuesta correcta la producía un
    `reversed()`: bastaba que el almacén devolviera otro orden para que AURA afirmase una fecha
    caducada. Ahora el criterio es la vigencia, así que invertir el almacén no cambia nada."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    mem._items.reverse()
    r = await _turno(orq, "¿Cuál es mi cumpleaños?")
    assert "3 de junio" in r["say"], r["say"]
    assert espia.llamadas == 0


# ------------------------------------------------------ H · LA V1 SIGUE SIENDO DEMOSTRABLE --


@pytest.mark.asyncio
async def test_la_version_anterior_se_conserva_y_se_puede_inspeccionar():
    """Supersession NO es borrado (ADR-0017): lo que el usuario dijo sigue ahí, fechado."""
    mem = SimpleMemory()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    modelo = ModeloUsuario(mem, motor=motor)
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    historial = {e["contenido"]: e for e in await modelo.ver("mauricio")}
    assert set(historial) == {V1, V2}, "la V1 no se pierde al ser superseded"
    assert (historial[V1]["version"], historial[V1]["valid_until"]) == (1, 2000.0)
    assert (historial[V2]["version"], historial[V2]["valid_until"]) == (2, None)
    assert historial[V2]["supersedes"] == 1


@pytest.mark.asyncio
async def test_refutar_no_reinicia_el_contador_de_versiones():
    """Caso de control: refutar retira algo del presente, no reescribe la historia."""
    mem = SimpleMemory()
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), PermissionManager(_si))
    modelo = ModeloUsuario(mem, motor=motor)
    await _declarar(mem, V1, ts=1000.0)
    await _declarar(mem, V2, ts=2000.0)
    await modelo.refutar("mauricio", V2)
    await _declarar(mem, "Mi cumpleaños es el 7 de julio", ts=3000.0)
    assert _prov(mem, "Mi cumpleaños es el 7 de julio")["version"] == 3


# --------------------------------------------------------- I · COMPATIBILIDAD CON LO HEREDADO --


@pytest.mark.asyncio
async def test_una_entrada_escrita_antes_de_esta_etapa_sigue_respondiendose():
    """Lo ya guardado no tiene los cuatro campos. Si eso lo dejara fuera del presente, la mejora
    habría borrado la memoria existente del usuario."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await mem.write(
        "mauricio",
        "semantica",
        V1,
        {
            "trace_id": "t",
            "fuente": "conversacion",
            "clase": ClaseSenal.HECHO_DECLARADO.value,
            "origen": "declarada",
            "ts": 1000.0,
        },
    )
    r = await _turno(orq, "¿Cuál es mi cumpleaños?")
    assert "10 de mayo" in r["say"], r["say"]
    assert espia.llamadas == 0


@pytest.mark.asyncio
async def test_una_entrada_heredada_cuenta_como_la_version_1_al_redeclararse():
    """La heredada existía y era vigente aunque nadie la numerase: la nueva es la 2, no otra 1."""
    mem = SimpleMemory()
    await mem.write(
        "mauricio",
        "semantica",
        V1,
        {
            "trace_id": "t",
            "fuente": "conversacion",
            "clase": ClaseSenal.HECHO_DECLARADO.value,
            "origen": "declarada",
            "ts": 1000.0,
        },
    )
    await _declarar(mem, V2, ts=2000.0)
    assert (_prov(mem, V2)["version"], _prov(mem, V2)["supersedes"]) == (2, 1)
    assert _prov(mem, V1)["valid_until"] == 2000.0, "la heredada también se cierra"


# ------------------------------- EL DRY-RUN DICE LA VERDAD COMPLETA SOBRE LO QUE VA A PASAR --


@pytest.mark.asyncio
async def test_el_dry_run_anuncia_la_version_y_el_cierre_que_va_a_producir():
    """Quien aprueba el plan tiene que ver TODO el efecto. Decir solo «registraría una entrada»
    cuando además se cierra la vigencia de la anterior es «declarado ≠ real» en pequeño."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    ejecutor = EjecutorModeloUsuario(mem)
    plan = await ejecutor.simular("registrar_informacion_usuario", {"user_id": "mauricio", "contenido": V2}, "t")
    assert plan["viable"] is True
    assert "v2" in plan["efecto"] and "cerrando la vigencia de 1" in plan["efecto"], plan["efecto"]


@pytest.mark.asyncio
async def test_el_dry_run_no_muta_el_historial():
    """Caso de control: un dry-run que cerrase la vigencia habría ejecutado sin permiso."""
    mem = SimpleMemory()
    await _declarar(mem, V1, ts=1000.0)
    antes = json.dumps(mem._items, sort_keys=True)
    await EjecutorModeloUsuario(mem).simular(
        "registrar_informacion_usuario", {"user_id": "mauricio", "contenido": V2}, "t"
    )
    assert json.dumps(mem._items, sort_keys=True) == antes


@pytest.mark.asyncio
async def test_el_dry_run_de_algo_que_no_declara_un_atributo_no_promete_version():
    """Caso de control del anterior: sin identidad no hay versión que anunciar."""
    plan = await EjecutorModeloUsuario(SimpleMemory()).simular(
        "registrar_informacion_usuario", {"user_id": "mauricio", "contenido": "Me gusta el jazz"}, "t"
    )
    assert plan == {"viable": True, "efecto": "registraria una entrada"}


# ------------------------------------------------------------ J · NO CONTAMINAR LO QUE NO TOCA --


@pytest.mark.asyncio
async def test_lo_que_no_declara_un_atributo_NO_se_versiona():
    """Un gusto suelto no es una versión de nada: numerarlo sería declarar un historial que nadie
    pidió, y el perímetro de esta etapa es justo lo contrario."""
    mem = SimpleMemory()
    await _declarar(mem, "Me gusta el jazz", ts=1000.0)
    p = _prov(mem, "Me gusta el jazz")
    assert not ({"version", "supersedes", "valid_from", "valid_until"} & set(p)), p


@pytest.mark.asyncio
async def test_dos_gustos_distintos_no_se_superseden_entre_si():
    """Caso de control del anterior: sin identidad no hay cadena, así que nada se cierra."""
    mem = SimpleMemory()
    await _declarar(mem, "Me gusta el jazz", ts=1000.0)
    await _declarar(mem, "Me gusta el flamenco", ts=2000.0)
    for c in ("Me gusta el jazz", "Me gusta el flamenco"):
        assert _prov(mem, c).get("valid_until") is None


@pytest.mark.asyncio
async def test_preguntar_por_un_atributo_jamas_declarado_no_lo_fabrica():
    """INV-9 otra vez: la vigencia no abre una puerta nueva por la que inventar."""
    mem = SimpleMemory()
    orq, espia = _sistema(mem)
    await _declarar(mem, V2, ts=2000.0)
    r = await _turno(orq, "¿Cuál es mi cumpleaños?")
    assert "3 de junio" in r["say"]
    assert _prov(mem, V2)["supersedes"] is None
    assert espia.llamadas == 0
