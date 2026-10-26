"""El stack real se pide, no se hereda — y el modelo efectivo no vive en el repositorio.

POR QUÉ EXISTE ESTA PRUEBA. Una medición del 2026-09-20 encontró dos cosas que el proyecto daba por
sabidas y ninguna prueba sostenía:

1. **Que el arranque por defecto sea `mock` es una GARANTÍA, no una casualidad.** Está decidido y
   medido: `qwen2.5:0.5b` tardó 25,8 s en responder «Hola» contra un presupuesto declarado de
   1200 ms, y en esta misma máquina un turno cognitivo real midió **94,24 s**. Por eso el stack real
   es opt-in. Si alguien invirtiera el defecto, AURA pasaría a arrancar 78× por encima de su
   presupuesto sin que nada fallara: exactamente el tipo de cambio que hay que hacer a propósito.

2. **El modelo efectivo NO es derivable del repositorio.** El defecto en código es `qwen2.5:3b`;
   la máquina HC-1 exporta `AURA_LLM_MODEL=qwen2.5:0.5b` desde `~/.profile` —dos veces—, que es el
   único instalado. Leer solo el código lleva a una conclusión falsa sobre qué modelo corre. Es el
   patrón «declarado != real» con el signo invertido: aquí lo declarado es lo que NO se usa.

QUÉ NO HACE ESTA PRUEBA. No cambia el defecto, no descarga nada, no toca el modelo y no decide cuál
debería ser. Solo **fija el contrato vigente y hace visible la divergencia**, para que corregirla —o
no— sea una decisión y no un descubrimiento. Esa decisión es del CEO.

Las pruebas limpian el entorno con `monkeypatch.delenv`: si leyeran el entorno real medirían la
máquina de quien las ejecuta, no el contrato del código, y pasarían o fallarían por el motivo
equivocado.
"""

from __future__ import annotations

import pytest

from aura_skeleton.composicion import Configuracion

#: El defecto escrito en el código, hoy. No es una recomendación: es lo que hay.
MODELO_POR_DEFECTO_EN_CODIGO = "qwen2.5:3b"

#: Lo que exige el interruptor. Exactamente la cadena "1", nada más.
VALOR_QUE_ENCIENDE_EL_STACK_REAL = "1"


def _config(tmp_path) -> Configuracion:
    return Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),))


def _entorno_limpio(monkeypatch) -> None:
    monkeypatch.delenv("AURA_STACK_REAL", raising=False)
    monkeypatch.delenv("AURA_LLM_MODEL", raising=False)


# ===================================================== EL STACK SE PIDE --


def test_sin_pedirlo_el_stack_es_MOCK(tmp_path, monkeypatch):
    """El defecto es local-first y barato: nadie acaba llamando a un modelo por descuido."""
    _entorno_limpio(monkeypatch)
    assert _config(tmp_path).usar_stack_real is False


def test_con_AURA_STACK_REAL_1_el_stack_es_REAL(tmp_path, monkeypatch):
    _entorno_limpio(monkeypatch)
    monkeypatch.setenv("AURA_STACK_REAL", VALOR_QUE_ENCIENDE_EL_STACK_REAL)
    assert _config(tmp_path).usar_stack_real is True


@pytest.mark.parametrize("valor", ["", "0", "true", "True", "si", "yes", "2", " 1", "1 "])
def test_cualquier_otro_valor_NO_enciende_el_stack_real(tmp_path, monkeypatch, valor):
    """La comparación es de igualdad exacta, y eso es deliberado.

    Un interruptor que acepta «true», «yes» o «1 » con un espacio es un interruptor que alguien
    enciende sin querer. El caso `" 1"` no es rebuscado: es lo que produce un `export` mal copiado.
    """
    _entorno_limpio(monkeypatch)
    monkeypatch.setenv("AURA_STACK_REAL", valor)
    assert _config(tmp_path).usar_stack_real is False, f"{valor!r} encendio el stack real"


# ===================================================== EL MODELO EFECTIVO --


def test_el_defecto_del_modelo_vive_en_el_CODIGO_y_hoy_es_el_3b(tmp_path, monkeypatch):
    """Fija el valor real del defecto. Si alguien lo cambia, que sea un acto, no un efecto lateral."""
    _entorno_limpio(monkeypatch)
    assert _config(tmp_path).modelo == MODELO_POR_DEFECTO_EN_CODIGO


def test_el_entorno_GANA_al_defecto_del_codigo(tmp_path, monkeypatch):
    """La divergencia medida en HC-1, hecha explícita: el entorno decide, el código solo propone."""
    _entorno_limpio(monkeypatch)
    monkeypatch.setenv("AURA_LLM_MODEL", "qwen2.5:0.5b")
    config = _config(tmp_path)

    assert config.modelo == "qwen2.5:0.5b"
    assert config.modelo != MODELO_POR_DEFECTO_EN_CODIGO, (
        "esta prueba solo dice algo si los dos valores difieren; si coinciden, no mide nada"
    )


def test_el_modelo_y_el_stack_son_interruptores_INDEPENDIENTES(tmp_path, monkeypatch):
    """Nombrar un modelo no enciende el stack real: son dos decisiones distintas.

    Sin esta separación, exportar `AURA_LLM_MODEL` para documentar qué modelo hay instalado
    arrancaría el stack real de rebote — que es justo lo que el opt-in quiere evitar.
    """
    _entorno_limpio(monkeypatch)
    monkeypatch.setenv("AURA_LLM_MODEL", "qwen2.5:0.5b")

    config = _config(tmp_path)

    assert config.modelo == "qwen2.5:0.5b"
    assert config.usar_stack_real is False, "nombrar el modelo encendio el stack real"


# ===================================================== NO SE DESCARGA NADA --


def test_el_presupuesto_de_latencia_declarado_sigue_siendo_el_medido_contra(tmp_path, monkeypatch):
    """1200 ms es el listón contra el que se midieron los 94,24 s. Si cambia, cambia la conclusión.

    No se afirma que AURA lo cumpla —hoy no lo cumple con el 0.5b—: se afirma cuál es el listón, para
    que la brecha siga siendo medible y no se cierre bajando el listón.
    """
    _entorno_limpio(monkeypatch)
    assert _config(tmp_path).presupuesto_latencia_ms == 1200
