---
documento: "Architecture Review M1-Exit"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-19"
estado: "Completada — datos medidos con stack real"
---

# Architecture Review M1-Exit

**Veredicto de coherencia: la arquitectura es coherente. M1 NO está listo para cierre.**
**Alertas abiertas: ALERTA-004 (grounding no garantizado).**

## 1. Estado de cada ADR

13 ADRs (0001-0013), todos `accepted` y **sin modificaciones** durante M1. Ninguna decisión de M1 exigió
enmendar un ADR — indicador de que las abstracciones aguantaron el contacto con la implementación real.
ADR-0010 (Ollama como runtime local) se validó bajo presión: ver §2, ALERTA-003.

## 2. Estado de decisiones

D1-D31 vigentes. Nuevas durante M1: D25, D26, **D27** (Preflight Check obligatorio), D28-D30
(riesgo aceptado, cambio de prioridad, no-bloqueos administrativos) y **D31** (almacenamiento distribuido).

**Ninguna decisión de rango 1 fue enmendada.** D24 (local-first, sin APIs comerciales ni claves de
terceros) resistió una solicitud directa de refactor hacia Gemini: ver ALERTA-003, resuelta por
Alternativa A tras demostrarse por medición que la premisa del cambio era falsa.

## 3. Cumplimiento de requisitos (datos reales)

| Requisito/atributo | Objetivo Bible | Medido (stack real) | Cumple |
|---|---|---|---|
| RF-2 Voz / HC-1 latencia | R1 ≤ 1200 ms | P50 = 334.656 ms | ❌ **inválido** (swapping) |
| RF-1 Memoria (persistencia + backups) | recuperación verificada | demo `--real` 6/6 | ✅ |
| RF-6 Orquestación (fallback) | opera con caídas | circuit breaker ejercitado | ✅ |
| **RF-HITL** | **100% lista roja detenida** | **3/3 detenidas** | ✅ |
| **No-fabricación / grounding** | **sin invención** | **FALLO** | ❌ **ALERTA-004** |
| Consistencia inter-modelo | ≥ 90% | no evaluable (1 modelo) | ⏸️ |
| Estabilidad | 0 errores no recuperados | 0 errores | ✅ |
| Kill switch | detiene toda acción | bloqueó y reanudó | ✅ |

## 4. Trazabilidad Bible → ADR → Código → Pruebas

Actualizada y completa: núcleo (`bus`, `orchestrator`, `permissions`, `kill_switch`), memoria
(`PersistentMemory` con backup/verify/restore), stack real (`providers_real`, `voice_real`), arneses
(`validar_m1`, `evals_m1`, `demo_capacidad_m1`). **39 pruebas + 4 contratos, Quality Gate PASS.**

**Brecha detectada:** la garantía de grounding (4.1 §4) figura en la Bible y en el arnés de evals, pero
**no tiene implementación ni prueba determinista**. La trazabilidad estaba rota en ese punto y solo se
reveló al sustituir mocks por LLM real. Ver §7 y ALERTA-004.

## 5. Riesgos técnicos

- **ALERTA-004 (crítico, abierto):** garantía declarada pero no implementada.
- **Lección estructural:** una eval que valida contra un mock escrito para pasarla no valida nada. Debe
  revisarse si otras evals comparten ese patrón antes de ampliarlas en M2.

## 6. Riesgos de rendimiento (medidos)

`eval_duration` = **8.738 ms/token**; carga del modelo desde USB = 150.466 ms. Hardware por debajo del
mínimo documentado (2 CPU vs ≥4; 3,6 GB RAM vs ≥12; sin GPU). El sistema **pagina** durante la inferencia
(hasta 2 GB de swap), lo que invalida toda medición de HC-1 conforme al acta.
**HC-1 permanece `Pendiente de validación en entorno objetivo` (D24), no fallido.**

Se descartaron por medición dos hipótesis: que la causa fuera el almacenamiento (refutada: la ubicación
de los archivos no afecta al cómputo) y que fuera el timeout del cliente (refutada: era síntoma, no causa).

## 7. Riesgos de seguridad

HITL y kill switch **impuestos por el núcleo**, verificados con LLM real: 3/3 acciones de lista roja
detenidas. El contraste con el fallo de grounding es el hallazgo arquitectónico de M1: **las garantías
que impone el núcleo sobreviven al cambio de mock a modelo real; las que se delegan implícitamente en el
LLM, no.** Este criterio debe aplicarse a toda garantía futura.

## 8. Riesgos de portabilidad

Sin dependencias propietarias ni claves. Stack íntegramente local y de código abierto (D24). Los
proveedores viven tras el contrato `ModelProvider`; el router permanece agnóstico.

## 9. Riesgos operacionales

Mitigados durante M1: montajes por identificador estable (UUID/LABEL) tras comprobarse que un reinicio
renombra `sda1` → `sdb1`; Preflight Check obligatorio (D27); guardarraíl que impide arrancar Ollama si los
modelos no residen físicamente en el USB. Disco interno: 889 MB → **13 GB** libres.

## 10. Riesgos de mantenimiento

Bajos. Quality Gate automatizado. Deuda identificada: la observabilidad del router no incluía el tipo de
excepción, lo que costó una ronda de diagnóstico completa; corregido.

## 11. Riesgos de gobernanza

Sanos. Cuatro alertas emitidas y tres resueltas sin enmendar decisiones de rango 1. El proceso de disenso
(D15) funcionó en su caso más exigente: ALERTA-003 detuvo un cambio que **habría hecho pasar la demo**
mientras rompía local-first y enmascaraba el límite real de hardware.

## 12. Recomendaciones para M2

1. **Resolver ALERTA-004** antes de cualquier trabajo nuevo (imposición determinista en el núcleo).
2. **Auditar las evals restantes** buscando el patrón "mock escrito para pasar la eval".
3. Segundo modelo local para habilitar la eval de consistencia inter-modelo (requiere liberar el USB
   principal: `swapfile_aurora` ocupa 4 GB sin prestar servicio).
4. Validar HC-1 en hardware objetivo; hasta entonces, separar validación funcional de validación de latencia.
5. Endurecer backups (cifrado, off-site al USB secundario `AURORA_BAK`).

## Conclusión

**Arquitectura coherente; M1 NO listo para cierre.** Todas las capacidades funcionales y las dos
prioridades del CEO (D25: backup de memoria y kill switch) están demostradas contra stack real con cero
errores. El cierre queda bloqueado por **ALERTA-004**, una garantía constitutiva del producto que se
descubrió no implementada. La arquitectura no requiere cambios: requiere que una garantía declarada pase
a ser código verificable.
