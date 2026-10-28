# DP · Comparación de razonadores: `qwen2.5:0.5b` vs `qwen2.5:3b`

**Estado:** PROPUESTO — pendiente de aprobación. **No se ejecuta ninguna inferencia hasta que el CEO
lo apruebe.** No modifica producto, no abre incremento de arquitectura.
**Fecha:** 2026-08-15 · **Producto:** `main` = `origin/main` = `d933a08`, `aura_skeleton/` intacto.
El arnés permanece **fuera** del producto.

Clasificación (D47): `[EJEC]` medido · `[INFER]` derivado · `[HIPO]` no verificado.

---

## 0 · La pregunta

> **¿El `0.5b` está limitado principalmente por capacidad de razonamiento, y un modelo mayor cambia
> materialmente la capacidad de AURORA para formular trabajo válido?**

No se busca un número favorable. **Que el `3b` también falle es un resultado igual de valioso**, porque
cerraría la hipótesis «basta con un modelo mayor» y desplazaría el cuello a otra parte.

---

## 1 · Evidencia disponible, y su localización

Conservada en `milestones/m3-entry/medicion-razonador/`, sin sobrescribir:

| Artefacto | Contiene |
|---|---|
| `evidencia-humo-qwen2.5-0.5b.json` | **Humo 2** (el Humo 1 fue sobrescrito por el defecto del arnés, ya corregido) |
| `evidencia-humo-20260815-135951-0.json` | Humo 3 · `0.5b` · timeout 1800 s · turno completo |
| `evidencia-humo-20260815-151435-0.json` | Repetición del Humo 2 · timeout 300 s · turno completo |
| `evidencia-denegacion-20260815-135724-0.json` | Comprobación de gobierno, sin modelo |
| `registro-ollama-humos.log` | Tiempos y tokens del servidor, extraídos del log volátil |

**Los datos del Humo 1 sobreviven sólo en la conversación y en ese registro.** Es consecuencia del
defecto de instrumento ya declarado y corregido.

---

## 2 · Memoria requerida y residente

| | `qwen2.5:0.5b` | `qwen2.5:3b` |
|---|---|---|
| Blob en disco | **398 MB** `[EJEC]` | **1,93 GB** `[EJEC]` |
| Búfer de modelo al cargar | no capturado | **1.834,82 MiB** `[EJEC]` |
| Residente según `ollama ps` | **no medido** `[HIPO]` | **2,2 GB** `[EJEC]` |
| Residente estimado | ≈450 MB `[INFER]`, aplicando el factor 1,14× observado en 3b | — |
| Contexto configurado | 32.768 `[EJEC]` | 4.096 `[EJEC]` |

## 3 · Memoria disponible real

| Momento | Valor | Clase |
|---|---|---|
| RAM total | 3.719 MB | `[EJEC]` |
| Disponible en reposo | **1.109 – 1.629 MB** (varía con la caché) | `[EJEC]` |
| Disponible con `3b` residente | **183 – 234 MB** | `[EJEC]` |
| Consumo de AURORA durante un turno | **≈350 MB** | `[INFER]` — caída 962→615 MB en el Humo 3 |

**El déficit medido para que `3b` y AURORA coexistan es de unos cientos de MB**, no de gigabytes
`[INFER]`. Con `0.5b` la coexistencia funciona: turno completo en 253–233 s `[EJEC]`.

## 4 · Riesgo de swap

| Observación | Valor | Clase |
|---|---|---|
| Swap total | 4.103 MB | `[EJEC]` |
| Swap ya en uso al empezar la jornada | 2.600 – 3.200 MB | `[EJEC]` |
| Swap libre tras cargar `3b` | **275 MB** | `[EJEC]` |
| Swap consumido por un turno de `0.5b` | 72 – 431 MB | `[EJEC]` |

**El riesgo no es teórico: se materializó tres veces.** Los tres intentos de `3b` dentro del producto
fallaron —`499` a 77 s, `499` a 50 s, `500` a 9,7 s— y los dos primeros coinciden **al segundo** con
mensajes del kernel «Under memory pressure» `[EJEC]`. No hay línea de OOM del kernel y `systemd-oomd`
está inactivo: **el mecanismo exacto que mató el proceso no está identificado** `[EJEC]`.

## 5 · Protocolo de carga

| | `0.5b` | `3b` |
|---|---|---|
| Carga en frío | **19,67 – 24,13 s** `[EJEC]` | **151,0 – 153,4 s** `[EJEC]` |
| Origen | USB externo al 97 %, 250 MB libres `[EJEC]` | ídem |

La carga de `3b` cuesta **6–8 veces más** y se paga contra medios extraíbles. Con residencia previa
(`keep_alive`) se elimina ese coste, pero **cambia la condición del experimento y debe declararse**.

## 6 · Caso mínimo de comparación

**El caso ya existe y no se toca:** garantía sembrada `laboratorio-humo.toml:H1` en estado AUSENTE,
con verdad de referencia conocida por construcción. El contexto que produce el ciclo real es:

```
motivo            : veredicto negativo: 1 garantia(s) ... laboratorio-humo.toml:H1 (AUSENTE)
fichero_declarado : mutaciones/laboratorio-humo.toml
buscar_declarado  :     if not tiene_permiso(x):
referencia        : laboratorio-humo.toml:H1
```

### El problema de diseño, y cómo se resuelve

`3b` **no puede ejecutarse dentro del producto en esta máquina** `[EJEC]`. Comparar el resultado
in-producto de `0.5b` contra un resultado obtenido de otra forma para `3b` **no sería una comparación**:
diferirían en dos variables a la vez.

**Propuesta: RÉPLICA DEL PROMPT EXACTO, para AMBOS modelos.**

El prompt completo que el producto envió está **capturado literalmente** en la evidencia (727 tokens,
2.386 caracteres, prompt de sistema incluido) `[EJEC]`. Se reenvía **byte a byte** al mismo endpoint
local, sin componer AURORA en memoria, **para los dos modelos**. Difieren en el modelo y en nada más.

Lo que esto **sí** mide: adherencia al catálogo y completitud de argumentos ante una entrada idéntica.
Lo que **no** mide, y hay que decirlo: la ruta del producto —motor, permisos, confirmador—. **No hace
falta que la mida:** el gobierno ya está verificado por separado y ha rechazado correctamente las dos
acciones inventadas `[EJEC]`. La validación de la respuesta contra el catálogo se hace **leyendo**
`permissions.CATALOGO` y `ESPECIFICACIONES`, sin ejecutar nada.

**Ganancia de memoria:** elimina los ≈350 MB de AURORA, que es justo el orden del déficit medido. Es
la única vía identificada para preguntarle a `3b` en esta máquina `[INFER]`.

**Se replica también `0.5b`** aunque ya tengamos sus resultados in-producto: sin eso, la comparación
no sería limpia.

## 7 · Métricas de latencia — lo ya medido

| | `0.5b` | `3b` |
|---|---|---|
| Ingesta | **3,52 – 3,83 tok/s** en reposo · ≈1,9 con carga `[EJEC]` | **0,82 tok/s** `[EJEC]`, sobre una muestra de **32 tokens** |
| Generación | **1,85 – 2,23 tok/s** `[EJEC]` | **0,31 tok/s** `[EJEC]`, sobre **5 tokens** |
| Turno de 727 tokens | **231 – 253 s** `[EJEC]` | **≈1.190 s** `[INFER]` — extrapolación de una muestra pequeña; tómese con reserva |

**El umbral de 300 s queda invalidado como métrica de capacidad** `[EJEC]`: los tres humos cayeron a
ambos lados de él según la carga residual. **El timeout de la comparación será 1800 s**, que cubre a
ambos modelos con margen y no decide el resultado.

**La latencia la domina la ingesta**, no la generación: 206,5 s de 231,4 s en la última medición `[EJEC]`.

## 8 · Adherencia al catálogo — lo ya medido

| Turno | `action` emitida | ¿En catálogo? | Argumentos |
|---|---|---|---|
| `0.5b` #1 | `corregir` | **NO** | `patron` (vacío), `ruta` |
| `0.5b` #2 | `revisar` | **NO** | `ruta` |
| `3b` | — | **no medido** | — |

**`0.5b`: 0 de 2.** Dos acciones distintas, ninguna existente, ninguna con los tres campos. En ambos
casos acertó el artefacto —venía en el contexto— y **no fabricó datos falsos**: dejó el patrón vacío u
omitido en vez de inventarlo. El núcleo rechazó las dos `[EJEC]`.

**Matiz que conviene no perder:** el fallo es de **adherencia**, no de comprensión. Nombró la intención
razonablemente (`corregir`, `revisar`, `corregir_fichero`); lo que no hizo fue ceñirse a la superficie
declarada.

## 9 · Completitud de los argumentos requeridos

El ejecutor exige tres: **`fichero`**, **`buscar`**, **`sustituir`**. `0.5b` no produjo ninguno de los
tres en dos turnos `[EJEC]`.

**Observación ya registrada (deuda I-1), pertinente aquí:** el catálogo que se muestra al modelo lista
`proponer_cambio (roja)` **sin esquema de argumentos**, porque sólo se anexan los de las acciones
presentes en `ESPECIFICACIONES`, y `proponer_cambio` no está `[LECT]`. **Es un factor de confusión que
afecta por igual a los dos modelos**, así que no invalida la comparación — pero sí impide atribuir el
fallo exclusivamente al modelo. **No se toca**, por orden del CEO y porque cambiarlo rompería la
comparabilidad con los humos ya ejecutados.

## 10 · Criterio de éxito

Por modelo, sobre la respuesta cruda, evaluado **leyendo**, sin ejecutar:

| Paso | Pregunta |
|---|---|
| 1 | ¿`action` pertenece a `permissions.CATALOGO`? |
| 2 | ¿Trae `fichero`, `buscar` y `sustituir`? |
| 3 | ¿Los valores corresponden al esquema real (`fichero` = el TOML declarado)? |
| 4 | ¿`sustituir` aparece **exactamente una vez** en el fichero objetivo? (criterio conductual del DP de medición) |
| 5 | ¿Se mantiene el gobierno? — ya verificado por separado; **no se ejecuta ninguna acción** |

**ÉXITO del modelo** = pasos 1–3. **ÉXITO ROTUNDO** = además el 4.
**ÉXITO DEL EXPERIMENTO** = obtener respuesta cruda de ambos modelos y clasificarla, **sea cual sea**.

## 11 · Criterio de abandono por presión de memoria

Declarado **antes** de ejecutar, para no improvisar bajo presión:

1. **Antes de cargar:** si la RAM disponible es **< 1.400 MB** o el swap libre **< 600 MB**, no se
   inicia. Se espera o se reporta como no ejecutable.
2. **Tras cargar `3b`:** se registra la memoria. Si la disponible es **< 150 MB**, se reporta y **no se
   envía el prompt**: sabemos ya que ahí falla.
3. **Un solo intento por modelo.** Si aparece `HTTP 500`, `499` o el proceso muere: **se detiene**, se
   reporta el modo de fallo y **no se reintenta**.
4. **Al terminar, se descarga el modelo** (`ollama stop`) para devolver la máquina a un estado usable.
5. **Nada en paralelo** mientras corre.

Un abandono por memoria **no es un fracaso del experimento**: es la respuesta de que este entorno no
permite evaluar `3b` ni siquiera por la vía más ligera identificada.

## 12 · Qué resultado justificaría una medición más amplia

| Resultado de `3b` | Lectura | ¿Tanda amplia? |
|---|---|---|
| Pasa 1–3 (acción válida y completa) | **El tamaño del modelo SÍ es la palanca.** El cuello pasa a ser la memoria, y el déficit medido es de cientos de MB | **SÍ** — y con ella, replantear A |
| Pasa 1 pero no 2–3 | Adherencia parcial: la superficie del catálogo influye. Reabre la deuda I-1 como candidata **con su propio DP** | Sólo si el CEO abre I-1 |
| Falla 1, como `0.5b` | **El tamaño no es la palanca.** Cierra la hipótesis y ahorra la tanda entera | **NO** |
| Abandono por memoria | El entorno no permite evaluarlo ni por la vía ligera | **NO** — la decisión pasa a ser de recurso |

**La tercera fila es la más valiosa en coste evitado:** dos respuestas crudas bastarían para descartar
una hipótesis que, de no comprobarse, arrastraría decisiones de hardware.

## 13 · Lo que este DP NO hace

- **No** modifica el prompt, el catálogo, `ESPECIFICACIONES`, `proponer_cambio` ni `aura_skeleton/`.
- **No** ejecuta ninguna acción propuesta por ningún modelo.
- **No** ejecuta la tanda de 30.
- **No** abre incremento de arquitectura ni decide recurso.
- **No** compensa al `0.5b` con ningún ajuste: los dos modelos reciben **los mismos bytes**.
- **No** cita benchmarks externos.

## 14 · Retorno sobre Tokens

Dos inferencias —una por modelo— para decidir si tiene sentido gastar una tanda de 30 y, detrás, una
conversación sobre recursos. Reutiliza el prompt ya capturado, el caso ya sembrado y el criterio de
corrección ya definido; **no construye nada nuevo**. Y el resultado más probable a priori —que `3b`
tampoco se adhiera— es el que más trabajo futuro ahorra.

## 15 · Método

```
Diagnóstico ✔ → criterio de gobierno ✔ → DP de medición ✔ → medición ✔
   → DP de recurso mínimo (propuesto) → DP de comparación ← ESTAMOS AQUÍ
   → aprobación del CEO → réplica del prompt en ambos modelos → informe → decisión
```

**No se ejecuta ninguna inferencia hasta la aprobación.**
