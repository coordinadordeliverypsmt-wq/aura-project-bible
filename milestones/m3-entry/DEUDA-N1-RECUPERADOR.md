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

### Condición de disparo y riesgo hoy — **corregido a la baja el 2026-08-03**

Requiere **más de 256 recuerdos de un mismo usuario compartiendo un término**. Una versión anterior de
este documento decía que eso tardaría **meses**. Es falso, y por un motivo que no había mirado:

`orchestrator.py:636` escribe `usuario dijo: {text}` en **cada turno**, y `_terminos("usuario dijo:
…")` produce `{usuario, dijo}` — **ninguno de los dos está en la lista de palabras vacías**. Medido:
tras 300 turnos, `posteo('dijo') = 300` y `posteo('usuario') = 300`. **El umbral se cruza en el turno
257**, es decir en unos **5 días** con las ~50 vueltas/día que asume la prueba de escalabilidad.

**Matiz honesto, para no exagerar el riesgo:** entrar en el régimen **no basta** para perder un
recuerdo. Hace falta además que el solape con la consulta sea *solo* de términos ubicuos, y nadie
escribe «usuario dijo» en una pregunta. Verificado: con 301 recuerdos con ese prefijo y la consulta
«¿qué me dijo el médico del colesterol?», el recuerdo objetivo **sí** se recupera — lo salvan `medico`
y `colesterol`. La pérdida sigue exigiendo una **palabra de contenido** por encima de 256 apariciones.
Lo que cambia no es la probabilidad del fallo, sino **la fecha en que el régimen deja de ser
hipotético**.

La batería oficial **no puede** ejercitarlo por construcción (65 recuerdos, posteo máximo medido: 7).

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

---

## D-M-2 · El eco del propio turno desactiva ADR-0014 *(más grave que D-M-1)*

**Clasificación: DEUDA CRÍTICA** — compromete la **arquitectura** (viola una regla no negociable) y la
**veracidad**. Hallada por el barrido de regímenes no cubiertos del 2026-08-03.

`orchestrator.py:636` (`_finalizar_turno`) escribe `usuario dijo: {text}` en **todas** las rutas del
turno — **incluida la propia rama de ADR-0014**, que lo llama justo antes de retornar (línea 373).
Consecuencia: la pregunta del usuario queda almacenada como recuerdo, y **cubre su propia repetición
con cobertura 1,00**.

Verificado:

```
turno 1 · "¿Recuerdas cual es el nombre de mi abuela?"  → hits=0 → ADR-0014 ACTIVA
          (y sin embargo se escribe: "usuario dijo: ¿Recuerdas cual es el nombre de mi abuela?")
turno 2 · misma pregunta                                → hits=1 → ADR-0014 DESACTIVADA
          recuperado, cobertura 1.00: "usuario dijo: ¿Recuerdas cual es el nombre de mi abuela?"
```

**Lo que el LLM recibe como «contexto de memoria» es la propia pregunta del usuario.** La garantía que
existe para impedir que el modelo fabrique lo inexistente se apaga sola, y lo hace justo en el caso
que ADR-0014 fue escrito para cubrir: preguntar por algo que no existe.

**Condición de disparo: repetir cualquier pregunta una segunda vez.** No requiere volumen, ni tiempo,
ni corpus grande. Es el fallo más alcanzable de esta lista y el único que toca una regla no negociable.

Ninguna prueba lo detecta: la batería tiene **0 de 65** recuerdos con forma de pregunta y **0** con el
prefijo `usuario dijo:`, y ninguna prueba repite una consulta dos veces.

---

## D-M-3 · Una coletilla de cortesía derrumba el recall

**Clasificación: DEUDA** — «puede producir pérdida de información»: el recuerdo existe y se vuelve
inalcanzable por hablar con naturalidad.

La cobertura se normaliza por el número de términos de **la consulta**, así que cada palabra de más
sube el listón. Medido sobre la batería oficial, añadiendo un prefijo a las mismas 53 consultas:

| Prefijo | Términos extra | recall@3 |
|---|---|---|
| *(ninguno)* | 0 | **0,660** |
| «por favor» | 1 | **0,340** |
| «oye AURA por favor dime» | 3 | **0,000** |
| «oye AURA una cosa que quería preguntarte» | 5 | **0,000** |

No es ruido estadístico, es aritmética: `⌈0,6·n⌉` salta de 1→2, 2→3, 3→4 al añadir un término, y el
solape máximo observado en el corpus es 3. **Ninguna consulta de ≥6 términos informativos puede
alcanzar el umbral contra este corpus.** El orquestador pasa el texto **crudo** a `recall`, y «oye»,
«por favor» o «una cosa» no están en la lista de palabras vacías.

La batería no lo detecta porque su consulta más larga tiene **5** términos informativos: está
calibrada justo en el borde del régimen donde el algoritmo funciona.

---

## D-M-4 · Un recuerdo largo se convierte en atractor universal de falsos positivos críticos

**Clasificación: DEUDA** — compromete la **veracidad**: induce al LLM a responder un dato concreto y
equivocado, que es la definición de FP crítico que usa la propia batería.

La cobertura normaliza **solo por la longitud de la consulta**, nunca por la del recuerdo. Un recuerdo
largo contiene muchos términos, así que cubre casi cualquier consulta corta. Verificado con un turno
episódico real de 36 términos: consultas sobre entidades que el recuerdo solo menciona de pasada
(«¿qué coche tiene mi madre?», «¿cuál es el teléfono de la oficina?») lo recuperan como respuesta.

Alcanzable en cuanto el usuario dicte un turno largo: el orquestador lo almacena íntegro y verbatim.
El corpus de la batería tiene un máximo de **7 términos informativos** por recuerdo, así que este
régimen no existe en las pruebas.

---

## D-M-5 · Un recuerdo refutado sigue entrando en el prompt del LLM

**Clasificación: DEUDA** — compromete la **veracidad** y la **soberanía del usuario** (ADR-0017).

`recall` no consulta `provenance` en ningún punto. El filtro de refutados vive **solo en la capa de
presentación** (`modelo_usuario.py:135`, `orchestrator.py:408`). Verificado:

```
antes de refutar  → 1 hit
marcar(refutada)  → 1 marcado
después           → sigue devolviendo 'suele pagar las facturas por la app'  {'refutada': True}
```

El usuario ve su modelo limpio con `ver()` y cree que AURA dejó de afirmarlo, mientras el dato
refutado sigue alimentando el prompt en el turno siguiente. Es exactamente la promesa que
`modelo_usuario.py:15` declara cumplir.

---

## D-M-6 · Al corregir un dato, gana el más antiguo

**Clasificación: DEUDA** — «puede producir pérdida de información»: la corrección se vuelve
inalcanzable.

El desempate a igual cobertura es `(-cobertura, índice)`, y el índice menor es el recuerdo **más
antiguo**. Verificado con `k=1`: entre «Mi color favorito es el azul» y «Ahora mi color favorito es el
verde», devuelve **el azul**. Con repeticiones episódicas del dato viejo, la corrección cae fuera del
top-3.

La batería **no puede** contener este caso: `test_bateria_memoria.py` **prohíbe** contenidos duplicados
(`assert len(mapa) == len(corpus)`), de modo que el corpus no admite versiones sucesivas de un hecho.
Corregir un dato es un caso de uso explícito de `ModeloUsuario`.

---

## Observaciones técnicas (NO son backlog)

| Observación | Por qué NO es deuda hoy | Se promueve a deuda si… |
|---|---|---|
| **`recall(..., k=-1)` devuelve casi todos los recuerdos** en vez de fallar o no limitar (el slice `[:k]` con `k` negativo recorta por la cola). Preexistente, ya en `SimpleMemory`. | Verificado que producción usa **siempre** el `k=3` por defecto (`orchestrator.py:363`, sin argumento). No hay ruta que lo alcance. | Se exponga `k` a entrada del usuario o a configuración externa. |
| **`PersistentMemory` no tiene ninguna prueba de aislamiento entre `user_id`.** La que existe (`test_memory.py:28`) cubre solo `SimpleMemory`; el corpus de la batería es 65/65 `u1`. | Verificado que **hoy funciona**: el índice se clava en `(user_id, término)` y `recall("u2", …)` devuelve `[]`. Es una ruta correcta, pero sin red. | Nunca: conviene añadir la guardia igualmente al ampliar la batería (coste bajo, protege un límite de privacidad). |
| **Formatos numéricos divergentes**: `_terminos` usa `\w+`, así que `600123456`, `600 12 34 56` y `600-123-456` producen tokens distintos. Solo 1 de 77 consultas de la batería lleva dígitos. | Falla **hacia el silencio** (pérdida de recall), no hacia la fabricación. Con ADR-0014 el sistema declara ausencia en vez de inventar. | Se detecte en uso real, o se decida normalizar números como parte de un incremento de tokenización. |
| **`SemanticMemory` construye el índice léxico de `PersistentMemory` en cada escritura y nunca lo usa** (su `recall` barre por coseno). | Ineficiencia, no defecto: no altera resultados. Con N2 inactiva no se ejecuta. | N2 se active y el coste de indexado resulte medible. |
| **`test_el_recall_sigue_siendo_correcto_con_volumen` no ejercita el escenario que su nombre sugiere**: su recuerdo-aguja tiene términos exclusivos, así que pasa incluso con D-M-1 activo. | No es decorativa —sí detecta rotura del índice y del orden—, pero **no** es un control de D-M-1. | Se pretenda usarla como evidencia de corrección a volumen. |
