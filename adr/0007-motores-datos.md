---
numero: ADR-0007
titulo: "Motores de datos: SQLite/PostgreSQL + Qdrant"
estado: accepted
fecha: 2026-07-18
fecha-resolucion: 2026-07-18
decisor: "Mauricio (CEO)"
proponente: "Fable (CTO)"
impacta: ["3.5", "3.6", "4.1"]
origen: "Acta D3 (4 niveles); capítulo 3.6"
reabre: "—"
supersede: "—"
superseded-por: "—"
motivo-rechazo: "—"
---

# ADR-0007 — Motores de datos: SQLite/PostgreSQL + Qdrant

## Contexto

El modelo de datos (3.5) mapea clases de motor (relacional, vectorial, etc.) que requieren productos concretos. Selección de tecnología con alternativas → 4 niveles (D3), decisión del CEO. Las cuatro alternativas y su recomendación viven en el capítulo 3.6 §3.

## Decisión

**Aprobada por el CEO (2026-07-18): Nivel Balanceado.** Se adopta **SQLite/PostgreSQL** para datos relacionales/documentales y **Qdrant** para la memoria vectorial (RAG, 4.1). Regla del CEO: *"Cada motor deberá utilizarse para el propósito para el cual fue diseñado, evitando duplicidad de responsabilidades"* — coherente con la regla 13 del ADR-0004 (no multiplicar motores). SQLite en despliegue local ligero; PostgreSQL cuando el volumen o la concurrencia lo justifiquen (misma familia SQL, migración sin rediseño).

## Consecuencias

Positivas: cumple local-first (ADR-0001), sustituibilidad (P-ARQ-4) y sostenibilidad por equipo pequeño (regla 13 ADR-0004). Negativas: la optimización a niveles superiores exige un ADR (o Alerta si cambia un principio). Riesgos aceptados: si el rendimiento no basta, se escala por el instrumento correspondiente.

## Impacto (acta D11 — obligatorio)

| Dimensión | Impacto |
|---|---|
| Seguridad | Positivo: locales, cifrado en reposo (3.5) |
| Privacidad | Positivo: datos locales (ADR-0001) |
| Modularidad | Positivo: clases de motor, no acopladas al dominio |
| Costo | Bajo: libres |
| Experiencia de usuario | Positivo: Qdrant habilita memoria semántica rápida |
| Mantenimiento futuro | Positivo: SQLite→PostgreSQL sin cambiar el modelo (3.5 §4) |

## Trazabilidad

Capítulos: 3.5 (registra los motores), 4.1 (memoria vectorial), 3.6. Código futuro: capa de persistencia.
