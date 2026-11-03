"""Observabilidad (Bible P-ARQ-7): logs estructurados + trazabilidad por trace_id + latencia.
Los logs son dato del usuario (ADR-0001): en producción, locales y cifrados."""

from __future__ import annotations

import json
import os
import sys
import time

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
    """

    _UMBRAL_BYTES = 5_000_000  # 5 MB por defecto; los arneses/pruebas lo bajan para forzar rotacion

    def __init__(self, path: str, umbral_bytes: int | None = None) -> None:
        self._path = path
        self._umbral = umbral_bytes if umbral_bytes is not None else self._UMBRAL_BYTES
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self._seq = _max_seq(path)  # el proximo append usa +1; monotonico entre reinicios

    @property
    def path(self) -> str:
        return self._path

    def append(self, record: dict) -> None:
        self._seq += 1
        linea = json.dumps({**record, "ts": time.time(), "seq": self._seq}, ensure_ascii=False)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
            f.flush()
            os.fsync(f.fileno())
        if os.path.getsize(self._path) >= self._umbral:
            self._sellar()

    def _sellar(self) -> None:
        """Sella el fichero activo en un segmento inmutable con integridad. NO borra nada (D9)."""
        registros = _leer_fichero(self._path)
        if not registros:
            return
        seq_ini, seq_fin = registros[0].get("seq", 0), registros[-1].get("seq", 0)
        nombre = f"{os.path.basename(self._path)}.{seq_ini:012d}-{seq_fin:012d}"
        destino = os.path.join(os.path.dirname(self._path) or ".", nombre)
        os.replace(self._path, destino)  # sellar = renombrar (atomico)
        entrada = {
            "segmento": nombre,
            "sha256": _sha256_file(destino),
            "seq_ini": seq_ini,
            "seq_fin": seq_fin,
            "registros": len(registros),
            "ts_sellado": time.time(),
        }
        with open(_manifiesto(self._path), "a", encoding="utf-8") as mf:
            mf.write(json.dumps(entrada) + "\n")
            mf.flush()
            os.fsync(mf.fileno())
        open(self._path, "w").close()  # nuevo fichero activo, vacio

    def segmentos(self) -> list[dict]:
        """Segmentos sellados, leidos del manifiesto (en orden de sellado)."""
        return _leer_fichero(_manifiesto(self._path))

    def verificar(self, nombre_segmento: str) -> bool:
        """Integridad de un segmento: su sha256 actual == el anotado en el manifiesto."""
        esperado = next((s["sha256"] for s in self.segmentos() if s["segmento"] == nombre_segmento), None)
        ruta = os.path.join(os.path.dirname(self._path) or ".", nombre_segmento)
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


def _max_seq(path: str) -> int:
    """Mayor seq presente (segmentos + activo); 0 si no hay ninguno."""
    m = 0
    for s in _leer_fichero(_manifiesto(path)):
        m = max(m, s.get("seq_fin", 0))
    for r in _leer_fichero(path):
        m = max(m, r.get("seq", 0))
    return m


def leer_audit_desde(path: str, seq: int) -> list[dict]:
    """Registros del audit log con seq > `seq`, de los segmentos + el activo, ordenados por seq.

    Robusto a rotacion: recorre los segmentos cuyo rango aun contiene seqs mayores que el cursor, mas
    el fichero activo. Asi, un evento sellado en un segmento entre dos recogidas no se pierde.
    """
    registros: list[dict] = []
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
