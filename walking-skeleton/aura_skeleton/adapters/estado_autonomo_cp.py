"""Adaptador: leer el estado del ciclo autonomo desde el plano de control.

Este fichero es la **unica** pieza del producto que sabe que existe `entorno/control-plane`. El
nucleo conversacional habla con el puerto `FuenteEstadoAutonomo` y no se entera de nada de esto — que
es justo lo que permite que el producto se instale sin el plano de desarrollo y siga funcionando.

## Por que se carga por ruta y no con un `import`

`aura_skeleton` es un paquete instalable; `entorno/control-plane` es un directorio de trabajo que en
un despliegue puede sencillamente no estar. Un `import` normal ataria el arranque del producto a la
presencia del plano. Cargarlo por ruta convierte la ausencia en lo que de verdad es: **una fuente que
no esta**, no un fallo.

## Por que esto NO escribe nada

`observatorio.py` es de solo lectura y esta demostrado: una prueba recorre su arbol sintactico
comprobando que no aparecen `registrar_evento`, `write_text` ni un import de `descubrimiento` —cuya
funcion `descubrir()` SI registra un evento, de modo que una consola que descubriera dejaria rastro
cada vez que alguien la mira—. Aqui se llama a `estado()`, nada mas.

## Por que no hay cache

Porque el dato cambia: el `cron` despierta cada media hora y el ciclo avanza solo. Una instantanea
cacheada contaria como presente algo que dejo de serlo, y este proyecto ya sabe lo que cuesta enseñar
un estado que no es el real. Se paga la lectura en cada pregunta, que ocurre solo cuando alguien
pregunta.
"""

from __future__ import annotations

import os
import sys
import types

import aura_skeleton.observability as obs


def _ruta_por_defecto() -> str:
    """`<repo>/entorno/control-plane`, derivado de la posicion de este fichero.

    Se deriva en vez de configurarse para que no haya un segundo sitio donde declarar donde vive el
    plano; `AURA_CONTROL_PLANE` existe para el caso en que alguien lo mueva."""
    aqui = os.path.dirname(os.path.abspath(__file__))          # .../walking-skeleton/aura_skeleton/adapters
    repo = os.path.dirname(os.path.dirname(os.path.dirname(aqui)))
    return os.path.join(repo, "entorno", "control-plane")


class EstadoAutonomoDelControlPlane:
    """Implementa `FuenteEstadoAutonomo` leyendo el observatorio del plano de control."""

    def __init__(self, observatorio: types.ModuleType, directorio: str) -> None:
        self._obs = observatorio
        self._directorio = directorio

    def instantanea(self) -> dict:
        try:
            return self._obs.estado(self._directorio)
        except Exception as e:                                 # pragma: no cover - defensivo
            # Un plano ilegible NO puede tumbar una conversacion. Se declara la ausencia —que el
            # redactor traduce en «no me consta»— y se deja constancia en la telemetria: callarlo
            # haria indistinguible «no hay fuente» de «la fuente esta rota».
            obs.log("CORE", "estado-autonomo", f"plano ilegible: {type(e).__name__}: {e}", "-")
            return {}


def crear_fuente_estado_autonomo(directorio: str | None = None):
    """La fuente, o `None` si el plano de control no esta disponible.

    `None` no es un error: es un despliegue del producto sin plano de desarrollo, y la conversacion
    debe seguir comportandose exactamente como antes de este incremento."""
    if directorio is None:
        declarado = os.environ.get("AURA_CONTROL_PLANE")
        if declarado is not None and not declarado.strip():
            # DECLARADO Y VACIO significa «no hay plano», y no es lo mismo que no declararlo. Lo usa
            # la bateria de pruebas: sin esto, la suite leeria el `eventos.jsonl` REAL del equipo de
            # quien la ejecuta y sus resultados cambiarian solos cada media hora, cuando el `cron`
            # despierta a AURORA. Una prueba que depende del historial de hoy no prueba nada.
            return None
        directorio = declarado or _ruta_por_defecto()
    if not os.path.isdir(directorio) or not os.path.exists(os.path.join(directorio, "observatorio.py")):
        return None
    if directorio not in sys.path:
        # `observatorio` importa `control_plane` y `orquestador` por nombre corto: necesitan su
        # directorio en la ruta de busqueda. Se anade al final para no ensombrecer nada del producto.
        sys.path.append(directorio)
    try:
        import importlib

        modulo = importlib.import_module("observatorio")
    except Exception as e:
        obs.log("CORE", "estado-autonomo", f"no se pudo cargar el observatorio: {type(e).__name__}: {e}", "-")
        return None
    return EstadoAutonomoDelControlPlane(modulo, directorio)


__all__ = ["EstadoAutonomoDelControlPlane", "crear_fuente_estado_autonomo"]
