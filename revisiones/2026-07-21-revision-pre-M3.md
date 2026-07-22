---
documento: "Revisión de estado del proyecto AURA — Gate pre-M3"
fecha: 2026-07-21
autor: "CTO"
encargo: "CEO — documento de revisión versionado en Git que capture el estado actual del proyecto (pre-M3) como única referencia persistente"
base: "main @ 2e1c23a · tags v1.3.0-m2 / v1.4.0-m3.0"
metodo: "Medición directa sobre el código en esta sesión (pytest, grep verificado, git) + auditoría del 2026-07-21 como línea base"
estado: "Referencia de estado. Vigente hasta que una revisión posterior lo supere."
---

# Revisión de estado del proyecto AURA — Gate pre-M3

> **Propósito.** Este documento es la **única referencia persistente del estado del proyecto** a la
> entrada de M3. Sustituye a cualquier registro fuera del repositorio: la fuente de verdad es el
> contenido versionado en Git. Toda cifra procede de medición sobre el código en el estado
> `2e1c23a`; donde un dato es un objetivo o una estimación, se indica.

## 1. Resumen ejecutivo

- **Bible v1.0 cerrada.** M1 y M2 **cerrados e integrados** en `main`. M3.0 (captura de señales) y
  M3.2a (soberanía del modelo del usuario) implementados.
- **Suite verde:** 284 pruebas pasan, 3 se omiten (los e2e de stack real, diferidos a hardware por
  D24/D34). Quality Gate PASS.
- **Repositorio publicado** en GitHub en modo **privado** (decisión de diseño; hacerlo público es
  decisión explícita pendiente del CEO). `main` sincronizada con `origin/main`.
- **Línea MA (Madurez de Arquitectura)** aprobada y en curso: **MA.1 y MA.2 hechos**; **MA.3, MA.4,
  MA.5 pendientes**.
- **Product Readiness: 41%** (cierre de M2). No se ha movido con evidencia desde entonces.
- **HC-1 (latencia e2e) sigue ABIERTO** — no certificable en el hardware actual; pendiente de
  validación en el entorno objetivo.
- **Riesgo abierto de mayor gravedad:** la superficie que valida el sistema (scripts/demos) **diverge
  de la que arma la composición de producción**. Es un riesgo de corrección, detallado en §5.1 y §8.1.

## 2. Estado del roadmap

### 2.1 Cerrado

| Hito | Estado | Evidencia |
|---|---|---|
| Bible v1.0 | Cerrada | 36/36 capítulos aprobados, CHANGELOG 1.0.0 |
| M1 (núcleo conversacional, backups, kill switch) | Cerrado e integrado | tag histórico, pruebas activas |
| M2 (Manos Digitales — acciones reales) | Cerrado e integrado | tag `v1.3.0-m2`, demo 8/9 |
| M2.5 (ejecutor único, resuelve ALERTA-005) | Cerrado | `MotorAutomatizacion`, flujo canónico |
| M3.0 (captura de señales, ADR-0015) | Cerrado | tag `v1.4.0-m3.0` |
| M3.2a (modelo de usuario, ADR-0017) | Cerrado | `core/modelo_usuario.py` |

### 2.2 En curso — Línea MA (Madurez de Arquitectura, origen D39)

Trabajo transversal que avanza **sin depender de hardware**, para que al llegar el equipo sólo haya
que *habilitar* capacidades, no construirlas.

| Fase | Contenido | Estado |
|---|---|---|
| **MA.1** | Punto de entrada único de producción (`python -m aura_skeleton` + `composicion.py`) | ✅ Hecho |
| **MA.2** | Memoria escalable (JSONL incremental + índice invertido) | ✅ Hecho (MA.2a) |
| **MA.3** | Retención y rotación del audit log | ⏳ Pendiente |
| **MA.4** | Habilitación y transparencia de conectores (condiciones de D37) | ⏳ Pendiente |
| **MA.5** | Limpieza: código muerto y consolidación de scripts | ⏳ Pendiente |

### 2.3 Diferido a hardware / entorno físico (D39 — no cancelado)

| Hito | Motivo del aplazamiento |
|---|---|
| M3.1 (Home Assistant real) | Requiere entorno físico (D34) |
| M3.2b (inferencia real) | Requiere GPU/RAM del hardware objetivo |
| M3.3 (anticipación) | Depende de datos reales acumulados |
| M3.4 (avatar Live2D) | Depende de plataforma |

## 3. Decisiones vigentes — ADR

Los **17 ADR están en `accepted`** (0001–0017). Ninguno ha sido revocado ni sustituido.

**Hallazgo estructural:** el estado `accepted` no distingue *decidido* de *implementado*. Varios ADR
describen tecnología que el walking skeleton todavía no implementa:

| ADR | Decisión | Implementación real (2e1c23a) |
|---|---|---|
| 0006 | Event bus NATS | `InProcessEventBus` en la composición; `bus_nats.py` existe, sin cablear, sin pruebas |
| 0007 / 0011 | Qdrant + RAG vectorial híbrido | JSONL + índice léxico (interino de MA.2a, no reflejado en el ADR) |
| 0008 / 0012 / 0013 | Whisper / Piper (voz) | `voice_real.py` existe; diferido a hardware |
| 0009 | Avatar Live2D | No implementado (M3.4, diferido) |
| 0003, 0014, 0015, 0016, 0017 | HITL, Core única verdad, contexto, neutralidad, preferencias | Implementados y probados |

**Recomendación (barata, sin código):** añadir a cada ADR una línea `implementación: implementado |
interino | diferido-hardware | pendiente`. Hoy nadie que lea los ADR puede saber qué está en pie.

**Disciplina ADR-0011 (vigente):** la memoria léxica de MA.2a es un **interino deliberado**. La deuda
que cerró MA.2 era de *persistencia e índice*, no de *búsqueda semántica*. ADR-0011 (Qdrant) **no se
reabrió** porque no hay evidencia que lo contradiga; su reapertura sólo procede con evidencia técnica
objetiva (Architecture Review comparativo), no por preferencia. Ver §5.2 y §8.2.

## 4. Decisiones de gobierno vigentes (selección)

- **D24** — stack local-first, open source, **sin claves de terceros**. Aplica al stack de ejecución,
  no al alojamiento del código.
- **D27** — todo informe de entorno se basa en verificación ejecutada **en el momento** de generarlo.
- **D34** — no se construyen entornos artificiales para aprobar un milestone; una capacidad que actúa
  sobre el mundo físico se valida contra el mundo físico.
- **D39** — estado del proyecto = **desarrollo continuo con restricciones de hardware**, no congelado.
- **D40** — punto de entrada único (`python -m aura_skeleton`); todo ejecutable **consume** la
  composición, no la reconstruye; la composición permanece **declarativa**; observabilidad de
  arranque (AURA indica siempre qué cree que está activo antes de operar).

## 5. Deuda técnica (con evidencia)

### 5.1 🔴 Divergencia validación ↔ producción
De los 9 ejecutables, **8 construyen `Orchestrator(...)` a mano y ninguno consume `composicion`**. Y
los demos que "validaron" el sistema arman una AURA distinta a la de producción:

- `run_demo.py`, `run_demo_real.py`: **sin** ejecutor único, **sin** captura de señales, **sin**
  `AdaptadorComputador`.
- `demo_capacidad_m2.py`: ejecutor sí, **captura de señales no**.

Consecuencia: la superficie de validación no es la superficie de producción. Es el agujero que D40 y
MA.1 cierran en el arranque, pero abierto en los scripts (patrón ALERTA-004/005). **La "validación de
M2 sobre stack real" se hizo sobre un cableado que omite M3.0.**

### 5.2 🔴 Memoria léxica vs. RAG semántico
La implementación de MA.2a recupera por **solapamiento de términos de superficie**: una consulta
parafraseada sin términos compartidos devuelve vacío. Es un interino documentado en el commit de
MA.2a y en el docstring del test de escalabilidad, pero **no reflejado en Bible 4.1 ni en ADR-0011**,
que describen RAG semántico sobre Qdrant con "recall ≥90%". Ver §8.2 (se vuelve precondición de M3.3).

### 5.3 🟡 Código muerto — subsistema de métricas
`_metrics` / `metric_inc()` / `metrics()` (`observability.py`) no se consumen en ningún módulo.
Write-only. → MA.5.

### 5.4 🟢 Código limpio de marcadores de deuda
Cero `TODO/FIXME/HACK` reales en `aura_skeleton/`. La deuda se rastrea en documentos, no dispersa en
el código.

### 5.5 🟢 Flujo de acción consistente con la Bible
`MotorAutomatizacion.ejecutar` respeta Bible 5.3 §3.1 (dry-run → Permisos/HITL → adaptador →
auditoría), con el fix de M2.5 presente: **permisos antes de resolver adaptador**, de modo que una
acción de lista roja sin adaptador sigue auditada. Sin discrepancia.

## 6. Pruebas y cobertura

- **284 pruebas pasan, 3 omitidas** (e2e de stack real, diferidos a hardware).
- No fue posible medir cobertura `%` en esta sesión: `coverage`/`pytest-cov` no están instalados y no
  se instaló nada sin autorización. Se usó un **mapeo estructural** (proxy) test↔módulo.
- **Módulos del stack real, los menos probados:** `bus_nats` (0 referencias en pruebas),
  `providers_real` (1), `voice_real` (2). Es esperable (requieren NATS/Ollama/Whisper) y **legítimo
  por D34** (probar el doble no probaría el sistema), pero **son justo los que correrán en
  producción**: riesgo aceptado, no eliminado.
- **Falta una prueba anti-regresión de D40**: hoy nada impide que un nuevo script vuelva a cablear el
  sistema a mano.

## 7. Product Readiness

Se reporta **separado del progreso técnico** desde M2. Cierre de M2: **41%** (desde 32%).

| Dimensión | M2 |
|---|---|
| Hace cosas útiles (acciones reales) | 12% |
| Entiende y responde con sentido | 10% |
| Responde a tiempo | 0% (bloqueado por HC-1) |
| Disponible sin fricción | 0% |
| **Total** | **41%** |

**No se ha movido con evidencia desde M2.** MA.1 construyó el mecanismo que podría mover *"disponible
sin fricción"*, pero mientras (a) los demos no pasen por la composición y (b) no haya evidencia de
arranque y operación sostenida en hardware, la cifra se mantiene. *"Responde a tiempo"* está en 0% y
seguirá ahí hasta cerrar HC-1.

## 8. Riesgos arquitectónicos abiertos (antes de M3)

### 8.1 🔴 La validación no refleja la producción
Antes de M3: que **todo ejecutable pase por `composicion`**, y **re-validar el stack real a través de
`composicion`** cuando llegue el hardware — no vía `run_demo_real.py`. Cierra §5.1.

### 8.2 🔴 La memoria léxica es precondición funcional de M3.3
M3.3 (anticipación) se apoya en recuperar señales relevantes; un recall léxico no encuentra señales
parafraseadas. La deuda de ADR-0011 deja de ser "optimización" y pasa a ser **precondición de M3.3**.
Ahí sí habrá evidencia objetiva para el Architecture Review comparativo (Qdrant vs. índice más
simple) que condiciona ADR-0011.

### 8.3 🟡 Audit log sin rotación
Append-only con `fsync`, sin política de rotación: crece sin límite (el proyecto ya llenó un disco
una vez). Es **materia prima de las señales implícitas**: una rotación ingenua borraría el historial
que M3.3 necesita. Debe diseñarse junto con la retención de señales. Es MA.3.

### 8.4 🟡 HC-1 sin validar
Ver §9.

## 9. HC-1 — pendiente de validación en hardware

**Objetivo:** latencia percibida R1 P50 ≤ 1200 ms (etapa dominante de inferencia ≤ 500 ms).

**Estado: ABIERTO, no fallido.** No es certificable en el hardware actual: en la verificación del
2026-07-19 una sola inferencia real superó los 120.000 ms (~100× el objetivo) porque el modelo no
cabe en la RAM disponible → swapping. La máquina actual **no cumple el mínimo documentado** (≥4 CPU,
≥12 GB RAM), por lo que **no constituye prueba de HC-1** en ningún sentido. HC-1 se certificará en el
entorno objetivo, con `medicion_valida=false` automática si hay swapping.

## 10. Próximos hitos

1. **Línea MA** (sin hardware): MA.3 → MA.4 → MA.5, con la matización de §8.1 (ver propuesta de orden
   que acompaña a este documento). DoD de la línea: un único ejecutable enciende el sistema completo
   con prueba que lo verifica; memoria que no degrada; retención decidida e implementada; mecanismo
   de conectores verificado sin conector externo; sin código muerto; Quality Gate PASS; auditoría
   re-ejecutada mostrando la deuda cerrada.
2. **Al llegar el hardware objetivo:** validar HC-1, M3.1 (HA real), M3.2b (inferencia), y re-validar
   el stack real **a través de la composición**.
3. **Decisión de gobierno pendiente:** visibilidad del repositorio (privado → público es
   irreversible; hoy privado por diseño).

## 11. Referencias cruzadas

- Auditoría base: `auditoria/2026-07-21-auditoria-tecnica-integral.md`
- Roadmap de la línea: `milestones/ROADMAP-ADAPTADO-MADUREZ-ARQUITECTURA.md`
- Architecture Review M1: `revisiones/2026-07-18-architecture-review-m1.md`
- Executive Summary M2 (Product Readiness): `resumenes-ejecutivos/EXECUTIVE-SUMMARY-M2.md`
- Bible 4.1 (memoria), 5.3 §3.1 (flujo de acción); ADR-0011, ADR-0015, ADR-0017.
