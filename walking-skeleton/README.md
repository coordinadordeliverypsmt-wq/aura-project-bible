# AURA — Walking Skeleton

Primera etapa de construccion de AURA (Bible 7.3), autorizada por el CEO el 2026-07-18 tras el cierre de la Project Bible v1.0.

**Objetivo (no es funcionalidad completa):** validar en ejecucion que la arquitectura disenada funciona como fue concebida. Valida los 8 puntos exigidos por el CEO:

| # | Punto a validar | Como lo valida el skeleton |
|---|---|---|
| 1 | Arquitectura | Nucleo minimo (bus+orquestador+permisos) con memoria y router como modulos externos por contrato |
| 2 | Flujo Event-Driven | `InProcessEventBus` con eventos versionados y `trace_id` (contrato de 3.3; NATS es el producto, ADR-0006) |
| 3 | Orquestacion Multi-Modelo | `ModelRouter` con proveedores por contrato, enrutamiento, fallback y circuit breaker (4.2) |
| 4 | Memoria | `SimpleMemory` fuera del nucleo, con procedencia y no-fabricacion (4.1); Qdrant es el producto (ADR-0007) |
| 5 | Permisos | `PermissionManager` con listas verde/roja (ADR-0003/D4) y HITL en lista roja (5.3) |
| 6 | Latencia | `Timer` mide cada etapa y el total vs presupuesto R1 <=1200ms (2.5 5.1) |
| 7 | Observabilidad | Logs estructurados + trace_id + audit log (P-ARQ-7) |
| 8 | Integracion entre modulos | Un turno atraviesa percepcion -> memoria -> router -> permisos -> accion -> respuesta |

**Fidelidad a la Bible:** los productos reales (NATS, Qdrant, Whisper/Piper, LLMs de nube) se sustituyen por implementaciones mock **detras del mismo contrato** — exactamente lo que la arquitectura de Evolucion Permanente (ADR-0004) permite. Cambiar de mock a produccion es cambiar la implementacion, no los consumidores.

## Ejecutar

El **unico punto de entrada oficial** de AURA es (D40, ADR-0018):

```
python -m aura_skeleton              # inicia AURA (conversacion interactiva)
python -m aura_skeleton --verificar  # informa que quedo activo y sale
```

Ambos ensamblan el sistema desde `composicion.componer()` (la unica composicion). No requiere
dependencias externas (solo la stdlib de Python 3.11+ para el arranque en modo mock).

Los scripts de demo y validacion (`run_demo_*.py`, `demo_capacidad_*.py`, `validar_*.py`, `evals_m1.py`)
son **arneses de validacion**, no puntos de entrada de produccion. Su clasificacion —fuente unica de
verdad (D41)— vive en `architecture_manifest.toml`.
