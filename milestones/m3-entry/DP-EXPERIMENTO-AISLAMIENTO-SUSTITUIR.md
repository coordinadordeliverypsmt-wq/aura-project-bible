# DP · Experimento de aislamiento: ¿puede el modelo decidir `sustituir`?

**Estado:** PROPUESTO. **No se ejecuta nada.** No implementa, no modifica producto, no abre capacidad.
**Fecha:** 2026-08-15 · `main` = `origin/main` = `d933a08`, intacto. Sin commits.
Clasificación D47: `[EJEC]` · `[LECT]` · `[INFER]` · `[HIPO]`.

---

## 1 · La única pregunta abierta

> **¿Puede el modelo producir correctamente `sustituir` cuando `fichero` y `buscar` ya están
> determinados y se le retira de la tarea la selección de acción y la construcción del resto de
> parámetros?**

Es el último interrogante técnico vivo. Todo lo demás está medido: ambos modelos consumen el contexto,
ninguno produce propuesta ejecutable, el gobierno rechaza correctamente lo inválido, y la métrica sigue
en **0/7**.

## 2 · Por qué este experimento y no otro

`sustituir` es **el único campo irreducible** `[EJEC]`. `fichero` y `buscar` viajan literalmente en la
tarea derivada; `sustituir` exige leer el fichero objetivo y **decidir** un patrón nuevo.

Si el modelo no puede decidirlo **ni siquiera en las condiciones más favorables imaginables**, la vía
del razonador local queda cerrada para este dominio, y ninguna frontera determinista lo arregla.

## 3 · Qué se retira de la tarea, y por qué eso es el aislamiento

| Elemento | En los humos | En este experimento |
|---|---|---|
| Selección de acción del catálogo | exigida | **retirada** |
| Construcción de `fichero` y `buscar` | exigida | **retirada** — se dan hechos |
| Formato JSON con `intent`/`action`/`args`/`say` | exigido por `_SYSTEM` | **retirado** |
| Catálogo completo en el prompt | presente (995 caracteres) | **ausente** |
| Decidir el patrón nuevo | exigida | **lo único que queda** |

**Se prescinde deliberadamente de `_SYSTEM`.** Es justo lo que impone la selección de acción y el
formato, es decir, lo que este experimento quiere quitar de en medio. **Consecuencia directa: esto NO
mide la ruta del producto**, y §9 lo desarrolla.

## 4 · Caso de prueba

El mismo laboratorio sembrado, sin cambios `[EJEC]`: garantía `laboratorio-humo.toml:H1`, estado
AUSENTE, verdad de referencia conocida por construcción.

**Fichero objetivo** `laboratorio_objetivo.py`, contenido íntegro:

```python
def cobrar(x):
    if not autorizado(x):
        raise PermisoDenegado
    return x
```

**Patrón declarado que ya no aparece:** `    if not tiene_permiso(x):`
**Verdad de referencia:** `    if not autorizado(x):` — aparece **exactamente una vez**.

## 5 · Entrada exacta — PROMPT CONGELADO

Se fija aquí, antes de ejecutar. Si cambia, la tanda se anula y se repite. Su SHA-256 se calculará y
registrará en la evidencia.

```
En un fichero de declaraciones hay un patron declarado que ya no aparece en el fichero objetivo.

Patron declarado que ya no aparece:
    if not tiene_permiso(x):

Contenido actual del fichero objetivo (laboratorio_objetivo.py):
def cobrar(x):
    if not autorizado(x):
        raise PermisoDenegado
    return x

Responde UNICAMENTE con la linea del fichero objetivo que debe sustituir al patron declarado.
Sin explicaciones, sin formato, sin comillas.
```

**Sin `system`. Sin `format: json`.** Se pide texto plano porque la estructura es precisamente lo que
se ha retirado.

**Modelos:** `qwen2.5:0.5b` y `qwen2.5:3b`. **Un intento por modelo, sin reintentos.**

## 6 · Criterio binario de éxito

Se evalúa **leyendo**, sin ejecutar nada. Dos niveles, ambos binarios, y se reportan los dos:

| Nivel | Condición |
|---|---|
| **PASS estricto** | La respuesta, tras `strip()`, es exactamente `if not autorizado(x):` |
| **PASS funcional** | La respuesta aparece **exactamente una vez** en el fichero objetivo **y** contiene la subcadena `autorizado` |

**Por qué hacen falta los dos niveles.** «Aparece exactamente una vez» por sí solo es insuficiente:
la cadena `raise` también aparece una vez y sería una respuesta equivocada. Exigir además `autorizado`
ata el criterio a la garantía real. Y el nivel estricto evita discutir sobre espacios en blanco.

**FALLO** = ninguno de los dos niveles, o respuesta que fabrica texto ausente del fichero, o
no termina dentro del timeout.

### Qué es una propuesta correcta y qué no

| Respuesta | Veredicto |
|---|---|
| `    if not autorizado(x):` | **PASS estricto** |
| `if not autorizado(x):` | PASS estricto (tras `strip()`) |
| `if not autorizado(x):\n        raise PermisoDenegado` | **PASS funcional** — sirve, pero no es la línea pedida |
| `raise` | **FALLO** — aparece una vez, pero no es la guarda |
| `if not tiene_permiso(x):` | **FALLO** — repite el patrón obsoleto |
| `autorizado(x)` | PASS funcional; se anota que no es una línea completa |
| Cualquier texto ausente del fichero | **FALLO por fabricación** — y se registra como tal, que es el dato más grave |

## 7 · Timeout y condiciones de memoria

| Parámetro | Valor |
|---|---|
| Timeout | **1800 s** — el mismo que ya cubrió a ambos modelos |
| Umbral antes de cargar | RAM disponible **≥ 1.400 MB** y swap libre **≥ 600 MB** |
| Umbral tras cargar | RAM disponible **≥ 150 MB**; si no, no se envía el prompt |
| Carga de `3b` | **desacoplada**: en primer plano, con `keep_alive`, y la medición después. Validado hoy `[EJEC]` |
| Al terminar | descargar el modelo |
| Paralelismo | ninguno |

**El prompt es mucho más corto que el de los humos** —unos 300 caracteres frente a 2.386— así que la
ingesta será una fracción de los 638 s que costó al `3b` `[INFER]`. Es un experimento barato.

**Abandono:** un solo intento por modelo. Cualquier fallo de memoria o de carga → se detiene, se
reporta el modo, **no se reintenta**. Si ninguno de los dos modelos llega a responder, se declara **no
medible** y se cierra la línea.

## 8 · Qué conclusión PERMITE

| Resultado | Conclusión que autoriza |
|---|---|
| **FALLO en ambos** | **Fuerte y definitiva para este dominio.** Si el modelo no decide el patrón en la tarea más fácil posible —fichero de cuatro líneas, sin selección de acción, sin catálogo, sin formato—, no lo hará en la real. **Cierra la vía del razonador local aquí**, y la frontera determinista queda descartada como palanca |
| **PASS en alguno** | Que el modelo **sabe decidir el patrón** cuando se le aísla la tarea. Localiza la frontera: el obstáculo estaría en la representación, no en el razonamiento |

## 9 · Qué conclusión NO PERMITE — y esto importa más que lo anterior

**El experimento está deliberadamente sesgado hacia el PASS, así que un PASS vale poco y un FALLO vale
mucho.** Conviene tenerlo delante al leer el resultado:

1. **Un PASS no demuestra que AURORA pueda hacerlo.** Se han retirado `_SYSTEM`, el catálogo, la
   selección de acción y el formato — es decir, **toda la capa cuya viabilidad se discute**. Mide al
   modelo desnudo, no al producto.
2. **Un PASS sobre un fichero de cuatro líneas no generaliza.** Con una sola línea candidata que
   contenga `if`, la tarea roza lo trivial. Un fichero real tiene cientos de líneas y varias
   plausibles. **El resultado no dice nada sobre ficheros reales.**
3. **No mide latencia del turno real.** El prompt es ~8 veces más corto; los tiempos no son comparables
   con los humos.
4. **No autoriza implementar nada** — ni frontera determinista, ni parser, ni traductor, ni cableado
   del razonador al ciclo.
5. **No mueve la métrica de gobierno.** Sigue en **0/7** pase lo que pase, porque no se completa
   ningún trabajo: es una medición, no una capacidad.
6. **No sustituye a la pregunta de recurso.** Un turno del `3b` seguiría costando 13 minutos `[EJEC]`.

## 10 · Hechos que este DP conserva sin reabrir

- `0.5b`: responde pero **no produce propuesta válida** — 3 turnos `[EJEC]`.
- `3b`: **mejora la selección semántica** de la acción —eligió lista roja que altera— pero **tampoco
  produce los tres campos** — 1 turno `[EJEC]`.
- **Ambos: 0 propuestas ejecutables.** 0 de 3 campos en 4 de 4 respuestas `[EJEC]`.
- El gobierno **rechaza correctamente** las propuestas inválidas `[EJEC]`.
- **0/7** objetivos nuevos completables sigue siendo la métrica vigente `[EJEC]`.
- **Como hipótesis, no como hecho:** parte del error podría venir de la generalización de los nombres
  de argumento visibles en el catálogo `[INFER]` — coherente con las cuatro respuestas, **no
  cuantificada**.

## 11 · Riesgos del propio experimento

1. **Sobreinterpretar un PASS.** El riesgo principal, y por eso §9 va antes que cualquier conclusión.
2. **Que se lea como el primer paso de una implementación.** No lo es: es diagnóstico, y su resultado
   más probable —dado 0 de 3 campos en 4 de 4— es el FALLO.
3. **Cadena infinita de experimentos.** Por eso §7 declara un final: si no clasifica, se cierra.

## 12 · Coste

Dos inferencias, una por modelo, con prompt corto. Minutos, no horas. Reutiliza el laboratorio, el caso
sembrado y el protocolo de carga desacoplada ya validados. **No construye nada.**

---

# 13 · RESULTADOS Y EVIDENCIA — ejecutado el 2026-08-15

*Sección añadida tras la ejecución. Las secciones §1–§12 son el registro metodológico previo y **no se
han alterado**. Todos los valores proceden literalmente de los dos artefactos JSON referenciados en
§13.5; no se añade interpretación más allá de la conclusión acotada de §13.6.*

## 13.1 · Condiciones comunes a las dos ejecuciones

| Parámetro | Valor |
|---|---|
| Prompt congelado, SHA-256 | `c154e4f662c6b780ae9f109c4292525517a5e51e236b74760a83b5ba97988edf` |
| Fichero objetivo, SHA-256 | `3372a741938b7258f97afb713c3846c1df908856f5e3aa817eeb39cff9854cb2` |
| `system` | **no** (`usa_system: false`) |
| `format: json` | **no** |
| Catálogo en el prompt | **no** |
| Intentos | **uno por modelo**, sin reintentos |
| Timeout | **1800 s** |
| Guarda de diseño | **válida** en ambas: devolver el patrón antiguo **no** satisface ningún nivel de PASS |
| Producto | **no ejecutado y no modificado**; ninguna acción despachada |
| Errores de transporte | ninguno (`error: null` en ambas) |

## 13.2 · `qwen2.5:0.5b` — **FAIL**

Instante `2026-08-15T20:44:11`. Modelo **no residente** al empezar.

**Respuesta:** `Lo siento, pero no puedo asistir con eso. Si tienes alguna otra pregunta o necesitas
asesoramiento en el tema de tu interesante proyecto, estaré encantado de ayudarte.`

**Clasificación mecánica: FABRICACIÓN** — `apariciones_en_el_objetivo: 0`, `es_el_patron_obsoleto: false`.

**Aclaración expresa, y es necesaria:** esa etiqueta es **una limitación de la categoría mecánica**, que
marca como FABRICACIÓN todo texto ausente del fichero objetivo. **El modelo no fabricó código: rechazó
la tarea.** Son fallos materialmente distintos, y confundirlos sobrestimaría el riesgo observado.

| Métrica | Valor |
|---|---|
| Carga | 23,31 s |
| Tokens entrada / generados | 144 / 43 |
| Ingesta | 77,14 s → 1,87 tok/s |
| Generación | 41,14 s → 1,05 tok/s |
| Inferencia total | 141,72 s (pared: 142,10 s) |
| RAM disponible antes / después | 1.610 → 1.513 MB |
| Swap libre antes / después | 1.368 → 958 MB |
| Carga CPU antes / después | 4,44 → 7,84 |

## 13.3 · `qwen2.5:3b` — **FAIL**

Instante `2026-08-15T20:55:43`. Modelo **residente** al empezar (carga desacoplada en primer plano).

**Respuesta:** `if not tiene_permiso(x):`

**Esa respuesta corresponde exactamente al patrón obsoleto**, el mismo que el prompt presentaba como
«el que ya no aparece». La **guarda anti-fabricación lo detectó**: `es_el_patron_obsoleto: true`,
`apariciones_en_el_objetivo: 0`, y **rechazó el resultado** — no pasó ni el nivel estricto ni el
funcional. **El patrón correcto esperado, `    if not autorizado(x):`, no fue producido.**

| Métrica | Valor |
|---|---|
| Carga imputada a la llamada | 5,39 s (el modelo ya estaba residente) |
| Tokens entrada / generados | 144 / 8 |
| Ingesta | 342,46 s → 0,42 tok/s |
| Generación | 101,23 s → 0,08 tok/s |
| Inferencia total | 450,57 s (pared: 453,93 s) |
| RAM disponible antes / después | 776 → 278 MB |
| Swap libre antes / después | 430 → 871 MB |
| Carga CPU antes / después | 6,91 → 8,19 |

## 13.4 · Disco durante la ejecución

Sistema de ficheros raíz al **90–98 %** durante la campaña. El experimento **no crea laboratorio** ni
copias del repositorio: cada ejecución escribe únicamente su artefacto JSON (2.507 y 2.212 bytes).

## 13.5 · Artefactos de evidencia

Ubicados en `milestones/m3-entry/medicion-razonador/`, **fuera de cualquier directorio temporal**:

| Fichero | Bytes | SHA-256 |
|---|---|---|
| `evidencia-aislamiento-qwen2.5-0.5b-20260815-204634.json` | 2.507 | `511f8bc217477735dbaf31d22a969aad8c57b697eb3137c87f5954e091257418` |
| `evidencia-aislamiento-qwen2.5-3b-20260815-210320.json` | 2.212 | `c358bf796a4166b6d6d92ae4aaf25f6152e4e7d77c344abd7c4e4511e7396dfd` |

Cada uno conserva 27 claves: prompt íntegro, fichero objetivo, patrón obsoleto, patrón correcto
esperado, guarda de diseño, respuesta cruda, clasificación, memoria antes/después y latencias.

## 13.6 · Conclusión — estrictamente limitada

> En las condiciones de este experimento, ninguno de los dos modelos produjo el patrón correcto. El
> resultado descarta que la representación/estructura del problema, por sí sola, sea la explicación
> suficiente del fallo observado. El resultado **NO** permite concluir nada sobre otros modelos,
> cuantizaciones, ficheros reales ni sobre la capacidad general de razonamiento local.

## 13.7 · Alcance del resultado

- **Métrica de autonomía = 0/7.**
- **Este experimento NO cambia esa métrica.** Medir capacidad no equivale a completar trabajo.
- **Este resultado NO autoriza construir producto sobre el razonador local.**
- **Cualquier evaluación de otro modelo, cuantización o recurso requiere un nuevo Decision Package y
  aprobación previa.**
- **La rama de capacidad del razonador permanece abierta.** Lo que este experimento cierra es la rama
  de la representación, no la del razonamiento.

---

**Objetivo, en una línea:** localizar la frontera real del razonamiento **sin construir otro tubo antes
de saber si existe consumidor**.
