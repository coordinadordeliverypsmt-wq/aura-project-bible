"""Modulo de Memoria (Bible 4.1) — FUERA del nucleo (3.2, D10 'inteligencia desacoplada').
En produccion: Qdrant (ADR-0007). Aqui: store simple con procedencia y no-fabricacion."""

from __future__ import annotations

import json
import os
import re
import unicodedata

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


# --- Recuperacion lexica de N1 (V4) --------------------------------------------------------------
#
# COBERTURA MINIMA DE LA CONSULTA: un recuerdo se acepta solo si contiene al menos esta fraccion de
# los terminos informativos de la pregunta.
#
# POR QUE 0.60. Es el punto optimo MEDIDO sobre la bateria oficial (`tests/datos/bateria_memoria.json`,
# 59 recuerdos y 71 consultas), con el orden de prioridad fijado por el CEO: primero cero falsos
# positivos PUROS, luego cero falsos positivos CRITICOS, despues recall y por ultimo coste. 0.60 es el
# umbral MAS BAJO que logra ambos ceros, y por tanto el que conserva mas recall (0.654) y mas contexto
# util. Subir a 0.67 no elimina ningun error y pierde recuerdos legitimos; bajar a 0.50 reintroduce
# 3 falsos positivos criticos.
#
# POR QUE NO SE ANADIO "o solape >= 2 terminos" (variante V7, descartada). Subia el recall a 0.692
# (+3.8 puntos) pero una validacion adversarial dirigida la rompio en 6 de 6 casos disenados —frente
# a 2 de 6 de esta variante—: aceptar por numero absoluto de terminos, sin mirar la proporcion, deja
# pasar consultas largas sobre OTRA entidad ("la marca y el modelo del coche DE MI VECINO" contra "mi
# coche es de marca Ford"). Cuadruplicaba los falsos positivos criticos para ganar 2 aciertos de 52.
# Con el orden de prioridad vigente es el intercambio equivocado. No reintroducir sin superar antes
# `tests/datos/bateria_memoria.json`, casos adversariales incluidos.
#
# NO es un numero magico: si aparece una bateria mejor, se cambia AQUI y la bateria vuelve a decidir.
_COBERTURA_MINIMA = 0.60

# Palabras sin contenido discriminante: no se indexan ni se consultan.
#
# Emparejar por "mi", "es" o "el" devolvia recuerdos irrelevantes en ~78% de las consultas sin
# respuesta, lo que vaciaba de contenido la garantia de ADR-0014: el Core solo responde "no tengo
# ningun recuerdo" cuando la busqueda da CERO, y si casi nunca da cero, la garantia no se activa.
#
# Incluye tres familias, todas funcionales:
#   - articulos, preposiciones, pronombres y auxiliares;
#   - INTERROGATIVOS ("cual", "donde", "como"): sin ellos, "¿cual es mi cumpleanos?" solo cubria 1 de
#     2 terminos y no encontraba "mi cumpleanos es el 14 de marzo";
#   - VERBOS DE EVOCACION ("acordamos", "dijimos", "hablamos"): piden un recuerdo, no describen su
#     contenido. Sin ellos, "¿que acordamos sobre la sala?" no recuperaba "usuario dijo: enciende la
#     luz de la sala en modo tenue", porque el usuario nunca dijo la palabra "acordamos".
_VACIAS = frozenset(
    """a al ante con contra de del desde durante e el ella ellas ellos en entre era eran eres es esa esas
    ese eso esos esta estan estas este esto estos fue fueron ha han hasta hay la las le les lo los mas me
    mi mia mias mio mios mis mucho muy nos o para pero por porque que quien quienes se segun ser si sin
    sobre son su sus tambien te tengo tiene tienen todo todos tu tus un una unas uno unos y ya
    cual cuales cuando cuanto cuanta cuantos cuantas como donde cuyo cuya dime dice cuentame recuerdas
    sabes acordamos acordaste dijimos dijiste hablamos comentamos comente mencione quedamos""".split()
)


def _terminos(texto: str) -> set[str]:
    """Terminos informativos de un texto: sin acentos, sin puntuacion y sin palabras vacias.

    Se usa EXACTAMENTE la misma funcion al indexar y al consultar. Si divergieran, un recuerdo
    quedaria guardado bajo claves que la consulta nunca produce — que era el defecto de
    `.lower().split()`: dejaba la puntuacion pegada, de modo que "aura?" no encontraba "aura".
    """
    plano = unicodedata.normalize("NFD", texto.lower())
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return {t for t in re.findall(r"\w+", plano) if t not in _VACIAS}


class PersistentMemory:
    """Memoria persistente con backups y recuperacion (Bible 4.1 / 3.5 §6; prioridad M1).
    Cumple el contrato MemoryStore. Escrituras atomicas + integridad sha256 + copias 3-2-1.
    NOTA (ADR-0001): el cifrado en reposo se aplica en produccion; requiere una dependencia de cifrado
    que se justificara segun D26 (no se introduce aqui sin beneficio medible). La integridad ya se garantiza."""

    def __init__(self, path: str, backups_dir: str | None = None):
        self._path = path
        self._bdir = backups_dir or (path + ".backups")
        self._items: list[dict] = []
        self._indice: dict[tuple[str, str], list[int]] = {}
        self._cache_terminos: dict[int, set[str]] = {}  # termino -> posiciones (MA.2a)
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
        consulta = _terminos(query)
        if not consulta:
            # Sin terminos informativos no hay nada que discriminar: devolver algo seria emparejar por
            # palabras vacias, que es justo lo que vaciaba de contenido la garantia de ADR-0014.
            obs.log("MEM", "memory", f"recall '{query[:30]}' -> 0 hit(s)", "-")
            return []

        # CANDIDATOS solo desde los terminos SELECTIVOS: se conserva intacto el salto de terminos
        # ubicuos de MA.2a. Es posible porque la cobertura necesita la RESPUESTA a "¿contiene R el
        # termino T?", no el METODO: en vez de recorrer la lista larga de T (coste lineal en el
        # corpus), se mira el conjunto de terminos del propio candidato (coste constante). Verificado:
        # resultados identicos en las 71 consultas de la bateria visitando un 35% menos de posteos.
        candidatos: set[int] = set()
        for termino in sorted(consulta, key=lambda t: len(self._indice.get((user_id, t), ()))):
            posteo = self._indice.get((user_id, termino), ())
            if candidatos and len(posteo) > self._UMBRAL_UBICUO:
                continue  # los selectivos ya aportaron candidatos; este solo anadiria coste
            candidatos |= set(posteo)

        minimo = _COBERTURA_MINIMA * len(consulta)
        # Desempate por posicion en el almacen: dos recuerdos con la misma cobertura salen SIEMPRE en
        # el mismo orden. Antes dependia del orden de iteracion de un `set`, que varia con el hash del
        # proceso: la misma consulta podia devolver recuerdos distintos en dos arranques (comprobado).
        puntuados = [(idx, len(consulta & self._terminos_item(idx))) for idx in sorted(candidatos)]
        mejores = sorted(
            ((idx, n) for idx, n in puntuados if n >= minimo),
            key=lambda par: (-par[1], par[0]),
        )[:k]
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
    def _terminos_item(self, idx: int) -> set[str]:
        """Terminos informativos del recuerdo `idx`, cacheados.

        Permite completar la cobertura sin recorrer las listas de posteo ubicuas (MA.2a): responder
        "¿contiene este recuerdo el termino T?" pasa a costar O(1) en vez de O(longitud de la lista).
        """
        cache = self._cache_terminos
        if idx not in cache:
            cache[idx] = _terminos(self._items[idx]["content"])
        return cache[idx]

    def _indexar(self, idx: int, item: dict) -> None:
        clave_usuario = item["user_id"]
        for termino in _terminos(item["content"]):
            self._indice.setdefault((clave_usuario, termino), []).append(idx)

    def _reconstruir_indice(self) -> None:
        self._indice = {}
        self._cache_terminos = {}
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
