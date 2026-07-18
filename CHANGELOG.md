# Changelog — AURA Project Bible

Versionado documental con [Semantic Versioning](https://semver.org/lang/es/). La v1.0.0 corresponderá a la Bible cerrada según el criterio del capítulo 1.1.

## [0.10.0] — 2026-07-18

### Hito
- **Ola 1 de la Fase D2 APROBADA por el CEO:** capítulos 1.3, 1.4, 1.5, 2.3 y 2.4 (v1.0.0). Progreso P1: 5/28.

### Agregado (actas)
- **D18 — AURA es un Sistema Operativo de Inteligencia Personal (PIOS)**: no un asistente virtual. Redefinición primaria del producto.
- **D19 — Naturaleza:** personal de largo plazo con arquitectura comercial-escalable y desacoplada (resuelve 1.5 §5).
- **D20 — Horizonte mínimo de 10 años** en toda decisión de arquitectura.
- **D21 — Cinco preguntas de largo plazo**; si alguna es negativa, el CTO genera una Alerta de Arquitectura.

### Cambiado (enmiendas)
- **2.1 → v2.0.0 (enmienda MAYOR por D18):** definición primaria = PIOS; "compañero cognitivo" pasa a cara experiencial; anti-visión añade "no es un asistente virtual"; horizontes reencuadrados como madurez del PIOS. Título → "Definición, Visión, Misión y Anti-Visión".
- **3.1 → v1.2.0:** nueva §2.5 con el horizonte de 10 años (D20) y las cinco preguntas de largo plazo (D21).
- **1.5:** §5 resuelta con D19 (default prudente permanente).
- **ADR-0002 `accepted`:** MkDocs Material como estándar documental (criterios del CEO).

## [0.9.0] — 2026-07-18

### Agregado
- **Fase D2, ola 1 — 5 capítulos P1 redactados y revisados**, en gate del CEO: 1.3 (Proceso de Trabajo por Fases), 1.4 (Estándares Documentales + glosario + plantillas), 1.5 (Restricciones de Negocio: Presupuesto/Legal), 2.3 (Usuario y Escenarios Prioritarios), 2.4 (Personalidad, Ética y Límites).
- **ADR-0002 — Plataforma de generación del sitio documental** (`proposed`, origen D8+D12): 4 opciones de nivel (D3); recomendación del CTO = MkDocs Material (nivel Balanceado).

### Proceso
- La redacción se hizo con el pipeline de agentes; la fase de crítica automatizada no completó por límite de sesión. La **revisión pre-gate la realizó el CTO (Fable)**, revisor distinto del redactor (Sonnet), conforme a 1.1 §4.2. Los 5 capítulos pasan a "En revisión (gate del CEO)".

## [0.8.0] — 2026-07-17

### Agregado
- Acta v1.4.0: **D16** (estructura obligatoria de 10 secciones para toda Alerta de Arquitectura) y **D17** (CEO Executive Summary por fase).
- **CEO Executive Summary de la Fase D1** (`resumenes-ejecutivos/`).
- Plantilla obligatoria de Alerta de Arquitectura (`decisiones/alertas/plantilla-alerta.md`).

### Cambiado
- **ALERTA-001 RESUELTA — Opción A** aprobada por el CEO: Event Bus como plano de control; streams de voz/video/pantalla/sensores por canales dedicados de baja latencia; correlación por Correlation ID / Trace ID.
- **Paquete P-002 aplicado (11 correcciones, autorizado por el CEO):** capítulo 3.1 v1.1.0 (bus como plano de control, memoria fuera del núcleo, jerarquía de principios acotada, P-ARQ-7 sujeta a ADR-0001, P-ARQ-8 fiel a D7, checklist +3 preguntas) y **ADR-0004 enmendado** (3 cláusulas D10 restituidas, regla 13 versión fuerte, regla 11 con política de deprecación).
- Constitución 1.1 v1.3.0: enmienda D16 (estructura de alertas).

## [0.7.1] — 2026-07-17

### Agregado
- **ALERTA-001** (mecanismo D15): incompatibilidad bus-de-eventos vs streams de voz/avatar — gate extraordinario convocado; diseño de 3.3/6.2/6.5 suspendido preventivamente.
- P-002: paquete de 11 correcciones al 3.1 y al ADR-0004 (revisión adversarial post-aprobación), pendiente de autorización del CEO.

## [0.7.0] — 2026-07-17 — FASE D1 COMPLETA

### Hito
- **Los 5 capítulos P0 están Aprobados** (1.1, 1.2, 2.1, 2.2, 3.1): la fundación de la Bible queda cerrada. Inicia la Fase D2 (28 capítulos P1 según el grafo de dependencias).

### Cambiado
- **Capítulo 3.1 APROBADO por el CEO** (v1.0.0) — quinto gate.
- **ADR-0004 `accepted`** con las 3 reglas operativas del CTO aceptadas expresamente.
- Enmienda constitucional 1.1 v1.2.0 (deber de disenso, D15) **ratificada por el CEO**.

## [0.6.0] — 2026-07-17

### Agregado
- Acta v1.3.0: **D14** (Evolución Permanente) y **D15** (deber de disenso y Alerta de Arquitectura del CTO).
- **ADR-0004 — Principio de Evolución Permanente y arquitectura modular** (`proposed`, origen D10+D14), con 3 reglas operativas del CTO incluida la salvaguarda anti-sobre-ingeniería.
- Mecanismo de Alerta de Arquitectura en la constitución (`decisiones/alertas/`).

### Cambiado
- **Capítulo 2.2 APROBADO por el CEO** (v1.0.0, 6 propuestas † ratificadas); AR reubicada al Backlog R5/Investigación.
- Constitución 1.1 v1.2.0: enmienda D15 (deber de disenso del CTO) — redacción sujeta a ratificación.

## [0.5.2] — 2026-07-17

### Cambiado
- Capítulo 2.2 v0.3.0: incorpora las 19 correcciones de su revisión adversarial — convención † en la tabla de capacidades, gate de hito con autoridad exclusiva del CEO, circuito de fracaso anclado a D3/actas, regla de la ventana con registro automático y pausas/reinicios, exclusiones binarias por sistema (control + notificaciones), capacidad 5 sin sugerencias hasta M3, criterios R2-R4 como marco, supuestos de entorno validables por el inventario del 2.3, y fine-tuning fuera del roadmap actual (no para siempre). Pasa a "En revisión (gate del CEO)".

## [0.5.1] — 2026-07-17

### Cambiado
- Capítulo 2.1 v1.1.0: aplicadas las 8 correcciones de P-001, **ratificadas por el CEO** — momento mágico citado textualmente de la D2, convención † para desarrollos del CTO, criterios-marco con umbrales delegados a 2.5, zona intermedia adjudicada por el CEO, límites verificables de vigilancia/afecto remitidos a 2.4 y Libro V, "ningún proveedor único", visión de largo plazo condicionada a apertura de terceros.
- P-001 cerrado en decisiones/pendientes.md.

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
