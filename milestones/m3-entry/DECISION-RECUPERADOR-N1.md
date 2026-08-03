---
documento: "Por qué el recuperador de N1 usa cobertura ≥60% (variante V4)"
fecha: 2026-08-03
autor: "CTO / Director"
estado: "VIGENTE. Decisión respaldada por evidencia experimental reproducible."
base: "Batería oficial: walking-skeleton/tests/datos/bateria_memoria.json"
---

# Decisión del recuperador de N1

Este documento existe **para que la decisión no tenga que redescubrirse**. Si alguien propone cambiar
el recuperador, aquí está lo que ya se midió y por qué se descartó cada alternativa.

## La garantía que estaba en juego

ADR-0014 §Decisión, punto 1 —**intacto, no se modifica**:

> *«Cuando la búsqueda de memoria devuelve cero resultados y el usuario pregunta por un recuerdo, el
> Core responde declarando la ausencia de registro y no se realiza ninguna llamada al LLM.»*

**El código siempre implementó esa condición correctamente.** El problema era que «cero resultados»
casi nunca ocurría: el recuperador emparejaba por palabras vacías y devolvía algo en **~78%** de las
consultas sin respuesta. La garantía no estaba violada; estaba **vacía de contenido**.

> **Nota técnica sobre el alcance de N1.** La implementación N1 **aproxima** esta garantía mediante
> recuperación léxica determinista. Su satisfacción completa queda condicionada a la futura memoria
> semántica (N2).

## Por qué cobertura ≥60%

Comparativa **remedida sobre la batería vigente** (65 recuerdos, 77 consultas, 53 con respuesta
esperada), es decir con los 6 casos adversariales y sus recuerdos de apoyo ya incorporados:

| Umbral | FP puros | FP críticos | Recall@3 |
|---|---|---|---|
| ≥50% | 0 | **9** | 0,717 (38/53) |
| **≥60%** | **0** | **2** | **0,660 (35/53)** |
| ≥67% | 0 | 1 | 0,547 (29/53) |

Con el orden de prioridad fijado por el CEO —**FP puros → FP críticos → recall → coste**—, **0,60 es el
umbral más bajo que deja los FP críticos en el suelo de la frontera de N1**. Los 2 que quedan son los
adversariales «de mi vecino» / «de mi hermano», clasificados *corregibles* y con techo fijado en la
prueba (`_ADVERSARIALES_CONOCIDOS = 2`): no son ruido tolerado, son el límite medido. Bajar a 0,50 los
multiplica por 4,5. Subir a 0,67 elimina uno más, pero cuesta **6 aciertos legítimos** — un intercambio
que el orden de prioridad vigente no justifica.

> **Corrección (verificación de cierre).** Una versión anterior de esta tabla daba «0 / 3 / 0» FP
> críticos y recall 0,712 / 0,654 / 0,558 sobre una batería de 59 recuerdos y 71 consultas. Esas cifras
> quedaron obsoletas al ampliar la batería y **no se habían recomputado**. Las de arriba están medidas
> contra el fichero que hoy vive en el repositorio; el 0,660 coincide con el que reporta la prueba
> oficial. La consulta «¿cuál es la marca de mi coche?» se reclasificó de negativa a positiva: al
> ampliar el corpus, la respuesta pasó a existir.

El valor vive en `_COBERTURA_MINIMA` (`aura_skeleton/modules/memory.py`). **No es un número mágico:** si
aparece una batería mejor, se cambia ahí y la batería vuelve a decidir.

## Por qué se descartó la rama «o solape ≥2» (variante V7)

V7 subía el recall a 0,692 (**+3,8 puntos**). Fue rechazada por **validación adversarial dirigida**:

| | V4 | V7 |
|---|---|---|
| Casos adversariales fallados | **2/6** | **6/6** |
| Aciertos que aporta la 2ª rama | — | **+2 de 52** |

Aceptar por número absoluto de términos, sin mirar la proporción, deja pasar consultas largas sobre
**otra entidad**: *«la marca y el modelo del coche de mi vecino»* contra *«mi coche es de marca Ford»*.
**Cuadruplicaba los falsos positivos críticos para ganar 2 aciertos.**

## Las dos clases de error, y por qué se cuentan por separado

- **FP puro**: no existe ningún recuerdo relacionado. Objetivo **cero**, es criterio de aceptación.
- **FP temático crítico**: recuerdo de **otra entidad** que comparte un atributo genérico (`marca`,
  `color`, `número`, `años`). Induce al LLM a responder un dato **concreto y equivocado**. Objetivo cero.
- **FP temático aceptable**: recuerdo de **la misma entidad** sin el atributo pedido. El LLM recibe
  contexto correcto y dirá «no tengo ese dato». Se informa, no bloquea.

## La frontera de N1 — dónde está y dónde ya no está

**Ya no está en la tokenización.** Está en **distinguir si un atributo pertenece a la entidad
preguntada**: *«¿de qué color son mis ojos?»* frente a *«mi gato es de color negro»* comparte `color`,
y solo el significado los separa.

Se evaluaron seis familias léxicas —rareza/IDF, cobertura, tokenización estructurada, índices
invertidos, campos/atributos, filtros por tipo— y **todas desplazan la frontera; ninguna la elimina**.
Cada mecanismo resuelve el contraejemplo del anterior y genera uno nuevo.

**Es una demostración por agotamiento de las familias evaluadas, no una prueba de imposibilidad.** Si
aparece una técnica léxica nueva, esta conclusión debe reexaminarse — pero **con el benchmark**, no con
ejemplos aislados.

## Límite descubierto en la verificación final (2026-08-03)

**Consultas de UN solo término informativo.** Con un único término, *cualquier* recuerdo que lo contenga
alcanza el 100% de cobertura, así que el criterio no discrimina:

```
Corpus  : "Mi numero de telefono es 555-2938."
          "Perdi mi telefono en el taxi el martes por la noche."
Consulta: "¿cual es mi telefono?"   ->  devuelve LOS DOS
```

**Clasificación: aceptable, no crítico.** Ambos recuerdos son de la **misma entidad** (mi teléfono) y el
correcto se devuelve primero, así que el LLM dispone del dato bueno. No induce a responder un dato
equivocado de otra entidad, que es lo que define un FP crítico.

Se documenta porque es **estructural**: la cobertura es una fracción, y con denominador 1 solo puede
valer 0 o 1. Ninguna variante léxica lo resuelve — hace falta discriminar por relevancia semántica, es
decir, N2. Está incorporado a la batería para que no se olvide.

## Clasificación de los 6 casos adversariales

| Clase | N.º | Qué significa |
|---|---|---|
| `corregible` | **2** | El discriminante es un **poseedor** (`de mi vecino`, `de mi hermano`) que la consulta menciona y el recuerdo no. **Admite mejora léxica futura** (detección del patrón `de mi <X>`); no requiere semántica. V4 los falla hoy: es el techo documentado |
| `frontera_n1` | **4** | V4 ya los rechaza correctamente. Su función es **impedir que una variante futura los reintroduzca** — la descartada V7 fallaba los seis |

## Garantías que el Quality Gate hace cumplir

`tests/integration/test_bateria_memoria.py` falla si: reaparece un **FP puro**; aumentan los **FP
críticos** de referencia; se supera el **techo de 2** en adversariales; el recall baja de **0,63**; o
se pierde el **determinismo entre procesos** (verificado con 5 semillas de hash distintas).
