"""La voz es periférica: si falla, el turno sobrevive — MISIÓN VOZ (CEO, 2026-09-15).

DEFECTO MEDIDO. `_finalizar_turno` llamaba a `voice.tts(visible, tid)` ANTES de fijar
`self._results[tid]` y de `self._done[tid].set()`. Un fallo del sintetizador —modelo ausente, USB
desmontada, Piper caído— tumbaba el turno ENTERO: la respuesta ya calculada se perdía y el turno
quedaba sin resultado. Lo mismo en `handle_utterance` con `voice.stt`, que además ocurre ANTES de que
el Core vea nada. Medido en HC-1 el 2026-09-10: tres turnos reales, cero completados, y el `say` —hasta
seis minutos de inferencia— descartado.

LO QUE LA DECISIÓN EXIGE (§5 de la misión): la respuesta cognitiva NO se pierde porque el TTS falle.
Conservar el texto, registrar el fallo, terminar el turno, dejarlo observable, permitir recuperación en
el turno siguiente. Y no convertir un fallo de voz en una falsa indisponibilidad del modelo.

FRONTERA DE AUTORIDAD (§6). STT transforma audio en texto y NO decide nada: si falla, el Core lo dice
por sí mismo, sin llamar al modelo y sin inventar una transcripción. Un adaptador periférico no puede
inyectar hechos ni ganar autoridad por la puerta de atrás.

Todas las pruebas usan la COMPOSICIÓN REAL y un doble de voz que cuenta llamadas y falla a voluntad.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estatus import Estatus

UID = "mauricio"
# Pregunta que responde el CORE de forma determinista: aísla el fallo de voz de la ruta del modelo.
SALUDO = "hola"
HECHO = "me llamo Mauricio"


class _VozDoble:
    """Doble de `VoiceAdapter` que registra lo que se le pide y falla donde se le indique."""

    name = "voice"
    capabilities = ["stt", "tts"]

    def __init__(self, falla_tts: bool = False, falla_stt: bool = False) -> None:
        self.falla_tts = falla_tts
        self.falla_stt = falla_stt
        self.dicho: list[str] = []
        self.oido: list[str] = []

    async def stt(self, audio_ref: str, trace_id: str) -> str:
        self.oido.append(audio_ref)
        if self.falla_stt:
            raise RuntimeError("whisper: modelo no disponible (USB desmontada)")
        return audio_ref

    async def tts(self, text: str, trace_id: str) -> str:
        self.dicho.append(text)
        if self.falla_tts:
            raise RuntimeError("piper: no such file or directory: ''")
        return f"/tmp/aura/resp_{trace_id}.wav"


class _EspiaProveedor:
    name = "espia"

    def __init__(self) -> None:
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return '{"intent":"x","action":"consulta","args":{},"say":"respuesta del modelo"}'


def _sistema(tmp_path, voz: _VozDoble):
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    s = componer(config)
    s.orquestador.voice = voz
    espia = _EspiaProveedor()
    s.orquestador.router.providers = [espia]
    return s, espia


async def _turno(orq, texto: str, timeout: float = 5) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, texto, tid)
    return await orq.wait(tid, timeout=timeout)


# ============================================================== TTS: DEGRADACIÓN HONESTA --


@pytest.mark.asyncio
async def test_un_fallo_de_TTS_conserva_la_respuesta_textual(tmp_path):
    """La parte cara del turno ya está pagada cuando habla el sintetizador. No se tira."""
    voz = _VozDoble(falla_tts=True)
    s, _ = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, SALUDO)
    assert r is not None, "el turno se perdió entero por un fallo del sintetizador"
    assert r["say"].strip(), "la respuesta textual desapareció"
    assert voz.dicho, "ni siquiera se intentó sintetizar"


@pytest.mark.asyncio
async def test_un_fallo_de_TTS_deja_el_fallo_observable(tmp_path):
    """Degradar en silencio roza INV-9: quien lea el turno debe poder ver que no hubo voz."""
    voz = _VozDoble(falla_tts=True)
    s, _ = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, SALUDO)
    assert r["voz"] == "no_disponible", r


@pytest.mark.asyncio
async def test_CONTROL_con_voz_sana_el_turno_declara_voz_emitida(tmp_path):
    voz = _VozDoble()
    s, _ = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, SALUDO)
    assert r["voz"] == "ok", r
    assert voz.dicho[-1] == r["say"], "se sintetizó algo distinto de lo que se entregó"


@pytest.mark.asyncio
async def test_un_fallo_de_TTS_no_se_disfraza_de_modelo_no_disponible(tmp_path):
    """Un sintetizador roto no es un modelo caído: el estatus y el dominio no deben mentir."""
    voz = _VozDoble(falla_tts=True)
    s, _ = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, SALUDO)
    assert "no está disponible" not in r["say"], r["say"]
    assert r["provider"] == "core" and r["estatus"] == Estatus.HECHO.value, r


@pytest.mark.asyncio
async def test_tras_un_fallo_de_TTS_el_siguiente_turno_vuelve_a_hablar(tmp_path):
    """Recuperación: el fallo de voz no bloquea nada de forma permanente."""
    voz = _VozDoble(falla_tts=True)
    s, _ = _sistema(tmp_path, voz)
    primero = await _turno(s.orquestador, SALUDO)
    assert primero["voz"] == "no_disponible"
    voz.falla_tts = False
    segundo = await _turno(s.orquestador, SALUDO)
    assert segundo["voz"] == "ok", "la voz quedó bloqueada tras un fallo puntual"


@pytest.mark.asyncio
async def test_un_fallo_de_TTS_no_impide_que_el_Core_registre_el_hecho(tmp_path):
    """La memoria es del Core y se escribe antes de hablar: la voz no puede costarle un recuerdo."""
    voz = _VozDoble(falla_tts=True)
    s, _ = _sistema(tmp_path, voz)
    await _turno(s.orquestador, HECHO)
    assert await s.modelo_usuario.ver(UID) != [], "el hecho declarado se perdió por un fallo de voz"


@pytest.mark.asyncio
async def test_un_fallo_de_TTS_en_la_ruta_del_modelo_tampoco_pierde_la_respuesta(tmp_path):
    """La ruta cara —la que llama al proveedor— es justamente la que más daño sufría."""
    voz = _VozDoble(falla_tts=True)
    s, espia = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, "¿por qué el cielo es azul?")
    assert espia.llamadas == 1, "la prueba no ejercitó la ruta del modelo"
    assert "respuesta del modelo" in r["say"], r
    assert r["voz"] == "no_disponible", r


# ===================================================================== STT: SIN INVENTAR --


@pytest.mark.asyncio
async def test_un_fallo_de_STT_no_destruye_el_turno_y_lo_dice(tmp_path):
    voz = _VozDoble(falla_stt=True)
    s, _ = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, "/tmp/aura/entrada.wav")
    assert r is not None, "un fallo de transcripción dejó el turno sin resultado"
    assert r["provider"] == "core" and r["estatus"] == Estatus.ABSTENCION.value, r
    assert r["dominio"] == "voz", r
    assert "transcribir" in r["say"] or "entender" in r["say"], r["say"]


@pytest.mark.asyncio
async def test_un_fallo_de_STT_no_fabrica_texto_ni_consulta_al_modelo(tmp_path):
    """Sin transcripción no hay nada que el usuario haya dicho: ni memoria, ni LLM, ni hechos."""
    voz = _VozDoble(falla_stt=True)
    s, espia = _sistema(tmp_path, voz)
    await _turno(s.orquestador, "/tmp/aura/entrada.wav")
    assert espia.llamadas == 0, "se consultó al modelo sin saber qué dijo el usuario"
    assert await s.orquestador.memory.recall(UID, "entrada") == [], "se registró un turno inexistente"


@pytest.mark.asyncio
async def test_tras_un_fallo_de_STT_el_siguiente_turno_funciona(tmp_path):
    voz = _VozDoble(falla_stt=True)
    s, _ = _sistema(tmp_path, voz)
    await _turno(s.orquestador, "/tmp/aura/entrada.wav")
    voz.falla_stt = False
    r = await _turno(s.orquestador, SALUDO)
    assert r["say"].strip() and r["provider"] == "core", r


@pytest.mark.asyncio
async def test_CONTROL_el_texto_transcrito_llega_al_Core_y_es_el_Core_quien_decide(tmp_path):
    """La autoridad no cambia por venir de un micrófono: el mismo texto sigue el mismo camino."""
    voz = _VozDoble()
    s, espia = _sistema(tmp_path, voz)
    r = await _turno(s.orquestador, HECHO)
    assert voz.oido == [HECHO], "el Core no recibió lo transcrito"
    assert espia.llamadas == 0, "un hecho declarado lo resuelve el Core, no el modelo"
    assert await s.modelo_usuario.ver(UID) != [], r


# ================================================ EL ARRANQUE NO ANUNCIA LO QUE NO TIENE --


def _boot_espiado(monkeypatch) -> list[str]:
    """Registra lo que el arranque DICE. Se espia `obs.log` porque es el canal auditado del sistema."""
    from aura_skeleton import observability as obs

    dicho: list[str] = []
    real = obs.log
    monkeypatch.setattr(obs, "log", lambda *a, **k: (dicho.append(" ".join(str(x) for x in a)), real(*a, **k))[0])
    return dicho


def _sin_ollama_real(monkeypatch) -> list[str]:
    """Catalogo de Ollama FALSO y contado (2026-10-25).

    Componer con `usar_stack_real=True` consulta `GET /api/tags` en 127.0.0.1:11434. Medido con una traza de
    `connect()`: estas dos pruebas hablaban con el Ollama REAL del equipo, y su resultado dependia de que
    estuviera vivo. Mismo mecanismo que `test_composicion_motor_de_voz`. Se devuelven las URLs pedidas:
    la prueba exige que el catalogo se haya pedido AL DOBLE, asi que quitar el doble la rompe.
    """
    import json
    import urllib.request

    pedidas: list[str] = []

    class _Respuesta:
        def read(self) -> bytes:
            return json.dumps({"models": []}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

    def _urlopen(req, timeout=None):
        pedidas.append(getattr(req, "full_url", str(req)))
        return _Respuesta()

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    return pedidas


def test_el_arranque_declara_que_NO_hay_voz_cuando_no_la_hay(tmp_path, monkeypatch):
    """INV-9: «AURA lista: 21 capacidades, stack=real» no puede incluir una voz inexistente."""
    monkeypatch.setenv("AURA_PIPER_VOICE", "")
    pedidas = _sin_ollama_real(monkeypatch)
    dicho = _boot_espiado(monkeypatch)
    componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=True))
    assert any("voz: NO DISPONIBLE" in linea for linea in dicho), dicho
    assert pedidas and all(u.endswith("/api/tags") for u in pedidas), "el catalogo no se pidio al doble"


def test_CONTROL_el_arranque_declara_la_voz_cuando_existe(tmp_path, monkeypatch):
    onnx = tmp_path / "voz.onnx"
    onnx.write_bytes(b"onnx")
    (tmp_path / "voz.onnx.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AURA_PIPER_VOICE", str(onnx))
    pedidas = _sin_ollama_real(monkeypatch)
    dicho = _boot_espiado(monkeypatch)
    componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=True))
    assert any(f"voz: DISPONIBLE ({onnx})" in linea for linea in dicho), dicho
    assert pedidas and all(u.endswith("/api/tags") for u in pedidas), "el catalogo no se pidio al doble"


@pytest.mark.asyncio
async def test_un_turno_sin_transcripcion_no_ensucia_el_contexto(tmp_path):
    """Hallazgo de la auditoría (2026-09-15): el turno fallido entraba en el buffer de diálogo.

    `destino_de_memoria("")` ya impedía persistirlo, pero la memoria de trabajo sí lo recibía y volvía
    al prompt como un «Usuario:» vacío en los turnos siguientes.
    """
    voz = _VozDoble(falla_stt=True)
    s, _ = _sistema(tmp_path, voz)
    await _turno(s.orquestador, "/tmp/aura/entrada.wav")
    buffer = s.orquestador._dialogue.get(UID, [])
    assert all(t.usuario.strip() for t in buffer), f"un turno sin texto de usuario entró al contexto: {buffer}"


@pytest.mark.asyncio
async def test_CONTROL_un_turno_con_texto_si_entra_en_el_contexto(tmp_path):
    voz = _VozDoble()
    s, _ = _sistema(tmp_path, voz)
    await _turno(s.orquestador, SALUDO)
    buffer = s.orquestador._dialogue.get(UID, [])
    assert [t.usuario for t in buffer] == [SALUDO], buffer
