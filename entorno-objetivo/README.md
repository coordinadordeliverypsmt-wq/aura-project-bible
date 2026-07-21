---
documento: "Línea de trabajo — Preparación del Entorno Objetivo"
apertura: 2026-07-21
autoriza: "CEO (D35)"
naturaleza: "Solo documentación y análisis. No modifica el Core."
---

# Preparación del Entorno Objetivo

Línea de trabajo **independiente del roadmap funcional**, abierta por D35 mientras M3 espera sus
habilitadores externos.

## Qué es y qué no es

**Es** el análisis que debe existir *antes* de comprar hardware, elegir modelo o instalar nada.

**No es** avance de producto. Conforme a D35:

- **No modifica el Core** — ni un fichero de `walking-skeleton/aura_skeleton/`.
- **No incrementa el Product Readiness**, que permanece en **41%**. Documentar el entorno futuro no
  acerca a AURA a ser usable; prepara la decisión que sí lo hará.

Esta distinción importa: sin ella, una línea de documentación puede dar la sensación de progreso
mientras el producto no se mueve. Es el mismo error que se evitó al separar avance técnico de
Product Readiness al cerrar M1.

## Estado de M3 durante esta línea

**M3 está en espera de habilitadores externos, no bloqueado** (D35). La diferencia es material: un
milestone bloqueado señala un fallo del proyecto; uno en espera señala una dependencia externa
identificada y gestionada.

| Fase | Estado |
|---|---|
| M3.0 · Infraestructura de captura | ✅ Completada |
| M3.2a · Soberanía del modelo del usuario | ✅ Completada |
| M3.1 · Hogar real | ❄️ **Congelada** — requiere instalación real (D34) |
| M3.2b · Inferencia de preferencias | ❄️ **Congelada** — requiere datos de uso real |
| M3.3 · Anticipación · M3.4 · Avatar | ⏸ En espera |

## Documentos

| # | Documento | Temas de D35 que cubre |
|---|---|---|
| — | [Análisis de plataforma y modelo base](../entorno/ANALISIS-PLATAFORMA-OBJETIVO-R1.md) | **Hardware objetivo**, **modelo base** |
| 01 | [Requisitos y sistema operativo](01-requisitos-y-sistema-operativo.md) | **Requisitos mínimos y recomendados**, **SO recomendado** |
| 02 | [Estrategia de despliegue](02-estrategia-de-despliegue.md) | **Estrategia de despliegue** |
| 03 | [Costes, consumo y mantenimiento](03-costes-consumo-mantenimiento.md) | **Costes, consumo energético, mantenimiento** |
| 04 | [Conectores futuros](04-conectores-futuros.md) | **Arquitectura de conectores futuros** |

El análisis de plataforma es anterior a esta línea y **no se duplica aquí**. Léase con su aviso de
alcance: evalúa alternativas, no oficializa ninguna (D33).

## La decisión que desbloquea todo

Tres de las cinco fases de M3, la elección de hardware, la de modelo y la de sistema operativo
dependen de **una sola pregunta todavía sin responder**:

> **¿Dónde va a vivir AURA?** ¿Uso personal, instalación doméstica, distribución a terceros o
> producto comercial?

Es la razón de ser de esta línea. El documento 02 la aborda de frente, porque sin ella los otros
tres se quedan en comparativas sin criterio de decisión.

## Calidad de los datos

Se mantiene la convención del análisis de plataforma:

| Marca | Significado |
|---|---|
| **[medido]** | Medición propia con evidencia en el repositorio |
| **[terceros]** | Publicado por fuentes externas; orientativo, no verificado |
| **[cálculo]** | Derivado por aritmética a partir de requisitos de la Bible |

Ninguna decisión de compra debería apoyarse en un dato **[terceros]** sin verificarlo antes en el
equipo concreto.
