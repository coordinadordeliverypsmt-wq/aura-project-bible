---
documento: "Plan del Milestone M1 — Núcleo Conversacional"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "Activo"
---

# Milestone M1 — Núcleo Conversacional

**Autorizado por el CEO el 2026-07-18** tras aprobar la Architecture Review M1. Fase de **desarrollo funcional** sobre el walking skeleton, dentro de los contratos aprobados y sin ADR/dependencias nuevas sin beneficio medible (D26).

## Objetivo (2.2 §3, hito M1)

El núcleo conversacional: **memoria permanente + conversación por voz + orquestación multi-modelo** (con **Ollama local** por D24). Criterio de salida del hito: pruebas 1 y 2 del momento mágico (2.2 §3.2) y HC-1 validado en hardware objetivo.

## Criterios de seguimiento del CEO (obligatorios)

1. **HC-1 permanece ABIERTO** hasta completar la validación en hardware objetivo (`run_demo_real.py` + `entorno/VALIDACION-COMPLETA.md`).
2. **Backups y recuperación de memoria = prioridad de M1:** diseñados **e implementados** antes de considerar **estable** el subsistema de memoria.
3. **Kill Switch:** implementado **durante M1**, antes de ampliar las capacidades operativas del sistema.

## Orden de trabajo (prioridades del CEO primero)

| # | Entregable | Estado | Prueba |
|---|---|---|---|
| M1.1 | Persistencia + **backups/recuperación** de memoria (3-2-1, integridad) | en curso | unit/integration |
| M1.2 | **Kill Switch** (control-plane, reversible, auditable, fuera de banda) | en curso | unit/integration |
| M1.3 | Bucle conversacional real (voz+LLM+memoria) sobre Ollama | pendiente hardware | e2e real |
| M1.4 | Evals de IA (7.2): arnes `evals_m1.py` (HITL lista roja completa, no-ejecucion directa, grounding, consistencia). **Detecto y corrigio un bug de HITL** (solo 3 acciones pasaban por permisos). | arnes listo; evals reales pendientes de hardware | eval + regresion |
| M1.5 | Cierre HC-1 en hardware objetivo | pendiente | run_demo_real |

## Fase actual: VALIDACION FUNCIONAL (directriz del CEO, 2026-07-18)

- **Mocks CONGELADOS:** el desarrollo sobre el entorno simulado queda congelado; **solo se aceptan correcciones de errores**. El foco es integrar y validar el **stack real** (Ollama, faster-whisper, Piper, NATS, memoria persistente) sobre los **contratos existentes**.
- **Demostracion oficial de M1:** `walking-skeleton/demo_capacidad_m1.py --real` en el hardware objetivo.
- **Arnes de medicion:** `walking-skeleton/validar_m1.py --real` registra automaticamente latencia por etapa/total, CPU/RAM/almacenamiento y errores/recuperaciones -> `resultados-m1.json`.
- **Si un objetivo de rendimiento/estabilidad no se cumple:** Alerta de Arquitectura (D15), nunca ajuste silencioso.
- **Criterio de avance:** comportamiento observado del producto en ejecucion, no cantidad de codigo.

## Reglas de M1

- Cada entregable se integra con **sus pruebas** (Plan de Calidad); **Quality Gate en PASS** obligatorio.
- Sin ADR/dependencia nueva sin demostrar reducción de complejidad o beneficio medible (D26).
- Cualquier inconsistencia/contradicción → Alerta de Arquitectura (D15).
- **Cierre de M1:** Architecture Review M1-exit (D25) + CEO Executive Summary (D17).
