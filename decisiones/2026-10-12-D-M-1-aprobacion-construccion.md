---
documento: "Aprobación de construcción de D-M-1 A′ (recuperación exacta de memoria N1)"
tipo: "Registro de decisión del CEO"
fecha: 2026-10-12
mantenido-por: "Dirección Técnica (sesión de asistencia)"
decide: "CEO (Mauricio)"
sobre: "milestones/m3-entry/DP-D-M-1-RECUPERACION-EXACTA.md · DECISION-REQUERIDA-D-M-1-RECUPERACION-EXACTA.md"
---

# D-M-1 A′ — aprobación de construcción

**Fuente:** autorización explícita del CEO en esta sesión (2026-10-12): «AUTORIZACIÓN DE EJECUCIÓN
INTEGRAL … autorizo proceder … ejecutar D-M-1 A′». Precondición **D-M-2 resuelta** (verificado:
`intencion.py:548`, `test_correcciones_producto.py:65-105`). Se registra la decisión emitida.

## Alcance aprobado (A′, del DP)
- Sustituir la generación de candidatos de `PersistentMemory.recall` por **filtro por prefijo con cota de
  seguridad α=1**: ordenar términos por longitud de posteo ascendente, unir las `(n−m+1)` listas más
  cortas (exacto por el principio del palomar); si `Σ|listas| > α·N`, **barrido completo** (también
  exacto). Ambas ramas exactas → A′ exacta sea cual sea la rama.
- **Intactos:** `_COBERTURA_MINIMA`, tokenización, palabras vacías, criterio de aceptación. Cambia **qué
  recuerdos se examinan**, nunca cuáles se aceptan. Formato persistido sin migración.
- Respeta ADR-0014 (lo refuerza), MA.2a (A′ nunca visita más que el barrido completo), determinismo.

## Límite declarado (no se finge)
El DP (§2.4, §7.2) registra que **el defecto no se ha observado en uso real** («cero en uso real»). La
autorización permite construir; **no convierte evidencia ausente en positiva**. Se construye la corrección
exacta y se deja la observación real como pendiente de telemetría futura.

## NO concede
Tocar `_COBERTURA_MINIMA`/tokenización/criterio; `SemanticMemory`/D-N2-5; ampliar el MVP (D23); M3.2b,
CM2, S3; `~/.aura`; commit/push/merge. Si hiciera falta cambiar una decisión arquitectónica, detenerse.
