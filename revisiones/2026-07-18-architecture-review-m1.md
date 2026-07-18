---
documento: "Architecture Review M1"
version: 1.0.0
autor: "Fable (CTO), revisión de coherencia arquitectónica"
fecha: 2026-07-18
estado: "Aprobada por el CEO (2026-07-18)"
---

# Architecture Review M1 — Estado consolidado del proyecto AURA

**Propósito (mandato del CEO):** confirmar que la arquitectura permanece **coherente** tras la transición completa al stack real, antes de cerrar HC-1 y abrir el siguiente milestone. No desarrolla funcionalidad nueva.

**Veredicto de coherencia:** ✅ **La arquitectura permanece coherente.** Los 13 ADRs son consistentes entre sí y con las 24 decisiones; las 2 Alertas están resueltas; el walking skeleton valida la arquitectura en ejecución (Quality Gate PASS). Se detectó **una** inconsistencia menor de trazabilidad (solapamiento ADR-0007/0008 ↔ 0011/0012/0013), **evaluada contra el umbral de Alerta y resuelta como corrección editorial** (notas de refinamiento) por no ser una contradicción ni comprometer el proyecto. No se levanta ninguna Alerta de Arquitectura nueva; el detalle del criterio está en §5.

---

## 1. Estado de cada ADR

Los 13 ADRs están **`accepted`**; ninguno `proposed`, `superseded` ni `deprecated`.

| ADR | Estado | Título | Relación |
|---|---|---|---|
| 0001 | accepted | Postura local-first estricta | — |
| 0002 | accepted | Plataforma documental (MkDocs Material) | — |
| 0003 | accepted | Listas de Autonomía (verde/roja) y HITL | — |
| 0004 | accepted | Evolución Permanente y arquitectura modular | — |
| 0005 | accepted | Lenguaje/runtime del núcleo (Python) | — |
| 0006 | accepted | Event Bus (NATS local) | — |
| 0007 | accepted | Motores de datos (SQLite/PostgreSQL + Qdrant) | refinado por 0011 |
| 0008 | accepted | Voz local (Whisper + Piper) | refinado por 0012, 0013 |
| 0009 | accepted | Avatar (Live2D) | — |
| 0010 | accepted | Runtime LLM local (Ollama) | — |
| 0011 | accepted | Base vectorial (Qdrant; pgvector alterno) | refina 0007 |
| 0012 | accepted | STT local (faster-whisper) | refina 0008 |
| 0013 | accepted | TTS local (Piper) | refina 0008 |

## 2. Estado de cada decisión de arquitectura (D1-D24)

Las 24 decisiones están **vigentes**; ninguna revocada. Clasificación:

- **Principios permanentes:** D1 (local-first), D9 (HITL), D10/D14 (Evolución Permanente), D18 (PIOS), D19 (naturaleza), D20 (10 años), D21 (5 preguntas), D24 (local-first sin proveedores).
- **Alcance/producto:** D2 (MVP 9 cap.), D5 (multiusuario-ready), D6 (identidad), D23 (KCM + cierre de alcance).
- **Gobernanza/proceso:** D3 (4 niveles), D4 (autonomía→ADR-0003), D7 (cierre Bible), D8 (Git+Markdown→ADR-0002), D11 (matriz impacto), D12 (modo documental), D13 (estructura capítulo), D15/D16 (Alertas), D17 (Executive Summary), D22 (delegación de ejecución).
- **Materializadas y verificadas en código (skeleton):** D1, D4/D9 (permisos+HITL), D6 (guardrails de router), D10 (contratos), D21 (evaluación en cada capítulo/ADR).

## 3. Cumplimiento de requisitos (Bible)

**Nota honesta:** la Bible **diseña** el 100 %; sólo el **walking skeleton** está implementado (rebanada fina que valida la arquitectura). Estado por requisito funcional (2.5 §2):

| RF | Capacidad | Diseñado | Validado en skeleton | Implementación plena |
|---|---|---|---|---|
| RF-1 | Memoria | ✅ | ✅ contrato + recall + no-fabricación | pendiente (Qdrant real) |
| RF-2 | Voz | ✅ | ✅ contrato + latencia estructural | pendiente (Whisper/Piper reales, HC-1) |
| RF-3 | Avatar | ✅ | — | pendiente |
| RF-4/5/9 | Computador/Automatización/Notif. | ✅ | ✅ acción vía permisos (mock HA) | pendiente (agente local) |
| RF-6 | Orquestación 3 LLMs | ✅ | ✅ router + fallback + circuit breaker | pendiente (Ollama real) |
| RF-7 | Hogar | ✅ | ✅ adaptador (mock) | pendiente (HA+MQTT) |
| RF-8 | Aprendizaje | ✅ | parcial (memoria) | pendiente |
| RF-HITL | Human-in-the-Loop | ✅ | ✅ lista roja detenida, tolerancia cero | pendiente (5.3 completo) |

**Atributos de calidad (NFR, 2.5 §3):** seguridad/privacidad (diseñado + local-first en skeleton) ✅; fiabilidad/auditabilidad (audit log en skeleton) ✅; **latencia** (estructural OK; **real = HC-1 pendiente de hardware**); mantenibilidad/modularidad (contratos + Quality Gate PASS) ✅; escalabilidad/independencia (multi-proveedor por contrato) ✅; portabilidad (scripts 3 SO) ✅.

## 4. Trazabilidad Bible → ADR → Código → Pruebas

| Bible | ADR | Código (walking-skeleton) | Pruebas |
|---|---|---|---|
| 3.3 Event Bus | 0006 | `bus.py`, `bus_nats.py` | `integration/test_bus_flow.py`, latencia NATS |
| 3.4 Plugins/contratos | 0004 | `contracts.py` | `test_contracts.py` |
| 4.1 Memoria | 0007/0011 | `modules/memory.py` | `unit/test_memory.py` |
| 4.2 Orquestación | 0010 | `modules/router.py`, `modules/providers_real.py` | `unit/test_router.py` |
| 4.3 Agentes | — | `core/orchestrator.py` | `e2e/test_end_to_end.py` |
| 5.3 Permisos/HITL | 0003 | `core/permissions.py` | `unit/test_permissions.py` |
| 6.2 Voz | 0008/0012/0013 | `adapters/voice.py`, `adapters/voice_real.py` | `e2e/test_real_stack.py` (skip) |
| P-ARQ-7 Observabilidad | — | `observability.py` | (métricas/trace en logs) |

Cobertura de pruebas: **25 pruebas** (21 activas + 2 skip stack real + contratos), Quality Gate en **PASS**.

## 5. Riesgos técnicos abiertos

1. **HC-1 (latencia real):** pendiente de validación en hardware objetivo (D24). El presupuesto R1 ≤1200 ms con LLM local en CPU es plausible pero no probado.
2. **Evals de IA (7.2):** consistencia inter-modelo, guardrails y no-fabricación con LLMs reales — diseñadas, no ejecutadas (dependen del stack real).
3. **Inconsistencia de trazabilidad de ADRs de stack** (0007/0008 ↔ 0011/0012/0013): *resuelta* con notas de refinamiento. **Criterio de Alerta:** no se levantó Alerta porque las decisiones son **consistentes** (mismos productos) — es traceabilidad, no contradicción; el CEO puede solicitar una si discrepa.

## 6. Deuda técnica registrada

- **Publicación PDF (D12) inoperante** por timeout del publicador con ~60 documentos → migrar a MkDocs Material (ADR-0002 ya aceptado). *Debt priorizada.*
- **Redundancia D21 / checklist 3.1 §2.3 / regla 13 ADR-0004** (HM-3 auditoría): consolidar.
- **Consolidación/olvido de memoria** diferidos a v2 (4.1) — deuda de diseño aceptada.
- **run_demo_real.py sin ejecutar** (sin hardware) — deuda de validación, no de código.

## 7. Riesgos de rendimiento

- Latencia STT→LLM→TTS en CPU sin GPU puede exceder R1; mitigación: modelo 3B cuantizado, streaming por etapas (solapar), o R2 con GPU. Si excede: **Alerta D15**, no ajuste silencioso.
- Memoria vectorial a escala de años: Qdrant escala; pgvector para huella mínima (ADR-0011).

## 8. Riesgos de seguridad

- **Prompt injection con efecto físico** (riesgo #1, 5.2): diseño de defensa en profundidad; el skeleton ya separa intención (petición del usuario) de contexto (hallazgo real corregido). Pendiente: red teaming con LLM real (7.2).
- **Cadena de suministro de plugins** (3.4 §4): firma/SBOM diseñados, no implementados.
- **KCM y terceros:** guardrail resuelto (alcance de sesión, ALERTA-002); **revisión legal de llamadas/reuniones pendiente** (1.5) antes de habilitar esa sub-capacidad.
- Superficie local-first: sin claves de terceros (D24) reduce exposición.

## 9. Riesgos de portabilidad

- Diferencias de plataforma (venv, binario-vs-servicio, GPU, CRLF) **resueltas en `entorno/`, sin tocar el código** (endpoints idénticos NATS:4222 / Ollama:11434). Riesgo bajo.
- Windows: winget puede faltar → fallback manual documentado. Voz Piper: descarga manual documentada.

## 10. Riesgos operacionales

- **Arranque de servicios** (NATS, Ollama) manual en el equipo objetivo → `verify-stack` es el gate previo.
- **Backups de la memoria** (activo irremplazable): diseñados (3.5/7.4), no implementados; crítico antes de producción.
- **Kill switch** (5.3): diseñado, no implementado.

## 11. Riesgos de mantenimiento

- **Equipo de 1 humano + agentes** frente a un sistema amplio (HI-3 auditoría): mitigado por hitos secuenciales, Quality Gate y arquitectura por contratos; a vigilar.
- **Volumen documental** (60+ documentos) sin sitio navegable con búsqueda hasta migrar a MkDocs.
- Disciplina de "toda funcionalidad con sus pruebas" (nueva política): sostenible por el Quality Gate.

## 12. Recomendaciones para el Milestone M1

1. **Cerrar HC-1** ejecutando `run_demo_real.py` en hardware objetivo (runbook `entorno/VALIDACION-COMPLETA.md`); si un umbral falla, **Alerta D15**.
2. **M1 = núcleo conversacional** (memoria + voz + orquestación, 3 LLMs → aquí Ollama local por D24), construido sobre el walking skeleton, **cada incremento con sus pruebas** y sin salir de los contratos.
3. **Prioridad temprana en M1:** backups de memoria y kill switch (riesgos operacionales), y las **evals de IA** (7.2) con el LLM real (guardrails, no-fabricación, consistencia).
4. **Deuda a saldar en M1:** migrar la publicación a MkDocs (resuelve PDF y da búsqueda/Mermaid); consolidar la redundancia D21/checklist.
5. **Revisión legal del KCM** antes de su sub-capacidad de llamadas/reuniones.
6. Mantener el **Quality Gate en PASS** como condición de cada integración.

## Conclusión

La arquitectura de la Bible v1.0 **se mantiene coherente** tras la transición al stack real. **APROBADA por el CEO el 2026-07-18**; sin Alerta por la trazabilidad de ADRs (refinamiento documental, no contradicción). **Milestone M1 autorizado** con criterios de seguimiento (ver `milestones/M1-plan.md`): HC-1 abierto hasta validar en hardware; backups/recuperación de memoria e implementación del kill switch son prioridades de M1.
