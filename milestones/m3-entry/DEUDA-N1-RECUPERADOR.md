# Deuda registrada — Recuperador léxico N1 (cobertura de consulta)

**Origen:** auditoría independiente + ataques propios durante la **verificación de cierre** del
incremento «restauración de la garantía de ADR-0014» (2026-08-03).
**Estado:** registrada. **Ninguna de estas entradas fue introducida por el incremento**; todas son
límites heredados o preexistentes que la verificación sacó a la luz.

**Criterio del CEO para registrar deuda:** solo se registra lo que bloquea un incremento, compromete la
arquitectura, compromete la seguridad o **puede producir pérdida de información**. Lo demás vive como
observación técnica.

---

## D-M-1 · Un recuerdo válido puede volverse irrecuperable en corpus grande

**Clasificación: DEUDA** — cumple el criterio «puede producir pérdida de información». El dato **no se
pierde del disco** (el JSONL es append-only e íntegro), pero se vuelve **inalcanzable por consulta**,
que desde el punto de vista del usuario es indistinguible de haberlo perdido.

### Qué ocurre

La generación de candidatos (`PersistentMemory.recall`) recorre los términos de la consulta de posteo
más corto a más largo y **salta** los que superan `_UMBRAL_UBICUO` (256) en cuanto ya hay algún
candidato. Ese salto es la garantía de rendimiento MA.2a: evita recorrer listas de posteo enormes.

La consecuencia no documentada: **si un recuerdo comparte con la consulta únicamente términos ubicuos,
nunca entra en el conjunto de candidatos**, aunque su cobertura supere el umbral. No es que se
descarte por puntuación baja: es que nunca llega a puntuarse.

### Contraejemplo reproducible (verificado, **corregido 2026-08-03**)

```
corpus:    300 recuerdos con "trabajo" pero SIN "reunion"   → posteo trabajo = 301 > 256
           300 recuerdos con "reunion" pero SIN "trabajo"   → posteo reunion = 301 > 256
           + objetivo:   "Mi trabajo tiene una reunion importante"  → cobertura 2/3 = 0,67 ≥ 0,60
           + distractor: "Nota xyzterm sin relacion"                → cobertura 1/3, no cualifica
consulta:  "trabajo reunion xyzterm"

recuerdos que alcanzan la cobertura, por fuerza bruta: exactamente 1 (el objetivo)
resultado real del recuperador                       : []
```

Traza: `xyzterm` (posteo 1) entra primero y siembra `candidatos`; `trabajo` y `reunion` se saltan por
ubicuos; el objetivo no está en `candidatos`; el distractor sí, pero su cobertura es 1/3 y no pasa.

> **Por qué se corrigió este contraejemplo.** La primera versión usaba 300 rellenos que contenían
> **ambos** términos, igual que el objetivo. Demostraba el síntoma —el objetivo no se recupera— pero
> **no aislaba la causa**: los rellenos empataban en cobertura y el `top-k` habría enterrado el
> objetivo aunque el conjunto de candidatos fuese correcto. Verificado: con barrido completo tampoco
> se recuperaba. La versión de arriba deja **un solo** recuerdo cualificado, así que el fallo solo
> puede atribuirse a la generación de candidatos.

### Magnitud medida

Sobre corpus sintético de **3 000 recuerdos** con vocabulario zipfiano y 400 consultas aleatorias con
semilla fija, contrastadas contra barrido completo por fuerza bruta:

> **El algoritmo vigente devuelve un resultado distinto del correcto en el 9,8 % de las consultas
> (39 de 400).** De esos 39 fallos, **36 (92 %) ya devolvían 3 resultados**: completos y equivocados.

La segunda cifra importa porque descarta la mitigación intuitiva («completar solo si faltan
resultados»): no se activaría en la gran mayoría de los fallos.

### Por qué NO es una regresión de este incremento

Verificado ejecutando el algoritmo **anterior** (solape ≥1 término) sobre el mismo corpus:

| Algoritmo | Devuelve | ¿Incluye el recuerdo objetivo? |
|---|---|---|
| Anterior (solape ≥1) | `["Nota xyzterm sin relacion"]` | **No** |
| Actual (cobertura ≥0,60) | `[]` | **No** |

El objetivo se pierde **en ambos**. El defecto vive en la generación de candidatos de MA.2a, no en el
criterio de aceptación. Lo que el incremento cambió es **qué sale en su lugar**: antes un falso
positivo, ahora nada — que es el comportamiento honesto según ADR-0014, aunque el recuerdo siga
siendo irrecuperable.

### Por qué no se corrigió en este incremento

El CEO acotó el incremento a *«estrictamente restauración de una garantía, no mejora del algoritmo»*.
Tocar el salto de ubicuos es modificar el algoritmo de recuperación **y** una garantía de rendimiento
ya aprobada (MA.2a). Corresponde a su propio Decision Package.

### Condición de disparo y riesgo hoy

Requiere **más de 256 recuerdos de un mismo usuario compartiendo un término**. Hoy es inalcanzable en
la práctica y la batería oficial **no puede** ejercitarlo (65 recuerdos). Se vuelve alcanzable con
historial real acumulado: términos como «trabajo», «casa» o «hijo» superarían 256 apariciones en un
usuario activo durante meses. **El riesgo crece con el tiempo de uso**, que es exactamente el
escenario que AURA promete servir.

### Qué haría falta

**Propuesta analizada en `DP-D-M-1-RECUPERACION-EXACTA.md`** (pendiente de aprobación del CEO). En
resumen: unir las `n − m + 1` listas de posteo más cortas, donde `m` es el número de términos que un
recuerdo necesita para alcanzar la cobertura. Por el principio del palomar, todo recuerdo cualificado
aparece forzosamente en alguna de ellas — es exacto, no heurístico. Medido: 0 discrepancias frente a
fuerza bruta en 400 consultas, ~1 ms por consulta con 3 000 recuerdos, y MA.2a se preserva.

Queda descartada la mitigación que parecía obvia (completar solo si faltan resultados): no detectaría
el 92 % de los fallos.

### Afirmaciones corregidas a raíz de este hallazgo

`memory.py` declaraba que el resultado del índice era **«idéntico»** al del barrido completo y que eso
estaba **«verificado»**. La verificación existía, pero solo cubría el régimen por debajo de
`_UMBRAL_UBICUO` — el único que la batería puede ejercitar. La afirmación se acotó a su alcance real.

---

## Observaciones técnicas (NO son backlog)

| Observación | Por qué NO es deuda hoy | Se promueve a deuda si… |
|---|---|---|
| **`recall(..., k=-1)` devuelve casi todos los recuerdos** en vez de fallar o no limitar (el slice `[:k]` con `k` negativo recorta por la cola). Preexistente, ya en `SimpleMemory`. | Ningún llamador pasa `k` negativo: el orquestador usa el valor por defecto. No hay ruta que lo alcance. | Se exponga `k` a entrada del usuario o a configuración externa. |
| **`SemanticMemory` construye el índice léxico de `PersistentMemory` en cada escritura y nunca lo usa** (su `recall` barre por coseno). | Ineficiencia, no defecto: no altera resultados. Con N2 inactiva no se ejecuta. | N2 se active y el coste de indexado resulte medible. |
| **`test_el_recall_sigue_siendo_correcto_con_volumen` no ejercita el escenario que su nombre sugiere**: su recuerdo-aguja tiene términos exclusivos, así que pasa incluso con D-M-1 activo. | No es decorativa —sí detecta rotura del índice y del orden—, pero **no** es un control de D-M-1. | Se pretenda usarla como evidencia de corrección a volumen. |
