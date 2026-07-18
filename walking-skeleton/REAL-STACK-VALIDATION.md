# Walking Skeleton — Validación con Stack Real (parcial y honesta)

**Fecha:** 2026-07-18 · Sustitución de mocks por componentes reales y medición de latencia.

## Qué se pudo validar con producto REAL

### Event Bus: NATS real (ADR-0006) — VALIDADO
- Servidor `nats-server v2.10.22` real + cliente `nats-py`.
- **Latencia real del bus (publish → entrega al suscriptor), 1000 eventos:**
  - **P50 = 0.35 ms · P95 = 2.99 ms · P99 = 6.98 ms · media = 0.78 ms**
  - El bus consume **< 1 %** del presupuesto de latencia R1 (≤ 1200 ms). No es el cuello de botella.
- **Intercambio por contrato demostrado:** el mismo orquestador, memoria, router, permisos y adaptadores corrieron **sin cambio alguno**; solo se sustituyó `InProcessEventBus` por `NatsEventBus` (mismo contrato `EventBus`). Es la prueba en ejecución de la Evolución Permanente (ADR-0004). Ver `run_demo_nats.py`.
- End-to-end sobre NATS real: 3 turnos OK, HITL de lista roja correcto, recuerdo de memoria correcto. Latencia e2e P50 = 113.8 ms (dominada por el LLM mock ~110 ms).

## Qué NO se pudo validar en este entorno (y por qué) — límite honesto

| Componente | Real requerido (Bible) | Estado en este entorno | Por qué |
|---|---|---|---|
| **LLM (etapa dominante)** | ChatGPT/Claude/Gemini (D2) o local | **MOCK** | **Sin claves de API** (OPENAI/ANTHROPIC/GEMINI ausentes) y **sin GPU / RAM** (2 CPU, ~1 GB libre) para un LLM local |
| STT / TTS | Whisper + Piper local (ADR-0008) | MOCK | 2 CPU / 1 GB RAM: Whisper sería tan lento que la medición **no sería representativa** del hardware objetivo |
| Memoria vectorial | Qdrant (ADR-0007) | in-process | Qdrant no instalado; el contrato de memoria sí se valida |

## Conclusión sobre HC-1 (latencia real R1 ≤ 1200 ms)

**No es certificable en este entorno de job.** La etapa que domina el presupuesto — el **primer token del LLM (≤ 500 ms)** — no puede medirse aquí porque no hay claves de API ni hardware para un modelo local. Lo que sí quedó probado:

1. La **arquitectura y los contratos funcionan** de extremo a extremo, con el **bus real** (NATS) validado y despreciable en latencia.
2. El **intercambio mock→producto por contrato funciona** exactamente como diseñó la Bible.

**Para cerrar HC-1 se necesita tu entorno de despliegue real:** claves de API de los 3 proveedores (R1, nube) o una máquina con GPU/RAM para Whisper+Piper y un LLM local (R2). Ahí se mide la latencia real de STT→LLM→TTS y se compara contra R1 ≤ 1200 ms / R2 ≤ 800 ms.

## Cómo reproducir
```
pip install --user nats-py                 # cliente
# descargar nats-server v2.10.22 (binario) y arrancarlo:  ./nats-server -p 4222
python3 run_demo_nats.py                    # walking skeleton sobre NATS real
```
