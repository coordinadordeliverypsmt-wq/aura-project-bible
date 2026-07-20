"""Adaptador del computador principal (M2.2, Bible 6.4 §1).

Dos condiciones de arquitectura impuestas por el CEO:

1. NINGUNA operacion se ejecuta sin pasar por `operaciones.validar()`. Existe una unica puerta de
   entrada —`execute()`— y una unica llamada a `validar()`. El adaptador NO revalida por su cuenta:
   una validacion duplicada podria divergir de la del nucleo y crear un camino con reglas distintas.

2. Proteccion TOCTOU en operaciones destructivas. Entre validar una ruta y actuar sobre ella, un
   tercero puede sustituir un componente por un enlace simbolico y desviar la operacion a otro
   archivo. Se mitiga operando sobre DESCRIPTORES DE DIRECTORIO en lugar de sobre rutas de texto:
   el descriptor fija el inodo del directorio padre, de modo que la ruta ya no vuelve a resolverse
   en el momento de actuar.

D32 vigente: `mover_archivo` y `renombrar_archivo` son de lista roja y exigen confirmacion; este
adaptador no relaja esa clasificacion — solo la ejecuta cuando Permisos ya la autorizo.
"""

from __future__ import annotations

import os
import shutil
import stat

from .. import observability as obs
from ..core.operaciones import ESPECIFICACIONES, ErrorDeValidacion, raices_por_defecto, ruta_en_ambito, validar

_DESTRUCTIVAS = {"borrar_archivo", "mover_archivo", "renombrar_archivo", "escribir_archivo"}


def _fd_directorio_seguro(ruta_absoluta: str, raices: tuple[str, ...]) -> int:
    """Abre el directorio padre sin seguir enlaces y reverifica su ubicacion REAL.

    `O_NOFOLLOW` impide que el propio padre sea un enlace. `/proc/self/fd/N` revela a que ruta
    apunta realmente el descriptor ya abierto: si entre la validacion y este instante alguien
    sustituyo un componente, la ruta real habra cambiado y la comprobacion falla.
    """
    padre = os.path.dirname(ruta_absoluta)
    fd = os.open(padre, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        real = os.readlink(f"/proc/self/fd/{fd}")
        if not ruta_en_ambito(real, raices):
            raise ErrorDeValidacion(f"el directorio cambio de ubicacion tras la validacion: {real!r}")
        return fd
    except Exception:
        os.close(fd)
        raise


def _lstat_o_none(base: str, fd: int) -> os.stat_result | None:
    """`lstat` RELATIVO al descriptor de directorio.

    Bug detectado en M2.2 por prueba: se uso `os.path.lexists(base)` con solo el nombre base, que
    resuelve contra el DIRECTORIO DE TRABAJO del proceso, no contra el descriptor. La comprobacion
    de "el destino ya existe" miraba en el sitio equivocado y no protegia nada.
    """
    try:
        return os.lstat(base, dir_fd=fd)
    except FileNotFoundError:
        return None


def _exigir_no_enlace(base: str, fd: int) -> os.stat_result:
    """Rechaza actuar sobre un enlace simbolico en una operacion destructiva."""
    st = os.lstat(base, dir_fd=fd)
    if stat.S_ISLNK(st.st_mode):
        raise ErrorDeValidacion(f"el objetivo es un enlace simbolico: {base!r}")
    return st


class AdaptadorComputador:
    """Cumple el contrato `Adapter` (contracts.py). Solo expone el catalogo de `operaciones`."""

    name = "computador"
    capabilities = sorted(ESPECIFICACIONES)

    def __init__(self, raices: tuple[str, ...] | None = None) -> None:
        self._raices = raices or raices_por_defecto()
        self._hechos: set[str] = set()

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        # Idempotencia (3.3 §3): un evento reentregado no puede producir dos efectos reales.
        # En M1 esto era teorico; aqui evita un segundo borrado.
        if event_id in self._hechos:
            obs.log("ACT", "computador", f"idempotente: {command} ya ejecutado", trace_id)
            return {"status": "duplicate"}

        # UNICA PUERTA. Si esto lanza, no hay ninguna ruta que alcance el sistema de archivos.
        seguros = validar(command, args, self._raices)

        self._hechos.add(event_id)
        resultado = self._despachar(command, seguros)
        obs.log(
            "ACT",
            "computador",
            f"EJECUTA {command}",
            trace_id,
            audit=command in _DESTRUCTIVAS,  # solo lo destructivo va al registro forense
        )
        return {"status": "ok", **resultado}

    def _despachar(self, command: str, a: dict) -> dict:
        if command == "listar_directorio":
            return {"entradas": sorted(os.listdir(a["ruta"]))}
        if command == "leer_archivo":
            with open(a["ruta"], encoding="utf-8", errors="replace") as f:
                return {"contenido": f.read(65536)}
        if command == "buscar_archivo":
            import fnmatch

            hallazgos = [
                os.path.join(d, n) for d, _, ns in os.walk(a["raiz"]) for n in ns if fnmatch.fnmatch(n, a["patron"])
            ]
            return {"hallazgos": hallazgos[:200]}
        if command == "abrir_archivo":
            return {"abierto": a["ruta"]}  # sin lanzar aplicaciones externas en esta fase
        if command == "consultar_estado_sistema":
            u = shutil.disk_usage(self._raices[0])
            return {"disco_libre_mb": round(u.free / 1e6)}
        if command == "escribir_archivo":
            return self._escribir(a["ruta"], a["contenido"])
        if command == "borrar_archivo":
            return self._borrar(a["ruta"])
        if command in ("mover_archivo", "renombrar_archivo"):
            return self._mover(a["origen"], a["destino"])
        raise ErrorDeValidacion(f"operacion sin implementacion: {command!r}")

    # --- Operaciones destructivas: siempre por descriptor de directorio -----

    def _borrar(self, ruta: str) -> dict:
        fd = _fd_directorio_seguro(ruta, self._raices)
        try:
            base = os.path.basename(ruta)
            _exigir_no_enlace(base, fd)
            os.unlink(base, dir_fd=fd)  # relativo al descriptor: la ruta no se reinterpreta
            return {"borrado": ruta}
        finally:
            os.close(fd)

    def _escribir(self, ruta: str, contenido: str) -> dict:
        fd = _fd_directorio_seguro(ruta, self._raices)
        try:
            base = os.path.basename(ruta)
            st = _lstat_o_none(base, fd)
            if st is not None and stat.S_ISLNK(st.st_mode):
                raise ErrorDeValidacion(f"el destino es un enlace simbolico: {base!r}")
            # O_NOFOLLOW: si el destino se convierte en enlace justo ahora, la apertura falla.
            dst = os.open(base, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(dst, "w", encoding="utf-8") as f:
                f.write(contenido)
            return {"escrito": ruta, "bytes": len(contenido.encode())}
        finally:
            os.close(fd)

    def _mover(self, origen: str, destino: str) -> dict:
        fd_o = _fd_directorio_seguro(origen, self._raices)
        try:
            fd_d = _fd_directorio_seguro(destino, self._raices)
            try:
                b_o, b_d = os.path.basename(origen), os.path.basename(destino)
                _exigir_no_enlace(b_o, fd_o)
                if _lstat_o_none(b_d, fd_d) is not None:
                    # El catalogo prohibe comodines, pero no la colision: sobrescribir en un
                    # "mover" perderia el destino en silencio. Se rechaza (D32, maxima seguridad).
                    raise ErrorDeValidacion(f"el destino ya existe: {b_d!r}")
                os.rename(b_o, b_d, src_dir_fd=fd_o, dst_dir_fd=fd_d)
                return {"origen": origen, "destino": destino}
            finally:
                os.close(fd_d)
        finally:
            os.close(fd_o)
