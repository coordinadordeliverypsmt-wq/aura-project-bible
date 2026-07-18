"""Observabilidad (Bible P-ARQ-7): logs estructurados + trazabilidad por trace_id + latencia.
Los logs son dato del usuario (ADR-0001): en producción, locales y cifrados."""

from __future__ import annotations

import sys
import time

_records: list[dict] = []
_metrics: dict[str, float] = {}


def metric_inc(name: str, value: float = 1.0) -> None:
    """Metrica acumulativa (Bible P-ARQ-7): contadores y sumas por nombre."""
    _metrics[name] = _metrics.get(name, 0.0) + value


def metrics() -> dict:
    return dict(_metrics)


def log(level: str, module: str, msg: str, trace_id: str = "-", **kv) -> None:
    rec = {"level": level, "module": module, "msg": msg, "trace_id": trace_id, **kv}
    _records.append(rec)
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
