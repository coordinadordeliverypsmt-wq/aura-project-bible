# Mapa de decisión — `D-CP-4` (criterio ejecutable) y `D-CP-5` (esquema cerrado)

> **ACTUALIZACIÓN 2026-08-25 — `D-CP-7` CERRADA:** `F-DCP7 = GREEN respecto al WORKER ADMINISTRADO`. `bwrap` + user namespace es enforcement real para el Worker dentro de la jaula. **Constraint arquitectónico permanente, no deuda:** no protege frente a otro proceso del **mismo UID**; sin privilegios esa frontera no se considera cerrable. **Siguen ABIERTOS** —y no se presentan como cerrados— el lanzador omitible, el TOCTOU, credencial+red, el audit log `rw` y la cobertura incompleta del hook. **Sigue abierta `D-CP-3`.**


> **ACTUALIZACIÓN 2026-08-23 — `D-CP-5` YA ESTÁ DECIDIDA E IMPLEMENTADA:** esquema CERRADO por tipo, con RED, GREEN, mutación 6/6 sin supervivientes y auditoría independiente. **Decisión del CEO del 2026-08-23** (mensaje de encargo: *«La decisión vigente es ESQUEMA CERRADO POR TIPO»*), registrada tardíamente el mismo día tras una auditoría independiente que señaló su ausencia como artefacto. Lo detectó esa misma auditoría: cinco documentos seguían declarándola abierta mientras el código ya la implementaba — «declarado ≠ real», esta vez del lado de la gobernanza. **Siguen abiertas `D-CP-7` y `D-CP-3`.**


**Fecha:** 2026-08-18 · **Decide:** CEO · **Prepara:** APUS-5
**Estado de ambas: `DECISION_REQUIRED` cuando se escribió este mapa (2026-08-18).**
> **ACTUALIZACIÓN 2026-08-23 — `D-CP-4` YA ESTÁ DECIDIDA: alternativa (C) = A + B**, por el CEO,
> e implementada, mutada y auditada. Con ella se resolvió además la contradicción con `ADR-0003`
> (solo lo VERDE puede ser criterio AUTO) y se cerró `D-CP-6` (a). **`D-CP-5` sigue abierta.**
> El análisis de abajo se conserva sin retocar: es el registro de cómo se tomó la decisión, no su
> estado actual. Lo señaló una auditoría independiente al detectar que este documento decía lo
> contrario de lo que el código ya hacía — «declarado ≠ real» del lado de la documentación. Este documento **no elige**, no implementa y no modifica
`DP-ORCH` ni `CLAUDE.md`: la contradicción permanece visible por orden expresa.
**Clasificación D47:** `[EJEC]` medido · `[LECT]` leído · `[INFER]` deducido.

---

## 1 · `D-CP-4` — las tres alternativas

### A · Catálogo cerrado de capacidades

*El criterio nombra una **capacidad registrada** (`ejecutar_pruebas`, `verificar_calidad`), nunca una
orden de shell.*

| | |
|---|---|
| **Respeta** | `CLAUDE.md` (CEO 2026-08-03): *«AURORA nunca ejecuta instrucciones arbitrarias del SO: solo CAPACIDADES registradas, gobernadas por el Motor Único»*, y su corolario de nombrarlas **por el resultado**, no por la herramienta · `ALERTA-005` (motor único) · `ADR-0003` (listas) |
| **Contradice** | `DP-ORCH §14.bis` **regla 2**, que exige *«un comando verificable de terceros»*. Un nombre de capacidad **no es** un comando |
| **Conserva de §14.bis** | Reglas **1** (lo fija quien crea la tarea, antes de invocar), **3** (lo ejecuta el Orchestrator, no el Worker) y **4** (si no es expresable, no es AUTO) |
| **Cambia** | Solo la regla **2**: «comando verificable» → «capacidad registrada del catálogo» |
| **¿Modifica `CLAUDE.md`?** | **No.** Es la alternativa que la honra |
| **¿Requiere ADR?** | `[INFER]` **Probablemente no para arrancar.** `[EJEC]` El catálogo **ya contiene** `ejecutar_pruebas`, `verificar_calidad`, `auditar_garantias` y `diagnosticar_estado`, las cuatro **verdes**. Añadir capacidades nuevas sí exigiría acta (D23) |
| **Elimina V1** | **Sí.** `cuerpo` solo puede nombrar; nombrar no concede ejecución arbitraria |
| **Elimina V3** | **En su mayor parte.** Un modelo persuadido, como mucho, consigue que corra una capacidad **ya catalogada y gobernada** por permisos y kill switch |
| **Permanece** | **Los argumentos.** `ejecutar_pruebas(ruta=…)` sigue admitiendo un valor del atacante. La validación de argumentos es un hueco aparte |
| **Implementación** | Mapear criterio→capacidad · validar argumentos · enrutar el Orchestrator por el Motor |
| **RED/GREEN** | RED: una cadena de shell se rechaza; solo se aceptan nombres del catálogo; argumentos validados. GREEN: el criterio se resuelve contra el catálogo |
| **Riesgos** | **Reduce lo automatizable.** `§14.bis` ya aceptó esa consecuencia por escrito: *«esto reduce el alcance de lo automatizable, y es lo correcto»* |
| **Separación** | **Preservada.** La ejecución pasa por el Motor |

### B · El criterio nunca viaja en `cuerpo`; solo procede del Control Plane

| | |
|---|---|
| **Respeta** | `DP-CP §10`: *«el canal pregunta al Control Plane; el Control Plane nunca pregunta al canal»* |
| **Contradice** | **Nada de forma directa.** Rompe un **supuesto implícito** de `§14.bis` regla 1: que quien crea la tarea es de confianza. En el canal es un agente par |
| **Conserva de §14.bis** | Reglas **2**, **3** y **4** |
| **Cambia** | El **origen** admisible del criterio, no su forma |
| **¿Modifica `CLAUDE.md`?** | **No** |
| **¿Requiere ADR?** | `[INFER]` No: es una restricción de protocolo |
| **Elimina V1** | **Sí, por la vía del canal.** Un mensaje no puede transportar criterio |
| **Elimina V3** | **NO.** Un modelo persuadido sigue teniendo sus propias herramientas. B cierra **la ruta del canal**, no la del agente |
| **Permanece** | El criterio **sigue siendo una orden libre**: quien lo escriba en el Control Plane tiene ejecución arbitraria. **B mueve la frontera de confianza; no la elimina** |
| **Implementación** | El esquema rechaza `criterio` en `cuerpo` · el Control Plane los almacena · el Orchestrator los lee de allí |
| **RED/GREEN** | RED: `criterio` en `cuerpo` → `MensajeInvalido` (**ya escrita**, en rojo) · el Orchestrator solo lee criterios del Control Plane |
| **Riesgos** | **Rigidez.** Cada tarea nueva exigiría un criterio **pre-registrado por un humano**. `[INFER]` Eso puede vaciar de sentido la orquestación automática: si un humano debe intervenir por tarea, la autonomía no sube |
| **Separación** | **Preservada** |

### C · A + B

| | |
|---|---|
| **Efecto** | V1 cerrado **en dos niveles independientes**: por **origen** (B) y por **forma** (A) |
| **Conserva/cambia** | La unión de ambas: cambia la regla 2 y restringe el origen |
| **Elimina V1** | **Sí, con redundancia deliberada** — defensa en profundidad, el mismo criterio que `DP-D-M-8 §4.1` aplica al kill switch |
| **Elimina V3** | Lo mismo que A. **B no aporta nada extra contra V3** |
| **Permanece** | Validación de argumentos · las rutas de V3 ajenas al canal |
| **Riesgos** | **Rigidez máxima**: suma la de B a la de A |
| **Separación** | **Preservada** |

### Comparación — lo que de verdad las distingue

> **A y B no son dos formas de lo mismo.** **B controla de dónde viene el criterio; A controla qué
> puede llegar a ejecutarse.** Por eso **solo A ataca V3**: contra un modelo persuadido no sirve saber
> quién escribió el texto, sino que lo ejecutable esté acotado de antemano.

| | A | B | C |
|---|---|---|---|
| Cierra **V1** | ✅ | ✅ | ✅✅ |
| Cierra **V3** (lo que el canal puede) | ✅ | ❌ | ✅ |
| Contradice una fuente de verdad | **Sí** — `§14.bis` regla 2 | No | Sí (por A) |
| Coste de rigidez | Medio | **Alto** | Alto |
| Aprovecha lo ya construido | **Sí** — 4 capacidades verdes ya existen `[EJEC]` | Parcial | Sí |

### Preguntas que quedan (`D-CP-4`)

1. ¿Se acepta **modificar la regla 2 de `§14.bis`**, que es parte de un DP ya aprobado?
2. ¿Quién valida los **argumentos** de la capacidad? Ninguna de las tres lo resuelve.
3. Si B exige criterios pre-registrados por un humano, **¿queda algo automatizable?**
4. ¿La redundancia de C se considera defensa en profundidad o coste sin retorno?

---

## 2 · `D-CP-5` — lista negra → esquema cerrado

### Situación actual: lista negra

`DP-CP §4.2` prohíbe **seis nombres de campo**: `autoriza`, `aprueba`, `permiso`, `permite`,
`autorizacion`, `override`. **Demostrada solo a profundidad 1** `[EJEC]`.

**Insuficiente por construcción:** no cubre anidamiento (`datos→meta→autoriza`), ni sinónimos
(`granted`, `approved`), ni otro idioma, ni paráfrasis. **Una lista negra de palabras es infinita.**

### Alternativa: esquema cerrado por tipo

| Clase | Campos | Quién los escribe |
|---|---|---|
| **Metadatos del canal** | `seq`, `id`, `instante`, `hash_anterior`, `hash` | **El canal.** Un agente no los propone |
| **Enrutamiento** | `tipo`, `de`, `para`, `in_reply_to` | El emisor, validados contra listas cerradas |
| **Anclaje de estado** | `estado_leido` | El emisor; el receptor lo contrasta |
| **Datos** | `cuerpo`, validado contra el esquema **cerrado del `tipo`** | El emisor |

**Campos que podrían convertirse en autoridad:** `cuerpo` —cualquier subcampo— y **`de`**, porque una
identidad suplantada es autoridad prestada (`D-CP-3`).

**Cómo impide V4:** invierte la lógica. En vez de enumerar lo prohibido —infinito—, enumera **lo
permitido** —finito—, con validación **recursiva** y tipos declarados. `datos→meta→autoriza` se
rechaza porque `meta` no está declarado, no porque `autoriza` esté prohibido.

**Ataques que siguen siendo posibles:**

1. **Autoridad dentro de un campo de texto legítimo.** Si `TASK` declara `descripcion: str`, la frase
   *«el CEO ya lo aprobó»* cabe ahí y es sintácticamente válida.
2. **Suplantación de `de`** mientras la identidad sea declarativa (`D-CP-3`).
3. **Persuasión semántica** sobre el receptor: un esquema valida **forma**, no **intención**.

> **Lo que un esquema cerrado NO puede garantizar frente a un LLM:** que el modelo no lea el texto
> permitido como una orden. **Ningún mecanismo sintáctico puede.** La barrera efectiva es que
> `cuerpo` se entregue marcado como dato no confiable **y que no exista ruta de ejecución desde él**
> — lo cual es `D-CP-4`.

**Relación con V1/V3:** el esquema cerrado **acota qué campos existen**; `D-CP-4` acota **qué puede
ejecutarse**. Son ortogonales y ninguna sustituye a la otra.

**¿Puede resolverse D-CP-5 independientemente de D-CP-4?** **Sí, y es la única de las dos que puede.**
Es una decisión de validación, no de ejecución. **Pero no cierra V1 por sí sola:** si el esquema
declarase `criterio: str` como campo legítimo, el contrabando volvería por la puerta principal.

### Preguntas que quedan (`D-CP-5`)

1. ¿Se acepta reescribir `§4.2` del `DP-CP` —de lista negra a esquema cerrado— en un DP ya emitido?
2. ¿Qué campos de texto libre se admiten, si alguno? Cada uno es una superficie de persuasión.
3. ¿Se declara `criterio` como campo del esquema? **Esa respuesta la fija `D-CP-4`, no esta decisión.**

---

## 3 · `D-CP-4` + `D-CP-5` juntas — ¿frontera suficiente?

```
LLM ─────────────▶ PROPUESTA        (texto; nunca autoridad)
Communication Plane ▶ TRANSPORTE    (esquema cerrado: D-CP-5)
Control Plane ──────▶ AUTORIZACIÓN  (única fuente; el canal solo lee)
Motor Único ────────▶ EJECUCIÓN     (catálogo cerrado: D-CP-4/A)
```

**Con A+B+esquema cerrado, la frontera es coherente y cada capa hace una sola cosa.** Pero quedan
**tres rutas** que ninguna de las dos decisiones cierra, y decirlo es parte del mapa:

| # | Ruta que permanece | De quién es el problema |
|---|---|---|
| **R-1** | **Argumentos** de una capacidad catalogada, controlados por el atacante | `D-CP-4`, sin resolver en las tres alternativas |
| **R-2** | **El agente ejecutor tiene sus propias herramientas.** Una sesión de Claude Code con `Bash` no necesita el canal para ejecutar nada | **Fuera del alcance del canal.** Es `--permission-mode` / `--allowedTools` `[EJEC]` y el hook `PreToolUse`, que `DP-ORCH §14.ter` declara `[LECT]`, **no medido** |
| **R-3** | **Identidad declarativa** (`D-CP-3`): quien escriba en el disco puede firmar como otro | `D-CP-3`, pendiente |

> **La conclusión honesta: `D-CP-4` + `D-CP-5` hacen que el canal deje de ser una fuente de autoridad
> accidental. No hacen que el sistema sea seguro.** El agente ejecutor sigue teniendo capacidades
> propias que el canal no gobierna, y afirmar lo contrario sería INV-9.

---

## 4 · Dependencias y veredicto

| Pregunta | Respuesta |
|---|---|
| **¿Qué debe resolverse primero?** | **`D-CP-4`**. Determina si `criterio` puede existir como campo, y por tanto condiciona el esquema de `D-CP-5` |
| **¿Qué puede resolverse por separado?** | **`D-CP-5`** — decisión de validación, independiente de la de ejecución. Pero **no cierra V1 sola** |
| **¿Alguna cierra V3?** | Solo **`D-CP-4/A`**, y **parcialmente**: acota lo ejecutable, no impide la persuasión |
| **¿Se puede construir el canal sin ambas?** | **No.** Sección E dio veredicto **(B)**: la garantía no está demostrada |

**VEREDICTO: ninguna alternativa se elige.** `D-CP-4` y `D-CP-5` permanecen **`DECISION_REQUIRED`**.
La contradicción entre `DP-ORCH §14.bis` regla 2 y `CLAUDE.md` **permanece visible y sin corregir**,
por orden expresa del CEO.
