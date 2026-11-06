"""E2E MVP Modelo de Usuario: inspeccionar, entender, corregir y OLVIDAR — con REINICIO real.

Criterio definitivo del CEO (2026-07-28): tras "olvida eso" y un reinicio de AURA, el dato NO reaparece.
Si reaparece, el incremento NO está terminado aunque las pruebas estén en verde. Esta prueba reconstruye
la memoria desde disco (el "reinicio") y verifica que el olvido persistió.
"""

import os
import uuid

import pytest

from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.modules.memory import PersistentMemory
from aura_skeleton.modules.router import MockProvider, ModelRouter


async def _deny(a, args, tid):
    return False


def _orq(mem):
    # MOTOR ANADIDO 2026-08-25 (F4). `ModeloUsuario` ya no muta el almacen directamente: enruta por
    # el motor unico. Sin motor no mutaria nada y estas pruebas pasarian EN VACIO. El veredicto que
    # miden NO cambia; se completa el cableado que la migracion hizo obligatorio.
    permisos = PermissionManager(_deny)
    motor = MotorAutomatizacion(EjecutorModeloUsuario(mem), permisos)
    return Orchestrator(
        InProcessEventBus(),
        mem,
        ModelRouter([MockProvider("m", 1)], 1200),
        permisos,
        VoiceAdapterMock(),
        HomeAssistantMock(),
        modelo_usuario=ModeloUsuario(mem, motor=motor),
    )


async def _di(orq, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance("mauricio", texto, tid)
    return (await orq.wait(tid))["say"]


async def _sembrar(mem):
    # Lo que AURA "sabe" del usuario: uno declarado, uno observado.
    await mem.write(
        "mauricio", "semantica", "prefiere la luz tenue de noche", {"origen": "declarada", "fuente": "usuario"}
    )
    await mem.write(
        "mauricio",
        "semantica",
        "suele pagar las facturas por la app",
        {"origen": "observada", "fuente": "conversacion"},
    )


@pytest.mark.asyncio
async def test_soberania_completa_con_reinicio(tmp_path):
    ruta = os.path.join(tmp_path, "mem.jsonl")
    mem = PersistentMemory(ruta)
    await _sembrar(mem)
    orq = _orq(mem)

    # 1. Inspeccionar: AURA distingue declarado ("me lo dijiste") de observado ("lo he observado").
    r1 = await _di(orq, "¿Qué sabes de mí?")
    assert "prefiere la luz tenue de noche (me lo dijiste)" in r1
    assert "suele pagar las facturas por la app (lo he observado)" in r1

    # 2. Entender: por qué lo sabe (el foco es lo observado, lo cuestionable).
    r2 = await _di(orq, "¿Por qué dices eso?")
    assert "observado" in r2.lower() and "facturas" in r2.lower()

    # 3. Corregir: "eso ya no es cierto".
    r3 = await _di(orq, "Eso ya no es cierto.")
    assert "corrijo" in r3.lower()

    # 4. Olvidar: "olvida eso".
    r4 = await _di(orq, "Olvida eso.")
    assert "hecho" in r4.lower()

    # --- REINICIO: nueva memoria desde disco, nuevo orquestador ---
    orq2 = _orq(PersistentMemory(ruta))
    r5 = await _di(orq2, "¿Qué sabes de mí?")
    assert "luz tenue" in r5, "lo declarado no olvidado debe seguir"
    assert "facturas" not in r5, "lo OLVIDADO no puede reaparecer tras reiniciar"


@pytest.mark.asyncio
async def test_olvidar_un_termino_explicito(tmp_path):
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    r = await _di(orq, "Olvida lo de las facturas.")
    assert "hecho" in r.lower()
    r2 = await _di(orq, "¿Qué sabes de mí?")
    assert "facturas" not in r2 and "luz tenue" in r2


async def _di_uid(orq, uid, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return (await orq.wait(tid))["say"]


def _es_export_json(r):
    """True si la respuesta es el modelo exportado (JSON parseable del propio usuario)."""
    import json

    try:
        datos = json.loads(r)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(datos, dict) and datos.get("usuario") == "mauricio"


@pytest.mark.asyncio
async def test_M3_2a_solicitud_pregunta_y_solo_la_confirmacion_exporta(tmp_path):
    """M3.2a opción A (acta `decisiones/2026-10-11-M3.2a-exportar-confirmacion-opcion-A.md`): la solicitud
    NO vuelca el modelo — pide confirmación. Solo «sí, exporta» entrega el JSON neutral (Bible 4.1 §5)."""
    import json

    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    r1 = await _di(orq, "Exporta lo que sabes de mí.")
    assert not _es_export_json(r1), "la solicitud NO puede volcar el modelo: debe pedir confirmación"
    assert "confirmar" in r1.lower() or "sí, exporta" in r1.lower(), r1
    assert "luz tenue" not in r1 and "facturas" not in r1

    r2 = await _di(orq, "Sí, exporta.")
    datos = json.loads(r2)  # formato neutral parseable sin AURA
    assert datos["usuario"] == "mauricio" and "exportado_ts" in datos
    assert "luz tenue" in r2 and "facturas" in r2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    ["Exporta lo que sabes de mí.", "Dame todo lo que sabes de mí.", "Exporta mi modelo de usuario."],
)
async def test_peticiones_reflexivas_legitimas_preguntan_y_tras_confirmar_exportan(tmp_path, frase):
    """Formulaciones legítimas: preguntan y, tras confirmar, exportan (no «declarado ≠ real»)."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    r1 = await _di(orq, frase)
    assert not _es_export_json(r1) and "confirmar" in r1.lower()
    r2 = await _di(orq, "Sí, exporta.")
    assert _es_export_json(r2) and "luz tenue" in r2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    [
        # 1ª forma: verbo de exportación en conversación general (ni siquiera pregunta).
        "Mi empresa exporta café a Europa.",
        "Quiero exportar este archivo de Excel.",
        "Trabajo en una empresa exportadora.",
        # 2ª forma: verbo + objeto genérico.
        "Mi empresa exporta mis datos de ventas a otra sucursal.",
        "Necesito descargar mi memoria USB, se quedó sin espacio.",
        "Quiero exportar mi perfil de usuario de este videojuego a otra cuenta.",
        # 3ª forma (bypass del guard léxico): verbo y objeto reflexivo en cláusulas inconexas.
        "Dame limón. Lo que sabes de mi novio no me interesa.",
        "Descarga mi modelo de usuario para la demo del hackathon.",
        "Mándame la lista de lo que sabes de mi equipo de fútbol.",
    ],
)
async def test_mundanas_y_bypasses_NUNCA_vuelcan_el_modelo_directo(tmp_path, frase):
    """La garantía ya NO es la detección léxica (3 bypass demostrados, ECC) sino la CONFIRMACIÓN: ninguna
    frase, por mundana o retorcida que sea, vuelca el modelo en la respuesta directa. A lo sumo pregunta."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    r = await _di(orq, frase)
    assert not _es_export_json(r), f"la frase volcó el modelo sin confirmación: {r!r}"
    assert "luz tenue" not in r and "facturas" not in r, f"fuga de datos del modelo: {r!r}"


@pytest.mark.asyncio
async def test_un_bypass_sin_confirmar_nunca_vuelca(tmp_path):
    """Aunque un bypass dispare la PREGUNTA, sin una confirmación afirmativa jamás se exporta."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    await _di(orq, "Dame limón. Lo que sabes de mi novio no me interesa.")  # puede preguntar
    r = await _di(orq, "No, hablaba de otra cosa.")  # negativa / cambio de tema
    assert not _es_export_json(r) and "luz tenue" not in r


@pytest.mark.asyncio
async def test_confirmacion_sin_solicitud_no_exporta(tmp_path):
    """«Sí, exporta» suelto, sin una solicitud pendiente, no hace nada: no hay consentimiento que consumir."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    r = await _di(orq, "Sí, exporta.")
    assert not _es_export_json(r) and "luz tenue" not in r


@pytest.mark.asyncio
async def test_negativa_descarta_el_pendiente(tmp_path):
    """Tras pedir y decir «no», el pendiente se descarta: un «sí, exporta» POSTERIOR ya no vuelca nada."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    await _di(orq, "Exporta lo que sabes de mí.")  # pregunta
    r_no = await _di(orq, "No.")
    assert not _es_export_json(r_no)
    r_si = await _di(orq, "Sí, exporta.")  # ya no hay pendiente
    assert not _es_export_json(r_si), "una confirmación tardía no puede resucitar un pendiente descartado"


@pytest.mark.asyncio
async def test_cambio_de_tema_descarta_el_pendiente(tmp_path):
    """Un turno inconexo tras la solicitud descarta el pendiente (vive un turno)."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    await _di(orq, "Exporta lo que sabes de mí.")
    r_tema = await _di(orq, "¿Qué sabes de mí?")  # cambio de tema: listado de ver, no export
    assert not _es_export_json(r_tema)
    r_si = await _di(orq, "Sí, exporta.")
    assert not _es_export_json(r_si)


@pytest.mark.asyncio
async def test_confirmacion_de_otro_usuario_no_exporta(tmp_path):
    """El pendiente es por `uid`: si lo pide A, una confirmación de B no exporta (ni el modelo de A ni el de B)."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)  # modelo de "mauricio"
    orq = _orq(mem)
    await _di_uid(orq, "mauricio", "Exporta lo que sabes de mí.")  # pendiente de mauricio
    r_b = await _di_uid(orq, "otra", "Sí, exporta.")  # otra persona confirma
    assert not _es_export_json(r_b), "la confirmación de otro usuario no puede disparar el export pendiente"
    assert "luz tenue" not in r_b and "facturas" not in r_b


@pytest.mark.asyncio
async def test_exportar_aislado_por_usuario(tmp_path):
    """Seguridad: tras solicitud+confirmación, el export solo trae el modelo del `uid` que lo pide."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)  # mauricio
    await mem.write("otra", "semantica", "secreto de otra persona", {"origen": "declarada", "fuente": "usuario"})
    orq = _orq(mem)
    await _di(orq, "Exporta lo que sabes de mí.")
    r = await _di(orq, "Sí, exporta.")
    assert _es_export_json(r)
    assert "secreto de otra persona" not in r, "el export no puede filtrar el modelo de otro usuario"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confirmacion_mundana",
    [
        "Exportalo a otro formato de video, por favor.",  # ECC CRÍTICO: contiene «exportalo»
        "Dale, exporta el informe del trabajo a PDF.",  # contiene «dale, exporta»
        "Sí, hazlo con el archivo de Excel.",  # contiene «si, hazlo»
    ],
)
async def test_confirmacion_mundana_tras_un_bypass_NO_vuelca(tmp_path, confirmacion_mundana):
    """ECC CRÍTICO 2026-10-11: la confirmación NO puede reconocerse por subcadena. Un bypass dispara la
    pregunta (turno 1); en el turno 2 una frase mundana que CONTIENE un verbo de export/confirmación pero
    habla de otra cosa (un video, un PDF, un Excel) NO confirma. La confirmación exige el mensaje COMPLETO
    normalizado. Asimetría de seguridad: ante la duda, no se exporta."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)
    await _di(orq, "Dame limón. Lo que sabes de mi novio no me interesa.")  # dispara la pregunta
    r = await _di(orq, confirmacion_mundana)
    assert not _es_export_json(r) and "luz tenue" not in r, f"una frase mundana confirmó y volcó el modelo: {r!r}"
