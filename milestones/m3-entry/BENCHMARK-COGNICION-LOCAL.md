---
documento: "Benchmark reproducible de la cognición local en HC-1"
tipo: "Protocolo de medición + resultados"
fecha: 2026-09-10
estado: "Medido. Ningún parámetro aplicado al producto: todos los experimentos viven en la instrumentación."
mantenido-por: "APUS-5 (CTO)"
---

# Dónde se va el tiempo de un turno cognitivo

**Clasificación de evidencia** (D47): `[EJEC]` medido · `[INFER]` deducido · `[HIPO]` no verificado.

## 1 · Protocolo

**Arnés:** `$CLAUDE_JOB_DIR/tmp/bench/bench_cognicion.py` — instrumentación, **fuera del repositorio**.
No modifica `aura_skeleton`: envuelve `urllib.request.urlopen`, registra el cuerpo enviado y la
respuesta completa de Ollama, y devuelve al código medido el mismo cuerpo que leyó. De ahí salen, sin
estimar nada:

`prompt_eval_count` (tokens de entrada) · `prompt_eval_duration` (**prefill**) · `eval_count` (tokens
generados) · `eval_duration` (**generación**) · `load_duration` (carga del modelo) ·
`total_duration` · `done_reason` · **número de llamadas al modelo por turno**.

**Se mide a través del producto completo** —`handle_utterance` → orquestador → router → proveedor—,
porque es el único sitio donde el reparto del coste es el real.

**Dos neutralizaciones, ambas declaradas:** la **voz** se sustituye por un doble inerte (sin ella el
turno se cae: `DECISION-REQUERIDA-VOZ-NO-DISPONIBLE.md`), y `AURA_DATOS` apunta a un temporal, así que
**la memoria real del usuario no se toca**.

**Conjunto fijo de consultas:**

| # | Caso | Consulta |
|---|---|---|
| 1 | conocimiento general | «¿Cuál es la capital de Francia?» |
| 2 | matemática | «¿Cuánto es 17 por 23?» |
| 3 | razonamiento | «¿Por qué crees que dormir poco afecta al ánimo?» |
| 4 | conversación | «¿Qué me recomiendas para dormir mejor?» |
| 5 | memoria personal **existente** | «¿Cuál es mi color favorito?» (hecho sembrado en laboratorio) |
| 6 | memoria personal **inexistente** | «¿Cuál es el nombre de mi abuela?» |

**Entorno:** HC-1 · Celeron N4020 · **2 núcleos** · 3,6 GiB RAM · Ollama 0.32.1 · `qwen2.5:0.5b`
(`Q4_K_M`, 494 M parámetros, 484 MB residentes, **contexto residente 4096**) · `PARADA` ARMADA.

## 2 · Línea base `[EJEC]`

| Caso | Turno | tok entrada | tok salida | Prefill | Generación | Carga | tok/s ingesta | tok/s generación | Llamadas |
|---|---|---|---|---|---|---|---|---|---|
| conocimiento | **42,1 s** | 161 | 32 | 20,0 s | 21,2 s | 0,72 s | 8,07 | 1,51 | 1 |
| matemática | **0,0 s** | — | — | — | — | — | — | — | **0** |
| razonamiento | **154,2 s** | 214 | 84 | 36,7 s | 116,8 s | 0,67 s | 5,83 | 0,72 | 1 |
| conversación | **126,9 s** | 281 | 30 | 61,3 s | 64,1 s | 1,47 s | 4,58 | 0,47 | 1 |
| memoria existente | 126,4 s | — | — | — | — | — | — | — | **1** |
| memoria inexistente | **0,0 s** | — | — | — | — | — | — | — | **0** |

`done_reason = stop` en los tres casos cognitivos: **el modelo termina por sí mismo**, nunca por límite
de tokens.

## 3 · Cuatro hallazgos

**H-1 · No hay un único cuello: el coste por token se degrada con el tamaño del prompt.** Ingesta
**8,07 → 5,83 → 4,58** tok/s y generación **1,51 → 0,72 → 0,47** tok/s a medida que el prompt crece de
161 a 281 tokens. El caso «conversación» genera **30** tokens en **64 s**; «conocimiento» genera **32**
en **21 s**. Mismo trabajo nominal, **tres veces el tiempo**. Con 3,6 GiB y ~190 MB libres, la firma es
de presión de memoria y de atención que crece con el contexto, no de un parámetro mal puesto `[INFER]`.

**H-2 · La carga del equipo domina sobre cualquier otra variable.** Las mismas consultas, el mismo
código y el mismo modelo dieron **287,1 s de media ayer** (equipo ocupado) y **107,7 s hoy** (equipo
libre). **Esto invalida cualquier comparación que no lleve su propio control tomado en la misma
sesión** — y confirma que no había base para atribuir el aumento de ayer al esquema de salida.

**H-3 · Una llamada por turno. Ninguna duplicada.** La degradación a `format:"json"` solo dispara una
segunda llamada si el runtime rechaza el esquema; no ocurrió ni una vez.

**H-4 · La palanca más barata ya existe, y no se está usando en un caso.** La aritmética se resuelve en
el Core con **cero llamadas** (`matemática`: 0,0 s). Pero **una consulta de memoria con recuerdo sí
llama al modelo**: «¿Cuál es mi color favorito?» costó **126,4 s** para devolver un dato que el Core ya
tenía en la mano — el LLM solo lo redactó. La autoridad es correcta (el hecho viene del store, ADR-0014
intacto); el coste no.

## 4 · Experimentos de parámetros

**Regla aplicada:** cada parámetro se inyecta **en la instrumentación**, nunca en el producto; queda
identificado por etiqueta; y la serie termina con un **control base** para medir la deriva del equipo,
sin el cual H-2 haría ilegible cualquier resultado.

Resultados en §5.

## 5 · Resultados de los experimentos `[EJEC]`

Serie ejecutada **en este orden**, en serie, sin nada más corriendo, y terminada con un control:

| Caso | `base` | `num_ctx=512` | `num_ctx=512`+`num_thread=2` | **`base-control`** |
|---|---|---|---|---|
| conocimiento | 42,1 s | 124,4 s | 135,7 s | **120,7 s** |
| razonamiento | 154,2 s | 109,7 s | 89,2 s | **105,0 s** |
| conversación | 126,9 s | 77,6 s | 95,3 s | **80,6 s** |
| **media** | **107,7 s** | **103,9 s** | **106,7 s** | **102,1 s** |

### Veredicto: ningún parámetro muestra efecto distinguible del ruido

Las cuatro medias caben en una banda de **±6 %** (102,1–107,7 s), mientras el rango **dentro** de una
sola configuración va de **42,1 a 154,2 s**. El control, que no cambia nada, es el más rápido de los
cuatro. Leer «`num_ctx=512` mejoró la conversación de 126,9 a 77,6 s» sería exactamente el error que el
control existe para impedir: el mismo caso sin tocar nada dio 80,6 s.

Lo mismo en la métrica normalizada, que es la que de verdad compara:

| | ingesta (tok/s) | generación (tok/s) |
|---|---|---|
| `base` | 8,07 · 5,83 · 4,58 | 1,51 · 0,72 · 0,47 |
| `num_ctx=512` | 2,12 · 4,66 · 6,39 | 0,85 · 0,80 · 0,95 |
| `base-control` | 1,87 · 5,46 · 9,34 | 1,17 · 0,96 · 1,55 |

Las bandas se solapan por completo. **Con una repetición por celda y esta varianza, no hay señal.**

### Dos cosas que la serie sí estableció

**El modelo no es determinista, y eso mueve el reloj.** El mismo caso generó 32, 31, 27 y 26 tokens en
las cuatro pasadas (y 84, 50, 37, 62 en razonamiento). A ~1 tok/s, esa diferencia **es** decenas de
segundos. Comparar segundos por turno sin mirar los tokens generados es comparar dos cosas distintas.

**Recargar el modelo cuesta 10–12 s `[EJEC]`.** `load_duration` fue de 0,59–1,47 s cuando el modelo
estaba residente, y de **10,75 a 12,27 s** cuando había caído de `keep_alive` — y cambiar `num_ctx`
**fuerza esa recarga**. Es la única magnitud concreta que la serie aisló, y es un 10 % del turno.

### Lo que esto significa para la palanca

El cuello no está en un parámetro mal puesto: está en que el equipo entrega entre **0,47 y 1,55 tok/s**
de generación según su estado, y en que **todo turno cognitivo cuesta una inferencia completa**. La
palanca con efecto medido de primer orden no es de Ollama, es arquitectónica: **la llamada que no se
hace** (§3, H-4). La aritmética ya la aprovecha —0 llamadas—; una consulta de memoria **con** recuerdo
no: 126,4 s para redactar un dato que el Core ya tenía.

## 6 · Lo que NO se tocó

Ni el modelo, ni el hardware, ni la arquitectura, ni `Configuracion.modelo`, ni la política de voz, ni
el `24/24`, ni la autoridad del Core. Ningún parámetro quedó aplicado al producto: al terminar el
proceso del arnés no queda nada.
