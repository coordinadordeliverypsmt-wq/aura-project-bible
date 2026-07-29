"""Soberania del modelo del usuario (M3.2a, ADR-0017 / Bible 4.4 §2, 4.1 §5, ADR-0001).

> *"El modelo del usuario es dato del usuario: local, cifrado, exportable."* — 4.4 §2

Cuatro capacidades, todas DETERMINISTAS: ver, corregir, exportar y borrar. Su correccion no depende
de que ninguna inferencia acierte, solo de que el mecanismo funcione — por eso se construyen **antes**
de que AURA infiera nada. En el orden inverso existiria una ventana, de duracion indefinida porque
depende del hardware, en la que el sistema acumula conclusiones sobre una persona que esa persona no
puede rectificar.

Regla central (ADR-0017 §2): **una correccion del usuario prevalece sobre cualquier inferencia, sin
ponderacion.** Un hecho declarado es un hecho del sistema; una inferencia es una conjetura sobre el.
Que la conjetura pudiera vencer invertiria la linea de autoridad de ADR-0014.

La inferencia refutada **se conserva marcada, no se borra**: sin ese rastro, el sistema volveria a
deducir lo mismo de las mismas observaciones y el usuario tendria que corregirlo indefinidamente.
"""

from __future__ import annotations

import json
import time

_TIPOS = ("semantica", "procedimental")


class ModeloUsuario:
    """Lo que AURA cree saber sobre una persona. Opera sobre memoria semantica y procedimental."""

    def __init__(self, memoria) -> None:
        self._memoria = memoria

    # ------------------------------------------------------------------ ver --

    async def ver(self, user_id: str) -> list[dict]:
        """Todo lo que el sistema cree saber, con su procedencia (ADR-0017 §3)."""
        return [
            {
                "contenido": i["content"],
                "tipo": i["kind"],
                "origen": i.get("provenance", {}).get("origen", "desconocido"),
                "fuente": i.get("provenance", {}).get("fuente", "desconocida"),
                "clase": i.get("provenance", {}).get("clase"),
                "refutada": i.get("provenance", {}).get("refutada", False),
                "ts": i.get("provenance", {}).get("ts"),
            }
            for i in self._entradas(user_id)
        ]

    # ------------------------------------------------------------- corregir --

    async def corregir(self, user_id: str, anterior: str, correccion: str) -> None:
        """El usuario rectifica. Su version pasa a ser `declarada` y prevalece."""
        for i in self._entradas(user_id):
            if i["content"] == anterior:
                i.setdefault("provenance", {})["refutada"] = True
                i["provenance"]["refutada_ts"] = time.time()
        await self._memoria.write(
            user_id,
            "semantica",
            correccion,
            {
                "trace_id": "correccion",
                "fuente": "usuario",
                "clase": "correccion",
                "origen": "declarada",  # lo corrige el usuario: es un hecho, no una hipotesis
                "corrige": anterior,
                "ts": time.time(),
            },
        )

    # -------------------------------------------------------------- exportar --

    async def exportar(self, user_id: str) -> str:
        """JSON legible sin AURA (4.1 §5). Un formato que solo el sistema sabe leer no es soberania."""
        return json.dumps(
            {"usuario": user_id, "exportado_ts": time.time(), "entradas": await self.ver(user_id)},
            ensure_ascii=False,
            indent=2,
        )

    # ---------------------------------------------------------------- borrar --

    async def borrar(self, user_id: str, contiene: str | None = None) -> int:
        """Borra el modelo, entero o selectivamente, de forma PERSISTENTE (soberania, ADR-0017).

        NO toca la memoria episodica: borrar lo que AURA cree saber sobre alguien no puede borrarle
        su propia conversacion. Delega en `memoria.olvidar`, que reescribe el almacen: el olvido
        sobrevive al reinicio (antes solo se mutaba la lista en memoria y el dato reaparecia).
        """

        def objetivo(i: dict) -> bool:
            return i["user_id"] == user_id and i["kind"] in _TIPOS and (contiene is None or contiene in i["content"])

        return self._memoria.olvidar(objetivo)

    # ---------------------------------------------------------------- refutar --

    async def refutar(self, user_id: str, contiene: str) -> int:
        """El usuario dice "eso ya no es cierto": se marca `refutada` de forma PERSISTENTE.

        No borra (a diferencia de `borrar`): conserva el rastro (ADR-0017), pero AURA deja de afirmarlo.
        """

        def objetivo(i: dict) -> bool:
            return (
                i["user_id"] == user_id
                and i["kind"] in _TIPOS
                and contiene in i["content"]
                and not i.get("provenance", {}).get("refutada")
            )

        return self._memoria.marcar(objetivo, {"refutada": True, "refutada_ts": time.time()})

    # ----------------------------------------------------------------- util --

    def _entradas(self, user_id: str) -> list[dict]:
        """Aislamiento por usuario (P-ARQ-5): nadie ve ni altera el modelo de otro."""
        return [i for i in self._memoria._items if i["user_id"] == user_id and i["kind"] in _TIPOS]


# --- Presentacion FIEL AL MODELO (precision del CEO, 2026-07-28) --------------------------------------
#
# El sistema hoy distingue conocimiento `declarado` (el usuario lo dijo) de `observado` (patron visto en
# conversaciones); NO infiere. La interfaz refleja EXACTAMENTE eso: "me lo dijiste" / "lo he observado".
# No se inventan grados de certeza ("creo") que no correspondan a algo verificable en la procedencia.


def _marca_de_origen(entrada: dict) -> str:
    return "me lo dijiste" if entrada.get("origen") == "declarada" else "lo he observado"


def describir_conocimiento(entradas: list[dict]) -> str:
    """Lo que AURA sabe del usuario, sin lo refutado, con su procedencia. Comunicable, fiel al modelo."""
    vivas = [e for e in entradas if not e.get("refutada")]
    if not vivas:
        return "Todavía no sé nada sobre ti."
    lineas = "\n".join(f"• {e['contenido']} ({_marca_de_origen(e)})" for e in vivas)
    return f"Esto es lo que sé de ti:\n{lineas}"


def explicar_entrada(entrada: dict) -> str:
    """Por que AURA lo sabe, segun la procedencia (declarado vs observado). Toda afirmacion se explica."""
    if entrada.get("origen") == "declarada":
        return f"Lo de «{entrada['contenido']}» lo sé porque me lo dijiste tú."
    return (
        f"Lo de «{entrada['contenido']}» lo he observado en nuestras conversaciones; no me lo has dicho directamente."
    )
