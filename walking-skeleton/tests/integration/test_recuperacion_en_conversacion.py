"""Las TRES RUTAS, separadas y demostradas en conversación real (M8, CEO 2026-09-22).

    pregunta por un hecho personal      -> memoria personal
    pregunta por una ejecución anterior -> ventana de trabajo (DR-4)
    ninguna de las dos                  -> el camino de siempre

BEFORE, medido `[EJEC]` en 12 escenarios antes de tocar nada: en 8 de ellos la pregunta de
seguimiento —«¿cuántas entradas encontraste?»— recibía *«No tengo ningun recuerdo registrado sobre
eso»* mientras la ventana contenía el resultado entero. La memoria personal funcionaba bien; lo que
no existía era el camino hasta la ventana.

Lo que este fichero fija es sobre todo lo que **no** puede pasar: que recuperar un resultado
contamine la memoria personal, que la memoria personal conteste por un resultado, que recuperar
ejecute algo, o que una propuesta del modelo salga convertida en hecho del Core.
"""

from __future__ import annotations

import os

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.composicion import Configuracion, componer

SECRETO = "IBAN ES91-2100-0418 clave del router colibri-verde-1978"


def _aura(tmp_path):
    return componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))


async def _di(orq, texto, tid):
    await orq.handle_utterance("u", texto, tid)
    await orq.wait(tid)
    return orq._results.get(tid, {}).get("say", "")


def _memoria(tmp_path) -> str:
    ruta = os.path.join(str(tmp_path), "memoria.json")
    return open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""


# ------------------------------------------------------- RUTA 1: la ejecución se recupera --


@pytest.mark.asyncio
async def test_preguntar_por_el_resultado_anterior_lo_recupera(tmp_path):
    orq = _aura(tmp_path).orquestador
    primero = await _di(orq, f"lista el directorio {tmp_path}", "R1")

    recuperado = await _di(orq, "¿cuántas entradas encontraste?", "R2")

    assert "Ejecuté" in primero, f"la capacidad no se ejecuto: {primero!r}"
    assert "No tengo ningun recuerdo" not in recuperado, "sigue cayendo en la pared de memoria"
    assert primero in recuperado, "no recupero el resultado REAL, sino algo parecido"


@pytest.mark.asyncio
async def test_recuperar_dice_que_NO_ha_vuelto_a_ejecutar_y_ADEMAS_no_ejecuta(tmp_path):
    """Las dos mitades de la misma promesa. Si solo se comprobara la frase, un futuro cambio podría
    re-ejecutar de verdad y seguir diciendo que no: `ALERTA-005` es exactamente eso, una segunda
    ruta de ejecución que nadie vigila."""
    sis = _aura(tmp_path)
    orq = sis.orquestador
    await _di(orq, f"lista el directorio {tmp_path}", "R3")

    llamadas: list[str] = []
    ejecutar_real = sis.motor.ejecutar

    async def espia(accion, *a, **kw):
        llamadas.append(accion)
        return await ejecutar_real(accion, *a, **kw)

    sis.motor.ejecutar = espia
    recuperado = await _di(orq, "¿qué encontraste?", "R4")

    assert "no lo he vuelto a ejecutar" in recuperado.lower()
    assert llamadas == [], f"recuperar EJECUTO algo: {llamadas}"


@pytest.mark.asyncio
async def test_un_cambio_de_tema_no_impide_recuperar_lo_anterior(tmp_path):
    orq = _aura(tmp_path).orquestador
    primero = await _di(orq, f"lista el directorio {tmp_path}", "R5")
    await _di(orq, "cuéntame algo sobre los pájaros", "R6")

    recuperado = await _di(orq, "¿qué habías encontrado antes?", "R7")

    assert primero in recuperado


@pytest.mark.parametrize(
    "orden,pregunta,marca",
    [
        ("lee el archivo /etc/shadow", "¿qué decía ese archivo?", "no pude"),
        ("audita las garantias", "¿qué encontraste?", "Ejecuté"),
    ],
)
@pytest.mark.asyncio
async def test_cada_desenlace_se_recupera_CON_SU_DESENLACE(tmp_path, orden, pregunta, marca):
    """Un error no se recupera como si hubiera funcionado. El texto retenido ya lo distinguía; lo
    que se comprueba es que recuperar no lo aplana."""
    orq = _aura(tmp_path).orquestador
    await _di(orq, orden, "R8")

    recuperado = await _di(orq, pregunta, "R9")

    assert marca in recuperado


@pytest.mark.asyncio
async def test_una_orden_DETENIDA_por_el_kill_switch_se_recupera_como_detenida(tmp_path):
    sis = _aura(tmp_path)
    open(os.path.join(str(tmp_path), "KILL"), "w").close()
    orq = sis.orquestador
    await _di(orq, f"lista el directorio {tmp_path}", "R10")

    recuperado = await _di(orq, "¿qué encontraste?", "R11")

    assert "kill switch" in recuperado, "recuperar oculto que el gobierno lo impidio"
    assert "Ejecuté" not in recuperado, "recuperar convirtio un bloqueo en una ejecucion"


# ---------------------------------------------- RUTA 2: la memoria personal, intacta --


@pytest.mark.asyncio
async def test_la_memoria_personal_sigue_respondiendo_por_su_ruta(tmp_path):
    orq = _aura(tmp_path).orquestador
    await _di(orq, "me llamo Mauricio", "R12")

    assert "Mauricio" in await _di(orq, "¿cómo me llamo?", "R13")


@pytest.mark.asyncio
async def test_tras_una_ejecucion_preguntar_el_NOMBRE_no_devuelve_el_resultado(tmp_path):
    """La contaminación en un sentido. Sin la separación, «¿cuál es mi nombre?» después de listar un
    directorio podría contestarse con el listado."""
    orq = _aura(tmp_path).orquestador
    await _di(orq, f"lista el directorio {tmp_path}", "R14")

    respuesta = await _di(orq, "¿cuál es mi nombre?", "R15")

    assert "Ejecuté" not in respuesta and "entrada(s)" not in respuesta
    assert "no me has dicho" in respuesta.lower(), f"deberia ser la ausencia honesta: {respuesta!r}"


@pytest.mark.asyncio
async def test_tras_declarar_el_nombre_preguntar_por_el_RESULTADO_no_devuelve_el_nombre(tmp_path):
    """La contaminación en el sentido contrario."""
    orq = _aura(tmp_path).orquestador
    await _di(orq, "me llamo Mauricio", "R16")
    listado = await _di(orq, f"lista el directorio {tmp_path}", "R17")

    recuperado = await _di(orq, "¿qué encontraste?", "R18")

    assert listado in recuperado
    assert "Mauricio" not in recuperado


@pytest.mark.asyncio
async def test_recuperar_NO_escribe_nada_en_la_memoria_personal(tmp_path):
    orq = _aura(tmp_path).orquestador
    await _di(orq, "me llamo Mauricio", "R19")
    await _di(orq, f"lista el directorio {tmp_path}", "R20")
    antes = _memoria(tmp_path)

    await _di(orq, "¿qué encontraste?", "R21")

    assert "me llamo Mauricio" in antes, "control: la memoria personal no se escribio"
    assert _memoria(tmp_path) == antes, "recuperar modifico la memoria personal"


# --------------------------------------- RUTA 3: lo que no es ninguna de las dos --


@pytest.mark.asyncio
async def test_un_atributo_personal_nunca_declarado_SIGUE_recibiendo_la_pared(tmp_path):
    """La garantía de `ADR-0014` que no puede moverse, comprobada de extremo a extremo y no solo
    sobre el reconocedor."""
    orq = _aura(tmp_path).orquestador

    respuesta = await _di(orq, "¿Cuál es el nombre de mi abuela?", "R22")

    assert "No tengo ningun recuerdo registrado sobre eso" in respuesta


@pytest.mark.asyncio
async def test_sin_ninguna_ejecucion_la_ausencia_es_PRECISA_y_no_la_de_la_pared(tmp_path):
    orq = _aura(tmp_path).orquestador
    await _di(orq, "hola", "R23")

    respuesta = await _di(orq, "¿qué encontraste?", "R24")

    assert "No tengo ningun recuerdo registrado sobre eso" not in respuesta
    # PUNTO D, decision L: la ausencia ya no dice «no he ejecutado nada» (la ventana muere con el proceso y el
    # registro persistido puede no cubrir una accion): «No conservo registro…; podria haber alguna».
    assert "no conservo registro de acciones anteriores" in respuesta.lower()
    assert "podría haber alguna" in respuesta and "nunca" not in respuesta.lower()
    assert "no he ejecutado nada" not in respuesta.lower()


@pytest.mark.asyncio
async def test_recuperar_deja_rastro_forense(tmp_path):
    orq = _aura(tmp_path).orquestador
    await _di(orq, f"lista el directorio {tmp_path}", "R25")
    marca = len(obs.audit_records())

    await _di(orq, "¿qué encontraste?", "R26")

    nuevos = [r for r in obs.audit_records()[marca:] if r.get("module") == "recuperacion"]
    assert nuevos, "recuperar no dejo rastro"
    assert "sin LLM" in nuevos[0]["msg"]


@pytest.mark.asyncio
async def test_el_CONTENIDO_de_un_fichero_se_repite_al_recuperar(tmp_path):
    """**Decisión 1 del punto D (CEO Operativo, 2026-11-06).** Recuperar repite lo que AURA ya había dicho al
    MISMO usuario en la MISMA conversación, así que no es una divulgación nueva: el contenido SÍ se repite a
    petición. Lo que cambió es que ya NO reentra solo en el prompt de turnos ajenos (ver
    `test_frontera_continuidad.py`) ni se persiste (`test_continuidad_resultados.py`). Esta prueba fija la mitad
    que se mantuvo a propósito."""
    secreto = tmp_path / "privado.txt"
    secreto.write_text(SECRETO, encoding="utf-8")
    orq = _aura(tmp_path).orquestador
    await _di(orq, f"lee el archivo {secreto}", "R27")

    recuperado = await _di(orq, "¿y qué ponía?", "R28")

    assert "colibri-verde-1978" in recuperado
    assert "colibri-verde-1978" not in _memoria(tmp_path), (
        "ademas se filtro a la memoria personal: eso si seria una frontera rota"
    )
