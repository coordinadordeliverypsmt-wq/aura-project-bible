"""Una transcripción no es una declaración — DEFECTO REPRODUCIDO, corrección PENDIENTE DE DECISIÓN.

MEDIDO EN HC-1 EL 2026-09-15, con audio real y el stack real:

    audio del usuario : «¿Cómo me llamo?»        (una PREGUNTA)
    faster-whisper    : «Todo me llamo.»          (una AFIRMACIÓN)
    Core              : declaración de hecho propio
    memoria           : se guardó «Todo me llamo.»

El usuario nunca dijo eso. Un error de reconocimiento **creó un hecho**.

CAUSA, aislada por ejecución:

    es_declaracion_de_hecho_propio("¿Cómo me llamo?")  -> False   (correcto)
    es_declaracion_de_hecho_propio("Todo me llamo.")   -> True    (correcto para ESE texto)

El Core no se equivoca: acierta sobre el texto que recibe. El defecto está un paso antes — el texto
que recibe es una **hipótesis** del transcriptor y llega indistinguible de lo que el usuario teclea.
`VoiceAdapter.stt` devuelve `str`: el orquestador **no puede saber** si un turno vino por micrófono.

POR QUÉ ESTA PRUEBA NO ESTÁ CORREGIDA. Arreglarlo exige cambiar el contrato `VoiceAdapter` —para que
una transcripción viaje marcada como hipótesis— o el contrato de memoria. Ambos son cambios
arquitectónicos que corresponden al CEO, no al CTO (AMP-AURA: `EVIDENCE → PROPOSAL → VALIDATION →
ACTIVE FACT`; hoy la voz salta de EVIDENCE a ACTIVE FACT).

La marca es `xfail(strict=True)` **a propósito**: hoy falla, y el día que se implante la decisión
pasará y pytest lo reportará como XPASS. Es un recordatorio que no se puede ignorar en silencio.
"""

from __future__ import annotations

import uuid

import pytest

from aura_skeleton.composicion import Configuracion, componer

UID = "mauricio"
PREGUNTA_DICHA = "¿Cómo me llamo?"
LO_QUE_OYO = "Todo me llamo."  # la transcripción real que devolvió faster-whisper base


class _VozQueSeEquivoca:
    """Transcriptor determinista que reproduce el error medido: oye una pregunta, escribe una frase."""

    name = "voice"
    capabilities = ["stt", "tts"]

    def __init__(self) -> None:
        self.transcrito: list[str] = []

    async def stt(self, audio_ref: str, trace_id: str) -> str:
        if audio_ref.endswith(".wav"):
            self.transcrito.append(LO_QUE_OYO)
            return LO_QUE_OYO
        return audio_ref

    async def tts(self, text: str, trace_id: str) -> str:
        return "/tmp/aura/x.wav"


def _sistema(tmp_path):
    s = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False))
    voz = _VozQueSeEquivoca()
    s.orquestador.voice = voz
    return s, voz


async def _turno(orq, entrada: str) -> dict:
    tid = uuid.uuid4().hex[:12]
    await orq.handle_utterance(UID, entrada, tid)
    return await orq.wait(tid, timeout=10)


@pytest.mark.asyncio
async def test_la_causa_esta_en_el_texto_recibido_no_en_el_Core(tmp_path):
    """CONTROL del diagnóstico: el Core clasifica bien ambos textos. El fallo es de procedencia."""
    from aura_skeleton.conectores.conversacion import es_declaracion_de_hecho_propio

    assert es_declaracion_de_hecho_propio(PREGUNTA_DICHA) is False, "una pregunta no es declaración"
    assert es_declaracion_de_hecho_propio(LO_QUE_OYO) is True, "para ESE texto, clasificar así es correcto"


@pytest.mark.asyncio
async def test_CONTROL_la_misma_pregunta_por_TECLADO_no_escribe_memoria(tmp_path):
    """Por texto directo el sistema se comporta bien: la pregunta no deja hecho."""
    s, _ = _sistema(tmp_path)
    await _turno(s.orquestador, PREGUNTA_DICHA)
    assert await s.modelo_usuario.ver(UID) == [], "una pregunta tecleada no puede crear un hecho"


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    reason="DECISION_REQUIRED (CEO): una transcripción es una hipótesis y hoy entra como hecho. "
    "Corregirlo cambia el contrato de VoiceAdapter o el de memoria.",
)
async def test_una_transcripcion_erronea_NO_debe_crear_un_hecho(tmp_path):
    """Lo que DEBE ocurrir. Hoy no ocurre: por eso está marcado xfail estricto."""
    s, voz = _sistema(tmp_path)
    await _turno(s.orquestador, "/tmp/aura/pregunta.wav")
    assert voz.transcrito == [LO_QUE_OYO], "la prueba no ejercitó la ruta de voz"
    assert await s.modelo_usuario.ver(UID) == [], "un error de transcripción creó un hecho que el usuario nunca declaró"
