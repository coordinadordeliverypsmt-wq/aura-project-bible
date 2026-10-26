"""Detector de hardware REAL (ADR-0021, ADR-0020): mide el equipo, no lo supone.

POR QUE EXISTE. Hasta ahora el unico `DetectorHardware` era `_PerfilInyectado`, que devuelve el perfil de
`Configuracion` -- VACIO por defecto. El Capability Manager decidia la memoria con `ram_mb = 0` en cualquier
equipo. [EJEC] `--verificar` en HC-1 imprimia `degradadas=['memoria'] ... memoria -> N1`: correcto por
casualidad (3,6 GB < 8 GB), pero un equipo de 16 GB habria dicho lo mismo, y AURA no habria podido ampliar su
alcance teniendo capacidad. Es el patron «declarado != real». ADR-0020 exige seleccionar por capacidad
EFECTIVA sobre hardware VERIFICADO en el momento (D27), y bidireccional (tambien hacia arriba).

QUE MIDE (solo `recursos`, todo float; solo metricas, nunca marcas ni modelos):
`ram_mb`, `ram_disponible_mb` (/proc/meminfo), `nucleos`, `carga_1m`, `disco_libre_mb` (de `ruta_datos`),
`isa_sse4_2/ssse3/avx/avx2/fma/avx512f` (1.0/0.0, tokens EXACTOS de la linea `flags` de /proc/cpuinfo: «avx» no
casa con «avx2»; se declara una ISA solo si TODAS las lineas `flags` -una por CPU- la tienen) y `gpu_render`
(entradas `renderD*` en /dev/dri; sin el directorio es 0.0: medicion verdadera, ningun nodo render, no una
invencion). `disco_libre_mb` son MiB (1024*1024 bytes), no MB decimales como en `computador.py`.

MÉTRICAS DE PRESENCIA (DP-NODO-01 §4.4): `cpu_64bit` (flag `lm` en todas las lineas flags), `proceso_bits`
(bits del intérprete), `nucleos_fisicos` (pares distintos physical id/core id de /proc/cpuinfo; sin esas
líneas se omite), `video_dispositivos` (`video*` en /dev), `audio_tarjetas` (/proc/asound/cards; fichero
ausente se omite, sin tarjetas es 0.0) y `red_interfaces` (/sys/class/net sin `lo`). Son nivel HARDWARE /
INTERFAZ PRESENTE: NO son capacidades habilitadas ni demostradas. `gpu_render > 0` solo dice que hay un nodo
DRM; NO implica aceleración de IA. Las capacidades las decide solo el Capability Manager.
`detectar_con_omisiones()` devuelve además los nombres de las fuentes omitidas; `detectar()` delega en el.

HONESTIDAD (INV-9): cada metrica se obtiene de forma INDEPENDIENTE; si su fuente falla se OMITE del perfil:
no se inventa un valor. Cada omision deja un WARN (`detector-hardware`: solo fuente y tipo de error, sin
datos) y el BOOT auditado lista lo que si se midio. OJO: `PerfilHardware.valor(..., defecto=0.0)` hace que las
reglas del Manager lean una metrica omitida como 0 (lo conservador); el perfil distingue «omitida» de «0»,
la regla no. `pruebas` queda vacio: las pruebas de rendimiento
(D44) son trabajo posterior. HC-1 NO se hardcodea: los valores salen de la maquina donde corre. Sin
subprocess, sin red; solo lee /proc, /dev/dri y el uso de disco. Es un adaptador porque hace E/S; el Core
sigue puro.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import observability as obs
from ..core.capacidades import PerfilHardware

_KB_POR_MB = 1024
_BITS_POR_BYTE = 8
_TARJETA_ALSA = re.compile(r"^\s*\d+\s+\[")
_BYTES_POR_MB = 1024 * 1024
# metrica -> flag exacto de /proc/cpuinfo
_ISA = {
    "isa_sse4_2": "sse4_2",
    "isa_ssse3": "ssse3",
    "isa_avx": "avx",
    "isa_avx2": "avx2",
    "isa_fma": "fma",
    "isa_avx512f": "avx512f",
}


class DetectorHardwareLocal:
    """`DetectorHardware` que mide el equipo local. Todo lo externo es inyectable para las pruebas."""

    def __init__(
        self,
        ruta_datos: str,
        raiz_proc: str = "/proc",
        raiz_dev_dri: str = "/dev/dri",
        nucleos: Callable[[], int | None] = os.cpu_count,
        carga: Callable[[], tuple[float, float, float]] = os.getloadavg,
        disco: Callable[[str], Any] = shutil.disk_usage,
        raiz_dev: str = "/dev",
        raiz_sys_net: str = "/sys/class/net",
        bits_proceso: Callable[[], int] = lambda: struct.calcsize("P") * _BITS_POR_BYTE,
    ) -> None:
        self._ruta_datos = ruta_datos
        self._proc = Path(raiz_proc)
        self._dri = Path(raiz_dev_dri)
        self._nucleos = nucleos
        self._carga = carga
        self._disco = disco
        self._dev = Path(raiz_dev)
        self._sys_net = Path(raiz_sys_net)
        self._bits_proceso = bits_proceso

    def detectar(self) -> PerfilHardware:
        return self.detectar_con_omisiones()[0]

    def detectar_con_omisiones(self) -> tuple[PerfilHardware, tuple[str, ...]]:
        """Perfil medido + NOMBRES de las fuentes que fallaron (para que el nodo las reporte como `omitidas`)."""
        recursos: dict[str, float] = {}
        omitidas: list[str] = []
        for nombre, fuente in self._fuentes():
            try:
                recursos.update(fuente())
            except Exception as e:  # noqa: BLE001 - una fuente rota omite SUS metricas, no las demas
                omitidas.append(nombre)
                obs.log("WARN", "detector-hardware", f"no se pudo medir {nombre}: {type(e).__name__}", "-")
        return PerfilHardware(recursos=recursos), tuple(omitidas)

    def _fuentes(self) -> tuple[tuple[str, Callable[[], dict[str, float]]], ...]:
        return (
            ("ram_mb", lambda: self._meminfo("MemTotal:", "ram_mb")),
            ("ram_disponible_mb", lambda: self._meminfo("MemAvailable:", "ram_disponible_mb")),
            ("nucleos", self._nucleos_medidos),
            ("isa", self._isa),
            ("cpu_64bit", self._cpu_64bit),
            ("proceso_bits", self._proceso_bits),
            ("nucleos_fisicos", self._nucleos_fisicos),
            ("carga_1m", self._carga_1m),
            ("disco_libre_mb", self._disco_libre),
            ("gpu_render", self._gpu),
            ("video_dispositivos", self._video),
            ("audio_tarjetas", self._audio),
            ("red_interfaces", self._red),
        )

    def _meminfo(self, clave: str, metrica: str) -> dict[str, float]:
        """Lanza si el fichero falta o el campo no existe/es ilegible: `detectar` lo omite con WARN."""
        for linea in (self._proc / "meminfo").read_text().splitlines():
            if linea.startswith(clave):
                return {metrica: float(int(linea.split()[1]) // _KB_POR_MB)}
        raise ValueError(f"campo {clave} ausente")

    def _nucleos_medidos(self) -> dict[str, float]:
        n = self._nucleos()
        if not n:
            raise ValueError("nucleos sin valor")
        return {"nucleos": float(n)}

    def _flags_comunes(self) -> set[str]:
        """Interseccion de todas las lineas `flags`: no se declara avx2 si algun nucleo no lo tiene."""
        conjuntos = [
            set(valor.split())
            for linea in (self._proc / "cpuinfo").read_text().splitlines()
            for clave, sep, valor in [linea.partition(":")]
            if sep and clave.strip() == "flags"
        ]
        if not conjuntos:
            raise ValueError("cpuinfo sin linea flags")
        return set.intersection(*conjuntos)

    def _isa(self) -> dict[str, float]:
        comunes = self._flags_comunes()
        return {metrica: 1.0 if flag in comunes else 0.0 for metrica, flag in _ISA.items()}

    def _cpu_64bit(self) -> dict[str, float]:
        """Flag `lm` (long mode) en TODOS los núcleos: la CPU puede ejecutar 64 bits (no que el SO lo haga)."""
        return {"cpu_64bit": 1.0 if "lm" in self._flags_comunes() else 0.0}

    def _proceso_bits(self) -> dict[str, float]:
        return {"proceso_bits": float(self._bits_proceso())}

    def _nucleos_fisicos(self) -> dict[str, float]:
        """Pares distintos (physical id, core id). Sin esas líneas se omite: no se supone un valor."""
        pares: set[tuple[str, str]] = set()
        for bloque in (self._proc / "cpuinfo").read_text().split("\n\n"):
            campos = {
                clave.strip(): valor.strip()
                for clave, sep, valor in (linea.partition(":") for linea in bloque.splitlines())
                if sep
            }
            if "physical id" in campos and "core id" in campos:
                pares.add((campos["physical id"], campos["core id"]))
        if not pares:
            raise ValueError("cpuinfo sin physical id/core id")
        return {"nucleos_fisicos": float(len(pares))}

    def _carga_1m(self) -> dict[str, float]:
        return {"carga_1m": float(self._carga()[0])}

    def _disco_libre(self) -> dict[str, float]:
        ruta = Path(self._ruta_datos)
        while not ruta.exists() and ruta != ruta.parent:
            ruta = ruta.parent
        return {"disco_libre_mb": float(int(self._disco(str(ruta)).free) // _BYTES_POR_MB)}

    def _gpu(self) -> dict[str, float]:
        if not self._dri.is_dir():
            return {"gpu_render": 0.0}
        return {"gpu_render": float(sum(1 for e in self._dri.iterdir() if e.name.startswith("renderD")))}

    def _video(self) -> dict[str, float]:
        """Entradas `video*` en /dev (presencia de dispositivo; no prueba que capture imagen)."""
        return {"video_dispositivos": float(sum(1 for e in self._dev.iterdir() if e.name.startswith("video")))}

    def _audio(self) -> dict[str, float]:
        """Tarjetas de /proc/asound/cards. Fichero ausente: se omite; presente sin tarjetas: 0.0."""
        lineas = (self._proc / "asound" / "cards").read_text().splitlines()
        return {"audio_tarjetas": float(sum(1 for linea in lineas if _TARJETA_ALSA.match(linea)))}

    def _red(self) -> dict[str, float]:
        """Interfaces de red presentes salvo `lo` (presencia; no prueba conectividad)."""
        return {"red_interfaces": float(sum(1 for e in self._sys_net.iterdir() if e.name != "lo"))}
