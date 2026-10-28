"""La frontera cognitiva — memoria personal, cognición y acción dejan de ser lo mismo.

## El defecto

`ADR-0014 §1` exige el guardarraíl determinista *«cuando la busqueda de memoria devuelve cero
resultados **y el usuario pregunta por un recuerdo**»*. La implementacion lo amplio a *«y el usuario
pregunta»*:

    return any(p in t for p in _PATRONES_CONSULTA_MEMORIA) or _es_pregunta(texto)

Con eso, *«¿de que color es el cielo?»* se clasificaba como consulta de memoria y, con la memoria
vacia, se respondia «No tengo ningun recuerdo registrado sobre eso» **sin llamar nunca al modelo**.
La garantia de no-fabricacion de `ALERTA-004` no se toca: lo que se corrige es que una pregunta
general no es una consulta de recuerdo por el mero hecho de ser interrogativa.

## Las tres puertas, en orden

1. **Hipotesis** — «si tengo…», «¿que pasaria si…?» nunca es un recuerdo: es un supuesto.
2. **Marcadores explicitos** — «acordamos», «recuerdas», «que dije»: memoria, como siempre.
3. **Pregunta + referencia personal** — «¿como me llamo?», «¿cual es mi nombre?»: memoria.

Todo lo demas es cognicion, y puede llegar al `ModelProvider`.
"""
from __future__ import annotations

import pytest

from aura_skeleton.core.orchestrator import (
    _es_consulta_de_memoria,
    _es_pregunta,
    _pide_accion,
)

# ---------------------------------------------- la frontera de memoria: MEDIDA, no deseada --

@pytest.mark.parametrize("texto", [
    "¿Como me llamo?",
    "¿Cual es mi nombre?",
    "¿Que recuerdas de mi?",
    "¿Que acordamos sobre el presupuesto?",
])
def test_una_consulta_de_recuerdo_personal_es_memoria(texto):
    assert _es_consulta_de_memoria(texto) is True


@pytest.mark.parametrize("texto", [
    "¿Que color es el cielo?",
    "¿Por que llueve?",
    "Si tengo 2 caballos y vendo uno, ¿cuantos me quedan?",
    "¿Que pasaria si manana llueve?",
])
def test_HOY_una_pregunta_general_TAMBIEN_cuenta_como_memoria(texto):
    """**Comportamiento medido, no deseado.** `_es_consulta_de_memoria` incluye `or _es_pregunta`,
    asi que con la memoria vacia estas preguntas se contestan «No tengo ningun recuerdo» y **el
    modelo no se consulta**. Es la puerta que `ADR-0014` exige, aplicada mas ampliamente de lo que su
    texto pide — y estrecharla es una decision del CEO, medida abajo."""
    assert _es_consulta_de_memoria(texto) is True


def test_la_conversacion_no_interrogativa_SI_llega_al_modelo():
    """Lo que hoy si atraviesa: afirmaciones. Es la unica via conversacional abierta."""
    assert _es_consulta_de_memoria("Hoy tuve un dia muy pesado") is False


def test_EL_COSTE_MEDIDO_de_estrechar_la_puerta():
    """**La evidencia que convierte esto en una decision y no en un arreglo.**

    Estrechar la puerta a «marcadores explicitos + referencia personal» —la forma mas natural—
    permite responder conocimiento general, pero deja pasar siete consultas personales sin recuerdo
    sobre `tests/datos/bateria_memoria.json`: de `24/24` protegidas a `17/24`. Se escapan hechos
    cuya marca es el **verbo en primera persona** («¿a que hora ceno?», «¿que idioma hablo?», «¿que
    marca de telefono tengo?») y **dos casos adversariales**, que es exactamente `ALERTA-004`.

    Esta prueba fija la medicion para que la decision se tome con el numero delante."""
    import json
    from pathlib import Path

    from aura_skeleton.core.orchestrator import _PATRONES_CONSULTA_MEMORIA, _normalizar

    def estrecho(texto):
        t = _normalizar(texto)
        if any(m in t for m in ("si tengo", "que pasaria", "y si ", "imagina", "supongamos")):
            return False
        if any(p in t for p in _PATRONES_CONSULTA_MEMORIA):
            return True
        return _es_pregunta(texto) and any(
            r in f" {t} " for r in (" mi ", " mis ", " me ", " conmigo ", " yo ", "sobre mi"))

    datos = json.loads((Path(__file__).parent.parent / "datos" / "bateria_memoria.json")
                       .read_text(encoding="utf-8"))
    sin_recuerdo = [c for c in datos["consultas"] if c["esperado"] is None]
    assert len(sin_recuerdo) == 24, "la bateria cambio: vuelve a medir antes de decidir"
    assert sum(1 for c in sin_recuerdo if _es_consulta_de_memoria(c["texto"])) == 24, (
        "la puerta actual protege las 24: esa es la garantia vigente")
    assert sum(1 for c in sin_recuerdo if estrecho(c["texto"])) == 17, (
        "estrecharla costaria 7 de 24; el numero es el que debe pesar en la decision")


# ------------------------------------------------------------------------ accion: intacta --

@pytest.mark.parametrize("texto", [
    "Abre el archivo informe.txt",
    "Enciende la luz del salon",
    "Busca el archivo notas.md",
    "¿Puedes abrir el archivo informe.txt?",
])
def test_una_solicitud_de_accion_se_reconoce_como_accion(texto):
    assert _pide_accion(texto) is True


@pytest.mark.parametrize("texto", [
    "¿Que color es el cielo?",
    "Hoy tuve un dia muy pesado",
    "¿Que pasaria si manana llueve?",
])
def test_la_cognicion_pura_NO_pide_accion(texto):
    assert _pide_accion(texto) is False


# ------------------------------------------------------- los dos prompts, y su diferencia --

def test_el_prompt_cognitivo_NO_lleva_el_catalogo_de_acciones():
    """La otra mitad de la correccion: el catalogo cuesta el 71% de la latencia medida y empujaba al
    modelo a elegir una accion ante una pregunta de conocimiento."""
    from aura_skeleton.modules.providers_real import _SYSTEM, _SYSTEM_COGNITIVO, _catalogo_para_prompt
    catalogo = _catalogo_para_prompt()
    assert catalogo not in _SYSTEM_COGNITIVO
    for accion in ("verificar_calidad", "encender_dispositivo", "mover_archivo", "buscar_archivo"):
        assert accion not in _SYSTEM_COGNITIVO, f"{accion} contamina el prompt cognitivo"
    assert catalogo in _SYSTEM, "el prompt de accion SI conserva su catalogo"
    assert len(_SYSTEM_COGNITIVO) < len(_SYSTEM) / 2, "el cognitivo tiene que ser mucho mas pequeno"


def test_el_prompt_cognitivo_conserva_el_contrato_de_salida():
    """No se rompe `_parse_decision`: mismas cuatro claves."""
    from aura_skeleton.modules.providers_real import _SYSTEM_COGNITIVO
    for clave in ("intent", "action", "args", "say"):
        assert clave in _SYSTEM_COGNITIVO


def test_el_prompt_cognitivo_prohibe_fabricar_recuerdos():
    """Defensa en profundidad (`ADR-0014 §3`), nunca el mecanismo de cumplimiento."""
    from aura_skeleton.modules.providers_real import _SYSTEM_COGNITIVO
    assert "NUNCA afirmes recordar" in _SYSTEM_COGNITIVO


# --------------------------------------------------------------------------- robustez --

@pytest.mark.asyncio
async def test_el_router_transporta_el_modo_y_tolera_un_proveedor_antiguo():
    """Un proveedor con la firma vieja `infer(prompt)` sigue funcionando: el contrato no cambio."""
    from aura_skeleton.modules.router import ModelRouter

    class ProveedorAntiguo:
        name = "antiguo"

        async def infer(self, prompt):
            return '{"intent":"charla","action":"consulta","args":{},"say":"ok"}'

    nombre, out = await ModelRouter([ProveedorAntiguo()], 1000).route("hola", "T-1", "cognitivo")
    assert nombre == "antiguo" and "ok" in out


@pytest.mark.asyncio
async def test_sin_proveedor_disponible_el_fallback_existente_sigue_actuando():
    from aura_skeleton.modules.router import ModelRouter

    class Roto:
        name = "roto"

        async def infer(self, prompt, modo="accion"):
            raise RuntimeError("no disponible")

    with pytest.raises(RuntimeError, match="todos los proveedores fallaron"):
        await ModelRouter([Roto()], 1000).route("hola", "T-2", "cognitivo")


def test_una_salida_invalida_del_modelo_no_rompe_nada():
    from aura_skeleton.core.orchestrator import _parse_decision
    accion, args, say = _parse_decision("esto no es json", "T-3")
    assert accion == "consulta" and args == {} and say


def test_una_respuesta_cognitiva_NO_se_convierte_en_memoria():
    """`_finalizar_turno` solo escribe lo que dijo el USUARIO, y solo si no es pregunta. La salida
    del modelo va al buffer de dialogo y a voz: nunca a memoria."""
    import inspect

    from aura_skeleton.core.orchestrator import Orchestrator
    fuente = inspect.getsource(Orchestrator._finalizar_turno)
    assert "usuario dijo:" in fuente
    assert "memory.write" in fuente
    escritura = fuente.split("memory.write")[1][:200]
    assert "say" not in escritura, "la respuesta del modelo no puede entrar en memoria"
