"""Memoria de indice semantico (N2, ADR-0020) — segundo nivel de la capacidad Memoria (Bible 4.1).

N1 (`PersistentMemory`) recupera por **solapamiento lexico** de terminos exactos. N2 recupera por
**similitud semantica** (coseno de embeddings), de modo que una parafrasis sin terminos comunes puede
recuperar el recuerdo afin. Esa diferencia conductual es la que hace que el `PlanActivacion`, al elegir
entre N1 y N2 segun el perfil, gobierne una **materializacion real** (no solo una etiqueta): antes de N2,
la composicion devolvia el mismo objeto en ambas ramas del plan (delta observable 0).

**Contrato:** identico al de N1 (`MemoryStore`: `write`/`recall` async). N2 **reutiliza** `PersistentMemory`
para todo el almacenamiento y la persistencia (JSONL atomico, backups, recuperacion): no reimplementa nada
de eso —menor riesgo—; solo anade la capa de embeddings y sustituye el criterio de recall.

**Dependencias:** `onnxruntime` y `tokenizers` (ya en el entorno; ADR-0020 aprueba el indice embebido).
Se importan de forma **perezosa**: importar este modulo no las exige; solo se necesitan al instanciar N2,
que la composicion hace unicamente cuando el plan promueve memoria y el modelo esta presente. El pooling y
el coseno se calculan en Python puro, **sin numpy** en el codigo.

**Calidad del embedder:** fuera del alcance de este trabajo (Decision Package). El modelo disponible tiene
calidad limitada en espanol; mejorarlo (embedder multilingue) es seguimiento de PRODUCTO, no de esta
capacidad. Aqui solo importa que N2 cumpla el contrato y sea conductualmente distinta de N1.
"""

from __future__ import annotations

import math
import os

from .. import observability as obs
from .memory import PersistentMemory

# Cache de modelo por directorio: cargar el ONNX (90 MB) una sola vez por proceso, no por instancia.
# Es coste de arranque inevitable para cumplir el contrato, no una optimizacion de rendimiento anadida.
_MODELOS: dict[str, tuple] = {}


def modelo_disponible(modelo_dir: str) -> bool:
    """¿Existen los artefactos del embedder (model.onnx + tokenizer.json) en el directorio dado?"""
    return (
        bool(modelo_dir)
        and os.path.isfile(os.path.join(modelo_dir, "model.onnx"))
        and os.path.isfile(os.path.join(modelo_dir, "tokenizer.json"))
    )


def _cargar(modelo_dir: str) -> tuple:
    if modelo_dir not in _MODELOS:
        import onnxruntime as ort  # perezoso: no se exige para importar el modulo
        from tokenizers import Tokenizer

        tok = Tokenizer.from_file(os.path.join(modelo_dir, "tokenizer.json"))
        tok.no_padding()  # el tokenizer trae padding fijo a 128; sin esto cada embed viola el presupuesto ~3x
        sess = ort.InferenceSession(os.path.join(modelo_dir, "model.onnx"), providers=["CPUExecutionProvider"])
        _MODELOS[modelo_dir] = (tok, sess)
    return _MODELOS[modelo_dir]


class SemanticMemory:
    """N2: recall semantico tras el contrato MemoryStore. Almacena via PersistentMemory (N1)."""

    def __init__(self, path: str, modelo_dir: str, backups_dir: str | None = None) -> None:
        self._store = PersistentMemory(path, backups_dir)
        self._tok, self._sess = _cargar(modelo_dir)
        # Vectores (list[float] normalizados) alineados por indice con self._store._items.
        self._vectores: list[list[float]] = [self._embed(it["content"]) for it in self._store._items]

    def _embed(self, texto: str) -> list[float]:
        """Embedding L2-normalizado (list[float]). Sin numpy en el codigo: el ONNX devuelve arrays que se
        pasan a listas con .tolist(); el mean-pooling y la norma se hacen en Python puro (el corpus de
        memoria personal es pequeno; escalar con un indice ANN es trabajo posterior, fuera de alcance)."""
        cod = self._tok.encode(texto)
        feed = {
            "input_ids": [cod.ids],
            "attention_mask": [cod.attention_mask],
            "token_type_ids": [[0] * len(cod.ids)],
        }
        # no_padding() garantiza que TODOS los tokens son reales (mascara de atencion siempre 1), asi que
        # el mean-pooling es la media directa sobre los `seq` estados; no hace falta ponderar por mascara.
        estados = self._sess.run(None, feed)[0][0].tolist()  # (seq, 384) -> list[list[float]]
        n = len(estados)
        dim = len(estados[0])
        suma = [0.0] * dim
        for vec_tok in estados:
            for j in range(dim):
                suma[j] += vec_tok[j]
        suma = [x / n for x in suma]  # mean-pooling
        norma = math.sqrt(sum(x * x for x in suma)) or 1.0
        return [x / norma for x in suma]  # normalizacion L2 -> el producto punto es el coseno

    @staticmethod
    def _coseno(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    # --- contrato MemoryStore (identico a N1) ---
    async def write(self, user_id: str, kind: str, content: str, provenance: dict) -> None:
        await self._store.write(user_id, kind, content, provenance)
        self._vectores.append(self._embed(content))

    async def recall(self, user_id: str, query: str, k: int = 3) -> list[dict]:
        consulta = self._embed(query)
        puntuados = [
            (self._coseno(consulta, self._vectores[i]), it)
            for i, it in enumerate(self._store._items)
            if it["user_id"] == user_id
        ]
        puntuados.sort(key=lambda par: -par[0])
        hits = [it for _, it in puntuados[:k]]
        obs.log("MEM", "memory", f"recall semantico '{query[:30]}' -> {len(hits)} hit(s)")
        return hits
