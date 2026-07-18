"""Modulo de Memoria (Bible 4.1) — FUERA del nucleo (3.2, D10 'inteligencia desacoplada').
En produccion: Qdrant (ADR-0007). Aqui: store simple con procedencia y no-fabricacion."""

from __future__ import annotations

import json
import os

from .. import observability as obs


class SimpleMemory:
    def __init__(self):
        self._items: list[dict] = []

    async def write(self, user_id, kind, content, provenance):
        self._items.append({"user_id": user_id, "kind": kind, "content": content, "provenance": provenance})
        obs.log("MEM", "memory", f"write [{kind}] '{content[:40]}'", provenance.get("trace_id", "-"))

    async def recall(self, user_id, query, k=3):
        q = set(query.lower().split())
        scored = []
        for it in self._items:
            if it["user_id"] != user_id:
                continue
            overlap = len(q & set(it["content"].lower().split()))
            if overlap:
                scored.append((overlap, it))
        scored.sort(key=lambda x: -x[0])
        hits = [it for _, it in scored[:k]]
        obs.log("MEM", "memory", f"recall '{query[:30]}' -> {len(hits)} hit(s)")
        return hits  # con procedencia; si vacio, el orquestador NO fabrica (2.4 2 / 4.1 4)


class PersistentMemory:
    """Memoria persistente con backups y recuperacion (Bible 4.1 / 3.5 §6; prioridad M1).
    Cumple el contrato MemoryStore. Escrituras atomicas + integridad sha256 + copias 3-2-1.
    NOTA (ADR-0001): el cifrado en reposo se aplica en produccion; requiere una dependencia de cifrado
    que se justificara segun D26 (no se introduce aqui sin beneficio medible). La integridad ya se garantiza."""

    def __init__(self, path: str, backups_dir: str | None = None):
        self._path = path
        self._bdir = backups_dir or (path + ".backups")
        self._items: list[dict] = []
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        os.makedirs(self._bdir, exist_ok=True)
        self._load()

    # --- contrato MemoryStore ---
    async def write(self, user_id: str, kind: str, content: str, provenance: dict) -> None:
        self._items.append({"user_id": user_id, "kind": kind, "content": content, "provenance": provenance})
        self._persist()
        obs.log("MEM", "memory", f"write [{kind}] '{content[:40]}'", provenance.get("trace_id", "-"))

    async def recall(self, user_id: str, query: str, k: int = 3) -> list[dict]:
        q = set(query.lower().split())
        scored = []
        for it in self._items:
            if it["user_id"] != user_id:
                continue
            overlap = len(q & set(it["content"].lower().split()))
            if overlap:
                scored.append((overlap, it))
        scored.sort(key=lambda x: -x[0])
        hits = [it for _, it in scored[:k]]
        obs.log("MEM", "memory", f"recall '{query[:30]}' -> {len(hits)} hit(s)")
        return hits

    # --- persistencia atomica ---
    def _persist(self) -> None:
        tmp = self._path + ".tmp"
        data = json.dumps(self._items, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self._path)  # atomico (3.5 §4: no corromper la memoria)

    def _load(self) -> None:
        if os.path.exists(self._path):
            with open(self._path, encoding="utf-8") as f:
                self._items = json.load(f)

    # --- backups y recuperacion (3-2-1, prioridad M1) ---
    def backup(self) -> str:
        """Crea una copia de respaldo con checksum en el manifiesto. Devuelve el nombre del backup."""
        self._persist()
        digest = _sha256_file(self._path)
        name = f"memoria-{digest[:12]}.json"
        dst = os.path.join(self._bdir, name)
        with open(self._path, encoding="utf-8") as src, open(dst, "w", encoding="utf-8") as out:
            out.write(src.read())
        # manifiesto append-only con integridad
        with open(os.path.join(self._bdir, "manifest.jsonl"), "a", encoding="utf-8") as mf:
            mf.write(json.dumps({"backup": name, "sha256": digest, "items": len(self._items)}) + "\n")
        obs.log("BACKUP", "memory", f"backup creado {name} ({len(self._items)} items)", "-", audit=True)
        return name

    def verify(self, backup_name: str) -> bool:
        """Verifica la integridad de un backup contra el manifiesto (sha256)."""
        expected = None
        mpath = os.path.join(self._bdir, "manifest.jsonl")
        if os.path.exists(mpath):
            for line in open(mpath, encoding="utf-8"):
                rec = json.loads(line)
                if rec["backup"] == backup_name:
                    expected = rec["sha256"]
        actual = _sha256_file(os.path.join(self._bdir, backup_name))
        return expected is not None and expected == actual

    def restore(self, backup_name: str) -> bool:
        """Restaura desde un backup solo si su integridad es valida (recuperacion ante desastre)."""
        if not self.verify(backup_name):
            obs.log("BACKUP", "memory", f"restore RECHAZADO: integridad invalida {backup_name}", "-", audit=True)
            return False
        src = os.path.join(self._bdir, backup_name)
        with open(src, encoding="utf-8") as f:
            self._items = json.load(f)
        self._persist()
        obs.log("BACKUP", "memory", f"restore OK desde {backup_name} ({len(self._items)} items)", "-", audit=True)
        return True


def _sha256_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
