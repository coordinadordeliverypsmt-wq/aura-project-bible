"""Confinar un subagente con el kernel, no con buena voluntad (CEO, 2026-09-21).

POR QUÉ EXISTE. Una auditoría adversarial demostró, ejecutándolo, que `delegacion.ejecutar_pruebas`
implicaba **ejecución de código arbitrario**: pytest ejecuta como Python real el contenido del
sandbox, y desde ahí se leía y se escribía **fuera**. El perímetro de `delegacion.py` acota *qué
ficheros se le nombran a la herramienta*; no puede acotar *qué hace el código que contienen*. Esa
frontera solo la pone el sistema operativo.

CÓMO. **Landlock**, el LSM de autorrestricción del kernel Linux (5.13+). Un proceso se encierra a
sí mismo y la restricción es **irreversible**: se hereda por los hijos y no hay forma de deshacerla
desde dentro. No hace falta ser root, no hace falta instalar nada, y no es una dependencia de
terceros — es el kernel de la máquina. Medido aquí: ABI 6 sobre 6.14.

POR QUÉ NO CONTENEDORES. `bwrap` está instalado en esta máquina y habría servido, pero es un
**paquete del sistema**: convertirlo en requisito haría que la capacidad dejara de funcionar donde
no esté, y añadir dependencias de terceros es justo lo que `D24` acota. Landlock no añade ninguna.

FAIL-CLOSED, Y ESTO ES LO IMPORTANTE. Si el kernel no ofrece Landlock, este módulo **no finge**:
`DISPONIBLE` es `False` y quien lo use decide. `delegacion` está configurado para **negarse** en ese
caso (`EXIGIR_AISLAMIENTO`). Ejecutar declarando un confinamiento que no existe sería `INV-9` —
fingir capacidad no construida— con consecuencias de seguridad, que es la peor versión del patrón
«declarado ≠ real».

LA SEGUNDA CAPA: LÍMITES DE RECURSOS. Landlock acota el **sistema de ficheros**; no impide que una
misión agote la memoria, llene el disco o fabrique procesos sin fin. Eso lo acotan los `rlimit` del
propio proceso, que también se heredan y tampoco se pueden subir después de bajarlos. Las dos capas
se aplican juntas y ninguna sustituye a la otra.

MODO ESTRICTO (FASE B del PROMPT 03; CEO: «restringir lectura; denegar red por defecto, sin
excepciones»). `preparar_estricto()` es un modo APARTE: `preparar()` conserva su comportamiento. Lo usa
la verificacion por contrato (`review._verificador_de_review`). Si falta CUALQUIER control no se devuelve
confinador (`ConfinamientoInsuficiente`): nunca se degrada en silencio. Controles:

- Landlock FS: LECTURA = allowlist minima DERIVADA (`rutas_estrictas`): ejecutable resuelto, stdlib,
  librerias dinamicas realmente mapeadas por un interprete de sondeo, cada paquete de pytest importado (no
  `~/.local`, no `$HOME`; de sus padres solo se concede LISTAR nombres, `READ_DIR`) y la copia.
  ESCRITURA = copia + extra (temporal del informe) + `/dev/null`.
- Landlock NET (ABI>=4): BIND y CONNECT TCP manejados sin reglas = denegados.
- Landlock scoped (ABI>=6): SIGNAL y ABSTRACT_UNIX_SOCKET (el padre SI puede matar al hijo).
- seccomp-BPF (x86_64): ver mas abajo. NO_NEW_PRIVS. Heredado por hijos y nietos.
Medido en este equipo: Linux 6.14, Landlock ABI 6, x86_64.

`seccomp` (syscalls cerradas con EPERM): TODO `socket()` (sin dominios permitidos: cubre
INET/INET6/UNIX/NETLINK/PACKET/VSOCK/BLUETOOTH...), `io_uring_*`, IPC SysV (shm/sem/msg), colas POSIX
(`mq_open/unlink`) y los metadatos que Landlock no gobierna (chmod, fchmod, fchmodat(2), chown, fchown,
lchown, fchownat, utime, utimes, futimesat, utimensat, y los xattr set/remove en sus tres variantes), y el
keyring del kernel (`add_key`, `request_key`, `keyctl`), inotify (`inotify_init`, `inotify_init1`,
`inotify_add_watch`) y las syscalls que actuan sobre OTRO proceso por pid, que dan EPERM salvo pid 0 (el
propio): `prlimit64`, `sched_setparam`, `sched_setscheduler`, `sched_setattr`, `sched_setaffinity` y
`setpriority` (which=0 y who=0). Consecuencia deliberada: tampoco se pueden cambiar
permisos o fechas DENTRO de la copia. Arquitectura distinta de x86_64 => proceso muerto; syscalls x32
rechazadas. Antes de los filtros, `close_range(3, ~0, CLOEXEC)` hace que todo fd heredado no sobreviva al
`exec` (un UDP heredado habria permitido `sendto`, que ni Landlock ni seccomp miran).

`controles` es DECLARATIVO (una constante, no una medicion): lo acreditan las pruebas de ataque de
`test_red_aislamiento_estricto.py`, una por control, que fallan si un control deja de actuar.

Limites no mitigados (SOLO lo implementado y probado; lo no listado aqui no se promete):
- `stat`/existencia de rutas externas siguen visibles (Landlock no gobierna `stat`): se puede saber que
  un fichero existe y su tamano/permisos, no leerlo.
- Los NOMBRES de los directorios padre de los paquetes de pytest (p.ej. el `site-packages` del usuario)
  son listables (`READ_DIR`); su contenido no.
- `/dev/null` es escribible (sumidero necesario).
- `socketpair` anonimo sigue permitido; no se filtran `ptrace` ni `process_vm_*` (acotados por scoped).
- `shutil.copy`, `shutil.copy2` y `shutil.copytree` (copymode/copystat) fallan con `PermissionError`
  DENTRO del estricto, porque chmod/utime estan cerrados; `shutil.copyfile` si funciona. Es un falso
  rechazo conocido y fijado por prueba, no un hueco de seguridad.
- Con esas syscalls solo vale el pid 0: ni el propio pid explicito ni un tid de otro hilo propio (p.ej.
  `os.sched_setaffinity(os.getpid(), ...)` da EPERM); `resource.setrlimit` y `os.sched_setaffinity(0, ...)`
  si funcionan. La LECTURA de limites ajenos por `prlimit64` tambien se cierra (mismo filtro).
- `getpriority`, `sched_getaffinity`, `sched_getscheduler` y `sched_getattr` sobre otro pid siguen abiertos
  (solo lectura de datos de planificacion).
- No hay limite de procesos (haria falta cgroups).
- Solo x86_64 con Landlock ABI>=6 y seccomp: en otra plataforma NO hay estricto (falla cerrado).
- El sondeo de la allowlist esta cacheado por ejecutable y por la firma (mtime) del ejecutable y de los
  directorios de site-packages; un cambio de paquetes que no toque esos directorios no se ve hasta
  reiniciar el proceso.
- La delegacion (`delegacion.py`) usa el modo por defecto `preparar()`: lectura amplia y CON red.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import functools
import json
import os
import pathlib
import platform
import resource
import site
import struct
import subprocess
import sys

#: Números de syscall de Landlock (estables en Linux desde 5.13, iguales en todas las arquitecturas
#: que este proyecto soporta). Se declaran aquí y no se adivinan: si algún día no coincidieran, la
#: llamada falla y `abi_disponible()` devuelve 0, que es el camino seguro.
_SYS_CREATE_RULESET = 444
_SYS_ADD_RULE = 445
_SYS_RESTRICT_SELF = 446

_PR_SET_NO_NEW_PRIVS = 38
_LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
_LANDLOCK_RULE_PATH_BENEATH = 1

#: Los derechos de acceso al sistema de ficheros, en el orden de bits que fija el kernel. El orden
#: **es** la definición: cada uno vale `1 << su posición`.
_DERECHOS = ("EXECUTE", "WRITE_FILE", "READ_FILE", "READ_DIR", "REMOVE_DIR", "REMOVE_FILE",
             "MAKE_CHAR", "MAKE_DIR", "MAKE_REG", "MAKE_SOCK", "MAKE_FIFO", "MAKE_BLOCK",
             "MAKE_SYM", "REFER", "TRUNCATE", "IOCTL_DEV")
FS = {nombre: 1 << i for i, nombre in enumerate(_DERECHOS)}

#: Leer y ejecutar. Es lo que necesita el intérprete para arrancar y cargar sus módulos.
LECTURA = FS["EXECUTE"] | FS["READ_FILE"] | FS["READ_DIR"]

#: Todo lo demás: crear, borrar, truncar, mover. Solo se concede dentro del sandbox.
ESCRITURA = (FS["WRITE_FILE"] | FS["REMOVE_DIR"] | FS["REMOVE_FILE"] | FS["MAKE_CHAR"]
             | FS["MAKE_DIR"] | FS["MAKE_REG"] | FS["MAKE_SOCK"] | FS["MAKE_FIFO"]
             | FS["MAKE_BLOCK"] | FS["MAKE_SYM"] | FS["REFER"] | FS["TRUNCATE"])

TODO = LECTURA | ESCRITURA

#: Los pseudodispositivos que **hay que poder escribir** para que un proceso normal funcione.
#: Descubierto midiendo: con `/dev` en solo lectura, pytest revienta con
#: `PermissionError: /dev/null` antes de recolectar una sola prueba — el sandbox pasaba de ser
#: estrecho a ser inservible, que es el otro modo de fallar.
#:
#: Se les concede `WRITE_FILE` y **nada más**: eso permite escribir en un fichero que ya existe,
#: pero no crear, borrar ni enlazar. Dar `/dev` entero habría sido mucho más de lo necesario.
_DISPOSITIVOS = ("/dev/null", "/dev/zero", "/dev/full", "/dev/random", "/dev/urandom", "/dev/tty")
_ESCRITURA_EN_DISPOSITIVO = LECTURA | FS["WRITE_FILE"]

#: Derechos que **solo tienen sentido sobre un directorio**. Pedirlos sobre un fichero hace que el
#: kernel devuelva `EINVAL` y falle la regla entera — medido: `landlock_add_rule /dev/null` con
#: `READ_DIR` incluido reventaba el confinamiento y la mision entera moria con `SubprocessError`.
#: Se recortan automaticamente segun lo que sea la ruta, en vez de mantener dos listas a mano: dos
#: listas se desincronizan, y el fallo aparece lejos de su causa.
_SOLO_DIRECTORIO = (FS["READ_DIR"] | FS["REMOVE_DIR"] | FS["REMOVE_FILE"] | FS["MAKE_CHAR"]
                    | FS["MAKE_DIR"] | FS["MAKE_REG"] | FS["MAKE_SOCK"] | FS["MAKE_FIFO"]
                    | FS["MAKE_BLOCK"] | FS["MAKE_SYM"] | FS["REFER"])

#: Derechos que solo existen a partir de cierta versión del ABI. Pedir uno que el kernel no conoce
#: hace fallar la creación entera del ruleset, así que se recortan según lo que haya.
_DESDE_ABI = {2: FS["REFER"], 3: FS["TRUNCATE"], 5: FS["IOCTL_DEV"]}

#: Límites de recursos del subagente. Números deliberadamente holgados: acotan el desastre, no el
#: trabajo. Se documentan porque un límite sin justificación es un número inventado, y la regla del
#: CEO (2026-08-04) exige que sea **visible y ajustable**, no que sea el correcto a la primera.
LIMITE_CPU_S = 300          # tiempo de CPU, no de reloj: el plazo de pared ya lo pone `delegacion`
LIMITE_MEMORIA_BYTES = 4 * 1024 ** 3
LIMITE_FICHERO_BYTES = 256 * 1024 ** 2

#: **`RLIMIT_NPROC` NO se usa, y conviene decir por qué.** Cuenta los procesos **del usuario
#: entero**, no los del proceso confinado: ponerlo bajo no acota al subagente, estrangula la sesión
#: completa de quien lo lanzó. Medido aquí — con el límite en 256, `ruff` moría con
#: *«failed to spawn thread: Resource temporarily unavailable»* en una máquina con una sesión de
#: trabajo abierta, y el fallo se leía como «la capacidad está rota», no como «el límite es el que
#: no sirve».
#:
#: **Acotar los procesos de un subagente de verdad exige cgroups**, que es otra cosa y otra
#: decisión. Se deja dicho para que nadie lo añada de vuelta creyendo que cierra un hueco: lo que
#: cierra es la sesión del operador.

_libc = None


def _c() -> ctypes.CDLL:
    global _libc
    if _libc is None:
        _libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    return _libc


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def abi_disponible() -> int:
    """La versión de Landlock que ofrece este kernel, o **0** si no ofrece ninguna.

    Se pregunta al kernel en vez de deducirlo de `uname`: una versión de kernel reciente con
    Landlock deshabilitado en el arranque diría que sí y mentiría."""
    try:
        version = _c().syscall(_SYS_CREATE_RULESET, None, ctypes.c_size_t(0),
                               ctypes.c_uint32(_LANDLOCK_CREATE_RULESET_VERSION))
    except Exception:                                           # pragma: no cover - libc ausente
        return 0
    return version if version > 0 else 0


DISPONIBLE = abi_disponible() > 0


def rutas_del_interprete() -> tuple[str, ...]:
    """Lo mínimo que el intérprete necesita LEER para arrancar. **Se deriva, no se cablea.**

    Cablear `/usr/lib/python3.12` funcionaría hoy y se rompería con el siguiente intérprete, en un
    sitio donde el fallo se manifiesta como «la misión no arranca» y cuesta horas encontrar."""
    candidatas = {sys.prefix, sys.base_prefix, str(pathlib.Path(sys.executable).parent),
                  "/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/proc", "/dev"}
    candidatas.update(p for p in sys.path if p)

    # **Los paquetes y binarios del USUARIO, que `sys.path` no siempre alcanza.** Descubierto
    # midiendo: `ruff` se instala en `~/.local/bin` y su `__main__` hace `os.execvp` sobre ese
    # binario, así que con el confinamiento puesto moría con `PermissionError` y `verificar_calidad`
    # dejaba de funcionar. Es lectura y ejecución, nunca escritura: se puede usar la herramienta,
    # no modificarla.
    candidatas.add(site.USER_BASE)

    # Los directorios del `PATH`: una herramienta delegada tiene que poder EJECUTARSE. Se conceden
    # con `LECTURA`, que incluye ejecutar pero no escribir — el confinamiento sigue impidiendo que
    # una misión modifique el binario que acaba de correr.
    candidatas.update(d for d in os.environ.get("PATH", "").split(os.pathsep) if d)

    return tuple(sorted(r for r in candidatas if r and pathlib.Path(r).exists()))


#: Landlock de red (ABI>=4) y de ambito (ABI>=6). Valores del kernel (uapi/linux/landlock.h).
_NET_BIND_TCP = 1 << 0
_NET_CONNECT_TCP = 1 << 1
_SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0
_SCOPE_SIGNAL = 1 << 1
_ABI_ESTRICTO = 6


def _confinar_ficheros(lectura, escritura, abi: int, *, estricto: bool = False,
                       dispositivos=_DISPOSITIVOS, listado=()) -> None:
    """Encierra ESTE proceso. Irreversible: ni él ni sus hijos pueden salir. Con `estricto` maneja
    ademas la red TCP (sin reglas = denegada) y el ambito de senales y sockets unix abstractos."""
    manejado = TODO
    for version, derecho in _DESDE_ABI.items():
        if abi < version:
            manejado &= ~derecho

    red = (_NET_BIND_TCP | _NET_CONNECT_TCP) if estricto else 0
    ambito = (_SCOPE_SIGNAL | _SCOPE_ABSTRACT_UNIX_SOCKET) if estricto else 0
    attr = _RulesetAttr(manejado, red, ambito)
    fd = _c().syscall(_SYS_CREATE_RULESET, ctypes.byref(attr),
                      ctypes.c_size_t(ctypes.sizeof(attr)), ctypes.c_uint32(0))
    if fd < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")

    try:
        def permitir(ruta, accesos) -> None:
            # Una ruta que no existe no es un error: es una de las candidatas que esta maquina no
            # tiene. Lo que NO se permite en silencio es fallar al anadir una que si existe.
            try:
                pfd = os.open(str(ruta), os.O_PATH | os.O_CLOEXEC)
            except OSError:
                return
            try:
                permitidos = accesos & manejado
                if not os.path.isdir(str(ruta)):
                    permitidos &= ~_SOLO_DIRECTORIO
                if not permitidos:
                    return
                regla = _PathBeneathAttr(permitidos, pfd)
                if _c().syscall(_SYS_ADD_RULE, ctypes.c_int(fd),
                                ctypes.c_int(_LANDLOCK_RULE_PATH_BENEATH),
                                ctypes.byref(regla), ctypes.c_uint32(0)) < 0:
                    raise OSError(ctypes.get_errno(), f"landlock_add_rule {ruta}")
            finally:
                os.close(pfd)

        for ruta in lectura:
            permitir(ruta, LECTURA)
        for ruta in listado:                    # solo LISTAR nombres: sin READ_FILE ni EXECUTE
            permitir(ruta, FS["READ_DIR"])
        for ruta in dispositivos:
            permitir(ruta, _ESCRITURA_EN_DISPOSITIVO)
        for ruta in escritura:
            permitir(ruta, TODO)

        # `no_new_privs` es **obligatorio** antes de `restrict_self`: sin el, un binario `setuid`
        # dentro del confinamiento podria recuperar privilegios y el encierro seria decorativo.
        if _c().prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "prctl(NO_NEW_PRIVS)")
        if _c().syscall(_SYS_RESTRICT_SELF, ctypes.c_int(fd), ctypes.c_uint32(0)) < 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self")
    finally:
        os.close(fd)


def _limitar_recursos() -> None:
    """La segunda capa. Landlock acota el disco; esto acota lo demás.

    Se baja el límite **blando y el duro a la vez**: bajar solo el blando lo dejaría subible desde
    dentro, que es exactamente la clase de límite que no limita nada."""
    for recurso, valor in ((resource.RLIMIT_CPU, LIMITE_CPU_S),
                           (resource.RLIMIT_AS, LIMITE_MEMORIA_BYTES),
                           (resource.RLIMIT_FSIZE, LIMITE_FICHERO_BYTES)):
        try:
            blando, duro = resource.getrlimit(recurso)
            tope = valor if duro == resource.RLIM_INFINITY else min(valor, duro)
            resource.setrlimit(recurso, (tope, tope))
        except (ValueError, OSError):                           # pragma: no cover - limite fijado
            continue


def preparar(sandbox, escritura_extra=()) -> "callable":
    """Devuelve la función que confina al hijo, para `subprocess(..., preexec_fn=...)`.

    **Se aplica en el hijo, entre `fork` y `exec`**, que es el único punto donde el confinamiento
    puede ser total: el padre sigue sin restricciones —tiene que seguir trabajando— y el hijo nace
    ya encerrado, sin una ventana en la que estuviera libre.

    Nota sobre `preexec_fn`: la documentación de Python advierte de que no es seguro con hilos. Aquí
    lo es porque lo único que hace es llamar a `prctl`, `setrlimit` y tres syscalls — nada que
    reserve memoria del intérprete ni tome locks."""
    caja = pathlib.Path(sandbox).resolve(strict=False)
    escrituras = [caja, *[pathlib.Path(r).resolve(strict=False) for r in escritura_extra]]
    lecturas = [*rutas_del_interprete(), *escrituras]
    abi = abi_disponible()

    def confinar() -> None:                                     # pragma: no cover - corre en el hijo
        _limitar_recursos()
        if abi > 0:
            _confinar_ficheros(lecturas, escrituras, abi)

    # **El confinador es componible**, y hace falta que lo sea: `verificador` crea el temporal del
    # informe JUnit DESPUES de recibirlo, y un encierro que no lo contemple haria que pytest no
    # pudiera escribir su conteo — la medicion daria cero y el arbol se declararia insano. Ampliar
    # solo puede anadir rutas de ESCRITURA concretas; no existe forma de relajar lo demas.
    confinar.con_escritura_en = lambda ruta: preparar(caja, (*escritura_extra, ruta))
    confinar.sandbox = str(caja)
    confinar.abi = abi
    return confinar


# ======================================================================= MODO ESTRICTO ==

class ConfinamientoInsuficiente(RuntimeError):
    """El estricto no se puede construir COMPLETO en esta maquina. Quien lo use debe NO ejecutar."""


#: Los controles que un confinador estricto declara y que quien lo consuma DEBE exigir enteros.
CONTROLES_ESTRICTOS = ("landlock_lectura_minima", "landlock_escritura_confinada", "landlock_red_tcp",
                       "landlock_scoped_senales", "landlock_scoped_unix_abstracto", "seccomp_red",
                       "seccomp_io_uring", "seccomp_arquitectura", "no_new_privs", "rlimits")

# --- seccomp-BPF (x86_64). Un filtro clasico escrito a mano: sin libseccomp, sin dependencias.
_PR_SET_SECCOMP = 22
_SECCOMP_MODE_FILTER = 2
_AUDIT_ARCH_X86_64 = 0xC000003E
_RET_KILL_PROCESS = 0x80000000
_RET_ALLOW = 0x7FFF0000
_RET_ERRNO = 0x00050000
_EPERM = 1
_X32_BIT = 0x40000000
_SYS_SOCKET = 41
_SYS_IO_URING = (425, 426, 427)         # setup, enter, register
#: **Allowlist vacia de `socket()`**: TODO `socket()` da EPERM (una denylist de dominios dejaba pasar
#: AF_VSOCK=40 y AF_BLUETOOTH=31: un hijo llego a hablar con un listener vsock del padre). `socketpair`
#: sigue permitido (anonimo; pytest no necesita sockets).
#: IPC SysV (shm 29-31,67; sem 64-66,220; msg 68-71): el hijo leia un segmento de memoria compartida 0600
#: del padre. Colas POSIX (mq_open/mq_unlink 240-241): misma clase.
_SYS_SYSV_IPC = (29, 30, 31, 67, 64, 65, 66, 220, 68, 69, 70, 71, 240, 241)
#: Metadatos de ficheros, que Landlock NO gobierna: chmod 90, fchmod 91, chown 92, fchown 93, lchown 94,
#: utime 132, utimes 235, fchownat 260, futimesat 261, fchmodat 268, utimensat 280, fchmodat2 452.
#: Atributos extendidos: setxattr 188, lsetxattr 189, fsetxattr 190, removexattr 197, lremovexattr 198,
#: fremovexattr 199 (Landlock tampoco los gobierna: un hijo alteraba atributos de ficheros externos).
_SYS_METADATOS = (90, 91, 92, 93, 94, 132, 235, 260, 261, 268, 280, 452, 188, 189, 190, 197, 198, 199)
#: Keyring del kernel: add_key 248, request_key 249, keyctl 250 (un hijo estricto leia con KEYCTL_READ una
#: clave del keyring de sesion del padre: Landlock no gobierna las claves).
_SYS_KEYRING = (248, 249, 250)
#: inotify_init 253, inotify_add_watch 254, inotify_init1 294: vigilar directorios externos (Landlock no lo
#: gobierna). fanotify ya daba EPERM sin privilegios.
_SYS_INOTIFY = (253, 254, 294)
_SYS_CERRADAS = (*_SYS_IO_URING, _SYS_SOCKET, *_SYS_SYSV_IPC, *_SYS_METADATOS, *_SYS_KEYRING, *_SYS_INOTIFY)
#: Syscalls que actuan sobre OTRO proceso por pid: EPERM salvo que el argumento indicado valga 0 (= el propio
#: proceso) en los 64 bits. `(nr, (indices de argumento que deben ser 0))`. prlimit64 302 (un hijo mato a una
#: victima con RLIMIT_CPU {1,1}), sched_setparam 142, sched_setscheduler 144, setpriority 141 (which=0 Y
#: who=0), sched_setaffinity 203, sched_setattr 314.
_SYS_SOLO_PROPIO = ((302, (0,)), (142, (0,)), (144, (0,)), (141, (0, 1)), (203, (0,)), (314, (0,)))
_BPF_LD_W_ABS, _BPF_JEQ_K, _BPF_JGE_K, _BPF_RET_K = 0x20, 0x15, 0x35, 0x06


def _bloque_solo_propio(instr, nr, indices) -> None:
    """`nr` => permitido solo si cada argumento de `indices` es 0 (palabra baja y alta de `args[i]`);
    si no, EPERM. El acumulador conserva `nr` si la syscall no coincide, asi que el filtro sigue."""
    palabras = [off for i in indices for off in (16 + 8 * i, 20 + 8 * i)]   # seccomp_data.args[i] lo / hi
    k = len(palabras)
    instr(_BPF_JEQ_K, nr, 0, 2 * k + 2)
    for j, off in enumerate(palabras):
        instr(_BPF_LD_W_ABS, off)
        instr(_BPF_JEQ_K, 0, 0, 2 * k - 2 * j - 1)
    instr(_BPF_RET_K, _RET_ALLOW)
    instr(_BPF_RET_K, _RET_ERRNO | _EPERM)


def _programa_seccomp() -> bytes:
    """El filtro: arquitectura != x86_64 => matar; syscall x32 => matar; `_SYS_CERRADAS` => EPERM; el
    resto => permitido."""
    ins = []

    def instr(codigo, k, jt=0, jf=0):
        ins.append((codigo, jt, jf, k))

    instr(_BPF_LD_W_ABS, 4)                      # seccomp_data.arch
    instr(_BPF_JEQ_K, _AUDIT_ARCH_X86_64, 1, 0)
    instr(_BPF_RET_K, _RET_KILL_PROCESS)
    instr(_BPF_LD_W_ABS, 0)                      # seccomp_data.nr
    instr(_BPF_JGE_K, _X32_BIT, 0, 1)            # x32: nr >= 0x40000000 => matar
    instr(_BPF_RET_K, _RET_KILL_PROCESS)
    for nr in _SYS_CERRADAS:
        instr(_BPF_JEQ_K, nr, 0, 1)
        instr(_BPF_RET_K, _RET_ERRNO | _EPERM)
    for nr, indices in _SYS_SOLO_PROPIO:
        _bloque_solo_propio(instr, nr, indices)
    instr(_BPF_RET_K, _RET_ALLOW)
    return b"".join(struct.pack("HBBI", c, jt, jf, k) for c, jt, jf, k in ins)


class _SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]


def seccomp_disponible() -> bool:
    """True si ESTE kernel acepta filtros seccomp y la plataforma es x86_64 (el filtro lo asume).
    Se pregunta al kernel sin instalar nada: `PR_SET_SECCOMP/FILTER` con puntero nulo responde EFAULT si
    el modo existe y EINVAL si no."""
    if platform.machine() != "x86_64":
        return False
    try:
        r = _c().prctl(_PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, None, 0, 0)
    except Exception:                                           # pragma: no cover - libc ausente
        return False
    return r == -1 and ctypes.get_errno() == 14                 # EFAULT


def estricto_disponible() -> bool:
    """True si el modo estricto se puede construir COMPLETO aqui (Landlock ABI>=6 y seccomp)."""
    return abi_disponible() >= _ABI_ESTRICTO and seccomp_disponible()


_SONDA = r"""
import json, os, sys, sysconfig
try:
    import pytest
except BaseException:
    pass
din = os.path.join(sysconfig.get_path("platstdlib"), "lib-dynload")
if os.path.isdir(din):
    for f in sorted(os.listdir(din)):
        n = f.split(".")[0]
        if n and not n.startswith(("_test", "xx")):
            try:
                __import__(n)
            except BaseException:
                pass
mapas = set()
for linea in open("/proc/self/maps"):
    p = linea.split(None, 5)
    if len(p) == 6 and p[5].strip().startswith("/"):
        mapas.add(p[5].strip())
std = sorted({os.path.realpath(sysconfig.get_path(k)) for k in ("stdlib", "platstdlib")})
paq = set()
for n, m in list(sys.modules.items()):
    if "." in n:
        continue
    sp = getattr(m, "__spec__", None)
    if sp is None:
        continue
    locs = list(sp.submodule_search_locations or [])
    if not locs and sp.origin and os.path.isabs(sp.origin):
        locs = [sp.origin]
    for l in locs:
        r = os.path.realpath(l)
        if not any(r == s or r.startswith(s + os.sep) for s in std):
            paq.add(r)
print(json.dumps({"mapas": sorted(mapas), "paquetes": sorted(paq), "stdlib": std,
                  "exe": os.path.realpath(sys.executable)}))
"""

_PREFIJOS_NO_LECTURA = ("/dev/", "/proc/", "/sys/", "/tmp/", "/run/", "/memfd:")


def _firma_sondeo() -> tuple:
    """Lo que invalida el sondeo cacheado: mtime del ejecutable y de los directorios de paquetes."""
    dirs = {*site.getsitepackages(), site.getusersitepackages()}
    marcas = []
    for d in sorted(dirs | {os.path.realpath(sys.executable)}):
        try:
            marcas.append((d, os.stat(d).st_mtime_ns))
        except OSError:
            marcas.append((d, None))
    return tuple(marcas)


def _sondeo(ejecutable: str, firma: tuple | None = None) -> dict:
    return _sondeo_cacheado(ejecutable, _firma_sondeo() if firma is None else firma)


@functools.lru_cache(maxsize=4)
def _sondeo_cacheado(ejecutable: str, firma: tuple) -> dict:
    """Lanza UN interprete de sondeo (sin confinar, solo lee) que importa pytest y todos los modulos de
    extension de la stdlib, y devuelve que ficheros mapeo y que paquetes cargo. Es lo que hace que la
    allowlist se DERIVE del interprete real y no se cablee."""
    try:
        r = subprocess.run([ejecutable, "-c", _SONDA], capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL, cwd="/", env={"PATH": os.environ.get("PATH", ""),
                                                                   "HOME": os.environ.get("HOME", "/"),
                                                                   "PYTHONDONTWRITEBYTECODE": "1"})
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001 — sin sondeo no hay allowlist: el estricto no existe
        raise ConfinamientoInsuficiente(f"no se pudo derivar la allowlist de lectura: {exc!r}") from exc


def rutas_estrictas() -> tuple[str, ...]:
    """La LECTURA minima del modo estricto, derivada de un interprete de sondeo. Ejecutable resuelto,
    stdlib, librerias dinamicas mapeadas, y cada paquete/modulo de terceros importado por pytest
    (se concede el paquete concreto; nunca el site-packages entero ni `$HOME`). Para un modulo suelto
    (p.ej. `py.py`) se concede el fichero."""
    datos = _sondeo(sys.executable)
    rutas = {datos["exe"], sys.executable, *datos["stdlib"], *datos["paquetes"]}
    for m in datos["mapas"]:
        if not m.startswith(_PREFIJOS_NO_LECTURA) and pathlib.Path(m).is_file():
            rutas.add(m)
    for base in {sys.prefix, str(pathlib.Path(sys.executable).parent.parent)}:   # venv: pyvenv.cfg
        cfg = pathlib.Path(base) / "pyvenv.cfg"
        if cfg.is_file():
            rutas.add(str(cfg))
    return tuple(sorted(r for r in rutas if pathlib.Path(r).exists()))


def listados_estrictos() -> tuple[str, ...]:
    """Directorios de los que el estricto concede SOLO `READ_DIR` (listar nombres, no leer ficheros):
    los padres de cada paquete de terceros. Medido: sin esto el buscador de modulos no ve `pytest`
    aunque el paquete sea legible (`FileFinder` lista el directorio). Efecto: el confinado puede ver
    los NOMBRES de lo instalado en ese site-packages (p.ej. `~/.local/lib/python3.12/site-packages`),
    no su contenido; es un limite declarado, y no se concede `~/.local` ni `$HOME`."""
    datos = _sondeo(sys.executable)
    std = [pathlib.Path(x) for x in datos["stdlib"]]
    padres = {pathlib.Path(r).parent for r in datos["paquetes"]}
    return tuple(sorted(str(p) for p in padres
                        if not any(p.is_relative_to(x) for x in std) and p.is_dir()))


_SYS_CLOSE_RANGE = 436
_CLOSE_RANGE_CLOEXEC = 1 << 2


def _cerrar_fds_heredados() -> None:
    """Marca CLOEXEC todo fd >= 3 (`close_range(3, ~0, CLOSE_RANGE_CLOEXEC)`): un socket o fichero que el
    padre dejara heredable NO llega al programa confinado (tras el `exec` ya no existe: EBADF). Se usa
    CLOEXEC y no el cierre inmediato porque `subprocess` informa del fallo de `preexec`/`exec` por un fd
    interno >= 3; cerrarlo haria que un fallo se leyera como exito."""
    if _c().syscall(_SYS_CLOSE_RANGE, ctypes.c_uint(3), ctypes.c_uint(0xFFFFFFFF),
                    ctypes.c_uint(_CLOSE_RANGE_CLOEXEC)) != 0:
        raise OSError(ctypes.get_errno(), "close_range")


def _instalar_seccomp(fprog) -> None:
    if _c().prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(NO_NEW_PRIVS)")
    if _c().prctl(_PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(SECCOMP_FILTER)")


def preparar_estricto(sandbox, escritura_extra=()) -> "callable":
    """Como `preparar`, pero ESTRICTO: lectura minima, red denegada y senales acotadas (ver docstring del
    modulo). Lanza `ConfinamientoInsuficiente` si falta CUALQUIER control (ABI<6, sin seccomp, arquitectura
    no x86_64, sondeo fallido): jamas devuelve un confinador parcial. El confinador expone
    `controles` (nombre -> True), `completo`, `abi`, `estricto`, `sandbox` y `con_escritura_en`
    (que conserva el modo estricto). Un fallo al aplicar en el hijo lanza `OSError` entre fork y exec
    (el llamador lo ve como excepcion de `Popen`)."""
    abi = abi_disponible()
    if abi < _ABI_ESTRICTO:
        raise ConfinamientoInsuficiente(
            f"el modo estricto exige Landlock ABI>={_ABI_ESTRICTO} (red y ambito); este kernel ofrece {abi}")
    if not seccomp_disponible():
        raise ConfinamientoInsuficiente("el modo estricto exige seccomp-BPF en x86_64; no esta disponible")
    caja = pathlib.Path(sandbox).resolve(strict=False)
    escrituras = [caja, *[pathlib.Path(r).resolve(strict=False) for r in escritura_extra]]
    lecturas = [*rutas_estrictas(), *escrituras]
    listados = listados_estrictos()
    programa = _programa_seccomp()
    memoria = ctypes.create_string_buffer(programa, len(programa))   # viva mientras viva el confinador
    fprog = _SockFprog(len(programa) // 8, ctypes.cast(memoria, ctypes.c_void_p))

    def confinar() -> None:                                     # pragma: no cover - corre en el hijo
        _limitar_recursos()
        _cerrar_fds_heredados()
        _instalar_seccomp(fprog)
        _confinar_ficheros(lecturas, escrituras, abi, estricto=True, dispositivos=("/dev/null",),
                           listado=listados)

    confinar.con_escritura_en = lambda ruta: preparar_estricto(caja, (*escritura_extra, ruta))
    confinar.sandbox = str(caja)
    confinar.abi = abi
    confinar.estricto = True
    confinar.completo = True
    # DECLARATIVO: es una constante, no una medicion. Lo acreditan las pruebas de ataque de
    # `test_red_aislamiento_estricto.py` (una por control); si un control dejara de actuar, fallan ellas.
    confinar.controles = {nombre: True for nombre in CONTROLES_ESTRICTOS}
    confinar._memoria_seccomp = memoria
    return confinar


def descripcion() -> str:
    """Lo que hay, dicho para que quede en la evidencia de la misión. Sin adornos."""
    abi = abi_disponible()
    return f"landlock:abi{abi}+rlimits" if abi > 0 else "rlimits"


__all__ = ["DISPONIBLE", "abi_disponible", "preparar", "descripcion", "rutas_del_interprete",
           "preparar_estricto", "ConfinamientoInsuficiente", "CONTROLES_ESTRICTOS", "estricto_disponible",
           "seccomp_disponible", "rutas_estrictas", "listados_estrictos",
           "LIMITE_CPU_S", "LIMITE_MEMORIA_BYTES", "LIMITE_FICHERO_BYTES"]
