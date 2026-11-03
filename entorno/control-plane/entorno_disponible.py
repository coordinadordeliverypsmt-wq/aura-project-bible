"""Septima fuente de descubrimiento — **capacidades del entorno de ejecucion** (`DR-A`).

## Que cierra

Las seis fuentes anteriores miran dos sitios: el **arbol de ficheros** y el **historial**. Ninguna
mira la maquina. AURA podia tener un razonador local corriendo delante y no verlo: no es que le
faltara permiso para usarlo, es que le faltaba el organo para **observarlo**. Esta fuente abre ese
sentido, y solo ese.

## El limite exacto que aprueba el acta

`DR-A` autoriza **observar**. Nada mas. En consecuencia este modulo:

- **no ejecuta procesos** —ni los arranca, ni los para, ni los toca—;
- **no abre sockets ni hace peticiones**: preguntar por HTTP a un servicio es interactuar con el, y
  ademas ataria el descubrimiento a la red. Se leen ficheros que el nucleo ya publica;
- **no escribe una sola linea** en ningun sitio;
- **no puede producir `OPORTUNIDAD_REAL`**. Su techo es `DECISION_REQUIRED`, y por eso
  `planificador.a_tarea` la devuelve como `None`: lo que descubre es **conocimiento**, no permiso.

Puede decir *«hay un razonador local ahi y el ciclo no lo usa»*. **No** puede decir *«por tanto lo
pongo a trabajar»*: eso es una decision del CEO (`D22`, `seleccionar_tecnologia`).

## Por que se lee `/proc` y no se pregunta al servicio

`/proc/net/tcp` y `/proc/<pid>/comm` los publica el nucleo, se leen sin privilegios y sin efectos.
Una peticion a `127.0.0.1:11434` seria mas comoda y seria **otra cosa**: una interaccion con un
servicio ajeno desde el ciclo de descubrimiento, con su latencia y sus modos de fallo. Observar no
es preguntar.

## Los tres estados, y por que son tres y no dos

    DISPONIBLE   observado y esta
    AUSENTE      observado y no esta
    DESCONOCIDO  no se pudo observar

La distincion entre los dos ultimos es el corazon de `DR-A`. Con dos estados, un fichero ilegible se
convertiria en *«no existe»* —una ausencia inventada—, que es exactamente el patron
«declarado ≠ real» que este proyecto ya ha pagado ocho veces. **Fail-closed:** solo lo `DISPONIBLE`
con las tres senales observadas se eleva; `DESCONOCIDO` no eleva nada.
"""
from __future__ import annotations

import dataclasses
import pathlib

#: Estado `st` de un socket en escucha dentro de `/proc/net/tcp`. Una conexion establecida (`01`)
#: hacia ese puerto **no** prueba que alguien escuche: probaria que alguien escuchaba.
_LISTEN = "0A"

DISPONIBLE = "DISPONIBLE"
AUSENTE = "AUSENTE"
DESCONOCIDO = "DESCONOCIDO"

#: Nombra el **resultado** que se revisaria, no la herramienta (CEO, 2026-08-03). Es `HUMAN`: no
#: esta en `AUTO` ni en `TODO_LO_DELEGABLE`, y esta fuente no puede cambiarlo.
ACCION = "revisar_capacidad_del_entorno"


@dataclasses.dataclass(frozen=True)
class Capacidad:
    """Una capacidad se reconoce por **tres senales a la vez**. Con menos no se afirma."""
    nombre: str
    proceso: str
    puerto: int


#: Razonar en local necesita las tres cosas: algo que sirva, escuchando, y algo con que razonar.
#: Un servidor sin modelos no es la capacidad, igual que un modelo sin servidor tampoco.
RAZONAMIENTO_LOCAL = Capacidad("razonamiento_local", "ollama", 11434)

CAPACIDADES = (RAZONAMIENTO_LOCAL,)

_PROC = pathlib.Path("/proc")
_NET_TCP = pathlib.Path("/proc/net/tcp")
_MANIFESTS = pathlib.Path("~/.ollama/models/manifests/registry.ollama.ai/library").expanduser()


def _puertos_escuchando(net_tcp) -> set | None:
    """Puertos en LISTEN segun el nucleo. `None` = **no se pudo mirar**, que no es «no hay»."""
    try:
        crudo = pathlib.Path(net_tcp).read_text()
    except OSError:
        return None
    puertos = set()
    for linea in crudo.splitlines()[1:]:      # la primera es la cabecera
        campos = linea.split()
        if len(campos) < 4 or campos[3] != _LISTEN:
            continue
        trozos = campos[1].split(":")
        if len(trozos) != 2:
            continue
        try:
            puertos.add(int(trozos[1], 16))
        except ValueError:
            continue                          # una linea corrupta se ignora; el resto sigue valiendo
    return puertos


def _procesos(proc) -> set | None:
    """Nombres de proceso segun `/proc/<pid>/comm`. Un proceso ajeno ilegible se salta —es lo
    normal sin privilegios— pero un `/proc` que no se puede recorrer es `None`."""
    raiz = pathlib.Path(proc)
    if not raiz.is_dir():
        return None
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return None
    nombres = set()
    for entrada in entradas:
        if not entrada.name.isdigit():        # /proc tiene mucho que no es un proceso
            continue
        try:
            nombres.add((entrada / "comm").read_text().strip())
        except OSError:
            continue
    return nombres


def _modelos(manifests) -> dict | None:
    """`{"familia:tag": ruta_del_manifiesto}`. La ruta importa: es la evidencia que se puede abrir."""
    raiz = pathlib.Path(manifests)
    if not raiz.is_dir():
        return None
    try:
        familias = sorted(raiz.iterdir())
    except OSError:
        return None
    encontrados = {}
    for familia in familias:
        if not familia.is_dir():
            continue
        try:
            tags = sorted(familia.iterdir())
        except OSError:
            continue
        for tag in tags:
            if tag.is_file():
                encontrados[f"{familia.name}:{tag.name}"] = tag
    return encontrados


def observar(capacidad: Capacidad, *, proc=_PROC, net_tcp=_NET_TCP, manifests=_MANIFESTS) -> dict:
    """Las tres senales, sin combinarlas antes de tiempo. Si **alguna** no se pudo observar, el
    veredicto es `DESCONOCIDO`: afirmar sobre una observacion incompleta es inventar."""
    puertos = _puertos_escuchando(net_tcp)
    procesos = _procesos(proc)
    catalogo = _modelos(manifests)

    senal_puerto = None if puertos is None else (capacidad.puerto in puertos)
    senal_proceso = None if procesos is None else (capacidad.proceso in procesos)
    senal_modelos = None if catalogo is None else sorted(catalogo)
    senales = {"proceso": senal_proceso, "puerto": senal_puerto, "modelos": senal_modelos}

    if senal_proceso is None or senal_puerto is None or senal_modelos is None:
        estado = DESCONOCIDO
    elif senal_proceso and senal_puerto and senal_modelos:
        estado = DISPONIBLE
    else:
        estado = AUSENTE

    #: La evidencia es un fichero de verdad, no una afirmacion: `fuente_verificable` lo comprueba
    #: con `is_file()`, asi que una procedencia inventada no llega a construirse.
    evidencia = str(catalogo[senal_modelos[0]]) if estado == DISPONIBLE else None
    return {"capacidad": capacidad.nombre, "estado": estado, "senales": senales,
            "evidencia": evidencia}


def entorno(_raiz, _directorio, *, proc=_PROC, net_tcp=_NET_TCP, manifests=_MANIFESTS) -> list:
    """La fuente. **Solo lectura.** Una `DECISION_REQUIRED` como mucho por capacidad disponible.

    Ninguno de los dos primeros parametros se usa: el entorno no vive en el arbol de ficheros ni en
    el historial. Se aceptan para respetar la firma `(raiz, directorio)` que `descubrir()` invoca en
    toda fuente."""
    # Perezoso a proposito: `descubrimiento` importa este modulo para su dict `FUENTES`, asi que
    # importarlo arriba cerraria el ciclo. Mismo patron que `estancamiento`.
    import descubrimiento as des

    oportunidades = []
    for capacidad in CAPACIDADES:
        obs = observar(capacidad, proc=proc, net_tcp=net_tcp, manifests=manifests)
        if obs["estado"] != DISPONIBLE:
            continue                          # fail-closed: AUSENTE y DESCONOCIDO no elevan nada
        modelos = obs["senales"]["modelos"]
        #: La identidad es **la capacidad**, no la evidencia: asi el id no cambia porque aparezca un
        #: modelo nuevo, y el antiduplicados la reconoce vuelta tras vuelta.
        firma = f"capacidad:{capacidad.nombre}"
        oportunidades.append(des.Oportunidad(
            id=des._id_de(f"entorno:{capacidad.nombre}", capacidad.nombre, ACCION, firma),
            fuente=obs["evidencia"],
            justificacion=(
                f"el entorno ofrece {capacidad.nombre} observable —proceso {capacidad.proceso!r}, "
                f"puerto {capacidad.puerto} en escucha, modelos {modelos}— y el ciclo autonomo no lo "
                f"usa. Que hacer con eso es una decision del CEO, no de esta fuente"),
            alcance="entorno_de_ejecucion",
            accion=ACCION,
            autoridad="CEO",
            criterio_de_finalizacion={"capacidad": "diagnosticar_estado"},
            evidencia_requerida={"tipo": "fichero_existe", "patron": obs["evidencia"]},
            riesgo="ninguno: solo observacion",
            estado=des.DECISION_REQUIRED,
            detalle={"capacidad": capacidad.nombre, "modelos": modelos,
                     "proceso": capacidad.proceso, "puerto": capacidad.puerto,
                     "senales": obs["senales"]}))
    return oportunidades


__all__ = ["entorno", "observar", "Capacidad", "CAPACIDADES", "RAZONAMIENTO_LOCAL",
           "DISPONIBLE", "AUSENTE", "DESCONOCIDO", "ACCION"]
