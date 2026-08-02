"""Gestión de artefactos de IA (ADR-0022) — manifiesto declarativo + ModelResolver.

Los binarios de modelos viven en el ENTORNO, no en el código (ADR-0022, D24). El código depende de un
**contrato**, no de un binario concreto: cada artefacto se describe con un `manifiesto.json` situado junto
a él, y un `ModelResolver` de una sola responsabilidad lo localiza, verifica su integridad (SHA-256) y su
formato, y entrega la ruta válida al consumidor.

**Alcance (ADR-0022, estrictamente).** Manifiesto mínimo (`id`, `version` SemVer, `checksum` SHA-256,
`licencia`, `source`, `contrato`: formato + dims) + resolución (localizar, verificar integridad, comprobar
formato, entregar ruta). Fuera de alcance por decisión normativa: cachés multinivel, descarga inteligente,
múltiples proveedores, descubrimiento dinámico, registro distribuido, dependencias complejas.

**`source` (CEO, 2026-08-02):** integridad y recuperación son garantías distintas. El checksum dice *"este
binario es el que declaro"*; `source` dice *"y si se pierde, se repone desde aquí"*. Sigue siendo un dato
declarativo del entorno: este módulo **no descarga nada** — eso queda fuera de alcance por ADR-0022.

**Principio protegido (ADR-0022 / ADR-0016 / INV-6):** las capacidades nunca nombran un modelo; declaran el
contrato; la infraestructura (este módulo) decide qué artefacto lo satisface.

**Cambio de modelo sin tocar código:** el manifiesto es un dato del entorno; apuntar a otro directorio con
su propio manifiesto sustituye el modelo sin editar una línea.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

# Formato -> ficheros que el artefacto debe contener; el PRIMERO es el fichero principal (el del checksum).
_FORMATOS: dict[str, tuple[str, ...]] = {
    "onnx+tokenizer": ("model.onnx", "tokenizer.json"),
}

_MANIFIESTO = "manifiesto.json"


class ArtefactoNoResuelto(Exception):
    """El artefacto no se pudo resolver: ausente, manifiesto invalido, formato desconocido o integridad rota."""


@dataclass(frozen=True)
class ManifiestoArtefacto:
    """Descripcion declarativa minima de un artefacto de IA (ADR-0022). Datos puros; vive en el entorno."""

    id: str
    version: str  # SemVer
    checksum: str  # SHA-256 hex del fichero principal
    licencia: str
    formato: str
    dims: int  # contrato tecnico: dimension de salida esperada
    # Procedencia del artefacto (CEO, 2026-08-02). El checksum garantiza INTEGRIDAD —"es el que digo"—
    # pero no RECUPERACION: un artefacto perdido se puede verificar y no reponer. Lo detecto la revision
    # estrategica al evaluar el riesgo del modelo de N2, cuyo manifiesto no permitia saber de donde salio.
    # Es obligatorio: un campo opcional que casi nadie rellena no da trazabilidad, solo la aparenta.
    source: str


def cargar_manifiesto(directorio: str) -> ManifiestoArtefacto:
    """Lee `<directorio>/manifiesto.json`. Lanza `ArtefactoNoResuelto` si falta o esta mal formado."""
    ruta = os.path.join(os.path.expanduser(directorio), _MANIFIESTO)
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return ManifiestoArtefacto(
            id=datos["id"],
            version=datos["version"],
            checksum=datos["checksum"],
            licencia=datos["licencia"],
            formato=datos["formato"],
            dims=int(datos["dims"]),
            source=datos["source"],
        )
    except (OSError, ValueError, KeyError) as e:
        raise ArtefactoNoResuelto(f"manifiesto invalido o ausente en {directorio}: {e}") from e


def _sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


class ModelResolver:
    """Localiza un artefacto, verifica integridad y formato, y entrega la ruta valida. Una sola responsabilidad."""

    def resolver(self, directorio: str) -> str:
        """Devuelve la ruta del directorio del artefacto si es valido; lanza `ArtefactoNoResuelto` si no.

        Comprueba, en orden: (1) el manifiesto existe y es legible; (2) el formato es conocido; (3) los
        ficheros que el formato exige estan presentes (localizacion/compatibilidad de formato); (4) el
        SHA-256 del fichero principal coincide con el manifiesto (integridad). No carga el modelo.
        """
        base = os.path.expanduser(directorio)
        manifiesto = cargar_manifiesto(base)  # (1)

        ficheros = _FORMATOS.get(manifiesto.formato)  # (2)
        if ficheros is None:
            raise ArtefactoNoResuelto(f"formato desconocido: {manifiesto.formato!r}")

        for nombre in ficheros:  # (3)
            if not os.path.isfile(os.path.join(base, nombre)):
                raise ArtefactoNoResuelto(f"falta el fichero {nombre!r} exigido por el formato {manifiesto.formato!r}")

        principal = os.path.join(base, ficheros[0])  # (4)
        real = _sha256(principal)
        if real != manifiesto.checksum:
            raise ArtefactoNoResuelto(
                f"integridad: SHA-256 de {ficheros[0]!r} no coincide con el manifiesto "
                f"(esperado {manifiesto.checksum[:12]}..., real {real[:12]}...)"
            )
        return base
