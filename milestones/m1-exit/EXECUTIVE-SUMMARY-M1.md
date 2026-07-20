---
documento: "CEO Executive Summary — Cierre del Milestone M1"
version: 2.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "M1 CERRADO TÉCNICAMENTE"
---

# Executive Summary — Cierre del Milestone M1 (Núcleo Conversacional)

**Estado: CERRADO TÉCNICAMENTE** · **Alertas abiertas: ninguna**

## 1. Capacidad entregada

AURA sostiene un flujo conversacional completo con stack real, local y de código abierto: razona con
LLM local (Ollama), habla con voz propia (Piper, es_MX), recuerda entre sesiones, se recupera desde
backup, ejecuta acciones seguras, **detiene toda acción peligrosa** y puede apagarse por completo.

**Sin APIs comerciales. Sin claves de terceros. Sin que un dato del usuario salga de la máquina.**

## 2. Garantías críticas — todas verificadas con LLM real

| Garantía | Resultado | Impuesta por |
|---|---|---|
| HITL lista roja (tolerancia cero) | ✅ **3/3 detenidas** | el Core |
| Grounding / no-fabricación | ✅ **PASS** | el Core (ADR-0014) |
| Consistencia inter-modelo (≥90%) | ✅ **100%** | los contratos del Core |
| Lista verde auto-ejecuta | ✅ PASS | el Core |
| Kill switch | ✅ Bloquea y reanuda | el Core |
| Memoria persistente + recuperación | ✅ Verificada | el Core |

Demo oficial `--real`: **6/6 capacidades, 0 errores.** Quality Gate: **PASS** (45 pruebas + 4 contratos).

## 3. El hallazgo que define M1

M1 entrega más que capacidades: entrega un **criterio de verificación**.

Dentro del mismo milestone, dos garantías se comportaron de forma opuesta al pasar de mocks a modelo
real. **HITL pasó 3/3 porque la impone el núcleo. Grounding falló porque se delegaba implícitamente en
el LLM** — y su eval pasaba con mocks solo porque el doble de prueba estaba escrito para pasarla.

De ahí nació **ADR-0014**: *la verdad del sistema nunca dependerá del comportamiento probabilístico de
un modelo de lenguaje*. Su confirmación empírica llegó al final: `qwen2.5:0.5b`, **seis veces más
pequeño** que `qwen2.5:3b`, produjo la **misma acción segura con 100% de adherencia**. La seguridad no
reside en el modelo.

**Regla operativa que queda establecida:** si una garantía no puede verificarse con una prueba
determinista, no es una garantía — es una expectativa.

## 4. Gobernanza

Cuatro alertas de arquitectura emitidas, **cuatro resueltas**, **sin enmendar ninguna decisión de
rango 1**. El caso más exigente fue ALERTA-003: se detuvo un cambio hacia una API comercial que
**habría hecho pasar la demo** mientras rompía local-first y enmascaraba el límite real de hardware.

## 5. HC-1 (latencia)

**Pendiente de validación en entorno objetivo (D24) — no fallido.** Ratificado por el CEO.

e2e P50 = 160.267 ms frente a 1.200 ms de objetivo, con `medicion_valida: false` por paginación
(1,99 GB in / 2,49 GB out, RAM al 92,5%). La causa es hardware —2 CPU vs ≥4, 3,6 GB RAM vs ≥12, sin
GPU; 8.738 ms/token— no implementación. Se descartaron por medición dos hipótesis alternativas:
almacenamiento y timeout del cliente.

## 6. Riesgos vivos

1. **HC-1 sin validar** hasta disponer de hardware objetivo.
2. **Patrón "mock escrito para pasar la eval"** — detectado en grounding, pendiente de auditar en el resto.
3. **USB principal al límite:** 616 MB libres. `swapfile_aurora` ocupa 4 GB sin prestar servicio
   (el swap activo es el del disco interno). Recomendación del CTO pendiente de decisión.

## 7. Decisión solicitada al CEO

**Aprobar el cierre formal de M1** y autorizar el inicio de **M2**.
