"""Arnes de mutacion permanente de AURA.

Por que existe: un arnes ad-hoc anterior declaro "7 mutantes sobreviven" en produccion y la
afirmacion era falsa. Aquel arnes parseaba el TEXTO de salida de pytest para decidir si una
prueba paso o fallo, en vez de mirar el codigo de retorno del proceso. Un arnes que miente sobre
la cobertura de sus garantias es peor que no tener arnes: genera una falsa sensacion de seguridad.

Este modulo existe para que eso no vuelva a pasar. Reglas de diseno que no son negociables:

  1. La base debe estar en verde ANTES de mutar nada. Si no lo esta, no se informa de ningun
     mutante (informar "sobrevive"/"detectado" sobre una base rota es indistinguible de mentir).
  2. La decision de "paso" o "fallo" es SIEMPRE el returncode del subprocess de pytest. El texto
     de salida solo se usa para *informar* que pruebas fallaron, nunca para decidir el estado.
  3. El contenido original de cada fichero mutado se restaura siempre (try/finally), incluso si
     el subprocess lanza una excepcion, y se verifica byte a byte tras restaurar.
  4. Si el patron `buscar` no aparece en el fichero, el mutante no se pudo aplicar: NO_APLICADO.
     Nunca "detectado" (eso reportaria una garantia como probada cuando en realidad la garantia
     nunca se llego a mutar).
  5. Un mutante cuyas pruebas no terminan en `timeout_s` NUNCA es "detectado": es TIMEOUT
     (2026-08-04). Sin este limite, degradar una condicion de parada de un bucle cuelga el arnes
     entero en vez de reportarlo -- dano ya medido: 15+ horas de CPU con un proceso huerfano
     (ver `mutaciones/motor-ciclo.toml`, mutantes M2 y M3).
  6. La mutacion NUNCA escribe en el arbol del proyecto (2026-10-25): la base y los mutantes corren sobre
     una COPIA aislada fuera del proyecto (`_copia_aislada`), que se borra al terminar, y un `fichero` que
     saliera de la copia (absoluto o con `../` de mas) se rechaza sin tocarlo. Medido `[EJEC]`: el servicio
     `aura-receptor-nodos` y el despertador de AURORA cargan codigo de este mismo worktree; un reinicio
     mientras el fichero estaba mutado en el sitio habria arrancado produccion con un mutante. La unica
     escritura posible en el proyecto es restaurar un diario HEREDADO de una ejecucion anterior en el sitio.

Formato de declaracion (mutaciones/*.toml), ver ejemplos en la carpeta `mutaciones/`:

    incremento = "descripcion del incremento"
    pruebas = ["tests/unit/test_x.py", "tests/integration/test_y.py"]
    timeout_s = 60  # opcional; por defecto _TIMEOUT_S_POR_DEFECTO. GLOBAL para todo el fichero.

    [[mutante]]
    id = "M1"
    garantia = "frase humana: que garantia degrada este mutante"
    fichero = "aura_skeleton/core/reglas.py"
    buscar = \"\"\"texto exacto a sustituir\"\"\"
    sustituir = \"\"\"texto de reemplazo\"\"\"

`pruebas` es la lista global de pruebas para el incremento; un mutante puede llevar su propia
clave `pruebas` que la sobreescribe (por ejemplo, para acotar la verificacion a una prueba mas
especifica que la garantia de ese mutante concreto). `timeout_s`, en cambio, NO es por-mutante:
un incremento ya conoce cuanto tarda su propia suite en verde, asi que un unico plazo generoso
frente a eso basta para todos sus mutantes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Estados posibles de un mutante. Se dejan como constantes de texto (no Enum) porque el contrato
# del arnes los fija como literales exactos ("detectado" / "SOBREVIVE" / "NO_APLICADO") y las
# meta-pruebas comparan contra esas cadenas directamente.
_DETECTADO = "detectado"
_SOBREVIVE = "SOBREVIVE"
_NO_APLICADO = "NO_APLICADO"
# AMBIGUO: la declaracion del mutante no permite concluir nada (patron repetido, mutante que no
# degrada, o pytest que no llego a ejercitar las pruebas). NUNCA se cuenta como exito.
_AMBIGUO = "AMBIGUO"
# TIMEOUT: las pruebas del mutante no terminaron dentro del plazo (2026-08-04). Se distingue de
# SOBREVIVE a proposito -aunque ninguno de los dos cuenta jamas como exito- porque informa mejor:
# un TIMEOUT suele senalar que falta una garantia de TERMINACION (un bucle que no sabe parar),
# mientras que SOBREVIVE dice que las pruebas corrieron completas y no se dieron cuenta. Confundir
# ambos en el informe le ocultaria al humano que revisa la diferencia entre "nadie lo prueba" y
# "esto cuelga el proceso".
_TIMEOUT = "TIMEOUT"

# Plazo por defecto para las pruebas de UN mutante, si el TOML no declara `timeout_s` propio. Dano
# ya medido sin este limite (mutaciones/motor-ciclo.toml, M2 y M3 retirados 2026-08-03): degradar
# una condicion de parada de un bucle produce un BUCLE INFINITO y el arnes se colgaba en vez de
# reportar SOBREVIVE, dejando un proceso huerfano 15+ horas consumiendo CPU. 60s es generoso frente
# a una suite de pruebas normal (la de motor-ciclo.toml tarda ~2s) y acotado frente a un mutante que
# de verdad no termina nunca.
_TIMEOUT_S_POR_DEFECTO = 60.0

# DIARIO de la mutación en curso (2026-10-06). Un SIGKILL al arnés (`timeout -k`, OOM, corte de luz) no ejecuta
# ningún `finally`: el fichero quedaba MUTADO sin que nadie lo supiera. Antes de mutar se anota aquí, en la raíz
# del proyecto, qué fichero y con qué bytes originales; se borra tras restaurar. Si existe al arrancar, la
# ejecución anterior murió a medias y se restaura antes de nada (`recuperar_mutacion_interrumpida`).
# Desde 2026-10-25 el arnés YA NO ESCRIBE el diario: muta una copia aislada (regla 6) y un SIGKILL deja mutada la
# copia, nunca el proyecto, así que no hay nada que recuperar. Escribirlo en la copia era código muerto (mutantes
# AL-M4/AL-M5 supervivientes, retirados a `mutaciones/retiradas/`). La recuperación sobre la raíz real SE CONSERVA
# para los diarios que dejaran las ejecuciones anteriores, que sí mutaban en el sitio.
_DIARIO = ".mutar-en-curso.json"

# COPIA AISLADA (regla 6). Lo que no se copia: historia de git, caches y artefactos que no son del proyecto, y el
# diario (una copia nunca hereda una mutación en curso). Prefijo reconocible: tras un SIGKILL la copia queda en el
# directorio temporal del sistema y se identifica por él; el proyecto real sigue intacto.
_NO_SE_COPIA = (".git", ".venv", "__pycache__", ".pytest_cache", "pytest-of-*", "graphify-out", "node_modules", _DIARIO)
_PREFIJO_COPIA = "aura-mutar-"
#: Marca de dueño de cada copia (pid + starttime): permite retirar al arrancar las copias que dejó un arnés muerto
#: por SIGKILL, y solo esas. Un directorio sin marca nunca se toca.
_MARCA_DUENO = ".aura-mutar-dueno.json"

# Señales con las que se detiene al arnés por las buenas. Cualquiera de ellas restaura y limpia (ver `main`).
_SENALES_DE_PARADA = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class _InterrupcionDelArnes(KeyboardInterrupt):
    """SIGTERM/SIGHUP tratados como Ctrl-C: el `finally` restaura y `_ejecutar_pytest` mata el árbol."""


def _escribir_atomico(ruta: Path, datos: bytes) -> None:
    """Escribe `datos` sin estado intermedio visible: temporal en el mismo directorio + `os.replace`.

    `write_bytes` trunca y LUEGO escribe: una señal en medio dejaba el fuente vacío o a medias (revisión ECC).
    Si la ruta es un enlace simbólico se escribe en su destino (el enlace sigue siendo enlace), y si algo falla el
    temporal se borra: nunca queda `.x.mutar-tmp` en el árbol."""
    ruta = ruta.resolve() if ruta.is_symlink() else ruta
    temporal = ruta.with_name(f".{ruta.name}.mutar-tmp")
    try:
        with open(temporal, "wb") as f:
            f.write(datos)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(temporal, ruta.stat().st_mode & 0o7777)
        except FileNotFoundError:
            pass
        os.replace(temporal, ruta)
    except BaseException:
        try:
            temporal.unlink()
        except FileNotFoundError:
            pass
        raise


def _anotar_diario(raiz: str, fichero: str, original: bytes, mutado: bytes, pid: int | None = None) -> None:
    """Anota qué fichero se va a mutar, sus bytes originales, la huella del contenido MUTADO y el arnés dueño.

    La huella y el dueño hacen prudente la recuperación: solo se restaura si el fichero sigue siendo el mutado
    (nadie lo ha tocado después) y si el arnés que lo mutó ya no existe (revisión ECC)."""
    dueno = os.getpid() if pid is None else pid
    campos = _estado_proc(dueno)
    datos = {
        "fichero": fichero,
        "original_b64": base64.b64encode(original).decode("ascii"),
        "mutado_sha256": hashlib.sha256(mutado).hexdigest(),
        "pid": dueno,
        "inicio": campos[19] if campos and len(campos) > 19 else "",
    }
    _escribir_atomico(Path(raiz) / _DIARIO, json.dumps(datos).encode("utf-8"))


def recuperar_mutacion_interrumpida(raiz: str = ".") -> list[str]:
    """Si una ejecución anterior murió con un fichero mutado, lo restaura desde el diario. Devuelve los ficheros."""
    diario = Path(raiz) / _DIARIO
    if not diario.exists():
        return []
    try:
        datos = json.loads(diario.read_text(encoding="utf-8"))
        fichero = str(datos["fichero"])
        original = base64.b64decode(datos["original_b64"])
        mutado_sha256 = str(datos["mutado_sha256"])
        pid, inicio = int(datos["pid"]), str(datos["inicio"])
    except (ValueError, KeyError, TypeError) as e:
        raise RuntimeError(f"El diario {diario} es ilegible ({e}): revísalo a mano antes de volver a mutar.") from e
    campos = _estado_proc(pid)
    if campos and len(campos) > 19 and campos[19] == inicio and campos[0] != "Z":
        raise RuntimeError(f"Otro arnés (pid {pid}) está mutando esta raíz: no se toca nada ni se ejecuta este.")
    ruta = Path(raiz) / fichero
    actual = ruta.read_bytes() if ruta.exists() else None
    if actual is None or hashlib.sha256(actual).hexdigest() != mutado_sha256:
        # Después del corte alguien restauró o editó el fichero: el diario está obsoleto y no se pisa su trabajo.
        print(
            f"AVISO: diario obsoleto ({fichero} ya no contiene el mutante): se descarta sin tocar el fichero.",
            file=sys.stderr,
        )
        diario.unlink()
        return []
    _escribir_atomico(ruta, original)
    diario.unlink()
    return [fichero]


@dataclass
class ResultadoMutante:
    """Resultado de evaluar un unico mutante."""

    id: str
    garantia: str
    estado: str  # "detectado" | "SOBREVIVE" | "NO_APLICADO" | "AMBIGUO" | "TIMEOUT"
    pruebas_que_fallaron: str  # solo informativo; la decision del estado ya se tomo por returncode


@dataclass
class ResultadoMutacion:
    """Resultado de ejecutar el arnes completo sobre un fichero de declaracion."""

    base_verde: bool
    resultados: list[ResultadoMutante]
    detectados: int
    supervivientes: int
    no_aplicados: int
    ambiguos: int
    timeouts: int

    @property
    def concluyente(self) -> bool:
        """Solo es concluyente si TODO mutante murio. Un ambiguo, un no aplicado o un timeout invalidan
        el conjunto -- un TIMEOUT es una garantia sin red exactamente igual que un SOBREVIVE, solo que
        por un motivo distinto (ver comentario de `_TIMEOUT` mas arriba)."""
        return (
            self.base_verde
            and self.supervivientes == 0
            and self.no_aplicados == 0
            and self.ambiguos == 0
            and self.timeouts == 0
        )


def _matar_arbol_de_procesos(proceso: subprocess.Popen) -> None:
    """SIGKILL al GRUPO de procesos completo, no solo al hijo directo.

    Por que un grupo y no `proceso.kill()`: pytest puede arrancar sus propios subprocesos (un test de
    integracion que levanta un servicio real, por ejemplo). Matar solo el proceso de pytest los deja
    HUERFANOS -reparentados a init- siguiendo vivos y consumiendo CPU: es el dano ya medido en
    produccion, 15+ horas de CPU con un proceso huerfano. `_ejecutar_pytest` lanza el subprocess con
    `start_new_session=True` precisamente para que tenga su PROPIO grupo (nunca comparte el nuestro:
    matar nuestro propio grupo seria un suicidio del arnes), y aqui se manda la senal a ese grupo
    entero via PID NEGATIVO.
    """
    # Primero la FOTO de descendientes: después de matar al grupo se re-parentan a init y ya no se encuentran.
    # Incluye a los que abrieron su PROPIA sesión (escapan a killpg): ya ocurrió `[EJEC]` 2026-10-06.
    descendientes = _descendientes(proceso.pid)
    try:
        os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass  # ya habia terminado por su cuenta entre el TimeoutExpired y este punto: nada que matar
    for pid, inicio in descendientes:
        _matar_si_es_el_mismo(pid, inicio)


def _estado_proc(pid: int) -> list[str] | None:
    """Campos de `/proc/<pid>/stat` tras el nombre del ejecutable (que puede llevar espacios y paréntesis)."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (OSError, IndexError):
        return None


def _descendientes(raiz_pid: int) -> list[tuple[int, str]]:
    """(pid, starttime) de todos los descendientes de `raiz_pid`, siguiendo los enlaces ppid de `/proc`.

    El starttime identifica al proceso: si el PID se reutiliza entre la foto y la señal, ya no coincide y no se
    mata a nadie ajeno (revisión ECC). Límite declarado: un proceso que hizo doble fork y ya cuelga de init
    antes de la foto no se encuentra."""
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


def _matar_si_es_el_mismo(pid: int, inicio: str) -> None:
    """SIGKILL a `pid` solo si sigue siendo el proceso de la foto (mismo starttime), vía pidfd si existe."""
    abrir = getattr(os, "pidfd_open", None)
    enviar = getattr(signal, "pidfd_send_signal", None)
    if abrir is None or enviar is None:
        abrir = enviar = None
    try:
        fd = abrir(pid) if abrir is not None else None
    except ProcessLookupError:
        return
    except OSError:
        fd = None  # pidfd no disponible (ENOSYS, EMFILE…): se cae a `os.kill` con la misma comprobación
    try:
        if fd is None or enviar is None:
            campos = _estado_proc(pid)
            if campos and len(campos) > 19 and campos[19] == inicio:
                os.kill(pid, signal.SIGKILL)
            return
        try:
            campos = _estado_proc(pid)  # con el pidfd abierto, el PID ya no puede reasignarse a otro proceso
            if campos and len(campos) > 19 and campos[19] == inicio:
                enviar(fd, signal.SIGKILL)
        finally:
            os.close(fd)
    except (ProcessLookupError, PermissionError):
        pass


def _cargar_prctl():
    """`prctl` de la libc, resuelto UNA vez al importar: en el hijo, tras el fork, no se puede importar ni cargar
    nada (candados de import/malloc con hilos; revisión ECC). Fuera de Linux no existe y el arnés sigue sin esta red."""
    try:
        import ctypes

        return ctypes.CDLL(None, use_errno=True).prctl
    except Exception:  # noqa: BLE001
        return None


_PRCTL = _cargar_prctl()


def _morir_con_el_arnes() -> None:
    """En el hijo, antes de `exec`: PR_SET_PDEATHSIG = SIGKILL. Si el arnés muere —incluso por SIGKILL, donde
    ningún `finally` corre— el kernel mata a pytest en vez de dejarlo huérfano (el caso de 48 min).

    Límites declarados: alcanza al pytest (hijo directo), no a sus descendientes —el kernel lo borra en ellos—; y
    se dispara al morir el HILO que hizo el fork, que en el arnés es siempre el principal."""
    if _PRCTL is not None:
        _PRCTL(1, int(signal.SIGKILL), 0, 0, 0)  # 1 = PR_SET_PDEATHSIG


def _ejecutar_pytest(pruebas: list[str], raiz: str, timeout_s: float) -> tuple[int | None, str, bool]:
    """Ejecuta pytest con un LIMITE DE TIEMPO y devuelve (returncode, salida, agotado).

    Devuelve el codigo entero (no un booleano) porque pytest distingue casos que el arnes NO puede
    confundir (auditoria 2026-08-02):

      0 -> todo paso
      1 -> alguna PRUEBA fallo (una asercion se ejercito y no se cumplio)
      2 -> pytest se interrumpio: error de COLECCION (p. ej. el mutante rompio la sintaxis)
      5 -> no se recogio ninguna prueba

    Tratar el 2 como "detectado" seria mentir: significa que el fichero ni siquiera se pudo importar,
    no que una prueba protegiera la garantia. El texto se devuelve solo para informar.

    `agotado=True` (returncode devuelto como None) significa que las pruebas NO terminaron dentro de
    `timeout_s`: nadie llego a decidir si pasan o fallan, asi que quien llama a esta funcion NUNCA
    puede tratarlo como "detectado" (2026-08-04, ver `_TIMEOUT` mas arriba -- este es el motivo por
    el que existe: sin limite de tiempo, un mutante que degrada la condicion de parada de un bucle
    cuelga el arnes entero en vez de reportarlo).
    """
    # PYTHONDONTWRITEBYTECODE=1: hallazgo de esta verificacion (2026-08-04), no del timeout en si.
    # Sin esto, `_evaluar_mutante` es una CARRERA real: el cache de bytecode (`__pycache__`) de
    # Python invalida por (mtime en SEGUNDOS truncados, tamano). Un mutante como "return a + b" ->
    # "return a - b" no cambia el tamano del fichero, y si la reescritura y la reejecucion caen en
    # el MISMO segundo de reloj, el interprete reutiliza el .pyc COMPILADO ANTES DE MUTAR: la
    # prueba se ejecuta sobre el codigo VIEJO sin que nadie se entere, y el mutante se reporta
    # SOBREVIVE (o "detectado" en la base) por una razon ajena a la mutacion. Medido: 2/15
    # iteraciones con el mismo mutante dieron un estado erroneo antes de este fix, 0/30 despues.
    # Deshabilitar la escritura de bytecode fuerza a recompilar SIEMPRE desde el .py en disco.
    entorno = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proceso = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", "--color=no", *pruebas],
        cwd=raiz,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=entorno,
        # Sesion propia (= grupo de procesos propio): permite matar el ARBOL completo por PID
        # negativo sin arriesgarse a alcanzar el grupo del propio arnes. Ver `_matar_arbol_de_procesos`.
        start_new_session=True,
        preexec_fn=_morir_con_el_arnes,
    )
    try:
        salida, _ = proceso.communicate(timeout=timeout_s)
        return proceso.returncode, salida, False
    except subprocess.TimeoutExpired:
        try:
            _matar_arbol_de_procesos(proceso)
            # Tras el SIGKILL hay que drenar el pipe (o el proceso queda zombie) y recoger lo que se
            # alcanzo a imprimir, solo para informar -- la decision de estado ya es "agotado".
            try:
                salida, _ = proceso.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                salida = "(no se pudo leer la salida del proceso tras matarlo)"
        except BaseException:
            # Una interrupción DENTRO de la rama del timeout no la ve el `except BaseException` hermano: se mata el
            # árbol aquí también (idempotente) antes de propagar (revisión ECC).
            _matar_arbol_de_procesos(proceso)
            raise
        return None, salida, True
    except BaseException:
        # INTERRUPCIÓN (Ctrl-C, SIGTERM, error): pytest vive en su propia sesión y la señal no le llega. Sin
        # esto quedaba huérfano, y con un mutante que cuelga, para siempre (`[EJEC]` 2026-10-06: 48 min).
        _matar_arbol_de_procesos(proceso)
        try:
            proceso.communicate(timeout=2)
        except BaseException:  # noqa: BLE001 — drenar es un extra; la excepción original es la que importa
            pass
        raise


def _extraer_pruebas_que_fallaron(salida: str) -> str:
    """Extrae del texto de pytest que pruebas fallaron, solo para el informe humano.

    Esto NO participa en la decision de estado (esa ya se tomo por returncode en
    `_ejecutar_pytest`); es pura conveniencia para que el informe diga algo mas util que "fallo".
    """
    lineas_relevantes = [linea for linea in salida.splitlines() if linea.startswith(("FAILED ", "ERROR "))]
    if lineas_relevantes:
        return "\n".join(lineas_relevantes)
    return salida.strip()


def _evaluar_mutante(
    mutante: dict[str, Any], pruebas: list[str], raiz: str, timeout_s: float, limite: str | None = None
) -> ResultadoMutante:
    """Aplica un mutante, ejecuta sus pruebas y restaura el fichero pase lo que pase.

    `limite` es la raiz de la copia aislada: un `fichero` que resuelva fuera de ella no se lee ni se escribe."""
    id_mutante = str(mutante["id"])
    garantia = str(mutante.get("garantia", ""))
    ruta_fichero = (Path(raiz) / str(mutante["fichero"])).resolve()
    if not ruta_fichero.is_relative_to(Path(limite if limite is not None else raiz).resolve()):
        # `Path(raiz) / "/abs"` descarta la raiz y `../` de mas sale de ella: mutar ahi seria escribir FUERA de la
        # copia aislada, quiza en el arbol vivo (revision de seguridad 2026-10-25). Jamas se aplica.
        return ResultadoMutante(
            id=id_mutante,
            garantia=garantia,
            estado=_AMBIGUO,
            pruebas_que_fallaron=f"el fichero {mutante['fichero']!r} queda fuera de la raiz de la copia: no se muta",
        )
    buscar = str(mutante["buscar"])
    sustituir = str(mutante["sustituir"])

    original_bytes = ruta_fichero.read_bytes()
    contenido = original_bytes.decode("utf-8")

    apariciones = contenido.count(buscar)
    if apariciones == 0:
        # Patron ausente: el mutante nunca llego a aplicarse. Jamas "detectado" -- eso mentiria
        # sobre haber probado una garantia que en realidad no se toco.
        return ResultadoMutante(id=id_mutante, garantia=garantia, estado=_NO_APLICADO, pruebas_que_fallaron="")
    if apariciones > 1:
        # AMBIGUO (auditoria 2026-08-02): con el patron repetido se mutaria la PRIMERA aparicion, que
        # puede ser un comentario o codigo inocuo, dejando intacto lo que se queria degradar. El
        # resultado seria un "SOBREVIVE" falso: parece un hueco de cobertura y es una declaracion mal
        # escrita. Se rechaza en vez de adivinar cual de las N era la buena.
        return ResultadoMutante(
            id=id_mutante,
            garantia=garantia,
            estado=_AMBIGUO,
            pruebas_que_fallaron=f"el patron aparece {apariciones} veces en {mutante['fichero']}: amplialo hasta que sea unico",
        )
    if buscar == sustituir:
        # Mutante degenerado: no degrada nada, luego su "SOBREVIVE" no informaria de ningun hueco.
        return ResultadoMutante(
            id=id_mutante,
            garantia=garantia,
            estado=_AMBIGUO,
            pruebas_que_fallaron="'buscar' y 'sustituir' son identicos: el mutante no degrada nada",
        )

    contenido_mutado = contenido.replace(buscar, sustituir, 1)
    estado = _SOBREVIVE
    pruebas_que_fallaron = ""
    try:
        _escribir_atomico(ruta_fichero, contenido_mutado.encode("utf-8"))
        codigo, salida, agotado = _ejecutar_pytest(pruebas, raiz, timeout_s)
        if agotado:
            # Las pruebas NO terminaron en tiempo razonable: nadie llego a decidir si pasan o
            # fallan. JAMAS "detectado" -- eso mentiria sobre una garantia que nunca se ejercito
            # hasta el final. Ver el comentario de `_TIMEOUT` sobre por que es un estado propio.
            estado = _TIMEOUT
            pruebas_que_fallaron = (
                f"las pruebas no terminaron en {timeout_s:.0f}s (posible bucle infinito):\n"
                f"{_extraer_pruebas_que_fallaron(salida)}"
            )
        elif codigo == 0:
            # Las pruebas siguen en verde a pesar de la mutacion: la garantia NO esta cubierta.
            estado = _SOBREVIVE
        elif codigo == 1:
            # Una PRUEBA fallo: la garantia SI esta cubierta. Unico caso que merece "detectado".
            estado = _DETECTADO
            pruebas_que_fallaron = _extraer_pruebas_que_fallaron(salida)
        else:
            # pytest no llego a ejercitar las pruebas (error de coleccion, sintaxis rota, nada que
            # recoger). Contarlo como "detectado" daria confianza falsa: no se probo la garantia.
            estado = _AMBIGUO
            pruebas_que_fallaron = f"pytest termino con codigo {codigo} sin ejercitar las pruebas:\n{_extraer_pruebas_que_fallaron(salida)}"
    finally:
        # Restauracion garantizada: corre incluso si _ejecutar_pytest lanza una excepcion o el
        # proceso se interrumpe. La excepcion (si la hubo) sigue propagandose despues de esto.
        # Con las señales de parada BLOQUEADAS: una segunda señal no puede cortar la restauración a medias. Desde la
        # regla 6 la restauración es de la COPIA; se conserva porque el informe exige una base intacta para cada mutante.
        # Si la señal estaba pendiente y salta justo al bloquear, la restauración corre IGUAL (finally anidado).
        mascara_previa = None
        try:
            mascara_previa = _bloquear_senales()
        finally:
            try:
                _escribir_atomico(ruta_fichero, original_bytes)
                if ruta_fichero.read_bytes() != original_bytes:
                    # Verificacion byte a byte: si esto no se cumple, el arnes mismo esta roto y no debe
                    # informar nada como si todo estuviera bien.
                    raise RuntimeError(f"No se pudo restaurar {ruta_fichero} tras evaluar el mutante {id_mutante}")
            finally:
                _desbloquear_senales(mascara_previa)

    return ResultadoMutante(id=id_mutante, garantia=garantia, estado=estado, pruebas_que_fallaron=pruebas_que_fallaron)


def _bloquear_senales() -> set | None:
    """Bloquea las señales de parada y devuelve la máscara ANTERIOR (para restaurarla tal cual, no desbloquear a
    ciegas lo que el llamador tuviera bloqueado; revisión ECC). None fuera del hilo principal."""
    if threading.current_thread() is not threading.main_thread():
        return None
    return signal.pthread_sigmask(signal.SIG_BLOCK, _SENALES_DE_PARADA)


def _desbloquear_senales(mascara_previa: set | None) -> None:
    if mascara_previa is not None:
        signal.pthread_sigmask(signal.SIG_SETMASK, mascara_previa)


def _raiz_del_repositorio(origen: Path) -> Path:
    """La raíz del repositorio git que contiene `origen`, o `origen` si no está en ninguno.

    Se copia el repositorio entero y no solo `origen`: las pruebas reales leen ficheros hermanos (`entorno/`,
    `milestones/`) y una copia parcial las pondría en rojo por estructura, no por el mutante."""
    try:
        proceso = subprocess.run(
            ["git", "-C", str(origen), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
    except OSError as e:
        print(f"AVISO: no se pudo consultar git ({e}); se copia solo la raíz pedida.", file=sys.stderr)
        return origen
    if proceso.returncode != 0 or not proceso.stdout.strip():
        return origen
    raiz = Path(proceso.stdout.strip()).resolve()
    return raiz if origen.is_relative_to(raiz) else origen


@contextmanager
def _copia_aislada(raiz: str):
    """Copia el proyecto a un directorio temporal PROPIO (0700, fuera del proyecto) y cede la raíz equivalente.

    Se borra al salir, también si hay excepción o interrupción. Con SIGKILL no corre ningún `finally`: la copia
    queda en el temporal con el prefijo `_PREFIJO_COPIA`, y el proyecto real no se ha tocado nunca."""
    origen = Path(raiz).resolve()
    proyecto = _raiz_del_repositorio(origen)
    destino = Path(tempfile.mkdtemp(prefix=_PREFIJO_COPIA)).resolve()
    try:
        if destino.is_relative_to(proyecto):
            raise RuntimeError(f"La copia aislada caería dentro del proyecto ({destino}): revisa TMPDIR.")
        campos = _estado_proc(os.getpid())
        inicio = campos[19] if campos and len(campos) > 19 else ""
        (destino / _MARCA_DUENO).write_text(json.dumps({"pid": os.getpid(), "inicio": inicio}), encoding="utf-8")
        copia = destino / proyecto.name
        shutil.copytree(
            proyecto,
            copia,
            symlinks=False,
            ignore=shutil.ignore_patterns(*_NO_SE_COPIA),
            ignore_dangling_symlinks=True,
        )
        yield str(copia / origen.relative_to(proyecto)), str(copia)
    finally:
        shutil.rmtree(destino, ignore_errors=True)


def _retirar_copias_huerfanas() -> list[str]:
    """Retira las copias aisladas que dejó un arnés muerto (SIGKILL: ningún `finally`). Devuelve las retiradas.

    Solo las del mismo usuario, con el prefijo y con marca de dueño legible cuyo proceso ya no existe (mismo pid y
    starttime). Una copia sin marca, ajena, ilegible o de un arnés vivo NO se toca."""
    retiradas: list[str] = []
    for d in sorted(Path(tempfile.gettempdir()).glob(f"{_PREFIJO_COPIA}*")):
        try:
            if d.is_symlink() or not d.is_dir() or d.stat().st_uid != os.getuid():
                continue
            datos = json.loads((d / _MARCA_DUENO).read_text(encoding="utf-8"))
            pid, inicio = int(datos["pid"]), str(datos["inicio"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        campos = _estado_proc(pid)
        if campos and len(campos) > 19 and campos[19] == inicio and campos[0] != "Z":
            continue
        shutil.rmtree(d, ignore_errors=True)
        retiradas.append(str(d))
    return retiradas


def ejecutar(ruta_toml: str, raiz: str = ".") -> ResultadoMutacion:
    """Ejecuta el arnes de mutacion declarado en `ruta_toml`, con `raiz` como raiz del proyecto.

    Contrato (no cambiar sin cambiar tambien las meta-pruebas en tests/unit/test_arnes_mutacion.py):
      - Si la base (las pruebas declaradas) no esta en verde ANTES de mutar, se devuelve de
        inmediato con `base_verde=False` y `resultados=[]`, sin tocar ni un fichero.
      - Cada mutante se evalua con sus propias pruebas si las declara, o con las globales si no.
      - Base y mutantes corren en una COPIA aislada (regla 6): el arbol de `raiz` solo se lee.
    """
    restaurados = recuperar_mutacion_interrumpida(raiz)
    if restaurados:
        print(
            f"AVISO: una ejecución anterior murió a medias; restaurado desde el diario: {restaurados}", file=sys.stderr
        )
    with open(ruta_toml, "rb") as f:
        declaracion: dict[str, Any] = tomllib.load(f)

    pruebas_globales: list[str] = list(declaracion.get("pruebas", []))
    mutantes: list[dict[str, Any]] = list(declaracion.get("mutante", []))
    # `timeout_s` es GLOBAL para todo el fichero de declaracion (no por-mutante): un incremento ya
    # sabe de antemano cuanto tarda su propia suite en verde (aqui, ~2s para motor-ciclo.toml), asi
    # que un unico plazo generoso frente a eso basta para todos sus mutantes sin anadir superficie
    # de configuracion por mutante que nadie ha pedido todavia.
    timeout_s: float = float(declaracion.get("timeout_s", _TIMEOUT_S_POR_DEFECTO))

    # Base en verde: se verifica con la UNION de todas las pruebas que se van a usar (las
    # globales mas cualquier override por-mutante), para no dejar colarse una prueba ya rota que
    # luego se confundiria con un mutante "detectado" por razones ajenas a la mutacion.
    pruebas_a_verificar: list[str] = list(pruebas_globales)
    for mutante in mutantes:
        for prueba in mutante.get("pruebas", []):
            if prueba not in pruebas_a_verificar:
                pruebas_a_verificar.append(prueba)

    # `_ejecutar_pytest` devuelve el RETURNCODE, no un booleano: 0 es exito. Compararlo
    # explicitamente evita el error clasico de tratar el 0 como falso. Si la base misma se agotara
    # (agotado=True), el returncode devuelto es None, y `None == 0` ya es False: no hace falta un
    # caso especial para que una base colgada tambien cuente como "no verde".
    huerfanas = _retirar_copias_huerfanas()
    if huerfanas:
        print(f"AVISO: retiradas copias aisladas de arneses muertos: {huerfanas}", file=sys.stderr)
    with _copia_aislada(raiz) as (raiz_copia, limite):
        print(f"Arnés: muta una copia aislada ({raiz_copia}); el árbol original solo se lee.", file=sys.stderr)
        codigo_base, _, _ = _ejecutar_pytest(pruebas_a_verificar, raiz_copia, timeout_s)
        base_verde = codigo_base == 0
        if not base_verde:
            # Nunca informar de mutantes con la base en rojo: es la regla que el arnes historico violo.
            return ResultadoMutacion(
                base_verde=False,
                resultados=[],
                detectados=0,
                supervivientes=0,
                no_aplicados=0,
                ambiguos=0,
                timeouts=0,
            )

        resultados: list[ResultadoMutante] = []
        for mutante in mutantes:
            pruebas_del_mutante = list(mutante.get("pruebas", pruebas_globales))
            resultados.append(_evaluar_mutante(mutante, pruebas_del_mutante, raiz_copia, timeout_s, limite))

    detectados = sum(1 for r in resultados if r.estado == _DETECTADO)
    supervivientes = sum(1 for r in resultados if r.estado == _SOBREVIVE)
    no_aplicados = sum(1 for r in resultados if r.estado == _NO_APLICADO)
    ambiguos = sum(1 for r in resultados if r.estado == _AMBIGUO)
    timeouts = sum(1 for r in resultados if r.estado == _TIMEOUT)

    return ResultadoMutacion(
        base_verde=True,
        resultados=resultados,
        detectados=detectados,
        supervivientes=supervivientes,
        no_aplicados=no_aplicados,
        ambiguos=ambiguos,
        timeouts=timeouts,
    )


def _formatear_informe(resultado: ResultadoMutacion, ruta_toml: str) -> str:
    """Informe legible en texto plano. No decide nada -- el returncode de main() ya se decidio."""
    lineas = [f"Arnes de mutacion: {ruta_toml}"]

    if not resultado.base_verde:
        lineas.append("BASE EN ROJO: las pruebas declaradas no pasan antes de mutar nada.")
        lineas.append("No se evaluo ningun mutante (una base en rojo invalida cualquier resultado).")
        return "\n".join(lineas)

    lineas.append(f"Base en verde. Mutantes evaluados: {len(resultado.resultados)}")
    # `.get` con marca por defecto en vez de indexacion directa: un estado sin marca declarada
    # reventaba el informe entero con KeyError y ocultaba TODOS los resultados —incluidos los
    # supervivientes—. Un informe que no se puede leer es peor que uno con una marca fea.
    marcas = {_DETECTADO: "OK", _SOBREVIVE: "!!", _NO_APLICADO: "??", _AMBIGUO: "~~", _TIMEOUT: "XX"}
    for r in resultado.resultados:
        lineas.append(f"  [{marcas.get(r.estado, '??')}] {r.id} ({r.estado}): {r.garantia}")
        if r.estado == _SOBREVIVE:
            lineas.append("        garantia NO verificada por ninguna prueba declarada")
        elif r.estado == _NO_APLICADO:
            lineas.append("        el patron 'buscar' ya no existe en el fichero (declaracion obsoleta)")
        elif r.estado == _AMBIGUO:
            lineas.append("        declaracion ambigua: el patron no identifica un unico punto del codigo")
        elif r.estado == _TIMEOUT:
            lineas.append("        las pruebas no terminaron en el plazo: posible bucle infinito sin cubrir")
        elif r.pruebas_que_fallaron:
            for linea_falla in r.pruebas_que_fallaron.splitlines()[:3]:
                lineas.append(f"        {linea_falla}")

    lineas.append("")
    lineas.append(
        f"Total: {resultado.detectados} detectados, {resultado.supervivientes} sobreviven, "
        f"{resultado.no_aplicados} no aplicados, {resultado.ambiguos} ambiguos, "
        f"{resultado.timeouts} en timeout"
    )
    return "\n".join(lineas)


class _parada_limpia:
    """Durante `main`: SIGTERM/SIGHUP/SIGINT lanzan `_InterrupcionDelArnes` en vez de matar el proceso.

    `[EJEC]` 2026-10-06: un `timeout` externo mandó SIGTERM, el arnés murió sin `finally`, el fichero quedó mutado
    y pytest siguió 48 min huérfano. Tras la primera señal se ignoran las siguientes. Solo en el hilo principal
    (`signal.signal` no puede instalarse en otro); los manejadores anteriores se restauran al salir."""

    def __enter__(self):
        self._anteriores: dict = {}
        if threading.current_thread() is threading.main_thread():
            for senal in _SENALES_DE_PARADA:
                # Una señal que el llamador IGNORABA (`nohup` → SIGHUP, `cmd &` → SIGINT) sigue ignorada.
                if signal.getsignal(senal) is not signal.SIG_IGN:
                    self._anteriores[senal] = signal.signal(senal, self._manejador)
        return self

    @staticmethod
    def _manejador(*_a) -> None:
        for senal in _SENALES_DE_PARADA:
            signal.signal(senal, signal.SIG_IGN)
        raise _InterrupcionDelArnes

    def __exit__(self, *_exc) -> None:
        for senal, anterior in self._anteriores.items():
            signal.signal(senal, anterior if anterior is not None else signal.SIG_DFL)


def main(argv: list[str] | None = None) -> int:
    """CLI: `python3 -m herramientas.mutar <fichero.toml>`.

    Codigos de salida:
      0 -> base en verde y todos los mutantes fueron detectados.
      1 -> la base no esta en verde (no se evaluo ningun mutante).
      2 -> hay supervivientes, no aplicados, ambiguos y/o mutantes en TIMEOUT.
      130 -> interrumpido (Ctrl-C, SIGTERM, SIGHUP): la copia aislada se borró y el árbol de pytest se mató.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Uso: python3 -m herramientas.mutar <fichero.toml>", file=sys.stderr)
        return 1

    ruta_toml = args[0]
    # `--raiz` permite ejecutar el arnes sobre un proyecto distinto del directorio actual. Existe
    # sobre todo para que las meta-pruebas puedan ejercitar ESTA funcion contra un proyecto de
    # juguete: sin ella, el contrato de codigos de salida quedaria sin cobertura (auditoria 2026-08-02).
    raiz = args[args.index("--raiz") + 1] if "--raiz" in args and len(args) > args.index("--raiz") + 1 else "."
    try:
        with _parada_limpia():
            resultado = ejecutar(ruta_toml, raiz=raiz)
    except KeyboardInterrupt:
        print("Arnés interrumpido: copia aislada borrada y procesos de pytest terminados.", file=sys.stderr)
        return 130
    print(_formatear_informe(resultado, ruta_toml))

    if not resultado.base_verde:
        return 1
    # Un unico punto de decision: `concluyente` exige que TODO mutante haya muerto. Si se anadiera un
    # estado nuevo sin contarlo, el conjunto dejaria de ser concluyente en vez de pasar por exito.
    if not resultado.concluyente:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
