---
numero: ADR-0009
titulo: "Avatar: Live2D / 2D animado"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["6.5", "3.6", "3.4"]
origen: "Acta D3 (4 niveles); capítulo 3.6"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0009 — Avatar: Live2D / 2D animado

## Contexto

El avatar interactivo (6.5, capacidad del MVP D2) requiere una tecnología de render. Selección de tecnología con alternativas → 4 niveles (D3), decisión del CEO. Las cuatro alternativas y su recomendación viven en el capítulo 3.6 §3.

## Decisión

**Aprobada por el CEO (2026-07-18): Nivel Balanceado.** Se adopta **Live2D / avatar 2D animado**. Regla del CEO: *"La arquitectura deberá permitir evolucionar hacia un avatar 3D en el futuro sin requerir rediseños del sistema"* — el avatar es un plugin por contrato (3.4), sustituible por un motor 3D sin tocar el núcleo (Evolución Permanente).

## Consecuencias

Positivas: cumple local-first (ADR-0001), sustituibilidad (P-ARQ-4) y sostenibilidad por equipo pequeño (regla 13 ADR-0004). Negativas: la optimización a niveles superiores exige un ADR (o Alerta si cambia un principio). Riesgos aceptados: si el rendimiento no basta, se escala por el instrumento correspondiente.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Neutro |
| Privacidad | Positivo: render local |
| Modularidad | Positivo: adaptador de avatar por contrato (3.4); 3D futuro sin rediseño |
| Costo | Bajo: Live2D ligero vs 3D |
| Experiencia de usuario | Positivo: presencia visual con bajo costo computacional |
| Mantenimiento futuro | Positivo: evoluciona a 3D por sustitución de plugin |

## Trazabilidad

Capítulos: 6.5 (avatar), 3.4 (contrato de plugin), 3.6. Código futuro: adaptador de avatar.
