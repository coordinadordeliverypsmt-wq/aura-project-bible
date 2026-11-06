"""Modulo de Memoria (Bible 4.1) — FUERA del nucleo (3.2, D10 'inteligencia desacoplada').
En produccion: Qdrant (ADR-0007). Aqui: store simple con procedencia y no-fabricacion."""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata

from .. import observability as obs
from ..contracts import HISTORICO, es_recuperable  # noqa: F401  (HISTORICO se reexporta)


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
            if it["user_id"] != user_id or not es_recuperable(it):
                continue  # el historico no recuperable existe, se persiste, y NO vuelve por aqui
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
# 65 recuerdos y 77 consultas), con el orden de prioridad fijado por el CEO: primero cero falsos
# positivos PUROS, luego cero falsos positivos CRITICOS, despues recall y por ultimo coste. Medido
# sobre la bateria VIGENTE (0.50 / 0.60 / 0.67): FP puros 0 / 0 / 0; FP criticos 9 / 2 / 1; recall@3
# 0.717 / 0.660 / 0.547. Los 2 criticos que quedan en 0.60 son los adversariales de frontera ya
# clasificados como corregibles ("de mi vecino", "de mi hermano"), con techo fijado en la prueba. Es
# el umbral mas bajo que los deja en ese suelo: 0.50 los multiplica por 4.5. Subir a 0.67 elimina uno
# mas, pero cuesta 6 aciertos de 53 (recall 0.660 -> 0.547); con el orden de prioridad vigente no
# compensa cambiar un adversarial conocido por seis recuerdos legitimos perdidos.
#
# POR QUE NO SE ANADIO "o solape >= 2 terminos" (variante V7, descartada). Subia el recall a 0.692
# (+3.8 puntos) pero una validacion adversarial dirigida la rompio en 6 de 6 casos disenados —frente
# a 2 de 6 de esta variante—: aceptar por numero absoluto de terminos, sin mirar la proporcion, deja
# pasar consultas largas sobre OTRA entidad ("la marca y el modelo del coche DE MI VECINO" contra "mi
# coche es de marca Ford"). Cuadruplicaba los falsos positivos criticos para ganar 2 aciertos de 53.
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
    sabes acordamos acordaste dijimos dijiste hablamos comentamos comente mencione quedamos
    oye porfa favor gracias perdona disculpa hola cosa queria quiero preguntarte decirte saber
    podrias puedes ayudame necesito oiga mira escucha bueno pues entonces vale aura""".split()
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


#: Marca de baja logica. Una linea con esta bandera NO es un recuerdo: es la constancia de que el
#: recuerdo de su misma clave dejo de estar vigente.
_LAPIDA = "_olvidada"


def _forma_de_corte(linea: str) -> bool:
    """True solo si `linea` es un PREFIJO ESTRICTO de un objeto JSON valido: su unico defecto es que la entrada se
    acaba. Una linea con un token invalido en medio (comilla perdida, bytes cambiados, dos lineas fusionadas) es
    CORRUPCION, no un corte, y no se tolera aunque quede abierta. Un corte dentro de un escape o de un literal
    (`\\u00`, `tru`) tampoco es demostrable: falla en alto (prudencia; afecta a disponibilidad, no a integridad)."""
    if not linea.startswith("{"):
        return False
    profundidad, en_cadena, escape = 0, False, False
    for c in linea:
        if en_cadena:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                en_cadena = False
        elif c == '"':
            en_cadena = True
        elif c in "{[":
            profundidad += 1
        elif c in "}]":
            profundidad -= 1
            if profundidad <= 0:
                return False  # el objeto raiz se cerro: no es un corte
    if escape or not (profundidad > 0 or en_cadena):
        return False
    candidata = linea + ('"' if en_cadena else "")
    try:
        json.loads(candidata)
    except json.JSONDecodeError as e:
        return e.pos >= len(candidata)  # el unico error es el FIN de la entrada
    return False


def _prefijos_de_clave(linea: dict) -> list[str] | None:
    """Como empieza en disco cualquier linea con la clave de `linea` (lapida, marca o reescritura). None si la
    linea no empieza por `user_id, kind, content` en ese orden: entonces no se puede descartar nada."""
    if not isinstance(linea, dict):
        return None  # no es un recuerdo: no se puede descartar nada (fallo cerrado)
    clave = {"user_id": linea.get("user_id"), "kind": linea.get("kind"), "content": linea.get("content")}
    prefijos = [json.dumps(clave, ensure_ascii=a)[:-1] for a in (False, True)]
    if not json.dumps(linea, ensure_ascii=False).startswith(prefijos[0]):
        return None
    return prefijos


def _fragmento_ambiguo(fragmento: str, prefijos: list[str] | None) -> bool:
    """True si `fragmento` PODRIA ser el comienzo de una linea con la clave de alguna linea existente (una lapida
    de `olvidar` o una marca de `marcar`): ignorarlo podria resucitar lo olvidado o des-refutar lo refutado.
    `prefijos` None = alguna linea con orden de claves desconocido: no se puede descartar nada (fallo cerrado)."""
    if prefijos is None:
        return True
    return any(fragmento.startswith(p) or p.startswith(fragmento) for p in prefijos)


# Una interrupcion real deja como mucho UN fragmento (el write en curso); mas de esto en un mismo fichero es
# corrupcion, no cortes, y ademas acota el coste de la lectura (cada fragmento se compara con todas las claves).
_MAX_FRAGMENTOS_TOLERADOS = 3


def _lineas_legibles(contenido: str) -> tuple[list[dict], list[tuple[int, str]]]:
    """Lectura de `memoria.json` COMPARTIDA por `PersistentMemory._load` y el reloj de CM2 (DP-DURABILIDAD-MEMORIA,
    P2-B). Devuelve (lineas, [(posicion, fragmento tolerado)]). Un fragmento solo se tolera si tiene forma de corte
    Y no es ambiguo, y como mucho `_MAX_FRAGMENTOS_TOLERADOS`; cualquier otra linea ilegible relanza su
    `JSONDecodeError` (T9: falla en alto)."""
    # Solo '\n' separa lineas: el escritor no emite otro separador y json.dumps(ensure_ascii=False) NO escapa
    # U+2028/U+2029/U+0085, en los que str.splitlines() SI corta (partiria un recuerdo valido en dos).
    crudas = [linea for linea in contenido.split("\n") if linea.strip()]
    lineas: list[dict] = []
    ilegibles: list[tuple[int, str, json.JSONDecodeError]] = []
    for posicion, linea in enumerate(crudas, start=1):
        try:
            lineas.append(json.loads(linea))
        except json.JSONDecodeError as e:
            ilegibles.append((posicion, linea, e))
    if not ilegibles:
        return lineas, []
    # Prefijos de clave calculados UNA vez (coste O(N) por lectura, no O(N) por fragmento).
    todos: list[str] = []
    orden_conocido = True
    for existente in lineas:
        propios = _prefijos_de_clave(existente)
        if propios is None:
            orden_conocido = False
            break
        todos.extend(propios)
    prefijos = todos if orden_conocido else None
    tolerados: list[tuple[int, str]] = []
    for posicion, linea, error in ilegibles:
        if (
            len(tolerados) >= _MAX_FRAGMENTOS_TOLERADOS
            or not _forma_de_corte(linea)
            or _fragmento_ambiguo(linea, prefijos)
        ):
            raise error
        tolerados.append((posicion, linea))
    return lineas, tolerados


def _cola_abierta(path: str) -> bool:
    """True si el fichero existe, no esta vacio y no acaba en salto de linea (escritura cortada)."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        tam = os.fstat(fd).st_size
        return tam > 0 and os.pread(fd, 1, tam - 1) != b"\n"
    finally:
        os.close(fd)


def _fsync_dir(directorio: str) -> None:
    """Sincroniza la entrada de directorio (creacion o rename duraderos). Errores: se propagan."""
    fd = os.open(directorio, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _abrir_privado(ruta: str, flags: int) -> int:
    """`opener` de los ficheros de memoria: se CREAN con 0600 (punto D, 2026-11-06). `memoria.json` guarda ahora el
    registro de lo que AURA hizo; sin firma ni cifrado, la mitigacion es que solo el usuario lo lea. LIMITE DECLARADO:
    los permisos de los DIRECTORIOS no se cambian aqui."""
    return os.open(ruta, flags, 0o600)


def _clave(item: dict) -> tuple:
    """Identidad de un recuerdo a efectos de proyeccion, analoga a `(user_id, rule_id)` en reglas."""
    return (item.get("user_id"), item.get("kind"), item.get("content"))


def _proyectar(lineas: list[dict]) -> list[dict]:
    """`historial fisico completo + ultima linea por clave = estado logico` (DP-D-M-8 §5.2).

    Es la mitad que hace util a la lapida: sin ella, un recuerdo dado de baja **reapareceria** al
    reiniciar, y el olvido del usuario seria falso. Mismo modelo que `AlmacenReglas._cargar`, donde
    por cada clave gana la ULTIMA linea y solo se listan las activas.
    """
    vigente: dict[tuple, dict] = {}
    for linea in lineas:
        vigente[_clave(linea)] = linea
    return [i for i in vigente.values() if not i.get(_LAPIDA)]


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
        # D-M-1 A′: recuerdos por usuario, para la cota de seguridad del recall (α·N). O(1) en write;
        # se recomputa al reconstruir el indice. No se persiste: es estado derivado de `_items`.
        self._conteo_usuario: dict[str, int] = {}
        # DP-DURABILIDAD-MEMORIA: si sincronizar el directorio fallo al crear el fichero, se reintenta en el
        # siguiente _anexar (si no, los write posteriores darian exito con la entrada sin confirmar).
        self._dir_pendiente = False
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        os.makedirs(self._bdir, exist_ok=True)
        if os.path.exists(path):
            os.chmod(path, 0o600)  # idempotente: un memoria.json de antes de este incremento tambien se cierra
        self._load()

    _UMBRAL_UBICUO = 256  # una lista de posteo mas larga que esto es un stopword efectivo (MA.2a)

    # --- contrato MemoryStore ---
    async def write(self, user_id: str, kind: str, content: str, provenance: dict) -> None:
        item = {"user_id": user_id, "kind": kind, "content": content, "provenance": provenance}
        # DP-DURABILIDAD-MEMORIA: primero en disco (con fsync), luego en la sesion. Si la escritura falla, el
        # error se propaga y el recuerdo NO entra en la proyeccion: la sesion no recuerda lo no confirmado.
        self._anexar(item)  # MA.2a: append O(1), no reescritura del historial completo
        self._items.append(item)
        self._indexar(len(self._items) - 1, item)
        self._conteo_usuario[user_id] = self._conteo_usuario.get(user_id, 0) + 1
        obs.log("MEM", "memory", f"write [{kind}] '{content[:40]}'", provenance.get("trace_id", "-"))

    async def recall(self, user_id: str, query: str, k: int = 3) -> list[dict]:
        """MA.2a: solo visita los recuerdos que comparten algun termino con la consulta.

        Antes recorria TODOS los items en cada turno (R-1): 0,55 ms con 300 recuerdos, 9,22 ms con
        3.000.

        EQUIVALENCIA EXACTA CON EL BARRIDO COMPLETO (D-M-1 A′, CEO 2026-10-12). La generacion de
        candidatos usa filtro de prefijo con cota de seguridad: el resultado coincide con la fuerza
        bruta en TODOS los regimenes, incluido el ubicuo (>`_UMBRAL_UBICUO`) que antes producia falsos
        negativos (D-M-1). Antes se saltaban los terminos ubicuos y un recuerdo cuyo unico solape con la
        consulta fueran esos terminos nunca entraba en candidatos; ya no.
        """
        consulta = _terminos(query)
        if not consulta:
            # Sin terminos informativos no hay nada que discriminar: devolver algo seria emparejar por
            # palabras vacias, que es justo lo que vaciaba de contenido la garantia de ADR-0014.
            obs.log("MEM", "memory", f"recall '{query[:30]}' -> 0 hit(s)", "-")
            return []

        # D-M-1 A′ (DP-D-M-1-RECUPERACION-EXACTA.md; aprobacion CEO 2026-10-12): generacion de candidatos
        # EXACTA por filtro de PREFIJO con cota de seguridad. Sustituye al salto heuristico de terminos
        # ubicuos, que dejaba fuera un recuerdo cuyo unico solape con la consulta eran terminos ubicuos
        # (falso negativo: ADR-0014 hacia que AURA negara un recuerdo que si tenia). NO cambia el criterio
        # de cobertura (`minimo` abajo), solo QUE recuerdos se examinan.
        n = len(consulta)
        m = math.ceil(_COBERTURA_MINIMA * n)  # terminos minimos para alcanzar la cobertura
        # Palomar: un recuerdo con >= m de los n terminos aparece forzosamente en alguna de las (n-m+1)
        # listas de posteo mas cortas. Unir SOLO esas es poda exacta (no depende de cuales sean).
        listas = sorted((self._indice.get((user_id, t), ()) for t in consulta), key=len)
        prefijo = listas[: n - m + 1]
        # Cota α=1: si el prefijo visitaria mas posteos que recuerdos tiene el usuario (peor caso: todos
        # los terminos ubicuos), barrido completo de los N recuerdos del usuario. Ambas ramas son EXACTAS
        # —por el palomar y por definicion—; la cota solo acota el coste del peor caso (MA.2a: nunca
        # visita mas que la fuerza bruta). α=1 es la eleccion conservadora del rango util [1,2] (ver DP §4).
        if sum(len(p) for p in prefijo) > self._conteo_usuario.get(user_id, 0):
            candidatos: list[int] = [idx for idx, it in enumerate(self._items) if it["user_id"] == user_id]
        else:
            cand: set[int] = set()
            for p in prefijo:
                cand |= set(p)
            candidatos = sorted(cand)

        minimo = _COBERTURA_MINIMA * len(consulta)
        # Desempate por posicion en el almacen: dos recuerdos con la misma cobertura salen SIEMPRE en
        # el mismo orden. Antes dependia del orden de iteracion de un `set`, que varia con el hash del
        # proceso: la misma consulta podia devolver recuerdos distintos en dos arranques (comprobado).
        # El historico no recuperable se descarta ANTES de puntuar: no compite, no desplaza a un
        # recuerdo real por el hueco `k`, y no puede colarse por un empate.
        puntuados = [
            (idx, len(consulta & self._terminos_item(idx)))
            for idx in sorted(candidatos)
            if es_recuperable(self._items[idx])
        ]
        mejores = sorted(
            ((idx, n) for idx, n in puntuados if n >= minimo),
            key=lambda par: (-par[1], par[0]),
        )[:k]
        hits = [self._items[idx] for idx, _ in mejores]
        obs.log("MEM", "memory", f"recall '{query[:30]}' -> {len(hits)} hit(s)")
        return hits

    def olvidar(self, predicado) -> int:
        """Retira de la proyeccion las entradas que cumplen `predicado`, reconstruye el indice y PERSISTE la baja.

        Soberania del usuario (ADR-0017): un "olvida esto" debe sobrevivir al reinicio. Desde G-7 la baja se
        persiste ANEXANDO una lapida (copia de la entrada con `_LAPIDA`), no reescribiendo el fichero: el
        historial fisico conserva la linea original y la lapida, y el contenido sigue en disco. La purga fisica
        no esta implementada (ver el comentario de abajo y DP-S3-RELOJ-CM2 §4.1).

        DP-DURABILIDAD-MEMORIA P3: atomico respecto a la RAM. Se ANEXAN todas las lapidas PRIMERO; solo si
        las `len(bajas)` anexiones tienen exito se toca `self._items`/el indice/`_conteo_usuario`. Si
        `_anexar` falla a mitad (ENOSPC/EIO/fsync), el error se propaga (INV-9) y la RAM queda exactamente
        como antes de la llamada: no hay rollback de disco (no se puede "desanexar" una lapida ya escrita),
        pero eso no corrompe nada porque el formato es append-only — la lapida que SI llego a disco sigue
        siendo la ULTIMA linea de su clave y, al reabrir, esa entrada se proyecta correctamente olvidada; las
        entradas cuya lapida no llego a anexarse no tienen lapida en disco y se proyectan vivas, igual que en
        RAM tras el fallo.
        """
        bajas = [i for i in self._items if predicado(i)]
        if bajas:
            # Anexar TODO antes de tocar la RAM. Si una anexion falla, el error se propaga aqui mismo,
            # sin haber quitado nada de `self._items`: la sesion sigue mostrando TODO lo olvidable.
            for baja in bajas:
                self._anexar({**baja, _LAPIDA: True})
            # G-7 · LAPIDA en vez de reescritura (DP-D-M-8 §5.2). Antes esto llamaba a `_persist()`,
            # que reescribe el JSONL entero: el olvido borraba la historia junto con el dato, y no
            # quedaba forma de saber que se perdio. Ahora se ANEXA una baja logica por entrada, que
            # es el patron que `AlmacenReglas.desactivar` ya usaba —y que §5.2 llama «el modelo a
            # imitar»—. El historial fisico permanece intacto; la proyeccion de `_load` decide.
            #
            # La purga fisica NO se implementa: §5.2 la deja abierta («No lo decido aqui»).
            self._items = [i for i in self._items if not predicado(i)]
            self._reconstruir_indice()  # el indice guarda posiciones: hay que rehacerlo tras eliminar
            obs.log("MEM", "memory", f"olvidadas {len(bajas)} entrada(s) del modelo del usuario", "-", audit=True)
        return len(bajas)

    def marcar(self, predicado, campos: dict) -> int:
        """Anota `campos` en la procedencia de las entradas que cumplen `predicado`, y PERSISTE el cambio.

        Lo usa la refutacion del usuario ("eso ya no es cierto"): marcar `refutada` debe sobrevivir al
        reinicio, igual que el olvido — si no, AURA volveria a darlo por cierto al arrancar.

        DP-DURABILIDAD-MEMORIA P3: atomico respecto a la RAM. Se construyen COPIAS de las entradas
        seleccionadas con la procedencia YA actualizada (sin mutar los dicts vivos de `self._items`), se
        ANEXAN todas esas copias primero y solo si las `n` anexiones tienen exito se aplican los campos a
        los objetos en memoria. Si `_anexar` falla a mitad, el error se propaga y ningun objeto vivo queda
        marcado: la sesion no da por refutado/marcado algo que el disco no confirma.
        """
        objetivos = [i for i in self._items if predicado(i)]
        n = len(objetivos)
        if n:
            # Copias con la procedencia ya actualizada: no se toca el dict vivo todavia.
            copias = [{**i, "provenance": {**i.get("provenance", {}), **campos}} for i in objetivos]
            # G-7 · §5.2 pide para `marcar` lo mismo que para `olvidar`: **anexar la marca**. La
            # linea nueva gana en la proyeccion por su clave, y la anterior sigue en el historial.
            # Anexar TODO antes de aplicar nada a RAM: si una anexion falla, el error se propaga aqui
            # mismo, sin que ningun objeto vivo haya quedado marcado.
            for copia in copias:
                self._anexar(copia)
            # Solo tras el exito de las `n` anexiones se aplican los campos a los objetos vivos.
            for i in objetivos:
                i.setdefault("provenance", {}).update(campos)
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
        self._conteo_usuario = {}
        for idx, item in enumerate(self._items):
            self._indexar(idx, item)
            self._conteo_usuario[item["user_id"]] = self._conteo_usuario.get(item["user_id"], 0) + 1

    def _anexar(self, item: dict) -> None:
        """Escritura incremental en JSONL. Un corte solo puede danar la ultima linea.

        Duradera (DP-DURABILIDAD-MEMORIA): flush + fsync del fichero, y fsync del directorio si el fichero se
        acaba de crear. Cualquier error (ENOSPC, EIO, el propio fsync) se propaga: nunca se da por escrito."""
        existia = os.path.exists(self._path)
        # P2-B: una cola sin salto de linea (corte previo) se CIERRA en el mismo write, sin borrar bytes: la linea
        # nueva no se fusiona con el fragmento (que `_lineas_legibles` tolera solo si no es ambiguo).
        cierre = "\n" if _cola_abierta(self._path) else ""
        with open(self._path, "a", encoding="utf-8", opener=_abrir_privado) as f:
            f.write(cierre + json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        if not existia or self._dir_pendiente:
            self._dir_pendiente = True
            _fsync_dir(os.path.dirname(self._path) or ".")
            self._dir_pendiente = False

    # --- persistencia atomica ---
    def _persist(self) -> None:
        """Reescritura completa del fichero. Ya NO se usa en cada `write` (MA.2a): solo cuando el
        historial cambia por entero —restore, migracion de formato— o al crear un backup."""
        tmp = self._path + ".tmp"
        data = "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in self._items)
        with open(tmp, "w", encoding="utf-8", opener=_abrir_privado) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())  # el contenido en disco ANTES del rename: si no, un corte deja la memoria vacia
        os.replace(tmp, self._path)  # atomico (3.5 §4: no corromper la memoria)
        _fsync_dir(os.path.dirname(self._path) or ".")  # el rename, duradero

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
            lineas, tolerados = _lineas_legibles(contenido)
            for posicion, fragmento in tolerados:
                obs.log(
                    "WARN",
                    "memory",
                    "linea truncada tolerada (no ambigua: no puede ser lapida ni marca)",
                    "-",
                    audit=True,
                    evento="memoria.linea_truncada_tolerada",
                    linea=posicion,
                    bytes=len(fragmento.encode("utf-8")),  # sin contenido ni huella: un hash corto es reversible
                )
            self._items = _proyectar(lineas)
        self._reconstruir_indice()

    # --- backups y recuperacion (3-2-1, prioridad M1) ---
    def backup(self) -> str:
        """Crea una copia de respaldo con checksum en el manifiesto. Devuelve el nombre del backup."""
        self._persist()
        digest = _sha256_file(self._path)
        name = f"memoria-{digest[:12]}.json"
        dst = os.path.join(self._bdir, name)
        with open(self._path, encoding="utf-8") as src, open(dst, "w", encoding="utf-8", opener=_abrir_privado) as out:
            out.write(src.read())
        # manifiesto append-only con integridad
        with open(os.path.join(self._bdir, "manifest.jsonl"), "a", encoding="utf-8", opener=_abrir_privado) as mf:
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
            else [json.loads(x) for x in contenido.split("\n") if x.strip()]  # solo '\n' separa (P2-B)
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
