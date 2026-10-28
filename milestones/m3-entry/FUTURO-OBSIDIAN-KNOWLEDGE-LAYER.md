---
documento: "FUTURO — Obsidian / Knowledge Layer"
tipo: "Nota de intención (NO es un Decision Package, NO está aprobado)"
estado: "ANOTADO por instrucción del CEO (2026-09-09). NADA integrado, NADA instalado, NADA decidido."
fecha: 2026-09-09
---

# FUTURO: OBSIDIAN / KNOWLEDGE LAYER

**Instrucción literal del CEO en la misión de cognición local:** no integrar Obsidian, no instalar
plugins, **solo dejarlo documentado**. Esta nota existe para cumplir eso y para nada más.

## Qué se anota

La idea de una **capa de conocimiento** navegable (notas enlazadas, estilo Obsidian) sobre lo que AURA
sabe, distinta de la memoria personal del Core.

## Lo que esta nota NO autoriza

- No autoriza instalar Obsidian ni ningún plugin.
- No autoriza leer ni escribir una bóveda de notas desde AURA.
- No autoriza una capacidad nueva: el alcance del MVP está cerrado (`D23`).
- No autoriza ampliar la autoridad del LLM ni crear una segunda ruta a la memoria.

## La frontera que cualquier diseño futuro tendría que respetar

1. **El Core sigue siendo la única autoridad sobre los hechos del usuario** (`ADR-0014`). Una capa de
   conocimiento es material de lectura, no una fuente de verdad sobre la persona.
2. **Una bóveda de notas es disco, y el disco tiene una sola puerta**: `G-1` (ruta única de mutación)
   obliga a que cualquier escritura pase por el motor, con permisos y auditoría.
3. **Local-first, sin claves de terceros** (`D24` / `ADR-0001`): ninguna sincronización de pago.
4. **Nada de esto nace de una idea, sino de evidencia de uso repetido** (CEO 2026-08-04): si no hay un
   bloqueo observado en la operación diaria, no entra en la hoja de ruta.

## Condición para promoverlo

Un Decision Package con un bloqueo real observado y registrado en `PLAN-DE-FORMACION-AURORA.md`. Hasta
entonces, esto es una observación técnica, no deuda.
