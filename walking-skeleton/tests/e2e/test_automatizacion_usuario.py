"""Criterio de aceptación del MVP capacidad 5 — automatización definida por el usuario (Bible 6.4).

El CEO fijó el criterio como una CONVERSACIÓN, no como una API:

    Usuario: "Siempre que borres un archivo, guarda antes una copia."
    AURA:    "Entendido. Lo haré a partir de ahora."
    Usuario: "Borra informe.pdf"
    AURA:    "Guardé una copia de informe.pdf y luego lo borré."
    --- reinicio de AURA ---
    Usuario: "Borra notas.txt"
    AURA:    "Guardé una copia de notas.txt y luego lo borré."

El reinicio es REAL: la segunda mitad de la prueba construye un sistema completamente nuevo
(orquestador, memoria, motor y almacén nuevos) que solo comparte con el primero el DISCO. Si la regla
viviera en memoria de proceso —o en el buffer de conversación, o en el prompt del LLM— la segunda
mitad fallaría.

El proveedor de modelo es un guion determinista que solo sabe traducir "borra X" a `borrar_archivo`:
NO sabe nada de reglas ni de copias. Así, todo lo que ocurra con la automatización es obra del núcleo
(ADR-0014), no del LLM.
"""

import json
import os
import uuid

import pytest

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.core.reglas import AlmacenReglas
from aura_skeleton.modules.memory import SimpleMemory
from aura_skeleton.modules.router import ModelRouter

USUARIO = "mauricio"


class _GuionBorrado:
    """Doble del proveedor: traduce "borra <archivo>" a `borrar_archivo`. No conoce las reglas."""

    name = "guion"
    healthy = True

    def __init__(self, base: str) -> None:
        self._base = base

    async def infer(self, prompt: str) -> str:
        nombre = prompt.split("Usuario:")[-1].strip().split()[-1]
        decision = {
            "intent": "borrar",
            "action": "borrar_archivo",
            "args": {"ruta": os.path.join(self._base, nombre)},
            "say": "Borro el archivo.",
        }
        return json.dumps(decision)


class _GuionArchivos:
    """Doble del proveedor: traduce "borra <archivo>" y "escribe '<contenido>' en <archivo>".

    Necesario para probar de extremo a extremo la automatizacion "copia antes de escribir", que
    _GuionBorrado no sabe emitir. Como el, no conoce las reglas del usuario; una frase que no
    reconoce como orden explicita se traduce en "consulta" (sin efectos), igual que haria un LLM
    real ante una peticion de fuera de su catalogo.
    """

    name = "guion"
    healthy = True

    def __init__(self, base: str) -> None:
        self._base = base

    async def infer(self, prompt: str) -> str:
        orden = prompt.split("Usuario:")[-1].strip()
        u = orden.lower()
        if u.startswith("escribe"):
            contenido = orden.split("'")[1]
            nombre = orden.rstrip(".").split()[-1]
            decision = {
                "intent": "escribir",
                "action": "escribir_archivo",
                "args": {"ruta": os.path.join(self._base, nombre), "contenido": contenido},
                "say": "Escribo el archivo.",
            }
        elif "borra" in u or "elimina" in u:
            nombre = orden.split()[-1]
            decision = {
                "intent": "borrar",
                "action": "borrar_archivo",
                "args": {"ruta": os.path.join(self._base, nombre)},
                "say": "Borro el archivo.",
            }
        else:
            decision = {"intent": "charla", "action": "consulta", "args": {}, "say": "Entendido."}
        return json.dumps(decision)


class _GuionMover:
    """Doble del proveedor que emite `mover_archivo`, cuya clave de evento es `origen` (no `ruta`)."""

    name = "guion"
    healthy = True

    def __init__(self, base: str) -> None:
        self._base = base

    async def infer(self, prompt: str) -> str:
        nombre = prompt.split("Usuario:")[-1].strip().rstrip(".").split()[-1]
        return json.dumps(
            {
                "intent": "mover",
                "action": "mover_archivo",
                "args": {
                    "origen": os.path.join(self._base, nombre),
                    "destino": os.path.join(self._base, "movido-" + nombre),
                },
                "say": "Muevo el archivo.",
            }
        )


async def _aprobar(accion, args, trace_id):
    """El usuario confirma el borrado (lista roja). La copia es verde: no pasa por aquí."""
    return True


def _arrancar_aura(archivos, estado, proveedor=None):
    """Arranque completo de AURA. Todo es nuevo salvo el disco: esto ES el reinicio."""
    registro = RegistroAdaptadores([AdaptadorComputador(raices=(str(archivos),))])
    permisos = PermissionManager(_aprobar)
    motor = MotorAutomatizacion(registro, permisos)
    if proveedor is None:
        proveedor = _GuionBorrado(str(archivos))
    return Orchestrator(
        InProcessEventBus(),
        SimpleMemory(),
        ModelRouter([proveedor], 1200),
        permisos,
        VoiceAdapterMock(),
        registro,
        motor=motor,
        automatizaciones=AlmacenReglas(str(estado / "reglas.jsonl")),
    )


async def _decir(orq, texto):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(USUARIO, texto, tid)
    return (await orq.wait(tid))["say"]


@pytest.fixture
def entorno(tmp_path):
    archivos = tmp_path / "archivos"
    archivos.mkdir()
    (archivos / "informe.pdf").write_text("informe de julio")
    (archivos / "notas.txt").write_text("notas sueltas")
    estado = tmp_path / "estado"
    return archivos, estado


@pytest.mark.asyncio
async def test_la_automatizacion_del_usuario_sobrevive_al_reinicio(entorno):
    """La conversación completa del criterio de aceptación, incluido el reinicio."""
    archivos, estado = entorno

    aura = _arrancar_aura(archivos, estado)
    assert await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.") == (
        "Entendido. Lo haré a partir de ahora."
    )

    say = await _decir(aura, "Borra informe.pdf")
    assert "Guardé una copia de informe.pdf y luego lo borré." in say
    assert not (archivos / "informe.pdf").exists(), "la acción del usuario debe haberse ejecutado"
    assert (archivos / "informe.pdf.copia").read_text() == "informe de julio", "la copia debe existir en disco"

    # --- reinicio de AURA: proceso nuevo, memoria nueva, conversación nueva; solo persiste el disco ---
    aura = _arrancar_aura(archivos, estado)

    say = await _decir(aura, "Borra notas.txt")
    assert "Guardé una copia de notas.txt y luego lo borré." in say
    assert not (archivos / "notas.txt").exists()
    assert (archivos / "notas.txt.copia").read_text() == "notas sueltas", "la regla siguió activa tras reiniciar"


@pytest.mark.asyncio
async def test_sin_regla_no_hay_copia(entorno):
    """CONTROL imprescindible: sin la automatización, borrar NO deja copia.

    Sin este control, la prueba anterior pasaría igual si el sistema copiara SIEMPRE, y no
    demostraría nada sobre la regla del usuario.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    say = await _decir(aura, "Borra informe.pdf")

    assert not (archivos / "informe.pdf").exists()
    assert not (archivos / "informe.pdf.copia").exists(), "copió sin que el usuario lo pidiera"
    assert "copia" not in say.lower(), "narró una copia que no hizo"


@pytest.mark.asyncio
async def test_el_usuario_puede_inspeccionar_sus_automatizaciones(entorno):
    """ "¿Qué automatizaciones tengo?" debe ser fiel al estado interno, antes y después de crear una."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    assert await _decir(aura, "¿Qué automatizaciones tengo?") == "No tienes ninguna automatización activa."

    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")

    # Tras reiniciar: lo que se inspecciona sale del disco, no de la conversación anterior.
    aura = _arrancar_aura(archivos, estado)
    say = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "1 automatización activa" in say
    assert "copia" in say.lower() and "borrar" in say.lower()


# --- M3 entry: varias automatizaciones distintas, cada una con su propio disparador -----------------
#
# El MVP anterior solo reconocia "copia antes de borrar". Ahora el reconocedor debe extraer QUE accion
# del usuario dispara la regla (borrar/escribir/mover/renombrar), y cada una se persiste por separado
# (INV-9: solo estas cuatro, solo copiar_archivo como accion de la regla; nada de LLM en la deteccion).


@pytest.mark.asyncio
async def test_el_usuario_puede_crear_varias_automatizaciones_distintas(entorno):
    """Dos automatizaciones distintas coexisten y se listan cada una con su propia descripción."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    assert await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.") == (
        "Entendido. Lo haré a partir de ahora."
    )
    assert await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.") == (
        "Entendido. Lo haré a partir de ahora."
    )

    say = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "2 automatizaciones activas" in say
    assert "borrar" in say.lower()
    assert "escribir" in say.lower()


@pytest.mark.asyncio
async def test_la_automatizacion_de_escribir_funciona_de_extremo_a_extremo(entorno):
    """La automatización "copia antes de escribir" se ejecuta de verdad, no solo se declara."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    say = await _decir(aura, "Escribe 'version nueva' en notas.txt")

    assert "Guardé una copia de notas.txt y luego lo escribí." in say
    assert (archivos / "notas.txt.copia").read_text() == "notas sueltas", "debe copiar el contenido ANTERIOR"
    assert (archivos / "notas.txt").read_text() == "version nueva", "la escritura del usuario debe haberse ejecutado"


@pytest.mark.asyncio
async def test_frase_no_reconocida_no_crea_ninguna_regla(entorno):
    """CONTROL: una frase que no encaja en ningún disparador/acción conocido no crea regla alguna."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    await _decir(aura, "Cuando llueva, avísame.")

    say = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert say == "No tienes ninguna automatización activa."


@pytest.mark.asyncio
async def test_las_dos_automatizaciones_sobreviven_al_reinicio_y_ambas_disparan(entorno):
    """Tras reiniciar, las DOS reglas siguen activas y ambas siguen disparando (no solo persistidas)."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    # --- reinicio de AURA: proceso nuevo, memoria nueva; solo persiste el disco ---
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    say_listar = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "2 automatizaciones activas" in say_listar

    say_borrar = await _decir(aura, "Borra informe.pdf")
    assert "Guardé una copia de informe.pdf y luego lo borré." in say_borrar
    assert (archivos / "informe.pdf.copia").exists()

    say_escribir = await _decir(aura, "Escribe 'version 2' en notas.txt")
    assert "Guardé una copia de notas.txt y luego lo escribí." in say_escribir
    assert (archivos / "notas.txt.copia").read_text() == "notas sueltas"
    assert (archivos / "notas.txt").read_text() == "version 2"


@pytest.mark.asyncio
async def test_respaldar_un_archivo_nuevo_no_se_narra_como_fallo(entorno):
    """Crear un archivo que no existía NO es un fallo del respaldo: no hay nada que respaldar.

    La automatización "guarda una copia al escribir" sirve para conservar el contenido ANTERIOR
    antes de sobrescribirlo. Cuando el archivo es nuevo, la copia previa falla necesariamente —y
    ese es el caso más común—. Narrarlo como error convertiría la automatización en una molestia
    constante y haría que AURA reportase como problema algo perfectamente normal.

    Se sigue narrando cualquier otro fallo: el silencio es SOLO para "no había nada que copiar".
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    say = await _decir(aura, "Escribe 'contenido nuevo' en nuevo.txt")

    assert (archivos / "nuevo.txt").exists(), "el archivo debe crearse igualmente"
    assert "no pude copiar" not in say.lower(), f"avisó de un fallo que no lo es: {say!r}"
    assert "encontr" not in say.lower(), f"expuso el error interno al usuario: {say!r}"


@pytest.mark.asyncio
async def test_al_sobrescribir_si_se_guarda_la_copia(entorno):
    """CONTROL del anterior: cuando el archivo YA existe, la copia sí ocurre y sí se narra.

    Sin este control, silenciar el aviso podría estar ocultando que la automatización no funciona.
    """
    archivos, estado = entorno
    (archivos / "existe.txt").write_text("contenido anterior")
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    say = await _decir(aura, "Escribe 'contenido nuevo' en existe.txt")

    assert (archivos / "existe.txt.copia").read_text() == "contenido anterior", "no respaldó lo previo"
    assert "copia" in say.lower(), f"hizo la copia pero no lo contó: {say!r}"


@pytest.mark.asyncio
async def test_no_duplica_una_automatizacion_creada_por_una_version_anterior(entorno):
    """Una regla guardada con el identificador ANTIGUO no debe duplicarse al repetir la frase.

    Al ampliar el reconocedor, el `rule_id` de "copia antes de borrar" pasó de `copia-antes-de-borrar`
    a `copia-al-borrar`. Sin reconocer el identificador histórico, un usuario que ya tuviera esa
    automatización acabaría con DOS reglas activas haciendo lo mismo: la segunda copia fallaría por
    destino existente y AURA narraría un aviso de error en cada borrado.
    """
    archivos, estado = entorno
    estado.mkdir(parents=True, exist_ok=True)
    (estado / "reglas.jsonl").write_text(
        json.dumps(
            {
                "rule_id": "copia-antes-de-borrar",
                "user_id": USUARIO,
                "evento": "action.command",
                "condicion": {"campo": "action", "op": "==", "valor": "borrar_archivo"},
                "accion": "copiar_archivo",
                "args": {"ruta": "$evento.ruta"},
                "estado": "activa",
                "metadatos": {"descripcion": "Guardar una copia antes de borrar un archivo"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    aura = _arrancar_aura(archivos, estado)

    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")

    say = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "1 automatización activa" in say, f"se duplicó la automatización existente: {say!r}"


@pytest.mark.asyncio
async def test_un_disparador_desconocido_no_crea_regla_aunque_hable_de_copias(entorno):
    """La frase tiene disparador Y menciona copias, pero la acción NO existe: no se finge capacidad.

    El control anterior ("cuando llueva, avísame") no basta: no menciona copias, así que el
    reconocedor lo descarta por otro motivo. Esta frase aísla la condición que importa (INV-9).
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    say = await _decir(aura, "Siempre que llueva, guarda una copia.")

    assert "lo haré a partir de ahora" not in say.lower(), f"prometió una automatización imposible: {say!r}"
    assert "No tienes ninguna automatización activa." == await _decir(aura, "¿Qué automatizaciones tengo?")


@pytest.mark.asyncio
async def test_la_automatizacion_de_mover_respalda_el_archivo_de_origen(entorno):
    """`mover_archivo` publica el archivo en `origen`, no en `ruta`: la regla debe leer la clave correcta.

    Si leyera `ruta`, `resolver_args` devolvería None y la copia se haría sobre la nada — el respaldo
    no existiría y el usuario perdería el contenido al mover sobre un destino equivocado.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionMover(str(archivos)))

    await _decir(aura, "Cada vez que muevas un archivo, guarda una copia.")
    await _decir(aura, "Mueve informe.pdf")

    assert (archivos / "informe.pdf.copia").read_text() == "informe de julio", "no respaldó el origen"


@pytest.mark.asyncio
async def test_un_fallo_real_del_respaldo_si_se_comunica(entorno):
    """CONTROL del silencio: solo se calla "no había nada que respaldar", nunca un fallo real.

    Con la copia ya existente, el respaldo falla por destino ocupado. Ese fallo SÍ debe llegar al
    usuario: silenciarlo ocultaría que su automatización dejó de protegerle.
    """
    archivos, estado = entorno
    (archivos / "informe.pdf.copia").write_text("una copia previa")
    aura = _arrancar_aura(archivos, estado)

    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")
    say = await _decir(aura, "Borra informe.pdf")

    assert "no pude copiar" in say.lower(), f"silenció un fallo real del respaldo: {say!r}"


@pytest.mark.asyncio
async def test_la_ultima_defensa_no_inventa_una_automatizacion(entorno):
    """Prueba DIRECTA de la guarda de `_crear_regla`: sin acción reconocida, no se inventa ninguna.

    Es código defensivo deliberadamente inalcanzable desde la conversación —`_es_creacion_de_regla`
    filtra antes—, así que ninguna prueba de caja negra puede ejercerlo. Pero es la última línea que
    impide fingir una capacidad (INV-9) si algún día ese filtro se relaja, y una defensa que nadie
    verifica es una defensa que nadie sabe si sigue viva.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    respuesta = aura._crear_regla(USUARIO, "siempre que llueva, guarda una copia")

    assert "lo haré a partir de ahora" not in respuesta.lower(), "inventó una automatización"
    assert aura.automatizaciones.listar(USUARIO) == [], "persistió una regla sin disparador reconocido"


@pytest.mark.asyncio
async def test_una_negacion_no_crea_la_automatizacion_que_el_usuario_rechaza(entorno):
    """Pedir que AURA *deje* de hacer algo no puede crear la automatización: es lo contrario.

    Detectado por auditoría independiente (2026-08-02): «No quiero que cuando borres un archivo
    guardes una copia» creaba la regla, y «Deja de guardar copia cuando borres» respondía
    «Entendido. Lo haré a partir de ahora». AURA hacía exactamente lo opuesto a lo solicitado.

    Ninguna de las frases identifica una automatización EXISTENTE que desactivar (el usuario no
    tiene ninguna todavía), así que la respuesta correcta es la verdad: no tiene ninguna activa.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado)

    for frase in (
        "No quiero que cuando borres un archivo guardes una copia.",
        "Deja de guardar una copia cuando borres un archivo.",
        "Ya no guardes copia cada vez que escriba un archivo.",
    ):
        say = await _decir(aura, frase)
        assert "lo haré a partir de ahora" not in say.lower(), f"{frase!r} -> creó lo que se rechazaba: {say!r}"

    assert await _decir(aura, "¿Qué automatizaciones tengo?") == "No tienes ninguna automatización activa."


# --- M3 entry: desactivar una automatizacion hablando -------------------------------------------------
#
# Hasta ahora rechazar una automatizacion solo evitaba crear la que no se queria (test anterior). Ahora
# el usuario puede desactivar de verdad una automatizacion YA CREADA: no basta con que desaparezca del
# listado, tiene que dejar de dispararse, y la desactivacion debe sobrevivir al reinicio igual que la
# creacion (mismo almacen, mismo disco).


@pytest.mark.asyncio
async def test_el_usuario_puede_desactivar_una_automatizacion_hablando(entorno):
    """Ciclo completo: crear dos automatizaciones, desactivar una hablando, listar solo la otra."""
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    say = await _decir(aura, "Ya no quiero que guardes copia cuando escriba un archivo.")
    assert say == "Hecho. He desactivado esa automatización."

    say_listar = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "1 automatización activa" in say_listar
    assert "borrar" in say_listar.lower()
    assert "escrib" not in say_listar.lower(), f"la desactivada seguia en el listado: {say_listar!r}"


@pytest.mark.asyncio
async def test_la_automatizacion_desactivada_deja_de_dispararse_de_verdad(entorno):
    """Lo que de verdad importa: tras desactivar, escribir un archivo YA NO genera copia.

    No basta con que la regla desaparezca del listado (eso lo verifica la prueba anterior): si
    siguiera disparandose, la desactivacion seria solo cosmetica.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    await _decir(aura, "Ya no quiero que guardes copia cuando escriba un archivo.")
    say = await _decir(aura, "Escribe 'version nueva' en notas.txt")

    assert (archivos / "notas.txt").read_text() == "version nueva", "la escritura del usuario debe ejecutarse"
    assert not (archivos / "notas.txt.copia").exists(), "la automatizacion desactivada siguio disparando"
    assert "copia" not in say.lower(), f"narro una copia que ya no debia hacer: {say!r}"


@pytest.mark.asyncio
async def test_la_desactivacion_sobrevive_al_reinicio(entorno):
    """Tras reiniciar AURA, la desactivada sigue desactivada y la otra sigue funcionando.

    Mismo criterio que la creacion (ver test de arriba): si la desactivacion viviera solo en
    memoria de proceso, un reinicio la resucitaria sin que el usuario lo pidiera.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")
    await _decir(aura, "Ya no quiero que guardes copia cuando escriba un archivo.")

    # --- reinicio de AURA: proceso nuevo; solo persiste el disco ---
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    say_listar = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "1 automatización activa" in say_listar
    assert "borrar" in say_listar.lower()

    await _decir(aura, "Escribe 'version 2' en notas.txt")
    assert not (archivos / "notas.txt.copia").exists(), "la desactivada volvio a activarse tras reiniciar"

    say_borrar = await _decir(aura, "Borra informe.pdf")
    assert "Guardé una copia de informe.pdf y luego lo borré." in say_borrar
    assert (archivos / "informe.pdf.copia").read_text() == "informe de julio", "la activa siguio funcionando"


@pytest.mark.asyncio
async def test_eliminar_automatizacion_de_escribir_no_desactiva_la_de_borrar(entorno):
    """Auditoria independiente (2026-08-02): "elimin" es sinonimo de "borrar" en
    _PATRONES_ACCION_DISPARADORA, y tambien es el verbo de esta misma frase de cancelacion.
    _detectar_accion_disparadora devolvia la PRIMERA fila que coincidia en la tabla (borrar va
    antes que escribir), asi que "Elimina la automatización de escribir archivos." desactivaba
    la automatizacion de BORRAR -la equivocada- y encima respondia "Hecho." sobre ella.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")
    await _decir(aura, "Cada vez que escriba un archivo, guarda una copia.")

    say = await _decir(aura, "Elimina la automatización de escribir archivos.")
    assert say == "Hecho. He desactivado esa automatización."

    say_listar = await _decir(aura, "¿Qué automatizaciones tengo?")
    assert "1 automatización activa" in say_listar
    assert "borrar" in say_listar.lower(), f"desactivo la automatizacion equivocada: {say_listar!r}"
    assert "escrib" not in say_listar.lower(), f"la de escribir seguia activa: {say_listar!r}"


@pytest.mark.asyncio
async def test_frases_mundanas_con_marcador_de_cancelacion_no_secuestran_el_turno(entorno):
    """Auditoria independiente (2026-08-02): un marcador de cancelacion aislado ("ya no ", "no
    quiero", "deja de") bastaba para entrar en la rama de cancelacion de automatizaciones, aunque
    la frase no tuviera nada que ver con ellas. "Ya no tengo hambre, gracias." respondia "No tienes
    ninguna automatización activa.", secuestrando un turno que debia resolver el proveedor.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    for frase in (
        "Ya no tengo hambre, gracias.",
        "No quiero salir hoy.",
        "Deja de llover.",
    ):
        say = await _decir(aura, frase)
        assert say == "Entendido.", f"{frase!r} fue secuestrada por el nucleo de automatizaciones: {say!r}"


@pytest.mark.asyncio
async def test_cancelacion_real_sigue_funcionando_sin_automatizaciones_activas(entorno):
    """CONTROL del anterior: exigir mencion de dominio no debe romper la cancelacion real cuando el
    usuario no tiene ninguna automatizacion activa (debe seguir diciendo la verdad, no "hecho").
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))

    say = await _decir(aura, "Ya no quiero que guardes copia cuando escriba un archivo.")

    assert "hecho" not in say.lower()
    assert say == "No tienes ninguna automatización activa."


@pytest.mark.asyncio
async def test_desactivar_una_automatizacion_inexistente_no_miente(entorno):
    """Pedir desactivar una automatización que no tiene NO responde "hecho": dice la verdad.

    El usuario solo tiene la de "borrar"; pide desactivar la de "escribir", que no existe. AURA
    nunca debe afirmar un exito que no ocurrio (INV-9): debe ayudar contando lo que si tiene.
    """
    archivos, estado = entorno
    aura = _arrancar_aura(archivos, estado, proveedor=_GuionArchivos(str(archivos)))
    await _decir(aura, "Siempre que borres un archivo, guarda antes una copia.")

    say = await _decir(aura, "Ya no quiero que guardes copia cuando escriba un archivo.")

    assert "hecho" not in say.lower(), f"afirmo haber desactivado algo que no existia: {say!r}"
    assert "1 automatización activa" in say
    assert "borrar" in say.lower()
