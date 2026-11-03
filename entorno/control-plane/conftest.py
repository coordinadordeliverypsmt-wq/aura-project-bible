"""Blindaje del estado de produccion — **meta-control permanente** (CEO, 2026-08-26).

El 2026-08-26 una prueba de F1 recorrio las funciones publicas del Control Plane y llamo a
`guardar()` sin destino. El valor por defecto de ese parametro es el `estado.json` **real**, asi que
la prueba lo sobrescribio y destruyo informacion historica que solo pudo restaurarse en parte.

Orden del CEO: *«Agregar un meta-control permanente que impida que una prueba de auditoria escriba
accidentalmente sobre estado.json REAL. La prueba debe fallar si detecta que su destino coincide con
el estado de produccion.»*

**Dos capas, porque una sola no basta:**

1. **Intercepcion** — `guardar()` consulta un centinela antes de escribir. Falla **en el acto**, en
   la prueba culpable y en su linea, no tres pruebas mas tarde. Un fallo tardio ya se demostro
   inutil: el incidente no salio a la luz hasta la regresion general.
2. **Huella** — se compara el `sha256` del fichero antes y despues de **cada** prueba. Cubre lo que
   la intercepcion no ve: un `open()` directo, un `shutil.copy`, un subproceso.

Es `autouse`: una proteccion que hay que acordarse de pedir no protege de un descuido, y esto **fue**
un descuido.
"""

from __future__ import annotations

import hashlib

import control_plane as cp
import pytest


# Fijada **al cargar el conftest**, no leida de `cp.ESTADO_POR_DEFECTO` en cada comprobacion. Una
# prueba que reasigna esa global para «aislarse» movia con ella el objetivo del centinela, asi que el
# centinela dejaba de vigilar justo el fichero que debe proteger. Lo encontro la 3.a auditoria.
RUTA_PRODUCCION = cp.ESTADO_POR_DEFECTO


def _huella() -> str | None:
    return hashlib.sha256(RUTA_PRODUCCION.read_bytes()).hexdigest() if RUTA_PRODUCCION.exists() else None


@pytest.fixture(autouse=True)
def blindar_el_estado_de_produccion(request):
    """Ninguna prueba escribe el estado real. Ninguna. Leerlo si: hay pruebas de regresion del CEO
    que lo leen a proposito."""

    def centinela(destino):
        try:
            mismo = destino.resolve() == RUTA_PRODUCCION.resolve()
        except OSError:
            mismo = str(destino) == str(RUTA_PRODUCCION)
        if mismo:
            raise cp.EscrituraDeProduccionProhibida(
                f"la prueba {request.node.name!r} intento escribir el estado de produccion "
                f"({RUTA_PRODUCCION}). Usa `tmp_path`: el estado real no es un fixture.")

    antes = _huella()
    respaldo = RUTA_PRODUCCION.read_bytes() if RUTA_PRODUCCION.exists() else None
    cp.vigilar_escrituras(centinela)
    try:
        yield
    finally:
        cp.vigilar_escrituras(None)
    if _huella() != antes:
        # **Reparador, no solo detectivo.** Denunciar el cambio dejaba el fichero ya corrompido en
        # disco —fue exactamente lo que paso en el incidente—. Reponerlo hace que el dano no se
        # consolide aunque alguien desactive la intercepcion desde dentro de una prueba.
        if respaldo is not None:
            RUTA_PRODUCCION.write_bytes(respaldo)
        pytest.fail(f"la prueba {request.node.name!r} modifico el estado de produccion "
                    f"({RUTA_PRODUCCION}) por una via que la intercepcion no cubre. "
                    f"El fichero se ha RESTAURADO desde el respaldo previo a la prueba.")
