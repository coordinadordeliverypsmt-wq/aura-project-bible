---
documento: "Architecture Review — M2.4 Exit (centro único de notificaciones)"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Pendiente de aprobación del CEO"
---

# Architecture Review — M2.4 Exit

**Quality Gate: PASS — 220 pruebas + 8 contratos** (al entrar en M2.4: 202 + 8).

## El riesgo real de esta fase

Un centro de notificaciones parece una funcionalidad inofensiva de presentación. No lo es: **permite
actuar desde un solo lugar** (6.4 §3), y ahí está el peligro. Si el centro pudiera ejecutar por su
cuenta, sería una **puerta trasera** que rodearía todo lo construido en M2.0–M2.3.

**Decisión:** el centro **no ejecuta nada**. Delega en el motor de automatización (M2.3), que impone
dry-run obligatorio y confirmación para la lista roja. Sin motor, `actuar()` lanza una excepción — no
existe camino de ejecución directa.

### Evidencia

| Prueba | Demuestra |
|---|---|
| `test_actuar_sin_motor_es_imposible` | No hay ejecución directa |
| `test_accion_roja_desde_notificacion_exige_confirmacion` | Llegar por notificación **no evita el HITL**; árbol intacto |
| `test_accion_desde_notificacion_pasa_por_dry_run` | El plan previo tampoco se evita |
| `test_kill_switch_alcanza_a_las_acciones_del_centro` | El kill switch cubre esta vía |
| `test_operacion_fuera_del_catalogo_desde_notificacion` | RN-2 también aplica aquí |

Las comprobaciones de efecto usan la **huella completa del árbol** (tamaño + `mtime` en nanosegundos),
no la mera existencia del archivo.

## Frontera de fuentes cerrada al MVP

Solo `computador`, `home_assistant` y `aura` (2.2 §4.4). **Android, NAS, Docker y cualquier otra fuente
se rechazan** con excepción explícita — un centro que acepta cualquier origen es un canal de entrada
sin control, y la exclusión de esos sistemas hasta R2 es una decisión de alcance vigente.

Verificado por prueba parametrizada en ambos sentidos: 5 fuentes rechazadas, 3 aceptadas.

## Reducción de ruido

Deduplicación por `(fuente, título)`: la misma alerta repetida se suprime y se contabiliza. Notificaciones
de **fuentes distintas con el mismo título no se confunden** — son hechos diferentes.

Priorización: primero criticidad, después las más recientes.

## Privacidad de terceros (ALERTA-002, riesgo RN-5)

El cuerpo de una notificación puede contener información de otra persona (*"Juan: te espero a las 5"*).
Al cerrar sesión se **purga el contenido**, conservando el **hecho** de la notificación —fuente, momento,
prioridad—.

Así el usuario mantiene su historial de actividad **sin que AURA acumule un historial personal de
terceros entre sesiones**, que es exactamente la precisión que el CEO fijó al resolver ALERTA-002.

Verificado: el contenido de terceros se purga, **el contenido propio del usuario no se toca**, y la
purga es idempotente.

## Estado de M2 completo

| Fase | Estado |
|---|---|
| M2.0 — H1, H2, H3 | ✅ |
| M2.1 — Catálogo de operaciones tipadas | ✅ |
| M2.2 — Adaptador del computador (TOCTOU) | ✅ |
| M2.3 — Motor de automatización (dry-run) | ✅ |
| M2.4 — Centro de notificaciones | ✅ |

Las **tres capacidades del MVP asignadas a M2** (4, 5 y 9 del acta D2) están implementadas y
verificadas. Sin alertas de arquitectura abiertas. Ningún contrato roto: `Adapter` se corrigió en M2.0
y `AdaptadorSimulable` se añadió como Protocol separado y opcional.

## Pendiente antes de declarar M2 terminado

Conforme a la Definition of Done del M2 Entry (§7), quedan:

- **Demo de capacidad M2 con stack real** y 0 errores no recuperados.
- **Architecture Review M2-Exit + Executive Summary** (D25), con Product Readiness actualizado.

**Advertencia de expectativas:** la demo con stack real costará varios minutos por turno (~160 s
medidos). El valor de esa demo es demostrar el flujo completo, no medir latencia — HC-1 sigue
Pendiente en entorno objetivo (D24).
