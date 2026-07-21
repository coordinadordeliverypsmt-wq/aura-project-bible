"""Ejecutable oficial de AURA (MA.1).

    python -m aura_skeleton --verificar     comprueba el arranque y sale
    python -m aura_skeleton                 conversacion interactiva

Es el **unico** mecanismo previsto para ejecutar AURA. Los scripts de demo y validacion existen
para reproducir escenarios concretos; este es el programa.

`--verificar` esta pensado para el arranque en un equipo nuevo: enumera lo que quedo encendido, de
modo que un cableado incompleto se vea en pantalla en vez de descubrirse semanas despues con el
historial vacio.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from .composicion import Configuracion, componer


def _informe(sistema) -> str:
    caps = sorted(sistema.registro_adaptadores.capacidades())
    fuentes = sorted(sistema.registro_contexto.fuentes)
    lineas = [
        "=" * 62,
        "AURA — arranque verificado",
        "=" * 62,
        f"  capacidades activas ({len(caps)}): {', '.join(caps)}",
        f"  fuentes de contexto ({len(fuentes)}): {', '.join(fuentes)}",
        f"  memoria persistente : {sistema.ruta_memoria}",
        f"  registro forense    : {sistema.ruta_audit}",
        f"  kill switch         : {'ARMADO' if sistema.kill_switch.is_engaged() else 'en reposo'}",
        "=" * 62,
    ]
    return "\n".join(lineas)


async def _conversar(sistema) -> int:
    print(_informe(sistema))
    print("Escribe para hablar con AURA. Ctrl-D para salir.\n")
    while True:
        try:
            texto = input("tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nhasta luego.")
            return 0
        if not texto:
            continue
        tid = uuid.uuid4().hex[:12]
        try:
            await sistema.orquestador.handle_utterance("usuario", texto, tid)
            res = await sistema.orquestador.wait(tid, timeout=900)
            print(f"AURA> {res['say']}\n")
        except Exception as e:
            # Un turno fallido no puede tumbar la sesion: AURA sigue disponible.
            print(f"AURA> No pude completar el turno ({type(e).__name__}: {e})\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aura", description="Sistema Operativo de Inteligencia Personal")
    ap.add_argument("--verificar", action="store_true", help="verifica el arranque y sale")
    args = ap.parse_args(argv)

    sistema = componer(Configuracion.desde_entorno())

    if args.verificar:
        print(_informe(sistema))
        return 0
    return asyncio.run(_conversar(sistema))


if __name__ == "__main__":
    sys.exit(main())
