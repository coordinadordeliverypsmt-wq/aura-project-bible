# DP diagnóstico · ¿Es la forma de invocación una variable de confusión para cargar `qwen2.5:3b`?

**Estado:** PROPUESTO. **No se ha ejecutado ninguna inferencia nueva** para redactarlo.
**Ámbito:** instrumento de medición. **No** toca `aura_skeleton/`, prompt, catálogo ni protocolo.
**Fecha:** 2026-08-15 · Producto: `main` = `origin/main` = `d933a08`, intacto.

Clasificación (D47): `[EJEC]` medido · `[INFER]` derivado · `[HIPO]` no verificado.

---

## 1 · La pregunta

> **¿La forma de invocación —primer plano vs. segundo plano— es una variable de confusión real para
> la carga de `qwen2.5:3b`, o la correlación observada se explica por otra cosa?**

---

## 2 · Las seis observaciones, con su cronología real `[EJEC]`

| # | Hora | Forma | Duración | Resultado |
|---|---|---|---|---|
| 1 | 14:46:25 | segundo plano | 1m17s | `499` — cliente cerró durante `load_tensors` |
| 2 | 14:48:42 | segundo plano | 50s | `499` — ídem |
| 3 | **14:53:33** | **primer plano (`curl`)** | **3m28s** | **`200` — cargó y generó** |
| 4 | **15:02:23** | **primer plano (`curl`)** | **3m8s** | **`200` — cargó** (`llama-server started in 149,45 s`) |
| 5 | 15:03:48 | segundo plano, **modelo residente** | 9,68s | `500` — fallo del servidor |
| 6 | 18:00:11 | segundo plano | 59,56s | `499` — cliente cerró durante `load_tensors` |

Búfer del modelo en todos los casos: **1.834,82 MiB** `[EJEC]`.

---

## 3 · Qué diferencia exactamente hay entre ambas formas — **medido, y el resultado sorprende**

Sondeé los dos modos de ejecución **sin lanzar inferencia**, comparando propiedades del proceso:

| Propiedad | Primer plano | Segundo plano |
|---|---|---|
| `oom_score_adj` | **0** | **0** |
| cgroup | `…/app-code-1966.scope` | **el mismo** |
| pgid / sid propios | sí | sí |
| stdin / stdout es tty | no / no | no / no |
| Supervivencia ociosa 45 s | — | **sí** |

**No hay diferencia estructural.** Mismo cgroup, misma prioridad ante el OOM killer, ninguno tiene
terminal, ambos tienen su propio grupo de procesos. `[EJEC]`

Y la huella del cliente tampoco explica nada `[EJEC]`:

| Cliente | RSS |
|---|---|
| `curl` | **11 MB** |
| Python tras importar `permissions` y `providers_real` | **23 MB** |

**12 MB de diferencia.** Frente a un búfer de 1.834 MiB, es ruido. **La hipótesis «el cliente Python
pesa más» queda refutada.**

## 4 · ¿Hay timeout, cierre de descriptores o job control que explique el `499`?

- **Timeout del cliente: descartado** `[EJEC]`. `urllib.request.urlopen(..., timeout=1800)`; los
  cierres ocurrieron a 50–77 s. No fue el cliente rindiéndose.
- **Timeout por duración: descartado** `[EJEC]`, y esto es lo más contundente: los intentos que
  **sobrevivieron** duraron **188 y 208 s**, más que todos los que murieron (50, 59, 77 s). Si hubiera
  un límite temporal, habrían caído primero los largos.
- **Job control / señales del shell: sin evidencia.** El proceso de segundo plano no está en un grupo
  distinto ni tiene su terminal cerrada de forma diferente `[EJEC]`.
- **OOM del kernel: sin registro.** Ni línea `Killed process` en `dmesg`, ni `systemd-oomd` activo
  (inactivo) `[EJEC]`. **El mecanismo que mata el proceso sigue sin identificarse.**

## 5 · Por qué los dos `curl` sí llegaron a cargar — **la hipótesis alternativa, y es más fuerte**

Al ordenar las observaciones por hora aparece algo que la tabla «primer plano vs segundo plano» ocultaba:

**Los dos éxitos llegaron inmediatamente después de lecturas recientes del mismo fichero de modelo.**
El #3 (14:53) vino tras los intentos #1 y #2, que ya habían leído parte de los 1,93 GB desde el USB
hacia la caché de página. El #4 (15:02) vino nueve minutos después del #3. En cambio, #1 fue la
primera lectura del día y **#6 ocurrió tres horas más tarde**, con la caché ya desalojada.

**Hipótesis de confusión `[HIPO]`:** lo que separa éxito de fallo no sería el modo de invocación, sino
**cuánto tarda la carga**, que depende de si el modelo está caliente en caché de página. Una carga
larga desde un USB al 97 % mantiene al sistema más tiempo bajo presión de memoria, y esa ventana es la
que mata al cliente.

**Esta hipótesis explica las seis observaciones; la de primer/segundo plano no explica que no haya
ninguna diferencia estructural entre ambos modos.** Por eso el DP no da la correlación por causal.

## 6 · Una restricción del instrumento que hay que declarar `[EJEC]`

**El modo de ejecución en primer plano de mi arnés tiene un tope de 10 minutos.** Un turno de `3b`
con 727 tokens necesita, por lo medido, del orden de **20 minutos**. Es decir: **el único modo que ha
logrado cargar `3b` no puede albergar un turno completo de `3b`.**

Esto no es un detalle menor: condiciona el diseño de cualquier experimento posterior y es, por sí
mismo, una limitación del entorno de medición que debe constar en la decisión de capacidad.

## 7 · Experimento mínimo que separa «problema de invocación» de «problema físico»

**Idea: desacoplar la carga de la medición.** Si la ventana de carga es lo que mata al cliente,
eliminarla debería bastar — sin cambiar nada más.

| Paso | Acción | Modo |
|---|---|---|
| 1 | Esperar umbrales aprobados (≥1.400 MB / ≥600 MB) | — |
| 2 | Cargar `3b` con `keep_alive`, prompt trivial **sin `system`** | **primer plano** (151 s, cabe en el tope de 10 min) |
| 3 | Confirmar residencia con `ollama ps` y registrar memoria | — |
| 4 | Enviar el **prompt congelado** con el modelo ya residente | **segundo plano** |
| 5 | Validar por lectura, descargar el modelo | — |

**Lo que discrimina:**

- Si el paso 4 **completa** → la ventana de carga era el obstáculo. El modo de invocación **no** era la
  variable; era la duración de la carga. Y tendríamos por fin la medición del `3b`.
- Si el paso 4 falla con **`500`** → el muro es la memoria para el contexto KV de 727 tokens, no la
  carga. Es **físico** y no se resuelve con invocación.
- Si el paso 4 falla con **`499`** → el cliente muere aun sin ventana de carga: entonces sí apunta al
  modo de invocación, y el diagnóstico continuaría por ahí.

Los tres desenlaces son informativos. **Una sola inferencia**, la misma que ya estaba autorizada y
nunca llegó a ejecutarse.

**Diferencia con el intento #5 (que dio `500`):** aquél tenía AURORA compuesta en memoria y sólo
234 MB disponibles. Aquí el cliente son 23 MB y se parte de ≥1.400 MB. No es una repetición.

## 8 · Qué debe permanecer congelado para que siga siendo comparable

| Variable | Valor |
|---|---|
| Prompt de usuario | SHA `b9a01206…`, byte a byte |
| Prompt completo (`_SYSTEM` + usuario) | SHA `58159836…` |
| Contexto | SHA `0a5800b2…` |
| Caso | `laboratorio-humo.toml:H1`, AUSENTE |
| Catálogo y `ESPECIFICACIONES` | sin tocar |
| Umbrales | 1.400 / 600 / 150 MB |
| Timeout | 1800 s |
| Modelo | `qwen2.5:3b` |
| Validación | por lectura, **sin ejecutar ninguna acción** |
| Intentos | **uno**, sin reintentos |

**El calentamiento va sin `system` a propósito:** compartir el prefijo cachearía el prompt real y
rompería la comparabilidad con el `0.5b` y con los humos.

## 9 · Criterio de PASS / FAIL

**PASS del diagnóstico** = el paso 4 produce un desenlace clasificable —completa, `500` o `499`—, con
sus métricas y la respuesta cruda si la hay. **Los tres son PASS**: el objetivo es discriminar, no que
el modelo responda.

**FAIL del diagnóstico** = no se puede clasificar: el proceso muere sin código de estado, o el modelo
no llega a residir en el paso 2, o hay que modificar alguna variable congelada para que avance.

## 10 · Criterio de abandono

1. Umbrales incumplidos → no se inicia.
2. Tras el paso 2, si `ollama ps` no muestra el modelo residente → se detiene y se reporta.
3. **Un solo intento.** Cualquier fallo → se detiene, se reporta el modo, **no se reintenta**.
4. Se descarga el modelo al terminar, pase lo que pase.
5. Nada en paralelo.
6. **Si este diagnóstico no clasifica**, se declara que **`qwen2.5:3b` no es medible limpiamente en
   esta máquina bajo condiciones controlables**, y esa limitación pasa a ser evidencia para la
   decisión de capacidad. **No se abre otra ronda.**

El punto 6 es el que impide que esto se convierta en una cadena infinita: **hay un final declarado.**

## 11 · Lo que este DP NO hace

- **No** ejecuta nada: se presenta para aprobación.
- **No** modifica prompt, catálogo, `ESPECIFICACIONES`, umbrales, protocolo ni `aura_skeleton/`.
- **No** repite el `0.5b`. Su resultado de la última tanda queda como evidencia válida: acción de
  catálogo pero semánticamente incorrecta (`monitoreo`, lista verde de lectura, en vez de
  `proponer_cambio`), **cero de tres campos requeridos**, 727 tokens de entrada, 61 generados,
  **266,9 s** de inferencia `[EJEC]`.
- **No** concluye si el `3b` aporta mejora material: esa pregunta sigue abierta y depende de esta
  medición.
