---
documento: "Aprobación de D-M-7 — Opción A (clasificación de intención)"
tipo: "Registro de decisión del CEO"
fecha: 2026-09-09
mantenido-por: "APUS-5 (CTO)"
decide: "CEO (Mauricio)"
sobre: "milestones/m3-entry/DP-D-M-7-CLASIFICACION-DE-INTENCION.md"
---

# D-M-7 — Aprobación de la Opción A

## Origen de esta anotación

**Fuente: aprobación explícita del CEO, dada en la sesión de trabajo del 2026-09-09.** No existe
acta anterior. Este fichero **no** documenta una aprobación previa que se hubiera perdido: registra la
que se acaba de dar, en el momento en que se dio, y esa es toda su autoridad.

El Decision Package `DP-D-M-7` **no se ha modificado**. Su historia queda como estaba: dos commits del
2026-08-03 y un estado escrito de «propuesta, pendiente de aprobación del CEO», que fue cierto hasta
hoy. Reescribirlo para que dijera otra cosa sería fabricar un pasado.

## Alcance aprobado — Opción A

1. **Taxonomía de dos ejes ortogonales.**
   - Eje 1 · acto de habla: `CORRECCION`, `ORDEN`, `PREGUNTA`, `SOCIAL`, `AFIRMACION`.
   - Eje 2 · contenido proposicional: `HECHO_USUARIO`, `CONOCIMIENTO_PROCEDURAL`,
     `COMPROMISO_FUTURO`, `REGLA_CONDICIONAL`, `NADA_PROPOSICIONAL`, `INCIERTO`.
2. **M-1** como mecanismo: clasificador único **determinista**. Quedan descartados M-2, M-3
   (prohibido por `ADR-0014` §2), M-4 y M-5.
3. **Eje 2 conservador**: ante duda, **no almacenar**. El fallo seguro es perder recall, nunca
   fabricar.
4. **`PREGUNTA` ratificado como acto del eje 1**, y con él la protección de `ADR-0014`.
5. **No unificar clasificadores sin red de seguridad y regresión.**
6. **Medir** latencia, cobertura y conservación de la garantía anti-fabricación.
7. **M-1 precede** a cualquier clasificador táctico posterior, incluida la propuesta F
   (superficie cognitiva positiva y cerrada).

## Lo que esta aprobación NO concede

Aprobar un diseño no es autorizar obra. Esta decisión **no** autoriza modificar `ADR-0014`, la Bible,
la política ni `CLAUDE.md`; **no** amplía permisos, autoridad ni territorio de AURA; **no** habilita
razonamiento, hipótesis ni conversación libre; y **no** resuelve `ALERTA-006` ni `D-INT-1`, que siguen
requiriendo decisión propia.

## Trazabilidad

- Diseño: `milestones/m3-entry/DP-D-M-7-CLASIFICACION-DE-INTENCION.md` (sin modificar).
- Implementación: `walking-skeleton/aura_skeleton/core/intencion.py`.
- Garantías: `walking-skeleton/tests/unit/test_m1_clasificacion_intencion.py`.
- Restricción vigente: `ADR-0014` §2 y §4 — la clasificación es determinista y no se delega en el LLM.
- Checkpoint de referencia: `56cfe230badad4c997bb16638442446c06cbe8c0`.
