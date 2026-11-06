"""`ejecutar_pruebas` — el ejecutor de la capacidad que la politica ya tenia registrada.

## Que eslabon faltaba

La cadena `oportunidad -> tarea -> contrato -> review -> ejecutor -> efecto` estaba completa. Medido
en sandbox el 2026-09-20, con las cinco puertas de `review.ejecutar_bajo_review` en su sitio:

    PARADA armada                        -> ParadaActiva, fichero intacto
    PARADA desarmada, verificacion=None  -> el cambio se aplica y SE REVIERTE (revertido=True)
    PARADA desarmada, verificador real   -> ejecutado=True, efecto producido

El unico punto donde una tarea autorizada dejaba de poder continuar es el del medio: `aura.py` pasa
`verificacion=None`, y el blindaje trata «no se sabe» como fallo y revierte —correctamente—. Sin
verificador, **ninguna tarea puede completarse jamas**.

## Esto NO es una capacidad nueva

`politica-orquestador.toml` ya declaraba `ejecutar_pruebas` en nivel AUTO, con `tipo = "lectura"`,
`limites_de_modificacion = "ninguna"`, la precondicion *«el arnes de mutacion NO esta corriendo»* y
—esto es lo importante— `evidencia_requerida = "informe de pytest con conteo"`. **La politica ya
habia decidido no fiarse del `returncode`.** Lo que faltaba era el ejecutor: `agentes._EJECUTORES`
devuelve `exit_code=127` para todo. Este modulo lo implementa; no concede nada que no estuviera
autorizado, y **restringe** lo que antes era un `None` silencioso.

## Por que el conteo y no el returncode

`returncode == 0` significa «pytest termino contento», que no es «la bateria paso». Reproducido:

  · con `PYTEST_ADDOPTS=--collect-only` heredado del entorno -> exit 0 sin ejecutar una sola prueba
  · con un `conftest.py` que marca todo como skip          -> exit 0 con la bateria entera omitida
  · sin ficheros que recoger                                -> exit 5, que no es un fallo de prueba

Por eso el veredicto sale de `--junitxml`: **salida estructurada, no prosa**. Este proyecto ya pago
una vez por decidir leyendo el texto de pytest —*«aquel arnes parseaba el TEXTO de salida para
decidir si una afirmacion era falsa»*— y el arnes de mutacion lo arreglo decidiendo por el codigo
entero. Aqui se va un paso mas alla: se cuenta cuantas corrieron y cuantas pasaron.

## Que hace y que NO hace

**No escribe nada en el arbol.** Su unica escritura es el informe XML, en un directorio temporal
fuera del repositorio, que borra al terminar. **No instala, no descarga y no toca la red.**

**No decide si el cambio era correcto**: decide si el arbol quedo sano. Quien compara el efecto con
lo que el contrato prometio es `autoconstruccion.ejecutar`, releyendo el fichero. Son dos preguntas
distintas y las contesta cada una quien debe.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import orquestador

#: Plazo por defecto para la bateria entera. Sin limite, una prueba que cuelga cuelga el ciclo
#: —y el ciclo corre desatendido—. El arnes de mutacion aprendio esto con un proceso huerfano que
#: consumio CPU 15+ horas.
LIMITE_S = 600.0

#: Lo que se le deja ver al proceso hijo, y nada mas. **Se construye, no se hereda.**
#: `PYTEST_ADDOPTS` en el entorno del padre convierte cualquier ejecucion en un exit 0 vacio, y un
#: verificador que hereda el entorno hereda tambien esa mentira.
#:
#: Las dos ultimas son la **marca de delegacion** y se propagan a proposito (2026-09-21): sin
#: ellas, un proceso lanzado dentro de una mision delegada no sabria que lo esta, podria pedir otra
#: mision declarando `profundidad=0` y la cota no se enteraria. La profundidad tiene que viajar con
#: el proceso, no con el dato que trae quien pide.
_ENTORNO_MINIMO = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR",
                   "AURA_DELEGACION_PROFUNDIDAD", "AURA_DELEGACION_EN_CURSO")


class ArnesEnCurso(RuntimeError):
    """El arnes de mutacion esta corriendo: el arbol NO contiene el codigo real.

    Precondicion declarada en la ficha de la capacidad. Medir mientras `herramientas.mutar` muta
    ficheros en el sitio es medir un mutante y reportarlo como si fuera el producto: ya ocurrio
    (CEO, 2026-08-09) y estuvo a un paso de declarar rota una garantia que estaba sana."""


@dataclasses.dataclass(frozen=True)
class Informe:
    """El conteo, que es lo que la ficha de la capacidad exige como evidencia."""
    ejecutadas: int
    fallidas: int
    errores: int
    omitidas: int
    agotado: bool
    codigo: int | None
    salida: str

    @property
    def sano(self) -> bool:
        """Verde de verdad: **alguna** prueba corrio y **ninguna** fallo ni reviento.

        `ejecutadas > omitidas` no es una formalidad: es la condicion que distingue «la bateria
        paso» de «no se ejecuto nada util». Sin ella, un `--collect-only` heredado o un `conftest`
        hostil darian exactamente el mismo veredicto que un arbol sano.

        **Hubo una clausula `ejecutadas > 0` y se retiro.** La mutacion demostro que era muerta:
        `ejecutadas > omitidas` ya la implica, porque `omitidas` nunca es negativa. Una condicion
        que no puede cambiar ningun veredicto aparenta una garantia que otra ya daba."""
        return (not self.agotado
                and self.ejecutadas > self.omitidas
                and self.fallidas == 0
                and self.errores == 0)


#: Cada cuánto se vigila, DURANTE la batería, que el arnés de mutación no haya arrancado (2026-10-06).
_VIGILANCIA_S = 0.5
# Marca de la ejecución en el entorno del HIJO (nunca en el del plano): la heredan todos sus descendientes, también
# los que se desvinculan con doble fork y cuelgan de init, adonde la foto por ppid no llega `[EJEC]` 2026-10-06.
_VARIABLE_MARCA = "AURA_VERIFICADOR_EJECUCION"


def _matar_arbol(proceso: subprocess.Popen) -> None:
    """Mata el GRUPO **y** a los descendientes que se fueron a su propia sesión.

    pytest puede arrancar hijos —una prueba de integracion que levanta un servicio—. Matar solo a
    pytest los deja huerfanos consumiendo CPU sin que nadie los reclame. Y `killpg` no alcanza a quien abrió
    SU PROPIA sesión: reproducido `[EJEC]` 2026-10-06. Por eso, primero se CONGELA el árbol (SIGSTOP) y se
    fotografía `(pid, starttime)` hasta que la foto no cambia —así no escapa quien nazca durante la foto—, y
    después SIGKILL al grupo y a cada fotografiado que siga siendo el mismo proceso.

    Límite declarado: un proceso que ya cuelga de init antes de la foto (doble fork) solo cae aquí si sigue en el
    grupo de pytest; en `ejecutar_pruebas` lo recoge después `_barrer_marcados`. La firma no cambia: `delegacion`
    también lo usa, y allí no hay marca."""
    try:
        grupo = os.getpgid(proceso.pid)
    except (ProcessLookupError, OSError):
        grupo = None
    if grupo is not None:
        try:
            os.killpg(grupo, signal.SIGSTOP)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    vistos: dict[int, str] = {}
    try:
        for _ in range(5):  # la foto se repite hasta que deja de crecer (acotado)
            nuevos = [(pid, inicio) for pid, inicio in _descendientes(proceso.pid) if pid not in vistos]
            if not nuevos:
                break
            for pid, inicio in nuevos:
                vistos[pid] = inicio
                _senal_si_es_el_mismo(pid, inicio, signal.SIGSTOP)
    finally:
        # Pase lo que pase en la foto (un segundo Ctrl-C, un error), lo congelado SE MATA: un grupo en SIGSTOP
        # sin SIGKILL quedaría parado para siempre (revisión ECC del código).
        try:
            if grupo is None:
                raise ProcessLookupError
            os.killpg(grupo, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proceso.kill()
        for pid, inicio in vistos.items():
            _senal_si_es_el_mismo(pid, inicio, signal.SIGKILL)


def _marcados(marca: str) -> list[tuple[int, str]]:
    """(pid, starttime) de los procesos cuyo entorno inicial lleva la marca de esta ejecución, estén donde estén en
    el árbol. Solo se leen los del propio usuario (el resto da EACCES y se ignora)."""
    buscada = f"{_VARIABLE_MARCA}={marca}".encode()
    propio = os.getpid()
    try:
        entradas = [int(e) for e in os.listdir("/proc") if e.isdigit()]
    except OSError:
        return []
    encontrados: list[tuple[int, str]] = []
    for pid in entradas:
        if pid == propio:
            continue
        # starttime ANTES y DESPUÉS de leer el entorno: si el PID se recicló entre medias, no se anota al nuevo
        # proceso como si fuera el marcado (revisión ECC).
        antes = _estado_proc(pid)
        try:
            entorno = pathlib.Path(f"/proc/{pid}/environ").read_bytes()
        except OSError:
            continue
        if buscada in entorno.split(b"\0"):
            despues = _estado_proc(pid)
            if antes and despues and len(antes) > 19 and len(despues) > 19 and antes[19] == despues[19]:
                encontrados.append((pid, despues[19]))
    return encontrados


def _barrer_marcados(marca: str) -> None:
    """Mata lo que quede vivo de esta ejecución tras cualquier final (normal, plazo, interrupción). Congela y
    repite la búsqueda hasta que deja de crecer, como `_matar_arbol`, y SIGKILL en `finally`.

    Límite declarado: la marca viaja en el entorno, así que la pierde todo descendiente lanzado con un entorno
    CONSTRUIDO (`env -i`, `subprocess.Popen(env={...})`, como hace este mismo módulo) y lo que cuelgue de él; si
    además se desvincula (doble fork), sobrevive. Tampoco se barre lo que nazca tras la 5.ª ronda (fork-bomb)."""
    vistos: dict[int, str] = {}
    try:
        for _ in range(5):
            nuevos = [(pid, inicio) for pid, inicio in _marcados(marca) if pid not in vistos]
            if not nuevos:
                break
            for pid, inicio in nuevos:
                vistos[pid] = inicio
                _senal_si_es_el_mismo(pid, inicio, signal.SIGSTOP)
    finally:
        for pid, inicio in vistos.items():
            _senal_si_es_el_mismo(pid, inicio, signal.SIGKILL)


def _estado_proc(pid: int) -> list[str] | None:
    """Campos de `/proc/<pid>/stat` tras el nombre del ejecutable (que puede llevar espacios y paréntesis)."""
    try:
        return pathlib.Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (OSError, IndexError):
        return None


def _descendientes(raiz_pid: int) -> list[tuple[int, str]]:
    """(pid, starttime) de los descendientes de `raiz_pid` siguiendo los ppid de `/proc`. El starttime identifica
    al proceso: si el PID se reutiliza, deja de coincidir y no se toca a nadie ajeno."""
    hijos: dict[int, list[tuple[int, str]]] = {}
    try:
        entradas = [e for e in os.listdir("/proc") if e.isdigit()]
    except OSError:
        return []
    for entrada in entradas:
        campos = _estado_proc(int(entrada))
        if campos and len(campos) > 19:
            hijos.setdefault(int(campos[1]), []).append((int(entrada), campos[19]))
    encontrados: list[tuple[int, str]] = []
    pendientes = [raiz_pid]
    while pendientes:
        for pid, inicio in hijos.get(pendientes.pop(), []):
            encontrados.append((pid, inicio))
            pendientes.append(pid)
    return encontrados


def _senal_si_es_el_mismo(pid: int, inicio: str, senal: int) -> None:
    """Envía `senal` a `pid` solo si sigue siendo el proceso de la foto. Con pidfd, el starttime se comprueba
    DESPUÉS de abrirlo: a partir de ahí el PID ya no puede reasignarse. Sin pidfd, `os.kill` con la misma
    comprobación (la ventana es mínima)."""
    abrir = getattr(os, "pidfd_open", None)
    enviar = getattr(signal, "pidfd_send_signal", None)
    try:
        fd = abrir(pid) if abrir is not None and enviar is not None else None
    except ProcessLookupError:
        return
    except OSError:
        fd = None
    try:
        campos = _estado_proc(pid)
        if not (campos and len(campos) > 19 and campos[19] == inicio):
            return
        if fd is None or enviar is None:
            os.kill(pid, senal)
        else:
            enviar(fd, senal)
    except OSError:
        pass  # ya no existe, sin permiso, EINVAL…: un fallo al señalar a UNO no puede cortar la muerte del resto
    finally:
        if fd is not None:
            os.close(fd)


def _matar_si_es_el_mismo(pid: int, inicio: str) -> None:
    _senal_si_es_el_mismo(pid, inicio, signal.SIGKILL)


def _cargar_prctl():
    """`prctl` de la libc, resuelto al importar: en el hijo, tras el fork, no se carga ni se importa nada."""
    try:
        import ctypes

        return ctypes.CDLL(None, use_errno=True).prctl
    except Exception:  # noqa: BLE001 — sin prctl (fuera de Linux) no hay esta red; el resto sigue igual
        return None


_PRCTL = _cargar_prctl()


def _preparar_hijo(confinar):
    """El `preexec_fn` del hijo: primero «muere con quien te lanzó» (PR_SET_PDEATHSIG = SIGKILL), después el
    confinamiento de `aislamiento`, si lo hay.

    `[EJEC]` 2026-10-06: si el proceso que llama moría (SIGTERM con la acción por defecto, SIGKILL), ningún
    `finally` corría y pytest seguía vivo sin nadie que le aplicara el plazo. Va ANTES del confinador:
    NO_NEW_PRIVS no lo borra y Landlock no filtra las señales del núcleo. Si el padre murió entre el `fork` y el
    `prctl`, la señal no llegaría nunca: se comprueba y el hijo sale. Límites: solo alcanza a pytest (sus
    descendientes no la heredan) y se dispara al morir el HILO que lanza (hoy el plano no usa hilos)."""
    padre = os.getpid()

    def _preparar() -> None:  # pragma: no cover - corre en el hijo, entre fork y exec
        if _PRCTL is not None:
            if _PRCTL(1, int(signal.SIGKILL), 0, 0, 0) != 0:  # 1 = PR_SET_PDEATHSIG
                raise OSError("prctl(PR_SET_PDEATHSIG)")
            if os.getppid() != padre:
                os._exit(1)
        if callable(confinar):
            confinar()

    return _preparar


def _arnes_corriendo() -> bool:
    """La misma pregunta que la precondición de entrada, hecha DURANTE y AL TERMINAR la batería."""
    return bool(orquestador.mutacion_en_curso())


def _contar(ruta_xml: pathlib.Path) -> tuple[int, int, int, int]:
    """Lee el informe ESTRUCTURADO de pytest. Ante cualquier duda, cero ejecutadas.

    Devolver ceros hace que `sano` sea `False`: si no se puede contar, no se puede afirmar que la
    bateria paso. Es la misma regla que el resto del plano — ante la duda, roja (ADR-0003)."""
    try:
        raiz = ET.parse(ruta_xml).getroot()
    except (ET.ParseError, OSError):
        return (0, 0, 0, 0)
    suites = [raiz] if raiz.tag == "testsuite" else list(raiz.iter("testsuite"))
    if not suites:
        return (0, 0, 0, 0)
    entero = lambda s, k: int(s.get(k) or 0)                                    # noqa: E731
    return (sum(entero(s, "tests") for s in suites),
            sum(entero(s, "failures") for s in suites),
            sum(entero(s, "errors") for s in suites),
            sum(entero(s, "skipped") for s in suites))


def ejecutar_pruebas(pruebas, raiz, limite_s: float = LIMITE_S, confinar=None) -> Informe:
    """Ejecuta la bateria declarada y devuelve **el conteo**, no una impresion.

    `pruebas` son las rutas del contrato (`verificacion.pruebas_minimas`); `raiz` es el directorio
    desde el que se ejecutan. No se aceptan opciones: la linea de ordenes se **construye** aqui a
    partir de rutas, nunca se compone desde texto libre del contrato. Es la regla del CEO sobre las
    capacidades —se nombran por el resultado, `ejecutar_pruebas`, y no ejecutan ordenes arbitrarias
    del sistema operativo—."""
    if orquestador.mutacion_en_curso():
        raise ArnesEnCurso(
            "el arnes de mutacion esta corriendo: el arbol no contiene el codigo real y medirlo "
            "ahora seria medir un mutante")

    rutas = [str(p) for p in (pruebas or []) if str(p).strip()]
    if not rutas:
        return Informe(0, 0, 0, 0, False, None, "el contrato no declara ninguna prueba")

    entorno = {k: os.environ[k] for k in _ENTORNO_MINIMO if k in os.environ}
    # Sin cache de bytecode: una reescritura y una reejecucion en el mismo segundo de reloj hacen
    # que el interprete reutilice el `.pyc` compilado ANTES del cambio, y la bateria mediria el
    # codigo viejo sin que nadie se entere. Medido en el arnes de mutacion: 2 de 15 iteraciones.
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    marca = secrets.token_hex(16)
    entorno[_VARIABLE_MARCA] = marca

    temporal = pathlib.Path(tempfile.mkdtemp(prefix="aura-verificador-"))
    # **TMPDIR siempre dentro del temporal que ya concede escritura** (FASE B): sin un TMPDIR escribible
    # pytest muere o crea `pytest-of-<usuario>` en el cwd (ya ocurrio en el directorio vivo). Se fija
    # SIEMPRE, confinado o no, y pisa al heredado.
    entorno["TMPDIR"] = str(temporal)
    # El confinamiento se construye DESPUES de conocer el temporal: pytest tiene que poder escribir
    # ahi su informe, y un encierro que no lo contemple convierte cada medicion en un cero.
    if callable(confinar) and hasattr(confinar, "con_escritura_en"):
        confinar = confinar.con_escritura_en(temporal)
    informe_xml = temporal / "informe.xml"
    proceso = None
    try:
        proceso = subprocess.Popen(
            [sys.executable, "-m", "pytest", "-q", "--color=no",
             "-p", "no:cacheprovider", f"--junitxml={informe_xml}", *rutas],
            cwd=str(raiz), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env=entorno, start_new_session=True,
            # `confinar` encierra al hijo entre `fork` y `exec` (ver `aislamiento.py`). Es opcional
            # porque este modulo tambien se usa fuera de una delegacion, donde el arbol es el del
            # propio plano y no hay nada de lo que aislarse. Se compone DESPUES de ampliarlo con el
            # temporal: `_preparar_hijo` lo llama tal cual, tras la muerte con el padre.
            preexec_fn=_preparar_hijo(confinar))
        salida, agotado, codigo = _esperar(proceso, limite_s)
        if _arnes_corriendo():
            # El arnes arranco mientras corria la bateria: lo medido puede ser un mutante.
            raise ArnesEnCurso("el arnes de mutacion arranco durante la medicion: el resultado no vale")
        ejecutadas, fallidas, errores, omitidas = _contar(informe_xml)
        return Informe(ejecutadas, fallidas, errores, omitidas, agotado, codigo, salida[-4000:])
    except BaseException:
        # INTERRUPCION (Ctrl-C, una excepcion, el arnes detectado): pytest vive en su propia sesion y no
        # se entera. Sin esto quedaba huerfano `[EJEC]` 2026-10-06. Idempotente si ya estaba muerto.
        if proceso is not None and proceso.poll() is None:
            _matar_arbol(proceso)
            try:
                proceso.communicate(timeout=2)
            except BaseException:  # noqa: BLE001 — drenar es un extra; la excepcion original manda
                pass
        raise
    finally:
        _barrer_marcados(marca)
        shutil.rmtree(temporal, ignore_errors=True)


def _esperar(proceso: subprocess.Popen, limite_s: float) -> tuple[str, bool, int | None]:
    """Espera a pytest vigilando el arnes de mutacion cada `_VIGILANCIA_S`: el arnes muta y restaura en segundos,
    y una bateria dura hasta `LIMITE_S`; mirar solo al empezar y al terminar no lo veria (revision ECC)."""
    fin = time.monotonic() + limite_s
    while True:
        restante = fin - time.monotonic()
        if restante <= 0:
            _matar_arbol(proceso)
            try:
                salida, _ = proceso.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                salida = "(no se pudo leer la salida tras matar el proceso)"
            return salida, True, None
        try:
            salida, _ = proceso.communicate(timeout=min(_VIGILANCIA_S, restante))
            return salida, False, proceso.returncode
        except subprocess.TimeoutExpired:
            if _arnes_corriendo():
                raise ArnesEnCurso("el arnes de mutacion arranco durante la medicion: se detiene la bateria")


def arbol_sano(pruebas, raiz, limite_s: float = LIMITE_S) -> bool:
    """El booleano que `autoconstruccion.ejecutar` espera en `verificacion`.

    **Ante cualquier fallo del propio verificador, `False`.** Si la medicion no se pudo hacer, no se
    puede afirmar que el arbol esta sano — y `ejecutar` revierte, que es lo correcto. Dejar que la
    excepcion propagara tendria un efecto peor: `motor_autonomia` no la captura, el ciclo sale con
    codigo 3 y **la tarea se quema tras un intento**."""
    try:
        return ejecutar_pruebas(pruebas, raiz, limite_s=limite_s).sano
    except Exception:
        return False


def verificador_de(contrato: dict, raiz, limite_s: float = LIMITE_S):
    """El callable listo para pasar como `verificacion`, atado a las pruebas de ESE contrato.

    El liston lo pone el contrato, no el ejecutor: quien decide que hay que comprobar es quien
    autorizo el cambio. Un contrato sin `pruebas_minimas` no produce un verificador permisivo —
    produce uno que devuelve `False`, porque `ejecutar_pruebas` cuenta cero ejecutadas."""
    minimas = ((contrato or {}).get("verificacion") or {}).get("pruebas_minimas") or []
    return lambda: arbol_sano(minimas, raiz, limite_s=limite_s)
