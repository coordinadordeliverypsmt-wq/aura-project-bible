---
documento: "Roadmap de capacidades funcionales (orden de prioridad)"
fecha: 2026-07-28
autor: "CTO / Director"
origen: "Orden de prioridades fijado por el CEO (2026-07-28), tras cerrar N2"
estado: "VIGENTE. Fija el orden de las capacidades funcionales. Sustituye, en lo relativo al ORDEN de capacidades, al reordenamiento del 2026-07-21 (ROADMAP-M3-REORDENADO.md), que sigue vigente en su análisis de bloqueos por hardware/D34."
base: "main @ b0a4e33 (estado verificado 2026-08-02)"
---

# Roadmap de capacidades funcionales

Orden de inversión fijado por el CEO el 2026-07-28. Cada capacidad se implementa bajo la disciplina
estándar: Decision Package aprobado → (preparación de entorno si aplica) → TDD RED→GREEN→mutación→Quality
Gate → auditoría → cierre. Método de análisis: D47. Estándar de trabajo:
`decisiones/2026-07-28-estandar-de-trabajo-producto-demostrable.md`.

## Dos tipos de trabajo (regla del CEO, 2026-07-28)

- **Incrementos de CAPACIDAD:** añaden algo que AURA antes no podía hacer, con **conversación propia** que
  se explica por sí sola. Es lo que se construye **primero**.
- **Incrementos de INTEGRACIÓN:** hacen que capacidades ya existentes **colaboren** entre sí (p. ej.
  "notificaciones que respetan el Modelo de Usuario").

**Disciplina de orden:** primero se completan las capacidades base del MVP; la **fase de integración no se
abre** hasta que todas existan. Los cuatro incrementos cerrados (N2, Notificaciones, Modelo de Usuario,
Automatización) son de capacidad.

Esa condición es **necesaria, no suficiente**: agotar las capacidades construibles no abre la integración
por sí solo. El cambio de fase es siempre una **decisión explícita del CEO** (ver §Estado del MVP).

## Estado del MVP (evidencia: Bible 2.2 §capacidades; ROADMAP-M3-REORDENADO §1)

| Cap. MVP (D2) | Estado | Bloqueo |
|---|---|---|
| 1 · Memoria permanente | ✅ **N1** (léxico). **N2 construida pero NO se materializa** en este equipo | RAM 3,6 GB < umbral 8 GB, y no existe detector de hardware real |
| 4 · Control del computador | ✅ (archivos) | — |
| 9 · Centro de notificaciones | ✅ | — |
| 8 · Aprendizaje — soberanía (M3.2a) | ✅ (Modelo de Usuario) | — |
| **5 · Automatización definida por el usuario** | ✅ (MVP: crear, persistir, ejecutar, inspeccionar) | — |
| 2 · Voz | ⬜ | **hardware, medido 2026-08-02**: TTS 15,3 s · STT 15,2 s (+31,4 s de carga) vs 1200 ms |
| 3 · Avatar | ⬜ | plataforma de despliegue (D33) |
| 6 · Multi-modelo (LLM) | ⬜ | **hardware, medido 2026-08-02**: `qwen2.5:0.5b` tarda 25,8 s en «Hola» y no completa un prompt real. Sin claves de terceros (D24) |
| 7 · Hogar | ⬜ | HA ausente (D34). **El adaptador mock afirma acciones que no ejecuta** — deuda `D-ADP-1` |
| 8 · Aprendizaje — inferencia (M3.2b) | ⬜ | datos de uso real |

**Situación tras cerrar la #5:** las capacidades base restantes (voz, avatar, multi-modelo, hogar,
inferencia) dependen de hardware o servicios ausentes.

**Decisión del CEO (2026-08-02): la fase de integración NO se abre.** Haber completado la última capacidad
demostrable **no implica cambiar de fase automáticamente**; abrir la integración por descarte sería dejar
que la ausencia de alternativas decida por el proyecto. El siguiente paso se resolverá en una **revisión
del roadmap completo**, como decisión independiente y posterior al cierre de este incremento, ponderando
hardware disponible, dependencias y valor para el producto.

Hasta esa revisión, **ningún incremento de integración está autorizado**.

| # | Capacidad | Qué valida / aporta | Estado |
|---|---|---|---|
| **1** | **N2 · Memoria Semántica** | Valida **RECURSO → Materialización**: el Plan de Activación gobierna una materialización real (N1 léxico / N2 semántico por perfil). Cierra el defecto E1 (delta observable 0). | ✅ **COMPLETADA Y CERRADA** (2026-07-28, `e4a502e` / `1c80185b`). Quality Gate PASS 386/3. |
| **2** | **Centro de Notificaciones** | Proactividad: AURA cuenta en lenguaje natural lo que ha hecho («¿qué ha pasado mientras no estaba?»). Personalidad definitoria del PIOS (D2.6). | ✅ **COMPLETADA Y CERRADA** (2026-07-28, `964e2ee`). Cableado verificado en el arranque real. |
| **3** | **Modelo de Usuario** | Soberanía: el usuario inspecciona, entiende, corrige y **olvida de forma persistente** lo que AURA sabe de él (ADR-0017). El defecto de borrado se corrigió antes del cierre. | ✅ **COMPLETADA Y CERRADA** (2026-07-28, `e73cbb6`). Olvido verificado tras reinicio. |
| **4** | **Voz** | Valida la mitad **SOPORTE** del modelo (detector de entorno → contexto). | ⏸ **CONGELADA por hardware** (CEO, 2026-08-02). Medido en este equipo: TTS Piper **15,3 s** una frase · STT Whisper **15,2 s** para 5 s de audio, con transcripción errónea. Presupuesto: 1200 ms. |
| **5** | **Automatización definida por el usuario** | AURA deja de ser **turno a turno**: el usuario le enseña una conducta permanente y AURA la conserva y la aplica sola. Es la primera capacidad cuyo valor **solo existe si sobrevive al reinicio**. | ✅ **COMPLETADA Y CERRADA** (2026-08-02). Quality Gate PASS 427/3; mutación 10/10. |
| **6** | **Resto del MVP** | Captura de conocimiento (4.5, ALERTA-002 resuelta), avatar, aprendizaje continuo, inferencia real, automatización avanzada. | Pendiente; la mayoría **congelada por hardware** (CEO, 2026-08-02). Ver ROADMAP-M3-REORDENADO §1. |

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
