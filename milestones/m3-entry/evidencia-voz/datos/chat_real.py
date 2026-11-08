"""Validación del CHAT con el proveedor REAL (misión §15): ocho entradas, ruta por ruta.

Registra para cada turno: quién respondió (Core o modelo), dominio, estatus, llamadas al LLM, latencia,
memoria resultante y la respuesta literal. El contador de llamadas envuelve al proveedor SIN tocar el
código de AURA: si una superficie determinista contesta, debe marcar CERO llamadas.

Uso:  python3 chat_real.py <salida.json>
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid

ENTRADAS = [
    ("conversacion", "hola"),
    ("declaracion_propia", "me llamo Mauricio"),
    ("consulta_memoria", "como me llamo"),
    ("memoria_inexistente", "como se llama mi hija"),
    ("matematica_determinista", "si tengo 4 manzanas y me como una cuantas me quedan"),
    ("conocimiento_general", "el cielo de qué color es"),
    ("tema_sensible", "quién es Jesús Cristo"),
    ("persona_real", "quién es Simón Bolívar"),
]


class _Contador:
    """Envuelve al proveedor real y cuenta llamadas. No altera su comportamiento."""

    def __init__(self, real) -> None:
        self._real = real
        self.name = real.name
        self.llamadas = 0

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        self.llamadas += 1
        return await self._real.infer(prompt, modo)


async def _main() -> None:
    salida = sys.argv[1]
    datos = tempfile.mkdtemp(prefix="aura-chat-")

    from aura_skeleton.composicion import Configuracion, componer

    config = Configuracion(datos=datos, raices_permitidas=(datos,), usar_stack_real=True)
    sistema = componer(config)
    orq = sistema.orquestador
    contador = _Contador(orq.router.providers[0])
    orq.router.providers = [contador]

    informe: dict = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "modelo": config.modelo,
        "stack": "real",
        "voz": os.environ.get("AURA_PIPER_VOICE", "(sin declarar)"),
        "turnos": [],
    }

    for etiqueta, texto in ENTRADAS:
        antes = contador.llamadas
        tid = uuid.uuid4().hex[:12]
        t0 = time.time()
        await orq.handle_utterance("mauricio", texto, tid)
        r = await orq.wait(tid, timeout=1800)
        reg = {
            "caso": etiqueta,
            "entrada": texto,
            "say": r["say"],
            "quien_responde": "CORE" if r["provider"] == "core" else f"MODELO ({r['provider']})",
            "dominio": r["dominio"],
            "estatus": r["estatus"],
            "llamadas_llm": contador.llamadas - antes,
            "latencia_s": round(time.time() - t0, 2),
            "voz": r.get("voz", "(ausente)"),
        }
        informe["turnos"].append(reg)
        print(f"[{etiqueta}] {reg['latencia_s']}s  {reg['quien_responde']}  dominio={reg['dominio']}  "
              f"llm={reg['llamadas_llm']}  estatus={reg['estatus']}")
        print(f"      {reg['say'][:150]!r}")

    informe["memoria_final"] = await sistema.modelo_usuario.ver("mauricio")
    informe["llamadas_llm_totales"] = contador.llamadas
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nllamadas al LLM en total: {contador.llamadas} de {len(ENTRADAS)} turnos")
    print(f"memoria final: {informe['memoria_final']}")
    print(f"Informe -> {salida}")


if __name__ == "__main__":
    asyncio.run(_main())
