"""El arranque dice QUÉ MODELO va a usar y si lo tiene — INV-9 (2026-09-15).

DEFECTO MEDIDO. El valor por defecto de `Configuracion.modelo` es `qwen2.5:3b`; el único modelo instalado
en HC-1 es `qwen2.5:0.5b`. Arrancando con `AURA_STACK_REAL=1` y sin `AURA_LLM_MODEL`, AURA anunciaba:

    [BOOT] proveedor LLM: stack=real timeout=900s …
    [BOOT] AURA lista: 21 capacidades, 3 fuentes de contexto, stack=real

y en el primer turno cognitivo recibía `HTTP Error 404`, **abría el circuito** y contestaba
*«Mi modelo local no está disponible ahora mismo; inténtalo de nuevo en unos minutos»*.

Esa frase es falsa dos veces: el modelo local **sí** está disponible —otro—, y no es un problema
transitorio que se arregle «en unos minutos», sino una configuración que no se arreglará sola. Es el
patrón «declarado ≠ real» que este proyecto ha pagado ocho veces, y el mismo que la MISIÓN VOZ corrigió
para el sintetizador: el arranque anunciaba una capacidad sin comprobar si podía ejercerla.

LO QUE SE FIJA AQUÍ: el arranque declara el modelo y avisa si no está instalado. **No cambia el modelo**,
no descarga, no instala y no toca el catálogo de Ollama: solo mira `/api/tags` y dice la verdad.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from aura_skeleton.composicion import Configuracion, componer

MODELO_PRESENTE = "qwen2.5:0.5b"
MODELO_AUSENTE = "qwen2.5:3b"


class _Respuesta:
    def __init__(self, payload: dict) -> None:
        self._cuerpo = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def _ollama_falso(monkeypatch, modelos: list[str] | BaseException):
    """`urlopen` falso que responde a /api/tags. Devuelve las peticiones vistas."""
    vistas: list[dict] = []

    def _urlopen(req, timeout=None):
        vistas.append({"url": req.full_url, "metodo": req.get_method(), "timeout": timeout, "datos": req.data})
        if isinstance(modelos, BaseException):
            raise modelos
        return _Respuesta({"models": [{"name": m} for m in modelos]})

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    return vistas


def _boot_espiado(monkeypatch) -> list[str]:
    from aura_skeleton import observability as obs

    dicho: list[str] = []
    real = obs.log
    monkeypatch.setattr(obs, "log", lambda *a, **k: (dicho.append(" ".join(str(x) for x in a)), real(*a, **k))[0])
    return dicho


def _arrancar(tmp_path, monkeypatch, modelo: str):
    monkeypatch.setenv("AURA_LLM_MODEL", modelo)
    monkeypatch.setenv("AURA_PIPER_VOICE", "")
    dicho = _boot_espiado(monkeypatch)
    componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=True))
    return [linea for linea in dicho if "proveedor LLM" in linea]


# ==================================================== EL ARRANQUE DICE QUÉ MODELO USA --


def test_el_arranque_declara_el_modelo_que_va_a_usar(tmp_path, monkeypatch):
    _ollama_falso(monkeypatch, [MODELO_PRESENTE])
    lineas = _arrancar(tmp_path, monkeypatch, MODELO_PRESENTE)
    assert lineas, "el arranque no declaró nada sobre el proveedor"
    assert MODELO_PRESENTE in lineas[0], f"el arranque no dice qué modelo usa: {lineas[0]}"


def test_el_arranque_avisa_si_el_modelo_declarado_no_esta_instalado(tmp_path, monkeypatch):
    """El caso real de HC-1: se pide `qwen2.5:3b` y lo instalado es `qwen2.5:0.5b`."""
    _ollama_falso(monkeypatch, [MODELO_PRESENTE])
    lineas = _arrancar(tmp_path, monkeypatch, MODELO_AUSENTE)
    texto = lineas[0]
    assert "NO INSTALADO" in texto, f"el arranque no avisa de que el modelo falta: {texto}"
    assert MODELO_PRESENTE in texto, f"no dice qué hay instalado en su lugar: {texto}"


def test_CONTROL_con_el_modelo_instalado_no_hay_aviso(tmp_path, monkeypatch):
    _ollama_falso(monkeypatch, [MODELO_PRESENTE, "otro:1b"])
    texto = _arrancar(tmp_path, monkeypatch, MODELO_PRESENTE)[0]
    assert "NO INSTALADO" not in texto, texto


# ============================================== LA COMPROBACIÓN NO PUEDE HACER DAÑO --


def test_la_comprobacion_solo_consulta_el_catalogo_y_no_descarga_nada(tmp_path, monkeypatch):
    """D24: local-first. Mirar qué hay instalado no puede convertirse en instalarlo."""
    vistas = _ollama_falso(monkeypatch, [MODELO_PRESENTE])
    _arrancar(tmp_path, monkeypatch, MODELO_AUSENTE)
    assert vistas, "no se consultó el catálogo"
    for v in vistas:
        assert v["url"].endswith("/api/tags"), f"el arranque llamó a otra cosa: {v['url']}"
        assert v["metodo"] == "GET" and v["datos"] is None, f"petición con efectos: {v}"


def test_el_arranque_no_se_cae_si_ollama_no_responde(tmp_path, monkeypatch):
    """Degradación honesta, igual que con la voz: no saber no puede impedir arrancar."""
    _ollama_falso(monkeypatch, urllib.error.URLError("connection refused"))
    texto = _arrancar(tmp_path, monkeypatch, MODELO_PRESENTE)[0]
    assert MODELO_PRESENTE in texto, texto
    assert "no responde" in texto.lower() or "sin comprobar" in texto.lower(), texto


def test_la_comprobacion_lleva_un_tope_de_espera(tmp_path, monkeypatch):
    """Un Ollama colgado no puede colgar el arranque de AURA."""
    vistas = _ollama_falso(monkeypatch, [MODELO_PRESENTE])
    _arrancar(tmp_path, monkeypatch, MODELO_PRESENTE)
    assert all(v["timeout"] for v in vistas), f"consulta sin timeout: {vistas}"
    assert all(v["timeout"] <= 5 for v in vistas), f"tope demasiado largo para un arranque: {vistas}"


def test_el_stack_mock_no_consulta_a_ollama(tmp_path, monkeypatch):
    """Sin stack real no hay proveedor real: preguntar por su catálogo no tendría sentido."""
    vistas = _ollama_falso(monkeypatch, [MODELO_PRESENTE])
    monkeypatch.setenv("AURA_PIPER_VOICE", "")
    componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False))
    assert vistas == [], f"el arranque en mock consultó a Ollama: {vistas}"


@pytest.mark.asyncio
async def test_el_aviso_no_cambia_el_modelo_ni_el_comportamiento_del_turno(tmp_path, monkeypatch):
    """INV-7 / §14 de la misión: se hace VISIBLE la discrepancia; no se corrige por cuenta propia."""
    _ollama_falso(monkeypatch, [MODELO_PRESENTE])
    monkeypatch.setenv("AURA_LLM_MODEL", MODELO_AUSENTE)
    monkeypatch.setenv("AURA_PIPER_VOICE", "")
    s = componer(Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=True))
    assert s.orquestador.router.providers[0].model == MODELO_AUSENTE, "el arranque cambió el modelo por su cuenta"
