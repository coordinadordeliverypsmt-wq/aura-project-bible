"""Incremento A — Hechos declarados del usuario (acta del CEO, 2026-08-09).

DEFECTO DE USO REAL QUE LO MOTIVA. El CEO declaró `Mi nombre es Mauricio` y después `¿Cómo me
llamo?` respondió *«No tengo ningún recuerdo registrado sobre eso»*. Medido: `¿Qué sabes de mí?`
respondía además «Todavía no sé nada sobre ti», con el Modelo de Usuario vacío pese a la
declaración.

CAUSA RAÍZ. `conectores/conversacion.py::_clasificar` reconoce tres clases y las tres exigen
marcadores de PREFERENCIA (`prefiero`, `me gusta`, `suelo`…). `Mi nombre es Mauricio` no lleva
ninguno, devuelve `None`, y nada llega a memoria semántica. La cadena está sana; le falta una regla.

LA TRAMPA QUE ESTAS PRUEBAS EXISTEN PARA MATAR. Hoy, SIN incremento alguno, `¿Qué recuerdas de mi
trabajo?` ya responde «logística», por solape léxico entre «mi trabajo» y «Trabajo en logística».
Una prueba que sólo compruebe que la respuesta contiene esa palabra PASARÍA HOY y no demostraría
nada. Por eso el criterio principal es `¿Cómo me llamo?`, que tiene CERO solape léxico con su
declaración, y por eso hay tres candados (A: origen · B: episódica neutralizada · C: cero solape).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.senales import ClaseSenal, Senal, SenalDeTercero
from aura_skeleton.modules.router import ModelRouter

_RUTA_BATERIA_MEMORIA = Path(__file__).parent.parent / "datos" / "bateria_memoria.json"
_AUSENCIA = "No tengo ningun recuerdo registrado sobre eso."


class _ProveedorEspia:
    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str) -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"FABRICADO por el LLM"}'


async def _di(orq, texto, uid="mauricio"):
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(uid, texto, tid)
    return await orq.wait(tid)


@pytest.fixture
def sistema(tmp_path):
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    return componer(cfg)


# ------------------------------------------------------------------ P1 · CONTRATO DE TAXONOMÍA --

# Bible 4.4 §1, congelada aquí. El CEO lo exigió explícitamente: P1 no puede limitarse a comprobar
# que `HECHO_DECLARADO` existe; debe detectar también la ausencia o alteración de las clases
# contractuales existentes. Hoy NADA ata el enum a la Bible -- verificado: no existe ningún
# `len(ClaseSenal)` ni equivalente en el repositorio-, así que el enum podría divergir del documento
# sin que una sola prueba fallara. Ése es el patrón «declarado != real» que este proyecto ha pagado
# nueve veces.
_EXPLICITAS_CONTRACTUALES = {
    "correccion",
    "preferencia_declarada",
    "feedback_directo",
    "hecho_declarado",
}
_IMPLICITAS_CONTRACTUALES = {
    "patron_de_uso",
    "tema_recurrente",
    "respuesta_a_sugerencia",
}


def test_P1_la_taxonomia_de_senales_coincide_con_bible_44():
    """Correspondencia EXACTA entre `ClaseSenal` y Bible 4.4 §1, en ambos sentidos.

    Falla si se añade una clase sin documentarla, si se borra una contractual, o si se renombra el
    valor de cualquiera de ellas.
    """
    reales = {c.value for c in ClaseSenal}
    esperadas = _EXPLICITAS_CONTRACTUALES | _IMPLICITAS_CONTRACTUALES
    assert reales == esperadas, (
        f"la taxonomía divergió de Bible 4.4 §1.\n  sobran: {reales - esperadas}\n  faltan: {esperadas - reales}"
    )


def test_P1_las_familias_explicita_e_implicita_son_las_contractuales():
    """La FAMILIA también es contrato: `Senal.declarada` depende de ella, y de `declarada` depende la
    procedencia que se persiste. Una clase explícita degradada a implícita cambiaría el origen
    epistémico del dato sin tocar ni una línea del almacén."""
    declaradas = {c.value for c in ClaseSenal if Senal(c, "x", "conversacion", "t").declarada}
    assert declaradas == _EXPLICITAS_CONTRACTUALES, f"las señales explícitas dejaron de ser las de 4.4 §1: {declaradas}"


# ------------------------------------------------- P2-P4 · LA DECLARACIÓN ENTRA POR LA CADENA --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("declaracion", "fragmento"),
    [
        ("Mi nombre es Mauricio", "Mauricio"),
        ("Trabajo en logística", "logística"),
        ("Estoy trabajando en un proyecto llamado AURORA", "AURORA"),
    ],
)
async def test_P2_P3_P4_la_declaracion_aterriza_en_memoria_semantica_como_declarada(sistema, declaracion, fragmento):
    """Reglas 1-4 del acta: clase propia, ruta existente, memoria semántica y procedencia
    `declarada` desde el primer registro."""
    await _di(sistema.orquestador, declaracion)

    entradas = await sistema.modelo_usuario.ver("mauricio")
    coincidentes = [e for e in entradas if fragmento in e["contenido"]]
    assert coincidentes, f"{declaracion!r} no llegó al Modelo de Usuario: {entradas}"

    entrada = coincidentes[0]
    assert entrada["tipo"] == "semantica", f"aterrizó en {entrada['tipo']!r}, no en memoria semántica"
    assert entrada["origen"] == "declarada", f"procedencia {entrada['origen']!r}, debía ser 'declarada'"
    assert entrada["clase"] == ClaseSenal.HECHO_DECLARADO.value, (
        f"clasificada como {entrada['clase']!r}: regla 2 del acta prohíbe reutilizar preferencia_declarada"
    )


# --------------------------------------------------------------- P5-P6 · REFUTACIÓN Y BORRADO --


@pytest.mark.asyncio
async def test_P5_un_hecho_declarado_se_puede_refutar(sistema):
    """Regla 5, demostrada EJECUTANDO -- no inspeccionando código."""
    await _di(sistema.orquestador, "Trabajo en logística")
    n = await sistema.modelo_usuario.refutar("mauricio", "logística")
    assert n == 1, "la refutación no alcanzó al hecho declarado"

    vivas = [e for e in await sistema.modelo_usuario.ver("mauricio") if not e["refutada"]]
    assert not [e for e in vivas if "logística" in e["contenido"]], "sigue vivo tras refutarlo"


@pytest.mark.asyncio
async def test_P6_un_hecho_declarado_se_puede_borrar(sistema):
    """Regla 5. `borrar` es destructivo: el dato desaparece del modelo, no queda marcado."""
    await _di(sistema.orquestador, "Mi nombre es Mauricio")
    n = await sistema.modelo_usuario.borrar("mauricio", "Mauricio")
    assert n == 1, "el borrado no alcanzó al hecho declarado"
    assert not [e for e in await sistema.modelo_usuario.ver("mauricio") if "Mauricio" in e["contenido"]]


# ------------------------------------------------------------ P7 · LAS CUATRO CADENAS COMPLETAS --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("declaracion", "consulta", "esperado_en_respuesta"),
    [
        ("Mi nombre es Mauricio", "¿Cómo me llamo?", "Mauricio"),
        ("Trabajo en logística", "¿Qué trabajo hago?", "logística"),
        ("Estoy trabajando en un proyecto llamado AURORA", "¿En qué proyecto trabajo?", "AURORA"),
        ("Prefiero trabajar de noche", "¿Qué prefiero?", "noche"),
    ],
)
async def test_P7_las_cuatro_cadenas_declaracion_consulta(sistema, declaracion, consulta, esperado_en_respuesta):
    """Regla 7: nombre · ocupación · proyecto · preferencia. Declarar y recuperar POR INTENCIÓN."""
    await _di(sistema.orquestador, declaracion)
    r = await _di(sistema.orquestador, consulta)
    assert r["provider"] == "core", f"{consulta!r} no la respondió el núcleo: {r['provider']!r}"
    assert esperado_en_respuesta in r["say"], f"{consulta!r} no recuperó el hecho: {r['say']!r}"
    assert r["say"] != _AUSENCIA


# ------------------------------------------------- P9 · LOS TRES CANDADOS CONTRA EL SOLAPE LÉXICO --


@pytest.mark.asyncio
async def test_P9_candado_C_cero_solape_lexico(
    sistema,
):
    """CANDADO C, y criterio PRINCIPAL del CEO. `¿Cómo me llamo?` no comparte NI UN término con
    `Mi nombre es Mauricio`: ninguna coincidencia léxica puede resolverlo. Es el caso que hoy falla
    y el que demuestra que existe conocimiento, no parecido de texto."""
    await _di(sistema.orquestador, "Mi nombre es Mauricio")
    r = await _di(sistema.orquestador, "¿Cómo me llamo?")
    assert r["provider"] == "core"
    assert "Mauricio" in r["say"], f"no recuperó el nombre: {r['say']!r}"


@pytest.mark.asyncio
async def test_P9_candado_A_el_origen_es_el_modelo_de_usuario_no_el_recall(sistema):
    """CANDADO A. El recall episódico responde con el prefijo «Según lo que recuerdo: usuario dijo:»
    y `provider` del LLM; el Modelo de Usuario responde desde el núcleo. Son distinguibles sin
    ambigüedad, y esta prueba exige la segunda forma para la consulta TRAMPA -la de trabajo-, que es
    la única que el solape léxico podría resolver por accidente."""
    await _di(sistema.orquestador, "Trabajo en logística")
    r = await _di(sistema.orquestador, "¿Qué trabajo hago?")
    assert r["provider"] == "core", "respondió el LLM: viene del recall episódico, no del Modelo de Usuario"
    assert "usuario dijo:" not in r["say"], f"la respuesta es un volcado episódico: {r['say']!r}"
    assert "Según lo que recuerdo" not in r["say"], f"la respuesta es un volcado episódico: {r['say']!r}"
    assert "logística" in r["say"]


@pytest.mark.asyncio
async def test_P9_candado_B_con_la_memoria_episodica_neutralizada(sistema):
    """CANDADO B, el que mata la trampa de raíz. Se declara el hecho, se BORRAN todas las entradas
    episódicas del almacén, y se consulta. Si la respuesta sigue apareciendo, procede del Modelo de
    Usuario por construcción -- no queda otra fuente posible."""
    await _di(sistema.orquestador, "Trabajo en logística")

    episodicas = [i for i in sistema.memoria._items if i["kind"] == "episodica"]
    assert episodicas, "guarda de cordura: no había memoria episódica que neutralizar"
    sistema.memoria._items = [i for i in sistema.memoria._items if i["kind"] != "episodica"]

    r = await _di(sistema.orquestador, "¿Qué trabajo hago?")
    assert r["provider"] == "core"
    assert "logística" in r["say"], f"sin memoria episódica dejó de recuperarlo: venía del recall: {r['say']!r}"


@pytest.mark.asyncio
async def test_P9_negativo_un_hecho_no_declarado_no_aparece(sistema):
    """CONTROL NEGATIVO exigido por el CEO. Sin él, los tres candados se cumplirían con una
    superficie que responde siempre lo mismo."""
    await _di(sistema.orquestador, "Mi nombre es Mauricio")
    r = await _di(sistema.orquestador, "¿Qué trabajo hago?")
    assert "logística" not in r["say"], f"fabricó una ocupación que nadie declaró: {r['say']!r}"


# ------------------------------------------------------- P8 · PERSISTENCIA ENTRE PROCESOS --


@pytest.mark.asyncio
async def test_P8_el_hecho_sobrevive_a_un_proceso_nuevo(tmp_path):
    """Regla del CEO: toda capacidad importante sobrevive al reinicio. Se declara en UN proceso
    (subproceso real, no otra composición en el mismo intérprete) y se consulta en OTRO."""
    datos = str(tmp_path)
    guion = "Mi nombre es Mauricio\nsalir\n"
    primero = subprocess.run(
        [sys.executable, "-m", "aura_skeleton"],
        input=guion,
        capture_output=True,
        text=True,
        # Entorno REAL con `AURA_DATOS` redirigido, no uno mínimo construido a mano: con un `env`
        # recortado el subproceso arrancaba y salía con 0, pero no era el mismo entorno en que corre
        # el producto -- la prueba habría medido otra cosa. `AURA_DATOS` apunta a `tmp_path`, así que
        # `~/.aura` del usuario real queda intacto.
        env={**os.environ, "AURA_DATOS": datos},
        cwd=str(Path(__file__).resolve().parents[2]),
        timeout=180,
    )
    assert primero.returncode == 0, f"el primer proceso falló: {primero.stderr[-500:]}"

    cfg = Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=False)
    sistema = componer(cfg)

    # El `user_id` es el que usa el entrypoint real (`__main__.py:116`), no el de las demás pruebas.
    # No es un detalle de forma: consultar con otro identificador devolvía vacío porque el
    # aislamiento por usuario (P-ARQ-5) estaba funcionando -- nadie ve el modelo de otro-. La prueba
    # medía la garantía en vez de la persistencia.
    r = await _di(sistema.orquestador, "¿Cómo me llamo?", uid="usuario")
    assert r["provider"] == "core"
    assert "Mauricio" in r["say"], f"el hecho no sobrevivió al reinicio del proceso: {r['say']!r}"

    # Control del aislamiento: OTRO usuario no ve el hecho. Sin esto, la prueba pasaría igual si la
    # persistencia se hubiera vuelto global.
    ajeno = await _di(sistema.orquestador, "¿Cómo me llamo?", uid="otro")
    assert "Mauricio" not in ajeno["say"], f"el hecho se filtró a otro usuario: {ajeno['say']!r}"


# --------------------------------------------- P10-P12 · LA PROMOCIÓN ES CONSERVADORA --


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["Hoy estoy cansado", "Estoy cansado hoy", "Hoy tengo prisa"])
async def test_P10_un_estado_pasajero_no_se_promueve(sistema, frase):
    """Objetivo 4 del encargo del CEO: `Hoy estoy cansado` puede quedar como episódica, pero NO
    puede convertirse en «el usuario está cansado permanentemente»."""
    await _di(sistema.orquestador, frase)
    entradas = await sistema.modelo_usuario.ver("mauricio")
    assert not entradas, f"{frase!r} se promovió a conocimiento permanente: {entradas}"


@pytest.mark.asyncio
async def test_P11_usuario_nuevo_no_inventa_el_nombre(sistema):
    """INV-9. Sin declaración previa, AURORA dice que no lo sabe. No fabrica."""
    r = await _di(sistema.orquestador, "¿Cómo me llamo?")
    assert r["provider"] == "core"
    assert "Mauricio" not in r["say"], f"fabricó un nombre: {r['say']!r}"
    assert not (await sistema.modelo_usuario.ver("mauricio")), "apareció un hecho que nadie declaró"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase",
    ["Mi hermana se llama Ana", "Mi jefa trabaja en logística", "Mi amigo se llama Pedro"],
)
async def test_P12_no_se_capturan_hechos_de_terceros(sistema, frase):
    """ALERTA-002 y Bible 4.4 §1: señales del propio usuario, nunca de terceros. La guarda
    `_habla_de_tercero` ya existe y debe seguir vetando estas frases."""
    await _di(sistema.orquestador, frase)
    entradas = await sistema.modelo_usuario.ver("mauricio")
    assert not entradas, f"capturó un hecho sobre otra persona: {entradas}"


def test_P12_el_contrato_de_tercero_alcanza_a_la_clase_nueva():
    """La excepción `SenalDeTercero` se lanza en el constructor de `Senal`, así que cubre cualquier
    clase; se fija por contrato para que `HECHO_DECLARADO` no quede fuera por accidente."""
    with pytest.raises(SenalDeTercero):
        Senal(ClaseSenal.HECHO_DECLARADO, "mi hermana se llama Ana", "conversacion", "t", sobre_tercero=True)


# ----------------------------------------------------- P13 · ADR-0014 SIGUE INTACTO --


@pytest.mark.asyncio
async def test_P13_las_24_negativas_siguen_atendidas_por_el_nucleo_sin_llm(sistema):
    """Regla 10. La garantía irrenunciable no puede ceder al añadir una superficie nueva.
    Condición: memoria vacía (ver `DEUDA-ADR0014-MEMORIA-VACIA.md`)."""
    bateria = json.loads(_RUTA_BATERIA_MEMORIA.read_text(encoding="utf-8"))
    negativas = [c["texto"] for c in bateria["consultas"] if c.get("esperado") is None]
    assert len(negativas) == 24

    espia = _ProveedorEspia()
    sistema.orquestador.router = ModelRouter([espia], 1200)
    fallos = [
        (f, r["provider"], r["say"])
        for f in negativas
        if (r := await _di(sistema.orquestador, f))["provider"] != "core" or r["say"] != _AUSENCIA
    ]
    assert not fallos, f"{len(fallos)}/24 negativas desprotegidas: {fallos[:3]}"
    assert espia.llamadas == 0


# ------------------------------------- GARANTÍAS QUE LA MUTACIÓN DEMOSTRÓ SIN RED (H2, H4, H9, H10) --
#
# Las cuatro sobrevivían a las 25 pruebas de arriba. No son preventivas: cada una cubre un mutante
# que cambiaba la conducta y que nada detectaba.


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", ["Hoy trabajo en casa", "Esta semana trabajo en el almacén"])
async def test_H2_un_hecho_con_marca_temporal_no_se_promueve(sistema, frase):
    """MUTANTE VIVO H2. `Hoy estoy cansado` no bastaba: no lleva marcador de hecho, así que sin la
    guarda temporal tampoco se capturaba y el mutante sobrevivía. Hace falta una frase que lleve
    AMBAS cosas -marcador de hecho Y marca temporal-, como «hoy trabajo en casa»: describe un día,
    no una ocupación."""
    await _di(sistema.orquestador, frase)
    assert not await sistema.modelo_usuario.ver("mauricio"), f"{frase!r} se promovió pese a la marca temporal"


@pytest.mark.asyncio
async def test_H4_un_hecho_que_menciona_a_un_tercero_no_se_captura(sistema):
    """MUTANTE VIVO H4. Las frases de P12 no llevaban marcador de hecho, así que la guarda de
    terceros no se estaba ejercitando. «Trabajo en la empresa de mi hermana» sí lleva los dos: es
    una declaración sobre el usuario que MENCIONA a un tercero, y ante la mezcla no se captura
    (ALERTA-002)."""
    await _di(sistema.orquestador, "Trabajo en la empresa de mi hermana")
    assert not await sistema.modelo_usuario.ver("mauricio"), "capturó una frase que menciona a un tercero"


@pytest.mark.asyncio
async def test_H9_un_hecho_refutado_deja_de_recuperarse(sistema):
    """MUTANTE VIVO H9. La recuperación leía `vivas`, pero nada lo comprobaba: leyendo `entradas`
    -refutadas incluidas- AURORA seguiría afirmando un dato que el usuario ya corrigió (ADR-0017 §2,
    regla 5 del acta)."""
    await _di(sistema.orquestador, "Trabajo en logística")
    assert await sistema.modelo_usuario.refutar("mauricio", "logística") == 1

    r = await _di(sistema.orquestador, "¿Qué trabajo hago?")
    assert r["provider"] == "core"
    assert "logística" not in r["say"], f"siguió afirmando un hecho refutado: {r['say']!r}"
    assert r["say"] == "Todavía no me has dicho en qué trabajas."


@pytest.mark.asyncio
async def test_H10_sin_el_dato_declarado_se_declara_la_ausencia_exacta(sistema):
    """MUTANTE VIVO H10 (INV-9). Con el nombre declarado pero NO la ocupación, el mutante respondía
    «Trabajas en Mi nombre es Mauricio»: rellenaba la plantilla con la primera entrada que hubiera.
    No contenía «logística», así que el control negativo anterior lo dejaba pasar. Se fija el texto
    EXACTO de la ausencia."""
    await _di(sistema.orquestador, "Mi nombre es Mauricio")
    r = await _di(sistema.orquestador, "¿Qué trabajo hago?")
    assert r["say"] == "Todavía no me has dicho en qué trabajas.", f"fabricó una ocupación: {r['say']!r}"
