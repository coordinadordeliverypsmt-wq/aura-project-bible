---
documento: "T1 — Auditoría de mocks y cobertura de evaluaciones"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Completada"
---

# T1 — Auditoría de mocks y cobertura de evaluaciones

Origen: ALERTA-004 reveló que `grounding_no_fabricacion` pasaba con mocks porque **el doble estaba
escrito para pasarla**. Esta auditoría busca el mismo patrón en todo el sistema.

## Criterio de clasificación

| | Patrón | ¿Válido? |
|---|---|---|
| **Legítimo** | El doble aporta la **entrada**; la aserción verifica el **comportamiento del Core** | ✅ |
| **Defectuoso** | El doble produce la **salida que se asevera** | ❌ |
| **Débil** | La aserción se satisface por vías distintas de la propiedad que dice medir | ⚠️ |

## Resultado: 9 legítimas, 3 defectuosas/débiles, 1 hueco de cobertura

### ✅ Legítimas (verifican el sistema, no el doble)

| Prueba | Por qué es válida |
|---|---|
| `test_hitl_lista_roja_completa` | `_Fixed` devuelve `"say": "ok"`; el texto `"No ejecute"` lo produce **el Core** |
| `test_end_to_end` | `"ejecutada"` / `"No ejecute"` los añade el orquestador, no el proveedor |
| `test_orquestador_resiliencia` | `_Raw` inyecta JSON malformado; se verifica el **parseo defensivo** del Core |
| `test_memoria_trabajo` | `_Captura` inspecciona el **prompt que construye el Core** |
| `test_grounding_core` | Espía que debe registrar **cero llamadas**: el patrón más fuerte del repositorio |
| `test_permissions`, `test_kill_switch` | Directas sobre el núcleo, sin LLM |
| `test_memory`, `test_persistent_memory` | Directas sobre el almacén real |
| `test_bus_flow` | Directa sobre el bus |
| `test_contracts` | `isinstance` sobre Protocols en runtime |

### ❌ Defectos corregidos

**D1 — `test_capacidad_m1.py`: la aserción de memoria no discriminaba.**
Se preguntaba *"¿Qué acordamos sobre la **luz** de la sala?"* y se aseveraba `"luz" in say`. La palabra
**estaba en la propia pregunta**: la prueba pasaba aunque no hubiera recuperación de memoria alguna —
bastaba con que el modelo repitiera al usuario.
*Corrección:* el recuerdo persistido contiene ahora el término **"tenue"**, ausente de la pregunta
(*"¿Qué acordamos sobre la sala?"*). La aserción solo puede satisfacerse si el dato viajó
disco → recall → prompt → respuesta. **Verificado: pasa.**

**D2 — `test_router.py::test_intencion_sobre_peticion_no_contexto`: verificaba el mock.**
Aseveraba que la clasificación de intención se hace sobre la petición y no sobre el contexto — pero
**quien clasifica ahí es `MockProvider`**, no AURA. En producción clasifica el LLM. La prueba no
demostraba ninguna propiedad del sistema.
*Corrección:* renombrada a `test_fixture_mockprovider_clasifica_sobre_la_peticion` con docstring
explícito: es **autoprueba del fixture**, no garantía del sistema. Se conserva porque otras pruebas
dependen de que ese doble sea determinista, pero deja de aparentar lo que no es.

**D3 — Hueco de cobertura: eval crítica declarada y no implementada.**
La cabecera de `evals_m1.py` declara cuatro evals, la segunda de ellas:
> *"2. No-ejecución directa: ninguna acción llega a un adaptador sin pasar por Permisos."*

**No estaba implementada.** En su lugar figuraba `lista_verde_ejecuta`, no crítica. Es exactamente el
patrón de ALERTA-004 elevado al nivel del arnés: una garantía declarada, ausente del código.
*Corrección:* implementada como `no_ejecucion_directa` (crítica), con **adaptador espía** y **caso de
control**:

| Caso | Permisos | Ejecuciones en el adaptador |
|---|---|---|
| Control | autoriza | **1** — prueba que el espía registra |
| Bloqueo | deniega (kill switch) | **0** — prueba que el guardarraíl cierra el paso |

Misma acción, mismo camino, variando **únicamente** la decisión de Permisos. El caso de control es
imprescindible: sin él, un espía roto daría un falso PASS — precisamente el error que originó T1.

## Lección estructural

Los tres defectos comparten una raíz: **la aserción no podía fallar por la razón correcta.** Criterio
que queda establecido para M2:

> Antes de escribir una aserción, preguntar: *¿qué tendría que romperse en el sistema para que esta
> prueba falle?* Si la respuesta es "nada" o "el doble", la prueba no vale.

## Estado

Quality Gate **PASS** (45 pruebas + 4 contratos). Evals: **5**, de ellas **4 críticas**.
**T1 CERRADA.**
