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

    def __init__(self, memoria, motor=None) -> None:
        self._memoria = memoria
        # F4 tramo 3 · el motor unico. §4.2 lo señalaba como hueco: «la captura de señales escribe
        # conocimiento sobre el usuario sin correspondencia alguna». Sin motor NO se guarda nada.
        self._motor = motor

    async def guardar(self, user_id: str, senales: list[Senal]) -> int:
        """MIGRADA en F4: cada señal entra por `registrar_informacion_usuario`, que ya esta
        catalogada y declara `sujeto`. Devuelve cuantas se guardaron REALMENTE — con el kill switch
        armado son cero, y decir otra cosa seria narrar un efecto que no ocurrio (INV-9).
        """
        if self._motor is None:
            return 0
        guardadas = 0
        for s in senales:
            r = await self._motor.ejecutar(
                "registrar_informacion_usuario",
                {
                    "user_id": user_id,
                    "contenido": s.contenido,
                    "tipo": tipo_de_memoria(s.clase),
                    "procedencia": {
                        "trace_id": s.trace_id,
                        "fuente": s.fuente,
                        "clase": s.clase.value,
                        "origen": "declarada" if s.declarada else "observada",
                        "ts": s.ts,
                    },
                },
                s.trace_id or "-", f"senal-{s.clase.value}", origen="captura-de-senales",
            )
            if r.get("estado") == "ejecutada":
                guardadas += 1
        return guardadas
