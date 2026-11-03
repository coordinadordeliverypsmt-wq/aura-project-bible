---
documento: "AMP-AURA — Propuesta de Protocolo de Memoria de AURA"
tipo: "PROPUESTA ARQUITECTÓNICA. NO implementada. NO aprobada. NO es un ADR."
fecha: 2026-09-10
checkpoint: 5ebdce4
decide: "CEO (Mauricio)"
autor: "APUS-5 (CTO)"
investigacion: "AURA-MEMORY-PROTOCOL-COMPARISON.md"
---

# AMP-AURA · Protocolo de Memoria de AURA

**Nada de este documento está implementado.** No modifica Bible, ADR, contratos ni código. Es la pieza que el CEO
necesita para decidir **si** AURA adopta un protocolo de memoria y **qué partes** se construirían.

`[LECT]` leído en el código · `[EJEC]` medido · `[INFER]` deducido · `[HIPO]` no verificado.

---

## 1 · Resumen ejecutivo

AURA **ya tiene memoria gobernada**, pero **no tiene protocolo**. Tiene clases de señal, procedencia, autoridad del
Core, motor único, auditoría, protección de terceros y resolución determinista sin LLM `[LECT]`. Lo que no tiene es
un **contrato explícito de operaciones, identidad, versión y vigencia** que agentes futuros puedan usar sin
inventarse una segunda ruta.

La investigación externa arroja tres cosas: **no existe estándar** al que adherirse; **ningún protocolo resuelve
evidencia-vs-hecho ni la contradicción**; y la literatura de 2026 **respalda empíricamente** que el LLM no sea
autoridad de memoria —el envenenamiento necesita **una sola escritura** y el 89 % de las recuperaciones envenenadas
deriva en acciones del atacante.

**La propuesta es deliberadamente pequeña:** tomar de UMP el vocabulario y la forma de record, conservar intacto el
mecanismo determinista que AURA ya demostró, y añadir las cuatro cosas que hoy faltan: **identidad de hecho,
versión, vigencia y frontera de contexto**.

## 2 · Qué existe realmente (resumen; detalle en el documento de comparación)

| | Estado real |
|---|---|
| Estándar de memoria de agentes | **Ninguno.** W3C solo tiene un *Community Group* que no produce Recommendations; SAIHM es un Internet-Draft **sin standing en el IETF** |
| UMP | Propuesta con spec pública: 9 campos, 6+2 operaciones, niveles L1–L3, storage-agnóstico, ficheros portables |
| AMP (YouTale) | v0.1 draft: markdown + frontmatter + wiki-links (**el modelo Obsidian**) |
| SAIHM | Anclaje en cadena pública y claves de wallet → **incompatible con `D24`/`ADR-0001`** |
| Letta/MemGPT | Implementación y patrón; **el agente edita su propia memoria** |
| «OAMP» | **No existe.** Es `OpAMP`, de gestión de telemetría |

## 3 · Hallazgos

**H-1 · La autoridad centralizada no es una preferencia estética: es una defensa medida.** El envenenamiento de
memoria requiere **una escritura**, frente al prompt injection que necesita el payload en cada contexto. MemoryGraft
logra que **documentación** aparentemente benigna se persista como «experiencia exitosa».

**H-2 · El problema real es el olvido, no la recuperación.** En 385 casos adversariales, «los fallos de producción
son predominantemente fallos de olvido»; los primitivos deterministas dan **0 % en multilingüe** y **5 %** con
identificadores ofuscados, mientras un hook en tiempo de mutación alcanza **91,7–93,2 %**.
**Consecuencia para AURA:** la parte floja de AMP-AURA no será leer, será **invalidar**.

**H-3 · AURA ya gana en lo que los protocolos no miden.** «¿Cuál es mi cumpleaños?» se responde en **0,00 s con
`provider=core` y 0 llamadas al LLM** `[EJEC]`. UMP **no estandariza la recuperación**; Letta la resuelve con *tool
calls* o vectorial. El *deterministic lookup* es ventaja propia y **no se negocia**.

**H-4 · El hueco de AURA está en cuatro campos.** Verificado en el código: la procedencia persistida es
`{trace_id, fuente, clase, origen, ts}` y **no existen `version`, `valid_from`, `valid_until` ni `confidence`**
`[LECT]`. Tampoco hay identidad de hecho: la resolución empareja **texto** (`_atributo_declarado`), no un atributo
canónico.

**H-5 · La contaminación medida no es de memoria, es de contexto.** Con «Mi abuela es enfermera», el Core **no** la
convierte en hecho personal —la protección funciona—, pero el turno queda como episódico y el modelo la repite
`[EJEC]`. En otra medición, ante «¿Quién fue Jesús Cristo?» el modelo respondió mezclando hechos del contexto
(«mi nombre era María») `[EJEC]`. **Es un problema de *context bounding*, no de *retrieval*.**

## 4 · La hipótesis central: validada, con una corrección

> **MEMORY CORE = única autoridad de memoria.**

**Validada** por H-1 y H-3, y por lo que el propio código ya impone: toda escritura pasa por el motor único
(`ALERTA-005`), `ModeloUsuario` **sin motor no muta** `[LECT]`, y el Core responde los hechos sin consultar al
modelo.

**La corrección, que es importante:** «única autoridad» **no puede significar «único mecanismo»**. H-2 demuestra que
el determinismo puro falla en canonicalización. La formulación defendible es:

> El Core es la única autoridad que **decide** qué es un hecho. Puede **consultar** mecanismos no deterministas
> (embeddings, o incluso el LLM) como **asesores para proponer**, nunca para establecer. Un asesor produce
> `PROPOSED`; solo el Core produce `ACTIVE`.

Y los cuatro corolarios se sostienen sin matiz: **el LLM no es autoridad · el contexto no es memoria · la evidencia
no es automáticamente un hecho · el backend no es memoria.**

## 5 · Modelo conceptual

Los cuatro conceptos del encargo son **necesarios pero insuficientes**. Propongo cinco, y explico el que añado.

| Concepto | Qué es | Persiste | Lo ve el LLM |
|---|---|---|---|
| **CONTEXT** | Lo que se usa durante un turno: buffer de diálogo, hits del recall, prompt | No | Sí, y es el único que ve por defecto |
| **EVIDENCE** | Lo observado, declarado o recibido. Ya existe como `ClaseSenal` con `origen: declarada\|observada` | Sí, como evidencia | Solo si el *Context Builder* lo autoriza |
| **PROPOSAL** | **(AÑADIDO)** Una evidencia que un mecanismo no determinista sugiere elevar a hecho | Sí | **No** |
| **FACT** | Lo que el Core considera establecido: identidad, valor, versión, vigencia, procedencia | Sí | Solo el valor exacto, nunca para reescribirlo |
| **MEMORY** | El conjunto gobernado de los anteriores más su historial y auditoría | Sí | Nunca en bruto |

**Por qué `PROPOSAL` y no cuatro conceptos:** sin él, cualquier mecanismo que quiera mejorar la canonicalización
(H-2) tendría que escribir evidencia *o* hecho. Escribir hecho es la puerta del envenenamiento (H-1); escribir
evidencia confunde «lo que pasó» con «lo que alguien cree que significa». `PROPOSAL` es el lugar donde un asesor
puede equivocarse sin consecuencias.

## 6 · Tipos de memoria

Solo los que AURA puede justificar hoy. **No adopto la taxonomía académica completa.**

| Tipo | Ya existe | Autoridad | Recuperación | Justificación para conservarlo |
|---|---|---|---|---|
| **semántica** (hechos) | `kind: semantica` | Core | **determinista por atributo** | Es el caso que ya funciona en 0,00 s |
| **procedimental** | `kind: procedimental` | Core | estructurada | Ya distinguida por `tipo_de_memoria` |
| **episódica** | `kind: episodica` | Core | por solapamiento | Es la fuente de la contaminación de H-5: debe existir pero **acotada** |
| **histórica no recuperable** | `HISTORICO` + `KINDS_NO_RECUPERABLES` | Core | **nunca por `recall`** | Invento propio de AURA, ya aprobado y probado |
| **preferencias** | `PREFERENCIA_DECLARADA` | Core | por lista positiva | El acta de 2026-08-09 la separa de los hechos |
| **working/context** | buffer de diálogo | **ninguna** (no es memoria) | — | Debe quedar **explícitamente fuera** del protocolo |

**Rechazo por ahora:** *prospective memory* (recordatorios) se solapa con las automatizaciones ya existentes;
*social/relationship memory* es precisamente el terreno de terceros, y abrirla como categoría antes de resolver el
*scope* sería invertir el orden. `[INFER]`

## 7 · Ciclo de vida

El flujo propuesto en el encargo es **casi correcto**; sobra un estado y falta una condición.

```
OBSERVED ──► EVIDENCE ──► [PROPOSED] ──► ACTIVE ──► SUPERSEDED ──► ARCHIVED
                              │            │
                              └── REJECTED └──► INVALIDATED
```

**Qué cambio y por qué:**
- **`VALIDATED` se fusiona con `ACTIVE`.** Dos estados para «el Core lo aceptó» es estado muerto: nada puede estar
  validado y no activo sin una razón que nadie ha nombrado.
- **`PROPOSED` es opcional** (corchetes): una declaración directa del usuario va de `EVIDENCE` a `ACTIVE` sin pasar
  por proposición. Es lo que ya ocurre hoy y funciona.
- **`REJECTED` se añade:** una propuesta descartada debe dejar rastro, o el mismo asesor la repetirá.

| Transición | Quién puede | Evidencia exigida | ¿HITL? |
|---|---|---|---|
| → EVIDENCE | conector de conversación, observación | el enunciado y su procedencia | no |
| EVIDENCE → ACTIVE | **solo el Core**, por construcción declarativa reconocida | declaración directa del usuario | no |
| EVIDENCE → PROPOSED | asesor (embeddings, LLM, agente) | la evidencia + el motivo | no |
| PROPOSED → ACTIVE | **solo el Core** | regla determinista, **nunca** la confianza del asesor | **sí**, si el atributo es sensible |
| ACTIVE → SUPERSEDED | **solo el Core**, por nueva declaración del usuario | la declaración posterior | no |
| ACTIVE → INVALIDATED | usuario (`refutar`/`olvidar`) o Core | petición explícita | **sí** para borrado (lista roja, `ADR-0003`) |
| cualquiera → ARCHIVED | Core | política de retención | no |

**Recuperar una versión anterior** no es una transición nueva: es leer el historial y crear una versión nueva que
supersede a la actual. Nunca se «revive» una versión; se declara otra vez. `[INFER]`

## 8 · Autoridad y procedencia

```
registro = {
  id, subject, attribute, scope, type,      # identidad (§10)
  value,                                     # el valor LITERAL del usuario
  status, version, supersedes,               # ciclo de vida
  valid_from, valid_until,                   # vigencia  (§12)
  recorded_at,                               # transacción (ya existe como ts)
  source, authority, confidence,             # procedencia
  trace_id, fuente, clase, origen            # YA EXISTE en AURA, se conserva
}
```

**Qué fuente puede crear qué** — esta tabla es el corazón de la propuesta:

| Fuente | Puede crear | Nunca puede crear |
|---|---|---|
| Declaración directa del usuario | **FACT** | — |
| Corrección del usuario | **FACT** (supersede) | — |
| Observación de AURA (patrón de uso) | EVIDENCE | FACT |
| Agente interno | PROPOSAL | FACT, EVIDENCE |
| Herramienta / documento / sistema externo | EVIDENCE | FACT |
| **Inferencia del LLM** | **PROPOSAL** | **FACT, EVIDENCE** |

`confidence` se admite **solo en `PROPOSAL`**. Un `FACT` no tiene confianza: o el usuario lo declaró o no es un
hecho. Ponerle un número a la verdad sobre una persona es la vía por la que un umbral acaba decidiendo quién es.

## 9 · Contradicciones

El caso del encargo, resuelto por el protocolo y no por el modelo:

```
t0  "Mi cumpleaños es el 10 de mayo"
    → FACT{ id: usuario.cumpleanos, value:"10 de mayo", version:1, status:ACTIVE,
            valid_from:t0, source:declaracion_usuario }

t1  "Mi cumpleaños es el 3 de junio"
    → el Core detecta MISMA IDENTIDAD (usuario.cumpleanos) y valor distinto
    → v1.status = SUPERSEDED, v1.valid_until = t1
    → FACT{ version:2, value:"3 de junio", supersedes:v1, status:ACTIVE }
```

No hay dos verdades simultáneas porque **la identidad es la misma y la vigencia no se solapa**. Hoy AURA ya acierta
el resultado —«gana la última declaración» `[LECT]`— pero **sin dejar historial ni vigencia**: el dato viejo
simplemente deja de aparecer.

**Contradicción sin declaración posterior** (dos fuentes distintas a la vez): el Core **no elige**. Marca
`CONFLICTED`, conserva ambas y **pregunta**. El LLM no desempata jamás; ni con confianza, ni con recencia, ni con
«parece más probable».

## 10 · Identidad de memoria

```
subject . attribute [ @scope ] : type
```

`usuario.cumpleanos`, `usuario.nombre`, `usuario.trabajo`, `abuela.profesion@tercero`

**Esto es lo que hoy falta.** `_atributo_declarado` extrae el atributo **del texto** («color favorito»), así que dos
formas de decir lo mismo son dos atributos distintos — es exactamente el fallo de canonicalización que H-2 mide al
0 % en multilingüe. La identidad canónica permite que «mi cumple», «mi fecha de nacimiento» y «my birthday» apunten
al mismo hecho **sin** que el LLM decida que son lo mismo: lo decide una tabla de alias, determinista y auditable.

**Compatibilidad:** `_atributo_preguntado` / `_atributo_declarado` **no se rompen ni se reemplazan**. Serían el
primer *resolver* de identidad, y la tabla de alias un segundo resolver detrás. El flujo y el punto de corte en
`on_turn` no cambian. `[INFER]`

## 11 · Temporalidad

**Sí, bi-temporal, pero mínima.** Dos campos, no un modelo completo:
- `valid_from` / `valid_until` — **cuándo fue cierto**
- `recorded_at` — **cuándo AURA lo supo** (ya existe como `ts`)

El caso «hoy me dice que su trabajo cambió ayer» necesita exactamente esto y nada más. Lo que **no** propongo para
v1: consultas retroactivas («¿qué creías el martes?»), porque no hay un solo caso de uso observado que las pida.
La bi-temporalidad completa de UMP (L2) es más de lo que AURA puede justificar hoy. `[INFER]`

## 12 · Olvido e invalidación

Cinco verbos distintos, y ninguno es sinónimo de otro:

| Verbo | Qué le pasa al dato | Auditoría | Contexto | ¿Reversible? |
|---|---|---|---|---|
| **SUPERSEDE** | sigue, como versión anterior | conserva ambas | la nueva versión | sí (declarar otra vez) |
| **INVALIDATE** | sigue, marcado no cierto (hoy: `refutada`) | conserva el motivo | se excluye | sí |
| **ARCHIVE** | sigue, fuera de recuperación (hoy: `HISTORICO`) | intacta | nunca | sí |
| **FORGET** | se elimina el **valor**; queda el hecho de que existió | **el registro de borrado permanece** | se excluye | **no** |
| **DELETE** | no existe como operación del protocolo | — | — | — |

**`DELETE` se rechaza a propósito.** Un borrado que no deja rastro hace imposible responder «¿por qué AURA ya no
sabe esto?», y convierte el borrado malicioso en indetectable. `FORGET` satisface la soberanía del usuario —el valor
desaparece— sin destruir la auditoría. Qué pasa con índices, embeddings y copias: es responsabilidad del **adapter**,
que debe declarar su garantía de borrado; el protocolo exige que la declare, no cómo la cumple. `[INFER]`

## 13 · Frontera de contexto (el problema medido de H-5)

Aquí está la pieza nueva, y es la que más importa:

```
MEMORY CORE                                    ModelProvider
  ├─ FACTS      ──┐                                 ▲
  ├─ EVIDENCE   ──┤                                 │
  ├─ EPISODICA  ──┤──► MEMORY CONTEXT BUILDER ──────┘
  └─ TERCEROS   ──┘         (única puerta)
```

**Responsabilidad del Context Builder:** decidir **qué** de la memoria entra en el prompt, **en qué forma** y **con
qué etiqueta**. Reglas propuestas:

| Qué | Entra en el prompt |
|---|---|
| FACT pertinente al atributo preguntado | **valor exacto**, nunca parafraseado |
| FACT no pertinente | **no entra** |
| EVIDENCE | solo si el turno la requiere, **marcada como no establecida** |
| Episódica sobre **terceros** | **nunca** |
| PROPOSAL | **nunca** |
| Memoria sensible | **nunca** sin autorización explícita |

Esto resuelve H-5 por construcción: el modelo no pudo repetir «mi abuela es enfermera» porque el Core lo
considerase un hecho —no lo hacía—, sino porque **el episodio viajó en el prompt**. Con una única puerta, eso se
decide en un sitio y se audita.

**No modifico el contrato `ModelProvider`,** y la propuesta no lo requiere: el Builder se sitúa **antes** de
`router.route`, en el mismo punto donde hoy se construye el prompt.

## 14 · Operaciones

De las diez propuestas, **seis son necesarias**; las otras son casos de las seis.

| Operación | Entrada | Salida | Autoridad | Idempotente |
|---|---|---|---|---|
| `MEMORY.GET` | identidad | hecho activo + versión | cualquiera con scope | sí |
| `MEMORY.SEARCH` | consulta, scope | coincidencias ordenadas | cualquiera con scope | sí |
| `MEMORY.PROPOSE` | evidencia, motivo, confianza | id de propuesta | **cualquier asesor** | no |
| `MEMORY.COMMIT` | propuesta o declaración | hecho `ACTIVE` + versión | **solo el Core** | sí (misma identidad y valor → no crea versión) |
| `MEMORY.SUPERSEDE` | identidad, valor nuevo | versión n+1 | **solo el Core** | sí |
| `MEMORY.REVOKE` | identidad, modo, motivo | estado nuevo | Core; **HITL si es FORGET** | sí |

**Por qué descarto las otras cuatro:** `CREATE` y `UPDATE` son `COMMIT` y `SUPERSEDE` con otro nombre —y nombrarlas
aparte invita a escribir sin versión—; `INVALIDATE`/`ARCHIVE` son modos de `REVOKE`; `RESTORE` es `COMMIT` de una
versión anterior; `AUDIT` **no es una operación de memoria**: es una consulta al registro forense que ya existe.
Toda operación emite su evento de auditoría; eso no se pide, se cumple.

## 15 · Multi-agente y almacenamiento

```
AGENTE ──► AMP-AURA ──► MEMORY CORE ──► MEMORY STORE ADAPTER ──► storage
   ✗ nunca: AGENTE ──► storage
```

Un agente interno solo alcanza `GET`, `SEARCH` y `PROPOSE`. **No tiene `COMMIT`.** Esto no es una restricción
nueva: es `G-1` (ruta única de mutación) y `ALERTA-005` aplicados a la memoria, y ya están probados con verificación
de mutación `[LECT]`.

**Qué pertenece al protocolo:** identidad, estados, versiones, vigencia, procedencia, autoridad, auditoría y el
formato de intercambio. **Qué pertenece al adapter:** índices, embeddings, transacciones, ranking, y **declarar su
garantía de borrado**. Si el adapter cambia de JSON a SQLite o a Qdrant, **ningún concepto del protocolo cambia** —es
la propiedad que UMP declara explícitamente y que AURA ya tiene a medias con `MemoryStore` + N1/N2.

## 16 · Recuperación y rendimiento

| Caso | Mecanismo | Coste | LLM |
|---|---|---|---|
| «¿Cuál es mi cumpleaños?» | `GET` por identidad | **O(1)** | **nunca** |
| «¿Qué sabes de mí?» | `SEARCH` por scope | O(n) del scope | nunca |
| «¿Qué hablamos del viaje?» | episódica | solapamiento | puede |
| paráfrasis no resuelta por alias | `SEARCH` semántica → **PROPOSAL** | embedding | como asesor |
| conocimiento general, razonamiento, consejo | no es memoria | — | sí |

**La regla de HC-1, no negociable:** si el Core conoce el valor, **no se llama al modelo**. Ya está demostrado
—0,00 s frente a 129 s `[EJEC]`— y el protocolo no puede introducir un diseño que lo pierda. Ninguna operación de
memoria básica puede depender de inferencia.

## 17 · Seguridad

| Amenaza | Defensa en AMP-AURA |
|---|---|
| **Memory poisoning** | El LLM solo alcanza `PROPOSE`. **Una escritura no basta** porque no hay escritura disponible para él |
| Memoria falsa por documento | Un documento crea EVIDENCE, nunca FACT (contra MemoryGraft) |
| Prompt injection → memoria | La cadena de autoridad no depende del texto: depende de la fuente registrada |
| Escalamiento de autoridad | `COMMIT` es exclusivo del Core; motor único con permisos y HITL rojo |
| Replay | `trace_id` + `recorded_at` + idempotencia por identidad-valor |
| Borrado malicioso | `FORGET` deja registro; `DELETE` no existe |
| Contaminación de contexto | Context Builder como única puerta (§13) |
| Memoria sobre terceros | `scope: tercero` + nunca al prompt + `SenalDeTercero` ya existente |

## 18 · Compatibilidad con AURA actual

**Lo que NO cambia:** el punto de corte en `on_turn` (líneas 1102-1106, antes de `recall` y de `router.route`);
`_responder_hecho`; `_atributo_preguntado` / `_atributo_declarado`; las 24/24; `ClaseSenal`; el motor único;
`MemoryStore`; la auditoría; `HISTORICO`; `_TERCERO`.

**Lo que se añadiría, por orden de valor y riesgo creciente:**

| # | Añadido | Riesgo | Depende de |
|---|---|---|---|
| 1 | `version` + `supersedes` en la procedencia | bajo: campo nuevo en un dict libre | nada |
| 2 | `valid_from` / `valid_until` | bajo | 1 |
| 3 | Identidad canónica + tabla de alias | medio: toca la resolución | 1 |
| 4 | `PROPOSAL` y `MEMORY.PROPOSE` | medio | 1, 3 |
| 5 | **Memory Context Builder** | **alto: toca la construcción del prompt** | 1–4 |
| 6 | Formato de intercambio e importación | bajo | 1–3 |

## 19 · Adoptar / adaptar / rechazar / inventar

**ADOPTAR** (de UMP, con atribución): el **vocabulario** (`kind`, `scope`, `lifecycle`, `relations`, `provenance`,
`consent`); **`revise` = supersede preservando historial**; **`forget` = tombstone con razón**; los **niveles de
conformidad L1/L2/L3** como forma de implementar por etapas; la **independencia explícita del almacenamiento**; y la
regla de seguridad **«nunca interpolar la memoria en el prompt»**.

**ADAPTAR:** la **bi-temporalidad** de UMP, reducida a tres campos; los **tres niveles de Letta**, pero con la
autoridad **fuera** del agente —AURA ya tiene el equivalente en episódica/semántica/histórico—; el **formato
markdown** de AMP, **solo como exportación legible**, nunca como autoridad; y el **`consent`** de UMP, que en AURA
debe ser *scope* de terceros, no permiso de exportación.

**RECHAZAR, con motivo:** **SAIHM** entero —anclaje en cadena pública y claves de wallet violan `D24`/`ADR-0001`—;
**el modelo de autoridad de Letta** —el agente edita su memoria: es H-1—; **AMP como autoridad** —markdown es
representación, no gobierno—; **`DELETE`** —sin rastro, indetectable—; **`confidence` en hechos** —un umbral no debe
decidir quién es alguien—; y **la búsqueda vectorial como vía de recuperación básica** —rompe la regla de HC-1.

**INVENTAR** (nadie lo resuelve, y AURA lo necesita): **`EVIDENCE` vs `PROPOSAL` vs `FACT`** con tabla de fuentes
autorizadas; **resolución de contradicciones sin LLM**, incluido `CONFLICTED` que pregunta en vez de elegir;
**`scope: tercero`** como clase de primer orden con prohibición de llegar al prompt; el **Memory Context Builder**
como única puerta; **`HISTORICO` no recuperable** (ya inventado y aprobado); y la **primacía del lookup
determinista** como requisito de protocolo, no como optimización.

## 20 · DECISION_REQUIRED

**D-AMP-1 · ¿Se adopta AMP-AURA como protocolo de memoria?** Tres opciones: (a) adoptarlo como marco y construirlo
por etapas; (b) adoptar **solo** los añadidos 1–3 (versión, vigencia, identidad) sin protocolo formal; (c) no
adoptar y seguir con el mecanismo actual.

**D-AMP-2 · ¿Se autoriza el Memory Context Builder?** Es la única pieza que toca la construcción del prompt y la
única que resuelve la contaminación medida en H-5. Requiere decisión propia porque concentra en un módulo lo que hoy
está disperso.

**D-AMP-3 · ¿`FORGET` sin `DELETE` es aceptable como política de soberanía?** El valor desaparece pero el registro
de que existió permanece. Es una decisión sobre el derecho del usuario, no técnica.

**D-AMP-4 · ¿Se admite que un asesor no determinista (embeddings o LLM) pueda `PROPOSE`?** Es lo que corrige el
0 % multilingüe de H-2, y es también la superficie que H-1 señala como peligrosa. La propuesta la acota a
`PROPOSAL`, nunca a `FACT`.

**D-AMP-5 · ¿Identidad canónica con tabla de alias?** Implica que «mi cumple» y «mi fecha de nacimiento» sean el
mismo hecho por decisión declarada en una tabla, no por semejanza semántica.

## 21 · Riesgos

| Riesgo | Mitigación propuesta |
|---|---|
| Sobre-ingeniería: un protocolo para un usuario | Etapas 1–3 son cuatro campos y una tabla; nada más es obligatorio |
| Romper lo que ya funciona | Ningún añadido toca el punto de corte ni las 24/24; se verifica con la batería existente |
| La tabla de alias no escala | Es la misma deuda que el DP de hechos declarados ya identificó; se decide por uso observado |
| Atarse a UMP | Solo se toma vocabulario y forma; sin dependencia de código |
| El Context Builder concentra poder | Por eso es `DECISION_REQUIRED` propio y necesitaría su propia verificación de mutación |
| Quedarse en el documento | Las etapas 1 y 2 son pequeñas y medibles: si en tres meses no se han hecho, la respuesta correcta es (c) |

## 22 · Siguiente misión propuesta (no iniciada)

**Etapas 1 y 2 solamente:** `version` + `supersedes` + `valid_from` + `valid_until` en la procedencia, con
historial de versiones consultable y el caso del cumpleaños demostrando que la versión 1 queda `SUPERSEDED` con su
vigencia cerrada, en lugar de desaparecer. Sin identidad canónica, sin `PROPOSE`, sin Context Builder. Es el
incremento más pequeño que hace real el §9 y deja medir si el protocolo aporta antes de construirlo entero.

---

## Las 20 preguntas del criterio de éxito, respondidas

1. **¿Qué es la memoria de AURA?** El conjunto gobernado de hechos, evidencias e historial con identidad,
   procedencia, versión y vigencia, bajo autoridad del Core.
2. **¿Qué NO es memoria?** El contexto de un turno, el buffer de diálogo, el prompt, una inferencia del LLM, una
   propuesta no aceptada y el backend.
3. **¿Quién tiene autoridad?** El Memory Core, y solo él, para `COMMIT`, `SUPERSEDE` y `REVOKE`. El usuario es la
   fuente suprema de sus propios hechos.
4. **¿Qué puede hacer el LLM?** `PROPOSE`. Leer el **valor exacto** que el Context Builder le entregue. Nunca
   crear, alterar ni elegir entre versiones.
5. **¿Qué puede hacer un agente?** `GET`, `SEARCH`, `PROPOSE`. Nunca `COMMIT`. Nunca tocar el storage.
6. **¿Cómo se crea una memoria?** Declaración del usuario → `EVIDENCE` → `COMMIT` del Core → `FACT ACTIVE v1`.
7. **¿Cómo se modifica?** No se modifica: se **supersede**. La versión anterior queda con `valid_until` cerrado.
8. **¿Cómo se contradice?** Misma identidad + valor distinto → supersesión con historial. Sin declaración
   posterior: `CONFLICTED`, y se pregunta.
9. **¿Cómo se invalida?** `REVOKE` en cuatro modos: `SUPERSEDE`, `INVALIDATE`, `ARCHIVE`, `FORGET`. `DELETE` no existe.
10. **¿Cómo se recupera?** `GET` por identidad, determinista y O(1), sin LLM. `SEARCH` para lo demás.
11. **¿Cómo se audita?** Cada operación emite su evento al registro forense que ya existe; la cadena
    identidad-versión-procedencia responde quién, por qué, de dónde, cuándo y qué reemplazó.
12. **¿Cómo se protege a terceros?** `scope: tercero`, filtro en la entrada (`SenalDeTercero`, ya existente) y
    prohibición absoluta de llegar al prompt.
13. **¿Cómo se separa contexto de memoria?** Con el Memory Context Builder como única puerta, y con reglas
    explícitas de qué entra.
14. **¿Cómo funciona sin LLM?** Como ya funciona hoy: identidad → hecho → plantilla determinista. 0 llamadas.
15. **¿Cómo funciona sin Qdrant?** Porque la recuperación básica es estructural. El vector es un asesor opcional
    detrás de un adapter.
16. **¿Cómo se exporta/importa?** Formato canónico de registros con su procedencia y versiones —JSON por
    coherencia con `exportar()` ya existente—, más una representación markdown legible.
17. **¿Cómo se recupera tras reinstalar?** Importando el formato canónico; ya está acreditado que el repositorio se
    reconstruye desde GitHub.
18. **¿Qué viene de protocolos existentes?** Vocabulario, `revise`/`forget`, niveles de conformidad e independencia
    de almacenamiento (UMP); la jerarquía de tipos (Letta, sin su autoridad); markdown como exportación (AMP).
19. **¿Qué es específico de AURA?** Evidencia/propuesta/hecho con fuentes autorizadas, contradicción sin LLM,
    terceros como clase de primer orden, histórico no recuperable, Context Builder y la primacía del determinismo.
20. **¿Qué requiere aprobación?** Las cinco decisiones de §20.
