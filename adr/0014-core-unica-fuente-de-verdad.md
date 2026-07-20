---
adr: 14
titulo: "El Core es la única fuente de verdad; el LLM nunca es autoridad sobre los hechos"
estado: accepted
fecha: 2026-07-19
decide: "CEO (gate ALERTA-004)"
propone: "CTO"
supersede: null
relacionado: "ADR-0001 (local-first), ADR-0003 (HITL), ADR-0010 (Ollama), D15, D18, 4.1 §4"
---

# ADR-0014 — El Core es la única fuente de verdad

## Principio

> **La verdad del sistema nunca dependerá del comportamiento probabilístico de un modelo de lenguaje.**

Los modelos de IA son **motores de razonamiento y generación**, nunca **autoridades sobre los hechos
del sistema**. Ningún LLM tiene potestad para inferir, completar o reformular hechos que el núcleo
puede determinar de forma exacta.

## Contexto

ALERTA-004 (2026-07-19) reveló que la garantía de grounding / no-fabricación (Bible 4.1 §4) estaba
**declarada pero no implementada**. Con la memoria vacía, ante *"¿Qué acordamos sobre el presupuesto?"*,
el sistema respondió *"Establecemos la consulta sobre el presupuesto para el próximo trimestre"* — sin
revelar que no existía ningún registro.

El hallazgo determinante fue el **contraste** entre garantías dentro del mismo milestone:

| Garantía | Impuesta por | Resultado con LLM real |
|---|---|---|
| HITL lista roja | **el núcleo** | ✅ 3/3 detenidas |
| Grounding | *nadie* (se asumía del modelo) | ❌ fallo |

Las garantías que impone el núcleo sobrevivieron al paso de mocks a modelo real. La que se delegaba
implícitamente en el LLM, no. Además, la eval de grounding pasaba con mocks porque **el doble de prueba
estaba escrito para pasarla**: verificaba el mock, no el sistema.

## Decisión

1. **Imposición determinista en el orquestador.** Cuando la búsqueda de memoria devuelve cero
   resultados **y** el usuario pregunta por un recuerdo, el Core responde declarando la ausencia de
   registro y **no se realiza ninguna llamada al LLM**. No se le concede la oportunidad de inventar.

2. **La detección también es determinista.** Identificar "el usuario pregunta por un recuerdo" se hace
   por patrones en el núcleo, no por clasificación del modelo: delegar esa decisión en el LLM
   reintroduciría la dependencia que la decisión elimina.

3. **Refuerzo del prompt (defensa en profundidad).** El sistema instruye al modelo a no afirmar ni
   insinuar información inexistente cuando el contexto de memoria viene vacío. Es una **segunda
   barrera**, nunca el mecanismo de cumplimiento.

4. **Regla general para todo guardarraíl futuro.** Ninguna garantía del sistema puede depender de que
   un modelo se comporte como se espera. Toda garantía debe ser **código verificable con prueba
   determinista**. Si no se puede escribir esa prueba, no es una garantía: es una expectativa.

## Consecuencias

**Positivas.** El grounding pasa a ser verificable (`tests/unit/test_grounding_core.py`: el proveedor
es un espía que debe registrar **cero** llamadas). Elimina una inferencia completa —150.000-300.000 ms
en el hardware actual— cuando no hay nada que recordar. Independiente del modelo: cambiar de LLM,
de temperatura o de proveedor no puede romper la garantía.

**Negativas / límites.** La detección por patrones puede no reconocer formulaciones inusuales de una
consulta de memoria; en ese caso el turno sigue el camino normal y actúa la segunda barrera (prompt).
Es un fallo **degradado**, no silencioso, y ampliable con nuevos patrones y sus pruebas.

**Coste.** Cero dependencias nuevas (satisface D26). ~40 líneas de núcleo y 6 pruebas.

## Alternativas descartadas

- **Solo prompt (B sola):** probabilística y no verificable de forma determinista. Descartada como
  mecanismo de cumplimiento; retenida como refuerzo.
- **Aceptar el riesgo (C):** el grounding es constitutivo de un Sistema Operativo de Inteligencia
  Personal (D18). Un PIOS que confabula sobre lo acordado destruye la confianza que justifica su
  existencia.
