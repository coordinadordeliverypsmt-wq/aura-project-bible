#!/usr/bin/env python3
"""Bateria de turnos cognitivos REALES contra Ollama, un caso por ejecucion.

Dos preguntas que la medicion del 2026-09-15 dejo abiertas:

1. DISTRIBUCION. La primera campana midio UNA sola pregunta. Para decidir si `num_predict` tiene
   sentido hace falta saber cuantos tokens emite el modelo con el prompt actual ante preguntas
   variadas: si la cola larga no existe, un tope no gana nada y solo arriesga truncar el JSON.

2. DEGRADACION SEMANTICA. La auditoria independiente senalo que el 24/24 no puede detectar un
   efecto del prompt (no invoca al modelo). Aqui se compara el prompt LEGADO (con `intent`/`args` y
   sin «Responde BREVE») contra el ACTUAL ante preguntas cuya respuesta correcta es «no se sabe».

No estima: lee las metricas de la API de Ollama. Construye el prompt con los simbolos REALES del
producto (variante ACTUAL) o con una copia literal de los anteriores (variante LEGADO).

Uso:
    MEDIR_CASO=<id> MEDIR_PROMPT=actual|legado python3 bateria_cognitiva.py <salida.json>
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

RAIZ = "/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry/walking-skeleton"
sys.path.insert(0, RAIZ)

from aura_skeleton.modules.providers_real import _ESQUEMA_COGNITIVO, _SYSTEM_COGNITIVO  # noqa: E402

HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
MODELO = "qwen2.5:0.5b"

#: Copia LITERAL de los simbolos anteriores al recorte (git show 6dad6af:.../providers_real.py).
_SYSTEM_LEGADO = (
    "Eres AURA, un asistente personal. Responde UNICAMENTE un objeto JSON con las claves: "
    'intent (string), action (string, siempre "consulta"), args (object vacio), '
    "say (string en espanol, tu respuesta al usuario). "
    "Conversa con naturalidad y razona cuando haga falta. "
    "Si no sabes algo, dilo en `say` en vez de inventarlo. "
    "NUNCA afirmes recordar algo sobre el usuario que no aparezca en el contexto de memoria."
)
_ESQUEMA_LEGADO = {
    "type": "object",
    "properties": {
        "say": {"type": "string", "minLength": 1},
        "intent": {"type": "string"},
        "action": {"type": "string", "enum": ["consulta"]},
        "args": {"type": "object"},
    },
    "required": ["say", "action"],
}

#: (id, texto, tipo). Cada caso se VERIFICO antes de medir contra el enrutado real del producto:
#: `_es_turno_cognitivo` True, referente `mundo`, sin dominio sensible, sin accion y no resoluble por
#: la aritmetica determinista. Una primera lista incluia «¿quien escribio Don Quijote?» (desviado por
#: dominio sensible, `personas_reales`) y «¿como funciona el motor de un coche?» (cae en la puerta de
#: ADR-0014): medirlos habria sido medir un camino que el usuario nunca recorre.
#: `abierta` = pregunta especulativa, la que mas riesgo tiene de cola larga y de invencion.
CASOS = {
    "explicacion": ("por que el cielo es azul?", "conocimiento"),
    "definicion": ("que es la fotosintesis?", "conocimiento"),
    "concepto": ("que es un agujero negro?", "conocimiento"),
    "palabra": ("que significa la palabra resiliencia?", "conocimiento"),
    "incierta": ("que es la materia oscura?", "abierta"),
    "hipotesis": ("que pasaria si la luna desapareciera?", "abierta"),
    # NO se cuenta. Existe por la CACHE DE PROMPT de Ollama, que falseo la primera campana: cambiar de
    # variante cambia el system prompt e invalida el prefijo cacheado, asi que la primera llamada de
    # cada variante paga la ingesta completa y las siguientes no. Calentar con una pregunta ajena deja
    # a las dos variantes en la misma condicion -prefijo caliente, pregunta nueva-, que es ademas la
    # condicion real de una conversacion: mismo system turno tras turno, pregunta distinta cada vez.
    "calentamiento": ("que es un volcan?", "calentamiento"),
}


def prompt_de(texto: str) -> str:
    """Mismo ensamblado que `orchestrator.py`, con memoria y buffer vacios."""
    return f"[contexto memoria: (sin recuerdos relevantes)]\n[conversacion reciente:\n(inicio de la conversacion)]\nUsuario: {texto}"


def main() -> int:
    salida = sys.argv[1]
    caso = os.environ["MEDIR_CASO"]
    variante = os.environ.get("MEDIR_PROMPT", "actual")
    texto, tipo = CASOS[caso]
    system, esquema = (_SYSTEM_COGNITIVO, _ESQUEMA_COGNITIVO) if variante == "actual" else (_SYSTEM_LEGADO, _ESQUEMA_LEGADO)

    cuerpo = {"model": MODELO, "prompt": prompt_de(texto), "system": system, "stream": False, "format": esquema}
    pet = urllib.request.Request(f"http://{HOST}/api/generate", data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(pet, timeout=900) as r:  # noqa: S310 (local)
        crudo = json.loads(r.read())
    reloj = time.monotonic() - t0

    ns = 1_000_000_000
    gen_tok, gen_s = crudo.get("eval_count", 0), crudo.get("eval_duration", 0) / ns
    ing_tok, ing_s = crudo.get("prompt_eval_count", 0), crudo.get("prompt_eval_duration", 0) / ns
    total = crudo.get("total_duration", 0) / ns
    respuesta = crudo.get("response", "")
    try:
        say = json.loads(respuesta).get("say", "")
        json_valido = True
    except ValueError:
        say, json_valido = "", False

    informe = {
        "caso": caso, "tipo": tipo, "variante": variante, "texto": texto,
        "reloj_s": round(reloj, 2), "total_s": round(total, 2),
        "carga_s": round(crudo.get("load_duration", 0) / ns, 2),
        "ingesta_tokens": ing_tok, "ingesta_s": round(ing_s, 2),
        "generacion_tokens": gen_tok, "generacion_s": round(gen_s, 2),
        "generacion_tok_s": round(gen_tok / gen_s, 3) if gen_s else None,
        "motivo_fin": crudo.get("done_reason"), "json_valido": json_valido,
        "claves": sorted(json.loads(respuesta).keys()) if json_valido else None,
        "say": say, "respuesta_cruda": respuesta,
    }
    with open(salida, "w") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in informe.items() if k != "respuesta_cruda"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
