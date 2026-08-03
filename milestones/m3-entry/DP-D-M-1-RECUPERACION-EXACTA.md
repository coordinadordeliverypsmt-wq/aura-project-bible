# Decision Package — D-M-1: recuperación exacta de memoria en corpus grande

**Estado:** propuesta. **Pendiente de aprobación del CEO.** No se ha escrito ni una línea en el
repositorio: todo lo medido aquí procede de prototipos ejecutados fuera del árbol de código.
**Alcance:** exclusivamente `D-M-1`. No toca el criterio de cobertura, el umbral 0,60, la
tokenización ni la batería como criterio de aceptación.

**Clasificación de la evidencia** (D47): todas las cifras de este documento son `[EJEC]` salvo donde
se marque explícitamente `[INFER]` o `[HIPO]`.

---

## 1 · El problema, corregido

`PersistentMemory.recall` construye el conjunto de candidatos recorriendo los términos de la consulta
de lista de posteo más corta a más larga, y **salta** los que superan `_UMBRAL_UBICUO = 256` en cuanto
ya hay algún candidato. Consecuencia: **un recuerdo cuyo único solape con la consulta son términos
ubicuos nunca entra en el conjunto de candidatos**, y por tanto nunca llega a puntuarse — no se
descarta por cobertura insuficiente, se descarta antes de mirarlo.

### Corrección del contraejemplo publicado

El contraejemplo que publiqué en `DEUDA-N1-RECUPERADOR.md` **demostraba el síntoma pero no aislaba la
causa**. Sus 300 recuerdos de relleno contenían los mismos términos que el objetivo, así que empataban
en cobertura y el `top-k` habría enterrado el objetivo **aunque el conjunto de candidatos fuese
correcto**: verificado, el barrido completo tampoco lo recuperaba. Contraejemplo aislado y verificado:

```
corpus:    300 recuerdos con "trabajo" (sin "reunion")   → posteo trabajo = 301
           300 recuerdos con "reunion" (sin "trabajo")   → posteo reunion = 301
           +  objetivo:   "Mi trabajo tiene una reunion importante"   → cobertura 2/3
           +  distractor: "Nota xyzterm sin relacion"                 → cobertura 1/3
consulta:  "trabajo reunion xyzterm"

recuerdos que alcanzan la cobertura, por fuerza bruta: exactamente 1 (el objetivo)
```

| Estrategia de candidatos | Candidatos | Posteos visitados | ¿Recupera el objetivo? |
|---|---|---|---|
| **Vigente** | 1 | 1 | **No** |
| Filtro por prefijo | 302 | 302 | Sí |
| Unión completa | 602 | 603 | Sí |

### Magnitud real del defecto

Corpus sintético de **3 000 recuerdos** con vocabulario zipfiano (14 términos por encima del umbral),
400 consultas aleatorias con semilla fija, comparadas contra barrido completo por fuerza bruta:

> **El algoritmo vigente devuelve un resultado distinto del correcto en el 9,8 % de las consultas
> (39 de 400).**

No es un caso de laboratorio: es una de cada diez consultas en cuanto el historial crece.

### Por qué esto es más grave que un fallo de calidad

El defecto produce **falsos negativos**. Cuando `recall` devuelve vacío, ADR-0014 obliga al Core a
**declarar la ausencia de registro** sin llamar al LLM. Es decir: **AURA afirma con autoridad que no
recuerda algo que sí tiene guardado.** No es que responda peor — es que emite una afirmación falsa
sobre su propio estado, con el respaldo de una garantía diseñada para no fabricar. Roza INV-9 por el
lado contrario al habitual: no finge una capacidad que no tiene, niega una que sí tiene.

**El dato no se pierde del disco.** El JSONL es append-only e íntegro; el recuerdo sigue ahí y es
recuperable por otra consulta. Lo que falla es el acceso, no el almacenamiento.

---

## 2 · Restricciones que la solución no puede romper

| Restricción | Qué exige |
|---|---|
| **ADR-0014** | Cero resultados ⇒ declarar ausencia sin llamar al LLM. La solución debe hacer que «cero resultados» signifique de verdad «no hay nada que cubra la consulta» |
| **MA.2a** | `recall` no puede recorrer los N recuerdos en cada turno. Fue una garantía de rendimiento aprobada: 9,22 ms con 3 000 recuerdos era inaceptable |
| **Determinismo** | Mismo input ⇒ mismo output, entre procesos y entre arranques. Sin esto nada de lo anterior es auditable |
| **Criterio de cobertura** | `_COBERTURA_MINIMA = 0,60` y la tokenización quedan **intactos**. Este DP cambia *qué recuerdos se examinan*, nunca *cuáles se aceptan* |
| **Formato persistido** | `~/.aura/*.jsonl` no cambia. Sin migración de datos |

---

## 3 · Alternativas

### Notación

`n` = términos informativos de la consulta · `m = ⌈0,60·n⌉` = términos que un recuerdo debe contener
para alcanzar la cobertura · `N` = recuerdos del usuario · `L_t` = longitud de la lista de posteo del
término `t` · `P = Σ L_t` sobre los términos de la consulta · `|C|` = candidatos generados.

---

### Alternativa A — Filtro por prefijo *(recomendada)*

**Algoritmo.** Ordenar los términos de la consulta por longitud de posteo ascendente y unir
únicamente las **`n − m + 1` listas más cortas**.

**Por qué es exacto — principio del palomar.** Un recuerdo que alcanza la cobertura contiene al menos
`m` de los `n` términos. Si no apareciera en ninguna de las `n − m + 1` listas elegidas, sus `≥ m`
términos tendrían que estar todos entre las `m − 1` listas restantes: imposible. **Luego todo recuerdo
cualificado aparece forzosamente en al menos una lista del prefijo.** No es una heurística que acierte
casi siempre: es una garantía. Y el argumento **no depende de que sean las más cortas** —funciona con
cualquier subconjunto de ese tamaño—, así que elegir las más cortas es pura optimización de coste y no
compromete la exactitud.

**Complejidad.** `O(n log n + V + |C|·n)` con `V` = suma de las `n − m + 1` listas más cortas.
Asintóticamente `V ≤ ((n−m+1)/n)·P ≈ 0,4·P` con `c = 0,60`. `[INFER]` de la fórmula; el valor medido
es mejor porque las listas cortas son las que se eligen.

**Medido.**

| Métrica | Valor |
|---|---|
| Discrepancias frente a fuerza bruta (400 consultas, 3 000 recuerdos) | **0 / 400** |
| Discrepancias sobre la batería oficial (77 consultas) | **0 / 77** |
| Posteos visitados vs unión completa (sintético) | **15,9 %** |
| Latencia media por consulta con 3 000 recuerdos | **≈ 1 ms** (barrido completo: 9,22 ms) |
| Determinismo entre 5 valores de `PYTHONHASHSEED` | **1 sola huella SHA-256** |
| Batería oficial: recall@3 / FP puros / FP críticos | **0,6604 / 0 / 2 — idénticos a hoy** |
| Peor caso (todos los términos ubicuos) | 50–67 % de la unión completa |

**Impactos.** *Complejidad:* mínima — una línea de selección; el resto de `recall` no cambia.
*Rendimiento:* ~1,6× más lento que hoy, **5,6× más rápido que el barrido completo**; MA.2a se preserva.
*Determinismo:* el resultado es independiente del desempate entre listas de igual longitud (por el
argumento anterior); **solo el coste** puede variar, por lo que conviene desempatar por término.
*Memoria:* sin estructuras nuevas. *ADR-0014:* lo refuerza — «cero resultados» pasa a significar lo que
dice. *MA.2a:* respetada; sigue sin recorrer los N recuerdos.

**Ventajas.** Exacta, no heurística. Sin cambio de formato ni de índice. Reversible con un `revert`.
No mueve ninguna cifra de la batería, así que la migración no arrastra regresión.

**Riesgos.** (1) El peor caso —consulta larga con todos los términos ubicuos— cuesta ~2/3 de la unión
completa; acotado y medido, pero es el escenario a vigilar. (2) **Al ampliar los candidatos pueden
aflorar falsos positivos que el defecto enmascaraba**: no son nuevos errores, son errores que el corte
ocultaba. Sobre la batería no aparece ninguno, pero es la hipótesis a falsar en la implementación.

**Casos límite.** `n = 1` → une 1 lista (la única): correcto. `n = 2` → `m = 2`, une **solo la más
corta**: correcto y más barato que hoy. **Término inexistente en el índice** → su posteo vale 0, es el
más corto y ocupa un hueco del prefijo sin aportar candidatos; la exactitud se mantiene, pero hay una
optimización correcta disponible: si `n − (términos inexistentes) < m`, **ningún** recuerdo puede
cualificar y se puede devolver vacío sin tocar el índice.

**Migración.** Cambio de una función, sin datos que migrar y sin reindexado. Se puede desplegar y
revertir en un commit.

---

### Alternativa B — Unión completa (eliminar el corte)

**Algoritmo.** Unir las listas de posteo de todos los términos. Es lo que hacía el código antes de
MA.2a, con el criterio de cobertura encima.

**Complejidad.** `O(n log n + P + |C|·n)`.

**Ventajas.** Exacta por construcción y trivial de razonar: elimina el `continue` y ya está. La
implementación más difícil de equivocar.

**Riesgos.** **Revierte MA.2a**, una garantía de rendimiento ya aprobada por el CEO. Medido: 5,6× más
lento que A en el mismo banco, 758 080 posteos visitados frente a 120 349. Cambiar una garantía
aprobada para arreglar otra es exactamente el intercambio que el proyecto ha decidido no hacer a
ciegas.

**Casos límite.** Ninguno propio: es el comportamiento de referencia contra el que se miden las demás.

**Migración.** Trivial. **Pruebas:** las mismas que A, más una revisión explícita de los umbrales de
`tests/performance/test_escalabilidad_memoria.py`, que muy probablemente dejarían de pasar.

**Uso recomendado:** no como solución, sino como **oráculo de las pruebas** — es la referencia contra
la que verificar que A es exacta.

---

### Alternativa C — Completado adaptativo *(refutada con datos)*

**Algoritmo.** Mantener el corte actual y, si el resultado «parece insuficiente» (menos de `k`
resultados), rehacer la consulta con unión completa.

**Por qué no funciona.** Es la alternativa barata y evidente, y es **falsa**. Medido sobre las 39
consultas en que el algoritmo vigente devuelve un resultado incorrecto:

> **36 de 39 (92 %) ya devolvían `k = 3` resultados.** Estaban completos y equivocados.

El disparador «faltan resultados» no se activaría en el 92 % de los fallos. Para detectar el resto
haría falta saber si existe un candidato mejor entre los no examinados — que es precisamente la
pregunta que el corte impide responder. **Circular.**

**Riesgo adicional.** Daría una falsa sensación de resolución: el defecto seguiría vivo en 9 de cada
10 casos, ahora con una mitigación documentada que invita a no volver a mirar.

---

### Alternativa D — WAND / recorrido por documento con umbral

**Algoritmo.** El estándar de recuperación de información para top-k con umbral: cursores sobre las
listas ordenadas, cota superior de puntuación por término, y salto de bloques que no pueden superar el
umbral actual.

**Complejidad.** `O(P)` en el peor caso, típicamente muy sublineal.

**Ventajas.** Exacto para top-k. Escala mejor que A cuando `n` es grande y el corpus enorme. Es el
camino natural si algún día la memoria crece órdenes de magnitud.

**Riesgos.** Complejidad muy superior: cursores, punteros de salto, invariantes de cota. Introduce
estructuras propias con su propio determinismo que auditar. **Desproporcionado para el problema
actual:** resuelve a escala de millones un defecto que aparece a escala de cientos, y A ya lo elimina
por completo. Aplica INV-9 en su versión organizativa: no construir maquinaria que el sistema aún no
necesita.

**Migración.** Requeriría índice con listas ordenadas y bloques — cambio estructural, no de una función.

---

### Alternativa E — Subir `_UMBRAL_UBICUO` o hacerlo relativo al corpus *(descartada)*

Convertir el 256 fijo en, por ejemplo, el 10 % de `N`. **No resuelve nada:** desplaza la frontera a un
corpus mayor sin eliminar el régimen defectuoso, y lo hace más difícil de detectar porque el umbral
deja de ser un número fijo que se pueda ejercitar en una prueba. Es la peor combinación: mantiene el
defecto y le quita el punto de apoyo para probarlo. Se documenta para dejar constancia de que se
consideró.

---

## 4 · Comparativa

| | A · Prefijo | B · Unión completa | C · Adaptativo | D · WAND |
|---|---|---|---|---|
| **Exactitud** | Garantizada (palomar) | Garantizada | **No** (92 % de fallos sin detectar) | Garantizada |
| **Complejidad de código** | Baja | Mínima | Media | Alta |
| **Rendimiento vs hoy** | ~1,6× más lento | ~5,6× más lento | ≈ igual | Mejor con `n` grande |
| **Respeta MA.2a** | Sí | **No** | Sí | Sí |
| **Determinismo** | Verificado, 1 huella | Sí | Sí | A verificar |
| **Memoria adicional** | Ninguna | Ninguna | Ninguna | Cursores + índice nuevo |
| **Migración** | Una función | Una línea | Una función | Estructural |
| **Mueve la batería** | No | No | No | No |

---

## 5 · Recomendación

**Alternativa A — filtro por prefijo.** Es la única que elimina el defecto **por construcción** sin
sacrificar una garantía aprobada. No es un compromiso entre exactitud y velocidad: es exacta *y* sigue
siendo cinco veces más rápida que el barrido que MA.2a eliminó. El coste —1,6× sobre el algoritmo
vigente— compra pasar del 9,8 % de respuestas incorrectas al 0 %.

**Con B como oráculo, no como alternativa:** la unión completa debe existir en las pruebas como
referencia de verdad contra la que se contrasta A.

**Deber de disenso.** Un punto que el CEO debe pesar antes de aprobar: A puede **hacer visibles falsos
positivos que el defecto venía ocultando**. Si al implementar aparecen FP críticos nuevos, la respuesta
correcta **no** es volver al corte —eso sería preferir un sistema que miente por omisión a uno que se
equivoca a la vista—, sino tratarlos en el marco de la cobertura. Lo señalo ahora para que no se
interprete después como una regresión introducida por este cambio.

---

## 6 · Pruebas que se añadirían al Quality Gate

La lección de D-M-1 no es el defecto, es que **existía un régimen entero que ninguna prueba podía
alcanzar**. Las pruebas propuestas atacan eso primero:

1. **Control de exactitud por encima del umbral.** Corpus > `_UMBRAL_UBICUO` con términos ubicuos
   reales; comparación **contra fuerza bruta** en un lote de consultas con semilla fija. Es el control
   que hoy no existe y sin el cual ninguna afirmación de equivalencia es verificable.
2. **El contraejemplo aislado de D-M-1** como caso de regresión permanente.
3. **Prueba de propiedad:** para corpus aleatorio con semilla fija, `prefijo ≡ fuerza bruta` en N
   consultas. Falsable por construcción.
4. **Determinismo entre procesos** a escala grande (`PYTHONHASHSEED` 0..4), extendiendo la que ya
   existe para la batería.
5. **Guardia de rendimiento (MA.2a):** que el prefijo **no** visite todas las listas — si alguien
   «arregla» algo pasando a unión completa, esta prueba debe romperse.
6. **Meta-prueba de alcance:** una prueba que falle si la batería oficial deja de contener un caso por
   encima de `_UMBRAL_UBICUO`. Impide que el hueco de cobertura se reabra en silencio.

**Mutantes obligatorios** (`mutaciones/memoria-prefijo.toml`), porque una prueba sin caso de control no
vale:

| Mutante | Debe morir por |
|---|---|
| `n − m + 1` → `n − m` (prefijo corto) | pierde exactitud: el palomar deja de aplicar |
| `n − m + 1` → `n` (unión completa disfrazada) | guardia de rendimiento |
| Elegir las listas **más largas** | *no* muere por resultado (sigue siendo exacto): debe morir por **coste** — si ninguna prueba lo detecta, falta la guardia de MA.2a |
| Eliminar el desempate por término | determinismo del coste |

---

## 7 · Ampliación del benchmark — y una advertencia sobre el orden de prioridades

El CEO pidió revisar qué otros regímenes no ejercita la batería **antes** de tocar el algoritmo. El
barrido encontró **cinco defectos, y cuatro de ellos son más urgentes que D-M-1**. Todos verificados
por ejecución y registrados en `DEUDA-N1-RECUPERADOR.md`.

### Perfil medido de la batería: por qué no podía ver nada de esto

| Dimensión | Batería | Uso real |
|---|---|---|
| `user_id` distintos | **1** (65/65 `u1`) | ≥1, sin guardia |
| Términos por recuerdo | 3–7 | turnos episódicos íntegros (36+ medidos) |
| Términos por consulta | 1–5 | crudo del usuario, con cortesía |
| Posteo máximo | **7** | `dijo`/`usuario` cruzan 256 en el turno 257 |
| Recuerdos con forma de pregunta | **0 de 65** | uno por turno |
| Contenidos duplicados | **prohibidos por aserción** | correcciones y repeticiones |

La batería está calibrada **justo en el borde del régimen donde el algoritmo funciona**. No es mala
fe: es que se construyó para el problema que teníamos delante y nadie comprobó qué quedaba fuera.

### Los hallazgos, por urgencia

| # | Defecto | Se dispara | Gravedad |
|---|---|---|---|
| **D-M-2** | El eco `usuario dijo:` del propio turno **desactiva ADR-0014** | **repetir una pregunta 2 veces** | **Crítica — regla no negociable** |
| **D-M-3** | «oye AURA por favor dime» lleva el recall de 0,660 a **0,000** | hablar con naturalidad | Alta |
| **D-M-4** | Un recuerdo largo se vuelve atractor universal de FP críticos | dictar un turno largo | Alta |
| **D-M-5** | Un recuerdo **refutado** sigue entrando en el prompt del LLM | decir «eso ya no es cierto» | Alta — soberanía |
| **D-M-6** | Al corregir un dato, `recall` devuelve el **más antiguo** | corregir cualquier hecho | Media |
| D-M-1 | Recuerdo irrecuperable en régimen ubicuo | >256 recuerdos con un término de contenido | Media |

**Consecuencia para este DP, dicha sin adornos: D-M-1 ya no es el problema más urgente del
recuperador.** El análisis y la recomendación de las secciones 1–6 siguen siendo válidos y la solución
sigue siendo correcta — pero sería un error de prioridad implementarla antes que D-M-2, que se dispara
en el segundo turno de conversación y apaga la garantía que impide fabricar.

### Casos que la batería debe incorporar

Ordenados por el defecto que destapan. **Se añaden antes de tocar el algoritmo**, para que cada
corrección tenga su caso de control ya en rojo:

1. **Auto-eco (D-M-2):** recuerdos `usuario dijo: <pregunta>` en el corpus, y una consulta idéntica al
   texto de uno de ellos con `esperado: null` y `gravedad: "puro"`.
2. **Consultas largas (D-M-3):** duplicar un subconjunto de consultas literales con preámbulo
   conversacional (6–10 términos informativos) y el mismo `esperado`.
3. **Recuerdo largo (D-M-4):** 2–3 recuerdos de 30–60 términos informativos, con consultas `critico`
   sobre entidades que solo mencionan de pasada.
4. **Refutados (D-M-5):** exige un campo nuevo por recuerdo (`provenance`) para poder expresar
   `refutada: true`, más una consulta que lo cubriría con `esperado: null`.
5. **Contradicción (D-M-6):** par viejo/nuevo del mismo hecho con `esperado` = el nuevo. **Obliga a
   levantar la aserción que prohíbe duplicados**, que es justo lo que impedía ver este caso.
6. **Régimen de volumen (D-M-1):** no cabe en un fichero de 65 recuerdos. Necesita **relleno
   paramétrico** (>256 recuerdos generados) o una batería aparte de volumen.
7. **Multiusuario:** 5–8 recuerdos `user_id: "u2"` colindantes con los de `u1`, y que el arnés use el
   `user_id` de la consulta en vez del `"u1"` cableado.

### Descartados explícitamente, para no inflar el trabajo

`k` fuera de {1,3,5} (producción usa siempre 3); migración del formato antiguo en `_load` (ruta muerta,
merece una unitaria de 4 líneas, no un caso de batería); recuerdos de 0 términos informativos (su único
efecto es engordar posteos, que ya es D-M-1); y el campo `kind`, que `recall` no lee en ningún punto.

---

## 8 · Retorno sobre Tokens

- **Menos intervención humana:** hoy la única forma de descubrir este tipo de defecto es que alguien
  sospeche y construya el corpus a mano. Las pruebas 1 y 6 lo convierten en algo que el Quality Gate
  detecta solo.
- **Menor consumo de contexto:** un recuperador exacto elimina una clase entera de investigación
  («¿por qué AURA no encontró esto?») que consume sesiones completas — esta misma lo demuestra.
- **Reutilización:** el oráculo de fuerza bruta y el generador de corpus sintético sirven para
  **cualquier** cambio futuro del recuperador, incluida N2.
- **Para AURORA:** deja establecido el patrón «afirmación de equivalencia ⇒ oráculo ejecutable», que es
  reutilizable mucho más allá de la memoria.

---

## 9 · Lo que este DP NO incluye

- **No cambia** `_COBERTURA_MINIMA`, la tokenización, las palabras vacías ni el criterio de aceptación.
- **No aborda** los límites de N1 ya documentados (posesivos «de mi vecino», consultas de un solo
  término informativo): son frontera semántica, no de recuperación. Corresponden a N2.
- **No toca** `SemanticMemory` ni la deuda `D-N2-5`.
- **No propone** ampliar el alcance funcional del MVP (D23).
