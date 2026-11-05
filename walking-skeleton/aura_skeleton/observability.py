"""Observabilidad (Bible P-ARQ-7): logs estructurados + trazabilidad por trace_id + latencia.
Los logs son dato del usuario (ADR-0001): en producción, locales y cifrados."""

from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
import re
import stat
import sys
import time
from collections.abc import Iterator

_records: list[dict] = []

# --- Donde se IMPRIME la telemetria (CEO, 2026-09-01). -------------------------------------------
# El defecto que esto corrige: `log()` hacia un `print` incondicional, asi que la conversacion humana
# aparecia sepultada bajo [VOICE]/[MEM]/[EVENT]/[LAT] en la misma pantalla. La separacion por flujo ya
# existia —la telemetria va a `stderr` y la conversacion a `stdout`—, pero en una terminal los dos
# flujos caen en el mismo sitio, asi que en la practica no separaba nada.
#
# Lo que se separa aqui es SOLO la PRESENTACION. El registro en `_records` y la persistencia en el
# audit log ocurren ANTES de imprimir y no dependen de esto: apagar la pantalla no pierde ni un
# registro, no reduce la auditoria y no toca ningun contrato del nucleo. Es un sumidero, no un filtro.
#
# Por defecto `sys.stderr`, que es exactamente el comportamiento de hoy: ningun llamador existente
# —scripts, arneses, `--servir`— cambia de conducta. Solo la conversacion interactiva lo apaga.
_salida = sys.stderr

# --- Metricas basicas del contrato P-ARQ-7 (Bible 7.4, "metricas basicas"). ---
# Cableado en A2 (2026-07-26): el subsistema existia sin llamadores (clasificado por D42 el
# 2026-07-22 como implementacion pendiente, NO codigo muerto). A2 lo realiza en sus puntos de emision
# reales: `bus.publish` (eventos.publicados) y `permissions.authorize` (acciones.autorizadas/
# denegadas). Contadores acumulativos por nombre: evolucion ADITIVA (una metrica nueva no altera las
# existentes). Observabilidad INTERNA, local y en memoria (ADR-0001/D24): no es API publica ni un
# contrato para consumidores externos; nunca sale del perimetro (sin telemetria remota). La latencia
# por etapa se cubre con `Timer` + logs (decision CEO 2026-07-26): sin promedios ni agregaciones aqui.
_metrics: dict[str, float] = {}
_audit: AuditLog | None = None


def metric_inc(name: str, value: float = 1.0) -> None:
    """Incrementa una metrica basica acumulativa (P-ARQ-7 / Bible 7.4). Aditiva por nombre."""
    _metrics[name] = _metrics.get(name, 0.0) + value


def metrics() -> dict:
    """Instantanea de las metricas basicas (P-ARQ-7 / Bible 7.4). Observabilidad interna, local."""
    return dict(_metrics)


def configurar_salida(destino) -> None:
    """Cambia DONDE se imprime la telemetria. `None` la deja fuera de la pantalla.

    No es un filtro ni un nivel de log: el registro y la auditoria ya ocurrieron cuando esto decide.
    Existe para que la interfaz conversacional pueda ser legible sin que el sistema deje de observarse
    a si mismo."""
    global _salida
    _salida = destino


def salida_actual():
    """Sumidero vigente. Devolverlo permite restaurarlo, que es lo que necesita una prueba para no
    dejar el modulo tocado para las siguientes."""
    return _salida


def log(level: str, module: str, msg: str, trace_id: str = "-", **kv) -> None:
    rec = {"level": level, "module": module, "msg": msg, "trace_id": trace_id, **kv}
    _records.append(rec)
    if rec.get("audit") and _audit is not None:
        _audit.append(rec)  # H2: las acciones con efecto se persisten, no solo se imprimen
    if _salida is None:
        # La pantalla esta apagada. El registro y la auditoria de arriba YA ocurrieron: aqui no se
        # pierde observabilidad, solo se deja de estorbar a quien esta conversando.
        return
    extra = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"  [{level:<5}] {module:<14} trace={trace_id[:8]} {msg} {extra}".rstrip(), file=_salida)


class Timer:
    """Mide latencia por etapa y de extremo a extremo (Bible 2.5 §5.1)."""

    def __init__(self):
        self.marks: dict[str, float] = {}
        self.t0 = time.perf_counter()

    def mark(self, name: str) -> float:
        dt = (time.perf_counter() - self.t0) * 1000.0
        self.marks[name] = dt
        return dt

    def total_ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000.0


def audit_records() -> list[dict]:
    return [r for r in _records if r.get("audit")]


class AuditBloqueado(OSError):
    """El cerrojo del audit no se obtuvo dentro de `_ESPERA_CERROJO_S`. Fail-closed: el registro NO se
    escribio y NO se descarta en silencio; el llamador decide (reintentar, abortar la accion)."""


class ErrorEscrituraParcial(OSError):
    """`os.write` acepto menos bytes de los pedidos (disco lleno, cuota). La linea no cuenta como escrita
    y el `seq` no se consume; la cola parcial queda en disco y la cerrara el siguiente escritor."""


# Espera maxima por el cerrojo del audit. Una seccion critica es un append (un write + fsync, ms) o, en
# el peor caso, una rotacion de ~5 MB (releer el activo, sha256 y renombrar: decenas de ms). 5 s deja
# margen de sobra a un escritor lento o a un disco ocupado sin que un poseedor colgado congele el
# sistema: si se agota, `AuditBloqueado` en voz alta. Un poseedor muerto (SIGKILL) suelta el flock solo.
_ESPERA_CERROJO_S = 5.0
_PAUSA_CERROJO_S = 0.002  # entre reintentos de LOCK_NB

_PATRON_SEGMENTO_FMT = r"\.(\d{12})-(\d{12})"


def _dir_de(path: str) -> str:
    return os.path.dirname(path) or "."


@contextlib.contextmanager
def _cerrojo(path: str, modo: int, banderas: int = os.O_RDWR | os.O_CREAT) -> Iterator[None]:
    """flock sobre `<audit>.lock` (fichero propio, 0600, NUNCA renombrado ni borrado: el activo se
    renombra al rotar y un flock sobre el no excluiria a nadie). Un fd NUEVO por adquisicion: flock entre
    fds distintos se excluye tambien dentro del mismo proceso. Espera acotada; al agotarse, AuditBloqueado.
    `banderas` por defecto CREA el lock (escritores); los lectores lo abren sin O_CREAT."""
    # O_NOFOLLOW: un symlink plantado como `.lock` no se sigue (ELOOP); y solo vale un fichero regular.
    fd = os.open(path + ".lock", banderas | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.ELOOP, f"el cerrojo no es un fichero regular: {path}.lock")
        limite = time.monotonic() + _ESPERA_CERROJO_S
        while True:
            try:
                fcntl.flock(fd, modo | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= limite:
                    raise AuditBloqueado(f"cerrojo del audit ocupado tras {_ESPERA_CERROJO_S}s: {path}.lock") from None
                time.sleep(_PAUSA_CERROJO_S)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


@contextlib.contextmanager
def _cerrojo_lectura(path: str) -> Iterator[None]:
    """LOCK_SH para los lectores publicos. Los lectores NUNCA crean el `.lock` (ni el directorio): se
    abre con O_RDONLY, sin O_CREAT. Si no existe (nadie ha escrito aun), no hay escritor que excluir y se
    lee sin cerrojo; igual si no hay permiso.

    Ventana residual aceptada: un primer escritor puede crear el lock y escribir mientras un lector, que
    no lo encontro, lee sin cerrojo. Es el mismo estado que veia el lector antes de existir el audit
    (cola a lo sumo parcial, que `_leer_fichero` ya descarta) y no hay sellado que ver a medias, porque
    el primer sellado exige una escritura previa; el lector siguiente ya abrira el lock y excluira."""
    if not os.path.isdir(_dir_de(path)):
        yield
        return
    try:
        cm = _cerrojo(path, fcntl.LOCK_SH, banderas=os.O_RDONLY)
        cm.__enter__()
    except (FileNotFoundError, PermissionError):
        yield
        return
    except OSError as e:
        if e.errno != errno.ELOOP:  # symlink / no regular en lugar del lock: se lee sin cerrojo
            raise
        yield
        return
    try:
        yield
    finally:
        cm.__exit__(None, None, None)


def _fsync_dir(directorio: str) -> None:
    fd = os.open(directorio, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class AuditLog:
    """Registro de auditoria PERSISTENTE e INMUTABLE (H2, M2.0; D9). Rotacion por archivo (MA.3).

    Hasta M1 el audit log era una lista en memoria: se perdia en cada reinicio. En M2 lo auditado
    son acciones reales sobre archivos del usuario, de modo que el registro deja de ser
    observabilidad y pasa a ser prueba forense.

    Formato JSONL append-only: cada linea es un registro independiente. Elegido frente a un array
    JSON reescrito porque (a) un corte durante la escritura solo puede danar la ultima linea, no el
    historial completo, y (b) anadir es O(1) sin releer el archivo. `fsync` tras cada anexion:
    sobrevive a un corte de energia, no solo a un reinicio limpio.

    **Rotacion por archivo (MA.3, D9).** Para acotar el crecimiento del almacenamiento SIN reducir la
    evidencia: cuando el fichero activo supera `umbral_bytes` se **sella** en un segmento inmutable con
    integridad `sha256` (anotada en un manifiesto) y se abre uno nuevo. **Nada se elimina** — la
    rotacion no borra registros; el borrado solo existe a peticion del usuario (Bible 5.5). El historial
    completo se reconstruye con el activo + los segmentos. Cada registro lleva un `seq` monotonico:
    identificador estable para que los conectores de senales resuman sin perder ni reprocesar tras rotar.

    **Varios escritores (DP-RESIDENCIA-MEDICION-CM2, Fase 1).** Varios procesos pueden compartir el
    mismo audit. Todo lo que escribe o rota va bajo `flock(LOCK_EX)` de `<audit>.lock`; los lectores
    publicos, bajo `LOCK_SH`. El `seq` se asigna DENTRO del cerrojo (cache validada por inodo+tamano; si
    otro escribio, se relee). Una cola sin salto de linea se CIERRA (nunca se recorta) y se deja constancia; el
    sellado no trunca nunca y un segmento huerfano (corte entre renombrar y anotar) se reconcilia.
    Limites declarados: flock es CONSULTIVO (solo excluye a quien lo toma) y en NFS su semantica depende
    del montaje; el audit debe vivir en un sistema de ficheros local.
    """

    _UMBRAL_BYTES = 5_000_000  # 5 MB por defecto; los arneses/pruebas lo bajan para forzar rotacion

    def __init__(self, path: str, umbral_bytes: int | None = None) -> None:
        self._path = path
        self._umbral = umbral_bytes if umbral_bytes is not None else self._UMBRAL_BYTES
        # Cache de seq: (ultimo seq escrito por MI, inodo, tamano del activo justo despues). Solo vale si
        # el activo sigue siendo exactamente ese; si no, alguien mas escribio o roto y se relee.
        self._cache: tuple[int, int, int] | None = None
        self._seq = 0
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        # Perezoso: sin nada que reconciliar, construir no deja NINGUN efecto en disco (ni `.lock`); el
        # cerrojo se crea en la primera escritura y el seq se calcula bajo el en el primer append.
        self._rechazados: set[str] = set()  # constancia de rechazo: una vez por arranque
        if _candidatos_huerfanos(path):
            with _cerrojo(path, fcntl.LOCK_EX):
                self._cerrar_cola_truncada()  # antes de cualquier constancia: no fusionarla con una cola parcial
                self._reconciliar_huerfanos()  # vuelve a comprobar ya bajo el cerrojo

    @property
    def path(self) -> str:
        return self._path

    def append(self, record: dict) -> None:
        with _cerrojo(self._path, fcntl.LOCK_EX):
            self._cerrar_cola_truncada()
            self._escribir_registro(record)
            if os.path.getsize(self._path) >= self._umbral:
                self._sellar()

    # --- Todo lo de abajo se llama SIEMPRE con LOCK_EX tomado y NO toma cerrojo (sin reentrada) ---

    def _siguiente_seq(self) -> int:
        try:
            st = os.stat(self._path)
            ino, size = st.st_ino, st.st_size
        except FileNotFoundError:
            ino, size = -1, 0
        if self._cache is not None and self._cache[1] == ino and self._cache[2] == size:
            self._seq = self._cache[0]
        else:
            self._seq = _max_seq(self._path)
        return self._seq + 1

    def _anexar_bytes(self, datos: bytes) -> os.stat_result:
        """UN write O_APPEND + fsync (+ fsync del directorio si el fichero se acaba de crear)."""
        existia = os.path.exists(self._path)
        fd = os.open(self._path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(errno.ELOOP, f"el audit activo no es un fichero regular: {self._path}")
            escritos = os.write(fd, datos)
            if escritos != len(datos):
                raise ErrorEscrituraParcial(f"escritura parcial en {self._path}: {escritos}/{len(datos)} bytes")
            os.fsync(fd)
            st = os.fstat(fd)
        finally:
            os.close(fd)
        if not existia:
            _fsync_dir(_dir_de(self._path))
        return st

    def _escribir_registro(self, record: dict) -> None:
        seq = self._siguiente_seq()
        linea = json.dumps({**record, "ts": time.time(), "seq": seq}, ensure_ascii=False) + "\n"
        st = self._anexar_bytes(linea.encode("utf-8"))
        self._seq = seq  # solo si la escritura NO fallo: un append fallido no consume seq
        self._cache = (seq, st.st_ino, st.st_size)

    def _cerrar_cola_truncada(self) -> None:
        """Si el activo no acaba en salto de linea (corte a media escritura), lo cierra. Append-only:
        no se borra ni recorta ningun byte; la linea parcial queda como ilegible, que los lectores ya
        ignoran, y el evento siguiente deja de fusionarse con ella."""
        try:
            with open(self._path, "rb") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    return
                f.seek(-1, os.SEEK_END)
                if f.read(1) == b"\n":
                    return
        except FileNotFoundError:
            return
        self._anexar_bytes(b"\n")
        self._escribir_registro(
            {
                "level": "WARN",
                "module": "AUDIT",
                "msg": "linea parcial cerrada",
                "trace_id": "-",
                "audit": True,
                "evento": "audit.linea_parcial_cerrada",
            }
        )

    def _anotar_segmento(self, nombre: str, registros: list[dict]) -> dict:
        """Anexa la entrada del manifiesto (mismas claves de siempre) con fsync. Devuelve la entrada."""
        seqs = [r.get("seq", 0) for r in registros]
        entrada = {
            "segmento": nombre,
            "sha256": _sha256_file(os.path.join(_dir_de(self._path), nombre)),
            "seq_ini": min(seqs),
            "seq_fin": max(seqs),
            "registros": len(registros),
            "ts_sellado": time.time(),
        }
        datos = (json.dumps(entrada) + "\n").encode("utf-8")
        fd = os.open(_manifiesto(self._path), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            if os.write(fd, datos) != len(datos):
                raise ErrorEscrituraParcial(f"escritura parcial en {_manifiesto(self._path)}")
            os.fsync(fd)
        finally:
            os.close(fd)
        return entrada

    def _reconciliar_huerfanos(self) -> None:
        """Un segmento con nombre de segmento que no figura en el manifiesto es un sellado cortado entre
        renombrar y anotar: se anota (sus eventos siguen en disco) y se deja constancia. Solo se anota el
        que `_huerfanos_validos` acepta; los rechazados dejan constancia una vez por arranque. Limitacion
        declarada: un huerfano sin registros legibles no se anota (no hay seq que proteger)."""
        directorio = _dir_de(self._path)
        validos, rechazados = _huerfanos_validos(self._path)
        for nombre, motivo in rechazados:
            if nombre in self._rechazados:
                continue
            self._rechazados.add(nombre)
            self._escribir_registro(
                {
                    "level": "WARN",
                    "module": "AUDIT",
                    "msg": "segmento huerfano rechazado",
                    "trace_id": "-",
                    "audit": True,
                    "evento": "audit.segmento_rechazado",
                    "segmento": nombre,
                    "motivo": motivo,
                }
            )
        for nombre, registros in validos:
            entrada = self._anotar_segmento(nombre, registros)
            _fsync_dir(directorio)
            self._escribir_registro(
                {
                    "level": "WARN",
                    "module": "AUDIT",
                    "msg": "segmento reconciliado",
                    "trace_id": "-",
                    "audit": True,
                    "evento": "audit.segmento_reconciliado",
                    "segmento": nombre,
                    "sha256": entrada["sha256"],
                    "seq_ini": entrada["seq_ini"],
                    "seq_fin": entrada["seq_fin"],
                }
            )

    def _sellar(self) -> None:
        """Sella el fichero activo en un segmento inmutable con integridad. NO borra ni trunca nada (D9).
        Orden: renombrar -> manifiesto (+fsync) -> fsync del directorio. Si se corta entre medias, la
        reconciliacion del siguiente arranque anota el segmento. Llamado ya bajo LOCK_EX."""
        self._reconciliar_huerfanos()
        registros = _leer_fichero(self._path)
        if not registros:
            return
        seqs = [r.get("seq", 0) for r in registros]
        nombre = f"{os.path.basename(self._path)}.{min(seqs):012d}-{max(seqs):012d}"
        os.replace(self._path, os.path.join(_dir_de(self._path), nombre))  # sellar = renombrar (atomico)
        self._anotar_segmento(nombre, registros)
        _fsync_dir(_dir_de(self._path))
        self._cache = None  # no hay activo: el siguiente append relee (otro pudo escribir despues)

    def segmentos(self) -> list[dict]:
        """Segmentos sellados, leidos del manifiesto (en orden de sellado)."""
        with _cerrojo_lectura(self._path):
            return _leer_fichero(_manifiesto(self._path))

    def verificar(self, nombre_segmento: str) -> bool:
        """Integridad de un segmento: su sha256 actual == el anotado en el manifiesto."""
        with _cerrojo_lectura(self._path):
            manifiesto = _leer_fichero(_manifiesto(self._path))
            esperado = next((s["sha256"] for s in manifiesto if s["segmento"] == nombre_segmento), None)
            ruta = os.path.join(_dir_de(self._path), nombre_segmento)
            return esperado is not None and os.path.exists(ruta) and _sha256_file(ruta) == esperado

    def reconstruir(self) -> list[dict]:
        """Historial COMPLETO (D9): segmentos + activo, ordenado por seq, sin huecos ni duplicados."""
        return leer_audit_desde(self._path, -1)

    def leer_desde(self, seq: int) -> list[dict]:
        """Registros con seq > `seq`, de los segmentos relevantes + el activo. Robusto a rotacion."""
        return leer_audit_desde(self._path, seq)

    def records(self) -> list[dict]:
        """Compat (H2): el historial completo desde disco (activo + segmentos)."""
        return self.reconstruir()


def _manifiesto(path: str) -> str:
    return path + ".manifest"


def _leer_fichero(path: str) -> list[dict]:
    """Lee un JSONL descartando lineas truncadas (un corte solo dana la ultima, no el historial)."""
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                out.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return out


def _candidatos_huerfanos(path: str) -> list[str]:
    """Nombres con forma de segmento que el manifiesto no anota (sin cerrojo: solo lista, no valida)."""
    patron = re.escape(os.path.basename(path)) + _PATRON_SEGMENTO_FMT
    anotados = {s.get("segmento") for s in _leer_fichero(_manifiesto(path))}
    try:
        nombres = sorted(os.listdir(_dir_de(path)))
    except FileNotFoundError:
        return []
    return [n for n in nombres if n not in anotados and re.fullmatch(patron, n)]


def _huerfanos_validos(path: str) -> tuple[list[tuple[str, list[dict]]], list[tuple[str, str]]]:
    """(validos, rechazados) entre los candidatos a huerfano. Valido = fichero regular (lstat, no symlink)
    del uid propio cuyo rango de seq del NOMBRE coincide con el min/max del CONTENIDO. Un fichero sin
    registros legibles se ignora (ni valido ni rechazado). NO se exige contiguidad con el ultimo seq: el
    historico real puede traer duplicados previos y no es mision de la reconciliacion juzgarlos."""
    validos: list[tuple[str, list[dict]]] = []
    rechazados: list[tuple[str, str]] = []
    patron = re.escape(os.path.basename(path)) + _PATRON_SEGMENTO_FMT
    for nombre in _candidatos_huerfanos(path):
        ruta = os.path.join(_dir_de(path), nombre)
        try:
            st = os.lstat(ruta)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(st.st_mode):
            rechazados.append((nombre, "no es un fichero regular (symlink u otro)"))
            continue
        if st.st_uid != os.getuid():
            rechazados.append((nombre, "pertenece a otro uid"))
            continue
        registros = _leer_fichero(ruta)
        if not registros:
            continue
        seqs = [r.get("seq", 0) for r in registros]
        m = re.fullmatch(patron, nombre)
        if m is None or (int(m.group(1)), int(m.group(2))) != (min(seqs), max(seqs)):
            rechazados.append((nombre, "el rango del nombre no coincide con los seq del contenido"))
            continue
        validos.append((nombre, registros))
    return validos, rechazados


def _max_seq(path: str) -> int:
    """Mayor seq presente (segmentos + activo + huerfanos validos aun sin anotar); 0 si no hay ninguno.
    Los huerfanos cuentan: si otro escritor murio entre renombrar y anotar, su seq NO puede reutilizarse."""
    m = 0
    for _nombre, registros in _huerfanos_validos(path)[0]:
        m = max(m, *(r.get("seq", 0) for r in registros))
    for s in _leer_fichero(_manifiesto(path)):
        m = max(m, s.get("seq_fin", 0))
    for r in _leer_fichero(path):
        m = max(m, r.get("seq", 0))
    return m


def leer_audit_desde(path: str, seq: int) -> list[dict]:
    """Registros del audit log con seq > `seq`, de los segmentos + el activo, ordenados por seq.

    Robusto a rotacion: recorre los segmentos cuyo rango aun contiene seqs mayores que el cursor, mas
    el fichero activo. Asi, un evento sellado en un segmento entre dos recogidas no se pierde. Bajo
    LOCK_SH: no ve un sellado a medias (activo ya renombrado y manifiesto sin anotar).
    """
    registros: list[dict] = []
    with _cerrojo_lectura(path):
        for s in _leer_fichero(_manifiesto(path)):
            if s.get("seq_fin", 0) <= seq:
                continue  # segmento enteramente por debajo del cursor: ya procesado
            ruta = os.path.join(os.path.dirname(path) or ".", s["segmento"])
            registros += _leer_fichero(ruta)
        registros += _leer_fichero(path)
    return sorted((r for r in registros if r.get("seq", 0) > seq), key=lambda r: r.get("seq", 0))


def _sha256_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def configure_audit(path: str) -> AuditLog:
    """Activa la persistencia del audit log. Sin esto, el comportamiento es el de M1 (solo memoria)."""
    global _audit
    _audit = AuditLog(path)
    return _audit


def reset_audit() -> None:
    global _audit
    _audit = None
