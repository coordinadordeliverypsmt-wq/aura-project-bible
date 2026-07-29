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
        return hits

    def olvidar(self, predicado) -> int:
        """Elimina en RAM las entradas que cumplen `predicado`. Devuelve cuantas. (No persiste: en memoria.)"""
        antes = len(self._items)
        self._items = [i for i in self._items if not predicado(i)]
        return antes - len(self._items)

    def marcar(self, predicado, campos: dict) -> int:
        n = 0
        for i in self._items:
            if predicado(i):
                i.setdefault("provenance", {}).update(campos)
                n += 1
        return n  # con procedencia; si vacio, el orquestador NO fabrica (2.4 2 / 4.1 4)


class PersistentMemory:
    """Memoria persistente con backups y recuperacion (Bible 4.1 / 3.5 §6; prioridad M1).
    Cumple el contrato MemoryStore. Escrituras atomicas + integridad sha256 + copias 3-2-1.
    NOTA (ADR-0001): el cifrado en reposo se aplica en produccion; requiere una dependencia de cifrado
    que se justificara segun D26 (no se introduce aqui sin beneficio medible). La integridad ya se garantiza."""

    def __init__(self, path: str, backups_dir: str | None = None):
        self._path = path
        self._bdir = backups_dir or (path + ".backups")
        self._items: list[dict] = []
        self._indice: dict[tuple[str, str], list[int]] = {}  # termino -> posiciones (MA.2a)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        os.makedirs(self._bdir, exist_ok=True)
        self._load()

    _UMBRAL_UBICUO = 256  # una lista de posteo mas larga que esto es un stopword efectivo (MA.2a)

    # --- contrato MemoryStore ---
    async def write(self, user_id: str, kind: str, content: str, provenance: dict) -> None:
        item = {"user_id": user_id, "kind": kind, "content": content, "provenance": provenance}
        self._items.append(item)
        self._indexar(len(self._items) - 1, item)
        self._anexar(item)  # MA.2a: append O(1), no reescritura del historial completo
        obs.log("MEM", "memory", f"write [{kind}] '{content[:40]}'", provenance.get("trace_id", "-"))

    async def recall(self, user_id: str, query: str, k: int = 3) -> list[dict]:
        """MA.2a: solo visita los recuerdos que comparten algun termino con la consulta.

        Antes recorria TODOS los items en cada turno (R-1): 0,55 ms con 300 recuerdos, 9,22 ms con
        3.000. El resultado es identico —mismo criterio de solapamiento de terminos—, cambia lo que
        cuesta obtenerlo.
        """
        listas = sorted(
            (self._indice.get((user_id, t), ()) for t in set(query.lower().split())),
            key=len,
        )
        # Los terminos MAS SELECTIVOS primero. Un termino ubicuo ("tema", "usuario") no discrimina:
        # su lista cubre casi todo el corpus y recorrerla devuelve el recall a coste lineal. Se trata
        # como palabra vacia y se SALTA en cuanto ya hay candidatos de terminos mas informativos.
        # Es el mismo criterio por el que un buscador ignora los stopwords.
        candidatos: dict[int, int] = {}
        for posteo in listas:
            if candidatos and len(posteo) > self._UMBRAL_UBICUO:
                break  # los selectivos ya aportaron candidatos; este solo anadiria ruido caro
            for idx in posteo:
                candidatos[idx] = candidatos.get(idx, 0) + 1
        mejores = sorted(candidatos.items(), key=lambda par: -par[1])[:k]
        hits = [self._items[idx] for idx, _ in mejores]
        obs.log("MEM", "memory", f"recall '{query[:30]}' -> {len(hits)} hit(s)")
        return hits

    def olvidar(self, predicado) -> int:
        """Elimina las entradas que cumplen `predicado`, reconstruye el indice y PERSISTE el borrado.

        Soberania del usuario (ADR-0017): un "olvida esto" debe sobrevivir al reinicio. Antes, borrar solo
        mutaba la lista en memoria y el dato reaparecia al releer el JSONL; aqui se reescribe el fichero.
        """
        antes = len(self._items)
        self._items = [i for i in self._items if not predicado(i)]
        borrados = antes - len(self._items)
        if borrados:
            self._reconstruir_indice()  # el indice guarda posiciones: hay que rehacerlo tras eliminar
            self._persist()  # reescritura atomica del JSONL: el olvido sobrevive al reinicio
            obs.log("MEM", "memory", f"olvidadas {borrados} entrada(s) del modelo del usuario", "-", audit=True)
        return borrados

    def marcar(self, predicado, campos: dict) -> int:
        """Anota `campos` en la procedencia de las entradas que cumplen `predicado`, y PERSISTE el cambio.

        Lo usa la refutacion del usuario ("eso ya no es cierto"): marcar `refutada` debe sobrevivir al
        reinicio, igual que el olvido — si no, AURA volveria a darlo por cierto al arrancar.
        """
        n = 0
        for i in self._items:
            if predicado(i):
                i.setdefault("provenance", {}).update(campos)
                n += 1
        if n:
            self._persist()
        return n

    # --- indice invertido (MA.2a) ---
    def _indexar(self, idx: int, item: dict) -> None:
        clave_usuario = item["user_id"]
        for termino in set(item["content"].lower().split()):
            self._indice.setdefault((clave_usuario, termino), []).append(idx)

    def _reconstruir_indice(self) -> None:
        self._indice = {}
        for idx, item in enumerate(self._items):
            self._indexar(idx, item)

    def _anexar(self, item: dict) -> None:
        """Escritura incremental en JSONL. Un corte solo puede danar la ultima linea."""
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # --- persistencia atomica ---
    def _persist(self) -> None:
        """Reescritura completa del fichero. Ya NO se usa en cada `write` (MA.2a): solo cuando el
        historial cambia por entero —restore, migracion de formato— o al crear un backup."""
        tmp = self._path + ".tmp"
        data = "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in self._items)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self._path)  # atomico (3.5 §4: no corromper la memoria)

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, encoding="utf-8") as f:
            contenido = f.read().strip()
        if not contenido:
            return
        if contenido.startswith("["):
            # Formato antiguo (un unico JSON array). Se migra a JSONL una sola vez, conservando
            # el historial: la optimizacion no puede costar los recuerdos ya guardados.
            self._items = json.loads(contenido)
            self._persist()
            obs.log("MEM", "memory", f"memoria migrada a formato incremental ({len(self._items)} items)", "-")
        else:
            self._items = [json.loads(linea) for linea in contenido.splitlines() if linea.strip()]
        self._reconstruir_indice()

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
            contenido = f.read().strip()
        self._items = (
            json.loads(contenido)
            if contenido.startswith("[")
            else [json.loads(x) for x in contenido.splitlines() if x.strip()]
        )
        self._persist()
        self._reconstruir_indice()
        obs.log("BACKUP", "memory", f"restore OK desde {backup_name} ({len(self._items)} items)", "-", audit=True)
        return True


def _sha256_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
