# Changelog — AURA Project Bible

Versionado documental con [Semantic Versioning](https://semver.org/lang/es/). La v1.0.0 corresponderá a la Bible cerrada según el criterio del capítulo 1.1.

## [0.5.0] — 2026-07-17

### Cambiado
- **Capítulo 2.1 APROBADO por el CEO** (v1.0.0) — tercer capítulo P0 aprobado.
- Capítulo 2.2 (Alcance del MVP y Roadmap) en borrador: 9 capacidades D2, hitos M1-M3, exclusiones y releases R2-R4; a revisión adversarial.
- Publicación HTML/PDF regenerada (incluye 2.1).

## [0.4.0] — 2026-07-17

### Agregado
- Acta v1.2.0: **D11** (matriz de impacto obligatoria en ADRs), **D12** (modo de trabajo documental: archivos + PDF/HTML al aprobar, terminal solo resúmenes) y **D13** (estructura estándar de capítulo legible por humanos e IA).
- `herramientas/publicar.py`: generación automática de HTML navegable y PDF de los documentos aprobados (`publicado/`).

### Cambiado
- **Capítulo 1.2 APROBADO por el CEO** (v1.1.0, incluye matriz D11).
- **ADR-0001 `accepted`** con las 2 reglas adicionales del CTO aceptadas expresamente; incorpora matriz de impacto D11.
- Estructura estándar D13 aplicada a los 36 capítulos (resumen ejecutivo, decisiones, riesgos, próximos pasos, referencias cruzadas); los 7 capítulos impactados por el ADR-0001 lo listan en "Decisiones aplicables".

## [0.3.1] — 2026-07-17

### Cambiado
- Capítulo 1.2 v0.3.0, plantilla de ADR y ADR-0001: incorporan las 20 correcciones de la segunda revisión adversarial — inmutabilidad decisional precisada, estados `withdrawn`/re-propuesta, campos `fecha-resolucion`/`motivo-rechazo`/`reabre`, regla de oro anclada a commits, regla transitoria para capítulos inexistentes, excepción de enmienda constitucional, verificación por evento, D3/D9 incorporadas al plan de formalización, y ADR-0001 separa el texto literal de la D1 de las reglas adicionales del CTO. El 1.2 pasa a "En revisión (gate del CEO)".

## [0.3.0] — 2026-07-17

### Agregado
- Acta fundacional v1.1.0: **D10 — Filosofía de Desarrollo** (sistema vivo: modularidad obligatoria, sin monolitos, inteligencia desacoplada, compatibilidad hacia atrás).
- Capítulo 1.2 (Sistema de ADRs) en borrador: criterios de obligatoriedad, ciclo de vida, regla de oro operativa y plan de formalización de decisiones.
- Plantilla oficial de ADR y **ADR-0001 — Arquitectura local-first estricta** (`proposed`, origen acta D1).

### Cambiado
- **Capítulo 1.1 APROBADO por el CEO** (v1.0.0) — primer documento normativo aprobado de la Bible.
- 3.1: contenido previsto incorpora la filosofía de sistema vivo (D10).

## [0.2.1] — 2026-07-17

### Agregado
- Registro del Brief Fundacional del CEO (2026-07-16) como documento vinculante de rango 1.

### Cambiado
- Capítulo 1.1 v0.3.0: incorpora las 20 correcciones de la revisión adversarial interna (2 críticos, veredicto "aprobar con correcciones"): relación actas↔constitución, clases de artefactos normativos/operativos, reglas para conflictos entre borradores, regla de gates pendientes, veto técnico precisado, regla verificable de uso de Opus, RACI corregida, autoridad por transición de estados y criterio de cierre separado en mínimo del acta D7 + desarrollos del CTO. Pasa a estado "En revisión (gate del CEO)".

## [0.2.0] — 2026-07-17

### Agregado
- Esqueleto completo de la Bible: 7 libros, 36 capítulos con frontmatter (versión, autor, fecha, estado, prioridad, responsable, dependencias, historial).
- Índice maestro v0.2 (post-decisiones del CEO): 5 P0 · 28 P1 · 1 P2 · 2 P3 · 3 stubs.
- Acta de decisiones fundacionales del CEO (2026-07-17) — vinculante.
- Estructura de ADRs (plantilla pendiente del capítulo 1.2).
- Primer borrador del capítulo 1.1 (Constitución del Proyecto, Roles y Autoridad) — en revisión.

### Cambiado (respecto al índice v0.1 propuesto)
- Capítulos 4.4, 6.2, 6.3, 6.4 y 6.5 suben a P1 completo (el MVP del CEO incluye avatar, aprendizaje continuo, voz, hogar y control del computador).
- 6.4 incorpora el Centro único de notificaciones.
- 3.1 incorpora el principio obligatorio Human-in-the-Loop, la postura local-first estricta y el requisito multi-usuario-ready.
- 5.3 incorpora las listas verde/roja de autonomía decididas por el CEO.
- 1.5 y 3.6 incorporan el formato de alternativas en 4 niveles (Económica/Balanceada/Profesional/Enterprise).

## [0.1.0] — 2026-07-16

### Agregado
- Propuesta de índice sintetizada por panel multi-agente (5 arquitectos + 2 críticos adversariales), presentada al CEO.
