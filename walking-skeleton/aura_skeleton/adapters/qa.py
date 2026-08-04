"""Ejecutor QA: el primer ejecutor especializado del Sistema Operativo Interno.

PRINCIPIO PERMANENTE QUE ENCARNA (CEO, 2026-08-03):
**AURORA nunca ejecuta instrucciones arbitrarias del sistema operativo; ejecuta CAPACIDADES
registradas, gobernadas por el Motor Unico y auditadas.**

La diferencia no es tecnologica —ambas cosas acaban en un proceso— sino de **quien decide el comando**:

  ejecutar_comando(cmd)   -> el comando VIENE DE FUERA. Es una puerta al shell.
  ejecutar_pruebas()      -> el comando es una CONSTANTE de este modulo. `args` no participa en
                             construirlo, asi que ningun llamador —ni el Director, ni una regla, ni
                             el LLM— puede influir en que se ejecuta.

Por eso aqui NO hay un adaptador de shell generico y no puede haberlo: la superficie ejecutable es
cerrada y esta escrita en `_COMANDOS`.

LAS CAPACIDADES SE NOMBRAN POR EL RESULTADO QUE OFRECEN, NUNCA POR LA HERRAMIENTA (CEO, 2026-08-03):
`ejecutar_pruebas`, no `ejecutar_pytest`. Si mañana se sustituye pytest por otra cosa, el Director no
cambia una sola linea, porque nunca supo que habia detras.

FUERA DE ALCANCE POR DECISION DEL CEO: `ejecutar_mutacion`. Altera deliberadamente el arbol de trabajo
y, si el proceso muere, lo deja mutado (documentado en CLAUDE.md). Ante la duda, roja: se evaluara como
incremento independiente cuando este ejecutor ya funcione.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .. import observability as obs

# UNICA superficie ejecutable. Ampliarla exige tocar este fichero, revisarlo y clasificar la capacidad
# nueva en el catalogo de permisos: no se puede ampliar desde fuera ni en tiempo de ejecucion.
_COMANDOS: dict[str, tuple[str, ...]] = {
    "ejecutar_pruebas": ("python3", "-m", "pytest", "-q", "--no-header"),
    "verificar_calidad": ("bash", "./quality-gate.sh"),
}

_TIMEOUT_S = 900  # una verificacion que no termina es un fallo, no una espera indefinida


class EjecutorQA:
    """Adaptador de dominio (contrato `Adapter`) que ofrece capacidades de verificacion.

    Cumple el contrato como cualquier otro adaptador, de modo que el Motor Unico lo gobierna igual:
    permisos, kill switch y auditoria. El Director solo sabe que existe un responsable "qa" con
    capacidades disponibles; ignora por completo como se implementan.
    """

    name = "qa"
    capabilities = sorted(_COMANDOS)

    def __init__(self, raiz: str) -> None:
        # La raiz se fija al construir, NO llega por `args`: un llamador no puede redirigir la
        # verificacion a otro arbol de trabajo.
        self._raiz = Path(raiz)

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        """Ejecuta la capacidad y devuelve un resultado ESTRUCTURADO, no texto libre."""
        cmd = _COMANDOS.get(command)
        if cmd is None:
            # Capacidad no declarada: no se intenta nada. Es la misma regla que RN-2 aplica al catalogo.
            raise ValueError(f"capacidad no ofrecida por el ejecutor QA: {command!r}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(self._raiz), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        try:
            salida, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT_S)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            obs.log("QA", "ejecutor-qa", f"{command}: TIMEOUT tras {_TIMEOUT_S}s", trace_id, audit=True)
            return {"capacidad": command, "ok": False, "codigo_salida": None, "resumen": "tiempo agotado"}

        texto = salida.decode("utf-8", errors="replace")
        ok = proc.returncode == 0
        obs.log(
            "QA", "ejecutor-qa", f"{command}: {'OK' if ok else 'FALLO'} (rc={proc.returncode})", trace_id, audit=True
        )
        return {
            "capacidad": command,
            "ok": ok,
            "codigo_salida": proc.returncode,
            "resumen": _resumen(texto),
        }


def _resumen(texto: str) -> str:
    """Ultimas lineas utiles. El resultado ha de ser accionable sin arrastrar miles de lineas al estado."""
    lineas = [x.strip() for x in texto.splitlines() if x.strip()]
    return " | ".join(lineas[-3:]) if lineas else "(sin salida)"
