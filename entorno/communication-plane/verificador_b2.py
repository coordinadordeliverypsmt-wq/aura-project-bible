"""Verificador de B2 — las seis evidencias de `PLAN-B2.md §4`, sin juicio.

Todas son mecánicamente comprobables: la tarea es `17+25=42` precisamente para que *«no haya prosa
que evaluar»*. Este módulo no decide si el agente lo hizo «bien»; comprueba hechos.

**Lo que de verdad aporta es la distinción del §4:** si el proceso terminó limpio pero no hay
`RESULT` válido, *«el canal funciona y el agente no siguió la instrucción»* — y eso **no es** un
canal roto. Mezclar ambas cosas invalidaría el experimento entero, porque el fallo de un agente
pasaría por fallo de infraestructura.
"""

from __future__ import annotations

import communication_plane as cp

#: El cuerpo exacto que `§2` fija para la TASK. No se parametriza: es el experimento.
TAREA = {
    "objetivo": "sumar",
    "a": 17,
    "b": 25,
    "instruccion": "publica un RESULT con in_reply_to a este mensaje y cuerpo.suma",
}

SUMA_ESPERADA = 42


def publicar_tarea(canal) -> str:
    """Publica la TASK del §2 y devuelve su id."""
    return canal.publicar(tipo="TASK", de="orquestador-local", para="claude-code", cuerpo=dict(TAREA))


def _sin_error(sobre: dict) -> bool:
    """§4.2 · se decide por `is_error`, **nunca** por `subtype`.

    Medido el 2026-08-17: `claude -p` devolvió `is_error: true` junto a `subtype: "success"`. Y un
    sobre **sin** `is_error` tampoco es éxito: ausencia de dato no es dato.
    """
    try:
        return cp.ejecucion_correcta(sobre)
    except ValueError:
        return False


def verificar_b2(canal, id_tarea: str, sobre: dict, codigo_salida: int) -> dict:
    """Las seis evidencias del §4, como un dict de booleanos. Sin interpretación."""
    resultados = [m for m in canal.pendientes(para="orquestador-local")
                  if m.get("tipo") == "RESULT"]
    respuesta = next((m for m in resultados if m.get("in_reply_to") == id_tarea), None)

    integridad = canal.verificar_integridad()
    seqs = [m.get("seq") for m in canal.leer_desde(seq=0) if m.get("seq") is not None]

    return {
        "exit_cero": codigo_salida == 0,
        "sin_error_en_sobre": _sin_error(sobre),
        "hay_result": bool(resultados),
        "responde_a_la_tarea": respuesta is not None,
        "suma_correcta": bool(respuesta) and respuesta.get("cuerpo", {}).get("suma") == SUMA_ESPERADA,
        # §4.6 · `seq` monótona Y cadena de hashes intacta, comprobado DESPUES de que escriba el agente
        "integridad": bool(integridad.get("integro")) and cp.huecos_de_secuencia(seqs) == [],
    }


def veredicto(evidencias: dict) -> str:
    """`GREEN` solo con las seis. La distincion del §4 se conserva en el nombre del veredicto."""
    if all(evidencias.values()):
        return "GREEN"
    proceso_limpio = evidencias["exit_cero"] and evidencias["sin_error_en_sobre"]
    canal_sano = evidencias["integridad"]
    if proceso_limpio and canal_sano:
        # 1-2 pasan, 3-5 no: el canal hizo su parte.
        return "CANAL_OK_AGENTE_NO_SIGUIO"
    return "FALLO"
