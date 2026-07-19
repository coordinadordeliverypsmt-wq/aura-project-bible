# Demostración oficial M1 — Stack real

Fecha: 2026-07-19. Ejecución: `demo_capacidad_m1.py --real`. Errores: **0**.
Log crudo: `validacion/demo-m1-real-2026-07-19.log` (USB secundario).

## Backend real utilizado

| Componente | Implementación | Ubicación física |
|---|---|---|
| LLM | Ollama + `qwen2.5:3b` (Q4_K_M, 3.1B) | USB (`/dev/sdb1`) |
| TTS | Piper 1.5.0 + voz `es_MX-ald-medium` | USB (`/dev/sdb1`) |
| STT | passthrough (entrada de texto) | — |
| Bus | InProcessEventBus | — |
| Memoria | PersistentMemory (con backup/restore) | interno |

## Capacidades demostradas

| Capacidad | Resultado |
|---|---|
| Recuerda dentro de la conversación | ✅ |
| Ejecuta acciones seguras (lista verde) | ✅ auto-ejecución |
| Rechaza acciones peligrosas (lista roja, HITL) | ✅ `eliminar_informacion` → DENEGADA |
| Se detiene por completo con el kill switch | ✅ acción bloqueada, luego reanudada |
| Recuerda entre sesiones (persistencia tras reinicio) | ✅ |
| Recupera su memoria tras una pérdida (backup) | ✅ |

Continuidad verificada con el LLM real tras simular reinicio:
> Usuario: "¿Qué acordamos sobre la luz de la sala?"
> AURA: "Ya hemos acordado que prefieres una luz tenue en la sala por la noche."

Las dos prioridades que el CEO fijó para M1 (D25) — **backup/recuperación de memoria** y
**kill switch** — quedan validadas contra el stack real, no contra mocks.

## Latencias — NO VÁLIDAS para HC-1

| Métrica | Valor |
|---|---|
| n | 5 turnos |
| mínimo | 162.203 ms |
| **P50** | **334.656 ms** |
| máximo | 705.676 ms |
| Objetivo HC-1 | 1.200 ms |
| Exceso | **279x** |

**Estas mediciones son inválidas como métrica de HC-1.** Durante toda la ejecución el sistema
estuvo paginando (2 GB de swap en uso sobre 3,6 GB de RAM), y el acta invalida expresamente
cualquier medición de HC-1 con swapping activo.

Causa: hardware por debajo del mínimo documentado (2 CPU vs ≥4; 3,6 GB RAM vs ≥12 GB; sin GPU).
No es un defecto de implementación ni de almacenamiento: se midió `eval_duration` = 8.738 ms/token,
que es cómputo puro e independiente de dónde residan los modelos.

**HC-1 permanece `Pendiente de validación en entorno objetivo` (D24), no fallido.**

## Conclusión

`RESULTADO: CAPACIDAD CONVERSACIONAL M1 DEMOSTRADA (backend: STACK REAL)`

El núcleo conversacional y sus garantías de seguridad funcionan de extremo a extremo con
componentes reales, locales y de código abierto, sin APIs comerciales ni claves de terceros (D24).
El cierre formal de M1 sigue bloqueado por **ALERTA-003**, pendiente de gate extraordinario del CEO.
