"""Verificador de B3 — el segundo TIPO de agente, con `OpenCode` bajo demanda.

`PLAN-B3 §1`: *«un único ida y vuelta con un segundo tipo de agente»*. Decisión del CEO 2026-08-25
(`DEC-B3-QUE-AGENTE`): ese agente es **OpenCode bajo demanda**, no Codex — que quedó bloqueado por
`D24` al exigir credencial de terceros.

**No duplica el verificador de B2:** reutiliza sus seis evidencias y añade la única que B3 necesita
de más — **quién firma el RESULT**. En B2 daba igual porque solo había un agente; con dos, confundir
al emisor haría que un mensaje de B2 pasara por un resultado de B3, y el experimento no probaría
nada.
"""

from __future__ import annotations

from verificador_b2 import SUMA_ESPERADA, TAREA, veredicto, verificar_b2

AGENTE_B3 = "opencode"


def publicar_tarea_b3(canal) -> str:
    """La TASK del §4 de B3: idéntica a la de B2 salvo el destinatario.

    `para="opencode"` en vez de `para="codex"` por `DEC-B3-QUE-AGENTE`. El canal es **agnóstico del
    destinatario** —lo dice el propio §4 y B2 lo probó—, así que esto no toca el transporte.
    """
    return canal.publicar(tipo="TASK", de="orquestador-local", para=AGENTE_B3, cuerpo=dict(TAREA))


def verificar_b3(canal, id_tarea: str, sobre: dict, codigo_salida: int,
                 agente: str = AGENTE_B3) -> dict:
    """Las seis de B2 **más** la identidad del emisor. Devuelve un dict de booleanos."""
    evidencias = verificar_b2(canal, id_tarea, sobre, codigo_salida)
    respuesta = next((m for m in canal.leer_desde(seq=0)
                      if m.get("tipo") == "RESULT" and m.get("in_reply_to") == id_tarea), None)
    # La séptima: el RESULT lo firma el SEGUNDO agente, no el de B2. Sin esto, un canal reutilizado
    # daría B3 por bueno con la respuesta que dejó B2.
    evidencias["lo_firma_el_segundo_agente"] = bool(respuesta) and respuesta.get("de") == agente
    return evidencias


__all__ = ["AGENTE_B3", "SUMA_ESPERADA", "publicar_tarea_b3", "veredicto", "verificar_b3"]
