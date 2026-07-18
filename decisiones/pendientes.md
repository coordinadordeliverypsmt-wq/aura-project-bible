---
documento: "Registro de pendientes para gates"
tipo: "Artefacto operativo (1.1 §3.1)"
fecha: 2026-07-17
mantenido-por: "Fable (CTO)"
---

# Pendientes visibles para el próximo gate

Registro exigido por la constitución (1.1 §3.2.3): conflictos y correcciones detectados que requieren decisión del CEO.

## P-002 — Paquete de correcciones al 3.1 (Aprobado) y al ADR-0004 (accepted)

**Origen:** revisión adversarial del 3.1/ADR-0004 (16 hallazgos), concluida tras la aprobación del CEO. Requiere autorización expresa porque toca documentos aprobados/aceptados:

**Al capítulo 3.1 (→ v1.1.0):**
1. §2.1: alcance del bus según la resolución de la **ALERTA-001** (plano de control + streams dedicados correlacionados), si el CEO aprueba la Opción A.
2. §2.1: definir el núcleo por criterio de pertenencia (orquestación, permisos, bus — lo que no puede fallar aisladamente); **la memoria sale del núcleo** y se vuelve módulo con contrato versionado — corrige contradicción con D10 ("toda inteligencia será desacoplada").
3. Jerarquía de principios: P-ARQ-1 y P-ARQ-2 prevalecen siempre; los demás conflictos se resuelven por ADR con ambas lecturas; la jerarquía jamás ordena actas de rango 1.
4. P-ARQ-7: los logs/trazas/telemetría son datos del usuario sujetos íntegramente al ADR-0001 (retención y redacción → 7.4/5.5).
5. P-ARQ-8 fiel a la D7 (ningún código hasta cerrar la Bible; la regla per-capítulo queda como desarrollo † para la fase de implementación).
6. P-ARQ-4/checklist: definición operativa de "alternativa viable" (capacidades cubiertas, licencia/costo evaluados, prueba de humo documentada), validador = revisor pre-gate, re-verificación por evento.
7. Checklist §2.3: +3 preguntas (presupuesto de latencia, idempotencia de efectos físicos, comportamiento degradado offline) con evidencia por respuesta.
8. Atribuciones †: trade-offs "3 por actas + 1 propuesto"; fila monolito cita D10; "versionadas" atribuido a la regla 8; §2.4 cita el acta D15 y la enmienda ya ratificada.

**Al ADR-0004 (→ v1.1.0, autorización expresa por ser `accepted`):**
9. **Errata de transcripción:** el bloque "texto del CEO" omite 3 cláusulas de la D10 (módulos diseñados para evolucionar; capacidades nuevas sin rediseñar; aprendizaje continuo). Se completan — crítico: el ADR aceptado es hoy la fuente vigente y esos mandatos tuyos quedaron fuera.
10. Regla 10: declara frontalmente que **acota la D14.7** ("posible" se interpreta como "sostenible por el equipo real") — el CEO la aceptó, pero merece aceptación consciente de esa acotación; alternativa blanda: quitar el veto y dejar solo la obligación de documentar.
11. Regla 8: política de deprecación — la convivencia de versiones TERMINA (default: máx. 2 versiones mayores vivas; el retiro de la vieja cierra el ADR de ruptura).

**Decisión requerida:** (a) veredicto de la ALERTA-001 (Opción A/B/C); (b) autorizar P-002 completo o indicar exclusiones; (c) sobre la regla 10: acotación frontal o versión blanda.


## Resueltos

| ID | Asunto | Resolución |
|---|---|---|
| P-001 | 8 correcciones al capítulo 2.1 (revisión adversarial post-aprobación) | **Ratificadas por el CEO el 2026-07-17** → aplicadas en 2.1 v1.1.0 |
