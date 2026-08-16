# DP · Recurso mínimo para un razonador capaz de producir una acción válida del catálogo

**Estado:** PROPUESTO — evaluación arquitectónica. **No es un DP de implementación.**
**Fecha:** 2026-08-15 · **Base:** `d933a08` (`main`) · rama `worktree-m3-entry` en `6db8302`
**Evidencia:** exclusivamente la medición del razonador local ejecutada hoy
([`DP-MEDICION-RAZONADOR-LOCAL.md`](DP-MEDICION-RAZONADOR-LOCAL.md) y los artefactos de
`medicion-razonador/`). **No se cita ningún benchmark externo**, y todo dato no medido va marcado.

Clasificación de evidencia (D47): `[EJEC]` medido ejecutando · `[INFER]` derivado de lo medido ·
`[HIPO]` no verificado.

---

## 0 · La pregunta

> **¿Qué recurso mínimo necesita AURORA para disponer de un razonador capaz de producir una acción
> válida del catálogo?**

Este DP **no** propone comprar hardware ni cambiar de modelo. Separa las restricciones, dice cuáles
están medidas y cuáles no, y deja la decisión al CEO.

**Advertencia sobre el alcance de la evidencia.** Todo lo que sigue proviene de **un caso**, **una
repetición por configuración** y **dos modelos**. Es suficiente para acotar restricciones físicas; no
lo es para caracterizar capacidad de razonamiento.

---

## 1 · Lo que está medido

### Hardware `[EJEC]`

| Recurso | Valor |
|---|---|
| Núcleos | 2 |
| RAM total | 3.719 MB |
| Swap total | 4.103 MB (habitualmente 60–90 % en uso) |
| Disco raíz | 57 GB al 96 %, 2,3 GB libres |
| Almacén de modelos | **USB externo** `/dev/sdb1`, 7,3 GB al **97 %**, 250 MB libres |

### `qwen2.5:0.5b` — turno completo, máquina en reposo `[EJEC]`

| Métrica | Valor |
|---|---|
| Tokens de prompt | 727 |
| Ingesta | 189,74 s → **3,83 tok/s** |
| Generación | 47 tokens en 21,04 s → **2,23 tok/s** |
| Turno completo | 232,97 s · HTTP 200 |
| RAM disponible antes / después | 962 → 615 MB |

Respuesta: `{"intent":"consulta","action":"corregir","args":{"patron":"","ruta":"mutaciones/laboratorio-humo.toml"}}`
**Acción inexistente en el catálogo; sin los tres campos; `patron` vacío.** El núcleo la rechazó.
**No fabricó datos falsos** — dejó el patrón vacío en vez de inventarlo.

### `qwen2.5:0.5b` — sensibilidad a la carga `[EJEC]`

Con la máquina más cargada (load 1,59–2,60) el rendimiento cayó a **≈1,9 tok/s** y el turno no cupo en
300 s. **El mismo modelo rinde el doble o la mitad según la carga residual de la máquina.** Cualquier
umbral de latencia fijado sin margen mide la carga de la máquina, no el modelo.

### `qwen2.5:3b` — aislado, sin AURORA en memoria `[EJEC]`

| Métrica | Valor |
|---|---|
| Carga del modelo | **151–153 s** (desde USB externo) |
| Ingesta | 32 tokens en 38,9 s → **0,82 tok/s** |
| Generación | 5 tokens en 16,4 s → **0,31 tok/s** |
| Residente | 2,2 GB · 100 % CPU · contexto 4096 |
| RAM disponible tras cargar | **183–234 MB** · swap libre **275 MB** |

### `qwen2.5:3b` — dentro del producto: **tres fallos, ninguna inferencia** `[EJEC]`

| Intento | Condición | Resultado |
|---|---|---|
| 1 | frío | `HTTP 499` a 77 s, durante `load_tensors` |
| 2 | frío | `HTTP 499` a 50 s, durante `load_tensors` |
| 3 | **residente** | `HTTP 500` a **9,68 s** |

El tercero es el informativo: con el modelo ya cargado, la petición llegó al servidor y **falló en el
servidor** en menos de 10 s. Compatible con no poder reservar el contexto de 727 tokens teniendo
además el producto compuesto en memoria.

### Composición del prompt — medido contando caracteres, sin inferencia `[EJEC]`

| Parte | Caracteres | Proporción |
|---|---|---|
| `_SYSTEM` (instrucciones + catálogo) | 1.748 | 73,3 % |
| — de los cuales, **el catálogo** | 995 | 41,7 % |
| Prompt de usuario (cabeceras + texto) | 638 | 26,7 % |
| **Contexto real del fallo** | **185** | **7,8 %** |
| **Total enviado** | **2.386** → 727 tokens | 100 % |

**El 92,2 % de lo que el razonador ingiere no tiene nada que ver con el fallo que debe corregir.** El
catálogo por sí solo pesa 5,4 veces más que el contexto útil.

### Gobierno `[EJEC]`

Denegación sin aprobación: **PASA**, con la previsualización entregada al confirmador. Aprobación
diferida ligada a la huella exacta: **PASA**. 54 pruebas en verde. Una acción fuera del catálogo fue
**rechazada por el núcleo** sin llegar a permisos. **Ninguna garantía se relaja.**

---

## 2 · A · Restricciones de memoria

**Es la restricción que hoy bloquea la evaluación, y está medida.**

Aritmética, con su derivación explícita:

| Concepto | Valor | Clase |
|---|---|---|
| RAM disponible con la máquina en reposo | 1.629 MB | `[EJEC]` |
| Consumido al cargar `qwen2.5:3b` | ≈1.395 MB | `[EJEC]` |
| RAM disponible con el modelo residente | **234 MB** | `[EJEC]` |
| Consumido por AURORA durante un turno | **≈350 MB** | `[INFER]` — diferencia 962→615 MB en el turno con 0.5b |
| **Déficit para que coexistan** | **≈120 MB, más el contexto KV** | `[INFER]` |

**El déficit no es un abismo: son unos cientos de megabytes.** Con `qwen2.5:0.5b` (398 MB) la
coexistencia funciona y el turno se completa. Con `qwen2.5:3b` (2,2 GB residentes) no.

**Lo que esto significa para la pregunta del DP:** el recurso mínimo **no es «una máquina grande»**;
es *el margen suficiente para que el modelo y el producto estén vivos a la vez*. Hoy falta poco, y
hay más de una forma de conseguirlo —no todas son comprar hardware—.

**No medido `[HIPO]`:** cuánta RAM necesita exactamente el contexto KV de 727 tokens en 3b; si un
`num_ctx` menor que 4096 bastaría; cuánto del baseline del sistema es recuperable.

## 3 · B · Capacidad de razonamiento

**Es la incógnita central, y sigue abierta.**

- `0.5b`: **una** ejecución, **un** caso → acción fuera de catálogo, sin los tres campos `[EJEC]`. Una
  muestra no caracteriza un modelo, pero es lo que hay.
- `3b`: **sin medir**. No llegó a recibir el prompt en ninguno de los tres intentos `[EJEC]`. **No se
  concluye nada sobre su capacidad.**

**Ninguna decisión de recurso mínimo puede tomarse con rigor mientras B esté sin medir**, porque el
recurso mínimo depende de qué modelo basta, y eso no se sabe. Ésta es la brecha principal.

## 4 · C · Latencia

| Configuración | Ingesta de 727 tokens | Clase |
|---|---|---|
| `0.5b`, reposo | **189,7 s** | `[EJEC]` |
| `0.5b`, con carga | ≈380 s | `[INFER]` a 1,9 tok/s |
| `3b`, extrapolado | **≈887 s** | `[INFER]` — extrapola 0,82 tok/s medidos sobre **32 tokens**; una muestra pequeña, tómese con reserva |
| `3b`, más carga en frío | +151 s | `[EJEC]` |

Un turno completo con 3b rondaría los **15–20 minutos** `[HIPO]`. Para un ciclo desatendido que debe
encadenar tareas, eso condiciona el diseño tanto como la memoria.

**Matiz importante:** la latencia está dominada por la **ingesta**, no por la generación. Con 0.5b la
ingesta fue el 90 % del tiempo de inferencia (189,7 s de 210,8 s) `[EJEC]`.

## 5 · D · Tamaño y forma del contexto

**Aquí está el hallazgo con mayor relación entre efecto y coste.**

El contexto útil son **185 caracteres de 2.386 (7,8 %)** `[EJEC]`. El resto es prefijo fijo: catálogo
e instrucciones, idénticos en todos los turnos. Como la latencia la domina la ingesta, **AURORA está
pagando la mayor parte de su tiempo de razonamiento por texto que no cambia nunca.**

Consecuencias, marcadas honestamente:

- El log del servidor muestra que Ollama mantiene una **caché de prompt** (`prompt cache`, `cached
  n_tokens`) `[EJEC]`. Un prefijo fijo es exactamente lo que ese mecanismo puede reutilizar `[HIPO]`:
  **no se ha medido** si aquí se activaría ni cuánto ahorraría.
- **No medido `[HIPO]`:** cuánto bajarían latencia y memoria con un prefijo más corto, o con un
  catálogo filtrado a las capacidades pertinentes.

**Advertencia de gobierno.** Recortar el catálogo del prompt **no es una optimización inocua**:
`_catalogo_para_prompt()` se deriva del catálogo real precisamente para que no puedan divergir —el
propio módulo lo justifica citando ALERTA-005—. Cualquier cambio ahí toca una garantía y exige su
propio Decision Package. **Se señala como palanca, no se propone.**

## 6 · E · Capacidad del modelo para seguir el catálogo

Único dato duro `[EJEC]`: `0.5b` emitió `action: "corregir"`, que **no existe**, e inventó los nombres
de argumentos `patron` y `ruta` en lugar de `fichero`/`buscar`/`sustituir`.

Dos lecturas que conviene no mezclar:

1. **El fallo fue de adherencia al catálogo, no de comprensión.** Identificó correctamente el
   artefacto a corregir —`mutaciones/laboratorio-humo.toml`, que venía en el contexto— y nombró la
   intención en términos razonables. Lo que no hizo fue ceñirse a la superficie declarada.
2. **El núcleo aguantó.** La acción inexistente se rechazó sin llegar a permisos. La arquitectura hace
   su trabajo aunque el razonador no lo haga `[EJEC]`.

**No medido `[HIPO]`:** si un modelo mayor se adhiere mejor; si el catálogo, tal como se presenta hoy
—una lista sin esquema de argumentos para `proponer_cambio`, que no está en `ESPECIFICACIONES`—
contribuye al fallo. Esto último es una **observación relevante ya registrada** como deuda I-1 en el
checkpoint: el modelo ve `proponer_cambio (roja)` **sin lista de argumentos**, porque sólo se muestran
los de las acciones presentes en `ESPECIFICACIONES` `[LECT]`.

## 7 · F · Requisitos mínimos de hardware

**No se propone ninguna compra.** Lo que se puede afirmar con lo medido:

- **Medido `[EJEC]`:** 3,7 GB de RAM **no bastan** para `qwen2.5:3b` + AURORA simultáneamente.
- **Medido `[EJEC]`:** 3,7 GB **sí bastan** para `qwen2.5:0.5b` + AURORA, con turno completo en 233 s.
- **Derivado `[INFER]`:** el déficit para 3b es de unos cientos de MB, no de gigabytes.
- **No medido `[HIPO]`:** el mínimo real, porque depende de qué modelo sea suficiente — y eso es B,
  que sigue sin medir.

**El disco también es una restricción activa, y suele olvidarse:** raíz al 96 % (2,3 GB libres) y el
almacén de modelos en un **USB externo al 97 % con 250 MB libres** `[EJEC]`. Cualquier modelo
adicional **no cabe hoy**. Y los 151 s de carga se pagan contra ese USB.

## 8 · G · Alternativas de modelo y cuantización

**Sin benchmarks externos, y no los voy a inventar.** Lo único sustentado:

- Los dos modelos presentes son `qwen2.5:0.5b` (Q4_K_M) y `qwen2.5:3b` `[EJEC]`.
- Entre ellos hay un salto de ~6× en parámetros y de ~5,5× en memoria residente `[EJEC]`.
- **No hay medición de ningún punto intermedio**, ni de otras cuantizaciones. Cualquier afirmación
  sobre un modelo de 1B, o sobre una cuantización más agresiva de 3b, sería `[HIPO]` pura.
- Descargar otro modelo **no es posible hoy** sin liberar disco `[EJEC]`.

Lo que sí puede decirse: **el espacio entre 0.5b y 3b no se ha explorado**, y es donde podrían
coincidir «cabe en memoria» y «se adhiere al catálogo». Es una observación, no una propuesta.

## 9 · H · Impacto sobre local-first

**Nada de lo medido cuestiona el principio local-first (D24 / ADR-0001).** Todo se ejecutó en la
máquina, sin claves de terceros y sin red. El razonador local **funciona**: carga, ingiere y genera.

Lo que la medición cuestiona no es el principio, sino **el margen** de este equipo concreto. Distinguir
las dos cosas importa: un resultado de 0/7 en esta máquina no es un argumento contra local-first, del
mismo modo que no es un argumento contra la arquitectura de AURORA.

**Riesgo declarado `[HIPO]`:** si en algún momento se considerara un razonador remoto, chocaría de
frente con D24 y exigiría acta del CEO. **No se propone.**

## 10 · I · Impacto sobre la métrica de gobierno

> **«¿Qué trabajo nuevo puede completar AURORA por sí misma?»** → **Ninguno. 0/7.**

Con la formulación exacta que fijó el CEO:

> *Con el hardware y el razonador local actualmente disponibles, **no se ha demostrado** ninguna de las
> 7 capacidades autónomas.*

Y con la precisión que la medición añade: **el 0/7 ya no es un dato opaco.** Ahora se sabe que

- no es por pérdida de contexto —el contexto llega íntegro y correcto `[EJEC]`—;
- no es por incapacidad de ingestión —el turno se completa con 0.5b `[EJEC]`—;
- no es por gobierno —las garantías pasan y de hecho **protegieron** ante una acción inventada `[EJEC]`—;
- es por **adherencia al catálogo** en el único modelo que cabe, y por **memoria** en el que no cabe.

Eso convierte 0/7 de veredicto en diagnóstico.

---

## 11 · Qué falta medir para responder la pregunta del DP

Ordenado por lo que más reduce incertidumbre y menos cuesta. **No se ejecuta nada sin aprobación.**

| # | Incógnita | Por qué importa | Coste |
|---|---|---|---|
| 1 | **¿Se adhiere `3b` al catálogo?** (B) | Sin esto no hay «recurso mínimo»: no se sabe qué modelo basta | Requiere resolver A primero, o medirlo fuera del producto |
| 2 | **¿Cuánta memoria falta exactamente?** (A) | El déficit parece de cientos de MB; saberlo convierte una intuición en un número | Bajo |
| 3 | **¿Cuánto ahorra la caché de prompt?** (D) | El 92,2 % del prompt es prefijo fijo; es la palanca de mayor efecto sobre la latencia | Bajo |
| 4 | **¿Cambia la adherencia si el catálogo declara los argumentos de `proponer_cambio`?** (E) | Hoy el modelo ve la acción **sin esquema**; toca la deuda I-1 | Medio — **toca una garantía, exige DP propio** |

**La incógnita 1 es la que decide, y no puede medirse dentro del producto en esta máquina.** Ése es el
nudo: A bloquea la medición de B, y B es lo que determina el recurso mínimo.

## 12 · Retorno sobre Tokens

Este DP **no construye nada**, y ése es su retorno. La medición previa evitó el error de conectar un
razonador que hoy no puede consumir el contexto, y este documento evita el siguiente: dimensionar
recursos sin saber qué modelo basta.

Deja además tres cosas reutilizables: el arnés de medición con aislamiento probado y evidencia por
identificador único; la comprobación de gobierno sin modelo; y el desglose del prompt, que se obtuvo
**contando caracteres, sin gastar una sola inferencia**.

## 13 · Lo que este DP NO hace

- **No** propone comprar hardware.
- **No** propone cambiar de modelo ni de cuantización.
- **No** propone tocar el catálogo, el gobierno, los permisos ni `aura_skeleton/`.
- **No** abre ningún incremento.
- **No** cita benchmarks que no hayamos medido.
- **No** concluye que `qwen2.5:3b` sea incapaz de razonar: concluye que **este entorno no permite
  evaluarlo dentro de AURORA**.
