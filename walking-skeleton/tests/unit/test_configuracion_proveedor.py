"""Unit: timeout y enfriamiento del proveedor LLM DECLARADOS en `Configuracion` (D-FC-7).

## El defecto medido

El timeout efectivo de `OllamaProvider` era 900s (por `AURA_OLLAMA_TIMEOUT_S="900"` en el
`~/.profile` del usuario) mientras `Configuracion` no declaraba ese valor en absoluto y
`--verificar` no lo mostraba: el numero que corria y el numero que el operador podia ver eran dos
cosas distintas. Esta bateria prueba que `Configuracion` hace visible y reproducible ese valor (y el
del enfriamiento del circuito) SIN tocar el numero de defecto de `OllamaProvider` (180, D-FC-7).

Nada aqui llama a Ollama de verdad ni importa `voice_real`: el paso del timeout al proveedor real se
verifica por INSPECCION del codigo fuente de `componer()`, tal como ya hace el resto del proyecto
para invariantes que no conviene ejercitar con un proceso real (ver
`test_una_respuesta_cognitiva_NO_se_convierte_en_memoria` en `test_contrato_cognitivo.py`).
"""

import inspect

import pytest

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.modules.providers_real import OllamaProvider

# --------------------------------------------------------------- fuente: entorno vs defecto --


def test_timeout_proveedor_usa_el_defecto_del_codigo_sin_variable_de_entorno(monkeypatch):
    monkeypatch.delenv("AURA_OLLAMA_TIMEOUT_S", raising=False)
    config = Configuracion()
    assert config.timeout_proveedor_s == OllamaProvider.DEFAULT_TIMEOUT_S
    assert config.fuente_timeout_proveedor == "defecto_del_codigo"


def test_timeout_proveedor_lee_la_variable_de_entorno_cuando_esta(monkeypatch):
    monkeypatch.setenv("AURA_OLLAMA_TIMEOUT_S", "45")
    config = Configuracion()
    assert config.timeout_proveedor_s == 45
    assert config.fuente_timeout_proveedor == "entorno:AURA_OLLAMA_TIMEOUT_S"


def test_enfriamiento_circuito_usa_el_defecto_del_codigo_sin_variable_de_entorno(monkeypatch):
    monkeypatch.delenv("AURA_CIRCUITO_ENFRIAMIENTO_S", raising=False)
    config = Configuracion()
    assert config.enfriamiento_circuito_s == 60.0
    assert config.fuente_enfriamiento_circuito == "defecto_del_codigo"


def test_enfriamiento_circuito_lee_la_variable_de_entorno_cuando_esta(monkeypatch):
    monkeypatch.setenv("AURA_CIRCUITO_ENFRIAMIENTO_S", "12.5")
    config = Configuracion()
    assert config.enfriamiento_circuito_s == 12.5
    assert config.fuente_enfriamiento_circuito == "entorno:AURA_CIRCUITO_ENFRIAMIENTO_S"


# ------------------------------------------------------------------ valor invalido => error --


@pytest.mark.parametrize("crudo", ["no-es-un-numero", "", "1.5.5"])
def test_timeout_proveedor_invalido_falla_explicito(monkeypatch, crudo):
    monkeypatch.setenv("AURA_OLLAMA_TIMEOUT_S", crudo)
    with pytest.raises(ValueError, match="AURA_OLLAMA_TIMEOUT_S"):
        Configuracion()


def test_timeout_proveedor_negativo_o_cero_falla_explicito(monkeypatch):
    monkeypatch.setenv("AURA_OLLAMA_TIMEOUT_S", "0")
    with pytest.raises(ValueError, match="AURA_OLLAMA_TIMEOUT_S"):
        Configuracion()


@pytest.mark.parametrize("crudo", ["no-es-un-numero", ""])
def test_enfriamiento_circuito_invalido_falla_explicito(monkeypatch, crudo):
    monkeypatch.setenv("AURA_CIRCUITO_ENFRIAMIENTO_S", crudo)
    with pytest.raises(ValueError, match="AURA_CIRCUITO_ENFRIAMIENTO_S"):
        Configuracion()


def test_enfriamiento_circuito_negativo_falla_explicito(monkeypatch):
    monkeypatch.setenv("AURA_CIRCUITO_ENFRIAMIENTO_S", "-1")
    with pytest.raises(ValueError, match="AURA_CIRCUITO_ENFRIAMIENTO_S"):
        Configuracion()


# --------------------------------------------------------- componer() pasa el timeout explicito --


def test_componer_pasa_el_timeout_y_el_enfriamiento_explicitos_al_proveedor_real():
    """No se ejercita la rama `usar_stack_real=True` (importaria `voice_real` y necesitaria Ollama
    corriendo): se inspecciona el FUENTE de `componer()` para comprobar que el timeout declarado en
    `Configuracion` -- no una segunda lectura de `os.getenv` -- es el que llega a `OllamaProvider`,
    y que el enfriamiento declarado llega al `ModelRouter`."""
    fuente = inspect.getsource(componer)
    assert 'OllamaProvider("ollama", config.modelo, timeout_s=config.timeout_proveedor_s)' in fuente
    assert "enfriamiento_s=config.enfriamiento_circuito_s" in fuente


def test_componer_con_stack_mock_no_construye_ollama_ni_necesita_variables_de_entorno(tmp_path, monkeypatch):
    """Construccion DIRECTA (sin mockear nada): con `usar_stack_real=False` el sistema se arma
    completo sin tocar Ollama, y el timeout/enfriamiento declarados quedan expuestos en `config`."""
    monkeypatch.setenv("AURA_OLLAMA_TIMEOUT_S", "37")
    monkeypatch.setenv("AURA_CIRCUITO_ENFRIAMIENTO_S", "8")
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    sistema = componer(config)

    assert sistema.config.timeout_proveedor_s == 37
    assert sistema.config.fuente_timeout_proveedor == "entorno:AURA_OLLAMA_TIMEOUT_S"
    assert sistema.config.enfriamiento_circuito_s == 8.0
    # El router construido de verdad recibio el enfriamiento declarado (no el defecto de la clase).
    assert sistema.orquestador.router._enfriamiento_s == 8.0


# ------------------------------------------------------------------------------- el informe --


def test_el_informe_contiene_el_timeout_y_su_fuente(tmp_path, monkeypatch):
    from aura_skeleton.__main__ import _informe

    monkeypatch.setenv("AURA_OLLAMA_TIMEOUT_S", "77")
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    sistema = componer(config)

    texto = _informe(sistema)
    assert "77" in texto
    assert "entorno:AURA_OLLAMA_TIMEOUT_S" in texto
    assert "estado circuitos" in texto.lower()
    assert "mock" in texto.lower()


def test_el_informe_avisa_si_el_timeout_del_proveedor_supera_el_de_la_conversacion(tmp_path, monkeypatch):
    from aura_skeleton.__main__ import _TIMEOUT_TURNO_S, _informe

    monkeypatch.setenv("AURA_OLLAMA_TIMEOUT_S", str(_TIMEOUT_TURNO_S + 100))
    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    sistema = componer(config)

    texto = _informe(sistema)
    assert "SUPERA" in texto


# ------------------------------------------------------------------------- D-FC-6: el acuse --


class _OrquestadorLento:
    """No llama a Ollama ni a nada real: simula un turno que tarda mas que el primer tramo."""

    def __init__(self, en_modelo: bool = True) -> None:
        self._llamadas_wait = []
        self._en_modelo = en_modelo

    async def handle_utterance(self, user_id, texto, trace_id):
        return None

    async def wait(self, trace_id, timeout):
        self._llamadas_wait.append(timeout)
        if len(self._llamadas_wait) == 1:
            raise TimeoutError("simulado: el turno aun no termino")
        return {"say": "hola de vuelta"}

    def turno_en_modelo(self, trace_id) -> bool:
        return self._en_modelo


@pytest.mark.asyncio
async def test_esperar_con_acuse_avisa_consultando_modelo_local_cuando_el_orquestador_lo_confirma():
    from aura_skeleton.__main__ import _ACUSE_TRAMO_S, _TIMEOUT_TURNO_S, _esperar_con_acuse

    orquestador = _OrquestadorLento(en_modelo=True)
    resultado = await _esperar_con_acuse(orquestador, "t1")

    assert resultado == {"say": "hola de vuelta"}
    assert orquestador._llamadas_wait == [_ACUSE_TRAMO_S, _TIMEOUT_TURNO_S - _ACUSE_TRAMO_S]


@pytest.mark.asyncio
async def test_esperar_con_acuse_usa_mensaje_generico_sin_turno_en_modelo(capsys):
    from aura_skeleton.__main__ import _esperar_con_acuse

    class _SinSenal:
        def __init__(self):
            self._n = 0

        async def wait(self, trace_id, timeout):
            self._n += 1
            if self._n == 1:
                raise TimeoutError()
            return {"say": "ok"}

    resultado = await _esperar_con_acuse(_SinSenal(), "t2")
    assert resultado == {"say": "ok"}
    salida = capsys.readouterr().out
    assert "sigo trabajando" in salida


@pytest.mark.asyncio
async def test_esperar_con_acuse_imprime_el_texto_de_consulta_al_modelo_local(capsys):
    from aura_skeleton.__main__ import _esperar_con_acuse

    resultado = await _esperar_con_acuse(_OrquestadorLento(en_modelo=True), "t3")
    assert resultado == {"say": "hola de vuelta"}
    salida = capsys.readouterr().out
    assert "consultando mi modelo local" in salida


@pytest.mark.asyncio
async def test_esperar_con_acuse_no_avisa_si_el_turno_termina_dentro_del_primer_tramo(capsys):
    """Caso de control: si el turno termina RAPIDO (dentro de `_ACUSE_TRAMO_S`), no se imprime
    ningun acuse -- de lo contrario la prueba anterior no demostraria nada sobre la lentitud."""
    from aura_skeleton.__main__ import _esperar_con_acuse

    class _Rapido:
        async def wait(self, trace_id, timeout):
            return {"say": "instantaneo"}

    resultado = await _esperar_con_acuse(_Rapido(), "t4")
    assert resultado == {"say": "instantaneo"}
    salida = capsys.readouterr().out
    assert salida == ""


@pytest.mark.asyncio
async def test_la_cli_conversar_muestra_el_acuse_de_espera(tmp_path, monkeypatch, capsys):
    """`_conversar` completo, con un `input()` falso y un orquestador lento -- sin construir un
    `Sistema` real (evita Ollama y voice_real): solo los atributos que `_conversar`/`_informe`
    leen."""
    import types

    from aura_skeleton.__main__ import _conversar

    config = Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False)
    orquestador = _OrquestadorLento(en_modelo=True)
    orquestador.router = types.SimpleNamespace(providers=[], estado_circuitos=lambda: {})
    sistema = types.SimpleNamespace(
        registro_adaptadores=types.SimpleNamespace(capacidades=lambda: {"a"}),
        registro_contexto=types.SimpleNamespace(fuentes={"conversacion"}),
        ruta_memoria=str(tmp_path / "memoria.json"),
        ruta_audit=str(tmp_path / "audit.jsonl"),
        kill_switch=types.SimpleNamespace(is_engaged=lambda: False),
        capacidades_activas_efectivas=(),
        materializaciones=(),
        config=config,
        orquestador=orquestador,
    )

    entradas = iter(["hola aura"])

    def _input_falso(prompt=""):
        try:
            return next(entradas)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", _input_falso)

    codigo = await _conversar(sistema)

    assert codigo == 0
    salida = capsys.readouterr().out
    assert "consultando mi modelo local" in salida
    assert "hola de vuelta" in salida
