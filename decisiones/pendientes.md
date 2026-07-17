---
documento: "Registro de pendientes para gates"
tipo: "Artefacto operativo (1.1 §3.1)"
fecha: 2026-07-17
mantenido-por: "Fable (CTO)"
---

# Pendientes visibles para el próximo gate

Registro exigido por la constitución (1.1 §3.2.3): conflictos y correcciones detectados que requieren decisión del CEO.

## P-001 — Correcciones propuestas al capítulo 2.1 (v1.0.0 → v1.1.0)

**Origen:** la revisión adversarial del 2.1 (19 hallazgos, ambos críticos: "aprobar con correcciones") concluyó después de que el CEO lo aprobara. Ninguna corrección cambia la sustancia aprobada; todas mejoran atribución, verificabilidad y coherencia:

1. Citar el momento mágico de la D2 **textualmente** y marcar como operacionalización del CTO (†) las métricas añadidas ("una vez al día", "sin re-explicación", "2 semanas"), remitiendo umbrales a 2.5.
2. §5: declarar las 4 pruebas como **criterios-marco** (no "objetivos" aún); reconocer la zona intermedia éxito/fracaso y remitir su umbral y veredicto a 2.5 + autoridad del gate; eliminar absolutos ("cualquier tema").
3. §6.6: "exportables y portables siempre" no proviene de D1/ADR-0001 → marcar como desarrollo del CTO y canalizar a 3.5/4.1 o ADR futuro.
4. §3.4: el compromiso offline no está decidido → reformular como derivación del ADR-0001 ("las funciones locales no dependen de conectividad"; el conjunto mínimo offline se define en 2.2/3.x) y reconciliar con §1.
5. §3.5 (vigilancia): sustituir la cláusula de propósito por un límite verificable — AURA no construye perfiles persistentes de personas distintas de su usuario; captación incidental, retención y acceso → 5.x/2.4.
6. §3.6/§5 (afecto/dependencia): remitir a 2.4 la frontera operativa cercanía-diseñada vs afecto-simulado y las señales de detección de dependencia.
7. §1/§4: enumerar las 9 capacidades de la D2 (hoy solo aparecen 5); "no depende de ningún proveedor" → fórmula del brief "de ningún proveedor único"; atribuciones D6/D1 precisadas; "10 años" → "largo plazo" (†); H2/H3 condicionados a apertura de ecosistemas de terceros; estándares con la fórmula del brief; quitar "comercial" del punto 7 de la anti-visión.
8. Riesgos: las métricas se formalizan en 2.5 (2.3 aporta escenarios, no métricas).

**Decisión requerida:** ratificar la revisión v1.1.0 del 2.1 con estas 8 correcciones, o indicar cuáles rechazar.
