---
documento: "Acta de Decisiones Fundacionales"
version: 1.0.0
autor: "Mauricio (CEO) — registrada por Fable (CTO)"
fecha: 2026-07-17
estado: "Vinculante"
historial:
  - version: 1.0.0
    fecha: 2026-07-17
    cambio: "Registro de las 8 decisiones fundacionales + principio adicional y autorización de Fase D1"
---

# Acta de Decisiones Fundacionales — 2026-07-17

El CEO ratificó el método de trabajo y el índice de la Bible (v0.1 → v0.2), y resolvió las 8 decisiones abiertas. Estas decisiones son **vinculantes**: prevalecen sobre cualquier capítulo y se formalizarán como ADRs una vez aprobado el capítulo 1.2.

## D1 — Postura de datos: local-first estricto

Toda la información personal, memoria, documentos, fotografías, credenciales, dispositivos, automatizaciones y datos privados permanecerán **siempre bajo control del usuario**. La nube solo podrá utilizarse para: (a) consultar modelos de IA, (b) sincronizar información previamente autorizada, (c) respaldos cifrados, (d) servicios externos explícitamente aprobados. Toda comunicación deberá estar cifrada. La privacidad es un pilar fundamental de AURA.
*Impacta: 3.1 (será ADR-0001), 5.5, 4.1, 4.2.*

## D2 — Alcance del MVP

El MVP debe demostrar que AURA es un compañero inteligente, no otro asistente. Capacidades mínimas (9):
memoria permanente · conversación natural por voz · avatar interactivo · control básico del computador · automatización de tareas · integración con ChatGPT, Claude y Gemini · control básico del hogar inteligente · aprendizaje continuo · centro único de notificaciones.

**Momento mágico:** mantener conversaciones naturales, recordar semanas después cualquier tema tratado, ejecutar acciones reales y anticiparse a las necesidades del usuario.

*Nota del CTO (aceptada la decisión):* es el MVP más ambicioso de los evaluados por el panel; para gobernar el riesgo de alcance se estructurará en hitos internos — **M1** núcleo conversacional (memoria + voz + 3 LLMs), **M2** manos digitales (computador + automatización + notificaciones), **M3** presencia (hogar + avatar + aprendizaje/anticipación) — detallados en el capítulo 2.2.
*Impacta: 2.2; sube a P1 completo los capítulos 4.4, 6.2, 6.3, 6.4 y 6.5.*

## D3 — Presupuesto

Sin límite presupuestal inicial. Toda decisión técnica prioriza **calidad y escalabilidad**. Cuando existan alternativas, se presentarán siempre en 4 niveles — **Económica · Balanceada · Profesional · Enterprise** — y el CEO decidirá cuál implementar.
*Impacta: 1.5, 3.6 y todo ADR con alternativas.*

## D4 — Nivel inicial de autonomía

AURA ejecuta automáticamente **solo acciones de bajo riesgo**: automatizaciones, encender/apagar dispositivos, consultas, recordatorios, monitoreo, organización.

Requiere autorización **siempre**: pagos, compras, transferencias, eliminación de información, apertura de cerraduras, mensajes enviados a terceros, acciones legales, acciones financieras.

Conforme aumente la confianza podrán habilitarse niveles superiores mediante políticas.
*Impacta: 5.3 (listas verde/roja), 4.3.*

## D5 — Multiusuario

La versión inicial es para un único usuario (**Mauricio**). La arquitectura se diseña desde el inicio preparada para múltiples usuarios: cada usuario tendrá identidad, memoria, permisos, automatizaciones y preferencias completamente independientes.
*Impacta: 3.1, 5.4, 4.1.*

## D6 — Identidad de AURA

Nombre: **AURA**. Naturaleza: compañero de Inteligencia Artificial. Personalidad: profesional, cercana, proactiva, honesta, crítica cuando sea necesario, **jamás aduladora**. Siempre dirá la verdad aunque contradiga las ideas del usuario; no intentará complacer si considera que existe una mejor alternativa. Un compañero de confianza, no un asistente sumiso.
*Impacta: 2.4 (system prompt maestro).*

## D7 — Criterio de cierre de la Bible v1.0

Ratificado. No comenzará una sola línea de código hasta que: P0 aprobado · P1 aprobado · arquitectura validada · riesgos identificados · roadmap aprobado · ADRs principales documentados.
*Impacta: 1.1 (sección "Criterio de cierre").*

## D8 — Plataforma documental

Aprobado **Git + Markdown**. Toda la documentación vive en el repositorio. Versionado con Semantic Versioning. Cada documento lleva: versión, autor, fecha, estado e historial de cambios. La documentación deberá poder convertirse automáticamente en sitio web con **MkDocs Material o Docusaurus** (elección pendiente — se resolverá vía ADR con las 4 opciones de nivel).
*Impacta: 1.4.*

## D9 (adicional) — Principio obligatorio: Human in the Loop

Principio arquitectónico obligatorio para todo el proyecto: **toda acción crítica deberá poder ser auditada, explicada y revertida. Nunca sacrificar seguridad por comodidad. Toda decisión tomada por AURA deberá ser explicable.**
*Impacta: 3.1 (Principio #1), 5.3, 4.3.*

## Autorización

El CEO autoriza el inicio de la **Fase D1**: redacción de los 5 capítulos P0 (1.1 → 1.2 → 2.1 → 2.2 → 3.1), cada uno con gate de aprobación del CEO.
