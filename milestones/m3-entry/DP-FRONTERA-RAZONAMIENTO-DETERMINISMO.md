# DP · La frontera entre el razonamiento del modelo y la representación determinista de una acción

**Estado:** PROPUESTO — **exclusivamente analítico**. No se propone implementar nada, no hay diseño
cerrado, y **no debe asumirse que esta arquitectura será aprobada**.
**Fecha:** 2026-08-15 · Producto: `main` = `origin/main` = `d933a08`, intacto. Sin commits.
**Evidencia:** sólo mediciones ya realizadas. Clasificación D47: `[EJEC]` · `[LECT]` · `[INFER]` · `[HIPO]`.

---

## 0 · La pregunta

> **¿Cuál debe ser la frontera entre el razonamiento del modelo local y la representación/validación
> determinista de una acción de AURORA?**

---

## 1 · Qué capacidad semántica demostró `qwen2.5:0.5b`

Tres turnos completos, mismo caso, mismo prompt `[EJEC]`:

| # | `action` | ¿En catálogo? | `args` |
|---|---|---|---|
| 1 | `corregir` | no | `patron: ""`, `ruta: mutaciones/laboratorio-humo.toml` |
| 2 | `revisar` | no | `ruta: mutaciones/laboratorio-humo.toml` |
| 3 | `monitoreo` | **sí** (verde, lectura) | `patron: laboratorio-humo.toml:H1`, `ruta: mutaciones/laboratorio-humo.toml` |

**Demostrado:** JSON válido 3 de 3. **Identificación correcta del artefacto 3 de 3** — el TOML, nunca
otro fichero. Intención en prosa coherente («corregir la declaración»).
**No demostrado:** selección fiable de la capacidad (1 de 3 en catálogo, y esa incorrecta).

## 2 · Qué capacidad adicional demostró `qwen2.5:3b`

Un turno, **mismos bytes de entrada** (SHA `58159836…`) `[EJEC]`:

```json
{"intent":"modificar_configuracion","action":"modificar_configuracion",
 "args":{"ruta":"mutaciones/laboratorio-humo.toml"},
 "say":"Voy a modificar la configuración de tu fichero para corregir el problema con la garantía."}
```

**Mejora real y acotada:** eligió una acción **del catálogo**, de **lista roja** y **efecto altera** —
la familia correcta—, frente al `monitoreo` verde de lectura del `0.5b`. Y su `say` describe el
propósito con precisión.

**Lo que costó:** 786,2 s de inferencia frente a 266,9 s — **2,9× más lento** — a 1,14 tok/s de
ingesta `[EJEC]`.

**Conclusión acotada:** el salto de tamaño compró **selección semántica**, no formulación.

## 3 · Qué sigue fallando en ambos

**Los tres campos que el ejecutor necesita —`fichero`, `buscar`, `sustituir`— faltaron en 4 de 4
respuestas** `[EJEC]`. Ninguno de los dos modelos produjo uno solo.

Y hay un matiz que cambia el diagnóstico:

| Campo | ¿Está en el contexto que AURORA transporta? | ¿Lo produjo algún modelo? |
|---|---|---|
| `fichero` | **Sí** — `fichero_declarado` | no (usaron `ruta` con el valor correcto) |
| `buscar` | **Sí** — `buscar_declarado`, literal | **no, ni una vez** |
| `sustituir` | **No, y no puede estar** — exige decidir un patrón nuevo | no |

**Dos de los tres campos son transcripción, no razonamiento.** Sus valores ya viajan en la tarea
derivada. Los modelos fallaron en copiar datos que se les habían dado — y el valor correcto del
fichero sí lo emitieron, pero **bajo otro nombre**.

## 4 · ¿El catálogo actual exige al LLM resolver detalles que deberían ser deterministas?

**Sí, y la evidencia es más concreta de lo que esperaba** `[LECT]`.

`_catalogo_para_prompt()` anexa el esquema de argumentos **sólo** a las acciones presentes en
`ESPECIFICACIONES`. Lo que el modelo ve, literalmente:

```
- leer_archivo (verde) args: {ruta}
- proponer_cambio (roja)              ← sin esquema
- modificar_configuracion (roja)      ← sin esquema
```

Frecuencia de los nombres de argumento que **sí** se le muestran, en las diez acciones con esquema:

| Nombre | Veces |
|---|---|
| **`ruta`** | **6** |
| `origen` / `destino` | 2 / 2 |
| **`patron`** | **1** |
| `raiz`, `contenido` | 1 / 1 |

**El patrón de conducta encaja exactamente con lo que se le mostró:**

- Las **cuatro** acciones elegidas por los modelos —`corregir`, `revisar`, `monitoreo`,
  `modificar_configuracion`— son acciones **sin esquema de argumentos** en el prompt.
- Los **únicos** nombres de argumento que usaron —`ruta` y `patron`— son **los dos más frecuentes**
  del catálogo que sí vieron.

`[INFER]` Los modelos **generalizaron el esquema que se les enseñó para otras acciones**. No inventaron
al azar: rellenaron un hueco con la forma más disponible. Eso convierte parte del fallo en
**informacional**, no puramente de capacidad — aunque **no permite cuantificar cuánta parte**, y
sostenerlo requeriría medirlo.

**Este factor afecta por igual a los dos modelos**, así que no invalida la comparación entre ellos.

## 5 · Qué representación mínima podría producir el razonador sin autoridad de ejecución

Análisis de opciones, **sin elegir ninguna**:

| Opción | Qué pide al modelo | Autoridad que le otorga |
|---|---|---|
| **A · Acción completa** (actual) | acción + todos los argumentos | Ninguna de ejecución: el núcleo valida y el humano confirma. Pero le pide **transcribir** lo que ya se le dio |
| **B · Sólo lo inferencial** | únicamente el valor que **no** está en el contexto (el patrón nuevo) | La mínima. Todo lo demás lo aporta el contexto transportado |
| **C · Intención + referencia** | una etiqueta de intención de un conjunto cerrado, más el identificador de la garantía | Menor aún, pero traslada la decisión del patrón a otro sitio — y ese sitio hoy no existe |

**Lo que la evidencia dice de cada una:** A ha fallado 4 de 4 `[EJEC]`. B y C **no se han medido**
`[HIPO]`. Ninguna se propone.

**Principio que sí puede afirmarse:** el razonador nunca debe ser la fuente de un dato que el sistema
ya posee. Cada campo que se le pide transcribir es una oportunidad de error sin ninguna ganancia.

## 6 · Qué podría compilarse o validarse deterministamente

| Elemento | ¿Determinista? | Por qué |
|---|---|---|
| Pertenencia de la acción al catálogo | **Sí** | Es una comprobación de pertenencia a un conjunto cerrado. **Ya ocurre**: el núcleo rechazó las acciones inventadas `[EJEC]` |
| `fichero` | **Sí** — transcripción | El valor está en `fichero_declarado` |
| `buscar` | **Sí** — transcripción | El valor está en `buscar_declarado`, literal |
| Esquema de argumentos | **Sí** | Comparable contra `ESPECIFICACIONES`, **si la acción estuviera declarada allí** — hoy `proponer_cambio` no lo está (deuda I-1) `[LECT]` |
| Viabilidad | **Sí** | El dry-run real ya lo resuelve `[EJEC]` |
| **`sustituir`** | **NO** | Exige leer el fichero objetivo y **decidir** un patrón nuevo. Es razonamiento irreducible |

**La frontera que la evidencia sugiere** —como hipótesis, no como diseño—: **todo lo transcribible y
todo lo verificable, del lado determinista; sólo la decisión del patrón nuevo, del lado del modelo.**

## 7 · Cómo se preservarían las garantías

Ninguna de estas es una promesa de diseño: son **restricciones que cualquier propuesta tendría que
satisfacer**, y el modo de comprobarlo.

| Garantía | Restricción | Cómo se demuestra |
|---|---|---|
| **RN-2** — sin ejecución arbitraria | Una capa determinista sólo puede emitir acciones **de `CATALOGO`**, nunca construirlas | Prueba de pertenencia + mutante que la retire |
| **INV-9** — no fingir | **Cada valor emitido debe ser copia byte a byte de un valor presente en el contexto de entrada.** Con contexto vacío, salida vacía | Ver §8 |
| **ADR-0003** — consentimiento informado | La previsualización sigue siendo honesta y en ASCII; el humano confirma igual | Ya verificado `[EJEC]`, y protegido por C29/C30 |
| **Aprobación diferida + huella exacta** | La huella se calcula sobre los argumentos **finales**: cualquier relleno determinista debe ocurrir **antes** de calcularla, o la aprobación dejaría de corresponder a lo aprobado | Verificado hoy: una aprobación de otra huella **no** autoriza `[EJEC]` |
| **Kill switch** | Intacto, se comprueba antes de cada latido | Sin cambios |

**Riesgo de gobierno que hay que nombrar:** una capa que complete argumentos haría que **más** acciones
de lista roja lleguen al humano. Eso no es inseguro —la confirmación sigue siendo obligatoria— pero
**aumenta la carga de aprobación**, y un CEO saturado aprueba peor. Es un coste real del diseño.

## 8 · Cómo demostrar que una traducción determinista no inventa datos

La propiedad es comprobable y no requiere confiar en nadie:

1. **Invariante de procedencia.** Todo valor de salida ∈ conjunto de valores del contexto de entrada,
   comparado byte a byte. Verificable como propiedad, no como caso.
2. **Control de vacío.** Contexto sin datos accionables → salida **sin** campos de ejecución. Es el
   comportamiento que los casos 4–7 ya exigen.
3. **Mutación.** Un mutante que sustituya la transcripción por un valor fabricado —el patrón de C4—
   debe morir.
4. **Los siete casos como control.** En 4 de los 7 no hay datos accionables **por diseño**: si la capa
   produjera algo ejecutable ahí, sería fabricación y debería fallar la prueba.

**Esto es demostrable de forma fuerte**, y es la diferencia fundamental con pedírselo al modelo: de una
copia se puede probar la procedencia; de una generación, no.

## 9 · Cómo medir si la separación aumenta realmente 0/7

Volviendo a ejecutar los siete casos y contando cuántos producen una propuesta **completa y viable**,
con el mismo criterio conductual del DP de medición: `sustituir` aparece exactamente una vez en el
fichero objetivo.

**Y aquí está la objeción que este DP debe hacerse a sí mismo:**

**Aunque la frontera fuera perfecta, 0/7 podría seguir siendo 0/7.** La capa determinista llenaría
`fichero` y `buscar` —dos de tres—, pero **`sustituir` seguiría dependiendo del modelo**, y ninguno de
los dos lo ha producido jamás. Un contexto con dos de tres campos **no es ejecutable**: el todo-o-nada
lo degrada a `*_declarado`, exactamente como hoy.

`[INFER]` **La separación, por sí sola, no mueve la métrica.** Lo que cambiaría es *dónde* falla —de
«el modelo no acierta el formato» a «el modelo no decide el patrón»— y eso sí es medible y atacable.
Convertir un fallo difuso en uno localizado tiene valor, pero **no es autonomía nueva**, y presentarlo
como tal sería exactamente lo que este proyecto lleva evitando toda la sesión.

## 10 · Experimento mínimo para validar o refutar, antes de implementar nada

**Parte A — sin ninguna inferencia, ya es concluyente `[EJEC]`.** Reanalizando las cuatro respuestas
crudas ya capturadas: si una capa determinista hubiera transcrito `fichero` y `buscar` del contexto y
tomado la acción del modelo, **ninguna de las cuatro** habría producido una propuesta viable, porque
en las cuatro falta `sustituir`. **La hipótesis de suficiencia queda refutada sin gastar cómputo.**

**Parte B — la pregunta que queda, y es una sola.** ¿Puede el modelo producir **únicamente** el patrón
nuevo, si se le da el contenido del fichero objetivo y no se le pide nada más? Es una tarea mucho
menor que emitir una acción completa.

Ese experimento **exigiría un prompt distinto**, lo que rompe la comparabilidad con todo lo medido, y
por tanto **requeriría su propio Decision Package**. Se nombra; no se propone aquí.

**Coste estimado:** una inferencia por modelo, con la carga desacoplada como se validó hoy `[EJEC]`.

---

## 11 · Cierre

### Hipótesis

> El fallo de formulación no es principalmente de capacidad de razonamiento, sino de **frontera mal
> situada**: se le pide al modelo transcribir y respetar un esquema que el sistema conoce y que nunca
> le enseñó, en vez de pedirle sólo lo que exige razonar.

### Evidencia a favor

- Dos de los tres campos requeridos **son transcripción**: sus valores viajan ya en la tarea `[EJEC]`.
- Las **cuatro** acciones elegidas por los modelos son acciones **mostradas sin esquema de argumentos**
  `[LECT]`.
- Los **únicos** nombres de argumento usados, `ruta` y `patron`, son **los dos más frecuentes** del
  catálogo que sí se les mostró `[LECT]` — generalizaron lo que vieron `[INFER]`.
- El artefacto correcto se identificó **4 de 4** `[EJEC]`: la comprensión del problema existe.
- El `3b` acertó la **familia** de la acción —roja, altera— sin acertar el formato `[EJEC]`.

### Evidencia en contra

- **Ningún modelo produjo `sustituir` jamás** `[EJEC]`, y ése es el campo que la frontera **no** puede
  resolver. Es el bloqueante real.
- El `3b`, con 6× más parámetros, tampoco produjo ningún campo: **si el formato fuera el único
  obstáculo, cabría esperar alguna mejora ahí, y no la hubo** `[EJEC]`.
- La hipótesis del catálogo es `[INFER]` sobre **cuatro** respuestas. Coherente, pero no cuantificada.
- Un turno del `3b` cuesta **13 minutos** `[EJEC]`: aunque la frontera funcionara, la latencia sigue
  siendo un obstáculo aparte.

### Riesgos

1. **Que la frontera parezca resolver el problema sin moverlo.** §9: 0/7 podría no cambiar. Riesgo de
   declarar progreso donde sólo hay reubicación del fallo.
2. **Que tocar el catálogo rompa una garantía.** `_catalogo_para_prompt()` se deriva del catálogo real
   **precisamente** para que no puedan divergir, citando ALERTA-005. Cualquier cambio ahí exige su
   propio DP.
3. **Más carga de aprobación** sobre el CEO (§7).
4. **Que una capa determinista se convierta en un traductor con criterio propio** y acabe siendo una
   segunda vía de decisión — justo lo que INV-7 y ALERTA-005 prohíben.
5. **Andamiaje otra vez.** Construir la frontera antes de saber si el modelo puede decidir el patrón
   sería repetir el error diagnosticado: tubo sin consumidor.

### Experimento mínimo

**Parte A ya está hecha y refuta la suficiencia** (§10). La **Parte B** —¿puede el modelo producir sólo
el patrón nuevo?— es la única pregunta viva, y **necesita su propio DP** porque cambia el prompt.

### Criterio PASS / FAIL

Para la Parte B, si algún día se aprueba:
**PASS** = el modelo emite una cadena que aparece **exactamente una vez** en el fichero objetivo.
**FAIL** = no la emite, la fabrica, o no termina dentro del timeout.
Ambos son resultados válidos; el FAIL cerraría la vía del razonador local para este dominio.

### Impacto esperado sobre la métrica de gobierno

**Ninguno por sí solo.** `[INFER]` Con la frontera bien situada y sin capacidad de decidir el patrón,
la métrica **sigue en 0/7**. Sólo cambiaría si la Parte B resultara PASS — y eso está sin medir.

**Formulación honesta:** esta hipótesis no promete autonomía. Promete **convertir un fallo difuso en
uno localizado y medible**. Es un paso de diagnóstico, no de capacidad, y no debe aprobarse como si
fuera lo segundo.
