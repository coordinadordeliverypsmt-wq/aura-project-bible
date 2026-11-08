"""Bateria adversarial del olvido: TODAS las rutas T1-T10 del contrato de olvido y retencion (§2).

Fuente: `milestones/m3-entry/CONTRATO-OLVIDO-Y-RETENCION.md`. Cada ruta lleva dos pruebas:

- **CONTROL**: ANTES del olvido, por esa ruta, el contenido SI se recupera. Sin control, un «no aparece»
  no distingue entre «olvidado» y «la ruta nunca lo vio» (una prueba decorativa).
- **ADVERSARIAL**: DESPUES de «olvida ...» por la via real del usuario (declaracion y olvido por
  `handle_utterance` / `ModeloUsuario.borrar`), el contenido NO aparece por esa ruta.

Se parametrizan N1 (`PersistentMemory`) y N2 (`SemanticMemory`) donde la ruta es comun. N2 necesita el modelo
de embeddings; si no esta presente se hace skip CON motivo explicito (solo las variantes `n2`).

T11 (eco de la propia orden de olvido) vive en `tests/integration/test_eco_de_soberania_t11.py`.

Lo que NO se afirma: que el texto desaparezca del disco. Sigue en el JSONL (G-7) —contrato §5, bloqueado—.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.modelo_usuario import describir_conocimiento
from aura_skeleton.modules.memory import PersistentMemory

UID = "mauricio"
AUSENCIA = "No tengo ningun recuerdo registrado sobre eso."


def _buscar_modelo() -> str | None:
    for cand in (
        os.environ.get("AURA_EMBED_MODEL_DIR", ""),
        os.path.expanduser("~/.aura/models/all-MiniLM-L6-v2"),
        os.path.expanduser("~/.ruvector/models/all-MiniLM-L6-v2"),
    ):
        if (
            cand
            and os.path.exists(os.path.join(cand, "model.onnx"))
            and os.path.exists(os.path.join(cand, "tokenizer.json"))
        ):
            return cand
    return None


MODELO = _buscar_modelo()
_SIN_MODELO = "modelo de embeddings no presente: N2 no puede instanciarse (ver AURA_EMBED_MODEL_DIR)"

_RAZON_N2 = (
    "D-N2-2/D-N2-5 bloqueado: requiere declaracion G-1 aprobada + gate del CEO (DEUDA-N2); "
    "parche en milestones/m3-entry/propuestas/D-N2-5-y-restore.patch"
)
_RAZON_T8 = "T8 bloqueado: restore reescribe con _persist (G-7/ADR-0023); sin llamador en produccion"
# `raises` fija el MOTIVO: SemanticMemory no tiene `_items` ni `olvidar` (AttributeError). Un fallo distinto
# (p. ej. una asercion) NO seria este bloqueo y rompe la suite en vez de quedar oculto como xfail.
XFAIL_N2 = pytest.mark.xfail(strict=True, raises=AttributeError, reason=_RAZON_N2)
XFAIL_T8 = pytest.mark.xfail(strict=True, raises=AssertionError, reason=_RAZON_T8)

NIVELES = [
    "n1",
    pytest.param("n2", marks=[pytest.mark.skipif(MODELO is None, reason=_SIN_MODELO), XFAIL_N2]),
]

V1 = "mi cumpleaños es el 10 de mayo"
V2 = "mi cumpleaños es el 3 de junio"


class _Espia:
    name = "espia"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.prompts.append(prompt)
        return json.dumps({"intent": "x", "action": "consulta", "args": {}, "say": "respuesta del modelo"})


class Sistema:
    """El flujo REAL (`componer`) sobre una memoria N1 o N2, con datos en `tmp_path` (reabrible).

    Para N2 se sustituye `_memoria_por_nivel` (la unica costura donde la composicion elige nivel segun el
    hardware del plan): en este equipo el plan entrega siempre N1, y lo que se prueba aqui es el flujo
    del usuario sobre N2 con el modelo de embeddings real.
    """

    def __init__(self, tmp_path, nivel: str, monkeypatch) -> None:
        self.tmp = tmp_path
        self.nivel = nivel
        if nivel == "n2":
            from aura_skeleton import composicion
            from aura_skeleton.modules.memory_semantic import SemanticMemory

            def _n2(estado, ruta):
                assert MODELO is not None
                return SemanticMemory(ruta, MODELO), "N2 (indice semantico)", ""

            monkeypatch.setattr(composicion, "_memoria_por_nivel", _n2)
        self.abrir()

    def abrir(self) -> None:
        """(Re)abre desde disco: es el reinicio del proceso."""
        config = Configuracion(datos=str(self.tmp), raices_permitidas=(str(self.tmp),), usar_stack_real=False)
        self.s = componer(config)
        self.espia = _Espia()
        self.s.orquestador.router.providers = [self.espia]
        self.orq = self.s.orquestador
        self.memoria = self.s.orquestador.memory
        self.modelo_usuario = self.s.modelo_usuario

    async def decir(self, texto: str) -> dict:
        tid = uuid.uuid4().hex[:12]
        await self.orq.handle_utterance(UID, texto, tid)
        return await self.orq.wait(tid)

    async def declarar_y_olvidar_la_vigente(self) -> None:
        await self.decir(V1)
        await self.decir(V2)
        r = await self.decir("olvida mi cumpleaños")
        assert "Hecho" in r["say"], r["say"]

    def items(self) -> list[dict]:
        m = self.memoria
        return list(getattr(m, "_store", m)._items)


@pytest.fixture(params=NIVELES)
def sis(request, tmp_path, monkeypatch) -> Sistema:
    return Sistema(tmp_path, request.param, monkeypatch)


def _vigentes_con(items: list[dict], texto: str) -> list[dict]:
    """Entradas NO episodicas con ese contenido: el conocimiento afirmable (el eco retirado no cuenta)."""
    return [i for i in items if i["kind"] != "episodica" and texto in i["content"]]


def _ecos_activos(items: list[dict], texto: str) -> list[dict]:
    return [
        i
        for i in items
        if i["kind"] == "episodica" and texto in i["content"] and not i.get("provenance", {}).get("retirada")
    ]


# ------------------------------------------------------------ T1 · recall misma sesion --


@pytest.mark.asyncio
async def test_T1_CONTROL_antes_de_olvidar_recall_recupera_la_declaracion(sis):
    await sis.decir(V2)
    hits = await sis.memoria.recall(UID, "mi cumpleaños es el 3 de junio")
    assert _vigentes_con(hits, "3 de junio"), hits


@pytest.mark.asyncio
async def test_T1_tras_olvidar_ni_items_ni_recall_conservan_la_declaracion(sis):
    await sis.declarar_y_olvidar_la_vigente()
    assert _vigentes_con(sis.items(), "3 de junio") == []
    hits = await sis.memoria.recall(UID, "mi cumpleaños es el 3 de junio", k=10)
    assert _vigentes_con(hits, "3 de junio") == [], hits
    assert _ecos_activos(hits, "3 de junio") == [], "el eco solo puede salir retirado"


# ----------------------------------------------------------------- T2 · reinicio --


@pytest.mark.asyncio
async def test_T2_CONTROL_sin_olvidar_el_reinicio_conserva_la_declaracion(sis):
    await sis.decir(V2)
    sis.abrir()
    assert _vigentes_con(sis.items(), "3 de junio")
    assert _vigentes_con(await sis.memoria.recall(UID, "mi cumpleaños es el 3 de junio"), "3 de junio")


@pytest.mark.asyncio
async def test_T2_tras_olvidar_y_reiniciar_la_declaracion_no_reaparece(sis):
    await sis.declarar_y_olvidar_la_vigente()
    sis.abrir()
    assert _vigentes_con(sis.items(), "3 de junio") == []
    assert _vigentes_con(await sis.memoria.recall(UID, "mi cumpleaños es el 3 de junio", k=10), "3 de junio") == []
    assert [e["contenido"] for e in await sis.modelo_usuario.ver(UID) if "3 de junio" in e["contenido"]] == []


# ------------------------------------------------------- T3 · N2 (vectores alineados) --


@pytest.mark.skipif(MODELO is None, reason=_SIN_MODELO)
@pytest.mark.asyncio
async def test_T3_CONTROL_N2_recupera_lo_escrito_y_sus_vectores_estan_alineados(tmp_path):
    from aura_skeleton.modules.memory_semantic import SemanticMemory

    mem = SemanticMemory(str(tmp_path / "m.json"), MODELO)
    await mem.write(UID, "semantica", "tiene un gato llamado Mateo", {})
    await mem.write(UID, "semantica", "paga el alquiler por transferencia", {})
    assert len(mem._vectores) == len(mem._store._items) == 2
    hits = await mem.recall(UID, "tiene un gato llamado Mateo", k=1)
    assert hits[0]["content"] == "tiene un gato llamado Mateo"


@XFAIL_N2
@pytest.mark.skipif(MODELO is None, reason=_SIN_MODELO)
@pytest.mark.asyncio
async def test_T3_N2_olvidar_realinea_vectores_y_no_devuelve_lo_olvidado(tmp_path):
    from aura_skeleton.modules.memory_semantic import SemanticMemory

    mem = SemanticMemory(str(tmp_path / "m.json"), MODELO)
    for c in ("tiene un gato llamado Mateo", "paga el alquiler por transferencia", "prefiere la luz tenue"):
        await mem.write(UID, "semantica", c, {})
    n = mem.olvidar(lambda i: "gato" in i["content"])
    assert n == 1
    assert len(mem._vectores) == len(mem._store._items) == 2
    hits = await mem.recall(UID, "tiene un gato llamado Mateo", k=5)
    assert all("gato" not in h["content"] for h in hits), hits
    # El alineamiento es CORRECTO, no solo del mismo largo: cada vector sigue siendo el de su entrada.
    for item, vec in zip(mem._store._items, mem._vectores, strict=True):
        assert vec == pytest.approx(mem._embed(item["content"]))


# ------------------------------------------------------ T4 · puerta ADR-0014 y contexto --

_PREGUNTA = "¿mi cumpleaños?"


def _contexto_de_memoria(prompt: str) -> str:
    """Solo el bloque `[contexto memoria: ...]` del prompt: lo que la MEMORIA le pasa al modelo.

    El prompt lleva ademas el dialogo reciente («(previo) tu: ...»): es el buffer de la conversacion en
    curso, no memoria, y queda fuera de las rutas T1-T10 (el usuario ve lo que el mismo dijo en pantalla).
    """
    marca = "[contexto memoria: "
    if marca not in prompt:
        return ""
    inicio = prompt.index(marca) + len(marca)
    return prompt[inicio : prompt.index("]\n", inicio)]


@pytest.mark.asyncio
async def test_T4_CONTROL_con_la_declaracion_vigente_el_contexto_del_modelo_la_lleva(sis):
    await sis.decir(V2)
    await sis.decir(_PREGUNTA)
    assert sis.espia.prompts and "3 de junio" in _contexto_de_memoria(sis.espia.prompts[-1])


@pytest.mark.asyncio
async def test_T4_tras_olvidar_la_puerta_da_ausencia_y_el_modelo_no_recibe_el_dato(sis):
    await sis.declarar_y_olvidar_la_vigente()
    sis.espia.prompts.clear()
    r = await sis.decir(_PREGUNTA)
    assert "3 de junio" not in r["say"]
    assert all("3 de junio" not in _contexto_de_memoria(p) for p in sis.espia.prompts), (
        "el dato olvidado viajo al modelo por el contexto de memoria"
    )


# ----------------------------------------------------------------- T5 · hechos del Core --


@pytest.mark.asyncio
async def test_T5_CONTROL_el_Core_responde_el_hecho_vigente(sis):
    await sis.decir(V2)
    r = await sis.decir("¿Cuál es mi cumpleaños?")
    assert "3 de junio" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_T5_tras_olvidar_el_Core_no_afirma_el_hecho(sis):
    await sis.declarar_y_olvidar_la_vigente()
    for pregunta in ("¿Cuál es mi cumpleaños?", "¿qué sabes de mí?"):
        r = await sis.decir(pregunta)
        assert "3 de junio" not in r["say"], f"{pregunta!r}: {r['say']!r}"


# ----------------------------------------------------------------- T6 · historial --


@pytest.mark.asyncio
async def test_T6_CONTROL_el_historial_ofrece_la_version_anterior(sis):
    await sis.decir(V1)
    await sis.decir(V2)
    r = await sis.decir("¿cuál era mi cumpleaños?")
    assert "10 de mayo" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_T6_tras_olvidar_todas_las_versiones_el_historial_no_ofrece_ninguna(sis):
    await sis.decir(V1)
    await sis.decir(V2)
    n = await sis.modelo_usuario.borrar(UID, contiene="cumpleaños")
    assert n >= 2, "precondicion: se olvidaron las dos versiones"
    r = await sis.decir("¿cuál era mi cumpleaños?")
    assert "10 de mayo" not in r["say"] and "3 de junio" not in r["say"], r["say"]
    sis.abrir()
    r = await sis.decir("¿cuál era mi cumpleaños?")
    assert "10 de mayo" not in r["say"] and "3 de junio" not in r["say"], f"tras reiniciar: {r['say']}"


# ------------------------------------------------- T7 · ver / describir_conocimiento --


@pytest.mark.asyncio
async def test_T7_CONTROL_ver_y_describir_conocimiento_muestran_lo_declarado(sis):
    await sis.decir(V2)
    entradas = await sis.modelo_usuario.ver(UID)
    assert any("3 de junio" in e["contenido"] for e in entradas)
    assert "3 de junio" in describir_conocimiento(entradas)


@pytest.mark.asyncio
async def test_T7_tras_olvidar_ni_ver_ni_describir_conocimiento_lo_muestran(sis):
    await sis.declarar_y_olvidar_la_vigente()
    entradas = await sis.modelo_usuario.ver(UID)
    assert all("3 de junio" not in e["contenido"] for e in entradas)
    assert "3 de junio" not in describir_conocimiento(entradas)
    sis.abrir()
    entradas = await sis.modelo_usuario.ver(UID)
    assert "3 de junio" not in describir_conocimiento(entradas)


# ----------------------------------------------------------------- T8 · restore --


@pytest.mark.asyncio
async def test_T8_CONTROL_restaurar_una_copia_sin_olvido_posterior_devuelve_el_contenido(tmp_path):
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await mem.write(UID, "semantica", V2, {})
    copia = mem.backup()
    mem._items = []
    mem._persist()
    assert mem.restore(copia) is True
    assert _vigentes_con(mem._items, "3 de junio")
    assert _vigentes_con(PersistentMemory(str(tmp_path / "m.json"))._items, "3 de junio")


# Solo la variante n1 es el bloqueo T8 (la n2 lleva ya XFAIL_N2 por NIVELES): la marca se aplica por parametro.
@pytest.mark.parametrize(
    "nivel",
    [pytest.param("n1", marks=XFAIL_T8), NIVELES[1]],
)
@pytest.mark.asyncio
async def test_T8_restaurar_una_copia_anterior_al_olvido_no_resucita_lo_olvidado(tmp_path, nivel, monkeypatch):
    sis = Sistema(tmp_path, nivel, monkeypatch)
    await sis.decir(V1)
    await sis.decir(V2)
    copia = sis.memoria.backup()  # copia ANTERIOR al olvido: contiene V2
    r = await sis.decir("olvida mi cumpleaños")
    assert "Hecho" in r["say"], r["say"]
    assert _vigentes_con(sis.items(), "3 de junio") == []

    assert sis.memoria.restore(copia) is True

    assert _vigentes_con(sis.items(), "3 de junio") == [], "restore resucito lo olvidado en la sesion"
    if nivel == "n2":  # D-N2-5 / fragilidad ante restore: cada vector sigue siendo el de SU entrada
        mem = sis.memoria
        assert len(mem._vectores) == len(mem._store._items)
        for item, vec in zip(mem._store._items, mem._vectores, strict=True):
            assert vec == pytest.approx(mem._embed(item["content"]))
    assert _vigentes_con(await sis.memoria.recall(UID, "mi cumpleaños es el 3 de junio", k=10), "3 de junio") == []
    sis.abrir()
    assert _vigentes_con(sis.items(), "3 de junio") == [], "restore resucito lo olvidado tras reiniciar"
    assert [e for e in await sis.modelo_usuario.ver(UID) if "3 de junio" in e["contenido"]] == []
    # La copia SI devuelve el resto (lo no olvidado): restore no se vuelve un no-op.
    assert _vigentes_con(sis.items(), "10 de mayo"), "restore no restauro lo demas"


@pytest.mark.asyncio
async def test_T8_una_redeclaracion_POSTERIOR_al_olvido_si_sobrevive_al_restore(tmp_path):
    """La lapida solo se re-anexa si sigue siendo lo ULTIMO dicho de su clave: el usuario manda."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await mem.write(UID, "semantica", V2, {})
    copia = mem.backup()
    mem.olvidar(lambda i: i["content"] == V2)
    await mem.write(UID, "semantica", V2, {})  # el usuario vuelve a declararlo despues de olvidar
    assert mem.restore(copia) is True
    assert _vigentes_con(mem._items, "3 de junio"), "se olvido lo que el usuario volvio a declarar"


@XFAIL_T8
@pytest.mark.asyncio
async def test_T8_la_lapida_se_anexa_sin_reescribir_el_historial_posterior(tmp_path):
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    await mem.write(UID, "semantica", V2, {})
    copia = mem.backup()
    mem.olvidar(lambda i: i["content"] == V2)
    assert mem.restore(copia) is True
    lineas = [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lineas[-1].get("_olvidada") is True and lineas[-1]["content"] == V2, lineas


# ---------------------------------------------------- T9 · linea final truncada/corrupta --
#
# COMPORTAMIENTO EXISTENTE de `PersistentMemory._load` (no se cambia): lee cada linea con `json.loads` sin
# tolerancia, asi que una ultima linea truncada hace FALLAR la apertura con `json.JSONDecodeError`. Es
# fail-loud: no oculta el corte ni lo salta. Consecuencia buscada para el olvido: una lapida truncada NO
# produce una resurreccion silenciosa —la apertura falla y nadie sirve el dato—.


@pytest.mark.asyncio
async def test_T9_CONTROL_sin_truncar_el_fichero_abre_y_conserva_las_entradas(tmp_path):
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    await mem.write(UID, "semantica", V2, {})
    assert _vigentes_con(PersistentMemory(str(ruta))._items, "3 de junio")


@pytest.mark.asyncio
async def test_T9_una_lapida_truncada_hace_fallar_la_apertura_no_resucita_en_silencio(tmp_path):
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    await mem.write(UID, "semantica", V2, {})
    mem.olvidar(lambda i: i["content"] == V2)
    texto = ruta.read_text(encoding="utf-8")
    ruta.write_text(texto[: len(texto) - 25], encoding="utf-8")  # corta la lapida a mitad de linea
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


@pytest.mark.asyncio
async def test_T9_una_linea_final_truncada_cualquiera_es_fail_loud(tmp_path):
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    await mem.write(UID, "semantica", V2, {})
    with open(ruta, "a", encoding="utf-8") as f:
        f.write('{"user_id": "mauricio", "kind": "sem')  # sin salto de linea ni cierre
    with pytest.raises(json.JSONDecodeError):
        PersistentMemory(str(ruta))


# ------------------------------------------------------------------- T10 · reloj de CM2 --


@pytest.mark.asyncio
async def test_T10_el_reloj_lee_con_la_misma_proyeccion_que_la_memoria(tmp_path):
    """Control y adversarial en una sola lectura: antes del olvido el reloj ve la entrada; despues, no."""
    reloj = pytest.importorskip("aura_skeleton.core.reloj_cm2")
    lector = getattr(reloj, "_MemoriaSoloLectura", None)
    if lector is None:
        pytest.skip("reloj_cm2._MemoriaSoloLectura no existe en esta version del reloj")
    ruta = tmp_path / "m.json"
    mem = PersistentMemory(str(ruta))
    await mem.write(UID, "semantica", V2, {"clase": "hecho_declarado"})
    assert any(V2 == i["content"] for i in lector(str(ruta))._items), "CONTROL: el reloj debia ver la entrada"
    mem.olvidar(lambda i: i["content"] == V2)
    assert not any(V2 == i["content"] for i in lector(str(ruta))._items), "el reloj leyo lo olvidado"


# -------------------------------------------------- 4+ versiones desplazando a la vigente --

_CUMPLES = (V1, V2, "mi cumpleaños es el 4 de julio", "mi cumpleaños es el 5 de agosto")


@pytest.mark.asyncio
async def test_cuatro_versiones_CONTROL_la_vigente_llega_al_modelo_pese_al_recorte_de_k(tmp_path, monkeypatch):
    sis = Sistema(tmp_path, "n1", monkeypatch)
    for c in _CUMPLES:
        await sis.decir(c)
    antiguos = tuple(f"usuario dijo: {c}" for c in _CUMPLES[:3])
    n = sis.memoria.marcar(lambda i: i["content"] in antiguos, {"retirada": True})
    assert n == 3, "precondicion: los ecos de v1..v3 retirados (como tras olvidar/refutar)"
    sis.espia.prompts.clear()
    r = await sis.decir(_PREGUNTA)
    assert r["say"] != AUSENCIA
    assert sis.espia.prompts and "5 de agosto" in _contexto_de_memoria(sis.espia.prompts[-1])


@pytest.mark.asyncio
async def test_cuatro_versiones_olvidar_la_vigente_no_deja_que_una_antigua_ocupe_su_lugar(tmp_path, monkeypatch):
    sis = Sistema(tmp_path, "n1", monkeypatch)
    for c in _CUMPLES:
        await sis.decir(c)
    r = await sis.decir("olvida mi cumpleaños")
    assert "Hecho" in r["say"], r["say"]
    sis.espia.prompts.clear()
    r = await sis.decir("¿Cuál es mi cumpleaños?")
    for antigua in ("10 de mayo", "3 de junio", "4 de julio", "5 de agosto"):
        assert antigua not in r["say"], f"{antigua}: {r['say']!r}"
    assert all("5 de agosto" not in _contexto_de_memoria(p) for p in sis.espia.prompts)
    sis.abrir()
    r = await sis.decir("¿Cuál es mi cumpleaños?")
    assert "5 de agosto" not in r["say"], f"tras reiniciar: {r['say']!r}"
