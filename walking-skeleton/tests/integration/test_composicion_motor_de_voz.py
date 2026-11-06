"""`componer()` cablea el motor de voz elegido por el entorno (auditoría 2026-09-29, mutante M12).

Sin esta prueba, cambiar `sintetizador=_sintetizador_de_entorno(os.environ)` por `sintetizador=None`
dejaba pasar toda la batería: `AURA_TTS_MOTOR=espeak` se ignoraría SIN AVISO (el patrón de ALERTA-005:
la pieza existe y nadie la enciende). Aquí se compone el sistema REAL y se mira la voz que quedó.
"""

from __future__ import annotations

import json
import urllib.request

from aura_skeleton.adapters.tts_espeak import SintetizadorEspeak
from aura_skeleton.composicion import Configuracion, componer


class _Respuesta:
    def read(self) -> bytes:
        return json.dumps({"models": []}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def _componer(tmp_path, monkeypatch, motor: str | None):
    # Mismo mecanismo que `test_arranque_declara_el_modelo`: `urlopen` falso, sin Ollama ni red.
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Respuesta())
    monkeypatch.setenv("AURA_PIPER_VOICE", "")
    if motor is None:
        monkeypatch.delenv("AURA_TTS_MOTOR", raising=False)
    else:
        monkeypatch.setenv("AURA_TTS_MOTOR", motor)
    cfg = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=True)
    return componer(cfg).orquestador.voice


def test_con_AURA_TTS_MOTOR_espeak_la_voz_del_sistema_usa_espeak(tmp_path, monkeypatch):
    voz = _componer(tmp_path, monkeypatch, "espeak")
    assert isinstance(voz._sintetizador, SintetizadorEspeak)  # control: `sintetizador=None` lo rompe


def test_sin_la_variable_la_voz_del_sistema_sigue_siendo_piper(tmp_path, monkeypatch):
    voz = _componer(tmp_path, monkeypatch, None)
    assert voz._sintetizador is None


def test_un_motor_desconocido_deja_piper_y_lo_avisa(tmp_path, monkeypatch):
    from aura_skeleton import observability as obs

    antes = len(obs._records)
    voz = _componer(tmp_path, monkeypatch, "festival")
    assert voz._sintetizador is None
    assert any("festival" in r["msg"] for r in obs._records[antes:])
