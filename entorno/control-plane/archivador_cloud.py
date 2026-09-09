"""`DR-CLOUD-1` — el archivador: AURA **copia** al archivo Cloud, y nada más.

Esto no es memoria cognitiva: es preservación. Y por eso el contrato es casi todo prohibiciones. Un
archivador con permiso para mover o borrar no es un archivador: es un riesgo con buena intención.

## Las tres barreras

**Categorías en lista blanca.** Siete carpetas y ni una más. Una categoría inventada no crea destino:
lo rechaza. Sin esto, `archivar(...)` sería una escritura arbitraria en Drive con otro nombre.

**Contenido en lista negra.** `.git`, `estado.json`, `eventos.jsonl`, credenciales, caches y modelos
**no se archivan aunque se pidan**. El runtime vivo se queda en local: archivar `estado.json` seria
congelar algo que cambia solo, y archivar un `.env` seria sacar un secreto de la maquina.

**Solo copia, por construccion.** El modulo no importa `os`, `shutil` ni `subprocess`: no tiene con
que borrar ni con que mover, aunque alguien se lo pidiera. Una prueba lo comprueba sobre el arbol
sintactico, no sobre la buena fe.

## Fail-closed, literal

Si el destino no esta disponible —Drive no montado, montaje caido— **no pasa nada**: se registra el
fallo y el original **no se toca**. La ausencia de destino nunca puede convertirse en una
modificacion del origen.

## Idempotencia sin destruir

Un fichero ya archivado con el mismo contenido no se vuelve a copiar: se registra `ya_archivado`. Si
el contenido cambio, **la copia anterior no se sobrescribe**: se guarda una version nueva con el hash
en el nombre. Preservar es no perder lo anterior, incluso cuando llega algo mejor.

## Lo que no hace

No habla con la red: Drive llega por GVFS, que es una ruta del sistema de ficheros, asi que `A8 · §16`
sigue valiendo tal cual esta escrita. No esta cableado al ciclo autonomo. No amplia `AUTO`, no crea
acciones delegables y no toca autoridad. Drive es **archivo**, nunca runtime.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib

#: El destino, y solo este. Coincide con la estructura ya creada en `Mi unidad/AURA_CLOUD`.
CATEGORIAS = ("01_CHECKPOINTS", "02_DECISIONES", "03_QUALITY_GATES", "04_MEDICIONES",
              "05_AUDITORIAS", "06_BACKUPS", "99_ARCHIVO")

#: El montaje GVFS ya existente. Se puede sustituir en la llamada; no hay credenciales de por medio.
DESTINO_POR_DEFECTO = pathlib.Path(
    "/run/user/1000/gvfs/google-drive:host=gmail.com,user=auraproyecto05"
    "/0AN1yvmu9fPQUUk9PVA/AURA_CLOUD")

#: Resultados posibles por fichero. Cerrados a proposito: no hay «se hizo algo raro».
COPIADO, YA_ARCHIVADO, VERSIONADO, RECHAZADO, ERROR = (
    "copiado", "ya_archivado", "versionado", "rechazado", "error")

#: Directorios que jamas se archivan, esten donde esten en la ruta.
_DIRS_PROHIBIDOS = frozenset({
    ".git", "__pycache__", ".pytest_cache", ".ollama", "node_modules", ".cache",
    ".venv", "venv", ".mypy_cache", ".ruff_cache", "worktrees", ".claude",
})

#: Ficheros de runtime vivo o de secreto. El nombre exacto basta para rechazar.
_FICHEROS_PROHIBIDOS = frozenset({
    "estado.json", "eventos.jsonl", ".env", ".env.local", "credentials.json",
    "token.json", "id_rsa", "id_ed25519", ".netrc", ".pgpass", "secrets.json",
})

#: Sufijos que no son artefactos de archivo: binarios de modelo, bases activas, temporales.
_SUFIJOS_PROHIBIDOS = (".pyc", ".pyo", ".so", ".db", ".sqlite", ".sqlite3", ".sock",
                       ".gguf", ".bin", ".pem", ".key", ".swp", ".tmp", ".lock")

#: Fragmentos que delatan un secreto en el propio nombre.
_NOMBRES_SOSPECHOSOS = ("secret", "password", "passwd", "token", "credential", "apikey",
                        "api_key", "private")

_TROZO = 1 << 16


def _ahora() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _hash(ruta: pathlib.Path) -> str:
    """SHA-256 leido a trozos: un artefacto grande no tiene por que caber en memoria."""
    resumen = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(_TROZO), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _motivo_de_rechazo(origen: pathlib.Path, raiz: pathlib.Path) -> str | None:
    """Por que **no** se archiva. `None` significa que puede archivarse.

    Se comprueba sobre la ruta ya resuelta: un enlace que apunte fuera de la raiz, o dentro de `.git`,
    no cuela por escribir el camino de otra forma."""
    try:
        real = origen.resolve()
        base = raiz.resolve()
    except OSError:
        return "ruta ilegible"
    if not real.is_relative_to(base):
        return "fuera de la raiz declarada"
    if not real.is_file():
        return "no es un fichero regular"
    #: **Relativo a la raiz**, no sobre la ruta absoluta. Lo destapo la primera prueba real: este
    #: repositorio vive bajo `.claude/worktrees/`, asi que mirar la ruta completa bloqueaba el arbol
    #: entero. Lo que hay por encima de la raiz declarada no es asunto del archivador; dentro, si.
    partes = {p.lower() for p in real.relative_to(base).parts}
    if partes & _DIRS_PROHIBIDOS:
        return "dentro de un directorio prohibido (runtime, cache o control de versiones)"
    nombre = real.name.lower()
    if nombre in _FICHEROS_PROHIBIDOS:
        return "fichero de runtime vivo o de credenciales"
    if nombre.endswith(_SUFIJOS_PROHIBIDOS):
        return "extension no archivable (binario, base activa o temporal)"
    if any(s in nombre for s in _NOMBRES_SOSPECHOSOS):
        return "el nombre sugiere material sensible"
    return None


def _nombre_versionado(nombre: str, resumen: str) -> str:
    """`informe.md` -> `informe.a1b2c3d4.md`. La copia anterior se queda donde esta."""
    punto = nombre.rfind(".")
    if punto <= 0:
        return f"{nombre}.{resumen[:8]}"
    return f"{nombre[:punto]}.{resumen[:8]}{nombre[punto:]}"


def _copiar(origen: pathlib.Path, destino: pathlib.Path) -> int:
    """Copia por lectura y escritura explicitas. **No se importa `shutil`**: este modulo no debe
    tener a mano ninguna funcion capaz de mover o de borrar."""
    copiados = 0
    with origen.open("rb") as entrada, destino.open("wb") as salida:
        for bloque in iter(lambda: entrada.read(_TROZO), b""):
            salida.write(bloque)
            copiados += len(bloque)
    return copiados


def archivar(raiz, categoria: str, ficheros, *, destino=None) -> dict:
    """Copia `ficheros` a `<destino>/<categoria>`. Devuelve el registro de lo ocurrido.

    Nunca mueve, nunca borra, nunca modifica el origen. Ante cualquier duda —categoria desconocida,
    destino ausente, fichero de la lista negra— no archiva y lo dice."""
    raiz = pathlib.Path(raiz)
    registro = {"instante": _ahora(), "categoria": categoria, "destino": None, "ok": False,
                "copiados": 0, "bytes": 0, "ficheros": [], "errores": []}

    if categoria not in CATEGORIAS:
        registro["errores"].append(
            f"categoria {categoria!r} fuera de la lista blanca {CATEGORIAS}")
        return registro

    base = pathlib.Path(destino) if destino is not None else DESTINO_POR_DEFECTO
    if not base.is_dir():
        registro["errores"].append(
            f"destino no disponible: {base} — no se archiva y el origen queda intacto")
        return registro

    carpeta = base / categoria
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        registro["errores"].append(f"destino no escribible: {type(exc).__name__}")
        return registro

    registro["destino"] = str(carpeta)
    for entrada in ficheros:
        origen = pathlib.Path(entrada)
        anotacion = {"origen": str(origen), "destino": None, "resultado": RECHAZADO,
                     "bytes": 0, "hash": None, "hash_destino": None, "verificado": False,
                     "motivo": None}
        motivo = _motivo_de_rechazo(origen, raiz)
        if motivo is not None:
            anotacion["motivo"] = motivo
            registro["ficheros"].append(anotacion)
            continue
        try:
            resumen = _hash(origen)
            anotacion["hash"] = resumen
            candidato = carpeta / origen.name
            if candidato.is_file() and _hash(candidato) == resumen:
                #: Comprobar la igualdad **es** releer el destino: la verificacion ya ocurrio.
                anotacion.update(resultado=YA_ARCHIVADO, destino=str(candidato),
                                 bytes=candidato.stat().st_size, hash_destino=resumen,
                                 verificado=True)
            else:
                if candidato.is_file():
                    candidato = carpeta / _nombre_versionado(origen.name, resumen)
                    previsto = VERSIONADO
                else:
                    previsto = COPIADO
                escritos = _copiar(origen, candidato)
                #: **La copia se demuestra, no se supone.** Drive por GVFS no es transaccional: una
                #: escritura truncada o corrupta terminaria sin error y quedaria registrada como
                #: exito. Se relee lo que de verdad quedo en el destino y se compara con el origen.
                anotacion["destino"] = str(candidato)
                escrito = _hash(candidato) if candidato.is_file() else None
                anotacion["hash_destino"] = escrito
                if escrito != resumen:
                    #: Fail-closed. No se borra el destino defectuoso —seria destruir la evidencia de
                    #: lo ocurrido— y no se toca el origen, que es lo que un archivador nunca hace.
                    anotacion.update(resultado=ERROR, verificado=False,
                                     motivo="verificacion fallida: el destino no coincide")
                    registro["errores"].append(
                        f"{origen.name}: discrepancia en la verificacion del destino")
                else:
                    anotacion.update(resultado=previsto, bytes=escritos, verificado=True)
                    registro["copiados"] += 1
                    registro["bytes"] += escritos
        except OSError as exc:
            anotacion.update(resultado=ERROR, motivo=f"{type(exc).__name__}")
            registro["errores"].append(f"{origen.name}: {type(exc).__name__}")
        registro["ficheros"].append(anotacion)

    registro["ok"] = not registro["errores"]
    return registro


def como_jsonl(registro: dict) -> str:
    """El registro en una linea, para quien quiera conservarlo. **No se escribe en el log del
    ciclo**: archivar no es un hecho del ciclo autonomo, y mezclarlo alli seria inventar un contrato
    que nadie ha aprobado."""
    return json.dumps(registro, ensure_ascii=False, sort_keys=True)


__all__ = ["archivar", "como_jsonl", "CATEGORIAS", "DESTINO_POR_DEFECTO",
           "COPIADO", "YA_ARCHIVADO", "VERSIONADO", "RECHAZADO", "ERROR"]
