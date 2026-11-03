"""Model Router (Bible 4.2) — orquestacion multi-modelo por contrato. Proveedores mock
implementan el mismo contrato que ChatGPT/Claude/Gemini. Enrutamiento + fallback + circuit breaker."""

from __future__ import annotations

import asyncio
import json
import time

from .. import observability as obs


class MockProvider:
    def __init__(self, name, latency_ms, healthy=True):
        self.name = name
        self._lat = latency_ms
        self.healthy = healthy

    async def infer(self, prompt: str, modo: str = "accion") -> str:
        del modo  # el mock clasifica por palabras clave; el modo no le cambia el comportamiento
        await asyncio.sleep(self._lat / 1000.0)  # simula latencia del primer token
        if not self.healthy:
            raise RuntimeError(f"{self.name} no disponible")
        # La intencion se clasifica sobre la PETICION DEL USUARIO, no sobre el contexto de memoria:
        # el contexto no debe alterar lo que el usuario pide (leccion del walking skeleton; conecta con 5.2).
        u = prompt.split("Usuario:")[-1].lower() if "Usuario:" in prompt else prompt.lower()
        # Seguridad primero (P-ARQ-1): las intenciones de lista roja se detectan antes que las de lista verde.
        if "elimina" in u or "borra" in u:
            return json.dumps(
                {
                    "intent": "sistema",
                    "action": "eliminar_informacion",
                    "args": {"target": "archivo"},
                    "say": "Eso borrara informacion; necesito tu confirmacion.",
                }
            )
        if "acordamos" in u or "recuerda" in u or "que dijimos" in u:
            recuerdo = ""
            if "contexto memoria:" in prompt:
                recuerdo = prompt.split("contexto memoria:")[-1].split("]")[0].strip()
            return json.dumps(
                {"intent": "memoria", "action": "consulta", "args": {}, "say": f"Segun lo que recuerdo: {recuerdo}"}
            )
        if "luz" in u or "enciende" in u or "prende" in u:
            return json.dumps(
                {
                    "intent": "domotica",
                    "action": "encender_dispositivo",
                    "args": {"device": "luz sala"},
                    "say": "Listo, encendi la luz de la sala.",
                }
            )
        return json.dumps({"intent": "charla", "action": "consulta", "args": {}, "say": "Entendido."})


class ProveedoresNoDisponibles(RuntimeError):
    """Ningun proveedor pudo atender el turno: todos ABIERTOS (en enfriamiento) o fallaron en esta
    misma llamada a `route()`. Subclase de `RuntimeError` por COMPATIBILIDAD: el codigo existente que
    ya capturaba `RuntimeError` generico (p.ej. `__main__._conversar`) sigue funcionando sin cambios."""


class _EstadoCircuito:
    """Los tres estados del circuit breaker de UN proveedor (D-FC-7). Constantes, no un enum: el
    resto del modulo solo las compara por igualdad y un enum no aporta nada aqui."""

    CERRADO = "CERRADO"  # llama siempre
    ABIERTO = "ABIERTO"  # se salta sin llamar mientras no pase el enfriamiento
    SEMIABIERTO = "SEMIABIERTO"  # paso el enfriamiento: se permite UNA llamada de prueba


class _Circuito:
    """Estado persistente de un proveedor entre llamadas a `route()`. `abierto_desde is None`
    significa CERRADO; con marca de tiempo, ABIERTO hasta que el enfriamiento decide si ya toca
    SEMIABIERTO. No hay estado propio para SEMIABIERTO: se deriva del reloj en cada consulta, asi
    que dos hilos que preguntaran a la vez verian lo mismo (no hay bandera que puedan pisarse)."""

    __slots__ = ("abierto_desde",)

    def __init__(self) -> None:
        self.abierto_desde: float | None = None

    def estado(self, ahora: float, enfriamiento_s: float) -> str:
        if self.abierto_desde is None:
            return _EstadoCircuito.CERRADO
        if ahora - self.abierto_desde < enfriamiento_s:
            return _EstadoCircuito.ABIERTO
        return _EstadoCircuito.SEMIABIERTO

    def abrir(self, ahora: float) -> None:
        self.abierto_desde = ahora

    def cerrar(self) -> None:
        self.abierto_desde = None


class ModelRouter:
    def __init__(self, providers, latency_budget_ms, *, enfriamiento_s: float = 60.0, reloj=time.monotonic):
        """`enfriamiento_s` y `reloj` son NUEVOS y llevan defecto: la firma antigua
        `ModelRouter(providers, latency_budget_ms)` (la que usa el resto del proyecto) sigue
        funcionando sin tocarla. `reloj` es inyectable para que las pruebas puedan avanzar el tiempo
        sin dormir de verdad (D-FC-7: nada de sleeps en la bateria de circuito)."""
        self.providers = providers  # ordenados por preferencia (calidad/latencia/privacidad)
        self.budget = latency_budget_ms  # 2.5 5.1 (R1 nube <=1200ms)
        self._enfriamiento_s = enfriamiento_s
        self._reloj = reloj
        self._circuitos: dict[str, _Circuito] = {p.name: _Circuito() for p in providers}

    def estado_circuitos(self) -> dict:
        """Diagnostico (entregable 2): estado ACTUAL de cada proveedor, derivado del reloj en el
        instante de la llamada. No es un campo que se pueda leer "viejo": se recalcula siempre."""
        ahora = self._reloj()
        return {nombre: circuito.estado(ahora, self._enfriamiento_s) for nombre, circuito in self._circuitos.items()}

    async def route(self, prompt, trace_id, modo: str = "accion"):
        """`modo` distingue cognicion de accion. Es opcional: sin el, todo se comporta como antes.

        Un proveedor que no lo entienda —cualquier implementacion previa del puerto— se sigue
        llamando con la firma de siempre, asi que el contrato `ModelProvider` no cambia.

        Circuit breaker recuperable (D-FC-7): un proveedor ABIERTO se salta SIN llamarlo; uno
        SEMIABIERTO recibe EXACTAMENTE una llamada de prueba por `route()` (nunca dos, nunca en
        bucle) — si acierta vuelve a CERRADO, si falla reabre con una marca de tiempo nueva."""
        ahora = self._reloj()
        for prov in self.providers:
            circuito = self._circuitos.setdefault(prov.name, _Circuito())
            estado = circuito.estado(ahora, self._enfriamiento_s)
            if estado == _EstadoCircuito.ABIERTO:
                obs.log(
                    "WARN", "router", f"circuito ABIERTO: {prov.name} en enfriamiento, se salta sin llamar", trace_id
                )
                continue
            try:
                try:
                    out = await prov.infer(prompt, modo)
                except TypeError:
                    out = await prov.infer(prompt)
            except Exception as e:
                circuito.abrir(ahora)
                origen = "prueba SEMIABIERTA" if estado == _EstadoCircuito.SEMIABIERTO else "fallback"
                # audit=True: un circuito que se abre es un hecho forense (D-FC-7), no una curiosidad
                # de consola -- es la misma razon por la que composicion.py audita una degradacion.
                obs.log(
                    "WARN",
                    "router",
                    f"{origen}: {prov.name} fallo ({type(e).__name__}: {e}); circuito -> ABIERTO",
                    trace_id,
                    audit=True,
                )
                continue
            if estado == _EstadoCircuito.SEMIABIERTO:
                circuito.cerrar()
                obs.log(
                    "LLM", "router", f"prueba SEMIABIERTA OK: {prov.name} circuito -> CERRADO", trace_id, audit=True
                )
            obs.log("LLM", "router", f"enrutado a {prov.name}", trace_id)
            return prov.name, out
        raise ProveedoresNoDisponibles(
            f"todos los proveedores fallaron (sin fallback disponible); estado: {self.estado_circuitos()}"
        )
