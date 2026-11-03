"""Frontera cognitiva vertical: la batería T1..T8 atravesando el orquestador entero (D-FC-1..8).

Cada caso se ejecuta como un turno real (bus, cascada, cierre) con un proveedor espía que CUENTA las
llamadas: la aserción «0 LLM» no es una lectura del código, es un contador que tendría que moverse.

Los literales T1..T8 son los de aceptación de la misión. «hola, quien eres?» y «que capacidades
tienes?» se conservan como casos EXTRA: superficies del Core que la frontera no puede desplazar.
"""

from __future__ import annotations

import json
import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.conectores.conversacion import ConectorConversacion
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.contexto import RegistroContexto
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.estatus import MARCA_PROPUESTA, Estatus
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import ModelRouter

T1 = "hola como estas?"
T2 = "como me llamo?"
T3 = "a que me dedico?"
EXTRA_IDENTIDAD = "hola, quien eres?"
EXTRA_CAPACIDADES = "que capacidades tienes?"
T4 = "como se llama mi hija?"
T5 = "si meto la mano en agua caliente que me pasa?"
T6 = "si tengo 4 manzanas y me como una, cuantas manzanas me quedan?"
T7 = "quien es Jesus Cristo?"
T8 = "que desarrollas en este momento?"

SAY_MODELO = "Te quemarías la mano: MARCA-MODELO-T5"


class _Espia:
    name = "espia"

    def __init__(self, action: str = "consulta", say: str = SAY_MODELO) -> None:
        self.llamadas: list[tuple[str, str]] = []
        self.action, self.say = action, say

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas.append((prompt, modo))
        return json.dumps({"intent": "x", "action": self.action, "args": {"ruta": "/"}, "say": self.say})


class _Confirmador:
    def __init__(self, respuesta: bool) -> None:
        self.preguntas: list[str] = []
        self.respuesta = respuesta

    async def __call__(self, accion, args, trace_id):
        self.preguntas.append(accion)
        return self.respuesta


def _sistema(tmp_path, espia, confirmador=None):
    # Almacen de PRODUCCION: `SimpleMemory` recupera por `split()` sin palabras vacias y fabrica
    # coincidencias («mi») que `PersistentMemory` no tiene. La frontera se mide sobre lo que se ejecuta.
    mem = PersistentMemory(str(tmp_path / "memoria.json"))
    perm = PermissionManager(confirmador or _Confirmador(True))
    registro = RegistroAdaptadores()
    registro.registrar(EjecutorModeloUsuario(mem))
    motor = MotorAutomatizacion(registro, perm)
    orq = Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([espia], 1200),
        perm,
        VoiceAdapterMock(),
        HomeAssistantMock(),
        motor=motor,
        contexto=RegistroContexto([ConectorConversacion()]),
        modelo_usuario=ModeloUsuario(mem, motor=motor),
    )
    return orq, mem


async def _turno(orq, texto: str, uid: str = "mauricio") -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


def _en_memoria(mem, fragmento: str) -> bool:
    """En RAM y en el fichero persistido: lo que sobrevive al reinicio es lo que importa."""
    en_ram = any(fragmento in json.dumps(i, ensure_ascii=False) for i in mem._items)
    try:
        with open(mem._path, encoding="utf-8") as f:
            en_disco = fragmento in f.read()
    except FileNotFoundError:
        en_disco = False
    return en_ram or en_disco


# ============================================================================ BATERÍA --


@pytest.mark.parametrize(
    ("texto", "dominio", "estatus"),
    [
        (T1, "conversacion_general", Estatus.HECHO),  # saludo: respuesta social del Core
        (T2, "modelo_usuario", Estatus.AUSENCIA),  # T2b: sin memoria
        (T3, "modelo_usuario", Estatus.AUSENCIA),  # sin memoria
        (EXTRA_IDENTIDAD, "conversacion_general", Estatus.HECHO),
        (EXTRA_CAPACIDADES, "conversacion_general", Estatus.HECHO),  # la secuencia de intenciones la atiende
        (T4, "memoria", Estatus.AUSENCIA),
        (T6, "aritmetica", Estatus.HECHO),
        (T7, "sensible", Estatus.ABSTENCION),
    ],
)
async def test_lo_que_responde_el_core_no_llama_al_modelo(texto, dominio, estatus, tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    r = await _turno(orq, texto)
    assert espia.llamadas == [], f"{texto!r} llegó al modelo"
    assert r["provider"] == "core" and r["dominio"] == dominio, r
    assert r["estatus"] == estatus.value, r
    assert not r["say"].startswith(MARCA_PROPUESTA)


async def test_T2_con_hecho_declarado_por_la_via_real_es_HECHO_sin_modelo(tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    await _turno(orq, "Me llamo Mauricio")  # siembra por la vía real: turno + captura de señales
    sembrado = len(espia.llamadas)
    r = await _turno(orq, T2)
    assert r["say"] == "Te llamas Mauricio." and r["estatus"] == Estatus.HECHO.value
    assert len(espia.llamadas) == sembrado, "la respuesta del hecho declarado no puede pasar por el modelo"


async def test_T4_con_memoria_NO_vacia_sigue_en_AUSENCIA_sin_modelo(tmp_path):
    """Caso de control de la batería (T4 sin memoria): con un hecho declarado real en el almacén de
    producción, «mi» no es un término recuperable y la pregunta no sale al modelo."""
    espia = _Espia()
    orq, mem = _sistema(tmp_path, espia)
    await _turno(orq, "Mi color favorito es el azul")  # siembra por la vía real
    assert _en_memoria(mem, "azul"), "guarda: la memoria tenía que dejar de estar vacía"
    sembrado = len(espia.llamadas)
    r = await _turno(orq, T4)
    assert r["dominio"] == "memoria" and r["estatus"] == Estatus.AUSENCIA.value, r
    assert len(espia.llamadas) == sembrado


async def test_T1_es_una_respuesta_social_valida(tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    r = await _turno(orq, T1)
    assert espia.llamadas == []
    assert r["say"].strip() and "recuerdo" not in r["say"].lower(), r["say"]


async def test_T3_con_trabajo_declarado_por_la_via_real_es_HECHO_sin_modelo(tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    await _turno(orq, "Trabajo en logística")  # siembra por la vía real: turno + captura de señales
    sembrado = len(espia.llamadas)
    r = await _turno(orq, T3)
    assert r["say"] == "Trabajas en logística." and r["estatus"] == Estatus.HECHO.value
    assert len(espia.llamadas) == sembrado


async def test_T5_va_al_modelo_UNA_vez_como_PROPUESTA_y_nunca_a_memoria(tmp_path):
    espia = _Espia()
    orq, mem = _sistema(tmp_path, espia)
    r = await _turno(orq, T5)
    assert len(espia.llamadas) == 1 and espia.llamadas[0][1] == "cognitivo"
    assert r["estatus"] == Estatus.PROPUESTA.value and r["say"] == f"{MARCA_PROPUESTA} {SAY_MODELO}"
    assert not _en_memoria(mem, "MARCA-MODELO-T5")
    assert not [e for e in await orq.modelo_usuario.ver("mauricio") if "MARCA-MODELO" in str(e)]


async def test_T6_es_3_sin_modelo(tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    r = await _turno(orq, T6)
    assert r["say"] == "Te quedan 3 manzanas." and "3" in r["say"]
    assert espia.llamadas == []


async def test_T7_nunca_llega_a_memoria(tmp_path):
    espia = _Espia(say="FALSEDAD-T7")
    orq, mem = _sistema(tmp_path, espia)
    r = await _turno(orq, T7)
    assert "FALSEDAD-T7" not in r["say"] and not _en_memoria(mem, "FALSEDAD-T7")
    assert not _en_memoria(mem, "Jesus"), "una pregunta no se almacena"


class _Autonomo:
    def instantanea(self):
        return {"estado": "TRABAJANDO", "ultimo_ciclo": 42}


class _EstadoOperativoVacio:
    def objetivos_activos(self):
        return []


async def test_T8_sin_objetivos_es_AUSENCIA_del_core_sin_modelo(tmp_path):
    """El estado operativo real no tiene objetivos: la respuesta honesta es la ausencia, del Core."""
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    orq.estado_operativo = _EstadoOperativoVacio()
    r = await _turno(orq, T8)
    assert r["provider"] == "core" and r["dominio"] == "aura" and r["estatus"] == Estatus.AUSENCIA.value
    assert "ningún objetivo activo" in r["say"] and espia.llamadas == []


async def test_T8_con_estado_real_es_HECHO_con_el_dato(tmp_path):
    """Caso de control de la AUSENCIA de la batería: con fuente, el Core dice el dato real."""
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    orq.estado_autonomo = _Autonomo()
    r = await _turno(orq, T8)
    assert r["dominio"] == "aura" and r["estatus"] == Estatus.HECHO.value and "42" in r["say"]
    assert espia.llamadas == []


# ============================================================================ ACCIONES --


async def test_una_accion_inventada_por_el_modelo_no_se_ejecuta_y_es_PROPUESTA(tmp_path):
    """El modelo propone; el motor y los permisos deciden. `formatear_disco` no es una capacidad
    registrada: el motor no la ejecuta y la frase de éxito del modelo se descarta."""
    espia = _Espia(action="formatear_disco", say="Listo, disco formateado.")
    confirmador = _Confirmador(True)
    orq, _ = _sistema(tmp_path, espia, confirmador)
    r = await _turno(orq, "borra el archivo informe.txt")
    assert len(espia.llamadas) == 1 and espia.llamadas[0][1] == "accion"
    assert "Listo, disco formateado" not in r["say"]
    assert "No pude ejecutar la accion" in r["say"] or "No ejecute la accion" in r["say"], r["say"]
    assert r["estatus"] == Estatus.PROPUESTA.value


class _AdaptadorEspia:
    """Capacidad REAL de lista roja con dry-run viable: lo unico que decide es el permiso humano."""

    name = "espia-archivos"
    capabilities = ["renombrar_archivo"]

    def __init__(self) -> None:
        self.ejecutadas: list[str] = []

    async def simular(self, accion, args, trace_id):
        return {"viable": True}

    async def execute(self, command, args, trace_id, event_id):
        self.ejecutadas.append(command)
        return {"status": "ok"}


@pytest.mark.parametrize("humano_autoriza", [False, True])
async def test_una_accion_registrada_la_deciden_los_permisos_no_el_modelo(humano_autoriza, tmp_path):
    """Con `False` el modelo propone y no pasa nada; con `True` (caso de control) el MISMO turno ejecuta.
    Si la ejecucion dependiera del modelo, las dos variantes darian lo mismo."""
    espia = _Espia(action="renombrar_archivo", say="Renombrado.")
    confirmador = _Confirmador(humano_autoriza)
    orq, _ = _sistema(tmp_path, espia, confirmador)
    adaptador = _AdaptadorEspia()
    orq.motor.registro.registrar(adaptador)
    r = await _turno(orq, "renombra el archivo informe.txt")
    assert confirmador.preguntas == ["renombrar_archivo"], "lista roja: el humano tiene que ser preguntado"
    assert adaptador.ejecutadas == (["renombrar_archivo"] if humano_autoriza else [])
    assert r["estatus"] == Estatus.PROPUESTA.value


class _EspiaSinEsquema:
    """Devuelve SIEMPRE una accion real del catalogo con args, en cualquier modo: no hay esquema que
    la frene. Registra el modo en que se le llamo."""

    name = "sin-esquema"

    def __init__(self) -> None:
        self.modos: list[str] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.modos.append(modo)
        return json.dumps({"intent": "x", "action": "borrar_archivo", "args": {"ruta": "/tmp/x"}, "say": "Borrado."})


@pytest.mark.parametrize(
    ("texto", "modo", "llega_al_motor"),
    [
        (T5, "cognitivo", False),
        ("borra el archivo informe.txt", "accion", True),  # caso de control: el motor SÍ la recibe
    ],
)
async def test_en_modo_cognitivo_el_core_descarta_la_accion_aunque_no_haya_esquema(
    texto, modo, llega_al_motor, tmp_path
):
    espia = _EspiaSinEsquema()
    orq, _ = _sistema(tmp_path, espia, _Confirmador(False))
    llamadas_motor: list[tuple[str, dict]] = []
    ejecutar_real = orq.motor.ejecutar

    async def _motor_espia(accion, args, *a, **kw):
        llamadas_motor.append((accion, args))
        return await ejecutar_real(accion, args, *a, **kw)

    orq.motor.ejecutar = _motor_espia
    r = await _turno(orq, texto)
    assert espia.modos == [modo], "guarda: el turno tenia que llegar al proveedor en ese modo"
    assert llamadas_motor == ([("borrar_archivo", {"ruta": "/tmp/x"})] if llega_al_motor else [])
    assert r["estatus"] == Estatus.PROPUESTA.value
    if not llega_al_motor:
        assert "[accion" not in r["say"] and "[error en" not in r["say"], r["say"]


# ============================================ SUPOSICIONES NUMÉRICAS: NUNCA AL MODELO (D-FC-4) --


@pytest.mark.parametrize(
    "texto",
    [
        "si un coche cuesta 2000 euros al mes, cuanto cuesta en un año?",
        "si un tren va a 80 km por hora, cuantos km recorre en 3 horas?",
        "si compro 3 panes a 2 euros cada uno, cuanto pago?",
        "si todos los alumnos son 30 y faltan 4, cuantos vinieron?",
    ],
)
async def test_suposicion_numerica_infradeterminada_es_ACLARACION_sin_modelo(texto, tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    r = await _turno(orq, texto)
    assert espia.llamadas == [], f"{texto!r} llegó al modelo"
    assert r["provider"] == "core" and r["dominio"] == "formal" and r["estatus"] == Estatus.ACLARACION.value, r


async def test_suposicion_con_posesivo_nunca_es_PROPUESTA(tmp_path):
    espia = _Espia()
    orq, _ = _sistema(tmp_path, espia)
    r = await _turno(orq, "si mi hija tiene 7 años, cuantos cumplira el proximo verano?")
    assert espia.llamadas == []
    assert r["provider"] == "core" and r["estatus"] != Estatus.PROPUESTA.value, r


# ================================================================ «ESCRIBE» COMO ACCIÓN --


@pytest.mark.parametrize(
    ("texto", "pide"),
    [
        ("Escribe 'version nueva' en notas.txt", True),
        ("quiero escribir un informe en notas.txt", True),
        ("describe la fotosintesis", False),  # «describe» contiene «escribe»: la subcadena colisionaría
        ("describeme como funciona un motor", False),
        ("como se escribe hola en ingles?", False),  # ortografía, no una orden
    ],
)
def test_escribe_pide_accion_solo_como_palabra_y_no_impersonal(texto, pide):
    from aura_skeleton.core.orchestrator import _RE_PIDE_ESCRIBIR, _normalizar, _pide_accion

    assert _pide_accion(texto) is pide, texto
    # Guarda: el veredicto lo da ESTA regla, no otro verbo de la tupla.
    assert (_RE_PIDE_ESCRIBIR.search(_normalizar(texto)) is not None) is pide, texto


def test_las_24_negativas_de_memoria_no_cambian_de_ruta_por_escribe():
    """La pared va antes que la decisión de modo; y además ninguna negativa activa la regla nueva."""
    import pathlib

    from aura_skeleton.core.orchestrator import _RE_PIDE_ESCRIBIR, _es_consulta_de_memoria, _normalizar

    datos = pathlib.Path(__file__).resolve().parents[1] / "datos" / "bateria_memoria.json"
    negativas = [
        c["texto"] for c in json.loads(datos.read_text(encoding="utf-8"))["consultas"] if c["esperado"] is None
    ]
    assert len(negativas) == 24
    assert all(_es_consulta_de_memoria(t) for t in negativas)
    assert not [t for t in negativas if _RE_PIDE_ESCRIBIR.search(_normalizar(t))]


async def test_como_se_escribe_no_llega_al_motor(tmp_path):
    espia = _EspiaSinEsquema()
    orq, _ = _sistema(tmp_path, espia, _Confirmador(True))
    llamadas_motor: list[str] = []
    ejecutar_real = orq.motor.ejecutar

    async def _motor_espia(accion, args, *a, **kw):
        llamadas_motor.append(accion)
        return await ejecutar_real(accion, args, *a, **kw)

    orq.motor.ejecutar = _motor_espia
    await _turno(orq, "como se escribe hola en ingles?")
    assert llamadas_motor == []
    assert espia.modos in ([], ["cognitivo"]), espia.modos


async def test_escribe_en_un_fichero_SI_llega_al_motor(tmp_path):
    """Control del anterior: la orden real alcanza el motor, que la gobierna con permisos."""
    espia = _EspiaSinEsquema()
    orq, _ = _sistema(tmp_path, espia, _Confirmador(False))
    llamadas_motor: list[str] = []
    ejecutar_real = orq.motor.ejecutar

    async def _motor_espia(accion, args, *a, **kw):
        llamadas_motor.append(accion)
        return await ejecutar_real(accion, args, *a, **kw)

    orq.motor.ejecutar = _motor_espia
    await _turno(orq, "Escribe 'version nueva' en notas.txt")
    assert espia.modos == ["accion"] and llamadas_motor == ["borrar_archivo"]


def test_en_modo_cognitivo_el_esquema_fuerza_consulta():
    """La restricción del modo cognitivo vive en el esquema de decodificado del proveedor real: el
    modelo no puede nombrar otra acción ni al decodificar. Se comprueba el esquema que se envía."""
    from aura_skeleton.modules.providers_real import _ESQUEMA_COGNITIVO

    assert _ESQUEMA_COGNITIVO["properties"]["action"]["enum"] == ["consulta"]
    assert "action" in _ESQUEMA_COGNITIVO["required"]
