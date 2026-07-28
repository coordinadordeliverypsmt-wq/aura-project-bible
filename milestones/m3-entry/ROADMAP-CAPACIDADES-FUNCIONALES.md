---
documento: "Roadmap de capacidades funcionales (orden de prioridad)"
fecha: 2026-07-28
autor: "CTO / Director"
origen: "Orden de prioridades fijado por el CEO (2026-07-28), tras cerrar N2"
estado: "VIGENTE. Fija el orden de las capacidades funcionales. Sustituye, en lo relativo al ORDEN de capacidades, al reordenamiento del 2026-07-21 (ROADMAP-M3-REORDENADO.md), que sigue vigente en su análisis de bloqueos por hardware/D34."
base: "main @ 1c80185b"
---

# Roadmap de capacidades funcionales

Orden de inversión fijado por el CEO el 2026-07-28. Cada capacidad se implementa bajo la disciplina
estándar: Decision Package aprobado → (preparación de entorno si aplica) → TDD RED→GREEN→mutación→Quality
Gate → auditoría → cierre. Método de análisis: D47.

| # | Capacidad | Qué valida / aporta | Estado |
|---|---|---|---|
| **1** | **N2 · Memoria Semántica** | Valida **RECURSO → Materialización**: el Plan de Activación gobierna una materialización real (N1 léxico / N2 semántico por perfil). Cierra el defecto E1 (delta observable 0). | ✅ **COMPLETADA Y CERRADA** (2026-07-28, `e4a502e` / `1c80185b`). Quality Gate PASS 386/3. |
| **2** | **Centro de Notificaciones** | Proactividad: AURA deja de ser solo reactiva y puede avisar al usuario. Personalidad definitoria del PIOS (D2.6). Construido y probado; **no cableado**. | ⏭ **Siguiente** (pendiente de Decision Package). |
| **3** | **Modelo de Usuario** | Soberanía y personalización: ver/corregir/borrar lo que AURA cree saber (ADR-0017). Construido y probado; **no cableado**. **Defecto de borrado conocido** a corregir antes de cablear. | Pendiente. |
| **4** | **Voz** | Valida la mitad **SOPORTE** del modelo (detector de entorno → contexto). Rama ACTIVA no viable en el hardware actual (TTS ≫ presupuesto). | Pendiente **de hardware** que permita validar SOPORTE. |
| **5** | **Resto del MVP** | Automatización avanzada, captura de conocimiento (4.5, ALERTA-002 resuelta), avatar, aprendizaje continuo, inferencia real. | Pendiente; varios bloqueados por hardware/servicios (ver ROADMAP-M3-REORDENADO §1). |

## Nota sobre N2: deuda de producto diferida (registrada, no bloqueante)

N2 quedó cerrada validando la **arquitectura** (el plan gobierna la materialización). Su **calidad de
producto en español NO forma parte de ese cierre**: el embedder disponible (`all-MiniLM`) es débil en
español (margen semántico −0.074, medido). Por decisión del CEO, la mejora de calidad multilingüe es
**seguimiento de producto**, registrado como deuda en `DEUDA-N2-MEMORIA-SEMANTICA.md` y reevaluable antes
de escalar la memoria semántica. Su eventual ejecución (embedder multilingüe + validación de recall en
español) sería una **fase de producto de N2**, distinta de las capacidades 2–5, y requeriría su propio
Decision Package.

## Restricción transversal vigente

Presupuesto de hardware cero; congelación selectiva (D34): no se fabrican entornos para aprobar hitos. Las
capacidades cuya validación depende objetivamente de hardware/servicios ausentes (voz en tiempo real,
inferencia real, hogar) permanecen **previstas y pospuestas**, no canceladas — se activan cuando el entorno
lo permita, sin bifurcar el código (principio de capacidad latente).
