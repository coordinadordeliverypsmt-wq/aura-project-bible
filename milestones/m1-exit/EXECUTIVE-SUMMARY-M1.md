---
documento: "CEO Executive Summary — Milestone M1"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-19"
estado: "M1 condicionado — bloqueado por ALERTA-004"
---

# CEO Executive Summary — Milestone M1 (Núcleo Conversacional)

**Estado: CONDICIONADO** — no cerrado. · **Fecha:** 2026-07-19

## 1. Capacidad entregada

AURA sostiene un flujo conversacional completo con stack real, local y de código abierto: razona con LLM
local (Ollama + `qwen2.5:3b`), habla con voz propia (Piper, es_MX), recuerda entre sesiones, se recupera
desde backup, ejecuta acciones seguras, **detiene toda acción peligrosa** y puede apagarse por completo.

Sin APIs comerciales. Sin claves de terceros. Sin que un solo dato del usuario salga de la máquina.

## 2. Resultados medidos

| | |
|---|---|
| Demo oficial `--real` | **6/6 capacidades, 0 errores** |
| HITL lista roja | **3/3 detenidas** (tolerancia cero cumplida) |
| Grounding / no-fabricación | ❌ **FALLO** → ALERTA-004 |
| Consistencia inter-modelo | no evaluable (un solo modelo) |
| Quality Gate | PASS (39 pruebas + 4 contratos) |
| Latencia P50 | 334.656 ms — **inválida** (swapping) |

## 3. Cumplimiento vs objetivos

HC-1 R1 (≤1200 ms): **pendiente de validación en entorno objetivo** (D24), no fallido — la causa es
hardware (2 CPU, 3,6 GB RAM, sin GPU; 8.738 ms/token), no implementación.
Guardarraíles: HITL y kill switch ✅ · grounding ❌.

## 4. Riesgos vivos

1. **ALERTA-004** — el grounding estaba declarado en la Bible pero no implementado en ninguna parte.
2. Las evals con mocks pueden dar falsa confianza: el mock estaba escrito para pasar la eval que debía
   verificar el sistema.
3. HC-1 no validable en este hardware.

## 5. Decisiones para el CEO

- **Gate sobre ALERTA-004:** A (imposición determinista en el núcleo, recomendada), B (solo prompt) o C
  (aceptar riesgo, desaconsejada).
- Autorizar segundo modelo local para la eval de consistencia.
- Decidir sobre `swapfile_aurora` (4 GB en el USB principal sin prestar servicio).

## 6. Siguiente milestone

M2 (manos digitales) **no debe iniciarse** antes de resolver ALERTA-004 y auditar las evals restantes.

---

## Nota del CTO

M1 entrega más de lo que su cierre formal refleja. Lo relevante no es solo que las capacidades funcionen,
sino **qué aprendimos sobre cómo verificarlas**: las garantías que impone el núcleo sobrevivieron al paso
de mocks a modelo real; la única que se delegaba implícitamente en el LLM, no. Ese criterio —guardarraíl
es código verificable, no expectativa sobre un modelo— es el activo más valioso que deja este milestone,
y se descubrió precisamente porque se exigió validar contra stack real en vez de contra simulaciones.
