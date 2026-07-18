---
numero: ADR-0006
titulo: "Broker del Event Bus: NATS local"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["3.3", "3.6"]
origen: "Acta D3 (4 niveles); capítulo 3.6"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0006 — Broker del Event Bus: NATS local

## Contexto

El Event Bus (3.3) necesita un broker concreto que cumpla sus contratos (at-least-once + idempotencia, correlación Trace ID). Selección de tecnología con alternativas → 4 niveles (D3), decisión del CEO. Las cuatro alternativas y su recomendación viven en el capítulo 3.6 §3.

## Decisión

**Aprobada por el CEO (2026-07-18): Nivel Balanceado.** Se adopta **NATS** ejecutándose local como bus oficial de eventos, por su rendimiento, simplicidad y escalabilidad. Cumple los contratos de 3.3; los consumidores no dependen del broker (sustituible, P-ARQ-4).

## Consecuencias

Positivas: cumple local-first (ADR-0001), sustituibilidad (P-ARQ-4) y sostenibilidad por equipo pequeño (regla 13 ADR-0004). Negativas: la optimización a niveles superiores exige un ADR (o Alerta si cambia un principio). Riesgos aceptados: si el rendimiento no basta, se escala por el instrumento correspondiente.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: local, sin superficie de red externa |
| Privacidad | Positivo: 100% local (ADR-0001) |
| Modularidad | Positivo: los contratos 3.3 son independientes del broker |
| Costo | Bajo: libre, ligero |
| Experiencia de usuario | Neutro: invisible si cumple latencia |
| Mantenimiento futuro | Positivo: sustituible sin tocar consumidores |

## Trazabilidad

Capítulos: 3.3 (registra el broker), 3.6. Código futuro: infraestructura del bus.
