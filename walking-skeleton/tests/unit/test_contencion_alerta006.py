"""Unit: contencion de ALERTA-006 — la soberania no puede destruir en silencio.

ALERTA-006 (2026-08-03) demostro que la cascada de soberania del modelo del usuario destruye datos
sin pasar por el Motor Unico, sin permisos y sin kill switch. La correccion estructural vive en
D-M-8 (Motor Unico de Mutaciones). Estas pruebas cubren SOLO la fase de contencion que el CEO
autorizo adelantar, porque el defecto esta vivo:

  1. Guarda de dominio en el disparador de olvido: "se me olvida tomar la pastilla" NO es una orden
     de olvidar. Hoy destruia un dato clinico declarado.
  2. Ante un referente AMBIGUO no se actua: se pide desambiguacion. Hoy se elegia `vivas[0]`, que no
     tiene por que guardar ninguna relacion con lo pedido.
  3. `refutar` solo confirma exito cuando hubo mutacion efectiva (INV-9 / ALERTA-005 punto 4). Hoy
     responde "Entendido, lo corrijo" aunque no haya refutado nada.

Lo que estas pruebas NO cubren, para que nadie lea de mas en un verde: la mutacion sigue SIN pasar
por el Motor Unico, y el kill switch armado sigue sin detenerla. Eso es D-M-8 y sigue abierto.
"""

import os

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


async def _sembrar(mem):
    await mem.write("u", "semantica", "tiene alergia a la penicilina", {"origen": "declarada"})
    await mem.write("u", "semantica", "suele pagar las facturas por la app", {"origen": "observada"})


async def _contenidos(mem):
    return [e["contenido"] for e in await ModeloUsuario(mem).ver("u")]


@pytest.mark.asyncio
async def test_una_frase_reflexiva_no_destruye_nada(tmp_path):
    """GUARDA DE DOMINIO: "se me olvida X" describe un olvido PROPIO, no ordena a AURA olvidar.

    Caso real de ALERTA-006: esta frase mundana sobre medicacion destruyo "tiene alergia a la
    penicilina" —un dato clinico declarado— y dejo el fichero en 0 lineas.
    """
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    resp = await orq._atender_modelo_usuario("u", "Se me olvida siempre tomar la pastilla.")

    assert resp is None, f"una frase reflexiva no debe entrar en la rama de soberania (respondio {resp!r})"
    assert "tiene alergia a la penicilina" in await _contenidos(mem), "destruyo un dato clinico declarado"


@pytest.mark.asyncio
async def test_olvido_con_referente_ambiguo_pide_desambiguacion_y_no_borra(tmp_path):
    """ANTE LA DUDA NO SE DESTRUYE. El texto no menciona ninguna entrada viva: no hay a que referirse.

    Antes se elegia `vivas[0]` —la primera entrada, sin relacion con lo pedido— y se confirmaba el
    borrado. "Ante la duda, roja" (ADR-0003) aplicado a la soberania: ante la duda, se pregunta.
    """
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    resp = await orq._atender_modelo_usuario("u", "Olvida que a mi hermana le gusta el cafe verde")

    assert resp is not None, "la peticion de olvido si entra en la rama; lo que no puede es destruir a ciegas"
    assert "?" in resp, f"debe pedir desambiguacion, no confirmar un borrado: {resp!r}"
    assert len(await _contenidos(mem)) == 2, "no puede borrarse nada cuando el referente es ambiguo"


@pytest.mark.asyncio
async def test_refutacion_ambigua_no_marca_nada(tmp_path):
    """Mismo `_foco`, mismo riesgo: "eso ya no es cierto" sin referente no puede refutar al azar."""
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    resp = await orq._atender_modelo_usuario("u", "Eso ya no es cierto.")

    assert "?" in (resp or ""), f"debe preguntar a que se refiere: {resp!r}"
    entradas = await ModeloUsuario(mem).ver("u")
    assert not any(e.get("refutada") for e in entradas), "no puede refutarse una entrada elegida al azar"


@pytest.mark.asyncio
async def test_no_se_narra_exito_si_no_hubo_refutacion(tmp_path):
    """INV-9 / ALERTA-005 punto 4: no se informa exito sin efecto real.

    Con el foco apuntando a una entrada YA refutada, `refutar` devuelve 0. El codigo descartaba ese
    retorno y respondia "Entendido, lo corrijo" igualmente. `borrar` si lo comprobaba: la asimetria
    estaba en el codigo, no en la lectura.
    """
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    # Refutacion legitima: el texto menciona "facturas", que identifica una entrada viva.
    primera = await orq._atender_modelo_usuario("u", "Lo de las facturas ya no es cierto.")
    assert "corrijo" in (primera or "").lower(), f"la refutacion identificada SI debe surtir efecto: {primera!r}"

    # Repetirla: la entrada ya esta refutada, luego no queda nada que refutar.
    segunda = await orq._atender_modelo_usuario("u", "Lo de las facturas ya no es cierto.")
    assert "corrijo" not in (segunda or "").lower(), (
        f"no puede narrarse exito cuando no hubo mutacion efectiva: {segunda!r}"
    )


@pytest.mark.asyncio
async def test_control_el_olvido_identificado_sigue_funcionando(tmp_path):
    """CONTROL NEGATIVO: la contencion no puede romper la capacidad aprobada.

    Sin este control, las tres pruebas anteriores pasarian con un sistema que simplemente no borra
    nunca —que es justo lo que NO queremos—.
    """
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    resp = await orq._atender_modelo_usuario("u", "Olvida lo de las facturas.")

    assert "hecho" in (resp or "").lower(), f"un olvido IDENTIFICADO debe seguir ejecutandose: {resp!r}"
    contenidos = await _contenidos(mem)
    assert not any("facturas" in c for c in contenidos), "el olvido identificado debe surtir efecto"
    assert any("penicilina" in c for c in contenidos), "y no puede arrastrar lo que no se pidio"


@pytest.mark.asyncio
async def test_el_foco_no_sobrevive_a_la_entrada_que_señalaba(tmp_path):
    """El foco cacheado se valida: no puede seguir apuntando a algo que ya no esta en el modelo.

    Sin esta validacion el sistema arrastra una referencia huerfana. La consecuencia observable es
    que un "olvida eso" posterior responde "no he encontrado eso" —hablando de un fantasma— en vez
    de reconocer que no hay referente y pedir desambiguacion, que es lo que deja al usuario en
    condiciones de continuar.
    """
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    # Fija el foco por coincidencia lexica Y borra esa misma entrada.
    await orq._atender_modelo_usuario("u", "Olvida lo de las facturas.")
    assert not any("facturas" in c for c in await _contenidos(mem)), "precondicion: la entrada quedo borrada"

    # El foco cacheado apunta ahora a una entrada que ya no existe.
    resp = await orq._atender_modelo_usuario("u", "Olvida eso.")

    assert resp == "¿A qué te refieres? Puedes decirme «¿qué sabes de mí?» y lo revisamos.", (
        f"un foco huerfano debe resolverse como ambiguo, no como 'no encontrado': {resp!r}"
    )
    assert any("penicilina" in c for c in await _contenidos(mem)), "y no puede arrastrar la entrada restante"


@pytest.mark.asyncio
async def test_control_el_foco_de_una_conversacion_sigue_resolviendo_eso(tmp_path):
    """CONTROL: "¿que sabes de mi?" fija el foco; el "eso" siguiente debe seguir resolviendose.

    La contencion elimina el fallback ciego a `vivas[0]`, NO la memoria conversacional del foco.
    """
    mem = PersistentMemory(os.path.join(tmp_path, "m.jsonl"))
    await _sembrar(mem)
    orq = _orq(mem)

    await orq._atender_modelo_usuario("u", "Que sabes de mi?")
    resp = await orq._atender_modelo_usuario("u", "Olvida eso.")

    assert "hecho" in (resp or "").lower(), f"el foco de la conversacion debe seguir resolviendo 'eso': {resp!r}"
    assert len(await _contenidos(mem)) == 1, "debe haber borrado exactamente la entrada en foco"
