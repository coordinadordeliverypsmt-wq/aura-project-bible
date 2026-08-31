"""El despertador — **lo único que AURA necesita de fuera para trabajar sola**.

    python3 despertador.py --max-tareas 3

El motor ya sabe descubrir, decidir, ejecutar, verificar y parar. Lo que no tiene es quien lo llame, y
esa pieza tiene que vivir fuera de AURA porque **AURA no puede despertarse a si misma sin ser un
demonio**, y el `§23` del DP aprobado prohibe todos: *«Ningun daemon ni watcher permanente. El
Orchestrator se invoca y termina»*.

## La trampa que este modulo existe para evitar

Es facilisimo que el que despierta acabe decidiendo. Un despertador que consulta la cola para saber si
merece la pena arrancar, que reintenta cuando no hubo trabajo, o que decide cuantas tareas tocan hoy,
**ha dejado de ser un despertador**: es un planificador externo, y la autonomia se habria mudado fuera
de AURA sin que nadie lo declarase.

Por eso las garantias de este modulo son **negativas**, y se prueban como tales:

- no importa `descubrimiento` ni `planificador`: no puede mirar la cola;
- no llama a `transicion`, `guardar` ni `actualizar_estado`: no tiene autoridad;
- no tiene bucles, esperas ni reprogramacion: despierta una vez y termina;
- no interpreta el informe de AURA: lo devuelve tal cual.

## Las dos cosas que si le corresponden

Antes de despertar comprueba dos condiciones. Ninguna es una decision **sobre el trabajo** —eso es de
AURA—; las dos son sobre si es **seguro tocar el arbol**:

1. **El kill switch.** Si el sistema esta comprometido, lo ultimo que hace falta es despertarlo.
2. **El arnes de mutacion.** Mientras `herramientas.mutar` corre, el arbol **no contiene el codigo
   real**. Despertar a AURA entonces la pondria a trabajar sobre mutantes y a registrar como hecho un
   trabajo hecho sobre codigo que no existe. Es la trampa que este proyecto ya pago una vez.

## Como se programa

Este modulo **no se programa a si mismo**: eso seria reprogramarse, y volveriamos al demonio. La linea
para `cron` esta en `entorno/scripts/despertar-aura.sh --instrucciones`, y la ejecuta una persona.
Quien despierta a AURA es una decision de operacion, no de codigo.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import aura
import control_plane as cp
import orquestador as orq

#: Cota dura sobre lo que puede pedir quien despierta. Que el tope venga de fuera no significa que
#: valga cualquiera: un despertador mal configurado no puede convertirse en el demonio que el `§23`
#: prohibe. `§14`: ningun bucle sin cota.
TOPE_MAXIMO = 10


def _ciclo_de_aura(tope: int) -> dict:
    """La llamada, aislada en una funcion para poder sustituirla en las pruebas **sin tocar el arbol
    real**. Es lo unico que este modulo sabe hacer con AURA: llamarla."""
    return aura.trabajar(aura._base(), tope)


def _seguro_para_despertar(directorio) -> tuple[bool, str]:
    if orq.parada_solicitada(directorio):
        return False, "kill switch activado"
    if orq.mutacion_en_curso():
        return False, "arnés de mutación en curso"
    return True, ""


def despertar(directorio, max_tareas: int = 3) -> dict:
    """Despierta a AURA una vez, o explica por que no.

    Devuelve el informe de AURA **sin interpretarlo**: un despertador que lo reinterpretara estaria
    opinando sobre el trabajo, y opinar sobre el trabajo es justo lo que no le toca."""
    if int(max_tareas) < 1:
        raise ValueError(f"un tope de {max_tareas} no acota nada: paraliza. Minimo 1")
    directorio = pathlib.Path(directorio)
    tope = min(int(max_tareas), TOPE_MAXIMO)

    seguro, motivo = _seguro_para_despertar(directorio)
    if not seguro:
        # Una negativa sin motivo obliga al siguiente a averiguarlo, y averiguar es lo que el
        # Protocolo de Continuidad existe para evitar.
        cp.registrar_evento(directorio, "despertar_rechazado", {"motivo": motivo, "tope": tope})
        return {"despertado": False, "motivo": motivo, "informe": None}

    informe = _ciclo_de_aura(tope)
    cp.registrar_evento(directorio, "aura_despertada", {
        "tope": tope, "resultado": informe.get("motivo_de_parada"),
        "ejecutadas": informe.get("ejecutadas"),
        "actos_humanos": informe.get("actos_humanos_durante_el_ciclo")})
    return {"despertado": True, "motivo": "", "informe": informe}


def principal(argumentos=None) -> int:
    analizador = argparse.ArgumentParser(
        prog="despertador",
        description="Despierta el ciclo de AURA una vez. No decide que trabajo hacer.")
    analizador.add_argument("--max-tareas", type=int, default=3)
    opciones = analizador.parse_args(argumentos)

    base = aura._base()
    resultado = despertar(base, opciones.max_tareas)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if not resultado["despertado"]:
        print(f"despertador: no se desperto a AURA · {resultado['motivo']}", file=sys.stderr)
        return aura.SALIDA_PARADA
    return aura.codigo_de_salida(resultado["informe"])


__all__ = ["despertar", "principal", "TOPE_MAXIMO"]


if __name__ == "__main__":                             # pragma: no cover - entrada de linea de ordenes
    raise SystemExit(principal())
