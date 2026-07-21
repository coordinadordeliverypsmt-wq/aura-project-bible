"""Persistencia de senales como memoria semantica y procedimental (M3.0, Bible 4.1 §1 / 4.4 §2).

Hasta M2 el sistema escribia un unico tipo de memoria, `episodica` ("usuario dijo: X"). La taxonomia
de 4.1 §1 define tres y las otras dos no existian, que es la raiz de la deuda documentada en
`milestones/m3-entry/DEUDA-CAPTURA-DE-SENALES.md`.

El reparto sigue el sentido de 4.1 §1:
  - **semantica**: lo que AURA sabe SOBRE el usuario (preferencias, correcciones, temas).
  - **procedimental**: como el usuario hace las cosas (patrones de uso, respuestas a sugerencias).

Toda senal se escribe con **procedencia** (4.4 §2): trace_id, fuente, clase y origen epistemico. El
campo `origen` distingue `declarada` de `inferida`; en M3.0 siempre es `declarada` u observada,
porque la captura no infiere. Se registra desde el primer dia igualmente: cuando M3.2 empiece a
inferir, el historial ya distinguira ambas cosas sin necesidad de migrarlo.
"""

from __future__ import annotations

from .senales import ClaseSenal, Senal

_PROCEDIMENTALES = {ClaseSenal.PATRON_DE_USO, ClaseSenal.RESPUESTA_A_SUGERENCIA}


def tipo_de_memoria(clase: ClaseSenal) -> str:
    return "procedimental" if clase in _PROCEDIMENTALES else "semantica"


class AlmacenSenales:
    """Escribe senales en el MemoryStore. No lee, no infiere, no decide (restricciones 1 y 2)."""

    def __init__(self, memoria) -> None:
        self._memoria = memoria

    async def guardar(self, user_id: str, senales: list[Senal]) -> int:
        for s in senales:
            await self._memoria.write(
                user_id,
                tipo_de_memoria(s.clase),
                s.contenido,
                {
                    "trace_id": s.trace_id,
                    "fuente": s.fuente,
                    "clase": s.clase.value,
                    "origen": "declarada" if s.declarada else "observada",
                    "ts": s.ts,
                },
            )
        return len(senales)
