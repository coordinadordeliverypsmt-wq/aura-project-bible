# Changelog — AURA Project Bible

Versionado documental con [Semantic Versioning](https://semver.org/lang/es/). La v1.0.0 corresponderá a la Bible cerrada según el criterio del capítulo 1.1.

## [1.2.0] — 2026-07-18 — Auditoría del entorno + Entorno de Desarrollo v1.0

### Agregado
- **`entorno/AUDITORIA-ENTORNO.md`**: auditoría de los instaladores contra fuentes oficiales (PyPI/GitHub/sitios oficiales). Verificados los 6 paquetes (nombres correctos, sin sorpresas); nats-server ejecutado; corregido el mínimo real de Python a **3.11** (onnxruntime). Matriz automatizable-vs-manual por plataforma y riesgos con resolución (curl|sh, winget, voz Piper).
- **`entorno/ENTORNO-DE-DESARROLLO-v1.0.md`**: guía única para desarrolladores nuevos — por dependencia: instalar/actualizar/desinstalar/verificar; incompatibilidades entre plataformas y su resolución **sin tocar el código de AURA**; política de "cero sorpresas".
- `.gitattributes` (normalización de fin de línea LF/CRLF, incompatibilidad documentada).

### Cambiado
- requirements-stack.txt con versiones verificadas en PyPI (nats-py≥2.15, faster-whisper≥1.2, piper-tts≥1.5, qdrant-client≥1.18); Python ≥3.11.

### Estado
- HC-1: **Pendiente de validación en entorno objetivo** (D24). run_demo_real.py autorizado tras aprobación de esta auditoría del entorno.

## [1.1.0] — 2026-07-18 — Stack de producción local-first + transición del stack simulado

### Gobernanza
- **D24:** stack de validación y producción **local-first, open source, sin claves de terceros**; los modelos de nube (D2) quedan como recursos opcionales tras el router. **HC-1 = "Pendiente de validación en entorno objetivo"** (no fallido). Gestión proactiva de entorno. Análisis comparativo por ADR antes de adoptar componentes.

### Agregado
- **ADR-0010** (runtime LLM local = **Ollama**), **ADR-0011** (vectorial = Qdrant; pgvector alterno), **ADR-0012** (STT = faster-whisper), **ADR-0013** (TTS = Piper) — todos con análisis comparativo open source (6 criterios) y `accepted`.
- **`entorno/stack-produccion.md`**: stack oficial + requisitos mínimos por componente (CPU/RAM/almacenamiento/SO/deps) + descargas avisadas.
- **`entorno/scripts/`**: instaladores **Linux/macOS/Windows** (mismo código de AURA, solo cambia la preparación) + **verify-stack** (sh/ps1) que confirma servicios operativos antes del Walking Skeleton.
- **`entorno/HC-1-validacion.md`**: procedimiento reproducible para validar HC-1 en hardware objetivo, 100% local.

## [1.0.0] — 2026-07-18 — AURA PROJECT BIBLE v1.0 OFICIALMENTE CERRADA

### Hito mayor
- **La AURA Project Bible v1.0 queda oficialmente cerrada por el CEO.** Se cumple el criterio de cierre (1.1 §7): 36/36 capítulos aprobados, 10 ADRs aceptados, riesgos identificados, roadmap aprobado, Auditoría Técnica Integral **aprobada**.
- **Autorizada la transición de documentación a construcción**, comenzando por el **Walking Skeleton**.

### Correcciones de la auditoría (aprobadas por el CEO)
- **HC-1:** presupuesto de latencia reconciliado — R1 (nube) P50 ≤ 1200 ms; R2 (local) P50 ≤ 800 ms (2.5 v1.1.0, 6.2).
- **HI-1:** creado **ADR-0003** (Listas de Autonomía y HITL, accepted), consolidando la D4 como decisión arquitectónica permanente.
- **HM-1:** descripción de 2.1 en el índice actualizada a PIOS.
- Auditoría Técnica Integral marcada Aprobada.

## [0.17.0] — 2026-07-18 — CONTENIDO DE LA BIBLE v1.0 COMPLETO

### Hito mayor
- **Libros VI y VII COMPLETOS.** Con ello, **todo el contenido de la AURA Project Bible v1.0 está redactado y aprobado**: 36/36 capítulos (33 completos + 3 stubs), 9 ADRs aceptados, 2 Alertas resueltas, 23 decisiones del CEO.
- CEO Executive Summary de Libros V-VII generado (D17).

### Pendiente para cerrar la v1.0
- **Auditoría Técnica Integral** (CTO como auditor externo) sobre los 16 aspectos exigidos por el CEO → informe único → aprobación del CEO → autorización de construcción.

## [0.16.0] — 2026-07-18 — LIBRO V COMPLETO

### Hito
- **Libro V (Seguridad y Confianza) COMPLETO:** 5.1 Modelo de Amenazas, 5.2 Seguridad de IA (prompt injection), 5.3 Autonomía Gobernada (HITL/kill switch), 5.4 Identidad y Secretos, 5.5 Privacidad y Soberanía + 5.6 stub. Aprobados por el CTO (delegación D22). 26 capítulos aprobados + 1 stub.

## [0.15.0] — 2026-07-18 — LIBRO IV COMPLETO

### Hito
- **Libro IV (Cognición) COMPLETO:** 4.1 Memoria, 4.2 Orquestación, 4.3 Agentes y Tool Use, 4.4 Aprendizaje, 4.5 Módulo de Captura de Conocimiento — todos aprobados por el CTO (delegación D22). Progreso P1: 16/28. **21 capítulos aprobados** (5 P0 + 16 P1).
- CEO Executive Summary del Libro IV generado (acta D17).

## [0.14.0] — 2026-07-18

### Cambiado / Agregado
- **ALERTA-002 RESUELTA** (CEO): Alternativa A con precisión de **alcance de sesión** — identificación y atribución de participantes dentro de una sesión autorizada, sin perfil persistente de terceros entre sesiones. Guardrail **2.4 §5 precisado** (v1.1.0); capítulo 4.5 desbloqueado.
- **4.1 (Memoria a Largo Plazo) y 4.2 (Orquestación Multi-Modelo): APROBADOS por el CTO (delegación D22).** Ejecutan capacidades aprobadas sobre los contratos del Libro III y el stack (ADR-0007/0008). Progreso P1: 13/28.

## [0.13.0] — 2026-07-18

### Hito
- **Libro III COMPLETO** (3.1-3.6 aprobados). Stack oficial nivel Balanceado. Progreso P1: 11/28 (+3.6).

### Agregado / Cambiado
- **ADR-0005..0009 `accepted`** (stack, decisión del CEO): Python (con Alerta requerida para otros lenguajes), NATS local, SQLite/PostgreSQL + Qdrant, Whisper+Piper locales (nube solo contingencia), Live2D.
- **3.6 APROBADO por el CEO** (v1.0.0), nivel Balanceado como estándar oficial.
- **D22 refinada + D23:** el CEO fija que solo se elevan a su aprobación decisiones tecnológicas reservadas, cambios de alcance, guardrails éticos, Alertas y riesgos de largo plazo.
- **D23 — Módulo de Captura de Conocimiento** como 10ª capacidad oficial (capítulo 4.5) y **cierre del alcance funcional** de la versión inicial. 2.2 enmendado a v1.1.0.

### Alerta de Arquitectura
- **ALERTA-002 (D15/D16):** el CTO elevó que la captura de reuniones/llamadas con terceros choca con el guardrail de no-vigilancia (2.4 §5) y con la ley de consentimiento; recomienda la Alternativa A (conocimiento centrado en el usuario, terceros no perfilados, + atestación de consentimiento HITL + revisión legal). Diseño del 4.5 suspendido hasta el gate extraordinario del CEO.

## [0.12.0] — 2026-07-18

### Gobernanza
- **D22 — Fase de ejecución:** ejecutar la arquitectura aprobada sin cambios de alcance (salvo Alerta de Arquitectura justificada); el CEO **delega en el CTO la aprobación de capítulos de ejecución** (criterio: sin cambio de alcance, respeto de decisiones previas, cinco preguntas D21). Reservadas al CEO: tecnología con alternativas (D3), guardrails éticos, decisiones de rango 1 y Alertas. Enmienda 1.1 v1.4.0.

### Cambiado / Agregado
- **3.2 APROBADO por el CEO** (v1.0.0), incorporado como parte oficial de la Bible.
- **3.3 Núcleo Event-Driven, 3.4 Plugins y Adaptadores, 3.5 Modelo de Datos: APROBADOS por el CTO (delegación D22)** — ejecutan los contratos del 3.2 sin cambio de alcance. Progreso P1: 10/28.
- **3.6 Selección de Stack Tecnológico** ELEVADO AL CEO (materia reservada D3): 5 decisiones de stack en 4 niveles + **ADR-0005 (lenguaje/runtime, proposed)** como ancla.

## [0.11.0] — 2026-07-18

### Cambiado
- **Capítulo 2.5 APROBADO por el CEO** (v1.0.0): los umbrales del PIOS (latencia de voz P50≤800ms/P95≤1500ms, memoria ≥4 semanas/≥90% recall, anticipación ≥1/día y ≤20% FP, consistencia inter-modelo ≥90%, HITL tolerancia cero) quedan **ratificados como objetivos oficiales**. Progreso P1: 6/28.

### Agregado
- **Capítulo 3.2 (Arquitectura de Referencia C4)** en gate: vistas C4 de contexto y contenedores del PIOS, Event Bus como plano de control + canales de streaming (ALERTA-001), núcleo mínimo con memoria como módulo, capas percepción/cognición/acción, topología local-first y estructura multi-usuario-ready. Desbloquea 3.3/3.4/3.5 al aprobarse.

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
