---
documento: "Auditoría Técnica Integral — AURA Project Bible v1.0"
version: 1.0.0
autor: "Fable (CTO) actuando como auditor externo independiente"
fecha: 2026-07-18
estado: "Aprobada por el CEO (2026-07-18)"
historial:
  - version: 1.0.0
    fecha: 2026-07-18
    cambio: "Auditoría técnica integral de la Bible v1.0 completa, previa a autorización de construcción (mandato del CEO)"
---

# Auditoría Técnica Integral — AURA Project Bible v1.0

**Auditor:** CTO externo independiente (postura: no asumir que algo es correcto por estar aprobado). **Alcance:** los 36 capítulos, 9 ADRs, 23 decisiones y 2 alertas de la Bible v1.0. **Objetivo:** certificar (o no) la preparación para iniciar construcción.

**Método:** revisión de los 16 aspectos exigidos, con verificación cruzada entre capítulos, aritmética de presupuestos y trazabilidad de decisiones. Se buscaron activamente contradicciones, huecos y complejidad innecesaria.

## Veredicto general

La Bible es **excepcionalmente coherente, trazable y completa** para un proyecto de este alcance: arquitectura modular sólida (Event Bus como plano de control, memoria desacoplada, plugins por contrato), local-first consistente, gobernanza y trazabilidad de decisiones ejemplares, y horizonte de 10 años respetado. **No obstante, la auditoría identifica 1 hallazgo crítico, 3 importantes y 4 menores** que deben atenderse antes o durante el arranque. La certificación es **CONDICIONAL** (ver §6).

---

## 1. Hallazgos críticos

**HC-1 — El presupuesto de latencia de voz es aritméticamente inconsistente y su objetivo puede ser inalcanzable como está especificado.**
El 2.5 §5.1 fija P50 ≤ **800 ms** para el inicio de respuesta hablada (objetivo **oficial ratificado por el CEO**). Pero el presupuesto por etapa del mismo párrafo suma: captura+VAD ≤150 ms + STT (streaming, no cuantificado, > 0) + primer token del LLM ≤500 ms + primer audio TTS ≤300 ms = **≥ 950 ms** ignorando el STT. **Las etapas no caben dentro del P50.** Como la latencia es el factor make-or-break del hito M1 (el de mayor riesgo del MVP), esta inconsistencia debe resolverse antes de comprometer la construcción de M1. Agravante: con LLMs de nube (los 3 del MVP), 500 ms al primer token es optimista; el objetivo real puede requerir modelos locales (R2) para el camino conversacional.
*Impacto: arquitectura, rendimiento, UX, riesgo del MVP. Reservado al CEO (ratificó los números).*
**Acción:** reconciliar — reajustar el P50 a un valor alcanzable con nube (p. ej. P50 ≤ 1200 ms para R1) y/o mover el objetivo agresivo a R2 (local); y hacer que el **walking skeleton (7.3) mida la latencia real ANTES de construir M1 completo.**

## 2. Hallazgos importantes

**HI-1 — ADR-0003 planeado pero nunca creado (hueco de trazabilidad normativa).**
El plan de formalización (1.2 §9) asignó **ADR-0003 = autonomía/D4, "con el capítulo 5.3"**. El 5.3 se redactó y aprobó **sin crear el ADR-0003**; la secuencia de ADRs salta de 0002 a 0004. La obligación del plan quedó incumplida y hay un número faltante.
**Acción:** crear ADR-0003 (formaliza las listas verde/roja de la D4), **o** enmendar 1.2 §9 para declarar que la D4 se materializa directamente en 5.3 sin ADR (como D2/D5/D6/D7). Recomiendo crear el ADR-0003 por la relevancia de seguridad de la decisión.

**HI-2 — Todos los umbrales oficiales están sin validar empíricamente.**
Los objetivos del 2.5 (latencia, recall de memoria, anticipación, consistencia inter-modelo) son metas de diseño; las evals que los verifican (7.2) están **diseñadas, no ejecutadas**. No existe una sola prueba empírica de que la arquitectura los cumpla. Riesgo de descubrir infactibilidad tarde.
**Acción:** el walking skeleton (7.3) debe ser el **primer** entregable de construcción y debe validar HC-1 (latencia) y el recall de memoria antes de comprometerse al MVP completo.

**HI-3 — Ambición del alcance frente a la capacidad real de construcción.**
El MVP son 10 capacidades (9 + KCM) que incluyen voz de baja latencia, memoria de años, avatar, orquestación multi-modelo, domótica y captura de conocimiento — un alcance que, para un equipo de 1 humano + agentes, es enorme de **construir** (la salvaguarda anti-sobre-ingeniería protege el diseño, no el esfuerzo de implementación). Riesgo de no-convergencia del MVP.
**Acción:** ejecutar estrictamente los hitos secuenciales M1→M2→M3 con el circuito de fracaso (2.2 §3.5); considerar reducir el MVP a M1 (núcleo conversacional) como primer objetivo de valor demostrable antes de comprometerse a M2/M3.

## 3. Hallazgos menores

- **HM-1** — La descripción del capítulo 2.1 en el `INDICE.md` aún dice "compañero cognitivo" y no refleja la definición primaria **PIOS** (D18). Corregir el índice.
- **HM-2** — El mandato D12 (generar PDF automáticamente al aprobar) **falla operativamente**: el publicador (Chrome, un PDF por documento) excede el timeout con ~40+ documentos; los PDF están desactualizados. El HTML está al día. Se resuelve al migrar a MkDocs Material (ADR-0002, ya aceptado).
- **HM-3** — Redundancia parcial entre las cinco preguntas de largo plazo (D21, 3.1 §2.5), el checklist de evaluación arquitectónica (3.1 §2.3) y la regla 13 del ADR-0004. No es contradicción, pero podría consolidarse para evitar mantenimiento triplicado.
- **HM-4** — El 6.4 habla de "ejecución remota segura" para el computador principal, que en el MVP es **local**; precisar el término (aplica a R2 cuando haya sistemas remotos).

## 4. Recomendaciones

1. **Resolver HC-1 (latencia) antes de construir M1** — reconciliar los números y validar empíricamente en el walking skeleton.
2. **Crear ADR-0003** (o enmendar el plan 1.2 §9).
3. **Construir el walking skeleton primero** (7.3) como prueba de factibilidad de la arquitectura y de los umbrales top (latencia, memoria) — no comprometerse al MVP completo hasta que pase.
4. **Completar la revisión legal del KCM** (1.5) antes de habilitar la sub-capacidad de llamadas/reuniones (4.5).
5. **Migrar a MkDocs Material** (ADR-0002) para resolver HM-2 y mejorar la legibilidad (búsqueda, Mermaid).
6. **Corregir HM-1** (índice) y **consolidar HM-3** en una revisión de mantenimiento.
7. **Considerar M1 como primer objetivo de valor** (HI-3) antes de M2/M3.

## 5. Riesgos residuales

| Riesgo | Severidad | Mitigación vigente | Estado |
|---|---|---|---|
| Latencia de voz (M1) infactible con nube | Alta | Canales dedicados; R2 local; walking skeleton | **Abierto (HC-1)** |
| Umbrales sin validar empíricamente | Alta | 7.2 evals; walking skeleton | Abierto (HI-2) |
| No-convergencia del MVP por ambición | Media-alta | Hitos secuenciales + circuito de fracaso | Gestionado |
| Legalidad del KCM (llamadas/reuniones) | Media | Alcance de sesión + revisión legal 1.5 | Pendiente de revisión legal |
| Costo de inferencia en operación | Media | Economía cognitiva (4.2), visibilidad (1.5) | Gestionado, sin datos reales |
| Dependencia de 3 nubes en R1 | Media | Contrato de proveedor + R2 local | Gestionado |
| Degradación de memoria a años | Media | Consolidación diferida a v2 | Aceptado para v1 |
| Single point of compromise (AURA) | Alta | Todo el Libro V (zero trust, HITL, sandboxing) | Mitigado por diseño |

## 6. Certificación de preparación

**Certificación: CONDICIONAL — "Go condicionado".**

Como auditor externo, **certifico que la arquitectura de la Bible v1.0 es sólida, coherente y construible**, y que su gobernanza y trazabilidad son de nivel profesional. **No certifico** el arranque incondicional del MVP completo por el hallazgo crítico HC-1 (latencia) y la ausencia de validación empírica (HI-2).

**Recomendación de autorización:**

- **Autorizar** el inicio de la construcción **empezando por el walking skeleton (7.3)**, cuyo propósito es exactamente validar la arquitectura y los umbrales críticos en código real.
- **Condiciones previas a M1 completo:** (a) resolver HC-1 (reconciliar el presupuesto de latencia — decisión del CEO por ser umbral ratificado); (b) crear ADR-0003 (HI-1); (c) que el walking skeleton demuestre la latencia y el recall.
- Los hallazgos menores (HM-1..4) se corrigen en mantenimiento, sin bloquear.

La construcción del sistema queda supeditada a la **aprobación de esta auditoría por el CEO**, conforme a su mandato.

## Resolución del CEO (2026-07-18)

**Auditoría APROBADA.** Correcciones autorizadas y aplicadas: HC-1 (latencia reconciliada: R1 ≤1200 ms, R2 ≤800 ms), HI-1 (ADR-0003 creado), HM-1 (índice corregido). **La AURA Project Bible v1.0 queda oficialmente cerrada.** Autorizada la transición a la fase de construcción, comenzando por el **Walking Skeleton**.
