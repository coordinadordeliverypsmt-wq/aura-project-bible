---
documento: "Plan de Calidad y Validación de AURA (v1.0)"
version: 1.0.0
autor: "Fable (CTO)"
fecha: 2026-07-18
estado: "En revisión (gate del CEO)"
---

# Plan de Calidad y Validación de AURA — v1.0

Cómo se garantiza la **estabilidad del proyecto durante su crecimiento**. Materializa operativamente los capítulos 7.1 (estándares de código), 7.2 (pruebas y evals) y el principio de observabilidad (P-ARQ-7). **Regla permanente (acta):** toda nueva funcionalidad se integra **acompañada de su estrategia de pruebas y validación**.

## 1. Quality Gate (validación automática)

Se ejecuta **antes de cada ejecución o integración** (`walking-skeleton/quality-gate.sh`). Cinco verificaciones, todas deben pasar (PASS/FAIL explícito):

| # | Verificación | Herramienta | Qué garantiza |
|---|---|---|---|
| 1 | **Formato** | `ruff format --check` | Estilo uniforme; diffs limpios |
| 2 | **Análisis estático** | `ruff check` (E,F,I,UP,B) | Sin errores, imports ordenados, antipatrones |
| 3 | **Tipado** | `mypy` | Contratos de tipos respetados (Bible 3.3/3.4) |
| 4 | **Pruebas** | `pytest` (unit/integración/e2e/rendimiento) | Comportamiento correcto |
| 5 | **Contratos** | `pytest tests/test_contracts.py` | Las implementaciones cumplen los Protocolos (EventBus, MemoryStore, ModelProvider, Adapter) |

**Estado actual (2026-07-18):** GATE = **PASS** — 25 pruebas, mypy sin issues, lint limpio, contratos verificados.

Toolchain reproducible: `pip install -r walking-skeleton/requirements-dev.txt`. En el futuro (7.3) el gate correrá también en CI antes de cada merge.

## 2. Estructura de pruebas

Bajo `walking-skeleton/tests/`, reflejando la pirámide del capítulo 7.2:

| Nivel | Ubicación | Cubre | Ejemplos actuales |
|---|---|---|---|
| **Unitarias** | `tests/unit/` | Módulos aislados | permisos (listas verde/roja, HITL), memoria (recall, no-fabricación, aislamiento por usuario), router (fallback, prioridad de seguridad) |
| **Integración** | `tests/integration/` | Contratos entre módulos | Event Bus: entrega con trace_id, idempotencia |
| **End-to-End** | `tests/e2e/` | Turno completo | verde ejecuta; roja denegada no ejecuta |
| **Rendimiento** | `tests/performance/` | Latencia/overhead | latencia estructural del turno; overhead del bus (< 5 ms/evento) |
| **Contratos** | `tests/test_contracts.py` | Conformidad a Protocolos | isinstance sobre EventBus/MemoryStore/ModelProvider/Adapter |

**Nota sobre rendimiento:** las pruebas de latencia actuales son **estructurales** (mocks); la latencia **real** (HC-1) se valida en hardware objetivo (D24, `entorno/HC-1-validacion.md`). Las **evals de IA** (comportamiento no determinista de LLMs, consistencia inter-modelo ≥90%, guardrails) del capítulo 7.2 se incorporan al llegar el stack real (`run_demo_real.py`) y viven junto a las pruebas de rendimiento.

## 3. Estrategia de observabilidad (P-ARQ-7)

Implementada en `aura_skeleton/observability.py`; los logs son **dato del usuario** (locales y cifrados en producción, ADR-0001).

- **Logging estructurado:** cada registro lleva `level`, `module`, `msg`, `trace_id` y pares clave-valor; salida legible y filtrable. En producción, formato JSON y residencia local.
- **Métricas:** contadores/sumas por nombre (`metric_inc`, `metrics()`) — p. ej. eventos publicados, acciones autorizadas/denegadas, latencia por etapa. Base de los dashboards de 7.4.
- **Trazabilidad entre módulos:** el **`trace_id`** correlaciona todo un turno de extremo a extremo (percepción → memoria → router → permisos → acción → respuesta) y también los streams de baja latencia con los eventos de control (invariante de la ALERTA-001). El **audit log** (subconjunto marcado `audit=True`) es el registro inmutable de acciones (HITL/D9, 5.3).

## 4. Política de crecimiento: "toda funcionalidad con su validación"

- Ningún módulo/feature nuevo se integra sin: (a) pruebas del nivel que corresponda, (b) conformidad de contrato si expone o consume uno, (c) el Quality Gate en PASS.
- Un cambio que rompa un contrato exige ADR (1.2 §3.2) y actualización de las pruebas de contrato.
- Los umbrales oficiales (2.5) se verifican con evals (7.2); un umbral incumplido dispara Alerta de Arquitectura (D15), no un ajuste silencioso.
- **Cero sorpresas de entorno** (D24): toda dependencia nueva se anuncia y se automatiza antes de bloquear.

## 5. Cómo esto garantiza estabilidad al crecer

La arquitectura por contratos (ADR-0004) + el Quality Gate + la pirámide de pruebas hacen que **cada incremento se construya sobre una base verificada**: los contratos evitan acoplamientos, las pruebas de contrato detectan rupturas, el tipado y el lint frenan defectos temprano, y la trazabilidad permite diagnosticar cualquier regresión de extremo a extremo. Es la condición para escalar durante años (D20) sin degradar la calidad.

## 6. Siguiente paso

Con esta base integrada y el Gate en PASS, queda autorizado `walking-skeleton/run_demo_real.py` (adaptadores reales tras los mismos contratos), que **nace con sus pruebas** (integración con Ollama/Whisper/Piper y evals de latencia real) conforme a esta política.
