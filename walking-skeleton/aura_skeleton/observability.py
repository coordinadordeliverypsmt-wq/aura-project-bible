"""Observabilidad (Bible P-ARQ-7): logs estructurados + trazabilidad por trace_id + latencia.
Los logs son dato del usuario (ADR-0001): en producción, locales y cifrados."""

from __future__ import annotations

import json
import os
import sys
import time

_records: list[dict] = []
_metrics: dict[str, float] = {}
_audit: AuditLog | None = None


def metric_inc(name: str, value: float = 1.0) -> None:
    """Metrica acumulativa (Bible P-ARQ-7): contadores y sumas por nombre."""
    _metrics[name] = _metrics.get(name, 0.0) + value


def metrics() -> dict:
    return dict(_metrics)


def log(level: str, module: str, msg: str, trace_id: str = "-", **kv) -> None:
    rec = {"level": level, "module": module, "msg": msg, "trace_id": trace_id, **kv}
    _records.append(rec)
    if rec.get("audit") and _audit is not None:
        _audit.append(rec)  # H2: las acciones con efecto se persisten, no solo se imprimen
    extra = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"  [{level:<5}] {module:<14} trace={trace_id[:8]} {msg} {extra}".rstrip(), file=sys.stderr)


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
    """Registro de auditoria PERSISTENTE (H2, M2.0).

    Hasta M1 el audit log era una lista en memoria: se perdia en cada reinicio. En M2 lo auditado
    son acciones reales sobre archivos del usuario, de modo que el registro deja de ser
    observabilidad y pasa a ser prueba forense.

    Formato JSONL append-only: cada linea es un registro independiente. Elegido frente a un array
    JSON reescrito porque (a) un corte durante la escritura solo puede danar la ultima linea, no el
    historial completo, y (b) anadir es O(1) sin releer el archivo.

    `fsync` tras cada anexion: sobrevive a un corte de energia, no solo a un reinicio limpio. Es
    mas lento, y es el compromiso correcto para un registro forense.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)

    @property
    def path(self) -> str:
        return self._path

    def append(self, record: dict) -> None:
        linea = json.dumps({**record, "ts": time.time()}, ensure_ascii=False)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
            f.flush()
            os.fsync(f.fileno())

    def records(self) -> list[dict]:
        """Lee el historial completo desde disco. Una linea truncada se descarta sin invalidar el resto."""
        if not os.path.exists(self._path):
            return []
        out: list[dict] = []
        with open(self._path, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    out.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue  # corte a mitad de escritura: se pierde esa linea, no el registro
        return out


def configure_audit(path: str) -> AuditLog:
    """Activa la persistencia del audit log. Sin esto, el comportamiento es el de M1 (solo memoria)."""
    global _audit
    _audit = AuditLog(path)
    return _audit


def reset_audit() -> None:
    global _audit
    _audit = None
