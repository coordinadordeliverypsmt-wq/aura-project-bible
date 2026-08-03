# Decision Package — D-M-1: recuperación exacta de memoria

**Estado: APROBADO COMO DOCUMENTO DE DECISIÓN** por el CEO (2026-08-03), con dos observaciones, ambas
ya incorporadas:

1. La cota de A′ queda etiquetada como **elección de diseño «suficiente y conservadora»**, no como la
   única cota correcta — ver el apartado dedicado dentro de A′.
2. **La implementación NO está autorizada todavía.** Queda **supeditada a resolver antes `D-M-2`**, por
   su mayor impacto operativo. Decisión del CEO, coherente con lo que este mismo análisis demostró:
   D-M-2 se dispara en el segundo turno de conversación, D-M-1 exige un régimen que aún no se ha
   observado en uso real.

**No se ha modificado el repositorio ni implementado ninguna alternativa.** Todas las mediciones
proceden de prototipos ejecutados fuera del árbol de código, en `$CLAUDE_JOB_DIR/tmp/`.

**Recomendación en una línea:** adoptar **A′ — filtro por prefijo con cota de seguridad**. Es exacta
por demostración, respeta MA.2a y no puede ser más lenta que el barrido completo.

**Cambio respecto al borrador anterior:** el borrador recomendaba **A** (prefijo puro). El ataque de
la §5 encontró un agujero real de rendimiento en A, y la recomendación pasó a **A′**. Este documento
sustituye íntegramente al borrador.

**Clasificación de la evidencia** (D47). Cada cifra lleva su marca; el inventario de procedencia está
en la §8.

---

## 1 · El problema

`PersistentMemory.recall` construye los candidatos recorriendo los términos de la consulta de lista de
posteo más corta a más larga, y **salta** los que superan `_UMBRAL_UBICUO = 256` en cuanto ya hay algún
candidato. Consecuencia: **un recuerdo cuyo único solape con la consulta son términos ubicuos nunca
entra en el conjunto de candidatos** — no se descarta por cobertura insuficiente, se descarta antes de
mirarlo.

### Contraejemplo aislado `[EJEC]`

```
corpus:    300 recuerdos con "trabajo" (sin "reunion")   → posteo trabajo = 301 > 256
           300 recuerdos con "reunion" (sin "trabajo")   → posteo reunion = 301 > 256
           + objetivo:   "Mi trabajo tiene una reunion importante"  → cobertura 2/3 = 0,67
           + distractor: "Nota xyzterm sin relacion"                → cobertura 1/3
consulta:  "trabajo reunion xyzterm"

recuerdos que alcanzan la cobertura, por fuerza bruta: exactamente 1 (el objetivo)
resultado del recuperador vigente:                     []
```

El corpus está construido para que **solo un** recuerdo cualifique, de modo que el fallo no pueda
atribuirse al `top-k` ni al desempate. Una versión anterior de este contraejemplo usaba rellenos que
contenían ambos términos: demostraba el síntoma pero no aislaba la causa, porque el `top-k` habría
enterrado el objetivo aunque los candidatos fuesen correctos `[EJEC]`.

### Magnitud `[EJEC]`

Corpus sintético de 3 000 recuerdos, vocabulario zipfiano, 400 consultas aleatorias con semilla fija,
contrastadas contra barrido completo por fuerza bruta:

> **El algoritmo vigente devuelve un resultado distinto del correcto en el 9,8 % de las consultas
> (39 de 400).** De esos 39 fallos, **36 (92 %) ya devolvían 3 resultados**: completos y equivocados.

### Por qué importa

El defecto produce **falsos negativos**. Cuando `recall` devuelve vacío, ADR-0014 obliga al Core a
declarar la ausencia de registro sin llamar al LLM. Es decir: **AURA afirma con autoridad que no
recuerda algo que sí tiene guardado**, con el respaldo de una garantía diseñada para no fabricar. El
dato **no se pierde del disco** —el JSONL es append-only e íntegro—; lo que falla es el acceso.

---

## 2 · Barrido de regímenes no cubiertos, con clasificación

La batería oficial **no puede** ejercitar el régimen de D-M-1 por construcción: 65 recuerdos, posteo
máximo medido **7**, frente a un umbral de 256 `[EJEC]`. Eso motivó revisar qué otros regímenes quedan
fuera. Resultado del barrido, con la clasificación pedida.

### 2.1 · Defectos reales — reproducidos, violan una garantía declarada

| # | Defecto | Evidencia | Se dispara con |
|---|---|---|---|
| **D-M-2** | El eco `usuario dijo:` del propio turno **desactiva ADR-0014**. La pregunta se almacena y cubre su repetición con cobertura 1,00; en el turno 2 `hits` deja de estar vacío y el LLM recibe la propia pregunta como «memoria» | `[EJEC]` turno 1 → `hits=0`; turno 2 → `hits=1`, recuperado `"usuario dijo: ¿Recuerdas cual es el nombre de mi abuela?"` | **Repetir una pregunta una segunda vez.** Sin volumen ni tiempo |
| **D-M-3** | Una coletilla de cortesía derrumba el recall: la cobertura se normaliza por los términos de la **consulta**, así que cada palabra extra sube el listón | `[EJEC]` sin prefijo 0,660 · «por favor» 0,340 · «oye AURA por favor dime» **0,000** · «oye AURA una cosa que quería preguntarte» **0,000** | Hablar con naturalidad |
| **D-M-4** | Un recuerdo largo se vuelve atractor universal de FP críticos: la cobertura **nunca** normaliza por la longitud del recuerdo | `[EJEC]` un episódico de 36 términos responde a «¿qué coche tiene mi madre?» y «¿cuál es el teléfono de la oficina?» | Dictar un turno largo |
| **D-M-5** | Un recuerdo **refutado** sigue entrando en el prompt del LLM: `recall` no consulta `provenance`; el filtro vive solo en presentación | `[EJEC]` tras `marcar(refutada=True)`, `recall` lo sigue devolviendo con `{'refutada': True}` | Decir «eso ya no es cierto» |
| **D-M-6** | Al corregir un dato gana el **más antiguo** (desempate por índice ascendente) | `[EJEC]` entre «azul» y «ahora… verde», con `k=1` devuelve **azul** | Corregir cualquier hecho |
| **D-M-1** | Recuerdo irrecuperable en régimen ubicuo | `[EJEC]` §1 | >256 recuerdos con un término **de contenido** compartido |

### 2.2 · Deuda técnica — no viola una garantía hoy, pero acumula riesgo

| Hallazgo | Estado |
|---|---|
| `PersistentMemory` **no tiene ninguna prueba de aislamiento entre `user_id`**. La existente cubre solo `SimpleMemory`; el corpus es 65/65 `u1` | `[EJEC]` verificado que **hoy funciona**: el índice se clava en `(user_id, término)` y `recall("u2", …)` → `[]`. Ruta correcta, sin red |
| `SemanticMemory` no implementa `olvidar`/`marcar`/`_items` | Ya registrada como **D-N2-5**. `[EJEC]` `AttributeError` confirmado |
| `SemanticMemory` construye el índice léxico en cada escritura y **nunca lo usa** | `[EJEC]` ineficiencia, no defecto: no altera resultados |
| `SemanticMemory._vectores` se alinea por índice con `_store._items`, y `olvidar` reindexa `_items` sin tocar `_vectores` | `[INFER]` de la lectura del código — **desalineación silenciosa**; no ejecutado porque N2 no se materializa en esta máquina |

### 2.3 · Límites aceptados — comportamiento conocido y tolerado

| Límite | Por qué se acepta |
|---|---|
| `recall(k negativo)` recorta por la cola | `[EJEC]` producción usa **siempre** `k=3` por defecto (`orchestrator.py:363`, sin argumento). No hay ruta que lo alcance |
| Consulta sin términos informativos → `[]` | `[EJEC]` deliberado: emparejar por palabras vacías es lo que vaciaba de contenido ADR-0014 |
| Emoji y símbolos no son términos (`_terminos('🎉')` → `set()`) | `[EJEC]` consecuencia correcta de `\w+` |
| Migración del formato antiguo (array JSON) en `_load` | `[EJEC]` funciona; ruta muerta salvo instalaciones anteriores a MA.2a |
| Consulta de **un solo** término informativo: cobertura trivialmente 1,0 | Ya documentado. Estructural: denominador 1 |
| Los 2 adversariales «de mi vecino» / «de mi hermano» | Frontera de N1, con techo fijado en la prueba |
| Recuerdos de 0 términos informativos («usuario dijo: sí») | Su único efecto es engordar posteos ubicuos, que ya es D-M-1 |

### 2.4 · Hipótesis pendientes de evidencia

| Hipótesis | Qué falta para resolverla |
|---|---|
| Los formatos numéricos divergentes (`600123456` vs `600 12 34 56`) causan pérdida real de recall | **No he construido un fallo.** `[HIPO]`. Falla *hacia el silencio*, no hacia la fabricación, así que ADR-0014 lo cubre. Se resolvería con consultas de la misma cifra en formato distinto |
| D-M-1 se materializa en uso real | `[EJEC]` el régimen se alcanza en el turno **257** (~5 días), porque `usuario` y `dijo` no están en las palabras vacías. **Pero entrar en el régimen no basta**: verificado que con 301 recuerdos prefijados, «¿qué me dijo el médico del colesterol?» **sí** recupera el objetivo — lo salvan `medico` y `colesterol`. Sigue haciendo falta una palabra **de contenido** por encima de 256, y eso no se ha observado `[HIPO]` |
| El coste real de la alternativa D (WAND) | **No implementada.** `[HIPO]`: sus cifras provienen de la literatura, no de medición en este código |

### 2.5 · Regímenes verificados sin hallazgo `[EJEC]`

Corpus vacío → `[]` (ADR-0014 se activa) · el olvido **sobrevive al reinicio** y no arrastra lo demás ·
términos repetidos en la consulta dan resultado idéntico · acentos y `ñ` se normalizan · `k=0` → `[]` ·
consulta solo con palabras vacías → `[]`.

---

## 3 · Restricciones que la solución no puede romper

| Restricción | Qué exige |
|---|---|
| **ADR-0014** | Cero resultados ⇒ declarar ausencia sin llamar al LLM. «Cero» debe significar de verdad «nada cubre la consulta» |
| **MA.2a** | `recall` no puede recorrer los N recuerdos en cada turno |
| **Determinismo** | Mismo input ⇒ mismo output, entre procesos y entre arranques |
| **Criterio de cobertura** | `_COBERTURA_MINIMA` y la tokenización quedan **intactos**. Este DP cambia *qué recuerdos se examinan*, nunca *cuáles se aceptan* |
| **Formato persistido** | Sin migración de datos |

**Notación.** `n` = términos informativos de la consulta · `m = ⌈c·n⌉` con `c = 0,60` · `N` = recuerdos
del usuario · `L_t` = longitud del posteo de `t` · `P = Σ L_t` · `V` = suma de las `n − m + 1` listas
más cortas · `|C|` = candidatos.

---

## 4 · Alternativas

### A — Filtro por prefijo (puro)

**Algoritmo.** Ordenar los términos por longitud de posteo ascendente y unir las **`n − m + 1` listas
más cortas**.

**Demostración de exactitud (principio del palomar).** Un recuerdo que alcanza la cobertura contiene
`≥ m` de los `n` términos. Si no apareciera en ninguna de las `n − m + 1` listas elegidas, sus `≥ m`
términos estarían todos entre las `m − 1` restantes: imposible. **Todo recuerdo cualificado aparece
forzosamente en alguna lista del prefijo.** El argumento **no depende** de que sean las más cortas
—vale para cualquier subconjunto de ese tamaño—, luego elegir las más cortas es optimización de coste
y **el resultado es independiente del desempate**.

**Verificación empírica de la demostración `[EJEC]`:** 18 000 corpus aleatorios (3 000 por cada
`c ∈ {0,30 · 0,50 · 0,60 · 0,67 · 0,75 · 1,00}`), comparados contra fuerza bruta → **0 discrepancias**.

**Coste asintótico `[INFER]`.** `O(n log n + V + |C|·n)`, con `V ≤ ((n−m+1)/n)·P ≈ 0,4·P` para `c=0,60`.

**Coste medido `[EJEC]`.** Banco zipfiano, 3 000 recuerdos, 400 consultas: 15,9 % de los posteos de la
unión completa; ≈1 ms por consulta; 5,6× más rápido que fuerza bruta. Batería oficial: 67 posteos
frente a 234.

**Dónde gana.** Consultas con al menos un término selectivo — el caso normal. Corpus grande con
vocabulario desigual. Preserva MA.2a.

**Dónde falla.** **Peor caso: todos los términos de la consulta son ubicuos.** Entonces une
`n − m + 1` listas de tamaño ≈ N y visita **más** posteos que recuerdos tiene el usuario. Medido en el
peor caso construido (3 000 recuerdos, 8 términos presentes en todos): **hasta 2,15× más lento que la
fuerza bruta** `[EJEC]`, visitando hasta 12 000 posteos frente a 3 000 recuerdos. **A puede violar el
espíritu de MA.2a.**

**Veredicto: correcta pero incompleta.** Se sustituye por A′.

---

### A′ — Filtro por prefijo **con cota de seguridad** *(recomendada)*

**Algoritmo.** Igual que A, más una guarda previa: si la suma de los posteos que el prefijo visitaría
**supera α·N**, hacer barrido completo. Se propone **α = 1** (es decir, «más posteos que recuerdos
tiene el usuario»).

```
listas ← las (n − m + 1) de posteo más corto
si  Σ|listas| > α·N :  barrido completo        # nunca mucho peor que mirarlo todo
si no               :  unir listas             # poda exacta
```

**Exactitud.** Inmediata: **ambas ramas son exactas** —A por el palomar, el barrido completo por
definición—, luego A′ lo es sea cual sea la rama tomada. No introduce una tercera vía que auditar.

### La cota es una ELECCIÓN DE DISEÑO, no la única cota correcta

**Esto es una decisión de ingeniería, no un resultado.** `α = 1` es **suficiente y conservadora**, no
óptima ni única. La exactitud **no depende de α en absoluto**: al ser exactas las dos ramas, cualquier
valor produce el resultado correcto. `α` solo decide **dónde se prefiere una rama sobre la otra**, es
decir, es un parámetro de **coste**.

Medido `[EJEC]` — peor caso con `n=6`, y activaciones sobre las 400 consultas del banco realista:

| α | Peor caso | ¿Protege el peor caso? | Activaciones (realista) | ¿Exacta? |
|---|---|---|---|---|
| 0,5 | 5,08 ms | Sí | **8 / 400** — se activa sin necesidad | Sí |
| **1,0 (propuesta)** | **4,89 ms** | **Sí** | **0 / 400** | Sí |
| 1,5 | 4,95 ms | Sí | 0 / 400 | Sí |
| 2,0 | 4,91 ms | Sí | 0 / 400 | Sí |
| 4,0 | 8,61 ms | **No** | 0 / 400 | Sí |
| ∞ (= A puro) | 8,09 ms | **No** | 0 / 400 | Sí |

*(referencia: fuerza bruta en el mismo peor caso = 4,86 ms)*

**Lectura.** El rango útil es **α ∈ [1, 2]**: protege el peor caso sin activarse nunca en el normal.
Por debajo (0,5) la cota se dispara innecesariamente 8 veces de 400 y renuncia a poda que era válida;
por encima (≥4) deja de proteger. **`α = 1` es el extremo conservador del rango útil**, elegido porque
es el más fácil de razonar y de explicar en una prueba: *«nunca visites más posteos que recuerdos
tienes»*. Cualquier valor en `[1, 2]` sería igualmente defendible.

**Qué NO es esta cota.** No es una frontera teórica ni un óptimo demostrado. Es una **regla de parada
conservadora** que convierte un peor caso ilimitado en uno acotado. Si la medición futura mostrara que
el coste por posteo y el coste por recuerdo difieren mucho, `α` debería ponderarse — la forma de la
cota sobreviviría, su valor no.

**Coste asintótico `[INFER]`.** `O(n log n + min(V, N) + min(|C|,N)·n)`. **Acotado por la fuerza
bruta:** por construcción A′ nunca visita más que el barrido completo.

**Coste medido `[EJEC]`.**

| Escenario | A (prefijo) | A′ (con cota) | Fuerza bruta |
|---|---|---|---|
| Peor caso, `n=3` | 8,31 ms | **5,64 ms** | 3,87 ms |
| Peor caso, `n=7` | 8,31 ms | **5,30 ms** | 4,84 ms |
| Peor caso, `n=8` | 7,08 ms | **5,25 ms** | 4,93 ms |
| Banco realista, 400 consultas | ≈1 ms | ≈1 ms — **cota activada 0/400 veces** | 5,6× más lento |

Mediana de 25 repeticiones tras calentamiento de caché. La cota **no se activa nunca** en el banco
realista, así que no cuesta nada en el caso normal y solo actúa en el patológico.

**Determinismo `[EJEC]`.** Una sola huella SHA-256 entre 5 valores de `PYTHONHASHSEED`; resultado
idéntico con y sin desempate explícito por término.

**Dónde gana.** En todo el rango: hereda la poda de A en el caso normal y el techo de la fuerza bruta
en el patológico.

**Dónde falla.** No elimina el coste del peor caso, solo lo **acota**: sigue siendo ~1,3× la fuerza
bruta por el trabajo de decidir. Y **no resuelve ninguno de los defectos D-M-2…D-M-6**, que son
independientes de la generación de candidatos.

**Riesgo de regresión `[EJEC]`.** Batería oficial: recall 0,6604, FP puros 0, FP críticos 2 —
**idénticos a hoy**, 0 discrepancias en las 77 consultas. La migración no arrastra regresión medible.

---

### B — Unión completa (eliminar el corte)

**Algoritmo.** Unir los posteos de todos los términos.

**Exactitud.** Por construcción.

**Coste** `O(n log n + P + |C|·n)` `[INFER]`; medido: **758 080 posteos frente a 120 349** de A en el
mismo banco, es decir **6,3× más posteos** `[EJEC]`. *(No mido su latencia por separado: el 5,6× de
tiempo citado en A es el de la **fuerza bruta**, que recorre los N recuerdos y no es lo mismo que la
unión completa de posteos. Atribuirle esa cifra a B sería impreciso.)*

**Dónde gana.** Simplicidad: elimina un `continue`. Es la implementación más difícil de equivocar.

**Dónde falla.** **Revierte MA.2a**, una garantía aprobada. Cambiar una garantía para arreglar otra es
el intercambio que el proyecto decidió no hacer a ciegas.

**Veredicto: descartada como solución, imprescindible como oráculo.** Debe existir en las pruebas como
referencia de verdad contra la que se contrasta A′.

---

### C — Completado adaptativo

**Algoritmo.** Mantener el corte y, si «faltan resultados» (menos de `k`), rehacer con unión completa.

**Contraejemplo `[EJEC]`.** De las 39 consultas en que el algoritmo vigente falla, **36 (92 %) ya
devolvían `k = 3` resultados**. El disparador no se activaría. Para detectar el resto haría falta saber
si existe un candidato mejor entre los no examinados — que es exactamente la pregunta que el corte
impide responder. **Circular.**

**Veredicto: refutada con datos.** Riesgo adicional: daría sensación de resolución dejando el defecto
vivo en 9 de cada 10 casos.

---

### D — WAND / recorrido por documento con umbral

**Algoritmo.** Estándar de recuperación de información para top-k: cursores sobre listas ordenadas,
cotas superiores por término, salto de bloques que no pueden superar el umbral.

**Coste `[HIPO]`.** `O(P)` peor caso, típicamente sublineal — **según la literatura, no medido aquí**.

**Dónde gana.** Escala mejor que A′ con `n` grande y corpus de órdenes de magnitud mayores.

**Dónde falla.** Complejidad muy superior (cursores, punteros de salto, invariantes de cota), con su
propio determinismo que auditar y un cambio estructural del índice. **Desproporcionado:** resuelve a
escala de millones un defecto que aparece a escala de cientos, y A′ ya lo elimina por completo.

**Veredicto: descartada por desproporción, no por incorrección.** Es el camino natural si la memoria
crece órdenes de magnitud.

---

### E — Umbral ubicuo relativo al corpus

Convertir el 256 fijo en un porcentaje de `N`. **No resuelve nada:** desplaza la frontera sin eliminar
el régimen defectuoso, y lo hace **más difícil de probar** porque el umbral deja de ser un número fijo
que una prueba pueda ejercitar. Mantiene el defecto y le quita el punto de apoyo para detectarlo.
**Veredicto: descartada.**

---

## 5 · Ataque a la alternativa favorita

Sometí A al mismo tratamiento que hundió V7. **Un ataque de los cinco tuvo éxito y cambió la
recomendación.**

| # | Ataque | Resultado |
|---|---|---|
| 1 | **Rendimiento en el peor caso.** ¿Puede el prefijo ser más caro que mirarlo todo? | **ÉXITO DEL ATAQUE** `[EJEC]`. Con todos los términos ubicuos, A visita hasta 12 000 posteos frente a 3 000 recuerdos y es **hasta 2,15× más lento que la fuerza bruta**. Motivó A′ |
| 2 | **Exactitud fuera del umbral elegido.** ¿Sigue siendo exacto si cambia `c`? | Resistido `[EJEC]`. 18 000 corpus aleatorios en 6 valores de `c`: 0 discrepancias |
| 3 | **Términos inexistentes.** Ocupan huecos del prefijo sin aportar candidatos: ¿rompe el palomar? | Resistido `[EJEC]`. Los cuatro casos coinciden con fuerza bruta. El argumento se sostiene: si `n − inexistentes < m`, ningún recuerdo puede cualificar y devolver `[]` es **correcto** |
| 4 | **Determinismo bajo empates** de longitud de posteo | Resistido `[EJEC]`. Resultado idéntico con y sin desempate explícito, y 1 sola huella entre 5 semillas. Solo el **coste** puede variar, por eso conviene fijar el desempate |
| 5 | **Regresión sobre la batería.** ¿Afloran FP que el defecto ocultaba? | Resistido `[EJEC]` **en la batería**: 0/77 discrepancias, métricas idénticas. **Pero sigue siendo `[HIPO]` fuera de ella** — ver §7 |

**Autocrítica sobre el propio ataque.** El ataque 1 se ejecutó primero con caché fría y arrojó «2,7×».
Repetido con calentamiento y mediana de 25 repeticiones, el valor real es **2,15×**. La cifra publicada
es la segunda; la primera era ruido de medición y la retiro.

**Lo que el ataque NO cubre, dicho explícitamente.** El peor caso lo construí yo. No he demostrado que
sea el peor posible — solo que es peor que los que probé. Un patrón de consulta adversarial distinto
podría empeorarlo; la cota de A′ lo acota igualmente, y ese es el motivo de preferirla.

---

## 6 · Matriz comparativa

| Criterio | **A′ prefijo+cota** | A prefijo | B unión completa | C adaptativo | D WAND |
|---|---|---|---|---|---|
| **Corrección vs fuerza bruta** | Exacta (demostrada + 18 000 casos) | Exacta | Exacta | **No** — 92 % de fallos sin detectar | Exacta `[HIPO]` |
| **Rendimiento (caso normal)** | ≈1 ms · 15,9 % de posteos | ≈1 ms | 6,3× más posteos | ≈ igual que hoy | Mejor con `n` grande `[HIPO]` |
| **Rendimiento (peor caso)** | **Acotado por fuerza bruta** | **Hasta 2,15× peor** | Es el techo | Es el actual | `[HIPO]` |
| **Determinismo** | 1 huella / 5 semillas | 1 huella | Sí | Sí | Sin verificar |
| **Complejidad de código** | Baja (una guarda extra) | Baja | Mínima | Media | **Alta** |
| **Impacto arquitectónico** | Nulo — una función | Nulo | Nulo | Nulo | **Estructural** (índice nuevo) |
| **ADR-0014** | Lo refuerza | Lo refuerza | Lo refuerza | Lo deja roto | Lo refuerza |
| **MA.2a** | **Respetada** | **Comprometida en el peor caso** | **Revertida** | Respetada | Respetada |
| **Riesgo de regresión** | Nulo medible (0/77) | Nulo medible | Rompería pruebas de rendimiento | — | Alto |
| **Veredicto** | **RECOMENDADA** | Sustituida por A′ | Oráculo de pruebas | Refutada | Aplazada |

---

## 7 · Qué tendría que demostrarse para cambiar esta decisión

Condiciones concretas y falsables. Si alguna se cumple, la recomendación decae:

1. **Un contraejemplo de exactitud de A′.** Un corpus y una consulta donde A′ discrepe de la fuerza
   bruta. Refutaría la demostración del palomar y descartaría A′ por completo. *(18 000 casos no lo
   encontraron; una demostración vale más que el muestreo, y aquí hay ambas.)*
2. **Que el peor caso sea el caso normal.** Si la telemetría mostrara que una fracción apreciable de
   consultas reales activa la cota, A′ degeneraría en B y habría que ir a **D (WAND)**. Umbral
   sugerido: **>5 % de consultas con la cota activada**. Hoy es 0/400 en el banco sintético — y **cero
   en uso real, porque nadie ha usado AURA todavía**.
3. **Que afloren falsos positivos críticos nuevos.** Es el riesgo declarado: A′ examina recuerdos que
   el defecto ocultaba. Sobre la batería no aparece ninguno, pero **la batería no ejercita el régimen
   ubicuo**. Si al ampliarla aparecen FP críticos, la respuesta correcta **no** es volver al corte
   —eso preferiría un sistema que miente por omisión a uno que se equivoca a la vista— sino tratarlos
   en el criterio de cobertura, que es donde viven.
4. **Que el corpus crezca órdenes de magnitud.** Con memoria de millones de entradas, la ventaja de D
   dejaría de ser teórica. Disparador: `N > 10⁵` por usuario.
5. **Que `_COBERTURA_MINIMA` baje mucho.** `[EJEC]` con `c = 0,20` el prefijo une el 100 % de las
   listas y degenera en B. Por debajo de `c ≈ 0,4` la poda deja de compensar y habría que revisar la
   elección.
6. **Que la cota resulte mal calibrada.** `α = 1` es una elección conservadora dentro de un rango útil
   medido de `[1, 2]`, no un óptimo. Recalibrarla **no cambiaría la decisión** —A′ seguiría siendo la
   alternativa recomendada— solo su parámetro. Disparador: que la cota se active en más del 5 % de las
   consultas reales, o que el coste por posteo y por recuerdo resulten muy distintos.

---

## 8 · Procedencia de las cifras

**`[EJEC]` — medido ejecutando, reproducible.** Todas las cifras de las §1, §2.1–2.3, §2.5, §4 (salvo
las de D) y §5. Prototipos en `$CLAUDE_JOB_DIR/tmp/`: `proto*.py` (comparativas y batería), `atq1..4.py`
(ataques y medición con calentamiento), `barrido.py` (regímenes), `v_*.py` (verificación de D-M-2…6).
Semillas fijas: `20260803` (banco zipfiano) y `31415` (búsqueda de contraejemplos).

**`[INFER]` — deducido, no medido.** Las tres fórmulas de coste asintótico; la desalineación de
`SemanticMemory._vectores` (leída en el código, no ejecutada porque N2 no se materializa aquí).

**`[HIPO]` — no verificado.** El coste de D (WAND), tomado de la literatura. Que los formatos numéricos
causen pérdida real. Que D-M-1 se materialice en uso real. Que A′ no exponga FP nuevos fuera de la
batería.

**Advertencia de método.** Las comparaciones de latencia entre A′ y fuerza bruta usan la caché
`_terminos_item` **en ambas ramas**. La cifra histórica de MA.2a (9,22 ms con 3 000 recuerdos) se midió
**sin** esa caché, así que no es directamente comparable con las de este documento.

---

## 9 · Lo que este DP NO incluye

- **No cambia** `_COBERTURA_MINIMA`, la tokenización, las palabras vacías ni el criterio de aceptación.
- **No resuelve D-M-2…D-M-6.** Son independientes de la generación de candidatos y necesitan sus
  propias decisiones. **D-M-2 es más urgente que D-M-1** y se dispara en el segundo turno: el CEO fijó
  que se resuelve **antes** que este DP (ver encabezado). Su Decision Package es trabajo aparte.
- **No toca** `SemanticMemory` ni `D-N2-5`.
- **No propone** ampliar el alcance funcional del MVP (D23).
- **No implementa** las pruebas de la ampliación del benchmark, que acompañarían a la implementación.
