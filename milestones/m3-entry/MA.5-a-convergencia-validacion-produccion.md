---
documento: "MA.5-a — Convergencia validacion↔produccion: precision de D40 y clasificacion de arneses"
fecha: 2026-07-22
autor: "CTO"
estado: "Aprobada por el CEO (2026-07-22). Implementacion en curso segun el orden de la seccion 5."
origen: "Contradiccion reportada 2026-07-22; opcion (b) aprobada; ver ADR-0018 y D41"
---

# MA.5-a — Convergencia validacion↔produccion

Depende de **ADR-0018** (bus por escenario) y del principio **D41** (fuente unica de verdad). Este
documento **explica y justifica** la clasificacion de los ejecutables; la clasificacion **operativa**
vive en un unico manifiesto versionado (seccion 3). Si documento y manifiesto divergen, **manda el
manifiesto**.

## 1. Precision de D40 (registrada en el acta, 2026-07-22)

D40.2 se precisa asi: el **unico punto de entrada de produccion** es `python -m aura_skeleton`, y
**debe consumir `composicion.componer()`**. Los **arneses de validacion** pueden ensamblar variantes
deliberadas de la arquitectura (otro bus, varios proveedores, un componente aislado) **solo si estan
declarados en la fuente unica de clasificacion** (manifiesto, D41), y **nunca** como puntos de entrada
de produccion. Todo ejecutable que construya el sistema y no este clasificado es una violacion de D40,
verificada por prueba anti-regresion.

## 2. Clasificacion de los 9 scripts (con evidencia)

Esta es la version **narrada** de la clasificacion. La version **operativa** es el manifiesto (seccion 3).

**Produccion (unico punto de entrada):**

| Ejecutable | Estado |
|---|---|
| `python -m aura_skeleton` (`__main__.py` + `composicion.py`) | Consume `composicion`. Cumple D40. |

**Validacion vigente (arneses autorizados):**

| Arnes | Por que es vigente (evidencia) |
|---|---|
| `run_demo_nats.py` | Unica prueba viva de sustituibilidad de bus in-process→NATS (P-ARQ-4). `bus_nats.py` tiene 0 cobertura automatizada; este arnes es lo unico que lo ejercita. Valida E2 (ADR-0018). |
| `run_demo_real.py` | Unico e2e sobre stack real (NATS+Ollama+Whisper+Piper) para HC-1. HC-1 sigue ABIERTO → vigente hasta validar en hardware. |
| `validar_m1.py` | Instrumenta latencia HC-1 sobre hardware (uso `--real` diferido). |
| `evals_m1.py` | Evals de seguridad de IA sobre modelo real (HITL lista roja, grounding, consistencia). Uso `--real`/hardware. |
| `demo_capacidad_m1.py` | Demo de capacidad M1; la ruta `--real` es la demo oficial en hardware. (La ruta mock solapa con `tests/e2e/test_capacidad_m1.py`.) |
| `demo_capacidad_m2.py` | Demo de capacidad M2 reproducible. **Arnes autorizado** (opcion B, 2026-07-22): necesita `_ProveedorGuiado`, un doble determinista que mapea cada frase a su accion; no tendria sentido en produccion (criterio de admision, D40.5). `composicion` no inyecta proveedores, y no se cambia produccion. No se reescribe. |
| `validar_voz_t2.py` | Valida el adaptador de voz Whisper/Piper aislado. **No construye `Orchestrator`** → D40 no le aplica. |
| `generar_m1_exit.py` | Generador de informe (no construye `Orchestrator`); consume el JSON de los arneses `--real`. |

**Obsoletos (candidatos a eliminacion, con evidencia de cobertura equivalente):**

| Candidato | Evidencia de que ya no aporta cobertura |
|---|---|
| `run_demo.py` | Su fallback/circuit-breaker esta cubierto por `tests/unit/test_router.py::test_fallback_a_proveedor_sano`; su flujo conversacional (memoria/HITL/kill switch/persistencia) por `tests/e2e/test_capacidad_m1.py`. No tiene proposito de hardware (lo real lo cubre `run_demo_real.py`). Como forma de "correr AURA" queda superseded por `python -m aura_skeleton`. **Propuesto a eliminacion tras verificacion adicional (seccion 5.7).** |

**Resultado honesto:** la divergencia "8/9" de la revision pre-M3 **era real**, pero su correccion para
la mayoria es *clasificar y documentar como arnes autorizado*, no reescribir ni borrar. Solo
`run_demo.py` es candidato claro a obsoleto.

## 3. Fuente unica de verdad: el manifiesto (D41)

La clasificacion **no se codifica en la prueba ni se duplica aqui como lista operativa**. Vive en
**`walking-skeleton/architecture_manifest.toml`**, que la prueba anti-regresion lee (seccion 4). El
manifiesto declara cuatro grupos: `produccion` (consume `composicion`), `arneses` (autorizados a
ensamblar variantes, con `motivo`), `no_construyen_sistema` (no crean `Orchestrator`) y `obsoletos`
(candidatos con `motivo`). Agregar o reclasificar un ejecutable es un cambio en **un solo sitio**.

## 4. Especificacion de la prueba anti-regresion (lee el manifiesto)

Verifica **exactamente** la propiedad pedida, de forma estatica (sin ejecutar los scripts) y **leyendo
el manifiesto (D41)** como unica fuente:

1. **Cobertura total:** todo ejecutable `.py` que construya el sistema (contiene `Orchestrator(`) debe
   estar clasificado en el manifiesto. Un ejecutable nuevo sin clasificar **falla** la prueba — asi
   ninguno puede aparecer fuera de la clasificacion.
2. **Produccion consume `composicion`:** los ejecutables de `produccion` (`__main__.py`) **no**
   construyen `Orchestrator(` directamente; entran por `composicion`.
3. **Solo arneses declarados** construyen el sistema fuera de `composicion`: cualquier `.py` con
   `Orchestrator(` que no este en `arneses` (ni sea `composicion`) es una violacion.
4. **Consistencia del manifiesto:** cada entrada apunta a un fichero que existe (sin clasificaciones fantasma).

Se verifica ademas —igual que con las pruebas de escalabilidad— que la prueba **falla** ante una
regresion real: un script-doble que construye `Orchestrator` sin declararse debe dispararla.

## 5. Plan de implementacion (orden aprobado por el CEO, 2026-07-22)

1. Commit de **ADR-0018**.
2. Commit de la **precision de D40 + D41 + esta clasificacion**.
3. Crear el **manifiesto** `walking-skeleton/architecture_manifest.toml` (fuente unica, D41).
4. Clasificar **`demo_capacidad_m2.py`** como arnes autorizado en el manifiesto (opcion B, 2026-07-22): necesita un proveedor guionado que no cabe en produccion (D40.5). No se reescribe ni se toca produccion.
5. Implementar la **prueba anti-regresion** (seccion 4) **leyendo el manifiesto**.
6. Ejecutar el **Quality Gate**.
7. Si el Gate sigue verde, **proponer** la eliminacion de `run_demo.py` (no eliminarla). Antes de
   proponerla, verificar ademas: **(a)** que ningun documento, script de CI, README o guia lo
   referencia; **(b)** que ninguna prueba depende de el, ni directa ni indirecta. Solo si ambas son
   positivas se propone su eliminacion, en un paso independiente.

**Nada de lo anterior toca `composicion` ni el bus** (ADR-0018 no cambia produccion).
