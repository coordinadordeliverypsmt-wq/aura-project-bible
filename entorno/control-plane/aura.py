"""`aura` — el punto de entrada desde el que AURA trabaja **sin que nadie le pase la tarea**.

    python3 aura.py diagnosticar     # que ve, sin tocar nada
    python3 aura.py trabajar         # una vuelta acotada del ciclo, y termina

## Por que esto NO es un demonio, y no puede serlo

El `§23` del DP aprobado lo dice sin margen: *«**Ningun daemon ni watcher permanente.** El
Orchestrator se invoca y termina»*. Asi que este modulo **arranca, hace una cantidad acotada de
trabajo y sale**. Quien lo vuelve a llamar es asunto de fuera —`cron`, un hook, una persona—, y esa
es justamente la separacion que hace que la autonomia resida en AURA y no en quien la despierta.

Un proceso que no muere es un proceso al que hay que ir a matar, y un sistema que hay que ir a matar
no es un sistema gobernado: es uno al que se le pide permiso para pararlo. El kill switch existe
precisamente porque esa distincion importa.

## Que garantiza cada salida

El codigo de salida **dice algo** y por eso no es siempre 0: quien encadene esto necesita distinguir
«no habia trabajo» de «me tuve que parar», sin leer prosa.

| Codigo | Significa |
|---|---|
| `0` | trabajo hecho, o cola agotada — las dos son terminaciones correctas |
| `2` | el ciclo se detuvo por una causa que alguien tiene que mirar |
| `3` | error del propio arranque; no se llego a descubrir nada |

**Cola agotada sale 0 a proposito.** No haber encontrado trabajo autorizado no es un fallo: es la
respuesta correcta cuando no lo hay, y tratarla como error empujaria a quien lo automatice a fabricar
trabajo para que «pase».
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import control_plane as cp
import descubrimiento as des
import motor_autonomia as motor

#: Terminaciones que **no** son un problema: se hizo el trabajo, o no habia. Cualquier otra parada
#: la mira alguien.
PARADAS_NORMALES = ("cola agotada", "limite de seguridad")

SALIDA_OK = 0
SALIDA_PARADA = 2
SALIDA_ERROR = 3


def _base() -> pathlib.Path:
    """El plano de desarrollo. Se deriva del propio fichero: pasarlo por parametro invitaria a
    apuntarlo a otro sitio, y la zona de escritura no es algo que deba decidir quien invoca."""
    return pathlib.Path(__file__).resolve().parent


def diagnosticar(base: pathlib.Path) -> dict:
    return motor.diagnostico(base, base)


def trabajar(base: pathlib.Path, max_tareas: int) -> dict:
    return motor.trabajar(base, base, verificacion=None, max_tareas=max_tareas)


def codigo_de_salida(informe: dict) -> int:
    return SALIDA_OK if informe.get("motivo_de_parada") in PARADAS_NORMALES else SALIDA_PARADA


def principal(argumentos=None) -> int:
    analizador = argparse.ArgumentParser(
        prog="aura", description="Ciclo de trabajo de AURA: descubrir, ejecutar, verificar, seguir.")
    analizador.add_argument("orden", choices=("diagnosticar", "trabajar"))
    analizador.add_argument("--max-tareas", type=int, default=5,
                            help="tope de tareas por invocacion (§14: ningun bucle sin cota)")
    opciones = analizador.parse_args(argumentos)
    base = _base()

    try:
        if opciones.orden == "diagnosticar":
            informe = diagnosticar(base)
            print(json.dumps(informe, ensure_ascii=False, indent=2))
            return SALIDA_OK
        informe = trabajar(base, opciones.max_tareas)
    except Exception as exc:                           # pragma: no cover - arranque roto
        # Se registra el fallo de arranque **si se puede**: si ni siquiera eso funciona, se dice por
        # la salida de errores y se sale con 3. Callarse un arranque roto seria indistinguible de
        # una cola agotada, y son cosas opuestas.
        try:
            cp.registrar_evento(base, "arranque_fallido", {"error": f"{type(exc).__name__}: {exc}"[:300]})
        except Exception:
            pass
        print(f"aura: no se pudo arrancar el ciclo: {type(exc).__name__}: {exc}", file=sys.stderr)
        return SALIDA_ERROR

    print(json.dumps(informe, ensure_ascii=False, indent=2))
    if not informe["ejecutadas"] and informe["motivo_de_parada"] == "cola agotada":
        # La frase que el CEO pidio que significara algo: una cola vacia **no** es «no puedo hacer
        # nada». Se dice con las cuentas delante para que se pueda comprobar.
        print(f"aura: NO_HAY_TRABAJO_AUTORIZADO · bloqueadas={informe['bloqueadas']} "
              f"· elevadas={informe['elevadas']} · descubiertas={informe['descubiertas']}",
              file=sys.stderr)
    return codigo_de_salida(informe)


__all__ = ["principal", "diagnosticar", "trabajar", "codigo_de_salida",
           "PARADAS_NORMALES", "SALIDA_OK", "SALIDA_PARADA", "SALIDA_ERROR", "des"]


if __name__ == "__main__":                             # pragma: no cover - entrada de linea de ordenes
    raise SystemExit(principal())
