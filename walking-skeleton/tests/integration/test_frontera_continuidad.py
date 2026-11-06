"""La FRONTERA de la continuidad entre turnos, fijada como garantía (M7, CEO 2026-09-21).

**Este fichero no decide ninguna política. Fija la que ya rige, para que no cambie por descuido.**

Qué se descubrió midiendo `[EJEC]` el 2026-09-21, y por qué hacía falta escribirlo:

La misión anterior concluyó que AURA «no conserva resultados entre turnos». Medido de nuevo dentro de
**un mismo proceso** —la anterior arrancaba uno por turno— resulta que **sí los conserva**: la ventana
de trabajo `Orchestrator._dialogue` guarda literalmente

    [hecho] 'Ejecuté «listar_directorio». 7 entrada(s): CENTRO-DE-GOBIERNO.md, audit.jsonl, ...'

y esa ventana está gobernada por `DR-4` (CEO, 2026-09-15): `_DIALOG_N = 6`, `_DIALOG_MAX = 9`,
`_RECORTE_AURA = 160`. Es decir: **la retención de resultados en memoria de trabajo ya está aprobada
y ya funciona.** Lo que no está decidido es otra cosa, y conviene no confundirlas:

  1. si una pregunta posterior debe RESPONDERSE desde esa ventana (hoy la intercepta antes la
     superficie determinista de memoria y contesta la ausencia de `ADR-0014`);
  2. qué pasa con el contenido sensible: `leer_archivo` devuelve ficheros del usuario, y `DR-4` se
     decidió por latencia y caché, sin que nadie examinara la privacidad de lo que la ventana retiene.

Las tres fronteras que este fichero clava son las que hacen que (2) sea hoy **acotado**: el resultado
vive en RAM y **no se filtra** ni a la memoria persistente ni al registro forense. Si un incremento
futuro rompe cualquiera de las tres, la decisión pendiente se habrá tomado sola y por accidente —que
es exactamente como este proyecto ha perdido garantías otras ocho veces.

**PUNTO D (CEO Operativo, 2026-11-06) — la decisión pendiente se tomó, a propósito.** Tres de estas pruebas
cambian por esa decisión y no por accidente (`DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md` §7.7-7):

  * «la ventana no tiene respaldo en disco» y «el resultado no entra en la memoria persistente» pasan a ser
    «en disco solo hay registros `resultado_accion` de esquema cerrado»: el texto de la respuesta (el `say`)
    sigue sin llegar a disco, pero SÍ persiste un registro de metadatos (`core/resultado_accion.py`).
  * «el contenido del fichero reentra en el prompt del turno siguiente» pasa a su contrario: ya no reentra
    (decisión 1); solo el metadato («leí un archivo, N líneas»).

Las demás fronteras (audit sin payload, nadie lee el audit para conversar, proveedor local, rastro) no cambian.
"""

from __future__ import annotations

import json
import os

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core import resultado_accion as ra

CONTENIDO_SENSIBLE = "IBAN ES91-2100-0418-4502 y la clave del router es colibri-verde-1978"


def _sistema(tmp_path):
    return componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),)))


async def _turno(orq, texto, tid):
    await orq.handle_utterance("u", texto, tid)
    await orq.wait(tid)
    return orq._results.get(tid, {}).get("say", "")


def _memoria_en_disco(tmp_path) -> str:
    ruta = os.path.join(str(tmp_path), "memoria.json")
    return open(ruta, encoding="utf-8").read() if os.path.exists(ruta) else ""


# ------------------------------------------------- FRONTERA 1: la ventana SÍ retiene (DR-4) --


@pytest.mark.asyncio
async def test_el_resultado_de_una_ejecucion_SI_queda_en_la_ventana_de_trabajo(tmp_path):
    """`DR-4` aprobada. Que esto es así se afirma midiendo, no leyendo el comentario del código."""
    orq = _sistema(tmp_path).orquestador

    dicho = await _turno(orq, f"lista el directorio {tmp_path}", "F1")

    assert "Ejecuté" in dicho, f"la capacidad no llego a ejecutarse: {dicho!r}"
    ventana = orq._dialogue.get("u", [])
    assert any("Ejecuté" in turno.aura for turno in ventana), (
        f"el resultado NO quedo en la ventana de trabajo: {ventana!r}"
    )


def _lineas_de_memoria(tmp_path) -> list[dict]:
    return [json.loads(x) for x in _memoria_en_disco(tmp_path).split("\n") if x.strip()]


@pytest.mark.asyncio
async def test_la_ventana_de_trabajo_NO_se_vuelca_a_disco_solo_persisten_registros_de_esquema_cerrado(tmp_path):
    """PUNTO D. El TEXTO de la ventana (el `say`) muere con el proceso. Lo único que sobrevive a un reinicio es
    un registro `resultado_accion` de esquema cerrado (decisión 7: sustituye a «sin respaldo en disco»)."""
    sis = _sistema(tmp_path)
    await _turno(sis.orquestador, f"lista el directorio {tmp_path}", "F2")

    ficheros = os.listdir(str(tmp_path))
    volcado = "".join(
        open(os.path.join(str(tmp_path), f), encoding="utf-8", errors="ignore").read()
        for f in ficheros
        if os.path.isfile(os.path.join(str(tmp_path), f))
    )
    assert "Ejecuté" not in volcado, (
        f"el texto del resultado aparecio EN DISCO; la ventana dejo de ser efimera: {ficheros}"
    )
    # CONTROL (lo que cambia): ahora SI hay un registro, y es exactamente un registro de esquema cerrado.
    registros = [x for x in _lineas_de_memoria(tmp_path) if x["kind"] == ra.KIND]
    assert len(registros) == 1, f"la accion no dejo registro persistente: {_memoria_en_disco(tmp_path)!r}"
    assert ra.desde_contenido(registros[0]["content"]) is not None, "el registro no cumple el esquema cerrado"
    assert set(ra.desde_contenido(registros[0]["content"])) == set(ra.CAMPOS)


# --------------------------------- FRONTERA 2: no se filtra a la memoria PERSONAL persistente --


@pytest.mark.asyncio
async def test_el_resultado_de_una_ejecucion_entra_en_la_memoria_persistente_SOLO_como_registro_de_esquema_cerrado(
    tmp_path,
):
    """`Bible 4.1 §1` separa memoria de trabajo de las tres persistentes. Mezclarlas convertiría el ruido de una
    ejecución en «lo que AURA sabe del usuario». PUNTO D (decisión 7): lo único que entra es un registro
    `resultado_accion` —episódico de acción, no recuperable, fuera del modelo del usuario—, nunca el resultado."""
    orq = _sistema(tmp_path).orquestador

    # CASO DE CONTROL, y encontrado por el propio control `[EJEC]`: la primera version de esta prueba
    # ejecutaba solo la orden y miraba `memoria.json`; si el fichero no existia la asercion pasaba sin comprobar
    # nada —una prueba decorativa—. Se declara antes un hecho real: asi la memoria TIENE contenido.
    await _turno(orq, "me llamo Mauricio", "F3a")
    await _turno(orq, f"lista el directorio {tmp_path}", "F3b")

    escrito = _memoria_en_disco(tmp_path)
    assert "me llamo Mauricio" in escrito, (
        f"la memoria personal no se escribio: la asercion siguiente no probaria nada ({escrito!r})"
    )
    assert "Ejecuté" not in escrito, "el resultado de ejecutar una capacidad se persistio como memoria del usuario"
    registros = [x for x in _lineas_de_memoria(tmp_path) if x["kind"] == ra.KIND]
    assert len(registros) == 1, "debe constar el registro de la accion (punto D)"
    assert ra.desde_contenido(registros[0]["content"])["capacidad"] == "listar_directorio"
    # Y nada mas con forma de resultado: ningun otro kind lleva el listado ni el say.
    otros = [x for x in _lineas_de_memoria(tmp_path) if x["kind"] != ra.KIND]
    assert all("entrada(s)" not in str(x["content"]) for x in otros)


@pytest.mark.asyncio
async def test_el_CONTENIDO_de_un_fichero_del_usuario_no_entra_en_la_memoria_persistente(tmp_path):
    """El caso que de verdad importa para la privacidad (`Bible 5.5`): `leer_archivo` devuelve
    ficheros del usuario. Que su contenido no aterrice en `memoria.json` es la frontera concreta."""
    secreto = tmp_path / "privado.txt"
    secreto.write_text(CONTENIDO_SENSIBLE, encoding="utf-8")
    orq = _sistema(tmp_path).orquestador

    await _turno(orq, "me llamo Mauricio", "F4a")
    await _turno(orq, f"lee el archivo {secreto}", "F4b")

    escrito = _memoria_en_disco(tmp_path)
    assert "me llamo Mauricio" in escrito, (
        f"la memoria personal no se escribio: la asercion siguiente no probaria nada ({escrito!r})"
    )
    # OBSERVACION REGISTRADA, no corregida aqui: la RUTA del fichero si se persiste («usuario dijo:
    # lee el archivo /…/privado.txt»), porque la memoria guarda el texto del usuario. Que AURA
    # conserve para siempre QUE ficheros ha abierto el usuario es una cuestion de privacidad real
    # (`Bible 5.5`), pero decidirla no es competencia de una prueba: queda elevada al CEO.
    assert "colibri-verde-1978" not in escrito, (
        "el CONTENIDO de un fichero del usuario se persistio en la memoria personal"
    )


# -------------------------------------- FRONTERA 3: el audit log NO es memoria conversacional --


@pytest.mark.asyncio
async def test_el_audit_log_registra_el_HECHO_de_la_ejecucion_pero_no_su_RESULTADO(tmp_path):
    """La separación que impide que la continuidad se construya sola reutilizando el registro
    forense. Medido sobre el audit log real: 7 claves fijas, `msg` más largo de 1209 entradas = 288
    caracteres, y ningún campo donde quepa un payload."""
    secreto = tmp_path / "privado.txt"
    secreto.write_text(CONTENIDO_SENSIBLE, encoding="utf-8")
    sis = _sistema(tmp_path)
    marca = len(obs.audit_records())

    await _turno(sis.orquestador, f"lee el archivo {secreto}", "F5")

    nuevos = obs.audit_records()[marca:]
    assert nuevos, "la ejecucion no dejo ningun rastro forense"
    assert any("leer_archivo" in r["msg"] for r in nuevos), "el audit log no registra siquiera QUE capacidad se ejecuto"
    volcado = json.dumps(nuevos, ensure_ascii=False)
    assert "colibri-verde-1978" not in volcado, (
        "el audit log contiene el CONTENIDO del fichero: dejo de ser metadato forense"
    )


@pytest.mark.asyncio
async def test_ninguna_superficie_de_conversacion_LEE_el_audit_log_para_responder(tmp_path):
    """Caso de control de la frontera anterior. Aunque el registro forense no lleve el payload, si
    alguna superficie empezara a leerlo para conversar, el audit log se habria convertido en memoria
    recuperable **sin decisión**. Se fija por ausencia de acoplamiento, que es como se sostiene."""
    import inspect

    from aura_skeleton.core import orchestrator

    fuente = inspect.getsource(orchestrator)
    for prohibido in ("leer_audit_desde", "audit_records", "reconstruir("):
        assert prohibido not in fuente, (
            f"el orquestador ha empezado a leer el registro forense ({prohibido}): "
            f"eso convierte la auditoria en memoria conversacional y exige decision del CEO"
        )


# ------------- FRONTERA 4: qué ACOTA hoy que el resultado reentre en el prompt del modelo --


@pytest.mark.asyncio
async def test_el_CONTENIDO_de_un_fichero_del_usuario_NO_reentra_en_el_prompt_del_turno_siguiente(
    tmp_path,
):
    """**PUNTO D, decisión 1 (CEO Operativo, 2026-11-06): esta prueba invierte la que fijaba el hecho incómodo.**
    Medido `[EJEC]` el 2026-09-21, el contenido de un fichero leído viajaba en el prompt del turno siguiente
    aunque ese turno hablara de otra cosa («pájaros»). Era consecuencia de `DR-4` (latencia y caché, no
    privacidad). Ahora la capacidad lleva la marca declarativa `devuelve_contenido_usuario`
    (`operaciones.ESPECIFICACIONES`) y el prompt solo recibe el METADATO:

        (previo) tu: lee el archivo /…/privado.txt | AURA [HECHO]: Ejecuté «leer_archivo»: leí un archivo,
        1 línea(s). Su contenido no se repite aquí.

    La recuperación a petición, en la MISMA conversación, sí repite el contenido
    (`test_el_CONTENIDO_de_un_fichero_se_repite_al_recuperar`)."""
    secreto = tmp_path / "privado.txt"
    secreto.write_text(CONTENIDO_SENSIBLE, encoding="utf-8")
    sis = _sistema(tmp_path)
    orq = sis.orquestador
    prompts: list[str] = []

    class _Espia:
        def __init__(self, interno):
            self._i, self.name = interno, getattr(interno, "name", "espia")

        async def infer(self, prompt, *a, **kw):
            prompts.append(prompt)
            return await self._i.infer(prompt, *a, **kw)

    orq.router.providers = [_Espia(p) for p in orq.router.providers]

    dicho = await _turno(orq, f"lee el archivo {secreto}", "F6a")
    await _turno(orq, "cuéntame algo interesante sobre los pájaros", "F6b")

    assert "colibri-verde-1978" in dicho, "control: el contenido SI se le entrego al usuario"
    assert prompts, "el segundo turno no llego al proveedor: la prueba no mide lo que dice medir"
    assert not any("colibri-verde-1978" in p for p in prompts), "el contenido de un fichero reentro en el prompt"
    assert any("leí un archivo, 1 línea(s)" in p for p in prompts), "control: el metadato SI reentra"


def test_el_UNICO_proveedor_de_modelo_es_LOCAL():
    """Lo que ACOTA el hallazgo de arriba. El contenido reentra en el prompt, sí — pero ese prompt
    no sale de la máquina: no hay proveedor remoto, ni endpoint, ni clave de terceros (`D24`,
    `ADR-0001`). El día que se añada uno, `Bible 5.5 §2` («al LLM externo se envía el contexto
    mínimo, nunca la memoria completa; los datos identificables se redactan») dejaría de tener nada
    que la haga cumplir sobre esta ventana. Esta prueba es el centinela de ese día."""
    import inspect

    from aura_skeleton.modules import providers_real

    fuente = inspect.getsource(providers_real)
    for rastro in ("https://api.", "api_key", "API_KEY", "Authorization"):
        assert rastro not in fuente, (
            f"aparecio un proveedor de modelo REMOTO ({rastro}). La ventana de trabajo reentra "
            f"contenido de ficheros del usuario en el prompt: enviarlo fuera exige la minimizacion "
            f"de Bible 5.5 §2 y una decision del CEO"
        )


# ------------------------------------ FRONTERA 5: lo que se retiene deja rastro (observabilidad) --


@pytest.mark.asyncio
async def test_la_retencion_en_la_ventana_de_trabajo_queda_AUDITADA(tmp_path):
    """Hasta M7 la ventana era el único almacén del sistema del que no constaba nada: se podía
    demostrar que una capacidad se ejecutó, no que su resultado quedara retenido. Sin este rastro, la
    pregunta G de la decisión pendiente —«¿cómo se audita la lectura y la escritura?»— no tendría
    respuesta ni siquiera para el estado actual."""
    sis = _sistema(tmp_path)
    marca = len(obs.audit_records())

    await _turno(sis.orquestador, f"lista el directorio {tmp_path}", "F7")

    nuevos = obs.audit_records()[marca:]
    retencion = [r for r in nuevos if r.get("module") == "memoria-trabajo"]
    assert retencion, f"la retencion en la ventana no dejo rastro forense: {nuevos}"
    assert "DR-4" in retencion[0]["msg"], "el rastro no cita la politica que la gobierna"


@pytest.mark.asyncio
async def test_el_rastro_de_retencion_NO_incluye_el_contenido_retenido(tmp_path):
    """Caso de control del anterior, y el que impide que la mejora se convierta en el problema: si el
    rastro llevara el texto retenido, el registro forense pasaría a ser la copia persistente que la
    ventana precisamente NO es — y habría tomado por accidente la decisión que está elevada."""
    secreto = tmp_path / "privado.txt"
    secreto.write_text(CONTENIDO_SENSIBLE, encoding="utf-8")
    sis = _sistema(tmp_path)
    marca = len(obs.audit_records())

    await _turno(sis.orquestador, f"lee el archivo {secreto}", "F8")

    retencion = [r for r in obs.audit_records()[marca:] if r.get("module") == "memoria-trabajo"]
    assert retencion, "la retencion no dejo rastro"
    assert "colibri-verde-1978" not in json.dumps(retencion, ensure_ascii=False), (
        "el rastro de retencion lleva el CONTENIDO: el audit log se convirtio en memoria"
    )
